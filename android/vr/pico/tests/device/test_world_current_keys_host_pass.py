"""Actual host/OFD staging windows; no Native/SDK/current-observation model."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[4]
sys.path[:0]=[str(ROOT),str(ROOT/'tests/device'),str(HERE)]
import test_world_current_keys_originals as storage
from adapters.normal_ui import NativeUIError
from adapters.normal_feature_state import PrivateFeatureState
from adapters.native_fd_owner import OriginalDescriptor
from adapters.pico4.world_current_keys_originals import UNRESOLVED_HOST_FILES,UNRESOLVED_SOURCE_RECORDS
from adapters.pico4.world_current_keys_parent import PicoWorldCurrentKeysParent
from adapters.pico4.world_current_gesture import PicoWorldCurrentGesture
from test_world_current_input_reader import CurrentBoundary,RUN,URL,OWNER


class WorldCurrentKeysHostPassTests(unittest.TestCase):
    setUp=storage.WorldCurrentKeysOriginalsTests.setUp
    guard=storage.WorldCurrentKeysOriginalsTests.guard
    remember=storage.WorldCurrentKeysOriginalsTests.remember
    create=storage.WorldCurrentKeysOriginalsTests.create

    def tearDown(self):
        if self.ledger is not None:
            for window in getattr(self,'passes',[]):
                if window.final_pins is None and not getattr(self,'uncertain',False):
                    for writer in window.writers:
                        self.assertTrue(writer.close_host())
                    if window.directory is not None:self.assertTrue(window.directory.close())
            if not self.ledger.closed:self.assertTrue(self.ledger.file.close_host())
        count=len(os.listdir('/proc/self/fd'))
        if not getattr(self,'uncertain',False):self.assertEqual(self.fd_before,count)
        else:
            self.assertGreater(count,self.fd_before)
            (self.root/'intentional-unresolved-fds.json').write_text(__import__('json').dumps(dict(before=self.fd_before,after=count,
                reason='actual recycled directory FD: original anchor and foreign alias retained until Host process finalization')))

    def acquire(self,value):
        baseline=deepcopy(self.expected)
        with self.ledger.host_transaction(baseline) as window:
            self.passes=getattr(self,'passes',[])+[window]
            result=self.ledger.retain_source(value)
        self.expected=deepcopy(window.final_pins);self.guard();return result

    def test_same_source_bytes_schema_old_originals_and_full_entry_exit_rows(self):
        with self.lock.held():
            ledger=self.create();old=ledger.retain(dict(kind='previous-original',value='must remain immutable'))
            immutable=ledger.chunks.store(old['parts'][0]).path;before=immutable.read_bytes(),immutable.lstat()
            value=dict(kind='raw',request=dict(commandId='a'*32),raw='actual 東京\0 literal')
            root_before=ledger.store.path.lstat();seek=os.lseek;rewinds=[]
            def rewind(fd,offset,whence):
                rewinds.append((fd,offset,whence));return seek(fd,offset,whence)
            with patch.object(os,'lseek',side_effect=rewind):ref=self.acquire(value)
            record=ledger.read(ref);window=self.passes[-1]
            self.assertNotEqual(root_before.st_ino,ledger.store.path.lstat().st_ino)
            self.assertGreaterEqual(sum(offset==0 and whence==os.SEEK_SET for _fd,offset,whence in rewinds),3)
            self.assertEqual(value['raw'],storage.source_literal(record,ledger.raw))
            self.assertEqual(before[0],immutable.read_bytes());self.assertEqual(before[1],immutable.lstat())
            self.assertEqual(self.expected,self.parent.pins());self.assertEqual(1,len(self.passes[-1].writers))
            self.assertTrue(all(w.file.closed and w.parent.closed for w in self.passes[-1].writers))
            self.assertTrue(self.passes[-1].directory.closed)

    def test_namespace_addition_is_not_adopted_on_intermediate_root_commit(self):
        with self.lock.held():
            ledger=self.create();write=ledger.file.write;fired=[];baseline=deepcopy(self.expected)
            def foreign(value,previous):
                result=write(value,previous)
                if not fired:
                    fired.append(True);path=self.parent.root/'foreign.json';path.write_text('{}\n');path.chmod(0o600)
                return result
            with self.assertRaises(NativeUIError):
                with ledger.host_transaction(baseline) as window:
                    self.passes=[window]
                    with patch.object(ledger.file,'write',side_effect=foreign):ledger.retain_source(dict(request=dict(commandId='a'*32),raw='returned'))
            self.assertTrue(ledger.failed);self.assertEqual(baseline,self.expected);self.assertTrue((self.parent.root/'foreign.json').exists())
            self.assertIn(window,UNRESOLVED_HOST_FILES)

    def test_unrelated_actual_byte_change_or_same_byte_child_replacement_is_not_adopted(self):
        for replacement in (False,True):
            with self.subTest(replacement=replacement):
                # Independent real owner per fault; failed owners cannot reset.
                case=WorldCurrentKeysHostPassTests();case.setUp()
                try:
                    with case.lock.held():
                        ledger=case.create();ref=ledger.retain(dict(kind='old',value='unchanged'))
                        child=ledger.chunks.store(ref['parts'][0]).path;raw=child.read_bytes();write=ledger.file.write;fired=[]
                        def mutate(value,previous):
                            answer=write(value,previous)
                            if not fired:
                                fired.append(True)
                                if replacement:
                                    child.rename(case.root/'held-original.json');child.write_bytes(raw);child.chmod(0o600)
                                else:child.write_bytes(raw[:-1]+b' ');case.assertNotEqual(raw,child.read_bytes())
                            return answer
                        with case.assertRaises(NativeUIError):
                            with ledger.host_transaction(deepcopy(case.expected)) as window:
                                case.passes=[window]
                                with patch.object(ledger.file,'write',side_effect=mutate):ledger.retain_source(dict(request=dict(commandId='a'*32),raw='new'))
                        case.assertTrue(ledger.failed);case.assertEqual([True],fired)
                finally:case.tearDown()

    def test_new_child_write_uses_actual_prepared_ofd_and_rejects_byte_equal_exchange(self):
        from adapters.pico4.lifecycle_process_file import LifecycleProcessFile
        with self.lock.held():
            ledger=self.create();write=LifecycleProcessFile.write;fired=[]
            def exchange(owner,value,previous):
                answer=write(owner,value,previous)
                if owner is not ledger.file and not fired:
                    fired.append(True);path=owner.path;raw=path.read_bytes();path.rename(self.root/'held-prepared-child.json')
                    path.write_bytes(raw);path.chmod(0o600)
                return answer
            with self.assertRaises(NativeUIError):
                with ledger.host_transaction(deepcopy(self.expected)) as window:
                    self.passes=[window]
                    with patch.object(LifecycleProcessFile,'write',new=exchange):ledger.retain_source(dict(request=dict(commandId='a'*32),raw='new'))
            self.assertEqual([True],fired);self.assertTrue(ledger.failed);self.assertTrue((self.root/'held-prepared-child.json').exists())

    def test_lost_header_cas_retains_acquired_raw_and_does_not_update_expected_baseline(self):
        value=dict(request=dict(commandId='a'*32),raw='already acquired raw 東京');before=None
        with self.lock.held():
            ledger=self.create();before=deepcopy(self.expected)
            with self.assertRaises(RuntimeError):
                with ledger.host_transaction(before) as window:
                    self.passes=[window]
                    with patch.object(ledger.file,'write',side_effect=RuntimeError('DECLARED_LOST_CAS')):ledger.retain_source(value)
            self.assertTrue(ledger.failed);self.assertEqual(before,self.expected)
            self.assertTrue(any(v is value for v in UNRESOLVED_SOURCE_RECORDS));self.assertIn(window,UNRESOLVED_HOST_FILES)

    def test_actual_recycled_directory_fd_is_retained_foreign_description_untouched(self):
        with self.lock.held():
            ledger=self.create();foreign_path=self.root/'foreign-fd.json';foreign_path.write_text('{}\n');foreign_path.chmod(0o600)
            foreign=None
            with self.assertRaises(NativeUIError):
                with ledger.host_transaction(deepcopy(self.expected)) as window:
                    self.passes=[window];foreign=OriginalDescriptor(foreign_path,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
                    os.dup2(foreign.fd,window.directory.fd);self.uncertain=True
                    ledger.retain_source(dict(request=dict(commandId='a'*32),raw='acquired'))
            foreign.require(foreign.fd);self.assertEqual(foreign.node,(os.fstat(window.directory.fd).st_dev,os.fstat(window.directory.fd).st_ino))
            self.assertFalse(window.directory.close());self.assertIn(window,UNRESOLVED_HOST_FILES);self.assertTrue(foreign.close())

    def test_guard_source_capacity_and_publication_reentry_refuse_before_sdk_clock(self):
        owner=object.__new__(PicoWorldCurrentKeysParent);owner._pass_active=True
        for function in (owner.clock,owner.guard,owner.capacity,owner.source,lambda:owner.run({}),lambda:owner.retain({}),
                         lambda:owner.neutral({}),lambda:owner.gesture(None)):
            with self.subTest(function=function),self.assertRaises(NativeUIError):function()
        with self.lock.held():pass
        boundary=CurrentBoundary(self.lock);boundary.current.read(RUN,URL,OWNER,'measure-current-ray','text')
        native=[];owner._pass_active=False
        for source in (boundary.current,boundary.doc_source):
            source.clock_ms=lambda:(native.append('clock') or boundary.epoch)
            source.send=lambda _value:native.append('send')
            source.read_raw=lambda:(native.append('getter') or '')
        owner.protect_source(boundary.current);owner._pass_active=True
        for function in (boundary.current.clock_ms,lambda:boundary.current.send({}),boundary.current.read_raw,
                         boundary.doc_source.clock_ms,lambda:boundary.doc_source.send({}),boundary.doc_source.read_raw):
            with self.assertRaises(NativeUIError):function()
        gesture=PicoWorldCurrentGesture(boundary.current,lambda *_args,**_kw:native.append('stage'),lambda _v:None,lambda _v:None,
            lambda _v:None,started=0,requested=boundary.epoch)
        with self.assertRaises(NativeUIError):gesture.publish()
        self.assertEqual([],native)


if __name__=='__main__':unittest.main()
