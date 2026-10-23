#!/usr/bin/env python3
"""Offline CLI composition with native-shaped API, ZIPs and temporary Git.

The context, transport and record validators execute unchanged. Gate tests
substitute only the GET adapter, artifact bytes, loaded checkout identity and
the separately tested pure planner result. Execution tests intercept the
isolation boundary; no candidate command, network request or native run occurs.
"""
from contextlib import ExitStack, redirect_stdout
from copy import deepcopy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urlencode
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("pr_ci_cli_under_test",
    ROOT / "tools/repository-checks/pr_ci.py")
CLI = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CLI)
import pr_ci_observer as OBSERVER
import pr_ci_transport as TRANSPORT
import pr_ci_run as RUNNER


class NativeAPI:
    def __init__(self):
        self.objects, self.lists, self.calls, self.hooks = {}, {}, [], {}
    def get(self, endpoint):
        self.calls.append(("get", endpoint))
        value = deepcopy(self.objects[endpoint])
        return self.hooks.get(endpoint, lambda value: value)(value)
    def pages(self, endpoint, *, field=None):
        self.calls.append(("pages", endpoint, field))
        value = deepcopy(self.lists[endpoint])
        return self.hooks.get("pages:" + endpoint, lambda value: value)(value)


class GateTests(unittest.TestCase):
    def setUp(self):
        self.base, self.head, self.tree, self.original, self.regenerated = (x * 40 for x in "12345")
        self.controller = self.head
        self.api = NativeAPI()
        repo = {"full_name": CLI.C.REPOSITORY, "id": CLI.C.REPOSITORY_ID}
        self.pr = {"number": 42, "state": "open", "base": {"ref": "main", "sha": self.base, "repo": repo},
                   "head": {"ref": "fix/main/example", "sha": self.head, "repo": deepcopy(repo)}}
        self.api.objects.update({"": repo, "pulls/42": self.pr,
            "branches/main": {"name": "main", "protected": True, "commit": {"sha": self.base}},
            "git/ref/heads/fix%2Fmain%2Fexample": {"ref": "refs/heads/fix/main/example",
                "object": {"type": "commit", "sha": self.head}},
            "commits/refs/pull/42/merge": {"sha": self.regenerated},
            "actions/workflows/repository-checks.yml": {"id": 456, "path": TRANSPORT.WORKFLOW}})
        for revision in (self.original, self.regenerated):
            self.api.objects["git/commits/" + revision] = {"sha": revision, "tree": {"sha": self.tree},
                "parents": [{"sha": self.base}, {"sha": self.head}]}
        self.context = CLI.C.capture(self.api, 42, original_merge=self.original)
        self.context.update(controller=self.controller, caller_source=self.head,
            execution_event="workflow_dispatch", run_id=123, run_attempt=1)
        self.plan = {"host_suites": ["contract"], "npm_projects": [], "native": {"mode": "skip"},
            "codeql_languages": ["python"], "workflow_security": False,
            "android_required": False, "ios_required": False,
            "controller": self.controller, "input_identity": {"candidate": "full-tree-key"}}
        self.plan["owners"] = CLI.expected_owners(self.plan)
        self.record = {"kind": "pr-ci-execution-v1", "result": "success", "context": deepcopy(self.context),
            "observed_context": CLI.C.capture(self.api, 42, original_merge=self.original),
            "run_id": 123, "run_attempt": 1, "plan": deepcopy(self.plan), "owners": {
                name: {"result": "success" if selected else "skipped"}
                for name, selected in self.plan["owners"].items()}}
        self.native = {"id": 123, "run_attempt": 1, "check_suite_id": 789, "workflow_id": 456,
            "path": TRANSPORT.WORKFLOW, "event": "workflow_dispatch", "head_sha": self.head,
            "head_branch": self.pr["head"]["ref"], "repository": repo, "head_repository": deepcopy(repo),
            "pull_requests": [], "status": "in_progress", "conclusion": None,
            "url": TRANSPORT.API_ROOT + "/actions/runs/123",
            "html_url": "https://github.com/" + CLI.C.REPOSITORY + "/actions/runs/123"}
        self.api.objects["actions/runs/123"] = self.native
        self.api.objects["check-suites/789"] = {"id": 789, "head_sha": self.head,
            "repository": repo, "app": {"id": 15368}}
        self.job_rows = []
        def job(label, role, selected):
            self.job_rows.append({"id": 1000 + len(self.job_rows), "run_id": 123, "run_attempt": 1,
                "head_sha": self.head, "name": label, "status": "completed",
                "conclusion": "success" if selected else "skipped", "steps": [
                    {"name": name, "number": i + 1, "status": "completed", "conclusion": "success"}
                    for i, name in enumerate(TRANSPORT.STEPS[role])] if selected else []})
        job("Select exact candidate tasks", "plan", True)
        for role, label in TRANSPORT.LABELS.items(): job(label, role, self.plan["owners"][role])
        job("CodeQL (python)", "codeql", True)
        job("Candidate execution receipt", "receipt", True)
        self.job_rows.append({"id": 2000, "run_id": 123, "run_attempt": 1, "head_sha": self.head,
            "name": "required-ci", "status": "in_progress", "conclusion": None, "steps": []})
        self.api.lists["actions/runs/123/attempts/1/jobs"] = self.job_rows
        self.source_tree = {path: {"mode": "100644", "type": "blob", "sha": "a" * 40} for path in (
            TRANSPORT.WORKFLOW, ".github/pr-ci-suites.json", ".github/pr-ci-dependencies.json", *[
                "tools/repository-checks/pr_ci" + suffix + ".py"
                for suffix in ("", "_context", "_plan", "_run", "_observer", "_transport")])}
        self.actual_tree = deepcopy(self.source_tree)
        self.upload_id = "12345678-1234-4234-8234-000000000001"
        self.upload = {"schema": 1, "repository": CLI.C.REPOSITORY, "repository_id": CLI.C.REPOSITORY_ID,
            "run_id": 123, "run_attempt": 1, "language": "python", "source_commit": self.original,
            "ref": "refs/pull/42/merge", "workflow": TRANSPORT.WORKFLOW,
            "workflow_sha": self.controller, "sarif_id": self.upload_id}
        endpoint = "code-scanning/analyses?" + urlencode({"sarif_id": self.upload_id})
        self.api.objects["code-scanning/sarifs/" + self.upload_id] = {"processing_status": "complete",
            "errors": [], "analyses_url": TRANSPORT.API_ROOT + "/" + endpoint}
        self.api.lists[endpoint] = [{"id": 900, "sarif_id": self.upload_id,
            "ref": "refs/pull/42/merge", "commit_sha": self.original, "category": "/language:python",
            "analysis_key": OBSERVER.ANALYSIS_KEY, "tool": {"name": "CodeQL", "version": "2.27.2"},
            "error": "", "rules_count": 123, "environment": '{"language":"python"}'}]
        self.api.lists["code-scanning/alerts?" + urlencode({"ref": "refs/pull/42/merge", "state": "open",
            "tool_name": "CodeQL"})] = []
        self.downloads, self.selected_contexts = [], []
        self.environment = {"GITHUB_REPOSITORY": CLI.C.REPOSITORY,
            "GITHUB_REPOSITORY_ID": str(CLI.C.REPOSITORY_ID), "GITHUB_RUN_ID": "123",
            "GITHUB_RUN_ATTEMPT": "1", "GITHUB_WORKFLOW_SHA": self.controller, "GITHUB_SHA": self.head}
        self.api.calls.clear()

    def install_artifacts(self):
        raw, rows = {}, []
        for number, name, member, value in ((321, "pr-ci-123-1", "result.json", self.record),
                (322, "codeql-upload-123-1-python", "upload.json", self.upload)):
            stream = io.BytesIO()
            with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                archive.writestr(member, CLI.C.canonical(value))
            data = stream.getvalue(); raw[number] = data
            artifact = {"id": number, "name": name, "expired": False, "size_in_bytes": len(data),
                "digest": "sha256:" + hashlib.sha256(data).hexdigest(),
                "url": TRANSPORT.API_ROOT + "/actions/artifacts/" + str(number),
                "archive_download_url": TRANSPORT.API_ROOT + "/actions/artifacts/" + str(number) + "/zip",
                "workflow_run": {"id": 123, "repository_id": CLI.C.REPOSITORY_ID,
                    "head_repository_id": CLI.C.REPOSITORY_ID, "head_sha": self.head}}
            self.api.objects["actions/artifacts/" + str(number)] = artifact; rows.append(artifact)
        self.api.lists["actions/runs/123/artifacts"] = rows
        return raw

    def run_gate(self, event_name="workflow_dispatch", *, pause=None):
        archives = self.install_artifacts()
        def selection(api, context):
            self.selected_contexts.append(deepcopy(context))
            return deepcopy(self.plan), deepcopy(self.actual_tree), deepcopy(self.source_tree)
        def download(api, artifact_id):
            self.downloads.append(artifact_id)
            return archives[artifact_id]
        def no_wait(_): raise AssertionError("unexpected pending loop in terminal fixture")
        with ExitStack() as stack:
            stack.enter_context(patch.object(CLI, "API", return_value=self.api))
            stack.enter_context(patch.object(CLI, "git", return_value=(self.controller + "\n").encode()))
            stack.enter_context(patch.object(CLI, "remote_selection", side_effect=selection))
            stack.enter_context(patch.object(TRANSPORT, "_download", side_effect=download))
            stack.enter_context(patch.dict(os.environ, self.environment))
            output = stack.enter_context(redirect_stdout(io.StringIO()))
            CLI.gate({"number": 42, "pull_request": deepcopy(self.pr)}, event_name, 42, self.controller,
                     timeout=10, pause=no_wait if pause is None else pause)
        return json.loads(output.getvalue().splitlines()[-1])

    def test_manual_bootstrap_accepts_successful_owners_while_enclosing_run_is_in_progress(self):
        result = self.run_gate()
        self.assertEqual(result["result"], "success")
        self.assertEqual(self.native["status"], "in_progress")
        self.assertEqual(result["run_attempt"], 1)
        self.assertEqual(self.downloads, [321, 322])

    def test_original_merge_remains_upload_and_result_source_after_exact_merge_regeneration(self):
        result = self.run_gate()
        self.assertEqual(result["source"], self.original)
        self.assertEqual(self.selected_contexts[0]["original_merge"], self.original)
        self.assertEqual(self.selected_contexts[0]["observed_merge"], self.regenerated)
        self.assertEqual(self.upload["source_commit"], self.original)

    def ordinary_worker(self):
        self.controller = self.base
        self.context.update(controller=self.base, caller_source=self.original, execution_event="pull_request")
        self.plan["controller"] = self.base
        self.record.update(context=deepcopy(self.context), plan=deepcopy(self.plan))
        self.native["event"] = "pull_request"
        self.native["pull_requests"] = [{"number": 42,
            "base": deepcopy(self.pr["base"]), "head": deepcopy(self.pr["head"])}]
        self.upload["workflow_sha"] = self.original
        self.environment.update(GITHUB_WORKFLOW_SHA=self.base, GITHUB_RUN_ID="999")
        self.api.lists["actions/workflows/repository-checks.yml/runs?event=pull_request&head_sha="
            + self.head] = [self.native]
        self.job_rows[-1].update(name="Execution observer has no acceptance authority",
                                status="completed", conclusion="skipped")

    def test_protected_default_observes_ordinary_worker_without_relabeling_source(self):
        self.ordinary_worker()
        result = self.run_gate("pull_request_target")
        self.assertEqual(result["source"], self.original)
        self.assertEqual(self.selected_contexts[0]["controller"], self.base)
        self.assertEqual(self.selected_contexts[0]["caller_source"], self.original)

    def test_all_children_use_the_default_controller_and_authenticated_target_workflow_basis(self):
        for target in sorted(CLI.C.TARGETS - {"main"}):
            with self.subTest(target=target):
                self.setUp()
                self.pr["base"]["ref"] = target
                self.api.objects["branches/" + target] = {
                    "name": target, "protected": True, "commit": {"sha": self.base}}
                self.context["target"] = target
                self.plan["target"] = target
                self.ordinary_worker()
                self.controller = "9" * 40
                self.context["controller"] = self.controller
                self.plan["controller"] = self.controller
                self.record.update(context=deepcopy(self.context), plan=deepcopy(self.plan),
                    observed_context=CLI.C.capture(self.api, 42, original_merge=self.original))
                self.environment["GITHUB_WORKFLOW_SHA"] = self.controller
                self.api.objects["branches/main"] = {
                    "name": "main", "protected": True, "commit": {"sha": self.controller}}
                legacy = ".github/workflows/product-legacy.yml"
                self.actual_tree[legacy] = {"mode": "100644", "type": "blob", "sha": "b" * 40}
                base_tree = "6" * 40
                self.api.objects["git/commits/" + self.base] = {
                    "sha": self.base, "tree": {"sha": base_tree}}
                self.api.objects["git/trees/" + base_tree + "?recursive=1"] = {
                    "sha": base_tree, "truncated": False,
                    "tree": [{"path": path, **entry} for path, entry in self.actual_tree.items()]}
                result = self.run_gate("pull_request_target")
                self.assertEqual(self.original, result["source"])
                self.assertEqual(self.controller, self.selected_contexts[0]["controller"])
                self.assertEqual(target, self.selected_contexts[0]["target"])
                self.assertIn(("get", "git/commits/" + self.base), self.api.calls)
                self.assertIn(("get", "git/trees/" + base_tree + "?recursive=1"), self.api.calls)

    def selected_native(self, mode):
        self.plan["native"] = {"mode": mode}
        self.plan["owners"] = CLI.expected_owners(self.plan)
        self.record["plan"] = deepcopy(self.plan)
        self.record["owners"]["native"] = {"result": "success"}
        native = next(row for row in self.job_rows if row["name"] == "Native C++ owner / build")
        native.update(status="completed", conclusion="success", steps=[
            {"name": name, "number": index + 1, "status": "completed", "conclusion": "success"}
            for index, name in enumerate(TRANSPORT.STEPS["native"])])

    def test_manual_bootstrap_cannot_accept_a_native_owner_receipt(self):
        for mode in ("core", "full"):
            self.selected_native(mode)
            with self.subTest(mode=mode), self.assertRaisesRegex(CLI.C.ContextError, "(?i)bootstrap|manual"):
                self.run_gate()

    def test_ordinary_pr_can_use_the_unchanged_native_owner(self):
        self.ordinary_worker()
        self.selected_native("core")
        result = self.run_gate("pull_request_target")
        self.assertTrue(result["owners"]["native"])
        self.assertEqual(result["source"], self.original)

    def test_completed_metadata_only_worker_does_not_replace_original_execution(self):
        self.ordinary_worker()
        self.api.lists["actions/workflows/repository-checks.yml/runs?event=pull_request&head_sha="
            + self.head].append({**self.native, "id": 124})
        self.api.lists["actions/runs/124/attempts/1/jobs"] = [{"status": "completed", "conclusion": "skipped"}]
        self.assertEqual(self.run_gate("pull_request_target")["run_id"], 123)

    def test_initially_empty_metadata_job_listing_does_not_pin_a_nonexecution_run(self):
        self.ordinary_worker()
        later = {**deepcopy(self.native), "id": 124, "check_suite_id": 790,
            "status": "completed", "conclusion": "success",
            "url": TRANSPORT.API_ROOT + "/actions/runs/124",
            "html_url": "https://github.com/" + CLI.C.REPOSITORY + "/actions/runs/124"}
        self.api.objects["actions/runs/124"] = later
        self.api.objects["check-suites/790"] = {**self.api.objects["check-suites/789"], "id": 790}
        self.api.lists["actions/workflows/repository-checks.yml/runs?event=pull_request&head_sha="
            + self.head].append(later)
        self.api.lists["actions/runs/124/attempts/1/jobs"] = [{"status": "completed", "conclusion": "skipped"}]
        reads, pauses = [], []
        def delayed_jobs(rows):
            reads.append(True)
            return [] if len(reads) == 1 else rows
        def bounded_pause(seconds):
            pauses.append(seconds)
            self.assertLessEqual(len(pauses), 2, "observer stayed pinned to a metadata-only worker")
        self.api.hooks["pages:actions/runs/124/attempts/1/jobs"] = delayed_jobs
        self.assertEqual(self.run_gate("pull_request_target", pause=bounded_pause)["run_id"], 123)

    def test_closing_native_attempt_change_cannot_accept_the_earlier_receipt(self):
        reads = []
        def change_at_close(value):
            reads.append(True)
            if len(reads) >= 3: value["run_attempt"] = 2
            return value
        self.api.hooks["actions/runs/123"] = change_at_close
        with self.assertRaises(ValueError): self.run_gate()
        self.assertGreaterEqual(len(reads), 3)

    def test_closing_check_suite_app_change_cannot_accept_the_earlier_receipt(self):
        reads = []
        def change_at_close(value):
            reads.append(True)
            if len(reads) >= 2: value["app"]["id"] = 999
            return value
        self.api.hooks["check-suites/789"] = change_at_close
        with self.assertRaises(ValueError): self.run_gate()
        self.assertGreaterEqual(len(reads), 2)

    def test_final_pr_bookend_rejects_base_advance_during_artifact_processing(self):
        reads = []
        def change_at_close(value):
            reads.append(True)
            if len(reads) >= 3: value["base"]["sha"] = "9" * 40
            return value
        self.api.hooks["pulls/42"] = change_at_close
        with self.assertRaisesRegex(CLI.C.ContextError, "protected target advanced"):
            self.run_gate()

    def native_final(self):
        self.ordinary_worker()
        self.environment.update(GITHUB_WORKFLOW_SHA=self.original, GITHUB_SHA=self.original,
                                GITHUB_REF="refs/pull/42/merge", GITHUB_RUN_ID="123")
        self.job_rows[-1].update(name="required-ci", status="in_progress", conclusion=None)
        self.job_rows.append({"id": 2001, "run_id": 123, "run_attempt": 1, "head_sha": self.head,
            "name": "Source policy not applicable", "status": "completed", "conclusion": "skipped", "steps": []})

    def test_native_final_observes_its_own_completed_owners_without_searching_other_runs(self):
        self.native_final()
        self.assertEqual("success", self.run_gate("pull_request")["result"])
        self.assertFalse(any("/runs?event=" in call[1] for call in self.api.calls))

    def test_native_final_rejects_a_different_caller(self):
        self.native_final()
        self.environment["GITHUB_WORKFLOW_SHA"] = self.base
        with self.assertRaisesRegex(CLI.C.ContextError, "original PR caller"):
            self.run_gate("pull_request")

    def run_source_policy_cli(self):
        with tempfile.TemporaryDirectory(prefix="pr-ci-source-policy-") as tmp:
            event = Path(tmp) / "event.json"
            event.write_text(json.dumps({"number": 42, "pull_request": self.pr}))
            with patch.object(sys, "argv", ["pr_ci.py", "source-policy", "--event", str(event),
                    "--event-name", "pull_request_target", "--number", "42",
                    "--controller", self.controller]):
                return CLI.main()

    def test_fast_source_policy_validates_sources_without_reading_execution_metadata(self):
        self.ordinary_worker()
        with patch.object(CLI, "API", return_value=self.api), \
             patch.object(CLI, "git", return_value=(self.controller+"\n").encode()), \
             patch.object(CLI, "remote_selection", return_value=(self.plan,self.actual_tree,self.source_tree)), \
             patch.dict(os.environ,self.environment), redirect_stdout(io.StringIO()):
            self.assertEqual(0, self.run_source_policy_cli())
        self.assertFalse(any(call[1].startswith(("actions/", "check-suites/", "code-scanning/")) for call in self.api.calls))

    def test_fast_source_policy_rejects_candidate_workflow_mutation(self):
        self.ordinary_worker()
        self.actual_tree[TRANSPORT.WORKFLOW]["sha"] = "b"*40
        with patch.object(CLI, "API", return_value=self.api), \
             patch.object(CLI, "git", return_value=(self.controller+"\n").encode()), \
             patch.object(CLI, "remote_selection", return_value=(self.plan,self.actual_tree,self.source_tree)), \
             patch.dict(os.environ,self.environment), self.assertRaises(TRANSPORT.TransportError):
            self.run_source_policy_cli()

    def test_new_main_product_commit_preserves_controller_but_policy_or_runtime_change_does_not(self):
        self.ordinary_worker()
        revision="9"*40
        self.api.objects["branches/main"]["commit"]["sha"] = revision
        self.api.objects["git/commits/"+revision] = {"sha":revision,"tree":{"sha":"8"*40}}
        current=deepcopy(self.source_tree)
        current["interface/product.cpp"]={"mode":"100644","type":"blob","sha":"b"*40}
        with patch.object(CLI,"remote_tree",return_value=current), \
             patch.object(CLI.P._INPUTS,"full_tree",return_value=self.source_tree):
            CLI.current_controller(self.api,self.controller)
            current[TRANSPORT.WORKFLOW]["sha"]="c"*40
            with self.assertRaises(TRANSPORT.TransportError):
                CLI.current_controller(self.api,self.controller)
            current[TRANSPORT.WORKFLOW]["sha"]="a"*40
            current[CLI.P.RUNTIME_INPUTS[0]]={"mode":"100644","type":"blob","sha":"d"*40}
            with self.assertRaisesRegex(CLI.C.ContextError,"runtime inputs changed"):
                CLI.current_controller(self.api,self.controller)

    def test_native_failure_stops_before_artifact_download(self):
        self.job_rows[2]["conclusion"] = "failure"
        with self.assertRaisesRegex(CLI.C.ContextError, "worker job failed"):
            self.run_gate()
        self.assertFalse(self.downloads)
        self.assertNotIn(("pages", "actions/runs/123/artifacts", "artifacts"), self.api.calls)

    def test_foreign_suite_and_native_attempt_are_refused(self):
        self.api.objects["check-suites/789"]["app"]["id"] = 999
        with self.assertRaisesRegex(CLI.C.ContextError, "check suite"):
            self.run_gate()
        self.api.objects["check-suites/789"]["app"]["id"] = 15368
        reads = []
        def change_attempt(value):
            reads.append(True)
            if len(reads) > 1: value["run_attempt"] = 2
            return value
        self.api.hooks["actions/runs/123"] = change_attempt
        with self.assertRaisesRegex(CLI.C.ContextError, "attempt changed"):
            self.run_gate()

    def test_changed_base_head_or_regenerated_tree_cannot_be_accepted(self):
        self.api.objects["git/commits/" + self.regenerated]["tree"]["sha"] = "9" * 40
        with self.assertRaisesRegex(CLI.C.ContextError, "different content"):
            self.run_gate()
        self.api.objects["git/commits/" + self.regenerated]["tree"]["sha"] = self.tree
        self.api.objects["branches/main"]["commit"]["sha"] = "9" * 40
        with self.assertRaisesRegex(CLI.C.ContextError, "protected target advanced"):
            self.run_gate()

    def test_changed_controller_or_worker_workflow_refuses_artifact_content(self):
        self.actual_tree[TRANSPORT.WORKFLOW]["sha"] = "9" * 40
        with self.assertRaisesRegex(TRANSPORT.TransportError, "differs from trusted source"):
            self.run_gate()
        self.assertEqual(self.downloads, [321])

    def test_an_open_selected_codeql_finding_refuses_acceptance(self):
        endpoint = "code-scanning/alerts?" + urlencode({"ref": "refs/pull/42/merge", "state": "open",
            "tool_name": "CodeQL"})
        self.api.lists[endpoint] = [{"number": 7, "state": "open", "tool": {"name": "CodeQL"}}]
        self.api.lists["code-scanning/alerts/7/instances?" + urlencode({"ref": "refs/pull/42/merge"})] = [
            {"ref": "refs/pull/42/merge", "state": "open", "category": "/language:python",
             "commit_sha": self.original}]
        with self.assertRaisesRegex(OBSERVER.ObserverError, "open CodeQL finding"):
            self.run_gate()


class CommandTests(unittest.TestCase):
    def setUp(self):
        self.context = {"run_id": 123, "run_attempt": 1, "caller_source": "2" * 40,
                        "original_merge": "4" * 40, "head": "2" * 40, "number": 42}
        self.env = {"GITHUB_REPOSITORY": CLI.C.REPOSITORY,
            "GITHUB_REPOSITORY_ID": str(CLI.C.REPOSITORY_ID), "GITHUB_RUN_ID": "123",
            "GITHUB_RUN_ATTEMPT": "1", "GITHUB_WORKFLOW_SHA": "2" * 40}
        self.plan = {"host_suites": [], "npm_projects": [], "native": {"mode": "skip"},
            "codeql_languages": [], "workflow_security": False, "android_required": False, "ios_required": False}

    def test_complete_requires_successful_plan_and_all_eight_exact_owners(self):
        needs = {"plan": {"result": "success"}, **{name: {"result": "success" if selected else "skipped"}
            for name, selected in CLI.expected_owners(self.plan).items()}}
        with patch.dict(os.environ, self.env), patch.object(CLI.C, "bookend", return_value={"observed": True}):
            result = CLI.complete(self.context, self.plan, needs)
            self.assertEqual(set(result["owners"]), set(CLI.expected_owners(self.plan)))
            self.assertEqual(result["kind"], "pr-ci-execution-v1")
            for name in needs:
                changed = deepcopy(needs); changed[name]["result"] = "failure"
                with self.subTest(name=name), self.assertRaises(CLI.C.ContextError):
                    CLI.complete(self.context, self.plan, changed)
            with self.assertRaises(CLI.C.ContextError):
                CLI.complete(self.context, self.plan, {**needs, "extra": {"result": "success"}})

    def test_upload_proof_binds_native_run_attempt_caller_and_original_analysis(self):
        upload = "12345678-1234-4234-8234-000000000001"
        with patch.dict(os.environ, self.env):
            proof = CLI.upload_proof(self.context, "python", upload)
            self.assertEqual((proof["source_commit"], proof["workflow_sha"]), ("4" * 40, "2" * 40))
            self.assertEqual((proof["run_id"], proof["run_attempt"]), (123, 1))
            for key, value in (("GITHUB_RUN_ID", "124"), ("GITHUB_RUN_ATTEMPT", "2"),
                               ("GITHUB_WORKFLOW_SHA", "6" * 40)):
                with self.subTest(key=key), patch.dict(os.environ, {key: value}), self.assertRaises(CLI.C.ContextError):
                    CLI.upload_proof(self.context, "python", upload)

    def test_plan_execution_scope_rejects_manual_native_before_owner_execution(self):
        for mode in ("core", "full"):
            plan = {**self.plan, "native": {"mode": mode}}
            with self.subTest(mode=mode), self.assertRaises(CLI.C.ContextError):
                CLI.validate_execution_scope({**self.context, "execution_event": "workflow_dispatch"}, plan)
            CLI.validate_execution_scope({**self.context, "execution_event": "pull_request"}, plan)

    def candidate(self, path):
        subprocess.run([sys.executable, str(ROOT / "tools/branch-policy/check.py"), "check-name",
            "--branch", "test/main/pr-ci-cli-fixture"], cwd=ROOT, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.run(["git", "init", "--quiet", "--initial-branch=test/main/pr-ci-cli-fixture", str(path)], check=True)
        (path / "tracked.txt").write_text("immutable source\n")
        subprocess.run(["git", "-C", str(path), "add", "tracked.txt"], check=True)
        subprocess.run(["git", "-C", str(path), "-c", "user.name=Offline test", "-c", "user.email=offline@example.invalid",
            "commit", "--quiet", "-m", "Create isolated execution fixture"], check=True)
        return path

    def test_selected_jsdoc_command_replaces_only_reviewed_temporary_placeholder(self):
        task = {"id": "npm:tools/jsdoc", "kind": "npm", "command": [["npm", "ci"],
            ["npm", "exec", "jsdoc", "--", "-d", "{temporary_output}"]], "missing_inputs": [],
            "setup": [], "reuse_key": "actual-key"}
        with tempfile.TemporaryDirectory(prefix="pr-ci-command-") as tmp:
            root = self.candidate(Path(tmp) / "candidate")
            with patch.object(RUNNER, "run", return_value=0) as execute:
                receipts = CLI.execute(root, {"tasks": [task]}, "npm", "tools/jsdoc", [])
            self.assertEqual(len(receipts), 1)
            first, second = execute.call_args_list
            self.assertEqual(first.args[1], ["/usr/bin/env", "--chdir=/work/tools/jsdoc", "npm", "ci"])
            self.assertTrue(first.kwargs["network"])
            self.assertFalse(second.kwargs["network"])
            self.assertEqual(first.kwargs["boundary"], "user-namespace")
            self.assertEqual(second.kwargs["boundary"], "user-namespace")
            self.assertIn("/tmp/overte-jsdoc-output", second.args[1])
            self.assertNotIn("{temporary_output}", second.args[1])
            with self.assertRaisesRegex(CLI.C.ContextError, "unselected or empty"):
                CLI.execute(root, {"tasks": [task]}, "host", "", [])

    def test_failed_candidate_command_and_tracked_mutation_stop_execution(self):
        task = {"id": "suite:one", "kind": "host", "command": ["python", "tests/one.py"],
            "missing_inputs": [], "setup": [], "reuse_key": "actual-key"}
        with tempfile.TemporaryDirectory(prefix="pr-ci-command-") as tmp:
            root = self.candidate(Path(tmp) / "candidate")
            with patch.object(RUNNER, "run", return_value=1) as failed, self.assertRaisesRegex(CLI.C.ContextError, "selected command failed"):
                CLI.execute(root, {"tasks": [task]}, "host", "", [])
            self.assertEqual(failed.call_args.kwargs["boundary"], "user-namespace")
            self.assertEqual(failed.call_args.args[1][0], sys.executable)
            def mutate(*args, **kwargs):
                (root / "tracked.txt").write_text("changed by candidate\n")
                return 0
            with patch.object(RUNNER, "run", side_effect=mutate), self.assertRaisesRegex(CLI.C.ContextError, "changed its immutable"):
                CLI.execute(root, {"tasks": [task]}, "host", "", [])


if __name__ == "__main__":
    unittest.main()
