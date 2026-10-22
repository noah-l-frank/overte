#!/usr/bin/env python3
"""Offline composition of the central planner and the actual native worker CLI.

Create immutable Git candidate commits without materializing product resources.
No candidate programs, builds, network requests or GitHub Actions are executed.
Set OVERTE_NATIVE_TARGET_REFS=audit to additionally use locally fetched actual
protected target trees, rather than the checked-out tree for every target name.
"""
from copy import deepcopy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("native_central_cli", ROOT / "tools/repository-checks/pr_ci.py")
CLI = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CLI)


def git(root, *args, data=None, env=None):
    return subprocess.check_output(["git", "--no-replace-objects", *args], cwd=root,
        input=data, stderr=subprocess.PIPE, timeout=60, env=env).decode().strip()


class NativeWorkerComposition(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="overte-native-contract-")
        cls.root = Path(cls.temporary.name)
        cls.candidate = cls.root / "candidate.git"
        git(cls.root, "init", "--bare", "--quiet", str(cls.candidate))
        common = Path(git(ROOT, "rev-parse", "--git-common-dir"))
        if not common.is_absolute():
            common = ROOT / common
        (cls.candidate / "objects/info/alternates").write_text(str(common.resolve() / "objects") + "\n")
        cls.git_env = {**os.environ, "GIT_AUTHOR_NAME": "Offline native contract",
            "GIT_AUTHOR_EMAIL": "offline@example.invalid", "GIT_COMMITTER_NAME": "Offline native contract",
            "GIT_COMMITTER_EMAIL": "offline@example.invalid", "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull}
        cls.controller = git(ROOT, "rev-parse", "HEAD")
        cls.references = os.environ.get("OVERTE_NATIVE_TARGET_REFS")
        # Normal CI uses a small real Git fixture. The explicit audit mode
        # above additionally covers the seven complete protected product trees.
        if not cls.references:
            git(cls.candidate, "read-tree", "--empty", env=cls.git_env)
            fixture_paths = ["tests/shared/src/AABoxTests.cpp", "libraries/shared/src/AABox.cpp",
                "browser-client/src/zone-effects.ts", "tests/requirements-host.txt",
                *CLI.P._CODEQL._REVIEWED_CONTROLS,
                ".github/workflows/repository-checks.yml"]
            for project in ("browser-client", "script-archive/marketplace/S3Server"):
                fixture_paths += [project + "/package.json", project + "/package-lock.json"]
            for path in fixture_paths:
                row = git(ROOT, "ls-tree", "HEAD", "--", path)
                if row:
                    git(cls.candidate, "update-index", "--index-info", data=(row + "\n").encode(), env=cls.git_env)
            tree = git(cls.candidate, "write-tree", env=cls.git_env)
            cls.fixture_base = git(cls.candidate, "commit-tree", tree,
                data=b"Offline bounded source inventory\n", env=cls.git_env)

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    def candidate_for(self, target, changes):
        base = git(ROOT, "rev-parse", self.references + "/" + target) if self.references else self.fixture_base
        git(self.candidate, "read-tree", base, env=self.git_env)
        for path, mode, raw in changes:
            if mode is None:
                git(self.candidate, "update-index", "--index-info",
                    data=("0 " + "0" * 40 + "\t" + path + "\n").encode(), env=self.git_env)
            else:
                oid = git(self.candidate, "hash-object", "-w", "--stdin", data=raw, env=self.git_env)
                git(self.candidate, "update-index", "--add", "--cacheinfo", mode, oid, path, env=self.git_env)
        tree = git(self.candidate, "write-tree", env=self.git_env)
        head = git(self.candidate, "commit-tree", tree, "-p", base,
                   data=b"Offline candidate fixture\n", env=self.git_env)
        merge = git(self.candidate, "commit-tree", tree, "-p", base, "-p", head,
                    data=b"Offline test merge fixture\n", env=self.git_env)
        git(self.candidate, "update-ref", "HEAD", merge, env=self.git_env)
        context = {"repository": CLI.C.REPOSITORY, "repository_id": CLI.C.REPOSITORY_ID,
            "number": 42, "target": target, "base": base, "head_ref": "fix/main/offline-native",
            "head": head, "tree": tree, "original_merge": merge, "controller": self.controller,
            "execution_event": "pull_request", "caller_source": merge, "run_id": 777, "run_attempt": 1}
        plan = CLI.selection(self.candidate, context)
        return context, plan

    def worker(self, context, plan, *, expected=None, environment=None):
        env = {**os.environ, "GITHUB_REPOSITORY": CLI.C.REPOSITORY,
            "GITHUB_REPOSITORY_ID": str(CLI.C.REPOSITORY_ID), "GITHUB_RUN_ID": "777",
            "GITHUB_RUN_ATTEMPT": "1", "GITHUB_WORKFLOW_SHA": context["original_merge"],
            "GITHUB_SHA": context["original_merge"], "GITHUB_EVENT_NAME": "pull_request",
            "PR_CI_SOURCE_REF": "refs/pull/42/merge",
            "EXPECTED_MODE": plan["native"]["mode"] if expected is None else expected,
            **(environment or {})}
        out = self.root / "native-plan.json"
        out.unlink(missing_ok=True)
        result = subprocess.run([sys.executable, "-I", "-S", "-B",
            str(ROOT / "tools/repository-checks/pr_ci.py"), "verify-native",
            "--candidate", str(self.candidate), "--context-json", json.dumps(context),
            "--plan-json", json.dumps(plan), "--out", str(out)],
            env=env, text=True, capture_output=True, timeout=90)
        return result, json.loads(out.read_text()) if out.exists() else None

    def test_all_seven_targets_share_native_selection_for_pure_and_mixed_changes(self):
        cpp = "tests/shared/src/AABoxTests.cpp"
        # Existing, new, removed and nonregular inputs exercise immutable trees,
        # not a fabricated changed-path list or a mocked worker selection.
        cases = {
            "bounded": ([(cpp, "100644", b"// changed core test\n")], "core"),
            "mixed-browser": ([(cpp, "100644", b"// mixed core test\n"),
                ("browser-client/src/zone-effects.ts", "100644", b"export const changed = true;\n")], "core"),
            "mixed-host-requirements": ([(cpp, "100644", b"// mixed host test\n"),
                ("tests/requirements-host.txt", "100644", b"Pillow==13.0.0\n")], "core"),
            "production": ([("libraries/shared/src/AABox.cpp", "100644", b"// changed production\n")], "full"),
            "deleted": ([(cpp, None, None)], "core"),
            "new-unknown": ([("libraries/new-component/new.cpp", "100644", b"int fixture;\n")], "full"),
            "nonregular": ([(cpp, "120000", b"other.cpp")], "full"),
        }
        for target in CLI.P.TARGETS:
            for name, (changes, expected) in cases.items():
                if not self.references and target != "main" and name not in {"mixed-browser", "mixed-host-requirements"}:
                    continue
                with self.subTest(target=target, case=name):
                    context, plan = self.candidate_for(target, changes)
                    self.assertEqual(plan["native"]["mode"], expected)
                    result, native = self.worker(context, plan)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(native, {**plan["native"], "sha": context["original_merge"]})

    def test_skip_has_no_native_execution_and_cannot_obtain_native_receipt(self):
        for path, raw in (("browser-client/package-lock.json", b'{"lockfileVersion":3}\n'),
                ("script-archive/marketplace/S3Server/package-lock.json", b'{"lockfileVersion":3}\n'),
                ("docs/native-routing.md", b"Documentation only.\n")):
            with self.subTest(path=path):
                context, plan = self.candidate_for("main", [(path, "100644", raw)])
                self.assertEqual(plan["native"]["mode"], "skip")
                self.assertFalse(plan["owners"]["native"])
                result, native = self.worker(context, plan)
                self.assertNotEqual(result.returncode, 0)
                self.assertIsNone(native)

    def test_tampered_plan_candidate_and_source_ref_are_rejected(self):
        context, plan = self.candidate_for("main", [
            ("tests/shared/src/AABoxTests.cpp", "100644", b"// exact input\n")])
        for mutation in ("mode", "paths", "task", "tree", "merge", "target", "source-ref",
                         "controller", "event", "repository", "attempt", "caller", "source"):
            altered_context, altered_plan = deepcopy(context), deepcopy(plan)
            environment = {}
            if mutation == "mode":
                altered_plan["native"]["mode"] = "full"
            elif mutation == "paths":
                altered_plan["native"]["paths"] = []
            elif mutation == "task":
                altered_plan["tasks"] = []
            elif mutation == "tree":
                altered_context["tree"] = "1" * 40
            elif mutation == "merge":
                altered_context["original_merge"] = context["base"]
            elif mutation == "target":
                altered_context["target"] = "untrusted-target"
            elif mutation == "controller":
                altered_context["controller"] = "1" * 40
            elif mutation == "event":
                altered_context["execution_event"] = "workflow_dispatch"
            elif mutation == "repository":
                environment["GITHUB_REPOSITORY"] = "overte-org/overte"
            elif mutation == "attempt":
                environment["GITHUB_RUN_ATTEMPT"] = "2"
            elif mutation == "caller":
                environment["GITHUB_WORKFLOW_SHA"] = context["head"]
            elif mutation == "source":
                environment["GITHUB_SHA"] = context["head"]
            else:
                environment["PR_CI_SOURCE_REF"] = "refs/heads/main"
            with self.subTest(mutation=mutation):
                result, native = self.worker(altered_context, altered_plan, environment=environment)
                self.assertNotEqual(result.returncode, 0)
                self.assertIsNone(native)


if __name__ == "__main__":
    unittest.main()
