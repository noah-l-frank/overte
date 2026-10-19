"""Ordinary file picker recipe with explicit native controls as the boundary."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from urllib.parse import unquote, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adapters.normal_ui import NativeUIError
from adapters.token_script_file_ui import TokenScriptFilePicker
from fixture.serve import FixtureState


class NativeBoundary:
    def __init__(self, root):
        self.root, self.current = root, root.parent
        self.opened, self.review, self.primary = False, None, -1
        self.chosen, self.actions, self.accepted = [], [], []
        self.field, self.clock, self.fault = '', 0.0, ''
        self.instance = 'a' * 32

    def sleep(self, seconds): self.clock += seconds

    def rows(self):
        return list(sorted(self.current.iterdir()))

    def capture(self):
        def row(identifier, **fields):
            token = hashlib.sha256(identifier.encode()).hexdigest()[:32]
            return dict(id=identifier, token=token, enabled=True, **fields)
        controls = [row('scripts.from-file')]
        if self.opened:
            picker = dict(caption='Open Script and Companion Files', directory=self.current.as_uri(),
                review=self.review is not None, error='', selectedUrls=list(self.chosen),
                relativePaths=self.review['names'] if self.review else [],
                bundleRoot=self.review['root'] if self.review else '',
                bundleUrls=self.review['urls'] if self.review else [])
            if self.review:
                controls = [row('script-file.review-cancel', picker=deepcopy(picker)),
                    row('script-file.confirm', picker=deepcopy(picker)),
                    row('script-file.primary', currentIndex=self.primary,
                        currentText=self.review['names'][self.primary])]
            else:
                controls = [row('script-file.folder', text=self.field, picker=deepcopy(picker)),
                    row('script-file.cancel', picker=deepcopy(picker)), row('script-file.select')]
                controls += [row('script-file.row.' + str(index), sourceUrl=path.as_uri(),
                    rowLabel=path.name, directory=path.is_dir(), selected=path.as_uri() in self.chosen)
                    for index, path in enumerate(self.rows())]
        return dict(fileControlsVersion=1, instance=self.instance, ready=True, controls=controls)

    def activate(self, identifier, *, source=None):
        self.actions.append(identifier)
        if identifier == 'scripts.from-file':
            if self.fault != 'open': self.opened = True
        elif identifier.startswith('script-file.row.'):
            path = self.rows()[int(identifier.rsplit('.', 1)[1])]
            if self.fault == 'foreign-row': path = path.parent / ('foreign-' + path.name)
            if path.as_uri() != source: raise NativeUIError('Native row changed its source')
            if self.fault != 'row': self.chosen.append(path.as_uri())
        elif identifier == 'script-file.select':
            if self.fault == 'select': return
            paths = [Path(unquote(urlsplit(url).path)) for url in self.chosen]
            self.review = dict(root=self.current.as_uri(), urls=list(self.chosen), names=[p.name for p in paths])
            self.primary = 1 if self.fault in ('wrong-primary', 'primary') else 0
            if self.fault == 'extra-companion':
                self.review['names'].append('foreign.js'); self.review['urls'].append(self.current.as_uri() + '/foreign.js')
        elif identifier == 'script-file.confirm':
            if self.fault == 'confirm': return
            self.accepted.append(self.review['urls'][self.primary])
            self.opened = False; self.review = None
        elif identifier in ('script-file.cancel', 'script-file.review-cancel'):
            if self.fault != 'cancel': self.opened = False; self.review = None
        elif identifier != 'script-file.folder': raise AssertionError('Unexpected normal UI action')

    def replace(self, identifier, text):
        assert identifier == 'script-file.folder'
        self.actions.append('replace-folder')
        if self.fault != 'replace': self.field = text

    def submit(self, identifier):
        assert identifier == 'script-file.folder'
        self.actions.append('submit-folder')
        candidate = Path(self.field)
        if candidate.is_dir() and self.fault != 'navigate': self.current = candidate

    def select_index(self, identifier, index):
        assert identifier == 'script-file.primary' and 0 <= index < len(self.review['names'])
        self.actions.append('select-primary')
        if self.fault != 'primary': self.primary = index


class ScriptFilePickerTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(); self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / ('feature-script-' + 'a' * 32)
        self.root.mkdir(); (self.root / 'script-bundle').mkdir()
        for folder, main in ((self.root, 'script.js'), (self.root / 'script-bundle', 'main.js')):
            (folder / main).write_text("var module = Script.require('./companion.js');")
            (folder / 'companion.js').write_text('module.exports = {delta: 1};')

    def picker(self, fault=''):
        native = NativeBoundary(self.root); native.fault = fault
        picker = TokenScriptFilePicker(native, self.root.as_uri(), monotonic=lambda: native.clock, sleep=native.sleep)
        return native, picker

    def test_two_real_source_choices_use_normal_file_selection_and_actual_review(self):
        for resource in ('script.js', 'script-bundle/main.js'):
            with self.subTest(resource=resource):
                native, picker = self.picker(); picker.open(); picker.choose(resource)
                self.assertEqual([(self.root / resource).as_uri()], native.accepted)
                self.assertEqual(2, sum(a.startswith('script-file.row.') for a in native.actions))
                self.assertEqual(1, native.actions.count('script-file.confirm'))

    def test_cancel_and_review_cancel_accept_no_file(self):
        native, picker = self.picker(); picker.open(); picker.cancel()
        self.assertEqual([], native.accepted)
        native, picker = self.picker('confirm'); picker.open()
        with self.assertRaises(NativeUIError): picker.choose('script.js')
        native.fault = ''; picker.cancel()
        self.assertEqual([], native.accepted)
        self.assertIn('script-file.review-cancel', native.actions)

    def test_ignored_normal_inputs_never_prove_a_file_was_loaded_and_are_not_replayed(self):
        for fault in ('open', 'replace', 'navigate', 'row', 'select', 'confirm', 'primary'):
            with self.subTest(fault=fault):
                native, picker = self.picker(fault)
                with self.assertRaises(NativeUIError): picker.open(); picker.choose('script.js')
                self.assertEqual([], native.accepted)
                self.assertLessEqual(native.actions.count('scripts.from-file'), 1)
                self.assertLessEqual(native.actions.count('script-file.confirm'), 1)
                self.assertLessEqual(native.clock, 10.2)

    def test_ignored_cancel_remains_an_open_owned_dialog(self):
        native, picker = self.picker('cancel'); picker.open()
        with self.assertRaises(NativeUIError): picker.cancel()
        self.assertTrue(native.opened)
        self.assertEqual(1, native.actions.count('script-file.cancel'))

    def test_foreign_reused_row_missing_companion_and_extra_review_file_cannot_be_accepted(self):
        for fault in ('foreign-row', 'extra-companion', 'missing-companion'):
            with self.subTest(fault=fault):
                native, picker = self.picker(fault)
                if fault == 'missing-companion': (self.root / 'companion.js').unlink()
                with self.assertRaises(NativeUIError): picker.open(); picker.choose('script.js')
                self.assertEqual([], native.accepted)

    def test_wrong_default_main_uses_one_normal_selector_input_and_observed_readback(self):
        native, picker = self.picker('wrong-primary'); picker.open(); picker.choose('script.js')
        self.assertEqual([(self.root / 'script.js').as_uri()], native.accepted)
        self.assertEqual(1, native.actions.count('select-primary'))

    def test_missing_marker_foreign_context_and_foreign_dialog_fail_before_further_input(self):
        for fault in ('marker', 'context', 'dialog'):
            with self.subTest(fault=fault):
                native, picker = self.picker(); picker.open()
                before = list(native.actions); original = native.capture
                def capture():
                    value = original()
                    if fault == 'marker': value.pop('fileControlsVersion')
                    elif fault == 'context': value['instance'] = 'b' * 32
                    else:
                        for row in value['controls']:
                            if 'picker' in row: row['picker']['caption'] = 'Unrelated file dialog'
                    return value
                native.capture = capture
                with self.assertRaises(NativeUIError): picker.cancel()
                self.assertEqual(before, native.actions)

    def test_foreign_directory_and_encoded_parent_traversal_cannot_be_requested(self):
        native, _picker = self.picker()
        for directory in ('file:///unowned', self.root.as_uri() + '/%2e%2e', 'https://foreign/feature-script-' + 'a' * 32):
            with self.assertRaises(NativeUIError): TokenScriptFilePicker(native, directory)
        self.assertEqual([], native.actions)

    def test_existing_ios_fixture_admits_only_typed_bounded_native_selector_input(self):
        fixture = FixtureState()
        request = dict(schemaVersion=1, commandId='11111111-1111-4111-8111-111111111111',
            instance='22222222-2222-4222-8222-222222222222', sequence=1, observedElapsedMs=0,
            fieldToken='33333333-3333-4333-8333-333333333333', operation='select-index', index=0)
        outer = dict(schemaVersion=1, commandId='ios-' + 'a' * 32, action='normal-ui-input', operation='edit', input=request)
        self.assertEqual(outer, fixture.set_client_command(outer))
        for change in ({'index':True}, {'index':-1}, {'index':32}, {'text':'desired-main.js'}, {'expected':'main.js'}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                fixture.set_client_command(outer | {'input': request | change})


if __name__ == '__main__': unittest.main()
