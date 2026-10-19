"""Real iOS Script component over native W3C/HTTP/AFC/process boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from functools import partial
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from adapters.normal_script_manager import NormalScriptManager
from adapters.normal_ui import NativeUI, NativeUIError, W3C_ELEMENT
from adapters.token_script_ui import TokenScriptUI
from fixture.serve import FixtureState
from ios.adapters.adapter import IOSAdapter
from ios.adapters import adapter as component, appium_adapter, normal_input, normal_scripts, feature_observation
from self_tests.test_token_script_ui import NativeBoundary, SOURCE
from self_tests.test_token_script_file_ui import NativeBoundary as FileBoundary
from adapters import token_script_file_ui as file_module
from adapters.token_script_file_ui import TokenScriptFilePicker
from adapters.native_script_files import NativeScriptFiles
from self_tests.test_native_script_files import Boundary as FilesBoundary


class Native:
    def __init__(self):
        self.qt = NativeBoundary()
        self.pid, self.running, self.deleted, self.sequence = 42, True, False, 0
        self.version = 1
        self.file_ui, self.file_focus, self.file_version = None, None, 1
        self.instance = '11111111-1111-4111-8111-111111111111'
        self.elements, self.commands = {}, []
        self.fixture = FixtureState()
        self.retire_on_click = False
        self.file_source = None
        self.target = dict(platform='ios', physical=True, appId='org.example.client',
            serverUrl='http://controlled.invalid:49121', probe={'kind': 'ios-documents'},
            nativeUiObservation={'kind': 'uikit-documents', 'version': 1},
            testBuild=dict(fixtureOrigin='http://controlled.invalid:49121', resultsDirectory='owned-results'),
            normalScripts=dict(contractVersion=1, profile=normal_scripts.PROFILE))

    def process(self):
        return dict(bundleId=self.target['appId'], pid=self.pid, foreground=True) if self.running else None

    def epoch(self): return int(time.time() * 1000)

    def controls(self):
        value = self.qt.capture()
        if self.file_ui is not None and self.qt.page == 'scripts':
            files = self.file_ui.capture()
            value['controls'] = files['controls'] if self.file_ui.opened else value['controls'] + files['controls']
        rows = []
        for item in value['controls']:
            row = dict(item)
            row['token'] = str(uuid.uuid5(uuid.NAMESPACE_URL, row['id'] + row.get('sourceUrl', '') + str(row.get('currentIndex', ''))))
            if row['id'].startswith('script-file.') or row['id'] == 'scripts.from-file':
                row['focused'] = self.file_focus == row['id']
            row['frame'] = dict(x=10, y=20, width=200, height=48)
            rows.append(row)
        return rows

    def observed(self):
        return dict(schemaVersion=1, instance=self.instance, frameSpace='qt-window-logical', processId=42,
            sampleEpochMs=self.epoch(), elapsedMs=int(self.qt.clock * 1000), lastSequence=self.sequence,
            tabletShown=self.qt.opened, ready=True, controls=self.controls(), featureControlsVersion=self.version, fileControlsVersion=self.file_version)

    def post(self, request, timeout):
        command = self.fixture.set_client_command(json.loads(request.data))
        self.commands.append(command)
        self.echo = json.dumps(command).encode()
        if command['action'] == 'normal-ui-input':
            if command['operation'] == 'observe':
                self.receipt = dict(schemaVersion=1, commandId=command['commandId'], observation=self.observed())
            else:
                native = command['input']
                self.sequence += 1
                assert native['sequence'] == self.sequence and native['instance'] == self.instance
                field = next(row for row in self.controls() if row['token'] == native['fieldToken'])
                assert field['focused']
                if field['id'] == 'scripts.url.field': self.qt.replace(field['id'], native['text'])
                elif native['operation'] == 'replace': self.file_ui.replace(field['id'], native['text'])
                elif native['operation'] == 'submit': self.file_ui.submit(field['id'])
                else:
                    assert native['operation'] == 'select-index'
                    self.file_ui.select_index(field['id'], native['index'])
                self.receipt = dict(schemaVersion=1, commandId=command['commandId'], status=dict(
                    schemaVersion=1, commandId=native['commandId'], instance=self.instance, sequence=self.sequence,
                    performed=True, processId=42, sampleEpochMs=self.epoch()))
        elif command['action'] == 'feature-script-files':
            self.file_source.send(command)
        elif command['action'] == 'normal-feature-observe':
            self.diagnostic, _ = self.qt.observe(0)
            self.diagnostic.update(requestId=command['commandId'], sampleEpochMs=self.epoch())
        else:
            raise AssertionError('Unexpected synthetic native request')
        return self

    def read(self, limit): return self.echo[:limit]
    status = 200
    def __enter__(self): return self
    def __exit__(self, *_args): return False

    def execute(self, session, operation, values):
        if operation == 'mobile: overteProcessInfo': return self.process()
        if operation == 'mobile: terminateApp': self.running = False; return None
        assert operation == 'mobile: pullFile'
        root = '@org.example.client:documents/owned-results/'
        name = values['remotePath'].removeprefix(root)
        assert name in {'ios-normal-ui-request-result.json', 'normal-feature-observation.json', 'feature-script-files.json'}
        if name == 'feature-script-files.json':
            return base64.b64encode(self.file_source.read().encode()).decode()
        value = self.receipt if name.startswith('ios-normal-ui') else self.diagnostic
        return base64.b64encode(json.dumps(value).encode()).decode()

    def element(self, identifier):
        if identifier == 'OverteTabletOpen' and not self.qt.opened: return 'tablet.open', 'open-token'
        if identifier == 'OverteTabletClose' and self.qt.opened and not self.qt.dialog and not (self.file_ui and self.file_ui.opened): return 'tablet.close', 'close-token'
        name = identifier.removeprefix('OverteNavigation.')
        rows = [row for row in self.controls() if row['id'] == name]
        return (name, rows[0]['token']) if rows else None

    def call(self, method, path, body=None):
        if path == '/session/native-session' and method == 'DELETE': self.deleted = True; return None
        if path.endswith('/actions') and method == 'DELETE': return None
        if path.endswith('/elements'):
            found = self.element(body['value'])
            if found is None: return []
            reference = 'node-' + hashlib.sha256((found[0] + found[1]).encode()).hexdigest()
            self.elements[reference] = found
            return [{W3C_ELEMENT: reference}]
        reference = path.split('/element/')[1].split('/')[0]
        name, token = self.elements[reference]
        if path.endswith('/displayed'): return True
        if path.endswith('/enabled'): return True
        if path.endswith('/attribute/value'): return token
        assert path.endswith('/click') and method == 'POST'
        if self.retire_on_click and name.startswith(('scripts.stop.', 'scripts.restart.')):
            self.qt.foreign_source = True
        if name == 'tablet.open': self.qt.tablet(True)
        elif name == 'tablet.close': self.qt.tablet(False)
        else:
            row = next(row for row in self.controls() if row['id'] == name)
            if row['token'] != token: raise RuntimeError('retired native source token')
            if name.startswith('script-file.') or name == 'scripts.from-file':
                self.file_focus = name
                if name == 'script-file.primary': self.file_ui.actions.append(name)
                else: self.file_ui.activate(name, source=row.get('sourceUrl'))
            else: self.qt.activate(name, source=row.get('sourceUrl'))
        return None


class IOSNormalScriptsTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup); os.chmod(directory.name, 0o700)
        self.path = Path(directory.name) / 'session.json'
        self.native = Native()
        self.adapter = IOSAdapter.__new__(IOSAdapter)
        self.adapter.platform = 'ios'
        self.state = dict(sessionId='native-session', generation=1, processIdentity='42',
            targetFingerprint=hashlib.sha256(json.dumps(self.native.target, sort_keys=True,
                separators=(',', ':')).encode()).hexdigest())
        def terminate(_target): self.native.running = False
        for boundary in (
            patch.object(self.adapter, 'target', return_value=self.native.target),
            patch.object(self.adapter, 'ensure_session', side_effect=lambda _: (self.native, 'native-session', self.state)),
            patch.object(self.adapter, 'state_path', return_value=self.path),
            patch.object(self.adapter, 'read_session', side_effect=lambda _: None if self.native.deleted else self.state),
            patch.object(self.adapter, 'terminate_ios_app_without_wda', side_effect=terminate),
            patch.object(appium_adapter, 'WebDriver', return_value=self.native),
            patch.object(normal_input, 'urlopen', side_effect=self.native.post),
            patch.object(feature_observation, 'post_request', side_effect=self.native.post),
            patch.object(component, 'NativeUI', partial(NativeUI, monotonic=lambda: self.native.qt.clock,
                                                       sleep=self.native.qt.sleep)),
            patch.object(normal_scripts, 'NormalScriptManager', partial(NormalScriptManager,
                monotonic=lambda: self.native.qt.clock, sleep=self.native.qt.sleep)),
            patch.object(normal_scripts, 'TokenScriptUI', partial(TokenScriptUI,
                monotonic=lambda: self.native.qt.clock, sleep=self.native.qt.sleep))):
            boundary.start(); self.addCleanup(boundary.stop)

    def invoke(self, operation, arguments=None):
        return self.adapter.invoke('test-only-selector', operation, arguments or {})

    def load(self):
        self.invoke('scripts.manager.open')
        self.invoke('scripts.load-url', {'url': SOURCE})

    def file_picker(self, fault=''):
        self.invoke('scripts.manager.open')
        root = self.path.parent / ('feature-script-' + 'a' * 32)
        root.mkdir(); (root / 'script-bundle').mkdir()
        for folder, main in ((root, 'script.js'), (root / 'script-bundle', 'main.js')):
            (folder / main).write_text("var companion = Script.require('./companion.js');")
            (folder / 'companion.js').write_text('module.exports = {delta: 1};')
        self.native.file_ui = FileBoundary(root); self.native.file_ui.fault = fault
        boundary = patch.object(file_module, 'TokenScriptFilePicker', partial(TokenScriptFilePicker,
            monotonic=lambda: self.native.file_ui.clock, sleep=self.native.file_ui.sleep))
        boundary.start(); self.addCleanup(boundary.stop)
        return self.adapter._script_file_picker('test-only-selector', root.as_uri())

    def file_storage(self):
        source = FilesBoundary(self.path.parent); self.native.file_source = source
        source.mutate = lambda value: value.update(processId=42, requestedEpochMs=self.native.epoch(),
                                                  capturedEpochMs=self.native.epoch())
        boundary = patch.object(feature_observation, 'NativeScriptFiles', partial(NativeScriptFiles,
            monotonic=lambda: source.clock, sleep=source.sleep))
        boundary.start(); self.addCleanup(boundary.stop)
        return source, self.adapter._script_files('test-only-selector')

    def test_ios_staged_originals_use_actual_http_afc_and_separate_native_absence(self):
        source, files = self.file_storage()
        self.assertEqual(source.root.as_uri(), files.stage('a' * 32))
        intent = self.adapter.script_files_store('test-only-selector').read()
        self.assertEqual('NATIVE_UI_COMPONENT_ONLY', intent['binding']['scope'])
        self.assertNotIn('artifactSha256', intent['binding'])
        files.release(); self.assertFalse(source.root.exists())
        self.assertIsNone(self.adapter.script_files_store('test-only-selector').read())
        self.assertEqual([], self.native.qt.inputs)

    def test_ios_staged_ack_without_original_files_cannot_pass_readback(self):
        source, files = self.file_storage(); source.fault = 'ack-only'
        with self.assertRaises(NativeUIError): files.stage('a' * 32)
        self.assertIsNotNone(self.adapter.script_files_store('test-only-selector').read())
        self.assertEqual(1, sum(c['operation'] == 'stage' for c in source.commands))

    def test_ios_staged_file_foreign_process_cannot_release_or_retire_intent(self):
        source, files = self.file_storage(); files.stage('a' * 32)
        before = len(source.commands); self.native.pid = 43
        with self.assertRaises(NativeUIError): files.release()
        self.assertEqual(before, len(source.commands)); self.assertTrue(source.root.exists())
        self.assertIsNotNone(self.adapter.script_files_store('test-only-selector').read())

    def test_ios_staged_file_ignored_release_keeps_files_and_intent(self):
        source, files = self.file_storage(); files.stage('a' * 32); source.fault = 'ignored-release'
        with self.assertRaises(NativeUIError): files.release()
        self.assertTrue(source.root.exists())
        self.assertIsNotNone(self.adapter.script_files_store('test-only-selector').read())

    def test_ios_general_cleanup_fails_with_persistent_files_after_original_process_teardown(self):
        source, files = self.file_storage(); files.stage('a' * 32)
        with self.assertRaises(NativeUIError): self.adapter.cleanup('test-only-selector')
        self.assertFalse(self.native.running); self.assertTrue(source.root.exists())
        self.assertIsNotNone(self.adapter.script_files_store('test-only-selector').read())

    def test_ios_file_bundle_and_relative_companion_use_original_native_controls_and_review(self):
        picker = self.file_picker(); picker.open(); picker.choose('script-bundle/main.js')
        self.assertEqual([(self.native.file_ui.root / 'script-bundle/main.js').as_uri()], self.native.file_ui.accepted)
        self.assertEqual(1, self.native.file_ui.actions.count('script-file.confirm'))
        edits = [c['input'] for c in self.native.commands if c.get('operation') == 'edit']
        self.assertEqual(['replace', 'submit'], [c['operation'] for c in edits])
        self.assertFalse(self.native.file_ui.opened)

    def test_ios_file_ignored_row_acknowledgment_requires_explicit_observed_cancel(self):
        picker = self.file_picker('row'); picker.open()
        with self.assertRaises(NativeUIError): picker.choose('script.js')
        self.assertEqual([], self.native.file_ui.accepted)
        self.assertEqual(1, sum(a.startswith('script-file.row.') for a in self.native.file_ui.actions))
        picker.cancel(); self.assertFalse(self.native.file_ui.opened)

    def test_ios_file_primary_selector_uses_one_normal_key_input_and_actual_readback(self):
        picker = self.file_picker('wrong-primary'); picker.open(); picker.choose('script.js')
        self.assertEqual([(self.native.file_ui.root / 'script.js').as_uri()], self.native.file_ui.accepted)
        edits = [c['input'] for c in self.native.commands if c.get('operation') == 'edit']
        self.assertEqual(1, sum(c['operation'] == 'select-index' for c in edits))

    def test_ios_file_ignored_selector_cannot_confirm_and_cancel_observes_disappearance(self):
        picker = self.file_picker('primary'); picker.open()
        with self.assertRaises(NativeUIError): picker.choose('script.js')
        self.assertEqual([], self.native.file_ui.accepted)
        self.assertNotIn('script-file.confirm', self.native.file_ui.actions)
        picker.cancel(); self.assertFalse(self.native.file_ui.opened)

    def test_ios_file_missing_marker_or_changed_process_cannot_deliver_input(self):
        picker = self.file_picker(); before = list(self.native.file_ui.actions)
        self.native.file_version = None
        with self.assertRaises(NativeUIError): picker.open()
        self.assertEqual(before, self.native.file_ui.actions)
        self.native.file_version = 1; self.native.pid = 43
        with self.assertRaises(RuntimeError): picker.open()
        self.assertEqual(before, self.native.file_ui.actions)

    def test_ios_file_foreign_live_uikit_source_token_cannot_adopt_an_existing_row(self):
        picker = self.file_picker(); picker.open()
        original = self.native.call
        def call(method, path, body=None):
            if path.endswith('/attribute/value'):
                return '22222222-2222-4222-8222-222222222222'
            return original(method, path, body)
        self.native.call = call
        with self.assertRaises(NativeUIError): picker.choose('script.js')
        self.assertEqual([], self.native.file_ui.accepted)
        self.assertEqual(['scripts.from-file'], self.native.file_ui.actions)

    def test_original_normal_ui_component_load_restart_stop_and_owned_cleanup(self):
        self.load()
        value = self.adapter.script_store('test-only-selector').read()
        self.assertEqual('NATIVE_UI_COMPONENT_ONLY', value['binding']['scope'])
        self.assertNotIn('artifactSha256', value['binding'])
        self.assertEqual([dict(url=SOURCE, path=SOURCE)], self.native.qt.rows)
        self.invoke('scripts.restart', {'url': SOURCE})
        self.invoke('scripts.stop', {'url': SOURCE})
        self.invoke('scripts.manager.close')
        self.assertIsNone(self.adapter.script_store('test-only-selector').read())
        self.assertFalse(self.native.qt.opened)

    def test_missing_native_source_extension_fails_before_any_input(self):
        self.native.version = None
        with self.assertRaises(RuntimeError): self.invoke('scripts.manager.open')
        self.assertEqual([], self.native.qt.inputs)

    def test_ignored_field_edit_is_not_a_script_load_and_cancel_closes_owned_dialog(self):
        self.invoke('scripts.manager.open'); self.native.qt.ignore_text = True
        with self.assertRaises(RuntimeError): self.invoke('scripts.load-url', {'url': SOURCE})
        self.assertNotIn('scripts.url.submit', self.native.qt.inputs)
        self.invoke('scripts.manager.close')
        self.assertFalse(self.native.qt.dialog)

    def test_foreign_same_basename_and_retired_native_uikit_reference_never_stop_source(self):
        self.load(); self.native.retire_on_click = True
        with self.assertRaises(RuntimeError): self.invoke('scripts.stop', {'url': SOURCE})
        self.assertNotIn('scripts.stop.0', self.native.qt.inputs)
        self.assertEqual([dict(url=SOURCE, path=SOURCE)], self.native.qt.rows)

    def test_cleanup_observes_actual_source_stop_before_teardown(self):
        self.load()
        self.assertEqual({'cleaned': True}, self.adapter.cleanup('test-only-selector'))
        self.assertEqual([], self.native.qt.rows)
        self.assertFalse(self.native.running)

    def test_ignored_stop_retains_source_intent_and_fails_cleanup(self):
        self.load(); self.native.qt.ignore_stop = True
        with self.assertRaises(NativeUIError): self.adapter.cleanup('test-only-selector')
        self.assertFalse(self.native.running)
        self.assertTrue(self.adapter.script_store('test-only-selector').read()['loadAttempted'])

    def test_lost_native_process_still_reaches_teardown_and_retains_source_intent(self):
        self.load(); self.native.pid = 43
        with self.assertRaises(NativeUIError): self.adapter.cleanup('test-only-selector')
        self.assertFalse(self.native.running)
        self.assertTrue(self.adapter.script_store('test-only-selector').read()['loadAttempted'])
        self.assertEqual([dict(url=SOURCE, path=SOURCE)], self.native.qt.rows)

    def test_new_session_generation_cannot_adopt_the_previous_script_intent(self):
        self.load(); self.state['generation'] += 1
        with self.assertRaisesRegex(RuntimeError, '^Normal iOS Script component operation failed$'):
            self.invoke('scripts.stop', {'url': SOURCE})
        self.assertNotIn('scripts.stop.0', self.native.qt.inputs)


if __name__ == '__main__': unittest.main()
