"""Actual Session mutex transitions and pre-copy compact metadata admission."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
from pathlib import Path
import unittest
from unittest.mock import patch

from adapters.chat_journey.archive_file import signature
from adapters.normal_ui import NativeUIError
from adapters.pico4.lifecycle_namespace_bill import LifecycleNamespaceBill,canonical_size
from adapters.pico4.lifecycle_background_raw_state import close_or_retain,UNRESOLVED
from adapters.pico4.lifecycle_mutex_ledger import VERSION,WINDOW_BYTES
from adapters.script_journey.history import MAX_RAW
from self_tests import test_pico_lifecycle_background_raw as fixture


class LifecycleMutexLedger2Tests(unittest.TestCase):
    def prepare(self,*,two=False):
        case=fixture.LifecycleBackgroundRawTests();self.addCleanup(case.doCleanups)
        constructor=LifecycleNamespaceBill
        def namespace(*args,**kwargs):return constructor(*args,**kwargs,mutex_layout=2)
        with patch.object(fixture,'LifecycleNamespaceBill',namespace):case.setUp()
        self.fixture=case;self.namespace=case.namespace;self.raw=case.raw;self.lock=case.lock
        self.session=case.actual_session();self.second=None
        if two:
            from self_tests.test_pico_openxr_adapter_session import FakeTransport
            from openxr_input.adapter_session import PicoOpenXrAdapterSession
            self.second=PicoOpenXrAdapterSession(FakeTransport(),'second-admitted-host-mutex',case.root)
            self.second.begin(fixture.BINDING['processIdentity'])
        self.native,self.source=case.source();self.source.capture(fixture.RUN)
        self.ledger=self.namespace._mutex_ledger
        self.assertEqual(0,len(self.namespace.mutex_observations))
        return case

    def transition(self,session=None):
        session=session or self.session
        before=tuple(signature(session.lock_path.lstat()))
        session.require_process_identity(fixture.BINDING['processIdentity'])
        after=tuple(signature(session.lock_path.lstat()))
        self.assertEqual(before[:7],after[:7]);self.assertGreater(after[7],before[7])
        with self.lock.held():self.namespace.guard_lease()
        return session.lock_path.name,before,after

    def test_513_actual_session_fchmod_transitions_reconstruct_all_original_pairs_without_native_query(self):
        self.prepare();actual=[]
        for _ in range(513):actual.append(self.transition())
        self.assertEqual(513,len(self.namespace.mutex_observations))
        for index,pair in enumerate(actual):self.assertEqual(pair,self.namespace.mutex_observations[index])
        self.assertEqual(tuple(actual[-6:]),self.namespace.mutex_observations[-6:])
        cohorts,order,size=self.ledger.state
        self.assertEqual(1,len(cohorts));self.assertEqual(514,len(cohorts[0][2]));self.assertEqual(513,len(order))
        dto=dict(lifecycleMutexLedgerVersion=VERSION,cohorts=[dict(name=name,prefix=list(prefix),ctimes=list(times))
            for name,prefix,times in cohorts],order=[list(row) for row in order])
        self.assertEqual(canonical_size(dto),size)
        self.assertEqual(size+WINDOW_BYTES,self.namespace.metadata_bytes())
        legacy=2+sum(canonical_size(dict(name=name,before=list(before),after=list(after))) for name,before,after in actual)+len(actual)-1
        self.assertLess(size,legacy//3)
        with self.lock.held():bill=self.namespace()
        self.assertLess(bill['decodedBytes']+self.raw.metadata_capacity(),MAX_RAW)
        self.assertEqual(1,len(self.native.commands));self.assertEqual(1,self.raw.archive.bill()['receipts'])
        self.assertEqual([],self.raw.archive.state['pending']);self.assertFalse(self.ledger.poisoned)

    def test_two_actual_admitted_mutexes_preserve_global_interleaving_and_complete_prefixes(self):
        self.prepare(two=True)
        actual=[self.transition(session) for session in (self.session,self.second,self.session,self.second,self.second,self.session)]
        self.assertEqual(tuple(actual),self.namespace.mutex_observations[:6])
        self.assertEqual(2,len(self.ledger.state[0]));self.assertEqual(6,len(self.ledger.state[1]))
        self.assertEqual(1,len(self.native.commands));self.assertEqual(1,self.raw.archive.bill()['receipts'])

    def test_bounded_view_rejects_unadmitted_whole_list_or_large_reconstruction_window(self):
        self.prepare()
        for _ in range(7):self.transition()
        with self.assertRaises(NativeUIError):self.namespace.mutex_observations[:]
        with self.assertRaises(TypeError):list(self.namespace.mutex_observations)
        self.assertEqual(6,len(self.namespace.mutex_observations[-6:]))
        self.assertEqual(1,len(self.native.commands));self.assertFalse(self.ledger.poisoned)

    def test_actual_foreign_node_mode_size_mtime_and_other_root_stay_pinned(self):
        for fault in ('inode','mode','bytes','mtime','other-root'):
            with self.subTest(fault=fault):
                other=LifecycleMutexLedger2Tests();other.prepare();self.addCleanup(other.doCleanups)
                path=other.session.lock_path
                if fault=='inode':
                    changed=path.with_name('same-byte-new-node');changed.write_bytes(b'');changed.chmod(0o600);os.replace(changed,path)
                elif fault=='mode':path.chmod(0o400)
                elif fault=='bytes':path.write_bytes(b'x')
                elif fault=='mtime':
                    info=path.stat();os.utime(path,ns=(info.st_atime_ns,info.st_mtime_ns+1))
                else:
                    path=other.session.state_path;raw=path.read_bytes();changed=path.with_name('other-root-node')
                    changed.write_bytes(raw);changed.chmod(0o600);os.replace(changed,path)
                before=other.ledger.state
                with other.lock.held(),self.assertRaises(NativeUIError):other.namespace.guard_lease()
                self.assertIs(before,other.ledger.state)
                with self.assertRaises(NativeUIError):other.source.capture(fixture.RUN)
                self.assertEqual(1,len(other.native.commands))

    def test_same_node_same_mode_aba_is_only_observed_metadata_and_cannot_authorize_dead_source(self):
        self.prepare();path=self.session.lock_path;before=tuple(signature(path.lstat()))
        path.chmod(0o400);path.chmod(0o600);after=tuple(signature(path.lstat()))
        with self.lock.held():self.namespace.guard_lease()
        self.assertEqual((path.name,before,after),self.namespace.mutex_observations[-1])
        self.native.alive=False
        with self.assertRaises(NativeUIError):self.source.capture(fixture.RUN)
        self.assertEqual(1,len(self.native.commands))

    def test_actual_durable_reservations_exhaust_byte_budget_before_chain_copy_and_keep_failed_pair(self):
        self.prepare();archive=self.raw.archive;maximum_side=2*(11*48000*2*2+44)
        with self.lock.held():
            while True:
                current=self.raw.other_bill();ours=archive.bill();reserved=sum(row['limit']+row['sideBytes'] for row in archive.state['pending'])
                available=MAX_RAW-current['decodedBytes']-ours['decodedBytes']-reserved-1-3*65536
                if available<=maximum_side+4096:
                    archive.reserve('ui',dict(storageCounter='pending-byte-responsibility'),1,side_bytes=available-4096);break
                archive.reserve('ui',dict(storageCounter='pending-byte-responsibility'),1,side_bytes=maximum_side)
        self.assertTrue(archive.state['pending']);failed=False
        for _ in range(128):
            old=self.ledger.state;before=tuple(signature(self.session.lock_path.lstat()))
            self.session.require_process_identity(fixture.BINDING['processIdentity'])
            after=tuple(signature(self.session.lock_path.lstat()))
            try:
                with self.lock.held():self.namespace.guard_lease()
            except NativeUIError:
                failed=True;self.assertIs(old,self.ledger.state)
                self.assertEqual((self.session.lock_path.name,before,after),self.ledger.pending.pair)
                break
        self.assertTrue(failed);self.assertTrue(self.ledger.poisoned)
        pending=deepcopy(archive.state['pending']);close_or_retain(self.fixture.root,self.namespace)
        self.assertTrue(any(path==self.fixture.root and owner is self.namespace for path,owner in UNRESOLVED))
        self.assertEqual(pending,archive.state['pending'])
        with self.assertRaises(NativeUIError):self.source.capture(fixture.RUN)
        self.assertEqual(1,len(self.native.commands));self.assertEqual(1,archive.bill()['receipts'])

    def test_replaced_cached_cost_or_observation_view_refuses_without_next_source_query(self):
        for fault in ('cost','view','layout'):
            with self.subTest(fault=fault):
                other=LifecycleMutexLedger2Tests();other.prepare();self.addCleanup(other.doCleanups);other.transition()
                original=other.ledger.state
                if fault=='cost':other.ledger.state=(original[0],original[1],0)
                elif fault=='view':other.namespace.mutex_observations=()
                else:other.namespace.mutex_layout=1
                with self.assertRaises(NativeUIError):other.namespace.metadata_bytes()
                with self.assertRaises(NativeUIError):other.source.capture(fixture.RUN)
                self.assertEqual(1,len(other.native.commands));self.assertIs(original,other.ledger._state)
                close_or_retain(other.fixture.root,other.namespace)
                self.assertTrue(any(path==other.fixture.root and owner is other.namespace for path,owner in UNRESOLVED))

    def test_original_capacity_callback_cannot_reenter_commit_before_actual_budget_admission(self):
        from tempfile import TemporaryDirectory
        from adapters.script_journey.lock import ScriptSourceLock
        from self_tests.test_pico_openxr_adapter_session import FakeTransport
        from openxr_input.adapter_session import PicoOpenXrAdapterSession
        directory=TemporaryDirectory();self.addCleanup(directory.cleanup)
        root=Path(directory.name);root.chmod(0o700);lock=ScriptSourceLock(root/'script-sources.lock')
        namespace=LifecycleNamespaceBill(root,lock,mutex_layout=2);self.addCleanup(namespace.close)
        session=PicoOpenXrAdapterSession(FakeTransport(),'original-callback-reentry',root)
        session.begin(fixture.BINDING['processIdentity']);reenter=[False]
        def admitted_original_callback():
            if reenter[0]:namespace._mutex_ledger.commit(namespace._mutex_ledger.pending)
            return 0
        namespace.bind_raw_capacity(admitted_original_callback)
        with lock.held():namespace()
        original=namespace._mutex_ledger.state;before=tuple(signature(session.lock_path.lstat()))
        session.require_process_identity(fixture.BINDING['processIdentity']);after=tuple(signature(session.lock_path.lstat()))
        reenter[0]=True
        with lock.held(),self.assertRaises(NativeUIError):namespace.guard_lease()
        ledger=namespace._mutex_ledger
        self.assertIs(original,ledger.state);self.assertEqual((session.lock_path.name,before,after),ledger.pending.pair)
        self.assertTrue(ledger.poisoned);self.assertIsNone(ledger._admitted_permit);self.assertFalse(namespace.close())

    def test_failed_actual_ledger_constructor_retains_partial_namespace_and_exact_directory_owner(self):
        from tempfile import TemporaryDirectory
        from adapters.script_journey.lock import ScriptSourceLock
        from adapters.pico4.lifecycle_mutex_ledger import LifecycleMutexLedger2
        from adapters.pico4.lifecycle_background_raw_state import retained_path
        directory=TemporaryDirectory();self.addCleanup(directory.cleanup)
        root=Path(directory.name);root.chmod(0o700);lock=ScriptSourceLock(root/'script-sources.lock');created=[]
        failure=OSError('Explicit failure after actual original directory acquisition')
        def failed(ledger,owner):
            created.append((ledger,owner));owner.directory.require(owner.directory.fd);raise failure
        with patch.object(LifecycleMutexLedger2,'__init__',failed),self.assertRaises(OSError) as raised:
            LifecycleNamespaceBill(root,lock,mutex_layout=2)
        self.assertIs(failure,raised.exception);self.assertEqual(1,len(created))
        ledger,owner=created[0]
        self.assertIs(ledger,owner._mutex_ledger);self.assertIs(ledger,owner._original_mutex_ledger)
        self.assertTrue(owner.directory.closed);self.assertFalse(owner.directory.lost)
        self.assertEqual((-1,-1),(owner.directory.fd,owner.directory.anchor))
        self.assertTrue(any(path==root and original is owner for path,original in UNRESOLVED))
        self.assertTrue(retained_path(root));self.assertEqual([],list(root.iterdir()))

    def test_layout_aliases_refuse_before_opening_any_original_directory(self):
        for value in (True,False,0,3,2.0,'2',None):
            with self.subTest(value=value),patch('adapters.pico4.lifecycle_namespace_bill.OriginalDescriptor') as owner,\
                    self.assertRaises(NativeUIError):LifecycleNamespaceBill(Path('/unused'),None,mutex_layout=value)
            owner.assert_not_called()


if __name__=='__main__':unittest.main()
