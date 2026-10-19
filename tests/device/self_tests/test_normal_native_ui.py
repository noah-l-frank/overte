"""Counterfactual W3C input transport; no target discovery or device claims."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import sys
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adapters.normal_ui import Locator, NativeUI, NativeUIError, W3C_ELEMENT
from adapters.shared_appium.adapter import WebDriver


class NativeBoundary:
    def __init__(self):
        self.clock = 0.0
        self.calls, self.guards = [], 0
        self.elements = [{W3C_ELEMENT: 'actual-node'}]
        self.visible = self.enabled = True
        self.fail_path = None
        self.fail_guard_at = None
        self.text = 'previous native field text'
        self.click_count = 0
        self.arrive_after = None
        self.ignore_keys = False
        self.ui = NativeUI(self, 'owned-session', self.check, timeout=0.3,
                           monotonic=lambda: self.clock, sleep=self.sleep)

    def check(self):
        self.guards += 1
        if self.guards == self.fail_guard_at:
            raise RuntimeError('secret target selector from owning guard')

    def call(self, method, path, body=None):
        self.calls.append((method, path, body))
        if path.endswith(self.fail_path or '/never-fail'):
            raise RuntimeError('secret selector and entered credential from transport')
        if path.endswith('/elements'):
            return self.elements if self.arrive_after is None or self.clock >= self.arrive_after else []
        if path.endswith('/displayed'):
            return self.visible
        if path.endswith('/enabled'):
            return self.enabled
        if path.endswith('/text'):
            return self.text
        if method == 'POST' and path.endswith('/actions'):
            if not self.ignore_keys:
                keys = body['actions'][0]['actions'][4:]
                self.text = ''.join(value['value'] for value in keys
                                    if value['type'] == 'keyDown' and value['value'] != '\ue003')
            return None
        if path.endswith('/clear'):
            self.text = ''
        if path.endswith('/value'):
            self.text = body['text']
        if path.endswith('/click'):
            self.click_count += 1
        return None

    def sleep(self, seconds):
        self.clock += seconds

    @property
    def mutations(self):
        return [row for row in self.calls if row[0] == 'POST' and not row[1].endswith('/elements')]


class NormalNativeUITests(unittest.TestCase):
    def test_owned_ascii_replacement_uses_actual_keyboard_events_and_releases_modifiers(self):
        native = NativeBoundary()
        native.ui.replace_ascii_keys(Locator('id', 'ActualField'), 'OVERTE_123.5')
        self.assertEqual('OVERTE_123.5', native.text)
        self.assertFalse(any(path.endswith(('/clear', '/value')) for _, path, _ in native.calls))
        self.assertEqual(1, sum(method == 'POST' and path.endswith('/actions') for method, path, _ in native.calls))
        self.assertTrue(any(method == 'DELETE' and path.endswith('/actions') for method, path, _ in native.calls))
        native.ui.replace_ascii_keys(Locator('id', 'ActualField'), '')
        self.assertEqual('', native.text)

    def test_ignored_or_uncertain_keyboard_input_never_becomes_success_or_replay(self):
        native = NativeBoundary()
        native.ignore_keys = True
        with self.assertRaises(NativeUIError):
            native.ui.replace_ascii_keys(Locator('id', 'ActualField'), 'owned')
        native.fail_path = '/actions'
        with self.assertRaises(NativeUIError):
            native.ui.replace_ascii_keys(Locator('id', 'ActualField'), 'owned')
        self.assertEqual(2, sum(method == 'POST' and path.endswith('/actions') for method, path, _ in native.calls))
        with self.assertRaises(NativeUIError):
            native.ui.replace_ascii_keys(Locator('id', 'ActualField'), 'unbounded' * 100)

    def test_click_resolves_one_actual_visible_enabled_node_and_checks_application_binding(self):
        native = NativeBoundary()
        native.ui.click(Locator('accessibility id', 'ActualControl'))
        self.assertEqual(1, native.click_count)
        self.assertEqual(('POST', '/session/owned-session/elements',
            {'using': 'accessibility id', 'value': 'ActualControl'}), native.calls[0])
        self.assertEqual([('POST', '/session/owned-session/element/actual-node/click', {})], native.mutations)
        self.assertGreaterEqual(native.guards, 5)
        self.assertIsNone(native.ui.click(Locator('id', 'org.overte.example:id/ActualControl')))

    def test_unicode_replacement_uses_actual_clear_and_native_value_commands(self):
        native = NativeBoundary()
        value = 'Controlled URL ÄU0001f30d'
        native.ui.replace_text(Locator('id', 'ActualField'), value)
        self.assertEqual(value, native.text)
        self.assertEqual(['/session/owned-session/element/actual-node/clear',
            '/session/owned-session/element/actual-node/value'], [row[1] for row in native.mutations])
        self.assertEqual({'text': value, 'value': list(value)}, native.mutations[-1][2])
        self.assertGreaterEqual(native.guards, 6)

    def test_read_only_wait_accepts_late_native_controls_without_retrying_input(self):
        native = NativeBoundary()
        native.arrive_after = 0.2
        native.ui.click(Locator('id', 'LateControl'))
        self.assertGreaterEqual(native.clock, 0.2)
        self.assertEqual(1, native.click_count)
        self.assertEqual(1, len(native.mutations))

    def test_duplicate_or_missing_hidden_disabled_controls_never_receive_input(self):
        for mode in ('duplicate', 'absent', 'hidden', 'disabled'):
            with self.subTest(mode=mode):
                native = NativeBoundary()
                if mode == 'duplicate':
                    native.elements.append({W3C_ELEMENT: 'other-node'})
                elif mode == 'absent':
                    native.elements = []
                elif mode == 'hidden':
                    native.visible = False
                else:
                    native.enabled = False
                with self.assertRaises(NativeUIError):
                    native.ui.click(Locator('id', 'ActualControl'))
                self.assertEqual([], native.mutations)
                self.assertLessEqual(len(native.calls), 15)

    def test_malformed_or_conflicting_references_cannot_become_paths(self):
        for value in ({}, {W3C_ELEMENT: '../foreign'}, {W3C_ELEMENT: True},
                      {W3C_ELEMENT: 'one', 'ELEMENT': 'two'}, {'foreign': 'one'},
                      {W3C_ELEMENT: 'x?private=target'}, {W3C_ELEMENT: 'a/b'}):
            with self.subTest(value=value):
                native = NativeBoundary()
                native.elements = [value]
                with self.assertRaises(NativeUIError):
                    native.ui.click(Locator('id', 'ActualControl'))
                self.assertEqual([], native.mutations)

    def test_nonboolean_native_action_state_is_not_coerced_to_ready(self):
        for value in (None, 1, 'true', {}, []):
            with self.subTest(value=value):
                native = NativeBoundary()
                native.enabled = value
                with self.assertRaises(NativeUIError):
                    native.ui.click(Locator('id', 'ActualControl'))
                self.assertEqual([], native.mutations)

    def test_binding_failure_after_resolution_stops_input_and_keeps_details_private(self):
        native = NativeBoundary()
        native.fail_guard_at = 4
        with self.assertRaises(NativeUIError) as error:
            native.ui.click(Locator('id', 'PrivateLocator'))
        self.assertEqual([], native.mutations)
        self.assertNotIn('secret', str(error.exception))
        self.assertNotIn('PrivateLocator', str(error.exception))
        native.ui.release_actions()
        self.assertEqual(('DELETE', '/session/owned-session/actions', None), native.calls[-1])

    def test_uncertain_click_or_text_result_is_never_retried_or_replaced_by_script(self):
        for path in ('/click', '/clear', '/value'):
            with self.subTest(path=path):
                native = NativeBoundary()
                native.fail_path = path
                with self.assertRaises(NativeUIError) as error:
                    if path == '/click':
                        native.ui.click(Locator('id', 'ActualControl'))
                    else:
                        native.ui.replace_text(Locator('id', 'ActualField'), 'private input')
                self.assertEqual(1, sum(row[1].endswith(path) for row in native.mutations))
                self.assertNotIn('private', str(error.exception))
                self.assertNotIn('secret', str(error.exception))
                self.assertFalse(any('/execute' in row[1] or '/actions' in row[1] for row in native.calls))

    def test_invalid_locator_session_text_or_clock_fails_before_unsafe_input(self):
        for using, value in (('xpath', '//execute'), ('-ios predicate string', 'anything'),
                             ('id', ''), ('id', 'x\nsecret'), ('id', 'x' * 257),
                             ({}, 'x'), ('id', [])):
            with self.subTest(using=using, value=value), self.assertRaises(NativeUIError):
                Locator(using, value)
        native = NativeBoundary()
        for text in (None, 'x\n', 'x\x00', '\x01', 'U0001f30d' * 2049, '\ud800'):
            with self.subTest(text_type=type(text).__name__), self.assertRaises(NativeUIError):
                native.ui.replace_text(Locator('id', 'ActualField'), text)
        self.assertEqual([], native.calls)
        with self.assertRaises(NativeUIError):
            NativeUI(native, '../other-session', native.check)
        with self.assertRaises(NativeUIError):
            NativeUI(native, 'owned-session', None)
        native.elements = []
        native.clock = float('nan')
        with self.assertRaises(NativeUIError):
            native.ui.click(Locator('id', 'ActualControl'))
        self.assertEqual([], native.mutations)

    def test_actual_shared_webdriver_transports_normal_input_without_a_device_or_script_channel(self):
        native = NativeBoundary()

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_arguments):
                pass

            def request(self):
                length = int(self.headers.get('Content-Length', 0))
                body = json.loads(self.rfile.read(length)) if length else None
                value = native.call(self.command, self.path, body)
                payload = json.dumps({'value': value}).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            do_GET = do_POST = do_DELETE = request

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            client = WebDriver('http://127.0.0.1:' + str(server.server_port))
            ui = NativeUI(client, 'owned-session', native.check)
            ui.click(Locator('accessibility id', 'ActualControl'))
            ui.replace_text(Locator('id', 'ActualField'), 'Owned input ÄU0001f30d')
            ui.release_actions()
            self.assertEqual(1, native.click_count)
            self.assertEqual('Owned input ÄU0001f30d', native.text)
            self.assertEqual(3, len(native.mutations))
            self.assertEqual('DELETE', native.calls[-1][0])
            self.assertFalse(any('/execute' in row[1] for row in native.calls))
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def test_absence_requires_stable_missing_nodes_and_disabled_visible_nodes_do_not_disappear(self):
        native = NativeBoundary()
        native.elements = []
        native.ui.timeout = 0.5
        self.assertFalse(native.ui.available(Locator('id', 'ActualControl')))
        native.ui.wait_absent(Locator('id', 'ActualControl'))
        self.assertGreaterEqual(native.clock, 0.3)
        self.assertEqual([], native.mutations)
        for transient in (False, True):
            with self.subTest(transient=transient):
                native = NativeBoundary()
                native.enabled = False
                if transient: native.arrive_after = 0.2
                with self.assertRaises(NativeUIError):
                    native.ui.wait_absent(Locator('id', 'ActualControl'))
                self.assertEqual([], native.mutations)

    def test_literal_text_rejects_webdriver_control_keys_without_any_native_request(self):
        for key in ('\ue000', '\ue003', '\ue007', '\ue050', '\ue05d'):
            with self.subTest(key_codepoint=hex(ord(key))):
                native = NativeBoundary()
                with self.assertRaises(NativeUIError):
                    native.ui.replace_text(Locator('id', 'ActualField'), 'ordinary text' + key)
                self.assertEqual([], native.calls)

    def test_explicit_enter_is_one_native_key_action_and_never_replayed_after_failure(self):
        native = NativeBoundary()
        native.ui.press_enter(Locator('id', 'ActualField'))
        self.assertEqual([('POST', '/session/owned-session/element/actual-node/value',
                          {'text': '\ue007', 'value': ['\ue007']})], native.mutations)
        self.assertGreaterEqual(native.guards, 5)
        native = NativeBoundary()
        native.fail_path = '/value'
        with self.assertRaises(NativeUIError):
            native.ui.press_enter(Locator('id', 'ActualField'))
        self.assertEqual(1, len(native.mutations))
        native = NativeBoundary()
        # An ordinary private-use glyph outside the WebDriver key table stays
        # literal Unicode; do not reject every custom-font character.
        native.ui.replace_text(Locator('id', 'ActualField'), 'ordinary \ue100 glyph')
        self.assertEqual('ordinary \ue100 glyph', native.text)


if __name__ == '__main__':
    unittest.main()
