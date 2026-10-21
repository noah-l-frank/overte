"""iOS Authentication run attachment and original fixture-phase observations.

This module never registers/activates a run or substitutes requested outcomes
for measured account state. The full feature owner is composed on this source.
"""
# Derived from frozen Phone source fe4684bf46585088370b3a328a738f147e670b97.
# iOS transport, menu/login source and original clock admission are platform-owned.
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import math
import time
import uuid

from ios.adapters.account_preferences import require_owned,validate_basis,validate_intent
from adapters.native_feature_observation import exact,integer,need,number,validate as validate_native
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from feature_journeys.contract import arguments,identifier,result
from feature_journeys.scenarios import VERSION as CONTRACT_VERSION
from feature_journeys.witness import Client,projection
from ios.adapters.authentication_origin import origin as fixture_origin
from ios.adapters.authentication_samples import IOSAuthenticationSamples,provider_status,measurement,VERSION as SAMPLES_VERSION
from ios.adapters.authentication_samples import _native as restore_native,_ui as restore_ui
from ios.adapters.login_source import validate as validate_login,nonce as source_nonce
from adapters.script_feature.ui_source import validate as validate_tablet
from adapters.script_ui_inventory import validate as validate_inventory
from ios.adapters.authentication_causality import check as causal
from adapters.script_feature.history import pack,unpack,same,canonical
from adapters.script_feature.lock import ScriptSourceLock

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


class IOSAuthenticationFeature:
    """One full-area owner; all returned fields still come from fresh sources."""
    def __init__(self,adapter,selector,source,*,role='primary',monotonic=time.monotonic,sleep=time.sleep):
        need(isinstance(source,AuthenticationFixtureReader) and role in ('primary','actor')
             and callable(monotonic) and callable(sleep))
        self.adapter,self.selector,self.source,self.role=adapter,selector,source,role
        self.run,self.fixture_url=source.run,source.fixture_url
        self.monotonic,self.sleep=monotonic,sleep
        path=adapter.state_path(selector)
        self.store=PrivateFeatureState(path.with_name('ios-authentication-feature.json'))
        self.role_store=PrivateFeatureState(path.with_name('ios-authentication-'+role+'-feature.json'))
        self.retirement_store=PrivateFeatureState(path.with_name('ios-authentication-retirement.json'))
        self.lock=ScriptSourceLock(path.with_name('script-feature-sources.lock'))

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
            for entry in state['cleanupIntents']:
                exact(entry,{'stage','control','original','native'})
                need(type(entry['stage']) is str and type(entry['control']) is str)
                packet=entry['native'];validate_native(packet,packet.get('requestId'),packet.get('processId'),packet.get('capturedEpochMs'),require_account=True)
                need(state['binding'] is not None and state['binding']['processIdentity'].split(':')[0]==str(packet['processId']))
                stage=entry['stage'];stage=stage.removeprefix('restore-')
                if stage.startswith('account-preference-'):
                    original=validate_intent(entry['original'],fixture_origin(self.source.client.url),self.run)['native']
                    need(original['instance']==packet['instance'] and original['sequence']<=packet['sequence'])
                elif stage.startswith('account-menu-') or stage=='tablet-close':
                    original=entry['original'];validate_native(original,original.get('requestId'),packet['processId'],original.get('capturedEpochMs'),require_account=True)
                    need(original['instance']==packet['instance'] and original['sequence']<=packet['sequence'])
                else:
                    need(stage in ('login-activate','login-replace','login-submit','login-close'))
                    original=entry['original'];validate_login(original,original.get('commandId'),packet['processId'],original.get('capturedEpochMs'))
            for proof in state['cleanupProof']:
                need(type(proof) is dict and proof.get('kind') in ('native','login','tablet','frame'))
                if proof['kind']=='frame':
                    exact(proof,{'kind','ticket','frame'});identifier(proof['ticket'])
                    need(proof['frame']['probe']['ticket']==proof['ticket'])
                else:exact(proof,{'kind','packet'})
        return state

    def role_state(self,role=None):
        role=self.role if role is None else role;need(role in ('primary','actor'))
        store=PrivateFeatureState(self.store.path.with_name('ios-authentication-'+role+'-feature.json'))
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
        value.lock=self.lock;value.monotonic=self.monotonic;value.sleep=self.sleep;value.epoch_ms=self.source.epoch_ms
        return value

    def prepare(self):
        need(self.role=='primary')
        with self.lock.held():
            control=self.control()
            if control is None:
                need(self.retirement_store.read() is None and all(
                    self.adapter.authentication_samples_store(self.selector,role,stage).read() is None
                    for role in ('primary','actor') for stage in range(4)))
                need(all(PrivateFeatureState(self.store.path.with_name('ios-authentication-'+role+'-feature.json')).read() is None
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
        need(type(old) is dict and type(old.get('authenticationSamplesVersion')) is int and old['authenticationSamplesVersion']==SAMPLES_VERSION and old.get('runId')==self.run
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
        samples=IOSAuthenticationSamples(self.adapter,self.selector,self.source.client,self.run,self.source.instance,
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
        if active['verb']=='cleanup':
            require_owned(frame['login']['originalReceipt']['observation']['accountPreferences'],fixture_origin(self.source.client.url),
                run=self.run,baseline=actions['preferences']['preferences'])
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

    def _archives(self,control):
        """Original current-process cursor snapshots, including interrupted reads."""
        rows=[]
        for role in ('primary','actor'):
            value=self.adapter.authentication_samples_store(self.selector,role,control['stage']).read()
            if value is None:continue
            exact(value,{'authenticationSamplesVersion','runId','role','stage','providerInstance','fixtureUrl','payload'})
            need(type(value['authenticationSamplesVersion']) is int and value['authenticationSamplesVersion']==SAMPLES_VERSION
                 and value['runId']==self.run and value['role']==role and type(value['stage']) is int
                 and value['stage']==control['stage'] and value['providerInstance']==control['backend']['instance']
                 and value['fixtureUrl']==self.source.client.url)
            archive=unpack(value['payload']);need(len(archive)==1 and same(archive[0]['binding'],control['binding']))
            rows.append(archive[0])
        return rows

    def _cleanup_native(self,control):
        _ui,_service,binding,guard,_installed=self.adapter.normal_feature_runtime(self.selector,read_only=True)
        need(same(context(binding),control['binding']))
        actions=self._actions();state=actions.load();need(state is not None and same(state['binding'],binding))
        frames=[state['native']]+[row['native'] for row in self._archives(control) if row['native'] is not None]
        for proof in control['cleanupProof']:
            if proof['kind']=='native':frames.append(proof['packet'])
            elif proof['kind']=='frame':frames.append(proof['frame']['nativeAfter'])
        by_sequence={}
        for frame in frames:
            validate_native(frame,frame.get('requestId'),int(binding['processIdentity'].split(':')[0]),frame['capturedEpochMs'],require_account=True)
            sequence=frame['sequence']
            if sequence in by_sequence:need(same(frame,by_sequence[sequence]))
            by_sequence[sequence]=frame
        reader=self.adapter._native_feature_observer(self.selector,read_only=True)
        for sequence in sorted(by_sequence):restore_native(reader,by_sequence[sequence])
        packet=reader.read(reader.sequence,require_account=True);actions._scope(packet);need(guard() is not False)
        need(len(control['cleanupProof'])<64);control['cleanupProof'].append(dict(kind='native',packet=deepcopy(packet)))
        self._save(self.store,'owner',control)
        return packet

    def _cleanup_ui(self,control,key):
        if key=='login':
            reader=self.adapter._login_controls(self.selector,lambda *_args:need(False),self.run,
                fixture_origin(self.source.client.url),read_only=True).io
            validator=validate_login
        else:
            need(key=='tablet');reader=self.adapter._script_file_io(self.selector,read_only=True);validator=validate_tablet
        frames=[row[key] for row in self._archives(control) if row[key] is not None]
        frames += [proof['packet'] for proof in control['cleanupProof'] if proof['kind']==key]
        frames += [proof['frame'][key] for proof in control['cleanupProof'] if proof['kind']=='frame']
        if frames:
            latest=max(frames,key=lambda packet:packet['sourceSequence']);restore_ui(reader,latest,validator)
        packet=reader.capture()
        need(len(control['cleanupProof'])<64);control['cleanupProof'].append(dict(kind=key,packet=deepcopy(packet)))
        self._save(self.store,'owner',control)
        return packet

    def _cleanup_inputs(self,control,bound):
        """Attempt ordinary owned cleanup even if a main sample is interrupted."""
        with self.adapter.existing_input_session(self.selector):
            private=self.adapter.private_login_input_store(self.selector)
            if private.read() is not None:
                self.adapter._private_login_input(self.selector,self.run).retire();bound()
            packet=self._cleanup_native(control);bound()
            # Revoking the fixture wakes a held actual response. View dismissal
            # itself cannot claim to have cancelled that native request.
            started=self.monotonic()
            while any(packet['account']['observation'][key] for key in ('loginPending','refreshPending')):
                need(self.monotonic()-started<10 and len(control['cleanupProof'])<40)
                self.sleep(.1);packet=self._cleanup_native(control);bound()
            ui=self._cleanup_ui(control,'login');bound()
            def intent(stage,original,identifier):
                need(not any(row['stage']==stage and row['control']==identifier for row in control['cleanupIntents'])
                     and len(control['cleanupIntents'])<32)
                native=self._cleanup_native(control);bound()
                control['cleanupIntents'].append(dict(stage=stage,control=identifier,original=deepcopy(original),native=native))
                self._save(self.store,'owner',control);bound()
            if any(row['id']=='login.page' for row in ui['controls']):
                self.adapter._login_controls(self.selector,intent,self.run,fixture_origin(self.source.client.url)).cancel();bound()
            packet=self._cleanup_native(control);bound()
            if packet['account']['observation']['tokenPresent'] or packet['account']['observation']['refreshPresent']:
                need(packet['account']['loggedIn'] and not any(row['stage'].startswith('account-menu-') for row in control['cleanupIntents']))
                self.adapter._account_menu(self.selector,intent,self.run,fixture_origin(self.source.client.url)).logout();bound()
                self._cleanup_native(control);bound()
            actions=self._actions().load();need(actions is not None)
            self.adapter._restore_account_preferences(self.selector,actions['preferences'],intent);bound()
            tablet=self._cleanup_ui(control,'tablet');validate_inventory(tablet['scriptInventory']);bound()
            if tablet['scriptInventory']['tabletShown']:
                _ui,_service,binding,guard,_installed=self.adapter.normal_feature_runtime(self.selector,read_only=True)
                need(same(binding,control['binding']) and guard() is not False)
                normal=self.adapter._account_tablet(self.selector)
                native=self._cleanup_native(control);intent('tablet-close',native,'nav.close')
                normal.close_tablet();normal.wait_tablet_absent();bound()

    def _drain_measurements(self,control,bound):
        failures=[]
        with self.adapter.existing_input_session(self.selector):
            private=self.adapter.private_login_input_store(self.selector)
            try:
                if private.read() is not None:self.adapter._private_login_input(self.selector,self.run).retire()
            except Exception as error:failures.append(error)
            for role in ('primary','actor'):
                try:
                    store=self.adapter.account_probe_store(self.selector,role=role)
                    if store.read() is not None:
                        owned=self.adapter._account_probe(self.selector,read_only=True,role=role)
                        need(owned.owner.owned()['probe']['runId']==self.run);owned.release();bound()
                except Exception:failures.append(role)
            try:
                store=self.adapter.account_origin_store(self.selector)
                if store.read() is not None:
                    owned=self.adapter._account_origin(self.selector)
                    need(owned.owned()['data']['runId']==self.run);owned.release();bound()
            except Exception:failures.append('origin')
        need(not failures)

    def _cleanup_sample(self,control,active):
        samples=IOSAuthenticationSamples(self.adapter,self.selector,self.source.client,self.run,self.source.instance,
            'primary',control['stage'],self.lock,epoch_ms=self.source.epoch_ms,monotonic=self.monotonic)
        actual=samples.read(active['ticket'],active['afterEpochMs']);frame=deepcopy(samples.state['frame'])
        original=self._actions().load()['preferences']['preferences']
        require_owned(frame['login']['originalReceipt']['observation']['accountPreferences'],fixture_origin(self.source.client.url),run=self.run,baseline=original)
        need(actual['resources']==[] and actual['state']==dict(principal='anonymous',dialog=False,error='none',pending=False,
            protectedAccess=False,delayedGrantOutstanding=False))
        status=frame['status'];need(not status['grantsEnabled'] and not status['armedHold'] and not any(
            status[key] for key in ('heldRequests','inflightRequests','accessTokens','refreshTokens')))
        need(len(control['cleanupProof'])<64)
        control['cleanupProof'].append(dict(kind='frame',ticket=active['ticket'],frame=frame));self._save(self.store,'owner',control)
        return actual

    def cleanup(self,call):
        need(self.role=='primary');call=arguments('feature.authentication.cleanup',call);need(call['runId']==self.run)
        with self.lock.held():
            control=self.control();need(control is not None and control['binding'] is not None)
            active=self.source.read(control['backend']);need(active['verb']=='cleanup')
            need(control['phase'] in ('baseline','acting','active','cleaning','cleaned'))
            started=previous=self.monotonic();need(number(started,0,1e15))
            def bound():
                nonlocal previous
                now=self.monotonic();need(number(now,0,1e15) and previous<=now and now-started<30)
                previous=now;self.lock.assert_held()
            if control['phase']!='cleaned':
                control.update(phase='cleaning',ticket=active['ticket'],arguments=None,backend=active['status'])
                self._save(self.store,'owner',control)
                failure=None
                try:self._cleanup_inputs(control,bound)
                except Exception as error:failure=error
                try:self._drain_measurements(control,bound)
                except Exception as error:failure=error
                if failure is not None:raise failure
                first=since=None
                for attempt in range(32):
                    actual=self._cleanup_sample(control,active);bound()
                    if first is None:first,since=actual['capturedEpochMs'],self.monotonic()
                    if attempt>=2 and self.monotonic()-since>=3 and actual['capturedEpochMs']-first>=3000:break
                    need(attempt<31);self.sleep(.25)
                control['phase']='cleaned';self._save(self.store,'owner',control)
            else:
                need(control['ticket']==active['ticket']);self._cleanup_sample(control,active)
            bound();return {'performed':True}

    def _retirement_paths(self):
        paths=[self.adapter.authentication_actions_store(self.selector)]+[
            self.adapter.authentication_restart_store(self.selector,stage) for stage in range(1,4)]
        for role in ('primary','actor'):
            paths.extend(self.adapter.authentication_samples_store(self.selector,role,stage) for stage in range(4))
            paths.append(PrivateFeatureState(self.store.path.with_name('ios-authentication-'+role+'-feature.json')))
        return paths+[self.store]

    def _final_basis(self,control):
        need(control['phase']=='cleaned')
        actions=self._actions().load();need(actions is not None and actions['phase'] in ('ready','acknowledged')
             and same(actions['binding'],control['binding']) and actions['stage']==control['stage'])
        clean=[row['frame'] for row in control['cleanupProof'] if row['kind']=='frame']
        need(len(clean)>=3 and clean[-1]['nativeAfter']['capturedEpochMs']-clean[0]['nativeBefore']['capturedEpochMs']>=3000)
        roles={}
        for role in ('primary','actor'):
            state=self.role_state(role);last=state['last']
            need(state['phase'] in ('ready','retired') and state['sequence']>0 and state['stage']==control['stage']
                 and last is not None and last['stage']==control['stage'] and last['ticket']==control['ticket'])
            frame=last['frame']
            require_owned(frame['login']['originalReceipt']['observation']['accountPreferences'],fixture_origin(self.source.client.url),
                run=self.run,baseline=actions['preferences']['preferences'])
            actual=measurement(self.run,control['ticket'],fixture_origin(self.source.client.url),frame,
                provider_instance=control['backend']['instance'],native_epoch=frame['nativeAfter']['capturedEpochMs'],
                host_epoch=frame['status']['capturedEpochMs'],after_epoch=1,actor=role=='actor')
            need(actual['resources']==[] and actual['state']==dict(principal='anonymous',dialog=False,error='none',pending=False,
                protectedAccess=False,delayedGrantOutstanding=False))
            roles[role]=deepcopy(frame)
            for stage in range(control['stage']+1):
                archive=self.adapter.authentication_samples_store(self.selector,role,stage).read()
                transfer=state['restarts'][stage] if stage<control['stage'] else None
                expected=transfer['oldFrame'] if transfer is not None else frame
                binding=transfer['oldBinding'] if transfer is not None else control['binding']
                saved=IOSAuthenticationSamples.archive(archive,client=self.source.client,run=self.run,
                    provider_instance=control['backend']['instance'],role=role,stage=stage,binding=binding)
                need(same(saved['frame'],expected))
        native=[actions['native']]+[row['native'] for row in self._archives(control)]
        native += [row['packet'] for row in control['cleanupProof'] if row['kind']=='native']
        native += [row['nativeAfter'] for row in clean]
        native=[packet for packet in native if packet is not None]
        newest=max(native,key=lambda packet:packet['sequence'])
        login=[row['login'] for row in roles.values()]+[row['packet'] for row in control['cleanupProof'] if row['kind']=='login']
        tablet=[row['tablet'] for row in roles.values()]+[row['packet'] for row in control['cleanupProof'] if row['kind']=='tablet']
        return dict(binding=deepcopy(control['binding']),native=deepcopy(newest),roles=roles,preferences=deepcopy(actions['preferences']),
            login=deepcopy(max(login,key=lambda packet:packet['sourceSequence'])),
            tablet=deepcopy(max(tablet,key=lambda packet:packet['sourceSequence'])),status=deepcopy(control['backend']))

    def _final_absence(self,basis,previous=None,*,bound=lambda:None):
        """No new protected GET after the fixture retires; inspect original leases."""
        exact(basis,{'binding','native','roles','login','tablet','status','preferences'})
        validate_basis(basis['preferences'],fixture_origin(self.source.client.url))
        context(basis['binding']);exact(basis['roles'],{'primary','actor'});bound()
        if self.source.instance is None:self.source.attach()
        need(self.source.instance==basis['status']['instance'])
        _ui,_service,binding,guard,_installed=self.adapter.normal_feature_runtime(self.selector,read_only=True)
        need(same(binding,basis['binding']))
        bound()
        native=self.adapter._native_feature_observer(self.selector,read_only=True)
        restore_native(native,basis['native'])
        if previous is not None:
            restore_native(native,previous['native'])
        origin_floor=max(frame['originAbsent']['sequence'] for frame in basis['roles'].values())
        probe_floor=max(frame['probeReleased']['sequence'] for frame in basis['roles'].values())
        if previous is not None:
            origin_floor=max(origin_floor,max(row['sequence'] for row in previous['origins'].values()))
            probe_floor=max(probe_floor,max(row['sequence'] for row in previous['probes'].values()))
        origins={};probes={}
        for role in ('primary','actor'):
            frame=basis['roles'][role];owner=frame['originOwner']
            need(same(owner['binding'],binding) and owner['data']['runId']==self.run)
            source=self.adapter._account_origin(self.selector,read_only=True)
            restore_native(native,source.native_admission)
            source.source.sequence=origin_floor
            packet=source.source.request(owner['data'],'observe');origin_floor=packet['sequence']
            need(packet['source']['retired'] and not packet['source']['originExists'] and not packet['source']['ownerExists'])
            origins[role]=packet
            bound()
        # AccountProbe has one global native slot, not a per-role retired
        # request registry. Both original role frames already proved their own
        # releases. Freshly inspect the latest actual slot; querying an older
        # role's replaced request would be unavailable in the real native API.
        role=max(basis['roles'],key=lambda key:basis['roles'][key]['probeReleased']['sequence'])
        need(all(self.adapter.account_probe_store(self.selector,role=key).read() is None for key in ('primary','actor')))
        owned=self.adapter._account_probe(self.selector,read_only=True,role=role)
        original=basis['roles'][role]['probe'];reader=owned.probe
        reader.instance=original['instance'];reader.sequence=probe_floor
        request=dict(schemaVersion=1,commandId='ios-'+uuid.uuid4().hex,action='feature-account-probe',operation='inspect',
            requestId=original['requestId'],runId=self.run,ticket=original['ticket'])
        packet=reader._perform(request)
        need(packet['source']==dict(inflight=False,responseBytes=0,credentialBytes=0,released=True))
        probes['current']=packet;bound()
        login=self.adapter._login_controls(self.selector,lambda *_args:need(False),self.run,
            fixture_origin(self.source.client.url),read_only=True).io
        restore_ui(login,basis['login'] if previous is None else previous['login'],validate_login)
        ui=login.capture();need(not any(row['id']=='login.page' for row in ui['controls']))
        require_owned(ui['originalReceipt']['observation']['accountPreferences'],fixture_origin(self.source.client.url),
            run=self.run,baseline=basis['preferences']['preferences'])
        bound()
        tablet=self.adapter._script_file_io(self.selector,read_only=True)
        restore_ui(tablet,basis['tablet'] if previous is None else previous['tablet'],validate_tablet)
        tabs=tablet.capture();validate_inventory(tabs['scriptInventory']);need(not tabs['scriptInventory']['tabletShown'])
        bound()
        packet=native.read(native.sequence,require_account=True)
        bound()
        value=packet['account'];observed=value['observation']
        need(not value['loggedIn'] and value['principalSha256']==hashlib.sha256(b'').hexdigest()
             and observed['endpointSha256'] in {hashlib.sha256(text.encode()).hexdigest() for text in
                 (fixture_origin(self.source.client.url),fixture_origin(self.source.client.url)+'/')}
             and observed['credentialActive'] and not any(observed[key] for key in
                 ('tokenPresent','tokenValid','refreshPresent','loginPending','refreshPending')))
        old=basis['status'] if previous is None else previous['status']
        self.source.client.account_epoch=max(getattr(self.source.client,'account_epoch',0),old['capturedEpochMs'])
        self.source.client.account_sequence=max(getattr(self.source.client,'account_sequence',0),old['eventSequence'])
        status=self.source.client.account_status();provider_status(status,self.run,self.source.instance,int(self.source.clock()))
        need(not status['accountExists'] and not status['grantsEnabled'] and not status['armedHold']
             and not any(status[key] for key in ('heldRequests','inflightRequests','accessTokens','refreshTokens'))
             and guard() is not False)
        bound()
        return deepcopy(dict(native=packet,login=ui,tablet=tabs,origins=origins,probes=probes,status=status))

    def finalize(self):
        """Recoverable host retirement after both roles and fresh native absence."""
        need(self.role=='primary')
        started=previous=self.monotonic();need(number(started,0,1e15))
        def bound():
            nonlocal previous
            self.lock.assert_held();now=self.monotonic()
            need(number(now,0,1e15) and previous<=now and now-started<30);previous=now
        with self.lock.held(),self.adapter.existing_input_session(self.selector):
            bound()
            if self.source.instance is None:self.source.attach()
            bound()
            paths=self._retirement_paths();known={store.path.name:store for store in paths}
            plan=self._read(self.retirement_store,'retirement')
            if plan is None:
                control=self.control();need(control is not None)
                basis=self._final_basis(control)
                need(self.adapter.account_origin_store(self.selector).read() is None
                     and all(self.adapter.account_probe_store(self.selector,role=role).read() is None for role in ('primary','actor')))
                items=[]
                for store in paths:
                    value=store.read()
                    if value is not None:items.append(dict(name=store.path.name,sha256=hashlib.sha256(canonical(value)).hexdigest()))
                plan=dict(basis=basis,items=items,phase='verifying',verification=None)
                self._save(self.retirement_store,'retirement',plan)
            exact(plan,{'basis','items','phase','verification'})
            need(plan['phase'] in ('verifying','retiring') and type(plan['items']) is list and len(plan['items'])<=len(paths))
            names=set()
            for item in plan['items']:
                exact(item,{'name','sha256'})
                need(item['name'] in known and item['name'] not in names)
                names.add(item['name']);value=known[item['name']].read()
                need(value is None or hashlib.sha256(canonical(value)).hexdigest()==item['sha256'])
            plan['phase']='verifying';self._save(self.retirement_store,'retirement',plan)
            plan['verification']=self._final_absence(plan['basis'],plan['verification'],bound=bound)
            plan['phase']='retiring';self._save(self.retirement_store,'retirement',plan)
            for item in plan['items']:
                bound()
                store=known[item['name']];value=store.read()
                need(value is None or hashlib.sha256(canonical(value)).hexdigest()==item['sha256'])
                if value is not None:store.discard(value)
            need(all(store.read() is None for store in paths))
            self.retirement_store.discard(self.retirement_store.read())
            bound();return {'performed':True}
