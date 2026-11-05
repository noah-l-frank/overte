"""Actual normal prepare/CAS and graph lifetimes with declared Qt/SDK.

These component tests do not qualify the full born-host BG/Pending3 flow.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
import gc
import weakref
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from adapters.pico4.lifecycle_background_owner import PicoLifecycleBackground
from adapters.pico4.lifecycle_background_raw import LifecycleBackgroundHistory
from adapters.pico4.lifecycle_background_state5 import LifecycleBackgroundState5,OriginalGraph5
from adapters.pico4.lifecycle_family_gate import LifecycleFamilyGate4
from adapters.pico4.lifecycle_namespace_bill import LifecycleNamespaceBill,canonical_size
from adapters.pico4.lifecycle_source_raw import LifecycleSourceRaw4
from self_tests import test_pico_lifecycle_background_owner as background_fixture
from self_tests import test_pico_lifecycle_chat as chat_fixture
from self_tests.test_pico_lifecycle_source import RUN


def raw_frames(value):
    if type(value) is dict:
        if set(value)=={'raw','sha256'}:yield value
        else:
            for child in value.values():yield from raw_frames(child)
    elif type(value) is list:
        for child in value:yield from raw_frames(child)


class LifecycleBackgroundState5Tests(unittest.TestCase):
    QUIET_PERIOD=None
    def setUp(self):
        fixture=chat_fixture.LifecycleChatTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        fixture.owner.open_chat();fixture.owner.focus_chat();fixture.owner.type_chat()
        seams=background_fixture.LifecycleBackgroundOwnerTests();self.seams=seams
        def make():
            self.namespace=LifecycleNamespaceBill(seams.root,seams.lock,mutex_layout=2,
                expanded=lambda:None if getattr(seams,'owner',None) is None else seams.owner.state)
            self.addCleanup(self.namespace.close)
            self.bank=LifecycleSourceRaw4(seams.root/'lifecycle-background-raw.json',RUN,seams.chat.binding,
                seams.lock,seams.lock.assert_held,self.namespace,lambda:seams.native.clock,capacity_batches=True)
            self.addCleanup(self.bank.close_host)
            return PicoLifecycleBackground(seams.root/'lifecycle-background-owner.json',RUN,seams.chat.binding,
                seams.lock,seams.status,seams.os_input,seams.runtime,monotonic=lambda:seams.native.clock,
                sleep=seams.sleep,raw_layout=self.bank,state_layout=5,quiet_period=self.QUIET_PERIOD)
        seams.make=make;seams.initialize_from_chat(fixture);self.owner=seams.owner
        self.assertEqual(0,self.bank.archive.state['reads']);self.assertEqual([],seams.inputs)

    def prepare(self):self.owner.prepare(self.seams.chat)

    def test_existing_normal_prepare_keeps_projected_state_and_lossless_passive5_originals(self):
        self.prepare();owner=self.owner
        self.assertEqual(5,owner.disk['lifecycleBackgroundOwnerVersion']);self.assertEqual('prepared',owner.state['phase'])
        self.assertEqual([],list(raw_frames(owner.state)));self.assertIsNone(owner.state5.active)
        self.assertEqual([],owner.state5.held);self.assertIsNone(owner.state5.save_stage)
        count=self.bank.archive.state['reads'];commands=len(self.seams.history.commands)
        before={p.name:p.read_bytes() for p in self.seams.root.iterdir()}
        passive=LifecycleBackgroundHistory(owner.store.path);self.addCleanup(passive.close)
        expanded=passive.read();self.assertEqual(5,passive.version)
        self.assertTrue(list(raw_frames(expanded)));self.assertGreater(canonical_size(expanded),canonical_size(owner.state))
        self.assertEqual(count,self.bank.archive.state['reads']);self.assertEqual(commands,len(self.seams.history.commands))
        self.assertEqual(before,{p.name:p.read_bytes() for p in self.seams.root.iterdir()})
        self.assertFalse(passive.originals.report()['ownerCASAcknowledgementKnown'])

    def test_validation_stage_is_actually_dead_before_codec_while_actual_save_graph_remains_owned(self):
        created=[];seen=[];construct=OriginalGraph5.__init__;before=LifecycleFamilyGate4.before
        def tracked(stage,*args,**kwargs):construct(stage,*args,**kwargs);created.append((weakref.ref(stage),id(stage.source)))
        def codec(gate,value):
            helper=self.owner.state5
            self.assertIsNone(helper.active);self.assertEqual(1,len(helper.held))
            self.assertIs(helper.save_stage,helper.held[0]);self.assertIs(helper.save_stage.source,value)
            # Identify the actual SAME save value, independently of earlier
            # source projection stages. Its validation child must be dead
            # BEFORE codec entry while the acquired save value stays owned.
            actual=[reference for reference,source_id in created if source_id==id(helper.save_stage.source)]
            self.assertEqual(2,len(actual));self.assertIs(helper.save_stage,actual[0]())
            self.assertIsNone(actual[1]())
            previous=[reference for reference,source_id in created if source_id!=id(helper.save_stage.source)]
            self.assertTrue(previous);self.assertTrue(all(reference() is None for reference in previous))
            seen.append(True);return before(gate,value)
        enabled=gc.isenabled();gc.disable()
        try:
            with patch.object(OriginalGraph5,'__init__',tracked),patch.object(LifecycleFamilyGate4,'before',codec):self.prepare()
        finally:
            if enabled:gc.enable()
        self.assertTrue(seen);self.assertTrue(all(reference() is None for reference,_source_id in created))

    def test_same_phase_cas_uses_confirmed_original_refs_without_any_new_source_query(self):
        self.prepare();sources=self.bank.archive.state['reads'];commands=len(self.seams.history.commands)
        state=deepcopy(self.owner.state);prior=self.owner.disk
        with self.seams.lock.held():self.owner.save(state);self.owner.load();self.namespace.guard_lease()
        self.assertEqual(state,self.owner.state);self.assertEqual(sources,self.bank.archive.state['reads'])
        self.assertEqual(commands,len(self.seams.history.commands));self.assertEqual(2,len(self.bank.write_gates['background'].receipts))
        self.assertEqual(prior['originalChunks'],self.owner.disk['originalChunks']);self.assertEqual([],list(raw_frames(self.owner.state)))

    def test_validation_failure_retains_actual_expanded_graph_and_input_before_any_codec_or_next_sdk(self):
        self.prepare();value=deepcopy(self.owner.state);value['phase']='foreign-phase'
        calls=len(self.seams.history.commands);reads=self.bank.archive.state['reads']
        with self.seams.lock.held(),patch('adapters.pico4.lifecycle_family_gate.pack',side_effect=AssertionError('No codec')):
            with self.assertRaises(NativeUIError):self.owner.save(value)
        helper=self.owner.state5;self.assertTrue(helper.failed);self.assertTrue(self.bank.failed)
        self.assertIs(helper.save_stage.source,value);self.assertTrue(any(stage.graph is not None for stage in helper.held))
        self.assertGreater(helper.metadata_bytes(),canonical_size(value));self.assertFalse(self.bank.close_host())
        with self.seams.lock.held(),self.assertRaises(NativeUIError):self.owner.runtime[1].read(RUN)
        self.assertEqual(calls,len(self.seams.history.commands));self.assertEqual(reads,self.bank.archive.state['reads'])

    def test_capacity_failure_before_expansion_retains_actual_save_input(self):
        self.prepare();value=deepcopy(self.owner.state);sources=self.bank.archive.state['reads']
        full=self.bank.other_bill
        def exhausted():
            bill=full();bill['decodedBytes']=16*1024*1024;return bill
        with self.seams.lock.held(),patch.object(self.bank,'other_bill',exhausted):
            with self.assertRaises(NativeUIError):self.owner.save(value)
        helper=self.owner.state5;self.assertIs(helper.save_stage.source,value)
        self.assertTrue(all(stage.graph is None for stage in helper.held));self.assertEqual(sources,self.bank.archive.state['reads'])
        self.assertFalse(self.bank.close_host())

    def test_actual_prepare_capture_packet_uses_its_original_world_and_valid_source_index(self):
        self.prepare()
        with self.seams.lock.held():
            row=self.owner.capture();count=self.bank.archive.state['reads']
            packets=self.owner.packet(row)
            self.assertEqual(self.owner.pid,packets['ui']['processId'])
            self.assertLess(row['sourceIndex'],len(self.owner.state['sources']))
            self.assertEqual(count,self.bank.archive.state['reads'])
            self.assertEqual([],list(raw_frames(self.owner.state)))
            self.assertTrue(self.owner.state5.results)
            with self.assertRaises(NativeUIError):self.owner.evidence(row)

    def test_unconfirmed_historical_wire_cannot_replace_actual_latest_role_read(self):
        self.prepare()
        with self.seams.lock.held():
            old=self.owner.capture();latest=self.owner.capture()
            latest['world']['ui']=deepcopy(old['world']['ui'])
            count=self.bank.archive.state['reads'];commands=len(self.seams.history.commands)
            with self.assertRaises(NativeUIError):self.owner.packet(latest)
            self.assertTrue(self.bank.failed)
            with self.assertRaises(NativeUIError):self.owner.runtime[1].read(RUN)
            self.assertEqual(count,self.bank.archive.state['reads'])
            self.assertEqual(commands,len(self.seams.history.commands))

    def test_actual_unknown_post_cas_retains_root_and_input_with_old_confirmed_view_and_zero_next_sdk(self):
        self.prepare();view=self.bank.view('background');confirmed=view.confirmed
        before=self.owner.store.path.stat();state=deepcopy(self.owner.state)
        count=self.bank.archive.state['reads'];commands=len(self.seams.history.commands)
        with self.seams.lock.held(),patch.object(self.namespace,'finish_write',side_effect=OSError('Actual post-CAS global receipt failure')):
            with self.assertRaises(OSError):self.owner.save(state)
        after=self.owner.store.path.stat();gate=self.bank.write_gates['background']
        self.assertNotEqual((before.st_dev,before.st_ino),(after.st_dev,after.st_ino))
        self.assertIs(confirmed,view.confirmed);self.assertIsNotNone(view.pending)
        self.assertTrue(self.bank.failed);self.assertTrue(gate.held);self.assertIsNotNone(gate.held[0].root)
        self.assertIs(self.owner.state5.save_stage.source,state)
        with self.seams.lock.held(),self.assertRaises(NativeUIError):self.owner.runtime[1].read(RUN)
        self.assertEqual(count,self.bank.archive.state['reads']);self.assertEqual(commands,len(self.seams.history.commands))
        self.assertFalse(self.bank.close_host())

    def test_mutated_retained_actual_packet_cannot_keep_its_previous_cost_or_authorize_next_sdk(self):
        self.prepare()
        with self.seams.lock.held():
            row=self.owner.capture();packets=self.owner.packet(row)
            count=self.bank.archive.state['reads'];commands=len(self.seams.history.commands)
            packets['ui']['sequence']+=1
            with self.assertRaises(NativeUIError):self.owner.runtime[1].read(RUN)
            self.assertEqual(count,self.bank.archive.state['reads']);self.assertEqual(commands,len(self.seams.history.commands))
        self.assertTrue(self.bank.failed)
