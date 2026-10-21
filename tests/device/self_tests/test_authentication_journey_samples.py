"""Authentication original-source joins at synthetic seams; no client execution."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tests/device'))
from adapters.authentication_journey.samples import AuthenticationSamples,measurement
from adapters.script_journey.history import pack,unpack
from adapters.script_journey.lock import ScriptSourceLock
from adapters.authentication_journey.login_source import LoginObservationSource
from adapters.native_account_origin import NativeAccountOrigin,OwnedAccountOrigin
from adapters.native_account_probe import AccountProbeOwner,OwnedAccountProbe,NativeAccountProbe
from adapters.native_feature_observation import NativeFeatureObservation
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from feature_journeys.witness import Client
from self_tests.test_native_feature_observation import Boundary as NativeBoundary
from self_tests.test_native_account_observation import account
from self_tests.test_native_account_origin import Boundary as OriginBoundary
from self_tests.test_native_account_probe import Boundary as ProbeBoundary
from self_tests.test_script_ui_inventory import inventory
from adapters.script_journey.files import ScriptFileIO
from self_tests.authentication_file_boundary import FileNativeBoundary
from self_tests.authentication_login_boundary import LoginNativeBoundary

RUN='a'*32;TICKET='b'*32;PROVIDER='c'*32;ORIGIN='https://owned.invalid'
BINDING=dict(sourceRevision='e'*40,artifactSha256='f'*64,processIdentity='123:original-start',
             sessionId='owned-sdk-session',generation=1,targetFingerprint='1'*64)


class SingleSlotProbeBoundary(ProbeBoundary):
    """Mirror the real AccountProbe's one current request, not a fake registry."""
    def __init__(self):
        super().__init__();self.slot=None;self.used_requests=set();self.birth=self.instance

    def send(self,request):
        if self.ignored:return super().send(request)
        if self.birth!=self.instance:
            self.birth=self.instance;self.slot=None;self.used_requests.clear()
        key=tuple(request[field] for field in ('runId','ticket','requestId'))
        op=request['operation']
        if op=='read' and key!=self.slot and request['requestId'] not in self.used_requests:
            self.slot=key;self.used_requests.add(request['requestId'])
        elif op=='release' and key!=self.slot and request['requestId'] not in self.used_requests:
            self.slot=key;self.used_requests.add(request['requestId']) # Original never-delivered retirement.
        if self.slot!=key:
            self.commands.append(deepcopy(request));self.value=dict(commandId=request['commandId'],available=False);return
        return super().send(request)


class Sources:
    """Explicit source seams; fixture ownership and journals are real host files."""
    def __init__(self,root):
        self.root=root;self.path=root/'binding.json';self.clock=0.;self.okay=True;self.pinned=0;self.pid=123
        self.epoch_ms=lambda:20000;self.provider_epoch_ms=lambda:9000000
        self.fact=account();self.fact['observation']['endpointSha256']=hashlib.sha256(ORIGIN.encode()).hexdigest()
        self.native=NativeBoundary()
        def native(packet):
            epoch=self.epoch_ms();self.fact['observation']['capturedEpochMs']=epoch
            packet.update(account=deepcopy(self.fact),capturedEpochMs=epoch,requestedEpochMs=epoch)
            packet['animationFence']['requestedEpochMs']=epoch
        self.native.mutate=native
        self.origin=OriginBoundary(root/'native');self.probe=SingleSlotProbeBoundary()
        self.origin.mutate=lambda packet:packet.update(processId=self.pid,requestedEpochMs=self.epoch_ms(),capturedEpochMs=self.epoch_ms())
        self.provider_sequence=0
        def response(packet):
            packet['processId']=self.pid
            packet.update(requestedEpochMs=self.epoch_ms(),capturedEpochMs=self.epoch_ms())
            if packet['operation']=='read':
                self.provider_sequence+=1
                packet['source'].update(endpointSha256=self.fact['observation']['endpointSha256'],
                    credentialGeneration=self.fact['observation']['credentialGeneration'],sentEpochMs=self.epoch_ms(),completedEpochMs=self.epoch_ms())
        self.probe.mutate=response
        self.login=LoginNativeBoundary()
        def login(packet):
            packet['processId']=self.pid
            if packet['action']=='observe':packet['capturedEpochMs']=self.epoch_ms()
        self.login.mutate=login
        self.tablet=FileNativeBoundary(root/'native')
        self.tablet.mutate=lambda packet:packet.update(processId=self.pid,capturedEpochMs=self.epoch_ms(),controls=[],scriptInventory=inventory(tabletShown=False))
        self.calls=[];self.requests=[];self.proof_edit={};self.status_edit={};self.delayed_edit={}
        self.active=dict(schemaVersion=1,runId=RUN,area='authentication',ticket=TICKET,stimulus=dict(verb='baseline',inputs={}))
        self.client=Client.__new__(Client)
        self.client.url=ORIGIN+'/feature-fixture/v1';self.client.run=RUN;self.client.area='authentication'
        self.client.account_instance=PROVIDER;self.client.account_epoch=self.client.account_sequence=0
        self.client.request=self.request
        self.client.account_status=self.status

    def state_path(self,_selector):return self.path
    def account_origin_store(self,_selector):return PrivateFeatureState(self.root/'origin.json')
    def account_probe_store(self,_selector,*,role='primary'):return PrivateFeatureState(self.root/(role+'-probe.json'))
    def normal_feature_runtime(self,_selector,*,read_only):
        assert read_only
        return None,None,deepcopy(BINDING),lambda:self.okay,None
    @contextmanager
    def existing_input_session(self,_selector):
        self.pinned+=1
        try:yield
        finally:self.pinned-=1
    def check(self,read_only):
        assert self.pinned and self.okay
        self.calls.append(read_only)
    def _native_feature_observer(self,_selector,*,read_only):
        self.check(read_only)
        return NativeFeatureObservation(self.native.send,self.native.original,self.epoch_ms,lambda:self.okay,self.pid,
            monotonic=lambda:self.native.clock,sleep=self.native.sleep)
    def _account_origin(self,_selector,*,read_only=False):
        self.check(read_only)
        admission=self._native_feature_observer(_selector,read_only=True).read(0,require_account=True)
        source=NativeAccountOrigin(self.origin.send,self.origin.read,self.epoch_ms,lambda:self.okay,self.pid,admission['instance'],
            monotonic=lambda:self.origin.clock,sleep=self.origin.sleep)
        owner=OwnedAccountOrigin(source,PrivateFeatureState(self.root/'origin.json'),self.normal_feature_runtime(_selector,read_only=True)[2])
        owner.native_admission=admission;return owner
    def _account_probe(self,_selector,*,read_only,role):
        self.check(read_only)
        owner=AccountProbeOwner(PrivateFeatureState(self.root/(role+'-probe.json')),self.normal_feature_runtime(_selector,read_only=True)[2],lambda:self.okay)
        probe=NativeAccountProbe(self.probe.send,self.probe.read,self.epoch_ms,lambda:self.okay,self.pid,
            intent=owner.intent,monotonic=lambda:self.probe.clock,sleep=self.probe.sleep)
        return OwnedAccountProbe(probe,owner)
    def _login_controls(self,_selector,_intent,_run,_origin,*,read_only):
        self.check(read_only)
        return SimpleNamespace(io=LoginObservationSource(self.login.send,lambda:json.dumps(self.login.value),self.epoch_ms,lambda:self.okay,self.pid,
            monotonic=lambda:self.login.ui.clock,sleep=self.login.ui.sleep))
    def _script_file_io(self,_selector,*,read_only):
        self.check(read_only)
        return ScriptFileIO(self.tablet.send,lambda:json.dumps(self.tablet.value),self.epoch_ms,lambda:self.okay,self.pid,
            monotonic=lambda:self.tablet.ui.clock,sleep=self.tablet.ui.sleep)
    def request(self,path):
        self.requests.append(path)
        if path=='/runs/'+RUN+'/active':return deepcopy(self.active)
        if path=='/runs/'+RUN+'/account/delayed':
            return dict(providerVersion=2,instance=PROVIDER,runId=RUN,capturedEpochMs=self.provider_epoch_ms(),eventSequence=self.provider_sequence,
                grantsEnabled=True,requests=[],delayedGrantOutstanding=False)|self.delayed_edit
        if path.startswith('/runs/'+RUN+'/account/proof/'):
            return dict(providerVersion=2,instance=PROVIDER,runId=RUN,capturedEpochMs=self.provider_epoch_ms(),eventSequence=self.provider_sequence,
                kind='profile-request',ticket=path.rsplit('/',2)[1],requestId=path.rsplit('/',1)[1],status=self.probe.value['source']['httpStatus'],
                principal='owned' if self.fact['loggedIn'] else 'anonymous',protectedAccess=self.fact['loggedIn'])|self.proof_edit
        raise AssertionError('Unexpected synthetic provider route')
    def status(self):
        self.requests.append('status')
        return dict(providerVersion=2,instance=PROVIDER,runId=RUN,capturedEpochMs=self.provider_epoch_ms(),eventSequence=self.provider_sequence,
            accountExists=True,heldRequests=0,armedHold=False,inflightRequests=0,
            accessTokens=int(self.fact['loggedIn']),refreshTokens=int(self.fact['loggedIn']),grantsEnabled=True)|self.status_edit
    def logged_in(self):
        principal=hashlib.sha256(('e2e-'+RUN).encode()).hexdigest()
        self.fact.update(loggedIn=True,principalSha256=principal)
        self.fact['observation'].update(tokenPresent=True,tokenValid=True,refreshPresent=True)
        original=self.probe.mutate
        def response(packet):
            original(packet)
            if packet['operation']=='read':packet['source'].update(httpStatus=200,networkError=0,tokenAttached=True,principalSha256=principal)
        self.probe.mutate=response


class AuthenticationSampleTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);os.chmod(self.root,0o700)
        self.sources=Sources(self.root)
        self.lock=ScriptSourceLock(self.root/'authentication-sources.lock')

    def reader(self,role='primary',**changes):
        return AuthenticationSamples(self.sources,'private-selector',self.sources.client,RUN,PROVIDER,role,0,self.lock,
            epoch_ms=lambda:9000000,monotonic=lambda:self.sources.clock,**changes)
    def acquire(self,role='primary'):
        with self.lock.held():return self.reader(role).read(TICKET,19000)
    def stored(self,role='primary'):
        outer=PrivateFeatureState(self.root/('authentication-'+role+'-0-samples.json')).read()
        return unpack(outer['payload'])[0]
    def join(self,frame,*,actor=False):
        return measurement(RUN,TICKET,ORIGIN,frame,provider_instance=PROVIDER,native_epoch=20000,
            host_epoch=9000000,after_epoch=19000,actor=actor)

    def test_five_original_sources_are_fresh_and_each_observation_retires_actual_measurement_leases(self):
        first=self.acquire();before=deepcopy(self.stored())
        second=self.acquire();after=self.stored()
        self.assertEqual((1,2),(first['sequence'],second['sequence']))
        self.assertEqual(dict(principal='anonymous',dialog=False,error='none',pending=False,
            protectedAccess=False,delayedGrantOutstanding=False),second['state'])
        self.assertEqual([],second['resources']);self.assertEqual(20000,second['capturedEpochMs'])
        self.assertNotEqual(before['native']['requestId'],after['native']['requestId'])
        self.assertGreater(after['native']['sequence'],before['native']['sequence'])
        self.assertGreater(after['login']['sourceSequence'],before['login']['sourceSequence'])
        self.assertGreater(after['probe']['sequence'],before['probe']['sequence'])
        self.assertIsNone(PrivateFeatureState(self.root/'origin.json').read())
        self.assertIsNone(PrivateFeatureState(self.root/'primary-probe.json').read())
        self.assertFalse(self.sources.origin.path.exists());self.assertFalse(self.sources.origin.manifest.exists())
        self.assertEqual([],self.sources.login.inputs);self.assertEqual([],self.sources.tablet.input_requests)
        self.assertFalse(any('proof' in path for path in self.sources.requests))

    def test_independent_actor_reacquires_actual_sources_and_server_proof_with_own_lease(self):
        primary=self.acquire();saved=deepcopy(self.stored());actor=self.acquire('actor')
        self.assertEqual(primary['state'],actor['state']);self.assertEqual(saved,self.stored())
        self.assertEqual(1,actor['sequence']);self.assertIsNotNone(self.stored('actor')['frame']['proof'])
        self.assertNotEqual(saved['frame']['probe']['requestId'],self.stored('actor')['frame']['probe']['requestId'])
        self.assertIsNone(PrivateFeatureState(self.root/'actor-probe.json').read())

    def test_owned_success_requires_actual_native_token_cached_principal_and_current_http_200(self):
        self.sources.logged_in();actual=self.acquire('actor')
        self.assertTrue(actual['state']['protectedAccess']);self.assertEqual('owned',actual['state']['principal'])
        self.assertEqual(['connection:account-session','connection:remote-account-authority'],actual['resources'])
        frame=self.stored('actor')['frame'];frame['probe']['source']['httpStatus']=401
        with self.assertRaises(NativeUIError):self.join(frame,actor=True)

    def test_pending_login_and_visible_invalid_credentials_are_measured_without_mapping_ticket_to_result(self):
        self.sources.login.ui.dialog=True;self.sources.login.ui.error='invalid-credentials'
        actual=self.acquire();self.assertTrue(actual['state']['dialog']);self.assertEqual('invalid-credentials',actual['state']['error'])
        self.sources.fact['observation']['loginPending']=True
        self.sources.login.ui.pending=True;self.sources.login.ui.waiting=True;self.sources.login.ui.error='none'
        actual=self.acquire();self.assertTrue(actual['state']['pending']);self.assertFalse(actual['state']['protectedAccess'])
        self.assertIn('connection:account-request',actual['resources'])

    def test_foreign_or_wrong_endpoint_account_is_refused_before_staging_or_protected_get(self):
        for edit in (dict(principalSha256='f'*64),dict(endpointSha256='f'*64)):
            with self.subTest(edit=edit):
                with tempfile.TemporaryDirectory() as directory:
                    root=Path(directory);os.chmod(root,0o700);sources=Sources(root)
                    if 'principalSha256' in edit:sources.fact.update(edit)
                    else:sources.fact['observation'].update(edit)
                    lock=ScriptSourceLock(root/'authentication-sources.lock')
                    with lock.held(),self.assertRaises(NativeUIError):
                        AuthenticationSamples(sources,'selector',sources.client,RUN,PROVIDER,'primary',0,lock).read(TICKET,19000)
                    self.assertEqual([],sources.origin.commands);self.assertEqual([],sources.probe.commands)

    def test_missing_ignored_and_retained_originals_leave_pending_ownership_without_a_successful_reconstruction(self):
        for fault in ('native','login','probe','origin-cleanup','probe-cleanup'):
            with self.subTest(fault=fault):
                with tempfile.TemporaryDirectory() as directory:
                    root=Path(directory);os.chmod(root,0o700);sources=Sources(root)
                    if fault=='native':sources.native.ignored=True
                    if fault=='login':sources.login.mutate=lambda packet:packet.update(commandId='f'*32)
                    if fault=='probe':sources.probe.ignored=True
                    if fault=='origin-cleanup':sources.origin.fault='keep-files'
                    if fault=='probe-cleanup':sources.probe.pending=True
                    lock=ScriptSourceLock(root/'authentication-sources.lock')
                    with lock.held():
                        reader=AuthenticationSamples(sources,'selector',sources.client,RUN,PROVIDER,'primary',0,lock)
                        with self.assertRaises(NativeUIError):reader.read(TICKET,19000)
                        with self.assertRaises(NativeUIError):reader.read(TICKET,19000)
                        before=len(sources.native.commands)
                        with self.assertRaises(NativeUIError):AuthenticationSamples(sources,'selector',sources.client,RUN,PROVIDER,'primary',0,lock)
                        self.assertEqual(before,len(sources.native.commands))
                    retained=unpack(reader.store.read()['payload'])[0]
                    self.assertEqual('reading',retained['phase']);self.assertEqual(0,retained['sequence'])
                    if fault in ('login','origin-cleanup'):self.assertIsNotNone(PrivateFeatureState(root/'origin.json').read())
                    if fault in ('probe','probe-cleanup'):self.assertIsNotNone(PrivateFeatureState(root/'primary-probe.json').read())

    def test_wrong_provider_ticket_or_nonce_cannot_be_an_independent_actor_fact(self):
        for edit in (dict(instance='f'*32),dict(ticket='f'*32),dict(requestId='f'*32),dict(status=200),dict(capturedEpochMs=8998499)):
            self.sources.proof_edit=edit
            with tempfile.TemporaryDirectory() as directory:
                root=Path(directory);os.chmod(root,0o700);sources=Sources(root);sources.proof_edit=edit
                lock=ScriptSourceLock(root/'authentication-sources.lock')
                with lock.held(),self.assertRaises(NativeUIError):
                    AuthenticationSamples(sources,'selector',sources.client,RUN,PROVIDER,'actor',0,lock,epoch_ms=lambda:9000000).read(TICKET,19000)

    def test_split_native_account_birth_probe_ui_scope_and_changed_credential_generation_fail_join(self):
        self.acquire();original=self.stored()['frame']
        for source,key,value in (('nativeAfter','instance','f'*32),('probe','instance','f'*32),
                                 ('nativeAfter','sequence',1),('nativeAfter','requestId',original['nativeBefore']['requestId'])):
            frame=deepcopy(original);frame[source][key]=value
            with self.subTest(source=source,key=key),self.assertRaises(NativeUIError):self.join(frame)
        for key,value in (('credentialGeneration',2),('refreshPresent',True),('endpointSha256','f'*64)):
            frame=deepcopy(original);frame['nativeAfter']['account']['observation'][key]=value
            with self.subTest(key=key),self.assertRaises(NativeUIError):self.join(frame)

    def test_missing_or_unretired_probe_and_original_origin_files_never_count_as_clean(self):
        self.acquire();original=self.stored()['frame']
        for source,key,value in (('probeReleased','source',dict(inflight=False,responseBytes=1,credentialBytes=0,released=True)),
            ('probeReleased','sequence',original['probe']['sequence']),('originAbsent','source',original['originPresent']['source'])):
            frame=deepcopy(original);frame[source][key]=value
            with self.subTest(source=source,key=key),self.assertRaises(NativeUIError):self.join(frame)
        frame=deepcopy(original);frame['probeOwner']['probe']['ticket']='f'*32
        with self.assertRaises(NativeUIError):self.join(frame)

    def test_stale_originals_clock_domains_after_barrier_and_incomplete_ui_are_rejected(self):
        self.acquire();original=self.stored()['frame']
        for source,key,value in (('login','capturedEpochMs',18499),('nativeBefore','capturedEpochMs',18999),
            ('status','capturedEpochMs',8999999),('delayed','capturedEpochMs',8998499),('status','instance','f'*32)):
            frame=deepcopy(original);frame[source][key]=value
            with self.subTest(source=source,key=key),self.assertRaises(NativeUIError):self.join(frame)
        frame=deepcopy(original);frame['tablet']['scriptInventory']['complete']=False
        with self.assertRaises(NativeUIError):self.join(frame)

    def test_fresh_transport_cursors_cannot_hide_native_ui_or_delayed_history_regression_after_reconstruction(self):
        self.acquire();self.sources.native.sequence=0
        with self.assertRaises(NativeUIError):self.acquire()
        self.assertEqual('reading',self.stored()['phase'])

    def test_recreated_sampler_does_not_reset_original_login_or_tablet_cursors(self):
        self.acquire();self.sources.login.source_sequence=0
        with self.assertRaises(NativeUIError):self.acquire()
        self.assertEqual('reading',self.stored()['phase'])

    def test_recreated_sampler_rejects_rewritten_saved_originals_without_source_dispatch(self):
        self.acquire()
        store=PrivateFeatureState(self.root/'authentication-primary-0-samples.json')
        old=store.read();state=unpack(old['payload'])[0]
        state['frame']['probeReleased']['source']['credentialBytes']=1
        store.write(old|dict(payload=pack([state])),old)
        before=len(self.sources.native.commands)
        with self.lock.held(),self.assertRaises(NativeUIError):self.reader()
        self.assertEqual(before,len(self.sources.native.commands))

    def test_delayed_grant_original_issuance_is_retained_without_turning_it_into_local_login(self):
        row=dict(requestId='e'*32,requestTicket=TICKET,startedEpochMs=8999900,releasedEpochMs=8999950,
            issuedEpochMs=8999950,status=200,state='issued',accessValid=True,refreshValid=True)
        self.sources.delayed_edit=dict(requests=[row],delayedGrantOutstanding=True)
        self.sources.status_edit=dict(accessTokens=1,refreshTokens=1)
        actual=self.acquire();self.assertTrue(actual['state']['delayedGrantOutstanding'])
        self.assertFalse(actual['state']['protectedAccess']);self.assertEqual('anonymous',actual['state']['principal'])
        self.assertEqual(['connection:remote-account-authority'],actual['resources'])
        self.sources.delayed_edit=dict(requests=[],delayedGrantOutstanding=False)
        with self.assertRaises(NativeUIError):self.acquire()

    def test_remote_status_cannot_regress_original_provider_clock_sequence_or_types(self):
        self.acquire();frame=self.stored()['frame']
        for edit in (dict(eventSequence=0),dict(capturedEpochMs=8999999),dict(accessTokens=True),dict(heldRequests=2)):
            wrong=deepcopy(frame);wrong['status'].update(edit)
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):self.join(wrong)

    def test_lost_completed_write_return_requires_another_fresh_acquisition(self):
        with self.lock.held():
            reader=self.reader();write=reader.store.write
            def lost(value,previous):
                write(value,previous)
                if unpack(value['payload'])[0]['phase']=='ready':raise OSError('Synthetic lost persistence return')
            with patch.object(reader.store,'write',side_effect=lost),self.assertRaises(OSError):reader.read(TICKET,19000)
            before=len(self.sources.native.commands)
            actual=self.reader().read(TICKET,19000)
            self.assertGreater(len(self.sources.native.commands),before);self.assertEqual(2,actual['sequence'])

    def test_changed_ui_account_context_cannot_borrow_an_actual_native_token(self):
        self.sources.login.ui.dialog=True;self.acquire();frame=self.stored()['frame']
        for edit in (dict(accountInstance='f'*32),dict(credentialGeneration=2),dict(endpointSha256='f'*64),dict(nativePending=True)):
            wrong=deepcopy(frame);wrong['login']['controls'][0].update(edit)
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):self.join(wrong)

    def test_whole_deadline_includes_staging_and_guard_loss_preserves_pending_intent(self):
        original=self.sources.origin.send
        def late(value):original(value);self.sources.clock=20
        self.sources.origin.send=late
        with self.assertRaises(NativeUIError):self.acquire()
        self.assertEqual('reading',self.stored()['phase']);self.assertEqual([],self.sources.probe.commands)

    def test_without_held_shared_channel_lock_no_source_can_be_opened(self):
        with self.assertRaises(NativeUIError):self.reader()
        self.assertEqual([],self.sources.calls);self.assertEqual([],self.sources.native.commands)

    def test_failed_pending_write_and_stale_owner_do_not_dispatch_or_overwrite_other_history(self):
        with self.lock.held():
            old=self.reader();current=self.reader();current.read(TICKET,19000)
            before=len(self.sources.native.commands);saved=deepcopy(current.store.read())
            with self.assertRaises(NativeUIError):old.read(TICKET,19000)
            self.assertEqual(saved,current.store.read());self.assertEqual(before,len(self.sources.native.commands))
            current=self.reader()
            with patch.object(current.store,'write',side_effect=OSError('Synthetic storage failure')):
                with self.assertRaises(OSError):current.read(TICKET,19000)
            self.assertEqual(before,len(self.sources.native.commands))

    def interrupt_at_proof(self,reader):
        original=self.sources.client.request
        def unavailable(path):
            if '/account/proof/' in path:raise ValueError('Synthetic retired protected request')
            return original(path)
        with patch.object(self.sources.client,'request',side_effect=unavailable),self.assertRaises(ValueError):reader.read(TICKET,19000)
        self.sources.active['ticket']='f'*32

    def test_actual_phase_change_retires_own_measurement_leases_and_requires_new_originals_before_publication(self):
        self.acquire('actor');previous=deepcopy(self.stored('actor')['frame'])
        with self.lock.held():
            reader=self.reader('actor');self.interrupt_at_proof(reader)
            retirement=reader.retire_changed_ticket()
            self.assertEqual(TICKET,retirement['ticket']);self.assertEqual('f'*32,retirement['active']['ticket'])
            self.assertNotIn('state',retirement);self.assertEqual(previous,reader.state['frame'])
            self.assertIsNone(self.sources.account_origin_store('selector').read())
            self.assertIsNone(self.sources.account_probe_store('selector',role='actor').read())
            self.assertFalse(self.sources.origin.path.exists())
            recovered=self.reader('actor');actual=recovered.read('f'*32,19000)
            self.assertEqual(3,actual['sequence']);self.assertEqual('f'*32,recovered.state['frame']['probe']['ticket'])
            self.assertNotEqual(previous['probe']['requestId'],recovered.state['frame']['probe']['requestId'])
        self.assertEqual([],self.sources.login.inputs);self.assertEqual([],self.sources.tablet.input_requests)

    def test_same_ticket_source_failure_cannot_be_forgotten_as_a_transition(self):
        with self.lock.held():
            reader=self.reader('actor');self.interrupt_at_proof(reader);self.sources.active['ticket']=TICKET
            before=len(self.sources.native.commands)
            with self.assertRaises(NativeUIError):reader.retire_changed_ticket()
            self.assertEqual(before,len(self.sources.native.commands));self.assertEqual('reading',reader.state['phase'])
            self.assertIsNotNone(self.sources.account_probe_store('selector',role='actor').read())

    def test_missing_foreign_or_untyped_active_phase_cannot_authorize_source_retirement(self):
        with self.lock.held():
            reader=self.reader('actor');self.interrupt_at_proof(reader);active=deepcopy(self.sources.active)
            for edit in (dict(runId='f'*32),dict(area='scripts'),dict(schemaVersion=True),dict(ticket='foreign'),
                         dict(stimulus=dict(verb='login-submit',inputs={'account':'expected'}))):
                self.sources.active=active|edit
                with self.subTest(edit=edit),self.assertRaises((NativeUIError,ValueError)):reader.retire_changed_ticket()
            self.assertEqual('reading',reader.state['phase']);self.assertTrue(self.sources.origin.path.exists())

    def test_retained_probe_bytes_still_fail_retirement_after_a_real_phase_change(self):
        with self.lock.held():
            reader=self.reader('actor');self.interrupt_at_proof(reader);self.sources.probe.pending=True
            with self.assertRaises(NativeUIError):reader.retire_changed_ticket()
            self.assertEqual('reading',reader.state['phase']);self.assertIsNotNone(self.sources.account_probe_store('selector',role='actor').read())
            self.assertEqual(1,sum(command['operation']=='read' for command in self.sources.probe.commands))

    def test_retained_origin_files_still_fail_retirement_after_actual_probe_drain(self):
        with self.lock.held():
            reader=self.reader('actor');self.interrupt_at_proof(reader);self.sources.origin.fault='keep-files'
            with self.assertRaises(NativeUIError):reader.retire_changed_ticket()
            self.assertEqual('reading',reader.state['phase']);self.assertIsNotNone(self.sources.account_origin_store('selector').read())
            self.assertIsNone(self.sources.account_probe_store('selector',role='actor').read());self.assertTrue(self.sources.origin.path.exists())

    def test_phase_change_after_missing_origin_stage_return_uses_original_durable_owner_without_restaging(self):
        with self.lock.held():
            reader=self.reader('actor');stage=OwnedAccountOrigin.stage
            def lost(owner,run,origin):stage(owner,run,origin);raise OSError('Synthetic lost stage return')
            with patch.object(OwnedAccountOrigin,'stage',new=lost),self.assertRaises(OSError):reader.read(TICKET,19000)
            self.sources.active['ticket']='f'*32;reader.retire_changed_ticket();recovered=self.reader('actor')
            self.assertEqual('ready',recovered.state['phase']);self.assertFalse(self.sources.origin.path.exists())
            self.assertEqual(1,sum(command['operation']=='stage' for command in self.sources.origin.commands))

    def test_phase_change_after_lost_protected_get_return_never_reissues_get(self):
        with self.lock.held():
            reader=self.reader('actor');acquire=OwnedAccountProbe.acquire
            def lost(owner,run,ticket):acquire(owner,run,ticket);raise OSError('Synthetic lost GET return')
            with patch.object(OwnedAccountProbe,'acquire',new=lost),self.assertRaises(OSError):reader.read(TICKET,19000)
            self.sources.active['ticket']='f'*32;reader.retire_changed_ticket()
            self.assertEqual(1,sum(command['operation']=='read' for command in self.sources.probe.commands))
            self.assertIsNone(self.sources.account_probe_store('selector',role='actor').read());self.reader('actor')

    def test_lost_probe_release_return_can_only_drain_the_original_owned_nonce(self):
        with self.lock.held():
            reader=self.reader('actor');release=OwnedAccountProbe.release
            def lost(owner):release(owner);raise OSError('Synthetic lost drain return')
            with patch.object(OwnedAccountProbe,'release',new=lost),self.assertRaises(OSError):reader.read(TICKET,19000)
            self.sources.active['ticket']='f'*32;reader.retire_changed_ticket();self.reader('actor')
            self.assertEqual(1,sum(command['operation']=='read' for command in self.sources.probe.commands))
            self.assertEqual(1,len({command['requestId'] for command in self.sources.probe.commands}))

    def test_changed_native_birth_or_candidate_cannot_retire_the_old_scope(self):
        with self.lock.held():
            reader=self.reader('actor');self.interrupt_at_proof(reader)
            mutate=self.sources.native.mutate
            self.sources.native.mutate=lambda packet:(mutate(packet),packet.update(instance='f'*32))
            with self.assertRaises(NativeUIError):reader.retire_changed_ticket()
            self.assertEqual('reading',reader.state['phase']);self.assertTrue(self.sources.origin.path.exists())

    def test_retirement_whole_deadline_includes_fresh_native_acquisition(self):
        with self.lock.held():
            reader=self.reader('actor');self.interrupt_at_proof(reader)
            send=self.sources.native.send
            def late(command):send(command);self.sources.clock=20
            self.sources.native.send=late
            with self.assertRaises(NativeUIError):reader.retire_changed_ticket()
            self.assertEqual('reading',reader.state['phase']);self.assertTrue(self.sources.origin.path.exists())

    def test_legacy_sample_version_is_not_rewritten_or_queried_during_recreation(self):
        self.acquire();store=PrivateFeatureState(self.root/'authentication-primary-0-samples.json')
        old=store.read();legacy=old|dict(authenticationSamplesVersion=1);store.write(legacy,old)
        before=len(self.sources.native.commands)
        with self.lock.held(),self.assertRaises(NativeUIError):self.reader()
        self.assertEqual(before,len(self.sources.native.commands));self.assertEqual(legacy,store.read())

    def test_new_request_nonce_cannot_hide_a_replayed_original_peer_event_cursor(self):
        self.acquire('actor');self.sources.proof_edit=dict(eventSequence=1)
        with self.assertRaises(NativeUIError):self.acquire('actor')
        self.assertEqual('reading',self.stored('actor')['phase'])
        self.assertIsNotNone(self.sources.account_probe_store('selector',role='actor').read())

    def test_pure_archive_decoder_validates_original_scope_without_runtime_or_native_contact(self):
        self.acquire();store=PrivateFeatureState(self.root/'authentication-primary-0-samples.json')
        before=len(self.sources.native.commands)
        with patch.object(self.sources,'normal_feature_runtime',side_effect=AssertionError('Unexpected archive SDK access')):
            archived=AuthenticationSamples.archive(store.read(),client=self.sources.client,run=RUN,
                provider_instance=PROVIDER,role='primary',stage=0,binding=BINDING)
        self.assertEqual('ready',archived['phase']);self.assertEqual(before,len(self.sources.native.commands))
        with self.assertRaises(NativeUIError):AuthenticationSamples.archive(store.read(),client=self.sources.client,run=RUN,
            provider_instance=PROVIDER,role='actor',stage=0,binding=BINDING)


if __name__=='__main__':unittest.main()
