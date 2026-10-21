#!/usr/bin/env python3
"""Offline isolated-consumer regressions using tiny immutable suite fixtures."""

from contextlib import ExitStack, redirect_stderr, redirect_stdout
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
import importlib.util
import io
import json
import os
import subprocess
import tempfile
import unittest

import execution
import inputs
import runtime


SPEC = importlib.util.spec_from_file_location("test_isolated_sync_validation", Path(__file__).with_name("validate-sync.py"))
VALIDATION = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
SPEC.loader.exec_module(VALIDATION)


class EvidenceError(ValueError):
    pass


class FakeApi:
    def __init__(self, repository, pr):
        self.repository, self.pr = repository, pr
        self.calls = []

    def json(self, endpoint):
        self.calls.append(endpoint)
        if endpoint == "repos/noah-l-frank/overte":
            return deepcopy(self.repository)
        if endpoint == "repos/noah-l-frank/overte/pulls/42":
            return deepcopy(self.pr)
        raise AssertionError("unregistered read-only API fixture")


class IsolatedConsumerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="overte-sync-consumer-")
        self.addCleanup(self.temporary.cleanup)
        self.output = Path(self.temporary.name)
        self.candidate = self.output / "candidate"
        self.candidate.mkdir()
        (self.candidate / "tests").mkdir()
        (self.candidate / "libraries").mkdir()
        for directory in ("ios", "interface"):
            (self.candidate / directory).mkdir()
            (self.candidate / directory / ".keep").write_text("fixture root\n", encoding="utf-8")
        (self.candidate / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
        (self.candidate / "tests/platform-profile.json").write_text(
            json.dumps({"schema": 1, "platform": "shared", "suites": []}), encoding="utf-8")
        (self.candidate / "tests/control.py").write_text("# Trusted fixture control identity\n", encoding="utf-8")
        for name in ("alpha", "beta"):
            (self.candidate / "tests" / (name + ".py")).write_text(
                "from pathlib import Path\nimport os\n"
                "with Path(os.environ['FIXTURE_EXECUTION_LOG']).open('a') as log:\n"
                f"    log.write('{name}\\n')\n"
                "assert not any(os.environ.get(key) for key in ('GH_TOKEN','GITHUB_TOKEN','GITHUB_OUTPUT','GITHUB_ENV','GITHUB_PATH','GITHUB_STATE'))\n"
                f"assert os.environ.get('FIXTURE_FAIL_{name.upper()}') != '1'\n",
                encoding="utf-8")
            (self.candidate / "libraries" / (name + ".cpp")).write_text("candidate implementation\n", encoding="utf-8")
        self.git("init", "-q", "--initial-branch=main")
        self.git("config", "user.name", "Isolated consumer fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("add", ".")
        self.git("commit", "-qm", "Create immutable consumer fixture")
        self.commit, self.tree_sha = execution.checkout_identity(self.candidate)
        self.tree = inputs.full_tree(self.candidate)
        self.environment = {"toolchain": "prepared-test-host", "qt": "6", "backend": "software"}
        self.registry = {"schema": 1, "control_inputs": ["tests/control.py"], "suites": {}}
        for name in ("alpha", "beta"):
            self.registry["suites"][name] = {
                "command": ["python", "tests/" + name + ".py"], "layer": "quick", "scope": "content",
                "environment": "fixture-host", "closure": {"kind": "patterns",
                    "inputs": ["tests/" + name + ".py", "libraries/" + name + ".cpp"],
                    "required": ["tests/" + name + ".py", "libraries/" + name + ".cpp"]},
            }
        self.repository = {"full_name": "noah-l-frank/overte", "id": 1319052603}
        self.base, self.parent = "b" * 40, "a" * 40
        self.pr = {"number": 42, "state": "open", "mergeable": True, "merge_commit_sha": self.commit,
                   "base": {"ref": "apple-main", "sha": self.base},
                   "head": {"ref": "main", "sha": self.parent, "repo": {"id": 1319052603}}}
        self.request = SimpleNamespace(
            repository="noah-l-frank/overte", repository_id=1319052603, number=42,
            base="apple-main", base_sha=self.base, head="main", head_sha=self.parent,
            head_repository_id=1319052603, merge_sha=self.commit, parent="main", parent_sha=self.parent,
            profile="apple-family", classification="direct", repair_paths=(), changed_paths=("libraries/alpha.cpp",),
        )
        self.args = SimpleNamespace(candidate=self.candidate, repository="noah-l-frank/overte", pull_request=42,
                                    mode="reuse", profile="apple-family", base_sha=self.base,
                                    head_sha=self.parent, merge_sha=self.commit,
                                    junit=self.output / "results.xml", receipt=self.output / "validation.json")
        self.api = FakeApi(self.repository, self.pr)
        self.evidence = self.make_evidence()
        self.gate = SimpleNamespace(
            load_config=lambda: {"repository": "noah-l-frank/overte", "repository_id": 1319052603},
            effective_pr_context=lambda event, api: None,
            classify_event=lambda event, config, api: self.request,
            verify_evidence=lambda api, config, request: deepcopy(self.evidence),
            branch_sha=lambda api, repository, branch: self.base if branch == "apple-main" else self.parent,
            parse_time=lambda value, label: datetime.fromisoformat(value.replace("Z", "+00:00")),
            EvidenceError=EvidenceError,
            GateError=ValueError,
            paginate_pull_files=lambda *arguments: [{"filename": "libraries/alpha.cpp", "status": "modified"}],
            changed_paths=lambda documents: {item[key] for item in documents for key in ("filename", "previous_filename") if key in item},
        )
        self.log = self.output / "executed.log"

    def git(self, *arguments):
        return subprocess.run(["git", "-c", "commit.gpgsign=false", *arguments], cwd=self.candidate,
                              check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True).stdout.strip()

    def make_evidence(self, parent_tree=None):
        parent_tree = self.tree if parent_tree is None else parent_tree
        now = datetime.now(timezone.utc)
        return {
            "environment": self.environment, "parent_inputs": deepcopy(parent_tree), "candidate_inputs": deepcopy(self.tree),
            "results": {"suites": {name: {"status": "passed", "fingerprint": inputs.suite_fingerprint(
                self.registry, name, parent_tree, self.environment)} for name in self.registry["suites"]}},
            "evidence_digest": "sha256:" + "e" * 64, "parent_branch": "main", "parent_commit": self.parent,
            "parent_tree": "f" * 40, "workflow": {"run_id": 9001, "run_attempt": 3},
            "qualified_at": (now - timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
            "expires_at": (now + timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
        }

    def validate(self, *, actual_environment=None, runtime_failure=None, execute_override=None,
                 ci_execute_override=None, extra_environment=None):
        with ExitStack() as stack:
            stack.enter_context(patch.object(VALIDATION, "_gate", return_value=self.gate))
            stack.enter_context(patch.object(inputs, "load_registry", return_value=deepcopy(self.registry)))
            runtime_options = {"side_effect": runtime_failure} if runtime_failure is not None else {
                "return_value": self.environment if actual_environment is None else actual_environment}
            stack.enter_context(patch.object(runtime, "capture_host_environment", **runtime_options))
            stack.enter_context(patch.dict(os.environ, {"FIXTURE_EXECUTION_LOG": str(self.log),
                "GH_TOKEN": "trusted-read-token", "GITHUB_TOKEN": "trusted-read-token",
                "GITHUB_OUTPUT": "private-output", "GITHUB_ENV": "private-environment",
                "GITHUB_PATH": "private-path", "GITHUB_STATE": "private-state", **(extra_environment or {})}))
            if execute_override is not None:
                stack.enter_context(patch.object(execution, "execute", side_effect=execute_override))
            if ci_execute_override is not None:
                stack.enter_context(patch.object(VALIDATION, "_execute_ci", side_effect=ci_execute_override))
            stack.enter_context(redirect_stdout(io.StringIO()))
            stack.enter_context(redirect_stderr(io.StringIO()))
            return VALIDATION.validate_sync(self.args, api=self.api)

    def executed(self):
        return self.log.read_text(encoding="utf-8").splitlines() if self.log.exists() else []

    def test_full_reuse_empty_product_profile_executes_zero_shared_tests(self):
        result = self.validate()
        self.assertEqual(result["mode"], "reuse")
        self.assertEqual(result["reused_suites"], ["alpha", "beta"])
        self.assertEqual(result["executed_suites"], [])
        self.assertEqual(self.executed(), [])
        self.assertEqual(result["parent_evidence"]["workflow"], {"run_id": 9001, "run_attempt": 3})
        self.assertEqual(result["parent_evidence"]["expires_at"], self.evidence["expires_at"])
        self.assertEqual(json.loads(self.args.receipt.read_text()), result)

    def test_pre_reuse_and_execution_capture_observe_the_same_effective_child_environment(self):
        captures = []

        def capture():
            captures.append({name: os.environ.get(name) for name in (
                "PATH", "VIRTUAL_ENV", "GIT_CONFIG_COUNT", "GIT_CONFIG_KEY_0", "GIT_CONFIG_VALUE_0",
                "GH_TOKEN", "GITHUB_TOKEN", "GITHUB_OUTPUT",
            )})
            return self.environment

        result = self.validate(runtime_failure=capture)
        self.assertEqual(len(captures), 3, "pre-reuse, before-execution and after-execution observations are required")
        self.assertTrue(all(value == captures[0] for value in captures))
        self.assertEqual(captures[0]["GIT_CONFIG_COUNT"], "2")
        self.assertTrue(captures[0]["PATH"].startswith(str(Path(VALIDATION.sys.executable).parent) + os.pathsep))
        self.assertIsNone(captures[0]["GH_TOKEN"])
        self.assertEqual(result["reused_suites"], ["alpha", "beta"])

    def test_normal_reuse_keeps_exactly_one_token_free_branch_differential(self):
        original = VALIDATION._differential
        calls = []

        def differential(candidate, request, documents):
            self.assertNotIn("GH_TOKEN", os.environ)
            self.assertNotIn("GITHUB_OUTPUT", os.environ)
            calls.append(request.profile)
            return original(candidate, request, documents)

        with patch.object(VALIDATION, "_differential", side_effect=differential):
            result = self.validate()
        self.assertEqual(calls, ["apple-family"])
        self.assertEqual(result["reused_suites"], ["alpha", "beta"])

    def test_normal_reuse_cannot_skip_a_failed_branch_differential(self):
        with patch.object(VALIDATION, "_differential", side_effect=ValueError("invalid changed JSON")), self.assertRaises(ValueError):
            self.validate()
        self.assertEqual(self.executed(), [])
        self.assertFalse(self.args.receipt.exists())

    def test_historical_child_source_difference_executes_only_affected_suite(self):
        parent_tree = deepcopy(self.tree)
        parent_tree["libraries/alpha.cpp"]["sha"] = "d" * 40
        self.evidence = self.make_evidence(parent_tree)
        result = self.validate()
        self.assertEqual(result["mode"], "partial-reuse")
        self.assertEqual(result["reused_suites"], ["beta"])
        self.assertEqual(result["executed_suites"], ["alpha"])
        self.assertEqual(self.executed(), ["alpha"])

    def test_actual_runtime_difference_forces_complete_shared_execution(self):
        result = self.validate(actual_environment=self.environment | {"qt": "5"})
        self.assertEqual(result["mode"], "fallback")
        self.assertEqual(result["reused_suites"], [])
        self.assertEqual(set(self.executed()), {"alpha", "beta"})

    def test_missing_or_unsupported_proof_falls_back_without_matching_unknown(self):
        self.gate.verify_evidence = lambda *arguments: (_ for _ in ()).throw(EvidenceError("unavailable"))
        result = self.validate()
        self.assertEqual(result["reused_suites"], [])
        self.assertEqual(set(self.executed()), {"alpha", "beta"})

    def test_unknown_actual_runtime_executes_all_without_reusable_identity(self):
        result = self.validate(runtime_failure=runtime.RuntimeIdentityError("unsupported runtime"))
        self.assertEqual(result["reused_suites"], [])
        self.assertEqual(set(self.executed()), {"alpha", "beta"})
        self.assertFalse(result["execution"]["reusable"])
        self.assertIsNone(result["execution"]["environment"])

    def test_explicit_fallback_never_requires_parent_artifact(self):
        self.args.mode = "fallback"
        self.gate.verify_evidence = lambda *arguments: (_ for _ in ()).throw(AssertionError("must not read proof"))
        result = self.validate()
        self.assertEqual(result["mode"], "fallback")
        self.assertEqual(set(self.executed()), {"alpha", "beta"})

    def test_selected_failure_cannot_emit_successful_validation_receipt(self):
        self.args.mode = "fallback"
        with self.assertRaises(VALIDATION.ValidationError):
            self.validate(extra_environment={"FIXTURE_FAIL_ALPHA": "1"})
        self.assertFalse(self.args.receipt.exists())

    def test_missing_persisted_execution_receipt_cannot_authorize_success(self):
        with self.assertRaises(VALIDATION.ValidationError):
            self.validate(execute_override=lambda *arguments, **keywords: (0, {"conclusion": "success"}))
        self.assertFalse(self.args.receipt.exists())

    def test_unexecuted_required_suite_cannot_hide_in_success_receipt(self):
        original = execution.execute
        self.args.mode = "fallback"

        def omit(candidate, **options):
            options["suite_names"] = ["alpha"]
            return original(candidate, **options)

        with self.assertRaises(VALIDATION.ValidationError):
            self.validate(execute_override=omit)
        self.assertFalse(self.args.receipt.exists())

    def test_actual_execution_environment_change_rejects_remaining_reuse_without_retry(self):
        original = execution.execute

        def drift(candidate, **options):
            with patch.object(runtime, "capture_host_environment", return_value=self.environment | {"qt": "5"}):
                return original(candidate, **options)

        with self.assertRaises(VALIDATION.ValidationError):
            self.validate(execute_override=drift)
        self.assertEqual(self.executed(), [])

    def test_execution_expansion_to_all_shared_removes_effective_reuse(self):
        original = execution.execute

        def fallback(candidate, **options):
            with patch.object(runtime, "capture_host_environment", side_effect=runtime.RuntimeIdentityError("unsupported")):
                return original(candidate, **options)

        result = self.validate(execute_override=fallback)
        self.assertEqual(result["reused_suites"], [])
        self.assertEqual(set(result["executed_suites"]), {"alpha", "beta"})
        self.assertFalse(result["execution"]["reusable"])

    def test_ordinary_nonmatching_or_repair_reuse_cannot_run(self):
        for scenario in ("ordinary", "wrong-profile", "repair", "wrong-commit"):
            with self.subTest(scenario=scenario):
                old_classifier, old_profile, old_repairs, old_merge = self.gate.classify_event, self.args.profile, self.request.repair_paths, self.args.merge_sha
                if scenario == "ordinary":
                    self.gate.classify_event = lambda *arguments: None
                elif scenario == "wrong-profile":
                    self.args.profile = "apple-ios"
                elif scenario == "repair":
                    self.request.repair_paths = ("ios/source.cpp",)
                else:
                    self.args.merge_sha = "c" * 40
                with self.assertRaises(VALIDATION.ValidationError):
                    self.validate()
                self.gate.classify_event, self.args.profile, self.request.repair_paths, self.args.merge_sha = old_classifier, old_profile, old_repairs, old_merge
        self.assertEqual(self.executed(), [])

    def test_local_candidate_tree_must_match_verified_api_tree(self):
        self.evidence["candidate_inputs"]["libraries/alpha.cpp"]["sha"] = "d" * 40
        with self.assertRaises(VALIDATION.ValidationError):
            self.validate()
        self.assertEqual(self.executed(), [])

    def test_live_parent_or_pull_request_drift_after_execution_fails_closed(self):
        original = execution.execute

        def moved(candidate, **options):
            result = original(candidate, **options)
            self.api.pr["head"]["sha"] = "d" * 40
            return result

        with self.assertRaises(VALIDATION.ValidationError):
            self.validate(execute_override=moved)
        self.assertFalse(self.args.receipt.exists())

    def test_final_parent_ref_and_original_expiry_are_rechecked(self):
        self.gate.branch_sha = lambda api, repository, branch: self.base if branch == "apple-main" else "d" * 40
        with self.assertRaises(VALIDATION.ValidationError):
            self.validate()
        self.assertFalse(self.args.receipt.exists())
        self.gate.branch_sha = lambda api, repository, branch: self.base if branch == "apple-main" else self.parent
        self.evidence["expires_at"] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat().replace("+00:00", "Z")
        # The fake verifier deliberately omits expiry validation so this tests
        # the consumer's final check rather than the already-tested live gate.
        with self.assertRaises(VALIDATION.ValidationError):
            self.validate()
        self.assertFalse(self.args.receipt.exists())

    def test_platform_suites_always_execute_even_with_full_shared_reuse(self):
        profile = {"schema": 1, "platform": "android", "suites": [
            {"name": "product", "entrypoint": "tests/product.py", "interpreter": "python"}]}
        (self.candidate / "tests/platform-profile.json").write_text(json.dumps(profile), encoding="utf-8")
        (self.candidate / "tests/product.py").write_text(
            "from pathlib import Path\nimport os\nPath(os.environ['FIXTURE_EXECUTION_LOG']).write_text('product\\n')\n", encoding="utf-8")
        self.git("add", ".")
        self.git("commit", "-qm", "Add declared product fixture")
        self.commit, self.tree_sha = execution.checkout_identity(self.candidate)
        self.tree = inputs.full_tree(self.candidate)
        self.request.merge_sha = self.args.merge_sha = self.api.pr["merge_commit_sha"] = self.commit
        self.evidence = self.make_evidence()
        result = self.validate()
        self.assertEqual(result["reused_suites"], ["alpha", "beta"])
        self.assertEqual(self.executed(), ["product"])
        self.assertEqual(set(result["execution"]["platform_results"]), {"product"})

    def test_bounded_documentation_skips_host_capture_and_execution(self):
        self.args.profile = self.request.profile = "documentation"
        self.request.changed_paths = ("README.md",)
        documents = [{"filename": "README.md", "status": "modified"}]
        self.gate.paginate_pull_files = lambda *arguments: documents
        self.gate.changed_paths = lambda documents: {item["filename"] for item in documents}
        with patch.object(VALIDATION, "_differential") as differential, \
                patch.object(execution, "execute", side_effect=AssertionError("host execution is unnecessary")):
            result = self.validate(runtime_failure=AssertionError("host capture is unnecessary"))
        differential.assert_called_once()
        self.assertEqual(result["mode"], "documentation")
        self.assertIsNone(result["execution"])
        self.assertTrue(self.args.junit.exists())

    def test_bounded_tool_profile_uses_only_trusted_token_free_tool_helper(self):
        self.args.profile = self.request.profile = "tool-dependencies"
        self.request.changed_paths = ("server-console/package-lock.json",)
        documents = [{"filename": self.request.changed_paths[0], "status": "modified"}]
        self.gate.paginate_pull_files = lambda *arguments: documents
        self.gate.changed_paths = lambda documents: {item["filename"] for item in documents}
        observations = []

        def run(candidate, projects):
            self.assertNotIn("GH_TOKEN", os.environ)
            self.assertNotIn("GITHUB_OUTPUT", os.environ)
            observations.append((candidate, projects))

        self.gate.tool_dependencies = SimpleNamespace(affected_projects=lambda paths: ("server-console",), run=run)
        with patch.object(VALIDATION, "_differential") as differential, \
                patch.object(execution, "execute", side_effect=AssertionError("host execution is unnecessary")):
            result = self.validate(runtime_failure=AssertionError("host capture is unnecessary"))
        differential.assert_called_once()
        self.assertEqual(observations, [(self.candidate, ["server-console"])])
        self.assertEqual(result["bounded_projects"], ["server-console"])
        self.assertIsNone(result["execution"])

    def test_s3_sync_names_external_required_owner_without_duplicate_or_fake_pass(self):
        from unittest.mock import Mock
        s3 = 'script-archive/marketplace/S3Server'
        for mixed in (False, True):
            self.args.profile = self.request.profile = 'tool-dependencies'
            paths = [s3 + '/package-lock.json'] + (['server-console/package.json'] if mixed else [])
            self.request.changed_paths = tuple(paths)
            self.gate.paginate_pull_files = lambda *arguments: [{'filename': path, 'status': 'modified'} for path in paths]
            self.gate.changed_paths = lambda documents: {item['filename'] for item in documents}
            run = Mock()
            selector = Mock(return_value=(s3, 'server-console') if mixed else (s3,))
            self.gate.tool_dependencies = SimpleNamespace(affected_projects=selector, run=run)
            self.gate.package_checks = SimpleNamespace(activated=Mock(return_value=True), validate_wiring=Mock())
            with patch.object(VALIDATION, '_differential') as differential:
                result = self.validate(runtime_failure=AssertionError('host capture is unnecessary'))
            differential.assert_called_once()
            self.assertEqual(result['external_package_set'], [s3])
            self.assertEqual(result['bounded_projects'], ['server-console'] if mixed else [])
            self.assertEqual(result['executed_suites'], [])
            self.assertNotIn(s3, self.args.junit.read_text())
            self.gate.package_checks.validate_wiring.assert_called_once_with(self.candidate)
            selector.assert_called_once_with(paths, include_s3=True)
            if mixed: run.assert_called_once_with(self.candidate, ['server-console'])
            else: run.assert_not_called()
        self.gate.package_checks.activated.return_value = False
        with patch.object(VALIDATION, '_differential'), self.assertRaisesRegex(VALIDATION.ValidationError, 'not activated'):
            self.validate()
        self.gate.package_checks.activated.return_value = True
        self.gate.package_checks.validate_wiring.side_effect = ValueError('unapproved owner')
        with patch.object(VALIDATION, '_differential'), self.assertRaisesRegex(ValueError, 'unapproved owner'):
            self.validate()

    def test_candidate_secrets_are_removed_and_trusted_read_token_is_restored(self):
        with patch.dict(os.environ, {"GH_TOKEN": "original", "GITHUB_OUTPUT": "command-file"}):
            with VALIDATION.candidate_environment():
                self.assertNotIn("GH_TOKEN", os.environ)
                self.assertNotIn("GITHUB_OUTPUT", os.environ)
            self.assertEqual(os.environ["GH_TOKEN"], "original")
            self.assertEqual(os.environ["GITHUB_OUTPUT"], "command-file")

    def ci_fixture(self, *, npm=False, quick_beta=False):
        """Review a tiny immutable reader graph; run only real fixture commands."""
        self.registry["suites"]["beta"]["layer"] = "quick" if quick_beta else "host"
        path = self.candidate / ".github/test-suites.json"
        path.parent.mkdir(); path.write_text(json.dumps(self.registry))
        path = self.candidate / "tools/branch-cleanup/cleanup.py"
        path.parent.mkdir(parents=True); path.write_text("# Reviewed CI implementation\n")
        if npm:
            path = self.candidate / "browser-client/package-lock.json"
            path.parent.mkdir(); path.write_text('{"fixture-version":"old"}\n')
        self.git("add", "."); self.git("commit", "-qm", "Create reviewed selective fixture")
        self.base = self.git("rev-parse", "HEAD")
        self.ci_base_tree = inputs.full_tree(self.candidate, self.base)
        (self.candidate / "tools/branch-cleanup/cleanup.py").write_text("# Changed CI implementation\n")
        if npm:
            (self.candidate / "browser-client/package-lock.json").write_text('{"fixture-version":"new"}\n')
        self.git("add", "."); self.git("commit", "-qm", "Change independent CI inputs")
        self.parent = self.git("rev-parse", "HEAD")
        self.ci_refresh()
        self.args.mode = "fallback"
        real_loader = VALIDATION._trusted_module
        self.ci_host = real_loader("fixture_sync_ci_host", VALIDATION.ROOT / "tools/repository-checks/host_selection.py")
        reviewed = self.ci_host.program_digest(self.ci_base_tree, self.candidate)
        self.ci_host.REVIEWED_PROGRAMS = reviewed
        self.ci_host.REVIEWED_CHILD_PROGRAMS = {"apple-main": reviewed}
        actual_select = self.ci_host.select
        self.ci_host.select = lambda *args, **kwargs: actual_select(*args, **{**kwargs, "trusted_root": self.candidate})
        self.ci_packages = SimpleNamespace(validate_wiring=Mock(return_value="npm-consumers-v1"),
            consumer_generation=Mock(return_value=True), has_staged_caller=Mock(return_value=True),
            activated=Mock(return_value=False), candidate_plan=Mock(side_effect=self.ci_package_plan),
            run=Mock(side_effect=AssertionError("external npm owner must not run twice")))
        self.ci_host.package_policy = lambda: self.ci_packages
        real_tree = inputs.full_tree
        def full_tree(root, commit="HEAD"):
            return deepcopy(self.ci_base_tree) if Path(root).resolve() == VALIDATION.ROOT else real_tree(root, commit)
        for replacement in (patch.object(inputs, "full_tree", side_effect=full_tree),
                patch.object(VALIDATION, "_trusted_module", side_effect=lambda name, path:
                    self.ci_host if name == "sync_ci_host_policy" else real_loader(name, path))):
            replacement.start(); self.addCleanup(replacement.stop)
        self.evidence = self.make_evidence()

    def ci_refresh(self):
        self.git("add", ".")
        tree = self.git("write-tree")
        self.commit = self.git("commit-tree", tree, "-p", self.base, "-p", self.parent,
                               "-m", "Create immutable exact-parent merge fixture")
        self.git("reset", "--hard", self.commit)
        self.tree_sha = tree; self.tree = inputs.full_tree(self.candidate, self.commit)
        paths = self.git("diff", "--name-only", self.base, self.commit).splitlines()
        self.request.base_sha = self.base; self.request.head_sha = self.parent
        self.request.parent_sha = self.parent; self.request.merge_sha = self.commit
        self.request.changed_paths = tuple(paths)
        self.pr["base"].update(sha=self.base, repo=self.repository)
        self.pr["head"].update(sha=self.parent, repo=self.repository)
        self.pr["merge_commit_sha"] = self.commit
        self.args.base_sha = self.base; self.args.head_sha = self.parent; self.args.merge_sha = self.commit
        self.gate.paginate_pull_files = lambda *arguments: [{"filename": path, "status": "modified"}
                                                           for path in self.request.changed_paths]

    def ci_package_plan(self, candidate, event, source):
        projects, profiles = [], {}
        lock = "browser-client/package-lock.json"
        if lock in self.request.changed_paths:
            projects = ["browser-client"]
            profiles = {"browser-client": {"profile": "source-map-postcss-v1", "required": True,
                "changed_paths": [lock], "reason": "reviewed-single-dependency-security-update"}}
        return {"unknown": False, "consumer_generation": True, "base": self.base, "head": self.parent,
            "candidate": source, "tree": self.tree_sha, "paths": list(self.request.changed_paths),
            "regular": True, "package_set": projects, "plan": "a" * 64, "policy": {"fixture": "b" * 64},
            "dependency_profiles": {"unknown": False, "base": {"revision": self.base},
                "candidate": {"revision": source, "tree": self.tree_sha}, "projects": profiles}}

    def ci_prepare(self):
        with patch.object(VALIDATION, "_gate", return_value=self.gate), \
                patch.object(inputs, "load_registry", return_value=deepcopy(self.registry)):
            selected = VALIDATION.select_sync(self.args, api=self.api)
        self.args.expected_selection = selected["selection"]
        return selected

    def test_ci_prerequisite_selection_does_not_capture_runtime_or_execute_commands(self):
        self.ci_fixture()
        with patch.object(execution, "_runner", side_effect=AssertionError("selection cannot execute")), \
                patch.object(runtime, "capture_host_environment", side_effect=AssertionError("no Qt setup yet")):
            selected = self.ci_prepare()
        self.assertEqual((selected["lane"], selected["full_host"]), ("affected-ci", False))
        self.assertEqual(selected["suites"], ["alpha"])
        self.assertEqual(selected["omitted_suites"], ["beta"])
        self.assertIs(selected["reusable"], False)
        self.assertFalse(self.args.receipt.exists())
        self.assertEqual(self.executed(), [])

    def test_partial_ci_selection_cannot_claim_pending_platform_execution(self):
        self.ci_fixture()
        with patch.object(VALIDATION, "_sync_platform_owner", side_effect=AssertionError("partial CI cannot delegate product commands")):
            selected = self.ci_prepare()
            result = self.validate()
        self.assertEqual(selected["lane"], "affected-ci")
        self.assertNotIn("pending_platform_owners", selected)
        self.assertNotIn("pending_platform_owners", result)

    def test_ci_execution_observes_exact_selected_commands_without_reuse_or_product_run(self):
        self.ci_fixture(); selected = self.ci_prepare()
        with patch.object(execution, "execute", side_effect=AssertionError("complete executor must remain separate")), \
                patch.object(VALIDATION, "_differential") as differential:
            result = self.validate(runtime_failure=AssertionError("CI omission does not use cached runtime proof"))
        differential.assert_called_once()
        self.assertEqual(self.executed(), ["alpha"])
        self.assertEqual(result["mode"], "affected-ci")
        self.assertEqual(result["reused_suites"], [])
        self.assertEqual(result["executed_suites"], ["alpha"])
        self.assertIsNone(result["parent_evidence"])
        self.assertEqual(result["ci_selection"], selected)
        self.assertEqual(result["execution"]["producer"], VALIDATION.CI_EXECUTION_PRODUCER)
        self.assertIs(result["execution"]["reusable"], False)
        self.assertIs(result["execution"]["include_platform"], False)
        self.assertEqual(result["execution"]["results"], [{"name": "alpha", "status": "passed",
            "command": self.registry["suites"]["alpha"]["command"]}])

    def test_ci_sync_leaves_exact_npm_ownership_external_without_duplicate_or_fake_result(self):
        self.ci_fixture(npm=True); self.ci_prepare()
        with patch.object(VALIDATION, "_differential"):
            result = self.validate(runtime_failure=AssertionError("no reusable environment needed"))
        self.assertEqual(result["external_package_set"], ["browser-client"])
        self.assertEqual(result["executed_suites"], ["alpha"])
        self.assertNotIn("browser-client", json.dumps(result["execution"]["results"]))
        self.ci_packages.run.assert_not_called()

    def test_ci_missing_owner_repairs_or_changed_product_readers_select_complete_fallback(self):
        self.ci_fixture(npm=True)
        self.ci_packages.consumer_generation.return_value = False
        self.assertEqual(self.ci_prepare()["lane"], "complete")
        self.ci_packages.consumer_generation.return_value = True
        self.request.repair_paths = ("libraries/alpha.cpp",)
        self.assertEqual(self.ci_prepare()["lane"], "complete")
        self.request.repair_paths = ()
        (self.candidate / "libraries/beta.cpp").write_text("Changed native reader\n")
        self.ci_refresh()
        self.assertEqual(self.ci_prepare()["lane"], "complete")

    def test_ci_requires_bound_fork_configuration_and_mandatory_package_owner(self):
        self.ci_fixture(npm=True)
        selected = self.ci_prepare()
        self.assertEqual(selected["lane"], "affected-ci")
        path = VALIDATION.ROOT / ".github/repository-checks.json"
        import hashlib
        self.assertEqual(selected["policy"][".github/repository-checks.json"], hashlib.sha256(path.read_bytes()).hexdigest())
        valid = {"repository": self.repository["full_name"], "repository_id": self.repository["id"],
                 "required_contexts": ["repository-checks"]}
        for config in ({**valid, "required_contexts": []}, {**valid, "repository": "other/overte"},
                       {**valid, "repository_id": True}, {**valid, "repository_id": 1}, None):
            with self.subTest(config=config), patch.object(VALIDATION, "_repository_owner_policy", return_value=config):
                self.assertEqual(self.ci_prepare()["lane"], "complete")
        with patch.object(VALIDATION, "_repository_owner_policy", side_effect=FileNotFoundError("missing policy")):
            self.assertEqual(self.ci_prepare()["lane"], "complete")
        self.ci_packages.has_staged_caller.return_value = False
        self.assertEqual(self.ci_prepare()["lane"], "complete")
        self.ci_packages.activated.return_value = True
        self.assertEqual(self.ci_prepare()["lane"], "affected-ci")
        self.ci_packages.activated.return_value = False
        self.ci_packages.has_staged_caller.return_value = True
        self.ci_packages.consumer_generation.return_value = False
        self.assertEqual(self.ci_prepare()["lane"], "complete")
        self.ci_packages.consumer_generation.return_value = True
        owner = self.ci_package_plan(self.candidate, {}, self.commit)
        owner["package_set"] = []
        with patch.object(self.ci_packages, "candidate_plan", return_value=owner):
            self.assertEqual(self.ci_prepare()["lane"], "complete")

    def test_ci_stale_prerequisite_or_differential_failure_prevents_execution(self):
        self.ci_fixture(); self.ci_prepare()
        self.args.expected_selection = "sha256:" + "0" * 64
        with self.assertRaises(VALIDATION.ValidationError): self.validate()
        self.assertEqual(self.executed(), [])
        self.ci_prepare()
        with patch.object(VALIDATION, "_differential", side_effect=ValueError("changed contract")), \
                self.assertRaises(ValueError): self.validate()
        self.assertEqual(self.executed(), [])

    def test_ci_failed_selected_command_cannot_emit_a_successful_sync_receipt(self):
        self.ci_fixture(); self.ci_prepare()
        with patch.object(VALIDATION, "_differential"), self.assertRaises(VALIDATION.ValidationError):
            self.validate(extra_environment={"FIXTURE_FAIL_ALPHA": "1"})
        self.assertEqual(self.executed(), ["alpha"])
        self.assertFalse(self.args.receipt.exists())

    def test_ci_diagnostic_missing_or_forged_execution_receipt_never_qualifies(self):
        self.ci_fixture(); self.ci_prepare()
        real_execute = VALIDATION._execute_ci
        for mutation in ("missing", "diagnostic", "omitted", "command", "candidate", "selection", "reusable"):
            def execute(*args, **kwargs):
                status, receipt = real_execute(*args, **kwargs)
                path = args[-1]
                if mutation == "missing": Path(path).unlink(); return status, receipt
                receipt = deepcopy(receipt)
                if mutation == "diagnostic": receipt = {"kind": "host-impact-selection", "reusable": False}
                elif mutation == "omitted": receipt["results"] = []
                elif mutation == "command": receipt["results"][0]["command"] = ["python", "tests/beta.py"]
                elif mutation == "candidate": receipt["candidate_commit"] = "0" * 40
                elif mutation == "selection": receipt["selection"] = "sha256:" + "0" * 64
                else: receipt["reusable"] = True
                receipt.pop("receipt_digest", None); receipt["receipt_digest"] = execution.digest(receipt)
                execution._write_receipt(path, receipt)
                return status, receipt
            with self.subTest(mutation=mutation), patch.object(VALIDATION, "_differential"), \
                    self.assertRaises(VALIDATION.ValidationError):
                self.validate(ci_execute_override=execute)
            self.assertFalse(self.args.receipt.exists())

    def test_ci_final_live_branch_drift_cannot_emit_success(self):
        self.ci_fixture(); self.ci_prepare()
        real_execute = VALIDATION._execute_ci
        def execute(*args, **kwargs):
            result = real_execute(*args, **kwargs)
            self.gate.branch_sha = lambda *args: "0" * 40
            return result
        with patch.object(VALIDATION, "_differential"), self.assertRaises(VALIDATION.ValidationError):
            self.validate(ci_execute_override=execute)
        self.assertEqual(self.executed(), ["alpha"])
        self.assertFalse(self.args.receipt.exists())

    def test_staged_ci_workflow_selects_before_qt_and_binds_both_execution_paths(self):
        import yaml
        workflow = VALIDATION.ROOT / "tools/repository-checks/workflows/sync-ci-selection.yml"
        data = yaml.safe_load(workflow.read_text()); steps = data["jobs"]["validate"]["steps"]
        selection = next(step for step in steps if step.get("id") == "select")
        self.assertIn("--select-only", selection["run"])
        for name in ("Set up candidate Java", "Install candidate host prerequisites"):
            step = next(step for step in steps if step["name"] == name)
            self.assertGreater(steps.index(step), steps.index(selection))
            self.assertEqual(step["if"], "(steps.select.outputs.consumer_setup != 'none' || steps.select.outputs.native_setup == '') && steps.select.outputs.full_host == 'true' && !(steps.select.outputs.lane == 'verified-empty' && steps.select.outputs.consumer_setup == 'none' && steps.select.outputs.empty_setup != '')")
        executions = [step for step in steps if "--expected-selection" in step.get("run", "")]
        self.assertEqual(len(executions), 3)
        self.assertEqual({step['name'] for step in executions}, {
            'Verify bounded synchronization without product setup',
            'Verify exact candidate suites and complete runtime identity',
            'Validate the exact unchanged synchronization without test execution'})
        for step in executions:
            self.assertEqual(step["env"]["EXPECTED_SELECTION"], "${{ steps.select.outputs.selection }}")
            self.assertIn('trusted/tools/test-evidence/validate-sync.py', step["run"])
            if step['name'] == 'Verify exact candidate suites and complete runtime identity':
                self.assertIn('"$SYNC_VALIDATOR_PYTHON" -B ', step['run'])
                self.assertEqual(step['env']['SYNC_VALIDATOR_PYTHON'],
                    "${{ steps.select.outputs.consumer_setup == 'none' && steps.select.outputs.native_setup != '' && 'python3' || 'build/host-tests-env/bin/python' }}")
                self.assertEqual(step['env']['EXPECTED_NATIVE_SETUP'], '${{ steps.select.outputs.native_setup }}')
                self.assertIn('--expected-native-setup "$EXPECTED_NATIVE_SETUP"', step['run'])
            else:
                self.assertIn('python3 -B ', step['run'])
                if step['name'] == 'Validate the exact unchanged synchronization without test execution':
                    self.assertEqual(step['if'], "steps.select.outputs.lane == 'verified-empty'")
                    self.assertEqual(step['env']['EXPECTED_EMPTY_SETUP'], '${{ steps.select.outputs.empty_setup }}')
                    self.assertIn('--expected-empty-setup "$EXPECTED_EMPTY_SETUP"', step['run'])
                    self.assertNotIn('--expected-native-setup', step['run'])
                    self.assertNotIn('SYNC_VALIDATOR_PYTHON', step['env'])
        self.assertEqual(data["permissions"], {"actions": "read", "checks": "read", "contents": "read", "pull-requests": "read"})
        # The source-preparation PR still runs the deployed historical recipe.
        # The distinct prospective recipe above is not deployed by changing a
        # canonical source leaf. Authenticate the active blob against complete
        # reviewed catalog data; never rewrite an old row to the new template.
        import hashlib
        catalog=json.loads((VALIDATION.ROOT/'.github/package-workflow-generations.json').read_bytes())['generations']
        active=(VALIDATION.ROOT/'.github/workflows/sync-validation.yml').read_bytes()
        active_entry={'mode':'100644','type':'blob','sha':hashlib.sha1(
            b'blob '+str(len(active)).encode()+b'\0'+active).hexdigest()}
        self.assertTrue(any(row['workflows'].get('.github/workflows/sync-validation.yml')==active_entry
            for row in catalog))
        # Materialize the future six-path tuple as ordinary immutable fixture
        # data. Its enrollment belongs to source composition, not this test.
        sources={'.github/workflows/project-tests.yml':
                'tools/repository-checks/workflows/producers/protected-project-tests-android-platform.yml',
            '.github/workflows/parent-qualification.yml':
                'tools/repository-checks/workflows/producers/parent-qualification-android-platform.yml',
            '.github/workflows/repository-checks.yml':
                'tools/repository-checks/workflows/producers/repository-checks.yml',
            '.github/workflows/sync-validation.yml':str(workflow.relative_to(VALIDATION.ROOT)),
            '.github/workflows/browser-client.yml':'.github/workflows/browser-client.yml',
            '.github/workflows/pr-metadata-context.yml':
                'tools/repository-checks/workflows/metadata-edits/pr-metadata-context.yml'}
        with tempfile.TemporaryDirectory(prefix='sync-future-tuple-') as temporary:
            snapshot=Path(temporary)
            for path,relative in sources.items():
                target=snapshot/path;target.parent.mkdir(parents=True,exist_ok=True)
                target.write_bytes((VALIDATION.ROOT/relative).read_bytes());target.chmod(0o644)
            self.assertEqual(yaml.safe_load((snapshot/'.github/workflows/sync-validation.yml').read_bytes()),data)
            self.assertEqual(len(list((snapshot/'.github/workflows').iterdir())),6)
            # Select the exact assembled canonical tuple, not the newest row
            # merely present in a preregistration catalog.
            actual={path:{'mode':'100644','type':'blob',
                'sha':hashlib.sha1(b'blob '+str(len((snapshot/path).read_bytes())).encode()+b'\0'+(snapshot/path).read_bytes()).hexdigest()}
                for path in sources}
            candidates=[row for row in catalog if row['name'] in {
                'protected-producer-original-default-required-context-v1',
                'protected-producer-optional-parent-source-v1', 'protected-producer-optional-leaf-common-v1',
                'protected-producer-exact-parent-command-owners-v1'} and row['workflows']==actual]
            self.assertLessEqual(len(candidates),1)
            future=candidates[0] if candidates else None
            if future is None:
                future=next((row for row in catalog if row['name']=='protected-producer-original-default-boolean-v1'),None)
            if future is None:
                future=next((row for row in catalog if row['name']=='protected-producer-original-default-v1'),None)
            if future is not None:
                for path in sources:
                    raw=(snapshot/path).read_bytes()
                    self.assertEqual(future['workflows'][path],{'mode':'100644','type':'blob',
                        'sha':hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()},path)
        gate = yaml.safe_load((VALIDATION.ROOT / '.github/workflows/sync-test-reuse.yml').read_text())
        self.assertEqual(gate['permissions'], {'actions':'read','checks':'read','contents':'read','pull-requests':'read'})
        self.assertEqual(gate['jobs']['sync-test-reuse']['permissions'],
            {'actions':'write','checks':'read','contents':'read','pull-requests':'read'})
        gate_steps = gate['jobs']['sync-test-reuse']['steps']
        trusted_checkouts = [step for step in gate_steps
            if step.get('name') == 'Check out trusted default-branch gate only'
            and step.get('uses') == 'actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1']
        self.assertEqual(len(trusted_checkouts), 1)
        trusted = trusted_checkouts[0]
        self.assertEqual(gate_steps[0], {'name': 'Require a successful event policy',
            'env': {'EVENT_POLICY': '${{ needs.event-policy.result }}'},
            'run': 'test "$EVENT_POLICY" = success'})
        self.assertEqual(gate_steps[1], {'name': 'Reject unauthenticated text edits without dispatching a validator',
            'if': "needs.event-policy.outputs.metadata_only == 'true'", 'run': 'exit 1'})
        self.assertGreater(gate_steps.index(trusted), 1)
        self.assertEqual(trusted['with']['ref'], '${{ github.event.repository.default_branch }}')
        self.assertIs(trusted['with']['persist-credentials'], False)
        self.assertNotIn('secrets', gate['jobs']['sync-test-reuse'])
        invocations=[step['run'] for step in gate['jobs']['sync-test-reuse']['steps']
            if 'tools/sync-test-reuse/' in step.get('run','')]
        self.assertEqual(len(invocations),3)
        self.assertTrue(all('python3 -B ' in command for command in invocations))


class NativeParentConsumerTests(unittest.TestCase):
    """Actual tiny candidate commands; native API admission is a typed seam."""
    def setUp(self):
        self.fixture=IsolatedConsumerTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.native_type=VALIDATION._gate().NativeParentEvidence
        self.fixture.gate.NativeParentEvidence=self.native_type
        self.fixture.gate.native_parent_evidence=Mock(side_effect=lambda *args:deepcopy(self.fixture.evidence))
        self.bind_native()

    def bind_native(self, parent_tree=None):
        f=self.fixture
        f.evidence=self.native_type(f.make_evidence(parent_tree) | {
            'kind':'original-native-parent-v1','original_commit':'e'*40,
            'original_git_context':{'fixture':'original immutable M'},
            'original_proof':{'verified':True,'run_id':100,'attempt':1,
                'receipt_sha256':'1'*64,'expires_at':'kept in outer evidence'}})

    def test_complete_native_reuse_has_no_unused_consumer_e_or_execution_receipt(self):
        f=self.fixture
        result=f.validate(runtime_failure=AssertionError('no unused consumer E'),
            execute_override=lambda *a,**k:(_ for _ in ()).throw(AssertionError('no unused execution')))
        self.assertEqual(result['mode'],'reuse')
        self.assertEqual(result['reused_suites'],['alpha','beta'])
        self.assertEqual(result['executed_suites'],[])
        self.assertIsNone(result['execution'])
        self.assertEqual(f.executed(),[])
        self.assertFalse(Path(str(f.args.receipt)+'.execution.json').exists())
        self.assertEqual(result['parent_evidence']['original_commit'],'e'*40)
        self.assertEqual(result['parent_evidence']['parent_commit'],f.parent)
        self.assertFalse(result['parent_evidence']['qualification'])
        self.assertFalse(result['parent_evidence']['reusable'])
        self.assertEqual(result['parent_evidence']['expires_at'],f.evidence['expires_at'])
        self.assertNotIn('workflow',result['parent_evidence'])
        f.gate.native_parent_evidence.assert_called_once()
        import xml.etree.ElementTree as ET
        names=[item.attrib['name'] for item in ET.parse(f.args.junit).iter('testcase')]
        self.assertEqual(names,['sync-differential'])

    def test_historical_child_change_executes_only_affected_suite_under_its_actual_runtime(self):
        f=self.fixture
        parent=deepcopy(f.tree);parent['libraries/alpha.cpp']['sha']='c'*40
        self.bind_native(parent)
        result=f.validate(actual_environment=f.environment | {'qt':'different consumer runtime'})
        self.assertEqual(result['reused_suites'],['beta'])
        self.assertEqual(result['executed_suites'],['alpha'])
        self.assertEqual(f.executed(),['alpha'])
        self.assertEqual(result['execution']['environment']['qt'],'different consumer runtime')
        self.assertEqual(result['parent_evidence']['reused_results'],{'beta':f.evidence['results']['suites']['beta']})
        f.gate.native_parent_evidence.assert_called_once()

    def test_native_common_reuse_never_omits_actual_platform_commands(self):
        f=self.fixture
        profile=f.candidate/'tests/platform-profile.json'
        profile.write_text(json.dumps({'schema':1,'platform':'android','suites':[
            {'name':'product-fixture','interpreter':'python','entrypoint':'tests/product.py'}]}))
        (f.candidate/'tests/product.py').write_text('from pathlib import Path\nimport os\nPath(os.environ["FIXTURE_EXECUTION_LOG"]).write_text("product\\n")\n')
        f.git('add','.');f.git('commit','-qm','Declare required fixture platform')
        f.commit,f.tree_sha=execution.checkout_identity(f.candidate)
        f.tree=inputs.full_tree(f.candidate)
        f.request.merge_sha=f.commit;f.pr['merge_commit_sha']=f.commit;f.args.merge_sha=f.commit
        self.bind_native()
        result=f.validate()
        self.assertEqual(result['reused_suites'],['alpha','beta'])
        self.assertEqual(result['executed_suites'],[])
        self.assertEqual(f.executed(),['product'])
        self.assertEqual(set(result['execution']['platform_results']),{'product-fixture'})
        self.assertTrue(result['execution']['include_platform'])

    def test_after_start_missing_changed_or_expired_native_proof_is_hard_failure_without_retry(self):
        f=self.fixture
        parent=deepcopy(f.tree);parent['libraries/alpha.cpp']['sha']='c'*40
        self.bind_native(parent)
        f.gate.native_parent_evidence.side_effect=EvidenceError('native publisher unavailable')
        with self.assertRaisesRegex(VALIDATION.ValidationError,'became unavailable'):
            f.validate()
        self.assertEqual(f.executed(),['alpha'])
        self.assertFalse(f.args.receipt.exists())
        f.gate.native_parent_evidence.assert_called_once()

    def test_changed_native_bookend_is_rejected_even_without_workload(self):
        f=self.fixture
        changed=deepcopy(f.evidence);changed['original_proof']['receipt_sha256']='0'*64
        f.gate.native_parent_evidence.side_effect=None
        f.gate.native_parent_evidence.return_value=changed
        with self.assertRaisesRegex(VALIDATION.ValidationError,'proof changed'):
            f.validate(runtime_failure=AssertionError('no unused consumer E'))
        self.assertEqual(f.executed(),[])
        self.assertFalse(f.args.receipt.exists())

    def test_untyped_legacy_json_kind_cannot_bypass_consumer_runtime_comparison(self):
        f=self.fixture
        f.evidence=dict(f.evidence)
        result=f.validate(actual_environment=f.environment | {'qt':'different consumer runtime'})
        self.assertEqual(result['mode'],'fallback')
        self.assertEqual(set(f.executed()),{'alpha','beta'})
        f.gate.native_parent_evidence.assert_not_called()

    def test_expired_native_proof_during_validation_cannot_publish_success(self):
        f=self.fixture
        f.evidence['expires_at']='2020-01-01T00:00:00Z'
        with self.assertRaisesRegex(VALIDATION.ValidationError,'expired'):
            f.validate(runtime_failure=AssertionError('no unused consumer E'))
        self.assertFalse(f.args.receipt.exists())

    def test_missing_native_admission_keeps_real_full_fallback(self):
        f=self.fixture
        f.gate.verify_evidence=lambda *args:(_ for _ in ()).throw(EvidenceError('missing original native proof'))
        result=f.validate()
        self.assertEqual(result['mode'],'fallback')
        self.assertEqual(set(f.executed()),{'alpha','beta'})
        f.gate.native_parent_evidence.assert_not_called()


class ArtifactNamespaceSelectionTests(unittest.TestCase):
    def selected(self, **changes):
        value = {'schema': 1, 'kind': 'sync-ci-selection', 'reusable': False,
            'selection': 'sha256:' + '1' * 64, 'lane': 'affected-ci',
            'full_host': False, 'suites': ['workflow-contracts'],
            'profile': 'apple-family', 'requested_mode': 'reuse'}
        value.update(changes)
        return value

    def test_namespace_utility_follows_actual_selected_owners_not_full_host(self):
        for owner in ('project-runner', 'device-control-plane-full',
                      'project-runner-candidate-' + 'a' * 12,
                      'device-control-plane-full-candidate-' + 'b' * 12):
            for full_host in (False, True):
                selected = self.selected(suites=['workflow-contracts', owner], full_host=full_host)
                original = deepcopy(selected)
                with self.subTest(owner=owner, full_host=full_host):
                    self.assertTrue(VALIDATION.requires_artifact_namespace(selected))
                    self.assertEqual(selected, original)
        for full_host in (False, True):
            self.assertFalse(VALIDATION.requires_artifact_namespace(
                self.selected(full_host=full_host)))
        self.assertTrue(VALIDATION.requires_artifact_namespace(
            self.selected(lane='complete', full_host=True, suites=[])))
        for profile in ('documentation', 'tool-dependencies'):
            self.assertFalse(VALIDATION.requires_artifact_namespace(self.selected(
                lane='legacy-bounded', full_host=False, suites=[], profile=profile)))

    def test_unknown_or_malformed_setup_never_omits_namespace_utility(self):
        values = [None, [], {}, self.selected(lane='unknown'), self.selected(schema=True),
            self.selected(suites=[]), self.selected(suites=('project-runner',)),
            self.selected(suites=['workflow-contracts', 'workflow-contracts']),
            self.selected(suites=['foreign/module']), self.selected(full_host='false'),
            self.selected(selection='sha256:' + 'G' * 64),
            self.selected(consumer_setup='none'),
            self.selected(consumer_setup='none', native_setup='sha256:' + '2' * 64, suites=[]),
            self.selected(consumer_setup='unknown'),
            self.selected(consumer_setup='none', native_setup='invalid'),
            self.selected(native_setup='sha256:' + '2' * 64),
            self.selected(empty_setup='sha256:' + '1' * 64),
            self.selected(lane='complete', full_host=False),
            self.selected(lane='legacy-bounded', suites=[], profile='apple-family'),
            self.selected(lane='legacy-bounded', suites=[], profile='documentation', requested_mode='fallback')]
        for selected in values:
            original = deepcopy(selected)
            with self.subTest(selected=selected):
                self.assertTrue(VALIDATION.requires_artifact_namespace(selected))
                self.assertEqual(selected, original)

    def test_select_only_adds_utility_output_without_mutating_selection_or_receipt(self):
        for selected, expected in ((self.selected(suites=['project-runner']), 'true'),
                                   (self.selected(), 'false')):
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as directory:
                output = Path(directory) / 'output'
                original = deepcopy(selected)
                argv = ['--candidate', directory, '--repository', 'noah-l-frank/overte',
                    '--pull-request', '42', '--mode', 'reuse', '--profile', 'apple-family',
                    '--base-sha', 'a' * 40, '--head-sha', 'b' * 40, '--merge-sha', 'c' * 40,
                    '--junit', str(Path(directory) / 'unused.xml'),
                    '--receipt', str(Path(directory) / 'unused.json'), '--select-only', '--output', str(output)]
                rendered = io.StringIO()
                with patch.object(VALIDATION, 'select_sync', return_value=selected) as select, \
                        patch.object(VALIDATION, 'validate_sync', side_effect=AssertionError('selection cannot execute')) as execute, \
                        redirect_stdout(rendered), redirect_stderr(io.StringIO()):
                    self.assertEqual(VALIDATION.main(argv), 0)
                select.assert_called_once(); execute.assert_not_called()
                self.assertEqual(selected, original)
                self.assertEqual(json.loads(rendered.getvalue()), original)
                fields = dict(line.split('=', 1) for line in output.read_text().splitlines())
                self.assertEqual(fields.pop('requires_artifact_namespace'), expected)
                self.assertEqual(fields, {'selection': original['selection'], 'lane': original['lane'],
                    'full_host': str(original['full_host']).lower(), 'consumer_setup': 'required',
                    'native_setup': '', 'empty_setup': ''})
                self.assertFalse((Path(directory) / 'unused.xml').exists())
                self.assertFalse((Path(directory) / 'unused.json').exists())


class NativeZeroCommandSetupTests(unittest.TestCase):
    def setUp(self):
        self.native = NativeParentConsumerTests()
        self.native.setUp()
        self.addCleanup(self.native.doCleanups)
        self.fixture = self.native.fixture

    def prepare(self, *, affected=False):
        f = self.fixture
        if affected:
            f.ci_fixture(); f.args.mode = 'reuse'; self.native.bind_native()
        selected = f.ci_prepare()
        f.args.expected_native_setup = selected.get('native_setup', '')
        return selected

    def test_namespace_output_recognizes_actual_native_zero_and_partial_proof_loss(self):
        selected = self.prepare()
        original = deepcopy(selected)
        self.assertEqual(selected['consumer_setup'], 'none')
        self.assertFalse(VALIDATION.requires_artifact_namespace(selected))
        self.assertEqual(selected, original)
        f = self.fixture
        parent_tree = deepcopy(f.tree)
        parent_tree['libraries/alpha.cpp']['sha'] = 'd' * 40
        self.native.bind_native(parent_tree)
        partial = self.prepare()
        self.assertEqual(partial['lane'], 'complete')
        self.assertNotIn('consumer_setup', partial)
        self.assertNotIn('native_setup', partial)
        self.assertTrue(VALIDATION.requires_artifact_namespace(partial))
        affected = self.prepare(affected=True)
        self.assertEqual(affected['lane'], 'affected-ci')
        self.assertEqual(affected['consumer_setup'], 'none')
        original = deepcopy(affected)
        self.assertFalse(VALIDATION.requires_artifact_namespace(affected))
        self.assertEqual(affected, original)
        self.assertEqual(f.executed(), [])

    def test_early_lookup_is_stdlib_only_and_does_not_change_pure_selection(self):
        f = self.fixture
        with patch.object(execution,'execute',side_effect=AssertionError('no execution during setup plan')), \
                patch.object(execution,'capture_execution_environment',side_effect=AssertionError('no unused consumer E')):
            selected = self.prepare()
        self.assertEqual(selected['consumer_setup'], 'none')
        self.assertTrue(selected['native_setup'].startswith('sha256:'))
        with patch.object(inputs,'load_registry',return_value=f.registry):
            source = VALIDATION._ci_selection(f.args,f.request,f.candidate,(f.commit,f.tree_sha),f.registry,f.api)
        self.assertEqual({key:value for key,value in selected.items() if key not in {'consumer_setup','native_setup'}}, source)
        self.assertEqual(f.executed(), [])

    def test_no_setup_complete_and_selected_paths_revalidate_native_proof_around_differential(self):
        # Separate real candidates keep selection-policy and typed-proof seams
        # explicit; neither path needs a venv, Qt installation or consumer E.
        for affected in (False, True):
            if affected:
                self.native.doCleanups(); self.setUp()
            f = self.fixture; selected = self.prepare(affected=affected)
            self.assertEqual(selected['consumer_setup'],'none')
            f.gate.native_parent_evidence.reset_mock()
            f.gate.verify_evidence = lambda *a: (_ for _ in ()).throw(AssertionError('no legacy capsule'))
            def differential(*args):
                self.assertEqual(f.gate.native_parent_evidence.call_count, 1, 'fresh native proof precedes differential')
            with patch.object(VALIDATION,'_differential',side_effect=differential) as check:
                result = f.validate(runtime_failure=AssertionError('no unused consumer E'),
                    execute_override=lambda *a,**k: (_ for _ in ()).throw(AssertionError('no unprepared fallback')),
                    ci_execute_override=lambda *a,**k: (_ for _ in ()).throw(AssertionError('no selected command')))
            check.assert_called_once()
            self.assertEqual(f.gate.native_parent_evidence.call_count,2)
            self.assertIsNone(result['execution'])
            self.assertEqual(result['executed_suites'],[])
            self.assertEqual(f.executed(),[])

    def test_missing_initial_proof_keeps_existing_setup_and_real_execution(self):
        f = self.fixture
        f.gate.native_parent_evidence.side_effect = EvidenceError('no current native proof')
        selected = self.prepare()
        self.assertNotIn('consumer_setup',selected)
        self.assertEqual(f.args.expected_native_setup,'')
        f.gate.verify_evidence = lambda *a: (_ for _ in ()).throw(EvidenceError('no legacy proof'))
        result = f.validate()
        self.assertEqual(set(result['executed_suites']),{'alpha','beta'})
        self.assertEqual(set(f.executed()),{'alpha','beta'})

    def test_marker_without_proof_or_changed_expired_required_proof_never_runs_unprepared_commands(self):
        f = self.fixture; self.prepare()
        original = deepcopy(f.evidence)
        changed = deepcopy(original); changed['original_proof']['receipt_sha256']='0'*64
        expired = deepcopy(original); expired['expires_at']='2020-01-01T00:00:00Z'
        required = deepcopy(original); del required['results']['suites']['alpha']
        for value in (EvidenceError('proof unavailable'), dict(original), changed, expired, required):
            f.gate.native_parent_evidence.side_effect = [value]
            with self.subTest(value=type(value).__name__), patch.object(VALIDATION,'_differential') as differential, \
                    self.assertRaises(VALIDATION.ValidationError):
                f.validate(execute_override=lambda *a,**k: (_ for _ in ()).throw(AssertionError('no unprepared fallback')))
            differential.assert_not_called()
            self.assertEqual(f.executed(),[])
            self.assertFalse(f.args.receipt.exists())

    def test_original_proof_expiry_or_ref_drift_after_differential_is_hard_failure(self):
        f = self.fixture; self.prepare()
        original = deepcopy(f.evidence)
        def differential(*args):
            f.evidence['original_proof']['receipt_sha256']='0'*64
        with patch.object(VALIDATION,'_differential',side_effect=differential), self.assertRaises(VALIDATION.ValidationError):
            f.validate()
        self.assertEqual(f.executed(),[])
        self.assertFalse(f.args.receipt.exists())
        f.evidence=deepcopy(original)
        def expired(*args): f.evidence['expires_at']='2020-01-01T00:00:00Z'
        with patch.object(VALIDATION,'_differential',side_effect=expired), self.assertRaises(VALIDATION.ValidationError): f.validate()
        self.assertEqual(f.executed(),[])
        self.assertFalse(f.args.receipt.exists())
        f.evidence=deepcopy(original)
        def moved(*args): f.api.pr['head']['sha']='f'*40
        with patch.object(VALIDATION,'_differential',side_effect=moved), self.assertRaises(VALIDATION.ValidationError): f.validate()
        self.assertEqual(f.executed(),[])
        self.assertFalse(f.args.receipt.exists())

    def test_nonempty_current_platform_cannot_schedule_no_setup(self):
        f = self.fixture
        profile=f.candidate/'tests/platform-profile.json'
        profile.write_text(json.dumps({'schema':1,'platform':'android','suites':[
            {'name':'product','entrypoint':'tests/product.py','interpreter':'python'}]}))
        (f.candidate/'tests/product.py').write_text('raise AssertionError("unprepared product must not run")\n')
        f.git('add','.');f.git('commit','-qm','Declare actual product requirement')
        f.commit,f.tree_sha=execution.checkout_identity(f.candidate);f.tree=inputs.full_tree(f.candidate)
        f.request.merge_sha=f.args.merge_sha=f.api.pr['merge_commit_sha']=f.commit
        self.native.bind_native()
        selected=self.prepare()
        self.assertNotIn('consumer_setup',selected)
        f.args.expected_native_setup='sha256:'+'0'*64
        with self.assertRaises(VALIDATION.ValidationError): f.validate()
        self.assertEqual(f.executed(),[])

    def test_workflow_skips_all_unused_setup_and_missing_required_venv_cannot_silently_fall_back(self):
        import yaml
        path=VALIDATION.ROOT/'tools/repository-checks/workflows/sync-ci-selection.yml'
        steps=yaml.safe_load(path.read_text())['jobs']['validate']['steps']
        for name in ('Set up candidate Python','Set up candidate Node.js','Set up candidate Java',
                'Install candidate host prerequisites','Prepare isolated shared and product Python validators'):
            self.assertTrue(next(step for step in steps if step['name']==name)['if'].startswith("(steps.select.outputs.consumer_setup != 'none' || steps.select.outputs.native_setup == '') && "))
        step=next(step for step in steps if step['name']=='Verify exact candidate suites and complete runtime identity')
        self.assertEqual(step['env']['SYNC_VALIDATOR_PYTHON'],
            "${{ steps.select.outputs.consumer_setup == 'none' && steps.select.outputs.native_setup != '' && 'python3' || 'build/host-tests-env/bin/python' }}")
        f=self.fixture; binary=f.output/'bin';binary.mkdir()
        fake=binary/'python3';fake.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$FIXTURE_VALIDATOR_ARGS"\n');fake.chmod(0o755)
        environment={**os.environ,'PATH':str(binary)+os.pathsep+os.environ['PATH'],
            'SYNC_VALIDATOR_PYTHON':'python3','EXPECTED_NATIVE_SETUP':'sha256:'+'1'*64,
            'FIXTURE_VALIDATOR_ARGS':str(f.output/'args')}
        # The exact workflow command can run without its missing venv. The fake
        # interpreter observes argument transport only, never asserts authority.
        result=subprocess.run(['bash','-e','-o','pipefail','-c',step['run']],cwd=f.output,env=environment,capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr)
        arguments=(f.output/'args').read_text().splitlines()
        self.assertEqual(arguments[:2],['-B','trusted/tools/test-evidence/validate-sync.py'])
        self.assertEqual(arguments[arguments.index('--expected-native-setup')+1],environment['EXPECTED_NATIVE_SETUP'])
        environment['SYNC_VALIDATOR_PYTHON']='build/host-tests-env/bin/python'
        result=subprocess.run(['bash','-e','-o','pipefail','-c',step['run']],cwd=f.output,env=environment,capture_output=True)
        self.assertNotEqual(result.returncode,0)


class NativeSelectedParentConsumerTests(unittest.TestCase):
    """Real selected fixture commands plus independently supplied typed proof."""
    def setUp(self):
        self.fixture = IsolatedConsumerTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.native_type = VALIDATION._gate().NativeParentEvidence
        self.fixture.gate.NativeParentEvidence = self.native_type
        self.fixture.gate.native_parent_evidence = Mock(side_effect=lambda *args: deepcopy(self.fixture.evidence))

    def prepare(self, *, two_selected=False, npm=False, parent_tree=None):
        f = self.fixture
        if two_selected:
            (f.candidate / 'tests/gamma.py').write_text('raise AssertionError("unselected must never run")\n')
            (f.candidate / 'libraries/gamma.cpp').write_text('unselected fixture input\n')
            f.registry['suites']['gamma'] = deepcopy(f.registry['suites']['beta'])
            f.registry['suites']['gamma'].update(command=['python','tests/gamma.py'], layer='host',
                closure={'kind':'patterns','inputs':['tests/gamma.py','libraries/gamma.cpp'],
                    'required':['tests/gamma.py','libraries/gamma.cpp']})
        # Declare both suites before constructing reviewed immutable B/M;
        # changing command definitions after review correctly selects fallback.
        f.ci_fixture(npm=npm, quick_beta=two_selected)
        f.args.mode = 'reuse'
        selected = f.ci_prepare()
        self.bind_native(parent_tree)
        # These counters describe final validation; early no-setup scheduling
        # has its own typed-proof tests and cannot authorize this invocation.
        f.gate.native_parent_evidence.reset_mock()
        return selected

    def bind_native(self, parent_tree=None):
        f = self.fixture
        f.evidence = self.native_type(f.make_evidence(parent_tree) | {
            'kind':'original-native-parent-v1','original_commit':'e'*40,
            'original_git_context':{'fixture':'original immutable M'},
            'original_proof':{'verified':True,'run_id':100,'attempt':1,'receipt_sha256':'1'*64}})

    def test_exact_selected_native_reuse_does_no_unused_execution_or_consumer_capture(self):
        f = self.fixture; selected = self.prepare(npm=True)
        with patch.object(VALIDATION,'_differential') as differential:
            result = f.validate(runtime_failure=AssertionError('no consumer E'),
                ci_execute_override=lambda *a,**k: (_ for _ in ()).throw(AssertionError('no remaining command')))
        differential.assert_called_once()
        self.assertEqual(selected['suites'], ['alpha'])
        self.assertEqual(result['reused_suites'], ['alpha'])
        self.assertEqual(result['executed_suites'], [])
        self.assertEqual(result['not_selected_suites'], ['beta'])
        self.assertEqual(result['external_package_set'], ['browser-client'])
        self.assertIsNone(result['execution'])
        self.assertFalse(Path(str(f.args.receipt)+'.ci-execution.json').exists())
        self.assertEqual(result['parent_evidence']['original_commit'], 'e'*40)
        self.assertFalse(result['parent_evidence']['qualification'])
        self.assertFalse(result['parent_evidence']['reusable'])
        self.assertEqual(set(result['parent_evidence']['reused_results']), {'alpha'})
        self.assertEqual(f.executed(), [])
        f.ci_packages.run.assert_not_called()
        self.assertEqual(f.gate.native_parent_evidence.call_count, 2)
        import xml.etree.ElementTree as ET
        self.assertEqual([x.attrib['name'] for x in ET.parse(f.args.junit).iter('testcase')], ['sync-differential'])

    def test_historical_child_difference_executes_only_selected_required_intersection(self):
        f = self.fixture; self.prepare(two_selected=True)
        parent = deepcopy(f.tree); parent['libraries/alpha.cpp']['sha'] = 'c'*40
        self.bind_native(parent)
        result = f.validate(runtime_failure=AssertionError('no unused consumer E'))
        self.assertEqual(result['reused_suites'], ['beta'])
        self.assertEqual(result['executed_suites'], ['alpha'])
        self.assertEqual(result['not_selected_suites'], ['gamma'])
        self.assertEqual(f.executed(), ['alpha'])
        self.assertEqual(result['execution']['requested_suites'], ['alpha'])
        self.assertEqual(result['execution']['selection'], f.args.expected_selection)
        self.assertFalse(result['execution']['reusable'])
        self.assertEqual(set(result['parent_evidence']['reused_results']), {'beta'})

    def test_missing_native_proof_executes_existing_selected_work_once(self):
        f = self.fixture; self.prepare()
        f.gate.native_parent_evidence.side_effect = EvidenceError('no original publisher')
        result = f.validate(runtime_failure=AssertionError('CI fallback does not need reusable E'))
        self.assertEqual(f.executed(), ['alpha'])
        self.assertEqual(result['reused_suites'], [])
        self.assertEqual(result['not_selected_suites'], ['beta'])
        self.assertIsNone(result['parent_evidence'])
        f.gate.native_parent_evidence.assert_called_once()

    def test_untyped_or_unselected_only_proof_cannot_skip_selected_work(self):
        f = self.fixture; self.prepare()
        f.evidence = dict(f.evidence)
        result = f.validate()
        self.assertEqual(result['executed_suites'], ['alpha'])
        self.assertEqual(result['reused_suites'], [])
        self.assertIsNone(result['parent_evidence'])
        f.log.unlink(); self.bind_native()
        # beta is passed but not selected. It cannot compensate for alpha.
        del f.evidence['results']['suites']['alpha']
        result = f.validate()
        self.assertEqual(f.executed(), ['alpha'])
        self.assertEqual(result['reused_suites'], [])
        self.assertIsNone(result['parent_evidence'])

    def test_original_proof_or_expiry_change_after_execution_is_hard_failure(self):
        f = self.fixture; self.prepare(two_selected=True)
        parent = deepcopy(f.tree); parent['libraries/alpha.cpp']['sha'] = 'c'*40
        self.bind_native(parent)
        changed = deepcopy(f.evidence); changed['original_proof']['receipt_sha256'] = '0'*64
        for final in (EvidenceError('publisher missing'), changed):
            f.gate.native_parent_evidence.side_effect = [deepcopy(f.evidence), final]
            with self.subTest(final=type(final).__name__), self.assertRaises(VALIDATION.ValidationError):
                f.validate()
            self.assertEqual(f.executed(), ['alpha'])
            self.assertFalse(f.args.receipt.exists())
            f.log.unlink()
        f.gate.native_parent_evidence.side_effect = lambda *args: deepcopy(f.evidence)
        f.evidence['expires_at'] = '2020-01-01T00:00:00Z'
        with self.assertRaisesRegex(VALIDATION.ValidationError, 'expired'):
            f.validate()
        self.assertEqual(f.executed(), ['alpha'])
        self.assertFalse(f.args.receipt.exists())

    def test_source_or_expected_selection_mismatch_blocks_before_commands(self):
        f = self.fixture; self.prepare()
        f.evidence['candidate_inputs']['libraries/alpha.cpp']['sha'] = 'c'*40
        with self.assertRaisesRegex(VALIDATION.ValidationError, 'verified native API inputs'): f.validate()
        self.assertEqual(f.executed(), [])
        self.bind_native(); f.args.expected_selection = 'sha256:'+'0'*64
        with self.assertRaisesRegex(VALIDATION.ValidationError, 'prerequisite plan'): f.validate()
        self.assertEqual(f.executed(), [])

    def test_selected_failure_never_retries_or_borrows_unselected_pass(self):
        f = self.fixture; self.prepare(two_selected=True)
        parent = deepcopy(f.tree); parent['libraries/alpha.cpp']['sha'] = 'c'*40
        self.bind_native(parent)
        with self.assertRaises(VALIDATION.ValidationError):
            f.validate(extra_environment={'FIXTURE_FAIL_ALPHA':'1'})
        self.assertEqual(f.executed(), ['alpha'])
        self.assertFalse(f.args.receipt.exists())
        f.gate.native_parent_evidence.assert_called_once()

    def test_internal_remaining_subset_cannot_expand_reorder_or_repeat_selection(self):
        f = self.fixture; selected = self.prepare(two_selected=True)
        for names in (['gamma'], ['beta','alpha'], ['alpha','alpha'], 'alpha'):
            with self.subTest(names=names), self.assertRaises(VALIDATION.ValidationError):
                VALIDATION._ci_commands(selected, f.registry, suite_names=names)
        self.assertEqual(VALIDATION._ci_commands(selected, f.registry),
            {name:f.registry['suites'][name]['command'] for name in ('alpha','beta')})



class VerifiedEmptyConsumerTests(unittest.TestCase):
    """Dispatch proof is a narrow fixture; differential/source books are real."""
    def workflow_fixture_generation(self, root):
        # Classify complete ordinary endpoint bytes against the actual trusted
        # catalog. A matching synchronization leaf alone cannot select22.
        source=Path(__file__).resolve().parents[1]/'repository-checks/package_checks.py'
        packages=VALIDATION._trusted_module('verified_empty_fixture_packages',source)
        generation=packages.validate_wiring(root)
        self.assertIn(generation,{'npm-consumers-sync-ci-v1','npm-consumers-sync-ci-budget-v1','npm-consumers-sync-ci-budget-cleanup-v1','protected-producer-original-default-v1',
            'protected-producer-original-default-boolean-v1',
            'protected-producer-original-default-required-context-v1',
            'protected-producer-optional-parent-source-v1', 'protected-producer-optional-leaf-common-v1',
            'protected-producer-exact-parent-command-owners-v1'})
        return packages,generation

    def setUp(self):
        self.fixture=IsolatedConsumerTests('runTest');self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        f=self.fixture;f.request.changed_paths=()
        f.gate.paginate_pull_files=lambda *args:[]
        self.proof={'schema':1,'kind':'verified-empty-sync-v1','reusable':False,'qualification':False,
            'immutable':{'base':f.base,'head':f.parent,'candidate':f.commit,'tree':f.tree_sha},
            'native':{'job_id':702},'source':{'controller':'fixed actual default'}}
        f.gate.verified_empty_sync=Mock(side_effect=lambda *args:deepcopy(self.proof))
        f.gate.native_parent_evidence=Mock(side_effect=AssertionError('no prior test proof'))
        f.gate.verify_evidence=lambda *args:(_ for _ in ()).throw(AssertionError('no qualification capsule'))
        self.stack=self.enterContext(ExitStack())
        self.stack.enter_context(patch.object(VALIDATION,'_gate',return_value=f.gate))
        self.stack.enter_context(patch.object(inputs,'load_registry',return_value=f.registry))

    def prepare(self):
        f=self.fixture;selected=VALIDATION.select_sync(f.args,api=f.api)
        f.args.expected_selection=selected['selection']
        f.args.expected_empty_setup=selected.get('empty_setup','')
        return selected

    def run_without_tests(self):
        f=self.fixture
        with patch.object(execution,'execute',side_effect=AssertionError('no candidate command')), \
                patch.object(execution,'capture_execution_environment',side_effect=AssertionError('no unused E')), \
                patch.object(VALIDATION,'_execute_ci',side_effect=AssertionError('no CI command')), \
                patch.object(VALIDATION,'_bounded_junit',side_effect=AssertionError('no fictitious JUnit suite')), \
                patch.object(VALIDATION,'_native_zero_setup',side_effect=AssertionError('no prior-proof setup')):
            return VALIDATION.validate_sync(f.args,api=f.api)

    def test_namespace_output_recognizes_only_exact_verified_empty_marker(self):
        selected = self.prepare()
        original = deepcopy(selected)
        self.assertFalse(VALIDATION.requires_artifact_namespace(selected))
        self.assertEqual(selected, original)
        for name, value in (('empty_setup', 'sha256:' + 'f' * 64),
                            ('consumer_setup', 'required'), ('full_host', True),
                            ('native_setup', 'sha256:' + 'e' * 64)):
            changed = deepcopy(selected); changed[name] = value
            with self.subTest(field=name):
                self.assertTrue(VALIDATION.requires_artifact_namespace(changed))
        self.assertEqual(self.fixture.executed(), [])

    def test_early_empty_selection_and_final_validation_need_no_test_or_original_E(self):
        f=self.fixture
        with patch.object(execution,'execute',side_effect=AssertionError('no early candidate command')), \
                patch.object(execution,'capture_execution_environment',side_effect=AssertionError('no early E')), \
                patch.object(VALIDATION,'_native_zero_setup',side_effect=AssertionError('not native reused evidence')):
            selected=self.prepare()
        self.assertEqual(selected['lane'],'verified-empty');self.assertFalse(selected['full_host'])
        self.assertEqual(selected['consumer_setup'],'none');self.assertEqual(selected['empty_setup'],selected['selection'])
        self.assertNotIn('native_setup',selected);self.assertEqual(selected['suites'],[])
        with patch.object(VALIDATION,'_differential',wraps=VALIDATION._differential) as actual:
            result=self.run_without_tests()
        actual.assert_called_once();self.assertEqual(result['mode'],'verified-empty')
        self.assertEqual(result['kind'],'sync-no-execution-validation-v1')
        self.assertIsNone(result['execution']);self.assertIsNone(result['parent_evidence'])
        self.assertFalse(result['reusable']);self.assertFalse(result['qualification'])
        self.assertEqual(result['executed_suites'],[]);self.assertEqual(result['reused_suites'],[])
        self.assertFalse(f.args.junit.exists());self.assertEqual(f.executed(),[])
        self.assertEqual(json.loads(f.args.receipt.read_bytes()),result)
        self.assertGreaterEqual(f.gate.verified_empty_sync.call_count,4)
        f.gate.native_parent_evidence.assert_not_called()

    def test_forged_marker_prior_native_marker_and_nonempty_selection_cannot_skip_work(self):
        f=self.fixture;self.prepare()
        for kind in ('missing','changed','prior-native','no-proof','not-empty'):
            f.args.expected_empty_setup=self.proof_selection=f.args.expected_selection
            f.args.expected_native_setup=''
            f.gate.verified_empty_sync.side_effect=lambda *args:deepcopy(self.proof)
            if kind=='missing':f.args.expected_empty_setup=''
            elif kind=='changed':f.args.expected_empty_setup='sha256:'+'f'*64
            elif kind=='prior-native':f.args.expected_native_setup='sha256:'+'e'*64
            elif kind=='no-proof':f.gate.verified_empty_sync.side_effect=lambda *args:None
            else:f.request.changed_paths=('libraries/alpha.cpp',)
            with self.subTest(kind=kind),self.assertRaises(VALIDATION.ValidationError):self.run_without_tests()
            self.assertFalse(f.args.receipt.exists());self.assertEqual(f.executed(),[])
        f.request.changed_paths=()

    def test_missing_initial_proof_retains_default_setup_not_an_empty_execution_claim(self):
        f=self.fixture;f.gate.verified_empty_sync.return_value=None;f.gate.verified_empty_sync.side_effect=None
        # Avoid the independently existing native reuse lookup. Its absence is
        # unrelated to no-change source equality and cannot authorize omission.
        with patch.object(VALIDATION,'_native_zero_setup',return_value=(None,None)):
            selected=VALIDATION.select_sync(f.args,api=f.api)
        self.assertEqual(selected['lane'],'complete');self.assertTrue(selected['full_host'])
        self.assertNotIn('consumer_setup',selected);self.assertNotIn('empty_setup',selected)
        self.assertEqual(f.executed(),[])

    def test_source_or_ref_bookend_drift_after_real_differential_fails_without_fallback(self):
        f=self.fixture;self.prepare()
        original=deepcopy(self.proof)
        for kind in ('source','ref','tree'):
            self.proof=deepcopy(original)
            f.api.pr=deepcopy(f.pr)
            def differential(*args):
                if kind=='source':self.proof['source']['controller']='changed default'
                elif kind=='ref':f.api.pr['head']['sha']='f'*40
                else:self.proof['immutable']['tree']='f'*40
            with self.subTest(kind=kind),patch.object(VALIDATION,'_differential',side_effect=differential), \
                    self.assertRaises(VALIDATION.ValidationError):self.run_without_tests()
            self.assertFalse(f.args.receipt.exists());self.assertEqual(f.executed(),[])

    def test_future_workflow_gates_all_setup_and_uses_distinct_final_source_proof(self):
        import yaml
        path=VALIDATION.ROOT/'tools/repository-checks/workflows/sync-ci-selection.yml'
        steps=yaml.safe_load(path.read_text())['jobs']['validate']['steps']
        for name in ('Set up candidate Python','Set up candidate Node.js','Set up candidate Java',
                'Install candidate host prerequisites','Prepare isolated shared and product Python validators'):
            condition=next(step['if'] for step in steps if step['name']==name)
            self.assertIn("!(steps.select.outputs.lane == 'verified-empty' && steps.select.outputs.consumer_setup == 'none' && steps.select.outputs.empty_setup != '')",condition)
            self.assertIn("steps.select.outputs.native_setup == ''",condition)
        step=next(row for row in steps if row['name']=='Validate the exact unchanged synchronization without test execution')
        self.assertEqual(step['if'],"steps.select.outputs.lane == 'verified-empty'")
        self.assertTrue(step['run'].startswith('python3 -B '))
        self.assertIn('--expected-empty-setup "$EXPECTED_EMPTY_SETUP"',step['run'])
        self.assertNotIn('--expected-native-setup',step['run'])
        normal=next(row for row in steps if row['name']=='Verify exact candidate suites and complete runtime identity')
        self.assertIn("steps.select.outputs.lane != 'verified-empty'",normal['if'])
        active=(VALIDATION.ROOT/'.github/workflows/sync-validation.yml').read_text()
        packages,generation=self.workflow_fixture_generation(VALIDATION.ROOT)
        if generation in {'protected-producer-original-default-v1',
                'protected-producer-original-default-boolean-v1',
                'protected-producer-original-default-required-context-v1',
                'protected-producer-optional-parent-source-v1', 'protected-producer-optional-leaf-common-v1',
                'protected-producer-exact-parent-command-owners-v1'}:
            self.assertEqual(active,path.read_text())
            self.assertIn('expected-empty-setup',active)
            # Bind every independently stored canonical endpoint as well as the
            # deployed complete catalog; no old catalog row is rewritten.
            sources={'.github/workflows/project-tests.yml':'producers/protected-project-tests-android-platform.yml',
                '.github/workflows/parent-qualification.yml':'producers/parent-qualification-android-platform.yml',
                '.github/workflows/repository-checks.yml':'producers/repository-checks.yml',
                '.github/workflows/sync-validation.yml':'sync-ci-selection.yml',
                '.github/workflows/browser-client.yml':'npm-consumers/browser-client.yml',
                '.github/workflows/pr-metadata-context.yml':'metadata-edits/pr-metadata-context.yml'}
            if generation in {'protected-producer-optional-leaf-common-v1',
                    'protected-producer-exact-parent-command-owners-v1'}:
                sources['.github/workflows/project-tests.yml']='producers/protected-project-tests-optional-leaf.yml'
            if generation=='protected-producer-exact-parent-command-owners-v1':
                sources['.github/workflows/repository-checks.yml']='producers/repository-checks-parent-owners.yml'
            self.assertEqual(set(sources),set(packages.METADATA_WORKFLOW_PATHS))
            for target,relative in sources.items():
                actual=(VALIDATION.ROOT/target).read_bytes()
                historical_callers={'protected-producer-original-default-v1':
                    '81bcf1933edc435826e2de411a777cccd4dec7c7',
                    'protected-producer-original-default-boolean-v1':
                    '15d1b9ca9d4b58831cd5f8226efcd47681dd3e8a'}
                if generation in historical_callers and target=='.github/workflows/repository-checks.yml':
                    import hashlib
                    self.assertEqual(hashlib.sha1(b'blob '+str(len(actual)).encode()+b'\0'+actual).hexdigest(),
                        historical_callers[generation])
                    self.assertEqual(packages.validate_wiring(VALIDATION.ROOT),generation)
                else:
                    self.assertEqual(actual,
                        (VALIDATION.ROOT/'tools/repository-checks/workflows'/relative).read_bytes(),target)
        else:
            self.assertNotIn('expected-empty-setup',active)

    def test_empty_workflow_state_rejects_altered_missing_alias_mode_and_mixed_recipes(self):
        import shutil
        packages,generation=self.workflow_fixture_generation(VALIDATION.ROOT)
        reviewed=next(row for row in packages.workflow_generations() if row['name']==generation)
        self.assertEqual(set(reviewed['workflows']),set(packages.CONSUMER_WORKFLOW_PATHS
            if generation in ('npm-consumers-sync-ci-v1','npm-consumers-sync-ci-budget-v1','npm-consumers-sync-ci-budget-cleanup-v1') else packages.METADATA_WORKFLOW_PATHS))
        sync='.github/workflows/sync-validation.yml'
        for kind in ('altered','missing','alias','mode','mixed'):
            with self.subTest(kind=kind),tempfile.TemporaryDirectory(prefix='sync-whole-generation-') as temporary:
                snapshot=Path(temporary)
                for relative in reviewed['workflows']:
                    target=snapshot/relative;target.parent.mkdir(parents=True,exist_ok=True)
                    shutil.copyfile(VALIDATION.ROOT/relative,target);target.chmod(0o644)
                self.assertEqual(packages.validate_wiring(snapshot),generation)
                target=snapshot/sync
                if kind=='altered':target.write_text(target.read_text()+'\n# unreviewed recipe\n')
                elif kind=='missing':target.unlink()
                elif kind=='alias':
                    saved=target.with_suffix('.fixture');target.rename(saved);target.symlink_to(saved.name)
                elif kind=='mode':target.chmod(0o755)
                elif generation in ('npm-consumers-sync-ci-v1','npm-consumers-sync-ci-budget-v1','npm-consumers-sync-ci-budget-cleanup-v1'):
                    target.write_bytes((VALIDATION.ROOT/'tools/repository-checks/workflows/sync-ci-selection.yml').read_bytes())
                else:
                    (snapshot/'.github/workflows/project-tests.yml').write_bytes(
                        (VALIDATION.ROOT/'tools/repository-checks/workflows/host/project-tests.yml').read_bytes())
                with self.assertRaises(ValueError):packages.validate_wiring(snapshot)


class EffectiveBaseConsumerTests(unittest.TestCase):
    def setUp(self):
        self.fixture = IsolatedConsumerTests('test_full_reuse_empty_product_profile_executes_zero_shared_tests')
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()

    def test_fresh_api_snapshot_is_forwarded_separately_from_original_snapshot_and_live_base(self):
        f = self.fixture; f.ci_fixture(quick_beta=True)
        original_snapshot = f.git('rev-parse', f.base + '^')
        f.request.event_base_sha = original_snapshot
        contexts = []
        def current_context(api, request, *, event_pr=None):
            observed = f.pr if event_pr is None else event_pr
            value = {'base': request.base_sha, 'head': request.head_sha, 'candidate': request.merge_sha,
                     'event_base': observed['base']['sha']}
            contexts.append(deepcopy(value))
            return SimpleNamespace(planning=lambda: dict(value))
        f.gate.recheck_effective_request = current_context
        def plan(candidate, event, source, *, pr_context):
            self.assertEqual(event['pull_request']['base']['sha'], f.base)
            self.assertEqual(pr_context, {'base': f.base, 'head': f.parent, 'candidate': f.commit, 'event_base': f.base})
            self.assertNotEqual(pr_context['event_base'], original_snapshot)
            return f.ci_package_plan(candidate, event, source)
        f.ci_packages.candidate_plan.side_effect = plan
        selected = f.ci_prepare()
        self.assertEqual(selected['lane'], 'affected-ci')
        self.assertTrue(contexts)
        self.assertEqual(f.request.event_base_sha, original_snapshot)
        self.assertEqual(f.executed(), [])

    def test_candidate_differential_uses_complete_live_inventory_and_missing_paths_fail_before_commands(self):
        f = self.fixture; f.request.event_base_sha = 'c' * 40
        documents = [{'filename': 'libraries/alpha.cpp', 'status': 'modified'}]
        f.gate.immutable_change_documents = Mock(return_value=documents)
        f.gate.paginate_pull_files = Mock(side_effect=AssertionError('capped PR files cannot replace live inventory'))
        with patch.object(VALIDATION, '_differential') as differential:
            VALIDATION._candidate_differential(f.candidate, f.request, f.gate, f.api)
            differential.assert_called_once_with(f.candidate, f.request, documents)
        f.gate.immutable_change_documents.return_value = []
        with patch.object(VALIDATION, '_differential') as differential:
            with self.assertRaises(VALIDATION.ValidationError):
                VALIDATION._candidate_differential(f.candidate, f.request, f.gate, f.api)
            differential.assert_not_called()
        f.gate.paginate_pull_files.assert_not_called()
        self.assertEqual(f.executed(), [])


class NativeCurrentPrConsumerTests(unittest.TestCase):
    def setUp(self):
        self.f = IsolatedConsumerTests(); self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        f = self.f
        f.ci_fixture(quick_beta=True)
        f.args.mode = 'reuse'
        f.args.expected_selection = f.ci_prepare()['selection']
        f.gate.NativePrEvidence = VALIDATION._gate().NativePrEvidence
        self.evidence = f.gate.NativePrEvidence(kind='native-current-pr',
            original_commit=f.commit, candidate_inputs=deepcopy(f.tree), tested_inputs=deepcopy(f.tree),
            requested_suites=['alpha', 'beta'], environment=deepcopy(f.environment),
            results=deepcopy(f.evidence['results']), qualified_at=f.evidence['qualified_at'],
            expires_at=f.evidence['expires_at'],
            original_proof={'verified': True, 'run_id': 100, 'attempt': 1, 'receipt_sha256': '1' * 64},
            qualification=False, reusable=False)
        f.gate.native_pr_evidence = Mock(side_effect=lambda *args, **kwargs: deepcopy(self.evidence))
        f.gate.native_parent_evidence = Mock(side_effect=AssertionError('same PR is not parent proof'))

    def test_same_pr_no_setup_rechecks_proof_and_keeps_actual_differential(self):
        f = self.f
        selected = f.ci_prepare()
        f.args.expected_native_setup = selected['native_setup']
        self.assertEqual(selected['consumer_setup'], 'none')
        with patch.object(VALIDATION, '_differential') as differential:
            result = f.validate(runtime_failure=AssertionError('unused consumer E'),
                ci_execute_override=lambda *args, **kwargs: self.fail('duplicate executor'))
        differential.assert_called_once()
        self.assertEqual(result['reused_suites'], ['alpha', 'beta'])
        self.assertEqual(result['executed_suites'], [])
        self.assertIsNone(result['parent_evidence'])
        self.assertIsNone(result['execution'])
        self.assertEqual(result['original_pr_evidence']['original_commit'], f.commit)
        self.assertFalse(result['reusable']); self.assertFalse(result['qualification'])
        self.assertEqual(f.executed(), [])

    def test_selected_failed_stale_or_incomplete_original_never_runs_fallback(self):
        f = self.f
        for shape in ('failed', 'changed-tree', 'missing-suite'):
            with self.subTest(shape=shape):
                original = deepcopy(self.evidence)
                if shape == 'failed': f.gate.native_pr_evidence.side_effect = ValueError('selected native producer failed')
                elif shape == 'changed-tree': self.evidence['candidate_inputs'] = {}
                else: self.evidence['requested_suites'] = ['alpha']
                with self.assertRaises(ValueError), patch.object(execution, 'execute', side_effect=AssertionError('no second executor')):
                    f.validate(ci_execute_override=lambda *args, **kwargs: self.fail('no second executor'))
                self.evidence = original
                f.gate.native_pr_evidence.side_effect = lambda *args, **kwargs: deepcopy(self.evidence)
                self.assertEqual(f.executed(), [])
                self.assertFalse(f.args.receipt.exists())


class NativeProductPrConsumerTests(unittest.TestCase):
    """Real source plans and tiny Git inputs; native proof is a verifier seam."""
    def setUp(self):
        self.f = NativeCurrentPrConsumerTests(); self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        f = self.f.f; self.fixture = f
        # This is an actual product delta, so the unchanged reviewed CI graph
        # must select full setup. The native owner still supplies original E.
        (f.candidate / 'libraries/alpha.cpp').write_text('changed product implementation\n')
        f.ci_refresh()
        self.f.evidence.update(candidate_inputs=deepcopy(f.tree), tested_inputs=deepcopy(f.tree),
            original_commit=f.commit, results=deepcopy(f.make_evidence()['results']),
            platform_commands=[], original_platform_observation=None, platform_partition=None)
        source = SimpleNamespace(sync_source_ready=Mock(return_value=True))
        f.ci_packages.load = lambda *args: SimpleNamespace(native_owner_policy=lambda: source)
        original = f.ci_packages.candidate_plan.side_effect
        f.ci_packages.candidate_plan.side_effect = lambda *args: {**original(*args),
            'host_mode':'full' if source.sync_source_ready.return_value else 'delegated-sync'}
        self.source = source
        f.args.mode = 'reuse'
        f.args.expected_selection = ''
        if self._testMethodName == 'test_affected_full_profile_reports_only_actual_selected_subset':
            original_select = f.ci_host.select
            def select(*args, **kwargs):
                value = original_select(*args, **kwargs)
                return {**value, 'suites':['alpha'], 'include_platform':False,
                    'reason':'protected-affected-dependencies'}
            f.ci_host.select = select
            self.f.evidence['requested_suites'] = ['alpha']
            self.f.evidence['results']['suites'] = {'alpha':self.f.evidence['results']['suites']['alpha']}

    def prepare(self):
        f = self.fixture
        result = f.ci_prepare()
        f.args.expected_native_setup = result['native_setup']
        return result

    def test_product_source_plan_and_no_setup_consume_full_original_owner_once(self):
        f = self.fixture; selected = self.prepare()
        self.assertEqual(selected['lane'], 'native-owner')
        self.assertTrue(selected['full_host'])
        self.assertEqual(selected['consumer_setup'], 'none')
        self.assertTrue(selected['native_current_owner_required'])
        with patch.object(VALIDATION, '_differential') as differential:
            result = f.validate(runtime_failure=AssertionError('unused consumer E'),
                execute_override=lambda *a,**kw:self.fail('duplicate full executor'))
        differential.assert_called_once()
        self.assertEqual(result['mode'], 'native-current-owner')
        self.assertEqual(result['reused_suites'], ['alpha','beta'])
        self.assertEqual(result['executed_suites'], [])
        self.assertIsNone(result['execution']); self.assertIsNone(result['parent_evidence'])
        self.assertFalse(result['reusable']); self.assertFalse(result['qualification'])
        self.assertEqual(f.executed(), [])

    def test_affected_full_profile_reports_only_actual_selected_subset(self):
        f = self.fixture; selected = self.prepare()
        self.assertEqual(selected['lane'], 'native-owner')
        self.assertEqual(selected['suites'], ['alpha'])
        result = f.validate(runtime_failure=AssertionError('unused consumer E'),
            execute_override=lambda *a,**kw:self.fail('duplicate subset executor'))
        self.assertEqual(result['reused_suites'], ['alpha'])
        self.assertEqual(result['not_selected_suites'], ['beta'])
        self.assertEqual(result['executed_suites'], [])

    def test_failed_missing_or_incomplete_selected_owner_never_uses_parent_or_executor(self):
        f = self.fixture; self.prepare()
        for shape in ('missing','failed','subset'):
            with self.subTest(shape=shape):
                original = deepcopy(self.f.evidence)
                if shape == 'missing': f.gate.native_pr_evidence.side_effect = lambda *a,**kw:None
                elif shape == 'failed': f.gate.native_pr_evidence.side_effect = ValueError('failed native product owner')
                else: self.f.evidence['requested_suites'] = ['alpha']
                with self.assertRaises(ValueError):
                    f.validate(execute_override=lambda *a,**kw:self.fail('no second executor'))
                self.f.evidence = original
                f.gate.native_pr_evidence.side_effect = lambda *a,**kw:deepcopy(self.f.evidence)
                self.assertFalse(f.args.receipt.exists()); self.assertEqual(f.executed(), [])

    def test_promoted_owner_cannot_be_bypassed_by_fallback_mode(self):
        f = self.fixture; f.args.mode = 'fallback'
        with self.assertRaises(ValueError), patch.object(execution, 'execute', side_effect=AssertionError('no second executor')):
            f.ci_prepare()
        self.assertEqual(f.executed(), [])
        self.assertFalse(f.args.receipt.exists())

    def test_unadmitted_product_source_retains_existing_complete_fallback(self):
        self.source.sync_source_ready.return_value = False
        f = self.fixture
        f.gate.native_pr_evidence.side_effect = lambda *a,**kw:None
        f.gate.native_parent_evidence = Mock(return_value=None)
        selected = f.ci_prepare()
        self.assertEqual(selected['lane'], 'complete')
        self.assertNotIn('native_current_owner_required', selected)
        self.assertNotIn('native_setup', selected)

    def test_actual_platform_declarations_require_exact_completed_same_pr_native_coverage(self):
        f = self.fixture
        (f.candidate / 'tests/platform-profile.json').write_text(json.dumps({'schema':1,'platform':'android',
            'suites':[{'name':'pico4-device-free','entrypoint':'tests/pico.sh','interpreter':'bash'}]}))
        (f.candidate / 'tests/pico.sh').write_text('# fixture is never executed\n')
        f.ci_refresh()
        commands=[{'name':name,'command':command} for name,command in execution.platform_suites(f.candidate,f.registry['suites'])]
        self.f.evidence.update(candidate_inputs=deepcopy(f.tree), tested_inputs=deepcopy(f.tree), original_commit=f.commit,
            results=deepcopy(f.make_evidence()['results']), platform_commands=commands, platform_partition='sha256:'+'a'*64,
            original_platform_observation={'kind':'original-android-platform-native-job-v1','run_id':100,'attempt':1,
                'reusable':False,'qualification':False,'partition':'sha256:'+'a'*64})
        pending={'pico4-device-free':{'owner':'required-android','candidate':f.commit,
            'plan':'sha256:'+'b'*64,'inventory':'sha256:'+'c'*64}}
        def owner(*args, **kwargs): return deepcopy(pending) if kwargs.get('native_current') else {}
        with patch.object(VALIDATION, '_sync_platform_owner', side_effect=owner) as handoff:
            selected = self.prepare()
            self.assertEqual(selected['platform_commands'],commands)
            result=f.validate(execute_override=lambda *a,**kw:self.fail('duplicate platform executor'))
            self.assertEqual(result['original_platform_commands'],commands)
            self.assertEqual(result['external_platform_owners'],pending)
            self.assertFalse(result['reusable']); self.assertIsNone(result['execution'])
            self.assertTrue(any(call.kwargs.get('native_current') for call in handoff.call_args_list))
            f.args.receipt.unlink()
            self.f.evidence['original_platform_observation']=None
            with self.assertRaises(ValueError):
                f.validate(execute_override=lambda *a,**kw:self.fail('missing native owner cannot fallback'))
            self.assertFalse(f.args.receipt.exists())



class ExactTreeParentConsumerTests(unittest.TestCase):
    """The distinct native report path never captures consumer E or reruns CI."""
    def setUp(self):
        self.f=IsolatedConsumerTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        f=self.f;f.ci_fixture();f.args.mode='reuse'
        native_gate=VALIDATION._gate()
        self.kind=native_gate.NativeExactTreeParentEvidence
        f.gate.NativeExactTreeParentEvidence=self.kind
        # The existing tiny isolated fixture models one command. The finite
        # 32/37 cases below call the real protected-roster consistency helper.
        f.gate.exact_tree_covered_suites=lambda proof,names: (['alpha']
            if proof.get('kind')=='original-sync-identical-android-tree-v1'
            and proof.get('requested_suites')==names==['alpha']
            else native_gate.exact_tree_covered_suites(proof,names))
        now=datetime.now(timezone.utc)
        self.evidence=self.kind({'kind':'original-sync-identical-android-tree-v1','source':'a'*40,
            'qualification':False,'reusable':False,'parent_branch':'android-main','parent_commit':f.parent,
            'parent_tree':f.tree_sha,'candidate_inputs':deepcopy(f.tree),'requested_suites':['alpha'],
            'original_commit':'c'*40,'qualified_at':(now-timedelta(minutes=5)).isoformat().replace('+00:00','Z'),
            'expires_at':(now+timedelta(hours=1)).isoformat().replace('+00:00','Z'),
            'original_proof':{'parent_pr':40,'gate_run_id':100,'run_id':101,'attempt':1,
                'artifact_id':102,'artifact_digest':'sha256:'+'1'*64,'receipt_digest':'sha256:'+'2'*64},
            'original_report':{'mode':'affected-ci','reused_suites':[],'executed_suites':['alpha']}})
        f.gate.native_exact_tree_parent_evidence=Mock(side_effect=lambda *a:deepcopy(self.evidence))
        f.gate.native_parent_evidence=Mock(side_effect=EvidenceError('legacy parent proof unavailable'))

    def prepare(self):
        f=self.f;selected=f.ci_prepare();f.args.expected_native_setup=selected.get('native_setup','')
        return selected

    def test_zero_setup_differential_and_original_report_coverage_without_environment_or_commands(self):
        f=self.f;selected=self.prepare()
        self.assertEqual(selected['consumer_setup'],'none')
        self.assertEqual(selected['suites'],['alpha'])
        with patch.object(VALIDATION,'_differential') as differential, \
                patch.object(inputs,'plan_reuse',side_effect=AssertionError('no generic reuse/E')):
            result=f.validate(runtime_failure=AssertionError('no consumer environment'),
                execute_override=lambda *a,**k:(_ for _ in ()).throw(AssertionError('no full executor')),
                ci_execute_override=lambda *a,**k:(_ for _ in ()).throw(AssertionError('no duplicate CI')))
        differential.assert_called_once()
        self.assertEqual(result['mode'],'native-exact-tree-parent')
        self.assertEqual(result['reused_suites'],['alpha']);self.assertEqual(result['executed_suites'],[])
        self.assertIsNone(result['execution']);self.assertIs(result['reusable'],False);self.assertIs(result['qualification'],False)
        self.assertEqual(result['parent_evidence']['original_report'],self.evidence['original_report'])
        self.assertNotIn('reused_results',result['parent_evidence'])
        f.gate.native_parent_evidence.assert_not_called()
        self.assertEqual(f.executed(),[])
        self.assertFalse(Path(str(f.args.receipt)+'.ci-execution.json').exists())
        import xml.etree.ElementTree as ET
        self.assertEqual([c.get('name')for c in ET.parse(f.args.junit).iter('testcase')],['sync-differential'])

    def test_absent_initial_original_proof_retains_mandatory_real_selected_execution(self):
        f=self.f;f.gate.native_exact_tree_parent_evidence.return_value=None
        f.gate.native_exact_tree_parent_evidence.side_effect=None
        selected=self.prepare();self.assertNotIn('consumer_setup',selected)
        with patch.object(VALIDATION,'_differential'):
            result=f.validate(runtime_failure=AssertionError('no reusable runtime needed'))
        self.assertEqual(result['mode'],'affected-ci');self.assertEqual(result['executed_suites'],['alpha'])
        self.assertEqual(f.executed(),['alpha']);self.assertEqual(result['reused_suites'],[])

    def test_missing_changed_or_expired_proof_after_no_setup_never_executes_unprepared_fallback(self):
        for shape in ('missing','digest','tree','expired'):
            f=self.f
            if shape!='missing':self.evidence['original_proof']['artifact_digest']='sha256:'+'1'*64;self.evidence['candidate_inputs']=deepcopy(f.tree)
            self.prepare()
            def change(*args):
                if shape=='missing':f.gate.native_exact_tree_parent_evidence.side_effect=lambda *a:None
                elif shape=='digest':self.evidence['original_proof']['artifact_digest']='sha256:'+'0'*64
                elif shape=='tree':self.evidence['candidate_inputs']['libraries/alpha.cpp']['sha']='0'*40
                else:self.evidence['expires_at']='2020-01-01T00:00:00Z'
            with self.subTest(shape=shape),patch.object(VALIDATION,'_differential',side_effect=change), \
                    self.assertRaises(VALIDATION.ValidationError):
                f.validate(ci_execute_override=lambda *a,**k:(_ for _ in ()).throw(AssertionError('no unprepared CI')))
            self.assertEqual(f.executed(),[])
            f.gate.native_exact_tree_parent_evidence.side_effect=lambda *a:deepcopy(self.evidence)

    def test_changed_command_coverage_never_uses_parent_report_as_generic_E(self):
        f=self.f;self.evidence['requested_suites']=['beta']
        with self.assertRaises(VALIDATION.ValidationError):self.prepare()
        self.evidence['requested_suites']=['alpha'];self.evidence['reusable']=True
        with self.assertRaises(VALIDATION.ValidationError):self.prepare()

    def rosters(self, original, requested):
        f=self.f
        full=json.loads((VALIDATION.ROOT/'.github/ci37-runtime.json').read_bytes())['suites']
        command=deepcopy(f.registry['suites']['alpha'])
        f.registry['suites']={name:deepcopy(command)for name in full}
        self.selection={'schema':1,'lane':'affected-ci','requested_mode':'reuse','full_host':False,
            'suites':list(requested),'external_package_set':[],'selection':'fixture-fixed-selection'}
        f.args.expected_selection=self.selection['selection']
        self.evidence.update(requested_suites=list(requested))
        self.evidence['original_report'].update(requested_mode='fallback',executed_suites=list(original))
        if original!=full or requested!=full:
            self.evidence.update(kind='original-sync-identical-android-ci-subset-v1',original_suites=list(original),
                covered_suites=[n for n in requested if n in original])
        return [n for n in requested if n in original],[n for n in requested if n not in original]

    def test_finite32_37_combinations_execute_only_genuine_complement_with_no_E(self):
        full=json.loads((VALIDATION.ROOT/'.github/ci37-runtime.json').read_bytes())['suites']
        partial=[n for n in full if n not in {'producer-proof','python-test-runner','release-bundle',
            'project-coverage','native-registration'}]
        for original,requested in ((full,full),(partial,full),(partial,partial),(full,partial)):
            case=ExactTreeParentConsumerTests();case.setUp();self.addCleanup(case.doCleanups)
            f=case.f;covered,remaining=case.rosters(original,requested)
            with self.subTest(original=len(original),requested=len(requested)), \
                    patch.object(VALIDATION,'_ci_selection',return_value=deepcopy(case.selection)), \
                    patch.object(inputs,'plan_reuse',side_effect=AssertionError('no environment/E reuse')):
                selected=f.ci_prepare()
                self.assertEqual(selected.get('consumer_setup')=='none',not remaining)
                f.args.expected_native_setup=selected.get('native_setup','')
                result=f.validate(runtime_failure=AssertionError('no reusable environment'))
                self.assertEqual(result['reused_suites'],covered);self.assertEqual(result['executed_suites'],remaining)
                self.assertEqual(f.executed(),['alpha']*len(remaining))
                self.assertEqual(result['mode'],'native-exact-tree-parent')
                self.assertFalse(result['qualification']);self.assertFalse(result['reusable'])
                self.assertEqual(result['parent_evidence']['original_report'],case.evidence['original_report'])
                import xml.etree.ElementTree as ET
                self.assertEqual([c.get('name')for c in ET.parse(f.args.junit).iter('testcase')],remaining or ['sync-differential'])
                sidecar=Path(str(f.args.receipt)+'.ci-execution.json')
                self.assertEqual(sidecar.exists(),bool(remaining))
                if remaining:
                    self.assertEqual(json.loads(sidecar.read_bytes())['requested_suites'],remaining)
                    self.assertEqual(result['execution']['requested_suites'],remaining)

    def test_partial_cannot_claim_zero_setup_failed_complement_or_changed_final_coverage(self):
        full=json.loads((VALIDATION.ROOT/'.github/ci37-runtime.json').read_bytes())['suites']
        partial=[n for n in full if n not in {'producer-proof','python-test-runner','release-bundle',
            'project-coverage','native-registration'}]
        self.rosters(partial,full);f=self.f
        with patch.object(VALIDATION,'_ci_selection',return_value=deepcopy(self.selection)):
            f.args.expected_native_setup='sha256:'+'0'*64
            with self.assertRaises(VALIDATION.ValidationError):f.validate()
            self.assertEqual(f.executed(),[])
            f.args.expected_native_setup=''
            with self.assertRaises(VALIDATION.ValidationError):
                f.validate(extra_environment={'FIXTURE_FAIL_ALPHA':'1'})
            self.assertFalse(f.args.receipt.exists())
            self.assertEqual(f.executed(),['alpha']*5)
            f.log.unlink()
            def drift(*a,**k):self.evidence['covered_suites']=list(full)
            with patch.object(VALIDATION,'_differential',side_effect=drift), \
                    self.assertRaises(VALIDATION.ValidationError):f.validate()
            self.assertEqual(f.executed(),[])
            self.assertFalse(f.args.receipt.exists())



class StandaloneNativeOwnersTests(unittest.TestCase):
    """Real four-command native verifier; every network read is a fixed fake."""
    def setUp(self):
        self.gate = VALIDATION._gate()
        self.prefix = 'repos/noah-l-frank/overte'
        self.repo = {'id':1319052603,'full_name':'noah-l-frank/overte','default_branch':'main'}
        self.b,self.h,self.m,self.d,self.t = [c*40 for c in '12345']
        self.now = datetime(2026,10,20,20,10,tzinfo=timezone.utc)
        self.registry = inputs.load_registry(VALIDATION.ROOT/'.github/test-suites.json')
        self.names = json.loads((VALIDATION.ROOT/'.github/ci37-runtime.json').read_bytes())['suites']
        self.selection = {'lane':'affected-ci','requested_mode':'fallback','full_host':False,
            'suites':self.names,'external_package_set':[],'standalone_ci_schedule':True,
            'candidate':self.m,'tree':self.t}
        self.request = SimpleNamespace(repository=self.repo['full_name'],repository_id=self.repo['id'],number=42,
            base='apple-main',base_sha=self.b,head='reconcile/apple/example',head_sha=self.h,
            merge_sha=self.m,parent='main',parent_sha=self.d,head_repository_id=self.repo['id'],repair_paths=())
        self.tree = {'.github/workflows/'+name:{'mode':'100644','type':'blob','sha':sha}
            for name,sha in (('repository-checks.yml','22fe0d6d39d120f800099136d7d1ab5280d80b41'),
                ('documentation-checks.yml','a86e36287a315eed7bbadf366f923966a04bd806'))}
        for path in ('tools/test-evidence/validate-sync.py','tools/sync-test-reuse/gate.py',
                     '.github/test-suites.json','.github/ci37-runtime.json'):
            raw=(VALIDATION.ROOT/path).read_bytes()
            self.tree[path]={'mode':'100644','type':'blob','sha':__import__('hashlib').sha1(
                b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()}
        self.pr = {'number':42,'state':'open','merged':False,'mergeable':True,'merge_commit_sha':self.m,
            'base':{'ref':self.request.base,'sha':self.b,'repo':self.repo},
            'head':{'ref':self.request.head,'sha':self.h,'repo':self.repo}}
        association = [{'number':42,'base':{'sha':self.b},'head':{'sha':self.h}}]
        self.run = {'id':901,'workflow_id':900,'check_suite_id':902,'run_attempt':1,
            'path':'.github/workflows/repository-checks.yml','event':'pull_request','head_sha':self.h,
            'head_branch':self.request.head,'display_title':'Overte native ordinary qualification v2',
            'status':'completed','conclusion':'success','repository':self.repo,'head_repository':self.repo,
            'pull_requests':association,'run_started_at':'2026-10-20T20:00:00Z','updated_at':'2026-10-20T20:05:00Z',
            'referenced_workflows':[{'path':self.repo['full_name']+'/.github/workflows/documentation-checks.yml@'+self.m,
                'sha':self.m,'ref':'refs/pull/42/merge'}]}
        self.docs = {self.prefix:self.repo,
            self.prefix+'/branches/main':{'name':'main','protected':True,'commit':{'sha':self.d}},
            self.prefix+'/branches/apple-main':{'name':'apple-main','protected':True,'commit':{'sha':self.b}},
            self.prefix+'/actions/workflows/sync-validation.yml':{'id':350930895,'path':'.github/workflows/sync-validation.yml','name':'Sync validation','state':'active'},
            self.prefix+'/pulls/42':self.pr,
            self.prefix+'/git/ref/heads/apple-main':{'object':{'type':'commit','sha':self.b}},
            self.prefix+'/git/ref/heads/main':{'object':{'type':'commit','sha':self.d}},
            self.prefix+'/git/commits/'+self.m:{'sha':self.m,'tree':{'sha':self.t},'parents':[{'sha':self.b},{'sha':self.h}]},
            self.prefix+'/actions/workflows/repository-checks.yml':{'id':900,'path':'.github/workflows/repository-checks.yml','state':'active'},
            self.prefix+'/actions/runs/901':deepcopy(self.run),
            self.prefix+'/actions/runs/901/attempts/1':deepcopy(self.run),
            self.prefix+'/actions/workflows/900/runs?head_sha='+self.h+'&per_page=100':{'total_count':1,'workflow_runs':[deepcopy(self.run)]},
            self.prefix+'/check-suites/902':{'id':902,'head_sha':self.h,'app':{'id':15368},
                'repository':self.repo,'pull_requests':deepcopy(association)}}
        self.jobs = []
        steps = {'documentation / documentation':['Verify documentation checker behavior',
            'Check every workspace document and incoming link','Verify policy-derived branch and suite displays'],
            'workflow-contracts':['Verify remaining workflow contracts']}
        for index,name in enumerate(('project','native','android','Select required repository checks','repository-checks',*steps)):
            identifier=910+index;result='skipped' if name in ('project','native','android')else'success'
            job={'id':identifier,'name':name,'run_id':901,'run_attempt':1,'head_sha':self.h,
                'status':'completed','conclusion':result,'started_at':'2026-10-20T20:01:00Z','completed_at':'2026-10-20T20:04:00Z',
                'check_run_url':'https://api.github.com/'+self.prefix+'/check-runs/'+str(identifier),
                'steps':[{'name':step,'status':'completed','conclusion':'success',
                    'started_at':'2026-10-20T20:02:00Z','completed_at':'2026-10-20T20:03:00Z'}for step in steps.get(name,[])]}
            self.jobs.append(job)
            self.docs[self.prefix+'/check-runs/'+str(identifier)]={'id':identifier,'name':name,'head_sha':self.h,
                'status':'completed','conclusion':result,'app':{'id':15368},'check_suite':{'id':902},
                'pull_requests':deepcopy(association),
                'details_url':'https://github.com/'+self.repo['full_name']+'/actions/runs/901/job/'+str(identifier)}
        self.docs[self.prefix+'/actions/runs/901/attempts/1/jobs?per_page=100']={'total_count':len(self.jobs),'jobs':self.jobs}
        for revision in (self.b,self.d):
            self.docs[self.prefix+'/git/commits/'+revision]={'sha':revision,'tree':{'sha':self.t},'parents':[]}
        self.docs[self.prefix+'/git/trees/'+self.t+'?recursive=1']={'sha':self.t,'truncated':False,
            'tree':[{'path':p,**v}for p,v in self.tree.items()]}
        self.calls=[]

    def android_owners(self):
        self.request.base='android-main';self.pr['base']['ref']='android-main'
        self.docs[self.prefix+'/branches/android-main']={'name':'android-main','protected':True,'commit':{'sha':self.b}}
        self.docs[self.prefix+'/git/ref/heads/android-main']={'object':{'type':'commit','sha':self.b}}
        self.jobs[:]=[job for job in self.jobs if job['name']!='android']
        path='.github/workflows/android-required.yml';raw=(VALIDATION.ROOT/path).read_bytes()
        self.tree[path]={'mode':'100644','type':'blob','sha':__import__('hashlib').sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()}
        for run in (self.run,self.docs[self.prefix+'/actions/runs/901'],self.docs[self.prefix+'/actions/runs/901/attempts/1'],
                self.docs[self.prefix+'/actions/workflows/900/runs?head_sha='+self.h+'&per_page=100']['workflow_runs'][0]):
            run['referenced_workflows'].append({'path':self.repo['full_name']+'/'+path+'@'+self.m,
                'sha':self.m,'ref':'refs/pull/42/merge'})
        steps=('Independently select the complete Android union',
            'Execute and verify the independently selected Android owners once',
            'Recompute candidate union and require complete successful ownership')
        for index,(role,step)in enumerate(zip(('route','execute','verify'),steps)):
            identifier=930+index
            start,end=(('20:01:00','20:02:00'),('20:02:00','20:03:00'),('20:03:00','20:04:00'))[index]
            stamp=lambda value:'2026-10-20T'+value+'Z'
            job={'id':identifier,'name':'android / '+role,'run_id':901,'run_attempt':1,'head_sha':self.h,
                'status':'completed','conclusion':'success','started_at':stamp(start),'completed_at':stamp(end),
                'check_run_url':'https://api.github.com/'+self.prefix+'/check-runs/'+str(identifier),
                'steps':[{'name':step,'status':'completed','conclusion':'success',
                    'started_at':stamp(start),'completed_at':stamp(end)}]}
            self.jobs.append(job)
            self.docs[self.prefix+'/check-runs/'+str(identifier)]={'id':identifier,'name':job['name'],'head_sha':self.h,
                'status':'completed','conclusion':'success','app':{'id':15368},'check_suite':{'id':902},
                'started_at':job['started_at'],'completed_at':job['completed_at'],
                'pull_requests':deepcopy(self.run['pull_requests']),
                'details_url':'https://github.com/'+self.repo['full_name']+'/actions/runs/901/job/'+str(identifier)}
        self.docs[self.prefix+'/actions/runs/901/attempts/1/jobs?per_page=100']['total_count']=len(self.jobs)

    def verify(self, *, mutate=None, normal_parent=None, controller=None, observation_clock=None):
        owner=self
        class API:
            def native_producer_api(self, actual_controller):
                owner.assertIs(actual_controller,controller)
                return self
            def json(self,endpoint,**kwargs):
                owner.calls.append(endpoint)
                if kwargs.get('method','GET')!='GET':raise AssertionError('no mutation')
                value=deepcopy(owner.docs[endpoint])
                return mutate(endpoint,value)if mutate else value
        with patch.object(self.gate,'_dispatch_checkout_source',return_value=self.d), \
                patch.object(self.gate,'_callback_sync_recipe',return_value=True), \
                patch.object(self.gate,'_native_parent_controller',return_value=controller or SimpleNamespace()), \
                patch.object(inputs,'full_tree',return_value=deepcopy(self.tree)):
            self.docs[self.prefix+'/git/trees/'+self.t+'?recursive=1']['tree']=[{'path':p,**v}for p,v in self.tree.items()]
            return VALIDATION.verify_standalone_ci_owners(API(),self.gate,self.request,self.registry,self.selection,
                now=self.now,normal_parent=normal_parent,observation_clock=observation_clock)

    def test_real_native_four_command_source_app_and_complete_inventories_without_E(self):
        proof=self.verify()
        self.assertIsInstance(proof,VALIDATION.NativeStandaloneCIProof)
        self.assertEqual(proof['suites'],[n for n in self.names if n in VALIDATION.STANDALONE_CI_COMMANDS])
        self.assertEqual(proof['candidate'],self.m)
        self.assertIs(proof['qualification'],False);self.assertIs(proof['reusable'],False)
        self.assertNotIn('environment',proof);self.assertNotIn('fingerprint',str(proof))
        self.assertEqual(self.calls.count(self.prefix+'/actions/runs/901/attempts/1/jobs?per_page=100'),2)
        self.assertEqual(self.calls.count(self.prefix+'/git/commits/'+self.m),1)
        self.assertEqual(self.calls.count(self.prefix+'/git/trees/'+self.t+'?recursive=1'),1)
        self.assertEqual(self.calls.count(self.prefix+'/check-runs/910'),0,'unrelated skipped jobs grant no command coverage')
        self.assertLessEqual(len(self.calls),50)

    def successor(self):
        rows=self.gate.package_checks.workflow_generations()[:28]
        self.assertEqual(rows[-1]['name'],'protected-producer-optional-leaf-common-v1')
        new=deepcopy(rows[-1]);new['name']=self.gate.REPOSITORY_PARENT_GENERATION
        new['workflows'][self.gate._REPOSITORY_CALLER]={'mode':'100644','type':'blob',
            'sha':self.gate.REPOSITORY_PARENT_RECIPE}
        self.rows=[*rows,new]
        self.tree.update(deepcopy(new['workflows']))
        self.tree[self.gate.REPOSITORY_PARENT_TEMPLATE]=deepcopy(new['workflows'][self.gate._REPOSITORY_CALLER])
        names=('pr-metadata-context','native-tests','project-tests','android-required','documentation-checks','workflow-security')
        for name in names:
            path='.github/workflows/'+name+'.yml';raw=(VALIDATION.ROOT/path).read_bytes()
            self.tree[path]={'mode':'100644','type':'blob','sha':__import__('hashlib').sha1(
                b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()}
        before=deepcopy(self.tree);before.update(deepcopy(rows[-1]['workflows']))
        bt='9'*40;self.docs[self.prefix+'/git/commits/'+self.b]['tree']['sha']=bt
        self.docs[self.prefix+'/git/trees/'+bt+'?recursive=1']={'sha':bt,'truncated':False,
            'tree':[{'path':p,**v}for p,v in before.items()]}
        for run in (self.run,self.docs[self.prefix+'/actions/runs/901'],self.docs[self.prefix+'/actions/runs/901/attempts/1'],
                self.docs[self.prefix+'/actions/workflows/900/runs?head_sha='+self.h+'&per_page=100']['workflow_runs'][0]):
            run['referenced_workflows']=[{'path':self.repo['full_name']+'/.github/workflows/'+name+'.yml@'+self.m,
                'sha':self.m,'ref':'refs/pull/42/merge'}for name in names]

    def test_first_successor_Android_native_four_uses_actual_new_M_and_preserves_old_B(self):
        self.android_owners();self.successor()
        native=SimpleNamespace(plan=lambda *a,**k:{'mode':'skip'})
        android=SimpleNamespace(activated=lambda *a:False,has_staged_caller=lambda *a:False)
        bt=self.docs[self.prefix+'/git/trees/'+'9'*40+'?recursive=1']['tree']
        before={row['path']:{k:row[k]for k in ('mode','type','sha')}for row in bt}
        plan={'host_mode':'delegated-sync','package_set':[],'paths':['tools/sync-test-reuse/gate.py'],'regular':True}
        with patch.object(self.gate.package_checks,'workflow_generations',return_value=self.rows), \
                patch.object(VALIDATION,'_gate',return_value=self.gate), \
                patch.object(VALIDATION,'_trusted_module',side_effect=lambda name,path:
                    native if str(path).endswith('native-tests/check.py')else android):
            self.assertTrue(VALIDATION._standalone_ci_schedule(VALIDATION.ROOT,{},self.request,plan,
                base_tree=before,candidate_tree=self.tree,trusted_tree=self.tree,suite_names=self.names))
            proof=self.verify()
        self.assertIsInstance(proof,VALIDATION.NativeStandaloneCIProof)
        self.assertEqual(len(proof['suites']),4)
        self.assertEqual(proof['candidate'],self.m)
        self.assertIs(proof['qualification'],False);self.assertIs(proof['reusable'],False)
        self.assertEqual(self.docs[self.prefix+'/git/commits/'+self.b]['tree']['sha'],'9'*40)
        self.assertEqual(self.rows[-2]['workflows'][self.gate._REPOSITORY_CALLER],self.gate._REPOSITORY_PREVIOUS)

    def test_successor_native_mixed_ref_or_missing_complete_source_never_grants_four(self):
        self.successor()
        for field,value in (('sha','8'*40),('path','noah-l-frank/overte/.github/workflows/unknown.yml@'+self.m)):
            def wrong(endpoint,row,field=field,value=value):
                if endpoint.endswith('/actions/runs/901'):row['referenced_workflows'][0][field]=value
                return row
            with patch.object(self.gate.package_checks,'workflow_generations',return_value=self.rows), \
                    self.subTest(field=field),self.assertRaises(VALIDATION.ValidationError):
                self.verify(mutate=wrong)
        def missing(endpoint,row):
            if endpoint.endswith('/actions/runs/901'):row['referenced_workflows'].pop()
            return row
        with patch.object(self.gate.package_checks,'workflow_generations',return_value=self.rows), \
                self.assertRaises(VALIDATION.ValidationError):self.verify(mutate=missing)

    def documentation_three(self):
        self.selection['suites']=[n for n in self.names if n not in {'producer-proof','python-test-runner',
            'release-bundle','project-coverage','native-registration'}]
        # Actual immutable B/M delta is an implementation-only CI path. No
        # native workflow-contract job ran for the protected security=false route.
        before=deepcopy(self.tree);before['tools/sync-test-reuse/gate.py']['sha']='8'*40
        before_tree='9'*40
        self.docs[self.prefix+'/git/commits/'+self.b]['tree']['sha']=before_tree
        self.docs[self.prefix+'/git/trees/'+before_tree+'?recursive=1']={'sha':before_tree,'truncated':False,
            'tree':[{'path':p,**v}for p,v in before.items()]}
        job=next(j for j in self.jobs if j['name']=='workflow-contracts')
        job.update(conclusion='skipped',steps=[],started_at=None,completed_at=None)
        self.docs[self.prefix+'/check-runs/'+str(job['id'])]['conclusion']='skipped'
        return before_tree

    def test_actual_CI32_security_false_reuses_only_documentation_three_not_skipped_workflow(self):
        self.documentation_three();proof=self.verify()
        expected=[n for n in self.selection['suites']if n in VALIDATION.STANDALONE_CI_COMMANDS and n!='workflow-contracts']
        self.assertEqual(len(expected),3);self.assertEqual(proof['suites'],expected)
        self.assertEqual(proof['native']['repository_route'],{'mode':'delegated-sync','security':'false'})
        self.assertEqual(set(proof['native']['selected_jobs']),{'documentation / documentation'})
        self.assertNotIn('workflow-contracts',proof['native']['checks'])
        self.assertEqual(proof['native']['skipped_workflow_contracts']['job']['conclusion'],'skipped')
        self.assertIsNone(proof['native']['skipped_workflow_contracts']['job']['completed_at'])
        self.assertFalse(proof['qualification']);self.assertFalse(proof['reusable'])

    def test_CI32_requires_real_security_false_unique_skipped_workflow_and_unchanged_books(self):
        before_tree=self.documentation_three()
        for shape in ('security','success','missing','duplicate','foreign-check','closing-base'):
            reads=0
            def change(path,value):
                nonlocal reads
                if shape=='security'and path.endswith('/git/trees/'+before_tree+'?recursive=1'):
                    value['tree'].append({'path':'.github/workflows/unreviewed.yml','mode':'100644','type':'blob','sha':'7'*40})
                if path.endswith('/jobs?per_page=100'):
                    row=next(j for j in value['jobs']if j['name']=='workflow-contracts')
                    if shape=='success':row['conclusion']='success'
                    elif shape=='missing':value['jobs'].remove(row);value['total_count']-=1
                    elif shape=='duplicate':
                        value['jobs'].append({**row,'id':999});value['total_count']+=1
                if shape=='foreign-check'and path.endswith('/check-runs/916'):value['app']['id']=1
                if shape=='closing-base'and path.endswith('/branches/apple-main'):
                    reads+=1
                    if reads>1:value['commit']['sha']='a'*40
                return value
            with self.subTest(shape=shape),self.assertRaises((VALIDATION.ValidationError,self.gate.GateError)):
                self.verify(mutate=change)

    def test_completed_independent_Android_three_job_owner_still_supplies_only_four_CI_commands(self):
        self.android_owners();proof=self.verify()
        self.assertEqual(len(proof['suites']),4);self.assertEqual(set(proof['commands']),set(VALIDATION.STANDALONE_CI_COMMANDS))
        self.assertEqual(set(proof['native']['selected_jobs']),{'documentation / documentation','workflow-contracts'})
        self.assertTrue({'android / route','android / execute','android / verify'}<=proof['native']['checks'].keys())
        self.assertIs(proof['qualification'],False);self.assertIs(proof['reusable'],False)
        self.assertNotIn('platform_results',proof);self.assertNotIn('environment',proof)

    def test_incomplete_failed_pending_or_foreign_Android_owner_cannot_supply_command_coverage(self):
        self.android_owners()
        for shape in ('missing','duplicate','unknown','mixed','failed','pending','attempt','head','app','step','step-failed','source','ordering'):
            def change(path,value):
                if path.endswith('/jobs?per_page=100'):
                    row=next(j for j in value['jobs']if j['name']=='android / execute')
                    if shape=='missing':value['jobs'].remove(row);value['total_count']-=1
                    elif shape in ('duplicate','mixed'):
                        extra=deepcopy(row);extra['id']=990
                        if shape=='mixed':extra.update(name='android',conclusion='skipped',steps=[])
                        value['jobs'].append(extra);value['total_count']+=1
                    elif shape=='unknown':row['name']='android / foreign'
                    elif shape=='failed':row['conclusion']='failure'
                    elif shape=='pending':row.update(status='in_progress',conclusion=None,completed_at=None)
                    elif shape=='attempt':row['run_attempt']=2
                    elif shape=='head':row['head_sha']='a'*40
                    elif shape=='step':row['steps'][0]['name']='Run a different owner'
                    elif shape=='step-failed':row['steps'][0]['conclusion']='failure'
                    elif shape=='ordering':row['started_at']='2026-10-20T20:00:30Z'
                if shape=='app'and path.endswith('/check-runs/931'):value['app']['id']=1
                if shape=='source'and path.endswith('/actions/runs/901'):value['referenced_workflows'][-1]['sha']='a'*40
                return value
            with self.subTest(shape=shape),self.assertRaises((VALIDATION.ValidationError,self.gate.GateError)):
                self.verify(mutate=change)

    def test_wrong_attempt_source_recipe_App_steps_incomplete_inventory_and_failure_are_denied(self):
        variants = [
            (lambda path,v:v.update(run_attempt=2) if path.endswith('/attempts/1')else None),
            (lambda path,v:v.update(head_sha='a'*40) if path.endswith('/actions/runs/901')else None),
            (lambda path,v:v.update(conclusion='failure') if path.endswith('/actions/runs/901')else None),
            (lambda path,v:v.update(total_count=v['total_count']+1) if path.endswith('/jobs?per_page=100')else None),
            (lambda path,v:v['app'].update(id=1) if '/check-runs/'in path else None),
            (lambda path,v:v['referenced_workflows'][0].update(sha='a'*40) if path.endswith('/actions/runs/901')else None),
            (lambda path,v:v['jobs'][-1]['steps'][0].update(name='unreviewed command') if path.endswith('/jobs?per_page=100')else None),
            (lambda path,v:v.update(state='disabled_manually') if path.endswith('/workflows/repository-checks.yml')else None),
            (lambda path,v:v['commit'].update(sha='a'*40) if path.endswith('/branches/main')else None),
        ]
        for index,variant in enumerate(variants):
            with self.subTest(index=index),self.assertRaises((VALIDATION.ValidationError,self.gate.GateError)):
                self.verify(mutate=lambda p,v:(variant(p,v),v)[1])
        for path in self.tree:
            before=deepcopy(self.tree);self.tree[path]['mode']='120000'
            with self.subTest(recipe=path),self.assertRaises(VALIDATION.ValidationError):self.verify()
            self.tree=before

    def test_pending_never_supplies_coverage_and_whole_same_endpoint_closing_drift_blocks(self):
        def pending(path,value):
            if path.endswith('/actions/runs/901'):value.update(status='in_progress',conclusion=None)
            return value
        with self.assertRaises(VALIDATION.StandalonePending):self.verify(mutate=pending)
        def registering(path,value):
            if '/actions/runs/901'in path or '/runs?head_sha='in path:
                rows=value.get('workflow_runs',[value])
                for row in rows:row.update(status='queued',conclusion=None,run_started_at=None,referenced_workflows=None,pull_requests=[])
            return value
        with self.assertRaises(VALIDATION.StandalonePending):self.verify(mutate=registering)
        def absent(path,value):
            if '/runs?head_sha='in path:value.update(total_count=0,workflow_runs=[])
            return value
        with self.assertRaises(VALIDATION.StandalonePending):self.verify(mutate=absent)
        def ambiguous(path,value):
            if '/runs?head_sha='in path:
                another=deepcopy(value['workflow_runs'][0]);another['id']=903
                value['workflow_runs'].append(another);value['total_count']=2
            return value
        with self.assertRaises(VALIDATION.ValidationError)as failed:self.verify(mutate=ambiguous)
        self.assertNotIsInstance(failed.exception,VALIDATION.StandalonePending)
        def foreign_pending(path,value):
            value=pending(path,value)
            if path.endswith('/actions/runs/901'):value['head_sha']='a'*40
            return value
        with self.assertRaises(VALIDATION.ValidationError)as failed:self.verify(mutate=foreign_pending)
        self.assertNotIsInstance(failed.exception,VALIDATION.StandalonePending)
        reads=[]
        def drift(path,value):
            if path.endswith('/actions/runs/901'):
                reads.append(path)
                if len(reads)==2:value['updated_at']='2026-10-20T20:06:00Z'
            return value
        with self.assertRaises(VALIDATION.ValidationError):self.verify(mutate=drift)

    def test_only_exact_closed_normal_allows_cleared_associations_without_rebinding_original_M(self):
        opened=dict(self.verify());normal='a'*40
        self.pr.update(state='closed',merged=True,merge_commit_sha=normal)
        self.pr['base']['sha']=normal
        self.docs[self.prefix+'/git/ref/heads/apple-main']['object']['sha']=normal
        self.docs[self.prefix+'/branches/apple-main']['commit']['sha']=normal
        self.docs[self.prefix+'/git/commits/'+normal]={'sha':normal,'tree':{'sha':self.t},'parents':[{'sha':self.b},{'sha':self.h}]}
        for value in (self.docs[self.prefix+'/actions/runs/901'],self.docs[self.prefix+'/actions/runs/901/attempts/1'],
                self.docs[self.prefix+'/actions/workflows/900/runs?head_sha='+self.h+'&per_page=100']['workflow_runs'][0],
                self.docs[self.prefix+'/check-suites/902'],
                *[v for k,v in self.docs.items()if '/check-runs/'in k]):
            value['pull_requests']=[]
        closed=self.verify(normal_parent=normal)
        VALIDATION.verify_standalone_ci_provenance(opened,closed,self.request,normal_parent=normal)
        empty=deepcopy(opened);empty['native']['check_suite']['pull_requests']=[]
        for check in empty['native']['checks'].values():check['pull_requests']=[]
        VALIDATION.verify_standalone_ci_provenance(empty,closed,self.request,normal_parent=normal)
        forged=deepcopy(opened);forged['native']['check_suite']['pull_requests'][0]['number']=999
        with self.assertRaises(VALIDATION.ValidationError):
            VALIDATION.verify_standalone_ci_provenance(forged,closed,self.request,normal_parent=normal)
        self.assertEqual(closed['candidate'],self.m)
        with self.assertRaises(VALIDATION.ValidationError):self.verify()
        self.docs[self.prefix+'/git/commits/'+normal]['parents'].reverse()
        with self.assertRaises(VALIDATION.ValidationError):self.verify(normal_parent=normal)

    def test_closed_CI32_retains_exact_skipped_check_when_original_PR_association_clears(self):
        self.documentation_three();opened=dict(self.verify());normal='a'*40
        self.pr.update(state='closed',merged=True,merge_commit_sha=normal);self.pr['base']['sha']=normal
        self.docs[self.prefix+'/git/ref/heads/apple-main']['object']['sha']=normal
        self.docs[self.prefix+'/branches/apple-main']['commit']['sha']=normal
        self.docs[self.prefix+'/git/commits/'+normal]={'sha':normal,'tree':{'sha':self.t},
            'parents':[{'sha':self.b},{'sha':self.h}]}
        for value in (self.docs[self.prefix+'/actions/runs/901'],self.docs[self.prefix+'/actions/runs/901/attempts/1'],
                self.docs[self.prefix+'/actions/workflows/900/runs?head_sha='+self.h+'&per_page=100']['workflow_runs'][0],
                self.docs[self.prefix+'/check-suites/902'],*[v for k,v in self.docs.items()if '/check-runs/'in k]):
            value['pull_requests']=[]
        closed=self.verify(normal_parent=normal)
        VALIDATION.verify_standalone_ci_provenance(opened,closed,self.request,normal_parent=normal)
        self.assertEqual(closed['native']['skipped_workflow_contracts']['check']['pull_requests'],[])
        self.assertEqual(closed['candidate'],self.m)
        with self.assertRaises(VALIDATION.ValidationError):
            VALIDATION.verify_standalone_ci_provenance(opened,closed,self.request)
        for shape in ('number','base','head'):
            forged=deepcopy(opened);row=forged['native']['skipped_workflow_contracts']['check']['pull_requests'][0]
            if shape=='number':row['number']=999
            else:row[shape]['sha']='f'*40
            with self.subTest(shape=shape),self.assertRaises(VALIDATION.ValidationError):
                VALIDATION.verify_standalone_ci_provenance(forged,closed,self.request,normal_parent=normal)

    def test_only_pending_proof_retries_are_bounded(self):
        proof=VALIDATION.NativeStandaloneCIProof({'fixture':'completed native facts'})
        with patch.object(VALIDATION,'verify_standalone_ci_owners',side_effect=[VALIDATION.StandalonePending('pending'),proof])as verify, \
                patch.object(VALIDATION.time,'monotonic',return_value=0),patch.object(VALIDATION.time,'sleep')as sleep:
            self.assertIs(VALIDATION._native_standalone_ci_owners(None,None,None,None,None),proof)
            self.assertEqual(verify.call_count,2);sleep.assert_called_once_with(5)
        with patch.object(VALIDATION,'verify_standalone_ci_owners',side_effect=VALIDATION.StandalonePending('pending')), \
                patch.object(VALIDATION.time,'monotonic',side_effect=[0,901]),patch.object(VALIDATION.time,'sleep')as sleep, \
                self.assertRaises(VALIDATION.ValidationError):
            VALIDATION._native_standalone_ci_owners(None,None,None,None,None)
        sleep.assert_not_called()
        with patch.object(VALIDATION,'verify_standalone_ci_owners',side_effect=VALIDATION.ValidationError('failed'))as verify, \
                patch.object(VALIDATION.time,'sleep')as sleep,self.assertRaises(VALIDATION.ValidationError):
            VALIDATION._native_standalone_ci_owners(None,None,None,None,None)
        verify.assert_called_once();sleep.assert_not_called()

    def test_metadata_competitor_receives_fresh_observation_clock_without_future_time_waiver(self):
        later=self.now+timedelta(seconds=2)
        metadata=deepcopy(self.run);metadata.update(id=903,display_title='Overte native metadata nonproducer v2',
            updated_at=later.isoformat().replace('+00:00','Z'))
        listed=self.docs[self.prefix+'/actions/workflows/900/runs?head_sha='+self.h+'&per_page=100']
        listed['workflow_runs'].append(metadata);listed['total_count']=2
        def intent(row,binding,policy,**kwargs):
            self.assertEqual(kwargs['now'],self.now)
            self.assertIs(kwargs['observation_clock'],clock)
            observed=kwargs['observation_clock']()
            if self.gate.parse_time(row['updated_at'],'fixture metadata update')>observed:
                raise VALIDATION.ValidationError('metadata update exceeds fresh observation')
            return {'fixture':'authenticated neverproducer'}
        adapter=SimpleNamespace(_native_metadata_intent=Mock(side_effect=intent))
        controller=SimpleNamespace(A=SimpleNamespace(Adapter=Mock(return_value=adapter),MetadataPolicy=Mock()),
            producer=SimpleNamespace(metadata_generations=Mock(return_value=({},{})),_host_policy=Mock()))
        clock=lambda:later
        proof=self.verify(controller=controller,observation_clock=clock)
        self.assertIsInstance(proof,VALIDATION.NativeStandaloneCIProof)
        self.assertEqual(adapter._native_metadata_intent.call_count,2)
        clock=lambda:self.now+timedelta(seconds=1)
        with self.assertRaises(VALIDATION.ValidationError):
            self.verify(controller=controller,observation_clock=clock)


class StandaloneNativeConsumerTests(unittest.TestCase):
    def setUp(self):
        self.f=IsolatedConsumerTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        f=self.f;f.ci_fixture()
        self.names=json.loads((VALIDATION.ROOT/'.github/ci37-runtime.json').read_bytes())['suites']
        original=deepcopy(f.registry['suites']['alpha']);f.registry['suites']={n:deepcopy(original)for n in self.names}
        for n,c in VALIDATION.STANDALONE_CI_COMMANDS.items():f.registry['suites'][n]['command']=c
        self.selection={'schema':1,'lane':'affected-ci','requested_mode':'fallback','full_host':False,
            'suites':self.names,'external_package_set':[],'selection':'fixture-fixed-selection',
            'standalone_ci_schedule':True}
        f.args.expected_selection=self.selection['selection']
        self.proof=VALIDATION.NativeStandaloneCIProof({'kind':'same-pr-native-standalone-ci-commands-v1',
            'qualification':False,'reusable':False,'candidate':f.commit,'tree':f.tree_sha,
            'suites':[n for n in self.names if n in VALIDATION.STANDALONE_CI_COMMANDS]})
        self.required=[n for n in self.names if n not in self.proof['suites']]
        tree={'.github/workflows/'+name+'.yml':{'mode':'100644','type':'blob','sha':'a'*40}
            for name in ('pr-metadata-context','native-tests','project-tests','android-required','workflow-security')}
        tree.update({'.github/workflows/repository-checks.yml':{'mode':'100644','type':'blob','sha':'22fe0d6d39d120f800099136d7d1ab5280d80b41'},
            '.github/workflows/documentation-checks.yml':{'mode':'100644','type':'blob','sha':'a86e36287a315eed7bbadf366f923966a04bd806'},
            '.github/test-suites.json':{'mode':'100644','type':'blob','sha':'b'*40}})
        self.schedule_inputs={key:deepcopy(tree)for key in ('base_tree','candidate_tree','trusted_tree')}

    def run_case(self, *, opening=None, closing=None, reuse=None, probe=None):
        f=self.f
        observations=0
        def observe(*args,**kwargs):
            nonlocal observations
            observations+=1
            read=probe if observations==1 else closing
            return deepcopy(self.proof)if read is None else read(*args,**kwargs)
        with patch.object(VALIDATION,'_ci_selection',return_value=deepcopy(self.selection)), \
                patch.object(VALIDATION,'_native_ci_reuse',return_value=reuse or(None,[],self.names)), \
                patch.object(VALIDATION,'_native_standalone_ci_owners',side_effect=opening or(lambda *a:deepcopy(self.proof)))as owner, \
                patch.object(VALIDATION,'verify_standalone_ci_owners',side_effect=observe), \
                patch.object(VALIDATION,'_recheck_native_ci'),patch.object(runtime,'capture_host_environment',side_effect=AssertionError('no E capture')):
            result=f.validate()
            return result,owner

    def test_actual33_commands_JUnit33_plus_native4_is_complete37_without_E_or_fake_cases(self):
        result,owner=self.run_case()
        self.assertEqual(result['mode'],'native-standalone-ci');self.assertEqual(result['executed_suites'],self.required)
        self.assertEqual(result['reused_suites'],self.proof['suites']);self.assertEqual(len(self.f.executed()),33)
        xml=__import__('xml.etree.ElementTree',fromlist=['parse']).parse(self.f.args.junit)
        self.assertEqual([c.get('name')for c in xml.iter('testcase')],self.required)
        self.assertIs(result['reusable'],False);self.assertIs(result['qualification'],False)
        self.assertEqual(result['execution']['requested_suites'],self.required)
        self.assertEqual(result['standalone_owner_evidence'],self.proof);owner.assert_not_called()

    def documentation_three(self):
        self.names=[n for n in self.names if n not in {'producer-proof','python-test-runner','release-bundle',
            'project-coverage','native-registration'}]
        self.selection['suites']=self.names
        self.proof['suites']=[n for n in self.proof['suites']if n!='workflow-contracts']
        self.required=[n for n in self.names if n not in self.proof['suites']]
        f=self.f
        (f.candidate/'tests/workflow-contract-test.py').write_bytes((f.candidate/'tests/alpha.py').read_bytes())
        f.ci_refresh();self.proof.update(candidate=f.commit,tree=f.tree_sha)

    def test_actual29_commands_plus_native_documentation3_covers_CI32_without_fake_workflow_case(self):
        self.documentation_three();result,owner=self.run_case()
        self.assertEqual(len(self.proof['suites']),3);self.assertEqual(len(self.required),29)
        self.assertIn('workflow-contracts',self.required)
        self.assertEqual(result['executed_suites'],self.required);self.assertEqual(result['reused_suites'],self.proof['suites'])
        self.assertEqual(self.f.executed(),['alpha']*29)
        import xml.etree.ElementTree as ET
        self.assertEqual([c.get('name')for c in ET.parse(self.f.args.junit).iter('testcase')],self.required)
        self.assertEqual(result['execution']['requested_suites'],self.required)
        self.assertFalse(result['qualification']);self.assertFalse(result['reusable']);owner.assert_not_called()

    def test_CI32_pending_documentation_failure_after29_never_produces_success_or_repeats_three(self):
        self.documentation_three()
        def pending(*a,**k):raise VALIDATION.StandalonePending('original documentation pending')
        def failed(*a):
            self.assertEqual(self.f.executed(),['alpha']*29)
            self.assertFalse(self.f.args.receipt.exists())
            raise VALIDATION.ValidationError('original documentation failed')
        with self.assertRaises(VALIDATION.ValidationError):self.run_case(probe=pending,opening=failed)
        self.assertFalse(self.f.args.receipt.exists());self.assertEqual(self.f.executed(),['alpha']*29)

    def test_completed_independent_Android_still_leaves_only33_CI_commands_to_execute(self):
        self.proof['native']={'jobs':[{'name':'android / '+role,'status':'completed','conclusion':'success'}
            for role in ('route','execute','verify')]}
        result,owner=self.run_case()
        self.assertEqual(result['executed_suites'],self.required);self.assertEqual(len(self.f.executed()),33)
        self.assertEqual(result['reused_suites'],self.proof['suites']);owner.assert_not_called()
        self.assertIs(result['qualification'],False);self.assertNotIn('platform_results',result)

    def test_known_failed_or_invalid_native_proof_blocks_before_any_candidate_command(self):
        for proof in (None,dict(self.proof),VALIDATION.NativeStandaloneCIProof(dict(self.proof,suites=[]))):
            with self.subTest(proof=proof),self.assertRaises(VALIDATION.ValidationError):
                self.run_case(probe=lambda *a,**k:proof)
            self.assertEqual(self.f.executed(),[]);self.assertFalse(self.f.args.receipt.exists())
        with self.assertRaises(VALIDATION.ValidationError):
            self.run_case(probe=lambda *a,**k:(_ for _ in()).throw(VALIDATION.ValidationError('failed')))
        self.assertEqual(self.f.executed(),[]);self.assertFalse(self.f.args.receipt.exists())

    def test_pending_native_Android_allows33_concurrently_but_no_report_until_completed_proof(self):
        self.proof['native']={'jobs':[{'name':'android / '+role,'status':'completed','conclusion':'success'}
            for role in ('route','execute','verify')]}
        def pending(*args,**kwargs):
            self.assertEqual(self.f.executed(),[]);self.assertFalse(self.f.args.receipt.exists())
            raise VALIDATION.StandalonePending('original Android is running')
        def completed(*args):
            self.assertEqual(self.f.executed(),['alpha']*len(self.required))
            observed=json.loads(Path(str(self.f.args.receipt)+'.ci-execution.json').read_bytes())
            self.assertEqual(observed['requested_suites'],self.required)
            self.assertFalse(self.f.args.receipt.exists(),'33 alone must never produce a successful report')
            return deepcopy(self.proof)
        result,owner=self.run_case(probe=pending,opening=completed)
        owner.assert_called_once()
        self.assertEqual(result['executed_suites'],self.required)
        self.assertEqual(result['reused_suites'],self.proof['suites'])
        self.assertIs(result['qualification'],False);self.assertIs(result['reusable'],False)

    def test_failed_or_still_pending_final_owner_cannot_report_success_or_repeat_native_four(self):
        for error in (VALIDATION.ValidationError('Android failed'),VALIDATION.StandalonePending('wait expired')):
            self.f.log.unlink(missing_ok=True)
            def pending(*args,**kwargs):raise VALIDATION.StandalonePending('original Android is running')
            def failed(*args):
                self.assertEqual(self.f.executed(),['alpha']*len(self.required))
                observed=json.loads(Path(str(self.f.args.receipt)+'.ci-execution.json').read_bytes())
                self.assertEqual(observed['requested_suites'],self.required)
                self.assertFalse(self.f.args.receipt.exists())
                raise error
            with self.subTest(error=type(error)),self.assertRaises(VALIDATION.ValidationError):
                self.run_case(probe=pending,opening=failed)
            self.assertEqual(self.f.executed(),['alpha']*len(self.required))
            self.assertFalse(self.f.args.receipt.exists())

    def test_closing_drift_does_not_retry_or_repeat_the_completed33(self):
        changed=deepcopy(self.proof);changed['candidate']='a'*40
        with self.assertRaises(VALIDATION.ValidationError):self.run_case(closing=lambda *a,**k:changed)
        self.assertEqual(len(self.f.executed()),33)

    def test_existing_full_native_E_remains_preferred_and_factory_is_unused(self):
        self.f.evidence['results']['suites']={name:{'status':'passed','fingerprint':'fixture-existing-E'}for name in self.names}
        result,owner=self.run_case(reuse=(self.f.evidence,self.names,[]))
        self.assertEqual(result['reused_suites'],self.names);self.assertEqual(self.f.executed(),[])
        owner.assert_not_called();self.assertNotIn('standalone_owner_evidence',result)

    def test_independent_product_schedule_keeps_prior37_without_entering_native_factory(self):
        f=self.f
        for name,command in VALIDATION.STANDALONE_CI_COMMANDS.items():
            path=f.candidate/command[1];path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text("from pathlib import Path\nimport os\nwith Path(os.environ['FIXTURE_EXECUTION_LOG']).open('a') as s:s.write("+repr(name+'\n')+")\n")
        f.ci_refresh();self.selection['standalone_ci_schedule']=False
        result,owner=self.run_case(opening=lambda *a:(_ for _ in()).throw(AssertionError('independent product schedule must not select native four')))
        self.assertEqual(result['mode'],'affected-ci');self.assertEqual(result['executed_suites'],self.names)
        self.assertEqual(len(f.executed()),37);owner.assert_not_called()

    def test_scheduling_uses_current_trusted_native_Android_and_effective_context_without_authority(self):
        event={'pull_request':{'number':42}};context={'base':'actual-effective-base'}
        plan={'host_mode':'delegated-sync','package_set':[],'paths':['tools/branch-cleanup/cleanup.py'],'regular':True}
        native=SimpleNamespace(plan=Mock(return_value={'mode':'skip'}))
        android=SimpleNamespace(activated=Mock(return_value=True),has_staged_caller=Mock(return_value=False),
            validate_execution_generation=Mock(),candidate_plan=Mock(return_value={'candidate':self.f.request.merge_sha,'required':False}))
        def load(name,path):return native if str(path).endswith('native-tests/check.py')else android
        with patch.object(VALIDATION,'_trusted_module',side_effect=load):
            self.assertIs(VALIDATION._standalone_ci_schedule(self.f.candidate,event,self.f.request,plan,
                **self.schedule_inputs,pr_context=context),True)
            self.assertEqual(android.candidate_plan.call_args.kwargs['pr_context'],context)
            android.candidate_plan.return_value['required']=True
            self.assertIs(VALIDATION._standalone_ci_schedule(self.f.candidate,event,self.f.request,plan,
                **self.schedule_inputs,pr_context=context),True)
            native.plan.return_value={'mode':'full'};android.candidate_plan.reset_mock()
            self.assertIs(VALIDATION._standalone_ci_schedule(self.f.candidate,event,self.f.request,plan,
                **self.schedule_inputs),False)
            android.candidate_plan.assert_not_called()
            native.plan.return_value={'mode':'skip'};android.candidate_plan.side_effect=ValueError('source mismatch')
            with self.assertRaises(ValueError):VALIDATION._standalone_ci_schedule(
                self.f.candidate,event,self.f.request,plan,**self.schedule_inputs)

    def test_CI32_schedule_recomputes_trusted_security_false_before_reserving_documentation(self):
        partial=[n for n in self.names if n not in {'producer-proof','python-test-runner','release-bundle',
            'project-coverage','native-registration'}]
        plan={'host_mode':'delegated-sync','package_set':[],'paths':['tools/sync-test-reuse/gate.py'],'regular':True}
        event={'repository':self.f.repository,'pull_request':self.f.pr}
        native=SimpleNamespace(plan=Mock(return_value={'mode':'skip'}))
        android=SimpleNamespace(activated=Mock(return_value=False),has_staged_caller=Mock(return_value=False))
        real=VALIDATION._trusted_module
        def load(name,path):
            if str(path).endswith('native-tests/check.py'):return native
            if str(path).endswith('repository-checks/android_gate.py'):return android
            return real(name,path)
        with patch.object(VALIDATION,'_trusted_module',side_effect=load):
            self.assertTrue(VALIDATION._standalone_ci_schedule(self.f.candidate,event,self.f.request,plan,
                **self.schedule_inputs,suite_names=partial))
            plan['paths']=['.github/workflows/unreviewed.yml'];native.plan.reset_mock()
            self.assertFalse(VALIDATION._standalone_ci_schedule(self.f.candidate,event,self.f.request,plan,
                **self.schedule_inputs,suite_names=partial));native.plan.assert_not_called()

    def test_static_recipe_registry_and_complete_callee_entries_choose_only_supported_native_four(self):
        plan={'host_mode':'delegated-sync','package_set':[],'paths':['tools/branch-cleanup/cleanup.py'],'regular':True}
        native=SimpleNamespace(plan=Mock(return_value={'mode':'skip'}))
        android=SimpleNamespace(activated=Mock(return_value=False),has_staged_caller=Mock(return_value=False))
        def load(name,path):return native if str(path).endswith('native-tests/check.py')else android
        def selected(frames):
            return VALIDATION._standalone_ci_schedule(self.f.candidate,{},self.f.request,plan,**frames)
        with patch.object(VALIDATION,'_trusted_module',side_effect=load):
            self.assertIs(selected(self.schedule_inputs),True)
            for side in self.schedule_inputs:
                for path in ('.github/workflows/repository-checks.yml',
                        '.github/workflows/documentation-checks.yml','.github/test-suites.json'):
                    for shape in ('changed','missing','mode','type'):
                        frames=deepcopy(self.schedule_inputs)
                        if shape=='missing':frames[side].pop(path)
                        else:frames[side][path][{'changed':'sha','mode':'mode','type':'type'}[shape]]={
                            'changed':'c'*40,'mode':'100755','type':'commit'}[shape]
                        with self.subTest(side=side,path=path,shape=shape):self.assertIs(selected(frames),False)
            for name in ('pr-metadata-context','native-tests','project-tests','android-required','workflow-security'):
                path='.github/workflows/'+name+'.yml'
                for side in ('candidate_tree','trusted_tree'):
                    for shape in ('changed','missing','mode','type'):
                        frames=deepcopy(self.schedule_inputs)
                        if shape=='missing':frames[side].pop(path)
                        else:frames[side][path][{'changed':'sha','mode':'mode','type':'type'}[shape]]={
                            'changed':'c'*40,'mode':'100755','type':'commit'}[shape]
                        with self.subTest(side=side,path=path,shape=shape):self.assertIs(selected(frames),False)
                frames=deepcopy(self.schedule_inputs);frames['base_tree'][path]['sha']='c'*40
                with self.subTest(old_base_callee=name):self.assertIs(selected(frames),True)

    def test_unsupported_recipe_keeps_actual37_without_entering_expected_native_proof(self):
        f=self.f
        for name,command in VALIDATION.STANDALONE_CI_COMMANDS.items():
            path=f.candidate/command[1];path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text("from pathlib import Path\nimport os\nwith Path(os.environ['FIXTURE_EXECUTION_LOG']).open('a') as s:s.write("+repr(name+'\n')+")\n")
        f.ci_refresh()
        self.schedule_inputs['base_tree']['.github/workflows/documentation-checks.yml']['sha']='c'*40
        plan={'host_mode':'delegated-sync','package_set':[]}
        with patch.object(VALIDATION,'_trusted_module',side_effect=AssertionError('unsupported recipe is decided before owner routing')):
            self.selection['standalone_ci_schedule']=VALIDATION._standalone_ci_schedule(
                f.candidate,{},f.request,plan,**self.schedule_inputs)
        self.assertIs(self.selection['standalone_ci_schedule'],False)
        result,owner=self.run_case(opening=lambda *a:(_ for _ in()).throw(AssertionError('unsupported recipe cannot enter native proof')))
        self.assertEqual(result['mode'],'affected-ci');self.assertEqual(result['executed_suites'],self.names)
        self.assertEqual(len(f.executed()),37);owner.assert_not_called()

if __name__ == "__main__":
    unittest.main()
