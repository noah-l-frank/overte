"""Actual immutable files/directory FDs/phase/CAS; native production is a seam."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import os
import unittest
from unittest.mock import patch

from adapters.chat_journey.archive_file import ClosedOriginalFile
from adapters.chat_journey.evidence_archive import ChatArchiveCatalog,ChatEvidenceArchive,completed_archive
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from self_tests import test_chat_archive_unlink_fence as source_seams
from self_tests import test_restart_inputs as restart_seams


class ChatArchiveIndexTests(unittest.TestCase):
    def setUp(self):
        self.h=source_seams.ChatArchiveUnlinkFenceTests();self.h.setUp();self.addCleanup(self.h.doCleanups)

    def test_full_bytes_before_retirement_and_final_source_with_linear_owned_copy_read_windows(self):
        archive=self.h.make(32,indexed=True);read=ClosedOriginalFile.read;copies=[]
        def counted(owner,*args):
            if owner.path.parent==archive.directory:copies.append(owner.path.name)
            return read(owner,*args)
        with patch.object(ClosedOriginalFile,'read',counted):result=archive.retire()
        self.assertEqual(4,result['chatEvidenceArchiveVersion']);self.assertLessEqual(len(copies),7*32+20)
        for index in range(32):self.assertGreaterEqual(copies.count(f'original-{index:04d}.json'),4)
        cold=completed_archive(archive.directory)
        self.assertEqual('full-current-copy-and-original-physical-inventory',cold['copyVerification'])
        self.assertEqual(32,len(archive.deleted));self.assertIsNone(self.h.ledger.read());self.assertTrue(archive.complete)

    def test_own_other_manifest_and_extra_copy_changes_after_final_intent_preserve_every_original(self):
        for fault in ('own','other','part','manifest','extra'):
            with self.subTest(fault=fault):
                self.setUp();archive=self.h.make(indexed=True);write=self.h.ledger.write
                def change(value,previous):
                    write(value,previous)
                    if value['phase']!='unlink-issued':return
                    name={'own':'original-0000.json','other':'original-0001.json','part':'manifest-000.json','manifest':'manifest.json','extra':'foreign.json'}[fault]
                    path=archive.directory/name
                    if path.exists():path.chmod(0o600)
                    path.write_bytes(b'{"changed":true}\n');path.chmod(0o400)
                self.h.ledger.write=change
                with self.assertRaises(NativeUIError):archive.retire()
                self.assertEqual([],archive.deleted);self.assertEqual('unlink-issued',self.h.ledger.read()['phase'])
                self.assertTrue(all(row['store'].path.exists() for row in self.h.catalog.rows.values()))

    def test_mutated_memory_bytes_digest_or_stamp_cannot_requalify_original_copy_cache(self):
        for fault in ('bytes-and-digest','stamp','digest-chain'):
            with self.subTest(fault=fault):
                self.setUp();archive=self.h.make(indexed=True);write=self.h.ledger.write
                def change(value,previous):
                    write(value,previous)
                    if value['phase']!='unlink-issued':return
                    row=archive.archived['original-0001.json']
                    if fault=='bytes-and-digest':row['raw']=b'changed';row['sha256']=hashlib.sha256(row['raw']).hexdigest()
                    elif fault=='stamp':row['stamp'][6]+=1
                    else:archive.cache_digest='f'*64
                self.h.ledger.write=change
                with self.assertRaises(NativeUIError):archive.retire()
                self.assertEqual([],archive.deleted);self.assertTrue(all(row['store'].path.exists() for row in self.h.catalog.rows.values()))

    def test_original_archive_directory_swap_during_held_fd_inventory_never_touches_foreign_files(self):
        archive=self.h.make(indexed=True);stat=os.stat;moved=[];saved=archive.directory.with_name('held-original-archive')
        def restore():
            if moved:
                archive.directory.rmdir();saved.rename(archive.directory)
        self.addCleanup(restore)
        def change(name,*args,**kw):
            value=stat(name,*args,**kw)
            if kw.get('dir_fd') is not None and name=='original-0000.json' and self.h.ledger.read()['phase']=='unlink-issued' and not moved:
                archive.directory.rename(saved);archive.directory.mkdir(mode=0o700);moved.append(True)
            return value
        with patch('adapters.chat_journey.evidence_archive.os.stat',change),self.assertRaises(NativeUIError):archive.retire()
        self.assertTrue(moved);self.assertEqual([],archive.deleted)
        self.assertTrue(all(row['store'].path.exists() for row in self.h.catalog.rows.values()))

    def test_replaced_original_serialization_index_after_unlink_intent_keeps_all_sources(self):
        for fault in ('admission-tuple','index-tuple','canonical-body'):
            with self.subTest(fault=fault):
                self.setUp();archive=self.h.make(indexed=True);write=self.h.ledger.write
                def change(value,previous):
                    write(value,previous)
                    if value['phase']!='unlink-issued':return
                    if fault=='admission-tuple':
                        name='original-0001.json'
                        archive.admitted[name]=tuple(list(archive.admitted[name]))
                    elif fault=='index-tuple':archive.index_rows=tuple(list(archive.index_rows))
                    else:
                        rows=list(archive.index_rows);name,(admitted,path,_raw)=rows[1]
                        rows[1]=(name,(admitted,path,b'[]'));archive.index_rows=tuple(rows)
                self.h.ledger.write=change
                with self.assertRaises(NativeUIError):archive.retire()
                self.assertEqual([],archive.deleted)
                self.assertEqual('unlink-issued',self.h.ledger.read()['phase'])
                self.assertTrue(all(row['store'].path.exists() for row in self.h.catalog.rows.values()))

    def test_final_physical_index_delay_keeps_original_final_deadline_and_retirement_marker(self):
        archive=self.h.make(indexed=True);verify=archive.verify_index
        def late():
            verify()
            if self.h.ledger.read() and self.h.ledger.read()['phase']=='complete':self.h.epoch+=2000
        archive.verify_index=late
        with self.assertRaises(NativeUIError):archive.retire()
        self.assertEqual('complete',self.h.ledger.read()['phase']);self.assertFalse(archive.complete)
        self.assertTrue((archive.directory/'final.json').exists())

    def test_final_receipt_cannot_seal_a_lost_or_identical_bytes_replaced_archived_copy(self):
        for replaced in (False,True):
            with self.subTest(replaced=replaced):
                self.setUp();archive=self.h.make(indexed=True);original=archive.original
                def change(name,raw):
                    result=original(name,raw)
                    if name=='final.json':
                        path=archive.directory/'original-0000.json';saved=path.read_bytes();path.unlink()
                        if replaced:path.write_bytes(saved);path.chmod(0o400)
                    return result
                archive.original=change
                with self.assertRaises((NativeUIError,OSError)):archive.retire()
                self.assertEqual('complete',self.h.ledger.read()['phase']);self.assertFalse(archive.complete)

    def test_copy_change_after_inner_restart_observation_cas_prevents_actual_intent_discard(self):
        restart=restart_seams.RestartInputTests();restart.setUp();self.addCleanup(restart.doCleanups)
        restart.inputs();restart.flow().observe(restart_seams.NEW,restart.new_source);store=restart.store
        catalog=ChatArchiveCatalog(hold_files=False);self.addCleanup(catalog.close_host)
        catalog.add('primary/'+store.path.name,store,store.read());ledger=PrivateFeatureState(store.path.parent/'retirement.json')
        catalog.rows['primary/'+store.path.name]['retire']=lambda check:restart.flow().retire(restart_seams.NEW,restart.new_source,before_discard=check)
        archive=ChatEvidenceArchive(catalog,store.path.parent/'archive',ledger,dict(runId=source_seams.RUN),self.h.guard,
            lambda expected:self.assertEqual(expected,{store.path} if store.path.exists() else set()),unlink_fence=self.h.fence,indexed_verify=True)
        self.addCleanup(archive.close_host);write=store.write
        def change(value,previous):
            write(value,previous);path=archive.directory/'original-0000.json';path.chmod(0o600)
            path.write_bytes(b'{"changed":true}\n');path.chmod(0o400)
        store.write=change
        with self.assertRaises(NativeUIError):archive.retire()
        self.assertEqual('observed',store.read()['phase']);self.assertEqual([],archive.deleted)
        self.assertEqual('unlink-issued',ledger.read()['phase']);self.assertEqual(['stop','launch'],restart.calls)

    def test_cold_complete_byte_validation_and_retry_refuse_lost_replaced_or_corrupt_originals(self):
        archive=self.h.make(indexed=True);archive.retire();completed_archive(archive.directory)
        with self.assertRaises(NativeUIError):ChatEvidenceArchive(archive.catalog,archive.directory,archive.store,archive.metadata,
            archive.guard,archive.inventory,unlink_fence=archive.unlink_fence,indexed_verify=True)
        path=archive.directory/'original-0000.json';archive.directory.chmod(0o700);path.chmod(0o600)
        path.write_bytes(b'{"changed":true}\n');path.chmod(0o400);archive.directory.chmod(0o500)
        with self.assertRaises(NativeUIError):completed_archive(archive.directory)


if __name__=='__main__':unittest.main()
