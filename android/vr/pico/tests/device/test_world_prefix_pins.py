"""Fresh full-file windows under one original private directory descriptor.

These are real host filesystem/OFD checks. They provide no target or journey
effects, live history adoption, source freshness or whole-feature authority.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[5]
sys.path[:0]=[str(ROOT/'tests/device')]
from adapters.chat_journey.archive_file import signature
from adapters.normal_ui import NativeUIError
from adapters.pico4 import world_web_prefix as subject


class WorldPrefixPinsTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name)/'original';self.root.mkdir(mode=0o700)
        self.owner=SimpleNamespace(root=self.root)
        for name,raw in (('a.json',b'{"value":1}'),('b.part-0000',b'original-fragment')):
            path=self.root/name
            with os.fdopen(os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600),'wb') as stream:stream.write(raw)

    def pins(self):return subject.PicoWorldWebPrefix.pins(self.owner)

    def test_every_file_has_exact_bytes_full_stamp_and_a_fresh_closed_window(self):
        before=len(os.listdir('/proc/self/fd'));actual_read=subject.ClosedOriginalFile.read;reads=[]
        def observed(reader,*args,**kwargs):
            value=actual_read(reader,*args,**kwargs);self.assertIsNone(reader.active);reads.append(reader.path);return value
        with patch.object(subject.ClosedOriginalFile,'read',observed):first=self.pins();second=self.pins()
        expected=[dict(path=str(path),signature=signature(path.lstat()),sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            for path in sorted(self.root.iterdir())]
        self.assertEqual(expected,first);self.assertEqual(first,second)
        self.assertEqual(list(sorted(self.root.iterdir()))*2,reads)
        self.assertEqual(before,len(os.listdir('/proc/self/fd')))

    def test_read_only_original_directory_keeps_its_existing_read_semantics(self):
        expected=self.pins();self.root.chmod(0o500)
        try:self.assertEqual(expected,self.pins())
        finally:self.root.chmod(0o700)

    def test_namespace_added_after_first_file_cannot_escape_final_namespace_check(self):
        actual=subject.ClosedOriginalFile.read;added=[]
        def changed(reader,*args,**kwargs):
            value=actual(reader,*args,**kwargs)
            if not added:
                path=self.root/'unexpected';path.touch(mode=0o600);added.append(path)
            return value
        with patch.object(subject.ClosedOriginalFile,'read',changed),self.assertRaises(NativeUIError):self.pins()
        self.assertEqual(1,len(added))

    def test_same_bytes_in_replacement_directory_cannot_replace_original_ofd(self):
        actual=subject.ClosedOriginalFile.read;replaced=[]
        def changed(reader,*args,**kwargs):
            value=actual(reader,*args,**kwargs)
            if not replaced:
                held=self.root.with_name('held');self.root.rename(held);self.root.mkdir(mode=0o700)
                for path in held.iterdir():
                    target=self.root/path.name
                    with os.fdopen(os.open(target,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600),'wb') as stream:stream.write(path.read_bytes())
                replaced.append(held)
            return value
        with patch.object(subject.ClosedOriginalFile,'read',changed),self.assertRaises(NativeUIError):self.pins()
        self.assertEqual(1,len(replaced));self.assertEqual(b'{"value":1}',(replaced[0]/'a.json').read_bytes())

    def test_symlinked_parent_is_refused_before_original_file_read(self):
        held=self.root.with_name('held');self.root.rename(held);self.root.symlink_to(held,target_is_directory=True)
        with (patch.object(subject.ClosedOriginalFile,'read',side_effect=AssertionError('unexpected file read')),
                self.assertRaises(NativeUIError)):self.pins()

    def test_changed_file_bytes_are_reread_and_change_the_actual_pin(self):
        before=self.pins();path=self.root/'a.json';path.write_bytes(b'{"value":2}')
        after=self.pins();self.assertNotEqual(before,after)
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),after[0]['sha256'])

    def test_recycled_directory_half_is_retained_and_foreign_handle_not_closed_or_readopted(self):
        actual_owner=subject.OriginalDescriptor;actual_read=subject.ClosedOriginalFile.read;directory=[];foreign=[]
        def opened(path,flags):
            value=actual_owner(path,flags);directory.append(value);return value
        def recycled(reader,*args,**kwargs):
            value=actual_read(reader,*args,**kwargs)
            if not foreign:
                owner=directory[0];os.close(owner.fd)
                descriptor=os.open(self.root,os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC)
                self.assertEqual(owner.fd,descriptor);foreign.append(descriptor)
            return value
        try:
            with patch.object(subject,'OriginalDescriptor',opened),patch.object(subject.ClosedOriginalFile,'read',recycled),self.assertRaises(NativeUIError):self.pins()
            self.assertEqual(1,len(directory));self.assertEqual(1,len(foreign))
            self.assertEqual(self.root.lstat().st_ino,os.fstat(foreign[0]).st_ino)
            self.assertIn((self.root,directory[0]),subject.UNRESOLVED_PIN_READS)
            with patch.object(subject.ClosedOriginalFile,'read',side_effect=AssertionError('unexpected readoption')),self.assertRaises(NativeUIError):self.pins()
            self.assertEqual(self.root.lstat().st_ino,os.fstat(foreign[0]).st_ino)
        finally:
            # This fixture created the replacement and owns its finalization.
            # The production read window never closes either uncertain half.
            for descriptor in foreign:os.close(descriptor)
            for owner in directory:
                if owner.anchor>=0:os.close(owner.anchor)
                subject.UNRESOLVED_PIN_READS[:]=[(root,held) for root,held in subject.UNRESOLVED_PIN_READS if held is not owner]


if __name__=='__main__':unittest.main()
