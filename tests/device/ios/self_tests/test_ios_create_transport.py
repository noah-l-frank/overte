"""Actual HTTP/AFC factories and JS dispatch, with native SDKs modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import json
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from adapters.normal_ui import NativeUIError
from fixture.serve import FixtureState
from ios.adapters import create_state, create_files, feature_observation
from ios.self_tests.test_ios_create_state import packet, RUN
from ios.self_tests.test_ios_create_files import Boundary as FileBoundary
from ios.self_tests.test_ios_feature_observation import Native
from ios.self_tests.test_ios_location_bookmarks import Boundary as Clocks
from self_tests.test_native_feature_observation import Boundary as ClockBoundary, probe_source


class StateBoundary(Clocks):
    def __init__(self): super().__init__(None)
    def original(self):
        if self.ignore: return ''
        self.clock += .001; before = self.clocks(); self.sequence += 1; self.clock += .001
        value = packet(); value.update(requestId=self.requests[-1]['commandId'], sequence=self.sequence,
            clockBefore=before, clockAfter=self.clocks())
        if self.mutate: self.mutate(value)
        self.last = deepcopy(value); return json.dumps(value)
    def reader(self):
        return create_state.IOSCreateState(self.send, self.original, self.native_clock, lambda: self.live, 42,
                                          monotonic=lambda: self.clock, sleep=self.sleep)


class CreateTransportTests(unittest.TestCase):
    def test_state_reader_never_resends_a_missing_or_foreign_native_result(self):
        for fault in ('missing', 'foreign', 'stale', 'birth'):
            source = StateBoundary(); reader = source.reader()
            if fault == 'birth': reader.read(RUN)
            if fault == 'missing': source.ignore = True
            elif fault == 'foreign': source.mutate = lambda packet: packet.update(requestId='ios-'+'f'*32)
            elif fault == 'stale': source.mutate = lambda packet: packet['clockAfter'].update(epochMs=1)
            else: source.mutate = lambda packet: packet.update(instance='f'*32)
            before = len(source.requests)
            with self.subTest(fault=fault), self.assertRaises(NativeUIError): reader.read(RUN)
            self.assertEqual(before+1, len(source.requests))

    def test_closed_actual_fixture_rejects_expected_values_entity_scope_and_arbitrary_file_roles(self):
        fixture = FixtureState(); state = dict(schemaVersion=1, commandId='ios-'+'e'*32, action=create_state.ACTION, runId=RUN)
        self.assertEqual(state, fixture.set_client_command(state))
        for extra in ({'expected': {}}, {'ids': []}, {'radius': 100}, {'schemaVersion': True}):
            with self.assertRaises((RuntimeError, ValueError)): fixture.set_client_command(state | extra)
        query = dict(state, action=create_files.ACTION, operation='stage', ownerToken='f'*64, inputBase64='e30=')
        self.assertEqual(query, fixture.set_client_command(query))
        for extra in ({'output': 'generated-export.json'}, {'operation': 'download'}, {'inputBase64': 'bad base64'}):
            with self.assertRaises((RuntimeError, ValueError)): fixture.set_client_command(query | extra)

    def test_actual_probe_retains_exact_original_and_does_not_replay_lost_file_mutations(self):
        program = r'''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,k)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.sort());
let files=[],calls=0;const original={requestId:'ios-'+'e'.repeat(32),source:{complete:false,entities:[]}};
const Test={featureIOSCreateState:c=>{calls++;return original},saveObject:(v,name)=>files.push({v,name})};
SOURCE
const c={schemaVersion:1,commandId:'ios-'+'e'.repeat(32),action:'feature-ios-create-state',runId:'a'.repeat(32)};
applyClientCommand(c);applyClientCommand(c);
if(calls!==1||files.length!==1||files[0].v!==original||files[0].name!=='feature-ios-create-state.json')throw Error('source replaced/replayed');
applyClientCommand({...c,commandId:'ios-'+'d'.repeat(32),expected:{}});
if(calls!==1)throw Error('expected outcome admitted');
delete Test.featureIOSCreateState;applyClientCommand({...c,commandId:'ios-'+'c'.repeat(32)});
if(files[1].v.status!=='unavailable')throw Error('missing source became empty success');
let mutations=0;Test.featureIOSCreateFiles=c=>{mutations++;throw Error('lost native return')};
const stage={...c,action:'feature-ios-create-files',commandId:'ios-'+'b'.repeat(32),operation:'stage',ownerToken:'f'.repeat(64),inputBase64:'e30='};
applyClientCommand(stage);applyClientCommand(stage);
applyClientCommand({...stage,commandId:'ios-'+'9'.repeat(32),operation:'observe',inputBase64:undefined});
applyClientCommand(stage);
if(mutations!==1||files[2].v.status!=='unavailable'||files[2].name!=='feature-ios-create-files.json')throw Error('uncertain mutation replayed');
'''.replace('SOURCE', probe_source())
        result = subprocess.run(['node', '-e', program], capture_output=True, text=True, timeout=5)
        self.assertEqual(0, result.returncode, result.stderr)

    def transport(self, source, source_file):
        native = Native(); clock = ClockBoundary(); observer = native.observer()
        if isinstance(source, StateBoundary):
            observer.monotonic = lambda: source.clock; observer.sleep = source.sleep
            epoch, increment = source.epoch, source.native_clock
        else:
            observer.monotonic = source.monotonic; observer.sleep = source.sleep
            epoch = lambda: source.elapsed+1700000000000; increment = source.clock
        observer.epoch_ms = lambda: 9000
        def stamp(value):
            increment(); now = epoch(); value.update(processId=42, capturedEpochMs=now, requestedEpochMs=now,
                                                   animation={}, animationFence={})
        clock.mutate = stamp
        def post(request, timeout):
            query = native.fixture.set_client_command(json.loads(request.data)); native.commands.append(deepcopy(query))
            native.echo = json.dumps(query).encode()
            if query['action'] == 'feature-native-observe': clock.send(query)
            else: source.send(query)
            return native
        def execute(session, operation, values):
            self.assertEqual(('native-session', 'mobile: pullFile'), (session, operation)); path = values['remotePath']
            prefix = '@org.example.client:documents/owned-results/'
            self.assertIn(path, (prefix+'feature-native-observation.json', prefix+source_file)); native.reads.append(path)
            original = clock.original() if path.endswith('/feature-native-observation.json') else source.original()
            return base64.b64encode(original.encode()).decode()
        for boundary in (patch.object(feature_observation, 'post_request', side_effect=post),
                         patch.object(native, 'execute', side_effect=execute)):
            boundary.start(); self.addCleanup(boundary.stop)
        return native, observer

    def test_actual_state_factory_reads_original_afc_and_native_clock_bracket_with_foreign_host_utc(self):
        source = StateBoundary(); native, observer = self.transport(source, create_state.FILE)
        value = observer.create_state().read(RUN)
        self.assertEqual(source.last, value)
        self.assertEqual(['feature-native-observe', create_state.ACTION, 'feature-native-observe'],
                         [row['action'] for row in native.commands])
        self.assertGreater(value['clockAfter']['epochMs'], 9000)

    def test_actual_file_factory_stages_once_and_independently_reads_original_afc_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            source = FileBoundary(directory); native, observer = self.transport(source, create_files.FILE)
            reader = observer.create_files(); reader.request('stage', RUN, 'e'*64, content=b'actual controlled input')
            original = reader.request('observe', RUN, 'e'*64)
            self.assertEqual(b'actual controlled input', base64.b64decode(original['source']['files'][0]['base64']))
            self.assertFalse(original['source']['files'][1]['exists'])
            self.assertEqual(1, sum(row.get('operation') == 'stage' for row in native.commands))
            self.assertEqual(6, len(native.commands)); self.assertEqual(6, len(native.reads))


if __name__ == '__main__': unittest.main()
