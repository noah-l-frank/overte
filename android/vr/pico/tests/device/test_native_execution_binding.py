#!/usr/bin/env python3
"""Real canonical entry/native verifier; synthetic APK/tools and in-memory ADB only."""
import contextlib
import argparse
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[5]
sys.path.insert(0, str(ROOT / 'tests/device'))
from adapters.android import adapter

spec = importlib.util.spec_from_file_location('pico_candidate_test_fixture',
    Path(__file__).with_name('test_candidate_identity.py'))
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)


class FakeAdb:
    """Test boundary: no subprocess, SDK, socket, discovery or real receipt."""
    target = 'synthetic-private-target'
    path = '/data/app/~~synthetic/org.overte.pico-fixture/base.apk'

    def __init__(self, digest):
        self.digest = digest
        self.mapping = 'package:' + self.path + '\n'
        self.paths = []
        self.events = []
        self.after_install = None
        self.error = False

    def require_connected(self, target, **kwargs):
        assert target == self.target

    def authorized_targets(self):
        return [self.target]

    def prop(self, target, name):
        assert target == self.target
        return {'ro.product.manufacturer': 'Pico', 'ro.product.brand': 'Pico',
            'ro.product.model': 'Pico 4', 'ro.product.device': 'Pico',
            'ro.product.cpu.abilist': 'arm64-v8a', 'ro.build.version.sdk': '26',
            'ro.opengles.version': '196610', 'ro.kernel.qemu': '0',
            'ro.build.version.release': 'test-only'}.get(name, '')

    def process_state(self, target, package):
        assert target == self.target and package == 'org.overte.pico'
        return {'running': False, 'identity': None}

    def properties(self, target):
        return {name: self.prop(target, name) for name in (
            'ro.product.manufacturer', 'ro.product.brand', 'ro.product.model',
            'ro.product.device', 'ro.product.cpu.abilist', 'ro.build.version.sdk',
            'ro.opengles.version', 'ro.kernel.qemu')}

    def shell(self, target, *args, check=True):
        assert target == self.target
        self.events.append(args)
        if self.error:
            raise RuntimeError('PRIVATE_OS_EXCEPTION_CANARY')
        if args == ('pm', 'path', 'org.overte.pico'):
            return self.paths.pop(0) if self.paths else self.mapping
        if args[:2] == ('toybox', 'sha256sum'):
            assert args[2] == self.path
            return self.digest + '  ' + args[2] + '\n'
        if args == ('am', 'force-stop', 'org.overte.pico'):
            return ''
        if args == ('pidof', '-s', 'org.overte.pico'):
            return ''
        raise AssertionError('unexpected fake native operation')

    def execute(self, args, *, target, timeout):
        assert target == self.target and args[:4] == ['install', '-r', '-d', '-g']
        self.events.append(('install',))
        if self.after_install:
            self.after_install()
        return ''


class NavigationAdb(FakeAdb):
    """Native Qt/file/OpenXR boundaries only; no simulated arrival verdicts."""
    bridge_id = '11111111-1111-4111-8111-111111111111'
    generation = '22222222-2222-4222-8222-222222222222'

    def __init__(self, digest, state_root):
        super().__init__(digest)
        self.state_root, self.identity = state_root, '123:synthetic-start'
        self.running = True
        self.opened = self.editor = self.focused = False
        self.page = 1
        self.sequence = 0
        self.inputs, self.controllers, self.entered = [], [], []
        self.text, self.status = '', {}
        self.native_elapsed, self.installation_delay_ms = 100, 0
        self.input_ages = []
        self.after_read = self.after_send = self.snapshot_mutation = self.status_mutation = None

    def process_state(self, target, package):
        assert target == self.target and package == 'org.overte.pico'
        return {'running': self.running, 'identity': self.identity if self.running else None}

    def foreground_package(self, target):
        assert target == self.target
        return 'org.overte.pico'

    def shell(self, target, *args, check=True):
        result = super().shell(target, *args, check=check)
        if args == ('pm', 'path', 'org.overte.pico'):
            self.native_elapsed += self.installation_delay_ms
        if args == ('am', 'force-stop', 'org.overte.pico'):
            self.running = False
        return result

    def epoch_milliseconds(self, target):
        assert target == self.target
        return int(time.time() * 1000)

    def snapshot(self):
        names = []
        if self.opened:
            names = (['navigation.address', 'navigation.back', 'navigation.forward'] if self.editor
                     else ['tablet.page.1', 'tablet.page.2'] + (['navigation.goto'] if self.page == 2 else []))
        value = dict(schemaVersion=1, bridgeId=self.bridge_id, generation=self.generation,
            processId=123, elapsedMs=self.native_elapsed, updatedEpochMs=self.epoch_milliseconds(self.target),
            lastCommandSequence=self.sequence, open=self.opened, ready=self.opened,
            controls=[dict(id=name, token='33333333-3333-4333-8333-' + format(index + 1, '012d'),
                           enabled=True, focused=self.focused and name == 'navigation.address')
                      for index, name in enumerate(names)])
        if self.snapshot_mutation:
            self.snapshot_mutation(value)
        return value

    def read_debug_app_file(self, target, package, path, attempts=1):
        assert target == self.target and package == 'org.overte.pico'
        if path == adapter.ANDROID_CONTROL_MARKER:
            return json.dumps(adapter.ANDROID_CONTROL_CONTRACT | {'processId': 123})
        if path == adapter.ANDROID_DEBUG_PROBE:
            return json.dumps(dict(sampleEpochMs=self.epoch_milliseconds(target),
                control=adapter.ANDROID_CONTROL_CONTRACT, application={'running': True}))
        if path == 'files/overte-e2e/navigation-ui-observation.json':
            value = self.snapshot()
            if self.after_read:
                callback, self.after_read = self.after_read, None
                callback()
            return json.dumps(value)
        if path == 'files/overte-e2e/navigation-ui-status.json':
            return json.dumps(self.status)
        raise AssertionError('unexpected debug read: no feature mutation probe fallback')

    def write_debug_app_file(self, target, package, path, raw):
        assert target == self.target and package == 'org.overte.pico'
        assert path == 'files/overte-e2e/navigation-ui-command.json'
        value = json.loads(raw)
        self.input_ages.append(self.native_elapsed - value['observedElapsedMs'])
        assert 0 <= self.input_ages[-1] <= 5000
        assert value['sequence'] == self.sequence + 1
        assert value['bridgeId'] == self.bridge_id and value['generation'] == self.generation
        self.sequence += 1; self.inputs.append(value)
        control, action = value['controlId'], value['action']
        if control.startswith('tablet.page.'):
            assert action == 'activate'; self.page = int(control.rsplit('.', 1)[1])
        elif control == 'navigation.goto':
            assert action == 'activate'; self.editor = True
        elif control == 'navigation.address':
            if action == 'activate': self.focused = True
            elif action == 'replace':
                assert self.focused; self.text = value['text']
            elif action == 'submit':
                assert self.focused; self.entered.append(self.text)
            else: raise AssertionError('unsupported native input action')
        else:
            assert control in {'navigation.back', 'navigation.forward'} and action == 'activate'
        self.status = dict(schemaVersion=1, bridgeId=self.bridge_id, commandId=value['commandId'],
            sequence=value['sequence'], performed=True, error='', processId=123,
            updatedEpochMs=self.epoch_milliseconds(target))
        if self.status_mutation: self.status_mutation(self.status)
        if self.after_send:
            callback, self.after_send = self.after_send, None
            callback()

    def require_process_identity(self, identity):
        assert identity == '123:synthetic-start'

    def stage(self, identity, operation, values):
        assert identity == '123:synthetic-start' and values == {'holdMilliseconds': 1000}
        assert operation in {'tablet.open', 'tablet.close'}
        # The real flow must persist ownership intent before a native gesture.
        states = list(self.state_root.glob('normal-navigation-*.json'))
        assert len(states) == 1 and json.loads(states[0].read_text())['tabletOwned'] is True
        self.controllers.append(operation)
        self.opened = operation == 'tablet.open'
        return {'performed': True}

    def cleanup(self, running):
        assert type(running) is bool

    def discard_local_state(self):
        pass


class NativeExecutionBindingTest(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture.CandidateIdentityTest('test_actual_candidate_entry_and_pending_semantics')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.record_file.write_text(json.dumps(self.fixture.record))
        self.fake = FakeAdb(self.fixture.record['artifactSha256'])
        self.prefix = ['--kind', 'pico', '--native-binding', '--apk', str(self.fixture.apk),
                       *self.fixture.command[3:], '--expected-version-code', '7']
        native = patch.object(adapter, 'AdbTransport', return_value=self.fake)
        native.start(); self.addCleanup(native.stop)
        environment = patch.dict(os.environ, {'OVERTE_PICO_OPENXR_INPUT': '0',
            'OVERTE_PICO_NORMAL_NAVIGATION': '0',
            'OVERTE_ANDROID_E2E_DEBUG': '0', 'OVERTE_E2E_UPGRADE_SOURCE_ARTIFACT': ''})
        environment.start(); self.addCleanup(environment.stop)

    def invoke(self, action, extra=(), prefix=None):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = adapter.main([*(self.prefix if prefix is None else prefix), action,
                                   '--target', self.fake.target, *extra])
        self.assertEqual(result, 0)
        self.assertNotIn(self.fake.target, output.getvalue())
        self.assertNotIn(str(self.fixture.root), output.getvalue())
        return json.loads(output.getvalue())

    def instance(self):
        args, binding = adapter.cli([*self.prefix, 'describe', '--target', self.fake.target])
        return binding.create_adapter(args, adapter.AndroidAdapter)

    def navigation_setup(self):
        self.fixture.rebind_synthetic_archive(e2e_layer=True)
        self.prefix = ['--kind', 'pico', '--native-binding', '--apk', str(self.fixture.apk),
                       *self.fixture.command[3:], '--expected-version-code', '7', '--expect-e2e-input-layer']
        self.state_root = self.fixture.root / 'native-ui-state'
        self.state_root.mkdir(mode=0o700)
        self.fake = NavigationAdb(self.fixture.record['artifactSha256'], self.state_root)
        for change in (patch.object(adapter, 'AdbTransport', return_value=self.fake),
                       patch.object(adapter.AndroidAdapter, 'pico_input_session', return_value=self.fake),
                       patch.dict(os.environ, {'OVERTE_PICO_OPENXR_INPUT': '1',
                           'OVERTE_ANDROID_E2E_DEBUG': '1', 'OVERTE_PICO_NORMAL_NAVIGATION': '1',
                           'ANDROID_ADB_SERVER_PORT': '5038', 'OVERTE_PICO_OPENXR_STATE_DIR': str(self.state_root),
                           'OVERTE_E2E_SCENE_URL': 'http://controlled.invalid/scene.json',
                           'OVERTE_ANDROID_E2E_PROBE_ATTEMPTS': '1'})):
            change.start(); self.addCleanup(change.stop)

    def navigation_invoke(self, operation, arguments=None):
        result = self.invoke('invoke', ['--operation', operation, '--arguments', json.dumps(arguments or {})])
        self.assertEqual(result, {'performed': True})
        return result

    def snapshot_setup(self, mutation='', images=None):
        self.navigation_setup()
        spec = importlib.util.spec_from_file_location('_overte_pico_snapshot_native_boundary',
            Path(__file__).with_name('snapshot_native_boundary.py'))
        boundary = importlib.util.module_from_spec(spec); spec.loader.exec_module(boundary)
        self.fake = boundary.create(NavigationAdb, self.fixture.record['artifactSha256'], self.state_root,
                                    mutation=mutation, fixtures=images)
        from adapters.pico4.navigation import PicoNavigation
        original_init = PicoNavigation.__init__
        def timed_init(instance, *arguments, **keywords):
            keywords.update(monotonic=lambda: self.fake.clock, sleep=self.fake.sleep)
            original_init(instance, *arguments, **keywords)
        for change in (
                patch.object(adapter, 'AdbTransport', return_value=self.fake),
                patch.object(adapter.AndroidAdapter, 'pico_input_session', return_value=self.fake),
                patch.object(PicoNavigation, '__init__', timed_init),
                patch.dict(os.environ, {'OVERTE_PICO_NORMAL_NAVIGATION': '0',
                    'OVERTE_PICO_NORMAL_SNAPSHOT': '1', 'OVERTE_DEVICE_ARTIFACT_DIR': str(self.fake.artifacts),
                    'OVERTE_PICO_SNAPSHOT_TEST_APP': str(self.fake.app)})):
            change.start(); self.addCleanup(change.stop)

    def snapshot_invoke(self, operation, arguments=None):
        return self.invoke('invoke', ['--operation', operation, '--arguments', json.dumps(arguments or {})])

    def test_snapshot_original_candidate_wrapper_reads_original_bytes_and_restores_own_ui(self):
        self.snapshot_setup()
        self.assertTrue({'snapshot.open', 'snapshot.capture', 'snapshot.files', 'snapshot.close'}
                        <= set(self.instance().capabilities(self.fake.target)))
        self.snapshot_invoke('snapshot.open')
        prefix = 'parity-0123456789abcdef-still-png'
        self.assertEqual(self.snapshot_invoke('snapshot.files', {'prefix': prefix}), {'files': []})
        self.snapshot_invoke('snapshot.capture', {'name': prefix, 'mode': 'still', 'format': 'png'})
        observed = self.snapshot_invoke('snapshot.files', {'prefix': prefix})['files']
        self.assertEqual(1, len(observed))
        self.assertEqual((self.fake.artifacts / observed[0]['artifact']).read_bytes(), b'original synthetic Pico bytes')
        self.assertNotIn('passed', observed[0])
        self.snapshot_invoke('snapshot.close')
        self.assertEqual((self.fake.mode, self.fake.format), ('animated', 'webp'))
        self.assertFalse(self.fake.opened)
        self.assertEqual([], list(self.state_root.glob('normal-snapshot-*.json')))
        self.assertEqual(1, self.fake.captures)

    def test_snapshot_requires_opt_in_and_current_installed_bytes_before_input(self):
        self.snapshot_setup()
        with patch.dict(os.environ, {'OVERTE_PICO_NORMAL_SNAPSHOT': '0'}):
            self.assertNotIn('snapshot.open', self.instance().capabilities(self.fake.target))
            with self.assertRaises(ValueError): self.snapshot_invoke('snapshot.open')
        self.fake.digest = 'f' * 64
        with self.assertRaises(ValueError): self.snapshot_invoke('snapshot.open')
        self.assertEqual([], self.fake.inputs)
        self.assertEqual([], self.fake.controllers)

    def test_snapshot_partial_entry_can_close_its_original_owned_openxr_panel(self):
        self.snapshot_setup('partial-entry-error')
        with self.assertRaises(ValueError): self.snapshot_invoke('snapshot.open')
        self.assertTrue(self.fake.opened)
        self.assertTrue(list(self.state_root.glob('normal-snapshot-ui-*.json')))
        self.snapshot_invoke('snapshot.close')
        self.assertFalse(self.fake.opened)
        self.assertEqual((self.fake.mode, self.fake.format), ('animated', 'webp'))
        self.assertEqual([], list(self.state_root.glob('normal-snapshot-*.json')))

    def test_snapshot_owned_pending_capture_is_cancelled_and_preferences_restored(self):
        self.snapshot_setup('capture-pending')
        prefix = 'parity-0123456789abcdef-still-png'
        self.snapshot_invoke('snapshot.open')
        self.snapshot_invoke('snapshot.files', {'prefix': prefix})
        self.snapshot_invoke('snapshot.capture', {'name': prefix, 'mode': 'still', 'format': 'png'})
        self.assertTrue(self.fake.capturing)
        self.snapshot_invoke('snapshot.close')
        self.assertIn('snapshot.cancel', [value['controlId'] for value in self.fake.inputs])
        self.assertFalse(self.fake.capturing)
        self.assertEqual((self.fake.mode, self.fake.format), ('animated', 'webp'))

    def test_snapshot_install_replacement_after_input_retains_original_cleanup_path(self):
        self.snapshot_setup()
        self.fake.after_send = lambda: setattr(self.fake, 'digest', 'f' * 64)
        with self.assertRaises(ValueError): self.snapshot_invoke('snapshot.open')
        self.assertTrue(list(self.state_root.glob('normal-snapshot-ui-*.json')))
        self.assertEqual(self.invoke('cleanup', prefix=['--kind', 'pico', '--native-binding']), {'cleaned': True})
        self.assertIn(('am', 'force-stop', 'org.overte.pico'), self.fake.events)
        self.assertEqual([], list(self.state_root.glob('normal-snapshot-*.json')))

    def test_snapshot_does_not_adopt_foreign_open_tablets_or_unknown_process_start(self):
        self.snapshot_setup()
        self.fake.opened = True
        with self.assertRaises(ValueError): self.snapshot_invoke('snapshot.open')
        self.snapshot_invoke('snapshot.close')
        self.assertTrue(self.fake.opened)
        self.assertEqual([], self.fake.controllers)
        self.fake.opened = False; self.fake.identity = '123:unknown'
        with self.assertRaises(ValueError): self.snapshot_invoke('snapshot.open')
        self.assertEqual([], self.fake.controllers)

    def test_snapshot_cannot_capture_into_an_old_or_foreign_run_prefix(self):
        self.snapshot_setup()
        self.snapshot_invoke('snapshot.open')
        prefix = 'parity-0123456789abcdef-still-png'
        (self.fake.files / (prefix + '-old.png')).write_bytes(b'old original')
        self.assertEqual(1, len(self.snapshot_invoke('snapshot.files', {'prefix': prefix})['files']))
        with self.assertRaises(ValueError):
            self.snapshot_invoke('snapshot.capture', {'name': prefix, 'mode': 'still', 'format': 'png'})
        with self.assertRaises(ValueError):
            self.snapshot_invoke('snapshot.files', {'prefix': 'parity-fedcba9876543210-still-png'})
        self.assertEqual(0, self.fake.captures)
        self.snapshot_invoke('snapshot.close')

    def test_native_navigation_actual_dispatch_candidate_reader_and_private_ownership(self):
        from navigation_observation import OPERATIONS, viewpoint_urls
        self.navigation_setup()
        self.assertEqual(self.fixture.fixture.parent, ROOT)
        self.assertTrue(set(OPERATIONS).issubset(self.instance().capabilities(self.fake.target)))
        urls = viewpoint_urls(os.environ['OVERTE_E2E_SCENE_URL'])
        self.navigation_invoke('places.open')
        for url in urls.values():
            self.navigation_invoke('places.goto', {'url': url})
        self.navigation_invoke('places.back'); self.navigation_invoke('places.forward')
        self.assertEqual(self.fake.entered, list(urls.values()))
        self.assertEqual(self.fake.controllers, ['tablet.open'])
        self.assertEqual([row['sequence'] for row in self.fake.inputs], list(range(1, len(self.fake.inputs) + 1)))
        self.assertEqual(len({row['commandId'] for row in self.fake.inputs}), len(self.fake.inputs))
        self.assertIn('tablet.page.2', [row['controlId'] for row in self.fake.inputs])
        state = next(self.state_root.glob('normal-navigation-*.json'))
        self.assertEqual(state.stat().st_mode & 0o777, 0o600)
        self.assertNotIn('controlled.invalid', state.read_text())
        self.navigation_invoke('places.close'); self.navigation_invoke('places.close')
        self.assertEqual(self.fake.controllers, ['tablet.open', 'tablet.close'])
        self.assertFalse(list(self.state_root.iterdir()))
        self.assertFalse(self.fake.opened)
        # Every phase retains the original verifier/installed OS-byte guard.
        self.assertGreater(self.fake.events.count(('pm', 'path', 'org.overte.pico')), 30)
        self.assertEqual(self.fixture.record['signature']['state'], 'pending')

    def test_native_navigation_requires_explicit_bound_profile(self):
        from navigation_observation import OPERATIONS
        self.navigation_setup()
        self.assertFalse(set(OPERATIONS) & set(adapter.AndroidAdapter('pico').capabilities(self.fake.target)))
        with patch.dict(os.environ, {'OVERTE_PICO_NORMAL_NAVIGATION': '0'}):
            self.assertFalse(set(OPERATIONS) & set(self.instance().capabilities(self.fake.target)))
            with self.assertRaises(ValueError): self.navigation_invoke('places.open')
        with patch.dict(os.environ, {'OVERTE_E2E_SCENE_URL': ''}):
            with self.assertRaises(ValueError): self.instance().capabilities(self.fake.target)
        self.assertEqual(self.fake.inputs + self.fake.controllers, [])

    def test_native_navigation_rejects_foreign_url_and_unowned_open_tablet(self):
        self.navigation_setup()
        with self.assertRaises(ValueError):
            self.navigation_invoke('places.goto', {'url': 'http://foreign.invalid/scene.json'})
        self.fake.opened = True
        with self.assertRaises(ValueError): self.navigation_invoke('places.open')
        self.assertEqual(self.fake.inputs + self.fake.controllers, [])
        self.assertFalse(list(self.state_root.iterdir()))

    def test_native_navigation_rejects_ordinary_apk_despite_runtime_opt_in(self):
        self.navigation_setup()
        self.fixture.rebind_synthetic_archive(e2e_layer=False)
        self.fake.digest = self.fixture.record['artifactSha256']
        self.prefix = ['--kind', 'pico', '--native-binding', '--apk', str(self.fixture.apk),
                       *self.fixture.command[3:], '--expected-version-code', '7']
        with self.assertRaises(ValueError): self.instance().capabilities(self.fake.target)
        with self.assertRaises(ValueError): self.navigation_invoke('places.open')
        self.assertEqual(self.fake.inputs + self.fake.controllers, [])

    def test_native_navigation_changed_apk_before_and_after_input_rejects(self):
        self.navigation_setup()
        original = self.fake.digest
        self.fake.digest = 'f' * 64
        with self.assertRaises(ValueError): self.navigation_invoke('places.open')
        self.assertEqual(self.fake.inputs + self.fake.controllers, [])
        self.fake.digest = original
        self.fake.after_send = lambda: setattr(self.fake, 'digest', 'f' * 64)
        with self.assertRaises(ValueError): self.navigation_invoke('places.open')
        self.assertEqual(len(self.fake.inputs), 1)  # An uncertain page click is never replayed.

    def test_native_navigation_process_replacement_after_native_lookup_stops_before_input(self):
        self.navigation_setup()
        self.fake.after_read = lambda: setattr(self.fake, 'identity', '124:replaced-start')
        with self.assertRaises(ValueError): self.navigation_invoke('places.open')
        self.assertEqual(self.fake.inputs + self.fake.controllers, [])
        self.assertFalse(list(self.state_root.iterdir()))

    def test_native_navigation_slow_artifact_verification_does_not_age_out_input(self):
        self.navigation_setup()
        self.fake.installation_delay_ms = 1000
        self.navigation_invoke('places.open')
        self.assertTrue(self.fake.editor)
        self.assertTrue(self.fake.input_ages)
        self.assertTrue(all(0 <= age <= 5000 for age in self.fake.input_ages))

    def test_native_navigation_malformed_status_is_not_a_success_and_input_is_not_replayed(self):
        self.navigation_setup()
        self.fake.status_mutation = lambda value: value.update(navigationPassed=True)
        with self.assertRaises(ValueError): self.navigation_invoke('places.open')
        self.assertEqual(len(self.fake.inputs), 1)
        self.assertEqual(self.fake.controllers, ['tablet.open'])
        self.assertTrue(next(self.state_root.glob('normal-navigation-*.json')).exists())

    def test_native_navigation_rejects_stale_foreign_and_malformed_native_observations(self):
        self.navigation_setup()
        for mutate in (lambda value: value.update(processId=999),
                       lambda value: value.update(updatedEpochMs=1),
                       lambda value: value.update(lastCommandSequence=True),
                       lambda value: value.update(expectedScene='forbidden'),
                       lambda value: value.update(ready=True)):
            with self.subTest(mutation=mutate.__code__.co_firstlineno):
                self.fake.snapshot_mutation = mutate
                with self.assertRaises(ValueError): self.navigation_invoke('places.open')
                self.assertEqual(self.fake.inputs + self.fake.controllers, [])
        self.assertFalse(list(self.state_root.iterdir()))

    def test_native_navigation_durable_state_cannot_move_to_another_bridge(self):
        self.navigation_setup()
        self.navigation_invoke('places.open')
        count = len(self.fake.inputs)
        path = next(self.state_root.glob('normal-navigation-*.json'))
        value = json.loads(path.read_text()); value['bridgeId'] = '44444444-4444-4444-8444-444444444444'
        path.write_text(json.dumps(value))
        with self.assertRaises(ValueError): self.navigation_invoke('places.back')
        self.assertEqual(len(self.fake.inputs), count)

    def test_native_navigation_native_cleanup_retires_partial_state_with_invalid_candidate(self):
        self.navigation_setup()
        self.navigation_invoke('places.open')
        self.assertTrue(list(self.state_root.glob('normal-navigation-*.json')))
        self.fake.digest = 'f' * 64
        result = self.invoke('cleanup', prefix=['--kind', 'pico', '--native-binding'])
        self.assertEqual(result, {'cleaned': True})
        self.assertFalse(self.fake.running)
        self.assertFalse(list(self.state_root.iterdir()))

    def test_original_candidate_seal_reuses_only_verified_host_bytes_and_keeps_installation_live(self):
        args,pico=adapter.cli([*self.prefix,'describe','--target',self.fake.target])
        original=pico.verifier.verify_candidate
        with patch.object(pico.verifier,'verify_candidate',wraps=original) as verify:
            bound=pico.create_adapter(args,adapter.AndroidAdapter);self.assertEqual(1,verify.call_count)
            bound.describe(self.fake.target);bound.describe(self.fake.target)
            self.assertEqual(1,verify.call_count)
            result=bound._candidate();result['sha256']='f'*64
            self.assertEqual(self.fake.digest,bound._candidate()['sha256'])
            self.assertGreaterEqual(self.fake.events.count(('pm','path','org.overte.pico')),6)
            self.fake.digest='f'*64
            with self.assertRaises(ValueError):bound.describe(self.fake.target)
            self.assertEqual(1,verify.call_count)

    def test_unsupported_ofd_query_retains_original_full_verifier_on_every_guard(self):
        from adapters.pico4 import candidate_read_seal
        args,pico=adapter.cli([*self.prefix,'describe','--target',self.fake.target]);original=pico.verifier.verify_candidate
        with patch.object(candidate_read_seal,'DUPFD_QUERY',None),patch.object(pico.verifier,'verify_candidate',wraps=original) as verify:
            bound=pico.create_adapter(args,adapter.AndroidAdapter);self.assertEqual(1,verify.call_count)
            bound.describe(self.fake.target);self.assertGreaterEqual(verify.call_count,2)

    def test_original_candidate_seal_refuses_all_changed_argument_values_and_types(self):
        from adapters.pico4 import binding as pico
        for name,value in (('source_revision','b'*40),('minimum_version',5),
                ('expected_version_name','changed'),('expect_e2e_input_layer',0),
                ('forbid_e2e_input_layer',True),('require_identity',1),('aapt2','changed')):
            with self.subTest(argument=name):
                args,_binding=adapter.cli([*self.prefix,'describe','--target',self.fake.target])
                bound=pico.create_adapter(args,adapter.AndroidAdapter);self.fake.events.clear()
                setattr(args,name,value)
                with self.assertRaises(ValueError):bound.describe(self.fake.target)
                self.assertEqual([],self.fake.events)

    def test_original_candidate_seal_detects_same_bytes_replacement_and_restored_mtime_writes(self):
        for mode in ('replace','write-restore'):
            with self.subTest(mode=mode):
                bound=self.instance();path=self.fixture.input_file;original=path.read_bytes();before=path.stat()
                if mode=='replace':
                    replacement=path.with_suffix('.replacement');replacement.write_bytes(original)
                    os.utime(replacement,ns=(before.st_atime_ns,before.st_mtime_ns));replacement.replace(path)
                else:
                    path.write_bytes(original+b' ');path.write_bytes(original)
                    os.utime(path,ns=(before.st_atime_ns,before.st_mtime_ns))
                self.fake.events.clear()
                with self.assertRaises(ValueError):bound.describe(self.fake.target)
                self.assertEqual([],self.fake.events)

    def test_original_candidate_seal_refuses_arguments_changed_during_original_verification(self):
        args,pico=adapter.cli([*self.prefix,'describe','--target',self.fake.target]);original=pico.verifier.verify_candidate
        def changing(value):
            verified=original(value);value.expected_version_code='changed-after-verify';return verified
        with patch.object(pico.verifier,'verify_candidate',side_effect=changing):
            with self.assertRaises(ValueError):pico.create_adapter(args,adapter.AndroidAdapter)
        self.assertEqual([],self.fake.events)

    def test_original_candidate_seal_detects_receipt_mutation(self):
        bound=self.instance();entry=self.fixture.build['evidence']['receipts'][0]
        receipt=self.fixture.build_file.parent/entry['path'];receipt.write_bytes(receipt.read_bytes()+b' ')
        self.fake.events.clear()
        with self.assertRaises(ValueError):bound.describe(self.fake.target)
        self.assertEqual([],self.fake.events)

    def test_original_candidate_seal_refuses_changed_tool_environment(self):
        bound=self.instance();self.fake.events.clear()
        with patch.dict(os.environ,MOCK_SIGNED='0'):
            with self.assertRaises(ValueError):bound.describe(self.fake.target)
        self.assertEqual([],self.fake.events)

    def test_original_candidate_seal_rechecks_actual_decoder_dependency_inventory(self):
        sdk=self.fixture.root/'seal-sdk';(sdk/'bin').mkdir(parents=True);(sdk/'lib').mkdir()
        analyzer=sdk/'bin/apkanalyzer';analyzer.write_bytes(self.fixture.fixture.analyzer.read_bytes());analyzer.chmod(0o755)
        prefix=list(self.prefix);prefix[prefix.index('--apkanalyzer')+1]=str(analyzer)
        args,binding=adapter.cli([*prefix,'describe','--target',self.fake.target]);bound=binding.create_adapter(args,adapter.AndroidAdapter)
        (sdk/'lib/apkanalyzer-classpath.jar').write_bytes(b'new dependency')
        self.fake.events.clear()
        with self.assertRaises(ValueError):bound.describe(self.fake.target)
        self.assertEqual([],self.fake.events)

    def test_original_candidate_seal_rechecks_hashed_jvm_and_nested_jar_inventory(self):
        sdk=self.fixture.root/'seal-sdk-full';(sdk/'bin').mkdir(parents=True);(sdk/'lib/nested').mkdir(parents=True)
        analyzer=sdk/'bin/apkanalyzer';analyzer.write_bytes(self.fixture.fixture.analyzer.read_bytes());analyzer.chmod(0o755)
        (sdk/'source.properties').write_bytes(b'explicit synthetic SDK')
        (sdk/'lib/apkanalyzer-classpath.jar').write_bytes(b'synthetic jar')
        java=self.fixture.root/'seal-jvm';(java/'bin').mkdir(parents=True);(java/'lib/server').mkdir(parents=True)
        for path in ('bin/java','release','lib/modules','lib/server/libjvm.so'):(java/path).write_bytes(b'synthetic '+path.encode())
        prefix=list(self.prefix);prefix[prefix.index('--apkanalyzer')+1]=str(analyzer)
        with patch.dict(os.environ,JAVA_HOME=str(java)):
            args,binding=adapter.cli([*prefix,'describe','--target',self.fake.target]);bound=binding.create_adapter(args,adapter.AndroidAdapter)
            from adapters.pico4 import candidate_read_seal
            with patch.object(candidate_read_seal,'bounded_decoder_tree',side_effect=AssertionError('query must not rescan SDK')):
                bound.describe(self.fake.target)
            (sdk/'lib/nested/new.jar').write_bytes(b'new nested dependency')
            self.fake.events.clear()
            with self.assertRaises(ValueError):bound.describe(self.fake.target)
            self.assertEqual([],self.fake.events)
            (sdk/'lib/nested/new.jar').unlink()
            # A separately verified original lifetime independently rejects
            # JVM bytes, without borrowing the earlier failed inventory check.
            args2,binding2=adapter.cli([*prefix,'describe','--target',self.fake.target]);jvm_bound=binding2.create_adapter(args2,adapter.AndroidAdapter)
            (java/'lib/modules').write_bytes(b'changed original modules')
            with self.assertRaises(ValueError):jvm_bound.describe(self.fake.target)

    def test_original_candidate_seal_rechecks_physical_network_policy_bytes(self):
        args,pico=adapter.cli([*self.prefix,'describe','--target',self.fake.target])
        web=self.fixture.root/'seal-web';(web/'res/xml').mkdir(parents=True)
        for name in ('network_policy.py','network-capability.json','res/xml/overte_embedded_web_network_security_config.xml'):
            (web/name).write_bytes((pico.verifier.WEB_ROOT/name).read_bytes())
        manifest=self.fixture.root/'seal-manifest.xml';manifest.write_bytes(pico.verifier.PICO_MANIFEST.read_bytes())
        with patch.object(pico.verifier,'WEB_ROOT',web),patch.object(pico.verifier,'PICO_MANIFEST',manifest):
            bound=pico.create_adapter(args,adapter.AndroidAdapter);(web/'network-capability.json').write_bytes(b'{}');self.fake.events.clear()
            with self.assertRaises(ValueError):bound.describe(self.fake.target)
            self.assertEqual([],self.fake.events)

    def test_native_candidate_network_decoder_bytes_are_rechecked(self):
        bound = self.instance()
        self.fixture.fixture.analyzer.write_text('#!/usr/bin/env python3\nraise SystemExit(2)\n')
        with self.assertRaisesRegex(ValueError, '^OVT_PICO_BINDING_REJECTED$'):
            bound.describe(self.fake.target)
        self.assertEqual(self.fake.events, [])

    def test_real_dispatch_and_original_candidate_verifier(self):
        result = self.invoke('describe')
        self.assertEqual(result['adapter'], 'android-pico-adb')
        self.assertEqual(result['executionIdentity'], dict(schemaVersion=1, sourceRevision='a'*40,
            artifactSha256=self.fake.digest, installedCandidateVerified=True))
        self.assertGreaterEqual(self.fake.events.count(('pm', 'path', 'org.overte.pico')), 6)
        self.assertEqual(self.invoke('invoke', ['--operation', 'app.process']),
                         {'running': False, 'identity': None})
        self.assertNotIn('app.upgrade', self.instance().capabilities())
        # The signature-tool output and OS bytes above are synthetic. Pending
        # SH009 receipt semantics remain unchanged even on this positive path.
        self.assertEqual(self.fixture.record['signature']['state'], 'pending')

    def test_missing_split_unsafe_changed_and_foreign_installations(self):
        for mapping in ['', self.fake.mapping * 2,
                        'package:/data/app/x/../base.apk\n',
                        'package:/data/app/x/$(private)/base.apk\n',
                        'package:/data/app/x/base.apk\nWARNING\n']:
            with self.subTest(mapping=mapping):
                self.fake.mapping = mapping
                with self.assertRaisesRegex(ValueError, '^OVT_PICO_BINDING_REJECTED$'):
                    self.invoke('describe')
        self.fake.mapping = 'package:' + self.fake.path + '\n'
        self.fake.paths = [self.fake.mapping, 'package:/data/app/other/base.apk\n']
        with self.assertRaises(ValueError): self.invoke('describe')
        self.fake.paths = []
        self.fake.digest = 'f' * 64
        with self.assertRaises(ValueError): self.invoke('describe')

    def test_build_receipt_bytes_frozen_and_missing_evidence_precedes_device(self):
        bound = self.instance()
        # Harmless JSON whitespace still changes frozen bytes, even though the
        # receipt could be rehashed consistently in a modified envelope.
        entry = self.fixture.build['evidence']['receipts'][0]
        path = self.fixture.build_file.parent / entry['path']
        path.write_bytes(path.read_bytes() + b'\n')
        with self.assertRaisesRegex(ValueError, '^OVT_PICO_BINDING_REJECTED$'):
            bound.describe(self.fake.target)
        self.assertEqual(self.fake.events, [])
        self.fixture.build_file.unlink()
        with self.assertRaises(ValueError):
            self.instance()
        self.assertEqual(self.fake.events, [])
        self.invoke('cleanup')

    def test_candidate_and_evidence_rechecked_not_cached_receipts(self):
        bound = self.instance()
        self.fixture.files['spdx'].write_text('PRIVATE_MUTATED_EVIDENCE')
        with self.assertRaisesRegex(ValueError, '^OVT_PICO_BINDING_REJECTED$'):
            bound.describe(self.fake.target)
        # Cleanup remains usable even on the very same now-invalid instance.
        self.assertEqual(bound.cleanup(self.fake.target), {'cleaned': True})
        self.fixture.apk.unlink()
        self.assertEqual(self.invoke('cleanup', prefix=['--kind', 'pico', '--native-binding']),
                         {'cleaned': True})

    def test_reinstall_same_candidate_late_mismatch_and_upgrade_rejected(self):
        values = json.dumps({'path': str(self.fixture.apk)})
        extra = ['--operation', 'app.install', '--arguments', values]
        self.assertEqual(self.invoke('invoke', extra), {'installed': True})
        self.fake.after_install = lambda: setattr(self.fake, 'digest', 'f' * 64)
        with self.assertRaises(ValueError): self.invoke('invoke', extra)
        self.fake.events.clear()
        with self.assertRaises(ValueError):
            self.invoke('invoke', ['--operation', 'app.upgrade'])
        self.assertNotIn(('install',), self.fake.events)

    def test_incomplete_inputs_and_private_native_failure_closed(self):
        with patch.object(adapter, 'AdbTransport') as transport:
            with self.assertRaises(ValueError):
                adapter.main(['--kind', 'pico', '--native-binding', 'describe'])
            transport.assert_not_called()
        self.fake.error = True
        with self.assertRaisesRegex(ValueError, '^OVT_PICO_BINDING_REJECTED$'):
            self.invoke('describe')
        result = subprocess.run([sys.executable, str(ROOT / 'tests/device/adapters/android/adapter.py'),
            '--kind', 'pico', '--native-binding', '--apk', 'PRIVATE_PATH_CANARY', 'describe'],
            capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stderr.strip(), 'OVT_ANDROID_ADAPTER_REJECTED')
        self.assertEqual(result.stdout, '')
        # The same original Pico entry as a REAL child through the canonical
        # runner. Missing candidate inputs reject before constructing ADB, as
        # asserted above; this never discovers or accesses a device.
        runner_spec = importlib.util.spec_from_file_location('pico_adapter_error_runner',
            ROOT / 'tests/device/run.py')
        runner = importlib.util.module_from_spec(runner_spec)
        runner_spec.loader.exec_module(runner)
        with self.assertRaisesRegex(RuntimeError, '^OVT_TEST_INFRASTRUCTURE_ERROR$'):
            runner.adapter_call([sys.executable,
                str(ROOT / 'tests/device/adapters/android/adapter.py'),
                '--kind', 'pico', '--native-binding', '--apk', 'PRIVATE_PATH_CANARY'],
                'describe', self.fake.target, timeout=5)

    def test_real_runner_producer_native_claim_and_pico_consumer(self):
        from adapters.pico4.verify_result import verify
        runner_spec = importlib.util.spec_from_file_location('pico_bound_original_runner',
            ROOT / 'tests/device/run.py')
        runner = importlib.util.module_from_spec(runner_spec)
        runner_spec.loader.exec_module(runner)
        native_path = ROOT / 'tests/device/adapters/android/adapter.py'
        manifest = self.fixture.root / 'private-bound-manifest.json'
        manifest.write_text(json.dumps(dict(schemaVersion=1, id='android-pico-adb',
            command=[str(native_path), *self.prefix])))
        args = argparse.Namespace(adapter_manifest=manifest, catalog=ROOT / 'tests/device/catalog.json',
            suite='smoke', list=False, tablet_policy=None, target=None, allow_virtual=False,
            output_dir=self.fixture.root / 'producer', keep_running=False, require_complete=True,
            candidate_artifact=self.fixture.apk, expected_source_sha='a'*40,
            expected_artifact_sha256=self.fixture.record['artifactSha256'])
        original_run = subprocess.run
        def in_process_native(command, **kwargs):
            if len(command) > 1 and command[1] == str(native_path):
                self.assertIs(kwargs['stderr'], subprocess.DEVNULL)
                stdout, stderr = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    try:
                        code = adapter.main(command[2:])
                    except ValueError:
                        code = 2
                        print('OVT_ANDROID_ADAPTER_REJECTED', file=sys.stderr)
                return subprocess.CompletedProcess(command, code, stdout.getvalue(), None)
            # Only the synthetic aapt/apksigner fixtures reach this boundary.
            return original_run(command, **kwargs)
        changed = False
        def module_result(module, *unused):
            if changed:
                self.fake.digest = 'f'*64
            return dict(id=module['id'], description=module['description'], status='passed',
                        returncode=0, durationSeconds=0.0, output='TEST_MODULE_NOT_DEVICE_EVIDENCE')
        with patch.object(runner, 'parse_args', return_value=args), \
             patch.object(runner.subprocess, 'run', side_effect=in_process_native), \
             patch.object(runner, 'run_module', side_effect=module_result), \
             patch.dict(os.environ, {'OVERTE_DEVICE_LOCK_ROOT': str(self.fixture.root / 'locks')}), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(runner.main(), 0)
            self.assertEqual(verify(args.output_dir, args.expected_source_sha,
                args.expected_artifact_sha256, ['launch-smoke'])['status'], 'RESULT_BOUND_NOT_NODE_ACCEPTED')
            changed = True
            args.output_dir = self.fixture.root / 'late-installation-mismatch'
            self.assertEqual(runner.main(), 1)
            self.assertFalse((args.output_dir / 'result-identity.json').exists())


class SnapshotInputObservationTests(unittest.TestCase):
    """Closed read schema, not a fabricated capture or installed-code verdict."""
    def snapshot(self):
        return dict(schemaVersion=1, bridgeId='11111111-1111-4111-8111-111111111111',
            generation='22222222-2222-4222-8222-222222222222', processId=42,
            elapsedMs=12, updatedEpochMs=1000, lastCommandSequence=0, open=True, ready=True,
            controls=[dict(id='snapshot.mode.still', token='33333333-3333-4333-8333-333333333333',
                           enabled=True, focused=False, checked=True)])

    def validate(self, value):
        from adapters.pico4.navigation import validate_snapshot
        return validate_snapshot(value, 42, 1000)

    def test_actual_snapshot_choice_shape_is_readable_without_a_success_claim(self):
        value = self.validate(self.snapshot())
        self.assertTrue(value['controls'][0]['checked'])
        self.assertNotIn('performed', value)
        self.assertNotIn('snapshotPassed', value)

    def test_snapshot_selected_state_requires_an_actual_boolean(self):
        for invalid in ('true', 1, None):
            value = self.snapshot(); value['controls'][0]['checked'] = invalid
            with self.subTest(checked=invalid), self.assertRaises(RuntimeError): self.validate(value)
        value = self.snapshot(); del value['controls'][0]['checked']
        with self.assertRaises(RuntimeError): self.validate(value)

    def test_existing_navigation_controls_do_not_admit_extra_selected_state(self):
        value = self.snapshot(); value['controls'][0]['id'] = 'navigation.address'
        with self.assertRaises(RuntimeError): self.validate(value)
        del value['controls'][0]['checked']
        self.assertEqual(self.validate(value), value)

    def test_unknown_choices_and_feature_verdicts_are_rejected(self):
        value = self.snapshot(); value['controls'][0]['id'] = 'snapshot.mode.unreviewed'
        with self.assertRaises(RuntimeError): self.validate(value)
        value = self.snapshot(); value['snapshotPassed'] = True
        with self.assertRaises(RuntimeError): self.validate(value)

    def test_distinct_choices_cannot_reuse_one_native_control_token(self):
        value = self.snapshot()
        value['controls'].append(dict(value['controls'][0], id='snapshot.mode.animated', checked=False))
        with self.assertRaises(RuntimeError): self.validate(value)



class CandidateReadSealTests(unittest.TestCase):
    """Real private local filesystem/FD evidence; no product/device process."""
    def setUp(self):
        import tempfile
        import hashlib
        from adapters.pico4.candidate_read_seal import CandidateReadSeal
        self.temporary=tempfile.TemporaryDirectory(prefix='pico-candidate-read-seal-');self.addCleanup(self.temporary.cleanup)
        self.path=Path(self.temporary.name)/'original';self.path.write_bytes(b'original verified bytes')
        self.inventory={str(self.path):hashlib.sha256(self.path.read_bytes()).hexdigest()};self.metadata={'argument':'original'}
        self.create=lambda:CandidateReadSeal(lambda:dict(self.inventory),lambda:dict(self.metadata),{'verified':['original']})

    def test_only_original_read_only_cloexec_descriptor_survives_unchanged_reads(self):
        import fcntl
        seal=self.create();self.addCleanup(seal.close);fd=seal.rows[0][2]
        self.assertEqual(os.O_RDONLY,fcntl.fcntl(fd,fcntl.F_GETFL)&os.O_ACCMODE)
        self.assertTrue(fcntl.fcntl(fd,fcntl.F_GETFD)&fcntl.FD_CLOEXEC)
        result=seal.check();result['verified'].append('foreign')
        self.assertEqual({'verified':['original']},seal.check())
        seal.close()
        with self.assertRaises(OSError):os.fstat(fd)
        with self.assertRaises(ValueError):seal.check()

    def test_failed_metadata_check_closes_original_fd_and_cannot_resume_after_reversal(self):
        seal=self.create();fd=seal.rows[0][2];self.metadata['argument']='changed'
        with self.assertRaises(ValueError):seal.check()
        with self.assertRaises(OSError):os.fstat(fd)
        self.metadata['argument']='original'
        with self.assertRaises(ValueError):seal.check()

    def test_added_inventory_cannot_be_removed_to_resume_this_lifetime(self):
        seal=self.create();fd=seal.rows[0][2];self.inventory[str(self.path.with_name('new'))]='a'*64
        with self.assertRaises(ValueError):seal.check()
        with self.assertRaises(OSError):os.fstat(fd)
        self.inventory.pop(str(self.path.with_name('new')))
        with self.assertRaises(ValueError):seal.check()

    def test_original_digest_mismatch_never_admits_or_leaks_fd(self):
        self.inventory[str(self.path)]='f'*64
        before={int(row.name) for row in Path('/proc/self/fd').iterdir()}
        with self.assertRaises(ValueError):self.create()
        self.assertEqual(before,{int(row.name) for row in Path('/proc/self/fd').iterdir()})

    def test_unlink_and_same_bytes_symlink_replacement_fail_original_inode_admission(self):
        seal=self.create();target=self.path.with_name('foreign');target.write_bytes(self.path.read_bytes())
        self.path.unlink();self.path.symlink_to(target)
        with self.assertRaises(ValueError):seal.check()

    def test_cold_directory_scan_is_bounded_and_query_does_not_adopt_new_entries(self):
        from adapters.pico4 import candidate_read_seal as module
        root=self.path.parent/'sdk';root.mkdir();(root/'original.jar').write_bytes(b'original jar')
        jars,directories=module.bounded_decoder_tree(root)
        self.assertEqual({str(root/'original.jar')},jars)
        seal=module.CandidateReadSeal(lambda:dict(self.inventory),lambda:dict(self.metadata),{},directories=directories)
        with patch.object(module,'bounded_decoder_tree',side_effect=AssertionError('no scan during check')):seal.check()
        (root/'new.jar').write_bytes(b'new jar')
        with self.assertRaises(ValueError):seal.check()
        with patch.object(module,'MAX_ENTRIES',1):
            with self.assertRaises(ValueError):module.bounded_decoder_tree(root)

    def test_lost_original_fd_cannot_close_a_foreign_replacement_or_resume(self):
        seal=self.create();fd=seal.rows[0][2];os.close(fd)
        foreign=self.path.with_name('foreign-fd');foreign.write_bytes(b'foreign original')
        replacement=os.open(foreign,os.O_RDONLY|os.O_CLOEXEC)
        try:
            self.assertEqual(fd,replacement)
            with self.assertRaises(ValueError):seal.check()
            self.assertEqual(b'foreign original',os.read(replacement,64))
            seal.close();os.fstat(replacement)
            with self.assertRaises(ValueError):seal.check()
        finally:
            os.close(replacement);os.close(seal.rows[0][4])

    def test_reopened_same_inode_under_original_number_is_foreign_and_left_open(self):
        seal=self.create();fd=seal.rows[0][2];anchor=seal.rows[0][4];os.close(fd)
        replacement=os.open(self.path,os.O_RDONLY|os.O_CLOEXEC)
        try:
            self.assertEqual(fd,replacement)
            with self.assertRaises(ValueError):seal.check()
            self.assertEqual(b'original verified bytes',os.read(replacement,64))
            seal.close();os.fstat(replacement);os.fstat(anchor)
        finally:os.close(replacement);os.close(anchor)

    def test_lost_anchor_cannot_adopt_a_new_same_inode_open_description(self):
        seal=self.create();fd=seal.rows[0][2];anchor=seal.rows[0][4];os.close(anchor)
        replacement=os.open(self.path,os.O_RDONLY|os.O_CLOEXEC)
        try:
            self.assertEqual(anchor,replacement)
            with self.assertRaises(ValueError):seal.check()
            seal.close();os.fstat(replacement);os.fstat(fd)
        finally:os.close(replacement);os.close(fd)

    def test_unsupported_kernel_ofd_query_never_leaks_initial_unexposed_handles(self):
        import errno
        from adapters.pico4 import candidate_read_seal as module
        original=module.fcntl.fcntl
        def unavailable(fd,operation,*values):
            if operation==module.DUPFD_QUERY:raise OSError(errno.EINVAL,'explicit unsupported kernel seam')
            return original(fd,operation,*values)
        before={int(row.name) for row in Path('/proc/self/fd').iterdir()}
        with patch.object(module.fcntl,'fcntl',side_effect=unavailable):
            with self.assertRaises(module.CandidateReadSealUnavailable):self.create()
        self.assertEqual(before,{int(row.name) for row in Path('/proc/self/fd').iterdir()})

    def test_object_finalization_releases_original_descriptor(self):
        import gc
        import weakref
        seal=self.create();fd=seal.rows[0][2];reference=weakref.ref(seal)
        del seal;gc.collect();self.assertIsNone(reference())
        with self.assertRaises(OSError):os.fstat(fd)

if __name__ == '__main__':
    unittest.main(verbosity=2)
