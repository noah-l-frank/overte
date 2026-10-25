#!/usr/bin/env python3
"""Host admission regressions: no device processes, credentials, or services."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import phone_runtime as runtime
import phone_worker as worker


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class RuntimeAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.deploy = self.root / 'deployment'
        self.deploy.mkdir()
        self.source = self.deploy / 'source'
        self.client = self.deploy / 'client'
        self.source.mkdir()
        self.client.mkdir()
        names = ['tests/device/catalog.json', 'tests/device/capabilities.json',
                 'tests/device/contracts.py', 'tests/device/feature_journeys/scenarios.py',
                 'tests/device/jenkins/phone_selection.py', 'tests/device/jenkins/phone_worker.py',
                 'tests/device/run.py', 'tests/device/policies/android-phone-flat-touch.json']
        for name in names:
            target = self.source / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(HERE.parents[2] / name, target)
        for name in ('fixture.py', 'tutorial.py'):
            (self.source / name).write_text('raise AssertionError("helper imported before admission")\n')
        (self.client / 'client.cpp').write_text('// original client source\n')
        self.runs = self.root / 'runs'
        self.runs.mkdir()
        self.env = {'JOB_NAME': 'overte-pixel6a', 'BUILD_NUMBER': '42',
                    'OVT_PHONE_EXECUTION': 'live', 'OVT_PHONE_FAILURE_POLICY': 'debug-hold',
                    'OVT_PHONE_SCOPE': 'single-test', 'OVT_PHONE_AREA': 'world-navigation',
                    'OVT_PHONE_CASE': 'domain-enter'}
        source_inventory = {path.relative_to(self.source).as_posix(): sha(path)
                            for path in self.source.rglob('*') if path.is_file()}
        client_inventory = {'client.cpp': sha(self.client / 'client.cpp')}
        self.write('source-inventory.json', source_inventory)
        self.write('client-inventory.json', client_inventory)
        delta = {name: {'client': client_inventory.get(name), 'harness': source_inventory.get(name)}
                 for name in sorted(set(client_inventory) | set(source_inventory))}
        self.write('delta.json', delta)
        for name in ('adapter.json', 'environment.json', 'targets.json', 'debug.json', 'fixture.json'):
            self.write(name, {})
        (self.deploy / 'candidate.apk').write_bytes(b'candidate identity bytes, never installed')
        self.recipe = {'schemaVersion': 1, 'kind': 'original-harness-v1',
                       'moduleIds': ['launch-smoke', 'domain-enter'], 'sourceRevision': 'a' * 40,
                       'clientSourceRevision': 'b' * 40, 'candidateSha256': sha(self.deploy / 'candidate.apk'),
                       'capabilities': ['app.launch', 'process.inspect', 'app.foreground', 'probe.snapshot',
                                        'navigation.enter-domain', 'scene.load'],
                       'files': {key: self.ref(path) for key, path in {
                           'originalRun': 'source/tests/device/run.py', 'adapterManifest': 'adapter.json',
                           'environment': 'environment.json', 'targets': 'targets.json', 'debugTemplate': 'debug.json',
                           'fixtureHelper': 'source/fixture.py', 'fixtureConfig': 'fixture.json',
                           'tutorialHelper': 'source/tutorial.py',
                           'tabletPolicy': 'source/tests/device/policies/android-phone-flat-touch.json'}.items()}}
        # Obtain exactly the real plan's capability union, never a dummy runner.
        import phone_selection
        self.recipe['capabilities'] = phone_selection.build_index(self.source / 'tests/device/catalog.json')['plans']['single-test:domain-enter']['requiredCapabilities']
        self.write('recipe.json', self.recipe)
        self.manifest = {'schemaVersion': 1, 'deploymentRoot': str(self.deploy), 'runRoot': str(self.runs),
                         'source': {'root': str(self.source), 'revision': 'a' * 40, 'inventory': self.ref('source-inventory.json')},
                         'client': {'root': str(self.client), 'revision': 'b' * 40, 'inventory': self.ref('client-inventory.json')},
                         'delta': self.ref('delta.json'), 'catalog': self.ref('source/tests/device/catalog.json'),
                         'planner': self.ref('source/tests/device/jenkins/phone_selection.py'),
                         'worker': self.ref('source/tests/device/jenkins/phone_worker.py'),
                         'candidate': {**self.ref('candidate.apk'), 'sourceRevision': 'b' * 40},
                         'recipes': {name: self.ref('recipe.json') for name in self.recipe['moduleIds']}}
        self.manifest_path = self.deploy / 'manifest.private.json'
        self.save_manifest()

    def write(self, name, value):
        path = self.deploy / name
        path.write_text(json.dumps(value))
        path.chmod(0o600)
        return path

    def ref(self, name):
        return {'path': name, 'sha256': sha(self.deploy / name)}

    def save_manifest(self):
        self.write('manifest.private.json', self.manifest)
        return sha(self.manifest_path)

    def admit(self):
        with patch('subprocess.Popen', side_effect=AssertionError('process started during admission')), \
             patch('socket.socket', side_effect=AssertionError('network during admission')):
            return runtime.admit(self.manifest_path, sha(self.manifest_path), self.env)

    def test_complete_read_only_admission_uses_real_selection(self):
        admitted = self.admit()
        self.assertEqual(admitted.plan['moduleIds'], ['launch-smoke', 'domain-enter'])
        self.assertEqual(admitted.run_root, self.runs / 'overte-pixel6a-42')
        self.assertEqual(list(self.runs.iterdir()), [])
        self.assertFalse((self.source / '__pycache__').exists())

    def test_tampered_inputs_and_extra_source_rejected_before_import_or_output(self):
        for target in ('adapter.json', 'source/fixture.py', 'candidate.apk'):
            path = self.deploy / target
            original = path.read_bytes()
            path.write_bytes(original + b'changed')
            with self.subTest(target=target), self.assertRaises(runtime.AdmissionError):
                self.admit()
            path.write_bytes(original)
        (self.source / 'unreviewed.py').write_text('pass\n')
        with self.assertRaisesRegex(runtime.AdmissionError, 'INVENTORY_INCOMPLETE'):
            self.admit()
        self.assertEqual(list(self.runs.iterdir()), [])

    def test_path_escape_and_symlink_rejected(self):
        self.manifest['delta']['path'] = '../outside.json'
        self.save_manifest()
        with self.assertRaisesRegex(runtime.AdmissionError, 'REFERENCE_ESCAPE'):
            self.admit()
        self.manifest['delta'] = self.ref('delta.json')
        self.save_manifest()
        (self.deploy / 'adapter.json').unlink()
        (self.deploy / 'adapter.json').symlink_to(self.deploy / 'debug.json')
        with self.assertRaises(runtime.AdmissionError):
            self.admit()

    def test_wrong_source_delta_candidate_and_missing_recipe_never_fall_back(self):
        mutations = [lambda: self.manifest['candidate'].update(sourceRevision='c' * 40),
                     lambda: self.manifest['recipes'].pop('domain-enter'),
                     lambda: self.manifest.update(delta=self.ref('source-inventory.json'))]
        original = copy.deepcopy(self.manifest)
        for mutate in mutations:
            self.manifest = copy.deepcopy(original)
            mutate()
            self.save_manifest()
            with self.assertRaises(runtime.AdmissionError):
                self.admit()
        self.assertEqual(list(self.runs.iterdir()), [])

    def test_namespace_policy_unknown_selection_and_reused_run_rejected(self):
        original = dict(self.env)
        for key, value in [('JOB_NAME', 'other-job'), ('BUILD_NUMBER', '../1'),
                           ('OVT_PHONE_EXECUTION', 'plan'), ('OVT_PHONE_FAILURE_POLICY', 'cleanup'),
                           ('OVT_PHONE_CASE', 'unregistered')]:
            self.env = dict(original, **{key: value})
            with self.subTest(key=key), self.assertRaises(runtime.AdmissionError):
                self.admit()
        self.env = original
        (self.runs / 'overte-pixel6a-42').mkdir()
        with self.assertRaisesRegex(runtime.AdmissionError, 'FRESH_RUN_REQUIRED'):
            self.admit()


class WorkerGuardTests(unittest.TestCase):
    def test_nonpass_holds_before_next_module_or_cleanup_and_release_is_distinct(self):
        from types import SimpleNamespace
        events = []
        class Held(BaseException):
            pass
        def run(row, *args, **kwargs):
            events.append(('run', row['id']))
            return {'status': 'failed', 'returncode': 1}
        def hold(reason, **kwargs):
            events.append(('hold', reason))
            raise Held()
        runner = SimpleNamespace(run_module=run)
        worker.install_first_failure(runner, SimpleNamespace(hold=hold), lambda: events.append(('tutorial',)))
        with self.assertRaises(Held):
            for identifier in ('launch-smoke', 'domain-enter', 'domain-roundtrip'):
                runner.run_module({'id': identifier})
            events.append(('cleanup',))
        self.assertEqual(events, [('run', 'launch-smoke'), ('hold', 'PHONE_FIRST_MODULE_NONPASS')])
        self.assertEqual(worker.RELEASED, 77)

    def test_tutorial_between_successful_launch_and_target_and_no_skipped_green(self):
        from types import SimpleNamespace
        events = []
        runner = SimpleNamespace(run_module=lambda row: events.append(row['id']) or {'status': 'passed', 'returncode': 0})
        policy = SimpleNamespace(hold=lambda *args, **kwargs: self.fail('unexpected hold'))
        worker.install_first_failure(runner, policy, lambda: events.append('tutorial-observed'))
        for identifier in ('launch-smoke', 'domain-enter', 'domain-roundtrip'):
            runner.run_module({'id': identifier})
        self.assertEqual(events, ['launch-smoke', 'tutorial-observed', 'domain-enter', 'domain-roundtrip'])
        for status in ('skipped', 'error', 'failed'):
            with self.assertRaises(worker.WorkerError):
                worker.assert_complete({'status': 'passed', 'results': [{'id': 'launch-smoke', 'status': status, 'returncode': 0}]}, ['launch-smoke'])
        with self.assertRaises(worker.WorkerError):
            worker.assert_complete({'status': 'passed', 'results': []}, ['launch-smoke'])

    def test_tutorial_requires_fresh_stable_grounded_independent_observations(self):
        rows = [{'runNonce': 'fresh', 'observedEpochMs': stamp, 'processIdentity': 'same-process',
                 'sceneUrl': worker.TUTORIAL_URL, 'protocol': 'file', 'serverless': True,
                 'connected': False, 'entityCount': 39, 'feet': list(worker.TUTORIAL_FEET),
                 'inAir': False, 'flying': False, 'velocity': [0, .00293, 0]} for stamp in (1000, 1300, 1600)]
        self.assertTrue(worker.validate_tutorial(rows, 'fresh', 999, 1700))
        for field, value in [('runNonce', 'old'), ('observedEpochMs', 1001), ('entityCount', 0),
                             ('flying', True), ('sceneUrl', 'about:blank'), ('feet', [0, 0, 4]),
                             ('velocity', [float('nan'), 0, 0])]:
            broken = copy.deepcopy(rows)
            broken[1][field] = value
            with self.subTest(field=field), self.assertRaises(worker.WorkerError):
                worker.validate_tutorial(broken, 'fresh', 999, 1700)

    def test_preparation_base_exception_holds_before_target_or_cleanup(self):
        from types import SimpleNamespace
        class Held(BaseException):
            pass
        events = []
        def hold(*args, **kwargs):
            events.append('hold')
            raise Held()
        def tutorial():
            raise KeyboardInterrupt()
        policy = SimpleNamespace(cleanup_authorized=False, hold=hold,
                                 record_exception=lambda *args: events.append('private-exception'))
        runner = SimpleNamespace(run_module=lambda row: events.append(row['id']) or {'status': 'passed', 'returncode': 0})
        worker.install_first_failure(runner, policy, tutorial)
        runner.run_module({'id': 'launch-smoke'})
        with self.assertRaises(Held):
            runner.run_module({'id': 'domain-enter'})
        self.assertEqual(events, ['launch-smoke', 'private-exception', 'hold'])

    def test_public_export_is_build_bound_sealed_and_rejects_hash_tampering(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            stage = root / 'stage'
            stage.mkdir()
            (stage / 'summary.json').write_bytes(b'{"status":"error"}')
            index = {'files': [{'path': 'summary.json', 'sha256': sha(stage / 'summary.json'),
                                'bytes': (stage / 'summary.json').stat().st_size}]}
            (stage / 'artifact-index.json').write_text(json.dumps(index))
            (stage / 'debug-state.json').write_text(json.dumps({'artifacts': {'artifact-index.json': {
                'sha256': sha(stage / 'artifact-index.json'), 'bytes': (stage / 'artifact-index.json').stat().st_size}}}))
            validated = []
            policy = SimpleNamespace(stage=stage, validate_public_data=lambda: validated.append(True))
            destination = root / 'public' / '42'
            with patch.dict(os.environ, {'BUILD_NUMBER': '42'}):
                worker.export_public(policy, destination)
            exported = json.loads((destination / 'export-index.json').read_bytes())
            self.assertEqual(exported['runNamespace'], 'overte-pixel6a-42')
            self.assertEqual(exported['build'], 42)
            self.assertEqual((destination / 'EXPORT_READY').read_text().strip(), sha(destination / 'export-index.json'))
            self.assertEqual(set(exported['files']), {'summary.json', 'artifact-index.json', 'debug-state.json'})
            self.assertEqual(validated, [True])
            (stage / 'summary.json').write_bytes(b'tampered private bytes')
            rejected = root / 'rejected'
            with patch.dict(os.environ, {'BUILD_NUMBER': '42'}), self.assertRaises(worker.WorkerError):
                worker.export_public(policy, rejected)
            self.assertFalse((rejected / 'EXPORT_READY').exists())


if __name__ == '__main__':
    unittest.main()
