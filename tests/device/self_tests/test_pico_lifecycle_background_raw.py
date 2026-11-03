"""Actual source/getter and durable HOME owner over opt-in Background3 ranges.

These are explicit host Qt/SDK models, not compiled native or headset evidence.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4.lifecycle_back import frame
from adapters.pico4.lifecycle_background_raw import LifecycleBackgroundRaw3,LifecycleBackgroundRawHistory3,LifecycleBackgroundHistory
from adapters.pico4.lifecycle_namespace_bill import LifecycleNamespaceBill,canonical_size
from adapters.script_journey.lock import ScriptSourceLock
from self_tests.test_pico_lifecycle_source import Boundary,RUN
from self_tests.test_pico_lifecycle_world import BINDING
from self_tests.test_pico_lifecycle_chat import LifecycleChatTests
from self_tests.test_pico_lifecycle_background_owner import LifecycleBackgroundOwnerTests
from adapters.pico4.lifecycle_background_owner import PicoLifecycleBackground

class LifecycleBackgroundRawTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.root.chmod(0o700)
        self.lock=ScriptSourceLock(self.root/'script-sources.lock');self.clock=0.
        self.namespace=LifecycleNamespaceBill(self.root,self.lock);self.addCleanup(self.namespace.close)
        self.raw=self.make();self.addCleanup(self.raw.close_host)

    def make(self):
        return LifecycleBackgroundRaw3(self.root/'lifecycle-background-raw.json',RUN,BINDING,self.lock,
            self.lock.assert_held,self.namespace,lambda:self.clock)

    def source(self):
        native=Boundary();source=native.source();source.source_lock=self.lock
        self.raw.hook(source,'ui');return native,source

    def test_actual_source_getter_is_retained_before_parser_and_range_reconstructs_exact_literal(self):
        native,source=self.source();packet=source.capture(RUN)
        self.assertEqual(packet,json.loads(native.read()))
        projected=self.raw.encode([frame(source.last_raw)])
        self.assertEqual([frame(native.read())],self.raw.decode(projected))
        self.assertEqual(1,self.raw.archive.bill()['receipts'])
        self.raw.seal()
        historical=LifecycleBackgroundRawHistory3(self.raw.path,RUN,BINDING,self.raw.manifest)
        self.addCleanup(historical.close)
        self.assertEqual([frame(native.read())],historical.decode(projected))
        self.assertTrue(historical.report()['historicalOnly']);self.assertFalse(historical.report()['liveAuthority'])

    def test_actual_semantic_rejection_keeps_acquired_raw_before_any_next_query(self):
        native,source=self.source();native.mutate=lambda value:value.update(processId=999)
        with self.assertRaises(NativeUIError):source.capture(RUN)
        self.assertEqual(1,len(native.commands));self.assertEqual(1,self.raw.archive.bill()['receipts'])
        row=self.raw.archive.pages[0]['receipts'][0]
        reference=dict(audioRawRangeVersion=1,scopeSha256=self.raw.archive.scope_sha,read=0,sha256=row['sha256'])
        self.assertEqual(native.read(),self.raw.archive.literal(reference))

    def test_candidate_death_inside_actual_getter_does_not_block_archival_of_acquired_response(self):
        native=Boundary();source=native.source();source.source_lock=self.lock;getter=source.original
        def acquired():
            raw=getter();native.alive=False;return raw
        source.original=acquired;self.raw.hook(source,'ui')
        with self.assertRaises(NativeUIError):source.capture(RUN)
        self.assertEqual(1,len(native.commands));self.assertEqual(1,self.raw.archive.bill()['receipts'])

    def test_repeated_actual_getter_has_distinct_original_clock_receipt_without_new_send(self):
        native,source=self.source();source.capture(RUN);self.clock=7.
        with self.lock.held():self.assertEqual(native.read(),source.original())
        self.assertEqual(1,len(native.commands));self.assertEqual(2,self.raw.archive.bill()['receipts'])
        self.assertEqual(7.,self.raw.archive.pages[0]['receipts'][1]['hostMonotonic'])

    def test_unknown_pending_or_oversize_other_original_fails_before_actual_send(self):
        for name,data in [('lifecycle-world-owner.json.pending-x',b'{}\n'),
                ('foreign.json',b'{}\n'),('lifecycle-world-owner.json',b'x'*65537),
                ('lifecycle-world-owner.json',b'{"lifecycleWorldOwnerVersion":2,"lifecycleWorldOwnerVersion":2}\n')]:
            with self.subTest(name=name):
                fixture=LifecycleBackgroundRawTests();fixture.setUp()
                try:
                    native,source=fixture.source();path=fixture.root/name
                    path.write_bytes(data);path.chmod(0o600)
                    with self.assertRaises((NativeUIError,ValueError)):source.capture(RUN)
                    self.assertEqual([],native.commands);self.assertTrue(fixture.raw.archive.stopped)
                finally:fixture.doCleanups()

    def test_unobserved_or_forged_raw_dto_cannot_become_an_original(self):
        for value in ([frame('{}')],[{'raw':'{}','sha256':'f'*64}]):
            with self.subTest(value=value),self.assertRaises(NativeUIError):self.raw.encode(value)
        self.assertEqual(0,self.raw.archive.bill()['receipts'])

    def test_actual_lost_send_keeps_pending_and_never_replays(self):
        native=Boundary();source=native.source();source.source_lock=self.lock;send=source.send
        def lost(command):send(command);raise OSError('actual delivery acknowledgment lost')
        source.send=lost;self.raw.hook(source,'ui')
        with self.assertRaises(NativeUIError):source.capture(RUN)
        with self.assertRaises(NativeUIError):source.capture(RUN)
        self.assertEqual(1,len(native.commands));self.assertEqual(1,len(self.raw.archive.state['pending']))

    def test_unknown_receipt_cas_preserves_actual_literal_and_blocks_next_dispatch(self):
        native,source=self.source();save=self.raw.archive.save
        def fail_after_actual_append():
            if self.raw.archive.pages:raise OSError('uncertain actual receipt/root CAS')
            return save()
        with patch.object(self.raw.archive,'save',side_effect=fail_after_actual_append),self.assertRaises(NativeUIError):source.capture(RUN)
        self.assertEqual(1,len(native.commands));self.assertTrue(self.raw.failed)
        self.assertEqual(native.read().encode(),self.raw.archive.open_data)
        history=LifecycleBackgroundRawHistory3(self.raw.path,RUN,BINDING,[]);self.addCleanup(history.close)
        self.assertTrue(history.report()['pendingOrUncertain'])
        self.assertEqual(native.read().encode(),b''.join(history.archive.recorded_parts))
        with self.assertRaises(NativeUIError):source.capture(RUN)
        self.assertEqual(1,len(native.commands))

    def test_uncertain_append_root_retains_and_passively_exposes_the_actual_unconfirmed_tail(self):
        native,source=self.source();save=self.raw.archive.save
        def failed_prefix_cas():
            if self.raw.archive.open_data:raise OSError('actual appended bytes, unknown root CAS')
            return save()
        with patch.object(self.raw.archive,'save',side_effect=failed_prefix_cas),self.assertRaises(NativeUIError):source.capture(RUN)
        history=LifecycleBackgroundRawHistory3(self.raw.path,RUN,BINDING,[]);self.addCleanup(history.close)
        self.assertTrue(history.report()['pendingOrUncertain'])
        originals=list(history.originals());part=next(row for row in originals if row['name'].endswith('.part-000.bin'))
        self.assertEqual(native.read().encode(),part['raw']);self.assertFalse(part['liveAuthority'])
        self.assertEqual(b'',b''.join(history.archive.recorded_parts))
        with self.assertRaises(NativeUIError):source.capture(RUN)
        self.assertEqual(1,len(native.commands))

    def test_same_byte_replaced_original_part_is_not_adopted(self):
        native,source=self.source();source.capture(RUN);path=self.raw.archive.part_path(0)
        replacement=path.with_name('same-byte-replacement');replacement.write_bytes(path.read_bytes());replacement.chmod(0o600)
        os.replace(replacement,path)
        with self.assertRaises(NativeUIError):source.capture(RUN)
        self.assertEqual(1,len(native.commands))

    def test_cold_writer_never_adopts_existing_raw_root_or_pending(self):
        native,source=self.source();source.capture(RUN)
        with self.assertRaises(NativeUIError):self.make()
        self.assertEqual(1,len(native.commands))

    def test_full_declared_decoded_history_is_billed_before_decoder_or_next_target_query(self):
        native,source=self.source()
        value=dict(lifecycleWorldOwnerVersion=2,payload=dict(encoding='xz-base64-json',bytes=16*1024*1024,
            sha256='f'*64,data='AAAA'))
        PrivateFeatureState(self.root/'lifecycle-world-owner.json').write(value,None)
        # Adversarial old cache-shaped attributes cannot replace fresh file
        # parsing or reduce the declared decoder/copy reservation.
        self.namespace.cache={'lifecycle-world-owner.json':(None,b'',{},0)}
        self.namespace.chunk_frames={('forged','f'*64):[]};self.namespace.bundles={('forged',):0}
        with self.assertRaises(NativeUIError):source.capture(RUN)
        self.assertEqual([],native.commands);self.assertEqual(0,self.raw.archive.state['reads'])

    def test_reader_hook_replacement_cannot_skip_original_capture(self):
        native,source=self.source();source.original=native.read
        with self.assertRaises(NativeUIError):source.capture(RUN)
        self.assertEqual([],native.commands)

    def test_passive_reader_detects_same_byte_part_replacement_after_original_read(self):
        native,source=self.source();source.capture(RUN);projected=self.raw.encode([frame(native.read())]);self.raw.seal()
        history=LifecycleBackgroundRawHistory3(self.raw.path,RUN,BINDING,self.raw.manifest);self.addCleanup(history.close)
        self.assertEqual([frame(native.read())],history.decode(projected))
        path=self.raw.archive.part_path(0);copy=path.with_name('same-byte-foreign')
        copy.write_bytes(path.read_bytes());copy.chmod(0o400);os.replace(copy,path)
        with self.assertRaises(NativeUIError):history.decode(projected)

    def clock_archive(self,clock,bill_wrapper):
        root=Path(tempfile.mkdtemp(dir=self.root));root.chmod(0o700)
        lock=ScriptSourceLock(root/'script-sources.lock');namespace=LifecycleNamespaceBill(root,lock)
        self.addCleanup(namespace.close)
        bill=bill_wrapper(namespace);bill.namespace=namespace
        raw=LifecycleBackgroundRaw3(root/'lifecycle-background-raw.json',RUN,BINDING,lock,
            lock.assert_held,bill,clock);self.addCleanup(raw.close_host)
        return raw,lock,root

    def test_actual_slow_reservation_with_frozen_native_clock_cannot_dispatch_after_original_five_seconds(self):
        native=Boundary();source=native.source();source.monotonic=time.monotonic
        def wrapped(namespace):
            def bill():
                result=namespace();time.sleep(5.05);return result
            return bill
        raw,lock,_root=self.clock_archive(time.monotonic,wrapped);source.source_lock=lock
        gets=[];getter=source.original
        source.original=lambda:(gets.append(True),getter())[1];raw.hook(source,'ui')
        with self.assertRaises(NativeUIError):source.capture(RUN)
        self.assertEqual([],native.commands);self.assertEqual([],gets)
        self.assertEqual(1,len(raw.archive.state['pending']))

    def test_actual_slow_later_getter_reservation_keeps_same_original_start_and_never_reacquires(self):
        native=Boundary();source=native.source();source.monotonic=time.monotonic;calls=[]
        def wrapped(namespace):
            def bill():
                result=namespace();calls.append(True)
                if len(calls)==2:time.sleep(5.05)
                return result
            return bill
        raw,lock,_root=self.clock_archive(time.monotonic,wrapped);source.source_lock=lock
        gets=[];getter=source.original
        source.original=lambda:(gets.append(True),getter())[1];raw.hook(source,'ui');source.capture(RUN)
        with lock.held(),self.assertRaises(NativeUIError):source.original()
        self.assertEqual(1,len(native.commands));self.assertEqual(1,len(gets))
        self.assertEqual(1,raw.archive.bill()['receipts'])

    def test_actual_world_acquire_retains_its_original_one_point_five_second_boundary_between_readers(self):
        from self_tests.test_pico_lifecycle_world import Native
        from self_tests.test_pico_openxr_adapter_session import FakeTransport
        from openxr_input.adapter_session import PicoOpenXrAdapterSession
        from adapters.pico4.lifecycle_world import PicoLifecycleWorld
        native=Native()
        def wrapped(namespace):
            def bill():
                result=namespace();time.sleep(.55);return result
            return bill
        raw,lock,root=self.clock_archive(time.monotonic,wrapped)
        session=PicoOpenXrAdapterSession(FakeTransport(),'original-world-clock',root)
        session.begin(BINDING['processIdentity']);readers=native.sources()
        for reader in readers:reader.monotonic=time.monotonic
        world=PicoLifecycleWorld(*readers,session,root/'lifecycle-world-owner.json',RUN,BINDING,
            lambda:native.alive,lock,monotonic=time.monotonic,sleep=time.sleep)
        raw.bind_world(world)
        for reader,role in zip(readers,('ui','gesture','drive')):raw.hook(reader,role)
        with lock.held(),self.assertRaises(NativeUIError):world.acquire()
        self.assertEqual(1,len(native.axes.commands));self.assertEqual(1,len(native.drive.commands))
        self.assertEqual([],native.ui.commands);self.assertEqual(2,raw.archive.bill()['receipts'])

    def test_two_pass_full_physical_namespace_refuses_before_first_json_or_decoder(self):
        native,source=self.source()
        for index in range(90):
            path=self.root/f'lifecycle-x-join.json.frame-{index:03d}.json'
            path.write_bytes(b'x'*65536);path.chmod(0o600)
        with patch('adapters.pico4.lifecycle_namespace_bill.strict') as parser,\
                patch('adapters.pico4.lifecycle_namespace_bill.unpack') as decoder,\
                self.assertRaises(NativeUIError):source.capture(RUN)
        parser.assert_not_called();decoder.assert_not_called();self.assertEqual([],native.commands)

    def test_late_sorted_physical_files_are_charged_before_early_root_decoder(self):
        native,source=self.source()
        root=dict(lifecycleWorldOwnerVersion=2,payload=dict(encoding='zlib-base64-json',bytes=4*1024*1024,
            sha256='f'*64,data='AAAA'))
        PrivateFeatureState(self.root/'lifecycle-world-owner.json').write(root,None)
        from adapters.script_journey.history import canonical
        data=canonical(dict(padding='x'*65000))+b'\n'
        for index in range(70):
            path=self.root/f'lifecycle-x-join.json.frame-{index:03d}.json'
            path.write_bytes(data);path.chmod(0o600)
        with patch('adapters.pico4.lifecycle_namespace_bill.unpack') as decoder,\
                self.assertRaises(NativeUIError):source.capture(RUN)
        decoder.assert_not_called();self.assertEqual([],native.commands)

    def test_exact_canonical_size_preflight_counts_actual_json_dto_types_and_unicode(self):
        from adapters.script_journey.history import canonical
        value={'array':['plain','"\\\x00\b\f\n\r\t\x1f\x7f','é😀',1,-2,1.25,True,None], 'empty':{}}
        self.assertEqual(len(canonical(value)),canonical_size(value))
        for bad in ((1,2),{1:'coerced-key'},float('nan')):
            with self.subTest(bad=bad),self.assertRaises((NativeUIError,ValueError)):canonical_size(bad)

    def test_no_long_lived_literal_or_dto_cache_and_first_original_receipt_never_renews(self):
        native,source=self.source();source.capture(RUN)
        first=self.raw.encode([frame(native.read())]);self.clock=1.
        with self.lock.held():source.original()
        second=self.raw.encode([frame(native.read())])
        self.assertEqual(first,second);self.assertEqual(0,second[0]['source']['read'])
        self.assertEqual(2,self.raw.archive.bill()['receipts']);self.assertFalse(hasattr(self.raw,'frames'))

    def test_foreign_namespace_growth_invalidates_original_budget_lease_before_batch_read(self):
        native,source=self.source();source.capture(RUN);before=self.raw.archive.part_path(0).read_bytes()
        path=self.root/'unowned-growth.json';path.write_bytes(b'{}\n');path.chmod(0o600)
        with self.lock.held(),patch('adapters.pico4.lifecycle_background_raw.os.pread') as read,\
                self.assertRaises(NativeUIError):self.raw.verify()
        read.assert_not_called();self.assertTrue(self.raw.failed)
        self.assertEqual(before,self.raw.archive.part_path(0).read_bytes())
        self.assertEqual(1,len(native.commands))

    def test_replaced_budget_lease_cannot_authorize_batch_allocation(self):
        native,source=self.source();source.capture(RUN);self.namespace.lease=((),())
        with self.lock.held(),patch('adapters.pico4.lifecycle_background_raw.os.pread') as read,\
                self.assertRaises(NativeUIError):self.raw.verify()
        read.assert_not_called();self.assertTrue(self.raw.failed);self.assertEqual(1,len(native.commands))

    def test_full_bill_itself_rejects_equal_byte_replaced_known_root_before_parser_and_next_query(self):
        from adapters.script_journey.history import pack
        store=PrivateFeatureState(self.root/'lifecycle-world-owner.json')
        store.write(dict(lifecycleWorldOwnerVersion=1,payload=pack([{'retained':'existing'}])),None)
        native,source=self.source();source.capture(RUN);replacement=self.root/'same-byte-root'
        replacement.write_bytes(store.path.read_bytes());replacement.chmod(0o600);os.replace(replacement,store.path)
        with self.lock.held(),patch('adapters.pico4.lifecycle_namespace_bill.strict') as parser,\
                self.assertRaises(NativeUIError):self.namespace()
        parser.assert_not_called()
        with self.assertRaises(NativeUIError):source.capture(RUN)
        self.assertEqual(1,len(native.commands))

    def test_full_bill_itself_cannot_adopt_plausible_new_committed_chunk_without_original_writer_receipt(self):
        from adapters.chat_journey.source_chunks import ChatSourceChunks
        from adapters.chat_journey.source_bundles import prepare
        scope=dict(lifecyclePrimaryObservationVersion=3,runId=RUN,binding=BINDING,role='primary')
        store=PrivateFeatureState(self.root/'lifecycle-primary-observation.json')
        root=dict(scope,phase='reading',chunks=[],bundles=[],records=[],pending=None)
        store.write(root,None);history=ChatSourceChunks(store,scope)
        native,source=self.source();source.capture(RUN)
        reference,parts=prepare(frame(native.read()),0,[]);manifest=[]
        for part in parts:manifest=history.append(part,manifest)
        store.write(dict(root,chunks=manifest,bundles=[reference]),root)
        with self.lock.held(),patch('adapters.pico4.lifecycle_namespace_bill.strict') as parser,\
                self.assertRaises(NativeUIError):self.namespace()
        parser.assert_not_called()
        with self.assertRaises(NativeUIError):source.capture(RUN)
        self.assertEqual(1,len(native.commands))

    def actual_session(self):
        from self_tests.test_pico_openxr_adapter_session import FakeTransport
        from openxr_input.adapter_session import PicoOpenXrAdapterSession
        session=PicoOpenXrAdapterSession(FakeTransport(),'existing-mutex-source-boundary',self.root)
        session.begin(BINDING['processIdentity']);return session

    def test_actual_session_lock_refresh_retains_both_physical_stamps_without_source_or_input_authority(self):
        from adapters.chat_journey.archive_file import signature
        session=self.actual_session();native,source=self.source();source.capture(RUN)
        before=signature(session.lock_path.lstat());session.require_process_identity(BINDING['processIdentity'])
        after=signature(session.lock_path.lstat());self.assertEqual(before[:7],after[:7]);self.assertGreater(after[7],before[7])
        with self.lock.held():self.namespace.guard_lease()
        self.assertEqual((session.lock_path.name,tuple(before),tuple(after)),self.namespace.mutex_observations[-1])
        self.assertGreater(self.namespace.metadata_bytes(),2);self.assertEqual(1,len(native.commands))
        # A foreign same-mode ABA on this same empty node is also metadata
        # progress. No claim identifies its actor, SDK effect or input fact.
        session.lock_path.chmod(0o400);session.lock_path.chmod(0o600)
        with self.lock.held():self.namespace.guard_lease()
        self.assertEqual(2,len(self.namespace.mutex_observations));native.alive=False
        with self.assertRaises(NativeUIError):source.capture(RUN)
        self.assertEqual(1,len(native.commands));self.assertEqual(1,self.raw.archive.bill()['receipts'])

    def test_foreign_session_mutex_inode_mode_bytes_mtime_and_other_root_remain_pinned(self):
        for fault in ('inode','mode','bytes','mtime','other-root'):
            with self.subTest(fault=fault):
                fixture=LifecycleBackgroundRawTests();fixture.setUp()
                try:
                    session=fixture.actual_session();native,source=fixture.source();source.capture(RUN);path=session.lock_path
                    if fault=='inode':
                        replacement=path.with_name('foreign-empty-mutex');replacement.write_bytes(b'');replacement.chmod(0o600);os.replace(replacement,path)
                    elif fault=='mode':path.chmod(0o400)
                    elif fault=='bytes':path.write_bytes(b'x')
                    elif fault=='mtime':
                        info=path.stat();os.utime(path,ns=(info.st_atime_ns,info.st_mtime_ns+1000000))
                    else:
                        path=session.state_path;replacement=path.with_name('foreign-same-byte-root')
                        replacement.write_bytes(path.read_bytes());replacement.chmod(0o600);os.replace(replacement,path)
                    with fixture.lock.held(),patch('adapters.pico4.lifecycle_background_raw.os.pread') as read,\
                            self.assertRaises(NativeUIError):fixture.raw.verify()
                    read.assert_not_called();self.assertEqual(1,len(native.commands))
                finally:fixture.doCleanups()

    def test_empty_mutex_observations_are_bounded_charged_and_never_evicted(self):
        from adapters.script_journey.history import MAX_FRAMES
        session=self.actual_session();native,source=self.source();source.capture(RUN)
        with self.lock.held():
            for _ in range(MAX_FRAMES):
                session.require_process_identity(BINDING['processIdentity']);self.namespace.guard_lease()
            admitted=dict(self.namespace._admitted_bill);self.namespace.last['decodedBytes']=0
            self.assertEqual(admitted,dict(self.namespace._admitted_bill))
            session.require_process_identity(BINDING['processIdentity'])
            with patch('adapters.pico4.lifecycle_background_raw.os.pread') as read,self.assertRaises(NativeUIError):self.raw.verify()
        read.assert_not_called();self.assertEqual(MAX_FRAMES,len(self.namespace.mutex_observations))
        self.assertGreater(self.namespace.metadata_bytes(),65536);self.assertEqual(1,len(native.commands))


class LifecycleBackgroundRawOwnerTests(unittest.TestCase):
    def setUp(self):
        fixture=LifecycleChatTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        fixture.owner.open_chat();fixture.owner.focus_chat();fixture.owner.type_chat()
        seams=LifecycleBackgroundOwnerTests();self.seams=seams
        def make():
            self.namespace=LifecycleNamespaceBill(seams.root,seams.lock,
                expanded=lambda:None if getattr(seams,'owner',None) is None else seams.owner.state)
            self.addCleanup(self.namespace.close)
            self.raw=LifecycleBackgroundRaw3(seams.root/'lifecycle-background-raw.json',RUN,
                seams.chat.binding,seams.lock,seams.lock.assert_held,self.namespace,lambda:seams.native.clock)
            self.addCleanup(self.raw.close_host)
            return PicoLifecycleBackground(seams.root/'lifecycle-background-owner.json',RUN,seams.chat.binding,
                seams.lock,seams.status,seams.os_input,seams.runtime,monotonic=lambda:seams.native.clock,
                sleep=seams.sleep,raw_layout=self.raw)
        seams.make=make;seams.initialize_from_chat(fixture)

    def test_original_chat_world_receipts_allow_actual_prepare_with_no_os_input(self):
        seams=self.seams;seams.owner.prepare(seams.chat)
        self.assertEqual('prepared',seams.owner.state['phase']);self.assertEqual([],seams.inputs)
        self.assertEqual(['observe'],[row['operation'] for row in seams.history.commands])
        self.assertEqual(1,len(self.raw.write_gates['chat'].receipts))
        self.assertEqual(1,len(self.raw.write_gates['world'].receipts))
        with seams.lock.held():self.namespace.guard_lease();self.raw.preflight_batch()
        self.assertGreater(self.raw.archive.bill()['receipts'],0)

    def test_default_owner_cannot_bypass_rootless_opt_in_raw_responsibility(self):
        seams=self.seams;before={path.name:path.read_bytes() for path in seams.root.iterdir()}
        with self.assertRaises(NativeUIError):
            PicoLifecycleBackground(seams.root/'lifecycle-background-owner.json',RUN,seams.chat.binding,seams.lock,
                seams.status,seams.os_input,seams.runtime,monotonic=lambda:seams.native.clock,sleep=seams.sleep)
        self.assertEqual(before,{path.name:path.read_bytes() for path in seams.root.iterdir()})
        self.assertEqual([],seams.runtime_calls);self.assertEqual([],seams.inputs)


class LifecycleBackgroundHistoryTests(unittest.TestCase):
    def test_actual_legacy_one_owner_reads_without_live_owner_or_file_rewrites(self):
        seams=LifecycleBackgroundOwnerTests();seams.setUp();self.addCleanup(seams.doCleanups)
        from adapters.chat_journey.archive_file import signature
        def snapshot():return {path.name:(path.read_bytes(),signature(path.lstat())) for path in seams.root.iterdir()}
        before=snapshot();calls=len(seams.runtime_calls)
        history=LifecycleBackgroundHistory(seams.owner.store.path);self.addCleanup(history.close)
        self.assertEqual(1,history.version);self.assertEqual(seams.owner.state,history.read())
        self.assertEqual(calls,len(seams.runtime_calls));self.assertEqual([],seams.inputs);self.assertEqual(before,snapshot())


if __name__=='__main__':unittest.main()
