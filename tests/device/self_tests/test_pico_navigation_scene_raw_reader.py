"""Actual native reader/send/get/parser with one existing Navigation raw bill."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import random
import unittest
from unittest.mock import patch

from adapters.native_feature_observation import NativeFeatureObservation
from adapters.normal_ui import NativeUIError
from adapters.pico4.navigation_scene_raw_reader import NavigationSceneRawReader
from self_tests.test_pico_navigation_scene_prefix import NavigationScenePrefixTests
from self_tests import test_pico_navigation_prefix as prefix


class NavigationSceneRawReaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):NavigationScenePrefixTests.setUpClass()
    @classmethod
    def tearDownClass(cls):NavigationScenePrefixTests.tearDownClass()
    def setUp(self):
        self.f=NavigationScenePrefixTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.owner=self.f.owner;self.model=self.f.f.model;self.producer=self.f.f.world.features
        self.sends=[];self.getters=[];self.returns=[];self.literal=None;self.delay=0;self.lose=False
        def send(command):self.sends.append(command);return self.producer.send(command)
        def get():
            raw=self.producer.original() if self.literal is None else self.literal;self.getters.append(raw)
            self.model.clock+=self.delay
            if self.lose:self.owner.path.unlink()
            return raw
        self.reader=NativeFeatureObservation(send,get,self.model.epoch,self.model.guard,prefix.PID,
            monotonic=lambda:self.model.clock,sleep=self.model.sleep)
        self.channel=NavigationSceneRawReader(self.owner,self.reader,self.f.f.binding,'navigation-native-test',self.owner.bound,
            lambda reference,request:self.returns.append((reference,request)))
    def read(self):
        with self.f.f.lock.held():return self.reader.read(0)
    def reference(self):
        row=self.owner.raw.pages[0]['receipts'][0]
        return dict(audioRawRangeVersion=1,scopeSha256=self.owner.raw.scope_sha,read=0,sha256=row['sha256'])
    def test_legal_incompressible_nul_literal_is_durable_before_actual_native_parser_boundary(self):
        rng=random.Random(417);self.literal=''.join(chr(rng.randrange(128)) for _ in range(262144));self.assertIn('\0',self.literal)
        parsed=[]
        def parser(raw):
            self.assertEqual(self.literal,raw);self.assertEqual(raw,self.owner.raw.literal(self.returns[-1][0]))
            parsed.append(True);raise RuntimeError('Stop after actual parser archival counter')
        with patch('adapters.native_feature_observation.decode',side_effect=parser),self.assertRaises(NativeUIError):self.read()
        self.assertEqual([True],parsed);self.assertEqual(1,len(self.sends));self.assertEqual(1,len(self.getters))
        self.assertEqual(1,self.owner.raw.bill()['receipts']);self.assertEqual([],self.owner.raw.state['pending'])
    def test_raw_admission_cost_expiring_original_query_prevents_actual_send(self):
        reserve=self.owner.raw.reserve
        def delayed(*args,**kwargs):
            token=reserve(*args,**kwargs);self.model.clock+=5.001;return token
        with patch.object(self.owner.raw,'reserve',side_effect=delayed),self.assertRaises(NativeUIError):self.read()
        self.assertEqual([],self.sends);self.assertEqual([],self.getters);self.assertEqual(1,len(self.owner.raw.state['pending']))
    def test_lost_parent_after_reservation_prevents_actual_send(self):
        reserve=self.owner.raw.reserve
        def lost(*args,**kwargs):
            token=reserve(*args,**kwargs);self.owner.path.unlink();return token
        with patch.object(self.owner.raw,'reserve',side_effect=lost),self.assertRaises(NativeUIError):self.read()
        self.assertEqual([],self.sends);self.assertEqual([],self.getters);self.assertEqual(1,len(self.owner.raw.state['pending']))
    def test_issued_late_query_return_is_retained_without_parser_or_later_getter(self):
        self.delay=5.001
        with patch('adapters.native_feature_observation.decode') as parser,self.assertRaises(NativeUIError):self.read()
        parser.assert_not_called();self.assertEqual(self.getters[0],self.owner.raw.literal(self.reference()))
        with self.assertRaises(NativeUIError):self.read()
        self.assertEqual(1,len(self.getters));self.assertEqual(1,len(self.sends))
    def test_issued_lost_parent_return_is_retained_before_business_rejection(self):
        self.lose=True
        with patch('adapters.native_feature_observation.decode') as parser,self.assertRaises(NativeUIError):self.read()
        parser.assert_not_called();self.assertEqual(self.getters[0],self.owner.raw.literal(self.reference()))
        with self.assertRaises(NativeUIError):self.read()
        self.assertEqual(1,len(self.getters));self.assertEqual(1,len(self.sends))
    def test_aggregate_part_cap_refuses_before_actual_native_send_and_getter(self):
        for index in range(512):
            path=self.f.f.root/f'other-source.part-{index:03d}.bin';path.write_bytes(b'original');path.chmod(0o600)
        with self.assertRaises(NativeUIError):self.read()
        self.assertEqual([],self.sends);self.assertEqual([],self.getters);self.assertEqual([],self.owner.raw.state['pending'])
    def test_original_read_callback_replacement_is_refused_before_source_io(self):
        self.reader.original=lambda:'{}'
        with self.assertRaises(NativeUIError):self.read()
        self.assertEqual([],self.sends);self.assertEqual([],self.getters)


if __name__=='__main__':unittest.main()
