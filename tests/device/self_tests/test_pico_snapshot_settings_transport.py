"""Exact Source2 read script on owned Host files, PID/start and real clocks.

GNU sh/stat/head run here, without ADB/run-as or an Android app. This qualifies
these real Host shell/file branches, not Android utility/runtime parity.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import time
import unittest

from adapters.normal_ui import NativeUIError
from adapters.pico4.snapshot_settings_transport import READ_SCRIPT,body,HEAD


class SnapshotSettingsShellTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(tempfile.mkdtemp(prefix='snapshot-settings-real-shell-'));self.root.chmod(0o700)
        self.directory=self.root/'files/overte-e2e';self.directory.mkdir(parents=True,mode=0o700);self.directory.chmod(0o700)
        self.path=self.directory/'feature-pico-snapshot-settings-originals.json';self.nonce='f'*32
        self.path.write_bytes(b'actual Host original\x00\xff without UTF8 interpretation');self.path.chmod(0o600)
        self.pid=os.getpid();self.start=Path('/proc',str(self.pid),'stat').read_text().rsplit(') ',1)[1].split()[19]

    def run_script(self,*,start=None,expired=False,environment=None):
        epoch=time.time_ns()//1000000
        command=['sh','-c',READ_SCRIPT,'overte-snapshot-settings2',str(self.pid),self.start if start is None else start,
            str(epoch-2000 if expired else epoch),str(epoch-500 if expired else epoch+1500),self.nonce]
        result=subprocess.run(command,cwd=self.root,env=environment,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=5,check=False)
        raw=self.root/('actual-wire-'+str(len(list(self.root.glob('actual-wire-*'))))+'.bin');raw.write_bytes(result.stdout);raw.chmod(0o600)
        return result

    def test_actual_host_pid_epoch_stat_and_nul_binary_body(self):
        original=self.path.read_bytes();before=self.path.stat();result=self.run_script()
        self.assertEqual(0,result.returncode,result.stderr);self.assertEqual(original,body(result.stdout,self.nonce));self.assertLessEqual(len(result.stdout),69632)
        self.assertEqual(before,self.path.stat());self.assertIn(b'\x00\xff',result.stdout)

    def test_actual_foreign_process_birth_and_expired_real_deadline_emit_no_body(self):
        for options in ({'start':str(int(self.start)+1)},{'expired':True}):
            with self.subTest(options=options):
                result=self.run_script(**options);self.assertNotEqual(0,result.returncode);self.assertEqual(b'',result.stdout)

    def test_symlink_and_actual_one_byte_oversize_cannot_be_accepted(self):
        original=self.directory/'actual-original.bin';self.path.rename(original);self.path.symlink_to(original.name)
        result=self.run_script();self.assertNotEqual(0,result.returncode);self.assertEqual(b'',result.stdout)
        self.path.unlink();self.path.write_bytes(b'x'*65537);self.path.chmod(0o600)
        result=self.run_script();self.assertEqual(0,result.returncode,result.stderr)
        with self.assertRaises(NativeUIError):body(result.stdout,self.nonce)
        self.assertLessEqual(len(result.stdout),69632)

    def test_same_bytes_replacement_after_actual_head_read_loses_original_footer(self):
        utilities=self.root/'fault-utilities';utilities.mkdir(mode=0o700);head=shutil.which('head');self.assertIsNotNone(head)
        wrapper=utilities/'head'
        # Only this task-owned PATH wrapper changes a file AFTER actual head
        # read. The production READ_SCRIPT itself is executed byte unchanged.
        wrapper.write_text('#!/bin/sh\n'+shlex.quote(head)+' "$@" || exit 1\n'
            +'mv '+shlex.quote(str(self.path))+' '+shlex.quote(str(self.path)+'.original')+' || exit 1\n'
            +'cp '+shlex.quote(str(self.path)+'.original')+' '+shlex.quote(str(self.path))+' || exit 1\n'
            +'chmod 600 '+shlex.quote(str(self.path))+'\n');wrapper.chmod(0o700)
        environment=dict(os.environ,PATH=str(utilities)+os.pathsep+os.environ['PATH']);result=self.run_script(environment=environment)
        self.assertNotEqual(0,result.returncode);self.assertTrue(result.stdout.startswith(HEAD))
        self.assertEqual(self.path.read_bytes(),Path(str(self.path)+'.original').read_bytes())
        self.assertNotEqual(self.path.stat().st_ino,Path(str(self.path)+'.original').stat().st_ino)
        with self.assertRaises(NativeUIError):body(result.stdout,self.nonce)


if __name__=='__main__':unittest.main()
