"""Actual fixed shell/file/stdin receipts; Android SDK/run-as remain models.

No ADB, device, service, compiler or product process is invoked. The SDK callback
runs ONLY the transport's fixed shell script in an owned host directory; its
/proc identity, stage bytes, named files and process exit are real.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import time
from types import SimpleNamespace
from unittest.mock import patch
from adb_transport import AdbTransport
import unittest
import uuid

from adapters.assets_input import documents
from adapters.normal_ui import NativeUIError
from adapters.pico4.assets_files import command
from adapters.pico4.assets_transport import PicoAssetsTransport,BODY_LIMIT,AUX_LIMIT,PATH,FILES
from adapters.script_journey.history import canonical
from fixture.messages_mixer import start_identity


class AssetsBinaryTransportTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(tempfile.mkdtemp(prefix='pico-assets-binary-transport-'));self.root.chmod(0o700)
        (self.root/'files/overte-e2e').mkdir(parents=True,mode=0o700)
        self.identity=str(os.getpid())+':'+start_identity(os.getpid())
        self.calls=[];self.retained=[];self.admissions=[];self.after_execute=None;self.ignore=False
        self.adapter=SimpleNamespace(kind='pico',profile={'package':'org.overte.pico'},
            require_same_process=lambda target,identity,operation:self.assertEqual(self.identity,identity))
        self.adapter.adb=SimpleNamespace(execute_bytes=self.execute)
        self.transport=self.make()
        print('Retained actual host shell/bytes originals:',self.root,flush=True)

    def make(self,*,capacity=None,binary=None):
        if binary is not None:self.adapter.adb.execute_bytes=binary
        return PicoAssetsTransport(self.adapter,'declared-host-model',self.identity,lambda:True,
            lambda role,raw:self.retained.append((role,raw)),
            capacity if capacity is not None else lambda *args:self.admissions.append(args),
            lambda:time.time_ns()//1000000)

    def execute(self,args,*,target,timeout,check,input_bytes=None):
        self.calls.append(dict(args=args,target=target,timeout=timeout,check=check,inputBytes=input_bytes))
        parsed=shlex.split(args[1]);self.assertEqual(['run-as','org.overte.pico','sh','-c'],parsed[:4])
        if self.ignore:return b''
        result=subprocess.run(['sh','-c',*parsed[4:]],input=input_bytes,cwd=self.root,
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout,check=False)
        (self.root/f'shell-{len(self.calls):02d}.stderr').write_bytes(result.stderr)
        (self.root/f'shell-{len(self.calls):02d}.stdout').write_bytes(result.stdout)
        self.assertEqual(0,result.returncode,result.stderr)
        raw=result.stdout
        if self.after_execute is not None:raw=self.after_execute(raw)
        return raw

    def stage(self):
        import base64
        return command(dict(schemaVersion=1,commandId=uuid.uuid4().hex,action='feature-pico-assets-files',
            operation='stage',runId='a'*32,ownerToken='b'*64,stage=2,
            files={name:base64.b64encode(raw).decode() for name,raw in documents().items()}))

    def original(self,raw,role='files'):
        path=self.root/'files/overte-e2e'/FILES[role];path.write_bytes(raw);path.chmod(0o600)
        return path

    def test_real_fixed_script_stages_exact37209_bytes_and_confirms_original_process(self):
        value=self.stage();payload=canonical(value)+b'\n';self.assertEqual(37209,len(payload))
        self.transport.stage(value)
        self.assertEqual(payload,(self.root/PATH).read_bytes());self.assertEqual(1,len(self.calls))
        self.assertEqual(payload,self.calls[0]['inputBytes']);self.assertEqual(1,len(self.transport.receipts))
        self.assertEqual(hashlib.sha256(payload).hexdigest(),self.transport.receipts[0]['sha256'])
        self.assertEqual(self.calls[0]['inputBytes'],payload);self.assertEqual('stage-receipt',self.retained[0][0])
        with self.assertRaises(NativeUIError):self.transport.stage(value)
        self.assertEqual(1,len(self.calls))

    def test_invalid_utf8_is_retained_as_actual_bytes_and_never_decoded_by_transport(self):
        raw=b'\xff\x00 actual invalid UTF8';self.original(raw)
        self.assertEqual(raw,self.transport.read('files'));self.assertIn(raw,self.retained[0][1])
        self.assertFalse(self.transport.failed)

    def test_actual_overrun_prefix_and_framing_retained_before_refusal(self):
        raw=b'x'*(BODY_LIMIT+1);self.original(raw)
        with self.assertRaises(NativeUIError):self.transport.read('files')
        wire=self.retained[0][1]
        self.assertIn(raw,wire);self.assertLessEqual(len(wire),BODY_LIMIT+AUX_LIMIT)
        self.assertTrue(self.transport.failed)
        with self.assertRaises(NativeUIError):self.transport.read('files')
        self.assertEqual(1,len(self.calls))

    def test_actual_lost_receipt_keeps_unknown_stage_issued_and_is_never_replayed(self):
        value=self.stage();self.after_execute=lambda raw:b''
        with self.assertRaises(NativeUIError):self.transport.stage(value)
        self.assertEqual(canonical(value)+b'\n',(self.root/PATH).read_bytes())
        self.assertEqual([('stage-receipt',b'')],self.retained);self.assertTrue(self.transport.failed)
        with self.assertRaises(NativeUIError):self.transport.stage(value)
        self.assertEqual(1,len(self.calls));self.assertEqual([],self.transport.receipts)

    def test_original_expired_capacity_prevents_all_sdk_dispatch(self):
        self.original(b'{}');capacity=self.transport.capacity
        def delayed(*args):capacity(*args);time.sleep(1.51)
        self.transport=self.make(capacity=delayed)
        with self.assertRaises(NativeUIError):self.transport.read('files')
        self.assertFalse(self.calls);self.assertFalse(self.retained)

    def test_acquired_late_bytes_durable_before_original_age_failure(self):
        self.original(b'{}')
        def late(raw):time.sleep(1.51);return raw
        self.after_execute=late
        with self.assertRaises(NativeUIError):self.transport.read('files')
        self.assertEqual(1,len(self.retained));self.assertIn(b'{}',self.retained[0][1])
        self.assertTrue(self.transport.failed)

    def test_timeout_partial_binary_is_retained_before_sticky_refusal(self):
        def timeout(*args,**options):
            self.calls.append(options);raise subprocess.TimeoutExpired('declared-SDK',1,output=b'\xff partial')
        self.transport=self.make(binary=timeout)
        with self.assertRaises(subprocess.TimeoutExpired):self.transport.read('files')
        self.assertEqual([('files',b'\xff partial')],self.retained);self.assertTrue(self.transport.failed)

    def test_original_sdk_wrapped_timeout_preserves_actual_binary_partial_before_refusal(self):
        sdk=object.__new__(AdbTransport);sdk.command=['declared-no-execution']
        self.transport=self.make(binary=sdk.execute_bytes)
        error=subprocess.TimeoutExpired('declared-SDK',1,output=b'\xff actual subprocess partial')
        with patch('adb_transport.subprocess.run',side_effect=error) as execute:
            with self.assertRaises(RuntimeError):self.transport.read('files')
            self.assertEqual(1,execute.call_count)
        self.assertEqual([('files',b'\xff actual subprocess partial')],self.retained)
        self.assertTrue(self.transport.failed)

    def test_capacity_callback_reentry_rejected_before_clock_or_sdk(self):
        calls=[];original=self.transport.capacity
        def reenter(*args):
            original(*args)
            with self.assertRaises(NativeUIError):self.transport.read('files')
            calls.append('rejected')
        self.transport=self.make(capacity=reenter)
        self.original(b'{}');self.assertEqual(b'{}',self.transport.read('files'))
        self.assertEqual(['rejected'],calls);self.assertEqual(1,len(self.calls))


if __name__=='__main__':unittest.main()
