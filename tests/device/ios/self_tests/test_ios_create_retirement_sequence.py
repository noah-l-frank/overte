"""Actual retained history/retirement cursor continuity, without native resets."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from types import SimpleNamespace
from adapters.native_clock_join import digest
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack,unpack
from ios.self_tests import test_ios_create_retirement as fixture
from ios.self_tests.test_ios_create_primary_images import ClockedSDK
from ios.self_tests.test_ios_create_state import EPOCH


class RetirementSequenceTests(unittest.TestCase):
    def setUp(self):
        self.h=fixture.CreateRetirementTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
        clock=SimpleNamespace(clock=max(self.h.h.primary_h.sdk.clock,self.h.h.peer_h.sdk.clock))
        clock.epoch=lambda:EPOCH+round(clock.clock*1000)
        for harness in (self.h.h.primary_h,self.h.h.peer_h):harness.sdk.shared=clock;harness.sdk.__class__=ClockedSDK
    def test_public_cursor_spans_actual_history_and_new_retirement_originals_without_changing_native_counters(self):
        with self.h.h.held():
            facts,owner=self.h.admitted();original=owner.cleanup('2'*32);first=owner.validate_original(original)
            self.assertEqual(len(facts.state['records'])+len(owner.state['records']),first['public']['sequence'])
            native=deepcopy(owner.frame(owner.state['records'][-1])['clockJoin']['nativeAfter'])
            facts.capture(marker_active=False);second=owner.refresh();measured=owner.validate_original(second)
            self.assertEqual(len(facts.state['records'])+len(owner.state['records']),measured['public']['sequence'])
            self.assertGreater(measured['public']['sequence'],first['public']['sequence'])
            self.assertEqual(native,owner.frame(owner.state['records'][-2])['clockJoin']['nativeAfter'])
    def test_a_genuine_older_history_original_cannot_replace_the_prefix_after_a_newer_one_was_retained(self):
        with self.h.h.held():
            facts,owner=self.h.admitted();owner.cleanup('2'*32)
            old=deepcopy(owner.frame(owner.state['records'][-1])['components']['history'])
            facts.capture(marker_active=False);owner.refresh();owner.refresh()
            ref=owner.state['records'][-1];carrier=owner.record_store(ref['index']);packet=carrier.read();frame=unpack(packet['payload'])[0]
            native=deepcopy(frame['clockJoin']);frame['components']['history']=old;packet['payload']=pack([frame]);carrier.write(packet,carrier.read())
            state=deepcopy(owner.state);state['records'][-1]=dict(index=ref['index'],sha256=digest(packet))
            self.assertEqual(native,unpack(carrier.read()['payload'])[0]['clockJoin'])
            with self.assertRaises(NativeUIError):owner.decode(owner.envelope(state))


if __name__=='__main__':unittest.main()
