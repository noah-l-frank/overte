"""No-build normal Assets prefix; Qt/SDK/native responses remain declared models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
sys.path[:0] = [str(ROOT/'tests/device'), str(HERE)]
import test_normal_scripts as normal
from adapters.normal_ui import NativeUIError
from adapters.pico4.assets_prefix import PicoAssetsPrefix
from adapters.pico4.navigation import validate_snapshot, NavigationError
from adapters.script_journey.history import unpack
from adapters.token_create_ui import snapshot as create_snapshot, control_id
from adapters.pico4.normal_create import project as create_project
from adapters.pico4.assets_raw_archive import compact
from adapters.pico4.assets_prefix_originals import AssetsPrefixOriginals
from adapters.chat_journey import source_bundles
from adapters.chat_journey.source_chunks import ChatSourceChunks
from adapters.normal_feature_state import PrivateFeatureState
from self_tests.pico_assets_prefix_fixture import AssetsPrefixModel


class AssetsPrefixTests(unittest.TestCase):
    def setUp(self):
        self.normal = normal.PicoNormalScriptsTests(methodName='runTest')
        self.normal.setUp()
        self.addCleanup(self.normal.doCleanups)
        destination = os.environ.get('OVERTE_ASSETS_PREFIX_EVIDENCE')
        if destination is None:
            self.directory = tempfile.TemporaryDirectory(prefix='pico-assets-prefix-')
            self.addCleanup(self.directory.cleanup)
            path = self.directory.name
        else:
            path = tempfile.mkdtemp(prefix=self._testMethodName+'-', dir=destination)
            # Preserve the original canonical namespace at its original path,
            # not a reconstructed copy with different physical identities.
            temporary = self.normal.fixture.fixture.fixture.temporary
            temporary._finalizer.detach()
            temporary.cleanup = lambda:None
            (Path(path)/'canonical-original-root.txt').write_text(temporary.name+'\n')
        self.model = AssetsPrefixModel(self, path, self.normal,
            manual_owner=self._testMethodName != 'test_canonical_factory_composes_normal_open_and_original_cancel_file_owners')
        self.owner = self.model.owner

    def baseline(self):
        self.model.activate('baseline')
        result = self.owner.observe()
        self.assertFalse(result['open'])
        self.assertFalse(result['completeCommonObservation'])

    def open(self):
        self.baseline()
        fields = self.model.activate('open')
        self.assertTrue(self.owner.act(fields)['openDelivered'])

    def test_same_actual_normal_recipe_and_same_cancel_file_owners_keep_responsibility(self):
        self.open()
        fields = self.model.activate('upload-picker-open', {'resource':'gltf-bundle/main.gltf'})
        self.assertTrue(self.owner.act(fields)['pickerObserved'])
        child = self.owner.child
        fields = self.model.activate('upload-picker-cancel')
        result = self.owner.act(fields)
        self.assertTrue(result['cancelObserved'] and result['filesRetired'] and result['retained'])
        self.assertIs(child, self.owner.child)
        self.assertEqual('cancel-observed-files-retired', child.store.read()['phase'])
        self.assertEqual('retired', child.files.store.read()['phase'])
        self.assertGreaterEqual(self.model.clock, 3)
        ui_rows = unpack(child.store.read()['uiOriginals'])
        quiet = [row['assetsUiInventory'] for row in ui_rows if row['elapsedMs'] >= ui_rows[-1]['elapsedMs']-3000]
        self.assertGreaterEqual(quiet[-1]['elapsedMs']-quiet[0]['elapsedMs'], 3000)
        self.assertGreaterEqual(quiet[-1]['capturedEpochMs']-quiet[0]['capturedEpochMs'], 3000)
        for left, right in zip(quiet, quiet[1:]):
            if right['elapsedMs'] > left['elapsedMs']:
                self.assertTrue(0 < right['elapsedMs']-left['elapsedMs'] <= 500)
                self.assertTrue(0 < right['capturedEpochMs']-left['capturedEpochMs'] <= 500)
        self.assertTrue(result['browser']['contextAlive'] and result['browser']['windowAlive'])
        self.assertFalse(self.owner.observe()['picker'])
        before = deepcopy(self.model.inputs)
        self.assertTrue(self.owner.responsibility()['retained'])
        self.assertFalse(self.owner.responsibility()['completedCleanup'])
        self.assertEqual(before, self.model.inputs)
        with self.owner.lock.held():
            bill = self.owner.bill()
        self.assertLessEqual(bill['frames'], 512)
        self.assertLessEqual(bill['decodedBytes'], 16*1024*1024)
        self.assertEqual(['create.entry', 'create.tab.3', 'create.assets'],
                         [row['controlId'] for row in self.model.inputs[:3]])
        self.assertEqual(1, sum(row['controlId']=='assets.upload' for row in self.model.inputs))
        self.assertEqual(1, sum(row['controlId']=='assets-file.cancel' for row in self.model.inputs))
        destination = os.environ.get('OVERTE_ASSETS_PREFIX_EVIDENCE')
        if destination is not None:
            (Path(self.model.root)/'actual-bill.json').write_text(json.dumps(dict(bill=bill,
                actualQueries=len(self.model.calls), actualInputs=len(self.model.inputs), quietHostSeconds=self.model.clock,
                sourceKinds={kind:sum(row['action']==kind for row in self.model.calls) for kind in {row['action'] for row in self.model.calls}},
                nativeQualification=False), sort_keys=True, indent=2))

    def test_skipped_actual_prefix_is_archived_before_any_target_query_or_input(self):
        self.baseline()
        before = len(self.model.calls)
        fields = self.model.activate('upload-picker-open', {'resource':'gltf-bundle/main.gltf'})
        with self.assertRaises(NativeUIError):
            self.owner.act(fields)
        self.assertEqual(before, len(self.model.calls))
        self.assertFalse(self.model.inputs)
        self.assertTrue(self.owner.responsibility()['retained'])

    def test_acquired_invalid_raw_is_durable_before_next_query_and_not_retried(self):
        self.model.activate('baseline')
        self.model.corrupt = lambda value:value.update(processId=124)
        with self.assertRaises(NativeUIError):
            self.owner.observe()
        state = self.owner.store.read()
        self.assertEqual(1, len(self.model.calls))
        self.assertIsNotNone(state['pendingSource'])
        with self.owner.lock.held():
            original = self.owner.literal(state['pendingSource']['raw'][-1])
        self.assertEqual(124, json.loads(original)['processId'])
        self.model.corrupt = None
        with self.assertRaises(NativeUIError):
            self.owner.observe()
        self.assertEqual(1, len(self.model.calls))

    def test_lost_open_reply_retains_real_command_and_refuses_any_repeat(self):
        self.baseline()
        self.model.lose = True
        fields = self.model.activate('open')
        with self.assertRaises(NativeUIError):
            self.owner.act(fields)
        pending = self.owner.store.read()['pendingInput']
        self.assertEqual(self.model.inputs[-1], pending['native'])
        self.model.lose = False
        count = len(self.model.inputs)
        with self.assertRaises(NativeUIError):
            self.owner.act(fields)
        self.assertEqual(count, len(self.model.inputs))
        self.assertEqual(pending, self.owner.responsibility()['pendingInput'])

    def test_changed_phase_at_original_writer_refuses_after_durable_intent(self):
        self.baseline()
        fields = self.model.activate('open')
        before = self.owner.before_send
        def change(command, navigation):
            self.model.activate('upload-picker-open', {'resource':'gltf-bundle/main.gltf'})
            return before(command, navigation)
        self.owner.before_send = change
        with self.assertRaises(NativeUIError):
            self.owner.act(fields)
        self.assertFalse(self.model.inputs)
        self.assertIsNotNone(self.owner.store.read()['pendingInput'])

    def test_repeated_same_phase_uses_new_original_queries_and_preserves_old_clocks(self):
        self.baseline()
        first = deepcopy(self.owner.mappings.history[0])
        for _ in range(3):
            self.model.sleep(.25)
            self.owner.observe()
        self.assertEqual(first, self.owner.mappings.history[0])
        self.assertEqual(4, len(self.owner.mappings.history))
        self.assertEqual(4, len({row['command']['commandId'] for row in self.owner.mappings.history}))
        self.assertGreater(self.owner.mappings.last['capturedEpochMs'], json.loads(first['raw'])['capturedEpochMs'])

    def test_late_actual_activation_is_preserved_before_next_source_query(self):
        self.baseline()
        fields = self.model.activate('open')
        self.model.activate('upload-picker-open', {'resource':'gltf-bundle/main.gltf'})
        before = len(self.model.calls)
        with self.assertRaises(NativeUIError):
            self.owner.act(fields)
        with self.owner.lock.held():
            original = self.owner.original(self.owner.last_phase)
        self.assertEqual('upload-picker-open', original['activations'][-1]['stimulus']['verb'])
        self.assertEqual(before, len(self.model.calls))
        self.assertFalse(self.model.inputs)

    def test_capacity_work_cannot_dispatch_after_original_sample_window(self):
        self.model.activate('baseline')
        reserve = self.owner.raw_archive.reserve
        def delayed(role, command):
            result = reserve(role, command)
            if role == 'mappings':
                self.model.clock += 2
            return result
        self.owner.raw_archive.reserve = delayed
        # Frozen native time cannot hide work charged to the original host clock.
        self.owner.clock_ms = lambda:self.model.origin
        with self.assertRaises(NativeUIError):
            self.owner.observe()
        self.assertEqual([], self.model.calls)
        self.assertIsNotNone(self.owner.store.read()['pendingRawRead'])

    def test_ui_capacity_work_cannot_acquire_after_original_sample_window(self):
        self.model.activate('baseline')
        reserve = self.owner.raw_archive.reserve
        reads = []
        original = self.owner.raw_ui
        def delayed(role, command):
            result = reserve(role, command)
            if role == 'ui':
                self.model.clock += 2
            return result
        def read():
            reads.append(True)
            return original()
        self.owner.raw_archive.reserve = delayed
        self.owner.raw_ui = read
        self.owner.clock_ms = lambda:self.model.origin
        with self.assertRaises(NativeUIError):
            self.owner.observe()
        self.assertEqual([], reads)
        self.assertIsNotNone(self.owner.store.read()['pendingRawRead'])

    def test_child_invalid_reply_is_retained_before_any_next_child_query(self):
        self.open()
        fields = self.model.activate('upload-picker-open', {'resource':'gltf-bundle/main.gltf'})
        self.model.corrupt = lambda value:value.update(processId=124)
        before = len(self.model.calls)
        with self.assertRaises(NativeUIError):
            self.owner.act(fields)
        self.assertEqual(before+1, len(self.model.calls))
        pending = self.owner.store.read()['pendingChildSource']
        self.assertIsNotNone(pending)
        with self.owner.lock.held():
            original = self.owner.literal(pending['raw'][-1])
        self.assertEqual(124, json.loads(original)['processId'])
        self.assertTrue(self.owner.responsibility()['retained'])

    def test_candidate_death_after_raw_response_still_retains_raw_and_queries_nothing_next(self):
        self.model.activate('baseline')
        self.model.after_original = lambda:setattr(self.model.native, 'running', False)
        with self.assertRaises(NativeUIError):
            self.owner.observe()
        pending = self.owner.store.read()['pendingSource']
        self.assertEqual(1, len(self.model.calls))
        self.assertTrue(pending['raw'])
        with self.owner.lock.held():
            original = self.owner.literal(pending['raw'][-1])
        self.assertEqual(self.model.calls[0]['commandId'], json.loads(original)['requestId'])

    def test_phase_change_after_first_response_preserves_raw_and_refuses_second_query(self):
        self.model.activate('baseline')
        def change():
            self.model.after_original = None
            self.model.activate('open')
        self.model.after_original = change
        with self.assertRaises(NativeUIError):
            self.owner.observe()
        self.assertEqual(1, len(self.model.calls))
        self.assertTrue(self.owner.mappings.history)
        self.assertFalse(self.owner.uploads.history)
        with self.owner.lock.held():
            original = self.owner.original(self.owner.last_phase)
        self.assertEqual('open', original['activations'][-1]['stimulus']['verb'])

    def test_fresh_but_pre_activation_ui_is_retained_without_becoming_current(self):
        self.model.activate('baseline')
        def old():
            value = self.model.snapshot()
            value['updatedEpochMs'] -= 1000
            value['assetsUiInventory']['capturedEpochMs'] -= 1000
            return json.dumps(value)
        self.owner.raw_ui = old
        with self.assertRaises(NativeUIError):
            self.owner.observe()
        self.assertEqual(0, self.owner.store.read()['observations'])
        with self.owner.lock.held():
            indexes = [index for index,value in enumerate(self.owner.disk['rawReads']) if value.get('role')=='ui']
            ui = self.owner.literal(indexes[0])
        self.assertLess(json.loads(ui)['updatedEpochMs'], self.model.epoch())

    def prepare_cancel(self):
        self.open()
        self.owner.act(self.model.activate('upload-picker-open', {'resource':'gltf-bundle/main.gltf'}))
        return self.model.activate('upload-picker-cancel')

    def test_original_cancel_quiet_rejects_slow_source_cross_clock_gaps_without_resend(self):
        fields = self.prepare_cancel()
        def slow(_command):
            if self.owner.child.store.read()['phase'] == 'canceling':
                self.model.sleep(.2)
        self.model.before_query = slow
        with self.assertRaises(NativeUIError):
            self.owner.act(fields)
        self.assertNotEqual('cancel-observed-files-retired', self.owner.child.store.read()['phase'])
        self.assertEqual('ready', self.owner.child.files.store.read()['phase'])
        count = len(self.model.inputs)
        self.model.before_query = None
        with self.assertRaises(NativeUIError):
            self.owner.act(fields)
        self.assertEqual(count, len(self.model.inputs))
        self.assertEqual(1, sum(row['controlId']=='assets-file.cancel' for row in self.model.inputs))

    def test_original_cancel_real_point45_acquisition_does_not_add_double_sleep(self):
        self.prepare_standalone_real_cancel()
        durations=self.real_acquisition_cost(.45)
        first=len(unpack(self.owner.child.store.read()['uiOriginals']))
        result=self.owner.child.cancel()
        self.assertTrue(result['cancelObserved'] and result['filesRetired'])
        rows=[row['assetsUiInventory'] for row in unpack(self.owner.child.store.read()['uiOriginals'])]
        current=rows[first:]
        self.assertTrue(all(0<right['elapsedMs']-left['elapsedMs']<=500 for left,right in zip(current,current[1:])))
        self.assertTrue(durations and min(durations)>=.45)

    def real_acquisition_cost(self,seconds):
        # Preserve the original epoch/domain birth and all old packets. Move
        # the declared clock forward to real elapsed time, never backwards.
        elapsed=max(self.model.clock,(time.time()*1000-self.model.origin)/1000)
        self.model.real_time_start=time.monotonic()-elapsed
        sample=self.owner.child.sample;durations=[]
        def acquired():
            value=sample()
            time.sleep(max(0,seconds-(self.owner.child.now()-value['started'])))
            self.owner.child.check_sample(value)
            durations.append(self.owner.child.now()-value['started'])
            return value
        self.owner.child.sample=acquired
        return durations

    def prepare_standalone_real_cancel(self):
        # Match the existing standalone Cancel fixture: the normal Assets page
        # is already present. This does not claim normal Prefix Open delivery.
        # The separate canonical case exercises the whole parent/raw archive.
        self.model.page='assets'
        self.model.activate('upload-picker-open',{'resource':'gltf-bundle/main.gltf'})
        self.owner.child=self.model.cancel()
        self.owner.child.open()
        self.model.activate('upload-picker-cancel')

    def test_original_cancel_real_point6_acquisition_still_refuses_actual_cadence(self):
        self.prepare_standalone_real_cancel();durations=self.real_acquisition_cost(.6)
        with self.assertRaises(NativeUIError):self.owner.child.cancel()
        self.assertTrue(durations and min(durations)>=.6)
        self.assertEqual('ready',self.owner.child.files.store.read()['phase'])
        self.assertEqual(1,sum(row['controlId']=='assets-file.cancel' for row in self.model.inputs))

    def test_original_cancel_quiet_phase_change_refuses_before_next_native_query(self):
        fields = self.prepare_cancel()
        sleep = self.owner.child.sleep
        calls = []
        def change(seconds):
            sleep(seconds)
            calls.append(len(self.model.calls))
            self.model.activate('upload', {'resource':'gltf-bundle/main.gltf'})
        self.owner.child.sleep = change
        with self.assertRaises(NativeUIError):
            self.owner.act(fields)
        self.assertTrue(calls)
        self.assertEqual(calls[-1], len(self.model.calls))
        self.assertEqual('ready', self.owner.child.files.store.read()['phase'])
        self.assertEqual(1, sum(row['controlId']=='assets-file.cancel' for row in self.model.inputs))

    def test_opt_in_create_marker_does_not_expand_default_or_historical_inventory(self):
        self.model.page, self.model.tab = 'create', 3
        packet = self.model.snapshot()
        ordinary = create_project(packet)
        self.assertFalse(control_id('create.assets'))
        self.assertFalse(any(row['id']=='create.assets' for row in ordinary['controls']))
        self.assertEqual(ordinary, create_snapshot(ordinary))
        extended = create_project(packet, pico_assets=True)
        self.assertTrue(any(row['id']=='create.assets' for row in extended['controls']))
        with self.assertRaises(NativeUIError):
            create_snapshot(extended)
        default = self.model.adapter._create_controls(self.model.native.target, lambda _value: self.fail('Default inventory cannot issue Assets intent'))
        with self.assertRaises(NativeUIError):
            default.input('create.assets')
        for marker in (None, True, 2):
            changed = deepcopy(packet)
            if marker is None:
                del changed['picoAssetsCreateControlsVersion']
            else:
                changed['picoAssetsCreateControlsVersion'] = marker
            with self.assertRaises((NativeUIError, NavigationError, ValueError)):
                validate_snapshot(changed, 123, self.model.epoch())
        self.assertFalse(self.model.inputs)

    def test_unknown_raw_transfer_cas_preserves_exact_immutable_part_without_next_query(self):
        import base64
        import zlib
        for delivered in (False, True):
            with self.subTest(delivered=delivered):
                if delivered:
                    self.setUp()
                self.model.activate('baseline')
                write = self.owner.store.write
                def uncertain(value, previous):
                    pending = value['pendingSource']
                    if pending is not None and pending['raw']:
                        if delivered:
                            write(value, previous)
                        raise OSError('Declared unknown original raw-transfer CAS')
                    return write(value, previous)
                with patch.object(self.owner.store, 'write', side_effect=uncertain):
                    with self.assertRaises(NativeUIError):
                        self.owner.observe()
                self.assertEqual(1, len(self.model.calls))

                reference = self.owner.raw_archive.active['literal']
                raw = b''.join((self.model.root/part['name']).read_bytes() for part in reference['parts'])
                self.assertEqual(self.model.calls[0]['commandId'], json.loads(raw)['requestId'])
                passive=AssetsPrefixOriginals(self.owner.store.path);self.addCleanup(passive.close_host)
                if delivered:
                    self.assertEqual(raw,passive.literal(len(passive.value['rawReads'])-1))
                else:
                    uncertain=passive.pending_read()
                    self.assertTrue(uncertain['completeBytes'])
                    self.assertFalse(uncertain['qualifiedOriginal'] or uncertain['liveAdoptionPermitted'])
                    self.assertEqual(raw,uncertain['raw'])
                with self.assertRaises(NativeUIError):
                    self.owner.observe()
                self.assertEqual(1, len(self.model.calls))

    def test_actual_four_mib_hostile_reply_is_preserved_before_parser_and_no_next_query(self):
        import adapters.pico4.assets_source as native
        self.model.activate('baseline')
        raw='\0'*(4*1024*1024)
        send=self.owner.mappings.send
        getters=[]
        def hostile(command):
            send(command);self.model.raw=raw
        self.owner.mappings.send=hostile
        self.model.after_original=lambda:getters.append(True)
        with patch.object(native,'decode',side_effect=AssertionError('Hostile literal must not reach parser')) as parser:
            with self.assertRaises(NativeUIError):self.owner.observe()
            self.assertFalse(parser.called)
        self.assertEqual(1,len(getters));self.assertEqual(1,len(self.model.calls))
        index=self.owner.store.read()['pendingSource']['raw'][-1]
        with self.owner.lock.held():
            self.assertEqual(raw.encode(),self.owner.literal(index))
            self.assertLessEqual(self.owner.bill()['decodedBytes'],16*1024*1024)
        reader=AssetsPrefixOriginals(self.owner.store.path);self.addCleanup(reader.close_host)
        self.assertTrue(reader.historical_only);self.assertEqual(2,reader.version)
        self.assertEqual(raw.encode(),reader.literal(index))
        with self.assertRaises(NativeUIError):self.owner.observe()
        self.assertEqual(1,len(getters));self.assertEqual(1,len(self.model.calls))

    def test_actual_retained_capacity_refuses_original_native_send_and_getter(self):
        with self.owner.lock.held():
            for character in ('a','b','c'):
                self.owner.raw_archive.reserve('mappings',dict(commandId=character*32))
                reference=self.owner.raw_archive.retain(character*(4*1024*1024))
                self.owner.raw_receipt(dict(role='mappings',rawOriginal=compact(reference)))
        self.model.activate('baseline');getters=[]
        self.model.after_original=lambda:getters.append(True)
        with self.assertRaises(NativeUIError):self.owner.observe()
        self.assertFalse(getters);self.assertFalse(self.model.calls)
        self.assertEqual(192,self.owner.raw_archive.bill()['parts'])
        self.assertEqual(12*1024*1024,self.owner.raw_archive.bill()['bytes'])

    def test_partial_original_binary_write_stays_readonly_uncertain_without_retry(self):
        self.model.activate('baseline');write=os.write
        def partial(descriptor,data):
            write(descriptor,data[:max(1,len(data)//2)])
            raise OSError('Declared failed original binary write')
        with patch('os.write',side_effect=partial),self.assertRaises(NativeUIError):self.owner.observe()
        self.assertEqual(1,len(self.model.calls))
        reader=AssetsPrefixOriginals(self.owner.store.path);self.addCleanup(reader.close_host)
        pending=reader.pending_read()
        self.assertFalse(pending['completeBytes'] or pending['qualifiedOriginal'] or pending['liveAdoptionPermitted'])
        self.assertTrue(pending['segments'] and pending['segments'][0]['raw'])
        with self.assertRaises(NativeUIError):self.owner.observe()
        self.assertEqual(1,len(self.model.calls))

    def test_historical_source1_literal_decodes_without_live_query_or_adoption(self):
        import hashlib
        store=PrivateFeatureState(self.model.root/'historical-prefix1.json')
        scope={key:deepcopy(value) for key,value in self.owner.scope.items() if key!='assetsRawOriginalLayoutVersion'}
        scope['assetsPrefixVersion']=1
        state=deepcopy(self.owner.state);state.update(scope)
        for key in ('assetsRawOriginalLayoutVersion','pendingRawRead','rawReads'):state.pop(key,None)
        store.write(state,None);disk=deepcopy(state);history=ChatSourceChunks(store,scope)
        literal='original historical source1 bytes\n'
        ref,parts=source_bundles.prepare(dict(role='mappings',raw=literal,
            sha256=hashlib.sha256(literal.encode()).hexdigest()),0,[])
        for part in parts:
            state['chunks']=history.append(part,state['chunks']);store.write(state,disk);disk=deepcopy(state)
        state['bundles'].append(ref);store.write(state,disk)
        before=deepcopy(self.model.calls);reader=AssetsPrefixOriginals(store.path);self.addCleanup(reader.close_host)
        self.assertEqual(1,reader.version);self.assertTrue(reader.historical_only)
        self.assertEqual(literal.encode(),reader.literal(0));self.assertEqual(before,self.model.calls)

    def test_existing_cancel_lost_reply_reconciles_without_repeating_normal_input(self):
        fields=self.prepare_cancel();self.model.lose=True
        with self.assertRaises(NativeUIError):self.owner.act(fields)
        child=self.owner.child;pending=deepcopy(child.store.read()['pendingInput']);before=deepcopy(self.model.inputs)
        self.model.lose=False
        with self.owner.lock.held():result=child.reconcile()
        self.assertTrue(result['cancelObserved'] and result['filesRetired'])
        self.assertEqual(before,self.model.inputs);self.assertEqual(pending,child.store.read()['pendingInput'])

    def test_existing_cancel_undelivered_input_keeps_live_consumers_and_files(self):
        fields=self.prepare_cancel();before=deepcopy(self.model.inputs)
        self.model.before_input=lambda _command:(_ for _ in ()).throw(OSError('Declared undelivered Cancel'))
        with self.assertRaises(NativeUIError):self.owner.act(fields)
        self.model.before_input=None
        with self.owner.lock.held():result=self.owner.child.reconcile()
        self.assertFalse(result['cancelObserved']);self.assertTrue(result['retained'])
        self.assertEqual(before,self.model.inputs)
        self.assertEqual('ready',self.owner.child.files.store.read()['phase'])

    def test_native_selector_uses_actual_existing_tools_delegate_and_normal_pointer_dispatch(self):
        qml = (ROOT/'scripts/system/create/qml/NativeCreate.qml').read_text()
        self.assertIn('["assets", qsTr("Domain assets")]', qml)
        self.assertIn('objectName: "NativeCreateTool_" + modelData[0]', qml)
        self.assertIn('onClicked: root.tool(modelData[0])', qml)
        native = (ROOT/'tests/device/native/NormalCreateControls.h').read_text()
        ordinary = native[native.index('inline QString createControlId('):native.index('inline QString picoAssetsCreateControlId(')]
        self.assertNotIn('create.assets', ordinary)
        section = native[native.index('#if defined(ANDROID_APP_PICO_INTERFACE)'):]
        section = section[:section.index('#endif')]
        self.assertIn('createPage(item)', section)
        self.assertIn('item->objectName()=="NativeCreateTool_assets"', section)
        self.assertIn('indexOfSignal("clicked()")', section)
        producer = (ROOT/'android/vr/pico/apps/picoInterface/e2e/PicoE2eNavigationUi.cpp').read_text()
        marker = producer.index('result["picoAssetsCreateControlsVersion"]=1')
        self.assertLess(producer.index('observed.append(row)'), marker)
        self.assertIn('row.toObject().value("id").toString()=="create.assets"', producer[marker-100:marker])
        self.assertIn('delivered=pointerClick(control.item)', producer)
        self.assertIn('picoAssetsCreateControlId(item)', producer)


class AssetsPrefixBindingTests(AssetsPrefixTests):
    # Select only new factory/ownership cases; inherited prefix cases stay in
    # their original class and are not duplicated by the module loader below.
    def test_canonical_factory_composes_normal_open_and_original_cancel_file_owners(self):
        self.owner = self.model.canonical()
        self.assertIs(self.owner.lock, self.model.lock)
        self.assertEqual(self.model.adapter._assets_prefix_store(self.model.native.target).path, self.owner.store.path)
        before = deepcopy(self.model.inputs)
        self.assertEqual([], self.model.calls)
        self.assertEqual([], before)
        self.model.activate('baseline')
        self.assertFalse(self.owner.observe()['open'])
        self.assertTrue(self.owner.act(self.model.activate('open'))['openDelivered'])
        self.assertTrue(self.owner.act(self.model.activate('upload-picker-open', {'resource':'gltf-bundle/main.gltf'}))['pickerObserved'])
        self.assertTrue(self.owner.act(self.model.activate('upload-picker-cancel'))['filesRetired'])
        self.assertTrue(self.owner.observe()['retained'])
        self.assertFalse(self.owner.responsibility()['completedCleanup'])
        self.assertTrue(self.model.adapter._assets_prefix_owned(self.model.native.target))
        with self.owner.lock.held():
            bill = self.owner.bill()
        (Path(self.model.root)/'canonical-bill.json').write_text(json.dumps(dict(bill=bill,
            queries=len(self.model.calls), inputs=len(self.model.inputs), actualHostSeconds=self.model.clock,
            sourceRoot=str(self.owner.store.path), nativeQualified=False), indent=2))

    def test_root_and_rootless_source_intents_refuse_before_any_native_input_or_base_stop(self):
        adapter, target = self.model.adapter, self.model.native.target
        store = adapter._assets_prefix_store(target)
        for suffix in ('', '.pending-original', '.frame-000.json', '.child-original', '.chunk-original', '.partial-original'):
            with self.subTest(suffix=suffix):
                owned = store.path.with_name(store.path.name+suffix)
                owned.write_bytes(b'original unresolved prefix responsibility\n')
                owned.chmod(0o600)
                original = owned.read_bytes()
                with patch.object(self.model.native, 'read_debug_app_file', side_effect=AssertionError('No Native read allowed')) as read, \
                     patch.object(self.model.native, 'write_debug_app_file', side_effect=AssertionError('No Native input allowed')) as write, \
                     patch.object(self.model.native, 'shell', side_effect=AssertionError('No Native shell allowed')) as shell, \
                     patch.object(self.model.native, 'process_state', side_effect=AssertionError('No Native process query allowed')) as process, \
                     patch.object(type(adapter).__mro__[1], 'cleanup', side_effect=AssertionError('No base stop allowed')) as stop:
                    self.assertTrue(adapter._assets_prefix_owned(target))
                    with self.assertRaises(ValueError):
                        adapter.cleanup(target)
                    self.assertFalse(read.called or write.called or shell.called or process.called or stop.called)
                self.assertEqual(original, owned.read_bytes())
                # Only this test-created counter file is removed between cases.
                owned.unlink()


def load_tests(loader, tests, pattern):
    ordinary = loader.loadTestsFromTestCase(AssetsPrefixTests)
    binding = unittest.TestSuite(AssetsPrefixBindingTests(name) for name in (
        'test_canonical_factory_composes_normal_open_and_original_cancel_file_owners',
        'test_root_and_rootless_source_intents_refuse_before_any_native_input_or_base_stop'))
    return unittest.TestSuite((ordinary, binding))


if __name__ == '__main__':
    unittest.main()
