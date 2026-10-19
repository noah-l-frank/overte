"""Actual Pico wrapper and token flow; synthetic native/Qt/OpenXR boundaries."""
# SPDX-License-Identifier: Apache-2.0
from functools import partial
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import uuid

import test_native_execution_binding as existing

sys.path.insert(0, str(Path(__file__).resolve().parents[5] / 'tests/device'))
from adapters.android import adapter
from adapters.pico4 import normal_scripts
from adapters.pico4 import binding as pico_binding
from adapters.normal_script_manager import NormalScriptManager
from adapters.token_script_ui import TokenScriptUI
from self_tests.test_token_script_ui import NativeBoundary, SOURCE
from self_tests.test_token_script_file_ui import NativeBoundary as FileBoundary
from adapters.token_script_file_ui import TokenScriptFilePicker
from adapters.native_script_files import NativeScriptFiles
from self_tests.test_native_script_files import Boundary as FilesBoundary


class PicoNormalScriptsTests(unittest.TestCase):
    def setUp(self):
        self.fixture = existing.NativeExecutionBindingTest()
        self.fixture.setUp(); self.addCleanup(self.fixture.doCleanups)
        self.fixture.navigation_setup()
        self.native = self.fixture.fake
        self.qt = NativeBoundary(menu=True)
        self.native_version = 1
        self.file_ui, self.file_focus, self.file_version = None, None, 1
        self.last_read_request = None
        original_read = self.native.read_debug_app_file
        self.original_snapshot = self.native.snapshot

        def snapshot():
            self.qt.opened = self.native.opened
            value = self.original_snapshot()
            actual = self.qt.capture()
            if self.file_ui is not None and self.qt.page == 'scripts':
                files = self.file_ui.capture()
                actual['controls'] = files['controls'] if self.file_ui.opened else actual['controls'] + files['controls']
                value['fileControlsVersion'] = self.file_version
            value.update(open=actual['open'], ready=actual['ready'], featureControlsVersion=self.native_version)
            value['controls'] = []
            for item in actual['controls']:
                row = dict(item)
                row['token'] = str(uuid.uuid5(uuid.NAMESPACE_URL, row['id'] + row.get('sourceUrl', '') + str(row.get('currentIndex', ''))))
                if row['id'] == 'scripts.from-file' or row['id'].startswith('script-file.'):
                    row['focused'] = self.file_focus == row['id']
                value['controls'].append(row)
            return value

        def read(target, package, path, **kwargs):
            if path.endswith('/normal-feature-observation.json'):
                value, _ = self.qt.observe(0)
                value.update(requestId=self.last_read_request, sampleEpochMs=self.native.epoch_milliseconds(target))
                return json.dumps(value)
            return original_read(target, package, path, **kwargs)

        def write(target, package, path, raw):
            command = json.loads(raw)
            if path == adapter.ANDROID_CONTROL_COMMAND:
                self.assertEqual('normal-feature-observe', command['action'])
                self.last_read_request = command['commandId']
                return
            self.assertEqual('files/overte-e2e/navigation-ui-command.json', path)
            current = snapshot()
            row = next(item for item in current['controls'] if item['id'] == command['controlId'])
            self.assertEqual(row['token'], command['controlToken'])
            self.assertEqual(current['generation'], command['generation'])
            self.assertEqual(self.native.sequence + 1, command['sequence'])
            self.native.sequence += 1; self.native.inputs.append(command)
            file = self.file_ui is not None and (command['controlId'] == 'scripts.from-file' or command['controlId'].startswith('script-file.'))
            if file:
                identifier = command['controlId']
                if command['action'] == 'replace': self.file_ui.replace(identifier, command['text'])
                elif command['action'] == 'submit': self.file_ui.submit(identifier)
                elif command['action'] == 'select-index': self.file_ui.select_index(identifier, command['index'])
                elif identifier == 'script-file.primary': self.file_ui.actions.append(identifier)
                else: self.file_ui.activate(identifier, source=row.get('sourceUrl'))
                if command['action'] == 'activate': self.file_focus = identifier
            elif command['action'] == 'replace': self.qt.replace(command['controlId'], command['text'])
            else: self.qt.activate(command['controlId'], source=row.get('sourceUrl'))
            self.native.status = dict(schemaVersion=1, bridgeId=self.native.bridge_id,
                commandId=command['commandId'], sequence=command['sequence'], performed=True, error='',
                processId=123, updatedEpochMs=self.native.epoch_milliseconds(target))

        def stage(identity, operation, values):
            self.assertEqual('123:synthetic-start', identity)
            states = list(self.fixture.state_root.glob('normal-script-state-*.json'))
            self.assertEqual(1, len(states))
            self.assertTrue(json.loads(states[0].read_text())['tabletOwned'])
            self.native.controllers.append(operation)
            self.native.opened = operation == 'tablet.open'
            if not self.native.opened: self.qt.page = 'home'
            return {'performed': True}

        for boundary in (patch.dict(os.environ, {'OVERTE_PICO_NORMAL_SCRIPTS': '1'}),
            patch.object(self.native, 'snapshot', side_effect=snapshot),
            patch.object(self.native, 'read_debug_app_file', side_effect=read),
            patch.object(self.native, 'write_debug_app_file', side_effect=write),
            patch.object(self.native, 'stage', side_effect=stage),
            patch.object(normal_scripts, 'NormalScriptManager', partial(NormalScriptManager,
                monotonic=lambda: self.qt.clock, sleep=self.qt.sleep)),
            patch.object(normal_scripts, 'TokenScriptUI', partial(TokenScriptUI,
                monotonic=lambda: self.qt.clock, sleep=self.qt.sleep))):
            boundary.start(); self.addCleanup(boundary.stop)
        self.instance = self.fixture.instance()

    def invoke(self, operation, arguments=None):
        return self.instance.invoke(self.native.target, operation, arguments or {})

    def load(self):
        self.invoke('scripts.manager.open')
        self.invoke('scripts.load-url', {'url': SOURCE})

    def cleanup_instance(self):
        args, binding = adapter.cli([*self.fixture.prefix, 'cleanup', '--target', self.native.target])
        return binding.create_adapter(args, adapter.AndroidAdapter)

    def file_picker(self, fault=''):
        self.invoke('scripts.manager.open')
        root = self.fixture.fixture.root / ('feature-script-' + 'a' * 32)
        root.mkdir()
        (root / 'script.js').write_text("var companion = Script.require('./companion.js');")
        (root / 'companion.js').write_text('module.exports = {delta: 1};')
        self.file_ui = FileBoundary(root); self.file_ui.fault = fault
        boundary = patch.object(pico_binding, 'TokenScriptFilePicker', partial(TokenScriptFilePicker,
            monotonic=lambda: self.file_ui.clock, sleep=self.file_ui.sleep))
        boundary.start(); self.addCleanup(boundary.stop)
        return self.instance._script_file_picker(self.native.target, root.as_uri())

    def file_storage(self):
        source = FilesBoundary(self.fixture.fixture.root)
        def mutate(value):
            value.update(processId=123, requestedEpochMs=self.native.epoch_milliseconds(self.native.target),
                         capturedEpochMs=self.native.epoch_milliseconds(self.native.target))
        source.mutate = mutate
        original_write, original_read = self.native.write_debug_app_file, self.native.read_debug_app_file
        def write(target, package, path, raw):
            value = json.loads(raw)
            if value['action'] == 'feature-script-files':
                self.assertEqual(adapter.ANDROID_CONTROL_COMMAND, path)
                self.assertEqual('org.overte.pico', package)
                return source.send(value)
            return original_write(target, package, path, raw)
        def read(target, package, path, **kwargs):
            if path == 'files/overte-e2e/feature-script-files.json': return source.read()
            return original_read(target, package, path, **kwargs)
        for boundary in (patch.object(self.native, 'write_debug_app_file', side_effect=write),
            patch.object(self.native, 'read_debug_app_file', side_effect=read),
            patch.object(pico_binding, 'NativeScriptFiles', partial(NativeScriptFiles,
                monotonic=lambda: source.clock, sleep=source.sleep))):
            boundary.start(); self.addCleanup(boundary.stop)
        return source, self.instance._script_files(self.native.target)

    def test_pico_staged_original_bytes_use_bound_transport_and_separate_release_absence(self):
        source, files = self.file_storage()
        self.assertEqual(source.root.as_uri(), files.stage('a' * 32)); files.release()
        self.assertFalse(source.root.exists()); self.assertIsNone(self.instance._script_files_store(self.native.target).read())
        self.assertEqual([], self.native.inputs)

    def test_pico_staged_file_acknowledgment_without_originals_keeps_cleanup_intent(self):
        source, files = self.file_storage(); source.fault = 'ack-only'
        with self.assertRaises(RuntimeError): files.stage('a' * 32)
        self.assertIsNotNone(self.instance._script_files_store(self.native.target).read())
        self.assertEqual(1, sum(c['operation'] == 'stage' for c in source.commands))

    def test_pico_staged_file_candidate_loss_blocks_release_without_discarding_intent(self):
        source, files = self.file_storage(); files.stage('a' * 32)
        before = len(source.commands); self.native.digest = 'f' * 64
        with self.assertRaises(RuntimeError): files.release()
        self.assertEqual(before, len(source.commands)); self.assertTrue(source.root.exists())
        self.assertIsNotNone(self.instance._script_files_store(self.native.target).read())

    def test_pico_general_cleanup_cannot_retire_persistent_files_when_only_app_teardown_succeeded(self):
        source, files = self.file_storage(); files.stage('a' * 32)
        with self.assertRaises(ValueError): self.cleanup_instance().cleanup(self.native.target)
        self.assertFalse(self.native.running)
        self.assertIsNotNone(self.instance._script_files_store(self.native.target).read())
        self.assertTrue(source.root.exists())

    def test_pico_file_picker_uses_real_native_row_tokens_and_review_without_executing_via_api(self):
        picker = self.file_picker(); picker.open(); picker.choose('script.js')
        self.assertEqual([(self.file_ui.root / 'script.js').as_uri()], self.file_ui.accepted)
        self.assertEqual(1, sum(item['controlId'] == 'script-file.confirm' for item in self.native.inputs))

    def test_pico_file_ignored_row_acknowledgment_cannot_confirm_the_bundle(self):
        picker = self.file_picker('row'); picker.open()
        with self.assertRaises(RuntimeError): picker.choose('script.js')
        self.assertEqual([], self.file_ui.accepted)
        self.assertEqual(1, sum(item['controlId'].startswith('script-file.row.') for item in self.native.inputs))
        picker.cancel()
        self.assertFalse(self.file_ui.opened)

    def test_pico_file_main_selector_is_actual_normal_input_with_observed_readback(self):
        picker = self.file_picker('wrong-primary'); picker.open(); picker.choose('script.js')
        self.assertEqual([(self.file_ui.root / 'script.js').as_uri()], self.file_ui.accepted)
        self.assertEqual(1, sum(item['action'] == 'select-index' for item in self.native.inputs))

    def test_pico_file_candidate_change_and_missing_native_marker_stop_before_file_input(self):
        picker = self.file_picker(); self.file_version = None
        before = len(self.native.inputs)
        with self.assertRaises(RuntimeError): picker.open()
        self.assertEqual(before, len(self.native.inputs))
        self.file_version = 1; self.native.digest = 'f' * 64
        with self.assertRaisesRegex(ValueError, 'OVT_PICO_BINDING_REJECTED'): picker.open()
        self.assertEqual(before, len(self.native.inputs))

    def test_existing_native_candidate_wrapper_executes_normal_vr_menu_load_restart_stop_and_close(self):
        self.load()
        self.assertEqual([dict(url=SOURCE, path=SOURCE)], self.qt.rows)
        self.assertEqual(['scripts.menu', 'scripts.menu-edit', 'scripts.menu-running'],
            [item['controlId'] for item in self.native.inputs[:3]])
        self.invoke('scripts.restart', {'url': SOURCE})
        self.invoke('scripts.stop', {'url': SOURCE})
        self.invoke('scripts.manager.close')
        self.assertEqual([], self.qt.rows)
        self.assertEqual([], list(self.fixture.state_root.glob('normal-script-state-*.json')))
        self.assertFalse(self.native.opened)

    def test_missing_native_control_extension_fails_before_any_vr_input(self):
        self.native_version = None
        with self.assertRaises(ValueError): self.invoke('scripts.manager.open')
        self.assertEqual([], self.native.inputs)
        self.assertEqual([], self.native.controllers)

    def test_foreign_actual_full_source_cannot_receive_a_row_action(self):
        self.load(); self.qt.foreign_source = True
        with self.assertRaises(ValueError): self.invoke('scripts.stop', {'url': SOURCE})
        self.assertFalse(any(item['controlId'].startswith('scripts.stop.') for item in self.native.inputs))

    def test_changed_installed_candidate_stops_delivery_and_retains_cleanup_intent(self):
        self.load(); self.native.digest = 'f' * 64
        with self.assertRaises(ValueError): self.cleanup_instance().cleanup(self.native.target)
        self.assertFalse(self.native.running)
        self.assertEqual([dict(url=SOURCE, path=SOURCE)], self.qt.rows)
        self.assertEqual(1, len(list(self.fixture.state_root.glob('normal-script-state-*.json'))))

    def test_cleanup_with_valid_candidate_stops_source_before_original_process_teardown(self):
        self.load()
        self.assertEqual({'cleaned': True}, self.cleanup_instance().cleanup(self.native.target))
        self.assertFalse(self.native.running)
        self.assertEqual([], self.qt.rows)
        self.assertEqual([], list(self.fixture.state_root.glob('normal-script-state-*.json')))

    def test_ignored_native_stop_fails_cleanup_and_retains_persisted_source_intent(self):
        self.load(); self.qt.ignore_stop = True
        with self.assertRaises(ValueError): self.cleanup_instance().cleanup(self.native.target)
        self.assertFalse(self.native.running)
        self.assertEqual(1, len(list(self.fixture.state_root.glob('normal-script-state-*.json'))))


if __name__ == '__main__': unittest.main()
