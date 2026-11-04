"""Actual owned host pipes; the child is a Python SDK-output fixture, never ADB."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import gc
import os
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from adapters.android_process_query import AndroidProcessQuery
from adapters.bounded_process_original import BoundedProcessOriginal
from adapters.normal_ui import NativeUIError


class ProcessOriginalTests(unittest.TestCase):
    def setUp(self):self.owners=[];self.retained=[]

    def collect(self,code,*,timeout=2,retain=None):
        owner=BoundedProcessOriginal();self.owners.append(owner)
        callback=self.retained.append if retain is None else retain
        return owner.capture([sys.executable,'-c',code],timeout=timeout,retain=callback)

    def test_success_has_exact_original_bytes_eof_and_actual_worker_exit(self):
        result=self.collect("import sys;sys.stdout.buffer.write(b'PID\\n31\\n')")
        owner=self.owners[-1]
        self.assertEqual(b'PID\n31\n',result.stdout);self.assertEqual(b'',result.stderr)
        self.assertEqual(0,result.returncode);self.assertEqual(0,owner.process.returncode)
        self.assertEqual({'stdout':True,'stderr':True},owner.eof)
        self.assertIs(owner,self.retained[0]);self.assertTrue(owner.closed)
        self.assertTrue(owner.process.stdout.closed and owner.process.stderr.closed)

    def test_nonzero_and_invalid_stderr_are_retained_before_any_pid_parser(self):
        result=self.collect("import sys;sys.stdout.buffer.write(b'PID\\n');sys.stderr.buffer.write(b'bad');sys.exit(1)")
        self.assertEqual((b'PID\n',b'bad',1),(result.stdout,result.stderr,result.returncode))
        self.assertEqual(b'bad',bytes(self.retained[0].buffers['stderr']))

    def test_exact_128_byte_original_is_allowed_but_129_is_not(self):
        self.assertEqual(128,len(self.collect("import os;os.write(1,b'x'*128)").stdout))
        with self.assertRaises(ValueError):self.collect("import os,time;os.write(1,b'x'*1000000);time.sleep(2)")
        owner=self.owners[-1]
        self.assertEqual('stdout',owner.overflow);self.assertEqual(129,len(owner.buffers['stdout']))
        self.assertIs(owner,self.retained[-1]);self.assertIsNotNone(owner.failure)
        self.assertTrue(owner.closed);self.assertIsNotNone(owner.process.returncode)

    def test_stderr_overflow_is_separately_bounded_and_original_prefix_owned(self):
        with self.assertRaises(ValueError):self.collect("import os;os.write(2,b'e'*1000000)")
        owner=self.owners[-1]
        self.assertEqual('stderr',owner.overflow);self.assertEqual(b'e'*129,bytes(owner.buffers['stderr']))
        self.assertEqual(0,len(owner.buffers['stdout']));self.assertTrue(owner.closed)

    def test_real_timeout_keeps_partial_bytes_error_traceback_and_known_child(self):
        with self.assertRaises(subprocess.TimeoutExpired):
            self.collect("import os,time;os.write(1,b'PID\\n');time.sleep(2)",timeout=.15)
        owner=self.owners[-1];error,traceback=owner.failure
        self.assertIs(type(error),subprocess.TimeoutExpired)
        self.assertIsNotNone(traceback);self.assertEqual(b'PID\n',bytes(owner.buffers['stdout']))
        gc.collect();self.assertIs(error,owner.failure[0]);self.assertIs(traceback,owner.failure[1])
        self.assertTrue(owner.closed);self.assertIsNotNone(owner.process.returncode)

    def test_original_acquisition_error_survives_retention_callback_error(self):
        def failed(_owner):raise RuntimeError('Owned archival callback failure')
        with self.assertRaises(ValueError):
            self.collect("import os;os.write(1,b'x'*129)",retain=failed)
        owner=self.owners[-1]
        self.assertIs(type(owner.failure[0]),ValueError)
        self.assertIs(type(owner.cleanup_failures[-1][0]),RuntimeError)
        self.assertTrue(owner.closed)

    def test_actual_owned_pipe_close_error_precedes_later_retention_error(self):
        owner=None;fault=[False]
        def clock():
            if (owner is not None and owner.process is not None
                    and all(owner.eof.values()) and owner.process.poll() is not None and not fault[0]):
                os.close(owner.process.stdout.fileno())
                fault[0]=True
            return time.monotonic()
        owner=BoundedProcessOriginal(monotonic=clock);self.owners.append(owner)
        def failed(_owner):raise RuntimeError('Later owned archival callback failure')
        with self.assertRaises(OSError):
            owner.capture([sys.executable,'-c',"print('PID')"],timeout=2,retain=failed)
        self.assertTrue(fault[0]);self.assertIs(type(owner.failure[0]),OSError)
        self.assertEqual(9,owner.failure[0].errno)
        self.assertIs(type(owner.cleanup_failures[-1][0]),RuntimeError)
        self.assertEqual(b'PID\n',owner.result.stdout);self.assertEqual(0,owner.process.returncode)
        self.assertFalse(owner.closed)

    def test_successful_acquisition_callback_failure_is_strong_and_no_retry(self):
        def failed(_owner):raise RuntimeError('Owned archival callback failure')
        with self.assertRaises(RuntimeError):self.collect("print('PID')",retain=failed)
        owner=self.owners[-1];before=owner.process
        with self.assertRaises(NativeUIError):
            owner.capture([sys.executable,'-c',"print('PID')"],timeout=1,retain=self.retained.append)
        self.assertIs(before,owner.process);self.assertTrue(owner.closed)
        self.assertIs(type(owner.failure[0]),RuntimeError)


class QueryOriginalTests(unittest.TestCase):
    def setUp(self):self.owners=[];self.retained=[];self.guards=0

    def guard(self):self.guards+=1;return True

    def acquire(self,argv,*,timeout):
        owner=BoundedProcessOriginal();self.owners.append(owner)
        return owner.capture(argv,timeout=timeout,retain=self.retained.append)

    def query(self,code):
        # The original query appends its exact argv, which this Python fixture
        # receives as unused arguments; no real ADB path or executable exists.
        transport=SimpleNamespace(command=[sys.executable,'-c',code])
        return AndroidProcessQuery(transport,'org.overte.pico',self.guard,acquire=self.acquire)

    def test_actual_query_parser_uses_bounded_original_and_existing_present_absent_abi(self):
        yes=self.query("print('PID\\n31')").read('owned-host-fixture',31)
        no=self.query("import sys;print('PID');sys.exit(1)").read('owned-host-fixture',31)
        self.assertEqual([31],yes['processIds']);self.assertEqual([],no['processIds'])
        self.assertEqual(2,len(self.owners));self.assertEqual(2,len(self.retained))
        self.assertTrue(all(owner.closed for owner in self.owners))

    def test_invalid_pid_original_is_retained_and_parser_error_cannot_mean_absence(self):
        with self.assertRaises(NativeUIError):self.query("print('PID\\n32')").read('owned-host-fixture',31)
        self.assertEqual(b'PID\n32\n',self.retained[0].result.stdout)
        self.assertIsNotNone(self.owners[0].result);self.assertEqual(0,self.owners[0].returncode)

    def test_mutated_selected_acquirer_refuses_before_first_child(self):
        query=self.query("print('PID')");query.acquire=None
        with self.assertRaises(NativeUIError):query.read('owned-host-fixture',31)
        self.assertEqual([],self.owners);self.assertEqual([],self.retained)


if __name__=='__main__':unittest.main()
