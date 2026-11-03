"""Actual loaded codec/OFD ownership; no Native source or input authority."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import ctypes
import gc
import os
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch
import zlib

from adapters.loaded_chunk_codec import OriginalChunkCodec,UNRESOLVED
from adapters.native_fd_owner import OriginalDescriptor
from adapters.normal_ui import NativeUIError
from adapters.script_journey import history


class LoadedChunkCodecTests(unittest.TestCase):
    def test_actual_bound_vectors_profile_copy_and_original_descriptor_close(self):
        before=set(os.listdir('/proc/self/fd'));owner=OriginalChunkCodec()
        try:
            for value in (b'',b'a',bytes(4096),random.Random(113).randbytes(69632)):
                self.assertLessEqual(len(zlib.compress(value,level=9)),owner.compress_bound(len(value)))
            self.assertGreaterEqual(owner.compress_bound(history.MAX_RAW),history.MAX_RAW)
            value=owner.public_profile();value['files'][0]['sha256']='0'*64;owner.guard()
            self.assertGreater(owner.metadata_bytes(),0)
        finally:self.assertTrue(owner.close_host())
        self.assertTrue(owner.close_host())
        self.assertEqual(before,set(os.listdir('/proc/self/fd')))

    def test_forged_closed_flag_cannot_retire_actual_open_original_descriptors(self):
        owner=OriginalChunkCodec();pairs=[row[1] for row in owner.files]
        stamps=[(os.fstat(pair.fd),os.fstat(pair.anchor)) for pair in pairs]
        owner.closed=True
        self.assertFalse(owner.close_host());self.assertIn(owner,UNRESOLVED)
        for pair,(descriptor,anchor) in zip(pairs,stamps):
            pair.require(pair.fd)
            self.assertEqual(descriptor,os.fstat(pair.fd));self.assertEqual(anchor,os.fstat(pair.anchor))

    def test_closed_terminal_field_types_do_not_accept_equal_values(self):
        for key,value in (('closed',1),('lost',0),('fd',-1.0),('anchor',-1.0)):
            with self.subTest(key=key):
                owner=OriginalChunkCodec();self.assertTrue(owner.close_host())
                setattr(owner.files[0][1],key,value)
                self.assertFalse(owner.close_host());self.assertIn(owner,UNRESOLVED)

    def test_closed_foreign_holder_has_no_close_or_equality_callback(self):
        owner=OriginalChunkCodec();self.assertTrue(owner.close_host());calls=[]
        with tempfile.TemporaryDirectory(prefix='codec-closed-foreign-') as directory:
            path=Path(directory)/'foreign';path.write_bytes(b'foreign independently opened original')
            fd=os.open(path,os.O_RDONLY|os.O_CLOEXEC);before=os.fstat(fd)
            class Foreign:
                def __eq__(self,_):calls.append('equal');return True
                def close(self):calls.append('close');return True
            try:
                owner.files[0][1]=Foreign()
                self.assertFalse(owner.close_host());self.assertFalse(calls);self.assertEqual(before,os.fstat(fd))
            finally:os.close(fd)

    def test_foreign_equal_callable_refuses_without_any_foreign_hook(self):
        owner=OriginalChunkCodec();calls=[]
        class Foreign:
            def __eq__(self,_other):calls.append('equality');return True
            def __call__(self,*args,**options):calls.append('codec');raise AssertionError('Foreign codec')
        with patch.object(zlib,'compress',Foreign()),self.assertRaises(NativeUIError):owner.compress_bound(64)
        self.assertFalse(calls);self.assertIn(owner,UNRESOLVED);self.assertFalse(owner.close_host())

    def test_equal_code_alias_cannot_replace_original_function_code_seal(self):
        owner=OriginalChunkCodec();owner.codes=tuple(list(owner.codes))
        with self.assertRaises(NativeUIError):owner.compress_bound(64)
        self.assertIn(owner,UNRESOLVED);self.assertFalse(owner.close_host())

    def test_ffi_argument_type_change_refuses_before_bound_call(self):
        owner=OriginalChunkCodec();owner.bound.argtypes=[ctypes.c_uint]
        with self.assertRaises(NativeUIError):owner.compress_bound(64)
        self.assertIn(owner,UNRESOLVED);self.assertFalse(owner.close_host())

    def test_ffi_return_type_change_refuses_before_bound_call(self):
        owner=OriginalChunkCodec();owner.bound.restype=ctypes.c_ubyte
        with self.assertRaises(NativeUIError):owner.compress_bound(64)
        self.assertIn(owner,UNRESOLVED);self.assertFalse(owner.close_host())

    def test_ffi_error_callback_is_never_executed(self):
        owner=OriginalChunkCodec();calls=[]
        owner.bound.errcheck=lambda *args:calls.append(args) or 0
        with self.assertRaises(NativeUIError):owner.compress_bound(64)
        self.assertFalse(calls);self.assertIn(owner,UNRESOLVED);self.assertFalse(owner.close_host())

    def test_foreign_equal_descriptor_refuses_before_callbacks_and_close(self):
        owner=OriginalChunkCodec();calls=[]
        with tempfile.TemporaryDirectory(prefix='loaded-codec-foreign-') as directory:
            path=Path(directory)/'foreign';path.write_bytes(b'actual independently owned fixture bytes')
            descriptor=os.open(path,os.O_RDONLY|os.O_CLOEXEC)
            class Foreign:
                fd=descriptor
                def __eq__(self,_other):calls.append('equality');return True
                def require(self,*args):calls.append('require');raise AssertionError('Foreign holder')
                def close(self):calls.append('close');return True
            try:
                original=os.fstat(descriptor);owner.files[0][1]=Foreign()
                with self.assertRaises(NativeUIError):owner.compress_bound(64)
                self.assertFalse(owner.close_host());self.assertFalse(calls);self.assertEqual(original,os.fstat(descriptor))
            finally:os.close(descriptor) # Only the independently opened fixture FD.
        self.assertIn(owner,UNRESOLVED)

    def test_constructor_failure_after_actual_open_retains_owner_after_traceback_gc(self):
        original=OriginalDescriptor.__init__;opened=[]
        def fail_after_open(owner,*args,**options):
            original(owner,*args,**options);opened.append(owner.fd)
            raise OSError('Actual descriptor opened before constructor response loss')
        with patch.object(OriginalDescriptor,'__init__',fail_after_open):
            try:OriginalChunkCodec()
            except OSError:pass
            else:self.fail('Expected the actual opened constructor failure')
        gc.collect();self.assertEqual(1,len(opened));owner=UNRESOLVED[-1]
        self.assertIs(type(owner.files[0][1]),OriginalDescriptor)
        self.assertEqual(opened[0],owner.files[0][1].fd);owner.files[0][1].require(opened[0])
        self.assertFalse(owner.close_host());self.assertIsNotNone(os.fstat(opened[0]))

    def test_nested_metadata_type_alias_is_not_canonical_admission(self):
        owner=OriginalChunkCodec();owner._public['files']=tuple(owner._public['files'])
        with self.assertRaises(NativeUIError):owner.compress_bound(64)
        self.assertIn(owner,UNRESOLVED);self.assertGreater(owner.metadata_bytes(),0);self.assertFalse(owner.close_host())


if __name__=='__main__':unittest.main()
