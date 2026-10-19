"""Native Script execution reader counterexamples; no client or compiler."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adapters.native_script_observation import NativeScriptObservation, running_owned_engine, loaded_relative_modules
from adapters.normal_ui import NativeUIError
from fixture.serve import FixtureState
from self_tests.test_native_feature_observation import probe_source


class Boundary:
    def __init__(self):
        self.sequence, self.clock, self.okay, self.ignore = 0, 0.0, True, False
        self.commands, self.sample, self.mutate = [], None, None
        self.engine = dict(url='file:///actual/private/owned/main.js', running=True, stopping=False, finished=False,
            required=dict(instance='a' * 32, sequence=1, modules=[dict(
                url='file:///actual/private/owned/companion.js', loaded=True, cached=False,
                sequence=1, capturedEpochMs=17000)]))

    def send(self, command):
        self.commands.append(command)
        if self.ignore: return
        self.sequence += 1
        self.sample = dict(schemaVersion=1, requestId=command['commandId'], instance='b' * 32,
            sequence=self.sequence, requestedEpochMs=20000, capturedEpochMs=20000,
            processId=31, source=dict(complete=True, engines=[deepcopy(self.engine)]))
        if self.mutate: self.mutate(self.sample)

    def original(self): return json.dumps(self.sample)
    def sleep(self, seconds): self.clock += seconds
    def reader(self, **kwargs):
        return NativeScriptObservation(self.send, self.original, lambda: 20000, lambda: self.okay,
            31, monotonic=lambda: self.clock, sleep=self.sleep, **kwargs)


class NativeScriptObservationTests(unittest.TestCase):
    def test_original_loaded_companion_keeps_native_engine_and_historical_load_time(self):
        source = Boundary(); reader = source.reader()
        first = reader.read(0); second = reader.read(first['sequence'])
        self.assertEqual(source.sample, second)
        module = second['source']['engines'][0]['required']['modules'][0]
        self.assertEqual(17000, module['capturedEpochMs'])
        self.assertTrue(module['loaded'])
        self.assertEqual(1, module['sequence'])  # Reads cannot invent module loads.
        self.assertEqual({'schemaVersion', 'commandId', 'action'}, set(source.commands[0]))

    def test_requested_main_without_real_loaded_module_never_becomes_loaded_evidence(self):
        source = Boundary()
        source.engine['required']['modules'][0]['loaded'] = False
        actual = source.reader().read(0)['source']['engines'][0]
        self.assertFalse(actual['required']['modules'][0]['loaded'])
        source.engine['required'].update(sequence=0, modules=[])
        self.assertEqual([], source.reader().read(0)['source']['engines'][0]['required']['modules'])

    def test_native_stop_disappearance_and_restart_have_distinct_real_engine_ids(self):
        source = Boundary(); reader = source.reader(); first = reader.read(0)
        source.mutate = lambda value: value['source'].update(engines=[])
        stopped = reader.read(first['sequence'])
        self.assertEqual([], stopped['source']['engines'])
        source.engine['required']['instance'] = 'c' * 32; source.mutate = None
        restarted = reader.read(stopped['sequence'])
        self.assertEqual('c' * 32, restarted['source']['engines'][0]['required']['instance'])

    def test_loaded_relative_companion_comes_from_unique_actual_engine_and_resolved_url(self):
        source = Boundary(); value = source.reader().read(0)
        engine = running_owned_engine(value, source.engine['url'])
        self.assertEqual(['companion.js'], loaded_relative_modules(engine))
        engine['required']['modules'][0]['url'] = 'file:///foreign/root/companion.js'
        self.assertEqual([], loaded_relative_modules(engine))
        engine['required']['modules'][0]['url'] = 'file:///actual/private/owned/%2e%2e/companion.js'
        with self.assertRaises(NativeUIError): loaded_relative_modules(engine)
        engine['stopping'] = True
        with self.assertRaises(NativeUIError): running_owned_engine(value, source.engine['url'])

    def test_restart_overlap_is_observed_and_ambiguous_running_instances_cannot_be_selected(self):
        source = Boundary()
        def overlap(value):
            old = deepcopy(value['source']['engines'][0]); old.update(running=False, stopping=True)
            old['required']['instance'] = 'c' * 32
            value['source']['engines'].append(old)
        source.mutate = overlap
        value = source.reader().read(0)
        self.assertEqual('a' * 32, running_owned_engine(value, source.engine['url'])['required']['instance'])
        value['source']['engines'][1].update(running=True, stopping=False)
        with self.assertRaises(NativeUIError): running_owned_engine(value, source.engine['url'])

    def test_retired_engine_cannot_reappear_inside_a_new_request_envelope(self):
        source = Boundary(); reader = source.reader(); reader.read(0)
        source.mutate = lambda value: value['source'].update(engines=[])
        reader.read(reader.sequence); source.mutate = None
        with self.assertRaises(NativeUIError): reader.read(reader.sequence)
        self.assertEqual(2, reader.sequence)

    def test_wrong_process_instance_request_and_incomplete_or_duplicated_sources_are_rejected(self):
        for fault in ('pid', 'instance', 'request', 'incomplete', 'duplicate-engine', 'duplicate-module', 'wrong-types'):
            with self.subTest(fault=fault):
                source = Boundary(); reader = source.reader(); first = reader.read(0)
                def mutate(value):
                    if fault == 'pid': value['processId'] = 99
                    elif fault == 'instance': value['instance'] = 'c' * 32
                    elif fault == 'request': value['requestId'] = 'd' * 32
                    elif fault == 'incomplete': value['source']['complete'] = False
                    elif fault == 'duplicate-engine': value['source']['engines'].append(deepcopy(value['source']['engines'][0]))
                    elif fault == 'duplicate-module': value['source']['engines'][0]['required']['modules'] *= 2
                    else: value['source']['engines'][0]['required']['modules'][0]['loaded'] = 1
                source.mutate = mutate
                with self.assertRaises(NativeUIError): reader.read(first['sequence'])
                self.assertEqual(first['sequence'], reader.sequence)

    def test_original_engine_cannot_change_source_or_regress_module_history(self):
        for fault in ('engine-url', 'source-cursor', 'missing-module', 'future-module', 'retimed-history'):
            with self.subTest(fault=fault):
                source = Boundary(); reader = source.reader(); first = reader.read(0)
                def mutate(value):
                    engine = value['source']['engines'][0]; required = engine['required']
                    if fault == 'engine-url': engine['url'] = 'file:///foreign/same-basename/main.js'
                    elif fault == 'source-cursor': required['sequence'] = 0
                    elif fault == 'missing-module': required.update(sequence=0, modules=[])
                    elif fault == 'future-module': required['modules'][0]['capturedEpochMs'] = 21000
                    else: required['modules'][0]['capturedEpochMs'] = 16000
                source.mutate = mutate
                with self.assertRaises(NativeUIError): reader.read(first['sequence'])

    def test_returned_observation_cannot_mutate_private_history_for_next_validation(self):
        source = Boundary(); reader = source.reader(); first = reader.read(0)
        first['source']['engines'][0]['required']['modules'][0]['capturedEpochMs'] = 1
        source.engine['required']['modules'][0]['capturedEpochMs'] = 16000
        with self.assertRaises(NativeUIError): reader.read(reader.sequence)

    def test_loaded_flag_or_timestamp_cannot_change_without_a_real_new_native_module_event(self):
        for fault in ('loaded', 'cached', 'retimed', 'insert-old-event'):
            with self.subTest(fault=fault):
                source = Boundary(); reader = source.reader(); reader.read(0)
                def mutate(value):
                    required = value['source']['engines'][0]['required']; module = required['modules'][0]
                    if fault == 'loaded': module['loaded'] = False
                    elif fault == 'cached': module['cached'] = True
                    elif fault == 'retimed': module['capturedEpochMs'] = 19000
                    else:
                        required['sequence'] = 2
                        module['sequence'] = 2
                        required['modules'].append(dict(url='file:///actual/private/owned/older.js',
                            loaded=True, cached=False, sequence=1, capturedEpochMs=17000))
                source.mutate = mutate
                with self.assertRaises(NativeUIError): reader.read(reader.sequence)

    def test_ignored_request_and_slow_transfer_are_bounded_and_never_repeat_product_inputs(self):
        source = Boundary(); source.ignore = True
        with self.assertRaises(NativeUIError): source.reader().read(0)
        self.assertEqual(1, len(source.commands)); self.assertLessEqual(source.clock, 5.1)
        source = Boundary(); reader = source.reader()
        def slow():
            source.clock += 5
            return source.original()
        reader.original = slow
        with self.assertRaises(NativeUIError): reader.read(0)
        self.assertEqual(0, reader.sequence)

    def test_ios_native_module_times_remain_original_across_host_clock_skew(self):
        source = Boundary(); reader = source.reader(ios=True); reader.clock_ms = lambda: 9000000
        actual = reader.read(0)
        self.assertEqual(17000, actual['source']['engines'][0]['required']['modules'][0]['capturedEpochMs'])
        self.assertTrue(source.commands[0]['commandId'].startswith('ios-'))

    def test_actual_probe_and_fixture_accept_only_closed_read_only_script_commands(self):
        fixture = FixtureState()
        command = dict(schemaVersion=1, commandId='ios-' + 'a' * 32, action='feature-script-observe')
        self.assertEqual(command, fixture.set_client_command(command))
        for extra in ({'source':'file:///owned/main.js'}, {'code':'load()'}, {'expected':['companion.js']}):
            with self.assertRaises(ValueError): fixture.set_client_command(command | extra)
        program = '''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,keys)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(keys.sort());
let calls=0,files=[];
const Test={featureScriptObservation:requestId=>{calls++;return {schemaVersion:1,requestId,source:{engines:[]}};},
 saveObject:(v,name)=>files.push({v,name})};
SOURCE
const command={schemaVersion:1,commandId:"a".repeat(32),action:"feature-script-observe"};
applyAndroidControlCommand(command);applyAndroidControlCommand(command);
if(calls!==1||files[0].name!=="feature-script-observation.json")throw Error("native read");
applyClientCommand({...command,commandId:"b".repeat(32),source:"file:///owned/main.js"});
if(calls!==1)throw Error("source input");
delete Test.featureScriptObservation;
applyClientCommand({...command,commandId:"ios-"+"c".repeat(32)});
if(files[1].v.available!==false)throw Error("missing hook green");
'''.replace('SOURCE', probe_source())
        completed = subprocess.run(['node', '-e', program], capture_output=True, text=True, timeout=5)
        self.assertEqual(0, completed.returncode, completed.stderr)


if __name__ == '__main__': unittest.main()
