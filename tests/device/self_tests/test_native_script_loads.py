"""Synthetic native callback histories exercise the original reader/probe only."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adapters.native_script_loads import result
from adapters.native_script_observation import running_owned_engine
from adapters.normal_ui import NativeUIError
from self_tests.test_native_script_observation import Boundary, code_source, effect_source
from self_tests.test_native_feature_observation import probe_source

URL = 'http://owned.invalid/run/main.js'


def event(sequence=1, **changes):
    return dict(sequence=sequence, eventId=f'{sequence:032x}', managerInstance='a' * 32,
        url=URL, loadGeneration=sequence * 2, isURL=True, success=False, status='NotFound',
        callbackEpochMs=19000 + sequence) | changes


def history(packet, events=None):
    events = [event()] if events is None else events
    packet['source'].update(loadSourceVersion=1, loads=dict(complete=True, instance='c' * 32,
        sequence=len(events), events=deepcopy(events)))


class ScriptLoadTests(unittest.TestCase):
    def source(self, events=None):
        source = Boundary(); source.mutate = lambda packet: history(packet, events)
        return source, source.reader()

    def test_actual_status_and_original_callback_epoch_survive_later_observations(self):
        source, reader = self.source()
        first = reader.read(0, require_load_history=True)
        second = reader.read(first['sequence'])
        self.assertEqual(source.sample, second)
        self.assertEqual(first['source']['loads'], second['source']['loads'])
        actual = result(second, URL, after_sequence=0, after_epoch=19000)
        self.assertEqual('NotFound', actual['status']); self.assertFalse(actual['success'])
        self.assertEqual(19001, actual['callbackEpochMs'])
        self.assertTrue(all(set(command) == {'schemaVersion', 'commandId', 'action'} for command in source.commands))

    def test_fetch_failure_and_absent_engine_are_separate_original_facts(self):
        source, reader = self.source()
        def failed(packet): history(packet); packet['source']['engines'] = []
        source.mutate = failed
        packet = reader.read(0, require_load_history=True)
        self.assertEqual('NotFound', result(packet, URL, after_sequence=0, after_epoch=19000)['status'])
        with self.assertRaises(NativeUIError): running_owned_engine(packet, URL)

    def test_successful_fetch_never_creates_running_engine_or_effects(self):
        source, reader = self.source([event(success=True, status='Cached')])
        def fetched(packet):
            history(packet, [event(success=True, status='Cached')]); packet['source']['engines'] = []
            effect_source(packet); packet['source']['effects'].update(entities=[], absentIds=[])
        source.mutate = fetched
        packet = reader.read(0, require_load_history=True, require_effects=True)
        self.assertTrue(result(packet, URL, after_sequence=0, after_epoch=19000)['success'])
        self.assertEqual([], packet['source']['effects']['entities'])
        with self.assertRaises(NativeUIError): running_owned_engine(packet, URL)

    def test_full_url_and_actual_cursor_epoch_and_manager_barriers_are_required(self):
        source, reader = self.source(); packet = reader.read(0, require_load_history=True)
        for url, sequence, epoch, manager in (
                ('http://foreign.invalid/run/main.js', 0, 19000, None),
                (URL + '?different', 0, 19000, None), (URL, 1, 19000, None),
                (URL, 0, 19002, None), (URL, 0, 19000, 'd' * 32)):
            with self.subTest(url=url, sequence=sequence, epoch=epoch, manager=manager):
                with self.assertRaises(NativeUIError):
                    result(packet, url, after_sequence=sequence, after_epoch=epoch, manager_instance=manager)

    def test_multiple_matching_callbacks_are_ambiguous_and_an_actual_later_barrier_selects_one(self):
        source, reader = self.source([event(), event(2)])
        packet = reader.read(0, require_load_history=True)
        with self.assertRaises(NativeUIError): result(packet, URL, after_sequence=0, after_epoch=19000)
        self.assertEqual(2, result(packet, URL, after_sequence=1, after_epoch=19000)['sequence'])

    def test_empty_fresh_history_does_not_prove_a_load_happened(self):
        source, reader = self.source([]); packet = reader.read(0, require_load_history=True)
        self.assertEqual([], packet['source']['loads']['events'])
        with self.assertRaises(NativeUIError): result(packet, URL, after_sequence=0, after_epoch=19000)

    def test_required_extension_cannot_be_missing_boolean_or_downgraded(self):
        source = Boundary(); reader = source.reader()
        with self.assertRaises(NativeUIError): reader.read(0, require_load_history=True)
        source.mutate = history; packet = reader.read(0, require_load_history=True)
        source.mutate = None
        with self.assertRaises(NativeUIError): reader.read(packet['sequence'])
        source.mutate = lambda value: (history(value), value['source'].update(loadSourceVersion=True))
        with self.assertRaises(NativeUIError): reader.read(packet['sequence'])

    def test_malformed_results_generations_identifiers_and_future_times_cannot_pass(self):
        for change in ({'sequence': True}, {'eventId': 'wrong'}, {'managerInstance': 'unknown'},
                {'loadGeneration': 0}, {'loadGeneration': 2**53}, {'success': True},
                {'status': 'expected-not-found'}, {'isURL': False}, {'success': 0},
                {'callbackEpochMs': 20001}, {'url': ''}, {'url': URL + '\n'}):
            with self.subTest(change=change):
                source, reader = self.source([event(**change)])
                with self.assertRaises(NativeUIError): reader.read(0, require_load_history=True)
                self.assertEqual(0, reader.sequence); self.assertIsNone(reader.loads)

    def test_inline_status_is_preserved_only_with_actual_inline_origin_and_success(self):
        source, reader = self.source([event(status='Inline', success=True, isURL=False, url='')])
        self.assertFalse(reader.read(0, require_load_history=True)['source']['loads']['events'][0]['isURL'])
        source, reader = self.source([event(status='Inline', success=True)])
        with self.assertRaises(NativeUIError): reader.read(0, require_load_history=True)

    def test_credentials_queries_fragments_and_inline_source_are_never_exportable_receipts(self):
        for url in ('http://user:secret@owned.invalid/main.js', URL + '?token=private',
                    URL + '?', URL + '#private', 'javascript:secret()', 'secret code'):
            with self.subTest(url=url):
                source, reader = self.source([event(url=url)])
                with self.assertRaises(NativeUIError): reader.read(0, require_load_history=True)
        source, reader = self.source([event(status='Inline', success=True, isURL=False, url='secret code')])
        with self.assertRaises(NativeUIError): reader.read(0, require_load_history=True)

    def test_duplicate_identity_generation_and_regressing_history_time_are_invalid(self):
        for second in (event(2, eventId=event()['eventId']), event(2, loadGeneration=2),
                       event(2, callbackEpochMs=19000)):
            with self.subTest(second=second):
                source, reader = self.source([event(), second])
                with self.assertRaises(NativeUIError): reader.read(0, require_load_history=True)

    def test_original_prefix_cannot_be_rewritten_truncated_or_replaced(self):
        for fault in ('retimed', 'status-replaced', 'lost-prefix', 'new-instance', 'incomplete'):
            with self.subTest(fault=fault):
                source, reader = self.source(); first = reader.read(0, require_load_history=True)
                def corrupt(packet):
                    history(packet)
                    loads = packet['source']['loads']
                    if fault == 'retimed': loads['events'][0]['callbackEpochMs'] += 1
                    elif fault == 'status-replaced': loads['events'][0]['status'] = 'Timeout'
                    elif fault == 'lost-prefix': loads.update(sequence=0, events=[])
                    elif fault == 'new-instance': loads['instance'] = 'd' * 32
                    else: loads['complete'] = False
                source.mutate = corrupt
                with self.assertRaises(NativeUIError): reader.read(first['sequence'])
                self.assertEqual(first['sequence'], reader.sequence)
                self.assertEqual(first['source']['loads'], reader.loads)

    def test_new_manager_or_new_generation_appends_without_retiming_prior_events(self):
        source, reader = self.source(); first = reader.read(0, require_load_history=True)
        events = [event(), event(2), event(3, managerInstance='d' * 32, loadGeneration=2)]
        source.mutate = lambda packet: history(packet, events)
        second = reader.read(first['sequence'])
        self.assertEqual(events, second['source']['loads']['events'])
        self.assertEqual(first['source']['loads']['events'], events[:1])

    def test_caller_mutation_and_failed_final_clock_do_not_corrupt_frozen_history(self):
        source, reader = self.source(); first = reader.read(0, require_load_history=True)
        frozen = deepcopy(reader.loads); first['source']['loads']['events'][0]['status'] = 'Timeout'
        source.mutate = lambda packet: history(packet, [event(), event(2)])
        calls = [0]
        def clock():
            calls[0] += 1
            return 20000 if calls[0] == 1 else 19800
        reader.clock_ms = clock
        with self.assertRaises(NativeUIError): reader.read(reader.sequence)
        self.assertEqual(frozen, reader.loads); self.assertEqual(1, reader.sequence)

    def test_all_existing_source_extensions_compose_without_retiming_original_evidence(self):
        source, reader = self.source()
        def observed(packet): history(packet); code_source(packet); effect_source(packet)
        source.mutate = observed
        packet = reader.read(0, require_load_history=True, require_code_identity=True, require_effects=True)
        self.assertEqual(15000, packet['source']['engines'][0]['code']['submittedEpochMs'])
        self.assertEqual(17000, packet['source']['engines'][0]['required']['modules'][0]['capturedEpochMs'])
        self.assertEqual(19000000, packet['source']['effects']['entities'][0]['lastEditedEpochUs'])

    def test_count_bound_and_unavailable_source_are_not_truncated_successful_inventories(self):
        for count in (256, 257):
            events = [event(index, callbackEpochMs=19000) for index in range(1, count + 1)]
            source, reader = self.source(events)
            if count == 256: self.assertEqual(count, reader.read(0, require_load_history=True)['source']['loads']['sequence'])
            else:
                with self.assertRaises(NativeUIError): reader.read(0, require_load_history=True)

    def test_original_probe_passes_native_history_unchanged_and_does_not_replay(self):
        source, reader = self.source(); packet = reader.read(0, require_load_history=True)
        program = '''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,keys)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(keys.sort());
const original=PACKET;let calls=0,files=[];
const Test={featureScriptObservation:id=>{calls++;return {...original,requestId:id};},
saveObject:(v,name)=>files.push({v,name})};
SOURCE
const command={schemaVersion:1,commandId:"a".repeat(32),action:"feature-script-observe"};
applyAndroidControlCommand(command);applyAndroidControlCommand(command);
if(calls!==1||files.length!==1||files[0].name!=="feature-script-observation.json")throw Error("replay/path");
if(JSON.stringify(files[0].v.source.loads)!==JSON.stringify(original.source.loads))throw Error("retimed/replaced");
'''.replace('PACKET', json.dumps(packet)).replace('SOURCE', probe_source())
        completed = subprocess.run(['node', '-e', program], capture_output=True, text=True, timeout=5)
        self.assertEqual(0, completed.returncode, completed.stderr)


if __name__ == '__main__': unittest.main()
