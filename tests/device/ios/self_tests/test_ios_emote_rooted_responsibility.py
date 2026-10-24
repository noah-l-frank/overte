"""Actual private-file continuity; no product, SDK or native fact is modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.avatar_record_cache import AvatarRecordCache
from ios.adapters.emote_rooted_responsibility import IOSEmoteRootedResponsibility
from ios.adapters.emote_scene_history import validate as scene_history
from ios.adapters.emote_scene_proof import rooted


class RootedResponsibilityGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.locks={}
        for role in ('primary','actor'):
            directory=self.root/role;directory.mkdir(mode=0o700)
            self.locks[role]=ScriptSourceLock(directory/'script-feature-sources.lock')
        for role in ('actor','primary'):
            held=self.locks[role].held();held.__enter__();self.addCleanup(held.__exit__,None,None,None)
        self.flow=SimpleNamespace(role='primary',run='c'*32,selector='primary',primary_selector='primary',
            lock=self.locks['primary'],primary_lock=self.locks['primary'],
            runtime=SimpleNamespace(state_path=lambda role:self.root/role/'session.json'))
        self.owner=object.__new__(IOSEmoteRootedResponsibility);self.owner.flow=self.flow
        self.owner.values={};self.owner.signatures=None

    def test_new_previously_absent_recovery_metadata_invalidates_the_original_cut(self):
        self.owner.values=self.owner.metadata();self.owner.guard()
        path=self.owner.path('ios-emote-primary-source-recovery.json',primary=True)
        path.write(dict(testContinuityOnly=1),None)
        with self.assertRaises(NativeUIError):self.owner.guard()
        self.assertEqual(dict(testContinuityOnly=1),path.read())

    def test_restored_original_bytes_and_mtime_do_not_hide_a_same_inode_rewrite(self):
        store=self.owner.path('ios-emote-primary-marker-recovery.json');value=dict(testContinuityOnly=1)
        store.write(value,None);self.owner.values={str(store.path):value}
        self.owner.signatures=AvatarRecordCache.signatures({store.path});self.owner.patterns=[];self.owner.carriers=set()
        before=store.path.stat();raw=store.path.read_bytes();time.sleep(.002)
        store.path.write_bytes(raw.replace(b':1',b':2'));store.path.write_bytes(raw)
        os.utime(store.path,ns=(before.st_atime_ns,before.st_mtime_ns))
        self.assertEqual(raw,store.path.read_bytes());self.assertEqual(value,store.read())
        with self.assertRaises(NativeUIError):self.owner.guard()

    def test_unaccounted_original_does_not_hide_behind_unchanged_metadata(self):
        store=self.owner.path('ios-emote-primary-marker-recovery.json');value=dict(testContinuityOnly=1)
        store.write(value,None);self.owner.values={str(store.path):value}
        self.owner.signatures=AvatarRecordCache.signatures({store.path})
        directory=store.path.parent;self.owner.patterns=[(directory,'emote-source-abandoned-*.json')];self.owner.carriers=set()
        self.owner.guard();orphan=PrivateFeatureState(directory/('emote-source-abandoned-'+'c'*32+'-primary-1.json'))
        orphan.write(dict(unresolvedOriginal=True),None)
        with self.assertRaises(NativeUIError):self.owner.guard()
        self.assertEqual(dict(unresolvedOriginal=True),orphan.read())

    def test_pending_actor_publication_is_rejected_before_any_record_is_opened(self):
        self.flow.role=self.flow.selector='actor';self.flow.lock=self.locks['actor']
        store=self.owner.path('phase-publication-emotes-'+'c'*32+'-actor.json')
        value=dict(payload=pack([dict(records=[],pending=dict(testUnknownDelivery=True))]))
        store.write(value,None);before=set(store.path.parent.iterdir())
        with self.assertRaises(NativeUIError):self.owner.metadata()
        self.assertEqual(value,store.read());self.assertEqual(before,set(store.path.parent.iterdir()))

    def test_actor_record_collection_uses_the_actual_area_run_and_record_namespace(self):
        self.flow.role=self.flow.selector='actor';self.flow.lock=self.locks['actor']
        for prefix in ('phase-publication','phase-retirement'):
            store=self.owner.path(prefix+'-emotes-'+self.flow.run+'-actor.json')
            store.write(dict(payload=pack([dict(records=[dict(ordinal=1,sha256='a'*64)],pending=None)])),None)
            record=self.owner.path(prefix+'-emotes-'+self.flow.run+'-actor-1.json')
            record.write(dict(testContinuityOnly=prefix),None)
        values=self.owner.metadata()
        for prefix in ('phase-publication','phase-retirement'):
            record=self.owner.path(prefix+'-emotes-'+self.flow.run+'-actor-1.json')
            self.assertEqual(record.read(),values[str(record.path)])

    def test_legacy_scene_reader_remains_default_and_rooted_reader_requires_explicit_selection(self):
        self.flow.root=self.root/'primary';self.flow.state=dict(binding={},phaseInstance='d'*32)
        path=self.owner.path('ios-emote-primary-scene-gate.json')
        value=dict(peerStatePath=str(self.root/'actor'/'ios-emote-actor-scene-gate.json'),peerAdmission={})
        for validator in (None,rooted):
            options={} if validator is None else dict(validate_original=validator)
            with patch('ios.adapters.emote_scene_history.IOSEmoteSceneGate.archive',side_effect=RuntimeError('Reader selection boundary')) as archive:
                with self.assertRaises(RuntimeError):scene_history(self.owner,{str(path.path):value},None,None,**options)
                if validator is None:self.assertNotIn('validate_original',archive.call_args.kwargs)
                else:self.assertIs(rooted,archive.call_args.kwargs['validate_original'])


if __name__=='__main__':unittest.main()
