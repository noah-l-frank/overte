"""Phone feature adapter boundary tests; no device or candidate APK execution."""
# SPDX-License-Identifier: Apache-2.0
from functools import partial
from copy import deepcopy
import json
import os
import shlex
import subprocess
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
from self_tests.test_native_feature_observation import Boundary as NativeFeatureBoundary
from adapters.native_feature_observation import NativeFeatureObservation
from self_tests.test_native_web_dom import Boundary as WebDOMBoundary, RUN as WEB_RUN, URL as WEB_URL
from self_tests.test_pending_commit_owner import Boundary as PendingOwnerBoundary, RUN as INPUT_RUN
from self_tests.test_native_navigation_replies import Boundary as NavigationReplyBoundary, RUN as LOOKUP_RUN
from self_tests.test_recorded_preview_evidence import Boundary as PreviewBoundary
from self_tests.test_recorded_preview_history import complete as completed_voice
from adapters.recorded_preview_history import measured_state as measured_audio_state
from adapters.recorded_preview_evidence import RecordedPreviewEvidence
from self_tests.test_native_script_observation import Boundary as ScriptBoundary, effect_source, code_source, RUN as EFFECT_RUN
from adapters.native_script_observation import loaded_relative_modules, running_owned_engine, measured_effect
from adapters.native_script_loads import result as load_result
from self_tests.test_native_script_loads import history as load_history, URL as LOAD_URL, event as load_event
from self_tests.test_native_process_presence import Boundary as PresenceBoundary
from self_tests.test_native_feature_observation import probe_source
from adapters.token_script_file_ui import TokenScriptFilePicker
from adapters.native_script_files import NativeScriptFiles
from adapters.native_script_files import originals
from adapters.script_restart_handoff import ScriptRestartHandoff
from adapters.restart_inputs import RestartInputs
from self_tests.test_native_script_files import Boundary as ScriptFilesBoundary
from script_file_native_boundary import FileNativeBoundary
from audio_native_boundary import AudioNativeBoundary, ControlNativeBoundary
from login_native_boundary import LoginNativeBoundary
from chat_native_boundary import ChatNativeBoundary
from adapters.token_login_ui import TokenLoginUI
from self_tests.test_token_login_ui import RUN as LOGIN_RUN, ORIGIN as LOGIN_ORIGIN, CREDS as LOGIN_CREDS
from adapters.token_graphics_ui import TokenGraphicsUI
from self_tests.test_token_graphics_ui import GraphicsBoundary
from adapters.token_audio_ui import TokenAudioUI
from adapters.android_world_render import AndroidWorldRenderReceipts
from adapters.world_render_storage import receipt_file
from self_tests.test_world_render_evidence import Boundary as WorldBoundary
from self_tests.test_world_render_storage import Boundary as WorldStorageBoundary
from self_tests.test_owned_world_render import LocalAdb
from self_tests.test_native_animation_history import history_source
from adapters.native_animation_history import clip_run
from self_tests.test_native_account_observation import account_source
from self_tests.test_native_chat_observation import Boundary as ChatBoundary, RUN as CHAT_RUN, SELF as CHAT_SELF, PEER as CHAT_PEER
from adapters.native_chat_observation import NativeChatObservation, received_texts
from adapters.native_chat_view import NativeChatView, measured_view
from self_tests.test_native_chat_view import Boundary as ChatViewBoundary
from self_tests.test_native_account_probe import Boundary as AccountProbeBoundary, RUN as ACCOUNT_RUN, TICKET as ACCOUNT_TICKET
from self_tests.test_native_account_origin import Boundary as AccountOriginBoundary, ORIGIN as ACCOUNT_ORIGIN

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
        self.instance = 'f' * 32
        self.clock = 0.0
        self.identity = '31:14'
        self.running = True
        self.lifecycle = dict(backgrounds=0, activations=1, launches=1)
        self.lifecycle_inputs = []
        self.on_launch = None
        self.ignore_app_stop = self.ignore_app_launch = self.lose_stop_ack = self.lose_launch_ack = False
        self.epoch_ms = 10000
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

    def execute(self, session, operation, values):
        assert session == 'native-session'
        if operation == 'mobile: startActivity':
            assert values == {'intent': PACKAGE + '/org.overte.phone.E2eLauncherActivity', 'stop': True, 'wait': False}
        else: assert values == {'appId': PACKAGE}
        if operation == 'mobile: terminateApp':
            self.lifecycle_inputs.append('stop')
            if not self.ignore_app_stop and self.running:
                self.running = False; self.lifecycle['backgrounds'] += 1
            if self.lose_stop_ack: raise RuntimeError('synthetic lost stop SDK receipt')
        elif operation in ('mobile: activateApp', 'mobile: startActivity'):
            self.lifecycle_inputs.append('launch')
            if not self.ignore_app_launch and not self.running:
                assert self.on_launch is not None
                self.on_launch(); self.running = True
                self.lifecycle['activations'] += 1; self.lifecycle['launches'] += 1
            if self.lose_launch_ack: raise RuntimeError('synthetic lost launch SDK receipt')
        else: raise AssertionError('Unexpected synthetic native lifecycle operation')

    def read(self, target, package, path, **kwargs):
        if path != 'files/overte-e2e/normal-feature-observation.json':
            raise AssertionError('Unexpected native file')
        self.sequence += 1
        value = dict(schemaVersion=1, requestId=self.request['commandId'], instance=self.instance, complete=True,
            sampleSequence=self.sequence, sampleEpochMs=self.epoch_ms, scripts=self.rows)
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
            patch.object(self.adapter, 'query_app_state', side_effect=lambda *_: 4 if self.native.running else 1),
            patch.object(self.adapter, 'process_state', side_effect=lambda *_:
                {'running': self.native.running, 'identity': self.native.identity if self.native.running else None}),
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

    def native_feature_boundaries(self):
        source = NativeFeatureBoundary()
        source.mutate = lambda value: value.update(processId=31)
        def send(_client, _session, target, command, process):
            self.assertEqual(PACKAGE, target['appId'])
            self.assertEqual({'running': True, 'identity': '31:14'}, process)
            source.send(command)
        def read(_device, package, path, **kwargs):
            self.assertEqual(PACKAGE, package)
            self.assertEqual('files/overte-e2e/feature-native-observation.json', path)
            self.assertEqual({'attempts': 1}, kwargs)
            return source.original()
        for boundary in (
            patch.object(self.adapter, 'write_android_client_command', side_effect=send),
            patch.object(self.fixture.adb, 'read_debug_app_file', side_effect=read, create=True),
            patch.object(self.fixture.adb, 'epoch_milliseconds', return_value=20000, create=True),
            patch.object(appium, 'NativeFeatureObservation', partial(NativeFeatureObservation,
                monotonic=lambda: source.clock, sleep=source.sleep))):
            boundary.start(); self.addCleanup(boundary.stop)
        return source

    def world_render_boundaries(self):
        source=WorldBoundary();storage=WorldStorageBoundary();storage.raw=source.raw
        storage.mutate=lambda sample:sample.update(instance='a'*32)
        root=self.fixture.root/'files/overte-e2e';root.mkdir(parents=True,mode=0o700)
        local=LocalAdb(self.fixture.root)
        local.read_debug_app_file=lambda _device,_package,path,**_options:(root/path.rsplit('/',1)[1]).read_text()
        def send(_client,_session,target,command,process):
            self.assertEqual(PACKAGE,target['appId']);self.assertEqual('31:14',process['identity'])
            journal=self.adapter.world_render_store(SELECTOR).read()
            self.assertEqual(command.get('requestId',command['commandId']),journal['capture']['commandId'])
            if command['action']=='feature-world-render-observe':
                source.intents.append(command);source.send(command)
            else:
                self.assertIn(command['commandId'],journal['receipts'])
                storage.intents.append(command);storage.send(command)
                name=receipt_file(command['commandId']);(root/name).write_text(storage.files[name])
        def read(_device,package,path,**kwargs):
            self.assertEqual(PACKAGE,package);self.assertEqual({'attempts':1},kwargs)
            if path.endswith('/world-render-observation.json'):return source.original()
            return (root/path.rsplit('/',1)[1]).read_text()
        def receipt_io(adb,device,package,guard):
            self.assertIs(self.fixture.adb,adb);self.assertEqual(PACKAGE,package)
            return AndroidWorldRenderReceipts(local,device,'org.overte.test',guard)
        for boundary in (
            patch.object(self.adapter,'write_android_client_command',side_effect=send),
            patch.object(self.fixture.adb,'read_debug_app_file',side_effect=read,create=True),
            patch.object(self.fixture.adb,'epoch_milliseconds',return_value=20000,create=True),
            patch.object(appium,'AndroidWorldRenderReceipts',side_effect=receipt_io),
            patch.object(appium,'NativeFeatureObservation',partial(NativeFeatureObservation,
                monotonic=lambda:source.clock,sleep=source.sleep))):
            boundary.start();self.addCleanup(boundary.stop)
        return source,local,self.adapter._world_render_capture(SELECTOR)

    def test_phone_world_original_pixels_and_separate_memory_file_cleanup_use_bound_factory(self):
        source,local,capture=self.world_render_boundaries()
        value,raw=capture.read(0);self.assertEqual(source.raw,raw)
        self.assertIsNotNone(self.adapter.world_render_store(SELECTOR).read())
        capture.release();self.assertIsNone(self.adapter.world_render_store(SELECTOR).read())
        self.assertEqual([],list((local.path/'files/overte-e2e').iterdir()))
        self.assertEqual([],self.native.inputs)
        self.assertFalse(any(c.startswith('feature.') for c in self.adapter.advertised_capabilities(self.target)))

    def test_phone_world_ignored_cleanup_retains_original_owner_for_recovery(self):
        source,local,capture=self.world_render_boundaries();capture.read(0);local.ignore_remove=True
        with self.assertRaises(RuntimeError):capture.release()
        self.assertIsNotNone(self.adapter.world_render_store(SELECTOR).read())
        local.ignore_remove=False;capture.release()
        self.assertIsNone(self.adapter.world_render_store(SELECTOR).read())

    def test_phone_world_replaced_candidate_process_cannot_acquire_or_clean_original_owner(self):
        source,local,capture=self.world_render_boundaries();capture.read(0)
        self.native.identity='32:foreign-start';before=len(source.commands)
        with self.assertRaisesRegex(ValueError,'PHONE_NORMAL_SCRIPTS_PROCESS_OR_SESSION_CHANGED'):capture.release()
        self.assertEqual(before,len(source.commands));self.assertIsNotNone(self.adapter.world_render_store(SELECTOR).read())

    def test_phone_atomic_audio_history_keeps_native_terminal_frames_and_refuses_source_downgrade(self):
        source = self.native_feature_boundaries(); original = source.mutate
        def history(value):
            original(value); value['audio']['recordedVoice'] = completed_voice()
        source.mutate = history
        reader = self.adapter._native_feature_observer(SELECTOR)
        first = reader.read(0, require_recorded_history=True)
        actual = measured_audio_state(first)
        self.assertEqual(144000, actual['recordedFrames']); self.assertEqual(0, actual['bufferedFrames'])
        second = reader.read(first['sequence'], require_recorded_history=True)
        self.assertEqual(first['audio']['recordedVoice'], second['audio']['recordedVoice'])
        source.mutate = original
        with self.assertRaises(RuntimeError): reader.read(second['sequence'], require_recorded_history=True)
        self.assertEqual([], self.native.inputs)

    def test_phone_passive_account_source_is_bound_and_refuses_a_narrow_producer(self):
        source=self.native_feature_boundaries();original=source.mutate
        def observed(value):original(value);account_source(value)
        source.mutate=observed;reader=self.adapter._native_feature_observer(SELECTOR)
        first=reader.read(0,require_account=True)
        self.assertEqual(source.sample['account'],first['account'])
        self.assertFalse(first['account']['observation']['loginPending'])
        source.mutate=original
        with self.assertRaises(RuntimeError):reader.read(first['sequence'])
        self.assertEqual([],self.native.inputs)

    def test_phone_animation_history_preserves_original_effect_frames_and_refuses_downgrade(self):
        source=self.native_feature_boundaries();original=source.mutate
        def observed(value):original(value);history_source(value)
        source.mutate=observed;reader=self.adapter._native_feature_observer(SELECTOR)
        first=reader.read(0,require_animation_history=True)
        event,frames=clip_run(first,'file:///actual/bundled/Sit2.fbx',after_event=0,after_epoch=19000)
        self.assertEqual(19000,event['capturedEpochMs']);self.assertEqual(2,len(frames))
        second=reader.read(first['sequence'],require_animation_history=True)
        self.assertEqual(first['animation']['history'],second['animation']['history'])
        source.mutate=original
        with self.assertRaises(RuntimeError):reader.read(second['sequence'])
        self.assertEqual([],self.native.inputs)

    def test_native_feature_packet_is_original_and_bound_to_actual_installed_candidate_and_pid(self):
        source = self.native_feature_boundaries()
        reader = self.adapter._native_feature_observer(SELECTOR)
        value = reader.read(0, require_animation=True)
        self.assertEqual(source.sample, value)
        self.assertEqual(31, value['processId'])
        self.assertEqual('file:///actual/bundled/Sit2.fbx', value['animation']['clip']['url'])
        self.assertEqual([], self.native.inputs)
        self.assertFalse(any(cap.startswith('feature.') for cap in self.adapter.advertised_capabilities(self.target)))

    def preview_boundaries(self, source=None, filename='recorded-preview-observation.json'):
        source = PreviewBoundary() if source is None else source
        def send(_client, _session, target, command, process):
            self.assertEqual(PACKAGE, target['appId'])
            self.assertEqual({'running': True, 'identity': '31:14'}, process)
            source.send(command)
        def read(_device, package, path, **kwargs):
            self.assertEqual(PACKAGE, package)
            self.assertEqual('files/overte-e2e/' + filename, path)
            self.assertEqual({'attempts': 1}, kwargs)
            return json.dumps(source.sample if hasattr(source, 'sample') else source.value)
        def binary(command, *, target, timeout):
            self.assertEqual('exec-out', command[0]); self.assertEqual(5, timeout)
            name = shlex.split(command[1])[-1]
            raw = source.files.get(name)
            return b'OVT_PREVIEW_MISSING_V1\n' if raw is None else b'OVT_PREVIEW_BYTES_V1\n' + raw + b'\nOVT_PREVIEW_BYTES_END_V1\n'
        for boundary in (
            patch.object(self.adapter, 'write_android_client_command', side_effect=send),
            patch.object(self.fixture.adb, 'read_debug_app_file', side_effect=read, create=True),
            patch.object(self.fixture.adb, 'execute_bytes', side_effect=binary, create=True),
            patch.object(self.fixture.adb, 'epoch_milliseconds', return_value=20000, create=True),
            patch.object(appium, 'RecordedPreviewEvidence', partial(RecordedPreviewEvidence,
                monotonic=lambda: source.clock, sleep=source.sleep))):
            boundary.start(); self.addCleanup(boundary.stop)
        return source

    def account_origin_boundaries(self):
        source=AccountOriginBoundary(self.fixture.root/'origin-native-files');native=NativeFeatureBoundary()
        source.mutate=lambda value:value.update(processId=31)
        def observed(value):value.update(processId=31);account_source(value)
        native.mutate=observed
        def send(_client,_session,target,value,process):
            self.assertEqual(PACKAGE,target['appId']);self.assertEqual('31:14',process['identity'])
            if value['action']=='feature-native-observe':native.send(value)
            else:
                self.assertEqual('feature-account-origin',value['action'])
                self.assertEqual(native.sample['instance'],value['instance'])
                self.assertIsNotNone(self.adapter.account_origin_store(SELECTOR).read());source.send(value)
        def read(_device,package,path,**kwargs):
            self.assertEqual(PACKAGE,package);self.assertEqual({'attempts':1},kwargs)
            if path.endswith('/feature-native-observation.json'):return native.original()
            self.assertEqual('files/overte-e2e/feature-account-origin-result.json',path);return source.read()
        for boundary in (patch.object(self.adapter,'write_android_client_command',side_effect=send),
            patch.object(self.fixture.adb,'read_debug_app_file',side_effect=read,create=True),
            patch.object(self.fixture.adb,'epoch_milliseconds',return_value=20000,create=True),
            patch.object(appium,'NativeFeatureObservation',partial(NativeFeatureObservation,
                monotonic=lambda:source.clock,sleep=source.sleep))):
            boundary.start();self.addCleanup(boundary.stop)
        return source,native,self.adapter._account_origin(SELECTOR)

    def test_phone_account_origin_uses_actual_native_context_and_original_file_readback(self):
        source,native,origin=self.account_origin_boundaries()
        self.assertEqual(ACCOUNT_ORIGIN,origin.stage(ACCOUNT_RUN,ACCOUNT_ORIGIN))
        self.assertEqual(native.sample['instance'],self.adapter.account_origin_store(SELECTOR).read()['instance'])
        self.assertTrue(source.path.exists());origin.release()
        self.assertFalse(source.path.exists());self.assertFalse(source.manifest.exists())
        self.assertIsNone(self.adapter.account_origin_store(SELECTOR).read());self.assertEqual([],self.native.inputs)

    def test_phone_account_origin_ack_without_originals_keeps_private_owner(self):
        source,_native,origin=self.account_origin_boundaries();source.fault='ack-only'
        with self.assertRaises(RuntimeError):origin.stage(ACCOUNT_RUN,ACCOUNT_ORIGIN)
        self.assertIsNotNone(self.adapter.account_origin_store(SELECTOR).read())
        origin.release();self.assertIsNone(self.adapter.account_origin_store(SELECTOR).read())

    def test_phone_account_origin_different_native_instance_cannot_adopt_existing_scope(self):
        source,native,origin=self.account_origin_boundaries();origin.stage(ACCOUNT_RUN,ACCOUNT_ORIGIN)
        original=native.mutate
        def changed(value):original(value);value['instance']='f'*32
        native.mutate=changed;before=len(source.commands)
        with self.assertRaises(RuntimeError):self.adapter._account_origin(SELECTOR).release()
        self.assertEqual(before,len(source.commands));self.assertIsNotNone(self.adapter.account_origin_store(SELECTOR).read())

    def test_phone_adapter_cleanup_removes_owned_origin_before_base_teardown(self):
        source,_native,origin=self.account_origin_boundaries();origin.stage(ACCOUNT_RUN,ACCOUNT_ORIGIN)
        with patch.object(AppiumAdapter,'cleanup',return_value={'cleaned':True}) as base:
            self.assertEqual({'cleaned':True},self.adapter.cleanup(SELECTOR));base.assert_called_once()
        self.assertFalse(source.path.exists());self.assertIsNone(self.adapter.account_origin_store(SELECTOR).read())

    def test_phone_adapter_cleanup_retains_origin_when_file_absence_was_not_observed(self):
        source,_native,origin=self.account_origin_boundaries();origin.stage(ACCOUNT_RUN,ACCOUNT_ORIGIN);source.fault='keep-files'
        with patch.object(AppiumAdapter,'cleanup',return_value={'cleaned':True}) as base:
            with self.assertRaisesRegex(ValueError,'PHONE_ACCOUNT_ORIGIN_CLEANUP_INCOMPLETE'):self.adapter.cleanup(SELECTOR)
            base.assert_called_once()
        self.assertTrue(source.path.exists());self.assertIsNotNone(self.adapter.account_origin_store(SELECTOR).read())

    def navigation_reply_boundaries(self):
        source=self.preview_boundaries(NavigationReplyBoundary(),'feature-navigation-replies.json')
        source.edit=lambda value:value.update(processId=31)
        def read(_device,package,path,**options):
            self.assertEqual(PACKAGE,package);self.assertEqual('files/overte-e2e/feature-navigation-replies.json',path)
            self.assertEqual({'attempts':1},options);return source.original()
        for boundary in (patch.object(self.fixture.adb,'read_debug_app_file',side_effect=read),
            patch.object(self.fixture.adb,'epoch_milliseconds',side_effect=lambda _device:source.epoch()),
            patch.object(appium,'NativeFeatureObservation',partial(NativeFeatureObservation,
                monotonic=lambda:source.clock,sleep=source.sleep))):
            boundary.start();self.addCleanup(boundary.stop)
        return source,self.adapter._navigation_replies(SELECTOR)

    def test_phone_navigation_reply_joins_only_original_current_callback_and_fixture_id(self):
        source,reader=self.navigation_reply_boundaries();self.assertEqual([],reader.read(LOOKUP_RUN)['events'])
        source.error();joined=source.join(reader)
        self.assertEqual(source.events[0],joined['native']);self.assertEqual(source.provider()['responses'][0],joined['http'])
        self.assertFalse(any(c.startswith('feature.') for c in self.adapter.advertised_capabilities(self.target)))

    def test_phone_navigation_reply_ignored_hook_foreign_pid_and_retired_scope_fail(self):
        source,reader=self.navigation_reply_boundaries();source.ignored=True
        with self.assertRaises(RuntimeError):reader.read(LOOKUP_RUN)
        self.assertEqual(1,len(source.commands));source.ignored=False;source.error();source.generation+=1
        with self.assertRaises(RuntimeError):source.join(reader,barrier=source.epoch())
        source.edit=lambda value:value.update(processId=32)
        with self.assertRaises(RuntimeError):reader.read(LOOKUP_RUN)

    def test_phone_navigation_reply_changed_installation_blocks_before_private_read_command(self):
        source,reader=self.navigation_reply_boundaries();reader.read(LOOKUP_RUN);before=len(source.commands)
        self.fixture.adb.digest='f'*64
        with self.assertRaises(RuntimeError):reader.read(LOOKUP_RUN)
        self.assertEqual(before,len(source.commands))

    def pending_owner_boundaries(self, intent=True):
        source=self.preview_boundaries(PendingOwnerBoundary(),'feature-pending-commit-owner.json')
        def edit(value):
            value['processId']=31
            if value['commit']:value['commit']['observation']['processId']=31
        source.edit=edit
        def read(_device,package,path,**options):
            self.assertEqual(PACKAGE,package);self.assertEqual('files/overte-e2e/feature-pending-commit-owner.json',path)
            self.assertEqual({'attempts':1},options);return source.original()
        for boundary in (patch.object(self.fixture.adb,'read_debug_app_file',side_effect=read),
            patch.object(self.fixture.adb,'epoch_milliseconds',side_effect=lambda _device:source.epoch()),
            patch.object(appium,'NativeFeatureObservation',partial(NativeFeatureObservation,
                monotonic=lambda:source.clock,sleep=source.sleep))):
            boundary.start();self.addCleanup(boundary.stop)
        return source,self.adapter._pending_owner(SELECTOR,source.intents.append if intent else None)

    def test_phone_pending_owner_uses_bound_private_source_and_original_retirement(self):
        source,owner=self.pending_owner_boundaries()
        owner.focus(INPUT_RUN);owner.type_owned(INPUT_RUN);held=owner.hold(INPUT_RUN)
        source.replace_context();owner.attempt_retired(INPUT_RUN,held['commit']['observation']['eventId'])
        result=owner.release_owned(INPUT_RUN,held['commit']['observation']['eventId'])
        self.assertEqual([],result['resources']['pendingRuns']);self.assertEqual(31,result['processId'])
        self.assertEqual(source.intents,[c for c in source.commands if c['operation']!='observe'])
        self.assertFalse(any(c.startswith('feature.') for c in self.adapter.advertised_capabilities(self.target)))

    def test_phone_pending_owner_ignored_focus_and_incomplete_cleanup_fail_without_replay(self):
        source,owner=self.pending_owner_boundaries();source.fault='focus-ignored'
        with self.assertRaises(RuntimeError):owner.focus(INPUT_RUN)
        self.assertEqual(1,sum(c['operation']=='focus' for c in source.commands))
        source.fault='';owner.focus(INPUT_RUN);owner.type_owned(INPUT_RUN);held=owner.hold(INPUT_RUN)
        source.fault='release-ignored'
        with self.assertRaises(RuntimeError):owner.release_owned(INPUT_RUN,held['commit']['observation']['eventId'])

    def test_phone_pending_owner_changed_candidate_and_foreign_process_stop_new_effects(self):
        source,owner=self.pending_owner_boundaries();owner.read(INPUT_RUN);before=len(source.commands)
        original_digest=self.fixture.adb.digest;self.fixture.adb.digest='f'*64
        with self.assertRaises(RuntimeError):owner.read(INPUT_RUN)
        self.assertEqual(before,len(source.commands))
        self.fixture.adb.digest=original_digest
        original=source.edit
        def foreign(value):original(value);value['processId']=32
        source.edit=foreign
        with self.assertRaises(RuntimeError):owner.read(INPUT_RUN)

    def test_phone_pending_owner_without_durable_intent_cannot_mutate(self):
        source,owner=self.pending_owner_boundaries(intent=False);owner.read(INPUT_RUN)
        with self.assertRaises(RuntimeError):owner.focus(INPUT_RUN)
        self.assertFalse(any(c['operation']!='observe' for c in source.commands))

    def web_dom_boundaries(self):
        source=self.preview_boundaries(WebDOMBoundary(),'feature-web-dom-observation.json')
        source.mutate=lambda value:value.update(processId=31)
        def read(_device,package,path,**options):
            self.assertEqual(PACKAGE,package);self.assertEqual('files/overte-e2e/feature-web-dom-observation.json',path)
            self.assertEqual({'attempts':1},options);return source.original()
        for boundary in (patch.object(self.fixture.adb,'read_debug_app_file',side_effect=read,create=True),
            patch.object(appium,'NativeFeatureObservation',partial(NativeFeatureObservation,
                monotonic=lambda:source.clock,sleep=source.sleep))):
            boundary.start();self.addCleanup(boundary.stop)
        return source,self.adapter._web_dom(SELECTOR)

    def test_phone_native_web_dom_uses_actual_private_file_and_separate_clock_without_full_capability(self):
        source,reader=self.web_dom_boundaries();value=reader.read(WEB_RUN,'world',WEB_URL)
        self.assertEqual(31,value['processId']);self.assertEqual('Grüße 🌍',value['source']['dom']['editor']['text'])
        self.assertEqual(0,value['source']['nativeView']['httpErrorStatus']);self.assertEqual([],self.native.inputs)
        self.assertFalse(any(c.startswith('feature.') for c in self.adapter.advertised_capabilities(self.target)))

    def test_phone_native_web_dom_ignored_or_foreign_pid_cannot_become_empty_success(self):
        source,reader=self.web_dom_boundaries();source.ignored=True
        with self.assertRaises(RuntimeError):reader.read(WEB_RUN,'world',WEB_URL)
        self.assertEqual(1,len(source.commands));self.assertLessEqual(source.clock,5)
        source.ignored=False;source.mutate=lambda value:value.update(processId=32)
        with self.assertRaises(RuntimeError):reader.read(WEB_RUN,'world',WEB_URL)

    def test_phone_native_web_dom_changed_candidate_or_process_blocks_new_request(self):
        source,reader=self.web_dom_boundaries();reader.read(WEB_RUN,'world',WEB_URL);before=len(source.commands)
        self.fixture.adb.digest='f'*64
        with self.assertRaises(RuntimeError):reader.read(WEB_RUN,'world',WEB_URL)
        self.assertEqual(before,len(source.commands))

    def chat_view_boundaries(self):
        source=self.preview_boundaries(ChatViewBoundary(),'feature-chat-view-observation.json')
        source.mutate=lambda value:value.update(processId=31)
        boundary=patch.object(appium,'NativeChatView',partial(NativeChatView,
            monotonic=lambda:source.clock,sleep=source.sleep))
        boundary.start();self.addCleanup(boundary.stop)
        return source,self.adapter._chat_view(SELECTOR)

    def test_phone_chat_view_binds_original_ui_storage_file_without_delivery_claim(self):
        source,reader=self.chat_view_boundaries();value=reader.read(CHAT_RUN)
        self.assertEqual(31,value['processId']);self.assertEqual('domain',measured_view(value)['channel'])
        self.assertEqual(2,len(value['source']['storage']['events']));self.assertEqual([],self.native.inputs)
        self.assertFalse(any(c.startswith('feature.') for c in self.adapter.advertised_capabilities(self.target)))

    def test_phone_chat_view_ignored_input_or_stale_native_source_cannot_become_empty_success(self):
        source,reader=self.chat_view_boundaries();source.ignored=True
        with self.assertRaises(RuntimeError):reader.read(CHAT_RUN)
        self.assertEqual(1,len(source.commands));self.assertLessEqual(source.clock,5)
        source.ignored=False;source.mutate=lambda value:value.update(processId=32)
        with self.assertRaises(RuntimeError):reader.read(CHAT_RUN)

    def test_phone_chat_view_changed_apk_or_process_blocks_dispatch(self):
        source,reader=self.chat_view_boundaries();reader.read(CHAT_RUN);before=len(source.commands)
        self.fixture.adb.digest='f'*64
        with self.assertRaisesRegex(RuntimeError,'Native Chat view observation failed'):reader.read(CHAT_RUN)
        self.assertEqual(before,len(source.commands))

    def chat_capture_boundaries(self):
        source=self.preview_boundaries(ChatBoundary(),'feature-chat-observation.json')
        source.mutate=lambda value:value.update(processId=31)
        source.store=self.adapter.chat_capture_store(SELECTOR)
        boundary=patch.object(appium,'NativeChatObservation',partial(NativeChatObservation,
            monotonic=lambda:source.clock,sleep=source.sleep))
        boundary.start();self.addCleanup(boundary.stop)
        return source,self.adapter._chat_capture(SELECTOR,CHAT_RUN)

    def test_phone_chat_factory_reads_original_reception_and_retires_actual_scope(self):
        source,capture=self.chat_capture_boundaries();capture.observe();source.event();value=capture.observe()
        self.assertEqual(31,value['processId']);self.assertEqual(1,len(received_texts(value,
            sender_sha256=CHAT_PEER,receiver_sha256=CHAT_SELF,channel='domain')))
        capture.retire();self.assertIsNone(self.adapter.chat_capture_store(SELECTOR).read())
        self.assertEqual([],self.native.inputs)
        self.assertFalse(any(c.startswith('feature.') for c in self.adapter.advertised_capabilities(self.target)))

    def test_phone_chat_factory_does_not_adopt_foreign_source_or_local_echo(self):
        source,capture=self.chat_capture_boundaries();capture.observe();source.event(local=True)
        value=capture.observe();self.assertEqual([],received_texts(value,sender_sha256=CHAT_PEER,receiver_sha256=CHAT_SELF,channel='domain'))
        source.mutate=lambda value:value.update(processId=31,instance='f'*32)
        with self.assertRaises(RuntimeError):self.adapter._chat_capture(SELECTOR,CHAT_RUN).retire()
        self.assertIsNotNone(self.adapter.chat_capture_store(SELECTOR).read())
        self.assertFalse(any(c['operation']=='retire' for c in source.commands))

    def test_phone_chat_changed_candidate_blocks_request_and_keeps_journal(self):
        source,capture=self.chat_capture_boundaries();capture.observe();before=len(source.commands)
        self.fixture.adb.digest='f'*64
        with self.assertRaisesRegex(ValueError,'PHONE_INSTALLED_BYTES_MISMATCH'):capture.observe()
        self.assertEqual(before,len(source.commands));self.assertIsNotNone(self.adapter.chat_capture_store(SELECTOR).read())

    def test_phone_chat_cleanup_drains_before_original_base_teardown(self):
        source,capture=self.chat_capture_boundaries();capture.observe();source.event()
        def base(*_):
            self.assertFalse(source.present);self.assertEqual(2,source.inspect_after_retire)
            return {'cleaned':True}
        with patch.object(AppiumAdapter,'cleanup',side_effect=base) as original:
            self.assertEqual({'cleaned':True},self.adapter.cleanup(SELECTOR));original.assert_called_once()
        self.assertIsNone(self.adapter.chat_capture_store(SELECTOR).read())

    def test_phone_chat_failed_cleanup_reaches_base_and_refuses_green(self):
        source,capture=self.chat_capture_boundaries();capture.observe();source.ignore_retire=True
        with patch.object(AppiumAdapter,'cleanup',return_value={'cleaned':True}) as original:
            with self.assertRaisesRegex(ValueError,'PHONE_CHAT_CAPTURE_CLEANUP_INCOMPLETE'):self.adapter.cleanup(SELECTOR)
            original.assert_called_once()
        self.assertTrue(source.present);self.assertIsNotNone(self.adapter.chat_capture_store(SELECTOR).read())

    def account_probe_boundaries(self):
        source=self.preview_boundaries(AccountProbeBoundary(),'feature-account-probe.json')
        source.mutate=lambda value:value.update(processId=31)
        boundary=patch.object(appium,'NativeFeatureObservation',partial(NativeFeatureObservation,
            monotonic=lambda:source.clock,sleep=source.sleep))
        boundary.start();self.addCleanup(boundary.stop)
        return source,self.adapter._account_probe(SELECTOR)

    def test_phone_protected_probe_uses_actual_bound_transport_and_private_intent_cleanup(self):
        source,probe=self.account_probe_boundaries();original=source.send
        def inspect_intent(command):
            self.assertEqual(command['requestId'],self.adapter.account_probe_store(SELECTOR).read()['probe']['commandId'])
            original(command)
        source.send=inspect_intent
        value=probe.acquire(ACCOUNT_RUN,ACCOUNT_TICKET)
        self.assertEqual(401,value['source']['httpStatus']);self.assertEqual(31,value['processId'])
        probe.release();self.assertIsNone(self.adapter.account_probe_store(SELECTOR).read())
        self.assertEqual([],self.native.inputs)
        self.assertFalse(any(c.startswith('feature.') for c in self.adapter.advertised_capabilities(self.target)))

    def test_phone_adapter_cleanup_drains_owned_probe_before_base_teardown(self):
        source,probe=self.account_probe_boundaries();probe.acquire(ACCOUNT_RUN,ACCOUNT_TICKET)
        with patch.object(AppiumAdapter,'cleanup',return_value={'cleaned':True}) as base:
            self.assertEqual({'cleaned':True},self.adapter.cleanup(SELECTOR));base.assert_called_once()
        self.assertIsNone(self.adapter.account_probe_store(SELECTOR).read())

    def test_phone_adapter_cleanup_runs_base_but_refuses_green_for_undrained_probe(self):
        source,probe=self.account_probe_boundaries();probe.acquire(ACCOUNT_RUN,ACCOUNT_TICKET);source.pending=True
        with patch.object(AppiumAdapter,'cleanup',return_value={'cleaned':True}) as base:
            with self.assertRaisesRegex(ValueError,'PHONE_ACCOUNT_PROBE_CLEANUP_INCOMPLETE'):self.adapter.cleanup(SELECTOR)
            base.assert_called_once()
        self.assertIsNotNone(self.adapter.account_probe_store(SELECTOR).read())

    def test_phone_protected_probe_incomplete_drain_keeps_private_owner(self):
        source,probe=self.account_probe_boundaries();probe.acquire(ACCOUNT_RUN,ACCOUNT_TICKET);source.pending=True
        with self.assertRaises(RuntimeError):probe.release()
        self.assertIsNotNone(self.adapter.account_probe_store(SELECTOR).read())
        source.pending=False;probe.release();self.assertIsNone(self.adapter.account_probe_store(SELECTOR).read())

    def test_phone_protected_probe_replaced_candidate_cannot_clear_original_owner(self):
        source,probe=self.account_probe_boundaries();probe.acquire(ACCOUNT_RUN,ACCOUNT_TICKET)
        self.fixture.adb.digest='f'*64;before=len(source.commands)
        with self.assertRaises(ValueError):probe.release()
        self.assertEqual(before,len(source.commands));self.assertIsNotNone(self.adapter.account_probe_store(SELECTOR).read())

    def script_file_storage(self):
        source = self.preview_boundaries(ScriptFilesBoundary(self.fixture.root), 'feature-script-files.json')
        boundary = patch.object(appium, 'NativeScriptFiles', partial(NativeScriptFiles,
            monotonic=lambda: source.clock, sleep=source.sleep))
        boundary.start(); self.addCleanup(boundary.stop)
        return source, self.adapter._script_files(SELECTOR)

    def process_presence_boundaries(self):
        source = self.preview_boundaries(PresenceBoundary(), 'feature-process-presence.json')
        boundary = patch.object(appium, 'NativeFeatureObservation', partial(NativeFeatureObservation,
            monotonic=lambda: source.clock, sleep=source.sleep))
        boundary.start(); self.addCleanup(boundary.stop)
        return source, self.adapter._process_presence(SELECTOR)

    def test_phone_process_presence_keeps_original_kernel_states_without_scripts_input(self):
        source, reader = self.process_presence_boundaries()
        self.assertEqual('present', reader.read(29)['presence'])
        source.presence = 'unknown'
        with self.assertRaises(RuntimeError): reader.require_absent(29)
        source.presence = 'absent'; actual = reader.require_absent(29)
        self.assertEqual(source.value, actual); self.assertEqual(3, actual['nativeError'])
        self.assertEqual([], self.native.inputs)

    def test_phone_process_presence_ignored_or_foreign_source_cannot_prove_exit(self):
        source, reader = self.process_presence_boundaries(); source.ignored = True
        with self.assertRaises(RuntimeError): reader.require_absent(29)
        self.assertEqual(1, len(source.commands)); self.assertIsNone(reader.last)
        source.ignored = False; source.presence = 'absent'; source.edit = lambda value: value.update(processId=32)
        with self.assertRaises(RuntimeError): reader.require_absent(29)
        self.assertIsNone(reader.last)

    def test_phone_process_presence_changed_candidate_or_same_pid_new_birth_blocks_another_query(self):
        source, reader = self.process_presence_boundaries(); reader.read(29)
        before = len(source.commands); original = self.fixture.adb.digest; self.fixture.adb.digest = 'f' * 64
        with self.assertRaises(RuntimeError): reader.read(29)
        self.assertEqual(before, len(source.commands))
        self.fixture.adb.digest = original; self.native.identity = '31:15'
        with self.assertRaises(RuntimeError): reader.read(29)
        self.assertEqual(before, len(source.commands))

    def file_manager_boundaries(self):
        storage = ScriptFilesBoundary(self.fixture.root)
        file_ui = FileNativeBoundary(storage.root)
        self.native.epoch_ms = 20000
        def send(client, session, target, command, process):
            self.assertEqual(PACKAGE, target['appId']); self.assertEqual(self.native.identity, process['identity'])
            if command['action'] == 'feature-script-files': storage.send(command)
            elif command['action'] == 'phone-script-file-ui': file_ui.send(command)
            else: self.native.command(client, session, target, command, process)
        def read(device, package, path, **options):
            self.assertEqual(PACKAGE, package); self.assertEqual({'attempts': 1}, options)
            if path == 'files/overte-e2e/feature-script-files.json': return storage.read()
            if path == 'files/overte-e2e/phone-script-file-ui.json': return json.dumps(file_ui.value)
            return self.native.read(device, package, path, **options)
        original = file_ui.ui.activate
        def input(identifier, **kwargs):
            if identifier == 'scripts.from-file':
                self.assertTrue(self.adapter.script_store(SELECTOR).read()['pickerOwned'])
                file_ui.ui.chosen = []
            if identifier == 'script-file.confirm':
                self.assertTrue(self.adapter.script_store(SELECTOR).read()['loadAttempted'])
            original(identifier, **kwargs)
            if identifier == 'script-file.confirm' and file_ui.ui.accepted:
                actual = file_ui.ui.accepted[-1]; self.native.rows.append(dict(url=actual, path=actual))
        file_ui.ui.activate = input
        for boundary in (
            patch.object(self.adapter, 'write_android_client_command', side_effect=send),
            patch.object(self.fixture.adb, 'read_debug_app_file', side_effect=read),
            patch.object(self.fixture.adb, 'epoch_milliseconds', return_value=20000),
            patch.object(appium, 'NativeScriptFiles', partial(NativeScriptFiles,
                monotonic=lambda: storage.clock, sleep=storage.sleep)),
            patch.object(appium, 'PhoneScriptFileIO', partial(appium.PhoneScriptFileIO,
                monotonic=lambda: file_ui.ui.clock, sleep=file_ui.ui.sleep)),
            patch.object(appium, 'TokenScriptFilePicker', partial(TokenScriptFilePicker,
                monotonic=lambda: file_ui.ui.clock, sleep=file_ui.ui.sleep))):
            boundary.start(); self.addCleanup(boundary.stop)
        files = self.adapter._script_files(SELECTOR); files.stage('a' * 32)
        return storage, file_ui, files, self.adapter._script_file_manager(SELECTOR)

    def test_phone_file_manager_journals_normal_selection_and_separate_file_cleanup(self):
        storage, file_ui, files, manager = self.file_manager_boundaries()
        manager.open(); manager.file_picker_open(); manager.file_picker_cancel()
        manager = self.adapter._script_file_manager(SELECTOR)
        manager.file_picker_open(); manager.file_picker_choose('script-bundle/main.js')
        actual = file_ui.ui.accepted[-1]
        self.assertEqual((storage.root / 'script-bundle/main.js').as_uri(), actual)
        manager.stop_source(actual); manager.close()
        self.assertIsNone(self.adapter.script_store(SELECTOR).read())
        self.assertTrue(storage.root.exists()); files.release(); self.assertFalse(storage.root.exists())
        self.assertFalse(any(cap.startswith('feature.') for cap in self.adapter.advertised_capabilities(self.target)))

    def test_phone_file_manager_replaced_candidate_blocks_input_and_preserves_original_intents(self):
        _storage, file_ui, files, manager = self.file_manager_boundaries()
        manager.open(); manager.file_picker_open()
        before = len(file_ui.commands); self.fixture.adb.digest = 'f' * 64
        with self.assertRaises(RuntimeError): manager.file_picker_choose('script.js')
        self.assertEqual(before, len(file_ui.commands))
        self.assertTrue(self.adapter.script_store(SELECTOR).read()['pickerOwned'])
        self.assertIsNotNone(files.store.read())

    def restart_boundaries(self, *, staged_restart=True):
        if not staged_restart:
            # Exercise the actual shared Appium capability/startActivity path,
            # with its exact controlled-target declaration rather than a flag.
            self.target.update(scene={'kind': 'android-debug-e2e'}, clientControl={
                'kind': 'android-run-as-command', 'relativePath': self.adapter.ANDROID_CLIENT_COMMAND})
            self.target['capabilities']['appium:autoLaunch'] = False
            self.adapter.read_session(SELECTOR)['targetFingerprint'] = self.adapter.snapshot_fingerprint(self.target)
        storage, file_ui, files, manager = self.file_manager_boundaries()
        manager.open(); manager.file_picker_open(); manager.file_picker_choose('script-bundle/main.js')
        source = ScriptBoundary(); source.engine['url'] = storage.root.as_uri() + '/script-bundle/main.js'
        source.engine['required']['modules'][0]['url'] = storage.root.as_uri() + '/script-bundle/companion.js'
        presence = PresenceBoundary(pid=32, epoch_ms=lambda: self.native.epoch_ms); presence.presence = 'absent'
        lifecycle = NativeFeatureBoundary()
        state = {'restarted': False, 'replay': False}
        def mutate(packet):
            packet.update(processId=int(self.native.identity.split(':')[0]),
                instance=('a' if state['restarted'] else 'd') * 32,
                requestedEpochMs=self.native.epoch_ms, capturedEpochMs=self.native.epoch_ms)
            code_source(packet, originals('a' * 32)['script-bundle/main.js'].decode())
            effect_source(packet)
            row = packet['source']['effects']['entities'][0]
            row['name'] = 'e2e-' + 'a' * 32 + '-script'; row['userData'] = json.dumps(dict(runId='a' * 32, ticks=2))
            packet['source'].update(loadSourceVersion=1,
                loads=dict(complete=True, instance='7' * 32, sequence=0, events=[]))
            if state['restarted'] and not state['replay']:
                packet['source']['engines'] = []
                packet['source']['effects'].update(scannedEntities=0, entities=[], absentIds=[])
        source.mutate = mutate
        def native_lifecycle(packet):
            packet.update(processId=int(self.native.identity.split(':')[0]),
                instance=('a' if state['restarted'] else 'd') * 32,
                requestedEpochMs=self.native.epoch_ms, capturedEpochMs=self.native.epoch_ms,
                lifecycle=dict(self.native.lifecycle))
            packet['animationFence']['requestedEpochMs'] = packet['requestedEpochMs']
        lifecycle.mutate = native_lifecycle
        def storage_mutate(packet):
            packet.update(processId=int(self.native.identity.split(':')[0]),
                instance=('a' if state['restarted'] else 'd') * 32,
                requestedEpochMs=self.native.epoch_ms, capturedEpochMs=self.native.epoch_ms)
        storage.mutate = storage_mutate
        def file_mutate(packet):
            packet['processId'] = int(self.native.identity.split(':')[0])
            if packet['action'] == 'observe': packet['capturedEpochMs'] = self.native.epoch_ms
        file_ui.mutate = file_mutate
        original_send = self.adapter.write_android_client_command.side_effect
        original_read = self.fixture.adb.read_debug_app_file.side_effect
        def send(client, session, target, command, process):
            if command['action'] == 'feature-script-observe': source.send(command)
            elif command['action'] == 'feature-process-presence': presence.send(command)
            elif command['action'] == 'feature-native-observe': lifecycle.send(command)
            else: return original_send(client, session, target, command, process)
        def read(device, package, path, **options):
            if path.endswith('/feature-script-observation.json'): return source.original()
            if path.endswith('/feature-process-presence.json'): return presence.original()
            if path.endswith('/feature-native-observation.json'): return lifecycle.original()
            return original_read(device, package, path, **options)
        def sleep(seconds):
            self.native.sleep(seconds); self.native.epoch_ms += round(seconds * 1000)
        for boundary in (patch.object(self.adapter, 'write_android_client_command', side_effect=send),
            patch.object(self.fixture.adb, 'read_debug_app_file', side_effect=read),
            patch.object(self.fixture.adb, 'epoch_milliseconds', side_effect=lambda *_: self.native.epoch_ms),
            patch.object(appium, 'ScriptRestartHandoff', partial(ScriptRestartHandoff,
                monotonic=lambda: self.native.clock, sleep=sleep)),
            patch.object(appium, 'RestartInputs', partial(RestartInputs, monotonic=lambda: self.native.clock))):
            boundary.start(); self.addCleanup(boundary.stop)
        def transition():
            state['restarted'] = True; self.native.identity = '32:15'
            self.native.screen = None; self.native.rows = []; self.native.instance = '9' * 32
            file_ui.ui.opened = False
        self.native.on_launch = transition
        if staged_restart:
            self.adapter._script_restart_prepare(SELECTOR)
            # Only the synthetic OS boundary changes; use the actual adapter
            # source/ownership/result logic on both sides.
            transition()
        return storage, file_ui, source, presence, state

    def test_phone_restart_handoff_uses_new_original_process_and_preserved_file_bytes_without_product_input(self):
        storage, file_ui, source, presence, _state = self.restart_boundaries()
        before = (list(self.native.inputs), list(file_ui.input_requests))
        result = self.adapter._script_restart_adopt(SELECTOR)
        self.assertEqual('ESRCH', result['exit']['errorSymbol'])
        self.assertEqual([], result['execution']['source']['engines'])
        self.assertEqual(before, (self.native.inputs, file_ui.input_requests))
        self.assertEqual('32:15', self.adapter.script_files_store(SELECTOR).read()['binding']['processIdentity'])
        self.assertFalse(self.adapter.script_store(SELECTOR).read()['loadAttempted'])
        self.assertIsNone(self.adapter.script_restart_store(SELECTOR).read())
        self.assertEqual(1, sum(row['operation'] == 'stage' for row in storage.commands))
        self.assertGreaterEqual(len(source.commands), 3); self.assertTrue(presence.commands)

    def test_phone_restart_handoff_retained_execution_or_unavailable_exit_retains_both_owners(self):
        _storage, _file_ui, source, presence, state = self.restart_boundaries()
        presence.presence = 'unknown'
        with self.assertRaises(RuntimeError): self.adapter._script_restart_adopt(SELECTOR)
        before = len(source.commands); presence.presence = 'absent'; state['replay'] = True
        with self.assertRaises(RuntimeError): self.adapter._script_restart_adopt(SELECTOR)
        self.assertGreater(len(source.commands), before)
        self.assertEqual('31:14', self.adapter.script_files_store(SELECTOR).read()['binding']['processIdentity'])
        self.assertTrue(self.adapter.script_store(SELECTOR).read()['loadAttempted'])
        self.assertIsNotNone(self.adapter.script_restart_store(SELECTOR).read())

    def test_phone_restart_handoff_candidate_replacement_blocks_adoption_before_native_query(self):
        _storage, _file_ui, source, presence, _state = self.restart_boundaries()
        before = len(source.commands); self.fixture.adb.digest = 'f' * 64
        with self.assertRaisesRegex(ValueError, 'PHONE_INSTALLED_BYTES_MISMATCH'):
            self.adapter._script_restart_adopt(SELECTOR)
        self.assertEqual(before, len(source.commands)); self.assertEqual([], presence.commands)
        self.assertIsNotNone(self.adapter.script_restart_store(SELECTOR).read())

    def test_phone_unresolved_restart_journal_blocks_green_cleanup_even_without_other_host_intents(self):
        self.adapter.script_restart_store(SELECTOR).write({'unresolved': True}, None)
        with patch.object(AppiumAdapter, 'cleanup', return_value={'cleaned': True}) as teardown:
            with self.assertRaisesRegex(ValueError, 'PHONE_SCRIPT_RESTART_CLEANUP_INCOMPLETE'):
                self.adapter.cleanup(SELECTOR)
            teardown.assert_called_once()
        self.assertIsNotNone(self.adapter.script_restart_store(SELECTOR).read())

    def test_phone_normal_restart_composes_sdk_inputs_original_lifecycle_and_file_handoff_once(self):
        storage, _file_ui, _source, _presence, _state = self.restart_boundaries(staged_restart=False)
        result = self.adapter._script_restart(SELECTOR)
        self.assertEqual(['stop', 'launch'], self.native.lifecycle_inputs)
        self.assertEqual(self.native.lifecycle, result['native']['lifecycle'])
        self.assertEqual(2, result['native']['lifecycle']['launches'])
        self.assertIsNone(self.adapter.script_restart_store(SELECTOR).read())
        self.assertEqual('observed', self.adapter.script_restart_inputs_store(SELECTOR).read()['phase'])
        # Retrying a lost operation response reobserves the transferred owner;
        # neither lifecycle input nor original fixture staging is repeated.
        self.adapter._script_restart(SELECTOR)
        self.assertEqual(['stop', 'launch'], self.native.lifecycle_inputs)
        self.assertEqual(1, sum(command['operation'] == 'stage' for command in storage.commands))

    def test_phone_restart_ignored_stop_prevents_launch_and_never_replays_stop(self):
        self.restart_boundaries(staged_restart=False); self.native.ignore_app_stop = True
        for _ in range(2):
            with self.assertRaises(RuntimeError): self.adapter._script_restart(SELECTOR)
        self.assertEqual(['stop'], self.native.lifecycle_inputs)
        self.assertEqual('stop-issued', self.adapter.script_restart_inputs_store(SELECTOR).read()['phase'])

    def test_phone_restart_lost_sdk_acks_require_original_new_process_and_native_counters(self):
        self.restart_boundaries(staged_restart=False); self.native.lose_stop_ack = self.native.lose_launch_ack = True
        with self.assertRaises(RuntimeError): self.adapter._script_restart(SELECTOR)
        self.assertEqual(['stop'], self.native.lifecycle_inputs)
        with self.assertRaises(RuntimeError): self.adapter._script_restart(SELECTOR)
        self.assertEqual(['stop', 'launch'], self.native.lifecycle_inputs)
        result = self.adapter._script_restart(SELECTOR)
        self.assertEqual('ESRCH', result['handoff']['exit']['errorSymbol'])
        self.assertEqual(['stop', 'launch'], self.native.lifecycle_inputs)

    def test_phone_restart_ignored_launch_is_not_retried_and_retains_original_file_and_input_ownership(self):
        self.restart_boundaries(staged_restart=False); self.native.ignore_app_launch = True
        for _ in range(2):
            with self.assertRaises(ValueError): self.adapter._script_restart(SELECTOR)
        self.assertEqual(['stop', 'launch'], self.native.lifecycle_inputs)
        self.assertEqual('launch-issued', self.adapter.script_restart_inputs_store(SELECTOR).read()['phase'])
        self.assertEqual('31:14', self.adapter.script_files_store(SELECTOR).read()['binding']['processIdentity'])

    def test_phone_restart_input_intent_blocks_cleanup_when_other_owners_are_absent(self):
        self.adapter.script_restart_inputs_store(SELECTOR).write({'unresolved': True}, None)
        with patch.object(AppiumAdapter, 'cleanup', return_value={'cleaned': True}):
            with self.assertRaisesRegex(ValueError, 'PHONE_SCRIPT_RESTART_INPUTS_CLEANUP_INCOMPLETE'):
                self.adapter.cleanup(SELECTOR)
        self.assertIsNotNone(self.adapter.script_restart_inputs_store(SELECTOR).read())

    def test_phone_native_effect_counters_are_actual_rows_and_process_loss_blocks_new_reads(self):
        source = self.preview_boundaries(ScriptBoundary(), 'feature-script-observation.json')
        source.mutate = effect_source
        reader = self.adapter._script_execution_observer(SELECTOR)
        first = reader.read(0, require_effects=True)
        self.assertEqual(2, measured_effect(first, EFFECT_RUN)['ticks'])
        second = reader.read(first['sequence'], require_effects=True)
        self.assertEqual(measured_effect(first, EFFECT_RUN), measured_effect(second, EFFECT_RUN))
        self.native.identity = '32:foreign-start'; before = len(source.commands)
        with self.assertRaises(RuntimeError): reader.read(second['sequence'], require_effects=True)
        self.assertEqual(before, len(source.commands)); self.assertEqual([], self.native.inputs)

    def test_phone_fixture_originals_stage_readback_and_release_through_actual_bound_factory(self):
        source, files = self.script_file_storage()
        self.assertEqual(source.root.as_uri(), files.stage('a' * 32))
        files.release()
        self.assertFalse(source.root.exists())
        self.assertIsNone(self.adapter.script_files_store(SELECTOR).read())
        self.assertEqual([], self.native.inputs)

    def test_phone_fixture_acknowledged_missing_content_retains_intent(self):
        source, files = self.script_file_storage(); source.fault = 'ack-only'
        with self.assertRaises(RuntimeError): files.stage('a' * 32)
        self.assertIsNotNone(self.adapter.script_files_store(SELECTOR).read())
        self.assertEqual(1, sum(c['operation'] == 'stage' for c in source.commands))

    def test_phone_fixture_candidate_loss_blocks_release_and_keeps_persistent_files(self):
        source, files = self.script_file_storage(); files.stage('a' * 32)
        before = len(source.commands); self.fixture.adb.digest = 'f' * 64
        with self.assertRaises(RuntimeError): files.release()
        self.assertEqual(before, len(source.commands)); self.assertTrue(source.root.exists())
        self.assertIsNotNone(self.adapter.script_files_store(SELECTOR).read())

    def test_phone_unresolved_fixture_files_prevent_green_general_cleanup_after_teardown(self):
        source, files = self.script_file_storage(); files.stage('a' * 32)
        with patch.object(AppiumAdapter, 'cleanup', return_value={'cleaned':True}) as teardown:
            with self.assertRaisesRegex(ValueError, 'PHONE_SCRIPT_FILES_CLEANUP_INCOMPLETE'):
                self.adapter.cleanup(SELECTOR)
            teardown.assert_called_once()
        self.assertIsNotNone(self.adapter.script_files_store(SELECTOR).read())
        self.assertTrue(source.root.exists())

    def test_original_phone_preview_pcm_keeps_actual_candidate_and_process_binding(self):
        source = self.preview_boundaries()
        reader = self.adapter._recorded_preview_evidence(SELECTOR)
        value, raw = reader.read(0, after_cycle=6)
        self.assertEqual(source.value, value)
        self.assertEqual(source.files['recorded-preview-input.pcm16le'], raw['input'])
        reader.release(); reader.release()
        self.assertEqual({}, source.files)
        self.assertEqual([], self.native.inputs)

    def test_phone_preview_candidate_loss_blocks_evidence_before_command(self):
        source = self.preview_boundaries()
        reader = self.adapter._recorded_preview_evidence(SELECTOR)
        self.fixture.adb.digest = 'f' * 64
        with self.assertRaises(RuntimeError): reader.read(0)
        self.assertEqual([], source.commands)

    def test_phone_preview_ignored_cleanup_and_changed_process_cannot_pass(self):
        source = self.preview_boundaries(); source.retain = True
        reader = self.adapter._recorded_preview_evidence(SELECTOR)
        reader.read(0)
        with self.assertRaises(RuntimeError): reader.release()
        self.native.identity = '99:foreign-process'
        before = len(source.commands)
        with self.assertRaises(RuntimeError): reader.read(reader.sequence)
        self.assertEqual(before, len(source.commands))

    def test_phone_submitted_code_uses_original_bound_source_and_refuses_older_producer(self):
        source=self.preview_boundaries(ScriptBoundary(), 'feature-script-observation.json')
        original=source.mutate
        def identified(value):
            if original: original(value)
            code_source(value)
        source.mutate=identified;reader=self.adapter._script_execution_observer(SELECTOR)
        first=reader.read(0,require_code_identity=True)
        code=first['source']['engines'][0]['code']
        self.assertEqual(15000,code['submittedEpochMs']);self.assertTrue(code['submitted'])
        second=reader.read(first['sequence'],require_code_identity=True)
        self.assertEqual(code,second['source']['engines'][0]['code'])
        source.mutate=original
        with self.assertRaises(RuntimeError):reader.read(second['sequence'],require_code_identity=True)

    def test_phone_original_load_failure_history_survives_transport_and_refuses_downgrade(self):
        source = self.preview_boundaries(ScriptBoundary(), 'feature-script-observation.json')
        original = source.mutate
        def observed(packet):
            if original: original(packet)
            load_history(packet)
        source.mutate = observed
        reader = self.adapter._script_execution_observer(SELECTOR)
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

    def missing_load(self, *, ignored=False):
        source = ScriptBoundary(); events = []
        url = 'http://fixture.test/feature-fixture/v1/runs/' + 'a' * 32 + '/tickets/' + 'b' * 32 + '/missing.js'
        def observed(packet):
            packet.update(requestedEpochMs=self.native.epoch_ms, capturedEpochMs=self.native.epoch_ms)
            packet['source']['engines'] = []; load_history(packet, events)
        source.mutate = observed
        send_original = self.adapter.write_android_client_command
        read_original = self.fixture.adb.read_debug_app_file
        def send(client, session, target, request, process):
            if request['action'] == 'feature-script-observe': source.send(request)
            else: return send_original(client, session, target, request, process)
        def read(device, package, path, **kwargs):
            if path.endswith('/feature-script-observation.json'):
                self.assertEqual({'attempts': 1}, kwargs); return source.original()
            return read_original(device, package, path, **kwargs)
        for boundary in (patch.object(self.adapter, 'write_android_client_command', side_effect=send),
                         patch.object(self.fixture.adb, 'read_debug_app_file', side_effect=read)):
            boundary.start(); self.addCleanup(boundary.stop)
        def input(name):
            if name == 'OK' and not ignored:
                events.append(load_event(url=self.native.text, callbackEpochMs=self.native.epoch_ms))
        self.native.mutation = input
        return source, url

    def test_phone_missing_script_uses_normal_input_original_failure_and_explicit_retirement(self):
        source, url = self.missing_load()
        manager = self.adapter._script_missing_manager(SELECTOR); manager.open()
        manager.load_missing(url, self.adapter._script_execution_observer(SELECTOR))
        manager = self.adapter._script_missing_manager(SELECTOR)
        actual = manager.settle_missing(self.adapter._script_execution_observer(SELECTOR))
        self.assertEqual(source.sample['source']['loads']['events'][0], actual)
        self.assertEqual('NotFound', actual['status']); manager.close()
        self.assertIsNone(self.adapter.script_store(SELECTOR).read())
        self.assertEqual(1, self.native.inputs.count('OK'))
        self.assertFalse(any(cap.startswith('feature.') for cap in self.adapter.advertised_capabilities(self.target)))

    def test_phone_missing_script_ignored_submit_cannot_retire_or_replay(self):
        _source, url = self.missing_load(ignored=True)
        manager = self.adapter._script_missing_manager(SELECTOR); manager.open()
        manager.load_missing(url, self.adapter._script_execution_observer(SELECTOR))
        with self.assertRaises(RuntimeError): manager.settle_missing(self.adapter._script_execution_observer(SELECTOR))
        with self.assertRaises(RuntimeError): manager.load_missing(url, self.adapter._script_execution_observer(SELECTOR))
        self.assertTrue(self.adapter.script_store(SELECTOR).read()['loadAttempted'])
        self.assertEqual(1, self.native.inputs.count('OK'))

    def test_phone_missing_script_candidate_loss_cannot_be_adopted(self):
        source, url = self.missing_load()
        manager = self.adapter._script_missing_manager(SELECTOR); manager.open()
        manager.load_missing(url, self.adapter._script_execution_observer(SELECTOR))
        before = len(source.commands); self.fixture.adb.digest = 'f' * 64
        with self.assertRaisesRegex(ValueError, 'PHONE_INSTALLED_BYTES_MISMATCH'):
            self.adapter._script_missing_manager(SELECTOR)
        self.assertEqual(before, len(source.commands))
        self.assertTrue(self.adapter.script_store(SELECTOR).read()['loadAttempted'])

    def test_phone_missing_script_cannot_adopt_existing_public_manager_owner(self):
        self.invoke('scripts.manager.open')
        before = list(self.native.inputs)
        with self.assertRaises(RuntimeError): self.adapter._script_missing_manager(SELECTOR)
        self.assertEqual(before, self.native.inputs)
        self.assertEqual('scripts', self.adapter.script_store(SELECTOR).read()['sourceKind'])


    def test_phone_script_execution_source_uses_bound_original_native_module_history(self):
        source = self.preview_boundaries(ScriptBoundary(), 'feature-script-observation.json')
        reader = self.adapter._script_execution_observer(SELECTOR)
        value = reader.read(0)
        self.assertEqual(source.sample, value)
        self.assertEqual(['companion.js'], loaded_relative_modules(running_owned_engine(value, source.engine['url'])))
        self.assertEqual([], self.native.inputs)

    def test_phone_script_execution_source_rejects_replaced_installed_candidate(self):
        source = self.preview_boundaries(ScriptBoundary(), 'feature-script-observation.json')
        reader = self.adapter._script_execution_observer(SELECTOR)
        self.fixture.adb.digest = 'f' * 64
        with self.assertRaises(RuntimeError): reader.read(0)
        self.assertEqual([], source.commands)

    def file_picker_boundaries(self):
        root = self.fixture.root / ('feature-script-' + 'a' * 32)
        root.mkdir()
        (root / 'script.js').write_text("var companion = Script.require('./companion.js');")
        (root / 'companion.js').write_text('module.exports = {delta: 1};')
        source = FileNativeBoundary(root)
        def send(_client, _session, target, command, process):
            self.assertEqual(PACKAGE, target['appId'])
            self.assertEqual({'running': True, 'identity': '31:14'}, process)
            source.send(command)
        def read(_device, package, path, **kwargs):
            self.assertEqual(PACKAGE, package)
            self.assertEqual('files/overte-e2e/phone-script-file-ui.json', path)
            self.assertEqual({'attempts': 1}, kwargs)
            return json.dumps(source.value)
        for boundary in (
            patch.object(self.adapter, 'write_android_client_command', side_effect=send),
            patch.object(self.fixture.adb, 'read_debug_app_file', side_effect=read, create=True),
            patch.object(self.fixture.adb, 'epoch_milliseconds', return_value=20000, create=True),
            patch.object(appium, 'PhoneScriptFileIO', partial(appium.PhoneScriptFileIO,
                monotonic=lambda: source.ui.clock, sleep=source.ui.sleep)),
            patch.object(appium, 'TokenScriptFilePicker', partial(TokenScriptFilePicker,
                monotonic=lambda: source.ui.clock, sleep=source.ui.sleep))):
            boundary.start(); self.addCleanup(boundary.stop)
        return source, self.adapter._script_file_picker(SELECTOR, root.as_uri())

    def test_phone_file_picker_uses_actual_native_review_and_one_normal_confirmation(self):
        source, picker = self.file_picker_boundaries()
        picker.open(); picker.choose('script.js')
        self.assertEqual([(source.ui.root / 'script.js').as_uri()], source.ui.accepted)
        self.assertEqual(1, sum(row['controlId'] == 'script-file.confirm' for row in source.input_requests))
        self.assertTrue(all(set(command) == {'schemaVersion', 'commandId', 'action', 'request'} for command in source.commands))
        self.assertEqual([], self.native.inputs)

    def test_phone_manager_status_returns_actual_separate_label_metadata_without_input(self):
        from self_tests.test_script_manager_status import observed
        source, _picker = self.file_picker_boundaries()
        actual = observed(statusText='original native root', labelText='separate original label')
        def measured(packet):
            for row in packet.get('controls', []):
                if row['id'] == 'scripts.from-file': row['manager'] = deepcopy(actual)
        source.mutate = measured
        self.assertEqual(actual, self.adapter._script_manager_status(SELECTOR))
        self.assertEqual([], source.input_requests); self.assertEqual([], self.native.inputs)
        actual['labelText'] = 'new actual label'
        self.assertEqual(actual, self.adapter._script_manager_status(SELECTOR))

    def test_phone_script_inventory_reads_original_picker_and_manager_without_input_carrier(self):
        from self_tests.test_script_ui_inventory import inventory, picker
        from self_tests.test_script_manager_status import observed
        source, _picker = self.file_picker_boundaries()
        actual = inventory([observed(statusText='original root', labelText='separate display')], [picker()])
        def measured(packet):
            packet['controls'] = []
            packet['scriptInventory'] = deepcopy(actual)
        source.mutate = measured
        value = self.adapter._script_ui_state(SELECTOR)
        self.assertTrue(value['open']); self.assertTrue(value['picker'])
        self.assertEqual(actual['managers'][0], value['manager'])
        actual.update(managers=[], pickers=[])
        self.assertFalse(self.adapter._script_ui_state(SELECTOR)['open'])
        self.assertEqual([], source.input_requests); self.assertEqual([], self.native.inputs)

    def test_phone_script_inventory_missing_incomplete_or_foreign_is_not_closed_success(self):
        from self_tests.test_script_ui_inventory import inventory, picker
        source, _picker = self.file_picker_boundaries()
        with self.assertRaises(RuntimeError): self.adapter._script_ui_state(SELECTOR)
        for value in (inventory(complete=False), inventory(pickers=[picker(componentSource='file:///foreign.qml')])):
            source.mutate = lambda packet: packet.update(scriptInventory=deepcopy(value))
            with self.subTest(value=value), self.assertRaises(RuntimeError): self.adapter._script_ui_state(SELECTOR)
        self.assertEqual([], source.input_requests)

    def test_phone_script_inventory_stale_foreign_pid_or_nonce_cannot_prove_closed(self):
        from self_tests.test_script_ui_inventory import inventory
        source, _picker = self.file_picker_boundaries()
        for key, value in (('capturedEpochMs', 1), ('processId', 9999), ('commandId', 'f' * 32)):
            source.mutate = lambda packet: packet.update(scriptInventory=inventory(), **{key: value})
            with self.subTest(key=key), self.assertRaises(RuntimeError): self.adapter._script_ui_state(SELECTOR)
        self.assertEqual([], source.input_requests)

    def test_phone_script_inventory_candidate_replacement_blocks_query_before_send(self):
        source, _picker = self.file_picker_boundaries(); self.fixture.adb.digest = 'f' * 64
        with self.assertRaises((ValueError, RuntimeError)): self.adapter._script_ui_state(SELECTOR)
        self.assertEqual([], source.commands)
        self.assertEqual([], source.input_requests); self.assertEqual([], self.native.inputs)

    def test_phone_manager_status_missing_or_foreign_source_is_not_empty_success(self):
        from self_tests.test_script_manager_status import observed
        source, _picker = self.file_picker_boundaries()
        with self.assertRaises(RuntimeError): self.adapter._script_manager_status(SELECTOR)
        def foreign(packet):
            for row in packet.get('controls', []):
                if row['id'] == 'scripts.from-file': row['manager'] = observed(componentSource='file:///foreign.qml')
        source.mutate = foreign
        with self.assertRaises(RuntimeError): self.adapter._script_manager_status(SELECTOR)
        self.assertEqual([], source.input_requests)

    def test_phone_manager_status_candidate_loss_is_refused_before_original_source_query(self):
        source, _picker = self.file_picker_boundaries(); self.fixture.adb.digest = 'f' * 64
        with self.assertRaises((ValueError, RuntimeError)): self.adapter._script_manager_status(SELECTOR)
        self.assertEqual([], source.commands)

    def test_phone_file_input_ack_cannot_hide_ignored_native_selection(self):
        source, picker = self.file_picker_boundaries(); source.ui.fault = 'row'
        picker.open()
        with self.assertRaises(RuntimeError): picker.choose('script.js')
        self.assertEqual([], source.ui.accepted)
        self.assertEqual(1, sum(row['controlId'].startswith('script-file.row.') for row in source.input_requests))
        picker.cancel()
        self.assertFalse(source.ui.opened)

    def test_phone_file_main_selector_uses_normal_input_and_real_readback(self):
        source, picker = self.file_picker_boundaries(); source.ui.fault = 'wrong-primary'
        picker.open(); picker.choose('script.js')
        self.assertEqual([(source.ui.root / 'script.js').as_uri()], source.ui.accepted)
        selections = [request for request in source.input_requests if request['action'] == 'select-index']
        self.assertEqual(1, len(selections)); self.assertEqual(0, selections[0]['index'])

    def test_phone_file_ignored_main_selector_cannot_confirm_the_companion_as_main(self):
        source, picker = self.file_picker_boundaries(); source.ui.fault = 'primary'
        picker.open()
        with self.assertRaises(RuntimeError): picker.choose('script.js')
        self.assertEqual([], source.ui.accepted)
        self.assertEqual(1, sum(request['action'] == 'select-index' for request in source.input_requests))
        self.assertFalse(any(request['controlId'] == 'script-file.confirm' for request in source.input_requests))
        picker.cancel()

    def test_phone_file_picker_changed_candidate_blocks_before_any_ui_request(self):
        source, picker = self.file_picker_boundaries()
        self.fixture.adb.digest = 'f' * 64
        with self.assertRaises(RuntimeError): picker.open()
        self.assertEqual([], source.commands)

    def test_phone_file_generation_change_cannot_adopt_the_old_dialog_context(self):
        source, picker = self.file_picker_boundaries(); picker.open()
        before = len(source.input_requests); source.generation = 'c' * 32
        with self.assertRaises(RuntimeError): picker.choose('script.js')
        self.assertEqual(before, len(source.input_requests))
        self.assertTrue(source.ui.opened)

    def test_phone_file_foreign_ack_fails_without_replay_and_actual_dialog_can_be_cancelled(self):
        source, picker = self.file_picker_boundaries()
        source.mutate = lambda value: value.update(processId=999) if value['action'] == 'activate' else None
        with self.assertRaises(RuntimeError): picker.open()
        self.assertTrue(source.ui.opened)
        self.assertEqual(1, len(source.input_requests))
        source.mutate = None; picker.cancel()
        self.assertFalse(source.ui.opened)

    def test_phone_file_partial_result_retries_reads_without_repeating_a_request(self):
        source, picker = self.file_picker_boundaries(); original = picker.io.original; reads = []
        def partial_read():
            reads.append(1)
            return '{"schemaVersion":' if len(reads) == 1 else original()
        picker.io.original = partial_read
        self.assertTrue(picker.io.capture()['ready'])
        self.assertEqual(1, len(source.commands)); self.assertEqual(2, len(reads))
        self.assertEqual([], source.input_requests)

    def test_phone_file_result_with_wrong_types_or_missing_marker_never_authorizes_input(self):
        source, picker = self.file_picker_boundaries()
        for fault in ('version', 'cursor', 'marker'):
            with self.subTest(fault=fault):
                def mutate(value):
                    if fault == 'version': value['schemaVersion'] = True
                    elif fault == 'cursor': value['sourceSequence'] = 0
                    else: value.pop('fileControlsVersion')
                source.mutate = mutate
                with self.assertRaises(RuntimeError): picker.open()
        self.assertEqual([], source.input_requests)

    def test_actual_phone_probe_rejects_extra_or_untyped_file_inputs_before_native_dispatch(self):
        program = '''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,keys)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(keys.sort());
let calls=[],files=[];
const Test={phoneScriptFileUi:request=>{calls.push(request);return {schemaVersion:1,commandId:request.commandId,performed:true};},
 saveObject:(v,name)=>files.push({v,name})};
SOURCE
function outer(request){return {schemaVersion:1,commandId:request.commandId,action:"phone-script-file-ui",request};}
const observe={schemaVersion:1,commandId:"a".repeat(32),action:"observe"};
applyAndroidControlCommand(outer(observe));applyAndroidControlCommand(outer(observe));
if(calls.length!==1||files[0].name!=="phone-script-file-ui.json")throw Error("original dispatch");
applyClientCommand(outer({...observe,commandId:"b".repeat(32),expected:{files:["script.js"]}}));
const input={schemaVersion:1,commandId:"c".repeat(32),action:"activate",instance:"d".repeat(32),generation:"e".repeat(32),
 sequence:1,observedElapsedMs:0,controlId:"scripts.from-file",controlToken:"f".repeat(32)};
applyAndroidControlCommand(outer(input));
if(calls.length!==2)throw Error("normal input");
applyClientCommand(outer({...input,commandId:"1".repeat(32),sequence:true}));
applyClientCommand(outer({...input,commandId:"2".repeat(32),text:"unowned"}));
if(calls.length!==2)throw Error("untyped or extra input");
delete Test.phoneScriptFileUi;
applyClientCommand(outer({...observe,commandId:"3".repeat(32)}));
if(files[2].v.available!==false)throw Error("missing hook green");
'''.replace('SOURCE', probe_source())
        completed = subprocess.run(['node', '-e', program], capture_output=True, text=True, timeout=5)
        self.assertEqual(0, completed.returncode, completed.stderr)

    def create_boundaries(self):
        from create_native_boundary import CreateNativeBoundary
        from adapters.token_create_ui import TokenCreateUI
        source=CreateNativeBoundary(self.fixture.root)
        self.native.screen='create'
        def send(client,session,target,command,process):
            self.assertEqual({'running':True,'identity':'31:14'},process);source.send(command)
        def read(_device,package,path,**kwargs):
            self.assertEqual('files/overte-e2e/phone-create-ui.json',path)
            self.assertEqual({'attempts':1},kwargs);return json.dumps(source.value)
        for boundary in (
            patch.object(self.adapter,'write_android_client_command',side_effect=send),
            patch.object(self.fixture.adb,'read_debug_app_file',side_effect=read,create=True),
            patch.object(self.fixture.adb,'epoch_milliseconds',return_value=20000,create=True),
            patch.object(appium,'PhoneCreateIO',partial(appium.PhoneCreateIO,
                monotonic=lambda:source.native.clock,sleep=source.native.sleep)),
            patch.object(appium,'TokenCreateUI',partial(TokenCreateUI,
                monotonic=lambda:source.native.clock,sleep=source.native.sleep))):
            boundary.start();self.addCleanup(boundary.stop)
        return source,self.adapter._create_controls(SELECTOR,source.ui.intents.append)

    def test_phone_create_original_fields_choices_and_scroll_use_bound_reference(self):
        source,ui=self.create_boundaries()
        ui.choose('create.host',1)
        self.assertEqual(1,source.ui.indexes['create.host'])
        source.ui.hidden='create.resource';ui.replace('create.resource','owned-resource')
        self.assertEqual('owned-resource',source.ui.texts['create.resource'])
        self.assertTrue(any(r['action']=='scroll' for r in source.input_requests))
        self.assertTrue(all(r['sequence']==n+1 for n,r in enumerate(source.input_requests)))
        self.assertFalse(any(c.startswith('feature.create.') for c in self.adapter.advertised_capabilities(self.target)))

    def test_phone_create_ignored_choice_and_text_are_not_success(self):
        source,ui=self.create_boundaries();source.ui.ignore={'create.host'}
        with self.assertRaises(RuntimeError):ui.choose('create.host',1)
        self.assertEqual(0,source.ui.indexes['create.host'])
        source.ui.ignore={'create.resource'}
        with self.assertRaises(RuntimeError):ui.replace('create.resource','owned-resource')
        self.assertNotIn('create.resource',source.ui.texts)

    def test_phone_create_changed_native_context_refuses_before_mutation(self):
        source,ui=self.create_boundaries();reference=ui.capture()
        source.ui.selected=['22222222-2222-2222-2222-222222222222']
        with self.assertRaises(RuntimeError):ui.io.activate('create.tab.0',reference=reference)
        self.assertEqual([],source.input_requests)
        source.ui.selected=[];source.before_input=lambda:setattr(source.ui,'generation','c'*32)
        with self.assertRaises(RuntimeError):ui.tab(0)
        self.assertEqual(0,source.ui.sequence)

    def test_phone_create_missing_marker_false_types_and_changed_candidate_refuse_input(self):
        for fault in ('version','missing','pid','epoch'):
            with self.subTest(fault=fault):
                source,ui=self.create_boundaries()
                def mutate(v):
                    if fault=='missing':v.pop('createControlsVersion',None)
                    elif fault=='version':v['createControlsVersion']=True
                    elif fault=='pid':v['processId']=99
                    else:v['capturedEpochMs']=1
                source.mutate=mutate
                with self.assertRaises(RuntimeError):ui.tab(0)
                self.assertEqual([],source.input_requests)
        self.fixture.adb.digest='f'*64
        with self.assertRaises(ValueError):self.adapter._create_controls(SELECTOR,lambda _:None)

    def test_actual_phone_probe_create_grammar_rejects_shortcuts_and_extra_results(self):
        program=r'''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,keys)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(keys.sort());
let calls=[],files=[];
const Test={phoneCreateUi:r=>{calls.push(r);return {commandId:r.commandId,performed:true};},saveObject:(v,name)=>files.push({v,name})};
SOURCE
const outer=r=>({schemaVersion:1,commandId:r.commandId,action:"phone-create-ui",request:r});
const observe={schemaVersion:1,commandId:"a".repeat(32),action:"observe"};
applyAndroidControlCommand(outer(observe));applyAndroidControlCommand(outer(observe));
if(calls.length!==1||files[0].name!=="phone-create-ui.json")throw Error("original observe or dedup");
const input={schemaVersion:1,commandId:"b".repeat(32),action:"replace",instance:"c".repeat(32),generation:"d".repeat(32),
sequence:1,observedElapsedMs:0,controlId:"create.name",controlToken:"e".repeat(32),text:"test-only"};
applyAndroidControlCommand(outer(input));
for(const change of [{sequence:true},{text:"line\nsecret"},{controlId:"create.page"},{action:"create-direct"},{expected:{entities:[]}}]){
 applyAndroidControlCommand(outer({...input,...change,commandId:"f".repeat(32)}));}
if(calls.length!==2)throw Error("untyped or shortcut input");
let choice={...input,commandId:"1".repeat(32),action:"select-index",controlId:"create.host",index:1};delete choice.text;
applyAndroidControlCommand(outer(choice));applyAndroidControlCommand(outer({...choice,index:2,commandId:"2".repeat(32)}));
if(calls.length!==3)throw Error("host bounds");
delete Test.phoneCreateUi;applyAndroidControlCommand(outer({...observe,commandId:"3".repeat(32)}));
if(files[3].v.available!==false)throw Error("missing native hook green");
'''.replace('SOURCE',probe_source())
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)

    def chat_control_boundaries(self):
        from adapters.token_chat_ui import TokenChatUI
        source=ChatNativeBoundary();self.native.screen='chat'
        def send(client,session,target,command,process):
            self.assertEqual({'running':True,'identity':'31:14'},process);source.send(command)
        def read(_device,package,path,**kwargs):
            self.assertEqual('files/overte-e2e/phone-chat-ui.json',path)
            self.assertEqual({'attempts':1},kwargs);return json.dumps(source.value)
        for boundary in (
            patch.object(self.adapter,'write_android_client_command',side_effect=send),
            patch.object(self.fixture.adb,'read_debug_app_file',side_effect=read,create=True),
            patch.object(self.fixture.adb,'epoch_milliseconds',return_value=20000,create=True),
            patch.object(appium,'PhoneChatIO',partial(appium.PhoneChatIO,
                monotonic=lambda:source.native.clock,sleep=source.native.sleep)),
            patch.object(appium,'TokenChatUI',partial(TokenChatUI,
                monotonic=lambda:source.native.clock,sleep=source.native.sleep))):
            boundary.start();self.addCleanup(boundary.stop)
        source.intents=[]
        return source,self.adapter._chat_controls(SELECTOR,source.intents.append,CHAT_RUN)

    def test_phone_chat_controls_use_unicode_normal_send_enter_and_original_counter(self):
        from feature_journeys.fixtures import context
        source,ui=self.chat_control_boundaries()
        ui.select_channel('domain');ui.type(context(CHAT_RUN)['unicode']);ui.send()
        ui.type(context(CHAT_RUN)['retry']);ui.send(enter=True);ui.close()
        self.assertEqual([('domain',context(CHAT_RUN)['unicode']),('domain',context(CHAT_RUN)['retry'])],source.ui.sent)
        self.assertFalse(source.ui.panel);self.assertEqual([],source.ui.domain)
        self.assertEqual(list(range(1,len(source.input_requests)+1)),[r['sequence'] for r in source.input_requests])
        self.assertNotIn(context(CHAT_RUN)['unicode'],str(source.intents))
        self.assertFalse(any(c.startswith('feature.chat.') for c in self.adapter.advertised_capabilities(self.target)))

    def test_phone_chat_consumed_but_ignored_field_is_not_success(self):
        from feature_journeys.fixtures import context
        source,ui=self.chat_control_boundaries();source.ui.ignore_effect=True
        with self.assertRaises(RuntimeError):ui.type(context(CHAT_RUN)['unicode'])
        self.assertEqual('',source.ui.draft);self.assertFalse(source.ui.focus)
        self.assertEqual(1,len(source.input_requests))

    def test_phone_chat_draft_or_native_context_changes_do_not_retarget_input(self):
        from feature_journeys.fixtures import context
        source,ui=self.chat_control_boundaries();ui.type(context(CHAT_RUN)['unicode']);reference=ui.capture()
        before=len(source.input_requests);source.ui.draft=context(CHAT_RUN)['retry']
        with self.assertRaises(RuntimeError):ui.io.activate('chat.send',reference=reference)
        self.assertEqual(before,len(source.input_requests));self.assertEqual([],source.ui.sent)
        source.before_input=lambda:setattr(source.ui,'generation','f'*32)
        with self.assertRaises(RuntimeError):ui.send()
        self.assertEqual([],source.ui.sent)

    def test_phone_chat_missing_marker_wrong_pid_time_and_changed_candidate_are_unavailable(self):
        for fault in ('version','missing','pid','epoch'):
            with self.subTest(fault=fault):
                source,ui=self.chat_control_boundaries()
                def mutate(value):
                    if fault=='missing':value.pop('chatControlsVersion',None)
                    elif fault=='version':value['chatControlsVersion']=True
                    elif fault=='pid':value['processId']=99
                    else:value['capturedEpochMs']=1
                source.mutate=mutate
                with self.assertRaises(RuntimeError):ui.select_channel('domain')
                self.assertEqual([],source.input_requests)
        self.fixture.adb.digest='f'*64
        with self.assertRaises(ValueError):self.adapter._chat_controls(SELECTOR,lambda _:None,CHAT_RUN)

    def test_actual_phone_probe_chat_grammar_rejects_fake_results_and_non_normal_shortcuts(self):
        program=r'''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,keys)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(keys.sort());
let calls=[],files=[];
const Test={phoneChatUi:r=>{calls.push(r);return {commandId:r.commandId,performed:true};},saveObject:(v,name)=>files.push({v,name})};
SOURCE
const outer=r=>({schemaVersion:1,commandId:r.commandId,action:"phone-chat-ui",request:r});
const observe={schemaVersion:1,commandId:"a".repeat(32),action:"observe"};
applyAndroidControlCommand(outer(observe));applyAndroidControlCommand(outer(observe));
if(calls.length!==1||files[0].name!=="phone-chat-ui.json")throw Error("original observe or dedup");
const input={schemaVersion:1,commandId:"b".repeat(32),action:"replace",instance:"c".repeat(32),generation:"d".repeat(32),
sequence:1,observedElapsedMs:0,controlId:"chat.input",controlToken:"e".repeat(32),text:"Overte ä Ω 東京 "+"a".repeat(32)};
applyAndroidControlCommand(outer(input));
for(const change of [{sequence:true},{text:"private user content"},{text:input.text+"\n"},{controlId:"chat.page"},
 {commandId:"f".repeat(32)+"\n"},{instance:"f".repeat(32)+"\n"},{action:"send-message-direct"},{expected:{messages:[]}}]){
 applyAndroidControlCommand(outer({...input,commandId:"f".repeat(32),...change}));}
if(calls.length!==2)throw Error("untyped, private or shortcut input");
let enter={...input,commandId:"1".repeat(32),action:"submit"};delete enter.text;
applyAndroidControlCommand(outer(enter));
let activate={...enter,action:"activate",controlId:"chat.send",commandId:"2".repeat(32)};
applyAndroidControlCommand(outer({...activate,controlId:"chat.send\n"}));applyAndroidControlCommand(outer(activate));
if(calls.length!==4)throw Error("original Enter/Send or newline control");
delete Test.phoneChatUi;applyAndroidControlCommand(outer({...observe,commandId:"3".repeat(32)}));
if(files[4].v.available!==false)throw Error("missing native hook green");
'''.replace('SOURCE',probe_source())
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)

    def graphics_boundaries(self):
        source=ControlNativeBoundary(GraphicsBoundary(),'phone-graphics-ui')
        def send(client,session,target,command,process):
            self.assertEqual({'running':True,'identity':'31:14'},process);source.send(command)
        def read(_device,package,path,**kwargs):
            self.assertEqual('files/overte-e2e/phone-graphics-ui.json',path)
            self.assertEqual({'attempts':1},kwargs);return json.dumps(source.value)
        for boundary in (
            patch.object(self.adapter,'write_android_client_command',side_effect=send),
            patch.object(self.fixture.adb,'read_debug_app_file',side_effect=read,create=True),
            patch.object(self.fixture.adb,'epoch_milliseconds',return_value=20000,create=True),
            patch.object(appium,'PhoneGraphicsIO',partial(appium.PhoneGraphicsIO,
                monotonic=lambda:source.ui.clock,sleep=source.ui.sleep)),
            patch.object(appium,'TokenGraphicsUI',partial(TokenGraphicsUI,
                monotonic=lambda:source.ui.clock,sleep=source.ui.sleep))):
            boundary.start();self.addCleanup(boundary.stop)
        return source,self.adapter._graphics_controls(SELECTOR,source.ui.intent)

    def test_phone_graphics_normal_settings_scroll_and_nondefault_restore_use_original_readback(self):
        source,ui=self.graphics_boundaries();source.ui.flick_duration=0.3;initial=source.ui.resolution
        ui.set_resolution(0.5);ui.set_resolution(0.6);ui.set_resolution(initial)
        ui.toggle('graphics.haze',True);ui.toggle('graphics.mirrors',True)
        ui.toggle('graphics.haze',False);ui.toggle('graphics.mirrors',False)
        self.assertEqual(initial,source.ui.resolution);self.assertFalse(source.ui.haze);self.assertFalse(source.ui.mirrors)
        self.assertEqual(3,source.ui.actions.count('resolution'));self.assertEqual([],self.native.inputs)

    def test_phone_graphics_ignored_and_ui_only_slider_cannot_be_success(self):
        source,ui=self.graphics_boundaries();source.ui.fault='resolution'
        with self.assertRaises(RuntimeError):ui.set_resolution(0.5)
        self.assertEqual(0.65,source.ui.resolution);self.assertEqual(1,source.ui.actions.count('resolution'))
        source.ui.fault='ui-only'
        with self.assertRaises(RuntimeError):ui.set_resolution(0.5)
        self.assertEqual(0.65,source.ui.resolution);self.assertEqual(2,source.ui.actions.count('resolution'))

    def test_phone_graphics_candidate_change_and_missing_marker_refuse_before_input(self):
        source,ui=self.graphics_boundaries();original=self.fixture.adb.digest;self.fixture.adb.digest='f'*64
        with self.assertRaises(RuntimeError):ui.set_resolution(0.5)
        self.assertEqual([],source.commands);self.fixture.adb.digest=original
        source.mutate=lambda value:value.pop('graphicsControlsVersion',None)
        with self.assertRaises(RuntimeError):ui.set_resolution(0.5)
        self.assertEqual([],source.input_requests)

    def test_phone_graphics_retired_original_token_cannot_adopt_layout_or_setting_change(self):
        source,ui=self.graphics_boundaries();source.ui.position=0.6
        source.before_input=lambda:setattr(source.ui,'resolution',0.7)
        with self.assertRaises(RuntimeError):ui.set_resolution(0.5)
        self.assertEqual([],source.ui.actions);self.assertEqual(1,len(source.input_requests))

    def test_phone_graphics_missing_reply_after_slider_delivery_never_replays(self):
        source,ui=self.graphics_boundaries();source.ui.position=0.6
        def mutate(value):
            if value.get('action')!='observe':value['commandId']='f'*32
        source.mutate=mutate
        with self.assertRaises(RuntimeError):ui.set_resolution(0.5)
        self.assertEqual(['resolution'],source.ui.actions);self.assertEqual(0.5,source.ui.resolution)

    def test_phone_graphics_foreign_native_process_or_generation_cannot_authorize_input(self):
        source,ui=self.graphics_boundaries();ui.capture()
        for field,value in (('processId',99),('generation','f'*32),('sourceSequence',0)):
            with self.subTest(field=field):
                source.mutate=lambda packet:packet.update({field:value})
                with self.assertRaises(RuntimeError):ui.toggle('graphics.haze',True)
        self.assertEqual([],source.input_requests)

    def test_actual_phone_probe_graphics_requests_are_closed_typed_and_source_owned(self):
        program=r'''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,keys)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(keys.sort());
let calls=[],files=[];
const Test={phoneGraphicsUi:r=>{calls.push(r);return {commandId:r.commandId,performed:true};},
 saveObject:(v,name)=>files.push({v,name})};
SOURCE
function outer(request){return {schemaVersion:1,commandId:request.commandId,action:"phone-graphics-ui",request};}
const observe={schemaVersion:1,commandId:"a".repeat(32),action:"observe"};
applyAndroidControlCommand(outer(observe));applyAndroidControlCommand(outer(observe));
if(calls.length!==1||files[0].name!=="phone-graphics-ui.json")throw Error("original dispatch");
const input={schemaVersion:1,commandId:"b".repeat(32),action:"set-value",instance:"c".repeat(32),generation:"d".repeat(32),
 sequence:1,observedElapsedMs:0,controlId:"graphics.resolution",controlToken:"e".repeat(32),value:0.5};
applyAndroidControlCommand(outer(input));
for(const change of [{value:true},{value:3},{expected:0.5},{controlId:"graphics.page"},{action:"apply-preset"}]){
 applyClientCommand(outer({...input,...change,commandId:"f".repeat(32)}));}
if(calls.length!==2)throw Error("untyped or extra input");
const scroll={...input,commandId:"1".repeat(32),action:"scroll",controlId:"graphics.scrollbar",direction:"down"};delete scroll.value;
applyAndroidControlCommand(outer(scroll));if(calls.length!==3)throw Error("scroll missing");
delete Test.phoneGraphicsUi;applyClientCommand(outer({...observe,commandId:"2".repeat(32)}));
if(files[3].v.available!==false)throw Error("missing hook green");
'''.replace('SOURCE',probe_source())
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)

    def login_boundaries(self):
        source=LoginNativeBoundary()
        def send(client,session,target,command,process):
            self.assertEqual({'running':True,'identity':'31:14'},process);source.send(command)
        def read(_device,package,path,**kwargs):
            self.assertEqual('files/overte-e2e/phone-login-ui.json',path)
            self.assertEqual({'attempts':1},kwargs);return json.dumps(source.value)
        for boundary in (
            patch.object(self.adapter,'write_android_client_command',side_effect=send),
            patch.object(self.fixture.adb,'read_debug_app_file',side_effect=read,create=True),
            patch.object(self.fixture.adb,'epoch_milliseconds',return_value=20000,create=True),
            patch.object(appium,'PhoneLoginIO',partial(appium.PhoneLoginIO,
                monotonic=lambda:source.ui.clock,sleep=source.ui.sleep)),
            patch.object(appium,'TokenLoginUI',partial(TokenLoginUI,
                monotonic=lambda:source.ui.clock,sleep=source.ui.sleep))):
            boundary.start();self.addCleanup(boundary.stop)
        return source,self.adapter._login_controls(SELECTOR,source.ui.intent,LOGIN_RUN,LOGIN_ORIGIN)

    def test_phone_login_uses_original_private_fields_and_normal_submit_without_a_success_verdict(self):
        source,ui=self.login_boundaries();ui.open();ui.fill(LOGIN_CREDS);ui.submit()
        self.assertTrue(source.ui.pending);self.assertFalse(source.ui.token)
        self.assertEqual(LOGIN_CREDS['password'],source.ui.fields['login.password'])
        self.assertNotIn(LOGIN_CREDS['password'],repr(source.commands)+repr(source.ui.intents)+repr(source.value))
        ui.cancel();ui.open();self.assertTrue(ui.capture()['controls'][0]['nativePending'])
        self.assertEqual(1,sum(action=='submit' for _,action in source.inputs))

    def test_phone_login_stale_foreign_missing_and_retimed_sources_refuse_input(self):
        for kind in ('version','reader','nonce','process','timestamp','context','error'):
            with self.subTest(kind=kind):
                source,ui=self.login_boundaries()
                def mutate(value):
                    if kind=='version':value['loginControlsVersion']=True
                    elif kind=='reader':value.pop('privateCommandReaderVersion')
                    elif kind=='nonce':value['commandId']='f'*32
                    elif kind=='process':value['processId']=999
                    elif kind=='timestamp':value['capturedEpochMs']=19999
                    elif kind=='context':value['instance']='foreign'
                    else:value['error']='copied expectation'
                source.mutate=mutate
                with self.assertRaises(RuntimeError):ui.open()
                self.assertEqual([],source.inputs)

    def test_phone_login_candidate_or_native_endpoint_change_blocks_credential_delivery(self):
        source,ui=self.login_boundaries();ui.open();count=len(source.inputs)
        self.fixture.adb.digest='f'*64
        with self.assertRaises(RuntimeError):ui.fill(LOGIN_CREDS)
        self.assertEqual(count,len(source.inputs))

    def test_phone_login_changed_native_context_between_read_and_input_refuses_old_token(self):
        source,ui=self.login_boundaries();ui.open()
        source.before_input=lambda:setattr(source.ui,'endpoint','f'*64)
        with self.assertRaises(RuntimeError):ui.fill(LOGIN_CREDS)
        self.assertEqual({},source.ui.fields)

    def test_phone_login_lost_input_receipt_never_replays_or_claims_completion(self):
        source,ui=self.login_boundaries()
        source.mutate=lambda v:v.update(commandId='e'*32) if v.get('action')=='activate' else None
        with self.assertRaises(RuntimeError):ui.open()
        self.assertTrue(source.ui.dialog);self.assertEqual(1,len(source.inputs));self.assertFalse(source.ui.token)

    def test_phone_login_uncertain_secret_input_is_replaced_by_readonly_command_without_replay(self):
        source,ui=self.login_boundaries();ui.open()
        source.mutate=lambda v:v.update(commandId='e'*32) if v.get('action')=='replace' else None
        with self.assertRaises(RuntimeError):ui.fill(LOGIN_CREDS)
        self.assertEqual(1,sum(action=='replace' for _,action in source.inputs))
        self.assertEqual('observe',source.commands[-1]['request']['action'])
        self.assertEqual({'schemaVersion','commandId','action'},set(source.commands[-1]['request']))
        self.assertEqual(3,len(source.ui.intents)) # Entry, focus and one uncertain replacement.

    def test_phone_login_source_epoch_cannot_regress_with_the_device_clock(self):
        source,ui=self.login_boundaries();ui.open()
        source.mutate=lambda v:v.update(capturedEpochMs=19900) if v.get('action')=='observe' else None
        with patch.object(self.fixture.adb,'epoch_milliseconds',return_value=19900,create=True):
            with self.assertRaises(RuntimeError):ui.capture()

    def test_original_phone_login_dispatch_rejects_extra_fields_secret_echo_and_missing_native_hook(self):
        program=r'''const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,k)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.sort());
let calls=[],files=[];
const Test={phoneLoginUi:r=>{calls.push(r);return {schemaVersion:1,commandId:r.commandId,performed:true};},
saveObject:(v,name)=>files.push({v,name})};
SOURCE
const outer=r=>({schemaVersion:1,commandId:r.commandId,action:"phone-login-ui",request:r});
const observe={schemaVersion:1,commandId:"a".repeat(32),action:"observe"};
applyAndroidControlCommand(outer(observe));applyAndroidControlCommand(outer(observe));
if(calls.length!==1 || files[0].name!=="phone-login-ui.json")throw Error("original dispatch or duplicate");
const replace={schemaVersion:1,commandId:"b".repeat(32),action:"replace",instance:"c".repeat(32),generation:"d".repeat(32),
sequence:1,observedElapsedMs:0,controlId:"login.password",controlToken:"e".repeat(32),text:"private-test-only"};
applyAndroidControlCommand(outer(replace));
if(calls.length!==2 || JSON.stringify(files).includes("private-test-only") || "text" in replace)throw Error("delivery or secret retention");
const invalidBase={...replace,text:"private-test-only"};
for(const bad of [{...invalidBase,commandId:"1".repeat(32),expected:"owned"},
 {...invalidBase,commandId:"2".repeat(32),text:"bad\ninput"}, {...invalidBase,commandId:"3".repeat(32),sequence:true},
 {...invalidBase,commandId:"4".repeat(32),controlId:"loginXpassword"},
 {...invalidBase,commandId:"5".repeat(32),action:"activate"}, {...invalidBase,commandId:"6".repeat(32),text:""}]){
 applyClientCommand(outer(bad));
}
if(calls.length!==2)throw Error("unreviewed input dispatched");
delete Test.phoneLoginUi;applyClientCommand(outer({...observe,commandId:"7".repeat(32)}));
if(files[2].v.available!==false)throw Error("missing native hook counted as delivery");
'''.replace('SOURCE',probe_source())
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)

    def test_original_phone_poll_bypasses_module_cache_and_retires_secret_even_when_native_input_throws(self):
        probe=(Path(__file__).resolve().parents[4]/'tests/device/probe/overte_e2e_probe.js').read_text()
        start=probe.index('    function pollAndroidControlCommand()')
        end=probe.index('    function pollAndroidControlMarker()',start)
        program=r'''const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,k)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.sort());
let reads=0,writes=[];
const Script={require:()=>{throw Error("CommonJS credential caching is forbidden");}};
const command={schemaVersion:1,commandId:"a".repeat(32),action:"phone-login-ui",request:{schemaVersion:1,commandId:"a".repeat(32),
action:"replace",instance:"b".repeat(32),generation:"c".repeat(32),sequence:1,observedElapsedMs:0,
controlId:"login.password",controlToken:"d".repeat(32),text:"private-uncached-test"}};
const Test={phoneReadFeatureCommand:()=>{reads++;return command;},phoneLoginUi:()=>{throw Error("unavailable native input");},
saveObject:(v,name)=>writes.push({v,name})};
SOURCE
var androidControlAvailable=true;
POLL
pollAndroidControlCommand();
if(reads!==1||writes.length!==1||writes[0].v.available!==false||"text" in command.request)throw Error("cache/secret retention or green unavailable");
'''.replace('SOURCE',probe_source()).replace('POLL',probe[start:end])
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)

    def audio_boundaries(self):
        source = AudioNativeBoundary()
        def send(client,session,target,command,process):
            self.assertEqual({'running':True,'identity':'31:14'},process); source.send(command)
        def read(_device,package,path,**kwargs):
            self.assertEqual('files/overte-e2e/phone-audio-ui.json',path)
            self.assertEqual({'attempts':1},kwargs); return json.dumps(source.value)
        for boundary in (
            patch.object(self.adapter,'write_android_client_command',side_effect=send),
            patch.object(self.fixture.adb,'read_debug_app_file',side_effect=read,create=True),
            patch.object(self.fixture.adb,'epoch_milliseconds',return_value=20000,create=True),
            patch.object(appium,'PhoneAudioIO',partial(appium.PhoneAudioIO,
                monotonic=lambda: source.ui.clock,sleep=source.ui.sleep)),
            patch.object(appium,'TokenAudioUI',partial(TokenAudioUI,
                monotonic=lambda: source.ui.clock,sleep=source.ui.sleep))):
            boundary.start(); self.addCleanup(boundary.stop)
        return source,self.adapter._audio_controls(SELECTOR,source.ui.intent)

    def test_phone_audio_ordinary_scroll_start_cancel_and_toggles_use_original_readback(self):
        source,ui = self.audio_boundaries(); ui.mute(True); ui.mute(False)
        record = ui.start(); ui.cancel(record['cycle']); ui.echo(True); ui.echo(False)
        self.assertEqual(1,source.ui.cycle); self.assertFalse(source.ui.active)
        self.assertEqual(2,source.ui.actions.count('audio.record'))
        self.assertEqual([],self.native.inputs)

    def test_phone_audio_ignored_input_and_natural_completion_cannot_prove_effect(self):
        source,ui = self.audio_boundaries(); source.ui.fault='record'
        with self.assertRaises(RuntimeError): ui.start()
        self.assertEqual(1,source.ui.actions.count('audio.record'))
        source.ui.fault=''; ui.start(); source.ui.fault='natural-completion'
        with self.assertRaises(RuntimeError): ui.cancel(1)
        self.assertEqual('completed',source.ui.phase)

    def test_phone_audio_candidate_change_refuses_before_any_native_request(self):
        source,ui = self.audio_boundaries(); self.fixture.adb.digest='f'*64
        with self.assertRaises(RuntimeError): ui.start()
        self.assertEqual([],source.commands)

    def test_phone_audio_cycle_change_before_native_delivery_refuses_old_start_token(self):
        source,ui = self.audio_boundaries(); source.ui.position=0.6
        source.before_input=lambda: setattr(source.ui,'cycle',source.ui.cycle+1)
        with self.assertRaises(RuntimeError): ui.start()
        self.assertEqual([],source.ui.actions); self.assertEqual(1,len(source.input_requests))

    def test_phone_audio_missing_reply_after_delivery_never_replays_input(self):
        source,ui = self.audio_boundaries(); source.ui.position=0.6
        def mutate(value):
            if value.get('action') != 'observe': value['commandId']='f'*32
        source.mutate=mutate
        with self.assertRaises(RuntimeError): ui.start()
        self.assertEqual(1,len(source.input_requests)); self.assertTrue(source.ui.active)

    def test_phone_audio_foreign_clock_process_generation_or_marker_prevents_input(self):
        source,ui = self.audio_boundaries(); ui.capture()
        for field,value in (('capturedEpochMs',1),('processId',99),('generation','f'*32),
                            ('audioControlsVersion',2),('sourceSequence',0)):
            with self.subTest(field=field):
                source.mutate=lambda packet: packet.update({field:value})
                with self.assertRaises(RuntimeError): ui.start()
        self.assertEqual([],source.input_requests)

    def test_actual_phone_probe_audio_is_closed_and_missing_hook_never_green(self):
        program = r'''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,keys)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(keys.sort());
let calls=[],files=[];
const Test={phoneAudioUi:r=>{calls.push(r);return {commandId:r.commandId,performed:true};},
 saveObject:(v,name)=>files.push({v,name})};
SOURCE
function outer(request){return {schemaVersion:1,commandId:request.commandId,action:"phone-audio-ui",request};}
const observe={schemaVersion:1,commandId:"a".repeat(32),action:"observe"};
applyAndroidControlCommand(outer(observe));applyAndroidControlCommand(outer(observe));
if(calls.length!==1||files[0].name!=="phone-audio-ui.json")throw Error("original dispatch");
const input={schemaVersion:1,commandId:"b".repeat(32),action:"activate",instance:"c".repeat(32),generation:"d".repeat(32),
 sequence:1,observedElapsedMs:0,controlId:"audio.record",controlToken:"e".repeat(32)};
applyAndroidControlCommand(outer(input));
for(const change of [{sequence:true},{expected:"capturing"},{controlId:"audio.page"},{action:"cancel-direct"}]){
 applyClientCommand(outer({...input,...change,commandId:"f".repeat(32)}));}
if(calls.length!==2)throw Error("untyped or extra input");
applyAndroidControlCommand(outer({...input,commandId:"1".repeat(32),action:"scroll",controlId:"audio.scrollbar",direction:"down"}));
if(calls.length!==3)throw Error("scroll missing");
delete Test.phoneAudioUi;applyClientCommand(outer({...observe,commandId:"2".repeat(32)}));
if(files[3].v.available!==false)throw Error("missing hook green");
'''.replace('SOURCE',probe_source())
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)

    def test_native_feature_reader_rejects_process_change_and_does_not_replay_request(self):
        source = self.native_feature_boundaries()
        def mutate(value):
            value['processId'] = 31
            self.native.identity = '99:foreign-process'
        source.mutate = mutate
        reader = self.adapter._native_feature_observer(SELECTOR)
        with self.assertRaises(RuntimeError): reader.read(0)
        self.assertEqual(1, len(source.commands))
        self.assertEqual(0, reader.sequence)

    def test_native_feature_reader_rejects_changed_candidate_before_delivery(self):
        source = self.native_feature_boundaries()
        reader = self.adapter._native_feature_observer(SELECTOR)
        self.fixture.adb.digest = 'f' * 64
        with self.assertRaises(RuntimeError): reader.read(0)
        self.assertEqual([], source.commands)

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
