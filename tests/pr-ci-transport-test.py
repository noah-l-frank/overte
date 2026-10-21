#!/usr/bin/env python3
"""Offline native transport contracts; fixtures cannot issue native authority."""
from copy import deepcopy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import unittest
from unittest.mock import patch
import urllib.error
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("pr_ci_transport_tested",
    ROOT / "tools/repository-checks/pr_ci_transport.py")
T = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(T)


def context():
    return {"repository": T.C.REPOSITORY, "repository_id": T.C.REPOSITORY_ID,
        "number": 42, "target": "main", "base": "1" * 40, "head": "2" * 40,
        "head_ref": "fix/main/example", "tree": "3" * 40, "original_merge": "4" * 40,
        "observed_merge": "5" * 40, "run_id": 123, "run_attempt": 1,
        "controller": "6" * 40}


def run():
    c = context()
    repo = {"id": T.C.REPOSITORY_ID, "full_name": T.C.REPOSITORY}
    return {"id": 123, "run_attempt": 1, "check_suite_id": 789,
        "workflow_id": 456, "path": T.WORKFLOW, "event": "pull_request",
        "head_sha": c["head"], "head_branch": c["head_ref"], "repository": repo,
        "head_repository": deepcopy(repo), "status": "in_progress", "conclusion": None,
        "url": T.API_ROOT + "/actions/runs/123",
        "html_url": "https://github.com/" + T.C.REPOSITORY + "/actions/runs/123",
        "pull_requests": [{"number": 42,
            "base": {"sha": c["base"], "ref": "main", "repo": repo},
            "head": {"sha": c["head"], "ref": c["head_ref"], "repo": repo}}]}


def jobs(owners):
    result = []
    def add(label, owner, selected):
        result.append({"id": 1000 + len(result), "run_id": 123, "run_attempt": 1,
            "head_sha": context()["head"], "name": label, "status": "completed",
            "conclusion": "success" if selected else "skipped",
            "steps": [{"name": name, "number": index + 1, "status": "completed",
                       "conclusion": "success"} for index, name in enumerate(T.STEPS[owner])]
                       if selected else []})
    add("Select exact candidate tasks", "plan", True)
    for owner, label in T.LABELS.items():
        add(label, owner, owners[owner])
    add("npm (browser-client)", "npm", owners["npm"])
    add("CodeQL (python)", "codeql", owners["codeql"])
    add("Candidate execution receipt", "receipt", True)
    result.append({"id": 2000, "run_id": 123, "run_attempt": 1,
        "head_sha": context()["head"], "name": "required-ci", "status": "in_progress",
        "conclusion": None, "steps": []})
    return result


class NativeTests(unittest.TestCase):
    def verify_run(self, value=None, c=None):
        c = context() if c is None else c
        return T.validate_run(run() if value is None else value, c, workflow_id=456,
            controller=c["controller"], execution_event="pull_request")

    def test_head_is_pr_head_not_synthetic_merge_and_lifecycle_may_run(self):
        self.assertEqual(self.verify_run()["head_sha"], context()["head"])
        c = context(); c["original_merge"] = "7" * 40
        self.verify_run(c=c)  # M is independently authenticated by the receipt.
        wrong = run(); wrong["head_sha"] = context()["original_merge"]
        with self.assertRaises(T.TransportError):
            self.verify_run(wrong)

    def test_foreign_or_stale_run_and_workflow_are_rejected(self):
        for key, value in (("id", 124), ("run_attempt", 2), ("workflow_id", 457),
            ("path", ".github/workflows/project-tests.yml"), ("head_branch", "other"),
            ("event", "push"), ("url", "https://example.invalid/run")):
            candidate = run(); candidate[key] = value
            with self.subTest(key=key), self.assertRaises(T.TransportError):
                self.verify_run(candidate)
        candidate = run(); candidate["head_repository"]["id"] += 1
        with self.assertRaises(T.TransportError):
            self.verify_run(candidate)

    def test_present_pr_associations_are_exact_but_absence_has_no_authority(self):
        candidate = run(); candidate["pull_requests"] = []
        self.verify_run(candidate)
        for side in ("base", "head"):
            candidate = run(); candidate["pull_requests"][0][side]["sha"] = "8" * 40
            with self.subTest(side=side), self.assertRaises(T.TransportError):
                self.verify_run(candidate)
        candidate = run(); candidate["pull_requests"][0]["number"] = 43
        with self.assertRaises(T.TransportError):
            self.verify_run(candidate)

    def test_manual_bootstrap_is_the_explicit_reviewed_head(self):
        c = context(); c["controller"] = c["head"]
        candidate = run(); candidate["event"] = "workflow_dispatch"; candidate["pull_requests"] = []
        T.validate_run(candidate, c, workflow_id=456, controller=c["head"], execution_event="workflow_dispatch")
        with self.assertRaises(T.TransportError):
            T.validate_run(candidate, context(), workflow_id=456, controller="6" * 40,
                           execution_event="workflow_dispatch")

    def test_full_controller_inventory_including_new_modules_is_exact(self):
        paths = [T.WORKFLOW, ".github/pr-ci-suites.json", ".github/pr-ci-dependencies.json"]
        paths += ["tools/repository-checks/pr_ci" + suffix + ".py"
                  for suffix in ("", "_context", "_plan", "_run", "_observer", "_transport")]
        trusted = {path: {"mode": "100644", "type": "blob", "sha": "a" * 40} for path in paths}
        actual = deepcopy(trusted); actual["libraries/product.cpp"] = {"sha": "b" * 40}
        self.assertTrue(T.validate_sources(actual, trusted))
        for operation in ("workflow", "new-module", "missing", "symlink"):
            actual = deepcopy(trusted)
            if operation == "workflow": actual[T.WORKFLOW]["sha"] = "b" * 40
            elif operation == "new-module": actual["tools/repository-checks/shadow.py"] = trusted[T.WORKFLOW]
            elif operation == "missing": del actual[T.WORKFLOW]
            else: actual[T.WORKFLOW]["mode"] = "120000"
            with self.subTest(operation=operation), self.assertRaises(T.TransportError):
                T.validate_sources(actual, trusted)

    def setUp(self):
        self.owners = {name: name in {"policy", "host", "npm", "codeql"} for name in T.OWNERS}
        self.plan = {"npm_projects": ["browser-client"], "codeql_languages": ["python"]}

    def verify_jobs(self, values):
        return T.validate_jobs(values, self.owners, plan=self.plan, context=context())

    def test_producer_success_does_not_wait_for_observer_or_whole_lifecycle(self):
        self.assertTrue(self.verify_jobs(jobs(self.owners)))
        values = jobs(self.owners)
        values[-1].update(name="Execution observer has no acceptance authority",
                          status="completed", conclusion="skipped")
        self.assertTrue(self.verify_jobs(values))

    def test_pending_is_distinct_and_known_failures_remain_fatal(self):
        values = jobs(self.owners); values[-2].update(status="in_progress", conclusion=None, steps=[])
        with self.assertRaises(T.Pending): self.verify_jobs(values)
        values[1]["conclusion"] = "failure"
        with self.assertRaises(T.TransportError) as error: self.verify_jobs(values)
        self.assertNotIsInstance(error.exception, T.Pending)

    def test_missing_required_command_cannot_be_replaced_by_success_json(self):
        values = jobs(self.owners); values[-2]["steps"] = []
        with self.assertRaises(T.TransportError): self.verify_jobs(values)
        values = jobs(self.owners); values[2]["steps"][0]["conclusion"] = "skipped"
        with self.assertRaises(T.TransportError): self.verify_jobs(values)

    def test_matrix_is_exact_and_unselected_owners_cannot_execute(self):
        values = jobs(self.owners); values = [row for row in values if row["name"] != "CodeQL (python)"]
        with self.assertRaises(T.TransportError): self.verify_jobs(values)
        values = jobs(self.owners); values[3]["conclusion"] = "success"
        with self.assertRaises(T.TransportError): self.verify_jobs(values)
        values = jobs(self.owners); values.append({**values[0], "id": 3000, "name": "Forged owner"})
        with self.assertRaises(T.TransportError): self.verify_jobs(values)

    def test_job_run_attempt_head_and_duplicate_inventory_are_bound(self):
        for key, value in (("run_id", 999), ("run_attempt", 2), ("head_sha", "9" * 40)):
            values = jobs(self.owners)
            for row in values: row[key] = value
            with self.subTest(key=key), self.assertRaises(T.TransportError): self.verify_jobs(values)
        values = jobs(self.owners); values.append(deepcopy(values[0]))
        with self.assertRaises(T.TransportError): self.verify_jobs(values)


def archive(name="result.json", data=b'{"result":"success"}', extra=False):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as value:
        value.writestr(name, data)
        if extra: value.writestr("unexpected.txt", "untrusted")
    return stream.getvalue()


class FakeAPI:
    def __init__(self, metadata):
        self.metadata, self.calls = metadata, []
    def get(self, endpoint):
        self.calls.append(endpoint)
        return deepcopy(self.metadata)


class ArtifactTests(unittest.TestCase):
    def setUp(self):
        self.raw = archive()
        self.metadata = {"id": 321, "name": "pr-ci-123-1", "expired": False,
            "size_in_bytes": len(self.raw), "digest": "sha256:" + hashlib.sha256(self.raw).hexdigest(),
            "url": T.API_ROOT + "/actions/artifacts/321",
            "archive_download_url": T.API_ROOT + "/actions/artifacts/321/zip",
            "workflow_run": {"id": 123, "repository_id": T.C.REPOSITORY_ID,
                "head_repository_id": T.C.REPOSITORY_ID, "head_sha": context()["head"]}}

    def verify(self, raw=None, metadata=None, api=None):
        value = self.metadata if metadata is None else metadata
        with patch.object(T, "_download", return_value=self.raw if raw is None else raw):
            return T.read_artifact(FakeAPI(value) if api is None else api, value,
                expected_name="pr-ci-123-1", run_id=123, run_attempt=1, head_sha=context()["head"])

    def test_single_json_has_whole_zip_digest_and_direct_bookends(self):
        api = FakeAPI(self.metadata)
        self.assertEqual(self.verify(api=api), {"result": "success"})
        self.assertEqual(api.calls, ["actions/artifacts/321"] * 2)

    def test_source_name_expiration_size_and_digest_are_not_receipt_claims(self):
        for key, value in (("name", "pr-ci-123-2"), ("expired", True),
            ("size_in_bytes", len(self.raw) + 1), ("digest", "sha256:" + "0" * 64)):
            metadata = deepcopy(self.metadata); metadata[key] = value
            with self.subTest(key=key), self.assertRaises(T.TransportError): self.verify(metadata=metadata)
        metadata = deepcopy(self.metadata); metadata["workflow_run"]["head_sha"] = "9" * 40
        with self.assertRaises(T.TransportError): self.verify(metadata=metadata)

    def test_zip_member_traversal_extra_files_and_json_ambiguity_reject(self):
        for raw in (archive("../result.json"), archive(extra=True),
                    archive(data=b'{"a":1,"a":2}'), archive(data=b'{"a":NaN}'),
                    archive(data=b'[]'), b"not a ZIP"):
            metadata = deepcopy(self.metadata)
            metadata.update(size_in_bytes=len(raw), digest="sha256:" + hashlib.sha256(raw).hexdigest())
            with self.subTest(size=len(raw)), self.assertRaises(T.TransportError):
                self.verify(raw=raw, metadata=metadata)

    def test_native_artifact_rebound_before_or_after_download_rejects(self):
        api = FakeAPI(self.metadata); api.metadata = {**self.metadata, "name": "other"}
        with self.assertRaises(T.TransportError): self.verify(api=api)
        class Drift(FakeAPI):
            def get(self, endpoint):
                value = super().get(endpoint)
                if len(self.calls) == 2: value["digest"] = "sha256:" + "1" * 64
                return value
        with self.assertRaises(T.TransportError): self.verify(api=Drift(self.metadata))

    def test_encrypted_and_symlink_members_reject(self):
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w") as value:
            info = zipfile.ZipInfo("result.json"); info.create_system = 3
            info.external_attr = (stat.S_IFLNK | 0o777) << 16
            value.writestr(info, "elsewhere")
        raw = stream.getvalue(); metadata = deepcopy(self.metadata)
        metadata.update(size_in_bytes=len(raw), digest="sha256:" + hashlib.sha256(raw).hexdigest())
        with self.assertRaises(T.TransportError): self.verify(raw=raw, metadata=metadata)

    def test_download_strips_token_before_signed_blob_redirect(self):
        requests = []
        target = "https://productionresultssa1.blob.core.windows.net/results/archive?sig=private"
        raw = self.raw
        class Response(io.BytesIO):
            status = 200
            def geturl(self): return target
        class Opener:
            def open(self, request, timeout):
                requests.append(request)
                if len(requests) == 1:
                    raise urllib.error.HTTPError(request.full_url, 302, "Found", {"Location": target}, io.BytesIO())
                return Response(raw)
        with patch.dict(os.environ, {"GH_TOKEN": "dummy-not-a-secret"}), \
             patch.object(T.urllib.request, "build_opener", return_value=Opener()):
            self.assertEqual(T._download(FakeAPI(self.metadata), 321), self.raw)
        self.assertEqual(requests[0].get_header("Authorization"), "Bearer dummy-not-a-secret")
        self.assertIsNone(requests[1].get_header("Authorization"))
        self.assertIsNone(requests[1].get_header("Cookie"))

    def test_redirect_cannot_escape_github_storage_or_carry_credentials(self):
        for url in ("http://productionresultssa1.blob.core.windows.net/x", "https://evil.invalid/x",
                    "https://user:secret@productionresultssa1.blob.core.windows.net/x",
                    "https://productionresultssa1.blob.core.windows.net:444/x",
                    "https://productionresultssa1.blob.core.windows.net/x#fragment"):
            with self.subTest(url=url), self.assertRaises(T.TransportError): T._signed_url(url)


if __name__ == "__main__":
    unittest.main()
