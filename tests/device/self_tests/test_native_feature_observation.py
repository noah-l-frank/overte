"""Device-free counterexamples for original native feature observation reads."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adapters.native_feature_observation import NativeFeatureObservation, validate, LIMIT
from adapters.normal_ui import NativeUIError


class Boundary:
    def __init__(self):
        self.clock, self.sequence = 0.0, 0
        self.commands, self.sample, self.mutate = [], None, None
        self.ignored, self.guard_okay, self.guards = False, True, 0

    def send(self, command):
        self.commands.append(command)
        if self.ignored:
            return
        self.sequence += 1
        self.sample = dict(schemaVersion=1, requestId=command['commandId'], instance='a' * 32,
            sequence=self.sequence, capturedEpochMs=20000, processId=123,
            lifecycle=dict(backgrounds=0, activations=1, launches=1),
            animation=dict(rigId=2, capturedEpochMs=20000, evaluationSequence=self.sequence + 10,
                animationsEnabled=True, graphLoaded=True, overrideActive=True,
                joints=[[0.0, 0.0, 0.0, 1.0, 0.1, 0.2, 0.3]],
                clip=dict(url='file:///actual/bundled/Sit2.fbx', requestedUrl='file:///actual/bundled/Sit2.fbx', frame=25.5, firstFrame=0.0,
                    lastFrame=120.0, framesPerSecond=60.0, loop=False, loadedFrames=121,
                    evaluatedEpochMs=20000, evaluationSequence=self.sequence + 100)),
            graphics=dict(requestedResolutionScale=0.65, applicationResolutionScale=0.65,
                shadowsSetting=False, mirrorsSetting=False, hazeSetting=False,
                localLightingSetting=False, proceduralMaterialsSetting=False,
                deferredRenderingAvailable=False), audio=dict(recording=False, muted=True),
            account=dict(loggedIn=False, principalSha256='b' * 64))
        if self.mutate:
            self.mutate(self.sample)

    def guard(self):
        self.guards += 1
        return self.guard_okay

    def original(self):
        return json.dumps(self.sample) if self.sample is not None else ''

    def sleep(self, seconds):
        self.clock += seconds

    def reader(self, **kwargs):
        return NativeFeatureObservation(self.send, self.original, lambda: 20000,
            self.guard, 123, monotonic=lambda: self.clock, sleep=self.sleep, **kwargs)


class NativeFeatureObservationTests(unittest.TestCase):
    @staticmethod
    def recorded(value):
        value['audio']['recordedVoice'] = dict(active=True, capturedBytes=4000, playedBytes=0,
            frameBytes=4, sampleRate=48000, channels=2, event=dict(schemaVersion=1, eventSequence=1,
                publishedEpochMs=20000, phase='capturing', error='', capturedBytes=4000,
                playedBytes=0, totalBytes=576000))

    def test_real_recorded_voice_source_is_distinct_from_file_recording_and_retains_native_event_time(self):
        boundary = Boundary(); boundary.mutate = self.recorded
        value = boundary.reader().read(0, require_recorded_voice=True)
        self.assertFalse(value['audio']['recording'])
        self.assertTrue(value['audio']['recordedVoice']['active'])
        self.assertEqual(4000, value['audio']['recordedVoice']['capturedBytes'])
        self.assertEqual(20000, value['audio']['recordedVoice']['event']['publishedEpochMs'])
        def completed(value):
            self.recorded(value)
            voice = value['audio']['recordedVoice']
            voice.update(active=False, capturedBytes=0, playedBytes=0)
            voice['event'].update(publishedEpochMs=10000, phase='completed', capturedBytes=576000, playedBytes=576000)
        boundary.mutate = completed
        actual = boundary.reader().read(0, require_recorded_voice=True)['audio']['recordedVoice']
        self.assertEqual(10000, actual['event']['publishedEpochMs'])
        self.assertEqual(0, actual['capturedBytes'])
        self.assertEqual(576000, actual['event']['capturedBytes'])

    def test_missing_stale_incomplete_or_regressing_recorded_voice_evidence_cannot_pass(self):
        boundary = Boundary()
        with self.assertRaises(NativeUIError): boundary.reader().read(0, require_recorded_voice=True)
        for fault in ('old-active-event', 'counter', 'event-regressed', 'event-missing'):
            with self.subTest(fault=fault):
                boundary = Boundary(); boundary.mutate = self.recorded
                reader = boundary.reader(); first = reader.read(0, require_recorded_voice=True)
                def mutate(value):
                    self.recorded(value)
                    voice = value['audio']['recordedVoice']
                    if fault == 'old-active-event': voice['event']['publishedEpochMs'] = 1
                    elif fault == 'counter': voice['playedBytes'] = 9000
                    elif fault == 'event-regressed': voice['event']['eventSequence'] = 0
                    else: voice.update(active=False, event={})
                boundary.mutate = mutate
                with self.assertRaises(NativeUIError): reader.read(first['sequence'], require_recorded_voice=True)

    def test_original_actual_values_and_source_metadata_survive_without_expected_state_input(self):
        boundary = Boundary()
        reader = boundary.reader()
        first = reader.read(0, require_animation=True)
        self.assertEqual(boundary.sample, first)
        self.assertEqual('file:///actual/bundled/Sit2.fbx', first['animation']['clip']['url'])
        self.assertEqual(0.65, first['graphics']['applicationResolutionScale'])
        self.assertEqual(25.5, first['animation']['clip']['frame'])
        self.assertEqual(20000, first['animation']['capturedEpochMs'])
        second = reader.read(first['sequence'], require_animation=True)
        self.assertGreater(second['animation']['evaluationSequence'], first['animation']['evaluationSequence'])
        self.assertEqual({'schemaVersion', 'commandId', 'action'}, set(boundary.commands[0]))
        self.assertEqual('feature-native-observe', boundary.commands[0]['action'])
        self.assertGreaterEqual(boundary.guards, 8)

    def test_missing_hook_matching_incomplete_or_stale_native_packet_cannot_pass(self):
        mutations = [lambda v: v.clear(), lambda v: v.update(available=False),
            lambda v: v.update(capturedEpochMs=1), lambda v: v.update(processId=999),
            lambda v: v.update(schemaVersion=True), lambda v: v.update(sequence=0),
            lambda v: v['lifecycle'].update(launches=0),
            lambda v: v['graphics'].update(applicationResolutionScale=True),
            lambda v: v['audio'].update(recording='false'),
            lambda v: v['account'].update(principalSha256='private account name')]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                boundary = Boundary(); boundary.mutate = mutate
                reader = boundary.reader()
                with self.assertRaises(NativeUIError): reader.read(0)
                self.assertEqual(0, reader.sequence)

    def test_ignored_and_foreign_request_cannot_relabel_old_native_capture(self):
        for fault in ('ignored', 'foreign'):
            with self.subTest(fault=fault):
                boundary = Boundary()
                boundary.ignored = fault == 'ignored'
                if fault == 'foreign': boundary.mutate = lambda v: v.update(requestId='f' * 32)
                with self.assertRaises(NativeUIError): boundary.reader().read(0)
                self.assertEqual(1, len(boundary.commands))
                self.assertLessEqual(boundary.clock, 5.1)

    def test_new_request_stamp_cannot_refresh_old_animation_or_unevaluated_clip(self):
        mutations = [lambda v: v['animation'].update(capturedEpochMs=1),
            lambda v: v['animation']['clip'].update(evaluatedEpochMs=1),
            lambda v: v['animation']['clip'].update(loadedFrames=0),
            lambda v: v['animation']['clip'].update(evaluationSequence=0),
            lambda v: v['animation'].update(graphLoaded=False),
            lambda v: v['animation'].update(animationsEnabled=False),
            lambda v: v['animation'].update(joints=[]),
            lambda v: v['animation'].pop('clip')]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                boundary = Boundary(); boundary.mutate = mutate
                with self.assertRaises(NativeUIError): boundary.reader().read(0, require_animation=True)

    def test_nonadvancing_native_evaluation_and_rig_instance_change_are_rejected(self):
        for fault in ('stale-pose', 'rig', 'instance', 'lifecycle-regressed'):
            with self.subTest(fault=fault):
                boundary = Boundary(); reader = boundary.reader()
                first = reader.read(0, require_animation=True)
                def mutate(value):
                    if fault == 'stale-pose': value['animation']['evaluationSequence'] = first['animation']['evaluationSequence']
                    elif fault == 'rig': value['animation']['rigId'] += 1
                    elif fault == 'instance': value['instance'] = 'c' * 32
                    else: value['lifecycle']['activations'] = 0
                boundary.mutate = mutate
                with self.assertRaises(NativeUIError): reader.read(first['sequence'], require_animation=True)
                self.assertEqual(first['sequence'], reader.sequence)

    def test_animation_unavailable_remains_explicit_for_other_feature_readers(self):
        boundary = Boundary(); boundary.mutate = lambda v: v.update(animation={})
        self.assertEqual({}, boundary.reader().read(0)['animation'])
        with self.assertRaises(NativeUIError): boundary.reader().read(0, require_animation=True)

    def test_final_idle_pose_is_native_data_not_an_invented_clip(self):
        boundary = Boundary()
        def idle(value):
            value['animation']['overrideActive'] = False
            value['animation'].pop('clip')
        boundary.mutate = idle
        self.assertNotIn('clip', boundary.reader().read(0, require_animation=True)['animation'])

    def test_new_requested_asset_does_not_relabel_the_previous_loaded_animation(self):
        boundary = Boundary()
        boundary.mutate = lambda v: v['animation']['clip'].update(requestedUrl='file:///actual/bundled/Waving.fbx')
        actual = boundary.reader().read(0, require_animation=True)['animation']['clip']
        self.assertTrue(actual['url'].endswith('/Sit2.fbx'))
        self.assertTrue(actual['requestedUrl'].endswith('/Waving.fbx'))

    def test_recent_pose_before_request_waits_for_a_real_later_native_evaluation(self):
        boundary = Boundary()
        def native(value):
            if len(boundary.commands) == 1:
                # Within the age limit but BEFORE this input/read barrier.
                value['animation']['capturedEpochMs'] = 19900
        boundary.mutate = native
        value = boundary.reader().read(0, require_animation=True)
        self.assertEqual(20000, value['animation']['capturedEpochMs'])
        self.assertEqual(2, len(boundary.commands))
        self.assertNotEqual(boundary.commands[0]['commandId'], boundary.commands[1]['commandId'])
        self.assertTrue(all(command['action'] == 'feature-native-observe' for command in boundary.commands))

    def test_permanently_recent_but_preinput_pose_never_becomes_current(self):
        boundary = Boundary()
        boundary.mutate = lambda value: value['animation'].update(capturedEpochMs=19900)
        reader = boundary.reader()
        with self.assertRaises(NativeUIError): reader.read(0, require_animation=True)
        self.assertEqual(0, reader.sequence)
        self.assertLessEqual(len(boundary.commands), 51)

    def test_resampling_cannot_adopt_another_native_instance_or_regressed_source_cursor(self):
        for fault in ('instance', 'rig', 'sequence', 'lifecycle'):
            with self.subTest(fault=fault):
                boundary = Boundary()
                def pending(value):
                    if len(boundary.commands) == 1:
                        value['animation']['capturedEpochMs'] = 19900
                        if fault == 'lifecycle': value['lifecycle']['backgrounds'] = 1
                    elif fault == 'instance': value['instance'] = 'b' * 32
                    elif fault == 'rig': value['animation']['rigId'] = 999
                    elif fault == 'sequence': value['sequence'] = 1
                boundary.mutate = pending
                reader = boundary.reader()
                with self.assertRaises(NativeUIError): reader.read(0, require_animation=True)
                self.assertEqual(0, reader.sequence)

    def test_process_loss_and_invalid_cursor_stop_before_observation_request(self):
        for after in (-1, True, '0'):
            boundary = Boundary()
            with self.assertRaises(NativeUIError): boundary.reader().read(after)
            self.assertEqual([], boundary.commands)
        boundary = Boundary(); boundary.guard_okay = False
        with self.assertRaises(NativeUIError): boundary.reader().read(0)
        self.assertEqual([], boundary.commands)

    def test_duplicate_keys_nonfinite_oversize_and_future_native_values_are_rejected(self):
        for fault in ('duplicate', 'nan', 'large', 'future'):
            with self.subTest(fault=fault):
                boundary = Boundary()
                def original():
                    raw = boundary.original()
                    if fault == 'duplicate': return raw[:-1] + ',"sequence":100}'
                    if fault == 'nan': return raw.replace('25.5', 'NaN')
                    if fault == 'large': return raw + ' ' * LIMIT
                    return raw.replace('20000', '30000')
                reader = boundary.reader(); reader.original = original
                with self.assertRaises(NativeUIError): reader.read(0)

    def test_partial_original_write_is_polled_without_repeating_command_or_retiming(self):
        boundary = Boundary(); reader = boundary.reader(); reads = []
        def original():
            reads.append(1)
            return '{"schemaVersion":' if len(reads) == 1 else boundary.original()
        reader.original = original
        self.assertEqual(20000, reader.read(0)['capturedEpochMs'])
        self.assertEqual(2, len(reads))
        self.assertEqual(1, len(boundary.commands))

    def test_actual_probe_dispatches_closed_native_read_and_android_private_channel(self):
        probe = (Path(__file__).resolve().parents[1] / 'probe/overte_e2e_probe.js').read_text()
        start = probe.index('    var normalFeatureInstance =')
        end = probe.index('    var phoneTouchHistory', start)
        branch = probe.index('    function applyClientCommand(command)')
        branch_end = probe.index('        if (command && command.schemaVersion === 1\n                && /^ios-', branch)
        source = probe[start:end] + probe[branch:branch_end] + '\n return false; }'
        android = probe.index('    function applyAndroidControlCommand(command)')
        android_end = probe.index('        if (applyVoice(command))', android)
        source += probe[android:android_end] + '\n return false; }'
        program = '''
let calls=0,files=[];
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,keys)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(keys.sort());
const Test={featureNativeObservation:requestId=>{calls++;return {schemaVersion:1,requestId,sequence:77};},
 saveObject:(v,name)=>files.push({v,name})};
SOURCE
const good={schemaVersion:1,commandId:"a".repeat(32),action:"feature-native-observe"};
applyAndroidControlCommand(good); applyAndroidControlCommand(good);
if(calls!==1||files[0].v.sequence!==77||files[0].name!=="feature-native-observation.json")throw Error("original read");
applyClientCommand({...good,commandId:"b".repeat(32),expected:{animation:"Waving"}});
if(calls!==1)throw Error("expectation accepted");
delete Test.featureNativeObservation;
applyClientCommand({...good,commandId:"ios-"+"c".repeat(32)});
if(files[1].v.available!==false||files[1].v.requestId!=="ios-"+"c".repeat(32))throw Error("missing hook");
'''.replace('SOURCE', source)
        completed = subprocess.run(['node', '-e', program], capture_output=True, text=True, timeout=5)
        self.assertEqual(0, completed.returncode, completed.stderr)

    def test_ios_request_uses_its_original_closed_command_prefix(self):
        boundary = Boundary(); boundary.reader(ios=True).read(0)
        self.assertRegex(boundary.commands[0]['commandId'], '^ios-[0-9a-f]{32}$')


if __name__ == '__main__': unittest.main()
