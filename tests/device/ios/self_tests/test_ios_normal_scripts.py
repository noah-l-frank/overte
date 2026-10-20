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
from adapters.native_script_files import originals
from self_tests.test_native_script_observation import Boundary as ScriptBoundary, code_source, effect_source
from self_tests.test_native_process_presence import Boundary as PresenceBoundary
from adapters.token_graphics_ui import TokenGraphicsUI
from self_tests.test_token_graphics_ui import GraphicsBoundary
from adapters.token_audio_ui import TokenAudioUI
from self_tests.test_token_audio_ui import AudioBoundary
from self_tests.test_native_script_files import Boundary as FilesBoundary
from adapters.world_render_storage import receipt_file
from self_tests.test_world_render_evidence import Boundary as WorldBoundary
from self_tests.test_world_render_storage import Boundary as WorldStorageBoundary
from self_tests.test_native_chat_observation import Boundary as ChatBoundary, RUN as CHAT_RUN, SELF as CHAT_SELF, PEER as CHAT_PEER
from adapters.native_chat_observation import received_texts
from adapters.native_chat_view import measured_view
from self_tests.test_native_chat_view import Boundary as ChatViewBoundary
from self_tests.test_native_account_probe import Boundary as AccountProbeBoundary, RUN as ACCOUNT_RUN, TICKET as ACCOUNT_TICKET
from self_tests.test_native_account_origin import Boundary as AccountOriginBoundary, ORIGIN as ACCOUNT_ORIGIN
from self_tests.test_native_feature_observation import Boundary as NativeFeatureBoundary
from self_tests.test_native_account_observation import account_source


class Native:
    def __init__(self):
        self.qt = NativeBoundary()
        self.pid, self.running, self.deleted, self.sequence = 42, True, False, 0
        self.version = 1
        self.lifecycle = dict(backgrounds=0, activations=1, launches=1)
        self.lifecycle_inputs = []; self.on_launch = None; self.first_probe = None
        self.ignore_app_stop = self.ignore_app_launch = self.lose_stop_ack = self.lose_launch_ack = False
        self.file_ui, self.file_focus, self.file_version = None, None, 1
        self.instance = '11111111-1111-4111-8111-111111111111'
        self.elements, self.commands = {}, []
        self.fixture = FixtureState()
        self.retire_on_click = False
        self.file_source = None
        self.audio_ui = None
        self.graphics_ui = None
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
        if self.audio_ui is not None: value['controls'] = self.audio_ui.capture()['controls']
        if self.graphics_ui is not None:value['controls']=self.graphics_ui.capture()['controls']
        rows = []
        for item in value['controls']:
            row = dict(item)
            row['token'] = str(uuid.uuid5(uuid.NAMESPACE_URL, row['id'] + row.get('sourceUrl', '') + str(row.get('currentIndex', '')) + (row['token'] if self.audio_ui or self.graphics_ui else '')))
            if row['id'].startswith('script-file.') or row['id'] == 'scripts.from-file':
                row['focused'] = self.file_focus == row['id']
            row.setdefault('focused',False)
            row['frame'] = None if self.graphics_ui is not None and row.get('viewport') in ('above','below') else dict(x=10, y=20, width=200, height=48)
            rows.append(row)
        return rows

    def observed(self):
        value = dict(schemaVersion=1, instance=self.instance, frameSpace='qt-window-logical', processId=self.pid,
            sampleEpochMs=self.epoch(), elapsedMs=int(self.qt.clock * 1000), lastSequence=self.sequence,
            tabletShown=self.qt.opened, ready=True, controls=self.controls(), featureControlsVersion=self.version, fileControlsVersion=self.file_version)
        if self.audio_ui is not None: value['audioControlsVersion'] = self.audio_ui.capture()['audioControlsVersion']
        if self.graphics_ui is not None:value['graphicsControlsVersion']=self.graphics_ui.capture()['graphicsControlsVersion']
        return value

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
                assert field['focused'] or native['operation'] in ('scroll','set-value')
                if native['operation']=='set-value':
                    original=next(r for r in self.graphics_ui.capture()['controls'] if r['id']==field['id'])
                    self.graphics_ui.set_value(field['id'],native['value'],token=original['token'])
                elif native['operation'] == 'scroll':
                    owner=self.graphics_ui if field['id']=='graphics.scrollbar' else self.audio_ui
                    original=next(r for r in owner.capture()['controls'] if r['id']==field['id'])
                    owner.scroll(field['id'],native['direction'],token=original['token'])
                elif field['id'] == 'scripts.url.field': self.qt.replace(field['id'], native['text'])
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
        elif command['action'] == 'idle': pass
        else:
            raise AssertionError('Unexpected synthetic native request')
        return self

    def read(self, limit): return self.echo[:limit]
    status = 200
    def __enter__(self): return self
    def __exit__(self, *_args): return False

    def execute(self, session, operation, values):
        if operation == 'mobile: overteProcessInfo': return self.process()
        if operation == 'mobile: queryAppState': return 4 if self.running else 1
        if operation == 'mobile: terminateApp':
            assert values == {'bundleId': self.target['appId']}
            self.lifecycle_inputs.append('stop')
            if not self.ignore_app_stop and self.running:
                self.running = False; self.lifecycle['backgrounds'] += 1
            if self.lose_stop_ack: raise RuntimeError('synthetic lost stop SDK receipt')
            return None
        if operation == 'mobile: launchApp':
            contract = self.target['testBuild']; origin = contract['fixtureOrigin']
            assert values == {'bundleId': self.target['appId'], 'arguments': [
                '--url', origin + contract['scenePath'], '--testScript', origin + component.AppiumAdapter.IOS_PROBE_SCRIPT_PATH,
                '--testResultsLocation', contract['resultsDirectory']], 'environment': {}}
            self.lifecycle_inputs.append('launch')
            if not self.ignore_app_launch and not self.running:
                assert self.on_launch is not None
                self.on_launch(); self.running = True
                self.lifecycle['activations'] += 1; self.lifecycle['launches'] += 1
                from ios.self_tests.test_appium_adapter import snapshot
                self.first_probe = snapshot(sampled=self.epoch())
            if self.lose_launch_ack: raise RuntimeError('synthetic lost launch SDK receipt')
            return None
        assert operation == 'mobile: pullFile'
        root = '@org.example.client:documents/owned-results/'
        name = values['remotePath'].removeprefix(root)
        if name == 'overte-probe.json':
            assert self.first_probe is not None
            return base64.b64encode(json.dumps(self.first_probe).encode()).decode()
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
        if self.graphics_ui is not None and (name in ('graphics.page','graphics.scrollbar','graphics.resolution')
                or rows and rows[0].get('viewport')!='visible'):return None
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
            if name.startswith('graphics.') or name=='settings.entry' and self.graphics_ui is not None:
                original=next(r for r in self.graphics_ui.capture()['controls'] if r['id']==name)
                self.graphics_ui.activate(name,token=original['token'])
            elif name.startswith('audio.') or name == 'settings.entry':
                original=next(r for r in self.audio_ui.capture()['controls'] if r['id']==name)
                self.audio_ui.activate(name,token=original['token'])
            elif name.startswith('script-file.') or name == 'scripts.from-file':
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

    def graphics_controls(self):
        self.native.graphics_ui=GraphicsBoundary(generic=True);self.native.qt.opened=True
        native=self.native.graphics_ui
        boundary=patch('adapters.token_graphics_ui.TokenGraphicsUI',partial(TokenGraphicsUI,
            monotonic=lambda:native.clock,sleep=native.sleep))
        boundary.start();self.addCleanup(boundary.stop)
        return native,self.adapter._graphics_controls('test-only-selector',native.intent)

    def account_origin(self):
        source=AccountOriginBoundary(self.path.parent/'native-origin-files');native=NativeFeatureBoundary()
        source.mutate=lambda value:value.update(processId=42)
        def feature(value):value.update(processId=42);account_source(value)
        native.mutate=feature
        original_post=self.native.post;original_execute=self.native.execute
        def post(request,timeout):
            value=json.loads(request.data)
            if value['action']=='feature-native-observe':native.send(value)
            elif value['action']=='feature-account-origin':
                self.assertEqual(native.sample['instance'],value['instance'])
                self.assertIsNotNone(self.adapter.account_origin_store('test-only-selector').read());source.send(value)
            else:return original_post(request,timeout)
            self.native.fixture.set_client_command(value);self.native.echo=json.dumps(value).encode();return self.native
        def execute(session,operation,values):
            if operation=='mobile: pullFile':
                remote=values['remotePath'];prefix='@org.example.client:documents/owned-results/'
                if remote==prefix+'feature-native-observation.json':return base64.b64encode(native.original().encode()).decode()
                if remote==prefix+'feature-account-origin-result.json':return base64.b64encode(source.read().encode()).decode()
            return original_execute(session,operation,values)
        for boundary in (patch.object(feature_observation,'post_request',side_effect=post),
            patch.object(self.native,'execute',side_effect=execute),
            patch.object(component,'FeatureObservation',partial(feature_observation.FeatureObservation,
                monotonic=lambda:source.clock,sleep=source.sleep))):
            boundary.start();self.addCleanup(boundary.stop)
        return source,native,self.adapter._account_origin('test-only-selector')

    def test_ios_account_origin_component_uses_original_afc_files_and_actual_native_scope(self):
        source,native,origin=self.account_origin();self.assertEqual(ACCOUNT_ORIGIN,origin.stage(ACCOUNT_RUN,ACCOUNT_ORIGIN))
        self.assertEqual(native.sample['instance'],self.adapter.account_origin_store('test-only-selector').read()['instance'])
        origin.release();self.assertFalse(source.path.exists());self.assertIsNone(self.adapter.account_origin_store('test-only-selector').read())
        self.assertEqual([],self.native.qt.inputs)

    def test_ios_account_origin_component_ack_without_files_keeps_owner(self):
        source,_native,origin=self.account_origin();source.fault='ack-only'
        with self.assertRaises(RuntimeError):origin.stage(ACCOUNT_RUN,ACCOUNT_ORIGIN)
        self.assertIsNotNone(self.adapter.account_origin_store('test-only-selector').read());origin.release()
        self.assertIsNone(self.adapter.account_origin_store('test-only-selector').read())

    def test_ios_account_origin_component_foreign_native_context_cannot_adopt_owned_files(self):
        source,native,origin=self.account_origin();origin.stage(ACCOUNT_RUN,ACCOUNT_ORIGIN);original=native.mutate
        def foreign(value):original(value);value['instance']='f'*32
        native.mutate=foreign;before=len(source.commands)
        with self.assertRaises(RuntimeError):self.adapter._account_origin('test-only-selector').release()
        self.assertEqual(before,len(source.commands));self.assertIsNotNone(self.adapter.account_origin_store('test-only-selector').read())

    def test_ios_account_origin_component_cleanup_retires_files_before_base_teardown(self):
        source,_native,origin=self.account_origin();origin.stage(ACCOUNT_RUN,ACCOUNT_ORIGIN)
        self.assertEqual({'cleaned':True},self.adapter.cleanup('test-only-selector'))
        self.assertFalse(self.native.running);self.assertFalse(source.path.exists())
        self.assertIsNone(self.adapter.account_origin_store('test-only-selector').read())

    def test_ios_account_origin_component_cleanup_keeps_files_when_independent_absence_fails(self):
        source,_native,origin=self.account_origin();origin.stage(ACCOUNT_RUN,ACCOUNT_ORIGIN);source.fault='keep-files'
        with self.assertRaises(RuntimeError):self.adapter.cleanup('test-only-selector')
        self.assertFalse(self.native.running);self.assertTrue(source.path.exists());self.assertIsNotNone(self.adapter.account_origin_store('test-only-selector').read())

    def chat_view(self):
        source=ChatViewBoundary();source.mutate=lambda value:value.update(processId=42)
        original_post=self.native.post;original_execute=self.native.execute
        def post(request,timeout):
            value=json.loads(request.data)
            if value['action']!='feature-chat-view-observe':return original_post(request,timeout)
            self.native.fixture.set_client_command(value);self.native.echo=json.dumps(value).encode();source.send(value)
            return self.native
        def execute(session,operation,values):
            if operation=='mobile: pullFile' and values['remotePath']=='@org.example.client:documents/owned-results/feature-chat-view-observation.json':
                return base64.b64encode(source.read().encode()).decode()
            return original_execute(session,operation,values)
        for boundary in (patch.object(feature_observation,'post_request',side_effect=post),
            patch.object(self.native,'execute',side_effect=execute),
            patch.object(component,'FeatureObservation',partial(feature_observation.FeatureObservation,
                monotonic=lambda:source.clock,sleep=source.sleep))):
            boundary.start();self.addCleanup(boundary.stop)
        return source,self.adapter._chat_view('test-only-selector')

    def test_ios_chat_view_original_afc_ui_and_storage_retain_native_epoch(self):
        source,reader=self.chat_view();value=reader.read(CHAT_RUN)
        self.assertEqual(42,value['processId']);self.assertEqual(20000,value['capturedEpochMs'])
        self.assertEqual('domain',measured_view(value)['channel']);self.assertEqual(2,len(value['source']['storage']['events']))
        self.assertTrue(value['commandId'].startswith('ios-'));self.assertEqual([],self.native.qt.inputs)

    def test_ios_chat_view_ignored_or_foreign_source_and_session_loss_refuse_results(self):
        source,reader=self.chat_view();source.ignored=True
        with self.assertRaises(RuntimeError):reader.read(CHAT_RUN)
        self.assertEqual(1,len(source.commands));self.assertLessEqual(source.clock,5)
        source.ignored=False;source.mutate=lambda value:value.update(processId=43)
        with self.assertRaises(RuntimeError):reader.read(CHAT_RUN)
        before=len(source.commands);self.native.deleted=True
        with self.assertRaises(RuntimeError):reader.read(CHAT_RUN)
        self.assertEqual(before,len(source.commands))

    def test_ios_chat_view_canonical_binding_refuses_before_target_or_transport(self):
        from types import SimpleNamespace
        from adapters.ios import binding
        with patch.object(component.AppiumAdapter,'load_targets',return_value={}):
            adapter=binding.create_adapter(SimpleNamespace(platform='ios',action='cleanup'),component.AppiumAdapter)
        with patch.object(adapter,'ensure_session') as session:
            with self.assertRaisesRegex(ValueError,'OVT_IOS_INSTALLED_CODE_BINDING_UNAVAILABLE'):adapter._chat_view('private-selector')
            session.assert_not_called()

    def chat_capture(self):
        source=ChatBoundary();source.store=self.adapter.chat_capture_store('test-only-selector')
        source.mutate=lambda value:value.update(processId=42)
        original_post=self.native.post;original_execute=self.native.execute
        def post(request,timeout):
            value=json.loads(request.data)
            if value['action']!='feature-chat-observe':return original_post(request,timeout)
            self.native.fixture.set_client_command(value);self.native.echo=json.dumps(value).encode();source.send(value)
            return self.native
        def execute(session,operation,values):
            if operation=='mobile: pullFile' and values['remotePath']=='@org.example.client:documents/owned-results/feature-chat-observation.json':
                return base64.b64encode(source.read().encode()).decode()
            return original_execute(session,operation,values)
        for boundary in (patch.object(feature_observation,'post_request',side_effect=post),
            patch.object(self.native,'execute',side_effect=execute),
            patch.object(component,'FeatureObservation',partial(feature_observation.FeatureObservation,
                monotonic=lambda:source.clock,sleep=source.sleep))):
            boundary.start();self.addCleanup(boundary.stop)
        return source,self.adapter._chat_capture('test-only-selector',CHAT_RUN)

    def test_ios_chat_factory_preserves_original_afc_reception_and_native_epoch(self):
        source,capture=self.chat_capture();capture.observe();source.event();value=capture.observe()
        self.assertEqual(42,value['processId']);self.assertEqual(20000,value['capturedEpochMs'])
        self.assertEqual(1,len(received_texts(value,sender_sha256=CHAT_PEER,receiver_sha256=CHAT_SELF,channel='domain')))
        self.assertTrue(value['commandId'].startswith('ios-'))
        self.assertEqual('NATIVE_UI_COMPONENT_ONLY',self.adapter.chat_capture_store('test-only-selector').read()['binding']['scope'])
        capture.retire();self.assertIsNone(self.adapter.chat_capture_store('test-only-selector').read());self.assertEqual([],self.native.qt.inputs)

    def test_ios_chat_local_echo_and_foreign_source_never_become_remote_delivery(self):
        source,capture=self.chat_capture();capture.observe();source.event(local=True);value=capture.observe()
        self.assertEqual([],received_texts(value,sender_sha256=CHAT_PEER,receiver_sha256=CHAT_SELF,channel='domain'))
        source.mutate=lambda value:value.update(processId=42,instance='f'*32)
        with self.assertRaises(RuntimeError):self.adapter._chat_capture('test-only-selector',CHAT_RUN).retire()
        self.assertIsNotNone(self.adapter.chat_capture_store('test-only-selector').read())
        self.assertFalse(any(c['operation']=='retire' for c in source.commands))

    def test_ios_chat_session_replacement_blocks_dispatch_and_keeps_intent(self):
        source,capture=self.chat_capture();capture.observe();before=len(source.commands);self.native.deleted=True
        with self.assertRaises((ValueError,RuntimeError)):capture.observe()
        self.assertEqual(before,len(source.commands));self.assertIsNotNone(self.adapter.chat_capture_store('test-only-selector').read())

    def test_ios_chat_cleanup_retires_actual_cache_before_original_teardown(self):
        source,capture=self.chat_capture();capture.observe();source.event()
        self.adapter.cleanup('test-only-selector')
        self.assertFalse(self.native.running);self.assertEqual(2,source.inspect_after_retire)
        self.assertIsNone(self.adapter.chat_capture_store('test-only-selector').read())

    def test_ios_chat_failed_cleanup_reaches_base_teardown_and_refuses_green(self):
        source,capture=self.chat_capture();capture.observe();source.ignore_retire=True
        with self.assertRaises(RuntimeError):self.adapter.cleanup('test-only-selector')
        self.assertFalse(self.native.running);self.assertTrue(source.present)
        self.assertIsNotNone(self.adapter.chat_capture_store('test-only-selector').read())

    def test_ios_canonical_binding_explicitly_refuses_chat_factory_before_io(self):
        from types import SimpleNamespace
        from adapters.ios import binding
        with patch.object(component.AppiumAdapter,'load_targets',return_value={}):
            adapter=binding.create_adapter(SimpleNamespace(platform='ios',action='cleanup'),component.AppiumAdapter)
        with self.assertRaisesRegex(ValueError,'OVT_IOS_INSTALLED_CODE_BINDING_UNAVAILABLE'):adapter._chat_capture('private-selector',CHAT_RUN)

    def account_probe(self):
        source=AccountProbeBoundary();source.mutate=lambda value:value.update(processId=42)
        original_post=self.native.post;original_execute=self.native.execute
        def post(request,timeout):
            value=json.loads(request.data)
            if value['action']!='feature-account-probe':return original_post(request,timeout)
            self.native.fixture.set_client_command(value);self.native.echo=json.dumps(value).encode()
            owner=self.adapter.account_probe_store('test-only-selector').read()
            self.assertEqual(value['requestId'],owner['probe']['commandId']);source.send(value)
            return self.native
        def execute(session,operation,values):
            if operation=='mobile: pullFile' and values['remotePath']=='@org.example.client:documents/owned-results/feature-account-probe.json':
                return base64.b64encode(source.read().encode()).decode()
            return original_execute(session,operation,values)
        for boundary in (patch.object(feature_observation,'post_request',side_effect=post),
            patch.object(self.native,'execute',side_effect=execute),
            patch.object(component,'FeatureObservation',partial(feature_observation.FeatureObservation,
                monotonic=lambda:source.clock,sleep=source.sleep))):
            boundary.start();self.addCleanup(boundary.stop)
        return source,self.adapter._account_probe('test-only-selector')

    def test_ios_protected_probe_component_uses_actual_afc_and_native_clock_with_private_owner(self):
        source,probe=self.account_probe();value=probe.acquire(ACCOUNT_RUN,ACCOUNT_TICKET)
        self.assertEqual(42,value['processId']);self.assertEqual(20000,value['capturedEpochMs'])
        self.assertTrue(value['commandId'].startswith('ios-'))
        probe.release();self.assertIsNone(self.adapter.account_probe_store('test-only-selector').read())
        self.assertEqual([],self.native.qt.inputs)

    def test_ios_protected_probe_component_undrained_reply_keeps_owner(self):
        source,probe=self.account_probe();probe.acquire(ACCOUNT_RUN,ACCOUNT_TICKET);source.pending=True
        with self.assertRaises(RuntimeError):probe.release()
        self.assertIsNotNone(self.adapter.account_probe_store('test-only-selector').read())
        source.pending=False;probe.release();self.assertIsNone(self.adapter.account_probe_store('test-only-selector').read())

    def test_ios_protected_probe_component_replaced_process_cannot_retire_original_owner(self):
        source,probe=self.account_probe();probe.acquire(ACCOUNT_RUN,ACCOUNT_TICKET)
        self.native.pid=43;before=len(source.commands)
        with self.assertRaises(RuntimeError):probe.release()
        self.assertEqual(before,len(source.commands));self.assertIsNotNone(self.adapter.account_probe_store('test-only-selector').read())

    def test_ios_component_cleanup_drains_probe_before_original_app_teardown(self):
        source,probe=self.account_probe();probe.acquire(ACCOUNT_RUN,ACCOUNT_TICKET)
        self.assertEqual({'cleaned':True},self.adapter.cleanup('test-only-selector'))
        self.assertFalse(self.native.running);self.assertIsNone(self.adapter.account_probe_store('test-only-selector').read())

    def test_ios_component_cleanup_runs_base_but_retains_an_undrained_probe(self):
        source,probe=self.account_probe();probe.acquire(ACCOUNT_RUN,ACCOUNT_TICKET);source.pending=True
        with self.assertRaises(RuntimeError):self.adapter.cleanup('test-only-selector')
        self.assertFalse(self.native.running);self.assertIsNotNone(self.adapter.account_probe_store('test-only-selector').read())

    def world_capture(self):
        source=WorldBoundary();source.mutate=lambda sample:sample.update(processId=42)
        storage=WorldStorageBoundary();storage.raw=source.raw
        storage.mutate=lambda sample:sample.update(instance='a'*32,processId=42)
        root=self.path.parent/'remote-results';root.mkdir(mode=0o700)
        state=dict(sequence=0,receipt=None,ignore_remove=False)
        original_post=self.native.post;original_execute=self.native.execute
        def post(request,timeout):
            value=json.loads(request.data)
            if not value['action'].startswith('feature-world-render-'):return original_post(request,timeout)
            self.native.fixture.set_client_command(value);self.native.echo=json.dumps(value).encode()
            owner=self.adapter.world_render_store('test-only-selector').read()
            self.assertEqual(value.get('requestId',value['commandId']),owner['capture']['commandId'])
            if value['action']=='feature-world-render-observe':source.intents.append(value);source.send(value)
            elif value['action']=='feature-world-render-storage':
                self.assertIn(value['commandId'],owner['receipts']);storage.intents.append(value);storage.send(value)
                name=receipt_file(value['commandId']);(root/name).write_text(storage.files[name])
            else:
                self.assertIn(value['receiptId'],[c['commandId'] for c in storage.commands])
                file=root/receipt_file(value['receiptId']);state['sequence']+=1
                if value['operation']=='remove':
                    if not state['ignore_remove']:file.unlink(missing_ok=True)
                    measured=dict(performed=True)
                else:measured=dict(exists=file.exists())
                state['receipt']=dict(receiptVersion=1,commandId=value['commandId'],requestId=value['requestId'],
                    receiptId=value['receiptId'],operation=value['operation'],instance='a'*32,sequence=state['sequence'],
                    processId=42,capturedEpochMs=20000,source=measured)
            return self.native
        def execute(session,operation,values):
            remote=values.get('remotePath','')
            prefix='@org.example.client:documents/owned-results/world-render-'
            if operation!='mobile: pullFile' or not remote.startswith(prefix):return original_execute(session,operation,values)
            name=remote.rsplit('/',1)[1]
            if name=='world-render-observation.json':raw=source.original()
            elif name=='world-render-receipt-result.json':raw=json.dumps(state['receipt'])
            else:raw=(root/name).read_text()
            return base64.b64encode(raw.encode()).decode()
        for boundary in (patch.object(feature_observation,'post_request',side_effect=post),
            patch.object(self.native,'execute',side_effect=execute),
            patch.object(component,'FeatureObservation',partial(feature_observation.FeatureObservation,
                monotonic=lambda:source.clock,sleep=source.sleep))):
            boundary.start();self.addCleanup(boundary.stop)
        return source,state,root,self.adapter._world_render_capture('test-only-selector')

    def test_ios_world_component_original_bytes_and_independent_native_receipt_cleanup(self):
        source,state,root,capture=self.world_capture();value,raw=capture.read(0)
        self.assertEqual(source.raw,raw);self.assertEqual(42,value['processId'])
        self.assertEqual('NATIVE_UI_COMPONENT_ONLY',capture.owner.binding['scope'])
        capture.release();self.assertEqual([],list(root.iterdir()))
        self.assertIsNone(self.adapter.world_render_store('test-only-selector').read())

    def test_ios_world_ignored_native_unlink_keeps_original_receipts_and_owner_for_recovery(self):
        source,state,root,capture=self.world_capture();capture.read(0);state['ignore_remove']=True
        with self.assertRaises(NativeUIError):capture.release()
        self.assertTrue(list(root.iterdir()));self.assertIsNotNone(self.adapter.world_render_store('test-only-selector').read())
        state['ignore_remove']=False;capture.release();self.assertIsNone(self.adapter.world_render_store('test-only-selector').read())

    def test_ios_world_session_or_process_replacement_cannot_adopt_original_acquisition(self):
        source,state,root,capture=self.world_capture();capture.read(0);self.state['generation']+=1
        with self.assertRaises(RuntimeError):capture.release()
        self.assertIsNotNone(self.adapter.world_render_store('test-only-selector').read());self.assertTrue(list(root.iterdir()))

    def test_ios_graphics_actual_slider_scroll_and_uikit_toggles_restore_originals(self):
        native,ui=self.graphics_controls();native.flick_duration=0.3;initial=native.resolution
        ui.set_resolution(0.5);ui.set_resolution(0.8);ui.set_resolution(initial)
        ui.toggle('graphics.haze',True);ui.toggle('graphics.mirrors',True)
        ui.toggle('graphics.haze',False);ui.toggle('graphics.mirrors',False)
        self.assertEqual(initial,native.resolution);self.assertFalse(native.haze);self.assertFalse(native.mirrors)
        edits=[c['input'] for c in self.native.commands if c.get('operation')=='edit']
        self.assertEqual(3,sum(c['operation']=='set-value' for c in edits))
        self.assertIsNone(self.native.element('OverteNavigation.graphics.resolution'))
        self.assertIsNone(self.native.element('OverteNavigation.graphics.page'))

    def test_ios_graphics_ignored_slider_and_ui_only_readback_cannot_prove_effect(self):
        native,ui=self.graphics_controls();native.fault='resolution'
        with self.assertRaises(NativeUIError):ui.set_resolution(0.5)
        self.assertEqual(0.6,native.resolution);native.fault='ui-only'
        with self.assertRaises(NativeUIError):ui.set_resolution(0.5)
        self.assertEqual(0.6,native.resolution);self.assertEqual(2,native.actions.count('resolution'))

    def test_ios_graphics_retired_original_token_is_refused_before_native_slider_input(self):
        native,ui=self.graphics_controls();row=ui.visible('graphics.resolution');native.resolution=0.7
        before=len(self.native.commands);actions=list(native.actions)
        with self.assertRaises(NativeUIError):ui.io.set_value('graphics.resolution',0.5,token=row['token'])
        self.assertFalse(any(c.get('operation')=='edit' for c in self.native.commands[before:]))
        self.assertEqual(actions,native.actions)

    def test_ios_graphics_process_session_and_source_loss_prevent_new_input(self):
        native,ui=self.graphics_controls();ui.capture();self.native.pid=99
        with self.assertRaises(RuntimeError):ui.toggle('graphics.haze',True)
        self.assertEqual([],native.actions);self.native.pid=42
        native.transform=lambda value:dict(value,graphicsControlsVersion=2)
        with self.assertRaises(RuntimeError):ui.set_resolution(0.5)
        self.assertEqual([],native.actions)
        native.transform=lambda value:value;self.state['generation']+=1
        with self.assertRaises(RuntimeError):ui.set_resolution(0.5)
        self.assertEqual([],native.actions)

    def test_ios_graphics_offscreen_rows_are_read_only_and_cannot_forge_clickable_frames(self):
        native,ui=self.graphics_controls();value=ui.capture()
        row=next(r for r in value['controls'] if r['id']=='graphics.resolution')
        self.assertEqual('below',row['viewport']);self.assertIsNone(row['frame'])
        self.assertIsNone(self.native.element('OverteNavigation.graphics.mirrors'))
        row['frame']=dict(x=10,y=20,width=200,height=48)
        with self.assertRaises(NativeUIError):normal_input.observation(value,42,self.native.epoch())
        row['frame']=None;row['viewport']='visible'
        with self.assertRaises(NativeUIError):normal_input.observation(value,42,self.native.epoch())
        self.assertEqual([],native.actions)

    def audio_controls(self):
        self.native.audio_ui=AudioBoundary();self.native.qt.opened=True
        native=self.native.audio_ui
        boundary=patch('adapters.token_audio_ui.TokenAudioUI',partial(TokenAudioUI,
            monotonic=lambda: native.clock,sleep=native.sleep))
        boundary.start();self.addCleanup(boundary.stop)
        return native,self.adapter._audio_controls('test-only-selector',native.intent)

    def test_ios_audio_original_uikit_token_start_cancel_scroll_and_toggles(self):
        native,ui=self.audio_controls();ui.mute(True);ui.mute(False)
        record=ui.start();ui.cancel(record['cycle']);ui.echo(True);ui.echo(False)
        self.assertEqual('cancelled',native.phase);self.assertFalse(native.active)
        self.assertEqual(2,native.actions.count('audio.record'))
        edits=[c['input'] for c in self.native.commands if c.get('operation')=='edit']
        self.assertEqual(['scroll'],[c['operation'] for c in edits])

    def test_ios_audio_ignored_start_cancel_scroll_and_echo_do_not_prove_effect(self):
        native,ui=self.audio_controls();native.fault='scroll'
        with self.assertRaises(NativeUIError):ui.start()
        native.fault='record';native.position=0.6
        with self.assertRaises(NativeUIError):ui.start()
        native.fault='';ui.start();native.fault='natural-completion'
        with self.assertRaises(NativeUIError):ui.cancel(1)
        native.fault='echo'
        with self.assertRaises(NativeUIError):ui.echo(True)
        self.assertEqual(3,native.actions.count('audio.record'));self.assertFalse(native.echo)

    def test_ios_audio_original_token_cannot_be_replaced_by_new_cycle(self):
        native,ui=self.audio_controls();native.position=0.6
        row=ui.visible('audio.record');native.cycle+=1
        with self.assertRaises(RuntimeError):ui.io.activate('audio.record',token=row['token'])
        self.assertEqual([],native.actions)

    def test_ios_audio_process_and_session_changes_refuse_before_input(self):
        native,ui=self.audio_controls();ui.capture();self.native.pid=99
        with self.assertRaises(RuntimeError):ui.start()
        self.assertEqual([],native.actions)
        self.native.pid=42;self.state['generation']+=1
        with self.assertRaises(RuntimeError):ui.start()
        self.assertEqual([],native.actions)

    def test_ios_audio_missing_version_and_blocked_intent_prevent_input(self):
        native,ui=self.audio_controls();native.transform=lambda v:dict(v,audioControlsVersion=2)
        with self.assertRaises(RuntimeError):ui.start()
        native.transform=lambda v:v;native.fault='intent';native.position=0.6
        with self.assertRaises(NativeUIError):ui.start()
        self.assertEqual([],native.actions)

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
        source.mutate = lambda value: value.update(processId=42)
        clock = NativeFeatureBoundary(); clock.mutate = lambda value: value.update(processId=42)
        original_post, original_execute = self.native.post, self.native.execute
        def post(request, timeout):
            command = json.loads(request.data)
            if command['action'] != 'feature-native-observe': return original_post(request, timeout)
            clock.send(command); self.native.fixture.set_client_command(command)
            self.native.echo = json.dumps(command).encode(); return self.native
        def execute(session, operation, values):
            if operation == 'mobile: pullFile' and values == {
                    'remotePath': '@org.example.client:documents/owned-results/feature-native-observation.json'}:
                return base64.b64encode(clock.original().encode()).decode()
            return original_execute(session, operation, values)
        for boundary in (patch.object(feature_observation, 'post_request', side_effect=post),
                patch.object(self.native, 'execute', side_effect=execute),
                patch.object(component, 'FeatureObservation', partial(feature_observation.FeatureObservation,
                    monotonic=lambda: source.clock, sleep=source.sleep))):
            boundary.start(); self.addCleanup(boundary.stop)
        return source, self.adapter._script_files('test-only-selector')

    def file_manager(self):
        source, files = self.file_storage(); files.stage('a' * 32)
        self.native.file_ui = FileBoundary(source.root)
        original = self.native.file_ui.activate
        def input(identifier, **kwargs):
            state = self.adapter.script_store('test-only-selector').read()
            if identifier == 'scripts.from-file':
                self.assertTrue(state['pickerOwned']); self.native.file_ui.chosen = []
            if identifier == 'script-file.confirm': self.assertTrue(state['loadAttempted'])
            original(identifier, **kwargs)
            if identifier == 'script-file.confirm' and self.native.file_ui.accepted:
                actual = self.native.file_ui.accepted[-1]; self.native.qt.rows.append(dict(url=actual, path=actual))
        self.native.file_ui.activate = input
        boundary = patch.object(component, 'TokenScriptFilePicker', partial(TokenScriptFilePicker,
            monotonic=lambda: self.native.file_ui.clock, sleep=self.native.file_ui.sleep))
        boundary.start(); self.addCleanup(boundary.stop)
        return source, files, self.adapter._script_file_manager('test-only-selector')

    def test_ios_file_manager_journals_normal_selection_and_separate_native_file_absence(self):
        source, files, manager = self.file_manager()
        manager.open(); manager.file_picker_open(); manager.file_picker_cancel()
        manager = self.adapter._script_file_manager('test-only-selector')
        manager.file_picker_open(); manager.file_picker_choose('script-bundle/main.js')
        actual = self.native.file_ui.accepted[-1]
        self.assertEqual((source.root / 'script-bundle/main.js').as_uri(), actual)
        manager.stop_source(actual); manager.close()
        self.assertIsNone(self.adapter.script_store('test-only-selector').read())
        self.assertTrue(source.root.exists()); files.release(); self.assertFalse(source.root.exists())
        self.assertFalse(any(cap.startswith('feature.') for cap in self.adapter.advertised_capabilities(self.native.target)))

    def test_ios_file_manager_process_loss_blocks_input_and_preserves_original_intents(self):
        source, files, manager = self.file_manager(); manager.open(); manager.file_picker_open()
        before = (len(self.native.commands), len(source.commands)); self.native.pid = 43
        with self.assertRaises(RuntimeError): manager.file_picker_choose('script.js')
        self.assertEqual(before, (len(self.native.commands), len(source.commands)))
        self.assertTrue(self.adapter.script_store('test-only-selector').read()['pickerOwned'])
        self.assertIsNotNone(files.store.read())

    def test_ios_unbound_file_manager_runtime_and_storage_cannot_bypass_installed_source_gate(self):
        from types import SimpleNamespace
        from adapters.ios import binding
        with patch.object(component.AppiumAdapter, 'load_targets', return_value={}):
            adapter = binding.create_adapter(SimpleNamespace(platform='ios', action='cleanup'), component.AppiumAdapter)
        for method, arguments in (('_script_runtime', ('private-selector',)),
                ('_script_file_manager', ('private-selector',)), ('_bound_script_files', ('private-selector', None, None)),
                ('_script_restart_prepare', ('private-selector',)), ('_script_restart_adopt', ('private-selector',)),
                ('_script_restart_handoff', ('private-selector',)), ('_script_restart', ('private-selector',)),
                ('_script_restart_inputs', ('private-selector',)), ('_script_restart_source', ('private-selector',)),
                ('_script_restart_session', ('private-selector',)), ('_script_restart_stopped', ('private-selector',))):
            with self.subTest(method=method), self.assertRaisesRegex(ValueError, 'INSTALLED_CODE_BINDING_UNAVAILABLE'):
                getattr(adapter, method)(*arguments)

    def restart_sources(self, *, staged_restart=True):
        if not staged_restart:
            self.native.target['testBuild'].update(scenePath='/scene.json', launchEnvironment={})
            self.native.target['capabilities'] = {'appium:autoLaunch': False}
            self.state['targetFingerprint'] = hashlib.sha256(json.dumps(self.native.target,
                sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        storage, files, manager = self.file_manager()
        manager.open(); manager.file_picker_open(); manager.file_picker_choose('script-bundle/main.js')
        source = ScriptBoundary(); source.engine['url'] = storage.root.as_uri() + '/script-bundle/main.js'
        source.engine['required']['modules'][0]['url'] = storage.root.as_uri() + '/script-bundle/companion.js'
        clock = NativeFeatureBoundary(); presence = PresenceBoundary(pid=43, epoch_ms=self.native.epoch)
        presence.presence = 'absent'; state = {'restarted': False, 'replay': False}
        def metadata(packet):
            packet.update(processId=self.native.pid, instance=('a' if state['restarted'] else 'd') * 32,
                requestedEpochMs=self.native.epoch(), capturedEpochMs=self.native.epoch())
        storage.mutate = metadata
        def clock_metadata(packet):
            metadata(packet)
            packet['animationFence']['requestedEpochMs'] = packet['requestedEpochMs']
            packet['lifecycle'] = dict(self.native.lifecycle)
        clock.mutate = clock_metadata
        def enrich(packet):
            metadata(packet); code_source(packet, originals('a' * 32)['script-bundle/main.js'].decode())
            effect_source(packet)
            row = packet['source']['effects']['entities'][0]
            row['name'] = 'e2e-' + 'a' * 32 + '-script'; row['userData'] = json.dumps(dict(runId='a' * 32, ticks=2))
            packet['source'].update(loadSourceVersion=1,
                loads=dict(complete=True, instance='7' * 32, sequence=0, events=[]))
            if state['restarted'] and not state['replay']:
                packet['source']['engines'] = []; packet['source']['effects'].update(scannedEntities=0, entities=[])
        source.mutate = enrich
        original_post, original_execute = self.native.post, self.native.execute
        def post(request, timeout):
            command = json.loads(request.data)
            producer = {'feature-native-observe': clock, 'feature-script-observe': source,
                        'feature-process-presence': presence}.get(command['action'])
            if producer is None:
                result = original_post(request, timeout)
                if command['action'] == 'normal-feature-observe' and state['restarted']:
                    self.native.diagnostic['instance'] = '9' * 32
                return result
            producer.send(command); self.native.fixture.set_client_command(command)
            self.native.echo = json.dumps(command).encode(); return self.native
        def execute(session, operation, values):
            if operation == 'mobile: pullFile':
                name = values['remotePath'].rsplit('/', 1)[-1]
                producer = {'feature-native-observation.json': clock,
                            'feature-script-observation.json': source,
                            'feature-process-presence.json': presence}.get(name)
                if producer is not None: return base64.b64encode(producer.original().encode()).decode()
            return original_execute(session, operation, values)
        for boundary in (patch.object(feature_observation, 'post_request', side_effect=post),
                         patch.object(self.native, 'execute', side_effect=execute),
                         patch.object(appium_adapter, 'urlopen', side_effect=self.native.post)):
            boundary.start(); self.addCleanup(boundary.stop)
        def transition():
            state['restarted'] = True; self.native.pid = 43; self.native.instance = str(uuid.uuid4())
            self.native.qt.opened = False; self.native.qt.page = 'home'; self.native.qt.rows = []
            self.native.file_ui.opened = False
        self.native.on_launch = transition
        if staged_restart:
            self.adapter._script_restart_prepare('test-only-selector'); transition()
            self.state.update(processIdentity='43', generation=2)
        return storage, source, presence, state

    def test_ios_normal_restart_uses_one_sdk_stop_launch_original_lifecycle_probe_and_file_handoff(self):
        storage, _source, _presence, _state = self.restart_sources(staged_restart=False)
        result = self.adapter._script_restart('test-only-selector')
        self.assertEqual(['stop', 'launch'], self.native.lifecycle_inputs)
        self.assertEqual(self.native.lifecycle, result['native']['lifecycle'])
        self.assertEqual(2, result['native']['lifecycle']['launches'])
        self.assertEqual('NATIVE_UI_COMPONENT_ONLY', self.adapter.script_restart_inputs_store('test-only-selector').read()['newBinding']['scope'])
        self.adapter._script_restart('test-only-selector')
        self.assertEqual(['stop', 'launch'], self.native.lifecycle_inputs)
        self.assertEqual(1, sum(command['operation'] == 'stage' for command in storage.commands))

    def test_ios_restart_ignored_stop_prevents_launch_and_is_never_replayed(self):
        self.restart_sources(staged_restart=False); self.native.ignore_app_stop = True
        for _ in range(2):
            with self.assertRaises(RuntimeError): self.adapter._script_restart('test-only-selector')
        self.assertEqual(['stop'], self.native.lifecycle_inputs)
        self.assertEqual('stop-issued', self.adapter.script_restart_inputs_store('test-only-selector').read()['phase'])

    def test_ios_restart_lost_sdk_returns_preserve_intent_and_resume_without_repeating_inputs(self):
        self.restart_sources(staged_restart=False); self.native.lose_stop_ack = self.native.lose_launch_ack = True
        for _ in range(2):
            with self.assertRaises(RuntimeError): self.adapter._script_restart('test-only-selector')
        actual = self.adapter._script_restart('test-only-selector')
        self.assertEqual(['stop', 'launch'], self.native.lifecycle_inputs)
        self.assertEqual('ESRCH', actual['handoff']['exit']['errorSymbol'])

    def test_ios_restart_ignored_launch_is_unavailable_and_never_replayed(self):
        self.restart_sources(staged_restart=False); self.native.ignore_app_launch = True
        for _ in range(2):
            with self.assertRaises(RuntimeError): self.adapter._script_restart('test-only-selector')
        self.assertEqual(['stop', 'launch'], self.native.lifecycle_inputs)
        self.assertEqual('launch-issued', self.adapter.script_restart_inputs_store('test-only-selector').read()['phase'])

    def test_ios_restart_input_intent_prevents_green_cleanup_after_other_owners_are_absent(self):
        self.adapter.script_restart_inputs_store('test-only-selector').write({'unresolved': True}, None)
        with self.assertRaises(RuntimeError): self.adapter.cleanup('test-only-selector')
        self.assertTrue(self.native.deleted)
        self.assertIsNotNone(self.adapter.script_restart_inputs_store('test-only-selector').read())

    def test_ios_restart_handoff_preserves_original_files_and_component_scope_using_http_afc_sources(self):
        storage, source, presence, _state = self.restart_sources()
        before = list(self.native.qt.inputs)
        actual = self.adapter._script_restart_adopt('test-only-selector')
        self.assertEqual('ESRCH', actual['exit']['errorSymbol']); self.assertEqual([], actual['execution']['source']['engines'])
        self.assertEqual(before, self.native.qt.inputs)
        current = self.adapter.script_files_store('test-only-selector').read()
        self.assertEqual('43', current['binding']['processIdentity'])
        self.assertEqual('NATIVE_UI_COMPONENT_ONLY', current['binding']['scope'])
        self.assertNotIn('artifactSha256', current['binding'])
        self.assertIsNone(self.adapter.script_restart_store('test-only-selector').read())
        self.assertEqual(1, sum(command['operation'] == 'stage' for command in storage.commands))
        self.assertTrue(presence.commands); self.assertGreater(len(source.commands), 2)

    def test_ios_restart_handoff_unknown_exit_or_retained_execution_cannot_rebind_old_ownership(self):
        _storage, _source, presence, state = self.restart_sources()
        presence.presence = 'unknown'
        with self.assertRaises(RuntimeError): self.adapter._script_restart_adopt('test-only-selector')
        presence.presence = 'absent'; state['replay'] = True
        with self.assertRaises(RuntimeError): self.adapter._script_restart_adopt('test-only-selector')
        self.assertEqual('42', self.adapter.script_files_store('test-only-selector').read()['binding']['processIdentity'])
        self.assertIsNotNone(self.adapter.script_restart_store('test-only-selector').read())

    def test_ios_restart_handoff_target_replacement_fails_before_new_kernel_or_engine_reads(self):
        _storage, source, presence, _state = self.restart_sources()
        before = len(source.commands); self.native.target['appId'] = 'org.example.foreign'
        with self.assertRaises(RuntimeError): self.adapter._script_restart_adopt('test-only-selector')
        self.assertEqual(before, len(source.commands)); self.assertEqual([], presence.commands)
        self.assertIsNotNone(self.adapter.script_restart_store('test-only-selector').read())

    def test_ios_unresolved_restart_intent_prevents_green_cleanup_after_native_session_teardown(self):
        self.adapter.script_restart_store('test-only-selector').write({'unresolved': True}, None)
        with self.assertRaises(RuntimeError): self.adapter.cleanup('test-only-selector')
        self.assertTrue(self.native.deleted)
        self.assertIsNotNone(self.adapter.script_restart_store('test-only-selector').read())

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
