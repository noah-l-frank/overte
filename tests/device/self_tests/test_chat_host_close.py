"""Actual archive/kernel pairs/CAS/parent; preceding product facts are seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
from types import SimpleNamespace
import os
import unittest
from unittest.mock import patch

from adapters.chat_actor_files import ChatActorFiles
from adapters.chat_journey.owned_peer import OwnedChatPeer
from adapters.native_fd_owner import OriginalDescriptor
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4.chat_archive import PicoChatArchivePlan
from adapters.pico4.chat_composition import PicoChatComposition
from adapters.pico4.chat_restart_io import PicoChatRestartIO
from adapters.script_journey.lock import ScriptSourceLock
from fixture.chat_actor_process import LinuxChatActorProcess
from openxr_input.binding_transfer import OriginalBindingTransfer
from self_tests import test_chat_archive_unlink_fence as archive_seams
from self_tests.test_native_chat_observation import BINDING


class ChatHostCloseTests(unittest.TestCase):
    def setUp(self):
        self.h=archive_seams.ChatArchiveUnlinkFenceTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
        p=self.parent=PicoChatComposition.__new__(PicoChatComposition)
        p.failed=False;p.binding=BINDING;p.source=SimpleNamespace(run=archive_seams.RUN)
        p.application_close=SimpleNamespace(new_binding=BINDING|dict(processIdentity='789:999'))
        archive=self.archive=self.h.make(indexed=True)
        archive.metadata.update(picoChatArchivePlanVersion=4,oldBinding=p.binding,newBinding=p.application_close.new_binding)
        archive.retire();p.archive_plan=PicoChatArchivePlan.__new__(PicoChatArchivePlan)
        p.archive_plan.parent=p;p.archive_plan.archive=archive
        p.peer=OwnedChatPeer.__new__(OwnedChatPeer);p.peer.retirement_files=None
        p.peer.files=ChatActorFiles.__new__(ChatActorFiles)
        p.peer.files.fd_owner=self.descriptor(self.h.root,True);p.peer.files.fd=p.peer.files.fd_owner.fd
        p.peer.process=LinuxChatActorProcess.__new__(LinuxChatActorProcess)
        p.peer.process.fd_owner=self.descriptor(Path('/proc/self/exe'));p.peer.process.fd=p.peer.process.fd_owner.fd
        p.restart_io=PicoChatRestartIO.__new__(PicoChatRestartIO)
        p.restart_io.transfer=OriginalBindingTransfer.__new__(OriginalBindingTransfer)
        transfer=p.restart_io.transfer;transfer.new=None;transfer.root=self.descriptor(self.h.root,True)
        self.session=self.h.root/'original-session.json';self.session.write_bytes(b'original-session');self.session.chmod(0o600)
        transfer.old=self.descriptor(self.session);transfer.lock_owner=None
        self.addCleanup(p.detach)
        p.lock=ScriptSourceLock(self.h.root/'script-sources.lock');p.peer.lock=ScriptSourceLock(self.h.root/'peer-sources.lock')
        self.store=PrivateFeatureState(self.h.root/'host-close.json')
        p.adapter=SimpleNamespace(_chat_host_close_store=lambda target:self.store);p.target='explicit-host-seam'

    def descriptor(self,path,directory=False):
        flags=os.O_RDONLY|os.O_CLOEXEC
        if str(path)!='/proc/self/exe':flags|=os.O_NOFOLLOW
        if directory:flags|=os.O_DIRECTORY
        owner=OriginalDescriptor(path,flags)
        self.addCleanup(owner.close);return owner

    def test_original_parent_closes_real_kernel_pairs_before_removing_separate_host_intent(self):
        result=self.parent.finalize_host();owner=self.parent.host_close
        self.assertEqual('original-host-chat-handles',result['sourceScope']);self.assertTrue(owner.complete)
        self.assertTrue(all(pair.closed and pair.fd==pair.anchor==-1 for pair,_row in owner.pairs))
        self.assertEqual(len(owner.pairs),result['closedPairs']);self.assertIsNone(self.store.read())
        self.assertEqual(2,result['closedJournalWindows'])
        self.assertIsNone(self.parent.peer.files);self.assertIsNone(self.parent.peer.process)
        self.assertTrue(self.archive.complete)
        with self.assertRaises(NativeUIError):self.parent.finalize_host()

    def test_lost_initial_host_intent_never_closes_or_replays_original_pairs(self):
        write=self.store.write
        def lost(value,previous):write(value,previous);raise OSError('Original initial host intent receipt lost')
        self.store.write=lost
        with self.assertRaises(NativeUIError):self.parent.finalize_host()
        owner=self.parent.host_close;self.assertEqual('detach-issued',self.store.read()['phase'])
        self.assertTrue(all(not pair.closed for pair,_row in owner.pairs))
        with self.assertRaises(NativeUIError):self.parent.finalize_host()

    def test_unknown_existing_host_root_is_never_adopted_replaced_or_detached(self):
        value=dict(original='unknown-host-intent');self.store.write(value,None)
        with self.assertRaises(NativeUIError):self.parent.finalize_host()
        self.assertEqual(value,self.store.read());self.assertFalse(self.parent.peer.process.fd_owner.closed)

    def test_final_intent_fd_recycle_retains_original_owner_and_never_closes_same_file_foreign_fd(self):
        original=self.parent.restart_io.transfer.old;descriptor,anchor=original.fd,original.anchor
        write=self.store.write;foreign=[]
        def recycled(value,previous):
            write(value,previous)
            if value['phase']=='detach-issued':
                os.close(descriptor);foreign.append(os.open(self.session,os.O_RDONLY|os.O_CLOEXEC));self.assertEqual(descriptor,foreign[0])
        self.store.write=recycled
        try:
            with self.assertRaises(NativeUIError):self.parent.finalize_host()
            self.assertEqual('unresolved',self.store.read()['phase']);self.assertIs(original,self.parent.restart_io.transfer.old)
            self.assertFalse(original.closed);self.assertEqual(descriptor,original.fd)
            self.assertEqual(self.session.stat().st_ino,os.fstat(foreign[0]).st_ino)
            with self.assertRaises(NativeUIError):self.parent.finalize_host()
        finally:
            for fd in foreign:os.close(fd)
            os.close(anchor)

    def test_success_ack_without_actual_descriptor_close_cannot_retire_host_intent(self):
        close=OriginalDescriptor.close
        def ack(owner):
            finalizer=getattr(self.parent,'host_close',None)
            if finalizer is not None and any(owner is pair for pair,_row in finalizer.pairs):return True
            return close(owner) # Transient byte-read windows still close for real.
        with patch.object(OriginalDescriptor,'close',ack),self.assertRaises(NativeUIError):self.parent.finalize_host()
        self.assertEqual('unresolved',self.store.read()['phase'])
        self.assertTrue(all(not pair.closed for pair,_row in self.parent.host_close.pairs))
        self.assertGreaterEqual(self.parent.peer.files.fd,0)

    def test_replaced_original_parent_after_intent_does_not_adopt_or_modify_foreign_root(self):
        root=self.h.root;saved=root.with_name(root.name+'-original');moved=[];write=self.store.write
        def restore():
            if moved:
                for path in root.iterdir():path.unlink()
                root.rmdir();saved.rename(root)
        self.addCleanup(restore)
        def replace(value,previous):
            write(value,previous)
            if value['phase']=='detach-issued':
                root.rename(saved);root.mkdir(mode=0o700);moved.append(True)
                PrivateFeatureState(self.store.path).write(dict(foreign='unowned-host-root'),None)
        self.store.write=replace
        with self.assertRaises(NativeUIError):self.parent.finalize_host()
        self.assertEqual(dict(foreign='unowned-host-root'),PrivateFeatureState(self.store.path).read())
        self.assertTrue(all(not pair.closed for pair,_row in self.parent.host_close.pairs))

    def test_replaced_wrapper_close_callback_cannot_be_adopted_as_original_owner(self):
        self.parent.restart_io.close_host=lambda:True
        with self.assertRaises(NativeUIError):self.parent.finalize_host()
        self.assertIsNone(self.store.read());self.assertFalse(self.parent.peer.process.fd_owner.closed)
        self.parent.restart_io.__dict__.pop('close_host')

    def test_lost_closed_record_keeps_durable_original_even_when_kernel_closes_landed(self):
        write=self.store.write
        def lost(value,previous):
            write(value,previous)
            if value['phase']=='closed':raise OSError('Original closed-record receipt lost')
        self.store.write=lost
        with self.assertRaises(NativeUIError):self.parent.finalize_host()
        self.assertEqual('closed',self.store.read()['phase']);self.assertFalse(self.parent.host_close.complete)
        self.assertTrue(all(pair.closed for pair,_row in self.parent.host_close.pairs))

    def test_lost_final_marker_unlink_leaves_cas_from_absence_failure_not_cold_success(self):
        discard=self.store.discard
        def lost(value):discard(value);raise OSError('Original final host marker unlink receipt lost')
        self.store.discard=lost
        with self.assertRaises(NativeUIError):self.parent.finalize_host()
        self.assertEqual('final-unavailable',self.store.read()['phase']);self.assertFalse(self.parent.host_close.complete)
        self.assertTrue(all(pair.closed for pair,_row in self.parent.host_close.pairs))

    def test_actual_parent_fsync_precedes_any_original_pair_close(self):
        fsync=os.fsync;close=OriginalDescriptor.close;events=[]
        def recorded(fd):
            if fd==self.archive.catalog.parents[self.h.root].fd:events.append('initial-parent-sync')
            return fsync(fd)
        def closed(owner):
            finalizer=getattr(self.parent,'host_close',None)
            if finalizer is not None and any(owner is pair for pair,_row in finalizer.pairs):events.append('captured-close')
            return close(owner)
        with patch('adapters.pico4.chat_host_close.os.fsync',recorded),patch.object(OriginalDescriptor,'close',closed):self.parent.finalize_host()
        self.assertLess(events.index('initial-parent-sync'),events.index('captured-close'));self.assertTrue(self.parent.host_close.complete)

    def test_recycled_final_directory_window_is_not_closed_or_hidden_by_landed_marker_unlink(self):
        fsync=os.fsync;foreign=[];anchors=[]
        def recycle(fd):
            owner=getattr(self.parent,'host_close',None)
            if owner is not None and len(owner.journal_pairs)==2 and fd==owner.journal_pairs[-1].fd and not foreign:
                original=owner.journal_pairs[-1];anchors.append(original.anchor);os.close(fd)
                foreign.append(os.open(self.h.root,os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC));self.assertEqual(fd,foreign[0])
            return fsync(fd)
        try:
            with patch('adapters.pico4.chat_host_close.os.fsync',recycle),self.assertRaises(NativeUIError):self.parent.finalize_host()
            self.assertEqual('final-unavailable',self.store.read()['phase']);self.assertFalse(self.parent.host_close.complete)
            self.assertFalse(self.parent.detach());self.assertFalse(self.parent.host_close.journal_pairs[1].closed)
            self.assertEqual(self.h.root.stat().st_ino,os.fstat(foreign[0]).st_ino)
        finally:
            for fd in foreign+anchors:os.close(fd)


if __name__=='__main__':unittest.main()
