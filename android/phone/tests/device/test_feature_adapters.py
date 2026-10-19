"""Phone feature adapter boundary tests; no device or candidate APK execution."""
# SPDX-License-Identifier: Apache-2.0
from functools import partial
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

import test_installed_identity as identity

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / 'tests/device'))
from adapters.normal_script_manager import NormalScriptManager, read_native_diagnostic
from adapters.normal_ui import NativeUI, W3C_ELEMENT
from adapters.shared_appium.adapter import AppiumAdapter
from create_observation import PREFIX
from create_journey import INITIAL, EDITED

appium = identity.appium
PACKAGE = 'io.github.noah_be.overte.phone'
SOURCE = 'http://fixture.test/script-management/' + 'a' * 32 + '/client.js'
SELECTOR = 'test-only-appium'


class Native:
    def __init__(self):
        self.screen = None
        self.dialog = False
        self.text = ''
        self.rows, self.inputs = [], []
        self.sequence = 0
        self.clock = 0.0
        self.identity = '31:14'
        self.ignore_stop = False
        self.ignore_delete = False
        self.mutation = None
        self.request = None
        self.entities, self.fields = [], {}
        self.selected = None
        self.popup = None
        self.by_reference = {}
        self.focused_field = None
        self.ignore_name_apply = False

    def visible(self, name):
        if name == 'tablet.open': return self.screen is None
        if name == 'nav.close': return self.screen is not None
        if name == 'nav.home': return self.screen not in (None, 'home')
        if name == 'app.scripts': return self.screen == 'home'
        if name == 'CREATE': return self.screen == 'home'
        if name == 'My avatar': return self.popup is not None
        if name == 'Cube': return self.screen == 'create'
        if name.startswith('NativeCreate'): return self.screen == 'create'
        if name in ('field', 'OK', 'Cancel'): return self.dialog
        if name == 'scriptFromUrl': return self.screen == 'scripts' and not self.dialog
        if name in ('scriptStop0', 'scriptRestart0'): return self.screen == 'scripts' and bool(self.rows)
        return False

    def sleep(self, seconds): self.clock += seconds

    def source(self):
        def node(kind, text='', identifier=''):
            return '<node package="' + PACKAGE + '" class="' + kind + '" text="' + text + '" resource-id="' + identifier + '"/>'
        if self.dialog:
            content = node('android.widget.TextView', 'Script URL') + node('android.widget.TextView', 'Open and Run Script')
        else:
            content = ''.join(node(kind, label, PACKAGE + ':id/' + name if name else '')
                for kind, label, name in (('android.widget.TextView', self.rows[0]['url'].rsplit('/', 1)[1], ''),
                    ('android.widget.Button', 'Restart', 'scriptRestart0'),
                    ('android.widget.Button', 'Stop', 'scriptStop0'))) if self.rows else ''
        return '<hierarchy><node>' + content + '</node></hierarchy>'

    def call(self, method, path, body=None):
        if path.endswith('/source'): return self.source()
        if method == 'POST' and path.endswith('/actions'):
            assert self.focused_field is not None
            assert body['actions'][0]['type'] == 'key'
            keys = body['actions'][0]['actions'][4:]
            self.fields[self.focused_field] = ''.join(value['value'] for value in keys if value['type'] == 'keyDown')
            self.inputs.append('normal-keyboard')
            return None
        if path.endswith('/elements'):
            name = 'field' if body['using'] == 'class name' else body['value'].removeprefix(PACKAGE + ':id/')
            if not self.visible(name): return []
            reference = 'reference' + str(len(self.by_reference))
            self.by_reference[reference] = name
            return [{W3C_ELEMENT: reference}]
        if '/element/' in path:
            reference = path.split('/element/', 1)[1].split('/')[0]
            name = self.by_reference[reference]
            if path.endswith('/displayed'): return self.visible(name)
            if path.endswith('/enabled'): return True
            if path.endswith('/attribute/className'): return 'android.widget.Button'
            if path.endswith('/attribute/resourceId'): return '' if name == 'My avatar' else PACKAGE + ':id/' + name
            if path.endswith('/attribute/package'): return PACKAGE
            if path.endswith('/text'): return self.text if name == 'field' else self.fields.get(name, '')
            if path.endswith('/clear'):
                if name == 'field': self.text = ''
                else: self.fields[name] = ''
                return None
            if path.endswith('/value'):
                if name == 'field': self.text = body['text']
                else: self.fields[name] = body['text']
                return None
            if path.endswith('/click'):
                self.inputs.append(name)
                if name == 'NativeCreateName' or name.startswith('NativeCreateField_'):
                    self.focused_field = name
                if name == 'tablet.open': self.screen = 'home'
                elif name == 'nav.home': self.screen = 'home'
                elif name == 'nav.close': self.screen = None
                elif name == 'app.scripts': self.screen = 'scripts'
                elif name == 'CREATE': self.screen = 'create'
                elif name in ('NativeCreateHost', 'NativeCreateImportHost'): self.popup = name
                elif name == 'My avatar': self.popup = None
                elif name == 'NativeCreateNew_Shape':
                    self.selected = dict(id='{11111111-1111-1111-1111-111111111111}', name='', type='Box')
                    self.entities.append(self.selected)
                elif name.startswith('NativeCreateEntity_'):
                    identifier = name.removeprefix('NativeCreateEntity_')
                    self.selected = next(row for row in self.entities if row['id'] == identifier)
                elif name == 'NativeCreateApply':
                    if 'NativeCreateName' in self.fields and not self.ignore_name_apply:
                        self.selected['name'] = self.fields['NativeCreateName']
                elif name == 'NativeCreateDelete' and not self.ignore_delete: self.entities.remove(self.selected)
                elif name == 'scriptFromUrl': self.dialog = True
                elif name == 'OK':
                    if not self.text.endswith('missing.js'): self.rows = [dict(url=self.text, path=self.text)]
                    self.dialog = False
                elif name == 'Cancel': self.dialog = False
                elif name == 'scriptStop0' and not self.ignore_stop: self.rows = []
                if self.mutation: self.mutation(name)
                return None
        if method == 'DELETE' and path.endswith('/actions'): return None
        raise AssertionError('Unexpected synthetic native endpoint')

    def command(self, client, session, target, command, process):
        assert command['action'] == 'normal-feature-observe'
        assert set(command) == {'schemaVersion', 'commandId', 'action', 'includeAvatarEntities'}
        assert process['identity'] == self.identity
        self.request = command

    def read(self, target, package, path, **kwargs):
        if path != 'files/overte-e2e/normal-feature-observation.json':
            raise AssertionError('Unexpected native file')
        self.sequence += 1
        value = dict(schemaVersion=1, requestId=self.request['commandId'], instance='f' * 32, complete=True,
            sampleSequence=self.sequence, sampleEpochMs=10000, scripts=self.rows)
        if self.request['includeAvatarEntities']:
            value.update(entitiesComplete=True, avatarEntities=self.entities)
        return json.dumps(value)


class FeatureAdapterTests(unittest.TestCase):
    def setUp(self):
        fixture = identity.InstalledIdentityTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.fixture = fixture
        self.adapter, self.target = fixture.appium_instance()
        self.target.update(probe={'kind': 'android-run-as', 'relativePath': self.adapter.ANDROID_DEBUG_PROBE},
            clientControl={'kind': 'android-run-as'}, scene={'kind': 'debug-fixture'})
        self.native = Native()
        self.state_path = fixture.root / 'session.json'
        state = dict(sessionId='native-session', generation=1,
                     targetFingerprint=self.adapter.snapshot_fingerprint(self.target))
        for boundary in (
            patch.dict(os.environ, {'OVERTE_PHONE_NORMAL_SCRIPTS': '1', 'OVERTE_PHONE_NORMAL_CREATE': '1'}),
            patch.object(self.adapter, 'controlled_android_client', return_value=True),
            patch.object(self.adapter, 'state_path', return_value=self.state_path),
            patch.object(AppiumAdapter, 'ensure_session', side_effect=lambda *_:
                (self.native, 'native-session', state)),
            patch.object(self.adapter, 'read_session', side_effect=lambda *_: state),
            patch.object(self.adapter, 'query_app_state', return_value=4),
            patch.object(self.adapter, 'process_state', side_effect=lambda *_:
                {'running': True, 'identity': self.native.identity}),
            patch.object(self.adapter, 'write_android_client_command', side_effect=self.native.command),
            patch.object(fixture.adb, 'read_debug_app_file', side_effect=self.native.read, create=True),
            patch.object(fixture.adb, 'epoch_milliseconds', return_value=10000, create=True),
            patch.object(appium, 'NormalScriptManager', partial(NormalScriptManager,
                monotonic=lambda: self.native.clock, sleep=self.native.sleep)),
            patch.object(appium, 'NativeUI', partial(NativeUI, timeout=0.6,
                monotonic=lambda: self.native.clock, sleep=self.native.sleep)),
            patch.object(appium, 'read_native_diagnostic', partial(read_native_diagnostic,
                monotonic=lambda: self.native.clock, sleep=self.native.sleep))):
            boundary.start(); self.addCleanup(boundary.stop)

    def invoke(self, operation, values=None):
        return self.adapter.invoke(SELECTOR, operation, values or {})

    def load(self):
        self.invoke('scripts.manager.open')
        self.invoke('scripts.load-url', {'url': SOURCE})

    def test_original_wrapper_native_input_and_candidate_checks_execute_complete_script_packet(self):
        self.load()
        self.invoke('scripts.restart', {'url': SOURCE})
        self.invoke('scripts.stop', {'url': SOURCE})
        self.invoke('scripts.manager.close')
        self.assertEqual(['tablet.open', 'app.scripts', 'scriptFromUrl', 'OK',
                          'scriptRestart0', 'scriptStop0', 'nav.close'], self.native.inputs)
        self.assertIsNone(self.adapter.script_store(SELECTOR).read())
        self.assertGreater(sum(row[0] == 'sha256sum' for row in self.fixture.adb.events), 10)
        self.assertFalse(any(cap.startswith('feature.') for cap in self.adapter.advertised_capabilities(self.target)))

    def test_changed_installed_bytes_fail_before_ui_session_or_input(self):
        self.fixture.adb.digest = '0' * 64
        with self.assertRaises(ValueError): self.invoke('scripts.manager.open')
        self.assertEqual([], self.native.inputs)

    def test_process_change_after_input_preserves_intent_and_fails(self):
        self.native.mutation = lambda _: setattr(self.native, 'identity', '32:14')
        with self.assertRaises(RuntimeError): self.invoke('scripts.manager.open')
        self.assertTrue(self.adapter.script_store(SELECTOR).read()['tabletOwned'])
        self.assertEqual(['tablet.open'], self.native.inputs)

    def test_missing_diagnostic_and_missing_opt_in_fail_before_input(self):
        with patch.object(self.fixture.adb, 'read_debug_app_file', return_value='{}'):
            with self.assertRaises(RuntimeError): self.invoke('scripts.manager.open')
        with patch.dict(os.environ, {'OVERTE_PHONE_NORMAL_SCRIPTS': '0'}):
            self.assertNotIn('scripts.manager.open', self.adapter.advertised_capabilities(self.target))
            with self.assertRaises(ValueError): self.invoke('scripts.manager.open')
        self.assertEqual([], self.native.inputs)

    def test_cleanup_cannot_report_green_when_owned_source_stop_is_ignored(self):
        self.load()
        self.native.ignore_stop = True
        with patch.object(AppiumAdapter, 'cleanup', return_value={'cleaned': True}) as base:
            with self.assertRaises(ValueError): self.adapter.cleanup(SELECTOR)
        base.assert_called_once()
        self.assertTrue(self.adapter.script_store(SELECTOR).read()['loadAttempted'])
        self.assertEqual(1, self.native.inputs.count('scriptStop0'))

    def test_cleanup_stops_owned_script_and_retires_only_after_native_absence(self):
        self.load()
        with patch.object(AppiumAdapter, 'cleanup', return_value={'cleaned': True}):
            self.assertEqual({'cleaned': True}, self.adapter.cleanup(SELECTOR))
        self.assertEqual([], self.native.rows)
        self.assertIsNone(self.adapter.script_store(SELECTOR).read())

    def test_cleanup_after_candidate_invalidation_still_stops_app_but_retains_unresolved_source(self):
        self.load()
        self.fixture.args.artifact.write_bytes(b'changed candidate')
        with patch.object(AppiumAdapter, 'cleanup', return_value={'cleaned': True}) as base:
            with self.assertRaises(ValueError): self.adapter.cleanup(SELECTOR)
        base.assert_called_once()
        self.assertTrue(self.adapter.script_store(SELECTOR).read()['loadAttempted'])

    def test_bound_create_uses_actual_native_uuid_normal_fields_and_observer_cleanup(self):
        url = 'http://fixture.test/create/' + 'a' * 32 + '/observer.js'
        name = PREFIX + 'a' * 32 + '_cube'
        self.invoke('create.reference.open', {'scriptUrl': url})
        self.invoke('create.cube', {'name': name, 'properties': INITIAL})
        self.assertEqual(name, self.native.entities[0]['name'])
        self.invoke('create.update', {'name': name, 'properties': EDITED})
        self.invoke('create.undo'); self.invoke('create.redo')
        self.invoke('create.reference.close', {'scriptUrl': url})
        self.assertEqual([], self.native.entities)
        self.assertEqual([], self.native.rows)
        self.assertIsNone(self.adapter.create_store(SELECTOR).read())
        self.assertIsNone(self.adapter.create_script_store(SELECTOR).read())
        self.assertIn('NativeCreateApply', self.native.inputs)
        self.assertEqual('0.8', self.native.fields['NativeCreateField_dimensions_x'])

    def test_create_cleanup_after_candidate_invalidation_is_not_reported_complete(self):
        url = 'http://fixture.test/create/' + 'a' * 32 + '/observer.js'
        self.invoke('create.reference.open', {'scriptUrl': url})
        self.fixture.args.artifact.write_bytes(b'changed candidate')
        with patch.object(AppiumAdapter, 'cleanup', return_value={'cleaned': True}) as base:
            with self.assertRaises(ValueError): self.adapter.cleanup(SELECTOR)
        base.assert_called_once()
        self.assertIsNotNone(self.adapter.create_store(SELECTOR).read())

    def test_foreign_native_script_label_cannot_authorize_restart(self):
        self.load()
        original = self.native.source
        self.native.source = lambda: original().replace('client.js', 'foreign.js')
        with self.assertRaises(RuntimeError): self.invoke('scripts.restart', {'url': SOURCE})
        self.assertNotIn('scriptRestart0', self.native.inputs)

    def test_ignored_delete_keeps_actual_entity_and_blocks_complete_cleanup(self):
        url = 'http://fixture.test/create/' + 'a' * 32 + '/observer.js'
        self.invoke('create.reference.open', {'scriptUrl': url})
        self.invoke('create.cube', {'name': PREFIX + 'a' * 32 + '_cube', 'properties': INITIAL})
        self.native.ignore_delete = True
        with patch.object(AppiumAdapter, 'cleanup', return_value={'cleaned': True}):
            with self.assertRaises(ValueError): self.adapter.cleanup(SELECTOR)
        self.assertEqual(1, len(self.native.entities))
        self.assertIsNotNone(self.adapter.create_store(SELECTOR).read())
        self.assertNotIn('scriptStop0', self.native.inputs)

    def test_flags_do_not_allow_an_unbound_or_uncontrolled_target(self):
        self.adapter.candidate = None
        with self.assertRaises(ValueError): self.adapter.advertised_capabilities(self.target)
        self.assertEqual([], self.native.inputs)

    def test_ignored_product_name_edit_is_detected_and_unnamed_native_effect_is_cleaned(self):
        url = 'http://fixture.test/create/' + 'a' * 32 + '/observer.js'
        self.invoke('create.reference.open', {'scriptUrl': url})
        self.native.ignore_name_apply = True
        with self.assertRaises(RuntimeError):
            self.invoke('create.cube', {'name': PREFIX + 'a' * 32 + '_cube', 'properties': INITIAL})
        self.assertEqual('', self.native.entities[0]['name'])
        keys_before = self.native.inputs.count('normal-keyboard')
        self.invoke('create.reference.close', {'scriptUrl': url})
        self.assertEqual([], self.native.entities)
        self.assertEqual(keys_before, self.native.inputs.count('normal-keyboard'))


if __name__ == '__main__': unittest.main()
