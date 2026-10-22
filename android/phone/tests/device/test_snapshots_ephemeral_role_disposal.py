"""Release only operation-owned Primary host graphs after original proof checks.

The public fixture uses actual TLS/journals/files and synthetic native/SDK
producers. Test-only GC disabling proves prompt reference release; production
never changes GC policy or retires target resources through this mechanism.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager,ExitStack
from copy import deepcopy
import gc
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import weakref

sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_snapshots_feature_journey as harness
import test_snapshots_quiet_role_reuse as quiet
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from overte_phone_script_history import unpack
from overte_phone_snapshots_history_pass import SnapshotHistoryReadPass
from overte_phone_snapshots_constructor_history import SnapshotConstructorHistoryPass
from overte_phone_snapshots_measurements import SnapshotPending
from overte_phone_snapshots_role import PhoneSnapshotsRole


class TrackedFrames(list):
    """Weak-referenceable wrapper over the unchanged actual original graph."""


@contextmanager
def reference_count_only():
    enabled=gc.isenabled();gc.disable()
    try:yield
    finally:
        if enabled:gc.enable()


def originals(root):
    return {p.name:(p.stat().st_dev,p.stat().st_ino,hashlib.sha256(p.read_bytes()).hexdigest())
        for p in root.iterdir() if p.is_file() and
        (p.name.startswith(('phone-snapshots-','emote-frame-snapshots-','emote-index-snapshots-','snapshots-')))}


class SnapshotEphemeralRoleDisposalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture_type=type('EphemeralSnapshotFixture',(harness.SnapshotJourneyTests,),{})
        cls.fixture_type.setUpClass()
    @classmethod
    def tearDownClass(cls):
        try:cls.fixture_type.tearDownClass()
        finally:cls.fixture_type.doClassCleanups()
    def setUp(self):
        self.fixture=self.fixture_type('test_original_public_baseline_before_any_input_or_capture')
        self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)

    def baseline(self):
        f=self.fixture;f.client.activate('c'*32)
        return f.invoke('feature.snapshots.observe',dict(contractVersion=harness.VERSION,runId=harness.RUN,afterSequence=0))

    def observe(self,after):
        return self.fixture.invoke('feature.snapshots.observe',dict(contractVersion=harness.VERSION,runId=harness.RUN,afterSequence=after))

    @contextmanager
    def record(self):
        f=self.fixture;constructed=[];released=[];returned=[]
        init=PhoneSnapshotsRole.__init__;dispose=PhoneSnapshotsRole._dispose_observation_graph;read=PhoneSnapshotsRole.read
        def tracking(role,*args,**kwargs):
            init(role,*args,**kwargs)
            role.frames=TrackedFrames(role.frames)
            constructed.append(dict(role=weakref.ref(role),frames=weakref.ref(role.frames),
                bytes=len(json.dumps(role.frames)),sequence=role.state['sequence']))
        def reading(role,*args,**kwargs):
            value=read(role,*args,**kwargs);returned.append((value,deepcopy(value)));return value
        def disposing(role):
            self.assertIsNone(role.feature.lock._owner)
            self.assertIsNone(f.adapter._existing_input_scope)
            paths=originals(f.root);calls=f.model.rpc_counts.copy();product=deepcopy(f.model.product.calls)
            snapshot=dict(state=deepcopy(role.state),frames=deepcopy(getattr(role,'frames',[])),path=role.store.path,
                header=role.store.read(),wasEphemeral=role._ephemeral_observation)
            dispose(role)
            self.assertEqual({},role.__dict__)
            self.assertEqual(paths,originals(f.root));self.assertEqual(calls,f.model.rpc_counts)
            self.assertEqual(product,f.model.product.calls)
            self.assertEqual(snapshot['header'],PrivateFeatureState(snapshot['path']).read())
            released.append(snapshot)
        with patch.object(PhoneSnapshotsRole,'__init__',tracking),patch.object(PhoneSnapshotsRole,'read',reading),\
                patch.object(PhoneSnapshotsRole,'_dispose_observation_graph',disposing):
            yield constructed,released,returned
        for value,before in returned:self.assertEqual(before,value)

    def test_large_actual_graph_drops_without_cycle_collection_and_returned_dto_is_unchanged(self):
        measured=self.baseline();f=self.fixture
        f.act('open');f.act('capture',dict(mode='still',format='png'))
        for _ in range(4):measured=self.observe(measured['sequence'])
        with reference_count_only(),self.record() as (made,released,returned):
            value=self.observe(measured['sequence'])
            self.assertGreater(value['sequence'],measured['sequence'])
            self.assertTrue(returned);self.assertTrue(released)
            self.assertTrue(all(row['frames']() is None for row in made))
            self.assertGreater(max(row['bytes'] for row in made),65536)
            self.assertEqual('ready',released[-1]['state']['phase'])
        self.assertEqual(1,released[-1]['frames'][-1]['state']['files'])

    def test_failed_constructor_releases_its_already_qualified_graph_and_preserves_originals(self):
        measured=self.baseline();f=self.fixture;before=originals(f.root);finish=SnapshotConstructorHistoryPass.finish_constructor;refs=[]
        def failed(token,role):
            finish(token,role)
            role.frames=TrackedFrames(role.frames);refs.append(weakref.ref(role.frames))
            raise RuntimeError('Controlled failure after actual constructor qualification')
        with reference_count_only(),self.record() as (_made,released,_returned):
            with patch.object(SnapshotConstructorHistoryPass,'finish_constructor',failed):
                with self.assertRaises(NativeUIError):self.observe(measured['sequence'])
            self.assertTrue(refs);self.assertTrue(all(ref() is None for ref in refs));self.assertEqual(1,len(released))
            self.assertEqual(before,originals(f.root))
        resumed=self.observe(measured['sequence']);self.assertGreater(resumed['sequence'],measured['sequence'])

    def test_default_constructor_failure_still_releases_its_original_graph(self):
        self.baseline();f=self.fixture;before=originals(f.root);restore=PhoneSnapshotsRole.restore_originals;refs=[]
        feature=f.adapter._snapshots_feature('test-only-appium',harness.RUN)
        def failed(role):
            role.frames=TrackedFrames(restore(role));refs.append(weakref.ref(role.frames))
            raise RuntimeError('Controlled failure in unchanged default constructor')
        with reference_count_only(),self.record() as (_made,released,_returned):
            with self.assertRaises(NativeUIError),ExitStack() as disposals,ExitStack() as session:
                with feature.lock.held():
                    session.enter_context(feature.adapter.existing_input_session(feature.selector));feature.load()
                    with patch.object(PhoneSnapshotsRole,'restore_originals',failed):
                        PhoneSnapshotsRole(feature,'primary',_observe_disposals=disposals)
            self.assertTrue(refs);self.assertTrue(all(ref() is None for ref in refs));self.assertEqual(1,len(released))
            self.assertEqual(before,originals(f.root))

    def test_actual_partial_read_error_keeps_durable_job_for_a_new_reader_to_recover(self):
        measured=self.baseline();batch=PhoneSnapshotsRole.batch;once=[]
        def failed(role):
            value=batch(role)
            if not once:once.append(True);raise NativeUIError('Controlled failure after original VM batch')
            return value
        with reference_count_only(),self.record() as (made,released,_returned):
            with patch.object(PhoneSnapshotsRole,'batch',failed):
                with self.assertRaises(NativeUIError):self.observe(measured['sequence'])
            self.assertTrue(all(row['frames']() is None for row in made));self.assertEqual(1,len(released))
        pending=unpack(PrivateFeatureState(released[0]['path']).read()['payload'])[0]
        self.assertEqual('reading',pending['phase']);self.assertTrue(pending['pending']['work']['groups'])
        with self.record() as (_made,resumed,_returned):value=self.observe(measured['sequence'])
        self.assertGreater(value['sequence'],measured['sequence'])
        self.assertTrue(any(frame.get('diagnostic') and frame.get('groups') for frame in resumed[-1]['frames']))

    def test_pending_retry_disposes_every_operation_reader_after_original_diagnostic_recovery(self):
        measured=self.baseline();batch=PhoneSnapshotsRole.batch;once=[]
        def pending(role):
            value=batch(role)
            if not once:once.append(True);raise SnapshotPending('Controlled pending after original VM batch')
            return value
        with reference_count_only(),self.record() as (made,released,_returned):
            with patch.object(PhoneSnapshotsRole,'batch',pending):value=self.observe(measured['sequence'])
            self.assertGreater(value['sequence'],measured['sequence']);self.assertGreaterEqual(len(released),2)
            self.assertTrue(all(row['frames']() is None for row in made))
        self.assertTrue(any(frame.get('diagnostic') for frame in released[-1]['frames']))
        self.assertTrue(all(row['state']['pending'] is None for row in released))

    def test_cleaned_reader_lives_through_phase_history_session_and_lock_checks(self):
        prepared=quiet.prepared_role(self.fixture);sequence=prepared['role'].state['sequence'];closed=[]
        close=SnapshotHistoryReadPass.close
        def closing(token):close(token);closed.append(token.closed)
        with reference_count_only(),self.record() as (made,released,_returned):
            # Wrap the recorder's actual release, retaining all of its checks.
            release=PhoneSnapshotsRole._dispose_observation_graph
            def after_history(role):
                self.assertTrue(closed);self.assertTrue(all(closed));return release(role)
            with patch.object(SnapshotHistoryReadPass,'close',closing),patch.object(PhoneSnapshotsRole,'_dispose_observation_graph',after_history):
                value=self.observe(sequence)
            self.assertEqual([],value['resources']);self.assertTrue(all(row['frames']() is None for row in made))
            self.assertTrue(released[-1]['frames'][-1]['phaseAfter']['active'])
        # The manually retained generic reader is outside facade ownership.
        self.assertTrue(prepared['role'].frames);self.assertIsNotNone(prepared['role'].feature)

    def test_cleaned_pending_retry_keeps_old_owner_usable_until_last_comparison(self):
        prepared=quiet.prepared_role(self.fixture);sequence=prepared['role'].state['sequence'];batch=PhoneSnapshotsRole.batch;once=[]
        def pending(role):
            value=batch(role)
            if role.feature.state['phase']=='cleaned' and not once:
                once.append(True);raise SnapshotPending('Controlled cleaned original batch pending')
            return value
        with reference_count_only(),self.record() as (made,released,_returned):
            with patch.object(PhoneSnapshotsRole,'batch',pending):value=self.observe(sequence)
            self.assertEqual([],value['resources']);self.assertGreaterEqual(len(released),2)
            self.assertTrue(all(row['frames']() is None for row in made))
        self.assertTrue(any(frame.get('diagnostic') for frame in released[-1]['frames']))

    def test_generic_and_actor_readers_remain_live_and_actor_cannot_opt_in(self):
        measured=self.baseline();f=self.fixture.adapter._snapshots_feature('test-only-appium',harness.RUN)
        with reference_count_only(),f.lock.held():
            f.load();primary=PhoneSnapshotsRole(f,'primary');primary.frames=TrackedFrames(primary.frames);p=weakref.ref(primary.frames)
            with self.assertRaises(NativeUIError):primary._dispose_observation_graph()
            self.assertIsNotNone(p());self.assertTrue(primary.frames)
            f.role='actor';actor=PhoneSnapshotsRole(f,'actor');actor.frames=TrackedFrames(actor.frames);a=weakref.ref(actor.frames)
            value=actor.read(actor.state['sequence']);self.assertGreater(value['sequence'],0)
            with ExitStack() as forbidden:
                with self.assertRaises(NativeUIError):PhoneSnapshotsRole(f,'actor',_observe_disposals=forbidden)
            self.assertIsNotNone(a());self.assertTrue(actor.frames);self.assertIs(actor.feature,f)
            self.assertFalse(actor._ephemeral_observation)
        self.assertGreater(measured['sequence'],0)


if __name__=='__main__':unittest.main()
