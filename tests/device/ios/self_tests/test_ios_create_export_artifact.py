"""Exact native export copies and inode-bound host retirement on real files."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.create_export_artifact import CreateExportArtifact
from ios.self_tests import test_ios_create_export as export_tests
from ios.self_tests.test_ios_create_files import BINDING,RUN
from ios.self_tests.test_ios_create_state import ID


class CreateExportArtifactTests(unittest.TestCase):
    def setUp(self):
        self.h=export_tests.CreateExportTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
        self.store=PrivateFeatureState(self.h.root/'ios-create-export-artifact.json')
    def owner(self,binding=BINDING):return CreateExportArtifact(self.store,self.h.lock,self.h.root,binding,RUN,lambda:True)
    def capture(self,owner):
        before,after,raw=self.h.fixtures();owner.capture(before,after,self.h.model,ID,after_native=before['packet']['clockAfter']['epochMs']);return raw
    def test_original_file_is_copied_exactly_and_reconstructed_without_querying_or_rewriting_product(self):
        with self.h.held():
            owner=self.owner();raw=self.capture(owner);path=self.h.root/owner.state['name']
            self.assertEqual(raw,path.read_bytes());self.assertEqual(raw,self.owner().read());self.assertEqual(raw,(self.h.sdk.root/'export.json').read_bytes())
            count=len(self.h.sdk.requests)
            with self.assertRaises(NativeUIError):self.owner().capture({}, {}, {}, ID, after_native=1)
            self.assertEqual(count,len(self.h.sdk.requests));self.assertIsNotNone(self.store.read())
    def test_changed_bytes_replacement_inode_and_foreign_candidate_never_retire_the_original(self):
        for fault in ('bytes','inode','candidate','hardlink'):
            if fault!='bytes':self.doCleanups();self.setUp()
            with self.h.held():
                owner=self.owner();raw=self.capture(owner);path=self.h.root/owner.state['name']
                if fault=='bytes':path.write_bytes(b'foreign')
                elif fault=='inode':path.unlink();path.write_bytes(raw);path.chmod(0o600)
                elif fault=='hardlink':(self.h.root/'foreign-link').hardlink_to(path)
                else:
                    with self.assertRaises(NativeUIError):self.owner(BINDING|dict(artifactSha256='0'*64))
                    continue
                with self.subTest(fault=fault),self.assertRaises(NativeUIError):owner.remove()
                self.assertTrue(path.exists());self.assertEqual('copied',owner.state['phase'])
    def test_failed_open_remains_reserved_and_absence_can_retire_only_that_empty_plan(self):
        with self.h.held():
            owner=self.owner();before,after,_=self.h.fixtures();real_open=__import__('os').open
            def fail(path,*args,**kwargs):
                if str(path).endswith('.json') and Path(path).name.startswith('create-export-'):raise OSError('Synthetic filesystem failure')
                return real_open(path,*args,**kwargs)
            with patch('ios.adapters.create_export_artifact.os.open',side_effect=fail),self.assertRaises(OSError):
                owner.capture(before,after,self.h.model,ID,after_native=before['packet']['clockAfter']['epochMs'])
            self.assertEqual('planned',self.owner().state['phase']);owner.remove();self.assertEqual('removed',owner.state['phase'])
    def test_lost_retirement_journal_is_resolved_from_real_absence_without_unlink_replay(self):
        with self.h.held():
            owner=self.owner();self.capture(owner);write=self.store.write
            def lost(value,previous):
                if value['payload']!=previous['payload'] and owner.state['phase']=='removed':raise NativeUIError('Lost final journal return')
                return write(value,previous)
            with patch.object(self.store,'write',side_effect=lost),self.assertRaises(NativeUIError):owner.remove()
            recovered=self.owner();self.assertEqual('removing',recovered.state['phase'])
            real_unlink=Path.unlink;owned=self.h.root/recovered.state['name']
            def no_replay(path,*args,**kwargs):
                if path==owned:raise AssertionError('No second original unlink')
                return real_unlink(path,*args,**kwargs)
            with patch.object(Path,'unlink',no_replay):recovered.recover_removal()
            self.assertEqual('removed',recovered.state['phase']);self.assertIsNotNone(self.store.read())
    def test_replacement_during_removal_intent_storage_is_not_unlinked(self):
        with self.h.held():
            owner=self.owner();self.capture(owner);write=self.store.write;path=self.h.root/owner.state['name']
            def replace(value,previous):
                result=write(value,previous)
                if owner.state['phase']=='removing':path.unlink();path.write_bytes(b'foreign');path.chmod(0o600)
                return result
            with patch.object(self.store,'write',side_effect=replace),self.assertRaises(NativeUIError):owner.remove()
            self.assertEqual(b'foreign',path.read_bytes());self.assertEqual('removing',self.owner().state['phase'])


if __name__=='__main__':unittest.main()
