"""Real Source/manifest/frame guards with an explicit Scene-header fixture.

These counterexamples qualify reader isolation and original-file ownership,
not Scene effects. The separate genuine Actor graph verifies the joined path.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
import unittest
from unittest.mock import patch

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.original_file_reads import scope as read_scope
from adapters.original_frame_store import OriginalFrameStore
from ios.adapters import avatar_observation as observation
from ios.adapters.avatar_held_scene import IOSAvatarHeldScene
from ios.adapters.avatar_scene_manifest_reader import JoinedManifestReader
from ios.self_tests import test_ios_avatar_observation as fixture
from ios.self_tests.test_ios_avatar_entities import EXPECTED


class AvatarSceneManifestReaderTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.AvatarObservationTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.source=self.f.history();source=self.source
        scene=object.__new__(IOSAvatarHeldScene);scene.store=PrivateFeatureState(source.store.path.with_name('ios-avatar-primary-scene.json'))
        scene.root,scene.lock,scene.binding,scene.run,scene.role=source.root,source.lock,deepcopy(source.binding),source.run,source.role
        scene.historical=True;scene.baseline,scene.clock,scene.paths,scene.state={}, {}, {}, dict(explicitModeledSceneHeader=True)
        scene.previous=scene.envelope(scene.state);scene.store.write(scene.previous,None)
        self.scene=scene;self.original=dict(explicitModeledSceneArgument=True)

    def reader(self):return JoinedManifestReader(self.scene,self.original,self.source)
    def appearance(self,reader):
        return observation.appearance(self.source,self.f.baseline,len(self.source.frames),
            fixture_url=self.f.fixture.fixture.phase.fixture_url,expected_code=EXPECTED,_manifest_reader=reader)

    def test_only_manifest_indexes_share_while_each_frame_and_membership_is_read_again(self):
        calls=[];reads=[];manifest=self.source.originals.manifest;frame=OriginalFrameStore.read
        def actual(reference):calls.append(reference);return manifest(reference)
        def actual_frame(store,value):reads.append(value);return frame(store,value)
        with patch.object(self.source.originals,'manifest',actual),patch.object(OriginalFrameStore,'read',actual_frame):
            with read_scope(fresh=True),self.reader() as reader:
                with read_scope(fresh=True) as first:a=self.appearance(reader)
                cold=len(calls);frames=len(reads)
                with read_scope(fresh=True) as second:b=self.appearance(reader)
                self.assertEqual(a,b);self.assertTrue(first);self.assertEqual(first,second)
                self.assertEqual(cold,len(calls));self.assertGreater(frames,0);self.assertEqual(frames*2,len(reads))
            self.assertGreater(cold,0)
            with self.assertRaises(NativeUIError):reader(1)
            with self.assertRaises(NativeUIError):
                with reader:self.fail('Closed reader reentered')
            before=len(calls)
            with self.reader() as fresh:self.appearance(fresh)
            self.assertGreater(len(calls),before)

    def test_equal_metadata_other_owner_cannot_borrow_a_scene_reader(self):
        other=self.f.history()
        with self.reader() as reader:
            reader(self.f.baseline)
            with self.assertRaises(NativeUIError):
                observation.appearance(other,self.f.baseline,len(other.frames),
                    fixture_url=self.f.fixture.fixture.phase.fixture_url,expected_code=EXPECTED,_manifest_reader=reader)

    def test_replaced_manifest_or_reader_parser_cannot_inherit_a_warm_index(self):
        for owner,name in ((self.source.originals,'manifest'),(self.source.originals,'key'),
                (self.source.originals,'manifest_reference'),(None,'manifest')):
            calls=[]
            def unavailable(*_a,**_k):calls.append(True);raise AssertionError('Replacement parser must not inherit an index')
            with self.subTest(parser=name,source=owner is not None):
                with self.assertRaises(NativeUIError):
                    with self.reader() as reader:
                        reader(self.f.baseline)
                        target=owner if owner is not None else reader.reader
                        with patch.object(target,name,unavailable):reader(self.f.baseline)
                self.assertEqual([],calls)

    def test_coordinated_scene_or_source_owner_mutation_is_rejected_before_reuse(self):
        for owner in (self.scene,self.source):
            old_state,old_previous=deepcopy(owner.state),deepcopy(owner.previous)
            try:
                with self.subTest(scene=owner is self.scene),self.assertRaises(NativeUIError):
                    with self.reader() as reader:
                        reader(self.f.baseline);owner.state['fabricatedOwnerField']=True
                        owner.previous=owner.envelope(owner.state);reader(self.f.baseline)
            finally:owner.state,owner.previous=old_state,old_previous

    def test_equal_bytes_new_manifest_inode_and_unknown_inventory_growth_fail_closed(self):
        path=self.source.originals.manifest_path(self.source.state['manifests'][0])
        with self.assertRaises(NativeUIError):
            with self.reader() as reader:
                reader(self.f.baseline);replacement=path.with_suffix('.replacement')
                replacement.write_bytes(path.read_bytes());replacement.chmod(0o600);os.replace(replacement,path)
                reader(self.f.baseline)
        with self.assertRaises(NativeUIError):
            with self.reader() as reader:
                reader(self.f.baseline)
                PrivateFeatureState(self.source.root/'unknown-reader-original.json').write({'unknown':True},None)

    def test_frame_mutation_and_lost_lock_are_refused_at_the_join_boundary(self):
        original=deepcopy(self.source.frames)
        try:
            with self.assertRaises(NativeUIError):
                with self.reader() as reader:
                    reader(self.f.baseline);self.source.frames[0]['unreadFrameMutation']=True
        finally:self.source.frames[:]=original
        held=self.source.lock._owner
        try:
            with self.assertRaises(NativeUIError):
                with self.reader() as reader:
                    reader(self.f.baseline);self.source.lock._owner=None;reader(self.f.baseline)
        finally:self.source.lock._owner=held


if __name__=='__main__':unittest.main()
