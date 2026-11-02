"""Actual immutable files/directory FDs/phase/CAS; native production is a seam."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import os
from pathlib import Path
import sys
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
        archive=self.h.make(indexed=True);scandir=os.scandir;moved=[];saved=archive.directory.with_name('held-original-archive')
        def restore():
            if moved:
                archive.directory.rmdir();saved.rename(archive.directory)
        self.addCleanup(restore)
        class Entry:
            def __init__(self,original):self.original=original;self.name=original.name
            def stat(self,**kw):
                value=self.original.stat(**kw)
                if self.name=='original-0000.json' and self_outer.h.ledger.read()['phase']=='unlink-issued' and not moved:
                    archive.directory.rename(saved);archive.directory.mkdir(mode=0o700);moved.append(True)
                return value
        class Scan:
            def __init__(self,descriptor):self.original=scandir(descriptor)
            def __enter__(self):self.original.__enter__();return (Entry(entry) for entry in self.original)
            def __exit__(self,*args):return self.original.__exit__(*args)
        self_outer=self
        def change(descriptor):
            return Scan(descriptor) if type(descriptor) is int and archive.root is not None and descriptor==archive.root.fd else scandir(descriptor)
        with patch('adapters.chat_journey.evidence_archive.os.scandir',change),self.assertRaises(NativeUIError):archive.retire()
        self.assertTrue(moved);self.assertEqual([],archive.deleted)
        self.assertTrue(all(row['store'].path.exists() for row in self.h.catalog.rows.values()))

    def test_same_byte_copy_replacement_between_index_passes_is_not_a_cached_stat(self):
        archive=self.h.make(indexed=True);verify=archive.verify_index;changed=[]
        def replace():
            verify()
            if self.h.ledger.read() and self.h.ledger.read()['phase']=='unlink-issued' and not changed:
                path=archive.directory/'original-0001.json';replacement=archive.directory/'replacement'
                replacement.write_bytes(path.read_bytes());replacement.chmod(0o400);replacement.replace(path);changed.append(True)
        archive.verify_index=replace
        with self.assertRaises(NativeUIError):archive.retire()
        self.assertEqual([True],changed);self.assertEqual([],archive.deleted)
        self.assertEqual('unlink-issued',self.h.ledger.read()['phase'])
        self.assertTrue(all(row['store'].path.exists() for row in self.h.catalog.rows.values()))

    def parent_fixture(self):
        ancestor=Path(self.h.temp.name)/'authority';ancestor.mkdir(mode=0o700)
        directory=ancestor/'sources';directory.mkdir(mode=0o700)
        catalog=ChatArchiveCatalog(hold_files=False);self.addCleanup(catalog.close_host)
        store=PrivateFeatureState(directory/'original.json');value=dict(original='complete private bytes')
        store.write(value,None);catalog.add('primary/'+store.path.name,store,value)
        return catalog,ancestor,directory,store

    def test_original_parent_canonical_path_rejects_ancestor_move_and_symlink_with_same_leaf_inode(self):
        catalog,ancestor,directory,store=self.parent_fixture();saved=ancestor.with_name('saved-authority')
        original=directory.stat().st_ino;ancestor.rename(saved);ancestor.symlink_to(saved,target_is_directory=True)
        try:
            self.assertEqual(original,directory.stat().st_ino)
            with self.assertRaises((NativeUIError,OSError)):catalog.verify_parent(directory)
            self.assertEqual(dict(original='complete private bytes'),PrivateFeatureState(saved/'sources'/'original.json').read())
        finally:ancestor.unlink();saved.rename(ancestor)

    def test_original_parent_exchange_rejects_foreign_named_directory_and_preserves_both_trees(self):
        catalog,ancestor,directory,store=self.parent_fixture();foreign=ancestor.with_name('foreign-authority')
        foreign.mkdir(mode=0o700);(foreign/'sources').mkdir(mode=0o700)
        outsider=foreign/'sources'/'foreign.json';outsider.write_bytes(b'foreign original');outsider.chmod(0o600)
        temporary=ancestor.with_name('exchange-held');ancestor.rename(temporary);foreign.rename(ancestor);temporary.rename(foreign)
        try:
            with self.assertRaises((NativeUIError,OSError)):catalog.verify_parent(directory)
            self.assertEqual(b'foreign original',(directory/'foreign.json').read_bytes())
            self.assertEqual(dict(original='complete private bytes'),PrivateFeatureState(foreign/'sources'/'original.json').read())
        finally:ancestor.rename(temporary);foreign.rename(ancestor);temporary.rename(foreign)

    def test_same_node_parent_alias_cannot_replace_the_original_canonical_path(self):
        catalog,ancestor,directory,_store=self.parent_fixture();alias=ancestor.with_name('alias-authority')
        alias.symlink_to(ancestor,target_is_directory=True);named=alias/'sources'
        self.assertEqual(directory.stat().st_ino,named.stat().st_ino)
        catalog.parents[named]=catalog.parents[directory]
        try:
            with self.assertRaises((NativeUIError,OSError)):catalog.verify_parent(named)
        finally:catalog.parents.pop(named);alias.unlink()

    @unittest.skipUnless(sys.platform.startswith('linux'),'Fresh Linux held-FD canonical path contract')
    def test_linux_canonical_observation_failure_does_not_fall_back_to_path_resolution(self):
        catalog,_ancestor,directory,store=self.parent_fixture()
        with patch('adapters.chat_journey.evidence_archive.os.readlink',side_effect=OSError('Original kernel path unavailable')):
            with self.assertRaises(OSError):catalog.verify_parent(directory)
        self.assertEqual(dict(original='complete private bytes'),store.read());catalog.verify_parent(directory)

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
