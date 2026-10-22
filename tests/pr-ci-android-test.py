#!/usr/bin/env python3
"""Offline negative contracts for trusted Android API acquisition/compilation."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools/repository-checks'))
import pr_ci_android as A
import pr_ci_platform as P
import pr_ci_context as C


class ApiRuntimeTests(unittest.TestCase):
    def archive(self, members):
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode='w:gz') as archive:
            for name, kind in members:
                entry = tarfile.TarInfo(name)
                entry.type = kind
                if kind == tarfile.REGTYPE:
                    entry.size = 3
                    archive.addfile(entry, io.BytesIO(b'jar'))
                else:
                    entry.linkname = '/etc/passwd'
                    archive.addfile(entry)
        return stream.getvalue()

    def test_only_verified_single_regular_qt_api_is_returned(self):
        payload = self.archive([('p/Qt/jar/QtAndroid.jar', tarfile.REGTYPE),
                                ('../../ignored', tarfile.SYMTYPE)])
        with patch.object(A.urllib.request, 'urlopen', return_value=io.BytesIO(payload)), \
                patch.object(A, 'QT_ARCHIVE_SHA', hashlib.sha256(payload).hexdigest()):
            self.assertEqual(A.qt_jar(), b'jar')

    def test_changed_archive_missing_duplicate_or_linked_api_is_rejected(self):
        cases = [([], '0' * 64),
                 ([('p/Qt/jar/QtAndroid.jar', tarfile.REGTYPE)], '0' * 64),
                 ([('p/Qt/jar/QtAndroid.jar', tarfile.SYMTYPE)], None),
                 ([('p/a/jar/QtAndroid.jar', tarfile.REGTYPE),
                   ('p/b/jar/QtAndroid.jar', tarfile.REGTYPE)], None)]
        for members, digest in cases:
            payload = self.archive(members)
            with self.subTest(members=members), \
                    patch.object(A.urllib.request, 'urlopen', return_value=io.BytesIO(payload)), \
                    patch.object(A, 'QT_ARCHIVE_SHA', digest or hashlib.sha256(payload).hexdigest()):
                with self.assertRaises(ValueError):
                    A.qt_jar()

    def runtime(self, root):
        for name in ('android.jar', 'aapt2', 'QtAndroid.jar', 'webkit.jar', 'core.jar', 'guava.jar'):
            (root / name).write_bytes(name.encode())
        manifest = {name.name: A.sha(name) for name in root.iterdir() if name.name != 'runtime.json'}
        (root / 'runtime.json').write_text(json.dumps(manifest))

    def test_runtime_rejects_mutation_and_manifest_rewrite_of_locked_jars(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch); self.runtime(root)
            with patch.object(A, 'FIXED_JARS', {}):
                self.assertEqual(A.verify_runtime(root), root)
                (root / 'core.jar').write_bytes(b'changed')
                with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
                    A.verify_runtime(root)
            self.runtime(root)
            with self.assertRaisesRegex(ValueError, 'unreviewed'):
                A.verify_runtime(root)

    def test_unowned_product_or_missing_runtime_cannot_be_skipped(self):
        for target, products, runtime in (
                ('android-phone', ['pico'], ROOT), ('android-main', ['phone'], ROOT),
                ('android-phone', ['phone'], None), ('main', ['phone'], ROOT)):
            with self.subTest(target=target), self.assertRaises(C.ContextError):
                P.android_compile_commands(target, {'android_compile_products': products}, runtime, [ROOT])

    def test_irrelevant_inputs_need_no_runtime_or_compile_process(self):
        self.assertEqual(P.android_compile_commands('android-phone', {'android_compile_products': []}, None, []), [])

    def test_real_compiler_is_controller_owned_and_uses_no_test_stubs(self):
        command = P.android_compile_commands('android-phone', {'android_compile_products': ['phone']}, ROOT, [ROOT])[0]
        self.assertEqual(command[1:5], ['-I', '-S', '-B', '-c'])
        self.assertIn("run(['javac'", command[5])
        self.assertIn("'aapt2'", command[5])
        self.assertNotIn('java-stubs', command[5])
        self.assertNotIn('robolectric/src/main', command[5])
        self.assertEqual(command[-4:], ['--runtime', str(ROOT), '--product', 'phone'])

    def test_incomplete_production_source_is_a_failure_before_compilation(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            with patch.object(A, 'verify_runtime', return_value=root), patch.object(A.subprocess, 'run') as run:
                with self.assertRaisesRegex(ValueError, 'production Android Java is missing'):
                    A.compile_product(root, root, 'phone')
                run.assert_not_called()

    def test_qt_reference_is_read_as_data_and_unknown_api_provider_is_rejected(self):
        with tempfile.TemporaryDirectory() as scratch:
            recipe = Path(scratch) / 'android/common/conan/conanfile-pico.py'
            recipe.parent.mkdir(parents=True)
            recipe.write_text('raise RuntimeError("must never execute candidate recipes")\n'
                              'class Product:\n    qt_ref = ' + repr(A.QT_API_REFERENCE) + '\n')
            A.verify_qt_api_reference(scratch)
            for value in ('qt/5.15.19@overte/stable', 'qt/5.15.18-2026.01.04@overte/stable#unreviewed'):
                recipe.write_text('qt_ref = ' + repr(value))
                with self.assertRaisesRegex(ValueError, 'provider changed'):
                    A.verify_qt_api_reference(scratch)

    def test_corrupt_optional_cache_is_refreshed_without_authorizing_its_bytes(self):
        for kind in ('changed-file', 'symlink', 'directory'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as scratch:
                root = Path(scratch); sdk = root / 'sdk'; destination = root / 'runtime'; destination.mkdir()
                for name in ('webkit.jar', 'core.jar', 'guava.jar'):
                    (destination / name).write_bytes(b'fixture-api')
                for name, payload in [('platforms/android-36/android.jar', b'sdk'),
                        ('build-tools/36.0.0/aapt2', b'aapt2'),
                        ('build-tools/36.0.0/source.properties', b'Pkg.Revision=36.0.0\n')]:
                    path = sdk / name; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(payload)
                cache = root / 'QtAndroid.jar'; sentinel = root / 'sentinel'; sentinel.write_bytes(b'not-an-api')
                if kind == 'symlink': cache.symlink_to(sentinel)
                elif kind == 'directory': cache.mkdir()
                else: cache.write_bytes(b'corrupt-cache')
                verified = b'reviewed-qt-api'; locked = {'QtAndroid.jar': hashlib.sha256(verified).hexdigest()}
                with patch.object(A, 'qt_jar', return_value=verified) as fetch, \
                        patch.object(A, 'MAVEN', ()), patch.object(A, 'FIXED_JARS', locked):
                    A.prepare(destination, sdk, cache)
                    A.verify_runtime(destination)
                    fetch.assert_called_once()
                self.assertEqual((destination / 'QtAndroid.jar').read_bytes(), verified)
                self.assertEqual(sentinel.read_bytes(), b'not-an-api')
                if kind != 'directory':
                    self.assertFalse(cache.is_symlink())
                    self.assertEqual(cache.read_bytes(), verified)

    def test_kotlin_production_source_cannot_silently_pass_java_compilation(self):
        for product, relative in [('phone', 'android/phone/apps/phoneInterface/src/main/kotlin/New.kt'),
                                   ('common', 'android/common/web/java/New.kt')]:
            with self.subTest(product=product), tempfile.TemporaryDirectory() as scratch:
                root = Path(scratch)
                (root / 'android/phone/apps/phoneInterface/src/main/java').mkdir(parents=True)
                kotlin = root / relative; kotlin.parent.mkdir(parents=True, exist_ok=True)
                kotlin.write_text('fun kotlinSource() = 1\n')
                with patch.object(A, 'verify_runtime', return_value=root):
                    with self.assertRaisesRegex(ValueError, 'Kotlin compiler owner'):
                        A.compile_product(root, root, product)

    def test_new_documents_resources_are_included_without_requiring_a_missing_module(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch); main = root / 'product'
            before = [main / 'res', *[root / path for path in A.RESOURCES]]
            self.assertEqual(A.resource_roots(root, main), before)
            documents = root / 'android/common/documents/res'
            documents.parent.mkdir(parents=True)
            documents.write_text('not a resource directory')
            with self.assertRaisesRegex(ValueError, 'not a directory'):
                A.resource_roots(root, main)
            documents.unlink(); documents.mkdir()
            self.assertEqual(A.resource_roots(root, main), [*before, documents])
            self.assertEqual(A.resource_roots(root, None), [*before[1:], documents])

    def test_phone_java_selects_only_proven_related_suites(self):
        profile = P.policy()['android']['android-phone']
        inputs = json.loads((ROOT / '.github/pr-ci-platform-inputs.json').read_text())['android'][0]
        plan = {'regular': True, 'paths': ['android/phone/apps/phoneInterface/src/main/java/org/overte/phone/PhoneInterfaceActivity.java']}
        def inventory(arguments, **_kwargs):
            return (inputs['inventory'][arguments[-1].removeprefix('HEAD:')] + '\n').encode()
        with patch.object(P.subprocess, 'check_output', side_effect=inventory):
            selected = P.android_suites(ROOT, 'android-phone', profile, plan)
        names = {suite['name'] for suite in selected}
        self.assertEqual(len(names), 6)
        self.assertNotIn('pico4-device-free', names)
        self.assertIn('phone-e2e-runtime-regressions', names)
        self.assertIn('phone-embedded-web', names)

    def test_unknown_mixed_or_evolved_inputs_keep_the_complete_android_profile(self):
        profile = P.policy()['android']['android-phone']
        known = 'android/phone/apps/phoneInterface/src/main/java/org/overte/phone/PhoneInterfaceActivity.java'
        cases = [None, {'regular': True, 'paths': []}, {'regular': False, 'paths': [known]},
                 {'regular': True, 'paths': [known, 'android/phone/build.sh']},
                 {'regular': True, 'paths': [known, 'android/vr/pico/tests/new-test.py']},
                 {'regular': True, 'paths': ['android/phone/apps/phoneInterface/src/main/new-input.kt']}]
        for plan in cases:
            with self.subTest(plan=plan), patch.object(P.subprocess, 'check_output') as git:
                self.assertEqual(P.android_suites(ROOT, 'android-phone', profile, plan), profile['suites'])
                git.assert_not_called()
        with patch.object(P.subprocess, 'check_output', return_value=('0' * 40).encode()):
            self.assertEqual(P.android_suites(ROOT, 'android-phone', profile,
                {'regular': True, 'paths': [known]}), profile['suites'])


if __name__ == '__main__':
    unittest.main()
