"""Actual bounded immutable-file windows; no native/device release is implied."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import os
import resource
import tempfile
import unittest
from unittest.mock import patch

from adapters.chat_journey.archive_file import ClosedOriginalFile
from adapters.chat_journey.evidence_archive import ChatArchiveCatalog,ChatEvidenceArchive,completed_archive
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError


class ChatArchiveFileTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.root.chmod(0o700)
        self.catalog=ChatArchiveCatalog(hold_files=False);self.addCleanup(self.catalog.close_host)
    def add(self,name='source.json'):
        store=PrivateFeatureState(self.root/name);store.write(dict(original=name),None)
        self.catalog.add('primary/'+name,store,store.read());return self.catalog.rows['primary/'+name]
    def test_catalog_exceeding_legacy_fd_capacity_keeps_only_original_directory_pairs_and_same_rlimit(self):
        limits=resource.getrlimit(resource.RLIMIT_NOFILE);baseline=len(list(Path('/proc/self/fd').iterdir()))
        for index in range(2100):
            self.add(f'original-{index:04d}.json')
            if index%100==0:self.assertLessEqual(len(list(Path('/proc/self/fd').iterdir())),baseline+4)
        self.assertEqual(2100,len(self.catalog.rows));self.catalog.verify_all()
        self.assertTrue(all(type(row['owner']) is ClosedOriginalFile and row['owner'].active is None for row in self.catalog.rows.values()))
        self.assertEqual(limits,resource.getrlimit(resource.RLIMIT_NOFILE));self.assertLessEqual(len(list(Path('/proc/self/fd').iterdir())),baseline+4)
    def test_replaced_same_bytes_original_and_changed_parent_cannot_requalify_closed_snapshot(self):
        row=self.add();before=row['raw'];row['store'].write(row['expected'],row['expected'])
        with self.assertRaises(NativeUIError):self.catalog.verify(row)
        self.assertEqual(before,row['store'].path.read_bytes());self.assertIsNone(row['owner'].active)
    def test_original_held_directory_replacement_during_reopened_window_keeps_foreign_file_untouched(self):
        row=self.add();saved=self.root.with_name(self.root.name+'-original');moved=[False];pread=os.pread
        def restore():
            if moved[0]:
                for path in self.root.iterdir():path.unlink()
                self.root.rmdir();saved.rename(self.root)
        self.addCleanup(restore)
        def replace(fd,size,offset):
            value=pread(fd,size,offset)
            if row['owner'].active is not None and not moved[0]:
                self.root.rename(saved);self.root.mkdir(mode=0o700);moved[0]=True
                PrivateFeatureState(self.root/'source.json').write(dict(foreign=True),None)
            return value
        with patch('adapters.chat_journey.archive_file.os.pread',replace),self.assertRaises(NativeUIError):self.catalog.verify(row)
        self.assertEqual(dict(foreign=True),PrivateFeatureState(self.root/'source.json').read())
        self.assertEqual(row['raw'],(saved/'source.json').read_bytes());self.assertIsNone(row['owner'].active)

    def test_recycled_same_file_fd_is_not_closed_and_its_uncertain_alias_remains_retained(self):
        row=self.add();owner=row['owner'];pread=os.pread;foreign=[];anchors=[]
        def recycle(fd,size,offset):
            if owner.active is not None and fd==owner.active.fd and not foreign:
                anchors.append(owner.active.anchor);os.close(fd);replacement=os.open(owner.path,os.O_RDONLY|os.O_CLOEXEC)
                self.assertEqual(fd,replacement);foreign.append(replacement)
            return pread(fd,size,offset)
        try:
            with patch('adapters.chat_journey.archive_file.os.pread',recycle),self.assertRaises(NativeUIError):self.catalog.verify(row)
            self.assertTrue(owner.failed);self.assertIsNotNone(owner.active);self.assertFalse(owner.close())
            self.assertEqual(owner.stamp[1],os.fstat(foreign[0]).st_ino);self.assertEqual(owner.stamp[1],os.fstat(anchors[0]).st_ino)
        finally:
            for fd in foreign+anchors:os.close(fd)
    def test_versioned_closed_archive_preserves_immutable_original_bytes_and_refuses_replaced_copy(self):
        row=self.add();directory=self.root/'archive';ledger=PrivateFeatureState(self.root/'retirement.json')
        original=row['raw'];proof=dict(original='explicit-release-source-seam')
        def guard(value=None):
            if value is not None:self.assertEqual(proof,value)
            return proof.copy()
        def inventory(expected):self.assertEqual(expected,{row['store'].path} if row['store'].path.exists() else set())
        archive=ChatEvidenceArchive(self.catalog,directory,ledger,dict(runId='a'*32),guard,inventory)
        self.addCleanup(archive.close_host);self.addCleanup(lambda:directory.chmod(0o700) if directory.exists() else None)
        result=archive.retire();self.assertEqual(2,result['chatEvidenceArchiveVersion'])
        cold=completed_archive(directory);self.assertEqual('closed-immutable-originals',cold['fileOwnership'])
        self.assertEqual(original,(directory/'original-0000.json').read_bytes());self.assertEqual(proof,cold['original'])
        self.assertTrue(all(item['owner'].active is None for item in archive.archived.values()))
        directory.chmod(0o700);path=directory/'original-0000.json';raw=path.read_bytes();path.unlink();path.write_bytes(raw);path.chmod(0o400)
        directory.chmod(0o500)
        with self.assertRaises(NativeUIError):completed_archive(directory)


if __name__=='__main__':unittest.main()
