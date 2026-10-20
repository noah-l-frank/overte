"""Original Phone Authentication acquisitions for the full journey owner.

Every sample creates and retires its own observer fixture/probe leases. Neither
an input acknowledgment nor a requested account outcome is accepted as facts.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import re
import time

from adapters.account_fixture_observation import DelayedGrantObservation,validate as validate_delayed
from adapters.native_account_origin import original_document,validate as validate_origin
from adapters.native_account_probe import bind_to_account,protected_proof,validate as validate_probe
from adapters.native_feature_observation import exact,fresh,integer,need,number,validate as validate_native
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.script_ui_inventory import validate as validate_inventory
from feature_journeys.contract import identifier,state as validate_state
from feature_journeys.witness import Client
from overte_phone_account_fixture import origin as fixture_origin
from overte_phone_login import validate as validate_login
from overte_phone_script_files import validate as validate_tablet
from overte_phone_script_history import pack,unpack,same
from overte_phone_script_lock import PhoneScriptSourceLock

VERSION=1
EMPTY=hashlib.sha256(b'').hexdigest()


def _native(reader,previous):
    """Restore source-owned last original histories, never a cached verdict."""
    if previous is None:return
    validate_native(previous,previous.get('requestId'),reader.pid,previous.get('capturedEpochMs'),require_account=True)
    need(re.fullmatch('[0-9a-f]{32}',previous['requestId']) is not None)
    if reader.instance is not None:
        need(reader.instance==previous['instance'] and previous['sequence']>reader.sequence
             and previous['capturedEpochMs']>=reader._authentication_epoch
             and all(previous['lifecycle'][key]>=reader.lifecycle[key] for key in reader.lifecycle))
    from adapters.native_account_observation import accept as accept_account
    account_history=accept_account(reader.account_history,previous['account'])
    recorded=previous['audio'].get('recordedVoice',{})
    voice_sequence=recorded.get('event',{}).get('eventSequence',0)
    need(voice_sequence>=reader.voice_event_sequence)
    if 'historyVersion' in recorded:
        from adapters.recorded_preview_history import accept_history
        voice_history=accept_history(reader.voice_history,recorded)
    else:need(reader.voice_history is None);voice_history=None
    animation=previous['animation']
    if 'history' in animation:
        from adapters.native_animation_history import accept
        animation_history=accept(reader.animation_history,animation['rigId'],animation['history'])
    else:need(reader.animation_history is None);animation_history=None
    reader.instance,reader.sequence=previous['instance'],previous['sequence']
    reader._authentication_epoch=previous['capturedEpochMs']
    reader.lifecycle=deepcopy(previous['lifecycle'])
    reader.account_history=account_history;reader.voice_event_sequence=voice_sequence
    reader.voice_history=voice_history;reader.animation_history=animation_history


def _ui(reader,previous,validator):
    if previous is None:return
    validator(previous,previous.get('commandId'),reader.pid,previous.get('capturedEpochMs'))
    reader.instance,reader.generation=previous['instance'],previous['generation']
    reader.sequence,reader.elapsed=previous['sourceSequence'],previous['elapsedMs']
    reader.last_command=previous['lastCommandSequence']
    reader.epoch_floor=previous['capturedEpochMs']


def measurement(run,ticket,origin,frame,*,provider_instance,native_epoch,host_epoch,after_epoch,actor):
    """Join originals after transport nonce/cursor validation by the owner."""
    identifier(run);identifier(ticket)
    exact(frame,{'nativeBefore','login','tablet','probe','originPresent','probeOwner','originOwner',
                 'probeReleased','originAbsent','nativeAfter','delayed','status','proof'})
    before,after=frame['nativeBefore'],frame['nativeAfter'];pid=after['processId']
    for packet,key in ((before,'requestId'),(after,'requestId'),(frame['login'],'commandId'),
                       (frame['tablet'],'commandId')):identifier(packet[key])
    validate_native(before,before.get('requestId'),pid,before['capturedEpochMs'],require_account=True)
    validate_native(after,after.get('requestId'),pid,native_epoch,require_account=True)
    need(after['requestId']!=before['requestId'] and after['instance']==before['instance'] and after['sequence']>before['sequence']
         and after['capturedEpochMs']>=before['capturedEpochMs'])
    from adapters.native_account_observation import accept
    accept(accept(None,before['account']),after['account'])
    need(all(after['lifecycle'][key]>=before['lifecycle'][key] for key in before['lifecycle']))
    account=after['account'];observed=account['observation'];old=before['account']
    need(all(account[key]==old[key] for key in ('loggedIn','principalSha256'))
         and all(observed[key]==old['observation'][key] for key in
            ('instance','credentialGeneration','endpointSha256','loginPending','refreshPending','tokenPresent','tokenValid','refreshPresent')))
    owned=hashlib.sha256(('e2e-'+run).encode()).hexdigest()
    need(account['principalSha256'] in (EMPTY,owned)
         and observed['endpointSha256'] in {hashlib.sha256(value.encode()).hexdigest() for value in (origin,origin+'/')})
    probe=frame['probe']
    request=dict(schemaVersion=1,action='feature-account-probe',**{key:probe[key] for key in
        ('commandId','requestId','runId','ticket','operation')})
    validate_probe(probe,request,pid,native_epoch)
    need(probe['runId']==run and probe['ticket']==ticket)
    probe_owner=frame['probeOwner']
    exact(probe_owner,{'ownershipVersion','binding','probe'})
    need(type(probe_owner['ownershipVersion']) is int and probe_owner['ownershipVersion']==1
         and same(probe_owner['probe'],request))
    context(probe_owner['binding'])
    bound=bind_to_account(probe,account)
    if actor:
        protected_proof(probe,frame['proof'],provider_instance=provider_instance,username='e2e-'+run)
        fresh(frame['proof']['capturedEpochMs'],host_epoch)
    else:need(frame['proof'] is None)
    login,tablet=frame['login'],frame['tablet']
    validate_login(login,login['commandId'],pid,native_epoch)
    validate_tablet(tablet,tablet['commandId'],pid,native_epoch)
    inventory=tablet.get('scriptInventory');validate_inventory(inventory);need(inventory['complete'])
    pages=[row for row in login['controls'] if row['id']=='login.page'];need(len(pages)<=1)
    page=pages[0] if pages else None
    if page is not None:
        need(not page['domain'] and page['accountInstance']==observed['instance']
             and page['credentialGeneration']==observed['credentialGeneration']
             and page['endpointSha256']==observed['endpointSha256']
             and page['nativePending']==observed['loginPending'] and page['tokenPresent']==observed['tokenPresent'])
    origin_owner=frame['originOwner']
    exact(origin_owner,{'ownershipVersion','binding','instance','data'})
    exact(origin_owner['data'],{'runId','ownerToken','origin'})
    need(type(origin_owner['ownershipVersion']) is int and origin_owner['ownershipVersion']==1
         and same(context(origin_owner['binding']),probe_owner['binding'])
         and origin_owner['binding']['processIdentity'].split(':')[0]==str(pid))
    need(origin_owner['data']['runId']==run and origin_owner['data']['origin']==origin
         and origin_owner['instance']==after['instance'])
    present,absent=frame['originPresent'],frame['originAbsent']
    for packet in (present,absent):
        command=dict(schemaVersion=1,commandId=packet['commandId'],action='feature-account-origin',operation='observe',
            runId=run,ownerToken=origin_owner['data']['ownerToken'],instance=after['instance'])
        validate_origin(packet,command,pid,packet['capturedEpochMs'])
    need(present['source']['originExists'] and present['source']['ownerExists'] and not present['source']['retired']
         and base64.b64decode(present['source']['originBase64'],validate=True)==original_document(run,origin)
         and absent['sequence']>present['sequence'] and absent['capturedEpochMs']>=present['capturedEpochMs']
         and absent['source']['retired'] and not absent['source']['originExists'] and not absent['source']['ownerExists'])
    released=frame['probeReleased']
    command=dict(request,operation='inspect',commandId=released['commandId'])
    validate_probe(released,command,pid,native_epoch)
    need(released['instance']==probe['instance'] and released['sequence']>probe['sequence']
         and released['source']==dict(inflight=False,responseBytes=0,credentialBytes=0,released=True))
    delayed=frame['delayed'];validate_delayed(delayed,run)
    need(delayed['instance']==provider_instance);fresh(delayed['capturedEpochMs'],host_epoch)
    status=frame['status']
    exact(status,{'providerVersion','instance','runId','capturedEpochMs','eventSequence','accountExists',
        'heldRequests','armedHold','inflightRequests','accessTokens','refreshTokens','grantsEnabled'})
    need(type(status['providerVersion']) is int and status['providerVersion']==2 and status['instance']==provider_instance
         and status['runId']==run and all(type(status[key]) is bool for key in ('accountExists','armedHold','grantsEnabled'))
         and all(integer(status[key]) for key in ('capturedEpochMs','eventSequence','heldRequests','inflightRequests','accessTokens','refreshTokens')))
    fresh(status['capturedEpochMs'],host_epoch)
    need(status['capturedEpochMs']>=delayed['capturedEpochMs'] and status['eventSequence']>=delayed['eventSequence']
         and status['heldRequests']<=1 and status['inflightRequests']<=16
         and status['accessTokens']<=64 and status['refreshTokens']<=64)
    if actor:need(status['eventSequence']>=frame['proof']['eventSequence']
                  and status['capturedEpochMs']>=frame['proof']['capturedEpochMs'])
    clocks=[before['capturedEpochMs'],after['capturedEpochMs'],login['capturedEpochMs'],tablet['capturedEpochMs'],probe['capturedEpochMs'],present['capturedEpochMs'],
            released['capturedEpochMs'],absent['capturedEpochMs']]
    need(integer(after_epoch,1) and min(clocks)>=after_epoch and max(clocks)-min(clocks)<=1500)
    fresh(min(clocks),native_epoch)
    state=dict(principal='owned' if bound['loggedIn'] else 'anonymous',dialog=page is not None,
        error=page['error'] if page is not None else 'none',pending=bound['loginPending'],
        protectedAccess=bound['protectedAccess'],delayedGrantOutstanding=delayed['delayedGrantOutstanding'])
    if bound['loggedIn']:need(account['principalSha256']==owned)
    validate_state('authentication',state,run)
    resources=[]
    if page is not None:resources.append('panel:account-dialog')
    if inventory['tabletShown']:resources.append('panel:account-tablet')
    if observed['tokenPresent'] or observed['refreshPresent']:resources.append('connection:account-session')
    if observed['loginPending'] or observed['refreshPending']:resources.append('connection:account-request')
    if status['accessTokens'] or status['refreshTokens']:resources.append('connection:remote-account-authority')
    return deepcopy(dict(state=state,resources=sorted(resources),lifecycle=after['lifecycle'],capturedEpochMs=min(clocks)))


class PhoneAuthenticationSamples:
    """A role/process ledger. A pending acquisition cannot be reset by recreation."""
    def __init__(self,adapter,selector,client,run,provider_instance,role,stage,lock,*,epoch_ms=lambda:int(time.time()*1000),
                 monotonic=time.monotonic):
        need(isinstance(client,Client) and role in ('primary','actor') and type(stage) is int and 0<=stage<=3
             and isinstance(lock,PhoneScriptSourceLock) and callable(epoch_ms) and callable(monotonic))
        identifier(run);identifier(provider_instance)
        need(getattr(client,'run',None)==run and getattr(client,'area',None)=='authentication'
             and getattr(client,'account_instance',None)==provider_instance)
        self.adapter,self.selector,self.client,self.run,self.role=adapter,selector,client,run,role
        self.provider_instance,self.stage,self.lock,self.epoch_ms=provider_instance,stage,lock,epoch_ms
        self.monotonic=monotonic
        self.origin=fixture_origin(client.url)
        path=adapter.state_path(selector)
        self.store=PrivateFeatureState(path.with_name('phone-authentication-'+role+'-'+str(stage)+'-samples.json'))
        need(lock.path==path.with_name('phone-script-sources.lock'));lock.assert_held()
        _ui,_service,binding,guard,_installed=adapter.normal_feature_runtime(selector,read_only=True)
        self.guard=guard
        self.previous=self.store.read()
        self.state=dict(binding=deepcopy(context(binding)),phase='ready',sequence=0,native=None,login=None,
                        tablet=None,probe=None,origin=None,delayed=None,status=None,pending=None,frame=None)
        if self.previous is not None:
            old=self._decode(self.previous)
            need(same(old['binding'],self.state['binding']) and old['phase']=='ready')
            self.state=old
        if self.state['status'] is not None:
            client.account_epoch=max(client.account_epoch,self.state['status']['capturedEpochMs'])
            client.account_sequence=max(client.account_sequence,self.state['status']['eventSequence'])

    def _decode(self,value):
        exact(value,{'authenticationSamplesVersion','runId','role','stage','providerInstance','fixtureUrl','payload'})
        need(type(value['authenticationSamplesVersion']) is int and value['authenticationSamplesVersion']==VERSION
             and value['runId']==self.run and value['role']==self.role and type(value['stage']) is int and value['stage']==self.stage
             and value['providerInstance']==self.provider_instance and value['fixtureUrl']==self.client.url)
        rows=unpack(value['payload']);need(len(rows)==1);state=rows[0]
        exact(state,set(self.state));context(state['binding'])
        need(state['phase'] in ('ready','reading') and integer(state['sequence'],0,1000000000))
        if state['phase']=='ready':
            need(state['pending'] is None)
            if state['sequence']==0:need(all(state[key] is None for key in
                ('native','login','tablet','probe','origin','delayed','status','frame')))
            else:
                frame=state['frame'];need(type(frame) is dict)
                for cursor,source in (('native','nativeAfter'),('login','login'),('tablet','tablet'),
                                     ('probe','probeReleased'),('origin','originAbsent'),('delayed','delayed'),('status','status')):
                    need(same(state[cursor],frame[source]))
                need(same(frame['originOwner']['binding'],state['binding']))
                measurement(self.run,frame['probe']['ticket'],self.origin,frame,provider_instance=self.provider_instance,
                    native_epoch=frame['nativeAfter']['capturedEpochMs'],host_epoch=frame['status']['capturedEpochMs'],
                    after_epoch=1,actor=self.role=='actor')
        return state

    def save(self):
        self.lock.assert_held();need(same(self.store.read(),self.previous))
        value=dict(authenticationSamplesVersion=VERSION,runId=self.run,role=self.role,stage=self.stage,
            providerInstance=self.provider_instance,fixtureUrl=self.client.url,payload=pack([self.state]))
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)

    def read(self,ticket,after_epoch):
        identifier(ticket);need(integer(after_epoch,1));self.lock.assert_held()
        need(self.state['phase']=='ready' and self.state['sequence']<1000000000)
        self.state.update(phase='reading',pending=dict(ticket=ticket,probeOwner=None,originOwner=None));self.save()
        started=previous=self.monotonic()
        need(number(started,0,1e15))
        def bound():
            nonlocal previous
            self.lock.assert_held();need(self.guard() is not False)
            now=self.monotonic();need(number(now,0,1e15) and previous<=now and now-started<20);previous=now
        with self.adapter.existing_input_session(self.selector):
            origin=self.adapter._account_origin(self.selector)
            native=self.adapter._native_feature_observer(self.selector,read_only=True)
            _native(native,self.state['native'])
            admission=origin.native_admission
            if self.state['native'] is not None:
                old=self.state['native']
                need(admission['instance']==old['instance'] and admission['sequence']>old['sequence']
                     and admission['capturedEpochMs']>=old['capturedEpochMs'])
            _native(native,admission);self.state['native']=deepcopy(admission);self.save();bound()
            before=native.read(native.sequence,require_account=True)
            owned=hashlib.sha256(('e2e-'+self.run).encode()).hexdigest();account=before['account']
            need(account['principalSha256'] in (EMPTY,owned) and (not account['observation']['tokenPresent'] or account['principalSha256']==owned))
            need(account['observation']['endpointSha256'] in {hashlib.sha256(text.encode()).hexdigest() for text in (self.origin,self.origin+'/')})
            if self.state['origin'] is not None:
                origin.source.sequence=self.state['origin']['sequence'];origin.source.captured=self.state['origin']['capturedEpochMs']
            origin.stage(self.run,self.origin)
            owner=origin.owned();self.state['pending']['originOwner']=deepcopy(owner);self.save();bound()
            present=origin.source.request(owner['data'],'observe')
            login=self.adapter._login_controls(self.selector,lambda *_args:need(False),self.run,self.origin,read_only=True).io
            _ui(login,self.state['login'],validate_login);ui=login.capture();bound()
            probe=self.adapter._account_probe(self.selector,read_only=True,role=self.role)
            if self.state['probe'] is not None:
                old=self.state['probe'];probe.probe.instance=old['instance'];probe.probe.sequence=old['sequence'];probe.probe.captured=old['capturedEpochMs']
            response=probe.acquire(self.run,ticket)
            self.state['pending']['probeOwner']=deepcopy(probe.owner.owned());self.save();bound()
            tablet=self.adapter._script_file_io(self.selector,read_only=True)
            _ui(tablet,self.state['tablet'],validate_tablet);tabs=tablet.capture();bound()
            if self.state['tablet'] is not None:need(tabs['capturedEpochMs']>=self.state['tablet']['capturedEpochMs'])
            proof=self.client.request('/runs/'+self.run+'/account/proof/'+ticket+'/'+response['requestId']) if self.role=='actor' else None
            released=probe.release();self.state['probe']=deepcopy(released);self.save();bound()
            origin.release()
            absent=origin.source.request(owner['data'],'observe');self.state['origin']=deepcopy(absent);self.save();bound()
            after=native.read(native.sequence,require_account=True);bound()
            delayed=self.client.request('/runs/'+self.run+'/account/delayed')
            accepted=DelayedGrantObservation(self.run,self.provider_instance)
            if self.state['delayed'] is not None:accepted.accept(self.state['delayed'])
            accepted.accept(delayed)
            status=self.client.account_status();bound()
            frame=dict(nativeBefore=before,login=ui,tablet=tabs,probe=response,originPresent=present,
                probeOwner=self.state['pending']['probeOwner'],originOwner=owner,probeReleased=released,
                originAbsent=absent,nativeAfter=after,delayed=delayed,status=status,proof=proof)
            actual=measurement(self.run,ticket,self.origin,frame,provider_instance=self.provider_instance,
                native_epoch=native.clock_ms(),host_epoch=self.epoch_ms(),after_epoch=after_epoch,actor=self.role=='actor')
            self.state.update(phase='ready',sequence=self.state['sequence']+1,native=deepcopy(after),login=deepcopy(ui),
                tablet=deepcopy(tabs),delayed=deepcopy(delayed),status=deepcopy(status),pending=None,frame=frame)
            self.save();bound()
            return deepcopy(dict(sequence=self.state['sequence'],**actual))
