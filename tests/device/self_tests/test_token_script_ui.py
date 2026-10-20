"""Counterexamples for normal token-based Script UI; no Qt/device claim."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_script_manager import NormalScriptManager
from adapters.normal_ui import NativeUIError
from adapters.token_script_ui import TokenScriptUI, script_control, metadata_fields, validate_metadata

SOURCE = 'http://controlled.test/script-management/' + 'a' * 32 + '/client.js'
BINDING = dict(sourceRevision='b' * 40, artifactSha256='c' * 64,
    processIdentity='123:native', sessionId='bound-native', generation=1, targetFingerprint='d' * 64)


class NativeBoundary:
    def __init__(self, *, menu=False):
        self.clock, self.sequence = 0.0, 0
        self.opened, self.dialog, self.focused = False, False, False
        self.menu, self.page, self.text = menu, 'home', ''
        self.rows, self.inputs = [], []
        self.enabled, self.ignore_text, self.ignore_stop = True, False, False
        self.version = 1
        self.foreign_label = self.foreign_source = False

    def sleep(self, seconds): self.clock += seconds

    def capture(self):
        names = []
        if self.opened:
            if self.dialog: names = ['scripts.url.field', 'scripts.url.submit', 'scripts.url.cancel']
            elif self.page == 'home': names = ['scripts.menu' if self.menu else 'scripts.entry']
            elif self.page == 'menu': names = ['scripts.menu-edit']
            elif self.page == 'edit': names = ['scripts.menu-running']
            elif self.page == 'scripts':
                names = ['scripts.from-url', 'tablet.home']
                if self.rows: names += ['scripts.stop.0', 'scripts.restart.0']
        controls = []
        for name in names:
            row = dict(id=name, enabled=self.enabled, focused=self.focused, token='native-current-token')
            if name == 'scripts.url.field': row['text'] = self.text
            if name.startswith(('scripts.stop.', 'scripts.restart.')):
                row['rowLabel'] = 'foreign.js' if self.foreign_label else self.rows[0]['url'].rsplit('/', 1)[-1]
                row['sourceUrl'] = 'http://foreign.test/client.js' if self.foreign_source else self.rows[0]['url']
            controls.append(row)
        return dict(featureControlsVersion=self.version, open=self.opened, ready=self.opened, controls=controls)

    def tablet(self, opened):
        self.inputs.append('tablet.open' if opened else 'tablet.close')
        self.opened = opened
        if not opened: self.page = 'home'

    def activate(self, control, *, source=None):
        assert control in {row['id'] for row in self.capture()['controls']}
        self.inputs.append(control)
        if control == 'scripts.menu': self.page = 'menu'
        elif control == 'scripts.menu-edit': self.page = 'edit'
        elif control in {'scripts.entry', 'scripts.menu-running'}: self.page = 'scripts'
        elif control == 'scripts.from-url': self.dialog = True
        elif control == 'scripts.url.field': self.focused = True
        elif control == 'scripts.url.submit':
            if not self.text.endswith('missing.js'): self.rows.append(dict(url=self.text, path=self.text))
            self.dialog = False
        elif control == 'scripts.url.cancel': self.dialog = False
        elif control == 'tablet.home': self.page = 'home'
        elif control == 'scripts.stop.0':
            if source != self.rows[0]['url']: raise NativeUIError('Native row source changed')
            if not self.ignore_stop: self.rows = []
        elif control == 'scripts.restart.0':
            if source != self.rows[0]['url']: raise NativeUIError('Native row source changed')

    def replace(self, control, text):
        assert control == 'scripts.url.field' and self.dialog and self.focused
        self.inputs.append('native-field-replace')
        if not self.ignore_text: self.text = text

    def release(self): self.inputs.append('release')

    def observe(self, after):
        self.sequence += 1
        return dict(schemaVersion=1, instance='f' * 32, sampleSequence=self.sequence,
            sampleEpochMs=10000, complete=True, scripts=[dict(row) for row in self.rows]), 10000

    def flow(self, path):
        ui = TokenScriptUI(self, monotonic=lambda: self.clock, sleep=self.sleep)
        return NormalScriptManager(ui, self.observe, PrivateFeatureState(path), BINDING,
                                   monotonic=lambda: self.clock, sleep=self.sleep)


class TokenScriptUITests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        os.chmod(directory.name, 0o700)
        self.path = Path(directory.name) / 'scripts.json'

    def invoke(self, native, operation, arguments=None):
        return native.flow(self.path).invoke(operation, arguments or {})

    def load(self, native):
        self.invoke(native, 'scripts.manager.open')
        self.invoke(native, 'scripts.load-url', {'url': SOURCE})

    def test_normal_native_entry_and_real_vr_menu_route_execute_same_owned_flow(self):
        for menu in (False, True):
            with self.subTest(menu=menu):
                native = NativeBoundary(menu=menu)
                self.load(native)
                self.assertEqual([dict(url=SOURCE, path=SOURCE)], native.rows)
                self.invoke(native, 'scripts.restart', {'url': SOURCE})
                self.invoke(native, 'scripts.stop', {'url': SOURCE})
                self.invoke(native, 'scripts.manager.close')
                self.assertFalse(native.opened)
                self.assertFalse(self.path.exists())
                self.assertEqual(1, native.inputs.count('scripts.url.submit'))
                if menu:
                    self.assertEqual(['tablet.open', 'scripts.menu', 'scripts.menu-edit', 'scripts.menu-running'], native.inputs[:4])

    def test_missing_native_extension_or_disabled_entry_cannot_receive_a_click(self):
        for version in (None, 0, True, 2):
            native = NativeBoundary(); native.version = version
            with self.assertRaises(NativeUIError): self.invoke(native, 'scripts.manager.open')
            self.assertEqual([], native.inputs)
        native = NativeBoundary(); native.enabled = False
        with self.assertRaises(NativeUIError): self.invoke(native, 'scripts.manager.open')
        self.assertEqual(['tablet.open'], native.inputs)

    def test_ignored_text_retains_dialog_intent_and_actual_cancel_cleans_the_panel(self):
        native = NativeBoundary(); native.ignore_text = True
        self.invoke(native, 'scripts.manager.open')
        with self.assertRaises(NativeUIError): self.invoke(native, 'scripts.load-url', {'url': SOURCE})
        self.assertTrue(PrivateFeatureState(self.path).read()['dialogOwned'])
        self.assertNotIn('scripts.url.submit', native.inputs)
        self.invoke(native, 'scripts.manager.close')
        self.assertIn('scripts.url.cancel', native.inputs)
        self.assertFalse(self.path.exists())

    def test_foreign_full_url_or_row_label_cannot_stop_or_restart_owned_source(self):
        for fault in ('label', 'source'):
            native = NativeBoundary(); self.load(native)
            native.foreign_label = fault == 'label'
            native.foreign_source = fault == 'source'
            for action in ('stop', 'restart'):
                with self.assertRaises(NativeUIError): self.invoke(native, 'scripts.' + action, {'url': SOURCE})
                self.assertNotIn('scripts.' + action + '.0', native.inputs)
            native.foreign_label = native.foreign_source = False
            self.invoke(native, 'scripts.stop', {'url': SOURCE})
            self.invoke(native, 'scripts.manager.close')

    def test_ignored_stop_and_missing_native_row_effect_cannot_report_clean(self):
        native = NativeBoundary(); self.load(native); native.ignore_stop = True
        with self.assertRaises(NativeUIError): self.invoke(native, 'scripts.stop', {'url': SOURCE})
        with self.assertRaises(NativeUIError): self.invoke(native, 'scripts.manager.close')
        self.assertTrue(PrivateFeatureState(self.path).read()['loadAttempted'])
        self.assertEqual([dict(url=SOURCE, path=SOURCE)], native.rows)
        self.assertEqual(1, native.inputs.count('scripts.stop.0'))

    def test_closed_control_inventory_and_original_metadata_reject_aliases_and_private_keys(self):
        for value in ('scripts.stop.128', 'scripts.stop.00', 'scripts.stop.-1', 'scripts.eval', None):
            self.assertFalse(script_control(value))
        self.assertTrue(script_control('scripts.restart.127'))
        self.assertEqual({'rowLabel', 'sourceUrl'}, metadata_fields('scripts.stop.1'))
        for row in ({'id': 'scripts.stop.1', 'rowLabel': 'client.js'},
                    {'id': 'scripts.url.field', 'text': False},
                    {'id': 'scripts.stop.1', 'rowLabel': 'client.js', 'sourceUrl': 'bad\nsource'}):
            with self.assertRaises(NativeUIError): validate_metadata(row)


if __name__ == '__main__': unittest.main()
