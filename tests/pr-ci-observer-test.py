#!/usr/bin/env python3
"""Offline trusted-record and CodeQL observation contracts; no native claims."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import unittest
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "pr_ci_observer_under_test", ROOT / "tools/repository-checks/pr_ci_observer.py")
O = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(O)


def context():
    return {"repository": O.C.REPOSITORY, "repository_id": O.C.REPOSITORY_ID,
            "number": 23, "target": "main", "base": "1" * 40,
            "head_ref": "fix/main/example", "head": "2" * 40, "tree": "3" * 40,
            "original_merge": "4" * 40, "observed_merge": "5" * 40,
            "run_id": 123, "run_attempt": 1, "caller_source": "4" * 40,
            "execution_event": "pull_request", "controller": "6" * 40}


class RecordTests(unittest.TestCase):
    def setUp(self):
        self.context = context()
        self.plan = {"host_suites": ["one"], "npm_projects": [], "native": {"mode": "skip"},
                     "codeql_languages": ["python"], "workflow_security": True,
                     "android_required": False, "ios_required": False,
                     "input_identity": {"candidate": "exact input digest"}}
        owners = O.expected_owners(self.plan)
        self.record = {"kind": "pr-ci-execution-v1", "result": "success", "run_id": 123,
                       "run_attempt": 1, "context": deepcopy(self.context), "plan": deepcopy(self.plan),
                       "owners": {key: {"result": "success" if selected else "skipped"}
                                  for key, selected in owners.items()}}

    def verify(self):
        return O.validate_record(self.record, self.plan, self.context, run_id=123, run_attempt=1)

    def test_complete_record_is_returned_unchanged_without_minting_authority(self):
        original = deepcopy(self.record)
        self.assertIs(self.verify(), self.record)
        self.assertEqual(original, self.record)
        self.assertNotIn("qualification", self.record)

    def test_only_mutable_observed_merge_may_differ(self):
        self.record["context"]["observed_merge"] = "6" * 40
        self.verify()
        for key in O.C.FIXED_FIELDS:
            original = self.record["context"][key]
            self.record["context"][key] = "changed"
            with self.subTest(key=key), self.assertRaises(O.ObserverError):
                self.verify()
            self.record["context"][key] = original

    def test_kind_result_run_attempt_and_caller_must_be_exact(self):
        for key, value in (("kind", "other"), ("result", "pending"), ("result", "failure"),
                           ("run_id", 124), ("run_id", "123"), ("run_attempt", 2)):
            original = self.record[key]; self.record[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(O.ObserverError):
                self.verify()
            self.record[key] = original
        self.record["context"]["caller_source"] = "6" * 40
        with self.assertRaises(O.ObserverError):
            self.verify()

    def test_complete_plan_is_compared_without_dropping_input_or_task_fields(self):
        self.record["plan"]["input_identity"]["candidate"] = "other"
        with self.assertRaises(O.ObserverError):
            self.verify()
        self.record["plan"] = deepcopy(self.plan)
        self.record["plan"]["unplanned"] = True
        with self.assertRaises(O.ObserverError):
            self.verify()

    def test_every_selected_owner_must_succeed_and_every_other_owner_skip(self):
        for name, expected in self.record["owners"].items():
            correct = expected["result"]
            for result in ("success", "skipped", "failure", "cancelled", None):
                if result == correct:
                    continue
                expected["result"] = result
                with self.subTest(owner=name, result=result), self.assertRaises(O.ObserverError):
                    self.verify()
            expected["result"] = correct
        self.record["owners"]["extra"] = {"result": "success"}
        with self.assertRaises(O.ObserverError):
            self.verify()
        self.record["owners"].pop("extra"); self.record["owners"].pop("policy")
        with self.assertRaises(O.ObserverError):
            self.verify()

    def test_all_eight_jobs_follow_strict_typed_selection(self):
        plan = {**self.plan, "npm_projects": ["server-console"], "native": {"mode": "core"},
                "android_required": True, "ios_required": True}
        self.assertTrue(all(O.expected_owners(plan).values()))
        for key in ("workflow_security", "android_required", "ios_required"):
            with self.subTest(key=key), self.assertRaises(O.ObserverError):
                O.expected_owners({**plan, key: "false"})

    def test_package_coverage_accepts_a_skipped_host_but_requires_successful_npm(self):
        self.plan.update(host_suites=["server-console-behavior"], npm_projects=["server-console"],
            covered_tasks={"suite:server-console-behavior": "npm:server-console"})
        self.record["plan"] = deepcopy(self.plan)
        self.record["owners"]["host"]["result"] = "skipped"
        self.record["owners"]["npm"]["result"] = "success"
        self.assertIs(self.verify(), self.record)
        for result in ("skipped", "failure"):
            self.record["owners"]["npm"]["result"] = result
            with self.subTest(result=result), self.assertRaises(O.ObserverError):
                self.verify()
        self.plan["host_suites"].append("another-contract")
        self.assertTrue(O.expected_owners(self.plan)["host"])

    def test_invalid_coverage_cannot_deselect_a_required_host_job(self):
        for covered in ([], {"suite:one": "npm:missing"}, {"suite:unknown": "npm:server-console"},
                        {"suite:one": ["npm:server-console"]}):
            with self.subTest(covered=covered), self.assertRaises(O.ObserverError):
                O.expected_owners({**self.plan, "npm_projects": ["server-console"],
                                   "covered_tasks": covered})

    def test_context_run_and_controller_cannot_disagree_with_transport(self):
        for key, value in (("run_id", 124), ("run_attempt", 2), ("controller", "7" * 40),
                           ("repository_id", float(O.C.REPOSITORY_ID))):
            original = self.record["context"][key]
            self.record["context"][key] = value
            with self.subTest(key=key), self.assertRaises(O.ObserverError): self.verify()
            self.record["context"][key] = original
        self.context["run_id"] = 124
        with self.assertRaises(O.ObserverError): self.verify()

    def test_completion_observed_merge_can_change_but_fixed_inputs_cannot(self):
        observed = deepcopy(self.context)
        observed["observed_merge"] = "7" * 40
        self.record["observed_context"] = observed
        self.verify()
        observed["base"] = "8" * 40
        with self.assertRaises(O.ObserverError): self.verify()

    def test_duplicate_plan_owner_declaration_must_equal_actual_selection(self):
        self.plan["owners"] = O.expected_owners(self.plan)
        self.record["plan"] = deepcopy(self.plan)
        self.verify()
        self.plan["owners"]["host"] = False
        self.record["plan"] = deepcopy(self.plan)
        with self.assertRaises(O.ObserverError): self.verify()


class FakeAPI:
    def __init__(self):
        self.objects, self.lists, self.calls = {}, {}, []

    def get(self, endpoint):
        self.calls.append(("get", endpoint))
        return deepcopy(self.objects[endpoint])

    def pages(self, endpoint):
        self.calls.append(("pages", endpoint))
        return deepcopy(self.lists[endpoint])


class CodeqlTests(unittest.TestCase):
    def setUp(self):
        self.context = context()
        self.languages = ["javascript-typescript", "python"]
        self.ref = "refs/pull/23/merge"
        self.api = FakeAPI()
        self.proofs = {}
        for index, language in enumerate(self.languages, 1):
            upload = "12345678-1234-4234-8234-" + str(index).zfill(12)
            self.proofs[language] = {"schema": 1, "repository": O.C.REPOSITORY,
                "repository_id": O.C.REPOSITORY_ID, "run_id": 123, "run_attempt": 1,
                "language": language, "source_commit": self.context["original_merge"],
                "ref": self.ref, "workflow": O.WORKFLOW,
                "workflow_sha": self.context["caller_source"], "sarif_id": upload}
            endpoint = "code-scanning/analyses?" + urlencode({"sarif_id": upload})
            self.api.objects["code-scanning/sarifs/" + upload] = {"processing_status": "complete",
                "errors": [], "analyses_url": "https://api.github.com/repos/" + O.C.REPOSITORY + "/" + endpoint}
            self.api.lists[endpoint] = [{"id": index, "sarif_id": upload, "ref": self.ref,
                "commit_sha": self.context["original_merge"], "category": "/language:" + language,
                "analysis_key": O.ANALYSIS_KEY, "tool": {"name": "CodeQL", "version": "2.27.2"},
                "error": "", "rules_count": 10, "environment": json.dumps({"language": language})}]
        self.alerts = "code-scanning/alerts?" + urlencode(
            {"ref": self.ref, "state": "open", "tool_name": "CodeQL"})
        self.api.lists[self.alerts] = []

    def verify(self):
        return O.verify_codeql(self.api, self.context, self.languages, self.proofs)

    def analysis(self, language="python"):
        return self.api.lists["code-scanning/analyses?" + urlencode(
            {"sarif_id": self.proofs[language]["sarif_id"]})]

    def test_actual_source_remains_original_when_observed_merge_regenerates(self):
        observed = self.verify()
        self.assertEqual(observed["state"], "complete")
        self.assertEqual(observed["source_commit"], self.context["original_merge"])
        self.assertEqual(set(observed["analyses"]), set(self.languages))
        self.assertTrue(all(method in {"get", "pages"} for method, _ in self.api.calls))

    def test_manual_and_prt_caller_sources_are_separate_from_analyzed_merge(self):
        for event, caller in (("workflow_dispatch", self.context["head"]),
                              ("pull_request_target", "7" * 40)):
            self.context.update(execution_event=event, caller_source=caller)
            for proof in self.proofs.values():
                proof["workflow_sha"] = caller
            self.assertEqual(self.verify()["state"], "complete")
        self.proofs["python"]["source_commit"] = self.context["head"]
        with self.assertRaises(O.ObserverError):
            self.verify()

    def test_pending_processing_is_distinct_and_does_not_schedule_anything(self):
        upload = self.proofs["python"]["sarif_id"]
        self.api.objects["code-scanning/sarifs/" + upload]["processing_status"] = "pending"
        result = self.verify()
        self.assertEqual(result["state"], "pending")
        self.assertEqual(result["pending_languages"], ["python"])
        self.assertEqual(set(result["analyses"]), {"javascript-typescript"})
        self.assertNotIn(("pages", "code-scanning/analyses?" + urlencode({"sarif_id": upload})), self.api.calls)

    def test_failed_unknown_or_error_processing_rejects(self):
        status = self.api.objects["code-scanning/sarifs/" + self.proofs["python"]["sarif_id"]]
        for value in ("failed", "unknown", None):
            status["processing_status"] = value
            with self.subTest(status=value), self.assertRaises(O.ObserverError):
                self.verify()
        status["processing_status"] = "complete"; status["errors"] = ["upload failed"]
        with self.assertRaises(O.ObserverError):
            self.verify()

    def test_native_upload_run_attempt_source_workflow_and_uuid_are_exact(self):
        proof = self.proofs["python"]
        for key, value in (("run_id", 124), ("run_attempt", 2), ("source_commit", "6" * 40),
                           ("workflow_sha", "6" * 40), ("workflow", ".github/workflows/foreign.yml"),
                           ("sarif_id", "../../foreign"), ("repository_id", 1)):
            original = proof[key]; proof[key] = value
            with self.subTest(key=key), self.assertRaises(O.ObserverError):
                self.verify()
            proof[key] = original
        proof["sarif_id"] = self.proofs["javascript-typescript"]["sarif_id"]
        with self.assertRaises(O.ObserverError):
            self.verify()

    def test_missing_upload_or_ambiguous_processed_analysis_rejects(self):
        proof = self.proofs.pop("python")
        with self.assertRaises(O.ObserverError):
            self.verify()

        self.proofs["python"] = proof
        analysis = self.analysis()
        original = deepcopy(analysis)
        for values in ([], [original[0], original[0]]):
            analysis[:] = values
            with self.subTest(count=len(values)), self.assertRaises(O.ObserverError):
                self.verify()

    def test_two_selected_languages_cannot_share_one_analysis_id(self):
        self.analysis("python")[0]["id"] = self.analysis("javascript-typescript")[0]["id"]
        with self.assertRaisesRegex(O.ObserverError, "share an analysis identity"):
            self.verify()

    def test_processed_analysis_uses_exact_original_source_tool_category_and_matrix(self):
        analysis = self.analysis()[0]
        for key, value in (("commit_sha", self.context["observed_merge"]), ("ref", "refs/heads/main"),
                           ("category", "/language:cpp"), ("analysis_key", ".github/workflows/codeql.yml:analyze"),
                           ("tool", {"name": "CodeQL", "version": "2.27.3"}), ("error", "partial"),
                           ("rules_count", 0), ("rules_count", True),
                           ("environment", '{"language":"python","language":"python"}')):
            original = analysis[key]; analysis[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(O.ObserverError):
                self.verify()
            analysis[key] = original

    def test_analysis_url_cannot_escape_repository_or_upload_uuid(self):
        status = self.api.objects["code-scanning/sarifs/" + self.proofs["python"]["sarif_id"]]
        status["analyses_url"] = "https://api.github.com/repos/foreign/repo/code-scanning/analyses?sarif_id=other"
        with self.assertRaises(O.ObserverError):
            self.verify()

    def finding(self, *, state="open", category="/language:python", source=None):
        self.api.lists[self.alerts] = [{"number": 9, "state": "open", "tool": {"name": "CodeQL"}}]
        self.api.lists["code-scanning/alerts/9/instances?" + urlencode({"ref": self.ref})] = [
            {"ref": self.ref, "category": category, "state": state,
             "commit_sha": source or self.context["original_merge"]}]

    def test_every_open_selected_finding_blocks_including_low_severity(self):
        self.finding()
        self.api.lists[self.alerts][0]["rule"] = {"security_severity_level": "low"}
        with self.assertRaisesRegex(O.ObserverError, "open CodeQL finding"):
            self.verify()
        self.finding(source="6" * 40)
        with self.assertRaisesRegex(O.ObserverError, "another source"):
            self.verify()

    def test_fixed_dismissed_or_unselected_instances_do_not_block(self):
        for state, category in (("fixed", "/language:python"), ("dismissed", "/language:python"),
                                ("open", "/language:cpp")):
            with self.subTest(state=state, category=category):
                self.finding(state=state, category=category)
                self.assertEqual(self.verify()["state"], "complete")

    def test_malformed_missing_duplicate_or_foreign_alert_instances_reject(self):
        self.finding()
        endpoint = "code-scanning/alerts/9/instances?" + urlencode({"ref": self.ref})
        for instances in ([], [{"ref": "refs/heads/main", "category": "/language:python", "state": "fixed"}],
                          [{"ref": self.ref, "category": "/language:python", "state": "unknown"}]):
            self.api.lists[endpoint] = instances
            with self.subTest(instances=instances), self.assertRaises(O.ObserverError):
                self.verify()
        self.finding(state="fixed")
        self.api.lists[self.alerts] *= 2
        with self.assertRaises(O.ObserverError):
            self.verify()

    def test_no_selected_languages_does_not_read_codeql_or_claim_execution(self):
        self.languages = []; self.proofs = {}
        result = self.verify()
        self.assertEqual(result["state"], "complete")
        self.assertEqual(self.api.calls, [])
        self.assertNotIn("qualification", result)


if __name__ == "__main__":
    unittest.main()
