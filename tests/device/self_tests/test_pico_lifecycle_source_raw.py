"""Real single archive/OFD originals; Qt and SDK producers are declared models.

Owner-CAS admission/confirmation is deliberately NOT claimed by these tests.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from adapters.normal_ui import NativeUIError
from adapters.pico4.lifecycle_back import frame
from adapters.pico4.lifecycle_field_binding import pending_match
from adapters.pico4.lifecycle_namespace_bill import LifecycleNamespaceBill
from adapters.pico4.lifecycle_source_raw import LifecycleSourceRaw4,LifecycleSourceRawHistory4
from adapters.script_journey.lock import ScriptSourceLock
from self_tests.test_pico_lifecycle_field_binding import BoundUi
from self_tests.test_pico_lifecycle_source import RUN
from self_tests.test_pico_lifecycle_world import BINDING


class LifecycleSourceRawTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.root.chmod(0o700)
        self.lock=ScriptSourceLock(self.root/'script-sources.lock')
        self.expanded=None
        self.namespace=LifecycleNamespaceBill(self.root,self.lock,mutex_layout=2,expanded=lambda:self.expanded)
        self.addCleanup(self.namespace.close);self.clock=0.
        self.bank=LifecycleSourceRaw4(self.root/'lifecycle-background-raw.json',RUN,BINDING,
            self.lock,self.lock.assert_held,self.namespace,lambda:self.clock)
        self.addCleanup(self.bank.close_host)
        self.native=BoundUi();self.ui=self.native.bound_source();self.ui.source_lock=self.lock
        self.pending,self.pending_native=self.native.pending()
        self.bank.hook(self.ui,'ui');self.bank.hook(self.pending,'pending')

    def acquire(self):
        ui=self.ui.capture(RUN)
        with self.lock.held():pending=self.pending.read(RUN)
        return ui,pending

    def test_actual_two_readers_share_one_journal_with_distinct_original_clocks_and_same_object_relation(self):
        ui,pending=self.acquire();self.clock=1.
        with self.lock.held():self.pending.read(RUN)
        current=next(row for row in ui['source']['editors'] if row['current'])
        self.assertEqual(current['fieldBinding'],pending_match(current,pending))
        self.assertNotEqual(current['fieldId'],pending['current']['token'])
        self.assertEqual(3,self.bank.archive.state['reads']);self.assertEqual(1,len(self.bank.archive.state['parts']))
        self.assertEqual(4,self.bank.archive.scope['lifecycleSourceRawVersion'])
        with self.lock.held():raws,records=self.bank.verify(materialize=True)
        self.assertEqual(['ui','pending','pending'],[row['role'] for row in records.values()])
        self.assertEqual([0.,0.,1.],[row['hostMonotonic'] for row in records.values()])
        self.assertEqual(self.pending_native.original().encode(),raws[2])
        self.assertEqual([],self.bank.view('background').manifest);self.assertEqual([],self.bank.view('pending').manifest)

    def test_pending_projection_reuses_existing_ui_range_but_never_confirms_owner_or_permits_next_query(self):
        self.acquire();value=[frame(self.ui.last_raw),frame(self.pending.last_raw)]
        view=self.bank.view('pending');projection=view.project(value)
        self.assertEqual(['ui','pending'],[row['role'] for row in projection.encoded])
        self.assertEqual((0,1),tuple(row[2] for row in projection.references))
        self.assertIs(projection.value,value);self.assertEqual([],view.manifest)
        self.assertEqual([],self.bank.view('background').manifest)
        before=len(self.pending_native.commands)
        with self.lock.held(),self.assertRaises(NativeUIError):self.pending.read(RUN)
        self.assertEqual(before,len(self.pending_native.commands));self.assertFalse(self.bank.close_host())

    def test_background_view_cannot_reference_pending_role_even_when_literal_is_an_actual_original(self):
        self.acquire();value=[frame(self.pending.last_raw)];view=self.bank.view('background')
        with self.assertRaises(NativeUIError):view.project(value)
        self.assertIs(view.held[0].value,value);self.assertTrue(self.bank.failed)
        self.assertEqual((),view.confirmed);self.assertFalse(self.bank.close_host())

    def test_unknown_receipt_cas_keeps_acquired_pending_literal_and_does_not_reseal_either_view(self):
        self.ui.capture(RUN);save=self.bank.archive.save
        def uncertain():
            if len(self.bank.archive.open_data)>len(self.ui.last_raw.encode()):raise OSError('uncertain actual Pending receipt CAS')
            return save()
        with self.lock.held(),patch.object(self.bank.archive,'save',side_effect=uncertain),self.assertRaises(NativeUIError):self.pending.read(RUN)
        self.assertEqual(1,len(self.pending_native.commands));self.assertTrue(self.bank.failed)
        self.assertIn(self.pending_native.original().encode(),self.bank.archive.open_data)
        self.assertTrue(all(view.confirmed==() for view in self.bank._views))
        with self.lock.held(),self.assertRaises(NativeUIError):self.pending.read(RUN)
        self.assertEqual(1,len(self.pending_native.commands))

    def test_global_capacity_is_billed_before_pending_send_and_preserves_already_acquired_ui_original(self):
        self.ui.capture(RUN);before=self.bank.archive.open_data
        self.expanded={'oversize':'x'*(16*1024*1024)}
        with self.lock.held(),self.assertRaises(NativeUIError):self.pending.read(RUN)
        self.assertEqual([],self.pending_native.commands);self.assertEqual(before,self.bank.archive.open_data)
        self.assertEqual(1,self.bank.archive.state['reads'])

    def test_same_byte_replaced_original_and_plausible_foreign_file_refuse_before_next_sdk(self):
        for kind in ('part','namespace'):
            with self.subTest(kind=kind):
                fixture=LifecycleSourceRawTests();fixture.setUp()
                try:
                    fixture.ui.capture(RUN)
                    if kind=='part':
                        path=fixture.bank.archive.part_path(0);replacement=fixture.root/'replacement'
                        replacement.write_bytes(path.read_bytes());replacement.chmod(0o600);os.replace(replacement,path)
                    else:(fixture.root/'lifecycle-world-owner.json').write_text('{}\n')
                    with fixture.lock.held(),self.assertRaises(NativeUIError):fixture.pending.read(RUN)
                    self.assertEqual([],fixture.pending_native.commands)
                finally:fixture.doCleanups()

    def test_failed_projection_keeps_exact_acquired_value_before_preflight_and_cannot_reduce_cost(self):
        self.acquire();view=self.bank.view('pending');value=[frame(self.pending.last_raw)]
        with patch.object(self.bank,'other_bill',side_effect=NativeUIError('actual admission refusal')):
            with self.assertRaises(NativeUIError):view.project(value)
        self.assertIs(view.held[0].value,value);self.assertTrue(view.held[0].failed)
        self.assertFalse(self.bank.close_host())

    def test_cold_new4_never_promotes_or_reopens_existing_scope3_or4(self):
        self.acquire();reads=self.bank.archive.state['reads']
        with self.assertRaises(NativeUIError):LifecycleSourceRaw4(self.bank.path,RUN,BINDING,
            self.lock,self.lock.assert_held,self.namespace,lambda:self.clock)
        self.assertEqual(reads,self.bank.archive.state['reads']);self.assertEqual([],self.bank.view('pending').manifest)

    def test_actual_two_roles_use_one_512_read_quota_and_final_refusal_sends_nothing(self):
        self.ui.capture(RUN)
        with self.lock.held():
            for _index in range(511):self.pending.read(RUN)
        self.assertEqual(512,self.bank.archive.state['reads']);self.assertEqual(511,len(self.pending_native.commands))
        with self.assertRaises(NativeUIError):self.ui.capture(RUN)
        self.assertEqual(1,len(self.native.commands));self.assertEqual(512,self.bank.archive.bill()['receipts'])
        history=LifecycleSourceRawHistory4(self.bank.path,RUN,BINDING,[],role='pending');self.addCleanup(history.close)
        self.assertEqual(512,history.report()['durableRawReceipts']);self.assertFalse(history.report()['liveAuthority'])
        self.assertEqual({'ui','pending'},{row['role'] for row in history.archive.receipts.values()})

    def test_mutable_projection_cost_or_hold_cannot_reduce_original_capacity_or_drop_exact_graph(self):
        self.acquire();view=self.bank.view('pending');value=[frame(self.pending.last_raw)]
        projection=view.project(value);before=view.metadata_bytes();projection.peak=0
        self.assertGreaterEqual(view.metadata_bytes(),before)
        projection.value=[]
        with self.assertRaises(NativeUIError):view.metadata_bytes()
        self.assertIs(value,view._held_seal[0][1]);self.assertFalse(self.bank.close_host())

    def test_replaced_view_cost_seal_or_removed_hold_is_rejected_without_new_sdk(self):
        self.acquire();view=self.bank.view('pending');value=[frame(self.pending.last_raw)];view.project(value)
        view.held.clear()
        with self.assertRaises(NativeUIError):view.metadata_bytes()
        self.assertIs(value,view._held_seal[0][1]);self.assertEqual(1,len(self.pending_native.commands))
        self.assertFalse(self.bank.close_host())

    def test_live_and_passive4_refuse_inline_raw_even_when_equal_bytes_exist_in_the_original_pool(self):
        self.acquire();original=frame(self.pending.last_raw)
        with self.assertRaises(NativeUIError):self.bank.decode([original])
        history=LifecycleSourceRawHistory4(self.bank.path,RUN,BINDING,[],role='pending');self.addCleanup(history.close)
        with self.assertRaises(NativeUIError):history.decode([original])
        self.assertEqual(2,history.report()['durableRawReceipts']);self.assertFalse(history.report()['liveAuthority'])

    def test_passive4_mutable_receipt_part_or_cost_cache_cannot_change_reconstruction_or_undercount(self):
        self.acquire()
        for kind in ('receipt','part','cost'):
            with self.subTest(kind=kind):
                history=LifecycleSourceRawHistory4(self.bank.path,RUN,BINDING,[],role='pending');self.addCleanup(history.close)
                if kind=='receipt':history.archive.receipts[0]['sha256']='f'*64
                elif kind=='part':history.archive.recorded_parts[0]=b'x'*len(history.archive.recorded_parts[0])
                else:
                    with self.assertRaises(AttributeError):history.stored_bytes=0
                    history._physical_bill=(history._physical_bill[0],0)
                with self.assertRaises(NativeUIError):history.decode([])
        self.assertEqual(1,len(self.pending_native.commands))

    def test_passive4_complete_namespace_growth_fails_before_decoder_and_preserves_new_original(self):
        self.acquire();history=LifecycleSourceRawHistory4(self.bank.path,RUN,BINDING,[],role='pending')
        self.addCleanup(history.close);foreign=self.bank.path.with_name(self.bank.path.name+'.unknown')
        foreign.write_bytes(b'original foreign tail');foreign.chmod(0o600)
        with self.assertRaises(NativeUIError):history.decode([])
        self.assertEqual(b'original foreign tail',foreign.read_bytes());self.assertEqual(1,len(self.pending_native.commands))


class PendingBeforeIoTests(unittest.TestCase):
    def fixture(self,callback=None):
        from adapters.pending_commit_owner import NativePendingCommitOwner
        from self_tests.test_pending_commit_owner import Boundary
        boundary=Boundary();trace=[]
        def send(value):trace.append('send');boundary.send(value)
        def getter():trace.append('get');return boundary.original()
        def intent(value):trace.append('intent');boundary.intents.append(value)
        owner=NativePendingCommitOwner(send,getter,boundary.epoch,lambda:True,123,
            intent=intent,monotonic=lambda:boundary.clock,sleep=boundary.sleep,before_io=callback)
        return boundary,owner,trace

    def test_callback_runs_after_actual_intent_before_send_and_before_get_with_same_original_anchor(self):
        boundary,owner,trace=self.fixture();anchors=[]
        def callback(started,requested,stage):trace.append('before-'+stage);anchors.append((started,requested))
        owner.bind_before_io(callback);owner.read(RUN);trace.clear();anchors.clear()
        owner.bind_before_send(lambda value:trace.append('phase-cas'))
        owner.operate(RUN,'focus')
        self.assertEqual(['intent','phase-cas','before-send','send','before-get','get'],trace)
        self.assertEqual([(0.,20000),(0.,20000)],anchors)

    def test_actual_slow_callback_with_frozen_native_clock_cannot_send_or_get_after_original_five_seconds(self):
        for refused in ('send','get'):
            with self.subTest(stage=refused):
                boundary,owner,trace=self.fixture()
                owner.clock_ms=lambda:20000
                def callback(started,requested,stage):
                    if stage==refused:boundary.clock=5.
                owner.bind_before_io(callback)
                with self.assertRaises(NativeUIError):owner.read(RUN)
                self.assertEqual(int(refused=='get'),len(boundary.commands));self.assertNotIn('get',trace)

    def test_replaced_callback_is_never_resealed_and_refuses_before_intent_or_sdk(self):
        boundary,owner,trace=self.fixture(lambda *_:None);owner.before_io=lambda *_:None
        with self.assertRaises(NativeUIError):owner.read(RUN)
        with self.assertRaises(NativeUIError):owner.bind_before_io(lambda *_:None)
        self.assertEqual([],trace);self.assertEqual([],boundary.intents)

    def test_none_replacement_inside_phase_guard_cannot_skip_admitted_callback(self):
        boundary,owner,trace=self.fixture(lambda *_:None);owner.read(RUN);trace.clear()
        owner.bind_before_send(lambda _value:setattr(owner,'before_io',None))
        with self.assertRaises(NativeUIError):owner.operate(RUN,'focus')
        self.assertEqual(['intent'],trace);self.assertEqual(1,len(boundary.commands))

    def test_one_time_hook_cannot_install_after_success_or_failed_first_exchange(self):
        for fail in (False,True):
            boundary,owner,trace=self.fixture();boundary.fault='ignored' if fail else ''
            if fail:
                with self.assertRaises(NativeUIError):owner.read(RUN)
            else:owner.read(RUN)
            with self.assertRaises(NativeUIError):owner.bind_before_io(lambda *_:None)

    def test_acquired_malformed_raw_is_retained_by_raw4_before_original_pending_parser_rejects(self):
        fixture=LifecycleSourceRawTests();fixture.setUp()
        try:
            fixture.pending_native.edit=lambda value:value.update(processId=999)
            with fixture.lock.held(),self.assertRaises(NativeUIError):fixture.pending.read(RUN)
            self.assertEqual(1,len(fixture.pending_native.commands));self.assertEqual(1,fixture.bank.archive.state['reads'])
            self.assertEqual(fixture.pending_native.original().encode(),fixture.bank.archive.open_data)
        finally:fixture.doCleanups()
