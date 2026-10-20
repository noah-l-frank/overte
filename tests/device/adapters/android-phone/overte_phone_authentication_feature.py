"""Phone Authentication run attachment and original fixture-phase observations.

This module never registers/activates a run or substitutes requested outcomes
for measured account state. The full feature owner is composed on this source.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import math
import time

from adapters.native_feature_observation import exact,integer,need,number,validate as validate_native
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from feature_journeys.contract import arguments,identifier,result
from feature_journeys.scenarios import VERSION as CONTRACT_VERSION
from feature_journeys.witness import Client,projection
from overte_phone_account_fixture import origin as fixture_origin
from overte_phone_authentication import PhoneAuthenticationSamples,provider_status,measurement
from overte_phone_authentication_causality import check as causal
from overte_phone_script_history import pack,unpack,same
from overte_phone_script_lock import PhoneScriptSourceLock

FIXTURE_READER_VERSION=1
VERSION=1


class AuthenticationPhasePending(NativeUIError):
    """An independent actor must wait for the existing input/phase transaction."""


class AuthenticationRunRetired(AuthenticationPhasePending):
    def __init__(self,status):
        super().__init__('Owned Authentication fixture run has retired')
        self.status=deepcopy(status)


class AuthenticationFixtureReader:
    def __init__(self,client,run,*,epoch_ms=lambda:int(time.time()*1000)):
        identifier(run);need(isinstance(client,Client) and callable(epoch_ms))
        fixture_origin(client.url)
        need(getattr(client,'run',None) in (None,run) and getattr(client,'area',None) in (None,'authentication')
             and getattr(client,'closed',False) is False)
        self.client,self.run,self.epoch_ms=client,run,epoch_ms
        self.fixture_url=client.url+'/runs/'+run+'/'
        self.instance=getattr(client,'account_instance',None)
        if self.instance is not None:identifier(self.instance)
        self.last_clock=None

    def clock(self):
        current=self.epoch_ms();need(number(current,1,1e15) and (self.last_clock is None or current>=self.last_clock))
        self.last_clock=current;return current

    def active(self,value):
        exact(value,{'schemaVersion','runId','area','ticket','stimulus'})
        need(type(value['schemaVersion']) is int and value['schemaVersion']==1
             and value['runId']==self.run and value['area']=='authentication')
        identifier(value['ticket']);exact(value['stimulus'],{'verb','inputs'})
        if value['stimulus']['verb'] in ('baseline','cleanup'):need(value['stimulus']['inputs']=={})
        else:arguments('feature.authentication.act',dict(contractVersion=CONTRACT_VERSION,runId=self.run,
            fixtureUrl=self.fixture_url,ticket=value['ticket'],**value['stimulus']))
        return value

    def attach(self):
        need(getattr(self.client,'run',None) in (None,self.run)
             and getattr(self.client,'area',None) in (None,'authentication')
             and getattr(self.client,'closed',False) is False
             and integer(getattr(self.client,'account_epoch',0)) and integer(getattr(self.client,'account_sequence',0)))
        prior_instance=getattr(self.client,'account_instance',None)
        if prior_instance is not None:identifier(prior_instance)
        if self.instance is not None:need(prior_instance==self.instance)
        provider=self.client.request('/account-provider')
        exact(provider,{'providerVersion','instance','transport','tlsVersion','internalErrors'})
        need(type(provider['providerVersion']) is int and provider['providerVersion']==2
             and provider['transport']=='https' and provider['tlsVersion'] in ('TLSv1.2','TLSv1.3')
             and type(provider['internalErrors']) is int and provider['internalErrors']==0)
        identifier(provider['instance']);need(self.instance in (None,provider['instance']) and prior_instance in (None,provider['instance']))
        self.instance=provider['instance']
        # Attach metadata to this role's credentialed existing Client only.
        # Client.register/activate/credentials/control are never called here.
        self.client.run,self.client.area=self.run,'authentication'
        self.client.account_instance=self.instance
        self.client.account_epoch=getattr(self.client,'account_epoch',0)
        self.client.account_sequence=getattr(self.client,'account_sequence',0)
        self.client.closed=getattr(self.client,'closed',False)

    def read(self,previous=None):
        self.attach()
        if previous is not None:
            provider_status(previous,self.run,self.instance,previous['capturedEpochMs'])
            self.client.account_epoch=max(self.client.account_epoch,previous['capturedEpochMs'])
            self.client.account_sequence=max(self.client.account_sequence,previous['eventSequence'])
        status=self.client.account_status();provider_status(status,self.run,self.instance,int(self.clock()))
        if not status['accountExists']:
            need(not status['grantsEnabled'] and not status['armedHold']
                 and not any(status[key] for key in ('heldRequests','inflightRequests','accessTokens','refreshTokens')))
            raise AuthenticationRunRetired(status)
        active=deepcopy(self.active(self.client.request('/runs/'+self.run+'/active')))
        original=self.client.observe()
        exact(original,{'schemaVersion','runId','area','ticket','sampleEpochMs','entries'})
        need(type(original['schemaVersion']) is int and original['schemaVersion']==1 and original['runId']==self.run
             and original['area']=='authentication' and type(original['entries']) is list and len(original['entries'])<=512
             and number(original['sampleEpochMs'],1,1e15)
             and -250<=self.clock()-original['sampleEpochMs']<=1500)
        identifier(original['ticket'])
        if original['ticket']!=active['ticket']:
            raise AuthenticationPhasePending('Original Authentication fixture phase changed during its read')
        # This is a fresh original host read barrier, not an activation time or
        # measured product state. Native acquisition must follow it.
        return deepcopy(dict(ticket=active['ticket'],verb=active['stimulus']['verb'],inputs=active['stimulus']['inputs'],
            afterEpochMs=math.ceil(original['sampleEpochMs']),status=status))


class PhoneAuthenticationFeature:
    """One full-area owner; all returned fields still come from fresh sources."""
    def __init__(self,adapter,selector,source,*,role='primary',monotonic=time.monotonic,sleep=time.sleep):
        need(isinstance(source,AuthenticationFixtureReader) and role in ('primary','actor')
             and callable(monotonic) and callable(sleep))
        self.adapter,self.selector,self.source,self.role=adapter,selector,source,role
        self.run,self.fixture_url=source.run,source.fixture_url
        self.monotonic,self.sleep=monotonic,sleep
        path=adapter.state_path(selector)
        self.store=PrivateFeatureState(path.with_name('phone-authentication-feature.json'))
        self.role_store=PrivateFeatureState(path.with_name('phone-authentication-'+role+'-feature.json'))
        self.retirement_store=PrivateFeatureState(path.with_name('phone-authentication-retirement.json'))
        self.lock=PhoneScriptSourceLock(path.with_name('phone-script-sources.lock'))

    def _read(self,store,kind):
        value=store.read()
        if value is None:return None
        exact(value,{'authenticationFeatureVersion','kind','runId','fixtureUrl','payload'})
        need(type(value['authenticationFeatureVersion']) is int and value['authenticationFeatureVersion']==VERSION
             and value['kind']==kind and value['runId']==self.run and value['fixtureUrl']==self.fixture_url)
        rows=unpack(value['payload']);need(len(rows)==1);return rows[0]

    def _save(self,store,kind,state):
        self.lock.assert_held();self._read(store,kind)
        old=store.read();value=dict(authenticationFeatureVersion=VERSION,kind=kind,runId=self.run,
            fixtureUrl=self.fixture_url,payload=pack([state]))
        store.write(value,old);need(same(store.read(),value))

    def control(self):
        state=self._read(self.store,'owner')
        if state is not None:
            exact(state,{'phase','stage','binding','ticket','arguments','backend','cleanupIntents','cleanupProof'})
            need(state['phase'] in ('preparing','baseline','acting','active','cleaning','cleaned')
                 and integer(state['stage'],0,3) and type(state['cleanupIntents']) is list and len(state['cleanupIntents'])<=32
                 and type(state['cleanupProof']) is list and len(state['cleanupProof'])<=64)
            if state['binding'] is not None:context(state['binding'])
            if state['ticket'] is not None:identifier(state['ticket'])
            if state['arguments'] is not None:
                call=arguments('feature.authentication.act',state['arguments'])
                need(call['runId']==self.run and call['fixtureUrl']==self.fixture_url and call['ticket']==state['ticket'])
        return state

    def role_state(self,role=None):
        role=self.role if role is None else role;need(role in ('primary','actor'))
        store=PrivateFeatureState(self.store.path.with_name('phone-authentication-'+role+'-feature.json'))
        state=self._read(store,role)
        if state is None:return dict(phase='ready',sequence=0,stage=0,capturedEpochMs=0,backend=None,last=None,restarts=[])
        exact(state,{'phase','sequence','stage','capturedEpochMs','backend','last','restarts'})
        need(state['phase'] in ('ready','reading','retired') and integer(state['sequence'],0,1000000000)
             and integer(state['stage'],0,3) and integer(state['capturedEpochMs'])
             and type(state['restarts']) is list and len(state['restarts'])==state['stage'])
        if state['backend'] is not None:
            provider_status(state['backend'],self.run,state['backend']['instance'],state['backend']['capturedEpochMs'])
        last=state['last']
        if last is not None:
            exact(last,{'stage','ticket','frame'});identifier(last['ticket']);need(integer(last['stage'],0,state['stage']))
            frame=last['frame'];need(frame['probe']['ticket']==last['ticket'])
            measurement(self.run,last['ticket'],fixture_origin(self.source.client.url),frame,
                provider_instance=state['backend']['instance'],native_epoch=frame['nativeAfter']['capturedEpochMs'],
                host_epoch=frame['status']['capturedEpochMs'],after_epoch=1,actor=role=='actor')
        from adapters.native_process_presence import validate as validate_exit
        for index,transfer in enumerate(state['restarts']):
            exact(transfer,{'oldStage','oldBinding','oldFrame','newBinding','exit'})
            need(type(transfer['oldStage']) is int and transfer['oldStage']==index)
            old_binding,new_binding=context(transfer['oldBinding']),context(transfer['newBinding'])
            frame=transfer['oldFrame'];old_native=frame['nativeAfter']
            need(old_binding['processIdentity'].split(':')[0]==str(old_native['processId'])
                 and all(same(old_binding[key],new_binding[key]) for key in
                     ('sourceRevision','artifactSha256','sessionId','generation','targetFingerprint')))
            measurement(self.run,frame['probe']['ticket'],fixture_origin(self.source.client.url),frame,
                provider_instance=state['backend']['instance'],native_epoch=old_native['capturedEpochMs'],
                host_epoch=frame['status']['capturedEpochMs'],after_epoch=1,actor=role=='actor')
            exit=transfer['exit'];request=dict(schemaVersion=1,commandId=exit['commandId'],action='feature-process-presence',queryProcessId=old_native['processId'])
            validate_exit(exit,request,int(new_binding['processIdentity'].split(':')[0]),exit['capturedEpochMs'])
            need(exit['presence']=='absent' and exit['instance']!=old_native['instance'])
            if index:
                previous=state['restarts'][index-1]
                need(same(old_binding,previous['newBinding']) and old_native['instance']==previous['exit']['instance'])
        if last is not None and last['stage']==state['stage'] and state['restarts']:
            need(last['frame']['nativeAfter']['instance']==state['restarts'][-1]['exit']['instance'])
        return state

    def _actions(self):
        value=self.adapter._authentication_actions(self.selector,self.source.client,self.run)
        value.lock=self.lock;value.monotonic=self.monotonic;value.sleep=self.sleep
        return value

    def prepare(self):
        need(self.role=='primary')
        with self.lock.held():
            control=self.control()
            if control is None:
                need(self.retirement_store.read() is None and all(
                    self.adapter.authentication_samples_store(self.selector,role,stage).read() is None
                    for role in ('primary','actor') for stage in range(4)))
                need(all(PrivateFeatureState(self.store.path.with_name('phone-authentication-'+role+'-feature.json')).read() is None
                         for role in ('primary','actor')) and self.adapter.authentication_actions_store(self.selector).read() is None)
                active=self.source.read()
                need(active['verb']=='baseline')
                control=dict(phase='preparing',stage=0,binding=None,ticket=None,arguments=None,
                    backend=active['status'],cleanupIntents=[],cleanupProof=[])
                self._save(self.store,'owner',control)
            if control['phase']=='preparing':
                self.source.attach();actions=self._actions().prepare()
                need(actions['phase']=='ready' and actions['stage']==0)
                control.update(phase='baseline',binding=actions['binding']);self._save(self.store,'owner',control)
            return deepcopy(control)

    def act(self,call):
        need(self.role=='primary');call=deepcopy(arguments('feature.authentication.act',call))
        need(call['runId']==self.run and call['fixtureUrl']==self.fixture_url)
        self.prepare()
        with self.lock.held():
            control=self.control();need(control['phase'] in ('baseline','acting','active'))
            active=self.source.read(control['backend'])
            need(active['ticket']==call['ticket'] and active['verb']==call['verb'] and same(active['inputs'],call['inputs']))
            if control['phase']=='acting':need(same(control['arguments'],call))
            elif control['ticket']==call['ticket']:return self._actions().act(call)
            else:
                control.update(phase='acting',ticket=call['ticket'],arguments=call,backend=active['status'])
                self._save(self.store,'owner',control)
            actions=self._actions();receipt=actions.act(call);actual=actions.load()
            need(actual['phase']=='acknowledged' and same(actual['current']['arguments'],call))
            control.update(phase='active',stage=actual['stage'],binding=actual['binding'])
            self._save(self.store,'owner',control);return receipt

    def _restart_role(self,state,control,actions):
        need(control['stage']==state['stage']+1 and state['last'] is not None and state['last']['stage']==state['stage'])
        proof=actions['restarts'][state['stage']];plan=proof['input']
        old=self.adapter.authentication_samples_store(self.selector,self.role,state['stage']).read()
        need(type(old) is dict and type(old.get('authenticationSamplesVersion')) is int and old['authenticationSamplesVersion']==2 and old.get('runId')==self.run
             and old.get('role')==self.role and type(old.get('stage')) is int and old['stage']==state['stage'] and old.get('fixtureUrl')==self.source.client.url)
        rows=unpack(old['payload']);need(len(rows)==1);archive=rows[0]
        need(archive['phase']=='ready' and archive['pending'] is None and same(archive['binding'],plan['oldBinding'])
             and same(archive['frame'],state['last']['frame']))
        old_native=state['last']['frame']['nativeAfter']
        need(old_native['processId']==plan['oldNative']['pid'] and old_native['instance']==plan['oldNative']['instance']
             and old_native['account']['observation']['instance']==proof['oldAccountInstance'])
        with self.adapter.existing_input_session(self.selector):
            exit=self.adapter._process_presence(self.selector,read_only=True).require_absent(old_native['processId'])
        need(exit['instance']==plan['newNative']['instance'])
        transfer=dict(oldStage=state['stage'],oldBinding=deepcopy(plan['oldBinding']),oldFrame=deepcopy(state['last']['frame']),
            newBinding=deepcopy(plan['newBinding']),exit=exit)
        state.update(stage=control['stage'],restarts=state['restarts']+[transfer])

    def observe(self,call):
        call=arguments('feature.authentication.observe',call);need(call['runId']==self.run)
        if self.role=='primary':self.prepare()
        with self.lock.held():
            try:return self._observe_locked(call)
            except AuthenticationPhasePending as error:pending=error
        raise pending # Expected actor waits must escape after successful lock release.

    def _observe_locked(self,call):
        control=self.control()
        if control is None or control['phase'] in ('preparing','acting','cleaning'):
            raise AuthenticationPhasePending('Authentication input or cleanup is incomplete')
        state=self.role_state();need(state['phase']=='ready' and call['afterSequence']<=state['sequence'])
        try:active=self.source.read(state['backend'])
        except AuthenticationRunRetired as error:
            need(self.role=='actor' and control['phase']=='cleaned' and state['last'] is not None
                 and state['last']['ticket']==control['ticket'])
            state.update(phase='retired',backend=error.status);self._save(self.role_store,self.role,state);raise
        waiting=(active['verb']=='cleanup' and control['phase']!='cleaned'
            or active['verb'] not in ('baseline','cleanup') and control['ticket']!=active['ticket'])
        if waiting:
            need(self.role=='actor');state['backend']=active['status'];self._save(self.role_store,self.role,state)
            raise AuthenticationPhasePending('Authentication phase is awaiting its ordinary input')
        if active['verb']=='baseline':need(control['phase']=='baseline')
        elif active['verb']=='cleanup':need(control['phase']=='cleaned' and control['ticket']==active['ticket'])
        else:need(control['phase']=='active' and control['ticket']==active['ticket'])
        self.source.attach();actions=self._actions().load();need(actions is not None)
        if state['stage']!=control['stage']:self._restart_role(state,control,actions)
        state['phase']='reading';self._save(self.role_store,self.role,state)
        samples=PhoneAuthenticationSamples(self.adapter,self.selector,self.source.client,self.run,self.source.instance,
            self.role,state['stage'],self.lock,epoch_ms=self.source.epoch_ms,monotonic=self.monotonic)
        try:actual=samples.read(active['ticket'],active['afterEpochMs'])
        except Exception:
            if self.role!='actor':raise
            # Only this still-live owner under the unchanged source lock can
            # retire an actual old-ticket race. Same-ticket failures propagate.
            samples.retire_changed_ticket()
            state.update(phase='ready',backend=self.source.read(active['status'])['status'])
            self._save(self.role_store,self.role,state)
            raise AuthenticationPhasePending('Retired Authentication acquisition was drained without publication') from None
        frame=deepcopy(samples.state['frame'])
        if state['stage']:
            proof=actions['restarts'][state['stage']-1]
            need(frame['nativeAfter']['instance']==proof['native']['instance']
                 and frame['nativeAfter']['account']['observation']['instance']==proof['native']['account']['observation']['instance'])
        if active['verb'] not in ('baseline','cleanup','restart-app'):
            current=actions['current'];before=current['barrier']
            if active['verb'] in ('login-submit','logout'):before=current['intents'][-1]['native']
            causal(current['arguments'],before,frame['nativeAfter'],frame['nativeAfter']['capturedEpochMs'],
                delayed=frame['delayed'] if active['verb']=='login-submit' and active['inputs']['account']=='delayed' else None,
                provider_instance=self.source.instance)
        need(actual['capturedEpochMs']>=state['capturedEpochMs'])
        confirmed=self.source.read(active['status'])
        state.update(phase='ready',sequence=state['sequence']+1,capturedEpochMs=actual['capturedEpochMs'],
            backend=confirmed['status'],last=dict(stage=state['stage'],ticket=active['ticket'],frame=frame))
        self._save(self.role_store,self.role,state)
        if confirmed['ticket']!=active['ticket']:
            need(self.role=='actor');raise AuthenticationPhasePending('Retired Authentication sample was dropped without relabelling')
        need(confirmed['verb']==active['verb'] and same(confirmed['inputs'],active['inputs']))
        value=dict(schemaVersion=1,contractVersion=CONTRACT_VERSION,runId=self.run,sequence=state['sequence'],
            capturedEpochMs=actual['capturedEpochMs'],state=actual['state'],artifacts=[],resources=actual['resources'],lifecycle=actual['lifecycle'])
        result('feature.authentication.observe',value);return deepcopy(value)

    def publish(self):
        need(self.role=='actor')
        value=self.observe(dict(contractVersion=CONTRACT_VERSION,runId=self.run,afterSequence=0))
        state=self.role_state();ticket=state['last']['ticket']
        payload=dict(ticket=ticket,actor='owned-observer',actorSequence=value['sequence'],capturedEpochMs=value['capturedEpochMs'],
            facts=projection('authentication',value['state']))
        try:self.source.client.request('/runs/'+self.run+'/samples',payload)
        except ValueError:
            if self.source.read(state['backend'])['ticket']!=ticket:return None
            raise
        return value['sequence']
