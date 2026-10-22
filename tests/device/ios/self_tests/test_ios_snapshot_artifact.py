"""Actual private artifact writes/loss/partial bytes; native producers modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.snapshot_artifact import SnapshotArtifact
from ios.self_tests import test_ios_snapshot_original_file as fixture


class SnapshotArtifactTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.SnapshotOriginalFileTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.ctx=self.f.f;self.run=fixture.fixture.fixture.RUN
    def owner(self):
        return SnapshotArtifact(PrivateFeatureState(self.ctx.root/'ios-snapshot-primary-artifact-0001.json'),
            self.ctx.lock,self.ctx.binding,self.run,'primary',1,lambda:True)
    def originals(self):
        args=self.f.completed();self.f.callbacks.clear();return (*args,self.f.jobs.read())
    def forbidden(self,*_args,**_kwargs):raise AssertionError('Artifact reconstruction rewrote or resampled an original')

    def test_actual_private_file_retains_all_original_bytes_and_separate_work_source(self):
        with self.ctx.lock.held():
            args=self.originals();owner=self.owner();fact=owner.capture(*args)
            self.assertEqual(self.f.h.path.read_bytes(),owner.read());self.assertEqual(0o600,owner.path().stat().st_mode&0o777)
            self.assertTrue(owner.frames().path(owner.state['work']).exists());self.assertTrue(fact['imageOutcomeRequired'])
            with patch.object(self.ctx.feature,'original',side_effect=self.forbidden):
                rebuilt=self.owner();self.assertEqual(fact,rebuilt.recover());self.assertEqual(owner.read(),rebuilt.read())
            with self.assertRaises(NativeUIError):rebuilt.capture(*args)
            self.assertEqual(5,len(self.ctx.files.commands))

    def test_lost_copied_metadata_return_adopts_same_inode_without_new_source_or_write(self):
        with self.ctx.lock.held():
            args=self.originals();owner=self.owner();write=owner.store.write
            def lost(value,previous):
                write(value,previous)
                if owner.state['phase']=='copied':raise OSError('Actual committed copy response lost')
            with patch.object(owner.store,'write',side_effect=lost),self.assertRaises(OSError):owner.capture(*args)
            path=owner.path();info=path.stat();rebuilt=self.owner()
            with patch.object(type(rebuilt.frames()),'write',side_effect=self.forbidden):rebuilt.recover()
            self.assertEqual((info.st_ino,info.st_mtime_ns),(path.stat().st_ino,path.stat().st_mtime_ns))
            self.assertEqual(5,len(self.ctx.files.commands))

    def test_actual_opened_empty_file_is_not_overwritten_and_can_be_retired_as_partial(self):
        with self.ctx.lock.held():
            args=self.originals();owner=self.owner();save=owner.save
            def lost():
                save()
                if owner.state['phase']=='opened':raise OSError('Actual opened empty artifact response lost')
            with patch.object(owner,'save',side_effect=lost),self.assertRaises(OSError):owner.capture(*args)
            rebuilt=self.owner();path=rebuilt.path();inode=path.stat().st_ino
            self.assertEqual(b'',path.read_bytes())
            with self.assertRaises(NativeUIError):rebuilt.recover()
            with self.assertRaises(NativeUIError):rebuilt.capture(*args)
            self.assertEqual(inode,path.stat().st_ino);self.assertEqual({'performed':True},rebuilt.remove())
            self.assertFalse(path.exists());self.assertEqual('removed',self.owner().state['phase'])

    def test_unrecorded_artifact_create_is_held_without_overwrite_or_unlink(self):
        with self.ctx.lock.held():
            args=self.originals();owner=self.owner();save=owner.save
            def interrupt():
                if owner.state['phase']=='opened':raise OSError('Opened inode metadata never committed')
                save()
            with patch.object(owner,'save',side_effect=interrupt),self.assertRaises(OSError):owner.capture(*args)
            rebuilt=self.owner();self.assertEqual('assembling',rebuilt.state['phase']);path=rebuilt.path();inode=path.stat().st_ino
            with self.assertRaises(NativeUIError):rebuilt.recover()
            with self.assertRaises(NativeUIError):rebuilt.remove()
            self.assertEqual(inode,path.stat().st_ino);self.assertEqual(b'',path.read_bytes())

    def test_modified_replaced_or_hardlinked_artifact_stays_owned(self):
        with self.ctx.lock.held():
            owner=self.owner();owner.capture(*self.originals());path=owner.path();raw=path.read_bytes()
            other=path.with_suffix('.link');os.link(path,other)
            with self.assertRaises(NativeUIError):owner.read()
            with self.assertRaises(NativeUIError):owner.remove()
            other.unlink();path.write_bytes(raw+b'changed')
            with self.assertRaises(NativeUIError):owner.read()
            with self.assertRaises(NativeUIError):owner.remove()
            replacement=path.with_suffix('.replacement');replacement.write_bytes(raw);replacement.chmod(0o600);os.replace(replacement,path)
            with self.assertRaises(NativeUIError):owner.read()
            with self.assertRaises(NativeUIError):owner.remove()

    def test_lost_unlink_result_uses_absence_without_repeating_unlink(self):
        with self.ctx.lock.held():
            owner=self.owner();owner.capture(*self.originals());path=owner.path();actual=type(path).unlink
            def lost(target,*args,**kwargs):
                actual(target,*args,**kwargs)
                if target==path:raise OSError('Actual unlink completed; caller return lost')
            with patch.object(type(path),'unlink',lost),self.assertRaises(OSError):owner.remove()
            rebuilt=self.owner();self.assertEqual('removing',rebuilt.state['phase'])
            def never_repeat(target,*args,**kwargs):
                if target==path:self.forbidden()
                return actual(target,*args,**kwargs)
            with patch.object(type(path),'unlink',never_repeat):self.assertTrue(rebuilt.remove()['performed'])
            self.assertEqual('removed',self.owner().state['phase']);self.assertTrue(rebuilt.frames().path(rebuilt.state['work']).exists())

    def test_native_work_original_or_query_original_loss_blocks_artifact_recovery(self):
        with self.ctx.lock.held():
            owner=self.owner();owner.capture(*self.originals());path=owner.frames().path(owner.state['work'])
            path.write_bytes(path.read_bytes()+b' ')
            with self.assertRaises(NativeUIError):self.owner().recover()
            self.assertTrue(owner.path().exists())

    def test_forgotten_actual_query_journal_blocks_recovery_and_keeps_host_file(self):
        with self.ctx.lock.held():
            args=self.originals();owner=self.owner();owner.capture(*args)
            args[2][0].store.discard(args[2][0].previous)
            with self.assertRaises(NativeUIError):self.owner().recover()
            with self.assertRaises(NativeUIError):self.owner().remove()
            self.assertTrue(owner.path().exists())


if __name__=='__main__':unittest.main()
