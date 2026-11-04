"""Actual-result signature/budget counters; no whole Lifecycle claim."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import marshal
import sys
import unittest
import gc
import weakref
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from adapters.pico4 import lifecycle_background_state5 as module
from adapters.pico4.lifecycle_namespace_bill import canonical_size
from adapters.chat_journey.source_chunks import json_digest
from self_tests import test_pico_lifecycle_background_state5 as state5_fixture


class LifecycleState5SignatureTests(unittest.TestCase):
    def setUp(self):
        self.fixture=state5_fixture.LifecycleBackgroundState5Tests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.fixture.prepare();self.owner=self.fixture.owner;self.bank=self.fixture.bank;self.helper=self.owner.state5
        self.lock=self.fixture.seams.lock
        with self.lock.held():self.row=self.owner.capture()

    def packet(self):
        with self.lock.held():return self.owner.packet(self.row)

    def test_current_actual_packet_is_completely_checked_without_repeated_canonical_work(self):
        self.packet();self.assertTrue(self.helper.results);self.assertTrue(all(row[3] for row in self.helper.results))
        before=self.helper.metadata_bytes();reads=self.bank.archive.state['reads']
        with (patch.object(module,'canonical_size',side_effect=AssertionError('No warm canonical size')),
                patch.object(module,'json_digest',side_effect=AssertionError('No warm canonical hash'))):
            self.assertEqual(before,self.helper.metadata_bytes())
        self.assertEqual(reads,self.bank.archive.state['reads']);self.assertGreater(self.helper._result_seal[2],0)

    def test_changed_actual_packet_uses_original_strict_fallback_without_resealing_and_blocks_next_sdk(self):
        packet=self.packet();seal=self.helper._result_seal;signature=self.helper.results[-1][3]
        packet['ui']['sequence']+=1;calls=[];size=module.canonical_size
        def strict(*args,**kwargs):calls.append(True);return size(*args,**kwargs)
        with self.lock.held(),patch.object(module,'canonical_size',strict):
            reads=self.bank.archive.state['reads'];commands=len(self.fixture.seams.history.commands)
            with self.assertRaises(NativeUIError):self.owner.runtime[1].read(self.owner.run)
        self.assertTrue(calls);self.assertIs(seal,self.helper._result_seal)
        self.assertIs(signature,self.helper.results[-1][3]);self.assertEqual(reads,self.bank.archive.state['reads'])
        self.assertEqual(commands,len(self.fixture.seams.history.commands))

    def test_foreign_metaclass_never_receives_equality_before_exact_type_refusal(self):
        calls=[]
        class Meta(type):
            def __eq__(self,other):calls.append(True);return other is int
        class Foreign(metaclass=Meta):pass
        with self.assertRaises(NativeUIError):module._result_signature(dict(value=Foreign()),32)
        self.assertEqual([],calls)

    def test_large_or_cyclic_metadata_refuses_marshal_before_any_oversized_copy(self):
        circular=[];circular.append(circular)
        with patch.object(module.marshal,'dumps',side_effect=AssertionError('No unsafe marshal')):
            self.assertIsNone(module._result_signature(dict(value='x'*(4*1024*1024)),32))
            self.assertIsNone(module._result_signature(circular,32))
            with self.assertRaises(NativeUIError):module._result_signature(dict(value=b'x'*(4*1024*1024)),32)

    def test_capacity_selection_happens_before_first_actual_marshal_and_keeps_original_result(self):
        original=self.bank.other_bill;calls=[]
        def pressure():
            bill=original();stage=self.helper.active
            if stage is not None and stage.result is not None and not any(row[0] is stage.result for row in self.helper.results):
                bill['decodedBytes']=max(bill['decodedBytes'],16*1024*1024-self.bank.archive.bill()['decodedBytes']-1)
            return bill
        def profile(frame,event,arg):
            if event=='c_call' and arg is marshal.dumps:calls.append(True)
        old=sys.getprofile();sys.setprofile(profile)
        try:
            with patch.object(self.bank,'other_bill',pressure):packet=self.packet()
        finally:sys.setprofile(old)
        self.assertEqual([],calls);self.assertIs(packet,self.helper.results[-1][0]);self.assertIsNone(self.helper.results[-1][3])
        self.assertFalse(self.bank.failed);self.assertIsNone(self.helper.active)

    def test_canonical_unicode_alias_keeps_old_size_sha_even_when_local_signature_differs(self):
        first=['\U0001f600'];alias=['\ud83d\ude00'];size=canonical_size(first)
        self.assertEqual(size,canonical_size(alias));self.assertEqual(json_digest(first),json_digest(alias))
        original=module._result_signature(first,size);self.assertIsNotNone(original)
        self.assertNotEqual(original,module._result_signature(alias,size))

    def test_replaced_signature_codec_is_refused_before_any_next_source_dispatch(self):
        self.packet();reads=self.bank.archive.state['reads'];commands=len(self.fixture.seams.history.commands)
        with self.lock.held(),patch.object(module.marshal,'dumps',side_effect=AssertionError('No replacement codec')):
            with self.assertRaises(NativeUIError):self.owner.runtime[1].read(self.owner.run)
        self.assertEqual(reads,self.bank.archive.state['reads']);self.assertEqual(commands,len(self.fixture.seams.history.commands))

    def test_optional_normalizer_failure_releases_partial_exception_graph_with_gc_disabled(self):
        class Probe:pass
        references=[];original=module._SignatureFallback.__init__
        def tracked(error,*args):
            original(error,*args);error.probe=Probe();references.append(weakref.ref(error.probe))
        value=dict(a=list(range(100)),z='x'*(4*1024*1024))
        enabled=gc.isenabled();gc.disable()
        try:
            with patch.object(module._SignatureFallback,'__init__',tracked):
                self.assertIsNone(module._result_signature(value,32))
            self.assertTrue(references)
            self.assertTrue(all(reference() is None for reference in references))
        finally:
            if enabled:gc.enable()
