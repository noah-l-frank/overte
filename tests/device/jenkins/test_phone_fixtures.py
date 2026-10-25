#!/usr/bin/env python3
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
"""Host-owned fixture lifecycle, with no device/SDK/ADB calls."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
from types import SimpleNamespace
import unittest
from urllib.parse import urlsplit

HERE = Path(__file__).parent
ROOT = HERE.parents[2]

def load(name):
    spec = importlib.util.spec_from_file_location(name, HERE / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

fixtures = load('phone_fixtures')
owned = load('phone_owned_scene')

class FixtureTests(unittest.TestCase):
    def test_pinned_reference_rejects_changed_bytes_and_alias(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            path = root / 'input.json'
            path.write_text('{}')
            context = SimpleNamespace(admission=SimpleNamespace(deployment=root))
            ref = dict(path='input.json', sha256=hashlib.sha256(b'{}').hexdigest())
            self.assertEqual(fixtures.checked_reference(context, ref)[1], b'{}')
            path.write_text('{"changed":true}')
            with self.assertRaisesRegex(ValueError, 'REFERENCE_CHANGED'):
                fixtures.checked_reference(context, ref)
            (root / 'alias').symlink_to(path)
            with self.assertRaisesRegex(ValueError, 'REFERENCE_ALIAS'):
                fixtures.checked_reference(context, dict(ref, path='alias'))

    def test_domain_semantics_preserve_original_url_and_feet_spawn(self):
        manifest = json.loads((ROOT / 'tests/device/fixture/domain-manifest.json').read_bytes())
        domain = dict(schemaVersion=1, domainUrl='hifi://127.0.0.1:40102' + manifest['spawnPath'],
                      domainHost='127.0.0.1', domainId='7c342493-99f8-4350-9760-5268381b7638',
                      requiredMarkers=manifest['requiredMarkers'], expectedEntityCount=manifest['expectedEntityCount'])
        keys = ('DOMAIN_URL', 'DOMAIN_HOST', 'DOMAIN_ID', 'DOMAIN_MARKERS_JSON', 'DOMAIN_CONTROL_URL', 'DOMAIN_CONTROL_TOKEN')
        expected = {'OVERTE_E2E_' + key: str(index) for index, key in enumerate(keys)}
        expected['OVERTE_E2E_DOMAIN_URL'] = domain['domainUrl']
        original = SimpleNamespace(environment=lambda scene, ready: expected)
        actual = fixtures.domain_environment(original, {}, domain, manifest)
        self.assertEqual(actual, expected)
        for replacement in ('hifi://127.0.0.1:40102/0,2,0', 'hifi://user@127.0.0.1:40102' + manifest['spawnPath']):
            with self.subTest(url=replacement), self.assertRaises(ValueError):
                fixtures.domain_environment(original, {}, dict(domain, domainUrl=replacement), manifest)

    def scene(self, directory):
        root = Path(directory).resolve()
        source = root / 'source'
        shutil.copytree(ROOT / 'tests/device/fixture', source / 'tests/device/fixture', ignore=shutil.ignore_patterns('__pycache__'))
        probe = source / 'tests/device/probe'
        probe.mkdir(parents=True)
        shutil.copyfile(ROOT / 'tests/device/probe/overte_e2e_probe.js', probe / 'overte_e2e_probe.js')
        inventory = {p.relative_to(source).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in source.rglob('*') if p.is_file()}
        inventory_path = root / 'inventory.json'
        inventory_path.write_text(json.dumps(inventory))
        config = root / 'config.json'
        config.write_text(json.dumps(dict(bind='127.0.0.1', port=0, publicHost='127.0.0.1')))
        return owned.OwnedScene(source, inventory_path, owned.digest(inventory_path), config,
                               owned.digest(config), root / 'runtime', allow_ephemeral_loopback=True)

    def test_real_owned_original_http_bytes_and_explicit_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            service = self.scene(directory)
            try:
                service.__enter__()
                self.assertIsNone(service.process.poll())
                self.assertEqual(service.environment['OVERTE_E2E_SCENE_URL'], service.ready['sceneUrl'])
                self.assertTrue(urlsplit(service.ready['sceneUrl']).query)
                receipt = json.loads((service.runtime / 'START_RESULT.actual.json').read_bytes())
                self.assertEqual(len(receipt['actualHttpEvidence']), 2)
                self.assertTrue(all(row['status'] == 200 for row in receipt['actualHttpEvidence']))
                self.assertFalse(service.__exit__(ValueError, ValueError('host failure'), None))
                self.assertIsNone(service.process.poll())
                self.assertIsNone(service.cleanup)
            finally:
                service.stop()
            self.assertTrue(service.cleanup['complete'])
            self.assertIsNotNone(service.process.returncode)

    def test_http_observation_failure_keeps_exact_child_and_logs(self):
        with tempfile.TemporaryDirectory() as directory:
            service = self.scene(directory)
            original = owned.read_listener_json
            def reject(*args):
                raise ValueError('PHONE_HOSTTEST_HTTP_OBSERVATION_FAILURE')
            owned.read_listener_json = reject
            try:
                with self.assertRaisesRegex(ValueError, 'HOSTTEST_HTTP'):
                    service.__enter__()
                self.assertIsNone(service.process.poll())
                self.assertIsNone(service.cleanup)
                self.assertTrue((service.runtime / 'server.private.log').is_file())
                self.assertTrue((service.runtime / 'START_FAILURE.actual.json').is_file())
            finally:
                owned.read_listener_json = original
                service.stop()  # Deliberate disposal of this unit test's exact owner.
            self.assertTrue(service.cleanup['complete'])

if __name__ == '__main__':
    unittest.main()
