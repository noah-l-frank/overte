"""Durable normal Assets Cancel joined to one actual Qt/native process.

Installation/SDK, fixture transport, server protocol/cache and keyboard device
are explicit host boundaries; no physical or server/oven qualification.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from test_assets_native_ui import compile_ui
SPEC=importlib.util.spec_from_file_location('assets_live_host',Path(__file__).with_name('assets-live-host.py'))
LIVE=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(LIVE)
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_journey.history import unpack
from adapters.normal_ui import NativeUIError
from adapters.pico4.assets_cancel_owner import OwnedAssetsCancel
from adapters.pico4.assets_file_owner import OwnedAssetsFiles
from adapters.pico4.navigation import NativeNavigationIO,NavigationError
from feature_journeys.witness import Client,Journal
from feature_journeys.phase_fixture import PhaseFixtureReader

class OriginalPhaseClient(Client):
    def __init__(self,journal,run):super().__init__('http://127.0.0.1:1/feature-fixture/v1','h'*32);self.journal=journal;self.run=run
    def request(self,path,value=None,method=None,*,phase_nonce=None,**options):
        assert path=='/runs/'+self.run+'/phase' and value is None and phase_nonce is not None
        return self.journal.phase(self.run,phase_nonce)

class AssetsCancelOwnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build=tempfile.TemporaryDirectory(prefix='pico-assets-cancel-build-');cls.binary,cls.environment,cls.args=compile_ui(cls.build.name)
    @classmethod
    def tearDownClass(cls):cls.build.cleanup()
    def setUp(self):
        self.directory=tempfile.TemporaryDirectory(prefix='pico-assets-cancel-owner-');self.addCleanup(self.directory.cleanup)
        self.path=Path(self.directory.name);self.host=LIVE.AssetsLiveHost(self.binary,self.environment,self.args,self.path);self.addCleanup(self.host.close)
        current=self.host.navigation.snapshot();self.binding=dict(sourceRevision='f8cd43a02da492fc326f3f86ccebcfd223d3bacf',
            artifactSha256=hashlib.sha256(Path(self.binary).read_bytes()).hexdigest(),processIdentity=self.host.identity,
            sessionId=current['bridgeId'],generation=0,targetFingerprint='d'*64)
        self.journal=Journal();self.run=self.journal.register('assets');self.openTicket='1'*32
        self.journal.activate(self.run,self.openTicket,'upload-picker-open',{'resource':'gltf-bundle/main.gltf'})
        self.client=OriginalPhaseClient(self.journal,self.run);self.url=self.client.url+'/runs/'+self.run+'/'
        self.store=PrivateFeatureState(self.path/'cancel.json');self.file_store=PrivateFeatureState(self.path/'files.json');self.make()
    def make(self):
        files=OwnedAssetsFiles(self.host.files(),self.file_store,self.binding,self.run,self.openTicket,self.url)
        self.owner=OwnedAssetsCancel(self.store,self.binding,self.run,self.url,files,self.host.mappings(),self.host.uploads(),
            self.host.io.original.capture,self.host.controls,PhaseFixtureReader(self.client,self.run,'assets'),self.host.guard,self.host.epoch_milliseconds)
    def cancel_phase(self):self.journal.activate(self.run,'2'*32,'upload-picker-cancel',{})
    def test_normal_cancel_exact_files_originals_and_retained_contexts(self):
        self.assertTrue(self.owner.open()['pickerObserved']);self.cancel_phase();result=self.owner.cancel()
        self.assertTrue(result['cancelObserved']);self.assertTrue(result['filesRetired']);self.assertTrue(result['retained'])
        archive=unpack(self.store.read()['inputs']);self.assertEqual(self.host.inputs,[frame['native'] for frame in archive])
        self.assertTrue(all(frame['after'] is not None for frame in archive));self.assertTrue(unpack(self.store.read()['uiOriginals']))
        self.assertEqual('cancel-observed-files-retired',self.store.read()['phase']);self.assertEqual('retired',self.file_store.read()['phase'])
        self.assertIsNotNone(self.store.read());self.assertFalse(result['browser']['rootAlive']);self.assertFalse(result['browser']['modelAlive'])
        self.assertEqual(1,sum(command['controlId']=='assets-file.cancel' for command in self.host.inputs))
        cold=self.host.uploads();cold.restore(self.owner.uploads.history)
        self.assertEqual(self.owner.uploads.history,cold.history);self.assertEqual(0,cold.last['source']['totalCalls'])
    def test_lost_cancel_reply_cold_reconcile_never_replays_original_input(self):
        self.owner.open();self.cancel_phase();self.host.lose=True
        with self.assertRaises((NativeUIError,NavigationError)):self.owner.cancel()
        self.host.lose=False;count=len(self.host.inputs);original=deepcopy(self.store.read()['pendingInput']);self.make()
        result=self.owner.reconcile();self.assertTrue(result['filesRetired']);self.assertEqual(count,len(self.host.inputs))
        self.assertEqual(original,self.store.read()['pendingInput']);self.assertIsNotNone(original['native']);self.assertIsNotNone(self.store.read())
    def test_undelivered_cancel_is_retained_with_live_consumers_and_original_bytes(self):
        self.owner.open();self.cancel_phase();self.host.fail_send=True
        with self.assertRaises((NativeUIError,NavigationError)):self.owner.cancel()
        self.host.fail_send=False;count=len(self.host.inputs);original=deepcopy(self.store.read()['pendingInput']);self.make()
        result=self.owner.reconcile();self.assertFalse(result['cancelObserved']);self.assertEqual(count,len(self.host.inputs))
        self.assertEqual('ready',self.file_store.read()['phase']);self.assertEqual(original,self.store.read()['pendingInput'])
        self.assertTrue(all(row['exists'] for row in self.owner.files.read()['source']['files']))
    def test_lost_navigation_reply_uses_admitted_originals_and_distinct_cancel(self):
        send=self.host.write_debug_app_file;admitted=None
        def lose_navigation(target,package,path,raw):
            nonlocal admitted
            import json
            command=json.loads(raw)
            if command['controlId']=='assets-file.folder' and command['action']=='replace':
                admitted=deepcopy(self.store.read())
                self.assertIsNotNone(admitted['browserId']);self.assertIsNotNone(admitted['modelId'])
                original=unpack(admitted['uiOriginals'])[-1]['assetsUiInventory']['browsers'][0]
                self.assertEqual((original['id'],original['modelId']),(admitted['browserId'],admitted['modelId']))
                self.assertTrue(original['rootAlive'] and original['modelAlive'])
                self.host.lose=True
            return send(target,package,path,raw)
        with patch.object(self.host,'write_debug_app_file',side_effect=lose_navigation),self.assertRaises((NativeUIError,NavigationError)):
            self.owner.open()
        self.assertIsNotNone(admitted);self.host.lose=False
        pending=deepcopy(self.store.read()['pendingInput']);prefix=deepcopy(self.host.inputs)
        self.assertEqual('replace',pending['native']['action']);self.assertEqual('assets-file.folder',pending['native']['controlId'])
        originals=unpack(self.store.read()['inputs']);self.make();self.cancel_phase();result=self.owner.cancel()
        self.assertTrue(result['cancelObserved'] and result['filesRetired']);state=self.store.read()
        self.assertEqual([pending],state['unresolvedInputs']);self.assertEqual(originals,unpack(state['inputs'])[:len(originals)])
        self.assertEqual(prefix,self.host.inputs[:-1]);self.assertEqual('assets-file.cancel',self.host.inputs[-1]['controlId'])
        self.assertNotEqual(pending['native']['commandId'],self.host.inputs[-1]['commandId'])
        self.assertEqual((admitted['browserId'],admitted['modelId']),(result['browser']['id'],result['browser']['modelId']))
        self.assertFalse(result['browser']['rootAlive'] or result['browser']['modelAlive']);self.assertEqual('retired',self.file_store.read()['phase'])
        self.assertEqual(0,self.owner.uploads.last['source']['totalCalls']);self.assertIsNotNone(state)
    def test_lost_first_open_reply_cancel_retains_files_without_adoption(self):
        self.host.lose=True
        with self.assertRaises((NativeUIError,NavigationError)):self.owner.open()
        self.host.lose=False;state=self.store.read();pending=deepcopy(state['pendingInput']);prefix=deepcopy(self.host.inputs)
        self.assertEqual('assets.upload',pending['native']['controlId']);self.assertIsNone(state['browserId']);self.assertIsNone(state['modelId'])
        files=deepcopy(self.owner.files.read()['source']['files']);originals=unpack(state['inputs'])
        self.make();self.cancel_phase();result=self.owner.cancel()
        self.assertFalse(result['cancelObserved']);self.assertTrue(result['retained']);state=self.store.read()
        self.assertIsNone(state['browserId']);self.assertIsNone(state['modelId']);self.assertEqual([pending],state['unresolvedInputs'])
        self.assertEqual(originals,unpack(state['inputs'])[:len(originals)]);self.assertEqual(prefix,self.host.inputs[:-1])
        self.assertEqual('assets-file.cancel',self.host.inputs[-1]['controlId']);self.assertNotEqual(pending['native']['commandId'],self.host.inputs[-1]['commandId'])
        actual=unpack(state['uiOriginals'])[-1]['assetsUiInventory']['browsers'][0]
        self.assertFalse(actual['rootAlive'] or actual['modelAlive']);self.assertEqual('ready',self.file_store.read()['phase'])
        self.assertEqual(files,self.owner.files.read()['source']['files']);count=len(self.host.inputs);self.make()
        self.assertFalse(self.owner.reconcile()['cancelObserved']);self.assertEqual(count,len(self.host.inputs))
        self.assertEqual(files,self.owner.files.read()['source']['files']);self.assertEqual([pending],self.store.read()['unresolvedInputs'])
        self.assertEqual(0,self.owner.uploads.last['source']['totalCalls'])
    def test_final_owner_cas_age_refuses_open_result_and_keeps_exact_inputs(self):
        self.synthetic=0;self.owner.monotonic=lambda:self.synthetic;write=self.store.write;aged=False
        def delayed(value,previous):
            nonlocal aged
            write(value,previous)
            if value['phase']=='open' and not aged:
                aged=True;epoch=self.host.epoch_milliseconds();self.owner.clock_ms=lambda:epoch;self.synthetic+=2
        with patch.object(self.store,'write',side_effect=delayed),self.assertRaises(NativeUIError):self.owner.open()
        self.assertTrue(aged);self.assertEqual('ready',self.file_store.read()['phase']);self.assertIsNotNone(self.store.read())
        self.assertEqual(self.host.inputs,[frame['native'] for frame in unpack(self.store.read()['inputs'])])
    def test_final_original_native_guard_phase_advance_prevents_first_pointer(self):
        actual=NativeNavigationIO.guard;advanced=False
        def guard(io):
            nonlocal advanced
            actual(io)
            import inspect
            if inspect.currentframe().f_back.f_code.co_name=='send' and not advanced:
                advanced=True;self.journal.activate(self.run,'3'*32,'upload-picker-cancel',{})
        with patch.object(NativeNavigationIO,'guard',guard),self.assertRaises((NativeUIError,NavigationError)):self.owner.open()
        self.assertTrue(advanced);self.assertFalse(self.host.inputs);self.assertIsNotNone(self.store.read()['pendingInput'])
        self.assertEqual('ready',self.file_store.read()['phase'])

if __name__=='__main__':unittest.main()
