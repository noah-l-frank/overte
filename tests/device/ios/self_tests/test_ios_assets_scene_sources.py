"""Fresh readonly raw ownership, exact recovery and replacement counterexamples."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from adapters.normal_ui import NativeUIError
from ios.self_tests.assets_scene_sources_fixture import Fixture
from ios.adapters.assets_session_owners import inspect_directory


class AssetsSceneSourcesTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.path=Path(temporary.name);self.path.chmod(0o700)
        self.f=Fixture(self.path);self.addCleanup(self.f.close);self.owner=self.f.owner();self.owner.reserve()
    def test_six_actual_query_originals_restore_without_any_input_or_new_clock(self):
        sample=self.owner.capture(self.f.epoch());self.assertEqual('actor-primary',sample['role']);self.assertEqual(6,len(self.f.queries));self.assertEqual(6,len(self.owner.raws.refs))
        queries=deepcopy(self.f.queries);before={path.name:(path.stat().st_ino,path.read_bytes()) for path in self.path.iterdir() if path.is_file()}
        restored=self.f.owner();self.assertEqual(sample,restored._cached[-1]['scene']);self.assertEqual(queries,self.f.queries)
        self.assertEqual(before,{path.name:(path.stat().st_ino,path.read_bytes()) for path in self.path.iterdir() if path.is_file()})
    def test_saved_logical_source_recovers_exact_original_after_lost_adoption_without_query_replay(self):
        intent=self.owner.originals.intent;errors=[]
        def interrupted(kind,reference):
            result=intent(kind,reference)
            if reference['phase']=='saved':
                error=RuntimeError('lost Assets scene logical adoption');errors.append(error);raise error
            return result
        self.owner.originals.intent=interrupted
        with self.assertRaises(RuntimeError) as caught:self.owner.capture(self.f.epoch())
        self.assertIs(caught.exception,errors[0]);queries=deepcopy(self.f.queries);restored=self.f.owner();sample=restored.recover_capture()
        self.assertEqual('actor-primary',sample['role']);self.assertEqual(queries,self.f.queries);self.assertIsNone(restored.state['pending'])
    def test_actual_opened_raw_prefix_is_retained_and_blocks_reacquisition(self):
        intent=self.owner.raws.store.intent
        def opened(kind,reference):
            result=intent(kind,reference)
            if reference['phase']=='opened':raise RuntimeError('interrupted actual raw scene file')
            return result
        self.owner.raws.store.intent=opened
        with self.assertRaises(NativeUIError):self.owner.capture(self.f.epoch())
        pending=deepcopy(self.owner.raws.pending);queries=deepcopy(self.f.queries);path=self.owner.raws.store.path(pending['original']);before=(path.stat().st_ino,path.read_bytes())
        restored=self.f.owner()
        with self.assertRaises(NativeUIError):restored.capture(self.f.epoch())
        with self.assertRaises(NativeUIError):restored.freeze_interrupted()
        self.assertEqual(queries,self.f.queries);self.assertEqual(pending,restored.raws.pending);self.assertEqual(before,(path.stat().st_ino,path.read_bytes()))
    def test_replaced_original_inode_or_current_guard_refusal_never_reuses_a_successful_sample(self):
        self.owner.capture(self.f.epoch());queries=deepcopy(self.f.queries);self.f.good=False
        with self.assertRaises(NativeUIError):self.owner.capture(self.f.epoch())
        self.assertEqual(queries,self.f.queries);self.f.good=True
        ref=self.owner.raws.refs[0];path=self.owner.raws.store.path(self.owner.raws.store.expand(ref));raw=path.read_bytes();path.rename(self.path/'retained-scene-raw');path.write_bytes(raw);path.chmod(0o600)
        with self.assertRaises(NativeUIError):self.f.owner()
        self.assertEqual(queries,self.f.queries)

    def test_pure_membership_rejects_orphans_and_preserves_an_unfinished_source_write(self):
        self.owner.capture(self.f.epoch());before={path.name:(path.stat().st_ino,path.read_bytes()) for path in self.path.iterdir() if path.is_file()};queries=deepcopy(self.f.queries)
        rows=inspect_directory(self.path);self.assertEqual([],rows[0]['responsibilities']);self.assertEqual('actor-primary',rows[0]['role'])
        self.assertEqual(queries,self.f.queries);self.assertEqual(before,{path.name:(path.stat().st_ino,path.read_bytes()) for path in self.path.iterdir() if path.is_file()})
        extra=self.path/('assets-scene-read-primary-source-frame-sources-'+self.owner.run+'-primary-0032-'+'a'*64+'.json')
        extra.write_bytes(b'{}');extra.chmod(0o600)
        with self.assertRaises(NativeUIError):inspect_directory(self.path)
        extra.unlink()
        intent=self.owner.raws.store.intent
        def opened(kind,reference):
            result=intent(kind,reference)
            if reference['phase']=='opened':raise RuntimeError('held unfinished original')
            return result
        self.owner.raws.store.intent=opened
        with self.assertRaises(NativeUIError):self.owner.capture(self.f.epoch())
        self.assertEqual(['scene-source-write'],inspect_directory(self.path)[0]['responsibilities'])

    def test_actor_source_reservation_never_implies_absence_of_peer_resources(self):
        actor_root=self.path/'peer';actor_root.mkdir(mode=0o700);actor=Fixture(actor_root,role='actor')
        try:
            owner=actor.owner();owner.reserve();rows=inspect_directory(actor_root)
            self.assertEqual(['scene-peer-resources'],rows[0]['responsibilities']);self.assertEqual([],actor.queries)
        finally:actor.close()
