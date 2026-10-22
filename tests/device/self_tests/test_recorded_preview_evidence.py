"""No-device checks for original PCM provenance, transport and cleanup."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import array
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adapters.recorded_preview_evidence import RecordedPreviewEvidence, AndroidPreviewFiles, INPUT, SINK
from adapters.normal_ui import NativeUIError
from fixture.serve import FixtureState
from self_tests.test_native_feature_observation import probe_source


class Boundary:
    def __init__(self):
        # Original-source bytes deliberately differ between input and sink.
        self.files = {INPUT: array.array('h', [100, -100] * 12000).tobytes(),
                      SINK: b'\0' * 48000 + array.array('h', [400, -400] * 12000).tobytes()}
        self.commands, self.value = [], None
        self.sequence, self.clock, self.cycle = 0, 0.0, 7
        self.ignore, self.okay, self.retain, self.mutate = False, True, False, None

    def send(self, command):
        self.commands.append(command)
        if self.ignore: return
        if command['action'].endswith('files'):
            self.sequence += 1
            self.value = dict(schemaVersion=1, requestId=command['commandId'], instance='c' * 32,
                sequence=self.sequence, requestedEpochMs=20000, capturedEpochMs=20000, processId=31,
                memoryEmpty=True, files=[dict(name=name, exists=name in self.files) for name in (INPUT, SINK)])
            if self.mutate: self.mutate(self.value)
            return
        if command['action'].endswith('release'):
            if not self.retain: self.files.clear()
            self.value = dict(schemaVersion=1, requestId=command['commandId'], released=True)
            return
        self.sequence += 1
        def file(name, tap):
            raw = self.files[name]
            return dict(name=name, tap=tap, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
        def event(sequence, phase, captured, played, epoch):
            return dict(schemaVersion=1, eventSequence=sequence, publishedEpochMs=epoch, phase=phase,
                error='', capturedBytes=captured, playedBytes=played, totalBytes=48000)
        self.value = dict(schemaVersion=1, requestId=command['commandId'], instance='c' * 32,
            sequence=self.sequence, requestedEpochMs=20000, capturedEpochMs=20000, processId=31,
            source=dict(cycle=self.cycle, startedEpochMs=13000, sampleRate=8000, channels=1,
                inputLastEpochMs=16000, sinkLastEpochMs=19000,
                events=[event(10, 'capturing', 0, 0, 13000), event(11, 'playing', 48000, 0, 16000),
                        event(12, 'draining', 48000, 48000, 19000), event(13, 'completed', 48000, 48000, 19500)],
                input=file(INPUT, 'capture-before-normalization'),
                sink=file(SINK, 'loopback-device-accepted-write')))
        if self.mutate: self.mutate(self.value)

    def sleep(self, seconds): self.clock += seconds

    def reader(self, **kwargs):
        return RecordedPreviewEvidence(self.send, lambda: json.dumps(self.value), self.files.get,
            lambda: 20000, lambda: self.okay, 31, monotonic=lambda: self.clock, sleep=self.sleep, **kwargs)


class RecordedPreviewEvidenceTests(unittest.TestCase):
    def test_original_separate_taps_and_native_cycle_history_survive_without_desired_inputs(self):
        native = Boundary(); reader = native.reader()
        packet, raw = reader.read(0, after_cycle=6)
        self.assertEqual(native.value, packet)
        self.assertEqual(native.files[INPUT], raw['input'])
        self.assertEqual(native.files[SINK], raw['sink'])
        self.assertNotEqual(raw['input'], raw['sink'])
        self.assertEqual(13000, packet['source']['startedEpochMs'])
        self.assertEqual({'schemaVersion', 'commandId', 'action'}, set(native.commands[0]))
        self.assertEqual('feature-recorded-audio-observe', native.commands[0]['action'])

    def test_foreign_missing_malformed_and_stale_cycle_evidence_cannot_pass(self):
        for fault in ('pid', 'instance', 'sequence', 'cycle', 'empty-source', 'missing-hook', 'old',
                      'wrong-tap', 'wrong-path', 'unaligned', 'event-replay', 'event-regression', 'incomplete', 'retimed-input'):
            with self.subTest(fault=fault):
                native = Boundary(); reader = native.reader()
                first, _raw = reader.read(0)
                def mutate(value):
                    source = value['source']
                    if fault == 'pid': value['processId'] = 999
                    elif fault == 'instance': value['instance'] = 'd' * 32
                    elif fault == 'sequence': value['sequence'] = first['sequence']
                    elif fault == 'cycle': source['cycle'] -= 1
                    elif fault == 'empty-source': source.clear()
                    elif fault == 'missing-hook': value.update(available=False)
                    elif fault == 'old': value['capturedEpochMs'] = 15000
                    elif fault == 'wrong-tap': source['sink']['tap'] = 'synthesized-desired-preview'
                    elif fault == 'wrong-path': source['input']['name'] = '../foreign.pcm'
                    elif fault == 'unaligned': source['input']['bytes'] -= 1
                    elif fault == 'event-replay': source['events'][-1]['eventSequence'] = 11
                    elif fault == 'event-regression': source['events'][-1]['capturedBytes'] = 0
                    elif fault == 'incomplete': source['events'][-1]['playedBytes'] = 46000
                    else: source['inputLastEpochMs'] = 20001
                native.mutate = mutate
                with self.assertRaises(NativeUIError): reader.read(first['sequence'])
                self.assertEqual(first['sequence'], reader.sequence)

    def test_same_cycle_new_envelope_cannot_rewrite_original_events_bytes_or_timestamps(self):
        for fault in ('event', 'drop', 'input', 'sink', 'retime', 'format', 'start'):
            with self.subTest(fault=fault):
                native = Boundary(); reader = native.reader(); first, _ = reader.read(0)
                if fault in ('input', 'sink'):
                    name = INPUT if fault == 'input' else SINK
                    native.files[name] = b'x' * len(native.files[name])
                else:
                    def mutate(value):
                        source = value['source']
                        if fault == 'event': source['events'][0]['publishedEpochMs'] += 1
                        elif fault == 'drop': source['events'].pop(0)
                        elif fault == 'retime': source['inputLastEpochMs'] += 1
                        elif fault == 'format': source['sampleRate'] = 16000
                        else: source['startedEpochMs'] += 1
                    native.mutate = mutate
                with self.assertRaises(NativeUIError): reader.read(first['sequence'])
                self.assertEqual(first['sequence'], reader.sequence)

    def test_first_completed_packet_requires_real_drain_contiguous_events_and_legal_phases(self):
        for fault in ('drain', 'gap', 'phase', 'error', 'frame'):
            with self.subTest(fault=fault):
                native = Boundary()
                def mutate(value):
                    events = value['source']['events']
                    if fault == 'drain': events.pop(2)
                    elif fault == 'gap': events[1]['eventSequence'] += 5
                    elif fault == 'phase': events[0]['phase'] = 'playing'
                    elif fault == 'error': events[1]['error'] = 'hidden-failure'
                    else: events[0]['capturedBytes'] = 1
                native.mutate = mutate
                with self.assertRaises(NativeUIError): native.reader().read(0)

    def test_new_request_and_envelope_cannot_make_previous_recording_a_new_capture(self):
        native = Boundary(); reader = native.reader()
        packet, _raw = reader.read(0)
        with self.assertRaises(NativeUIError): reader.read(packet['sequence'], after_cycle=7)
        self.assertEqual(1, reader.sequence)

    def test_foreign_or_truncated_original_bytes_are_detected_separately_from_metadata(self):
        for fault in ('missing', 'changed', 'truncated'):
            with self.subTest(fault=fault):
                native = Boundary(); reader = native.reader()
                reader.bytes = lambda name: None if fault == 'missing' else (
                    b'x' * len(native.files[name]) if fault == 'changed' else native.files[name][:-2])
                with self.assertRaises(NativeUIError): reader.read(0)
                self.assertEqual(0, reader.sequence)

    def test_release_checks_actual_absence_and_is_idempotent(self):
        native = Boundary(); reader = native.reader()
        reader.read(0); reader.release(); reader.release()
        self.assertEqual({}, native.files)
        self.assertEqual(5, len(native.commands))

    def test_quitted_cleanup_with_remaining_files_and_lost_process_cannot_pass(self):
        native = Boundary(); native.retain = True; reader = native.reader()
        with self.assertRaises(NativeUIError): reader.release()
        self.assertIn(INPUT, native.files)
        native.okay = False
        with self.assertRaises(NativeUIError): reader.release()
        self.assertEqual(2, len(native.commands))

    def test_separate_cleanup_query_rejects_foreign_stale_or_incomplete_actual_observations(self):
        for fault in ('pid', 'foreign', 'old', 'missing-file-row', 'memory-not-empty', 'false-absence'):
            with self.subTest(fault=fault):
                native = Boundary(); reader = native.reader(ios=fault != 'false-absence')
                reader.read(0)
                if fault == 'false-absence': native.retain = True
                def mutate(value):
                    if 'files' not in value: return
                    if fault == 'pid': value['processId'] = 999
                    elif fault == 'foreign': value['instance'] = 'd' * 32
                    elif fault == 'old': value['sequence'] = 1
                    elif fault == 'missing-file-row': value['files'].pop()
                    elif fault == 'memory-not-empty': value['memoryEmpty'] = False
                    else:
                        for row in value['files']: row['exists'] = False
                native.mutate = mutate
                with self.assertRaises(NativeUIError): reader.release()
                self.assertEqual(1, reader.sequence)

    def test_ignored_or_foreign_request_is_bounded_without_replaying_any_input(self):
        for fault in ('ignored', 'foreign'):
            native = Boundary(); native.ignore = fault == 'ignored'
            if fault == 'foreign': native.mutate = lambda v: v.update(requestId='e' * 32)
            with self.assertRaises(NativeUIError): native.reader().read(0)
            self.assertEqual(1, len(native.commands))
            self.assertLessEqual(native.clock, 5.1)

    def test_native_clock_skew_is_preserved_for_ios_and_never_retimes_pcm(self):
        native = Boundary(); reader = native.reader(ios=True); reader.clock_ms = lambda: 9000000
        value, raw = reader.read(0)
        self.assertEqual(16000, value['source']['inputLastEpochMs'])
        self.assertEqual(native.files[INPUT], raw['input'])
        self.assertTrue(native.commands[0]['commandId'].startswith('ios-'))

    def test_transfer_overrun_cannot_accept_even_matching_bytes(self):
        native = Boundary(); reader = native.reader()
        def transfer(name):
            native.clock += 3
            return native.files[name]
        reader.bytes = transfer
        with self.assertRaises(NativeUIError): reader.read(0)
        self.assertEqual(0, reader.sequence)

    def test_closed_fixture_http_command_inventory_rejects_expected_audio_or_paths(self):
        fixture = FixtureState()
        for action in ('feature-recorded-audio-observe', 'feature-recorded-audio-release', 'feature-recorded-audio-files'):
            command = dict(schemaVersion=1, commandId='ios-' + 'c' * 32, action=action)
            self.assertEqual(command, fixture.set_client_command(command))
            for extra in ({'expected': 'silence'}, {'filename': INPUT}, {'samples': [0]}):
                with self.assertRaises(ValueError): fixture.set_client_command(command | extra)

    def test_actual_probe_closed_commands_only_acquire_and_release_native_evidence(self):
        program = '''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,keys)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(keys.sort());
let reads=0,releases=0,files=[];
const Test={featureRecordedVoiceEvidence:requestId=>{reads++;return {schemaVersion:1,requestId,source:{cycle:7}};},
 featureRecordedVoiceFiles:requestId=>({schemaVersion:1,requestId,files:[],memoryEmpty:true}),
 releaseFeatureRecordedVoiceEvidence:requestId=>{releases++;return {schemaVersion:1,requestId,released:true};},
 saveObject:(v,name)=>files.push({v,name})};
SOURCE
const c={schemaVersion:1,commandId:"a".repeat(32),action:"feature-recorded-audio-observe"};
applyAndroidControlCommand(c);applyAndroidControlCommand(c);
if(reads!==1||files[0].name!=="recorded-preview-observation.json"||files[0].v.source.cycle!==7)throw Error("original read");
applyClientCommand({...c,commandId:"b".repeat(32),samples:[1,2,3]});
if(reads!==1)throw Error("supplied samples");
applyClientCommand({...c,commandId:"ios-"+"c".repeat(32),action:"feature-recorded-audio-release"});
if(releases!==1||files[1].v.released!==true)throw Error("native release");
applyClientCommand({...c,commandId:"e".repeat(32),action:"feature-recorded-audio-files"});
if(files[2].v.memoryEmpty!==true||releases!==1)throw Error("independent filesystem read");
delete Test.featureRecordedVoiceEvidence;
applyClientCommand({...c,commandId:"d".repeat(32)});
if(files[3].v.available!==false)throw Error("missing native source green");
'''.replace('SOURCE', probe_source())
        result = subprocess.run(['node', '-e', program], capture_output=True, text=True, timeout=5)
        self.assertEqual(0, result.returncode, result.stderr)

    def test_real_android_file_script_enforces_private_original_regular_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); directory = root / 'files/overte-e2e'
            directory.mkdir(parents=True, mode=0o700)
            class LocalBoundary:
                def execute_bytes(self, command, *, target, timeout):
                    self.assertions(command, target, timeout)
                    args = shlex.split(command[1])
                    return subprocess.run(args[2:], cwd=root, capture_output=True, timeout=timeout).stdout
                def assertions(self, command, target, timeout):
                    if command[0] != 'exec-out' or target != 'test-target' or timeout != 5:
                        raise AssertionError('Unexpected native boundary')
            reader = AndroidPreviewFiles(LocalBoundary(), 'test-target', 'org.example.client', lambda: True)
            self.assertIsNone(reader(INPUT))
            path = directory / INPUT; original = b'\0\xffOVT_PREVIEW_BYTES_END_V1\n\x10\x01'
            path.write_bytes(original); path.chmod(0o600)
            self.assertEqual(original, reader(INPUT))
            path.chmod(0o644)
            with self.assertRaises(NativeUIError): reader(INPUT)
            path.unlink(); path.symlink_to('/dev/null')
            with self.assertRaises(NativeUIError): reader(INPUT)
            with self.assertRaises(NativeUIError): reader('../foreign')


if __name__ == '__main__': unittest.main()
