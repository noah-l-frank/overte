"""Actual BG4 gate tests the read-only core; Pending3 remains unqualified."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import ExitStack
from copy import deepcopy
import os
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from adapters.normal_ui import NativeUIError
from adapters.pico4.lifecycle_pending_return import LifecyclePendingReturnPins,UNRESOLVED
from self_tests.test_pico_lifecycle_family_gate import LifecycleFamilyGateTests

LOCK_PROBE="""import fcntl,os,sys
fd=os.open(sys.argv[1],os.O_RDWR|os.O_NOFOLLOW)
try:
 try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);print('free')
 except BlockingIOError:print('busy')
finally:os.close(fd)
"""


class LifecyclePendingReturnPinsTests(unittest.TestCase):
    def setUp(self):
        self.fixture=LifecycleFamilyGateTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.seams=self.fixture.seams;self.raw=self.fixture.bank;self.writer=self.seams.owner
        self.writer.prepare(self.seams.chat);self.gate=self.raw.write_gates['background'];self.pins=None
        def close():
            if self.pins is not None:self.pins.close_host()
        self.addCleanup(close)

    def prepare(self):
        self.pins=LifecyclePendingReturnPins.__new__(LifecyclePendingReturnPins)
        LifecyclePendingReturnPins.__init__(self.pins,self.gate)

    def probe(self):
        result=subprocess.run([sys.executable,'-c',LOCK_PROBE,str(self.seams.lock.path)],
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,timeout=3,check=False)
        self.assertEqual(0,result.returncode,result.stderr);return result.stdout.strip()

    def test_original_data_is_freshly_verified_after_actual_outer_flock_exit_without_reentry_clock_or_sdk(self):
        with self.seams.lock.held():
            self.prepare();self.assertEqual('busy',self.probe())
        self.assertEqual('free',self.probe());self.assertIsNone(self.seams.lock._owner)
        with ExitStack() as no_callbacks:
            for owner,name in ((self.seams.lock,'held'),(self.writer,'monotonic'),(self.raw,'other_bill'),
                    (self.raw.archive,'identity'),(self.raw.archive,'clock')):
                no_callbacks.enter_context(patch.object(owner,name,side_effect=AssertionError('No lock/clock/SDK/bill callback after exit')))
            self.pins.verify_data()
        self.assertEqual('background',self.pins.role);self.assertIs(self.pins.writer,self.writer)
        self.assertTrue(self.pins.close_host());self.assertEqual([],self.seams.inputs)

    def test_mutable_actual_owner_state_or_equal_replaced_disk_cannot_reuse_prepared_data_verdict(self):
        with self.seams.lock.held():self.prepare()
        self.writer.disk=deepcopy(self.writer.disk)
        with self.assertRaises(NativeUIError):self.pins.verify_data()
        self.assertIn(self.pins,UNRESOLVED);self.assertFalse(self.pins.close_host())

    def test_inplace_decoded_state_change_without_any_file_write_refuses_after_exit(self):
        with self.seams.lock.held():self.prepare()
        name=next(iter(self.writer.state['archives']));self.writer.state['archives'][name]='e'*64
        with self.assertRaises(NativeUIError):self.pins.verify_data()
        self.assertFalse(self.pins.close_host());self.assertIn(self.pins,UNRESOLVED)

    def test_same_byte_owner_replacement_cannot_be_adopted(self):
        with self.seams.lock.held():self.prepare()
        path=self.writer.store.path;replacement=path.with_name('replacement-data-root')
        replacement.write_bytes(path.read_bytes());replacement.chmod(0o600);os.replace(replacement,path)
        before=path.read_bytes()
        with self.assertRaises(NativeUIError):self.pins.verify_data()
        self.assertEqual(before,path.read_bytes());self.assertIn(self.pins,UNRESOLVED)

    def test_new_unknown_raw_original_refuses_without_removing_it_or_reentering_lock(self):
        with self.seams.lock.held():self.prepare()
        path=self.raw.path.with_name(self.raw.path.name+'.pending-unknown');path.write_bytes(b'Unknown original retained\n');path.chmod(0o600)
        with patch.object(self.seams.lock,'held',side_effect=AssertionError('No reacquire')),self.assertRaises(NativeUIError):self.pins.verify_data()
        self.assertEqual(b'Unknown original retained\n',path.read_bytes());self.assertIn(self.pins,UNRESOLVED)

    def test_recycled_same_inode_data_fd_is_not_used_or_closed_as_original(self):
        with self.seams.lock.held():self.prepare()
        pin=self.pins._entries[0];descriptor=pin.descriptor;target=descriptor.fd
        os.close(target);foreign=os.open(self.raw.path.parent/pin.name,os.O_RDONLY|os.O_NOFOLLOW)
        if foreign!=target:os.dup2(foreign,target);os.close(foreign);foreign=target
        try:
            self.assertEqual(tuple(pin.physical[:2]),(os.fstat(foreign).st_dev,os.fstat(foreign).st_ino))
            with self.assertRaises(NativeUIError):self.pins.verify_data()
            self.assertFalse(self.pins.close_host())
            self.assertEqual(tuple(pin.physical[:2]),(os.fstat(foreign).st_dev,os.fstat(foreign).st_ino))
            self.assertIn(self.pins,UNRESOLVED)
        finally:
            # Only this fixture owns the replacement; the lost original alias
            # remains strongly retained until the actual owning host exits.
            os.close(foreign)

    def test_unadmitted_parent_namespace_growth_never_inherits_previous_budget(self):
        with self.seams.lock.held():self.prepare()
        marker=self.raw.path.parent/'legitimate-parent-metadata';marker.write_bytes(b'owned outside raw-prefix\n');marker.chmod(0o600)
        # Parent metadata growth must be admitted/staged before true exit; a
        # newly unaccounted name is refused, independently of directoryctime.
        with self.assertRaises(NativeUIError):self.pins.verify_data()
        self.assertEqual(b'owned outside raw-prefix\n',marker.read_bytes())

    def test_preparation_capacity_failure_keeps_partial_holder_and_does_not_open_data_fds(self):
        with self.seams.lock.held(),patch.object(self.raw,'other_bill',return_value={
                'parts':0,'storedBytes':0,'decodedBytes':16*1024*1024,'files':0}),self.assertRaises(NativeUIError):self.prepare()
        self.assertEqual([],self.pins.partial);self.assertIn(self.pins,UNRESOLVED)
        self.assertFalse(self.pins.close_host())

    def test_foreign_storage_gate_alias_cannot_borrow_the_original_data_verifier(self):
        with self.seams.lock.held():self.prepare()
        self.writer.storage_gate=SimpleNamespace(verify_data=lambda:None)
        with self.assertRaises(NativeUIError):self.pins.verify_data()
        self.assertIn(self.pins,UNRESOLVED);self.assertFalse(self.pins.close_host())

    def test_directory_mtime_progress_alone_does_not_change_data_identity_or_authority(self):
        with self.seams.lock.held():self.prepare()
        path=self.raw.path.parent;before=path.stat();os.utime(path,ns=(before.st_atime_ns,before.st_mtime_ns+1000000))
        self.assertEqual(before.st_ino,path.stat().st_ino);self.assertNotEqual(before.st_mtime_ns,path.stat().st_mtime_ns)
        self.pins.verify_data();self.assertTrue(self.pins.close_host())

    def test_actual_missing_data_file_refuses_without_reopening_or_replacement_adoption(self):
        with self.seams.lock.held():self.prepare()
        pin=next(value for value in self.pins._entries if '.part-' in value.name)
        path=self.raw.path.parent/pin.name;renamed=path.with_name('retained-renamed-original-part');os.rename(path,renamed)
        with self.assertRaises(NativeUIError):self.pins.verify_data()
        self.assertFalse(path.exists());self.assertTrue(renamed.exists());self.assertIn(self.pins,UNRESOLVED)

    def test_mutable_numeric_reservation_cannot_undercount_actual_pinned_metadata(self):
        with self.seams.lock.held():self.prepare()
        self.pins.reserve_bytes=0
        with self.assertRaises(NativeUIError):self.pins.metadata_bytes()
        self.assertIn(self.pins,UNRESOLVED);self.assertFalse(self.pins.close_host())
