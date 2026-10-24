"""Actual iOS adapter/flow and native original reader; explicit WDA/render seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from contextlib import ExitStack
import copy
import importlib.util
import json
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch
import uuid

DEVICE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(DEVICE))
from adapters.normal_ui import NativeUI, NativeUIError, W3C_ELEMENT
from fixture.serve import FixtureState
from ios.adapters import adapter as ios_adapter, normal_input, normal_snapshot, snapshot_files
from snapshot_journey import snapshot_journey
import test_ios_snapshot_files as _original_files

_spec = importlib.util.spec_from_file_location('_ios_snapshot_render_fixture', DEVICE / 'self_tests/test_snapshot_journey.py')
_render_fixture = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_render_fixture)


class SnapshotBoundary(_original_files.FileBoundary):
    def __init__(self, binary, environment, directory, fixtures, mutation=''):
        super().__init__(binary, environment, directory, mutation)
        (self.root / self.name).unlink()
        self.fixtures = fixtures
        self.shown, self.screen, self.page, self.popup, self.popup_after = False, 'home', 1, None, 0
        self.mode, self.format, self.name_value, self.focused = 'animated', 'webp', '', False
        self.instance = '11111111-2222-3333-4444-555555555555'
        self.sequence, self.frame, self.busy, self.foreign = 0, 0, False, False
        self.inputs, self.saved, self.reports = [], [], []
        self.state = {'sessionId': 'owned-session', 'processIdentity': str(self.pid), 'iosE2ELaunchCompleted': True}
        self.profile = {'contractVersion': 1, 'profile': normal_snapshot.PROFILE,
                        'sceneUrl': 'http://controlled.invalid:49121/scene.json'}
        self.target |= {'platform': 'ios', 'physical': True, 'probe': {'kind': 'ios-documents'},
            'normalSnapshot': self.profile, 'snapshotFilesObservation': {'kind': 'ios-documents', 'version': 1}}
        self.adapter = ios_adapter.IOSAdapter.__new__(ios_adapter.IOSAdapter)
        self.adapter.platform, self.adapter.adapter_id = 'ios', 'appium-ios'
        self.adapter.target = lambda _: self.target
        self.adapter.ensure_session = lambda _: (self, 'owned-session', self.state)
        self.adapter.state_path = lambda _: directory / 'session.json'
        self.adapter.save_session = lambda _, value: self.saved.append(copy.deepcopy(value))

    def sleep(self, seconds):
        self.clock += seconds

    def controls(self):
        controls = {}
        def add(name, *, enabled=True, focused=False, checked=None):
            row = {'id': name, 'token': str(uuid.uuid5(uuid.NAMESPACE_OID, name)), 'enabled': enabled,
                'focused': focused, 'frame': {'x': 10, 'y': 20, 'width': 180, 'height': 44}}
            if checked is not None: row['checked'] = checked
            controls[name] = row
        if self.foreign:
            add('address.field', focused=True); return controls
        if not self.shown:
            add('hud.tablet'); return controls
        add('tablet.close'); add('tablet.home')
        if self.screen == 'home':
            add('tablet.page.1'); add('tablet.page.2')
            if self.page == 2: add('snapshot.entry')
        elif self.screen == 'snapshot':
            add('snapshot.name', focused=self.focused)
            add('snapshot.mode', enabled=not self.busy); add('snapshot.format')
            add('snapshot.capture', enabled=not self.busy)
            if self.busy: add('snapshot.cancel')
            if self.popup and self.frame >= self.popup_after:
                values = normal_snapshot.MODES if self.popup == 'mode' else normal_snapshot.FORMATS
                for value in values: add('snapshot.' + self.popup + '.' + value, checked=getattr(self, self.popup) == value)
        return controls

    def observed(self):
        self.frame += 1
        return {'schemaVersion': 1, 'instance': self.instance, 'frameSpace': 'qt-window-logical',
            'processId': self.reader.pid, 'sampleEpochMs': time.time() * 1000, 'elapsedMs': self.frame,
            'lastSequence': self.sequence, 'tabletShown': self.shown, 'ready': True,
            'controls': list(self.controls().values())}

    def post(self, request, timeout):
        command = json.loads(request.data)
        FixtureState().set_client_command(command)
        if command['action'] == 'snapshot-files':
            return super().post(request, timeout)
        assert command['action'] == 'normal-ui-input'
        if command['operation'] == 'observe':
            receipt = {'observation': self.observed()}
        else:
            value = command['input']
            valid = self.shown and self.screen == 'snapshot' and self.focused and not self.foreign
            assert value['fieldToken'] == self.controls()['snapshot.name']['token']
            assert value['operation'] == 'replace', 'normal capture must never use field submission'
            if valid and self.mutation != 'name-ignored': self.name_value = value['text']
            self.sequence = value['sequence']
            receipt = {'status': {'schemaVersion': 1, 'commandId': value['commandId'], 'instance': self.instance,
                'sequence': self.sequence, 'performed': valid, 'processId': self.reader.pid,
                'sampleEpochMs': time.time() * 1000}}
        self.input_receipt = {'schemaVersion': 1, 'commandId': command['commandId'], **receipt}
        self.response = json.dumps(command).encode()
        return self

    def execute(self, session, operation, arguments):
        if operation == 'mobile: overteProcessInfo':
            assert arguments == {'bundleId': self.target['appId']}
            return self.process()
        if arguments.get('remotePath', '').endswith('/ios-normal-ui-request-result.json'):
            return base64.b64encode(json.dumps(self.input_receipt).encode()).decode()
        return super().execute(session, operation, arguments)

    @staticmethod
    def identifier(name):
        return str(uuid.uuid5(uuid.NAMESPACE_URL, name))

    def call(self, method, path, body=None):
        if path.endswith('/elements'):
            assert method == 'POST' and body['using'] == 'accessibility id'
            name = body['value']
            control = ('hud.tablet' if name == 'OverteTabletOpen' else 'tablet.close'
                       if name == 'OverteTabletClose' else name.removeprefix('OverteNavigation.'))
            return [{W3C_ELEMENT: self.identifier(control)}] if control in self.controls() else []
        if path.endswith('/actions'):
            assert method == 'DELETE'; return None
        parts = path.split('/')
        identifier, suffix = parts[-2:]
        name = next((name for name in self.controls() if self.identifier(name) == identifier), None)
        if suffix in ('displayed', 'enabled'):
            return name is not None and (suffix == 'displayed' or self.controls()[name]['enabled'])
        assert method == 'POST' and suffix == 'click' and name is not None
        self.inputs.append(name)
        if name == 'hud.tablet':
            self.shown = True
        elif name == 'tablet.close':
            if self.mutation != 'close-ignored': self.shown = False
        elif name == 'tablet.home': self.screen, self.popup = 'home', None
        elif name.startswith('tablet.page.'): self.page = int(name.rsplit('.', 1)[1])
        elif name == 'snapshot.entry':
            self.screen = 'snapshot'
            if self.mutation == 'entry-error-once':
                self.mutation = ''; raise RuntimeError('fixture boundary lost the first input response')
        elif name == 'snapshot.name': self.focused = True
        elif name in ('snapshot.mode', 'snapshot.format'):
            self.popup = name.rsplit('.', 1)[1]
            self.popup_after = self.frame + (3 if self.mutation == 'late-popup' else 0)
        elif name.startswith(('snapshot.mode.', 'snapshot.format.')):
            category, value = name.split('.')[1:]
            if self.mutation != category + '-ignored': setattr(self, category, value)
            self.popup = None
        elif name == 'snapshot.cancel': self.busy = False
        elif name == 'snapshot.capture': self.capture()
        return None

    def capture(self):
        if self.mutation != 'capture-ignored':
            keys = [self.format]
            if self.mode == 'animated' and self.mutation != 'missing-gif': keys.append('gif')
            label = 'still-' + self.format if self.mode == 'still' else self.mode
            for extension in keys:
                key = 'gif' if extension == 'gif' else label
                # Renderer is an explicit fixture. Original storage/transport,
                # actual file hashes and the independent decoder are real.
                content = self.fixtures[key]
                ticket = '124_1' if extension == 'gif' and self.mutation == 'wrong-ticket' else '123_1'
                (self.root / (self.name_value + '-snap_' + ticket + '.' + extension)).write_bytes(content)
        self.shown, self.focused, self.popup = False, False, None
        if self.mutation == 'reopen-home': self.screen = 'home'

    def invoke(self, operation, values):
        return self.adapter.invoke('fixture-only', operation, values)

    def run(self):
        return snapshot_journey('0123456789abcdef', invoke=self.invoke,
            read_artifact=lambda path: (self.artifacts / path).read_bytes(), assert_session=lambda _: self.process(),
            monotonic=lambda: self.clock, sleep=self.sleep, report=self.reports.append)

    def seams(self):
        stack = ExitStack()
        stack.enter_context(patch.dict('os.environ', OVERTE_DEVICE_ARTIFACT_DIR=str(self.artifacts)))
        stack.enter_context(patch.object(normal_input, 'urlopen', self.post))
        stack.enter_context(patch.object(snapshot_files, 'urlopen', self.post))
        native_type, files_type = normal_input.NativeInput, snapshot_files.SnapshotFiles
        stack.enter_context(patch.object(ios_adapter, 'NativeUI', lambda *args, **kwargs:
            NativeUI(*args, **kwargs, monotonic=lambda: self.clock, sleep=self.sleep)))
        stack.enter_context(patch.object(ios_adapter, 'NativeInput', lambda *args, **kwargs:
            native_type(*args, **kwargs, monotonic=lambda: self.clock, sleep=self.sleep)))
        stack.enter_context(patch.object(ios_adapter, 'SnapshotFiles', lambda *args, **kwargs:
            files_type(*args, **kwargs, monotonic=lambda: self.clock, sleep=self.sleep)))
        return stack


class IOSNormalSnapshot(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _original_files.OriginalSnapshotFiles.setUpClass()
        cls.native = _original_files.OriginalSnapshotFiles.native.SnapshotFiles
        cls.fixtures = {'still-png': _render_fixture.encoded(), 'still-jpg': _render_fixture.encoded(file_format='JPEG'),
            'animated': _render_fixture.encoded(), 'gif': _render_fixture.gif(),
            'panorama': _render_fixture.encoded((8192, 4096)), 'cubemap': _render_fixture.encoded((8192, 6144))}

    @classmethod
    def tearDownClass(cls):
        _original_files.OriginalSnapshotFiles.tearDownClass()

    def setUp(self):
        import tempfile
        self.temporary = tempfile.TemporaryDirectory(prefix='ios-normal-snapshot-')
        self.boundaries = []

    def tearDown(self):
        for boundary in self.boundaries: boundary.close()
        self.temporary.cleanup()

    def boundary(self, mutation=''):
        directory = Path(self.temporary.name) / str(len(self.boundaries)); directory.mkdir(mode=0o700)
        boundary = SnapshotBoundary(self.native.binary, self.native.environment, directory, self.fixtures, mutation)
        self.boundaries.append(boundary)
        return boundary

    def test_original_adapter_runs_five_cases_six_decoded_files_and_restores_actual_preferences(self):
        boundary = self.boundary()
        with boundary.seams(): result = boundary.run()
        self.assertEqual(len(result), 5)
        self.assertEqual(sum(len(row['outputs']) for row in result), 6)
        self.assertEqual((boundary.mode, boundary.format), ('animated', 'webp'))
        self.assertFalse(boundary.shown)
        self.assertNotIn('iosNormalSnapshot', boundary.state)
        self.assertTrue(boundary.reports[-1]['outputSequenceCompleted'])
        self.assertFalse(boundary.reports[-1]['deviceAcceptance'])
        self.assertTrue(any(value.get('iosNormalSnapshot', {}).get('context', {}).get('scope')
                            == normal_snapshot.SCOPE for value in boundary.saved))

    def test_acknowledged_capture_or_name_ignored_and_missing_or_foreign_gif_cannot_pass(self):
        for mutation in ('capture-ignored', 'name-ignored', 'missing-gif', 'wrong-ticket'):
            boundary = self.boundary(mutation)
            with self.subTest(mutation=mutation), boundary.seams(), self.assertRaises(AssertionError): boundary.run()
            self.assertFalse(boundary.reports[-1]['outputSequenceCompleted'])
            self.assertNotIn('iosNormalSnapshot', boundary.state)

    def test_ignored_mode_or_format_is_rejected_before_capture(self):
        for mutation in ('mode-ignored', 'format-ignored'):
            boundary = self.boundary(mutation)
            with self.subTest(mutation=mutation), boundary.seams(), self.assertRaises(NativeUIError): boundary.run()
            self.assertNotIn('snapshot.capture', boundary.inputs)
            self.assertFalse(boundary.reports[-1]['outputSequenceCompleted'])

    def test_popup_late_frame_and_reopened_home_use_normal_entry_and_preserve_all_preferences(self):
        for mutation in ('late-popup', 'reopen-home'):
            boundary = self.boundary(mutation)
            with self.subTest(mutation=mutation), boundary.seams():
                result = boundary.run()
                self.assertEqual(len(result), 5)
                self.assertEqual((boundary.mode, boundary.format), ('animated', 'webp'))
                self.assertFalse(boundary.shown)

    def test_foreign_panel_or_process_instance_cannot_be_adopted_or_closed(self):
        for panel in ('tablet', 'address'):
            boundary = self.boundary()
            if panel == 'tablet': boundary.shown = True
            else: boundary.foreign = True
            with self.subTest(panel=panel), boundary.seams(), self.assertRaisesRegex(NativeUIError, 'pre-existing'):
                boundary.invoke('snapshot.open', {})
            self.assertEqual(boundary.inputs, [])
            self.assertNotIn('iosNormalSnapshot', boundary.state)
        boundary = self.boundary()
        with boundary.seams():
            boundary.invoke('snapshot.open', {})
            before = list(boundary.inputs); boundary.instance = str(uuid.uuid4())
            with self.assertRaisesRegex(NativeUIError, 'different native UI session'):
                boundary.invoke('snapshot.close', {})
        self.assertEqual(boundary.inputs, before)
        self.assertIn('iosNormalSnapshot', boundary.state)

    def test_failed_or_covered_close_keeps_owned_intent_and_does_not_close_foreign_modal(self):
        for mutation in ('close-ignored', 'covered'):
            boundary = self.boundary(mutation)
            with self.subTest(mutation=mutation), boundary.seams():
                boundary.invoke('snapshot.open', {})
                if mutation == 'covered': boundary.foreign = True
                with self.assertRaises(NativeUIError): boundary.invoke('snapshot.close', {})
            self.assertIn('iosNormalSnapshot', boundary.state)
            self.assertTrue(boundary.shown)
            if mutation == 'covered': self.assertNotIn('tablet.close', boundary.inputs)

    def test_partial_entry_error_can_close_actual_entered_panel_without_capture(self):
        boundary = self.boundary('entry-error-once')
        with boundary.seams():
            with self.assertRaises(NativeUIError): boundary.invoke('snapshot.open', {})
            self.assertIn('iosNormalSnapshot', boundary.state)
            self.assertEqual(boundary.invoke('snapshot.close', {}), {'performed': True})
        self.assertNotIn('snapshot.capture', boundary.inputs)
        self.assertFalse(boundary.shown)

    def test_preexisting_empty_owned_prefix_blocks_capture_in_the_original_journey(self):
        boundary = self.boundary()
        (boundary.root / boundary.name).touch()
        with boundary.seams(), self.assertRaisesRegex(AssertionError, 'already exists before capture'):
            boundary.run()
        self.assertNotIn('snapshot.capture', boundary.inputs)
        self.assertTrue(boundary.reports[-1]['normalCloseSucceeded'])

    def test_profile_is_explicit_component_only_and_invalid_configuration_never_creates_session(self):
        boundary = self.boundary()
        self.assertTrue(normal_snapshot.OPERATIONS <= set(boundary.adapter.advertised_capabilities(boundary.target)))
        for change in ({'normalSnapshot': None}, {'snapshotFilesObservation': None}, {'physical': False},
                       {'snapshotFilesObservation': {'kind': 'ios-documents', 'version': True}},
                       {'normalSnapshot': boundary.profile | {'contractVersion': True}}):
            target = boundary.target | change
            called = []
            boundary.adapter.target = lambda _, target=target: target
            boundary.adapter.ensure_session = lambda _: called.append(True)
            with self.subTest(change=change), self.assertRaises((RuntimeError, ValueError)):
                boundary.invoke('snapshot.open', {})
            self.assertEqual(called, [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
