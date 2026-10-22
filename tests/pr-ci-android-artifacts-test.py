#!/usr/bin/env python3
"""Exercise source-bound preservation with actual files, Git and receipt bytes."""
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/repository-checks'))
import pr_ci_android_artifacts as E
import pr_ci_android_native as N


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = (json.dumps(value, sort_keys=True) + '\n').encode()
    path.write_bytes(raw)
    return raw


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.candidate = self.root / 'candidate'
        self.candidate.mkdir()
        def git(*arguments):
            return subprocess.check_output(['/usr/bin/git', '--no-replace-objects', '-C',
                str(self.candidate), *arguments], stderr=subprocess.PIPE).decode().strip()
        self.git = git
        git('init', '-q', '--initial-branch=test/main/native-export-fixture')
        git('config', 'user.name', 'Offline fixture')
        git('config', 'user.email', 'offline@example.invalid')
        (self.candidate / 'source.txt').write_text('tracked fixture\n')
        git('add', '--', 'source.txt')
        git('-c', 'core.hooksPath=/dev/null', 'commit', '-qm', 'Create offline source fixture')
        self.context = dict(target='android-main', original_merge=git('rev-parse', 'HEAD'),
            tree=git('rev-parse', 'HEAD^{tree}'), controller='3' * 40, run_id=123, run_attempt=2)
        self.scratch = self.root / 'scratch'; self.scratch.mkdir()
        self.qualification = self.root / 'qualification'; self.qualification.mkdir()
        self.runner = self.root / 'runner-temp'; self.runner.mkdir()
        self.target = self.runner / E.LEAF
        self.env = patch.dict(os.environ, RUNNER_TEMP=str(self.runner), PR_CI_ANDROID_NATIVE_EXPORT=str(self.target))
        self.env.start()
        self.addCleanup(self.env.stop)
        self.addCleanup(self.temp.cleanup)

    def fixture(self, product='common'):
        self.context['target'] = {'common': 'android-main', 'phone': 'android-phone', 'pico': 'android-vr-pico'}[product]
        output = dict(candidate_sha=self.context['original_merge'], candidate_tree=self.context['tree'])
        content = b'authenticated native-output fixture\n'
        if product == 'common':
            self.payload = self.scratch / 'common-native-build/libraries/a/liba.so'
            self.payload.parent.mkdir(parents=True)
            self.payload.write_bytes(content)
            output.update(scope='parent-owned-android-common-native-elf', outputs=[
                dict(path='libraries/a/liba.so', sha256=sha(content), target='a')])
        else:
            owner, app = ('android/phone', 'phoneInterface') if product == 'phone' else ('android/vr/pico', 'picoInterface')
            self.payload = self.candidate / owner / 'apps' / app / 'build/outputs/apk/release' / (app + '-release-unsigned.apk')
            self.payload.parent.mkdir(parents=True)
            self.payload.write_bytes(content)
            output.update(status=product.upper() + '_UNSIGNED_CI_APK_OUTPUT_VERIFIED', unsigned=True, apk_sha256=sha(content))
        self.output_name = {'common': 'common-native-receipt.json', 'phone': 'phone-native-apk-receipt.json',
            'pico': 'pico-unsigned-receipt.json'}[product]
        output_raw = write(self.scratch / self.output_name, output)
        self.config = self.qualification / 'consumer.json'
        config_raw = write(self.config, dict(product=product, candidate_tree=self.context['tree'], dependency_intent={'source.txt': sha(b'tracked fixture\n')}))
        raw = dict(kind='overte-android-offline-consumer-result-v1', result='success', product=product,
            candidate_sha=self.context['original_merge'], candidate_tree=self.context['tree'], actual_build_exit_code=0,
            device_tested=False, apk_qualified=product != 'common', executed_build_commands=[['actual-fixture-vector']],
            config_sha256=sha(config_raw), output_receipt_sha256=sha(output_raw), output_receipt=output,
            runtime_inventory_sha256='a' * 64, sdk_inventory_sha256='b' * 64)
        write(self.scratch / 'android-native-execution.json', raw)
        return dict(raw, toolchain_image_archive_sha256='c' * 64)

    def export(self, result):
        return E.export_success(self.target, self.candidate, self.scratch, self.config, self.context, result)

    def rewrite_output(self, result, update):
        output = deepcopy(result['output_receipt'])
        update(output)
        raw = write(self.scratch / self.output_name, output)
        result.update(output_receipt=output, output_receipt_sha256=sha(raw))
        write(self.scratch / 'android-native-execution.json', {key: value for key, value in result.items()
            if key != 'toolchain_image_archive_sha256'})

    def test_actual_common_outputs_remain_after_original_scratch_is_removed(self):
        result = self.fixture()
        exported = self.export(result)
        shutil.rmtree(self.scratch)
        manifest_raw = (self.target / 'manifest.json').read_bytes()
        manifest = json.loads(manifest_raw)
        self.assertEqual(exported['manifest_sha256'], sha(manifest_raw))
        self.assertTrue(manifest['artifact_preservation_complete'])
        self.assertFalse(manifest['recovery_data_retained'])
        self.assertEqual(manifest['status'], 'verified')
        self.assertEqual(manifest['candidate_tree'], self.context['tree'])
        self.assertEqual(manifest['run_attempt'], 2)
        self.assertEqual(len(manifest['entries']), 4)
        self.assertEqual(manifest['total_bytes'], sum(row['bytes'] for row in manifest['entries']))
        for row in manifest['entries']:
            path = self.target / row['path']
            self.assertEqual(sha(path.read_bytes()), row['sha256'])
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_actual_owning_phone_and_pico_unsigned_apk_bytes_are_exported(self):
        for product in ('phone', 'pico'):
            with self.subTest(product=product):
                if self.target.exists():
                    shutil.rmtree(self.target)
                self.export(self.fixture(product))
                self.assertEqual((self.target / ('outputs/' + product + '-release-unsigned.apk')).read_bytes(), self.payload.read_bytes())

    def test_missing_wrong_or_preexisting_destination_fails_before_export(self):
        for value in ('', str(self.root / 'other')):
            with patch.dict(os.environ, PR_CI_ANDROID_NATIVE_EXPORT=value), self.assertRaises(ValueError):
                E.destination()
        self.target.mkdir()
        with self.assertRaisesRegex(ValueError, 'already exists'):
            E.destination()

    def test_candidate_run_product_and_tree_identity_cannot_be_substituted(self):
        result = self.fixture()
        for change in ({'original_merge': '4' * 40}, {'tree': '4' * 40}, {'controller': 'bad'},
                       {'target': 'android-phone'}, {'run_id': 0}, {'run_attempt': True}):
            with self.subTest(change=change), patch.dict(self.context, change), self.assertRaises(ValueError):
                self.export(result)
        self.assertFalse(self.target.exists())

    def test_changed_payload_bytes_and_bound_receipt_config_fail_closed(self):
        result = self.fixture()
        self.payload.write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'bytes changed'):
            self.export(result)
        self.assertFalse(self.target.exists())
        self.assertTrue(list(self.runner.glob('.pr-ci-android-export-staging-*')))
        self.payload.write_bytes(b'authenticated native-output fixture\n')
        self.config.write_text('{}')
        with self.assertRaisesRegex(ValueError, 'configuration'):
            self.export(result)
        self.assertFalse(self.target.exists())

    def test_worker_receipt_cannot_be_replaced_by_equivalent_outer_claim(self):
        result = self.fixture()
        result['actual_build_exit_code'] = 1
        with self.assertRaisesRegex(ValueError, 'worker bytes'):
            self.export(result)
        result = self.fixture_reuse_result()
        (self.scratch / self.output_name).write_text('{}')
        with self.assertRaisesRegex(ValueError, 'Owning output receipt'):
            self.export(result)

    def fixture_reuse_result(self):
        return dict(json.loads((self.scratch / 'android-native-execution.json').read_bytes()), toolchain_image_archive_sha256='c' * 64)

    def test_symlink_leaf_directory_and_nonregular_payload_are_rejected(self):
        result = self.fixture()
        original = self.root / 'original.so'; self.payload.rename(original)
        self.payload.symlink_to(original)
        with self.assertRaises(OSError):
            self.export(result)
        self.payload.unlink()
        os.mkfifo(self.payload)
        with self.assertRaisesRegex(ValueError, 'regular file'):
            self.export(result)
        self.payload.unlink(); self.payload.write_bytes(original.read_bytes())
        directory = self.payload.parent
        moved = self.root / 'aliased'; directory.rename(moved); directory.symlink_to(moved, target_is_directory=True)
        with self.assertRaises(OSError):
            self.export(result)

    def test_unsafe_duplicate_and_nonlibrary_receipt_paths_are_rejected(self):
        result = self.fixture()
        for name in ('../escape.so', '/outside.so', 'a//b.so', 'a/../b.so', 'a\\b.so', 'library.txt'):
            changed = deepcopy(result)
            self.rewrite_output(changed, lambda output: output['outputs'][0].update(path=name))
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.export(changed)
        self.rewrite_output(result, lambda output: output['outputs'].append(deepcopy(output['outputs'][0])))
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            self.export(result)

    def test_export_write_failure_never_removes_execution_or_publishes_success(self):
        result = self.fixture()
        with patch.object(E, 'copy_file', side_effect=OSError('disk full')), self.assertRaises(OSError):
            self.export(result)
        self.assertTrue(self.payload.is_file())
        self.assertTrue((self.scratch / 'android-native-execution.json').is_file())
        self.assertFalse(self.target.exists())

    def test_source_mutation_during_copy_is_rejected_by_bookends(self):
        self.fixture()
        stage = self.runner / 'copy-stage'; stage.mkdir()
        original = E.os.fstat
        calls = []
        def observed(descriptor):
            calls.append(descriptor)
            if len(calls) == 2:
                self.payload.write_bytes(b'source changed after read')
            return original(descriptor)
        with patch.object(E.os, 'fstat', side_effect=observed), self.assertRaisesRegex(ValueError, 'bytes changed'):
            E.copy_file(self.payload.parent, self.payload.name, stage, 'output.so',
                        sha(self.payload.read_bytes()), [], 0)
        self.assertFalse(self.target.exists())

    def test_publication_never_replaces_an_existing_sink(self):
        stage = self.runner / 'stage'; stage.mkdir()
        write(stage / 'manifest.json', {'fixture': True})
        self.target.mkdir(); (self.target / 'sentinel').write_text('preserve')
        with self.assertRaises(OSError):
            E.commit(stage, self.target)
        self.assertEqual((self.target / 'sentinel').read_text(), 'preserve')
        self.assertTrue(stage.is_dir())

    def test_free_space_and_total_bounds_fail_without_removing_outputs(self):
        result = self.fixture()
        with patch.object(E, 'MAX_TOTAL', 1), self.assertRaisesRegex(ValueError, 'total bound'):
            self.export(result)
        with patch.object(E.os, 'statvfs') as space, self.assertRaisesRegex(ValueError, 'space'):
            space.return_value.f_bavail = 0
            space.return_value.f_frsize = 4096
            self.export(result)
        self.assertTrue(self.payload.exists())
        self.assertFalse(self.target.exists())

    def test_failure_diagnostics_are_incomplete_and_leave_recovery_data(self):
        self.fixture()
        (self.scratch / 'common-native-build/CMakeCache.txt').write_text('diagnostic fixture')
        E.export_failure(self.target, self.candidate, self.scratch, self.config, self.context, 'common', ValueError('do not expose arbitrary detail'))
        manifest = json.loads((self.target / 'manifest.json').read_bytes())
        self.assertEqual(manifest['status'], 'failed')
        self.assertFalse(manifest['artifact_preservation_complete'])
        self.assertTrue(manifest['recovery_data_retained'])
        self.assertFalse(manifest['qualification_claim'])
        self.assertNotIn('do not expose arbitrary detail', json.dumps(manifest))
        self.assertEqual(len(manifest['entries']), 2)
        self.assertTrue(self.payload.exists())

    def test_missing_export_destination_stops_before_runtime_or_build_setup(self):
        self.fixture()
        with patch.dict(os.environ, PR_CI_ANDROID_NATIVE_EXPORT=''), \
             patch.object(N.A, 'policy') as policy, patch.object(N.B, 'run') as build, \
             self.assertRaisesRegex(ValueError, 'fixed trusted artifact destination'):
            N.execute(self.candidate, self.context, {'android_native_products': ['common']},
                      self.root / 'unprepared', authenticate=lambda: None)
        policy.assert_not_called()
        build.assert_not_called()

    def test_outer_execute_exports_before_cleanup_and_retains_failure(self):
        result = self.fixture('phone')
        prepared = self.root / 'prepared'; prepared.mkdir()
        (prepared / 'qualification').mkdir()
        for name in ('runtime', 'sdk'):
            (prepared / (name + '-inventory.json')).write_text('fixture')
        template = json.loads(self.config.read_bytes())
        # Actual payload/receipts are copied into the private host session by a
        # fake boundary, exercising real exporter/cleanup with no Android build.
        sessions = []
        def boundary(*_args, **options):
            sessions.append(options['scratch'].parent)
            raw = dict(result)
            raw.pop('toolchain_image_archive_sha256')
            raw['config_sha256'] = sha((options['qualification'] / 'consumer.json').read_bytes())
            write(options['scratch'] / 'android-native-execution.json', raw)
            shutil.copyfile(self.scratch / self.output_name, options['scratch'] / self.output_name)
            return 0
        policy = {'assets': {name: {'inventory': {'sha256': value * 64}}
            for name, value in (('runtime', 'a'), ('sdk', 'b'))}}
        policy['assets']['image'] = {'archive': {'sha256': 'c' * 64}}
        with patch.object(N.A, 'policy', return_value=policy), patch.object(N, 'validate_prepared', return_value=prepared), \
             patch.object(N, 'load_template', return_value=template), patch.object(N, 'capacity_admission'), \
             patch.object(N.B, 'run', side_effect=boundary):
            value = N.execute(self.candidate, self.context, {'android_native_products': ['phone']}, prepared, authenticate=lambda: None)
            self.assertFalse(sessions[-1].exists())
            self.assertEqual(value['artifact_export']['path'], str(self.target))
            shutil.rmtree(self.target)
            with patch.object(E, 'export_success', side_effect=OSError('backup failed')), self.assertRaises(OSError):
                N.execute(self.candidate, self.context, {'android_native_products': ['phone']}, prepared, authenticate=lambda: None)
            self.assertTrue(sessions[-1].exists())
            manifest = json.loads((self.target / 'manifest.json').read_bytes())
            self.assertTrue(manifest['recovery_data_retained'])
            self.assertFalse(manifest['artifact_preservation_complete'])


if __name__ == '__main__':
    unittest.main()
