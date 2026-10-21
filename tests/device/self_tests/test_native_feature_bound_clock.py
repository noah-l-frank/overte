"""Opt-in independent native clock fences, without compiling or using devices."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest

from adapters.native_feature_observation import NativeFeatureObservation
from adapters.normal_ui import NativeUIError
from self_tests.test_native_feature_observation import Boundary


class BoundClockTests(unittest.TestCase):
    def reader(self, boundary, clock=None):
        return NativeFeatureObservation(boundary.send, boundary.original,
            clock or (lambda: 20000), boundary.guard, 123, ios=True,
            native_clock_bound=True, monotonic=lambda: boundary.clock, sleep=boundary.sleep)

    def test_original_values_and_nonce_are_preserved_under_independent_clocks(self):
        boundary=Boundary();calls=[]
        def clock():calls.append(20000);return 20000
        reader=self.reader(boundary,clock);value=reader.read(0)
        self.assertEqual(boundary.sample,value)
        self.assertEqual([20000]*3,calls)
        self.assertEqual(20000,reader.captured_epoch)
        self.assertEqual({'schemaVersion','commandId','action'},set(boundary.commands[0]))

    def test_current_nonce_cannot_refresh_a_stale_native_packet(self):
        boundary=Boundary()
        boundary.mutate=lambda value:value.update(capturedEpochMs=18000,requestedEpochMs=18000,animation={},animationFence={})
        with self.assertRaises(NativeUIError):self.reader(boundary).read(0)
        self.assertEqual(1,len(boundary.commands))
        self.assertEqual(18000,boundary.sample['capturedEpochMs'])

    def test_legacy_component_clock_mode_remains_explicitly_compatible(self):
        boundary=Boundary()
        boundary.mutate=lambda value:value.update(capturedEpochMs=18000,requestedEpochMs=18000,animation={},animationFence={})
        self.assertEqual(18000,boundary.reader(ios=True).read(0)['capturedEpochMs'])

    def test_recent_but_pre_request_packet_and_native_future_are_rejected(self):
        for epoch in (19999,20001):
            with self.subTest(epoch=epoch):
                boundary=Boundary()
                boundary.mutate=lambda value:value.update(capturedEpochMs=epoch,requestedEpochMs=epoch,animation={},animationFence={})
                with self.assertRaises(NativeUIError):self.reader(boundary).read(0)

    def test_old_request_stamp_is_not_hidden_by_a_fresh_capture(self):
        boundary=Boundary();boundary.mutate=lambda value:value.update(requestedEpochMs=19999,animation={},animationFence={})
        with self.assertRaises(NativeUIError):self.reader(boundary).read(0)

    def test_late_or_regressing_final_clock_cannot_commit_the_source_cursor(self):
        for epoch in (19999,21501):
            with self.subTest(epoch=epoch):
                boundary=Boundary();values=iter((20000,20000,epoch))
                reader=self.reader(boundary,lambda:next(values))
                with self.assertRaises(NativeUIError):reader.read(0)
                self.assertEqual((0,0),(reader.sequence,reader.captured_epoch))

    def test_clock_transport_and_final_guard_are_inside_the_acquisition_deadline(self):
        for fault in ('initial-slow','final-slow','lost-guard'):
            with self.subTest(fault=fault):
                boundary=Boundary();calls=0
                def clock():
                    nonlocal calls
                    calls+=1
                    if fault=='initial-slow' and calls==1 or fault=='final-slow' and calls==3:boundary.clock+=1.5
                    if fault=='lost-guard' and calls==3:boundary.guard_okay=False
                    return 20000
                reader=self.reader(boundary,clock)
                with self.assertRaises(NativeUIError):reader.read(0)
                self.assertEqual(0,reader.sequence)
                self.assertEqual(0 if fault=='initial-slow' else 1,len(boundary.commands))

    def test_missing_result_expires_without_replaying_an_input(self):
        boundary=Boundary();boundary.ignored=True
        with self.assertRaises(NativeUIError):self.reader(boundary).read(0)
        self.assertEqual(1,len(boundary.commands));self.assertLessEqual(boundary.clock,1.6)

    def test_source_birth_pid_cursor_and_lifecycle_remain_pinned(self):
        for fault in ('birth','pid','cursor','lifecycle'):
            with self.subTest(fault=fault):
                boundary=Boundary();reader=self.reader(boundary);first=reader.read(0)
                def mutate(value):
                    if fault=='birth':value['instance']='b'*32
                    elif fault=='pid':value['processId']=124
                    elif fault=='cursor':value['sequence']=first['sequence']
                    else:value['lifecycle']['activations']=0
                boundary.mutate=mutate
                with self.assertRaises(NativeUIError):reader.read(first['sequence'])
                self.assertEqual(first['sequence'],reader.sequence)

    def test_original_native_day_offset_is_independent_of_host_time(self):
        boundary=Boundary();epoch=20000+86400000
        def native(value):
            value.update(capturedEpochMs=epoch,requestedEpochMs=epoch,animation={},animationFence={})
        boundary.mutate=native;value=self.reader(boundary,lambda:epoch).read(0)
        self.assertEqual(epoch,value['capturedEpochMs'])
        self.assertEqual(boundary.sample,value)

    def test_clock_regression_across_reader_restoration_is_rejected(self):
        boundary=Boundary();reader=self.reader(boundary)
        reader.captured_epoch=20001
        with self.assertRaises(NativeUIError):reader.read(0)

    def test_invalid_opt_in_flags_are_rejected_before_io(self):
        for options in ({'native_clock_bound':1,'ios':True},{'native_clock_bound':True},
                        {'native_clock_bound':True,'ios':'true'}):
            boundary=Boundary()
            with self.assertRaises(NativeUIError):
                NativeFeatureObservation(boundary.send,boundary.original,lambda:20000,boundary.guard,123,**options)
            self.assertEqual([],boundary.commands)
