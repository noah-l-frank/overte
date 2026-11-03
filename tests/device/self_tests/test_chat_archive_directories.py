"""Existing archive/source fence plus real atomic private namespace retirement."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import os
import time
import unittest
import uuid
from unittest.mock import patch

from adapters.chat_journey.archive_file import signature
from adapters.chat_journey.directory_retirement import OriginalDirectoryRetirement
from adapters.chat_journey.evidence_archive import ChatEvidenceArchive,completed_archive
from adapters.native_fd_owner import OriginalDescriptor
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from self_tests import test_chat_archive_unlink_fence as existing


class ChatArchiveDirectoryTests(unittest.TestCase):
    SOURCE_FILES=33
    LITERAL='ä Ω 東京\x00'
    def setUp(self):
        self.h=existing.ChatArchiveUnlinkFenceTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
        h=self.h;self.source=h.root/'state';self.source.mkdir(mode=0o700)
        self.destination=h.root/'retained-state';self.before={};self.events=[]
        for index in range(self.SOURCE_FILES):
            store=PrivateFeatureState(self.source/f'original-{index:03d}.json')
            store.write(dict(consumed=index,literal=self.LITERAL),None)
            h.catalog.add('primary/'+store.path.name,store,store.read())
            self.before[store.path.name]=(store.path.read_bytes(),signature(store.path.lstat()))
        self.extra=PrivateFeatureState(h.root/'original-artifact.json');self.extra.write(dict(consumed='artifact'),None)
        h.catalog.add('primary/'+self.extra.path.name,self.extra,self.extra.read())
        self.group=OriginalDirectoryRetirement(h.catalog,self.source,self.destination)
        self.addCleanup(lambda:self.assertTrue(self.group.close_host()))
        self.archive=ChatEvidenceArchive(h.catalog,h.root/'archive',h.ledger,dict(runId=existing.RUN),
            h.guard,self.inventory,unlink_fence=h.fence,indexed_verify=True,directory_retirements=(self.group,))
        self.addCleanup(self.archive.close_host)
        self.addCleanup(lambda:self.archive.directory.chmod(0o700) if self.archive.directory.exists() else None)

    def inventory(self,remaining):
        if self.group.moved:
            self.group.verify();self.assertFalse(any(path.parent==self.source for path in remaining))
        else:self.assertEqual({path for path in remaining if path.parent==self.source},set(self.source.iterdir()))
        self.assertEqual(self.extra.path in remaining,self.extra.path.exists())

    def after_intent(self,callback):
        write=self.h.ledger.write
        def observed(value,previous):
            write(value,previous)
            if value['phase']=='directory-move-issued':self.events.append(value);callback()
        self.h.ledger.write=observed

    def test_complete_copies_and_original_phase_precede_one_move_then_existing_artifact_unlink(self):
        def before_move():
            self.assertTrue((self.archive.directory/'manifest.json').exists())
            self.assertEqual(self.SOURCE_FILES,len(list(self.source.iterdir())))
            self.assertTrue(self.extra.path.exists());self.assertEqual([],self.archive.deleted)
            for index,row in enumerate(self.h.catalog.rows.values()):
                self.assertEqual(row['raw'],(self.archive.directory/f'original-{index:04d}.json').read_bytes())
        self.after_intent(before_move)
        result=self.archive.retire();self.assertEqual(5,result['chatEvidenceArchiveVersion'])
        self.assertEqual(1,len(self.events));self.assertFalse(self.source.exists());self.assertFalse(self.extra.path.exists())
        for name,(raw,info) in self.before.items():
            path=self.destination/name;self.assertEqual(raw,path.read_bytes());self.assertEqual(info,signature(path.lstat()))
        proof=completed_archive(self.archive.directory)
        self.assertEqual(5,proof['chatEvidenceArchiveVersion']);self.assertEqual(1,len(proof['directoryRetirements']))
        self.assertEqual(self.SOURCE_FILES,proof['directoryRetirements'][0]['originals'])
        self.assertEqual(0,proof['directoryRetirements'][0]['originalUnlinks'])
        self.assertEqual(self.SOURCE_FILES+1,len(self.archive.deleted));self.assertEqual(2,self.h.fence.uses)
        self.assertIsNone(self.h.ledger.read());self.assertTrue(self.archive.complete)

    def test_unknown_actual_child_after_durable_intent_prevents_move_and_artifact_unlink(self):
        orphan=self.source/'unknown.json';self.after_intent(lambda:orphan.write_bytes(b'{"unknown":true}\n'))
        with self.assertRaises(NativeUIError):self.archive.retire()
        self.assertTrue(orphan.exists());self.assertFalse(self.group.attempted)
        self.assertTrue(self.extra.path.exists());self.assertEqual([],self.archive.deleted)
        self.assertEqual('directory-move-issued',self.h.ledger.read()['phase'])

    def test_changed_actual_archive_copy_after_durable_intent_prevents_original_namespace_move(self):
        def changed():
            path=self.archive.directory/'original-0000.json';path.chmod(0o600);path.write_bytes(b'{"changed":true}\n');path.chmod(0o400)
        self.after_intent(changed)
        with self.assertRaises(NativeUIError):self.archive.retire()
        self.assertTrue(self.source.exists());self.assertFalse(self.group.attempted)
        self.assertTrue(self.extra.path.exists());self.assertFalse(self.destination.exists())

    def test_new_independent_phase_after_intent_refuses_before_any_directory_mutation(self):
        self.after_intent(lambda:self.h.journal.activate(existing.RUN,uuid.uuid4().hex,'cleanup',{}))
        with self.assertRaises(NativeUIError):self.archive.retire()
        self.assertTrue(self.h.fence.failed);self.assertFalse(self.group.attempted)
        self.assertTrue(self.source.exists());self.assertTrue(self.extra.path.exists())

    def test_actual_slow_intent_cannot_hide_behind_frozen_model_clocks(self):
        self.after_intent(lambda:time.sleep(.260))
        with self.assertRaises(NativeUIError):self.archive.retire()
        self.assertFalse(self.group.attempted);self.assertTrue(self.source.exists())
        self.assertTrue(self.extra.path.exists());self.assertIsNotNone(self.h.fence.pending)

    def test_lost_landed_move_keeps_durable_intent_originals_and_original_source_reservation(self):
        from adapters.chat_journey.directory_retirement import rename_original
        def lost(*args):rename_original(*args);raise OSError('Actual moved receipt lost')
        with patch('adapters.chat_journey.directory_retirement.rename_original',lost):
            with self.assertRaises(OSError):self.archive.retire()
        self.assertTrue(self.group.attempted);self.assertTrue(self.group.failed)
        self.assertFalse(self.source.exists());self.assertTrue(self.destination.exists())
        self.assertTrue(self.extra.path.exists());self.assertEqual([],self.archive.deleted)
        self.assertIsNotNone(self.h.fence.pending);self.assertEqual('directory-move-issued',self.h.ledger.read()['phase'])
        before=self.h.ledger.path.read_bytes()
        with self.assertRaises(NativeUIError):self.archive.retire()
        self.assertEqual(before,self.h.ledger.path.read_bytes())


if __name__=='__main__':unittest.main()
