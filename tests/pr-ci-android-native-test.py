#!/usr/bin/env python3
"""Host joins reject stale/unowned native evidence before accepting a result.

Execution-boundary calls are intercepted here; these are controller contracts,
not claims of actual Android build qualification.
"""
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/repository-checks'))
import pr_ci_android_native as N


class NativeHostTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.candidate = self.root / 'candidate'; self.candidate.mkdir()
        self.prepared = self.root / 'prepared'; self.prepared.mkdir()
        (self.prepared / 'qualification').mkdir()
        for name in ('sdk', 'runtime'):
            (self.prepared / (name + '-inventory.json')).write_text('test fixture inventory')
        (self.candidate / 'conanfile.py').write_bytes(b'fixed declaration')
        self.intent = {'conanfile.py': hashlib.sha256(b'fixed declaration').hexdigest()}
        self.context = {'target': 'android-phone', 'original_merge': '1' * 40, 'tree': '2' * 40}
        self.plan = {'android_native_products': ['phone']}
        self.definition = {'assets': {name: {'inventory': {'sha256': value * 64}}
            for name, value in (('sdk', 'a'), ('runtime', 'b'))}}
        self.definition['assets']['image'] = {'archive': {'sha256': 'c' * 64}}
    def tearDown(self):
        self.temp.cleanup()
    def test_only_exact_owning_product_is_admitted(self):
        for target, product in N.OWNER.items():
            self.assertEqual(N.products({'android_native_products': [product]}, target), [product])
            self.assertEqual(N.products({}, target), [])
        for target, selected in (('main', ['phone']), ('android-phone', ['pico']),
                                 ('android-vr-pico', ['common']), ('android-main', ['common', 'common']),
                                 ('android-phone', 'phone')):
            with self.subTest(target=target, selected=selected), self.assertRaises(ValueError):
                N.products({'android_native_products': selected}, target)
    def test_unselected_change_does_not_load_or_prepare_native_assets(self):
        with patch.object(N.A, 'policy', side_effect=AssertionError('no native setup')):
            self.assertIsNone(N.prerequisites(self.candidate, {}, 'android-phone'))

    def test_groovy_classpath_is_separately_sealed_and_modified_jars_reject(self):
        tools = self.root / 'groovy'; tools.mkdir()
        jar = tools / 'groovy.jar'; jar.write_bytes(b'transport fixture only')
        ledger = tools.with_name('groovy-inventory.json'); ledger.write_bytes(N.R.canonical(N.R.inventory(tools)))
        definition = {'assets': {'groovy': {'inventory': {'sha256': N.R.digest(ledger)}}}}
        with patch.object(N.A, 'policy', return_value=definition):
            self.assertEqual(N.groovy_classpath(tools), str(jar))
            jar.write_bytes(b'modified fixture')
            with self.assertRaisesRegex(ValueError, 'payload differs'):
                N.groovy_classpath(tools)
    def test_changed_missing_and_aliased_dependency_declarations_fail_early(self):
        N.check_intent(self.candidate, self.intent)
        source = self.candidate / 'conanfile.py'
        source.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'declarations changed'):
            N.check_intent(self.candidate, self.intent)
        source.unlink(); source.symlink_to(self.root / 'foreign')
        (self.root / 'foreign').write_bytes(b'fixed declaration')
        with self.assertRaises(ValueError):
            N.check_intent(self.candidate, self.intent)
        with self.assertRaises(ValueError):
            N.check_intent(self.candidate, {})

    def test_insufficient_capacity_stops_before_any_native_asset_preparation(self):
        with patch.object(N.A, 'policy', return_value={'status': 'qualified'}), \
             patch.object(N, 'capacity_admission', side_effect=ValueError('insufficient capacity')), \
             patch.object(N.A, 'prepare') as prepare, self.assertRaisesRegex(ValueError, 'capacity'):
            N.prepare(self.root / 'new-native', self.root / 'cache')
        prepare.assert_not_called()
        self.assertFalse((self.root / 'cache').exists())

    def test_capacity_uses_fixed_tokenless_daemon_and_protected_phase_budget(self):
        limit = {name: 1 for name in N.CAP.KEYS}
        policy = {'status': 'qualified', 'capacity': {phase: dict(limit, workspace_free_bytes=index)
            for index, phase in enumerate(('bootstrap', 'prepare', 'execute'), 1)}}
        with patch.object(N.subprocess, 'run') as docker, patch.object(N.CAP, 'admit', return_value={'result': 'admitted'}) as admit:
            docker.return_value.stdout = b'"/var/lib/docker"\n'
            for phase in ('bootstrap', 'prepare', 'execute'):
                self.assertEqual(N.capacity_admission(policy, self.prepared, self.root, phase)['result'], 'admitted')
                self.assertEqual(admit.call_args.args[0], policy['capacity'][phase])
            argv = docker.call_args.args[0]
            self.assertEqual(argv[:4], ['/usr/bin/docker', '--host=unix:///var/run/docker.sock', 'info', '--format'])
            self.assertEqual(set(docker.call_args.kwargs['env']), {'PATH', 'HOME', 'DOCKER_CONFIG', 'LANG', 'LC_ALL'})
            self.assertEqual(admit.call_count, 3)
            self.assertEqual(admit.call_args.args[1:], (self.prepared, self.root, '/var/lib/docker'))
        with patch.object(N.subprocess, 'run') as docker:
            for value in ({'status': 'awaiting-local-qualification'}, {'status': 'qualified'},
                          {'status': 'qualified', 'capacity': {'prepare': limit}},
                          {'status': 'qualified', 'capacity': {'prepare': limit, 'execute': limit}}):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    N.capacity_admission(value, self.prepared, self.root, 'prepare')
            docker.assert_not_called()
    def test_early_cli_and_materialization_use_distinct_capacity_phases(self):
        definition = {'status': 'qualified'}
        with patch.object(N.A, 'policy', return_value=definition), \
             patch.object(N, 'capacity_admission', return_value={'result': 'admitted'}) as admit, \
             patch.object(sys, 'argv', ['native', '--capacity-only', '--destination', str(self.prepared),
                                        '--cache', str(self.root)]), patch('sys.stdout', new_callable=io.StringIO):
            N.main()
            admit.assert_called_once_with(definition, self.prepared, self.root, 'bootstrap')
        with patch.object(N.A, 'policy', return_value=definition), \
             patch.object(N, 'capacity_admission', side_effect=ValueError('stop before downloads')) as admit, \
             patch.object(N.A, 'prepare') as prepare, self.assertRaises(ValueError):
            N.prepare(self.prepared, self.root)
        admit.assert_called_once_with(definition, self.prepared, self.root, 'prepare')
        prepare.assert_not_called()

    def test_protected_template_and_baseline_are_digest_bound(self):
        path = self.prepared / 'qualification' / 'proof.json'; path.write_text('{"actual":"bytes"}')
        reference = {'path': 'proof.json', 'sha256': N.R.digest(path)}
        self.assertEqual(N.read_bound(path.parent, reference), {'actual': 'bytes'})
        path.write_text('{"actual":"other"}')
        with self.assertRaisesRegex(ValueError, 'differs'):
            N.read_bound(path.parent, reference)
        path.unlink(); path.symlink_to(self.candidate / 'conanfile.py')
        with self.assertRaises(ValueError):
            N.read_bound(path.parent, reference)

    def test_baseline_cannot_qualify_changed_runtime_sdk_image_or_template(self):
        proof = self.prepared / 'qualification'
        template = {'product': 'phone', 'dependency_intent': self.intent, 'candidate_tree': self.context['tree']}
        path = proof / 'template.json'; path.write_bytes(N.R.canonical(template))
        baseline = {'kind': 'overte-android-offline-consumer-result-v1', 'result': 'success', 'product': 'phone',
            'candidate_sha': self.context['original_merge'], 'candidate_tree': self.context['tree'],
            'device_tested': False, 'actual_build_exit_code': 0, 'executed_build_commands': [['intercepted fixture']],
            'apk_qualified': True, 'config_sha256': N.R.digest(path), 'runtime_inventory_sha256': 'b' * 64,
            'sdk_inventory_sha256': 'a' * 64, 'toolchain_image_archive_sha256': 'c' * 64}
        reference = {'path': 'template.json', 'sha256': N.R.digest(path)}
        for mutation in ({}, {'runtime_inventory_sha256': 'd' * 64}, {'sdk_inventory_sha256': 'd' * 64},
                         {'toolchain_image_archive_sha256': 'd' * 64}, {'config_sha256': 'd' * 64},
                         {'candidate_tree': '3' * 40}, {'executed_build_commands': []}):
            completed = proof / 'baseline.json'; completed.write_bytes(N.R.canonical(baseline | mutation))
            value = deepcopy(self.definition)
            value['products'] = {'phone': {'template': reference, 'dependency_intent': self.intent,
                'baseline': {'source': self.context['original_merge'], 'tree': self.context['tree'],
                             'receipt_path': 'baseline.json', 'receipt_sha256': N.R.digest(completed)}}}
            if not mutation:
                self.assertEqual(N.load_template(self.prepared, value, 'phone'), template)
            else:
                with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                    N.load_template(self.prepared, value, 'phone')
    def invoke(self, status=0, mutation=None):
        template = {'product': 'phone', 'dependency_intent': self.intent}
        authenticated = []
        def boundary(*_args, **options):
            config = options['qualification'] / 'consumer.json'
            receipt = {'kind': 'overte-android-offline-consumer-result-v1', 'result': 'success',
                'product': 'phone', 'candidate_sha': self.context['original_merge'],
                'candidate_tree': self.context['tree'], 'device_tested': False, 'apk_qualified': True,
                'actual_build_exit_code': 0, 'executed_build_commands': [['fixture intercepted build']],
                'config_sha256': N.R.digest(config), 'runtime_inventory_sha256': 'b' * 64,
                'sdk_inventory_sha256': 'a' * 64}
            if mutation:
                receipt.update(mutation)
            (options['scratch'] / 'android-native-execution.json').write_text(json.dumps(receipt))
            return status
        with patch.object(N.A, 'policy', return_value=self.definition), \
             patch.object(N, 'capacity_admission'), \
             patch.object(N, 'validate_prepared', return_value=self.prepared), \
             patch.object(N, 'load_template', return_value=template), \
             patch.object(N.B, 'run', side_effect=boundary) as run:
            value = N.execute(self.candidate, self.context, self.plan, self.prepared,
                              authenticate=lambda: authenticated.append(True))
        return value, authenticated, run.call_count
    def test_single_successful_execution_is_bound_before_and_after(self):
        value, authenticated, count = self.invoke()
        self.assertEqual(count, 1)
        self.assertEqual(authenticated, [True, True])
        self.assertEqual(value['product'], 'phone')
    def test_failure_or_stale_source_runtime_and_skip_claims_are_not_accepted(self):
        for mutation in ({'candidate_sha': '3' * 40}, {'product': 'pico'}, {'device_tested': True},
                         {'runtime_inventory_sha256': 'c' * 64}, {'config_sha256': 'c' * 64},
                         {'actual_build_exit_code': 77}, {'executed_build_commands': []},
                         {'apk_qualified': False}):
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                self.invoke(mutation=mutation)
        with self.assertRaisesRegex(ValueError, 'failed'):
            self.invoke(status=1)
    def test_unselected_native_execution_never_launches_a_boundary(self):
        self.plan['android_native_products'] = []
        with patch.object(N.B, 'run') as run, self.assertRaisesRegex(ValueError, 'Unselected'):
            N.execute(self.candidate, self.context, self.plan, self.prepared, authenticate=lambda: None)
        run.assert_not_called()


if __name__ == '__main__':
    unittest.main()
