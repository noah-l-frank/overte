"""Real Pico candidate wrapper and observation transport; native boundaries only."""
# SPDX-License-Identifier: Apache-2.0
from functools import partial
from copy import deepcopy
import json
import shlex
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import test_native_execution_binding as existing

sys.path.insert(0, str(Path(__file__).resolve().parents[5] / 'tests/device'))
from adapters.normal_script_manager import read_native_diagnostic
from adapters.pico4 import feature_observation
from adapters.android.adapter import ANDROID_CONTROL_COMMAND
from self_tests.test_native_feature_observation import Boundary as NativeFeatureBoundary
from self_tests.test_recorded_preview_evidence import Boundary as PreviewBoundary
from self_tests.test_recorded_preview_history import complete as completed_voice
from adapters.recorded_preview_history import measured_state as measured_audio_state
from self_tests.test_native_script_observation import Boundary as ScriptBoundary, effect_source, code_source, RUN as EFFECT_RUN
from adapters.native_script_observation import loaded_relative_modules, running_owned_engine, measured_effect
from adapters.native_script_loads import result as load_result
from self_tests.test_native_script_loads import history as load_history, URL as LOAD_URL
from self_tests.test_native_process_presence import Boundary as PresenceBoundary
from self_tests.test_native_animation_history import history_source
from adapters.native_animation_history import clip_run
from self_tests.test_native_account_observation import account_source


class FeatureObservationTests(unittest.TestCase):
    def setUp(self):
        self.fixture = existing.NativeExecutionBindingTest()
        self.fixture.setUp(); self.addCleanup(self.fixture.doCleanups)
        self.fixture.navigation_setup()
        self.native = self.fixture.fake
        self.clock = 0.0
        self.response = None
        self.sequence = 0
        self.mutation = None
        self.commands = []
        read_original = self.native.read_debug_app_file
        write_original = self.native.write_debug_app_file

        def write(target, package, path, raw):
            if path != ANDROID_CONTROL_COMMAND:
                return write_original(target, package, path, raw)
            command = json.loads(raw)
            self.commands.append(command)
            self.sequence += 1
            self.response = dict(schemaVersion=1, requestId=command['commandId'], instance='a' * 32,
                sampleSequence=self.sequence, sampleEpochMs=self.native.epoch_milliseconds(target),
                complete=True, scripts=[dict(url='http://native.actual/owned.js', path='native.actual/owned.js')])
            if command['includeAvatarEntities']:
                self.response.update(entitiesComplete=True, avatarEntities=[dict(
                    id='{11111111-1111-1111-1111-111111111111}', name='actual-native-name', type='Box')])
            if self.mutation:
                self.mutation(self.response)

        def read(target, package, path, **kwargs):
            if path == 'files/overte-e2e/normal-feature-observation.json':
                return json.dumps(self.response)
            return read_original(target, package, path, **kwargs)

        def sleep(seconds): self.clock += seconds
        for boundary in (patch.object(self.native, 'write_debug_app_file', side_effect=write),
                         patch.object(self.native, 'read_debug_app_file', side_effect=read),
                         patch.object(feature_observation, 'read_native_diagnostic',
                            partial(read_native_diagnostic, monotonic=lambda: self.clock, sleep=sleep))):
            boundary.start(); self.addCleanup(boundary.stop)
        self.adapter = self.fixture.instance()
        self.observer = self.adapter._feature_observer(self.native.target)

    def native_feature_boundaries(self):
        source = NativeFeatureBoundary()
        def mutate(value):
            epoch = self.native.epoch_milliseconds(self.native.target)
            value['capturedEpochMs'] = value['animation']['capturedEpochMs'] = epoch
            value['requestedEpochMs'] = value['animationFence']['requestedEpochMs'] = epoch
            value['animation']['clip']['evaluatedEpochMs'] = epoch
        source.mutate = mutate
        original_read = self.native.read_debug_app_file
        def write(target, package, path, raw):
            self.assertEqual(ANDROID_CONTROL_COMMAND, path)
            self.assertEqual('org.overte.pico', package)
            source.send(json.loads(raw))
        def read(target, package, path, **kwargs):
            if path == 'files/overte-e2e/feature-native-observation.json':
                self.assertEqual('org.overte.pico', package)
                self.assertEqual({'attempts': 1}, kwargs)
                return source.original()
            return original_read(target, package, path, **kwargs)
        for boundary in (patch.object(self.native, 'write_debug_app_file', side_effect=write),
                         patch.object(self.native, 'read_debug_app_file', side_effect=read)):
            boundary.start(); self.addCleanup(boundary.stop)
        return source

    def test_pico_scene_load_source_preserves_retained_callbacks_and_candidate_owner(self):
        from self_tests.test_native_scene_loads import Boundary, RUN, URL
        from adapters.native_scene_loads import committed
        source=Boundary();source.rows[0].update(pending=True,releasedEpochMs=None)
        old_send=source.send
        def send(command):
            source.epoch=self.native.epoch_milliseconds(self.native.target)
            old_send(command);source.sample['processId']=int(self.native.identity.split(':')[0])
        native=self.adapter._native_feature_observer(self.native.target);original_read=self.native.read_debug_app_file
        def read(target,package,path,**options):
            if path=='files/overte-e2e/feature-scene-load.json':return source.original()
            return original_read(target,package,path,**options)
        with patch.object(native,'send',side_effect=send),patch.object(self.adapter,'_native_feature_observer',return_value=native), \
                patch.object(self.native,'read_debug_app_file',side_effect=read):
            reader=self.adapter._scene_load_observer(self.native.target);first=reader.read(RUN)
            self.assertEqual(1,first['pendingLeases']);self.assertEqual(source.rows,first['requests'])
            with self.assertRaises(RuntimeError):committed(first,URL)
            source.rows[0].update(pending=False,releasedEpochMs=source.epoch,updatedEpochMs=source.epoch)
            second=reader.read(RUN);self.assertEqual(source.rows[0],committed(second,URL))
            self.assertEqual([],self.native.inputs)
            self.native.digest='f'*64
            with self.assertRaises(RuntimeError):reader.read(RUN)
            self.assertEqual(2,len(source.commands))

    def test_pico_graphics_subject_keeps_original_inventory_without_input(self):
        from self_tests.test_native_graphics_subject import Boundary, RUN
        source=Boundary();source.epoch=self.native.epoch_milliseconds(self.native.target)
        source.source.update(subjectVersion=2,avatarPose=dict(feetPosition=[0,-.2,0],orientation=[0,0,0,1],modelScale=1.25))
        old_send=source.send
        def send(command):
            source.epoch=self.native.epoch_milliseconds(self.native.target)
            old_send(command);source.sample['processId']=int(self.fixture.fake.identity.split(':')[0])
        native=self.adapter._native_feature_observer(self.native.target)
        original_read=self.native.read_debug_app_file
        def read(target,package,path,**options):
            if path=='files/overte-e2e/feature-graphics-subject.json':return source.original()
            return original_read(target,package,path,**options)
        with patch.object(native,'send',side_effect=send),patch.object(self.adapter,'_native_feature_observer',return_value=native), \
                patch.object(self.native,'read_debug_app_file',side_effect=read):
            reader=self.adapter._graphics_subject_observer(self.native.target)
            value=reader.read(RUN,require_avatar=True)
            self.assertEqual(source.source,value['source']);self.assertEqual(1,len(source.commands))
            self.assertEqual([],self.native.inputs)
            self.native.digest='f'*64
            with self.assertRaises(RuntimeError):reader.read(RUN,require_avatar=True)
            self.assertEqual(1,len(source.commands))

    def test_pico_passive_account_source_preserves_binding_and_refuses_downgrade(self):
        source=self.native_feature_boundaries();original=source.mutate
        def observed(value):original(value);account_source(value)
        source.mutate=observed;reader=self.adapter._native_feature_observer(self.native.target)
        first=reader.read(0,require_account=True)
        self.assertEqual(source.sample['account'],first['account'])
        self.assertFalse(first['account']['observation']['loginPending'])
        source.mutate=original
        with self.assertRaises(RuntimeError):reader.read(first['sequence'])
        self.assertEqual([],self.native.inputs)

    def test_pico_animation_history_keeps_original_effects_and_refuses_source_downgrade(self):
        source=self.native_feature_boundaries();original=source.mutate
        event_epoch=self.native.epoch_milliseconds(self.native.target)-1000
        def observed(value):original(value);history_source(value,event_epoch=event_epoch)
        source.mutate=observed;reader=self.adapter._native_feature_observer(self.native.target)
        first=reader.read(0,require_animation_history=True)
        event,frames=clip_run(first,'file:///actual/bundled/Sit2.fbx',after_event=0,after_epoch=event_epoch)
        self.assertEqual(event_epoch,event['capturedEpochMs']);self.assertEqual(2,len(frames))
        second=reader.read(first['sequence'],require_animation_history=True)
        self.assertEqual(first['animation']['history'],second['animation']['history'])
        source.mutate=original
        with self.assertRaises(RuntimeError):reader.read(second['sequence'])
        self.assertEqual([],self.native.inputs)

    def test_pico_atomic_audio_history_keeps_terminal_events_and_refuses_an_older_source(self):
        source = self.native_feature_boundaries(); original = source.mutate
        recorded = completed_voice()
        offset = self.native.epoch_milliseconds(self.native.target) - 20000
        recorded['startedEpochMs'] += offset
        for event in recorded['events']: event['publishedEpochMs'] += offset
        recorded['event'] = deepcopy(recorded['events'][-1])
        def history(value):
            original(value); value['audio']['recordedVoice'] = deepcopy(recorded)
        source.mutate = history
        reader = self.adapter._native_feature_observer(self.native.target)
        first = reader.read(0, require_recorded_history=True)
        self.assertEqual(144000, measured_audio_state(first)['recordedFrames'])
        self.assertEqual(0, measured_audio_state(first)['bufferedFrames'])
        second = reader.read(first['sequence'], require_recorded_history=True)
        self.assertEqual(first['audio']['recordedVoice'], second['audio']['recordedVoice'])
        source.mutate = original
        with self.assertRaises(RuntimeError): reader.read(second['sequence'], require_recorded_history=True)
        self.assertEqual([], self.native.inputs)

    def test_native_feature_original_evaluated_clip_and_native_lifecycle_keep_candidate_binding(self):
        source = self.native_feature_boundaries()
        reader = self.adapter._native_feature_observer(self.native.target)
        first = reader.read(0, require_animation=True)
        self.assertEqual(source.sample, first)
        self.assertEqual(123, first['processId'])
        self.assertTrue(first['animation']['clip']['url'].endswith('/Sit2.fbx'))
        self.assertEqual([], self.native.inputs)
        self.assertFalse(any(value.startswith('feature.') for value in self.adapter.capabilities(self.native.target)))

    def preview_boundaries(self, source=None, filename='recorded-preview-observation.json'):
        source = PreviewBoundary() if source is None else source
        event_offset = self.native.epoch_milliseconds(self.native.target) - 20000
        def mutate(value):
            value['processId'] = 123
            offset = self.native.epoch_milliseconds(self.native.target) - 20000
            value['requestedEpochMs'] += offset; value['capturedEpochMs'] += offset
            if 'source' in value and 'cycle' in value['source']:
                original = value['source']
                for key in ('startedEpochMs', 'inputLastEpochMs', 'sinkLastEpochMs'): original[key] += event_offset
                for event in original['events']: event['publishedEpochMs'] += event_offset
            elif 'source' in value:
                for engine in value['source']['engines']:
                    for module in engine['required']['modules']: module['capturedEpochMs'] += event_offset
        source.mutate = mutate
        original_read = self.native.read_debug_app_file
        def write(target, package, path, raw):
            self.assertEqual(ANDROID_CONTROL_COMMAND, path)
            self.assertEqual('org.overte.pico', package)
            source.send(json.loads(raw))
        def read(target, package, path, **kwargs):
            if path == 'files/overte-e2e/' + filename:
                return json.dumps(source.sample if hasattr(source, 'sample') else source.value)
            return original_read(target, package, path, **kwargs)
        def binary(command, *, target, timeout):
            self.assertEqual('exec-out', command[0]); self.assertEqual(5, timeout)
            raw = source.files.get(shlex.split(command[1])[-1])
            return b'OVT_PREVIEW_MISSING_V1\n' if raw is None else b'OVT_PREVIEW_BYTES_V1\n' + raw + b'\nOVT_PREVIEW_BYTES_END_V1\n'
        for boundary in (patch.object(self.native, 'write_debug_app_file', side_effect=write),
                         patch.object(self.native, 'read_debug_app_file', side_effect=read),
                         patch.object(self.native, 'execute_bytes', side_effect=binary, create=True)):
            boundary.start(); self.addCleanup(boundary.stop)
        return source

    def process_presence(self):
        source = self.preview_boundaries(PresenceBoundary(pid=123,
            epoch_ms=lambda: self.native.epoch_milliseconds(self.native.target)), 'feature-process-presence.json')
        return source, self.adapter._process_presence(self.native.target)

    def test_pico_process_presence_preserves_raw_kernel_states_without_scripts_input(self):
        source, reader = self.process_presence()
        self.assertEqual('present', reader.read(122)['presence'])
        source.presence = 'unknown'
        with self.assertRaises(RuntimeError): reader.require_absent(122)
        source.presence = 'absent'; actual = reader.require_absent(122)
        self.assertEqual(source.value, actual); self.assertEqual(3, actual['nativeError'])
        self.assertEqual([], self.native.inputs)

    def test_pico_process_presence_ignored_or_foreign_source_cannot_prove_exit(self):
        source, reader = self.process_presence(); source.ignored = True
        with self.assertRaises(RuntimeError): reader.require_absent(122)
        self.assertEqual(1, len(source.commands)); self.assertIsNone(reader.last)
        source.ignored = False; source.presence = 'absent'; source.edit = lambda value: value.update(processId=124)
        with self.assertRaises(RuntimeError): reader.require_absent(122)
        self.assertIsNone(reader.last)

    def test_pico_process_presence_changed_candidate_or_same_pid_new_birth_blocks_query(self):
        source, reader = self.process_presence(); reader.read(122)
        before = len(source.commands); original = self.native.digest; self.native.digest = 'f' * 64
        with self.assertRaises(RuntimeError): reader.read(122)
        self.assertEqual(before, len(source.commands))
        self.native.digest = original; self.native.identity = '123:another-start'
        with self.assertRaises(RuntimeError): reader.read(122)
        self.assertEqual(before, len(source.commands))

    def test_original_pico_preview_pcm_uses_bound_native_transport_and_verifies_cleanup(self):
        source = self.preview_boundaries()
        reader = self.adapter._recorded_preview_evidence(self.native.target)
        value, raw = reader.read(0, after_cycle=6)
        self.assertEqual(source.value, value)
        self.assertEqual(source.files['recorded-preview-sink.pcm16le'], raw['sink'])
        reader.release(); reader.release()
        self.assertEqual({}, source.files)
        self.assertEqual([], self.native.inputs)

    def test_pico_preview_candidate_change_blocks_request(self):
        source = self.preview_boundaries()
        reader = self.adapter._recorded_preview_evidence(self.native.target)
        self.native.digest = 'f' * 64
        with self.assertRaises(RuntimeError): reader.read(0)
        self.assertEqual([], source.commands)

    def test_pico_preview_ignored_release_and_foreign_process_are_rejected(self):
        source = self.preview_boundaries(); source.retain = True
        reader = self.adapter._recorded_preview_evidence(self.native.target)
        reader.read(0)
        with self.assertRaises(RuntimeError): reader.release()
        self.native.identity = '999:foreign'
        before = len(source.commands)
        with self.assertRaises(RuntimeError): reader.read(reader.sequence)
        self.assertEqual(before, len(source.commands))

    def test_pico_native_effect_extension_preserves_stalled_actual_counter_under_candidate_binding(self):
        source = self.preview_boundaries(ScriptBoundary(), 'feature-script-observation.json')
        original = source.mutate
        event_epoch = self.native.epoch_milliseconds(self.native.target) - 3000
        def effects(value):
            original(value)
            # The simulated native module/effect events are immutable even
            # while the source acquisition clock advances between requests.
            for engine in value['source']['engines']:
                for module in engine['required']['modules']: module['capturedEpochMs'] = event_epoch
            effect_source(value, edited=event_epoch * 1000)
        source.mutate = effects
        reader = self.adapter._script_execution_observer(self.native.target)
        first = reader.read(0, require_effects=True)
        self.assertEqual(2, measured_effect(first, EFFECT_RUN)['ticks'])
        second = reader.read(first['sequence'], require_effects=True)
        self.assertEqual(measured_effect(first, EFFECT_RUN), measured_effect(second, EFFECT_RUN))
        self.native.digest = 'f' * 64; before = len(source.commands)
        with self.assertRaises(RuntimeError): reader.read(second['sequence'], require_effects=True)
        self.assertEqual(before, len(source.commands)); self.assertEqual([], self.native.inputs)

    def test_pico_submitted_code_uses_original_bound_source_and_refuses_older_producer(self):
        source=self.preview_boundaries(ScriptBoundary(), 'feature-script-observation.json')
        original=source.mutate
        def identified(value):
            if original: original(value)
            code_source(value)
        source.mutate=identified;reader=self.adapter._script_execution_observer(self.native.target)
        first=reader.read(0,require_code_identity=True)
        code=first['source']['engines'][0]['code']
        self.assertEqual(15000,code['submittedEpochMs']);self.assertTrue(code['submitted'])
        second=reader.read(first['sequence'],require_code_identity=True)
        self.assertEqual(code,second['source']['engines'][0]['code'])
        source.mutate=original
        with self.assertRaises(RuntimeError):reader.read(second['sequence'],require_code_identity=True)

    def test_pico_original_load_failure_history_survives_transport_and_refuses_downgrade(self):
        source = self.preview_boundaries(ScriptBoundary(), 'feature-script-observation.json')
        original = source.mutate
        def observed(packet):
            if original: original(packet)
            load_history(packet)
        source.mutate = observed
        reader = self.adapter._script_execution_observer(self.native.target)
        first = reader.read(0, require_load_history=True)
        second = reader.read(first['sequence'], require_load_history=True)
        self.assertEqual(first['source']['loads'], second['source']['loads'])
        actual = load_result(second, LOAD_URL, after_sequence=0, after_epoch=19000)
        self.assertEqual('NotFound', actual['status']); self.assertFalse(actual['success'])
        self.assertEqual(19001, actual['callbackEpochMs'])
        self.assertTrue(all(set(command) == {'schemaVersion', 'commandId', 'action'} for command in source.commands))
        source.mutate = original
        with self.assertRaises(RuntimeError): reader.read(second['sequence'])
        self.assertEqual(second['sequence'], reader.sequence)
        self.assertEqual([], self.native.inputs)


    def test_pico_script_execution_source_retains_real_loaded_module_and_engine_identity(self):
        source = self.preview_boundaries(ScriptBoundary(), 'feature-script-observation.json')
        value = self.adapter._script_execution_observer(self.native.target).read(0)
        self.assertEqual(source.sample, value)
        self.assertEqual(['companion.js'], loaded_relative_modules(running_owned_engine(value, source.engine['url'])))
        self.assertEqual([], self.native.inputs)

    def test_pico_script_execution_source_rejects_candidate_change_before_request(self):
        source = self.preview_boundaries(ScriptBoundary(), 'feature-script-observation.json')
        reader = self.adapter._script_execution_observer(self.native.target)
        self.native.digest = 'f' * 64
        with self.assertRaises(RuntimeError): reader.read(0)
        self.assertEqual([], source.commands)

    def test_native_feature_candidate_change_after_original_read_is_rejected(self):
        source = self.native_feature_boundaries()
        reader = self.adapter._native_feature_observer(self.native.target)
        original = source.mutate
        def change(value):
            original(value)
            self.native.digest = 'f' * 64
        source.mutate = change
        with self.assertRaises(RuntimeError): reader.read(0)
        self.assertEqual(1, len(source.commands))
        self.assertEqual(0, reader.sequence)

    def test_native_feature_rejects_foreign_pid_and_unavailable_native_hook(self):
        for fault in ('pid', 'hook'):
            with self.subTest(fault=fault):
                source = self.native_feature_boundaries()
                source.mutate = (lambda value: value.update(processId=999)) if fault == 'pid' else (
                    lambda value: value.update(available=False))
                reader = self.adapter._native_feature_observer(self.native.target)
                with self.assertRaises(RuntimeError): reader.read(0)
                self.assertEqual(0, reader.sequence)

    def test_actual_request_original_rows_and_advancing_source_metadata_are_preserved(self):
        first = self.observer.read(0)
        second = self.observer.read(first['sampleSequence'], include_avatar_entities=True)
        self.assertEqual('http://native.actual/owned.js', first['scripts'][0]['url'])
        self.assertEqual(self.commands[1]['commandId'], second['requestId'])
        self.assertEqual('actual-native-name', second['avatarEntities'][0]['name'])
        self.assertGreater(second['sampleSequence'], first['sampleSequence'])
        self.assertEqual([], self.native.inputs)
        self.assertEqual([], self.native.controllers)
        self.assertFalse(any(value.startswith('feature.') for value in self.adapter.capabilities(self.native.target)))

    def test_ignored_foreign_stale_or_incomplete_native_observations_cannot_succeed(self):
        for changes in ({'requestId': 'f' * 32}, {'sampleEpochMs': 1}, {'complete': False},
                        {'sampleSequence': 0}, {'entitiesComplete': False}):
            with self.subTest(changes=changes):
                self.mutation = lambda value: value.update(changes)
                with self.assertRaisesRegex(RuntimeError, '^OVT_PICO_FEATURE_OBSERVATION_REJECTED$'):
                    self.observer.read(self.observer.sequence, include_avatar_entities=True)

    def test_probe_instance_change_and_regressed_request_sequence_are_rejected(self):
        first = self.observer.read(0)
        self.mutation = lambda value: value.update(instance='b' * 32)
        with self.assertRaises(RuntimeError): self.observer.read(first['sampleSequence'])
        self.mutation = None
        with self.assertRaises(RuntimeError): self.observer.read(0)

    def test_candidate_change_before_read_cannot_deliver_even_observation_input(self):
        self.native.digest = 'f' * 64
        with self.assertRaises(RuntimeError): self.observer.read(0)
        self.assertEqual([], self.commands)

    def test_candidate_change_after_capture_rejects_original_measurement(self):
        self.mutation = lambda value: setattr(self.native, 'digest', 'f' * 64)
        with self.assertRaises(RuntimeError): self.observer.read(0)
        self.assertEqual(0, self.observer.sequence)

    def test_process_or_foreground_loss_prevents_capture_and_redacts_native_details(self):
        self.native.identity = '999:foreign'
        with self.assertRaisesRegex(RuntimeError, '^OVT_PICO_FEATURE_OBSERVATION_REJECTED$'):
            self.observer.read(0)
        self.assertEqual([], self.commands)

    def test_unavailable_avatar_query_is_not_an_empty_world(self):
        self.mutation = lambda value: value.pop('entitiesComplete')
        with self.assertRaises(RuntimeError): self.observer.read(0, include_avatar_entities=True)


if __name__ == '__main__': unittest.main()
