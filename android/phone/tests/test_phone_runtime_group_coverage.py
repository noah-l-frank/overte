#!/usr/bin/env python3
"""Check grouped host coverage against a separately frozen pre-grouping runner."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import hashlib
import contextlib
import io
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BASELINE_SHA256 = '37c7592854d3f3e18325bce663d1d19d7ca2145085fc553d74114f49a99412eb'
ORIGINAL_REVISION = '7b4a33873678990b663f21bdef0c0432c522baf1'
ORIGINAL_RUNNER_SHA256 = 'fb5633548ded183c19ee193c9c107bb30d948e8e617a666f028095a56c37440e'


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class OriginalPhoneCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw = (HERE / 'phone-runtime-coverage-baseline.json').read_bytes()
        if hashlib.sha256(raw).hexdigest() != BASELINE_SHA256:
            raise AssertionError('The independent original coverage fixture changed; review its provenance explicitly')
        cls.baseline = json.loads(raw)
        cls.original = cls.baseline['checkSets']
        cls.groups = load(HERE / 'phone_runtime_groups.py', '_phone_independent_group_coverage')
        cls.registry = json.loads((HERE / 'phone-runtime-groups.json').read_bytes())
        cls.driver = load(HERE / 'phone-e2e-runtime-regressions.py', '_phone_independent_group_driver')

    def validate(self, registry, **changes):
        originals = {key: list(value) for key, value in self.original.items()}
        originals.update(changes)
        return self.groups.validate_groups(
            registry, originals['DEPENDENCY_LIGHT_CHECKS'], originals['PREPARED_HOST_CHECKS'],
            originals['COMMON_HOST_CHECKS'], originals['EXTENDED_HOST_CHECKS'])

    def test_reference_is_the_original_pinned_190_238_and_extended_contract(self):
        self.assertEqual(self.baseline['sourceRevision'], ORIGINAL_REVISION)
        self.assertEqual(self.baseline['sourceSha256'], ORIGINAL_RUNNER_SHA256)
        self.assertEqual(len(self.original['DEPENDENCY_LIGHT_CHECKS']) + len(self.original['COMMON_HOST_CHECKS']), 190)
        self.assertEqual(len(self.original['PREPARED_HOST_CHECKS']) + len(self.original['COMMON_HOST_CHECKS']), 238)
        self.assertEqual(len(self.original['EXTENDED_HOST_CHECKS']), 1)
        self.assertEqual(len(self.baseline['checks']), 242)
        for names in self.original.values():
            self.assertEqual(len(names), len(set(names)))

    def test_original_driver_declarations_have_no_hidden_deletion_or_addition(self):
        for name, expected in self.original.items():
            self.assertEqual(list(getattr(self.driver, name)), expected, name)

    def test_every_mode_covers_each_original_file_exactly_once(self):
        self.validate(self.registry)
        rows = {row['id']: row for row in self.registry['groups']}
        for mode, first in (('default', 'DEPENDENCY_LIGHT_CHECKS'), ('execute', 'PREPARED_HOST_CHECKS')):
            for extended in (False, True):
                with self.subTest(mode=mode, extended=extended):
                    ids = self.registry['modes'][mode] + (self.registry['extendedGroups'] if extended else [])
                    selected = [name for identifier in ids for name in rows[identifier]['files']]
                    expected = self.original[first] + self.original['COMMON_HOST_CHECKS']
                    if extended:
                        expected += self.original['EXTENDED_HOST_CHECKS']
                    self.assertEqual(Counter(selected), Counter(expected))
                    self.assertEqual(len(selected), len(set(selected)))

    def test_deleting_one_registered_file_fails_closed(self):
        registry = deepcopy(self.registry)
        registry['groups'][0]['files'].pop()
        registry['groups'][0]['timeoutSeconds'] = self.groups.group_timeout(registry['groups'][0]['files'])
        with patch('subprocess.run') as child:
            with self.assertRaises(ValueError):
                self.validate(registry)
            child.assert_not_called()

    def test_duplicating_one_registered_file_fails_closed(self):
        registry = deepcopy(self.registry)
        registry['groups'][0]['files'].append(registry['groups'][0]['files'][0])
        registry['groups'][0]['timeoutSeconds'] = self.groups.group_timeout(registry['groups'][0]['files'])
        with patch('subprocess.run') as child:
            with self.assertRaises(ValueError):
                self.validate(registry)
            child.assert_not_called()

    def test_unknown_file_in_group_fails_closed(self):
        registry = deepcopy(self.registry)
        registry['groups'][0]['files'].append('android/phone/tests/test_unknown_runtime_contract.py')
        registry['groups'][0]['timeoutSeconds'] = self.groups.group_timeout(registry['groups'][0]['files'])
        with patch('subprocess.run') as child:
            with self.assertRaises(ValueError):
                self.validate(registry)
            child.assert_not_called()

    def test_foreign_path_is_rejected_even_if_added_to_declarations(self):
        for foreign in ('../outside.py', '/tmp/outside.py', 'android/phone/tests/../../../outside.py',
                        'tools/test_foreign_runtime_contract.py'):
            with self.subTest(path=foreign):
                registry = deepcopy(self.registry)
                common = [*self.original['COMMON_HOST_CHECKS'], foreign]
                common_ids = set(registry['modes']['default']) & set(registry['modes']['execute'])
                row = min((row for row in registry['groups'] if row['id'] in common_ids),
                          key=lambda value: len(value['files']))
                row['files'].append(foreign)
                row['timeoutSeconds'] = self.groups.group_timeout(row['files'])
                with patch('subprocess.run') as child:
                    with self.assertRaises(ValueError):
                        self.validate(registry, COMMON_HOST_CHECKS=common)
                    child.assert_not_called()

    def test_new_declared_test_without_a_group_fails_before_execution(self):
        common = [*self.original['COMMON_HOST_CHECKS'], 'android/phone/tests/test_new_runtime_contract.py']
        with patch('subprocess.run') as child:
            with self.assertRaises(ValueError):
                self.validate(self.registry, COMMON_HOST_CHECKS=common)
            child.assert_not_called()

    def assert_driver_rejects_without_dispatch(self, registry, *, new_common=None):
        common = self.driver.COMMON_HOST_CHECKS if new_common is None else tuple(new_common)
        with (patch.object(self.driver, 'load_registry', return_value=registry),
              patch.object(self.driver, 'COMMON_HOST_CHECKS', common),
              patch.object(self.driver, 'run_groups', return_value=0) as dispatch,
              patch('subprocess.run') as child,
              contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO())):
            try:
                result = self.driver.main([])
            except SystemExit as error:
                self.assertNotEqual(error.code, 0)
            except ValueError:
                pass
            else:
                self.assertNotEqual(result, 0)
            dispatch.assert_not_called()
            child.assert_not_called()

    def test_real_driver_revalidates_mutated_registry_before_dispatch(self):
        for mutation in ('delete', 'duplicate', 'unknown'):
            with self.subTest(mutation=mutation):
                registry = deepcopy(self.registry)
                files = registry['groups'][0]['files']
                if mutation == 'delete':
                    files.pop()
                elif mutation == 'duplicate':
                    files.append(files[0])
                else:
                    files.append('android/phone/tests/test_unknown_runtime_contract.py')
                registry['groups'][0]['timeoutSeconds'] = self.groups.group_timeout(files)
                self.assert_driver_rejects_without_dispatch(registry)

    def test_real_driver_new_declaration_cannot_be_silently_unregistered(self):
        common = [*self.original['COMMON_HOST_CHECKS'], 'android/phone/tests/test_new_runtime_contract.py']
        self.assert_driver_rejects_without_dispatch(self.registry, new_common=common)

    def test_all_original_child_timeouts_and_argument_forms_are_preserved(self):
        build_id = 'a' * 32
        applied = {row['file']: row['calibratedSeconds'] for row in self.groups.load_calibration()['files']}
        for name, original in self.baseline['checks'].items():
            with self.subTest(file=name):
                self.assertEqual(self.groups.original_file_timeout(name), original['timeoutSeconds'])
                self.assertEqual(self.driver.file_timeout(name), applied.get(name, original['timeoutSeconds']))
                command = self.driver.file_command(name, root=ROOT, python=sys.executable, build_id=build_id)
                expected = [sys.executable, str(ROOT / name)]
                if original['argumentStyle'] == 'root-argument':
                    expected.append(str(ROOT))
                elif original['argumentStyle'] == 'fresh-chat-build-directory':
                    expected += ['--build-dir', str(ROOT / 'build' / ('phone-chat-runtime-' + build_id))]
                else:
                    self.assertEqual(original['argumentStyle'], 'plain')
                self.assertEqual(command, expected)


if __name__ == '__main__':
    unittest.main()
