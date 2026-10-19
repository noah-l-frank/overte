"""Original native protected profile acquisition; no ordinary login or verdict.

The private native origin must already be explicitly provisioned and match the
actual AccountManager endpoint. TLS trust and product account state are intact.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import re
import time
import uuid
from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.normal_ui import NativeUIError

VERSION=1
FILE='feature-account-probe.json'
ORIGIN_FILE='feature-account-origin.v1.json'
HEX='[0-9a-f]{32}'


def command(value,*,ios=False):
    exact(value,{'schemaVersion','commandId','action','operation','requestId','runId','ticket'})
    pattern=('ios-' if ios else '')+HEX
    need(type(ios) is bool and type(value['schemaVersion']) is int and value['schemaVersion']==1
         and value['action']=='feature-account-probe' and value['operation'] in ('read','release','inspect')
         and all(type(value[key]) is str and re.fullmatch(pattern,value[key]) for key in ('commandId','requestId'))
         and all(type(value[key]) is str and re.fullmatch(HEX,value[key]) for key in ('runId','ticket'))
         and ((value['commandId']==value['requestId'])==(value['operation']=='read')))
    return value


def sha(value):return type(value) is str and re.fullmatch('[0-9a-f]{64}',value) is not None


def validate(value,request,pid,epoch):
    ios=request['commandId'].startswith('ios-');command(request,ios=ios)
    exact(value,{'probeVersion','commandId','requestId','runId','ticket','operation','instance','sequence',
                 'processId','requestedEpochMs','capturedEpochMs','source'})
    need(type(value['probeVersion']) is int and value['probeVersion']==VERSION
         and all(value[key]==request[key] for key in ('commandId','requestId','runId','ticket','operation'))
         and type(value['instance']) is str and re.fullmatch(HEX,value['instance'])
         and integer(value['sequence'],1) and integer(pid,1) and integer(value['processId'],1) and value['processId']==pid
         and integer(value['requestedEpochMs'],1) and integer(value['capturedEpochMs'],1)
         and 0<=value['capturedEpochMs']-value['requestedEpochMs']<2000)
    fresh(value['capturedEpochMs'],epoch)
    source=value['source']
    if request['operation']=='read':
        exact(source,{'httpStatus','networkError','parsed','principalSha256','responseSha256','responseBytes',
                      'tokenAttached','credentialGeneration','endpointSha256','sentEpochMs','completedEpochMs'})
        need(type(source['httpStatus']) is int and source['httpStatus'] in (200,401)
             and integer(source['networkError'],0,499) and source['parsed'] is True and type(source['parsed']) is bool
             and all(sha(source[key]) for key in ('principalSha256','responseSha256','endpointSha256'))
             and integer(source['responseBytes'],1,4096) and type(source['tokenAttached']) is bool
             and integer(source['credentialGeneration'],1)
             and integer(source['sentEpochMs'],1) and integer(source['completedEpochMs'],1)
             and source['sentEpochMs']==value['requestedEpochMs']
             and source['sentEpochMs']<=source['completedEpochMs']<=value['capturedEpochMs'])
        if source['httpStatus']==200:need(source['networkError']==0 and source['tokenAttached'])
        else:need(source['networkError'] in (0,204) and source['principalSha256']==hashlib.sha256(b'').hexdigest())
    elif request['operation']=='release':
        exact(source,{'performed'});need(source['performed'] is True and type(source['performed']) is bool)
    else:
        exact(source,{'inflight','responseBytes','credentialBytes','released'})
        need(all(type(source[key]) is bool for key in ('inflight','released'))
             and integer(source['responseBytes'],0,4097) and integer(source['credentialBytes'],0,8192))
    return value


def protected_proof(native,proof,*,provider_instance,username):
    """Join actor-owned actual native response with original server request fact.

    Call only on an independently acquired actor source. Do not forward primary
    expectations or a primary observation into the journal as secondary facts.
    Provider epochs and native epochs are separate clock domains.
    """
    need(type(native) is dict and native.get('operation')=='read')
    request={key:native.get(key) for key in ('commandId','requestId','runId','ticket','operation')}
    request.update(schemaVersion=1,action='feature-account-probe')
    validate(native,request,native.get('processId'),native.get('capturedEpochMs'))
    exact(proof,{'providerVersion','instance','eventSequence','capturedEpochMs','kind','runId','ticket',
                 'requestId','status','principal','protectedAccess'})
    need(type(provider_instance) is str and re.fullmatch(HEX,provider_instance)
         and type(proof['providerVersion']) is int and proof['providerVersion']==2
         and proof['instance']==provider_instance and integer(proof['eventSequence'],1)
         and integer(proof['capturedEpochMs'],1) and proof['kind']=='profile-request'
         and all(proof[key]==native[key] for key in ('runId','ticket','requestId'))
         and native['operation']=='read' and type(username) is str and username=='e2e-'+native['runId'])
    source=native['source'];status=source['httpStatus']
    need(type(proof['status']) is int and proof['status']==status and type(proof['protectedAccess']) is bool
         and proof['principal'] in ('owned','anonymous') and proof['protectedAccess']==(status==200)
         and proof['principal']==('owned' if status==200 else 'anonymous')
         and source['principalSha256']==hashlib.sha256(username.encode() if status==200 else b'').hexdigest())
    return dict(principal=proof['principal'],protectedAccess=proof['protectedAccess'])


def bind_to_account(native,account):
    """Require a separately acquired later passive native account sample."""
    from adapters.native_account_observation import validate as account_observation
    need(type(native) is dict and native.get('operation')=='read' and type(account) is dict)
    request={key:native.get(key) for key in ('commandId','requestId','runId','ticket','operation')}
    request.update(schemaVersion=1,action='feature-account-probe')
    validate(native,request,native.get('processId'),native.get('capturedEpochMs'))
    observed=account.get('observation');need(type(observed) is dict)
    account_observation(account,observed.get('capturedEpochMs'))
    source=native['source']
    need(observed['instance']==native['instance'] and observed['credentialActive']
         and observed['credentialGeneration']==source['credentialGeneration']
         and observed['endpointSha256']==source['endpointSha256'] and observed['endpointPresent']
         and observed['tokenValid']==source['tokenAttached']
         and source['completedEpochMs']<=observed['capturedEpochMs']<=native['capturedEpochMs']+1500)
    if source['httpStatus']==200:need(account['principalSha256']==source['principalSha256'])
    return dict(loggedIn=account['loggedIn'],principalSha256=account['principalSha256'],
                loginPending=observed['loginPending'],refreshPending=observed['refreshPending'],
                protectedAccess=source['httpStatus']==200,profilePrincipalSha256=source['principalSha256'])


class NativeAccountProbe:
    def __init__(self,send,read,clock_ms,guard,pid,*,intent,ios=False,monotonic=time.monotonic,sleep=time.sleep):
        need(all(callable(v) for v in (send,read,clock_ms,guard,intent,monotonic,sleep)) and integer(pid,1) and type(ios) is bool)
        self.send,self.original,self.clock_ms,self.guard,self.pid=send,read,clock_ms,guard,pid
        self.intent,self.ios,self.monotonic,self.sleep=intent,ios,monotonic,sleep
        self.instance,self.sequence=None,0;self.captured=0

    def acquire(self,run,ticket):
        nonce=('ios-' if self.ios else '')+uuid.uuid4().hex
        request=dict(schemaVersion=1,commandId=nonce,action='feature-account-probe',operation='read',
                     requestId=nonce,runId=run,ticket=ticket)
        command(request,ios=self.ios)
        self.intent(deepcopy(request)) # Durable process-bound ownership before the actual network GET.
        return self._perform(request)

    def _perform(self,request):
        try:
            command(request,ios=self.ios);need(self.guard() is not False)
            started=previous=self.monotonic();need(number(started,0,1e15))
            requested=self.clock_ms();need(integer(requested,1))
            self.send(request) # Exactly one dispatch; only original-file reads are retried.
            for attempt in range(51):
                need(self.guard() is not False)
                raw=self.original()
                try:value=decode(raw) if raw else None
                except json.JSONDecodeError:value=None
                if type(value) is dict and value.get('commandId')==request['commandId']:
                    epoch=value.get('capturedEpochMs') if self.ios else self.clock_ms()
                    value=validate(value,request,self.pid,epoch)
                    need(self.instance in (None,value['instance']) and value['sequence']>self.sequence
                         and value['requestedEpochMs']>=self.captured
                         and (self.ios or value['requestedEpochMs']>=requested) and self.guard() is not False)
                    now=self.monotonic();need(number(now,0,1e15) and previous<=now and now-started<5)
                    self.instance,self.sequence=value['instance'],value['sequence'];self.captured=value['capturedEpochMs']
                    return value
                now=self.monotonic();need(number(now,0,1e15) and now>=previous);previous=now
                if now-started>=5 or attempt==50:break
                self.sleep(.1)
        except Exception:
            raise NativeUIError('Native protected account observation failed') from None
        raise NativeUIError('Native protected account observation is unavailable')

    def release(self,owned):
        command(owned,ios=self.ios);need(owned['operation']=='read')
        started=previous=self.monotonic();need(number(started,0,1e15))
        def budget():
            nonlocal previous
            now=self.monotonic();need(number(now,0,1e15) and previous<=now and now-started<5);previous=now
        def request(operation):
            value=deepcopy(owned);value.update(operation=operation,commandId=('ios-' if self.ios else '')+uuid.uuid4().hex)
            return self._perform(value)
        request('release');budget()
        for attempt in range(51):
            value=request('inspect');budget();source=value['source']
            if source==dict(inflight=False,responseBytes=0,credentialBytes=0,released=True):return value
            if attempt==50:break
            self.sleep(.05);budget()
        raise NativeUIError('Native protected account cleanup is incomplete')


class AccountProbeOwner:
    """One durable outstanding network intent, bound to the actual native session."""
    def __init__(self,store,binding,guard,*,ios=False,component_only=False):
        from adapters.normal_feature_state import context
        need(callable(guard) and type(ios) is bool and type(component_only) is bool)
        self.store,self.guard,self.ios,self.component_only=store,guard,ios,component_only
        self.binding=deepcopy(context(binding,component_only=component_only))

    def intent(self,request):
        need(self.guard() is not False and self.store.read() is None)
        command(request,ios=self.ios);need(request['operation']=='read')
        self.store.write(dict(ownershipVersion=1,binding=self.binding,probe=deepcopy(request)),None)

    def owned(self):
        from adapters.normal_feature_state import context
        need(self.guard() is not False)
        value=self.store.read();exact(value,{'ownershipVersion','binding','probe'})
        need(type(value['ownershipVersion']) is int and value['ownershipVersion']==1
             and context(value['binding'],component_only=self.component_only)==self.binding)
        command(value['probe'],ios=self.ios);need(value['probe']['operation']=='read')
        return value


class OwnedAccountProbe:
    def __init__(self,probe,owner):
        need(probe.intent==owner.intent)
        self.probe,self.owner=probe,owner

    def acquire(self,run,ticket):
        need(self.owner.store.read() is None)
        return self.probe.acquire(run,ticket)

    def release(self):
        before=self.owner.owned()
        value=self.probe.release(before['probe'])
        need(self.owner.guard() is not False)
        self.owner.store.discard(before)
        return value
