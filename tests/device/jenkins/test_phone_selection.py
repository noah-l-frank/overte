#!/usr/bin/env python3
"""Host-only contracts for registered Phone selection; no adapter execution."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import copy
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
from contextlib import redirect_stderr
import io
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import phone_selection as selection
from execution_plan import load_profiles, module_capabilities

CATALOG = HERE.parent / 'catalog.json'
# The historical standard Phone job contained precisely these35 source IDs.
# Only suite membership is preserved here; executable definitions stay in the
# one common catalog and are never duplicated in a second runnable catalog.
BASELINE_IDS = set('''launch-smoke voice-roundtrip update-upgrade scene spawn-grounded
domain-enter domain-roundtrip world-interaction scripted-entity multi-user
network-fault-recovery text-input audio-controls settings-persistence lifecycle-under-load
render-health entity-sync permission-recovery crash-recovery-under-load asset-load
sound-playback look move input-neutral collision scene-reload jump fly tablet
tablet-input-isolation app-restart tablet-e2e accessibility lifecycle-soak idle-soak'''.split())


class PhoneSelectionTests(unittest.TestCase):
    def setUp(self):
        self.catalog = json.loads(CATALOG.read_text())
        self.index = selection.build_index(CATALOG)

    def modified(self, mutate):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        data = copy.deepcopy(self.catalog)
        mutate(data)
        path = Path(temporary.name) / 'catalog.json'
        path.write_text(json.dumps(data))
        return path

    def test_whole_catalog_and_exact_historical_baseline_are_registered_only(self):
        index = self.index
        self.assertEqual(index['catalogSha256'], hashlib.sha256(CATALOG.read_bytes()).hexdigest())
        self.assertEqual(len(index['featureAreas']), 14)
        self.assertEqual(index['singleTests'], [m['id'] for m in self.catalog['modules']])
        self.assertEqual(set(index['plans']['baseline']['moduleIds']), BASELINE_IDS)
        self.assertEqual(len(index['plans']['baseline']['moduleIds']), 35)
        self.assertEqual(index['plans']['readiness']['moduleIds'], ['launch-smoke'])
        for plan in index['plans'].values():
            self.assertEqual(plan['qualification'], selection.QUALIFICATION)
            self.assertEqual(plan['moduleIds'][:len(plan['setupModuleIds'])], plan['setupModuleIds'])
            self.assertEqual(len(set(plan['moduleIds'])), len(plan['moduleIds']))
            self.assertNotIn('status', plan)

    def test_phone_catalog_and_original_execution_profiles_remain_compatible(self):
        # The Phone planner adds suite tags to the shared catalog. The original
        # execution planner admits an exact registry match for every platform;
        # a Phone-only planning test must detect an unregistered shared tag.
        profiles = load_profiles(HERE.parent / 'execution-profiles.json', CATALOG)
        identifiers, capabilities = module_capabilities(CATALOG, 'phone-baseline')
        baseline = self.index['plans']['baseline']
        self.assertEqual(identifiers, baseline['moduleIds'])
        self.assertEqual(capabilities, baseline['requiredCapabilities'])
        profile = profiles['suites']['phone-baseline']
        self.assertEqual(profile['fixture'], 'domain')
        self.assertTrue(profile['tabletPolicy'])
        self.assertEqual(set(profile['artifacts']), {'candidate', 'source'})
        with tempfile.TemporaryDirectory() as temporary:
            missing = copy.deepcopy(profiles)
            del missing['suites']['phone-baseline']
            path = Path(temporary) / 'profiles.json'
            path.write_text(json.dumps(missing))
            with self.assertRaisesRegex(ValueError, 'missing: phone-baseline'):
                load_profiles(path, CATALOG)

    def test_area_plans_keep_gate_foundations_and_original_requirements_budgets(self):
        by_id = {m['id']: m for m in self.catalog['modules']}
        for area in self.index['featureAreas']:
            plan = self.index['plans']['feature-area:' + area['id']]
            self.assertEqual(plan['moduleIds'], [m['id'] for m in self.catalog['modules'] if area['suite'] in m['suites']])
            self.assertEqual(plan['setupModuleIds'], ['launch-smoke', area['suite'] + '-required'])
            for row in plan['modules']:
                self.assertEqual(row, {key: by_id[row['id']][key] for key in ('id', 'description', 'timeoutSeconds', 'requires')})
            self.assertEqual(plan['requiredCapabilities'], sorted({cap for m in plan['modules'] for cap in m['requires']}))

    def test_all_features_include14_gates_and_shared_tests_only_once(self):
        plan = self.index['plans']['all-features']
        self.assertEqual(len(plan['setupModuleIds']), 15)
        self.assertEqual(plan['moduleIds'], [m['id'] for m in self.catalog['modules'] if 'feature-journeys' in m['suites']])
        self.assertEqual(plan['moduleIds'].count('domain-enter'), 1)
        self.assertEqual(plan['moduleIds'].count('text-input'), 1)

    def test_single_test_and_single_setup_are_explicit_without_expanding_an_area(self):
        plan = self.index['plans']['single-test:feature-world-navigation']
        self.assertEqual(plan['moduleIds'], ['launch-smoke', 'feature-world-navigation-required', 'feature-world-navigation'])
        self.assertEqual(plan['featureArea'], 'world-navigation')
        self.assertEqual(self.index['plans']['single-test:domain-enter']['moduleIds'], ['launch-smoke', 'domain-enter'])
        setup = self.index['plans']['single-test:feature-world-navigation-required']
        self.assertEqual(setup['moduleIds'], setup['setupModuleIds'])
        self.assertEqual(setup['testCase'], 'feature-world-navigation-required')

    def test_missing_gate_wrong_gate_command_and_missing_foundation_fail_closed(self):
        for mutate in (
            lambda c: c['modules'].remove(next(m for m in c['modules'] if m['id'] == 'feature-world-navigation-required')),
            lambda c: next(m for m in c['modules'] if m['id'] == 'feature-world-navigation-required').update(command=['modules/launch_smoke.py']),
            lambda c: next(m for m in c['modules'] if m['id'] == 'domain-enter')['suites'].remove('feature-world-navigation'),
        ):
            with self.subTest(mutate=mutate), self.assertRaises(selection.SelectionError):
                selection.build_index(self.modified(mutate))

    def test_empty_baseline_and_duplicate_modules_fail_closed(self):
        def remove_baseline(c):
            for module in c['modules']:
                if 'phone-baseline' in module['suites']:
                    module['suites'].remove('phone-baseline')
        for mutate in (remove_baseline, lambda c: c['modules'].append(copy.deepcopy(c['modules'][0]))):
            with self.assertRaises(selection.SelectionError):
                selection.build_index(self.modified(mutate))

    def test_source_byte_change_changes_catalog_identity_and_command_escape_rejects(self):
        path = self.modified(lambda c: next(m for m in c['modules'] if m['id'] == 'domain-enter').update(timeoutSeconds=181))
        changed = selection.build_index(path)
        self.assertNotEqual(changed['catalogSha256'], self.index['catalogSha256'])
        self.assertEqual(changed['plans']['single-test:domain-enter']['modules'][-1]['timeoutSeconds'], 181)
        escaped = self.modified(lambda c: c['modules'][0].update(command=['../untrusted.py']))
        with self.assertRaisesRegex(selection.SelectionError, 'PHONE_SELECTION_COMMAND_PATH'):
            selection.build_index(escaped)

    def test_unknown_ids_and_unsupported_combinations_never_fall_back(self):
        for args in (('unknown', None, None), ('baseline', 'audio', None),
                     ('feature-area', None, None), ('feature-area', 'missing', None),
                     ('single-test', None, 'missing'), ('single-test', 'audio', 'domain-enter'),
                     ('readiness', None, 'launch-smoke'), ('single-test', None, 12)):
            with self.subTest(args=args), self.assertRaises(selection.SelectionError):
                selection.select_plan(self.index, *args)
        selected = selection.select_plan(self.index, 'single-test', test_case='domain-enter')
        selected['moduleIds'].clear()
        self.assertTrue(self.index['plans']['single-test:domain-enter']['moduleIds'])

    def test_planning_never_runs_commands_contacts_network_or_reads_command_files(self):
        allowed_reads = {CATALOG.resolve(), (HERE.parent / 'capabilities.json').resolve()}
        original_open = Path.open
        def guarded_open(path, *args, **kwargs):
            self.assertIn(path.resolve(), allowed_reads)
            return original_open(path, *args, **kwargs)
        with patch('pathlib.Path.open', guarded_open), \
                patch.object(subprocess, 'run', side_effect=AssertionError('no subprocess')), \
                patch.object(subprocess, 'Popen', side_effect=AssertionError('no subprocess')), \
                patch.object(socket, 'socket', side_effect=AssertionError('no network')), \
                patch.object(os, 'system', side_effect=AssertionError('no shell')):
            self.assertEqual(selection.build_index(CATALOG), self.index)
        self.assertNotIn('adapter_client', selection.__dict__)
        self.assertNotIn('run', selection.__dict__)

    def test_cli_writes_only_plan_and_never_overwrites_existing_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / 'plan.json'
            args = ['--catalog', str(CATALOG), '--scope', 'single-test', '--test-case', 'domain-enter', '--output', str(output)]
            self.assertEqual(selection.main(args), 0)
            plan = json.loads(output.read_text())
            self.assertEqual(plan['moduleIds'], ['launch-smoke', 'domain-enter'])
            self.assertEqual(plan['catalogSha256'], self.index['catalogSha256'])
            before = output.read_bytes()
            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
                selection.main(args)
            self.assertEqual(caught.exception.code, 2)
            self.assertEqual(output.read_bytes(), before)


if __name__ == '__main__':
    unittest.main(verbosity=2)
