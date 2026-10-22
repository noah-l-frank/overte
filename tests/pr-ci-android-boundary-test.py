#!/usr/bin/env python3
"""Check the Android execution boundary without launching a build or daemon."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools/repository-checks"))
import pr_ci_android_boundary as B


class AndroidBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.candidate = self.root / "candidate"
        self.candidate.mkdir()
        subprocess.run(["git", "init", "--initial-branch=test/main/android-consumer", str(self.candidate)],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.runtime, self.sdk = self.root / "runtime", self.root / "sdk"
        self.scratch, self.controller = self.root / "scratch", self.root / "controller"
        self.qualification = self.root / "qualification"
        for path in (self.runtime, self.sdk, self.scratch, self.controller, self.qualification):
            path.mkdir()
        for name in ("conan", "target-continuation", "qt-composed"):
            (self.runtime / name).mkdir()
        for name in ("build-tools/36.0.0/aapt2", "platforms/android-36/android.jar",
                     "ndk/27.3.13750724/toolchains/llvm/prebuilt/linux-x86_64/bin/clang"):
            path = self.sdk / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"boundary fixture only; not SDK qualification")
        self.options = dict(runtime=self.runtime, sdk=self.sdk, scratch=self.scratch,
                            controller=self.controller, qualification=self.qualification, product="phone")
        self.name = "overte-android-ci-" + "a" * 32
        self.image = {"Id": B.IMAGE, "Os": "linux", "Architecture": "amd64",
                      "Config": {}, "RootFS": {"Type": "layers", "Layers": list(B.LAYERS)}}
        self.image_response = json.dumps([self.image]).encode()
        self.config_patch = patch.object(B, "CONFIG_SHA256",
            "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a")
        self.config_patch.start()

    def tearDown(self):
        self.config_patch.stop()
        self.temporary.cleanup()

    def argv(self, **options):
        return B.docker_command(self.candidate, ["python3", "/ci-controller/consumer.py"],
                                name=self.name, **(self.options | options))

    def test_offline_nonroot_bounded_execution_with_fixed_image(self):
        args = self.argv()
        for value in ("--pull=never", "--read-only", "--cap-drop=ALL", "--network=none",
                      "--security-opt=no-new-privileges:true", "--memory=8g", "--memory-swap=8g",
                      "--cpus=2", "--pids-limit=512", B.IMAGE):
            self.assertIn(value, args)
        self.assertIn("--user=" + str(os.getuid()) + ":" + str(os.getgid()), args)
        self.assertNotIn("--privileged", args)
        self.assertFalse(any("unconfined" in value for value in args))

    def test_only_explicit_mounts_no_host_system_or_socket(self):
        args = self.argv()
        mounts = [args[index + 1] for index, value in enumerate(args) if value == "--mount"]
        self.assertEqual(len(mounts), 8)
        self.assertTrue(any("target=/attempt," in value and ",readonly," in value for value in mounts))
        self.assertTrue(any("target=/attempt/source/.git," in value and ",readonly," in value for value in mounts))
        self.assertTrue(any("target=/opt/android-sdk," in value and ",readonly," in value for value in mounts))
        self.assertFalse(any("docker.sock" in value or "source=/usr," in value for value in mounts))

    def test_ambient_secrets_and_docker_overrides_are_ignored(self):
        with patch.dict(os.environ, {"GH_TOKEN": "private-token-fixture", "DOCKER_HOST": "tcp://evil",
                                     "DOCKER_CONTEXT": "hostile", "JAVA_HOME": "/private/java",
                                     "OVERTE_ANDROID_KEYSTORE_PASSWORD": "secret-signing-fixture"}):
            args = self.argv()
        raw = " ".join(args)
        for secret in ("private-token-fixture", "tcp://evil", "hostile", "/private/java", "secret-signing-fixture"):
            self.assertNotIn(secret, raw)
        self.assertIn("-i", args)
        self.assertIn("--host=unix:///var/run/docker.sock", args)
        self.assertIn("GRADLE_USER_HOME=/scratch/gradle-home", args)

    def test_whole_host_root_refused(self):
        for name in ("runtime", "sdk", "scratch", "controller", "qualification"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.argv(**{name: Path("/home")})

    def test_overlap_and_runtime_alias_refused(self):
        with self.assertRaisesRegex(ValueError, "overlap"):
            self.argv(scratch=self.runtime)
        alias = self.root / "runtime-alias"
        alias.symlink_to(self.runtime, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.argv(runtime=alias)

    def test_linked_worktree_or_external_git_objects_refused(self):
        (self.candidate / ".git/objects/info/alternates").write_text("/private/objects\n")
        with self.assertRaisesRegex(ValueError, "external object"):
            self.argv()

    def test_candidate_git_credentials_refused(self):
        with (self.candidate / ".git/config").open("a") as stream:
            stream.write('\n[http "https://github.com"]\nextraheader = bearer fixture\n')
        with self.assertRaisesRegex(ValueError, "credentials"):
            self.argv()

    def test_missing_runtime_and_sdk_fail_before_build(self):
        (self.runtime / "target-continuation").rmdir()
        with self.assertRaisesRegex(ValueError, "incomplete"):
            self.argv()
        (self.runtime / "target-continuation").mkdir()
        (self.sdk / "platforms/android-36/android.jar").unlink()
        with self.assertRaisesRegex(ValueError, "incomplete"):
            self.argv()

    def test_product_host_mapping_is_explicit_and_pico_has_no_phone_environment(self):
        for product in ("phone", "common"):
            with self.subTest(product=product):
                self.assertIn("OVERTE_FDROID_CONAN_DIR=/attempt/target-continuation",
                              self.argv(product=product))
        self.assertFalse(any(value.startswith("OVERTE_FDROID_CONAN_DIR=") for value in self.argv(product="pico")))
        with self.assertRaisesRegex(ValueError, "product"):
            self.argv(product="other")

    def test_mount_delimiters_and_unsafe_name_refused(self):
        unsafe = self.root / "runtime,readonly=false"
        unsafe.mkdir()
        with self.assertRaises(ValueError):
            self.argv(runtime=unsafe)
        with self.assertRaisesRegex(ValueError, "name"):
            B.docker_command(self.candidate, ["true"], name="other-running-container", **self.options)

    def test_root_identity_refused(self):
        with patch.object(B.os, "getuid", return_value=0), self.assertRaisesRegex(ValueError, "nonroot"):
            self.argv()

    def test_wrong_prepared_image_never_launches_candidate(self):
        with patch.object(B.subprocess, "check_output", return_value=b"sha256:wrong\n"), \
                patch.object(B.subprocess, "run") as run, self.assertRaisesRegex(ValueError, "image"):
            B.run(self.candidate, ["true"], **self.options)
        run.assert_not_called()

    def test_containerd_manifest_identity_requires_identical_runtime_bytes(self):
        self.image["Id"] = B.MANIFEST_IMAGE
        response = json.dumps([self.image]).encode()
        with patch.object(B.subprocess, "check_output", side_effect=[
                subprocess.CalledProcessError(1, ["docker", "inspect"]), response]) as inspect, \
                patch.object(B.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as run:
            self.assertEqual(B.run(self.candidate, ["true"], **self.options), 0)
        self.assertEqual(inspect.call_count, 2)
        self.assertEqual(run.call_count, 1)
        self.assertIn(B.MANIFEST_IMAGE, run.call_args.args[0])

    def test_changed_image_layers_config_architecture_or_id_rejected(self):
        for field, value in (("RootFS", {"Type": "layers", "Layers": list(reversed(B.LAYERS))}),
                             ("Config", {"User": "unreviewed"}), ("Architecture", "arm64"),
                             ("Id", "sha256:" + "0" * 64)):
            with self.subTest(field=field):
                metadata = self.image | {field: value}
                with patch.object(B.subprocess, "check_output", return_value=json.dumps([metadata]).encode()), \
                        patch.object(B.subprocess, "run") as run, self.assertRaisesRegex(ValueError, "identity"):
                    B.run(self.candidate, ["true"], **self.options)
                run.assert_not_called()

    def test_unavailable_image_does_not_pull_or_launch_candidate(self):
        with patch.object(B.subprocess, "check_output", side_effect=subprocess.CalledProcessError(1, ["inspect"])), \
                patch.object(B.subprocess, "run") as run, self.assertRaisesRegex(ValueError, "unavailable"):
            B.run(self.candidate, ["true"], **self.options)
        run.assert_not_called()

    def test_success_returns_actual_exit_code_without_retry(self):
        with patch.object(B.subprocess, "check_output", return_value=self.image_response), \
                patch.object(B.subprocess, "run", return_value=subprocess.CompletedProcess([], 17)) as run:
            result = B.run(self.candidate, ["true"], **self.options)
        self.assertEqual(result, 17)
        self.assertEqual(run.call_count, 1)
        self.assertNotIn("GH_TOKEN", run.call_args.kwargs["env"])
        self.assertEqual(run.call_args.kwargs["env"]["HOME"], run.call_args.kwargs["env"]["DOCKER_CONFIG"])
        self.assertNotEqual(run.call_args.kwargs["env"]["HOME"], str(Path.home()))
        self.assertFalse(Path(run.call_args.kwargs["env"]["DOCKER_CONFIG"]).exists())

    def test_timeout_removes_only_owned_container_and_does_not_retry(self):
        with patch.object(B.subprocess, "check_output", return_value=self.image_response), \
                patch.object(B.subprocess, "run", side_effect=[subprocess.TimeoutExpired([], 1),
                      subprocess.CompletedProcess([], 0)]) as run:
            result = B.run(self.candidate, ["true"], timeout=1, **self.options)
        self.assertEqual(result, 124)
        self.assertEqual(run.call_count, 2)
        launched = run.call_args_list[0].args[0]
        name = next(value.split("=", 1)[1] for value in launched if value.startswith("--name="))
        self.assertEqual(run.call_args_list[1].args[0][-3:], ["rm", "--force", name])

    def test_interrupt_cleans_owned_container_then_propagates(self):
        with patch.object(B.subprocess, "check_output", return_value=self.image_response), \
                patch.object(B.subprocess, "run", side_effect=[KeyboardInterrupt(),
                     subprocess.CompletedProcess([], 0)]) as run, self.assertRaises(KeyboardInterrupt):
            B.run(self.candidate, ["true"], **self.options)
        self.assertEqual(run.call_count, 2)

    def test_failed_cleanup_is_not_reported_as_a_clean_timeout(self):
        with patch.object(B.subprocess, "check_output", return_value=self.image_response), \
                patch.object(B.subprocess, "run", side_effect=[subprocess.TimeoutExpired([], 1),
                     subprocess.CompletedProcess([], 1)]), self.assertRaisesRegex(ValueError, "cleanup"):
            B.run(self.candidate, ["true"], **self.options)


if __name__ == "__main__":
    unittest.main()
