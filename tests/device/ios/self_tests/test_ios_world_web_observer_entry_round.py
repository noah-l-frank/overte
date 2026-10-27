"""Observation carriers are read again outside their exact readonly round."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.original_file_reads import scope
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.world_web_observer import WorldWebObserver
from ios.self_tests.world_web_sources_fixture import SDK


class WorldWebObserverEntryRoundTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);root=Path(temp.name);root.chmod(0o700)
        lock=ScriptSourceLock(root/'script-feature-sources.lock');self.enterContext(lock.held());self.sdk=SDK()
        source=self.sdk.owner(PrivateFeatureState(root/'ios-world-web-primary-sources.json'),lock)
        self.owner=WorldWebObserver(PrivateFeatureState(root/'ios-world-web-primary-observer.json'),source,
            dict(primary='http://controlled.invalid',foreign='http://foreign.invalid'),lambda:True)
        self.owner.capture();self.path=self.owner.record_store(1).path
    @contextmanager
    def reads(self):
        actual=PrivateFeatureState.read;calls=[]
        def reading(store):
            if store.path==self.path:calls.append(store.path)
            return actual(store)
        with patch.object(PrivateFeatureState,'read',new=reading):yield calls
    def test_same_round_reuses_actual_carrier_decode_and_outward_mutation_is_separate(self):
        with self.reads() as calls:
            with self.owner.validation_round():
                expected=self.owner.entries();changed=self.owner.entries();changed[0]['ticket']='outward-only'
                self.assertEqual(expected,self.owner.entries());self.assertEqual(1,len(calls))
            self.assertEqual(expected,self.owner.entries());self.assertEqual(2,len(calls))
    def test_independent_census_executes_actual_record_reader_then_reuses_only_its_own_membership(self):
        with scope(fresh=True),self.reads() as calls,self.owner.validation_round():
            expected=self.owner.entries();self.assertEqual(1,len(calls))
            with scope(fresh=True) as reads:
                self.assertEqual(expected,self.owner.entries());self.assertIn(self.path,reads)
                self.assertEqual(expected,self.owner.entries());self.assertEqual(2,len(calls))
            self.assertEqual(expected,self.owner.entries());self.assertEqual(3,len(calls))
    def test_changed_literal_parser_cannot_inherit_success(self):
        with self.owner.validation_round():
            self.owner.entries()
            with patch.object(self.owner,'_entries',side_effect=NativeUIError('Declared changed carrier parser')):
                with self.assertRaises(NativeUIError):self.owner.entries()
    def test_changed_original_run_role_or_binding_executes_literal_carrier_checks(self):
        owner=self.owner
        with owner.validation_round():
            owner.entries()
            for field,replacement in (('run','f'*32),('role','actor'),('binding',dict(owner.binding,sessionId='f'*32))):
                previous=getattr(owner,field);setattr(owner,field,replacement)
                try:
                    with self.subTest(field=field),self.assertRaises(NativeUIError):owner.entries()
                finally:setattr(owner,field,previous)
    def test_equal_byte_replaced_original_inode_refuses_during_warm_round(self):
        with self.assertRaises(NativeUIError),self.owner.validation_round():
            self.owner.entries();replacement=self.path.with_suffix('.replacement')
            replacement.write_bytes(self.path.read_bytes());replacement.chmod(0o600);replacement.replace(self.path)
            self.owner.entries()
    def test_actual_next_capture_reads_its_new_carrier_and_preserves_original_prefix(self):
        first=deepcopy(self.owner.entries())
        with self.owner.validation_round():self.assertEqual(first,self.owner.entries())
        self.owner.capture()
        with self.owner.validation_round():
            current=self.owner.entries();self.assertEqual(first,current[:1]);self.assertEqual(2,len(current))


if __name__=='__main__':unittest.main()
