"""Fresh actual original-file passes reuse numerical codec costs only."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import sys
import time
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from adapters.pico4 import lifecycle_namespace_bill as namespace_module
from adapters.pico4.lifecycle_namespace_bill import canonical_size
from self_tests import test_pico_lifecycle_background_state5 as state5_fixture


class LifecyclePackedCostsTests(unittest.TestCase):
    def setUp(self):
        self.fixture=state5_fixture.LifecycleBackgroundState5Tests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.fixture.prepare();self.namespace=self.fixture.namespace;self.bank=self.fixture.bank
        self.memo=self.bank._capacity_pass;self.lock=self.fixture.seams.lock

    def test_fresh_current_pass_really_omits_codec_calls_but_preserves_every_decoded_bill(self):
        with self.lock.held():
            expected=self.namespace();count=self.bank.archive.state['reads'];calls=[]
            codes=(namespace_module.unpack.__code__,namespace_module.lifecycle_world_codec.unpack.__code__)
            def profiler(frame,event,arg):
                if event=='call' and frame.f_code in codes:calls.append(frame.f_code.co_name)
            previous=sys.getprofile();sys.setprofile(profiler)
            try:actual=self.namespace()
            finally:sys.setprofile(previous)
            self.assertEqual([],calls);self.assertEqual(expected,actual);self.assertGreater(self.memo.root_hits,0)
            # A saturated/no-summary path performs the ORIGINAL full expansion;
            # no decoder/cost function is replaced by this numerical control.
            with patch.object(self.memo,'root_lookup',return_value=(None,None)),patch.object(self.memo,'root_begin',return_value=None):
                previous=sys.getprofile();sys.setprofile(profiler)
                try:control=self.namespace()
                finally:sys.setprofile(previous)
            self.assertTrue(calls);self.assertEqual(control,actual)
            self.assertEqual(count,self.bank.archive.state['reads'])

    def test_root_entry_fixed_metadata_reservation_covers_actual_canonical_row(self):
        with self.lock.held():self.namespace()
        self.assertTrue(self.memo.root_costs)
        for row in self.memo.root_costs:self.assertLessEqual(canonical_size(list(row)),256)
        count=self.memo.memo_count()
        self.assertLessEqual(count,512);self.assertGreaterEqual(self.memo.metadata_bytes(),3*256*count)

    def test_non_ascii_or_oversized_canonical_key_refuses_before_pending_metadata_or_sdk(self):
        with self.lock.held():
            previous=self.memo.root_pending;reads=self.bank.archive.state['reads']
            for name in ('é'*128,'\\'*128):
                with self.assertRaises(NativeUIError):self.memo.root_begin((name,'f'*64,65536))
                self.assertIs(previous,self.memo.root_pending)
            self.assertEqual(reads,self.bank.archive.state['reads'])

    def test_same_byte_cache_tuple_replacement_cannot_reuse_prior_decoded_cost(self):
        with self.lock.held():
            self.namespace();before=self.memo.root_costs;self.memo.root_costs=tuple(list(before))
            self.assertIsNot(before,self.memo.root_costs);reads=self.bank.archive.state['reads']
            with self.assertRaises(NativeUIError):self.bank.current_bill()
            self.assertEqual(reads,self.bank.archive.state['reads'])

    def test_actual_decoder_limit_mutation_refuses_before_next_source_dispatch(self):
        with self.lock.held():
            before=self.bank.archive.state['reads'];commands=len(self.fixture.seams.history.commands)
            codec=namespace_module.lifecycle_world_codec
            with patch.object(codec,'MEMORY_LIMIT',codec.MEMORY_LIMIT+1):
                with self.assertRaises(NativeUIError):self.fixture.owner.runtime[1].read(self.fixture.owner.run)
            self.assertEqual(before,self.bank.archive.state['reads'])
            self.assertEqual(commands,len(self.fixture.seams.history.commands))

    def test_complete_root_summary_metadata_is_preflighted_before_decoder_on_capacity_failure(self):
        with self.lock.held():
            self.namespace();reads=self.bank.archive.state['reads']
            original=self.namespace.capacity_bill
            def exhausted():return original()+16*1024*1024
            # This is the original current capacity callback, not a smaller
            # return value or a decoder bypass. It must refuse before parsing.
            self.namespace.capacity_bill=self.namespace._capacity_bill=exhausted
            with self.assertRaises(NativeUIError):self.namespace()
            self.assertEqual(reads,self.bank.archive.state['reads'])
