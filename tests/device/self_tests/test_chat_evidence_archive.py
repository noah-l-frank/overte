"""Actual private files/OFDs/write-once copies; release observations are seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import hashlib
import json
import os
import stat
import tempfile
import unittest

from adapters.chat_journey.evidence_archive import ChatArchiveCatalog,ChatEvidenceArchive,completed_archive
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_journey.history import unpack


class ChatEvidenceArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='chat-archive-');self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.root.chmod(0o700);self.catalog=ChatArchiveCatalog();self.addCleanup(self.catalog.close_host)
        self.a=PrivateFeatureState(self.root/'a.json');self.b=PrivateFeatureState(self.root/'b.frame-000.json')
        self.a.write(dict(phase='complete',original='a'),None);self.b.write(dict(phase='ready',original='b'),None)
        for store in (self.a,self.b):self.catalog.add('primary/'+store.path.name,store,store.read())
        self.originals={row['label']:row['raw'] for row in self.catalog.rows.values()};self.proof=dict(pid=789,oldAbsent=True,original='source-seam')
        self.guard_calls=0;self.fault=None;self.ledger=PrivateFeatureState(self.root/'retirement.json')
        self.archive=ChatEvidenceArchive(self.catalog,self.root/'evidence',self.ledger,dict(runId='a'*32),self.guard,self.inventory)
        self.addCleanup(self.archive.close_host)
        # A sealed directory stays read-only during the operation; test teardown
        # owns this temporary directory and can restore traversal for its removal.
        self.addCleanup(lambda:os.chmod(self.archive.directory,0o700) if self.archive.directory.exists() else None)
    def inventory(self,expected):
        need({path for path in self.root.iterdir() if path.name.startswith(('a.','b.'))}==expected)
    def guard(self,original=None):
        self.guard_calls+=1
        if self.fault:self.fault()
        if original is not None:need(original==self.proof)
        return self.proof.copy()
    def test_originals_preserved_before_retirement_and_final_sources_sealed_after_last_unlink(self):
        result=self.archive.retire();self.assertFalse(self.a.path.exists());self.assertFalse(self.b.path.exists());self.assertIsNone(self.ledger.read())
        self.assertEqual(0o500,stat.S_IMODE(self.archive.directory.stat().st_mode));self.assertEqual(1,result['chatEvidenceArchiveVersion'])
        manifest=json.loads((self.archive.directory/'manifest.json').read_bytes());parts=[]
        for item in manifest['parts']:
            raw=(self.archive.directory/item['file']).read_bytes();self.assertEqual(item['sha256'],hashlib.sha256(raw).hexdigest());parts+=json.loads(raw)
        for row in parts:self.assertEqual(self.originals[row['label']],(self.archive.directory/row['file']).read_bytes())
        final=json.loads((self.archive.directory/'final.json').read_bytes());self.assertEqual([self.proof],unpack(final['original']))
        self.assertEqual(result['archiveSha256'],final['archiveSha256']);self.assertTrue(self.archive.complete)
        with self.assertRaises(NativeUIError):self.archive.retire()
    def test_unknown_chunk_is_never_adopted_deleted_or_qualified(self):
        orphan=PrivateFeatureState(self.root/'b.frame-999.json');orphan.write(dict(unknown=True),None)
        with self.assertRaises(NativeUIError):self.archive.retire()
        self.assertIsNotNone(orphan.read());self.assertIsNotNone(self.a.read());self.assertFalse(self.archive.directory.exists())
    def test_replaced_original_or_archive_source_prevents_retirement_without_late_adoption(self):
        original=self.guard
        def guard(proof=None):
            value=original(proof)
            if self.ledger.read() and self.ledger.read()['phase']=='archived':self.a.write(self.a.read(),self.a.read())
            return value
        self.archive.guard=guard
        with self.assertRaises(NativeUIError):self.archive.retire()
        self.assertIsNotNone(self.a.read());self.assertIsNotNone(self.b.read());self.assertIsNotNone(self.ledger.read())
        self.assertTrue((self.archive.directory/'manifest.json').exists())
    def test_lost_unlink_intent_or_receipt_preserves_archive_and_never_repeats_attempt(self):
        write=self.ledger.write
        def lost(value,previous):
            write(value,previous)
            if value['phase']=='unlink-issued':raise OSError('durable unlink admission receipt lost')
        self.ledger.write=lost
        with self.assertRaises(OSError):self.archive.retire()
        self.assertEqual('unlink-issued',self.ledger.read()['phase']);self.assertIsNotNone(self.a.read())
        before=self.ledger.path.read_bytes()
        with self.assertRaises(NativeUIError):self.archive.retire()
        self.assertEqual(before,self.ledger.path.read_bytes())
    def test_final_source_expiration_keeps_retirement_marker_and_all_archived_originals(self):
        def guard(original=None):
            if original is not None:raise NativeUIError('original final packet aged during final receipt write')
            return self.proof.copy()
        self.archive.guard=guard
        with self.assertRaises(NativeUIError):self.archive.retire()
        self.assertEqual('complete',self.ledger.read()['phase']);self.assertFalse(self.archive.complete)
        self.assertFalse(self.a.path.exists());self.assertTrue((self.archive.directory/'final.json').exists())
        self.assertEqual(0o700,stat.S_IMODE(self.archive.directory.stat().st_mode))


    def test_original_parent_directory_replacement_never_unlinks_foreign_replacement_files(self):
        saved=self.root.with_name(self.root.name+'-original');moved=[False]
        def restore():
            if moved[0]:
                for path in self.root.iterdir():path.unlink()
                self.root.rmdir();saved.rename(self.root)
        self.addCleanup(restore)
        guard=self.guard
        def replaced(original=None):
            result=guard(original)
            if not moved[0] and self.ledger.read() and self.ledger.read()['phase']=='archived':
                self.root.rename(saved);self.root.mkdir(mode=0o700);moved[0]=True
                foreign=PrivateFeatureState(self.root/'a.json');foreign.write(dict(foreign=True),None)
            return result
        self.archive.guard=replaced
        with self.assertRaises(NativeUIError):self.archive.retire()
        self.assertTrue(moved[0]);self.assertEqual(dict(foreign=True),self.a.read())
        self.assertEqual(self.originals['primary/a.json'],(saved/'a.json').read_bytes())
        self.assertTrue((saved/'evidence/manifest.json').exists())

    def test_final_marker_unlink_cannot_hide_original_source_age_expiration(self):
        discard=self.ledger.discard;removed=[False]
        def late(previous):discard(previous);removed[0]=True
        self.ledger.discard=late
        def guard(original=None):
            if original is not None and removed[0]:raise NativeUIError('source aged inside final marker unlink')
            return self.proof.copy()
        self.archive.guard=guard
        with self.assertRaises(NativeUIError):self.archive.retire()
        self.assertEqual('final-unavailable',self.ledger.read()['phase']);self.assertFalse(self.archive.complete)
        self.assertTrue((self.archive.directory/'final.json').exists());self.assertFalse(self.a.path.exists())

    def test_cold_archive_validation_rejects_missing_extra_replaced_and_writable_bytes(self):
        self.archive.retire();self.assertEqual(self.proof,completed_archive(self.archive.directory)['original'])
        directory=self.archive.directory;directory.chmod(0o700)
        with self.assertRaises(NativeUIError):completed_archive(directory)
        directory.chmod(0o500);path=directory/'original-0000.json';path.chmod(0o600)
        with self.assertRaises(NativeUIError):completed_archive(directory)
        # Even restoring modes cannot restore its original ctime admission.
        path.chmod(0o400)
        with self.assertRaises(NativeUIError):completed_archive(directory)


if __name__=='__main__':unittest.main()
