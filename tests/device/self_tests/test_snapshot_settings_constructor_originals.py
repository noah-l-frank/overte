"""Actual Snapshot-path file constructor ownership; no Native/SDK endpoint."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import gc
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from adapters.chat_journey.archive_file import ClosedOriginalFile
from adapters.native_fd_owner import OriginalDescriptor
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.lifecycle_process_file import LifecycleProcessFile

HELD=[]


class SnapshotSettingsConstructorOriginalTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(tempfile.mkdtemp(prefix='snapshot-settings-constructors-'))
        self.root.chmod(0o700)
        self.path=self.root/'snapshot-settings-query-originals.json'

    def store(self):return PrivateFeatureState(self.path)

    def fail_after_open(self,predicate,action=None):
        original=OriginalDescriptor.__init__;seen=[]
        def construct(owner,path,*args):
            original(owner,path,*args)
            if predicate(Path(path)):
                seen.append(owner)
                if action is not None:action(owner,path)
                raise OSError('Actual original FD pair opened before constructor response loss')
        return construct,seen

    def test_original_file_window_normal_read_and_repeat_close_balance_fds(self):
        self.path.write_bytes(b'{"actual":"bounded original"}\n');self.path.chmod(0o600)
        before=set(os.listdir('/proc/self/fd'))
        owner=ClosedOriginalFile(self.path,0o600,lambda:None)
        self.assertEqual(self.path.read_bytes(),owner.read()[0]);self.assertTrue(owner.close());self.assertTrue(owner.close())
        self.assertEqual(before,set(os.listdir('/proc/self/fd')))

    def test_original_file_ctor_response_loss_keeps_existing_verified_safe_close(self):
        self.path.write_bytes(b'actual original before constructor response loss');self.path.chmod(0o600)
        owner=ClosedOriginalFile(self.path,0o600,lambda:None);HELD.append(owner)
        callback,seen=self.fail_after_open(lambda path:path==self.path)
        before=set(os.listdir('/proc/self/fd'))
        with patch.object(OriginalDescriptor,'__init__',callback),self.assertRaises(OSError):owner.read()
        gc.collect();self.assertEqual(1,len(seen));self.assertTrue(seen[0].closed)
        self.assertIsNone(owner.active);self.assertEqual(before,set(os.listdir('/proc/self/fd')))

    def test_recycled_fd_after_ctor_open_is_strongly_retained_and_foreign_not_closed(self):
        self.path.write_bytes(b'actual same-inode different-open-description fixture');self.path.chmod(0o600)
        owner=ClosedOriginalFile(self.path,0o600,lambda:None);HELD.append(owner);foreign=[]
        def recycle(original,path):
            descriptor=original.fd;os.close(descriptor);replacement=os.open(path,os.O_RDONLY|os.O_CLOEXEC)
            if replacement!=descriptor:os.dup2(replacement,descriptor);os.close(replacement)
            foreign.append(descriptor)
        callback,seen=self.fail_after_open(lambda path:path==self.path,recycle)
        with patch.object(OriginalDescriptor,'__init__',callback),self.assertRaises(OSError):owner.read()
        gc.collect();self.assertIs(owner.active,seen[0]);self.assertFalse(owner.close())
        stamp=os.fstat(foreign[0]);self.assertEqual(stamp,os.fstat(owner.active.fd));self.assertIsNotNone(os.fstat(owner.active.anchor))
        self.assertFalse(owner.close());self.assertEqual(stamp,os.fstat(foreign[0]))
        os.close(foreign[0]) # Only the independently opened fixture replacement.

    def test_parent_ctor_response_loss_retains_actual_original_pair_after_gc(self):
        owner=object.__new__(LifecycleProcessFile);HELD.append(owner)
        callback,seen=self.fail_after_open(lambda path:path==self.root)
        with patch.object(OriginalDescriptor,'__init__',callback),self.assertRaises(OSError):LifecycleProcessFile.__init__(owner,self.store())
        gc.collect();self.assertEqual(1,len(seen));self.assertIs(owner.parent,seen[0]);self.assertIs(owner._parent,seen[0])
        owner.parent.require(owner.parent.fd);self.assertIsNotNone(os.fstat(owner.parent.anchor))

    def test_initial_file_ctor_response_loss_retains_actual_original_pair_after_gc(self):
        self.store().write({'existing':'original'},None)
        owner=object.__new__(LifecycleProcessFile);HELD.append(owner)
        callback,seen=self.fail_after_open(lambda path:path==self.path)
        with patch.object(OriginalDescriptor,'__init__',callback),self.assertRaises(OSError):LifecycleProcessFile.__init__(owner,self.store())
        gc.collect();self.assertEqual(1,len(seen));self.assertIs(owner.file,seen[0]);self.assertIs(owner._file,seen[0])
        owner.file.require(owner.file.fd);owner.parent.require(owner.parent.fd)

    def test_prepared_candidate_ctor_loss_retains_actual_pending_file_and_pair_after_gc(self):
        owner=LifecycleProcessFile(self.store());HELD.append(owner)
        callback,seen=self.fail_after_open(lambda path:path.name.startswith(self.path.name+'.pending-'))
        with patch.object(OriginalDescriptor,'__init__',callback),self.assertRaises(OSError):owner.write({'actual':'candidate'},None)
        gc.collect();self.assertEqual(1,len(seen));self.assertTrue(owner.failed)
        self.assertEqual(1,len(owner.uncertain));self.assertIs(owner.uncertain[0],seen[0])
        seen[0].require(seen[0].fd);self.assertTrue(Path(owner.temporary).exists());self.assertFalse(self.path.exists())


if __name__=='__main__':unittest.main()
