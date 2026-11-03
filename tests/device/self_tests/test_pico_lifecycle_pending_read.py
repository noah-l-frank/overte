"""New wire prerequisite: actual Linux FD/file/read/timeout, declared SDK model.

No actual ADB, target startup, Native input, new journey or factory is invoked.
One existing AudioRawArchive carries all returned bytes under the same limits.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from adapters.host_process_identity import host_identity
from adapters.normal_ui import NativeUIError
from adapters.pico4.audio_raw_archive import AudioRawArchive
from adapters.pico4.lifecycle_namespace_bill import LifecycleNamespaceBill
from adapters.pico4.lifecycle_pending_read import (PicoLifecyclePendingRead,READ_SCRIPT,PATH,PACKAGE,HEADER,
    wire_extent,body_original,UNRESOLVED)
from adapters.script_journey.lock import ScriptSourceLock
from self_tests.test_pico_lifecycle_world import BINDING
from self_tests.test_pico_lifecycle_source import RUN


class LocalSdkModel:
    """Execute only the fixed remote script on a private HOST fixture tree."""
    def __init__(self,root):self.root=root;self.calls=[];self.mode='normal';self.partial=None;self.after=None
    def execute_bytes(self,arguments,*,target,timeout,check):
        self.calls.append((deepcopy(arguments),target,timeout,check))
        assert arguments[0]=='exec-out' and target=='explicit-pending-read-target' and check is False
        parts=shlex.split(arguments[1]);assert parts[:4]==['run-as',PACKAGE,'sh','-c'] and parts[4]==READ_SCRIPT
        assert parts[5]=='overte-lifecycle-pending-read'
        if self.mode=='timeout':
            nonce=parts[-1];prefix=HEADER+nonce.encode()+b'\npresent\nactual partial \x00\xff\r\n'
            code='import os,sys,time;os.write(1,bytes.fromhex(sys.argv[1]));time.sleep(2)'
            try:subprocess.run([sys.executable,'-u','-c',code,prefix.hex()],stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,timeout=.1,check=False)
            except subprocess.TimeoutExpired as error:
                self.partial=error.output
                raise RuntimeError('Original modeled SDK timeout') from error
            raise AssertionError('actual timeout did not occur')
        result=subprocess.run(['/bin/sh','-c',READ_SCRIPT,*parts[5:]],cwd=self.root,stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,timeout=timeout,check=False)
        if self.after:self.after()
        return result.stdout


class LifecyclePendingReadTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.root.chmod(0o700)
        self.file=self.root/PATH;self.file.parent.mkdir(parents=True,mode=0o700)
        self.file.parent.chmod(0o700);self.host=self.root/'host';self.host.mkdir(mode=0o700)
        self.lock=ScriptSourceLock(self.host/'script-sources.lock')
        self.expanded=None
        self.namespace=LifecycleNamespaceBill(self.host,self.lock,mutex_layout=2,expanded=lambda:self.expanded);self.addCleanup(self.namespace.close)
        pid,birth,_boot=host_identity().split(':');self.process=pid+':'+birth
        self.binding=BINDING|dict(processIdentity=self.process)
        self.scope=dict(lifecycleSourceRawVersion=4,pendingNativeReadVersion=1,role='lifecycle-source',runId=RUN,binding=self.binding)
        self.bank=None
        if getattr(self,'raw_bank_profile',False):
            from adapters.pico4.lifecycle_source_raw import LifecycleSourceRaw4
            self.bank=LifecycleSourceRaw4(self.host/'lifecycle-background-raw.json',RUN,self.binding,self.lock,
                self.lock.assert_held,self.namespace,time.monotonic,pending_read_version=1)
            self.archive=self.bank.archive;self.addCleanup(self.bank.close_host)
        else:
            self.archive=AudioRawArchive(self.host/'lifecycle-background-raw.json',self.scope,self.lock,
                self.lock.assert_held,self.namespace,time.monotonic);self.addCleanup(self.archive.close_host)
        self.sdk=LocalSdkModel(self.root);self.alive=True
        def same(target,identity,label):
            if not self.alive or target!='explicit-pending-read-target' or identity!=self.process:
                raise NativeUIError('Original modeled process identity is unavailable')
        self.adapter=SimpleNamespace(kind='pico',profile={'package':PACKAGE},adb=self.sdk,require_same_process=same)
        self.reader=PicoLifecyclePendingRead(self.adapter,'explicit-pending-read-target',self.binding,self.archive,bank=self.bank)
        self.request=dict(schemaVersion=1,commandId='f'*32,action='feature-pending-commit-owner',operation='observe',runId=RUN,eventId='')

    def store(self,raw):self.file.write_bytes(raw);self.file.chmod(0o600)
    def read(self):
        with self.lock.held():return self.reader.read(self.request,time.monotonic(),time.time_ns()//1000000)
    def original(self,read=0):
        record=self.archive.pages[read//32]['receipts'][read%32]
        ref=dict(audioRawRangeVersion=1,scopeSha256=self.archive.scope_sha,read=read,sha256=record['sha256'])
        with self.lock.held():return self.archive.literal(ref),record

    def test_actual_fixed_script_original_fd_and_exact_body_extent_roundtrip_without_native_parser(self):
        body=b'{"original":"Overte \\u00e4 \\u03a9"}\n';self.store(body)
        self.assertEqual(body.decode(),self.read());wire,record=self.original()
        self.assertEqual(body.decode(),body_original(wire,self.reader.last,record=record,scope_sha=self.archive.scope_sha,run=RUN))
        self.assertEqual('bytes',record['kind']);self.assertEqual('pending-wire',record['role'])
        self.assertEqual(1,len(self.sdk.calls));self.assertEqual(1,self.archive.state['reads'])
        self.assertLessEqual(self.sdk.calls[0][2],5);self.assertEqual(body,self.file.read_bytes())
        anchor,requested,entered,dispatched,returned=self.reader.timing
        self.assertLessEqual(anchor,entered);self.assertLessEqual(entered,dispatched);self.assertLessEqual(dispatched,returned)
        self.assertEqual(anchor,record['command']['originalStartedHost'])

    def test_exact_32k_payload_remains_accepted_without_raising_native_semantic_limit(self):
        body=b'{}'+b' '*(32768-2);self.store(body)
        self.assertEqual(body.decode(),self.read());wire,record=self.original()
        self.assertGreater(len(wire),32768);self.assertEqual(32768,self.reader.last['bytes'])
        self.assertEqual(1,self.archive.state['reads']);self.assertEqual(body.decode(),body_original(wire,self.reader.last,record=record,scope_sha=self.archive.scope_sha,run=RUN))

    def test_actual_32k_plus_one_and_4m_file_keep_complete_bounded_overflow_wire_before_refusal(self):
        for size in (32769,4*1024*1024):
            with self.subTest(size=size):
                fixture=LifecyclePendingReadTests();fixture.setUp()
                try:
                    fixture.store(b'{}'+b' '*(size-2))
                    with self.assertRaises(NativeUIError):fixture.read()
                    wire,record=fixture.original();extent=wire_extent(wire,record['command']['readNonce'])
                    self.assertEqual('over-limit',extent['status']);self.assertEqual(size,extent['sourceBytes'])
                    self.assertEqual(32769,extent['bytes']);self.assertEqual({},json.loads(wire[extent['offset']:extent['offset']+extent['bytes']]))
                    self.assertIsNone(fixture.reader.last);self.assertEqual(1,len(fixture.sdk.calls))
                    with self.assertRaises(NativeUIError):fixture.read()
                    self.assertEqual(1,len(fixture.sdk.calls));self.assertIn(fixture.reader,UNRESOLVED)
                finally:fixture.doCleanups()

    def test_actual_partial_stdout_timeout_is_retained_before_error_and_never_requeried(self):
        self.store(b'{}');self.sdk.mode='timeout'
        with self.assertRaises(NativeUIError):self.read()
        wire,_record=self.original();self.assertEqual(self.sdk.partial,wire);self.assertIn(b'\x00\xff\r\n',wire)
        self.assertIsNone(self.reader.last);self.assertIn(self.reader,UNRESOLVED)
        with self.assertRaises(NativeUIError):self.read()
        self.assertEqual(1,len(self.sdk.calls))

    def test_invalid_utf8_is_archived_as_exact_bytes_before_utf8_parser_and_refuses_next_read(self):
        self.store(b'{"original":"\xff"}')
        with self.assertRaises(NativeUIError):self.read()
        wire,_record=self.original();self.assertIn(b'\xff',wire);self.assertIsNone(self.reader.last)
        with self.assertRaises(NativeUIError):self.read()
        self.assertEqual(1,len(self.sdk.calls))

    def test_candidate_death_after_actual_sdk_return_cannot_block_archival_of_acquired_wire(self):
        self.store(b'{}');self.sdk.after=lambda:setattr(self,'alive',False)
        with self.assertRaises(NativeUIError):self.read()
        wire,_record=self.original();self.assertIn(b'{}',wire);self.assertEqual(1,len(self.sdk.calls))

    def test_genuinely_missing_file_is_explicit_missing_not_a_successful_native_empty_inventory(self):
        self.assertEqual('',self.read());wire,record=self.original()
        self.assertEqual('missing',wire_extent(wire,record['command']['readNonce'])['status'])
        self.assertIsNone(self.reader.last);self.assertFalse(self.reader.failed)

    def test_foreign_symlink_is_never_read_as_the_fixed_original(self):
        outside=self.root/'outside';outside.write_bytes(b'foreign original');outside.chmod(0o600)
        self.file.symlink_to(outside)
        with self.assertRaises(NativeUIError):self.read()
        wire,_record=self.original();self.assertNotIn(b'foreign original',wire)
        self.assertEqual(b'foreign original',outside.read_bytes());self.assertIsNone(self.reader.last)

    def test_wrong_run_is_refused_before_reservation_or_any_sdk_read(self):
        self.store(b'{}');self.request['runId']='b'*32
        with self.assertRaises(NativeUIError):self.read()
        self.assertEqual([],self.sdk.calls);self.assertEqual(0,self.archive.state['reads'])

    def test_slow_original_reservation_with_frozen_native_epoch_cannot_issue_late_sdk(self):
        self.store(b'{}');clock=[0.]
        reader=PicoLifecyclePendingRead(self.adapter,'explicit-pending-read-target',self.binding,self.archive,monotonic=lambda:clock[0])
        reserve=self.archive.reserve
        def slow(*args,**kwargs):
            result=reserve(*args,**kwargs);clock[0]=5.;return result
        with self.lock.held(),patch.object(self.archive,'reserve',side_effect=slow),self.assertRaises(NativeUIError):
            reader.read(self.request,0.,time.time_ns()//1000000)
        self.assertEqual([],self.sdk.calls);self.assertEqual(1,len(self.archive.state['pending']))
        self.assertIn(reader,UNRESOLVED)

    def test_issued_wire_receipt_unknown_cas_preserves_actual_return_and_forbids_requery(self):
        self.store(b'{}');save=self.archive.save
        def uncertain():
            if self.archive.open_data:raise OSError('Actual wire bytes appended; root CAS unknown')
            return save()
        with patch.object(self.archive,'save',side_effect=uncertain),self.assertRaises(NativeUIError):self.read()
        self.assertEqual(1,len(self.sdk.calls));self.assertIsNotNone(self.reader.acquired)
        self.assertEqual(self.reader.acquired,self.archive.open_data)
        self.assertIsNone(self.reader.last)
        with self.assertRaises(NativeUIError):self.read()
        self.assertEqual(1,len(self.sdk.calls))

    def test_body_reference_cannot_relabel_native_command_nonce_role_read_scope_or_timing(self):
        self.store(b'{}');self.read();wire,record=self.original();reference=deepcopy(self.reader.last)
        variants=[('reference',lambda value:value.__setitem__('nativeCommandId','e'*32)),
            ('reference',lambda value:value.__setitem__('readNonce','e'*32)),
            ('reference',lambda value:value['wireOriginal'].__setitem__('read',1)),
            ('reference',lambda value:value['wireOriginal'].__setitem__('scopeSha256','e'*64)),
            ('record',lambda value:value.__setitem__('role','pending')),
            ('record',lambda value:value['command'].__setitem__('readNonce','e'*32)),
            ('record',lambda value:value['command']['nativeRequest'].__setitem__('commandId','e'*32)),
            ('record',lambda value:value['command']['nativeRequest'].__setitem__('runId','e'*32)),
            ('record',lambda value:value.__setitem__('returnedHostMonotonic',value['command']['originalStartedHost']+5))]
        for kind,mutate in variants:
            with self.subTest(kind=kind,mutate=mutate):
                changed_reference=deepcopy(reference);changed_record=deepcopy(record)
                mutate(changed_reference if kind=='reference' else changed_record)
                with self.assertRaises(NativeUIError):
                    body_original(wire,changed_reference,record=changed_record,scope_sha=self.archive.scope_sha,run=RUN)
        self.assertEqual(1,len(self.sdk.calls));self.assertEqual(1,self.archive.state['reads'])

    def test_business_clock_failure_after_actual_sdk_response_or_timeout_cannot_discard_raw(self):
        for mode in ('normal','timeout'):
            with self.subTest(mode=mode):
                fixture=LifecyclePendingReadTests();fixture.setUp()
                try:
                    fixture.store(b'{"original":"preserve before clock"}');fixture.sdk.mode=mode
                    def clock():
                        if fixture.sdk.calls:raise RuntimeError('Original business clock lost after acquired SDK bytes')
                        return time.monotonic()
                    reader=PicoLifecyclePendingRead(fixture.adapter,'explicit-pending-read-target',fixture.binding,fixture.archive,monotonic=clock)
                    with self.assertRaises(NativeUIError),fixture.lock.held():
                        reader.read(fixture.request,time.monotonic(),time.time_ns()//1000000)
                    wire,record=fixture.original()
                    self.assertEqual(reader.acquired,wire);self.assertEqual('bytes',record['kind'])
                    if mode=='timeout':self.assertEqual(fixture.sdk.partial,wire)
                    else:self.assertIn(b'preserve before clock',wire)
                    self.assertIn(reader,UNRESOLVED)
                    with self.assertRaises(NativeUIError),fixture.lock.held():
                        reader.read(fixture.request,time.monotonic(),time.time_ns()//1000000)
                    self.assertEqual(1,len(fixture.sdk.calls))
                finally:fixture.doCleanups()

    def test_initial_business_clock_failure_is_sticky_and_strongly_retained_without_io(self):
        def missing_clock():raise RuntimeError('Original business clock unavailable at entry')
        reader=PicoLifecyclePendingRead(self.adapter,'explicit-pending-read-target',self.binding,self.archive,monotonic=missing_clock)
        with self.assertRaises(NativeUIError),self.lock.held():reader.read(self.request,time.monotonic(),time.time_ns()//1000000)
        self.assertIn(reader,UNRESOLVED);self.assertTrue(reader.failed);self.assertEqual([],self.sdk.calls)
        self.assertEqual(0,self.archive.state['reads']);self.assertFalse(reader.active)


class LifecyclePendingBankReadTests(unittest.TestCase):
    def setUp(self):
        self.fixture=LifecyclePendingReadTests();self.fixture.raw_bank_profile=True;self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)

    def test_actual_fixed_sdk_wire_uses_one_original_profile_bank_reservation_and_passive_no_rewrite(self):
        from adapters.pico4.lifecycle_source_raw import LifecycleSourceRawHistory4
        f=self.fixture;f.store(b'{"actual":"one original wire"}')
        self.assertEqual('{"actual":"one original wire"}',f.read())
        with f.lock.held():
            raws,records=f.bank.verify(materialize=True)
            self.assertEqual(1,len(records));self.assertEqual('pending-wire',records[0]['role'])
            self.assertEqual(1,f.archive.state['reads']);self.assertEqual(36864,f.bank.maximum_literal)
            self.assertEqual(36864,f.bank.literal_limit('pending-wire'));self.assertEqual(32768,f.bank.literal_limit('pending'))
            self.assertEqual(raws[0],f.original()[0]);f.bank.seal()
        snapshot={p.name:(p.read_bytes(),p.stat().st_ino,p.stat().st_mtime_ns,p.stat().st_ctime_ns) for p in f.host.iterdir() if p.is_file()}
        history=LifecycleSourceRawHistory4(f.archive.path,RUN,f.binding,[],role='pending',pending_read_version=1)
        try:
            wire=history.archive.literal(f.reader.last['wireOriginal'])
            self.assertEqual('{"actual":"one original wire"}',body_original(wire,f.reader.last,
                record=history.archive.receipts[0],scope_sha=history.archive.scope_sha,run=RUN))
            self.assertEqual([],history.references)
        finally:self.assertTrue(history.close())
        self.assertEqual(snapshot,{p.name:(p.read_bytes(),p.stat().st_ino,p.stat().st_mtime_ns,p.stat().st_ctime_ns) for p in f.host.iterdir() if p.is_file()})
        with self.assertRaises(NativeUIError):LifecycleSourceRawHistory4(f.archive.path,RUN,f.binding,[],role='pending')
        self.assertEqual(1,len(f.sdk.calls))

    def test_profile_is_pinned_before_first_query_and_cannot_be_mutated_or_bound_twice(self):
        f=self.fixture;f.store(b'{}')
        with self.assertRaises(NativeUIError):PicoLifecyclePendingRead(f.adapter,'explicit-pending-read-target',f.binding,f.archive,bank=f.bank)
        f.bank.pending_read_version=0
        with self.assertRaises(NativeUIError):f.read()
        self.assertEqual([],f.sdk.calls);self.assertEqual(0,f.archive.state['reads'])

    def test_actual_overflow_wire_poison_blocks_every_next_bank_admission_but_passive_original_remains(self):
        from adapters.pico4.lifecycle_source_raw import LifecycleSourceRawHistory4
        f=self.fixture;f.store(b'x'*32769)
        with self.assertRaises(NativeUIError):f.read()
        self.assertTrue(f.bank.failed);wire,record=f.original()
        with f.lock.held(),self.assertRaises(NativeUIError):f.bank.verify()
        history=LifecycleSourceRawHistory4(f.archive.path,RUN,f.binding,[],role='pending',pending_read_version=1)
        try:
            ref=dict(audioRawRangeVersion=1,scopeSha256=history.archive.scope_sha,read=0,sha256=record['sha256'])
            self.assertEqual(wire,history.archive.literal(ref));self.assertEqual('over-limit',wire_extent(wire,record['command']['readNonce'])['status'])
        finally:self.assertTrue(history.close())
        with self.assertRaises(NativeUIError):f.read()
        self.assertEqual(1,len(f.sdk.calls))

    def test_slow_actual_reservation_does_not_renew_existing_whole_acquisition_anchor(self):
        f=self.fixture;f.store(b'{}');original=f.bank.reserve_pending_wire
        requested=time.time_ns()//1000000;f.bank.begin_outer(time.monotonic()-1.45,requested)
        def slow(*args,**kwargs):
            token=original(*args,**kwargs);time.sleep(.1);return token
        with patch.object(f.bank,'reserve_pending_wire',side_effect=slow),self.assertRaises(NativeUIError):f.read()
        self.assertEqual([],f.sdk.calls);self.assertEqual(1,len(f.archive.state['pending']))
        self.assertTrue(f.bank.failed);self.assertIn(f.reader,UNRESOLVED)


class LifecyclePendingBoundOwnerTests(unittest.TestCase):
    """Actual NativePendingCommitOwner parser, declared Native dispatch model."""
    def setUp(self):
        from adapters.native_feature_observation import NativeFeatureObservation
        from adapters.pending_commit_owner import NativePendingCommitOwner
        from self_tests.test_pending_commit_owner import Boundary
        self.fixture=LifecyclePendingReadTests();self.fixture.raw_bank_profile=True;self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups);f=self.fixture;self.events=[];self.sent=[];self.fail_write=False;self.before_dispatch=None;self.candidate_alive=True
        self.boundary=Boundary();self.boundary.epoch=lambda:time.time_ns()//1000000
        self.boundary.edit=lambda value:value.update(processId=int(f.process.split(':')[0]))
        def guard():self.events.append('native-guard');return self.candidate_alive
        def original_write(wrapper):
            self.events.append('actual-write');self.sent.append(deepcopy(wrapper))
            assert len(f.archive.state['pending'])==1 and f.archive.state['pending'][0]['role']=='pending-wire'
            if self.fail_write:raise RuntimeError('Original SDK publication uncertain')
            assert wrapper['action']=='feature-pico-pending-read' and wrapper['picoPendingReadVersion']==1
            request=deepcopy(wrapper);del request['picoPendingReadVersion'];request['action']='feature-pending-commit-owner'
            self.boundary.send(request);f.store(self.boundary.original().encode())
        selected_dispatch=f.reader.dispatch
        def native_send(request):
            guard()
            readonly=request['action']=='feature-pending-commit-owner' and request['operation']=='observe'
            self.events.append('original-readonly' if readonly else 'original-phase-fence')
            if self.before_dispatch:self.before_dispatch()
            return selected_dispatch(request,original_write)
        self.native=NativeFeatureObservation(native_send,lambda:None,self.boundary.epoch,guard,
            int(f.process.split(':')[0]),monotonic=f.reader.monotonic)
        f.reader.bind_native(self.native,original_write,selected_dispatch)
        def old_getter():raise AssertionError('Unbounded original getter must not run in the explicit mode')
        self.owner=NativePendingCommitOwner(self.native.send,old_getter,self.native.clock_ms,self.native.guard,
            self.native.pid,monotonic=self.native.monotonic,sleep=self.native.sleep)
        f.reader.bind(self.owner,native=self.native,target=f.reader.target,binding=f.binding)

    def read(self):
        with self.fixture.lock.held():return self.owner.read(RUN)

    def test_existing_native_owner_uses_original_action_fence_then_one_reserved_wire_and_parser(self):
        f=self.fixture;value=self.read()
        self.assertEqual(RUN,value['runId']);self.assertEqual(1,len(self.sent));self.assertEqual(1,len(f.sdk.calls))
        self.assertIn('original-readonly',self.events);self.assertNotIn('original-phase-fence',self.events)
        self.assertLess(self.events.index('original-readonly'),self.events.index('actual-write'))
        wire,record=f.original();self.assertEqual(self.owner.last_request,record['command']['nativeRequest'])
        self.assertEqual(self.owner.last_received[:2],f.reader.timing[:2])
        self.assertEqual(self.owner.last_raw,body_original(wire,f.reader.last,record=record,scope_sha=f.archive.scope_sha,run=RUN))
        self.assertLessEqual(record['command']['reservationEnteredHost'],f.reader.timing[2])
        with f.lock.held():f.bank.verify()
        self.assertEqual(1,f.archive.state['reads'])

    def test_actual_capacity_refusal_precedes_native_write_and_keeps_original_request(self):
        f=self.fixture;f.expanded={'oversize':'x'*(16*1024*1024)}
        with self.assertRaises(NativeUIError):self.read()
        self.assertEqual([],self.sent);self.assertEqual([],f.sdk.calls);self.assertIsNotNone(f.reader.request)
        self.assertIn(f.reader,UNRESOLVED);self.assertTrue(f.bank.failed)

    def test_original_send_work_cannot_renew_exchange_deadline_or_reserve_after_expiry(self):
        f=self.fixture;self.before_dispatch=lambda:time.sleep(5.01)
        with self.assertRaises(NativeUIError):self.read()
        self.assertEqual([],self.sent);self.assertEqual([],f.sdk.calls)

    def test_lost_actual_native_write_is_sticky_with_preissued_wire_and_no_second_write(self):
        f=self.fixture;self.fail_write=True
        with self.assertRaises(NativeUIError):self.read()
        self.assertEqual(1,len(self.sent));self.assertEqual(1,len(f.archive.state['pending']))
        self.assertEqual([],f.sdk.calls);self.assertIsNotNone(f.reader.pending)
        with self.assertRaises(NativeUIError):self.read()
        self.assertEqual(1,len(self.sent));self.assertIn(f.reader,UNRESOLVED)

    def test_replaced_owner_or_native_callback_is_not_resealed_and_cannot_send(self):
        f=self.fixture;self.native.send=lambda value:None
        with self.assertRaises(NativeUIError):self.read()
        self.assertEqual([],self.sent);self.assertEqual([],f.sdk.calls);self.assertIn(f.reader,UNRESOLVED)

    def test_native_callback_lost_after_actual_sdk_return_does_not_block_archival_only_retention(self):
        f=self.fixture;f.sdk.after=lambda:setattr(self.native,'send',lambda value:None)
        with self.assertRaises(NativeUIError):self.read()
        wire,record=f.original();self.assertIn(b'pendingCommitOwnerVersion',wire)
        self.assertEqual(1,len(self.sent));self.assertEqual(1,len(f.sdk.calls))
        self.assertEqual(record['command']['nativeRequest']['commandId'],self.sent[0]['commandId'])
        self.assertIn(f.reader,UNRESOLVED)
        with self.assertRaises(NativeUIError):self.read()
        self.assertEqual(1,len(self.sent));self.assertEqual(1,len(f.sdk.calls))

    def test_candidate_lost_during_actual_reservation_refuses_before_original_native_write(self):
        f=self.fixture;reserve=f.bank.reserve_pending_wire
        def lose_after_capacity(*args,**kwargs):
            token=reserve(*args,**kwargs);self.candidate_alive=False;return token
        with patch.object(f.bank,'reserve_pending_wire',side_effect=lose_after_capacity),self.assertRaises(NativeUIError):self.read()
        self.assertEqual([],self.sent);self.assertEqual([],f.sdk.calls)
        self.assertEqual(1,len(f.archive.state['pending']));self.assertIn(f.reader,UNRESOLVED)


class LifecyclePendingBodyHistoryTests(unittest.TestCase):
    def setUp(self):
        self.fixture=LifecyclePendingReadTests();self.fixture.raw_bank_profile=True;self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups);self.fixture.store(b'{"original":"one body extent"}')
        self.body=self.fixture.read();self.reference=deepcopy(self.fixture.reader.last)

    def test_selected_body_is_validated_in_same_verified_pass_without_a_materialized_raw_cache(self):
        from adapters.pico4.lifecycle_raw_ranges import verified_ranges
        f=self.fixture
        with f.lock.held():
            raw,records=verified_ranges(f.archive,roles=f.bank.roles,materialize=False,pending_bodies=(self.reference,))
        self.assertEqual({},raw);self.assertEqual([0],list(records));self.assertEqual(1,len(f.sdk.calls))

    def test_actual_profile_history_reconstructs_typed_body_without_second_original_or_any_rewrite(self):
        from adapters.pico4.lifecycle_source_raw import LifecycleSourceRawHistory4
        from adapters.pico4.lifecycle_back import frame
        f=self.fixture
        with f.lock.held():f.bank.seal()
        before={p.name:(p.read_bytes(),p.stat().st_ino,p.stat().st_mtime_ns,p.stat().st_ctime_ns) for p in f.host.iterdir() if p.is_file()}
        history=LifecycleSourceRawHistory4(f.archive.path,RUN,f.binding,[self.reference],role='pending',pending_read_version=1)
        try:self.assertEqual([frame(self.body)],history.decode([self.reference]))
        finally:self.assertTrue(history.close())
        self.assertEqual(before,{p.name:(p.read_bytes(),p.stat().st_ino,p.stat().st_mtime_ns,p.stat().st_ctime_ns) for p in f.host.iterdir() if p.is_file()})
        self.assertEqual(1,f.archive.state['reads']);self.assertEqual(1,len(f.sdk.calls))

    def test_changed_body_command_nonce_range_or_hash_never_inherits_original_wire_identity(self):
        from adapters.pico4.lifecycle_raw_ranges import verified_ranges
        f=self.fixture
        mutations=[lambda r:r.__setitem__('nativeCommandId','e'*32),lambda r:r.__setitem__('readNonce','e'*32),
            lambda r:r.__setitem__('offset',r['offset']+1),lambda r:r.__setitem__('sha256','e'*64)]
        for mutate in mutations:
            changed=deepcopy(self.reference);mutate(changed)
            with self.assertRaises(NativeUIError),f.lock.held():
                verified_ranges(f.archive,roles=f.bank.roles,materialize=False,pending_bodies=(changed,))
        self.assertEqual(1,len(f.sdk.calls));self.assertEqual(1,f.archive.state['reads'])

    def test_duplicate_or_foreign_body_refs_refuse_before_record_decode_and_preserve_original(self):
        from adapters.pico4.lifecycle_raw_ranges import verified_ranges
        f=self.fixture;foreign=deepcopy(self.reference);foreign['wireOriginal']['scopeSha256']='e'*64
        for references in ((self.reference,self.reference),(foreign,)):
            with patch('adapters.pico4.lifecycle_raw_ranges.record_literal',side_effect=AssertionError('Decoder must not start')) as decoder:
                with self.assertRaises(NativeUIError),f.lock.held():
                    verified_ranges(f.archive,roles=f.bank.roles,materialize=False,pending_bodies=references)
                decoder.assert_not_called()
        self.assertEqual(1,len(f.sdk.calls))

    def test_passive_body_reference_mutation_cannot_change_cached_original_even_at_same_size(self):
        from adapters.pico4.lifecycle_source_raw import LifecycleSourceRawHistory4
        f=self.fixture
        with f.lock.held():f.bank.seal()
        history=LifecycleSourceRawHistory4(f.archive.path,RUN,f.binding,[self.reference],role='pending',pending_read_version=1)
        try:
            history.references[0]['nativeCommandId']='e'*32
            with self.assertRaises(NativeUIError):history.decode([self.reference])
        finally:self.assertTrue(history.close())
        self.assertEqual(1,len(f.sdk.calls))

    def test_passive_duplicate_body_manifest_cannot_reinterpret_one_original_as_two_selected_receipts(self):
        from adapters.pico4.lifecycle_source_raw import LifecycleSourceRawHistory4
        f=self.fixture
        with self.assertRaises(NativeUIError):LifecycleSourceRawHistory4(f.archive.path,RUN,f.binding,
            [self.reference,deepcopy(self.reference)],role='pending',pending_read_version=1)
        self.assertEqual(1,f.archive.state['reads']);self.assertEqual(1,len(f.sdk.calls))


class LifecyclePendingBodyProjectionTests(unittest.TestCase):
    def setUp(self):
        from adapters.pico4.lifecycle_back import frame
        self.fixture=LifecyclePendingReadTests();self.fixture.raw_bank_profile=True;self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups);self.fixture.store(b'{}')
        raw=self.fixture.read();self.value=[dict(request=deepcopy(self.fixture.request),original=frame(raw))]

    def test_provisional_body_uses_exact_original_request_context_and_never_a_fictitious_bare_body_row(self):
        from adapters.pico4.lifecycle_pending_read import body_key
        f=self.fixture;view=f.bank.view('pending');projection=view.project(self.value)
        encoded=projection.encoded[0]['original'];self.assertEqual(f.reader.last,encoded)
        self.assertEqual((body_key(encoded),),projection.references);self.assertEqual((),view.confirmed)
        self.assertEqual(1,f.archive.state['reads']);self.assertEqual(1,len(f.sdk.calls))
        self.assertEqual('pending-wire',f.archive.pages[0]['receipts'][0]['role'])
        with self.assertRaises(NativeUIError):f.read()
        self.assertEqual(1,len(f.sdk.calls));self.assertIs(projection.value,self.value)

    def test_equal_body_sha_with_foreign_original_request_never_relabels_the_captured_wire_clock(self):
        f=self.fixture;self.value[0]['request']['commandId']='e'*32
        with self.assertRaises(NativeUIError):f.bank.view('pending').project(self.value)
        self.assertIs(self.value,f.bank.view('pending').held[0].value)
        self.assertTrue(f.bank.failed);self.assertEqual(1,len(f.sdk.calls))

    def test_background_projection_cannot_borrow_a_pending_wire(self):
        f=self.fixture
        with self.assertRaises(NativeUIError):f.bank.view('background').project(self.value)
        self.assertEqual(1,len(f.sdk.calls));self.assertEqual(1,f.archive.state['reads'])

    def test_short_body_reference_growth_is_billed_before_first_projection_receipt_allocation(self):
        from adapters.pico4.lifecycle_namespace_bill import canonical_size
        from adapters.pico4 import lifecycle_pending_read as typed
        f=self.fixture;self.value=self.value*100;seen=[];original=typed.body_receipt
        def observe(*args,**kwargs):
            seen.append(f.bank.view('pending').held[0].peak);return original(*args,**kwargs)
        with patch.object(typed,'body_receipt',side_effect=observe):projection=f.bank.view('pending').project(self.value)
        self.assertGreater(canonical_size(projection.encoded),canonical_size(self.value))
        self.assertTrue(seen);self.assertGreaterEqual(min(seen),4*canonical_size(projection.encoded)+3*65536)
        self.assertEqual(1,f.archive.state['reads']);self.assertEqual(1,len(projection.references))

    def test_full_expanded_budget_refuses_before_any_body_decode_and_keeps_exact_acquired_graph(self):
        f=self.fixture;f.expanded={'oversize':'x'*(16*1024*1024)}
        with patch('adapters.pico4.lifecycle_pending_read.body_receipt',side_effect=AssertionError('Body decode before budget')) as decoder:
            with self.assertRaises(NativeUIError):f.bank.view('pending').project(self.value)
            decoder.assert_not_called()
        self.assertIs(self.value,f.bank.view('pending').held[0].value);self.assertEqual(1,len(f.sdk.calls))

    def test_pending_body_without_original_request_context_cannot_borrow_same_sha_wire(self):
        f=self.fixture;value=[self.value[0]['original']]
        with self.assertRaises(NativeUIError):f.bank.view('pending').project(value)
        self.assertIs(value,f.bank.view('pending').held[0].value)
        self.assertEqual(1,len(f.sdk.calls));self.assertTrue(f.bank.failed)

    def test_provisional_body_reference_cannot_decode_as_a_confirmed_owner_original(self):
        f=self.fixture;projection=f.bank.view('pending').project(self.value)
        with self.assertRaises(NativeUIError):f.bank.decode(projection.encoded,role='pending')
        self.assertEqual((),f.bank.view('pending').confirmed);self.assertEqual(1,len(f.sdk.calls))
