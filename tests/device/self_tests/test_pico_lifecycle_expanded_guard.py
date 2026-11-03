"""SAME callback result must contain every actual warm family state object."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from unittest.mock import patch
import unittest

from adapters.normal_ui import NativeUIError
from adapters.pico4.lifecycle_background_owner import PicoLifecycleBackground
from adapters.pico4.lifecycle_namespace_bill import LifecycleNamespaceBill
from adapters.pico4.lifecycle_source_raw import LifecycleSourceRaw4
from self_tests.test_pico_lifecycle_background_owner import LifecycleBackgroundOwnerTests
from self_tests.test_pico_lifecycle_chat import LifecycleChatTests
from self_tests.test_pico_lifecycle_source import RUN


class LifecycleExpandedGuardTests(unittest.TestCase):
    def setUp(self):
        fixture=LifecycleChatTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        fixture.owner.open_chat();fixture.owner.focus_chat();fixture.owner.type_chat()
        seams=LifecycleBackgroundOwnerTests();self.seams=seams;self.mode='current';self.stale=None;self.old_node=None
        def expanded():
            owner=getattr(seams,'owner',None);state=None if owner is None else owner.state
            if self.mode=='missing':return None
            if self.mode=='copy':return deepcopy(state)
            if self.mode=='stale':return self.stale
            if self.mode=='nested':return {'actualOwners':[state]}
            if self.mode=='after-cas' and owner.store.path.stat().st_ino!=self.old_node:return None
            return state
        def make():
            self.namespace=LifecycleNamespaceBill(seams.root,seams.lock,mutex_layout=2,expanded=expanded)
            self.addCleanup(self.namespace.close)
            self.bank=LifecycleSourceRaw4(seams.root/'lifecycle-background-raw.json',RUN,seams.chat.binding,
                seams.lock,seams.lock.assert_held,self.namespace,lambda:seams.native.clock)
            self.addCleanup(self.bank.close_host)
            return PicoLifecycleBackground(seams.root/'lifecycle-background-owner.json',RUN,seams.chat.binding,
                seams.lock,seams.status,seams.os_input,seams.runtime,monotonic=lambda:seams.native.clock,
                sleep=seams.sleep,raw_layout=self.bank)
        seams.make=make;seams.initialize_from_chat(fixture);seams.owner.prepare(seams.chat)

    def test_same_actual_callback_result_accepts_nested_original_state_identity_without_copy_or_requery(self):
        self.mode='nested';before=len(self.seams.native.ui.commands)
        self.seams.world.source.capture(RUN)
        self.assertEqual(before+1,len(self.seams.native.ui.commands))
        self.assertIs(self.seams.owner.state,self.bank.expanded_owner_states()[0])
        self.assertEqual([],self.seams.inputs)

    def test_missing_deepcopied_or_stale_actual_callback_result_refuses_before_next_sdk(self):
        for mode in ('missing','copy','stale'):
            with self.subTest(mode=mode):
                fixture=LifecycleExpandedGuardTests();fixture.setUp()
                try:
                    fixture.stale=deepcopy(fixture.seams.owner.state);fixture.mode=mode
                    before=len(fixture.seams.native.ui.commands);reads=fixture.bank.archive.state['reads']
                    original=fixture.bank.archive.open_data
                    with self.assertRaises(NativeUIError):fixture.seams.world.source.capture(RUN)
                    self.assertEqual(before,len(fixture.seams.native.ui.commands));self.assertEqual(reads,fixture.bank.archive.state['reads'])
                    self.assertEqual(original,fixture.bank.archive.open_data)
                finally:fixture.doCleanups()

    def test_missing_expanded_owner_refuses_before_any_projection_codec_or_owner_cas(self):
        self.mode='missing';view=self.bank.view('background');owner=self.seams.owner
        with (self.seams.lock.held(),patch.object(view,'project',wraps=view.project) as projection,
                patch.object(owner.store,'write',wraps=owner.store.write) as write,self.assertRaises(NativeUIError)):
            owner.save(deepcopy(owner.state))
        projection.assert_not_called();write.assert_not_called();self.assertEqual([],self.seams.inputs)

    def test_actual_cas_then_expanded_omission_retains_root_and_provisional_without_confirmation_or_next_query(self):
        owner=self.seams.owner;view=self.bank.view('background');confirmed=view.confirmed
        self.old_node=owner.store.path.stat().st_ino;self.mode='after-cas'
        with self.seams.lock.held(),self.assertRaises(NativeUIError):owner.save(deepcopy(owner.state))
        self.assertNotEqual(self.old_node,owner.store.path.stat().st_ino);self.assertIs(confirmed,view.confirmed)
        self.assertIsNotNone(view.pending);self.assertIsNotNone(self.namespace._write)
        before=len(self.seams.native.ui.commands)
        with self.assertRaises(NativeUIError):self.seams.world.source.capture(RUN)
        self.assertEqual(before,len(self.seams.native.ui.commands));self.assertFalse(self.bank.close_host())

    def test_guard_or_family_registry_cannot_be_replaced_or_resealed_after_admission(self):
        for fault in ('guard','family'):
            with self.subTest(fault=fault):
                fixture=LifecycleExpandedGuardTests();fixture.setUp()
                try:
                    if fault=='guard':fixture.namespace._expanded_guard=lambda *_:None
                    else:fixture.bank.write_gates.pop('background')
                    before=len(fixture.seams.native.ui.commands)
                    with self.assertRaises(NativeUIError):fixture.seams.world.source.capture(RUN)
                    self.assertEqual(before,len(fixture.seams.native.ui.commands))
                    with self.assertRaises(NativeUIError):fixture.namespace.bind_expanded_guard(fixture.bank)
                finally:fixture.doCleanups()
