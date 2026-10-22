#!/usr/bin/env python3
"""Offline regressions for the Android prerequisite boundary; no builds."""
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("android_preflight", ROOT / "tools/repository-checks/pr_ci_android_preflight.py")
PREFLIGHT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PREFLIGHT)


class AndroidPrerequisiteTests(unittest.TestCase):
    def test_phone_start_reserve_is_disabled_but_runtime_abort_floor_remains(self):
        for target in PREFLIGHT.ANDROID_TARGETS:
            producer = PREFLIGHT.classify(["android/phone/build.sh"], target=target)["producer"]
            self.assertEqual(0 if target == 'android-phone' else 60000000000,
                             producer['minimum_free_bytes'])
            self.assertEqual(12 * 1024 ** 3, producer['runtime_abort_free_bytes'])

    def test_shared_native_changes_require_target_compile_only_on_android(self):
        for target in PREFLIGHT.TARGETS:
            result = PREFLIGHT.classify(["libraries/shared/src/Example.cpp"], target=target)
            self.assertEqual(target.startswith("android-"), result["native_qualification_required"])
            self.assertFalse(result["execution"])
            self.assertFalse(result["build_qualified"])

    def test_build_packaging_and_unknown_android_inputs_are_explicitly_missing(self):
        for path in ("CMakeLists.txt", "conanfile.py", "conan.lock", "cmake/macros/Build.cmake",
                "android/phone/build.sh", "android/phone/apps/phoneInterface/build.gradle",
                "android/phone/settings.gradle", "android/common/conan/profiles/pico4-arm64",
                "android/vr/pico/apps/picoInterface/openxr/src/Plugin.cpp",
                "android/phone/apps/phoneInterface/proguard-rules.pro", "android/new-production.unknown",
                "android/phone/apps/phoneInterface/src/main/java/Activity.kt"):
            for target in PREFLIGHT.ANDROID_TARGETS:
                result = PREFLIGHT.classify([path], target=target)
                self.assertEqual([path], result["paths"])
                self.assertEqual("missing-android-native-prerequisites", result["status"])
                self.assertEqual(3, len(result["missing"]))
                self.assertEqual("android/phone/fdroid/scripts/cold-build.sh", result["producer"]["entrypoint"])

    def test_docs_test_fixtures_npm_and_java_resource_owners_stay_usable(self):
        paths = ["README.md", "android/README.md", "tests/shared/src/AABoxTests.cpp",
            "tests/device/self_tests/test_graph.py", "android/phone/tests/fixture.cpp",
            "android/common/web/tests/java/Regression.java", "browser-client/src/client.ts",
            "browser-client/package-lock.json", "script-archive/marketplace/S3Server/package-lock.json",
            "android/phone/apps/phoneInterface/src/main/java/org/overte/Activity.java",
            "android/phone/apps/phoneInterface/src/main/res/xml/policy.xml",
            "android/phone/apps/phoneInterface/src/main/AndroidManifest.xml",
            "android/common/web/java/org/overte/Host.java", "android/common/snapshot/res/xml/paths.xml",
            "security/redaction/java/org/overte/security/SafeDiagnostics.java"]
        for target in PREFLIGHT.ANDROID_TARGETS:
            result = PREFLIGHT.classify(paths, target=target)
            self.assertEqual("not-required", result["status"])
            self.assertEqual([], result["missing"])
            self.assertIsNone(result["producer"])

    def test_mixed_changes_cannot_hide_native_input_and_results_are_deterministic(self):
        paths = ["browser-client/package-lock.json", "tests/shared/src/Test.cpp", "interface/src/Application.cpp"]
        first = PREFLIGHT.classify(paths, target="android-phone")
        self.assertEqual(["interface/src/Application.cpp"], first["paths"])
        self.assertEqual(first, PREFLIGHT.classify(list(reversed(paths)) + paths, target="android-phone"))

    def test_actual_registered_platform_test_entrypoints_are_not_application_builds(self):
        policy = json.loads((ROOT / ".github/pr-ci-platforms.json").read_text())
        for target, profile in policy["android"].items():
            paths = [suite["entrypoint"] for suite in profile["suites"]]
            self.assertEqual("not-required", PREFLIGHT.classify(paths, target=target)["status"])
        for path in ("android/common/conan/test_unregistered.py",
                "android/phone/apps/phoneInterface/src/main/cpp/tests/Production.cpp"):
            self.assertTrue(PREFLIGHT.classify([path], target="android-phone")["native_qualification_required"])

    def test_invalid_paths_or_unrecognized_target_cannot_authorize_a_waiver(self):
        for path in ("../android/source.cpp", "/android/source.cpp", "android/./source.cpp",
                     "android//source.cpp", "android\\source.cpp", "android/source.cpp\n", None):
            with self.assertRaises(ValueError): PREFLIGHT.classify([path], target="android-phone")
        with self.assertRaises(ValueError): PREFLIGHT.classify([], target="feature/native")


if __name__ == "__main__":
    unittest.main()
