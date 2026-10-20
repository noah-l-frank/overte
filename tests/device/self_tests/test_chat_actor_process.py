"""Host-only kernel checks against a temporary synthetic Python worker."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.chat_actor_files import node
from adapters.normal_ui import NativeUIError
from fixture.chat_actor_process import LinuxChatActorProcess
from fixture.owned_processes import OwnedProcesses

WORKER='''
import json,os,sys
from pathlib import Path
root=Path(sys.argv[sys.argv.index('--e2eChatActorDir')+1])
fd=os.open(root/'held',os.O_RDWR|os.O_CREAT|os.O_EXCL,0o600)
v=os.fstat(fd)
print(json.dumps(dict(device=str(v.st_dev),inode=str(v.st_ino))),flush=True)
sys.stdin.readline()
os.close(fd)
print('closed',flush=True)
sys.stdin.readline()
'''


@unittest.skipUnless(sys.platform.startswith('linux'),'Linux actor-host kernel contract')
class ActorProcessTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'actor';self.root.mkdir(mode=0o700)
        environment=os.environ.copy();environment['XDG_CONFIG_HOME']=self.temp.name
        self.owner=OwnedProcesses(environment);self.enabled=True
        self.worker=subprocess.Popen([sys.executable,'-c',WORKER,'--testScript','--e2eChatActorDir',str(self.root)],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=environment)
        self.addCleanup(self.stop);self.original=json.loads(self.worker.stdout.readline())
        self.sha=hashlib.sha256(Path(f'/proc/{self.worker.pid}/exe').read_bytes()).hexdigest()
        self.guard=LinuxChatActorProcess(self.worker.pid,self.root,self.sha,self.owned);self.addCleanup(self.guard.close)
    def owned(self,pid):return self.enabled and self.owner.matches(pid)
    def stop(self):
        if self.worker.poll() is None:self.worker.terminate()
        self.worker.wait(timeout=3)
        for stream in (self.worker.stdin,self.worker.stdout,self.worker.stderr):stream.close()

    def test_actual_executable_owner_pid_start_and_private_path_are_bound(self):
        self.assertTrue(self.guard.guard());self.assertTrue(self.guard.process_identity.startswith(f'{self.worker.pid}:'))
        self.assertEqual(node(Path(f'/proc/{self.worker.pid}/exe').stat()),node(os.fstat(self.guard.fd)))
        self.assertEqual(self.sha,self.guard.sha256)

    def test_unlinked_original_is_not_released_until_actual_kernel_fd_closes(self):
        self.assertFalse(self.guard.released(self.original));(self.root/'held').unlink()
        self.assertFalse(self.guard.released(self.original))
        self.worker.stdin.write('close\n');self.worker.stdin.flush();self.assertEqual('closed',self.worker.stdout.readline().strip())
        self.assertTrue(self.guard.released(self.original))

    def test_expected_digest_is_not_measured_executable_identity(self):
        with self.assertRaises(NativeUIError):LinuxChatActorProcess(self.worker.pid,self.root,'f'*64,self.owned)
        self.assertTrue(self.guard.guard())

    def test_changed_start_or_lost_ownership_refuses_even_if_process_is_alive(self):
        original=self.guard.start;self.guard.start=str(int(original)+1)
        with self.assertRaises(NativeUIError):self.guard.guard()
        self.guard.start=original;self.enabled=False
        with self.assertRaises(NativeUIError):self.guard.released(self.original)
        self.assertIsNone(self.worker.poll())

    def test_shared_or_replaced_root_is_not_original_actor_directory(self):
        self.root.chmod(0o755)
        with self.assertRaises(NativeUIError):self.guard.guard()
        self.root.chmod(0o700);self.root.rename(self.root.with_name('old'));self.root.mkdir(mode=0o700)
        with self.assertRaises(NativeUIError):self.guard.guard()

    def test_exited_process_does_not_become_successfully_released(self):
        self.worker.terminate();self.worker.wait(timeout=3)
        with self.assertRaises(NativeUIError):self.guard.released(self.original)

    def test_foreign_owner_and_other_directory_cannot_be_qualified(self):
        with self.assertRaises(NativeUIError):LinuxChatActorProcess(self.worker.pid,self.root,self.sha,lambda _:False)
        other=self.root.with_name('other');other.mkdir(mode=0o700)
        with self.assertRaises(NativeUIError):LinuxChatActorProcess(self.worker.pid,other,self.sha,self.owned)


if __name__=='__main__':unittest.main()
