"""Synthetic kernel/native sources; exercise original host/probe logic only."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adapters.native_process_presence import NativeProcessPresence, command
from adapters.normal_ui import NativeUIError
from fixture.serve import FixtureState
from self_tests.test_native_feature_observation import probe_source


class Boundary:
    def __init__(self, *, pid=31, epoch_ms=lambda: 20000):
        self.pid, self.epoch_ms = pid, epoch_ms
        self.clock = 0.; self.sequence = 0; self.commands = []; self.value = None
        self.presence, self.ignored, self.okay, self.edit = 'present', False, True, None
    def send(self, request):
        self.commands.append(deepcopy(request))
        if self.ignored: return
        self.sequence += 1
        result, error, symbol = {'present': (0, 0, 'NONE'), 'absent': (-1, 3, 'ESRCH'),
            'unknown': (-1, 1, 'EPERM')}[self.presence]
        self.value = dict(processPresenceVersion=1, commandId=request['commandId'], instance='a' * 32,
            sequence=self.sequence, processId=self.pid, queryProcessId=request['queryProcessId'],
            requestedEpochMs=self.epoch_ms(), capturedEpochMs=self.epoch_ms(), presence=self.presence,
            nativeResult=result, nativeError=error, errorSymbol=symbol)
        if self.edit: self.edit(self.value)
    def original(self): return json.dumps(self.value)
    def sleep(self, seconds): self.clock += seconds
    def reader(self, *, ios=False):
        return NativeProcessPresence(self.send, self.original, self.epoch_ms, lambda: self.okay, self.pid,
            ios=ios, monotonic=lambda: self.clock, sleep=self.sleep)


class ProcessPresenceTests(unittest.TestCase):
    def test_present_unknown_and_original_absence_are_distinct_and_only_absence_qualifies(self):
        source = Boundary(); reader = source.reader()
        for state in ('present', 'unknown'):
            source.presence = state
            self.assertEqual(state, reader.read(29)['presence'])
            with self.assertRaises(NativeUIError): reader.require_absent(29)
        source.presence = 'absent'; actual = reader.require_absent(29)
        self.assertEqual(source.value, actual); self.assertEqual('ESRCH', actual['errorSymbol'])
        self.assertEqual(29, actual['queryProcessId']); self.assertEqual(31, actual['processId'])
        self.assertEqual(5, len(source.commands))

    def test_current_process_can_be_present_but_can_never_report_its_own_absence(self):
        source = Boundary(); reader = source.reader()
        self.assertEqual('present', reader.read(31)['presence'])
        source.presence = 'absent'
        with self.assertRaises(NativeUIError): reader.require_absent(31)
        self.assertEqual(1, reader.last['sequence'])

    def test_permission_unknown_cannot_become_absence_by_relabelling_or_missing_error(self):
        for changed in ({'presence': 'absent'}, {'presence': 'absent', 'errorSymbol': 'NONE'},
                        {'presence': 'absent', 'errorSymbol': 'ESRCH'},
                        {'nativeError': 0}, {'nativeResult': 0}, {'presence': False}):
            with self.subTest(changed=changed):
                source = Boundary(); source.presence = 'unknown'; source.edit = lambda value: value.update(changed)
                reader = source.reader()
                with self.assertRaises(NativeUIError): reader.require_absent(29)
                self.assertIsNone(reader.last)

    def test_foreign_query_process_request_version_and_types_never_qualify(self):
        for changed in ({'queryProcessId': 28}, {'processId': 32}, {'commandId': 'f' * 32},
                        {'processPresenceVersion': True}, {'nativeResult': False}, {'nativeError': True},
                        {'queryProcessId': 29.0}, {'sequence': 0}, {'errorSymbol': 'expected-dead'}):
            with self.subTest(changed=changed):
                source = Boundary(); source.presence = 'absent'; source.edit = lambda value: value.update(changed)
                reader = source.reader()
                with self.assertRaises(NativeUIError): reader.require_absent(29)
                self.assertIsNone(reader.last)

    def test_current_nonce_does_not_rescue_stale_or_precommand_kernel_observation(self):
        for requested, captured in ((18000, 18000), (19999, 20000), (20000, 21000)):
            with self.subTest(requested=requested, captured=captured):
                source = Boundary(); source.presence = 'absent'
                source.edit = lambda value: value.update(requestedEpochMs=requested, capturedEpochMs=captured)
                reader = source.reader(ios=True)
                with self.assertRaises(NativeUIError): reader.require_absent(29)
                self.assertIsNone(reader.last); self.assertEqual(1, len(source.commands))

    def test_missing_partial_unavailable_oversized_and_duplicate_results_are_not_empty_success(self):
        for raw in ('', '{', '{"commandId":"a","commandId":"b"}', ' ' * 8193):
            with self.subTest(raw=raw[:40]):
                source = Boundary(); reader = source.reader(); reader.original = lambda: raw
                with self.assertRaises(NativeUIError): reader.require_absent(29)
                self.assertEqual(1, len(source.commands)); self.assertIsNone(reader.last)
        source = Boundary(); source.ignored = True; reader = source.reader()
        with self.assertRaises(NativeUIError): reader.require_absent(29)
        self.assertEqual(1, len(source.commands))

    def test_reused_sequence_replaced_birth_and_regressing_capture_fail_without_committing(self):
        for changed in ({'sequence': 1}, {'instance': 'f' * 32},
                        {'requestedEpochMs': 19999, 'capturedEpochMs': 19999}):
            with self.subTest(changed=changed):
                source = Boundary(); reader = source.reader(); first = reader.read(29)
                source.presence = 'absent'; source.edit = lambda value: value.update(changed)
                with self.assertRaises(NativeUIError): reader.require_absent(29)
                self.assertEqual(first, reader.last)

    def test_independent_clock_and_whole_deadline_include_initial_and_final_acquisition(self):
        for fault in ('late-initial', 'late-final', 'rewound', 'native-clock-regressed', 'lost-owner'):
            with self.subTest(fault=fault):
                source = Boundary(); source.presence = 'absent'; reader = source.reader(ios=True); calls = [0]
                def clock():
                    calls[0] += 1
                    if fault == 'late-initial': source.clock = 6
                    elif calls[0] == 2:
                        if fault == 'late-final': source.clock = 6
                        elif fault == 'rewound': source.clock = -1
                        elif fault == 'native-clock-regressed': return 19800
                        else: source.okay = False
                    return 20000
                reader.clock_ms = clock
                with self.assertRaises(NativeUIError): reader.require_absent(29)
                self.assertIsNone(reader.last)
                self.assertEqual(0 if fault == 'late-initial' else 1, len(source.commands))

    def test_caller_mutation_cannot_replace_the_readers_previous_original(self):
        source = Boundary(); reader = source.reader(); value = reader.read(29)
        original = deepcopy(value); value['presence'] = 'absent'; value['instance'] = 'f' * 32
        self.assertEqual(original, reader.last)
        self.assertEqual('present', reader.read(28)['presence'])

    def test_closed_command_rejects_expected_results_arbitrary_paths_and_non_pid_values_before_send(self):
        source = Boundary(); reader = source.reader()
        for pid in (True, False, 0, -1, 2147483648, '29', 29.0):
            with self.subTest(pid=pid), self.assertRaises(NativeUIError): reader.read(pid)
        self.assertEqual([], source.commands)
        fixture = FixtureState(); request = dict(schemaVersion=1, commandId='ios-' + 'a' * 32,
            action='feature-process-presence', queryProcessId=29)
        self.assertEqual(request, fixture.set_client_command(request))
        for extra in ({'expected': 'absent'}, {'signal': 9}, {'path': '/proc/29/stat'}):
            with self.assertRaises(ValueError): fixture.set_client_command(request | extra)
        with self.assertRaises(NativeUIError): command(request, ios=False)

    def test_original_probe_preserves_actual_result_deduplicates_and_rejects_expected_outcomes(self):
        source = Boundary(); source.presence = 'unknown'; actual = source.reader().read(29)
        program = '''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,keys)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(keys.sort());
const original=PACKET;let calls=0,files=[];
const Test={featureProcessPresence:c=>{calls++;return {...original,commandId:c.commandId};},saveObject:(v,name)=>files.push({v,name})};
SOURCE
const c={schemaVersion:1,commandId:"a".repeat(32),action:"feature-process-presence",queryProcessId:29};
applyAndroidControlCommand(c);applyAndroidControlCommand(c);
if(calls!==1||files[0].name!=="feature-process-presence.json"||files[0].v.presence!=="unknown")throw Error("result/replay");
applyClientCommand({...c,commandId:"b".repeat(32),expected:"absent"});
if(calls!==1)throw Error("expected outcome admitted");
delete Test.featureProcessPresence;applyClientCommand({...c,commandId:"ios-"+"c".repeat(32)});
if(files[1].v.available!==false)throw Error("unavailable green");
'''.replace('PACKET', json.dumps(actual)).replace('SOURCE', probe_source())
        result = subprocess.run(['node', '-e', program], capture_output=True, text=True, timeout=5)
        self.assertEqual(0, result.returncode, result.stderr)


if __name__ == '__main__': unittest.main()
