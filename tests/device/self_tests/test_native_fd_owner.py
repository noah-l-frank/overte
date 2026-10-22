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
from adapters.native_fd_owner import OriginalDescriptor
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


if __name__=='__main__':unittest.main()
