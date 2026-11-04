"""Proposed actual close/number-reuse counters; no target resource authority."""
import os,sys,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import patch
from adapters.native_fd_owner import OriginalDescriptor
from adapters.normal_ui import NativeUIError
from adapters.pico4 import lifecycle_descriptor_close as module

RETAINED_ORIGINALS=[]


class LifecycleDescriptorCloseTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'original';self.path.write_bytes(b'owned original')
        self.path.chmod(0o600);self.owner=OriginalDescriptor(self.path,os.O_RDONLY|os.O_CLOEXEC)
        self.proof=module.pin()
        def close():
            if not self.owner.close():RETAINED_ORIGINALS.append(self.owner)
        self.addCleanup(close)

    def test_actual_thread_reuses_closed_numeric_slot_before_caller_resumes_and_foreign_pipe_remains_usable(self):
        owner=self.owner;fd,anchor=owner.fd,owner.anchor;closed=threading.Event();reused=threading.Event();pipes=[];errors=[]
        def worker():
            try:
                if not closed.wait(2):raise AssertionError('Actual original close never returned')
                read,write=os.pipe()
                if read!=fd:os.dup2(read,fd);os.close(read);read=fd
                pipes.extend((read,write));reused.set()
            except BaseException as error:errors.append(str(error));reused.set()
        thread=threading.Thread(target=worker,name='actual-fd-number-reuse');thread.start()
        original=sys.getprofile()
        def profile(frame,event,arg):
            if event=='return' and frame.f_code is self.proof[1] and frame.f_locals.get('self') is owner and arg is True:
                closed.set();self.assertTrue(reused.wait(2))
        sys.setprofile(profile)
        try:receipt=module.close_original(owner,self.proof)
        finally:sys.setprofile(original);closed.set();thread.join(2)
        try:
            self.assertFalse(thread.is_alive());self.assertEqual([],errors);self.assertEqual((owner,fd,anchor,owner.node),receipt)
            self.assertEqual(fd,pipes[0]);os.fstat(pipes[0]);os.write(pipes[1],b'x');self.assertEqual(b'x',os.read(pipes[0],1))
            self.assertTrue(owner.closed);self.assertFalse(owner.lost)
        finally:
            for number in pipes:os.close(number)

    def test_fake_close_replacement_is_refused_before_call_or_any_original_pair_release(self):
        with patch.object(OriginalDescriptor,'close',return_value=True) as fake:
            with self.assertRaises(NativeUIError):module.close_original(self.owner,self.proof)
            fake.assert_not_called()
        self.owner.require(self.owner.fd);self.assertFalse(self.owner.closed)

    def test_foreign_require_binding_is_refused_without_invoking_it(self):
        calls=[];self.owner.require=lambda *_args:calls.append(True)
        try:
            with self.assertRaises(NativeUIError):module.close_original(self.owner,self.proof)
            self.assertEqual([],calls);self.proof[2](self.owner,self.owner.fd)
        finally:del self.owner.require

    def test_false_preclosed_flag_cannot_take_original_close_fast_path(self):
        self.owner.closed=True
        try:
            with self.assertRaises(NativeUIError):module.close_original(self.owner,self.proof)
            os.fstat(self.owner.fd);os.fstat(self.owner.anchor)
        finally:self.owner.closed=False

    def test_replaced_os_close_cannot_manufacture_successful_syscall_observation(self):
        with patch.object(module.os,'close',return_value=None) as fake:
            with self.assertRaises(NativeUIError):module.close_original(self.owner,self.proof)
            fake.assert_not_called()
        self.owner.require(self.owner.fd)

    def test_preclose_same_inode_foreign_description_is_never_closed_as_original(self):
        target=self.owner.fd;os.close(target);foreign=os.open(self.path,os.O_RDONLY)
        if foreign!=target:os.dup2(foreign,target);os.close(foreign);foreign=target
        try:
            with self.assertRaises(NativeUIError):module.close_original(self.owner,self.proof)
            self.assertTrue(self.owner.lost);self.assertEqual(b'owned original',os.pread(foreign,64,0))
        finally:os.close(foreign)

    def test_foreign_callable_getattr_is_not_executed_as_a_method_guard(self):
        calls=[]
        class Foreign:
            def __getattr__(self,name):calls.append(name);raise AssertionError('No foreign getter')
        self.owner.close=Foreign()
        try:
            with self.assertRaises(NativeUIError):module.close_original(self.owner,self.proof)
            self.assertEqual([],calls);self.proof[2](self.owner,self.owner.fd)
        finally:del self.owner.close

    def test_foreign_class_descriptor_is_not_bound_before_raw_identity_refusal(self):
        calls=[]
        class Foreign:
            def __get__(self,instance,owner):calls.append(True);raise AssertionError('No foreign descriptor')
        with patch.object(OriginalDescriptor,'close',Foreign()):
            with self.assertRaises(NativeUIError):module.close_original(self.owner,self.proof)
            self.assertEqual([],calls)
        self.owner.require(self.owner.fd)
