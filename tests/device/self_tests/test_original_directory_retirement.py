"""Actual exclusive directories and paired kernel descriptors; no product IO."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from adapters.chat_journey.archive_file import signature
from adapters.chat_journey.directory_retirement import OriginalDirectoryRetirement
from adapters.chat_journey.evidence_archive import ChatArchiveCatalog
from adapters.native_fd_owner import OriginalDescriptor
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError


class OriginalDirectoryRetirementTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.root.chmod(0o700)
        self.source=self.root/'state';self.source.mkdir(mode=0o700)
        self.artifacts=self.root/'artifacts';self.artifacts.mkdir(mode=0o700)
        self.destination=self.artifacts/'retained-originals'
        self.catalog=ChatArchiveCatalog(hold_files=False)
        self.addCleanup(lambda:self.assertTrue(self.catalog.close_host()))
        self.catalog.parents[self.artifacts]=OriginalDescriptor(self.artifacts,
            os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
        self.stores=[]
        for index in range(3):
            store=PrivateFeatureState(self.source/f'original-{index}.json')
            value=dict(original=index,literal='\x00ä Ω 東京');store.write(value,None)
            self.catalog.add('primary/'+store.path.name,store,value);self.stores.append(store)
        self.calls=[];self.expected_close={}

    def plan(self):
        owner=OriginalDirectoryRetirement(self.catalog,self.source,self.destination)
        self.expected_close[owner]=True
        self.addCleanup(lambda:self.assertEqual(self.expected_close[owner],owner.close_host()));return owner

    def retire(self,owner):
        owner.retire(lambda:self.calls.append('phase'),before_move=lambda:self.calls.append('deadline'))

    def test_actual_no_replace_move_preserves_every_original_byte_stamp_and_directory_ofd(self):
        owner=self.plan();before={path.name:(path.read_bytes(),signature(path.lstat())) for path in self.source.iterdir()}
        directory=self.catalog.parents[self.source];fd,anchor=directory.fd,directory.anchor
        self.retire(owner)
        self.assertEqual(['phase','deadline'],self.calls)
        self.assertFalse(self.source.exists());self.assertEqual((fd,anchor),(directory.fd,directory.anchor))
        for name,(raw,info) in before.items():
            path=self.destination/name
            self.assertEqual(raw,path.read_bytes());self.assertEqual(info,signature(path.lstat()))
        receipt=owner.receipt();self.assertEqual(0,receipt['originalUnlinks']);self.assertEqual(1,receipt['atomicDirectoryMoves'])
        self.assertEqual(3,receipt['originals']);self.assertTrue(owner.close_host())
        directory.require(fd)

    def test_after_actual_host_close_only_historical_full_byte_readback_is_available(self):
        owner=self.plan();self.retire(owner)
        before=owner.receipt();self.assertTrue(self.catalog.close_host());self.assertTrue(owner.close_host())
        self.assertEqual(before,owner.receipt())
        with self.assertRaises(NativeUIError):owner.verify()
        self.assertFalse(owner.failed)

    def test_unknown_child_is_never_adopted(self):
        owner=self.plan();orphan=self.source/'unknown.json';orphan.write_bytes(b'{"unknown":true}\n')
        with self.assertRaises(NativeUIError):self.retire(owner)
        self.assertEqual([],self.calls);self.assertFalse(owner.attempted)
        self.assertTrue(orphan.exists());self.assertFalse(self.destination.exists())

    def test_existing_destination_even_empty_is_not_overwritten(self):
        owner=self.plan();self.destination.mkdir(mode=0o700)
        with self.assertRaises(NativeUIError):self.retire(owner)
        self.assertFalse(owner.attempted);self.assertTrue(self.source.exists());self.assertTrue(self.destination.exists())

    def test_same_byte_original_inode_replacement_refuses_before_phase_or_mutation(self):
        owner=self.plan();store=self.stores[0];store.write(store.read(),store.read())
        with self.assertRaises(NativeUIError):self.retire(owner)
        self.assertEqual([],self.calls);self.assertFalse(owner.attempted);self.assertTrue(self.source.exists())

    def test_phase_callback_replacement_is_detected_before_actual_move(self):
        owner=self.plan();store=self.stores[0]
        def changed():store.write(store.read(),store.read())
        with self.assertRaises(NativeUIError):owner.retire(changed,before_move=lambda:None)
        self.assertFalse(owner.attempted);self.assertTrue(self.source.exists());self.assertFalse(self.destination.exists())

    def test_expired_original_window_prevents_syscall_after_local_verification(self):
        owner=self.plan()
        def expired():raise NativeUIError('Original250ms window expired')
        with patch('adapters.chat_journey.directory_retirement.rename_original') as move:
            with self.assertRaises(NativeUIError):owner.retire(lambda:None,before_move=expired)
            move.assert_not_called()
        self.assertTrue(owner.failed);self.assertFalse(owner.attempted);self.assertTrue(self.source.exists())

    def test_same_inode_recycled_directory_half_is_not_force_closed(self):
        owner=self.plan();directory=owner.source_parent;foreign=os.open(self.source.parent,os.O_RDONLY|os.O_DIRECTORY)
        original_fd=directory.fd;os.close(original_fd);os.dup2(foreign,original_fd);os.close(foreign)
        self.addCleanup(lambda:os.close(original_fd))
        with self.assertRaises(NativeUIError):self.retire(owner)
        self.assertFalse(owner.close_host());self.assertFalse(directory.closed)
        os.fstat(original_fd);self.assertTrue(self.source.exists());self.assertFalse(self.destination.exists())
        # The unambiguously original alias is retained until host finalization.
        self.addCleanup(lambda:os.close(directory.anchor))
        # This intentionally lost owner has no successful close receipt.
        self.expected_close[owner]=False

    def test_unknown_landed_move_keeps_actual_originals_and_cannot_repeat(self):
        owner=self.plan()
        from adapters.chat_journey.directory_retirement import rename_original
        def lost(*args):rename_original(*args);raise OSError('Actual receipt lost')
        with patch('adapters.chat_journey.directory_retirement.rename_original',lost):
            with self.assertRaises(OSError):self.retire(owner)
        self.assertTrue(owner.attempted);self.assertTrue(owner.failed)
        self.assertFalse(self.source.exists());self.assertTrue(self.destination.exists())
        before={path.name:path.read_bytes() for path in self.destination.iterdir()}
        with self.assertRaises(NativeUIError):self.retire(owner)
        self.assertEqual(before,{path.name:path.read_bytes() for path in self.destination.iterdir()})

    def test_same_bytes_in_new_destination_inode_cannot_qualify_retained_receipt(self):
        owner=self.plan();self.retire(owner)
        store=PrivateFeatureState(self.destination/self.stores[0].path.name);store.write(store.read(),store.read())
        with self.assertRaises(NativeUIError):owner.receipt()


if __name__=='__main__':unittest.main()
