"""Real local receipt bytes/journal with simulated native memory and Android IO."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.android_world_render import AndroidWorldRenderReceipts
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.owned_world_render import WorldRenderOwner,OwnedWorldRenderCapture
from adapters.world_render_evidence import NativeWorldRenderCapture
from adapters.world_render_storage import receipt_file
from self_tests.test_world_render_storage import Boundary,CAPTURE

BINDING=dict(sourceRevision='a'*40,artifactSha256='b'*64,processIdentity='31:original-start',
    sessionId='original-session',generation=1,targetFingerprint='c'*64)


class LocalAdb:
    def __init__(self,path):self.path=path;self.calls=[];self.ignore_remove=False
    def execute(self,args,*,target,timeout):
        self.calls.append(args);assert args[0]=='shell';remote=shlex.split(args[1])
        assert remote[:4]==['run-as','org.overte.test','sh','-c']
        if self.ignore_remove and 'rm -f' in remote[4]:return ''
        result=subprocess.run(remote[2:],cwd=self.path,capture_output=True,text=True,timeout=timeout)
        if result.returncode:raise NativeUIError('Simulated private file operation failed')
        return result.stdout


class OwnedWorldRenderTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.path=Path(tmp.name);os.chmod(self.path,0o700)
        (self.path/'files/overte-e2e').mkdir(parents=True,mode=0o700)
        self.source=Boundary();self.native=self.source.storage();self.store=PrivateFeatureState(self.path/'owner.json')
        self.owner=WorldRenderOwner(self.store,BINDING,lambda:self.source.okay)
        self.adb=LocalAdb(self.path);self.receipts=AndroidWorldRenderReceipts(self.adb,'controlled-alias','org.overte.test',self.owner.guard)
        self.native.receipt_intent=self.owner.receipt_intent
        self.capture=NativeWorldRenderCapture(lambda _:None,lambda:'',self.native,lambda:20000,self.owner.guard,31,intent=self.owner.intent)
        self.owned=OwnedWorldRenderCapture(self.capture,self.native,self.owner,self.receipts)
        original=self.source.send
        def send(command):
            self.assertIn(command['commandId'],self.owner.owned()['receipts'])
            self.source.intents.append(deepcopy(command));original(command)
            name=receipt_file(command['commandId'])
            (self.path/'files/overte-e2e'/name).write_text(self.source.files[name])
        self.native.send=send
        self.owner.intent(dict(schemaVersion=1,commandId=CAPTURE,action='feature-world-render-observe'))

    def test_journal_precedes_artifacts_and_only_complete_independent_cleanup_discards_it(self):
        sample=self.owned.release();self.assertFalse(sample['present']);self.assertIsNone(self.store.read())
        self.assertEqual([],list((self.path/'files/overte-e2e').iterdir()))
        self.assertEqual(4,len(self.adb.calls)) # Remove and separate actual existence query for each receipt.

    def test_ignored_unlink_ack_keeps_journal_and_original_receipts(self):
        self.adb.ignore_remove=True
        with self.assertRaises(NativeUIError):self.owned.release()
        self.assertIsNotNone(self.store.read());self.assertTrue(list((self.path/'files/overte-e2e').iterdir()))
        self.adb.ignore_remove=False;self.owned.release();self.assertIsNone(self.store.read())

    def test_foreign_context_cannot_adopt_or_release_the_original_capture(self):
        foreign=WorldRenderOwner(self.store,BINDING|{'processIdentity':'32:foreign'},self.owner.guard)
        with self.assertRaises(NativeUIError):foreign.owned()
        self.assertEqual([],self.source.commands)

    def test_failed_persistence_prevents_even_the_storage_command_and_native_artifact(self):
        self.store.discard(self.store.read())
        with self.assertRaises(NativeUIError):self.native.release(CAPTURE)
        self.assertEqual([],self.source.commands);self.assertEqual({},self.source.files)

    def test_process_loss_never_removes_files_or_discards_original_journal(self):
        self.source.okay=False
        with self.assertRaises(NativeUIError):self.owned.release()
        self.assertIsNotNone(self.store.read());self.assertEqual([],self.adb.calls)

    def test_an_unfinished_acquisition_cannot_be_replaced_by_another_input(self):
        with self.assertRaises(NativeUIError):self.owned.read(0)
        self.assertEqual(CAPTURE,self.owner.owned()['capture']['commandId'])

    def test_only_the_issued_nonce_receipts_can_join_the_current_capture(self):
        before=self.owner.owned()
        with self.assertRaises(NativeUIError):self.owner.receipt_intent(dict(schemaVersion=1,commandId='d'*32,
            action='feature-world-render-storage',requestId='e'*32,operation='inspect'))
        self.assertEqual(before,self.owner.owned())

    def test_symlink_receipt_and_parent_are_refused_without_touching_foreign_bytes(self):
        foreign=self.path/'foreign.txt';foreign.write_text('foreign bytes')
        name=receipt_file('d'*32);file=self.path/'files/overte-e2e'/name;file.symlink_to(foreign)
        with self.assertRaises(NativeUIError):self.receipts.remove(name)
        self.assertFalse(self.receipts.absent(name));self.assertEqual('foreign bytes',foreign.read_text())
        file.unlink();(self.path/'files/overte-e2e').rmdir();(self.path/'files/overte-e2e').symlink_to(self.path)
        with self.assertRaises(NativeUIError):self.receipts.absent(name)

    def test_arbitrary_or_foreign_names_never_reach_the_transport(self):
        for name in ('../user.json','user.png','world-render-storage-user.json','files/overte-e2e/receipt.json'):
            with self.assertRaises(NativeUIError):self.receipts.remove(name)
        self.assertEqual([],self.adb.calls)
