"""Normal original Pico X/Home, persistent tablet loader and actual Qt lifetimes.

Standard controller, unrelated Home content, sound and SDK/network/keyboard
services are explicit host endpoints. No physical or whole Assets qualification.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from test_assets_native_ui import compile_ui
import test_assets_cancel_owner as cancel_module
from adapters.pico4.assets_pages import IDENTITIES,LIVENESS
from adapters.pico4 import assets_pages
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_journey.history import pack


class AssetsPageHomeTests(unittest.TestCase):
    setUp=cancel_module.AssetsCancelOwnerTests.setUp
    make=cancel_module.AssetsCancelOwnerTests.make
    cancel_phase=cancel_module.AssetsCancelOwnerTests.cancel_phase
    @classmethod
    def setUpClass(cls):
        cls.build=tempfile.TemporaryDirectory(prefix='pico-assets-page-build-')
        cls.binary,cls.environment,cls.args=compile_ui(cls.build.name,persistent_tablet=True)
    @classmethod
    def tearDownClass(cls):cls.build.cleanup()
    def pointers(self):return json.loads(self.host.request(dict(action='host-original-assets-pointers')))
    def assert_pointers(self,row):
        expected=self.pointers();self.assertEqual({key:row[key] for key in LIVENESS},expected)
    def preserve(self,source,receipt=None):
        destination=os.environ.get('OVERTE_ASSETS_PAGE_EVIDENCE')
        if destination is None:return
        directory=Path(destination).resolve(strict=True);prefix=self._testMethodName
        value=dict(assetsPagesHostEvidenceVersion=1,artifactSha256=self.binding['artifactSha256'],
            sourceOriginals=pack(source.history),independentPointers=self.pointers(),normalChannelReceipt=receipt,
            originalCppBodies=json.loads((Path(self.build.name)/'tablet-original-provenance.json').read_text()))
        PrivateFeatureState(directory/(prefix+'-pages.json')).write(value,None)
        for role,store in (('cancel',self.store),('files',self.file_store)):
            if store.read() is not None:PrivateFeatureState(directory/(prefix+'-'+role+'.json')).write(store.read(),None)
    def test_normal_original_home_retires_page_and_component_preserving_actual_context_and_shared_window(self):
        source=self.host.pages();before=source.capture();self.assertEqual(1,len(before['source']['pages']))
        original=before['source']['pages'][0];self.assert_pointers(original)
        self.assertTrue(all(original[key] for key in LIVENESS));self.assertFalse(before['source']['onHomeScreen'])
        self.owner.open();self.cancel_phase();self.assertTrue(self.owner.cancel()['filesRetired'])
        cancel_state=deepcopy(self.store.read());file_state=deepcopy(self.file_store.read())
        receipt=json.loads(self.host.request(dict(action='host-normal-pico-x')))
        self.assertTrue(receipt['accepted']);self.assertEqual(2,receipt['edges']);self.assertFalse(receipt['held'])
        after=source.capture();row=after['source']['pages'][0];self.assert_pointers(row)
        self.assertTrue(after['source']['onHomeScreen'] and after['source']['tabletShown']);self.assertFalse(row['pageAlive'])
        self.assertEqual({key:original[key] for key in IDENTITIES},{key:row[key] for key in IDENTITIES})
        self.assertTrue(row['windowAlive'] and row['loaderAlive']);self.assertFalse(row['inCurrentTree'] or row['visible'])
        loads=after['source']['qmlLoads'];self.assertEqual([],loads['components'])
        self.assertTrue(set(before['source']['qmlLoads']['retiredComponents'])<set(loads['retiredComponents']))
        self.assertEqual(cancel_state,self.store.read());self.assertEqual(file_state,self.file_store.read())
        history=deepcopy(source.history);cold=self.host.pages();cold.restore(history);self.assertEqual(history,cold.history)
        final=cold.capture();self.assertTrue(final['source']['onHomeScreen']);last=final['source']['pages'][0]
        self.assertEqual({key:row[key] for key in IDENTITIES},{key:last[key] for key in IDENTITIES})
        self.assertTrue(all(row[key] or not last[key] for key in LIVENESS));self.assert_pointers(last)
        self.assertEqual(2,receipt['edges']);self.assertIsNotNone(self.store.read())
        # A surviving valid or invalid context is measured as retained, not deleted
        # or treated as dead merely because the page/component have gone.
        self.preserve(cold,receipt)
    def test_ignored_controller_ack_keeps_actual_original_page_alive(self):
        source=self.host.pages();before=source.capture();request=self.host.request
        def ignore(command):
            if command['action']=='host-normal-pico-x':return '{"accepted":true,"edges":0,"held":false}'
            return request(command)
        with patch.object(self.host,'request',side_effect=ignore):
            receipt=json.loads(self.host.request(dict(action='host-normal-pico-x')))
            self.assertTrue(receipt['accepted']);after=source.capture()
        self.assertFalse(after['source']['onHomeScreen']);row=after['source']['pages'][0];self.assert_pointers(row)
        self.assertTrue(row['pageAlive'] and row['contextAlive']);self.assertEqual(before['source']['pages'],after['source']['pages'])
        self.preserve(source,receipt)
    def test_final_original_copy_aging_with_frozen_native_clock_refuses_publication(self):
        source=self.host.pages();clock=[0];epoch=self.host.epoch_milliseconds();source.monotonic=lambda:clock[0];source.clock_ms=lambda:epoch
        copied=assets_pages.deepcopy;aged=[]
        def delayed(value):
            result=copied(value)
            if type(value) is dict and value.get('assetsPagesVersion')==1 and not aged:aged.append(True);clock[0]+=2
            return result
        with patch.object(assets_pages,'deepcopy',side_effect=delayed),self.assertRaises(NativeUIError):source.capture()
        self.assertTrue(aged);self.assertEqual([],source.history);self.assertIsNone(source.last);self.assertIsNone(source.last_raw)
        self.assertEqual([],self.host.inputs);self.assertTrue(self.pointers()['pageAlive'])


if __name__=='__main__':unittest.main()
