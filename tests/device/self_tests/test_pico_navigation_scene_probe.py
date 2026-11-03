"""Actual SDK/framed producer probe inside the SAME pre-mutation scene lease."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import unittest
from unittest.mock import patch

from adapters.android.adapter import AndroidAdapter
from adapters.normal_ui import NativeUIError
from adapters.pico4.probe_originals import HEADER
from self_tests.test_pico_navigation_scene_prefix import NavigationScenePrefixTests


class NavigationSceneProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):NavigationScenePrefixTests.setUpClass()
    @classmethod
    def tearDownClass(cls):NavigationScenePrefixTests.tearDownClass()
    def setUp(self):
        self.f=NavigationScenePrefixTests();self.f.use_probe_sdk=True;self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.owner=self.f.owner;self.model=self.f.f.model;self.producer=self.f.f.world.navigation_probe_producer
    def test_actual_sdk_wire_is_retained_in_original_c_lease_before_every_normal_mutation(self):
        with self.f.f.lock.held():self.owner.original_lease()
        lease=self.owner.lease();reader=self.owner.probe_bindings[0][1]
        self.assertIs(AndroidAdapter.read_probe_snapshot,reader.reader.__func__)
        self.assertEqual(1,self.owner.scope['probeOriginalsVersion']);self.assertEqual(1,self.producer.calls)
        reference=json.loads(reader.receipts[0]);wire=self.owner.raw.literal(reference)
        self.assertTrue(wire.startswith(HEADER));self.assertEqual(self.producer.last_wire,wire)
        self.assertIn(reference,lease['raw']);self.assertEqual(self.f.f.world.current_scene_url,lease['originalUrl'])
        self.assertEqual([],self.model.calls);self.assertEqual([],self.model.controller_calls)
    def test_both_actual_role_probe_readers_are_bound_before_source_acquisition(self):
        self.owner.prepare();self.owner.observe('primary');self.owner.observe('actor')
        self.assertEqual(3,len(self.owner.probe_bindings))
        self.assertEqual(['primary','primary','actor'],[value[-1] for value in self.owner.probe_bindings])
        for _arrival,reader,_callback,_guard,_adapter,_target,_role in self.owner.probe_bindings:
            self.assertTrue(reader.receipts);self.assertIs(reader.archive,self.owner.raw)
            self.assertTrue(self.owner.raw.literal(json.loads(reader.receipts[-1])).startswith(HEADER))
        self.assertFalse(self.model.shown);self.assertLessEqual(self.owner.bill()['parts'],512)
    def test_foreign_sdk_callback_is_refused_before_any_binary_probe_or_input(self):
        reader=self.owner.probe_bindings[0][1];reader.adapter.read_probe_snapshot=lambda *_args,**_kwargs:{}
        with self.assertRaises(NativeUIError):self.owner.prepare()
        self.assertEqual(0,self.producer.calls);self.assertEqual([],self.model.calls);self.assertEqual([],self.model.controller_calls)
    def test_issued_late_actual_wire_remains_durable_before_sdk_parser_without_new_probe(self):
        self.producer.post=lambda:setattr(self.model,'clock',self.owner.deadline+.001)
        with self.assertRaises(NativeUIError):self.owner.prepare()
        reader=self.owner.probe_bindings[0][1]
        self.assertEqual(1,self.producer.calls);self.assertTrue(reader.failed);self.assertIsNone(reader.last_body)
        self.assertEqual(self.producer.last_wire,self.owner.raw.literal(json.loads(reader.receipts[-1])))
        with self.assertRaises(NativeUIError):self.owner.prepare()
        self.assertEqual(1,self.producer.calls);self.assertEqual([],self.model.calls);self.assertEqual([],self.model.controller_calls)


if __name__=='__main__':unittest.main()
