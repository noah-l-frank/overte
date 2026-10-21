"""Durable normal iOS Authentication inputs; no requested outcome as facts."""
# Derived from frozen Phone source fe4684bf46585088370b3a328a738f147e670b97.
# iOS transport, menu/login source and original clock admission are platform-owned.
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import time

from ios.adapters.account_preferences import validate_basis
from adapters.native_feature_observation import exact,integer,need,number,validate as validate_native
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.restart_inputs import RestartInputs,validate_native_restart
from adapters.native_account_observation import accept as account_history
from adapters.native_process_presence import validate as validate_exit
from feature_journeys.contract import arguments,identifier
from feature_journeys.witness import Client
from ios.adapters.authentication_origin import origin as fixture_origin
from ios.adapters.authentication_samples import _native
from ios.adapters.authentication_causality import wait as ready
from ios.adapters.login_source import validate as validate_login,nonce as source_nonce
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock

VERSION=2
EMPTY=hashlib.sha256(b'').hexdigest()


class IOSAuthenticationActions:
    def __init__(self,adapter,selector,client,run,*,monotonic=time.monotonic,sleep=time.sleep,
                 epoch_ms=lambda:int(time.time()*1000)):
        identifier(run)
        need(isinstance(client,Client) and client.run==run and client.area=='authentication'
             and callable(monotonic) and callable(sleep) and callable(epoch_ms))
        self.adapter,self.selector,self.client,self.run=adapter,selector,client,run
        self.origin=fixture_origin(client.url);self.fixture_url=client.url+'/runs/'+run+'/'
        self.monotonic,self.sleep=monotonic,sleep
        self.epoch_ms=epoch_ms
        path=adapter.state_path(selector)
        self.store=PrivateFeatureState(path.with_name('ios-authentication-actions.json'))
        self.lock=ScriptSourceLock(path.with_name('script-feature-sources.lock'))
        self.state=self.previous=None
        self._input_bound=None

    def load(self):
        value=self.store.read()
        if value is None:self.state=self.previous=None;return None
        exact(value,{'authenticationActionsVersion','runId','fixtureUrl','payload'})
        need(type(value['authenticationActionsVersion']) is int and value['authenticationActionsVersion']==VERSION
             and value['runId']==self.run and value['fixtureUrl']==self.fixture_url)
        rows=unpack(value['payload']);need(len(rows)==1);state=rows[0]
        exact(state,{'binding','native','stage','phase','tickets','current','restarts','preferences'})
        basis=validate_basis(state['preferences'],self.origin)
        need(all(basis['binding'][key]==state['binding'][key] for key in ('sourceRevision','artifactSha256','sessionId','generation','targetFingerprint')))
        context(state['binding']);need(state['phase'] in ('ready','issued','acknowledged')
            and integer(state['stage'],0,3) and type(state['tickets']) is list and len(state['tickets'])<=256
            and len({identifier(ticket) for ticket in state['tickets']})==len(state['tickets'])
            and type(state['restarts']) is list and len(state['restarts'])==state['stage'])
        packet=state['native']
        validate_native(packet,packet.get('requestId'),int(state['binding']['processIdentity'].split(':')[0]),packet['capturedEpochMs'],require_account=True)
        source_nonce(packet['requestId']);self._scope(packet)
        current=state['current']
        if current is None:need(state['phase']=='ready' and not state['tickets'] and state['stage']==0)
        else:
            exact(current,{'arguments','binding','barrier','intents','delivered','readiness','receipt'})
            call=arguments('feature.authentication.act',current['arguments'])
            need(call['runId']==self.run and call['fixtureUrl']==self.fixture_url and call['ticket']==state['tickets'][-1]
                 and type(current['delivered']) is bool and type(current['intents']) is list and len(current['intents'])<=32
                 and type(current['readiness']) is list and len(current['readiness'])<=64)
            context(current['binding']);before=current['barrier']
            validate_native(before,before.get('requestId'),int(current['binding']['processIdentity'].split(':')[0]),before['capturedEpochMs'],require_account=True)
            self._scope(before)
            previous=before
            for intent in current['intents']:
                exact(intent,{'stage','control','original','native'})
                need(type(intent['stage']) is str and type(intent['control']) is str)
                original=intent['original'];native=intent['native']
                self._advance(previous,native);previous=native
                if intent['stage'].startswith('account-menu-'):
                    validate_native(original,original.get('requestId'),native['processId'],original['capturedEpochMs'],require_account=True)
                    need(original['instance']==native['instance'])
                else:
                    need(intent['stage'] in ('login-activate','login-replace','login-submit','login-close'))
                    validate_login(original,original.get('commandId'),native['processId'],original['capturedEpochMs'])
            delayed_history=None
            for frame in current['readiness']:
                exact(frame,{'native','delayed'});self._advance(previous,frame['native']);previous=frame['native']
                if frame['delayed'] is not None:
                    from adapters.account_fixture_observation import DelayedGrantObservation
                    if delayed_history is None:delayed_history=DelayedGrantObservation(self.run,self.client.account_instance)
                    delayed_history.accept(frame['delayed'])
            if call['verb']!='restart-app':
                need(same(current['binding'],state['binding']))
                if packet['sequence']==previous['sequence']:need(same(packet,previous))
                else:self._advance(previous,packet)
            if state['phase']=='acknowledged':
                need(current['delivered'] and current['receipt'] is not None)
                if call['verb']=='restart-app':
                    need(bool(state['restarts']) and same(current['receipt'],state['restarts'][-1])
                         and same(current['binding'],current['receipt']['input']['oldBinding'])
                         and before['instance']==current['receipt']['input']['oldNative']['instance'])
                else:need(same(current['receipt'],{'performed':True}))
        for index,restart in enumerate(state['restarts'],1):
            exact(restart,{'input','oldAccountInstance','native','exit'})
            plan=restart['input']
            exact(plan,{'restartInputVersion','componentOnly','oldBinding','oldNative','phase','newBinding','newNative','ownerFiles','scriptHandoff'})
            expected=[self.adapter.account_origin_store(self.selector)]+[
                self.adapter.account_probe_store(self.selector,role=role) for role in ('primary','actor')]
            need(type(plan['restartInputVersion']) is int and plan['restartInputVersion']==1
                 and plan['componentOnly'] is False and plan['phase']=='observed' and plan['scriptHandoff'] is None
                 and plan['ownerFiles']==[str(store.path) for store in expected])
            context(plan['oldBinding']);context(plan['newBinding'])
            need(all(same(plan['oldBinding'][key],plan['newBinding'][key]) for key in
                 ('sourceRevision','artifactSha256','sessionId','generation','targetFingerprint')))
            validate_native_restart(plan['oldNative'],plan['newNative'])
            identifier(restart['oldAccountInstance'])
            native=restart['native'];validate_native(native,native.get('requestId'),plan['newNative']['pid'],native['capturedEpochMs'],require_account=True)
            self._scope(native)
            need(native['instance']==plan['newNative']['instance'] and same(native['lifecycle'],plan['newNative']['lifecycle'])
                 and native['account']['observation']['instance']!=restart['oldAccountInstance']
                 and plan['newBinding']['processIdentity'].split(':')[0]==str(native['processId'])
                 and plan['oldBinding']['processIdentity'].split(':')[0]==str(plan['oldNative']['pid']))
            exit=restart['exit'];request=dict(schemaVersion=1,commandId=exit['commandId'],action='feature-process-presence',queryProcessId=plan['oldNative']['pid'])
            validate_exit(exit,request,native['processId'],exit['capturedEpochMs'])
            need(exit['instance']==native['instance'] and exit['presence']=='absent')
            if index>1:
                old=state['restarts'][index-2]
                need(same(plan['oldBinding'],old['input']['newBinding'])
                     and restart['oldAccountInstance']==old['native']['account']['observation']['instance'])
        if state['restarts']:
            need(same(state['binding'],state['restarts'][-1]['input']['newBinding'])
                 and packet['instance']==state['restarts'][-1]['native']['instance'])
        self.previous,self.state=deepcopy(value),deepcopy(state)
        return deepcopy(state)

    def _advance(self,before,after):
        validate_native(after,after.get('requestId'),before['processId'],after['capturedEpochMs'],require_account=True)
        source_nonce(after['requestId']);self._scope(after)
        need(after['requestId']!=before['requestId'] and after['instance']==before['instance']
             and after['sequence']>before['sequence'] and after['capturedEpochMs']>=before['capturedEpochMs']
             and all(after['lifecycle'][key]>=before['lifecycle'][key] for key in before['lifecycle']))
        account_history(account_history(None,before['account']),after['account'])

    def save(self):
        self.lock.assert_held();need(same(self.store.read(),self.previous))
        value=dict(authenticationActionsVersion=VERSION,runId=self.run,fixtureUrl=self.fixture_url,payload=pack([self.state]))
        self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)

    def _scope(self,packet):
        value=packet['account'];observed=value['observation']
        need(value['principalSha256'] in (EMPTY,hashlib.sha256(('e2e-'+self.run).encode()).hexdigest())
             and observed['credentialActive'] and observed['endpointPresent']
             and observed['endpointSha256'] in {hashlib.sha256(text.encode()).hexdigest() for text in (self.origin,self.origin+'/')})

    def _source(self):
        _ui,_service,binding,guard,_installed=self.adapter.normal_feature_runtime(self.selector,read_only=True)
        need(same(binding,self.state['binding']))
        reader=self.adapter._native_feature_observer(self.selector,read_only=True)
        _native(reader,self.state['native'])
        packet=reader.read(reader.sequence,require_account=True);self._scope(packet);need(guard() is not False)
        self.state['native']=deepcopy(packet);self.save()
        return reader,packet

    def prepare(self):
        with self.lock.held(),self.adapter.existing_input_session(self.selector):
            self.load()
            if self.state is None:
                preferences=self.adapter._preference_basis(self.selector)
                need(self.adapter.private_login_input_store(self.selector).read() is None)
                _ui,_service,binding,guard,_installed=self.adapter.normal_feature_runtime(self.selector,read_only=True)
                source=self.adapter._native_feature_observer(self.selector,read_only=True)
                packet=source.read(0,require_account=True);self._scope(packet);need(guard() is not False)
                need(all(self.adapter.account_probe_store(self.selector,role=role).read() is None for role in ('primary','actor'))
                     and self.adapter.account_origin_store(self.selector).read() is None
                     and all(self.adapter.authentication_restart_store(self.selector,stage).read() is None for stage in range(1,4)))
                self.state=dict(binding=deepcopy(context(binding)),native=packet,stage=0,phase='ready',tickets=[],current=None,restarts=[],preferences=preferences)
                self.save()
            else:self._source()
            return deepcopy(self.state)

    def _intent(self,stage,original,control):
        need(callable(self._input_bound));self._input_bound()
        need(self.state['phase']=='issued' and not self.state['current']['delivered']
             and len(self.state['current']['intents'])<32 and type(stage) is str and type(control) is str)
        _reader,native=self._source()
        if stage.startswith('account-menu-'):
            validate_native(original,original.get('requestId'),native['processId'],native['capturedEpochMs'],require_account=True)
            need(original['instance']==native['instance'])
        else:
            validate_login(original,original.get('commandId'),native['processId'],native['capturedEpochMs'])
            source_nonce(original['commandId'])
            pages=[row for row in original['controls'] if row['id']=='login.page']
            if pages:
                page=pages[0];account=native['account']['observation']
                need(not page['domain'] and page['accountInstance']==account['instance']
                     and page['credentialGeneration']==account['credentialGeneration']
                     and page['endpointSha256']==account['endpointSha256'])
        # Original UI metadata/native barrier only. No text or credentials.
        self.state['current']['intents'].append(dict(stage=stage,control=control,original=deepcopy(original),native=native))
        self.save();self._input_bound()

    def _deliver(self,call):
        if call['verb']=='logout':
            self.adapter._account_menu(self.selector,self._intent,self.run,self.origin).logout()
        elif call['verb']=='release-stale-response':
            # Fixture activation owns the release exactly once. The adapter
            # observes the actual outcome later; it must not repeat the mutation.
            return
        else:
            controls=self.adapter._login_controls(self.selector,self._intent,self.run,self.origin)
            if call['verb']=='login-open':controls.open()
            elif call['verb']=='login-cancel':controls.cancel()
            elif call['verb']=='login-submit':
                credentials=self.client.account_credentials(call['inputs']['account'])
                try:controls.fill(credentials);controls.submit()
                finally:credentials.clear() # Drop the private temporary; never journal or export it.
            else:need(False)

    def _restart(self):
        current=self.state['current'];stage=self.state['stage']+1;need(stage<=3)
        owners=[self.adapter.account_origin_store(self.selector)]+[
            self.adapter.account_probe_store(self.selector,role=role) for role in ('primary','actor')]
        need(all(owner.read() is None for owner in owners))
        inputs=RestartInputs(self.adapter.authentication_restart_store(self.selector,stage),owners,monotonic=self.monotonic)
        if inputs.store.read() is None:
            reader,_packet=self._source();inputs.capture(self.state['binding'],reader)
        plan=inputs.read()
        need(same(plan['oldBinding'],current['binding']) and plan['oldNative']['instance']==current['barrier']['instance'])
        if plan['phase']=='prepared':inputs.stop(lambda:self.adapter.invoke(self.selector,'app.stop',{}))
        if inputs.read()['phase']=='stop-issued':
            inputs.launch(lambda:self.adapter._authentication_restart_stopped(self.selector,current['binding']),
                          lambda:self.adapter.invoke(self.selector,'app.launch',{}))
        self.adapter._authentication_recover_launch(self.selector,inputs)
        _ui,_service,binding,guard,_installed=self.adapter.normal_feature_runtime(self.selector,read_only=True)
        reader=self.adapter._native_feature_observer(self.selector,read_only=True)
        packet=inputs.observe(binding,reader);self._scope(packet)
        validate_native(packet,packet['requestId'],reader.pid,reader.clock_ms(),require_account=True)
        need(packet['account']['observation']['instance']!=current['barrier']['account']['observation']['instance'])
        exit=self.adapter._process_presence(self.selector,read_only=True).require_absent(current['barrier']['processId'])
        need(exit['instance']==packet['instance'] and guard() is not False)
        proof=dict(input=inputs.read(),oldAccountInstance=current['barrier']['account']['observation']['instance'],native=packet,exit=exit)
        self.state.update(stage=stage,binding=deepcopy(binding),native=deepcopy(packet),restarts=self.state['restarts']+[proof])
        self.state['current'].update(delivered=True,receipt=proof);self.save()

    def act(self,call):
        try:
            call=deepcopy(arguments('feature.authentication.act',call))
            need(call['runId']==self.run and call['fixtureUrl']==self.fixture_url)
            started=previous=self.monotonic();need(number(started,0,1e15))
            def bound():
                nonlocal previous
                self.lock.assert_held();now=self.monotonic()
                need(number(now,0,1e15) and previous<=now and now-started<30);previous=now
            self._input_bound=bound
            with self.lock.held(),self.adapter.existing_input_session(self.selector):
                self.load();need(self.state is not None)
                if call['ticket'] in self.state['tickets']:
                    need(same(self.state['current']['arguments'],call))
                    if self.state['phase']=='acknowledged':
                        self._source();bound();return {'performed':True}
                    need(self.state['phase']=='issued' and
                         (self.state['current']['delivered'] or call['verb']=='restart-app'))
                else:
                    need(self.state['phase'] in ('ready','acknowledged') and len(self.state['tickets'])<256)
                    _reader,before=self._source()
                    self.state.update(phase='issued',tickets=self.state['tickets']+[call['ticket']],current=dict(
                        arguments=call,binding=deepcopy(self.state['binding']),barrier=before,intents=[],delivered=False,readiness=[],receipt=None))
                    bound();self.save()
                bound()
                if call['verb']=='restart-app':
                    if not self.state['current']['delivered']:self._restart()
                else:
                    if not self.state['current']['delivered']:
                        self._deliver(call);bound()
                        self.state['current']['delivered']=True;self.save()
                    reader,_current=self._source();before=self.state['current']['barrier']
                    if call['verb'] in ('login-submit','logout'):
                        intents=self.state['current']['intents'];need(bool(intents))
                        last=intents[-1];need(last['stage']==('login-submit' if call['verb']=='login-submit' else 'account-menu-logout'))
                        before=last['native']
                    def record(frame):
                        need(len(self.state['current']['readiness'])<64)
                        self.state['native']=deepcopy(frame['native']);self.state['current']['readiness'].append(deepcopy(frame));self.save();bound()
                    ready(call,before,reader,provider=self.client,monotonic=self.monotonic,sleep=self.sleep,record=record,epoch_ms=self.epoch_ms)
                    self.state['current']['receipt']={'performed':True}
                bound();self.state['phase']='acknowledged';self.save();bound()
                return {'performed':True} # Native causality only; full independent state is still required.
        except Exception:
            raise NativeUIError('iOS Authentication input failed; original intent and provenance are retained') from None
        finally:self._input_bound=None
