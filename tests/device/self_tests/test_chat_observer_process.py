"""Actual owned stdin workers/kernel probes; no product Actor or device runs."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import os
from pathlib import Path
import select
import subprocess
import sys
import tempfile
import unittest
import uuid
from unittest.mock import patch

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from fixture import chat_observer_process as module
from fixture.chat_observer_process import LinuxChatObserverProcess


class ChatObserverProcessTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.root.chmod(0o700)
        self.entry=self.root/'original-observer.py'
        self.entry.write_text("import sys\nprint('ready',flush=True)\nsys.stdin.readline()\n");self.entry.chmod(0o600)
        self.config=PrivateFeatureState(self.root/'actor.json');self.config.write(dict(explicitStdinFixture=True),None)
        self.token=uuid.uuid4().hex
        self.worker=subprocess.Popen([sys.executable,str(self.entry),'--config',str(self.config.path)],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            env={'PYTHONDONTWRITEBYTECODE':'1','OVT_CHAT_OBSERVER_TEST_OWNER':self.token})
        self.addCleanup(self.finish)
        self.assertTrue(select.select([self.worker.stdout],[],[],5)[0]);self.assertEqual(b'ready\n',self.worker.stdout.readline())
        fields=(Path('/proc')/str(self.worker.pid)/'stat').read_text().rsplit(')',1)[1].split()
        self.identity=str(self.worker.pid)+':'+fields[19]+':'+Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        self.executable_sha=hashlib.sha256(Path(f'/proc/{self.worker.pid}/exe').read_bytes()).hexdigest()
        self.entry_sha=hashlib.sha256(self.entry.read_bytes()).hexdigest()

    def finish(self):
        if self.worker.stdin is not None and not self.worker.stdin.closed:self.worker.stdin.close()
        self.worker.wait(timeout=5)
        for stream in (self.worker.stdout,self.worker.stderr):
            if stream is not None:stream.close()

    def owned(self,pid):
        try:
            root=Path('/proc')/str(pid)
            with (root/'environ').open('rb') as stream:raw=stream.read(65537)
            return len(raw)<=65536 and root.stat().st_uid==os.geteuid() and raw.split(b'\0').count(
                ('OVT_CHAT_OBSERVER_TEST_OWNER='+self.token).encode())==1
        except FileNotFoundError:return False

    def acquire(self):
        owner=LinuxChatObserverProcess(self.identity,self.entry,self.config.path,self.executable_sha,self.entry_sha,self.owned)
        self.addCleanup(owner.close);return owner

    def test_original_live_process_qualifies_and_only_actual_reaped_esrch_proves_absence(self):
        owner=self.acquire();self.assertTrue(owner.guard());self.assertEqual(self.identity,owner.process_identity)
        with self.assertRaises(NativeUIError):owner.require_absent()
        self.worker.stdin.write(b'finish\n');self.worker.stdin.flush();self.worker.wait(timeout=5)
        value=owner.require_absent();self.assertEqual('ESRCH',value['errorSymbol']);self.assertEqual('absent',value['presence'])
        self.assertEqual(self.identity,value['hostProcessIdentity']);self.assertEqual(self.worker.pid,value['queryProcessId'])
        self.assertEqual(self.executable_sha,value['executableSha256']);self.assertFalse(owner.fd_owner.closed)
        self.assertTrue(owner.close());self.assertTrue(owner.entry_owner.closed)

    def test_exited_process_cannot_be_acquired_as_original_live_owner_from_its_old_identity(self):
        self.worker.stdin.write(b'finish\n');self.worker.stdin.flush();self.worker.wait(timeout=5)
        with self.assertRaises(NativeUIError):self.acquire()

    def test_same_bytes_configuration_replacement_does_not_become_original_after_process_exit(self):
        owner=self.acquire();value=self.config.read();self.config.write(value,value)
        with self.assertRaises(NativeUIError):owner.guard()
        self.worker.stdin.write(b'finish\n');self.worker.stdin.flush();self.worker.wait(timeout=5)
        with self.assertRaises(NativeUIError):owner.require_absent()
        self.assertTrue(self.config.path.exists())

    def test_wrong_program_hash_and_wrong_original_start_cannot_qualify_a_live_worker(self):
        with self.assertRaises(NativeUIError):LinuxChatObserverProcess(self.identity,self.entry,self.config.path,
            self.executable_sha,'f'*64,self.owned)
        fields=self.identity.split(':');fields[1]=str(int(fields[1])+1)
        with self.assertRaises(NativeUIError):LinuxChatObserverProcess(':'.join(fields),self.entry,self.config.path,
            self.executable_sha,self.entry_sha,self.owned)
        self.assertIsNone(self.worker.poll())

    def test_exact_reviewed_entry_and_private_configuration_arguments_are_required(self):
        other_entry=self.root/'other-observer.py';other_entry.write_bytes(self.entry.read_bytes());other_entry.chmod(0o600)
        other_config=PrivateFeatureState(self.root/'other-config.json');other_config.write(self.config.read(),None)
        for entry,configuration in ((other_entry,self.config.path),(self.entry,other_config.path)):
            with self.subTest(entry=entry.name,configuration=configuration.name),self.assertRaises(NativeUIError):
                LinuxChatObserverProcess(self.identity,entry,configuration,self.executable_sha,self.entry_sha,self.owned)
        self.assertIsNone(self.worker.poll())

    def test_cached_program_hash_mutation_cannot_change_original_kernel_program_receipt(self):
        owner=self.acquire();owner.sha256='e'*64
        with self.assertRaises(NativeUIError):owner.guard()
        self.worker.stdin.write(b'finish\n');self.worker.stdin.flush();self.worker.wait(timeout=5)
        with self.assertRaises(NativeUIError):owner.require_absent()

    def test_frozen_monotonic_and_final_copy_epoch_jump_cannot_return_a_fresh_absence(self):
        owner=self.acquire();self.worker.stdin.write(b'finish\n');self.worker.stdin.flush();self.worker.wait(timeout=5)
        copied=module.deepcopy;epoch=module.time.time;late=[False]
        def copy(value):
            result=copied(value)
            if type(value) is dict and value.get('sourceRole')=='independent-chat-host-observer':late[0]=True
            return result
        with patch.object(module,'deepcopy',side_effect=copy),patch.object(module.time,'monotonic',return_value=0),\
            patch.object(module.time,'time',side_effect=lambda:epoch()+(2 if late[0] else 0)):
            with self.assertRaises(NativeUIError):owner.require_absent()
        self.assertTrue(late[0]);self.assertEqual('ESRCH',owner.require_absent()['errorSymbol'])


if __name__=='__main__':unittest.main()
