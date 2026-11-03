"""Actual raw request/getter/parser ordering; no G1/device acceptance claim."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import json
import random
import unittest
from unittest.mock import patch

from adapters.native_navigation_environment import NativeNavigationEnvironment
from adapters.normal_ui import NativeUIError
from adapters.pico4.navigation_scene_generation import NavigationSceneEnvironment
from adapters.script_journey.history import pack
from self_tests.test_pico_navigation_scene_prefix import NavigationScenePrefixTests
from self_tests import test_pico_navigation_prefix as prefix


class NavigationSceneRawTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):NavigationScenePrefixTests.setUpClass()
    @classmethod
    def tearDownClass(cls):NavigationScenePrefixTests.tearDownClass()
    def setUp(self):
        self.f=NavigationScenePrefixTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.owner=self.f.owner;self.model=self.f.f.model;self.returns=[];self.getters=[]
        self.value=None;self.expire=False;self.lose_parent=False
        def getter():
            self.getters.append(True);raw=json.dumps(self.model.packet) if self.value is None else self.value
            if self.expire:self.model.clock=self.owner.deadline+.001
            if self.lose_parent:self.owner.store.path.unlink()
            return raw
        self.environment=NativeNavigationEnvironment(self.model.source_send,getter,self.model.epoch,self.model.guard,prefix.PID,
            monotonic=lambda:self.model.clock,sleep=self.model.sleep)
        self.channel=NavigationSceneEnvironment(self.owner,self.environment,self.f.f.binding,
            lambda reference,request:self.returns.append((reference,request)))
    def reference(self):
        row=self.owner.raw.pages[0]['receipts'][0]
        return dict(audioRawRangeVersion=1,scopeSha256=self.owner.raw.scope_sha,read=0,sha256=row['sha256'])
    def test_permitted_quarter_mib_incompressible_nul_literal_is_durable_before_actual_native_parser(self):
        rng=random.Random(773);self.value=''.join(chr(rng.randrange(128)) for _ in range(262144))
        self.assertIn('\0',self.value)
        with self.assertRaises(NativeUIError):pack([dict(raw=self.value)])
        parsed=[]
        def parser(raw):
            self.assertEqual(self.value,raw);self.assertEqual(self.value,self.owner.raw.literal(self.returns[-1][0]))
            parsed.append(True);raise RuntimeError('Actual parser boundary stops after archival proof')
        with patch('adapters.native_navigation_environment.decode',side_effect=parser),self.assertRaises(NativeUIError):self.environment.read(prefix.RUN)
        self.assertEqual([True],parsed);self.assertEqual(1,len(self.getters));self.assertEqual(1,self.owner.raw.bill()['receipts'])
        self.assertEqual([],self.owner.raw.state['pending']);self.assertEqual(hashlib.sha256(self.value.encode()).hexdigest(),self.returns[0][0]['sha256'])
    def test_actual_late_return_and_lost_parent_return_archive_without_parser_or_new_getter(self):
        self.expire=True
        with patch('adapters.native_navigation_environment.decode') as parser,self.assertRaises(NativeUIError):self.environment.read(prefix.RUN)
        parser.assert_not_called();self.assertEqual([],self.returns)
        self.assertEqual(json.dumps(self.model.packet),self.owner.raw.literal(self.reference()))
        with self.assertRaises(NativeUIError):self.environment.read(prefix.RUN)
        self.assertEqual(1,len(self.getters));self.assertEqual(1,self.model.source_sequence)
    def test_actual_lost_business_header_retains_original_raw_root_and_zero_new_source(self):
        self.lose_parent=True
        with patch('adapters.native_navigation_environment.decode') as parser,self.assertRaises(NativeUIError):self.environment.read(prefix.RUN)
        parser.assert_not_called();self.assertEqual(json.dumps(self.model.packet),self.owner.raw.literal(self.reference()))
        with self.assertRaises(NativeUIError):self.environment.read(prefix.RUN)
        self.assertEqual(1,len(self.getters));self.assertEqual(1,self.owner.raw.bill()['receipts'])
    def test_aggregate_cap_refuses_actual_send_and_getter_without_new_budget(self):
        for index in range(512):
            path=self.f.f.root/f'other-original.part-{index:03d}.bin';path.write_bytes(b'original');path.chmod(0o600)
        with self.assertRaises(NativeUIError):self.environment.read(prefix.RUN)
        self.assertEqual([],self.getters);self.assertEqual(0,self.model.source_sequence);self.assertEqual([],self.owner.raw.state['pending'])


if __name__=='__main__':unittest.main()
