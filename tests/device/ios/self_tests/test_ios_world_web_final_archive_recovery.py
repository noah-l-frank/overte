"""Actual archive WAL/carriers recover only observed fully readable proofs.

Native scene/retirement values are explicit grammar sentinels. These tests
qualify real file identity, metadata CAS and loss recovery, not a native end.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from adapters.native_clock_join import digest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.world_web_final_archive import WorldWebFinalArchive,file_original
from ios.self_tests.test_ios_create_files import BINDING

RUN='a'*32


class WorldWebFinalArchiveRecoveryTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.root.chmod(0o700)
        self.lock=ScriptSourceLock(self.root/'script-feature-sources.lock');self.enterContext(self.lock.held())
        self.store=PrivateFeatureState(self.root/('ios-world-web-primary-'+RUN+'-final.json'))
        self.child=PrivateFeatureState(self.root/'world-web-original.json');self.child.write(dict(original='actual stored bytes'),None)
        original=dict(modeledNativeScene=True)
        phase=dict(fixturePhaseVersion=1,instance='c'*32,sequence=2,requestId='d'*32,runId=RUN,area='world-web',
            capturedEpochMs=100000,active=False,createdEpochMs=90000,retiredEpochMs=99000,
            activations=[dict(sequence=1,ticket='b'*32,activatedEpochMs=92000,stimulus=dict(verb='cleanup',inputs={}))])
        self.frame=dict(iosWorldWebFinalProofVersion=2,binding=BINDING,runId=RUN,role='primary',phaseOriginal=phase,
            feature=dict(phase='paired',binding=BINDING,phaseInstance='c'*32),coordinatorHeader=None,original=original,
            measured=dict(scene=dict(remaining=['native-process-resources']),ticket='b'*32,
                acquisition=dict(hostAfterEpochMs=98000),retirement=dict(originalSha256=digest(original))),
            paired=dict(localSha256=digest(original)),files=[file_original(self.child.path)])

    def owner(self):return WorldWebFinalArchive(self.store,self.root,BINDING,RUN,'primary',self.lock)

    def writing(self):
        owner=self.owner();owner.state=dict(iosWorldWebFinalArchiveVersion=2,binding=BINDING,runId=RUN,role='primary',
            phase='writing',frameSha256=digest(self.frame),record=None,pending=None);owner.save();return owner

    def interrupted(self,mode):
        owner=self.writing();intent=owner.intent
        def losing(kind,value):
            if mode=='full-opened' and value['phase']=='saved':raise OSError('Lost saved callback before metadata CAS')
            intent(kind,value)
            if mode==value['phase']:raise OSError('Lost '+mode+' original return')
        owner.frames.intent=losing
        with self.assertRaises(OSError):owner.frames.write(1,self.frame)
        return self.owner()

    def test_opened_or_saved_complete_carrier_is_replayed_then_recovered_without_new_write(self):
        # Use separate roots for the two physical interruption positions.
        for mode in ('full-opened','saved'):
            with self.subTest(mode=mode):
                case=WorldWebFinalArchiveRecoveryTests();case.setUp();self.addCleanup(case.doCleanups)
                owner=case.interrupted(mode);before=deepcopy(owner.previous)
                wire=deepcopy(owner.state['pending']);path=owner.frames.path(wire);inode=path.stat().st_ino
                with patch.object(owner.store,'write',side_effect=AssertionError('Pure pending read wrote metadata')):
                    self.assertEqual(case.frame,owner.pending_original())
                self.assertEqual(before,owner.store.read());self.assertEqual('writing',owner.state['phase'])
                with patch.object(owner.frames,'write',side_effect=AssertionError('Observed original must not be rewritten')):
                    owner.recover();self.assertEqual(case.frame,owner.verify())
                self.assertEqual(inode,path.stat().st_ino);self.assertEqual('complete',owner.state['phase'])

    def test_planned_unknown_birth_stays_owned_and_is_never_created_by_recovery(self):
        owner=self.interrupted('planned');before=deepcopy(owner.previous);path=owner.frames.path(owner.state['pending'])
        self.assertFalse(path.exists())
        with self.assertRaises(NativeUIError):owner.pending_original()
        with self.assertRaises(NativeUIError):owner.recover()
        self.assertFalse(path.exists());self.assertEqual(before,owner.store.read())

    def test_opened_incomplete_original_stays_writing_without_a_replacement(self):
        owner=self.interrupted('opened');before=deepcopy(owner.previous);path=owner.frames.path(owner.state['pending'])
        inode=path.stat().st_ino;self.assertEqual(0,path.stat().st_size)
        with self.assertRaises(NativeUIError):owner.pending_original()
        with self.assertRaises(NativeUIError):owner.recover()
        self.assertEqual(before,owner.store.read());self.assertEqual(inode,path.stat().st_ino);self.assertEqual(0,path.stat().st_size)

    def test_missing_child_original_prevents_the_complete_metadata_commit(self):
        owner=self.interrupted('saved');before=deepcopy(owner.previous);self.child.path.unlink()
        with self.assertRaises((NativeUIError,OSError)):owner.recover()
        self.assertEqual(before,owner.store.read());self.assertEqual('writing',owner.state['phase'])

    def test_equal_bytes_with_replaced_child_inode_cannot_complete_the_pending_archive(self):
        owner=self.interrupted('saved');before=deepcopy(owner.previous)
        path=self.child.path;replacement=path.with_suffix('.replacement')
        replacement.write_bytes(path.read_bytes());replacement.chmod(0o600);replacement.replace(path)
        with self.assertRaises(NativeUIError):owner.pending_original()
        with self.assertRaises(NativeUIError):owner.recover()
        self.assertEqual(before,owner.store.read())

    def test_missing_observed_proof_does_not_regenerate_from_the_stored_digest(self):
        owner=self.interrupted('saved');before=deepcopy(owner.previous)
        path=owner.frames.path(owner.state['pending']);path.unlink()
        with self.assertRaises((NativeUIError,OSError)):owner.recover()
        self.assertFalse(path.exists());self.assertEqual(before,owner.store.read())


if __name__=='__main__':unittest.main()
