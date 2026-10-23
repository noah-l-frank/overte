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
        self.stage=1;self.store=PrivateFeatureState(self.path/'cancel.json');self.file_store=PrivateFeatureState(self.path/'files.json');self.make()
    def make(self):
        files=OwnedAssetsFiles(self.host.files(stage=self.stage),self.file_store,self.binding,self.run,self.openTicket,self.url)
        self.owner=OwnedAssetsCancel(self.store,self.binding,self.run,self.url,files,self.host.mappings(),self.host.uploads(),
            self.host.io.original.capture,self.host.controls,PhaseFixtureReader(self.client,self.run,'assets'),self.host.guard,self.host.epoch_milliseconds)
    def cancel_phase(self,ticket='2'*32):self.journal.activate(self.run,ticket,'upload-picker-cancel',{})
    def next_stage(self):
        self.stage=2;self.openTicket='3'*32
        self.journal.activate(self.run,self.openTicket,'upload-picker-open',{'resource':'gltf-bundle/main.gltf'})
        self.store=PrivateFeatureState(self.path/'cancel-stage2.json');self.file_store=PrivateFeatureState(self.path/'files-stage2.json');self.make()
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
    def test_undelivered_navigation_cancel_preserves_unsent_original(self):
        send=self.host.write_debug_app_file
        def fail_navigation(target,package,path,raw):
            import json
            command=json.loads(raw)
            if command['controlId']=='assets-file.folder' and command['action']=='replace':self.host.fail_send=True
            return send(target,package,path,raw)
        with patch.object(self.host,'write_debug_app_file',side_effect=fail_navigation),self.assertRaises((NativeUIError,NavigationError)):
            self.owner.open()
        self.host.fail_send=False;state=self.store.read();pending=deepcopy(state['pendingInput']);prefix=deepcopy(self.host.inputs)
        self.assertIsNotNone(state['browserId']);self.assertIsNotNone(state['modelId'])
        self.assertEqual('assets-file.folder',pending['native']['controlId']);self.assertEqual('replace',pending['native']['action'])
        self.assertEqual(pending['native']['sequence']-1,self.host.navigation.snapshot()['lastCommandSequence'])
        originals=unpack(state['inputs']);self.make();self.cancel_phase();result=self.owner.cancel()
        self.assertTrue(result['cancelObserved'] and result['filesRetired']);after=self.store.read()
        self.assertEqual([pending],after['unresolvedInputs']);self.assertEqual(originals,unpack(after['inputs'])[:len(originals)])
        self.assertEqual(prefix,self.host.inputs[:-1]);self.assertEqual('assets-file.cancel',self.host.inputs[-1]['controlId'])
        self.assertNotEqual(pending['native']['commandId'],self.host.inputs[-1]['commandId'])
        self.assertEqual(pending['native']['sequence'],self.host.inputs[-1]['sequence'])
        self.assertEqual((state['browserId'],state['modelId']),(result['browser']['id'],result['browser']['modelId']))
        self.assertFalse(result['browser']['rootAlive'] or result['browser']['modelAlive'])
        self.assertEqual('retired',self.file_store.read()['phase']);self.assertEqual(0,self.owner.uploads.last['source']['totalCalls'])
        count=len(self.host.inputs)
        with self.assertRaises(NativeUIError):self.owner.cancel()
        self.assertEqual(count,len(self.host.inputs));self.assertEqual([pending],self.store.read()['unresolvedInputs'])
    def test_lost_navigation_and_cancel_replies_cold_reconcile_keeps_both_originals(self):
        send=self.host.write_debug_app_file
        def lose_navigation(target,package,path,raw):
            import json
            command=json.loads(raw)
            if command['controlId']=='assets-file.folder' and command['action']=='replace':self.host.lose=True
            return send(target,package,path,raw)
        with patch.object(self.host,'write_debug_app_file',side_effect=lose_navigation),self.assertRaises((NativeUIError,NavigationError)):
            self.owner.open()
        navigation=deepcopy(self.store.read()['pendingInput']);admitted=deepcopy(self.store.read())
        self.cancel_phase();self.make()
        with self.assertRaises((NativeUIError,NavigationError)):self.owner.cancel()
        cancel=deepcopy(self.store.read()['pendingInput']);originals=unpack(self.store.read()['inputs']);inputs=deepcopy(self.host.inputs)
        self.assertEqual('assets-file.cancel',cancel['native']['controlId'])
        self.assertNotEqual(navigation['native']['commandId'],cancel['native']['commandId'])
        self.assertEqual([navigation],self.store.read()['unresolvedInputs']);self.assertIsNone(originals[-1]['after'])
        self.host.lose=False;self.make();result=self.owner.reconcile();state=self.store.read()
        self.assertTrue(result['cancelObserved'] and result['filesRetired']);self.assertEqual(inputs,self.host.inputs)
        self.assertEqual(cancel,state['pendingInput']);self.assertEqual([navigation],state['unresolvedInputs'])
        self.assertEqual(originals,unpack(state['inputs']))
        self.assertEqual((admitted['browserId'],admitted['modelId']),(result['browser']['id'],result['browser']['modelId']))
        self.assertFalse(result['browser']['rootAlive'] or result['browser']['modelAlive'])
        self.assertEqual('retired',self.file_store.read()['phase']);self.assertEqual(0,self.owner.uploads.last['source']['totalCalls'])
    def release_reply_boundary(self,delivered):
        self.owner.open();before=deepcopy(self.owner.files.read()['source']['files']);self.cancel_phase()
        send=self.owner.files.native.send;attempts=[];actual=[]
        def lose_release(command):
            if command.get('operation')=='release':
                attempts.append(deepcopy(command))
                if delivered:send(command);actual.append(deepcopy(command))
                else:self.host.operations.append(deepcopy(command))
                self.host.raw=''
            else:send(command)
        with patch.object(self.owner.files.native,'send',side_effect=lose_release),self.assertRaises(NativeUIError):self.owner.cancel()
        self.assertEqual(1,len(attempts));self.assertEqual(int(delivered),len(actual))
        self.assertEqual('retiring',self.file_store.read()['phase']);self.assertEqual('canceling',self.store.read()['phase'])
        inputs=deepcopy(self.host.inputs);originals=unpack(self.store.read()['inputs']);files=unpack(self.file_store.read()['originals'])
        self.assertEqual('assets-file.cancel',inputs[-1]['controlId']);self.assertTrue(all(row['after'] is not None for row in originals))
        self.make()
        if delivered:
            result=self.owner.reconcile();self.assertTrue(result['cancelObserved'] and result['filesRetired'])
            self.assertFalse(result['browser']['rootAlive'] or result['browser']['modelAlive'])
            self.assertEqual('retired',self.file_store.read()['phase'])
            source=self.owner.files.read()['source'];self.assertTrue(source['retired']);self.assertFalse(source['exists'])
        else:
            for repeat in range(2):
                with self.assertRaises(NativeUIError):self.owner.reconcile()
                self.assertEqual('retiring',self.file_store.read()['phase'])
                self.assertEqual(before,self.owner.files.read()['source']['files']);self.make()
        self.assertEqual(inputs,self.host.inputs);self.assertEqual(originals,unpack(self.store.read()['inputs']))
        self.assertEqual(files,unpack(self.file_store.read()['originals'])[:len(files)])
        releases=[command for command in self.host.operations if command.get('operation')=='release']
        self.assertEqual(attempts,releases);self.assertEqual(0,self.owner.uploads.last['source']['totalCalls'])
    def test_lost_file_release_reply_after_normal_cancel_reconciles_without_resend(self):self.release_reply_boundary(True)
    def test_undelivered_file_release_after_normal_cancel_keeps_exact_files_without_resend(self):self.release_reply_boundary(False)
    def test_original_unavailable_primary_error_then_normal_cancel_retires_companions(self):
        self.owner.open();before=deepcopy(self.owner.files.read()['source']['files'])
        retired=self.owner.files.retire_primary();self.assertTrue(retired['primaryRetired'])
        main=next(row for row in retired['files'] if row['name']=='gltf-bundle/main.gltf');self.assertFalse(main['exists'])
        self.assertEqual([row for row in before if row['name']!='gltf-bundle/main.gltf'],
            [row for row in retired['files'] if row['name']!='gltf-bundle/main.gltf'])
        self.owner.ui().input('assets-file.accept');sample=self.owner.sample();self.owner.unchanged(sample)
        original=unpack(self.store.read()['uiOriginals'])[-1]
        picker=next(row['picker'] for row in original['controls'] if row['id']=='assets-file.cancel')
        self.assertEqual('A selected file is no longer available.',picker['error']);self.assertFalse(picker['review'])
        self.assertEqual([self.store.read()['directory']+'/gltf-bundle/main.gltf'],picker['selectedUrls'])
        self.assertTrue(sample['ui']['browsers'][0]['rootAlive'] and sample['ui']['browsers'][0]['modelAlive'])
        self.assertEqual(0,sample['uploads']['source']['totalCalls']);self.assertEqual('primary-retired',self.file_store.read()['phase'])
        originals=unpack(self.file_store.read()['originals']);self.make();self.cancel_phase();result=self.owner.cancel()
        self.assertTrue(result['cancelObserved'] and result['filesRetired']);self.assertEqual('retired',self.file_store.read()['phase'])
        self.assertFalse(result['browser']['rootAlive'] or result['browser']['modelAlive'])
        self.assertEqual(originals,unpack(self.file_store.read()['originals'])[:len(originals)])
        self.assertEqual(1,sum(command['controlId']=='assets-file.accept' for command in self.host.inputs))
        self.assertEqual(1,sum(command['controlId']=='assets-file.cancel' for command in self.host.inputs))
        self.assertEqual(0,self.owner.uploads.last['source']['totalCalls'])
    def test_next_stage_reopens_after_original_cancel_without_adopting_retired_browser(self):
        self.owner.open();self.cancel_phase();first=self.owner.cancel()['browser']
        previous_store,previous_files=self.store,self.file_store
        previous_owner=deepcopy(previous_store.read());previous_file_owner=deepcopy(previous_files.read())
        self.next_stage();self.assertTrue(self.owner.open()['pickerObserved']);current=self.store.read()
        self.assertNotEqual(first['id'],current['browserId']);self.assertNotEqual(first['modelId'],current['modelId'])
        baseline=unpack(current['uiOriginals'])[0]['assetsUiInventory']['browsers'];self.assertEqual(1,len(baseline))
        self.assertEqual((first['id'],first['modelId']),(baseline[0]['id'],baseline[0]['modelId']))
        self.assertFalse(baseline[0]['rootAlive'] or baseline[0]['modelAlive'])
        self.make();self.cancel_phase('4'*32);result=self.owner.cancel()
        self.assertTrue(result['cancelObserved'] and result['filesRetired'])
        self.assertEqual((current['browserId'],current['modelId']),(result['browser']['id'],result['browser']['modelId']))
        self.assertFalse(result['browser']['rootAlive'] or result['browser']['modelAlive'])
        self.assertEqual(previous_owner,previous_store.read());self.assertEqual(previous_file_owner,previous_files.read())
        self.assertEqual(2,sum(command['controlId']=='assets.upload' for command in self.host.inputs))
        self.assertEqual(2,sum(command['controlId']=='assets-file.cancel' for command in self.host.inputs))
        self.assertEqual(0,self.owner.uploads.last['source']['totalCalls'])
    def test_next_stage_with_live_original_consumers_refuses_before_staging_or_pointer(self):
        self.owner.open();first=self.owner;before=deepcopy(first.files.read()['source']['files']);inputs=deepcopy(self.host.inputs)
        self.next_stage()
        with self.assertRaises(NativeUIError):self.owner.open()
        self.assertEqual(inputs,self.host.inputs);self.assertIsNone(self.file_store.read())
        self.assertEqual([],self.store.read()['attempted']);self.assertIsNone(self.store.read()['browserId'])
        self.assertIsNone(self.store.read()['modelId']);self.assertEqual(before,first.files.read()['source']['files'])
        original=unpack(self.store.read()['uiOriginals'])[0]['assetsUiInventory']['browsers'][0]
        self.assertTrue(original['rootAlive'] and original['modelAlive']);self.assertEqual(0,self.owner.uploads.last['source']['totalCalls'])
    def test_next_stage_lost_first_open_reply_never_adopts_retired_or_new_browser(self):
        self.owner.open();self.cancel_phase();self.owner.cancel()
        previous_store,previous_files=self.store,self.file_store
        previous_owner=deepcopy(previous_store.read());previous_file_owner=deepcopy(previous_files.read())
        self.next_stage();self.host.lose=True
        with self.assertRaises((NativeUIError,NavigationError)):self.owner.open()
        self.host.lose=False;state=self.store.read();pending=deepcopy(state['pendingInput'])
        self.assertIsNone(state['browserId']);self.assertIsNone(state['modelId'])
        baseline=unpack(state['uiOriginals'])[0]['assetsUiInventory']['browsers'];self.assertEqual(1,len(baseline))
        files=deepcopy(self.owner.files.read()['source']['files']);self.make();self.cancel_phase('4'*32);result=self.owner.cancel()
        self.assertFalse(result['cancelObserved']);self.assertEqual([pending],self.store.read()['unresolvedInputs'])
        self.assertIsNone(self.store.read()['browserId']);self.assertIsNone(self.store.read()['modelId'])
        current=unpack(self.store.read()['uiOriginals'])[-1]['assetsUiInventory']['browsers'];self.assertEqual(2,len(current))
        self.assertEqual(baseline[0],next(row for row in current if row['id']==baseline[0]['id']))
        self.assertTrue(all(not row['rootAlive'] and not row['modelAlive'] for row in current))
        self.assertEqual(files,self.owner.files.read()['source']['files']);self.assertEqual('ready',self.file_store.read()['phase'])
        inputs=deepcopy(self.host.inputs);self.make();self.assertFalse(self.owner.reconcile()['cancelObserved'])
        self.assertEqual(inputs,self.host.inputs);self.assertEqual(files,self.owner.files.read()['source']['files'])
        self.assertEqual(previous_owner,previous_store.read());self.assertEqual(previous_file_owner,previous_files.read())
    def test_retained_stage1_lost_cancel_then_stage2_lost_open_never_adopts_or_releases(self):
        self.owner.open();before=deepcopy(self.owner.files.read()['source']['files']);self.cancel_phase();self.host.lose=True
        with self.assertRaises((NativeUIError,NavigationError)):self.owner.cancel()
        self.host.lose=False;previous_store,previous_files=self.store,self.file_store
        previous_owner=deepcopy(previous_store.read());previous_file_owner=deepcopy(previous_files.read())
        self.assertEqual('canceling',previous_owner['phase']);self.assertIsNotNone(previous_owner['pendingInput'])
        self.assertEqual('ready',previous_file_owner['phase'])
        self.next_stage();self.host.lose=True
        with self.assertRaises((NativeUIError,NavigationError)):self.owner.open()
        self.host.lose=False;state=self.store.read();pending=deepcopy(state['pendingInput'])
        self.assertIsNone(state['browserId']);self.assertIsNone(state['modelId'])
        baseline=unpack(state['uiOriginals'])[0]['assetsUiInventory']['browsers'];self.assertEqual(1,len(baseline))
        self.assertFalse(baseline[0]['rootAlive'] or baseline[0]['modelAlive'])
        files=deepcopy(self.owner.files.read()['source']['files']);self.make();self.cancel_phase('4'*32);result=self.owner.cancel()
        self.assertFalse(result['cancelObserved']);self.assertEqual([pending],self.store.read()['unresolvedInputs'])
        self.assertIsNone(self.store.read()['browserId']);self.assertIsNone(self.store.read()['modelId'])
        current=unpack(self.store.read()['uiOriginals'])[-1]['assetsUiInventory']['browsers'];self.assertEqual(2,len(current))
        self.assertEqual(baseline[0],next(row for row in current if row['id']==baseline[0]['id']))
        self.assertTrue(all(not row['rootAlive'] and not row['modelAlive'] for row in current))
        self.assertEqual(files,self.owner.files.read()['source']['files']);self.assertEqual('ready',self.file_store.read()['phase'])
        inputs=deepcopy(self.host.inputs);self.make();self.assertFalse(self.owner.reconcile()['cancelObserved'])
        self.assertEqual(inputs,self.host.inputs);self.assertEqual(files,self.owner.files.read()['source']['files'])
        self.assertEqual(previous_owner,previous_store.read());self.assertEqual(previous_file_owner,previous_files.read())
        actual=self.host.files(stage=1).request('observe',self.run,previous_file_owner['ownerToken'])['source']
        self.assertTrue(actual['exists']);self.assertFalse(actual['retired']);self.assertEqual(before,actual['files'])
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
