"""Original Linux kernel OFDs, including recycled same-inode foreign handles."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import errno
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from adapters import native_fd_owner as module
from adapters.native_fd_owner import OriginalDescriptor,require_directory
from adapters.normal_ui import NativeUIError


class OriginalDescriptorTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.path=self.root/'original';self.path.write_bytes(b'actual owned original')

    @unittest.skipUnless(module.QUERY is not None,'Original Linux OFD query is unavailable')
    def test_original_kernel_aliases_close_together_without_guessing_from_inode(self):
        owner=OriginalDescriptor(self.path,os.O_RDONLY|os.O_CLOEXEC);descriptor,anchor=owner.fd,owner.anchor
        owner.require(descriptor);self.assertTrue(owner.close());self.assertTrue(owner.close())
        for fd in (descriptor,anchor):
            with self.assertRaises(OSError):os.fstat(fd)

    @unittest.skipUnless(module.QUERY is not None,'Original Linux OFD query is unavailable')
    def test_current_kernel_query_distinguishes_alias_from_independent_same_inode_and_cross_file(self):
        owner=OriginalDescriptor(self.path,os.O_RDONLY|os.O_CLOEXEC);self.addCleanup(owner.close)
        foreign_path=self.root/'other-original';foreign_path.write_bytes(b'other owned original')
        same=os.open(self.path,os.O_RDONLY|os.O_CLOEXEC);different=os.open(foreign_path,os.O_RDONLY|os.O_CLOEXEC)
        try:
            self.assertEqual(1,module.fcntl.fcntl(owner.fd,module.QUERY,owner.anchor))
            self.assertEqual(1,module.fcntl.fcntl(owner.fd,module.QUERY,owner.fd))
            self.assertEqual(os.fstat(owner.fd).st_ino,os.fstat(same).st_ino)
            self.assertEqual(0,module.fcntl.fcntl(owner.fd,module.QUERY,same))
            self.assertEqual(0,module.fcntl.fcntl(owner.fd,module.QUERY,different))
            owner.require(owner.fd);self.assertFalse(owner.lost)
        finally:os.close(same);os.close(different)

    @unittest.skipUnless(module.QUERY is not None,'Original Linux OFD query is unavailable')
    def test_closed_anchor_query_error_latches_loss_without_closing_original_descriptor(self):
        owner=OriginalDescriptor(self.path,os.O_RDONLY|os.O_CLOEXEC);descriptor,anchor=owner.fd,owner.anchor
        os.close(anchor)
        try:
            with self.assertRaises((OSError,NativeUIError)) as caught:owner.require(descriptor)
            if isinstance(caught.exception,OSError):self.assertEqual(errno.EBADF,caught.exception.errno)
            self.assertTrue(owner.lost);self.assertFalse(owner.close())
            self.assertEqual(owner.node,(os.fstat(descriptor).st_dev,os.fstat(descriptor).st_ino))
        finally:os.close(descriptor)

    @unittest.skipUnless(module.QUERY is not None,'Original Linux OFD query is unavailable')
    def test_cross_file_replacement_of_either_half_remains_foreign_and_sticky(self):
        foreign_path=self.root/'foreign-original';foreign_path.write_bytes(b'foreign original')
        for replace_anchor in (False,True):
            with self.subTest(anchor=replace_anchor):
                owner=OriginalDescriptor(self.path,os.O_RDONLY|os.O_CLOEXEC);descriptor,anchor=owner.fd,owner.anchor
                foreign=os.open(foreign_path,os.O_RDONLY|os.O_CLOEXEC)
                try:
                    owner.require(descriptor)
                    os.dup2(foreign,anchor if replace_anchor else descriptor)
                    self.assertEqual(0,module.fcntl.fcntl(descriptor,module.QUERY,anchor))
                    with self.assertRaises(NativeUIError):owner.require(descriptor)
                    self.assertTrue(owner.lost);self.assertFalse(owner.close())
                    self.assertEqual(b'foreign original',os.pread(foreign,32,0))
                    os.fstat(descriptor);os.fstat(anchor)
                finally:os.close(foreign);os.close(descriptor);os.close(anchor)

    @unittest.skipUnless(module.QUERY is not None,'Original Linux OFD query is unavailable')
    def test_actual_kernel_query_error_after_admission_never_closes_or_readopts_pair(self):
        owner=OriginalDescriptor(self.path,os.O_RDONLY|os.O_CLOEXEC);descriptor,anchor=owner.fd,owner.anchor
        try:
            # Only ordinary command data changes; the real kernel call returns
            # EINVAL. No syscall/function or class is substituted here.
            with patch.object(module,'QUERY',0x7fffffff):
                with self.assertRaises(OSError) as caught:owner.require(descriptor)
            self.assertEqual(errno.EINVAL,caught.exception.errno)
            self.assertTrue(owner.lost);self.assertFalse(owner.close())
            self.assertEqual(1,module.fcntl.fcntl(descriptor,module.QUERY,anchor))
            os.fstat(descriptor);os.fstat(anchor)
        finally:os.close(descriptor);os.close(anchor)

    @unittest.skipUnless(module.QUERY is not None,'Original Linux OFD query is unavailable')
    def test_aliased_pair_still_requires_the_current_expected_node_and_exact_descriptor(self):
        foreign_path=self.root/'other-node';foreign_path.write_bytes(b'other node')
        for wrong_node in (False,True):
            with self.subTest(node=wrong_node):
                owner=OriginalDescriptor(self.path,os.O_RDONLY|os.O_CLOEXEC);descriptor,anchor=owner.fd,owner.anchor
                old=owner.node
                try:
                    self.assertEqual(1,module.fcntl.fcntl(descriptor,module.QUERY,anchor))
                    if wrong_node:
                        info=foreign_path.stat();owner.node=(info.st_dev,info.st_ino)
                    with self.assertRaises(NativeUIError):owner.require(descriptor if wrong_node else anchor)
                    owner.node=old
                    self.assertTrue(owner.lost);self.assertFalse(owner.close())
                    os.fstat(descriptor);os.fstat(anchor)
                finally:os.close(descriptor);os.close(anchor)

    @unittest.skipUnless(module.QUERY is not None,'Original Linux OFD query is unavailable')
    def test_recycled_descriptor_or_anchor_of_same_original_inode_is_never_closed(self):
        for replace_anchor in (False,True):
            for path,flags in ((self.path,os.O_RDONLY|os.O_CLOEXEC),(self.root,os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC)):
                owner=OriginalDescriptor(path,flags);descriptor,anchor=owner.fd,owner.anchor
                lost=anchor if replace_anchor else descriptor;os.close(lost);foreign=os.open(path,flags)
                try:
                    self.assertEqual(lost,foreign)
                    self.assertEqual(os.fstat(descriptor).st_ino,os.fstat(anchor).st_ino)
                    with self.subTest(anchor=replace_anchor,directory=path==self.root),self.assertRaises(NativeUIError):owner.require(descriptor)
                    self.assertFalse(owner.close());self.assertFalse(owner.close())
                    self.assertGreaterEqual(os.fstat(foreign).st_size,0);self.assertTrue(owner.lost)
                    os.fstat(anchor if not replace_anchor else descriptor)
                finally:
                    # These are explicitly test-owned foreign/original halves;
                    # the production owner intentionally does not close them.
                    os.close(descriptor);os.close(anchor)

    @unittest.skipUnless(module.QUERY is not None,'Original Linux OFD query is unavailable')
    def test_lost_descriptor_number_cannot_adopt_a_different_file(self):
        owner=OriginalDescriptor(self.path,os.O_RDONLY|os.O_CLOEXEC);descriptor,anchor=owner.fd,owner.anchor
        foreign_path=self.root/'foreign';foreign_path.write_bytes(b'foreign')
        os.close(descriptor);foreign=os.open(foreign_path,os.O_RDONLY|os.O_CLOEXEC)
        try:
            self.assertEqual(descriptor,foreign)
            with self.assertRaises(NativeUIError):owner.require(descriptor)
            self.assertFalse(owner.close());self.assertEqual(b'foreign',os.read(foreign,20))
        finally:os.close(foreign);os.close(anchor)

    def test_unavailable_kernel_query_refuses_admission_without_opening_or_leaking_handles(self):
        with patch.object(module,'QUERY',None),patch.object(module.os,'open',wraps=os.open) as opened:
            with self.assertRaises(NativeUIError):OriginalDescriptor(self.path,os.O_RDONLY|os.O_CLOEXEC)
            opened.assert_not_called()
        if module.QUERY is None:return
        original=module.fcntl.fcntl;opened=[]
        def unavailable(descriptor,operation,argument):
            if operation==module.QUERY:raise OSError(errno.EINVAL,'Explicit unsupported OFD query seam')
            result=original(descriptor,operation,argument);opened.extend((descriptor,result));return result
        with patch.object(module.fcntl,'fcntl',side_effect=unavailable),self.assertRaises(OSError):
            OriginalDescriptor(self.path,os.O_RDONLY|os.O_CLOEXEC)
        self.assertEqual(2,len(opened))
        for fd in opened:
            with self.assertRaises(OSError):os.fstat(fd)

    @unittest.skipUnless(module.QUERY is not None and module.sys.platform.startswith('linux'),'Original Linux OFD query is unavailable')
    def test_directory_guard_rechecks_exact_ofd_after_current_kernel_path_observation(self):
        owner=OriginalDescriptor(self.root,os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC)
        descriptor,anchor=owner.fd,owner.anchor;readlink=os.readlink;recycled=[]
        def change(path):
            value=readlink(path)
            foreign=os.open(self.root,os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC)
            try:os.dup2(foreign,descriptor)
            finally:os.close(foreign)
            recycled.append(True);return value
        try:
            with patch.object(module.os,'readlink',change),self.assertRaises(NativeUIError):require_directory(owner,self.root)
            self.assertEqual([True],recycled);self.assertFalse(owner.close());self.assertTrue(owner.lost)
            self.assertEqual(os.fstat(descriptor).st_ino,os.fstat(anchor).st_ino)
        finally:os.close(descriptor);os.close(anchor)

    @unittest.skipUnless(module.QUERY is not None,'Original Linux OFD query is unavailable')
    def test_directory_modes_and_other_platform_strict_resolution_remain_explicit(self):
        owner=OriginalDescriptor(self.root,os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC);self.addCleanup(owner.close)
        require_directory(owner,self.root)
        with self.assertRaises(NativeUIError):require_directory(owner,self.root,mode=True)
        with self.assertRaises(NativeUIError):require_directory(owner,self.root,mode=0o777)
        self.root.chmod(0o500)
        try:
            with self.assertRaises(NativeUIError):require_directory(owner,self.root)
            require_directory(owner,self.root,mode=0o500)
        finally:self.root.chmod(0o700)
        original=Path.resolve;calls=[]
        def resolve(path,*args,**kwargs):calls.append((path,args,kwargs));return original(path,*args,**kwargs)
        with patch.object(module.sys,'platform','other-platform-fixture'),patch.object(Path,'resolve',resolve):
            require_directory(owner,self.root)
        self.assertEqual([(self.root,(),dict(strict=True))],calls)


if __name__=='__main__':unittest.main()
