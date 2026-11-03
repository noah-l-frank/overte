"""Actual owned Python process and kernel OFDs, no native/Runner attestation."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import uuid

from adapters.native_fd_owner import OriginalDescriptor
from adapters.normal_ui import NativeUIError
from adapters.pico4.browser_common_process import OriginalBrowserRunnerProcess,UNRESOLVED


class BrowserCommonProcessTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.path=Path(temporary.name);self.path.chmod(0o700)
        self.entry=self.path/'declared-source-worker.py'
        self.entry.write_text("import sys\nprint('ready',flush=True)\nfor line in sys.stdin:\n if line.strip()=='stop':break\n")
        self.entry.chmod(0o600);self.marker=uuid.uuid4().hex
        self.worker=subprocess.Popen([sys.executable,str(self.entry),'--area','tablet-web'],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,
            env={'PYTHONDONTWRITEBYTECODE':'1','OVT_COMMON_SOURCE_OWNER':self.marker})
        self.addCleanup(self.stop);self.assertEqual('ready',self.worker.stdout.readline().strip())
        fields=(Path('/proc')/str(self.worker.pid)/'stat').read_text().rsplit(')',1)[1].split()
        self.identity=str(self.worker.pid)+':'+fields[19]+':'+Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        self.exe=hashlib.sha256(Path(f'/proc/{self.worker.pid}/exe').read_bytes()).hexdigest()
        self.entry_sha=hashlib.sha256(self.entry.read_bytes()).hexdigest()
        self.owner=None;self.expected_close=True
    def stop(self):
        if self.worker.poll() is None:
            self.worker.stdin.write('stop\n');self.worker.stdin.flush()
        self.worker.wait(timeout=5);self.assertEqual(0,self.worker.returncode)
        for stream in (self.worker.stdin,self.worker.stdout,self.worker.stderr):stream.close()
    def owned(self,pid):
        try:raw=(Path('/proc')/str(pid)/'environ').read_bytes()
        except FileNotFoundError:return False
        return pid==self.worker.pid and raw.split(b'\0').count(('OVT_COMMON_SOURCE_OWNER='+self.marker).encode())==1
    def admit(self):
        self.owner=OriginalBrowserRunnerProcess(self.identity,self.entry,self.path,self.exe,self.entry_sha,self.owned)
        self.addCleanup(lambda:self.assertEqual(self.expected_close,self.owner.close()))
        self.addCleanup(lambda:UNRESOLVED.__setitem__(slice(None),[o for o in UNRESOLVED if o is not self.owner]))
        return self.owner
    def test_exact_live_kernel_process_entry_and_program_retain_their_original_pairs(self):
        owner=self.admit();self.assertTrue(owner.guard())
        self.assertEqual(self.identity,owner.process_identity)
        self.assertIs(owner.fd_owner,owner.original_executable_owner)
        owner.fd_owner.require(owner.fd);owner.entry_owner.require(owner.entry_owner.fd)
        self.assertTrue(owner.close());self.assertTrue(owner.entry_owner.closed)
    def test_changed_entry_same_bytes_new_inode_cannot_become_original_program(self):
        owner=self.admit();replacement=self.path/'replacement.py'
        replacement.write_bytes(self.entry.read_bytes());replacement.chmod(0o600);replacement.replace(self.entry)
        with self.assertRaises(NativeUIError):owner.guard()
    def test_original_process_exit_is_unavailable_not_a_live_exporter(self):
        owner=self.admit();self.stop()
        with self.assertRaises((NativeUIError,FileNotFoundError)):owner.guard()
    def test_same_inode_recycled_entry_half_is_never_force_closed(self):
        owner=self.admit();entry=owner.entry_owner;fd=entry.fd
        os.close(fd);foreign=os.open(self.entry,os.O_RDONLY);self.assertEqual(fd,foreign)
        try:
            with self.assertRaises(NativeUIError):owner.guard()
            self.expected_close=False;self.assertFalse(owner.close())
            self.assertEqual(self.entry.stat().st_ino,os.fstat(foreign).st_ino)
        finally:
            os.close(foreign);os.close(entry.anchor)
    def test_foreign_holder_replacement_does_not_close_either_original_or_foreign_owner(self):
        owner=self.admit();original=owner.entry_owner
        foreign=OriginalDescriptor(self.entry,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
        owner.entry_owner=foreign;self.expected_close=False
        try:
            self.assertFalse(owner.close());self.assertTrue(owner.lost)
            original.require(original.fd);foreign.require(foreign.fd)
            self.assertFalse(original.closed);self.assertFalse(foreign.closed)
        finally:
            self.assertTrue(foreign.close());self.assertTrue(original.close())
            self.assertTrue(owner.original_executable_owner.close())
            owner.fd=-1


if __name__=='__main__':unittest.main()
