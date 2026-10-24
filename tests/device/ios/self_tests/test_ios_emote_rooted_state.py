"""Closed frozen-metadata access; no native/product outcome is modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.emote_rooted_state import IOSEmoteRootedState


class RootedStateBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.locks={}
        for role in ('actor','primary'):
            directory=self.root/role;directory.mkdir(mode=0o700)
            lock=self.locks[role]=ScriptSourceLock(directory/'script-feature-sources.lock')
            held=lock.held();held.__enter__();self.addCleanup(held.__exit__,None,None,None)
        self.path=self.root/'primary'/'ios-emote-primary-feature.json'

    def reader(self,copies):
        return IOSEmoteRootedState(copies,run='c'*32,lock=self.locks['primary'],actor_lock=self.locks['actor'])

    def test_missing_snapshot_entry_never_falls_back_to_existing_current_metadata(self):
        actual=PrivateFeatureState(self.path);actual.write(dict(unresolvedCurrentOwner=True),None)
        reader=self.reader({str(self.path.with_name('known.json')):None})
        with self.assertRaises(NativeUIError):reader.store(self.path)
        self.assertEqual(dict(unresolvedCurrentOwner=True),actual.read())

    def test_explicit_absence_and_nested_original_values_remain_read_only(self):
        value=dict(nested=dict(actual=1));copies={str(self.path):value,str(self.path.with_name('absent.json')):None}
        reader=self.reader(copies);value['nested']['actual']=2
        with patch.object(PrivateFeatureState,'read',side_effect=AssertionError('Current metadata read forbidden')):
            store=reader.store(self.path);returned=store.read();returned['nested']['actual']=3
            self.assertEqual(dict(nested=dict(actual=1)),store.read())
            self.assertIsNone(reader.store(self.path.with_name('absent.json')).read())
            with self.assertRaises(NativeUIError):store.write({},None)
            with self.assertRaises(NativeUIError):store.discard(store.read())
        self.assertEqual(set(copies),reader.used)

    def test_missing_role_feature_cannot_start_an_original_or_runtime_reader(self):
        reader=self.reader({str(self.path.with_name('unknown.json')):None})
        with patch.object(PrivateFeatureState,'read',side_effect=AssertionError('Current reader forbidden')):
            with self.assertRaises(NativeUIError):reader.read()

    def test_noncanonical_keys_nonobjects_and_shared_role_lock_are_rejected(self):
        for copies in ({str(self.path.parent/'..'/'primary'/self.path.name):None},{str(self.path):[]},{Path(self.path):None}):
            with self.assertRaises(NativeUIError):self.reader(copies)
        with self.assertRaises(NativeUIError):
            IOSEmoteRootedState({str(self.path):None},run='c'*32,lock=self.locks['primary'],actor_lock=self.locks['primary'])

    def test_other_role_artifact_mutation_invalidates_the_enclosing_pure_read(self):
        copies={};artifacts={}
        for role,lock in self.locks.items():
            root=artifacts[role]=self.root/(role+'-artifacts');root.mkdir(mode=0o700)
            copies[str(lock.path.with_name('ios-emote-'+role+'-feature.json'))]=dict(artifactRoot=str(root))
        original=PrivateFeatureState(artifacts['actor']/'emote-original-continuity-only.json')
        original.write(dict(continuityOnly=True),None);raw=original.path.read_bytes()
        class BoundaryReached(Exception):pass
        def mutate(_role):
            original.path.write_bytes(raw)
            raise BoundaryReached('No role fact is supplied by this test')
        # The role parser is deliberately interrupted: this tests the actual
        # enclosing inventory guarantee, never a modeled product verdict.
        with patch.object(IOSEmoteRootedState,'role',side_effect=mutate):
            with self.assertRaises(NativeUIError):self.reader(copies).read()
        self.assertEqual(raw,original.path.read_bytes())


if __name__=='__main__':unittest.main()
