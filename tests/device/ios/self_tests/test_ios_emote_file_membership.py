"""Actual carrier inventory and exact old-index membership; no cleanup facts."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import tempfile
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.original_file_reads import scope,record
from adapters.original_frame_store import OriginalFrameStore
from ios.adapters.emote_session_carriers import inventory,covered
from ios.self_tests.test_ios_emote_sources import BINDING,RUN


class FileMembershipTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.root.chmod(0o700)
        self.store=OriginalFrameStore(self.root,BINDING,RUN,'primary',lambda:True,lambda *_:None,namespace='emote',schema_prefix='emote')
    def originals(self):
        first=self.store.write(1,dict(original='first'));before=self.store.append([],first)
        second=self.store.write(2,dict(original='second'));after=self.store.append(before,second)
        return before,after
    def test_current_full_originals_cover_exact_existing_old_manifest_prefixes(self):
        before,after=self.originals()
        with scope(fresh=True) as reads:
            self.assertEqual([dict(original='first'),dict(original='second')],self.store.restore(after,2))
        self.assertIn(self.store.manifest_path(before[0]),reads)
        covered({self.root},reads)
    def test_changed_old_prefix_cannot_be_qualified_by_only_the_new_index(self):
        before,after=self.originals();path=self.store.manifest_path(before[0]);value=PrivateFeatureState(path).read()
        PrivateFeatureState(path).write(dict(value,runId='a'*32),value)
        with self.assertRaises(NativeUIError),scope(fresh=True):self.store.restore(after,2)
    def test_outer_incidental_read_cannot_contaminate_the_fresh_full_decoder(self):
        foreign=self.root/'emote-unknown.json';foreign.write_bytes(b'{"unknown":true}');foreign.chmod(0o600)
        with scope() as outer:
            record(foreign)
            with scope(fresh=True) as inner:self.assertEqual(set(),inner)
            self.assertIn(foreign,outer)
        with self.assertRaises(NativeUIError):covered({self.root},inner)
        self.assertEqual(b'{"unknown":true}',foreign.read_bytes())
    def test_unknown_generic_gpu_owner_is_responsibility_only_and_never_ignored_or_deleted(self):
        path=self.root/('graphics-world-frame-primary-0-'+'7'*32+'.json')
        path.write_bytes(b'{"vulkanWorldOwnerVersion":1,"unknown":true}');path.chmod(0o600)
        before=path.read_bytes();self.assertEqual({path},inventory({self.root}))
        with self.assertRaises(NativeUIError):covered({self.root},set())
        self.assertEqual(before,path.read_bytes())
    def test_aliased_relevant_carrier_cannot_be_admitted_from_its_filename(self):
        actual=self.root/'unrelated';actual.write_bytes(b'original');actual.chmod(0o600)
        alias=self.root/'emote-unknown.json';alias.symlink_to(actual)
        with self.assertRaises(NativeUIError):inventory({self.root})
        self.assertEqual(b'original',actual.read_bytes())
