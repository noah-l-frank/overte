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


if __name__ == '__main__':
    unittest.main(verbosity=2)
