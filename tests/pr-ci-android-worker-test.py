#!/usr/bin/env python3
"""Bounded real Git/payload admission and fixed offline Android command tests."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("worker", ROOT / "tools/repository-checks/pr_ci_android_worker.py")
W = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(W)
RSPEC = importlib.util.spec_from_file_location("runtime", ROOT / "tools/repository-checks/pr_ci_android_runtime.py")
R = importlib.util.module_from_spec(RSPEC)
RSPEC.loader.exec_module(R)


class ConsumerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="android-worker-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.roots = W.Roots(source=self.base / "source", attempt=self.base / "payload",
            prepared=self.base / "payload", sdk=self.base / "sdk", controller=self.base / "controller",
            proof=self.base / "proof", scratch=self.base / "scratch")
        for path in vars(self.roots).values():
            path.mkdir(exist_ok=True)
        self.config_path = self.roots.proof / "consumer.json"
        self.product = "common"
        self.files = W.COMMON_INTENT | W.PICO_INTENT | W.PHONE_INTENT
        for relative in self.files:
            path = self.roots.source / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("frozen fixture declaration\n")
        for args in (("init", "-q"), ("add", "."), ("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "Fixture")):
            subprocess.run(["git", "-C", str(self.roots.source), *args], check=True, capture_output=True)
        self.head = W.git(self.roots, "rev-parse", "HEAD").decode().strip()
        self.tree = W.git(self.roots, "rev-parse", "HEAD^{tree}").decode().strip()
        code = set().union(*W.REQUIRED_CODE.values())
        for relative in code:
            path = self.roots.controller / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# protected fixture; not an actual build verifier\n")
        for relative in ("tools/repository-checks/pr_ci_android_worker.py", "tools/repository-checks/pr_ci_android_runtime.py"):
            path = self.roots.controller / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / relative, path)
        self.tools = {}
        for name in W.TOOLS:
            path = self.roots.attempt / "tools" / name
            path.parent.mkdir(exist_ok=True)
            path.write_text("sealed executable fixture, not executed\n")
            path.chmod(0o755)
            self.tools[name] = str(path)
        (self.roots.attempt / "gradle-home").mkdir()
        path = self.roots.sdk / "cmdline-tools/22.0/bin/apkanalyzer"
        path.parent.mkdir(parents=True)
        path.write_text("sealed analyzer fixture\n")
        self.config = dict(kind=W.KIND, product=self.product, candidate_tree=self.tree,
            dependency_intent={p: W.sha(self.roots.source / p) for p in self.files},
            runtime_inventory=self.seal("runtime.json", self.roots.prepared),
            sdk_inventory=self.seal("sdk.json", self.roots.sdk),
            controller_files={p.relative_to(self.roots.controller).as_posix(): W.sha(p)
                              for p in self.roots.controller.rglob("*") if p.is_file()},
            tools=self.tools, gradle_seed=None, product_map=None, apkanalyzer=None)

    def seal(self, name, root):
        path = self.roots.proof / name
        path.write_bytes(R.canonical(R.inventory(root)))
        return dict(path=str(path), sha256=W.sha(path))

    def prepare(self):
        self.config_path.write_bytes(R.canonical(self.config))
        return W.prepare(self.product, self.head, self.config_path, W.sha(self.config_path), roots=self.roots)

    def product_config(self, product):
        self.product = product
        self.config["product"] = product
        self.config["gradle_seed"] = str(self.roots.attempt / "gradle-home")
        self.config["apkanalyzer"] = str(self.roots.sdk / "cmdline-tools/22.0/bin/apkanalyzer")
        if product == "pico":
            path = self.roots.proof / "product-inputs-pico.json"
            path.write_text('{"fixture":true}\n')
            self.config["product_map"] = dict(path=str(path), sha256=W.sha(path))

    def test_real_git_and_full_inventory_admission_creates_no_state(self):
        roots, config, _ = self.prepare()
        self.assertEqual(config["candidate_tree"], self.tree)
        self.assertFalse(any(roots.scratch.iterdir()))

    def test_configuration_external_pin_and_duplicate_json_refuse(self):
        self.config_path.write_text('{"kind":1,"kind":2}')
        with self.assertRaisesRegex(ValueError, "duplicate"):
            W.prepare(self.product, self.head, self.config_path, W.sha(self.config_path), roots=self.roots)
        with self.assertRaisesRegex(ValueError, "configuration changed"):
            W.prepare(self.product, self.head, self.config_path, "0" * 64, roots=self.roots)

    def test_wrong_owner_tree_and_unknown_config_fields_refuse(self):
        for field, value in (("product", "pico"), ("candidate_tree", "a" * 40), ("arbitrary_command", ["true"])):
            old = copy.deepcopy(self.config)
            self.config[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.prepare()
            self.config = old

    def test_changed_tracked_dependency_requires_new_runtime(self):
        path = self.roots.source / "conanfile.py"
        path.write_text("candidate changed dependency\n")
        with self.assertRaisesRegex(ValueError, "tracked candidate source changed"):
            self.prepare()

    def test_untracked_ignored_old_build_inputs_are_not_accepted(self):
        (self.roots.source / "old-output").write_text("stale input")
        with self.assertRaisesRegex(ValueError, "untracked build inputs"):
            self.prepare()

    def test_gradle_seed_copies_only_its_own_prepared_bytes(self):
        seed = self.roots.attempt / "gradle-home"
        (seed / "file").write_text("prepared bytes")
        (seed / "internal").symlink_to("file")
        out = self.roots.scratch / "copied-seed"
        W.copy_gradle_seed(seed, out)
        self.assertEqual((out / "internal").read_text(), "prepared bytes")
        self.assertFalse((out / "internal").is_symlink())
        (seed / "directory-cycle").symlink_to(".")
        with self.assertRaisesRegex(ValueError, "directory or special symlink"):
            W.copy_gradle_seed(seed, self.roots.scratch / "cycle")
        self.assertFalse((self.roots.scratch / "cycle").exists())
        (seed / "directory-cycle").unlink()
        (seed / "escape").symlink_to("../tools/moc")
        with self.assertRaisesRegex(ValueError, "escapes its own seed"):
            W.copy_gradle_seed(seed, self.roots.scratch / "other")

    def test_new_committed_declaration_still_cannot_reuse_old_runtime(self):
        path = self.roots.source / "conanfile.py"
        path.write_text("new actual committed declaration\n")
        subprocess.run(["git", "-C", str(self.roots.source), "add", "."], check=True)
        subprocess.run(["git", "-C", str(self.roots.source), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "Change"], check=True)
        self.head = W.git(self.roots, "rev-parse", "HEAD").decode().strip()
        self.config["candidate_tree"] = W.git(self.roots, "rev-parse", "HEAD^{tree}").decode().strip()
        with self.assertRaisesRegex(ValueError, "prepare a new runtime"):
            self.prepare()

    def test_missing_required_dependency_or_controller_member_refuse(self):
        del self.config["dependency_intent"]["conanfile.py"]
        with self.assertRaisesRegex(ValueError, "incomplete frozen"):
            self.prepare()
        self.config["dependency_intent"]["conanfile.py"] = W.sha(self.roots.source / "conanfile.py")
        del self.config["controller_files"]["android/common/native-ci/verify.py"]
        with self.assertRaisesRegex(ValueError, "incomplete"):
            self.prepare()

    def test_changed_added_or_linked_controller_bytes_refuse(self):
        path = self.roots.controller / "android/common/native-ci/verify.py"
        original = path.read_bytes()
        path.write_text("unreviewed verifier\n")
        with self.assertRaisesRegex(ValueError, "controller bytes"):
            self.prepare()
        path.write_bytes(original)
        extra = self.roots.controller / "extra.py"
        extra.write_text("unlisted")
        with self.assertRaisesRegex(ValueError, "membership"):
            self.prepare()
        extra.unlink(); extra.symlink_to(path)
        with self.assertRaisesRegex(ValueError, "linked controller"):
            self.prepare()

    def test_changed_payload_sdk_or_ledger_bytes_refuse(self):
        for path in (Path(self.tools["moc"]), self.roots.sdk / "cmdline-tools/22.0/bin/apkanalyzer"):
            old = path.read_bytes(); path.write_text("tampered")
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, "payload differs"):
                self.prepare()
            path.write_bytes(old)
        Path(self.config["runtime_inventory"]["path"]).write_text("changed inventory")
        with self.assertRaisesRegex(ValueError, "reference changed"):
            self.prepare()

    def test_unshadowed_payload_and_fresh_scratch_required(self):
        other = self.base / "other-copy"; shutil.copytree(self.roots.attempt, other)
        self.roots.attempt = other
        with self.assertRaisesRegex(ValueError, "unshadowed"):
            self.prepare()
        self.roots.attempt = self.roots.prepared
        (self.roots.scratch / "old-output").write_text("stale")
        with self.assertRaisesRegex(ValueError, "fresh and empty"):
            self.prepare()

    def test_tool_in_writable_source_or_foreign_location_refuse(self):
        for value in (str(self.roots.source / "conanfile.py"), "/usr/bin/true"):
            self.config["tools"]["moc"] = value
            with self.assertRaisesRegex(ValueError, "sealed payload"):
                self.prepare()

    def test_pico_exact_map_seed_and_sdk_analyzer_are_required(self):
        self.product_config("pico")
        self.prepare()
        saved = self.config["controller_files"].pop("android/common/native-ci/apk_native.py")
        with self.assertRaisesRegex(ValueError, "incomplete"):
            self.prepare()
        self.config["controller_files"]["android/common/native-ci/apk_native.py"] = saved
        self.config["gradle_seed"] = "/tmp/ambient-gradle"
        with self.assertRaisesRegex(ValueError, "Gradle seed"):
            self.prepare()
        self.config["gradle_seed"] = str(self.roots.attempt / "gradle-home")
        self.config["apkanalyzer"] = "/attempt/android-tools/bin/apkanalyzer"
        with self.assertRaisesRegex(ValueError, "analyzer"):
            self.prepare()

    def test_phone_requires_full_protected_native_gate_and_matches_build_version(self):
        self.product_config("phone")
        self.prepare()
        commands = W.vectors("phone", self.head, self.config, self.roots)
        self.assertIn("-PRELEASE_NUMBER=0.1.0-ci", commands["candidate"][0])
        self.assertIn(str(self.roots.controller / "android/phone/native-ci/verify_apk.py"), commands["verify"])
        self.assertIn("--apksigner", commands["verify"])
        self.assertEqual(commands["verify"][commands["verify"].index("--version-name") + 1], "0.1.0-ci")
        del self.config["controller_files"]["android/common/native-ci/apk_native.py"]
        with self.assertRaisesRegex(ValueError, "incomplete"):
            self.prepare()

    def test_fixed_common_commands_build_production_and_protected_verifier(self):
        commands = W.vectors("common", self.head, self.config, self.roots)
        self.assertEqual(len(commands["candidate"]), 2)
        self.assertIn("-DOVERTE_ANDROID_COMMON_NATIVE=ON", commands["candidate"][0])
        self.assertIn("overte-android-common-native", commands["candidate"][1])
        self.assertIn(str(self.roots.controller / "android/common/native-ci/verify.py"), commands["verify"])
        self.assertFalse(any("conan" == item for command in commands["candidate"] for item in command))

    def test_fixed_pico_gradle_has_offline_unsigned_and_no_fdroid_environment(self):
        self.product_config("pico"); self.config["expected_head"] = self.head
        command = W.vectors("pico", self.head, self.config, self.roots)["candidate"][0]
        for item in ("--offline", "--no-daemon", "--max-workers=2", "-PPICO_UNSIGNED=1", ":picoInterface:assembleRelease"):
            self.assertIn(item, command)
        env = W.environment("pico", self.config, self.roots)
        self.assertNotIn("OVERTE_FDROID_CONAN_DIR", env)
        self.assertNotIn("CONTAINER_HOST", env)
        self.assertNotIn("conan/bin", env["PATH"])
        self.assertEqual(env["GIT_CONFIG_GLOBAL"], "/dev/null")
        self.assertEqual(env["GIT_CONFIG_NOSYSTEM"], "1")

    def test_failed_candidate_never_invokes_verifier_or_writes_success(self):
        self.config_path.write_bytes(R.canonical(self.config))
        calls = []
        def invoke(command, roots, env):
            calls.append(command)
            if command[0] == "cmake":
                raise ValueError("actual build failed")
        with mock.patch.object(W.os, "getpid", return_value=1), mock.patch.object(W.os, "getuid", return_value=1000), \
             mock.patch.object(W, "prepare", return_value=(self.roots, self.config, R)), \
             mock.patch.object(W, "invoke", side_effect=invoke):
            with self.assertRaisesRegex(ValueError, "build failed"):
                W.execute("common", self.head, self.config_path, "a" * 64)
        self.assertEqual(len(calls), 2)
        self.assertFalse((self.roots.scratch / "android-native-execution.json").exists())

    def test_successful_build_without_protected_receipt_is_not_acceptance(self):
        with mock.patch.object(W.os, "getpid", return_value=1), mock.patch.object(W.os, "getuid", return_value=1000), \
             mock.patch.object(W, "prepare", return_value=(self.roots, self.config, R)), \
             mock.patch.object(W, "invoke"):
            with self.assertRaisesRegex(ValueError, "consumer JSON"):
                W.execute("common", self.head, self.config_path, "a" * 64)
        self.assertFalse((self.roots.scratch / "android-native-execution.json").exists())

    def test_candidate_precreated_verifier_home_stops_trusted_phase(self):
        calls = []
        def invoke(command, roots, env):
            calls.append(command)
            if command[0] == "cmake" and "--build" in command:
                (roots.scratch / "verifier-home").mkdir()
        with mock.patch.object(W.os, "getpid", return_value=1), mock.patch.object(W.os, "getuid", return_value=1000), \
             mock.patch.object(W, "prepare", return_value=(self.roots, self.config, R)), \
             mock.patch.object(W, "invoke", side_effect=invoke):
            with self.assertRaisesRegex(ValueError, "substituted verifier home"):
                W.execute("common", self.head, self.config_path, "a" * 64)
        self.assertEqual(len(calls), 3)

    def test_worker_refuses_host_process_namespace_before_inspecting_inputs(self):
        with mock.patch.object(W.os, "getpid", return_value=1234):
            with self.assertRaisesRegex(ValueError, "PID 1"):
                W.execute("common", self.head, self.config_path, "0" * 64)
        with mock.patch.object(W.os, "getpid", return_value=1234), mock.patch.object(W.os, "kill") as kill:
            with self.assertRaisesRegex(ValueError, "PID 1"):
                W.stop_candidate_processes()
            kill.assert_not_called()


if __name__ == "__main__":
    unittest.main()
