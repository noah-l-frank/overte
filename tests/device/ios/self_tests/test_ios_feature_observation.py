"""Original iOS HTTP/AFC observation transport, with native boundaries replaced."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from adapters.normal_ui import NativeUIError
from fixture.serve import FixtureState
from ios.adapters import feature_observation
from ios.adapters.adapter import IOSAdapter
from ios.adapters.appium_adapter import WebDriverRequestError
from self_tests.test_native_feature_observation import Boundary as NativeFeatureBoundary
from self_tests.test_recorded_preview_evidence import Boundary as PreviewBoundary
from self_tests.test_recorded_preview_history import complete as completed_voice
from adapters.recorded_preview_history import measured_state as measured_audio_state
from self_tests.test_native_script_observation import Boundary as ScriptBoundary, effect_source, code_source, RUN as EFFECT_RUN
from adapters.native_script_observation import loaded_relative_modules, running_owned_engine, measured_effect
from adapters.native_script_loads import result as load_result
from self_tests.test_native_script_loads import history as load_history, URL as LOAD_URL
from self_tests.test_native_animation_history import history_source
from adapters.native_animation_history import clip_run
from self_tests.test_native_account_observation import account_source


class Native:
    def __init__(self):
        self.target = dict(platform='ios', physical=True, appId='org.example.client',
            probe={'kind': 'ios-documents'}, testBuild=dict(
                fixtureOrigin='http://controlled.invalid:49121', resultsDirectory='owned-results'))
        self.pid = 42
        self.sequence = 0
        self.clock = 0.0
        self.mutation = None
        self.commands, self.reads = [], []
        self.fixture = FixtureState()
        self.missing = 0

    def process(self): return dict(bundleId=self.target['appId'], pid=self.pid, foreground=True)
    def sleep(self, seconds): self.clock += seconds
    def post(self, request, timeout):
        command = self.fixture.set_client_command(json.loads(request.data))
        self.commands.append(command)
        self.echo = json.dumps(command).encode()
        self.sequence += 1
        self.value = dict(schemaVersion=1, requestId=command['commandId'], instance='a' * 32,
            sampleEpochMs=10000, sampleSequence=self.sequence, complete=True,
            scripts=[dict(url='http://actual.native/script.js', path='actual.native/script.js')])
        if command['includeAvatarEntities']:
            self.value.update(entitiesComplete=True, avatarEntities=[dict(
                id='{11111111-1111-1111-1111-111111111111}', name='actual-avatar-entity', type='Shape')])
        if self.mutation: self.mutation(self.value)
        return self
    def read(self, limit): return self.echo[:limit]
    status = 200
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def execute(self, session, operation, values):
        if operation == 'mobile: overteProcessInfo': return self.process()
        assert operation == 'mobile: pullFile'
        assert values == {'remotePath': '@org.example.client:documents/owned-results/normal-feature-observation.json'}
        self.reads.append(values)
        if self.missing:
            self.missing -= 1
            raise WebDriverRequestError(500)
        return base64.b64encode(json.dumps(self.value).encode()).decode()
    def observer(self):
        return feature_observation.FeatureObservation(self, 'native-session', self.target, self.process,
            monotonic=lambda: self.clock, sleep=self.sleep, epoch_ms=lambda: 10000)


class FeatureObservationTests(unittest.TestCase):
    def setUp(self):
        self.native = Native()
        boundary = patch.object(feature_observation, 'post_request', side_effect=self.native.post)
        boundary.start(); self.addCleanup(boundary.stop)
        self.observer = self.native.observer()

    def test_bound_native_clock_factory_uses_distinct_original_nonces_and_keeps_native_time(self):
        source=self.native_feature_boundaries();self.observer.epoch_ms=lambda:9000000
        reader=self.observer.bound_native_observer();value=reader.read(0)
        self.assertEqual(10000,value['capturedEpochMs'])
        self.assertEqual(4,len(source.commands))
        self.assertEqual(4,len({row['commandId'] for row in source.commands}))
        self.assertEqual(source.commands[1]['commandId'],value['requestId'])
        self.assertEqual(2,value['sequence']);self.assertEqual(4,source.sample['sequence'])

    def test_bound_native_clock_factory_refuses_a_foreign_birth_or_stale_middle_packet(self):
        for fault in ('birth','old'):
            with self.subTest(fault=fault):
                source=self.native_feature_boundaries();original=source.mutate
                def mutate(value):
                    original(value)
                    if source.sequence==2:
                        if fault=='birth':value['instance']='c'*32
                        else:value.update(capturedEpochMs=9000,requestedEpochMs=9000,animation={},animationFence={})
                source.mutate=mutate
                with self.assertRaises(NativeUIError):self.observer.bound_native_observer().read(0)

    def test_ios_passive_account_source_keeps_native_clock_and_refuses_downgrade(self):
        source=self.native_feature_boundaries();original=source.mutate
        def observed(value):original(value);account_source(value)
        source.mutate=observed;self.observer.epoch_ms=lambda:9000000
        reader=self.observer.native_observer();first=reader.read(0,require_account=True)
        self.assertEqual(10000,first['account']['observation']['capturedEpochMs'])
        self.assertEqual(source.sample['account'],first['account'])
        source.mutate=original
        with self.assertRaises(NativeUIError):reader.read(first['sequence'])

    def test_ios_animation_history_preserves_native_times_and_refuses_an_older_producer(self):
        source=self.native_feature_boundaries();original=source.mutate
        def observed(value):original(value);history_source(value,event_epoch=9000)
        source.mutate=observed;reader=self.observer.native_observer()
        first=reader.read(0,require_animation_history=True)
        event,frames=clip_run(first,'file:///actual/bundled/Sit2.fbx',after_event=0,after_epoch=9000)
        self.assertEqual(9000,event['capturedEpochMs']);self.assertEqual(2,len(frames))
        second=reader.read(first['sequence'],require_animation_history=True)
        self.assertEqual(first['animation']['history'],second['animation']['history'])
        source.mutate=original
        with self.assertRaises(RuntimeError):reader.read(second['sequence'])

    def native_feature_boundaries(self):
        source = NativeFeatureBoundary()
        def mutate(value):
            value['processId'] = 42
            value['capturedEpochMs'] = value['animation']['capturedEpochMs'] = 10000
            value['requestedEpochMs'] = value['animationFence']['requestedEpochMs'] = 10000
            value['animation']['clip']['evaluatedEpochMs'] = 10000
        source.mutate = mutate
        def post(request, timeout):
            command = self.native.fixture.set_client_command(json.loads(request.data))
            self.native.commands.append(command)
            self.native.echo = json.dumps(command).encode()
            source.send(command)
            return self.native
        def execute(session, operation, values):
            if operation == 'mobile: overteProcessInfo': return self.native.process()
            self.assertEqual('mobile: pullFile', operation)
            self.assertEqual({'remotePath': '@org.example.client:documents/owned-results/feature-native-observation.json'}, values)
            self.native.reads.append(values)
            if self.native.missing:
                self.native.missing -= 1
                raise WebDriverRequestError(500)
            return base64.b64encode(source.original().encode()).decode()
        for boundary in (patch.object(feature_observation, 'post_request', side_effect=post),
                         patch.object(self.native, 'execute', side_effect=execute)):
            boundary.start(); self.addCleanup(boundary.stop)
        return source

    def test_original_native_feature_packet_uses_closed_http_and_actual_afc_documents(self):
        source = self.native_feature_boundaries()
        reader = self.observer.native_observer()
        value = reader.read(0, require_animation=True)
        self.assertEqual(source.sample, value)
        self.assertEqual(42, value['processId'])
        self.assertEqual(10000, value['animation']['clip']['evaluatedEpochMs'])
        self.assertRegex(source.commands[0]['commandId'], '^ios-[0-9a-f]{32}$')
        self.assertEqual(1, len(self.native.reads))

    def preview_boundaries(self, source=None, filename='recorded-preview-observation.json'):
        source = PreviewBoundary() if source is None else source
        source.mutate = lambda value: value.update(processId=42)
        native_clock = NativeFeatureBoundary() if isinstance(source, ScriptBoundary) else None
        if native_clock is not None:
            native_clock.mutate = lambda value: value.update(processId=42)
        def post(request, timeout):
            command = self.native.fixture.set_client_command(json.loads(request.data))
            self.native.commands.append(command)
            self.native.echo = json.dumps(command).encode()
            if command['action'] == 'feature-native-observe' and native_clock is not None:
                native_clock.send(command)
            else:
                source.send(command)
            return self.native
        def execute(session, operation, values):
            if operation == 'mobile: overteProcessInfo': return self.native.process()
            self.assertEqual('mobile: pullFile', operation)
            remote = values['remotePath']
            self.assertTrue(remote.startswith('@org.example.client:documents/owned-results/'))
            self.native.reads.append(values)
            name = remote.rsplit('/', 1)[-1]
            if name == 'feature-native-observation.json' and native_clock is not None:
                raw = native_clock.original().encode()
            elif name == filename:
                raw = json.dumps(source.sample if hasattr(source, 'sample') else source.value).encode()
            elif self.native.missing: raise WebDriverRequestError(500)
            else: raw = source.files[name]
            return base64.b64encode(raw).decode()
        for boundary in (patch.object(feature_observation, 'post_request', side_effect=post),
                         patch.object(self.native, 'execute', side_effect=execute)):
            boundary.start(); self.addCleanup(boundary.stop)
        return source

    def test_original_ios_preview_pcm_keeps_native_cycle_and_separate_afc_files(self):
        source = self.preview_boundaries()
        reader = self.observer.recorded_preview_observer()
        value, raw = reader.read(0, after_cycle=6)
        self.assertEqual(source.value, value)
        self.assertEqual(source.files['recorded-preview-input.pcm16le'], raw['input'])
        reader.release(); reader.release()
        self.assertEqual({}, source.files)
        self.assertEqual(2, sum('pcm16le' in row['remotePath'] for row in self.native.reads))

    def test_ios_preview_afc_error_is_never_reported_as_empty_original_audio(self):
        self.preview_boundaries(); self.native.missing = 1
        reader = self.observer.recorded_preview_observer()
        with self.assertRaises(NativeUIError): reader.read(0)
        self.assertEqual(0, reader.sequence)

    def test_ios_preview_cleanup_requires_actual_file_and_memory_absence(self):
        source = self.preview_boundaries(); source.retain = True
        reader = self.observer.recorded_preview_observer(); reader.read(0)
        with self.assertRaises(NativeUIError): reader.release()
        self.assertTrue(source.files)

    def test_ios_preview_process_change_after_http_request_prevents_afc_acceptance(self):
        source = self.preview_boundaries()
        def change(value):
            value['processId'] = 42
            self.native.pid = 43
        source.mutate = change
        reader = self.observer.recorded_preview_observer()
        with self.assertRaises(NativeUIError): reader.read(0)
        self.assertEqual([], self.native.reads)

    def test_ios_original_native_effect_extension_keeps_edit_time_and_stalled_counter(self):
        source = self.preview_boundaries(ScriptBoundary(), 'feature-script-observation.json')
        original = source.mutate
        def effects(value):
            original(value); effect_source(value)
        source.mutate = effects
        reader = self.observer.script_execution_observer()
        first = reader.read(0, require_effects=True)
        self.assertEqual(2, measured_effect(first, EFFECT_RUN)['ticks'])
        second = reader.read(first['sequence'], require_effects=True)
        self.assertEqual(measured_effect(first, EFFECT_RUN), measured_effect(second, EFFECT_RUN))
        self.native.pid = 43; before = len(source.commands)
        with self.assertRaises(NativeUIError): reader.read(second['sequence'], require_effects=True)
        self.assertEqual(before, len(source.commands))

    def test_ios_submitted_code_uses_original_bound_source_and_refuses_older_producer(self):
        source=self.preview_boundaries(ScriptBoundary(), 'feature-script-observation.json')
        original=source.mutate
        def identified(value):
            if original: original(value)
            code_source(value)
        source.mutate=identified;reader=self.observer.script_execution_observer()
        first=reader.read(0,require_code_identity=True)
        code=first['source']['engines'][0]['code']
        self.assertEqual(15000,code['submittedEpochMs']);self.assertTrue(code['submitted'])
        second=reader.read(first['sequence'],require_code_identity=True)
        self.assertEqual(code,second['source']['engines'][0]['code'])
        source.mutate=original
        with self.assertRaises(RuntimeError):reader.read(second['sequence'],require_code_identity=True)

    def test_ios_original_load_failure_history_survives_transport_and_refuses_downgrade(self):
        source = self.preview_boundaries(ScriptBoundary(), 'feature-script-observation.json')
        original = source.mutate
        def observed(packet):
            if original: original(packet)
            load_history(packet)
        source.mutate = observed
        reader = self.observer.script_execution_observer()
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


    def test_ios_script_execution_component_keeps_original_afc_module_history(self):
        source = self.preview_boundaries(ScriptBoundary(), 'feature-script-observation.json')
        self.observer.epoch_ms = lambda: 9000000
        value = self.observer.script_execution_observer().read(0)
        self.assertEqual(source.sample, value)
        self.assertEqual(['companion.js'], loaded_relative_modules(running_owned_engine(value, source.engine['url'])))
        self.assertEqual(17000, value['source']['engines'][0]['required']['modules'][0]['capturedEpochMs'])

    def test_ios_script_execution_process_loss_cannot_consume_native_afc_result(self):
        source = self.preview_boundaries(ScriptBoundary(), 'feature-script-observation.json')
        reader = self.observer.script_execution_observer()
        def change(value):
            value['processId'] = 42
            self.native.pid = 43
        source.mutate = change
        with self.assertRaises(NativeUIError): reader.read(0)
        self.assertEqual([{'remotePath': '@org.example.client:documents/owned-results/feature-native-observation.json'}],
                         self.native.reads)

    def test_ios_atomic_audio_history_preserves_native_events_and_does_not_downgrade_source(self):
        source = self.native_feature_boundaries(); original = source.mutate
        recorded = completed_voice(); recorded['startedEpochMs'] -= 10000
        for event in recorded['events']: event['publishedEpochMs'] -= 10000
        recorded['event'] = deepcopy(recorded['events'][-1])
        def history(value):
            original(value); value['audio']['recordedVoice'] = deepcopy(recorded)
        source.mutate = history
        reader = self.observer.native_observer()
        first = reader.read(0, require_recorded_history=True)
        self.assertEqual(144000, measured_audio_state(first)['recordedFrames'])
        self.assertEqual(0, measured_audio_state(first)['bufferedFrames'])
        second = reader.read(first['sequence'], require_recorded_history=True)
        self.assertEqual(first['audio']['recordedVoice'], second['audio']['recordedVoice'])
        source.mutate = original
        with self.assertRaises(NativeUIError): reader.read(second['sequence'], require_recorded_history=True)

    def test_native_feature_original_fence_handles_device_host_clock_skew(self):
        source = self.native_feature_boundaries()
        self.observer.epoch_ms = lambda: 9000000
        value = self.observer.native_observer().read(0, require_animation=True)
        self.assertEqual(10000, value['requestedEpochMs'])
        self.assertEqual(source.sample, value)

    def test_native_feature_process_change_cannot_consume_original_result(self):
        source = self.native_feature_boundaries()
        original = source.mutate
        def change(value):
            original(value)
            self.native.pid = 43
        source.mutate = change
        reader = self.observer.native_observer()
        with self.assertRaises(NativeUIError): reader.read(0)
        self.assertEqual(0, reader.sequence)
        self.assertEqual([], self.native.reads)

    def test_native_feature_unavailable_hook_and_foreign_pid_are_rejected(self):
        for fault in ('hook', 'pid'):
            with self.subTest(fault=fault):
                source = self.native_feature_boundaries()
                source.mutate = (lambda value: value.update(available=False)) if fault == 'hook' else (
                    lambda value: value.update(processId=123))
                with self.assertRaises(NativeUIError): self.observer.native_observer().read(0)

    def test_native_feature_missing_afc_file_is_polled_without_replaying_http_command(self):
        self.native_feature_boundaries()
        self.native.missing = 1
        value = self.observer.native_observer().read(0)
        self.assertEqual(1, value['sequence'])
        self.assertEqual(2, len(self.native.reads))
        self.assertEqual(1, len(self.native.commands))

    def test_native_feature_fixture_rejects_expected_values_and_nonliteral_versions(self):
        command = dict(schemaVersion=1, commandId='ios-' + 'b' * 32, action='feature-native-observe')
        for extra in ({'expected': {'animation': 'Waving'}}, {'schemaVersion': True}, {'file': '/foreign'}):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                self.native.fixture.set_client_command(command | extra)

    def test_original_rows_request_ids_sequences_and_capture_times_are_retained(self):
        first = self.observer.read(0)
        second = self.observer.read(first['sampleSequence'], include_avatar_entities=True)
        self.assertEqual('http://actual.native/script.js', first['scripts'][0]['url'])
        self.assertEqual(10000, first['sampleEpochMs'])
        self.assertGreater(second['sampleSequence'], first['sampleSequence'])
        self.assertEqual(self.native.commands[1]['commandId'], second['requestId'])
        self.assertEqual('actual-avatar-entity', second['avatarEntities'][0]['name'])
        self.assertEqual({'schemaVersion', 'commandId', 'action', 'includeAvatarEntities'}, set(self.native.commands[0]))

    def test_missing_old_foreign_stale_and_incomplete_samples_cannot_be_results(self):
        self.native.missing = 2
        self.assertEqual(1, self.observer.read(0)['sampleSequence'])
        for changes in ({'requestId': 'ios-' + 'f' * 32}, {'sampleEpochMs': 1}, {'complete': False},
                        {'sampleSequence': 0}, {'entitiesComplete': False}):
            with self.subTest(changes=changes):
                self.native.mutation = lambda value: value.update(changes)
                with self.assertRaisesRegex(NativeUIError, '^Native iOS feature observation failed$'):
                    self.observer.read(self.observer.sequence, include_avatar_entities=True)

    def test_observer_instance_and_actual_process_change_fail_without_relabeling(self):
        self.observer.read(0)
        self.native.mutation = lambda value: value.update(instance='b' * 32)
        with self.assertRaises(NativeUIError): self.observer.read(1)
        self.native.mutation = None
        self.native.pid = 43
        with self.assertRaises(NativeUIError): self.observer.read(1)
        self.assertEqual(2, len(self.native.commands))

    def test_process_loss_after_capture_blocks_acceptance(self):
        self.native.mutation = lambda value: setattr(self.native, 'pid', 43)
        with self.assertRaises(NativeUIError): self.observer.read(0)
        self.assertEqual(0, self.observer.sequence)

    def test_native_base64_and_transport_errors_are_closed(self):
        for value in ('not-base64', 'a' * 100000):
            with patch.object(self.native, 'execute', return_value=value), self.assertRaises(NativeUIError) as error:
                self.observer.read(0)
            self.assertNotIn('controlled.invalid', str(error.exception))
        with patch.object(self.native, 'execute', side_effect=RuntimeError('private native selector')):
            with self.assertRaisesRegex(NativeUIError, '^Native iOS feature observation failed$'):
                self.observer.read(0)

    def test_unsafe_documents_paths_and_nonphysical_profiles_are_rejected(self):
        for path in ('../owned', '/owned', 'owned/../other', 'owned//other', 'owned?query'):
            self.native.target['testBuild']['resultsDirectory'] = path
            with self.assertRaises(NativeUIError): self.native.observer()
        self.native.target['testBuild']['resultsDirectory'] = 'owned-results'
        self.native.target['physical'] = False
        with self.assertRaises(NativeUIError): self.native.observer()
        self.assertEqual([], self.native.commands)

    def test_existing_ios_component_factory_uses_actual_native_process_reads(self):
        component = IOSAdapter.__new__(IOSAdapter)
        observer = component._feature_observer('private-target', self.native, 'native-session',
            {'processIdentity': '42'}, self.native.target)
        observer.epoch_ms = lambda: 10000
        self.assertEqual(1, observer.read(0)['sampleSequence'])
        self.assertFalse(any(value.startswith('feature.') for value in IOSAdapter.advertised_capabilities(self.native.target)))

    def test_post_transport_does_not_follow_redirects(self):
        # This owned loopback server is a protocol fixture, never a device lab.
        paths = []
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                paths.append(self.path)
                self.send_response(302); self.send_header('Location', '/foreign'); self.end_headers()
            def do_GET(self): paths.append(self.path); self.send_response(200); self.end_headers()
            def log_message(self, *_): pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        worker = threading.Thread(target=server.serve_forever, daemon=True); worker.start()
        try:
            request = Request('http://127.0.0.1:' + str(server.server_port) + '/owned', data=b'{}', method='POST')
            # Call the original implementation, not the component's HTTP mock.
            with self.assertRaises(HTTPError) as error:
                feature_observation.build_opener(feature_observation.NoRedirect()).open(request, timeout=2)
            error.exception.close()
            self.assertEqual(['/owned'], paths)
        finally:
            server.shutdown(); worker.join(timeout=2); server.server_close()


if __name__ == '__main__': unittest.main()
