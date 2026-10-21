#!/usr/bin/env python3
"""Regenerated merges must not hide changed inputs or bypass selected checks."""
from copy import deepcopy
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("pr_ci_context", ROOT / "tools/repository-checks/pr_ci_context.py")
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.b, self.h, self.m, self.new, self.t = (c * 40 for c in "12345")
        repo = {"full_name": C.REPOSITORY, "id": C.REPOSITORY_ID}
        self.pr = {"number": 23, "state": "open",
                   "base": {"ref": "apple-ios", "sha": self.b, "repo": repo},
                   "head": {"ref": "fix/ios/input", "sha": self.h, "repo": repo}}
        self.data = {"": repo, "pulls/23": self.pr,
                     "branches/apple-ios": {"name": "apple-ios", "protected": True,
                                             "commit": {"sha": self.b}},
                     "git/ref/heads/fix%2Fios%2Finput": {"ref": "refs/heads/fix/ios/input",
                                                        "object": {"type": "commit", "sha": self.h}},
                     "commits/refs/pull/23/merge": {"sha": self.m}}
        for oid in (self.m, self.new):
            self.data["git/commits/" + oid] = {"sha": oid, "tree": {"sha": self.t},
                                               "parents": [{"sha": self.b}, {"sha": self.h}]}
        self.api = type("API", (), {"get": lambda _, endpoint: deepcopy(self.data[endpoint])})()

    def test_regenerated_merge_keeps_original_execution_identity(self):
        planned = C.capture(self.api, 23, event_pr=self.pr)
        self.data["commits/refs/pull/23/merge"]["sha"] = self.new
        observed = C.bookend(self.api, planned)
        self.assertEqual(observed["original_merge"], self.m)
        self.assertEqual(observed["observed_merge"], self.new)
        self.assertEqual(observed["tree"], self.t)

    def test_equivalent_tree_with_different_or_reordered_parents_is_rejected(self):
        planned = C.capture(self.api, 23)
        self.data["commits/refs/pull/23/merge"]["sha"] = self.new
        for parents in ([self.h, self.b], [self.b, "6" * 40], [self.b]):
            with self.subTest(parents=parents):
                self.data["git/commits/" + self.new]["parents"] = [{"sha": p} for p in parents]
                with self.assertRaises(C.ContextError):
                    C.bookend(self.api, planned)

    def test_changed_complete_tree_is_rejected(self):
        planned = C.capture(self.api, 23)
        self.data["commits/refs/pull/23/merge"]["sha"] = self.new
        self.data["git/commits/" + self.new]["tree"]["sha"] = "6" * 40
        with self.assertRaisesRegex(C.ContextError, "different content"):
            C.bookend(self.api, planned)

    def test_third_equivalent_reported_merge_is_authenticated_without_substitution(self):
        planned = C.capture(self.api, 23)
        third = "7" * 40
        commit = deepcopy(self.data["git/commits/" + self.new]); commit["sha"] = third
        self.data["git/commits/" + third] = commit
        self.data["commits/refs/pull/23/merge"]["sha"] = self.new
        self.data["pulls/23"]["merge_commit_sha"] = third
        observed = C.bookend(self.api, planned)
        self.assertEqual(observed["original_merge"], self.m)
        self.assertEqual(observed["reported_merge"], third)
        self.data["git/commits/" + third]["tree"]["sha"] = "6" * 40
        with self.assertRaises(C.ContextError):
            C.bookend(self.api, planned)
        self.data["git/commits/" + third] = commit
        self.data["git/commits/" + third]["parents"].reverse()
        with self.assertRaises(C.ContextError):
            C.bookend(self.api, planned)

    def test_branch_and_protection_changes_invalidate_results(self):
        original = deepcopy(self.data)
        for endpoint, field, value in (("branches/apple-ios", "protected", False),
                                       ("pulls/23", "state", "closed")):
            with self.subTest(endpoint=endpoint, field=field):
                self.data = deepcopy(original)
                planned = C.capture(self.api, 23)
                self.data[endpoint][field] = value
                with self.assertRaises(C.ContextError):
                    C.bookend(self.api, planned)
        self.data = deepcopy(original)
        planned = C.capture(self.api, 23)
        self.data["branches/apple-ios"]["commit"]["sha"] = "6" * 40
        with self.assertRaises(C.ContextError):
            C.bookend(self.api, planned)
        self.data = deepcopy(original)
        self.data["git/ref/heads/fix%2Fios%2Finput"]["object"]["sha"] = "6" * 40
        with self.assertRaises(C.ContextError):
            C.capture(self.api, 23)

    def test_foreign_repository_and_stale_trigger_are_rejected(self):
        event = deepcopy(self.pr)
        event["head"]["sha"] = "6" * 40
        with self.assertRaises(C.ContextError):
            C.capture(self.api, 23, event_pr=event)
        self.data["pulls/23"]["head"]["repo"]["id"] += 1
        with self.assertRaises(C.ContextError):
            C.capture(self.api, 23)


class CoverageTests(unittest.TestCase):
    def test_every_selected_owner_must_succeed_and_unselected_owner_must_skip(self):
        expected = {"host": True, "native": False, "codeql": True}
        good = {name: {"result": "success" if needed else "skipped"}
                for name, needed in expected.items()}
        self.assertTrue(C.require_jobs(good, expected))
        for name in expected:
            for result in ("failure", "cancelled", "skipped", "success", None):
                if result == good[name]["result"]:
                    continue
                with self.subTest(name=name, result=result):
                    bad = deepcopy(good); bad[name]["result"] = result
                    with self.assertRaises(C.ContextError):
                        C.require_jobs(bad, expected)
        for bad in ({}, {**good, "unplanned": {"result": "success"}}):
            with self.assertRaises(C.ContextError):
                C.require_jobs(bad, expected)


if __name__ == "__main__":
    unittest.main()
