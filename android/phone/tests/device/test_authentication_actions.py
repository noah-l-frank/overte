"""Normal Authentication inputs through synthetic SDK/native/OS seams only."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone')]
from overte_phone_authentication_actions import PhoneAuthenticationActions
from overte_phone_script_history import pack,unpack
from adapters.native_feature_observation import NativeFeatureObservation
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUI,NativeUIError
from adapters.token_login_ui import TokenLoginUI
from overte_phone_account_menu import PhoneAccountMenu
from overte_phone_login import PhoneLoginIO
from feature_journeys.scenarios import VERSION
from self_tests.test_native_account_observation import account,event,append
from self_tests.test_native_feature_observation import Boundary as NativeBoundary
from self_tests.test_native_process_presence import Boundary as PresenceBoundary
from test_account_menu import MenuClient
from test_authentication_samples import Sources,RUN,ORIGIN,PROVIDER,BINDING
from login_native_boundary import LoginNativeBoundary


class InputSources(Sources):
    def __init__(self,root):
        super().__init__(root)
        self.pid=123;self.stage=0;self.lifecycle=dict(backgrounds=0,activations=1,launches=1)
        self.running=True;self.inputs=[];self.fault='';self.pending_ticket=None;self.provider_rows=[]
        self.proof_presence='absent';self.menu=None;self.bind();self.menu_client=MenuClient()
        self.client.account_credentials=self.credentials

    def credentials(self,role):
        return dict(username='e2e-'+RUN,password='synthetic-private-'+role)
    def normal_feature_runtime(self,_selector,*,read_only):
        assert read_only and self.running and self.okay
        return None,None,BINDING|dict(processIdentity=str(self.pid)+':original-start'),lambda:self.okay,None
    def _native_feature_observer(self,_selector,*,read_only):
        self.check(read_only)
        return NativeFeatureObservation(self.native.send,self.native.original,lambda:20000,lambda:self.okay,self.pid,
            monotonic=lambda:self.native.clock,sleep=self.native.sleep)
    def bind(self):
        def native(packet):
            packet.update(account=deepcopy(self.fact),processId=self.pid,instance=format(self.stage+10,'032x'),lifecycle=deepcopy(self.lifecycle))
        self.native.mutate=native
        capture=self.login.ui.capture
        def ui():
            observed=self.fact['observation'];self.login.ui.account=observed['instance']
            self.login.ui.account_generation=observed['credentialGeneration'];self.login.ui.endpoint=observed['endpointSha256']
            self.login.ui.pending=observed['loginPending'];self.login.ui.token=observed['tokenPresent']
            return capture()
        self.login.ui.capture=ui
        def output(packet):
            packet['processId']=self.pid
            if packet['action']=='submit' and packet['performed']:
                self.grant(self.login.ui.fields.get('login.password'))
        self.login.mutate=output
    def grant(self,password):
        if self.fault=='ignore-submit':
            self.login.ui.waiting=False;return
        observed=self.fact['observation'];observed['credentialGeneration']+=1
        if password=='synthetic-private-delayed':
            observed['loginPending']=True
            self.provider_rows.append(dict(requestId='e'*32,requestTicket=self.pending_ticket,startedEpochMs=int(time.time()*1000),
                releasedEpochMs=0,issuedEpochMs=0,status=0,state='held',accessValid=False,refreshValid=False))
            return
        success=password=='synthetic-private-owned'
        append(self.fact,event(sequence=observed['eventSequence']+1,generation=observed['credentialGeneration'],status=200 if success else 400))
        if success:
            self.fact.update(loggedIn=True,principalSha256=hashlib.sha256(('e2e-'+RUN).encode()).hexdigest())
            observed.update(tokenPresent=True,tokenValid=True,refreshPresent=True)
            self.login.ui.dialog=False
        else:self.login.ui.error='invalid-credentials'
        self.login.ui.waiting=False;observed['loginPending']=False
    def request(self,path):
        if path=='/runs/'+RUN+'/account/delayed':
            return dict(providerVersion=2,instance=PROVIDER,runId=RUN,capturedEpochMs=int(time.time()*1000),eventSequence=1,
                grantsEnabled=True,requests=deepcopy(self.provider_rows),delayedGrantOutstanding=False)
        return super().request(path)
    def account_origin_store(self,_selector):return PrivateFeatureState(self.root/'origin.json')
    def account_probe_store(self,_selector,*,role='primary'):return PrivateFeatureState(self.root/(role+'-probe.json'))
    def authentication_restart_store(self,_selector,stage):return PrivateFeatureState(self.root/('phone-authentication-restart-'+str(stage)+'.json'))
    def _login_controls(self,_selector,intent,_run,_origin):
        self.check(False)
        io=PhoneLoginIO(self.login.send,lambda:json.dumps(self.login.value),lambda:20000,lambda:self.okay,self.pid,
            monotonic=lambda:self.login.ui.clock,sleep=self.login.ui.sleep)
        def persist(stage,original,control):
            intent(stage,original,control);self.login.ui.intent(stage,original,control)
        return TokenLoginUI(io,persist,RUN,ORIGIN,monotonic=lambda:self.login.ui.clock,sleep=self.login.ui.sleep)
    def _account_menu(self,_selector,intent,_run,_origin):
        self.check(False);self.menu_client.logged=self.fact['loggedIn']
        def clicked(stage):
            if stage!='logout' or self.fault=='ignore-native-logout':return
            observed=self.fact['observation'];generation=observed['credentialGeneration']+1
            self.fact.update(loggedIn=False,principalSha256=hashlib.sha256(b'').hexdigest())
            observed.update(credentialGeneration=generation,tokenPresent=False,tokenValid=False,refreshPresent=False,loginPending=False,refreshPending=False)
            append(self.fact,event(sequence=observed['eventSequence']+1,kind='logout-complete',generation=generation))
        self.menu_client.after_click=clicked
        ui=NativeUI(self.menu_client,'original-menu-session',lambda:self.okay,timeout=.5,
            monotonic=lambda:self.menu_client.clock,sleep=lambda amount:setattr(self.menu_client,'clock',self.menu_client.clock+amount))
        return PhoneAccountMenu(ui,self._native_feature_observer(_selector,read_only=True),intent,RUN,ORIGIN)
    def _authentication_restart_stopped(self,_selector,_binding):
        return dict(running=self.running,identity=str(self.pid)+':original-start' if self.running else None)
    def invoke(self,_selector,operation,values):
        assert self.pinned and values=={} and operation in ('app.stop','app.launch')
        self.inputs.append(operation)
        if operation=='app.stop':
            if self.fault=='ignore-stop':return {'performed':True}
            self.running=False;self.lifecycle['backgrounds']+=1
        else:
            self.running=True;self.pid+=1;self.stage+=1
            self.lifecycle['launches']+=1;self.lifecycle['activations']+=1
            old=deepcopy(self.fact)
            self.fact=account();self.fact['observation'].update(instance=format(self.stage+30,'032x'),endpointSha256=hashlib.sha256(ORIGIN.encode()).hexdigest())
            if old['observation']['tokenPresent']:
                self.fact.update(loggedIn=old['loggedIn'],principalSha256=old['principalSha256'])
                self.fact['observation'].update(tokenPresent=True,tokenValid=True,refreshPresent=True)
            self.native=NativeBoundary();self.login=LoginNativeBoundary();self.bind()
        if self.fault=='lost-'+operation:raise RuntimeError('Synthetic lost SDK delivery return')
        return {'performed':True}
    def _process_presence(self,_selector,*,read_only):
        self.check(read_only);source=PresenceBoundary(pid=self.pid);source.presence=self.proof_presence
        source.edit=lambda packet:packet.update(instance=format(self.stage+10,'032x'))
        return source.reader()


class AuthenticationActionTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);os.chmod(self.root,0o700)
        self.sources=InputSources(self.root);self.counter=0;self.flow=self.owner();self.flow.prepare()
    def owner(self):
        return PhoneAuthenticationActions(self.sources,'private-selector',self.sources.client,RUN,
            monotonic=lambda:self.sources.clock,sleep=lambda value:setattr(self.sources,'clock',self.sources.clock+value))
    def call(self,verb,role='owned'):
        self.counter+=1
        return dict(contractVersion=VERSION,runId=RUN,ticket=format(self.counter,'032x'),fixtureUrl=ORIGIN+'/feature-fixture/v1/runs/'+RUN+'/',
            verb=verb,inputs={'account':role} if verb=='login-submit' else {})
    def act(self,verb,role='owned'):
        call=self.call(verb,role);self.sources.pending_ticket=call['ticket'];return self.flow.act(call)

    def test_prepare_is_read_only_and_normal_login_invalid_cancel_owned_uses_original_inputs_without_secret_journals(self):
        self.assertEqual([],self.sources.login.inputs);self.assertEqual('ready',self.flow.load()['phase'])
        for verb,role in (('login-open','owned'),('login-submit','invalid'),('login-cancel','owned'),('login-open','owned'),('login-submit','owned')):
            self.assertEqual({'performed':True},self.act(verb,role))
        state=self.flow.load();self.assertEqual(5,len(state['tickets']));self.assertEqual('acknowledged',state['phase'])
        self.assertTrue(self.sources.fact['loggedIn']);self.assertFalse(self.sources.login.ui.dialog)
        self.assertEqual(2,sum(action=='submit' for _,action in self.sources.login.inputs))
        self.assertNotIn('synthetic-private-',repr(state)+self.flow.store.path.read_text())
        self.assertTrue(all(intent['native']['requestId'] for intent in state['current']['intents']))

    def test_pending_cancel_reopen_preserves_original_delayed_request_without_resubmission(self):
        self.act('login-open');self.act('login-submit','delayed')
        for verb in ('login-cancel','login-open','login-cancel'):self.act(verb)
        self.assertTrue(self.sources.fact['observation']['loginPending'])
        self.assertEqual(1,len(self.sources.provider_rows));self.assertEqual(1,sum(action=='submit' for _,action in self.sources.login.inputs))

    def test_normal_logout_is_separate_from_visible_menu_row_disappearance_and_needs_native_clear(self):
        self.act('login-open');self.act('login-submit');self.act('logout')
        self.assertFalse(self.sources.fact['loggedIn'])
        self.assertTrue(any(label.startswith('Directory Service: Logout') for _,label in self.sources.menu_client.inputs))
        self.assertEqual('logout-complete',self.flow.load()['current']['readiness'][-1]['native']['account']['observation']['events'][-1]['kind'])

    def test_ignored_native_logout_cannot_pass_even_when_normal_row_has_disappeared(self):
        self.act('login-open');self.act('login-submit');self.sources.fault='ignore-native-logout'
        with self.assertRaises(NativeUIError):self.act('logout')
        self.assertTrue(self.sources.fact['loggedIn']);self.assertFalse(self.sources.menu_client.logged)
        self.assertEqual('issued',self.flow.load()['phase'])

    def test_completed_duplicate_is_revalidated_without_another_normal_input(self):
        call=self.call('login-open');self.flow.act(call);before=list(self.sources.login.inputs)
        self.assertEqual({'performed':True},self.owner().act(call));self.assertEqual(before,self.sources.login.inputs)
        with self.assertRaises(NativeUIError):self.owner().act(call|dict(verb='login-cancel'))
        self.assertEqual(before,self.sources.login.inputs)

    def test_lost_normal_input_return_remains_issued_and_recreation_never_replays_input(self):
        call=self.call('login-open');original=self.flow._deliver
        def lost(value):original(value);raise RuntimeError('Synthetic lost normal input return')
        with patch.object(self.flow,'_deliver',side_effect=lost),self.assertRaises(NativeUIError):self.flow.act(call)
        before=list(self.sources.login.inputs)
        with self.assertRaises(NativeUIError):self.owner().act(call)
        self.assertEqual(before,self.sources.login.inputs);self.assertFalse(self.flow.load()['current']['delivered'])

    def test_lost_final_ack_write_return_recovers_known_delivery_without_input_replay(self):
        call=self.call('login-open');write=self.flow.store.write
        def lost(value,previous):
            write(value,previous)
            if unpack(value['payload'])[0]['phase']=='acknowledged':raise OSError('Synthetic lost persistence return')
        with patch.object(self.flow.store,'write',side_effect=lost),self.assertRaises(NativeUIError):self.flow.act(call)
        before=list(self.sources.login.inputs);self.owner().act(call)
        self.assertEqual(before,self.sources.login.inputs)

    def test_ignored_submit_keeps_original_delivered_intent_and_retries_only_native_getters(self):
        self.act('login-open');self.sources.fault='ignore-submit';call=self.call('login-submit')
        with self.assertRaises(NativeUIError):self.flow.act(call)
        before=list(self.sources.login.inputs)
        with self.assertRaises(NativeUIError):self.owner().act(call)
        self.assertEqual(before,self.sources.login.inputs);self.assertTrue(self.flow.load()['current']['delivered'])

    def test_fixture_release_is_not_replayed_by_adapter_as_account_mutation(self):
        before=list(self.sources.requests);self.act('release-stale-response')
        self.assertEqual(before,self.sources.requests);self.assertEqual([],self.sources.login.inputs)

    def test_three_explicit_restarts_keep_actual_counters_and_distinct_account_births(self):
        for stage in range(1,4):
            self.act('restart-app');state=self.flow.load()
            self.assertEqual(stage,state['stage']);proof=state['restarts'][-1]
            self.assertEqual('ESRCH',proof['exit']['errorSymbol'])
            self.assertNotEqual(proof['oldAccountInstance'],proof['native']['account']['observation']['instance'])
            self.assertEqual(stage,proof['native']['lifecycle']['backgrounds'])
        self.assertEqual(['app.stop','app.launch']*3,self.sources.inputs)
        before=list(self.sources.inputs)
        with self.assertRaises(NativeUIError):self.act('restart-app')
        self.assertEqual(before,self.sources.inputs)

    def test_restart_during_held_login_retires_consumer_and_preserves_original_server_request(self):
        self.act('login-open');self.act('login-submit','delayed');held=deepcopy(self.sources.provider_rows)
        self.act('restart-app')
        self.assertFalse(self.sources.fact['observation']['loginPending']);self.assertEqual(held,self.sources.provider_rows)
        self.assertFalse(self.sources.fact['loggedIn'])

    def test_lost_stop_or_launch_return_resumes_original_restart_phase_without_redelivery(self):
        for operation in ('app.stop','app.launch'):
            with self.subTest(operation=operation):
                call=self.call('restart-app');self.sources.fault='lost-'+operation
                with self.assertRaises(NativeUIError):self.flow.act(call)
                self.sources.fault='';self.owner().act(call)
        self.assertEqual(['app.stop','app.launch']*2,self.sources.inputs)

    def test_live_old_process_or_unknown_kernel_error_cannot_be_a_restart_success(self):
        call=self.call('restart-app');self.sources.fault='ignore-stop'
        with self.assertRaises(NativeUIError):self.flow.act(call)
        self.assertEqual(['app.stop'],self.sources.inputs)
        # No hidden repair force-stops an ignored first input.
        with self.assertRaises(NativeUIError):self.owner().act(call)
        self.assertEqual(['app.stop'],self.sources.inputs)

    def test_unknown_exit_preserves_observed_restart_without_relaunching_on_recovery(self):
        call=self.call('restart-app');self.sources.proof_presence='unknown'
        with self.assertRaises(NativeUIError):self.flow.act(call)
        self.sources.proof_presence='absent';self.owner().act(call)
        self.assertEqual(['app.stop','app.launch'],self.sources.inputs)

    def test_foreign_run_endpoint_candidate_and_pending_measurement_lease_block_new_input(self):
        before=list(self.sources.login.inputs)
        with self.assertRaises(NativeUIError):self.flow.act(self.call('login-open')|dict(runId='f'*32))
        self.sources.fact['observation']['endpointSha256']='f'*64
        with self.assertRaises(NativeUIError):self.act('login-open')
        self.assertEqual(before,self.sources.login.inputs)
        self.sources.fact['observation']['endpointSha256']=hashlib.sha256(ORIGIN.encode()).hexdigest()
        owner=self.sources.account_probe_store('selector');owner.write({'unresolved':True},None)
        with self.assertRaises(NativeUIError):self.act('restart-app')
        self.assertEqual([],self.sources.inputs)

    def test_pending_input_journal_failure_stops_before_any_normal_widget_delivery(self):
        call=self.call('login-open');original=PrivateFeatureState.write
        def fail(store,value,previous):
            if store.path==self.flow.store.path and unpack(value['payload'])[0]['phase']=='issued':raise OSError('Synthetic full storage')
            return original(store,value,previous)
        with patch.object(PrivateFeatureState,'write',new=fail),self.assertRaises(NativeUIError):self.flow.act(call)
        self.assertEqual([],self.sources.login.inputs)

    def test_input_intent_deadline_expires_before_widget_delivery_even_after_slow_native_getter(self):
        original=self.flow._intent
        def late(stage,observed,control):
            self.sources.clock=30;original(stage,observed,control)
        with patch.object(self.flow,'_intent',side_effect=late),self.assertRaises(NativeUIError):self.act('login-open')
        self.assertEqual([],self.sources.login.inputs);self.assertEqual('issued',self.flow.load()['phase'])

    def test_rewritten_original_readiness_or_kernel_proof_is_rejected_before_new_source_or_input(self):
        self.act('login-open');self.act('login-submit','invalid')
        store=self.flow.store;old=store.read();state=unpack(old['payload'])[0]
        state['current']['readiness'][0]['native']['account']['observation']['events'][0]['httpStatus']=200
        store.write(old|dict(payload=pack([state])),old)
        calls=len(self.sources.native.commands)
        with self.assertRaises(NativeUIError):self.owner().act(self.call('login-cancel'))
        self.assertEqual(calls,len(self.sources.native.commands))
        # Restore only this test's original journal, then test independent exit provenance.
        store.write(old,store.read());self.act('restart-app');old=store.read();state=unpack(old['payload'])[0]
        state['restarts'][0]['exit'].update(presence='unknown',nativeError=1,errorSymbol='EPERM')
        store.write(old|dict(payload=pack([state])),old)
        before=list(self.sources.inputs)
        with self.assertRaises(NativeUIError):self.owner().act(self.call('login-cancel'))
        self.assertEqual(before,self.sources.inputs)


if __name__=='__main__':unittest.main()
