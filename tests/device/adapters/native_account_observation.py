"""Passive AccountManager state/history; no login verdict or network request."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import re
from adapters.native_feature_observation import need,integer,exact

VERSION=1
SIGNALS={'login-complete','login-failed','logout-complete','profile-changed','auth-endpoint-changed'}
REPLIES={'login-reply','refresh-reply','profile-reply'}
FIELDS={'accountVersion','instance','capturedEpochMs','credentialGeneration','credentialActive',
        'endpointPresent','endpointSha256','loginPending','refreshPending','tokenPresent','tokenValid',
        'refreshPresent','transportRejected','eventSequence','droppedEvents','events'}
BOOLEANS={'credentialActive','endpointPresent','loginPending','refreshPending','tokenPresent',
          'tokenValid','refreshPresent','transportRejected'}
EVENT_FIELDS={'sequence','capturedEpochMs','kind','credentialGeneration','hasReply','httpStatus',
              'networkError','transportRejected','timedOut'}


def validate(account,epoch,requested_epoch=None):
    """Reject absent/foreign history and contradictions; preserve original times."""
    exact(account,{'loggedIn','principalSha256','observation'})
    need(type(account['loggedIn']) is bool and type(account['principalSha256']) is str
         and re.fullmatch('[0-9a-f]{64}',account['principalSha256']) and integer(epoch,1)
         and (requested_epoch is None or integer(requested_epoch,1)))
    value=account.get('observation')
    exact(value,FIELDS)
    need(type(value['accountVersion']) is int and value['accountVersion']==VERSION
         and type(value['instance']) is str and re.fullmatch('[0-9a-f]{32}',value['instance'])
         and integer(value['capturedEpochMs'],1) and 0<=epoch-value['capturedEpochMs']<=1500
         and (requested_epoch is None or value['capturedEpochMs']>=requested_epoch)
         and integer(value['credentialGeneration'],1)
         and all(type(value[key]) is bool for key in BOOLEANS)
         and not (value['loginPending'] and value['refreshPending'])
         and (not value['tokenValid'] or value['tokenPresent'])
         and account['loggedIn']==(value['endpointPresent'] and value['tokenValid'])
         and type(value['endpointSha256']) is str and re.fullmatch('[0-9a-f]{64}',value['endpointSha256'])
         and (value['endpointPresent'] or value['endpointSha256']==hashlib.sha256(b'').hexdigest())
         and integer(value['eventSequence']) and integer(value['droppedEvents'])
         and type(value['events']) is list and len(value['events'])==min(64,value['eventSequence'])
         and value['droppedEvents']==value['eventSequence']-len(value['events']))
    previous_epoch=0;previous_generation=0
    for sequence,event in enumerate(value['events'],value['droppedEvents']+1):
        exact(event,EVENT_FIELDS)
        need(integer(event['sequence'],1) and event['sequence']==sequence
             and integer(event['capturedEpochMs'],1) and previous_epoch<=event['capturedEpochMs']<=value['capturedEpochMs']
             and integer(event['credentialGeneration'],1)
             and previous_generation<=event['credentialGeneration']<=value['credentialGeneration']
             and type(event['kind']) is str and event['kind'] in SIGNALS|REPLIES
             and all(type(event[key]) is bool for key in ('hasReply','transportRejected','timedOut'))
             and event['hasReply']==(event['kind'] in REPLIES)
             and integer(event['httpStatus'],0,599) and (event['httpStatus']==0 or event['httpStatus']>=100)
             and integer(event['networkError'],0,499))
        if not event['hasReply']:
            need(event['httpStatus']==event['networkError']==0 and not event['transportRejected'] and not event['timedOut'])
        previous_epoch=event['capturedEpochMs'];previous_generation=event['credentialGeneration']
    return value


def accept(previous,account):
    value=account['observation']
    if previous is not None:
        need(value['instance']==previous['instance'] and all(value[key]>=previous[key] for key in
             ('capturedEpochMs','credentialGeneration','eventSequence','droppedEvents')))
        old={event['sequence']:event for event in previous['events']}
        need(all(event['sequence'] not in old or event==old[event['sequence']] for event in value['events']))
        if value['credentialGeneration']==previous['credentialGeneration']:
            need(value['endpointSha256']==previous['endpointSha256'])
    return deepcopy(value)


def reply_after(account,kind,*,after_sequence,after_epoch,credential_generation):
    """Select original terminal reply only. HTTP 200 is not profile/UI success."""
    need(kind in REPLIES and integer(after_sequence) and integer(after_epoch,1) and integer(credential_generation,1))
    value=account['observation']
    rows=[event for event in value['events'] if event['kind']==kind and event['sequence']>after_sequence
          and event['capturedEpochMs']>=after_epoch and event['credentialGeneration']==credential_generation]
    need(len(rows)==1)
    return deepcopy(rows[0])
