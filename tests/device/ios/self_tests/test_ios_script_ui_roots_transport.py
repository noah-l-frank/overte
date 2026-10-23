"""Existing NativeInput transport joins real emitted parent/weak-model packets."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.adapters import normal_input
from ios.self_tests.test_ios_normal_input import Boundary
from ios.self_tests.world_web_ui_roots_fixture import Root,RootCensus
from self_tests.test_script_ui_inventory import inventory
from self_tests.test_script_manager_status import observed


class ScriptUiRootsTransportTests(unittest.TestCase):
    def boundary(self,version=2,fault=None):
        census=RootCensus();root=Root('manager');identity=census.observe(root)
        class Native(Boundary):
            def observed(self):
                # These are explicitly modeled native producers. Both fresh
                # components are composed before their original JSON emission.
                value=super().observed();source=census.source();epoch=source['capturedEpochMs']
                manager=observed(componentSource=root.source,rootVisible=False,labelVisible=False)
                inv=inventory([manager],tabletShown=False)
                if version==2:
                    if fault=='pid':source['processId']=53
                    elif fault=='clock':source['capturedEpochMs']-=2000
                    inv.update(inventoryVersion=2,rootOwnership=source,rootMembership=dict(managers=[identity],pickers=[]))
                value.update(processId=31,sampleEpochMs=epoch,scriptObservationVersion=1,scriptSourceSequence=census.sequence,scriptInventory=inv)
                return value
        native=Native();native.pid=31
        reader=normal_input.NativeInput(native,'owned-session',native.target,native.process,monotonic=native.tick,
            sleep=lambda _seconds:None,native_epoch_ms=lambda:20000+census.elapsed)
        return native,reader

    def test_actual_original_reader_preserves_literal1_and_joins_current2_to_the_parent_native_clock(self):
        for version in (1,2):
            with self.subTest(version=version):
                native,reader=self.boundary(version)
                with patch.object(normal_input,'urlopen',native.post):value=reader.capture()
                self.assertEqual(version,value['scriptInventory']['inventoryVersion'])
                self.assertEqual(31,value['processId'])
                if version==1:self.assertNotIn('rootOwnership',value['scriptInventory'])
                else:self.assertTrue(value['scriptInventory']['rootOwnership']['roots'][0]['weakAlive'])

    def test_foreign_or_old_nested_root_original_cannot_hide_inside_a_fresh_native_parent(self):
        for fault in ('pid','clock'):
            with self.subTest(fault=fault):
                native,reader=self.boundary(fault=fault)
                with patch.object(normal_input,'urlopen',native.post),self.assertRaises(NativeUIError):reader.capture()
