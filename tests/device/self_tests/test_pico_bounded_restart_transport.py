"""Original Pico restart transport with real bounded host PS-output workers.

Android process/SDK effects remain the existing declared boundary. No ADB runs.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from adapters.bounded_process_original import BoundedProcessOriginal
from adapters.normal_ui import NativeUIError
from adapters.pico4.chat_restart_io import PicoChatRestartIO
from self_tests.test_pico_chat_restart_io import RestartBoundary


class BoundedRestartTransportTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='pico-bounded-restart-original-')
        self.temp._finalizer.detach();self.root=Path(self.temp.name);self.root.chmod(0o700)
        print('Retained bounded restart originals:',self.root,flush=True)
        self.boundary=RestartBoundary(self.root);self.captures=[];self.raws=[]
        self.boundary.command=[sys.executable,'-c',"print('PID')"]
        self.io=PicoChatRestartIO(self.boundary,self.boundary.target,self.boundary.binding(),
            monotonic=time.monotonic,process_acquire=self.acquire)
        self.addCleanup(self.io.close_host)

    def retain(self,owner):
        index=len(self.raws)
        data=dict(boundedProcessOriginalVersion=1,
            stdoutHex=bytes(owner.buffers['stdout']).hex(),stderrHex=bytes(owner.buffers['stderr']).hex(),
            eof=dict(owner.eof),overflow=owner.overflow,nativeReturnCode=owner.returncode,
            childPid=None if owner.process is None else owner.process.pid,
            knownHostClose=owner.closed,
            acquisitionError=None if owner.failure is None else type(owner.failure[0]).__name__)
        raw=json.dumps(data,sort_keys=True,separators=(',',':')).encode()+b'\n'
        path=self.root/('owned-ps-original-'+str(index)+'.json')
        descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(descriptor,'wb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
        self.raws.append((path,hashlib.sha256(raw).hexdigest()))

    def acquire(self,argv,*,timeout):
        owner=BoundedProcessOriginal();self.captures.append(owner)
        return owner.capture(argv,timeout=timeout,retain=self.retain)

    def shells(self):return [row for row in self.boundary.trace if type(row) is tuple and row[0]=='shell']

    def test_actual_stop_ps_launch_keeps_original_cursor_and_each_literal(self):
        original=self.boundary.session.state_path.read_bytes()
        self.io.stop(lambda:None)
        self.assertEqual(dict(running=False,identity=None),self.io.stopped())
        self.io.launch(lambda:None)
        self.assertEqual(2,len(self.shells()));self.assertEqual('789:999',self.boundary.identity)
        self.assertEqual(original,self.boundary.session.state_path.read_bytes())
        self.assertEqual(2,len(self.captures));self.assertEqual(2,len(self.raws))
        for owner,(path,sha) in zip(self.captures,self.raws):
            self.assertEqual(b'PID\n',owner.result.stdout);self.assertTrue(owner.closed)
            self.assertEqual(sha,hashlib.sha256(path.read_bytes()).hexdigest())
            self.assertEqual(0,owner.process.returncode)

    def test_ignored_stop_and_declared_empty_ps_cannot_bypass_actual_process_state(self):
        self.boundary.effect=False;self.io.stop(lambda:None)
        with self.assertRaises(NativeUIError):self.io.launch(lambda:None)
        self.assertTrue(self.boundary.running);self.assertEqual(1,len(self.shells()))
        self.assertEqual(1,len(self.captures));self.assertEqual(b'PID\n',self.captures[0].result.stdout)

    def test_invalid_original_pid_reply_is_durable_and_cannot_launch(self):
        self.boundary.command=[sys.executable,'-c',"print('PID\\n999')"]
        self.io.stop(lambda:None)
        with self.assertRaises(NativeUIError):self.io.launch(lambda:None)
        self.assertEqual(1,len(self.shells()));self.assertEqual(1,len(self.raws))
        self.assertEqual(b'PID\n999\n',self.captures[0].result.stdout)
        self.assertFalse(self.boundary.running)

    def test_changed_cold_acquirer_prevents_ps_and_launch_without_cursor_repair(self):
        original=self.boundary.session.state_path.read_bytes();self.io.stop(lambda:None)
        self.io.process_acquire=None
        with self.assertRaises(NativeUIError):self.io.launch(lambda:None)
        self.assertEqual([],self.captures);self.assertEqual([],self.raws)
        self.assertEqual(1,len(self.shells()));self.assertEqual(original,self.boundary.session.state_path.read_bytes())


if __name__=='__main__':unittest.main()
