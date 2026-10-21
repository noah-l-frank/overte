"""Normal Authentication input causality from original native/HTTP events."""
# Derived from frozen Phone source fe4684bf46585088370b3a328a738f147e670b97.
# iOS transport, menu/login source and original clock admission are platform-owned.
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import time

from adapters.account_fixture_observation import validate as validate_delayed
from adapters.native_account_observation import accept
from adapters.native_feature_observation import NativeFeatureObservation,integer,need,number,validate
from adapters.normal_ui import NativeUIError
from ios.adapters.login_source import nonce as source_nonce
from feature_journeys.contract import arguments,identifier
from ios.adapters.authentication_origin import origin as fixture_origin

VERSION=1
EMPTY=hashlib.sha256(b'').hexdigest()


class AuthenticationReadinessPending(NativeUIError):
    """Only a missing original terminal event/readiness may be polled."""


def check(call,before,current,epoch,*,delayed=None,provider_instance=None):
    """A delivery ACK cannot manufacture a login, logout or retired response."""
    arguments('feature.authentication.act',call)
    need(call['verb']!='restart-app') # Requires a separate explicit process boundary.
    for packet in (before,current):
        source_nonce(packet['requestId'])
        validate(packet,packet['requestId'],before['processId'],epoch if packet is current else packet['capturedEpochMs'],require_account=True)
    need(current['requestId']!=before['requestId'] and current['instance']==before['instance']
         and current['sequence']>before['sequence'] and current['capturedEpochMs']>=before['capturedEpochMs']
         and all(current['lifecycle'][key]>=before['lifecycle'][key] for key in before['lifecycle']))
    old,new=before['account'],current['account'];previous,observed=old['observation'],new['observation']
    accept(accept(None,old),new)
    origin=fixture_origin(call['fixtureUrl'].split('/runs/',1)[0])
    endpoints={hashlib.sha256(value.encode()).hexdigest() for value in (origin,origin+'/')}
    owned=hashlib.sha256(('e2e-'+call['runId']).encode()).hexdigest()
    need(all(value['observation']['credentialActive'] and value['observation']['endpointPresent']
             and value['observation']['endpointSha256'] in endpoints and value['principalSha256'] in (EMPTY,owned)
             for value in (old,new)))
    # A new cursor must retain the original history. Dropped barrier events
    # cannot establish a unique new request completion either.
    need(observed['droppedEvents']<=previous['eventSequence'])
    added=[event for event in observed['events'] if event['sequence']>previous['eventSequence']]
    need(all(event['capturedEpochMs']>=before['capturedEpochMs'] for event in added))
    replies=[event for event in added if event['kind']=='login-reply']
    logouts=[event for event in added if event['kind']=='logout-complete']
    verb=call['verb']
    if verb=='login-submit':
        need(not previous['loginPending'] and not previous['refreshPending'] and not previous['tokenPresent']
             and not old['loggedIn'] and not logouts and len(replies)<=1)
        if call['inputs']['account']=='delayed':
            need(provider_instance is not None);identifier(provider_instance)
            validate_delayed(delayed,call['runId']);need(delayed['instance']==provider_instance and not replies)
            rows=[row for row in delayed['requests'] if row['requestTicket']==call['ticket']]
            need(len(rows)<=1)
            if not rows or not observed['loginPending']:
                raise AuthenticationReadinessPending('Original held login request is not ready')
            need(rows[0]['state']=='held' and rows[0]['status']==0 and not new['loggedIn']
                 and not observed['tokenPresent'] and not observed['refreshPresent']
                 and observed['credentialGeneration']>previous['credentialGeneration'])
            return deepcopy(dict(native=current,delayed=delayed))
        need(delayed is None)
        if not replies or observed['loginPending'] or observed['refreshPending']:
            raise AuthenticationReadinessPending('Original terminal login reply is not ready')
        reply=replies[0]
        need(previous['credentialGeneration']<reply['credentialGeneration']==observed['credentialGeneration'])
        # Profile adoption is asynchronous after the actual grant. Do not let
        # the protected source read an incomplete cached principal as identity.
        if observed['tokenPresent'] and new['principalSha256']==EMPTY:
            raise AuthenticationReadinessPending('Original account profile has not loaded')
    elif verb=='logout':
        need(old['loggedIn'] and old['principalSha256']==owned and not replies and len(logouts)<=1)
        if not logouts:raise AuthenticationReadinessPending('Original logout signal is not ready')
        need(logouts[0]['credentialGeneration']==observed['credentialGeneration']
             and observed['credentialGeneration']>previous['credentialGeneration']
             and not new['loggedIn'] and new['principalSha256']==EMPTY
             and not any(observed[key] for key in ('loginPending','refreshPending','tokenPresent','tokenValid','refreshPresent')))
    else:
        need(verb in ('login-open','login-cancel','release-stale-response') and not replies and not logouts
             and old['loggedIn']==new['loggedIn'] and old['principalSha256']==new['principalSha256']
             and all(previous[key]==observed[key] for key in
                 ('credentialGeneration','loginPending','refreshPending','tokenPresent','tokenValid','refreshPresent')))
    return deepcopy(dict(native=current,delayed=None))


def wait(call,before,reader,*,provider=None,monotonic=time.monotonic,sleep=time.sleep,record=None,
         epoch_ms=lambda:int(time.time()*1000)):
    need(isinstance(reader,NativeFeatureObservation) and all(callable(value) for value in (monotonic,sleep,record,epoch_ms)))
    started=previous=monotonic();need(number(started,0,1e15))
    for attempt in range(64):
        current=reader.read(reader.sequence,require_account=True)
        delayed=None;instance=None
        if call['verb']=='login-submit' and call['inputs']['account']=='delayed':
            need(provider is not None);instance=provider.account_instance
            delayed=provider.request('/runs/'+call['runId']+'/account/delayed')
            # Host/native clocks remain independent and neither may be retimed.
            from adapters.native_feature_observation import fresh
            fresh(delayed['capturedEpochMs'],epoch_ms())
        record(deepcopy(dict(native=current,delayed=delayed)))
        now=monotonic();need(number(now,0,1e15) and previous<=now and now-started<20);previous=now
        try:return check(call,before,current,reader.clock_ms(),delayed=delayed,provider_instance=instance)
        except AuthenticationReadinessPending:
            need(attempt<63);sleep(.25)
    raise NativeUIError('Original Authentication readiness did not settle')
