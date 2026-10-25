"""Abort-only account cleanup at the actual existing whole/native boundary."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from unittest.mock import patch
import threading
import time
import unittest

from adapters.normal_ui import NativeUIError
from ios.adapters.avatar_failed_preparation import AvatarFailedPreparation
from ios.self_tests.avatar_terminal_domain import TerminalDomain
from ios.self_tests.avatar_prepare_fixture import RUN
from self_tests import test_account_provider as tls


class AvatarFailedPreparationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):tls.AccountProviderTests.setUpClass()
    @classmethod
    def tearDownClass(cls):tls.AccountProviderTests.tearDownClass()

    def test_failed_before_first_login_never_finishes_setup_or_enters_account_input(self):
        domain=TerminalDomain(self);feature=domain.owners['primary']
        with feature.held():
            feature.initialize();failed=deepcopy(feature.previous);owner=AvatarFailedPreparation(feature)
            inputs=list(domain.natives['primary'].lifecycle_inputs)
            self.assertTrue(owner.restore_account());self.assertEqual('accounts-restored',owner.state['phase'])
            self.assertEqual(failed,feature.store.read());self.assertIsNone(owner.state['loginBefore'])
            self.assertIsNone(owner.state['preferences']);self.assertFalse(owner.state['account']['account']['loggedIn'])
            self.assertEqual(inputs,domain.natives['primary'].lifecycle_inputs)
            self.assertEqual('failed',owner.abort.state['phase']);self.assertIsNone(feature.state['initial'])

    def test_failure_after_actual_login_restores_only_original_account_preferences_without_marker_setup(self):
        domain=TerminalDomain(self);feature=domain.owners['primary']
        with feature.held():
            feature.initialize();feature.login();failed=deepcopy(feature.previous)
            owner=AvatarFailedPreparation(feature);self.assertTrue(owner.restore_account())
            self.assertEqual('restored',owner.validate_login(owner.state['loginAfter'])['phase'])
            self.assertEqual(owner.validate_login(owner.state['loginBefore'])['preferences']['preferences'],owner.state['preferences']['preferences'])
            self.assertEqual(failed,feature.store.read());self.assertIsNone(feature.state['initial'])
            self.assertFalse(owner.state['account']['account']['loggedIn']);self.assertEqual('failed',owner.abort.state['phase'])

    def test_changed_failed_original_refuses_any_later_input(self):
        domain=TerminalDomain(self);feature=domain.owners['primary']
        with feature.held():
            feature.initialize();owner=AvatarFailedPreparation(feature);value=feature.store.read();value['role']='actor'
            feature.store.write(value,feature.previous)
            with self.assertRaises(NativeUIError):owner.restore_account()

    def test_actual_paired_failed_early_setup_ends_once_and_replays_without_live_sdk_or_scene_success(self):
        domain=TerminalDomain(self);features=domain.owners;owners={};failed={}
        for role,feature in features.items():
            with feature.held():
                feature.initialize();failed[role]=deepcopy(feature.previous);owner=AvatarFailedPreparation(feature);owners[role]=owner
                self.assertTrue(owner.restore_account());self.assertTrue(owner.retire_native_inputs())
        for role,feature in features.items():
            with feature.held(paired=True):self.assertFalse(owners[role].process_round())
        domain.sleep(1.6)
        for role,feature in features.items():
            with feature.held(paired=True):self.assertFalse(owners[role].process_round())
        domain.sleep(1.6)
        for role,feature in features.items():
            with feature.held(paired=True):self.assertTrue(owners[role].process_round())
        for role,feature in features.items():
            with feature.held(paired=True):
                self.assertTrue(owners[role].retire_provider())
        for role,feature in features.items():
            with feature.held(paired=True):
                owner=owners[role];result=owner.result()
                self.assertEqual('failed',result['status']);self.assertTrue(result['performed'])
                self.assertEqual(failed[role],feature.store.read())
                self.assertEqual(1,domain.natives[role].lifecycle_inputs.count('app.stop'))
                self.assertEqual(1,domain.sdk_requests.count((role,'DELETE')))
        calls=list(domain.sdk_requests)
        for role,feature in features.items():
            with feature.held(paired=True),patch.object(domain.runtime.adapter,'_target',side_effect=AssertionError('No live SDK resolver in failed archive')):
                original=AvatarFailedPreparation.archive(feature,owners[role].previous)
                self.assertEqual(owners[role].original_result(),original.original_result())
        self.assertEqual(calls,domain.sdk_requests)
        self.assertFalse(domain.server.phase_retirements.snapshot(RUN)['entries'])

    def test_actual_incomplete_protected_login_releases_original_leases_and_unknown_release_is_never_repeated(self):
        from adapters.native_account_probe import OwnedAccountProbe,NativeAccountProbe
        domain=TerminalDomain(self);feature=domain.owners['primary'];acquire=OwnedAccountProbe.acquire
        with feature.held():
            feature.initialize()
            def lost_acquire(probe,*args):acquire(probe,*args);raise OSError('Actual protected response return lost')
            with patch.object(OwnedAccountProbe,'acquire',lost_acquire),self.assertRaises(NativeUIError):feature.login()
            failed=deepcopy(feature.previous);owner=AvatarFailedPreparation(feature);perform=NativeAccountProbe._perform;released=[]
            def lost_release(probe,query):
                result=perform(probe,query)
                if query['operation']=='release' and not released:
                    released.append(query.copy());raise OSError('Actual protected Release return lost')
                return result
            with patch.object(NativeAccountProbe,'_perform',lost_release),self.assertRaises(OSError):owner.restore_account()
            owner=AvatarFailedPreparation(feature);self.assertTrue(owner.restore_account())
            queries=owner.state['leases']['probe']['queries']
            self.assertEqual(1,len([row for row in queries if row['operation']=='release']))
            self.assertEqual(released[0],queries[0]);self.assertEqual('inspect',queries[-1]['operation'])
            self.assertTrue(owner.state['leases']['probe']['complete']);self.assertTrue(owner.state['leases']['origin']['complete'])
            self.assertEqual('reading',owner.validate_login(owner.state['loginBefore'])['protected'][-1]['phase'])
            self.assertEqual(failed,feature.store.read());self.assertFalse(owner.state['account']['account']['loggedIn'])

    def ready_peer_failure(self):
        domain=TerminalDomain(self);primary,actor=domain.owners['primary'],domain.owners['actor']
        with actor.held():actor.initialize();actor.login()
        sleep=primary.sleep;started=[];failed_input=[]
        def prepare_peer(seconds):
            if not started and primary.state is not None and primary.state['initial'] is not None:
                started.append(True);actor.prepare()
            sleep(seconds)
        primary.sleep=prepare_peer
        def original_failure():failed_input.append(True);raise OSError('Actual primary Scope preparation interrupted')
        try:
            with patch.object(domain.scenes['primary'].scope,'prepare',original_failure),self.assertRaises((NativeUIError,OSError)):primary.prepare()
        finally:primary.sleep=sleep
        self.assertEqual([True],started);self.assertEqual([True],failed_input)
        failed={}
        for owner,phase in ((primary,'preparing'),(actor,'ready')):
            with owner.held():owner.load();self.assertEqual(phase,owner.state['phase']);failed[owner.role]=deepcopy(owner.previous)
        return domain,failed

    def api_failed_case(self,*,logged_in=False,negative_archive=False,canonical_existing=False,ready_peer=False):
        from adapters.script_feature.lock import ScriptSourceBusy
        from feature_journeys.contract import VERSION
        from ios.avatar_observer import run_flow
        from ios.adapters.avatar_api_entry import scope
        from ios.self_tests.avatar_cleanup_scheduler import CleanupScheduler
        if ready_peer:domain,failed=self.ready_peer_failure()
        else:
            domain=TerminalDomain(self);failed={}
            for owner in domain.owners.values():
                with owner.held():
                    owner.initialize()
                    if logged_in:owner.login()
                    failed[owner.role]=deepcopy(owner.previous)
        primary,actor=domain.owners['primary'],domain.owners['actor']
        domain.client.activate('f'*32,'cleanup',{});result=[]
        scheduler=CleanupScheduler(domain.clock,domain.sleep)
        started=domain.clock[0]
        primary.sleep=lambda seconds:scheduler.sleep('primary',seconds)
        actor.sleep=lambda seconds:scheduler.sleep('actor',seconds)
        def independent():
            try:result.append(run_flow(actor,dict(durationSeconds=60,target='actor',primaryTarget='primary'),
                monotonic=lambda:domain.clock[0],sleep=lambda seconds:scheduler.sleep('actor',seconds)))
            except BaseException as error:result.append(error)
            finally:scheduler.finish('actor')
        worker=threading.Thread(target=independent,daemon=True);worker.start();self.addCleanup(worker.join,1)
        try:
            with scope(lambda:domain.clock[0]):
                for _ in range(128):
                    try:
                        self.assertEqual(dict(performed=True),primary.cleanup(dict(contractVersion=VERSION,runId=RUN)));break
                    except ScriptSourceBusy:time.sleep(.005)
                else:self.fail('Actual independent source lock never became available')
            self.assertLess(domain.clock[0]-started,25)
            print('Avatar failed cleanup original model clock: '+str(dict(loggedInSetup=logged_in,
                elapsedMs=round((domain.clock[0]-started)*1000),wakeSteps=len(scheduler.steps),
                waitUnionMs=round(sum(row['after']-row['before'] for row in scheduler.steps)*1000))),flush=True)
            self.assertFalse(domain.server.phase_retirements.snapshot(RUN)['entries'])
            domain.client.request('/runs/'+RUN,method='DELETE')
        finally:scheduler.finish('primary')
        worker.join(10);self.assertFalse(worker.is_alive());self.assertEqual([2],result)
        for owner in (primary,actor):
            with owner.held(paired=True):
                self.assertEqual(failed[owner.role],owner.store.read());self.assertTrue(owner.failed_preparation_ended())
            self.assertEqual(1,domain.natives[owner.role].lifecycle_inputs.count('app.stop'))
            self.assertEqual(1,domain.sdk_requests.count((owner.role,'DELETE')))
        from ios.adapters.avatar_failed_archive import verify
        from adapters.normal_feature_state import PrivateFeatureState
        calls=list(domain.sdk_requests);members=set()
        originals={}
        with patch.object(domain.runtime.adapter,'_target',side_effect=AssertionError('No target resolver during canonical failed replay')):
            for owner in (primary,actor):
                original=PrivateFeatureState(owner.store.path.with_name('ios-avatar-'+owner.role+'-'+owner.run+'-failed-preparation.json')).read()
                originals[owner.role]=original
                self.assertEqual(owner.state['bindings'][owner.role],verify(domain.runtime.adapter,owner.selector,
                    owner.store.read(),original,membership=members))
            if negative_archive:
                from adapters.script_feature.history import unpack
                private=PrivateFeatureState(primary.store.path.with_name('ios-avatar-primary-private-login-input.json'))
                state=unpack(originals['primary']['payload'])[0]
                unknown=dict(inputVersion=2,binding=primary.state['bindings']['primary'],runId=state['childRunId'],
                    inputId='e'*32,sourceInstance=None,transferPending=True)
                private.write(unknown,None)
                with self.assertRaises(NativeUIError):verify(domain.runtime.adapter,primary.selector,primary.store.read(),originals['primary'])
                private.discard(unknown)
                path=primary.store.path;raw=path.read_bytes();checks=[]
                def changed_original():
                    checks.append(True)
                    if len(checks)==3:
                        with path.open('ab') as stream:stream.write(b' ')
                try:
                    with self.assertRaises(NativeUIError):verify(domain.runtime.adapter,primary.selector,primary.store.read(),originals['primary'],check=changed_original)
                    self.assertGreaterEqual(len(checks),3)
                finally:path.write_bytes(raw)
                foreign=deepcopy(originals['primary']);foreign['role']='actor'
                with self.assertRaises(NativeUIError):verify(domain.runtime.adapter,primary.selector,primary.store.read(),foreign)
            if canonical_existing:
                from ios.adapters.avatar_existing import finalize_existing,retire_existing
                scopes=[]
                def retained_scope(target,scope):
                    owner=domain.owners[target]
                    self.assertEqual({key:item for key,item in owner.state['bindings'][owner.role].items() if key!='processIdentity'},scope)
                    self.assertFalse(domain.sdk_exists[target]);self.assertEqual('retired',domain.installed[target].make().record()['phase'])
                    scopes.append(target);return domain.natives[target].target
                domain.runtime.adapter._retired_candidate_scope=retained_scope
                before={path:path.read_bytes() for scene in domain.scenes.values() for path in scene.root.rglob('*') if path.is_file()}
                for owner in (primary,actor):
                    self.assertTrue(finalize_existing(domain.runtime,owner.selector,None,None))
                    self.assertEqual(dict(performed=True),retire_existing(domain.runtime,owner.selector,None,None))
                self.assertEqual(['primary','primary','actor','actor'],scopes)
                self.assertEqual(before,{path:path.read_bytes() for scene in domain.scenes.values() for path in scene.root.rglob('*') if path.is_file()})
        self.assertEqual(calls,domain.sdk_requests);self.assertTrue(members)

    def test_actual_cleanup_api_and_independent_worker_retire_failed_setup_and_exit_failed(self):
        self.api_failed_case()

    def test_actual_logged_in_failed_cleanup_api_preserves_original_preferences_and_ends_both_sdk_roles(self):
        self.api_failed_case(logged_in=True)

    def test_actual_ready_actor_worker_and_failed_primary_cleanup_api_keep_original_failure_and_end_once(self):
        self.api_failed_case(ready_peer=True)

    def test_sdk_free_failed_archive_refuses_unknown_credentials_changed_same_inode_and_foreign_original(self):
        self.api_failed_case(negative_archive=True)

    def test_generic_existing_hooks_authorize_only_original_ended_sdk_scope_without_another_delete_or_graph_write(self):
        self.api_failed_case(canonical_existing=True)

    def test_lost_initial_gpu_return_is_retired_without_new_capture_or_marker_preparation(self):
        from adapters.owned_vulkan_world_frame import VulkanWorldFrameOwner
        from ios.adapters.avatar_restoration_frames import IOSAvatarRestorationFrames
        domain=TerminalDomain(self);feature=domain.owners['primary'];capture=VulkanWorldFrameOwner.capture;attempts=[]
        with feature.held():
            feature.initialize();feature.login();failed=deepcopy(feature.previous)
            scope=domain.runtime._avatar_marker_scope(feature.selector,feature.client,RUN,'primary',feature.root,feature.state['initialTicket'],feature.lock)
            frames=IOSAvatarRestorationFrames(domain.runtime,feature.selector,scope,feature.root,feature.lock,
                epoch_ms=domain.host,monotonic=lambda:domain.clock[0],sleep=domain.sleep)
            def lost(owner,ticket):
                attempts.append(owner.request_id);capture(owner,ticket);raise OSError('Actual initial GPU return lost')
            with patch.object(VulkanWorldFrameOwner,'capture',lost),self.assertRaises(OSError):frames.capture('initial')
            owner=AvatarFailedPreparation(feature)
            with patch.object(VulkanWorldFrameOwner,'capture',side_effect=AssertionError('No failed capture resend')):
                self.assertTrue(owner.retire_native_inputs())
            self.assertEqual(1,len(attempts));self.assertIsNone(owner.state['scene']['scope'])
            self.assertIsNotNone(owner.state['scene']['restoration']);self.assertEqual(failed,feature.store.read())
            self.assertIsNone(scope.state['baseline']);self.assertFalse(scope.frames)

    def test_actual_ready_actor_joins_original_peer_failure_without_relabeling_or_resuming_primary_setup(self):
        from ios.adapters.avatar_abort import IOSAvatarAbort
        domain,failed=self.ready_peer_failure();primary,actor=domain.owners['primary'],domain.owners['actor']
        pfailed,aready=failed['primary'],failed['actor']
        with actor.held(paired=True),self.assertRaises(NativeUIError):
            IOSAvatarAbort(actor,epoch_ms=domain.host,monotonic=lambda:domain.clock[0])
        with primary.held():p=AvatarFailedPreparation(primary)
        with actor.held(paired=True):
            a=AvatarFailedPreparation(actor)
            self.assertEqual('peer-preparation-incomplete',a.abort.previous['failure']['kind'])
            self.assertIn('pairedPreparationFailure',a.abort.previous)
            self.assertEqual(aready,actor.store.read());self.assertEqual('ready',actor.state['phase'])
        for owner in (p,a):
            with owner.feature.held(paired=True):self.assertTrue(owner.restore_account())
        self.assertEqual(pfailed,primary.store.read());self.assertEqual(aready,actor.store.read())
        for owner in (p,a):
            with owner.feature.held(paired=True):self.assertFalse(owner.process_round())
        for expected in (False,True):
            domain.sleep(1.6)
            for owner in (p,a):
                with owner.feature.held(paired=True):self.assertEqual(expected,owner.process_round())
        for owner in (p,a):
            with owner.feature.held(paired=True):self.assertTrue(owner.retire_provider())
        for owner in (p,a):
            with owner.feature.held(paired=True):self.assertEqual('failed',owner.result()['status'])
            self.assertEqual(1,domain.natives[owner.role].lifecycle_inputs.count('app.stop'))
            self.assertEqual(1,domain.sdk_requests.count((owner.role,'DELETE')))
        with actor.held(paired=True):
            bad=deepcopy(a.abort.previous);bad['pairedPreparationFailure']['peerAdmissionSha256']='0'*64
            with self.assertRaises(NativeUIError):IOSAvatarAbort.history(actor,bad)
        with actor.held(paired=True),patch.object(domain.runtime.adapter,'_target',side_effect=AssertionError('No live ready-peer abort replay')):
            self.assertEqual(a.original_result(),AvatarFailedPreparation.archive(actor,a.previous).original_result())
        self.assertEqual(pfailed,primary.store.read());self.assertEqual(aready,actor.store.read())


if __name__=='__main__':unittest.main()
