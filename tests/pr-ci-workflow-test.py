#!/usr/bin/env python3
"""Offline contracts for central CI ownership and the protected observer.

These checks inspect real workflow data. They do not execute actions, contact
GitHub, qualify a candidate, or replace the first genuine manual bootstrap.
"""
from copy import deepcopy
import hashlib
from pathlib import Path
import re
import unittest

import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github/workflows"
CHECKOUT = "actions/checkout@3d3c42e5aac5ba805825da76410c181273ba90b1"
UPLOAD = "actions/upload-artifact@b7c566a772e6b6bfb58ed0dc250532a479d7789f"
CODEQL = "cdf488f595d80d6e07e03d4674febd5ab45fa938"
IMAGE = "ubuntu@sha256:4fbb8e6a8395de5a7550b33509421a2bafbc0aab6c06ba2cef9ebffbc7092d90"
OWNERS = {"policy", "host", "npm", "native", "codeql", "security", "android", "ios"}


def load(name):
    value = yaml.safe_load((WORKFLOWS / name).read_text())
    # PyYAML's YAML 1.1 resolver calls the Actions `on` key True.
    if True in value:
        value["on"] = value.pop(True)
    return value


def checkouts(job):
    return [step["with"] for step in job.get("steps", []) if step.get("uses") == CHECKOUT]


def scripts(job):
    return "\n".join(step.get("run", "") for step in job.get("steps", []))


def observer_contract(job):
    assert job["name"] == "${{ github.event_name == 'pull_request' && 'Execution observer has no acceptance authority' || 'required-ci' }}"
    assert job["needs"] == "ci-execution"
    condition = job["if"]
    assert "always()" in condition and "pull_request_target" in condition
    assert "workflow_dispatch" in condition and "!github.event.pull_request.draft" in condition
    assert all(permission == "read" for permission in job["permissions"].values())
    assert len(checkouts(job)) == 1
    checkout = checkouts(job)[0]
    assert checkout["path"] == "trusted" and checkout["persist-credentials"] is False
    assert checkout["ref"] == "${{ github.event_name == 'workflow_dispatch' && github.sha || github.workflow_sha }}"
    command = scripts(job)
    assert "trusted/tools/repository-checks/pr_ci.py gate" in command
    assert not re.search(r"\b(?:candidate|execute|platform|verify-native)\b", command)
    assert "git -C trusted rev-parse HEAD" in command


def owners_contract(workflow):
    jobs = workflow["jobs"]
    assert set(jobs["ci-execution"]["needs"]) == OWNERS | {"plan"}
    assert jobs["policy"]["needs"] == "plan"
    for owner in OWNERS - {"policy"}:
        assert set(jobs[owner]["needs"]) == {"plan", "policy"}
        condition = jobs[owner]["if"]
        assert "needs.plan.outputs.active == 'true'" in condition
        assert "needs.plan.outputs." + owner + " == 'true'" in condition


def source_contract(job):
    for checkout in checkouts(job):
        assert checkout["persist-credentials"] is False
        assert checkout["path"] in {"trusted", "candidate"}
        if checkout["path"] == "trusted":
            assert checkout["ref"] == "${{ needs.plan.outputs.controller }}"
        else:
            assert checkout["ref"] == "${{ needs.plan.outputs.source }}"
            assert checkout["fetch-depth"] == 2


def native_recipe_contract(caller, workflow):
    assert caller["with"] == {"mode": "${{ needs.plan.outputs.native_mode }}"}
    assert "github.event_name == 'pull_request'" in caller["if"]
    assert workflow["on"]["workflow_call"]["inputs"] == {"mode": {"type": "string", "required": True}}
    job = workflow["jobs"]["build"]
    candidate, trusted = checkouts(job)
    # Ordinary PR checkout remains GitHub's original merge source. A manual
    # workflow's H is different, so that execution path is deliberately excluded.
    assert "ref" not in candidate and "path" not in candidate
    assert candidate["fetch-depth"] == 2 and candidate["persist-credentials"] is False
    assert trusted["ref"] == "${{ github.event.repository.default_branch }}"
    assert trusted["path"] == "trusted" and trusted["persist-credentials"] is False
    recheck = next(step for step in job["steps"] if step["name"] == "Recheck exact candidate selection")
    assert "if" not in recheck
    assert recheck["env"]["EXPECTED_MODE"] == "${{ inputs.mode }}"
    assert 'trusted/tools/native-tests/check.py plan --candidate .' in recheck["run"]
    assert '--event "$GITHUB_EVENT_PATH" --sha "$GITHUB_SHA"' in recheck["run"]
    assert 'in ("core", "full")' in recheck["run"]


class WorkflowContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = load("repository-checks.yml")
        cls.jobs = cls.workflow["jobs"]
        cls.native = load("native-tests.yml")

    def test_initial_rollout_is_main_only_and_manual_bootstrap_is_explicit(self):
        events = self.workflow["on"]
        self.assertEqual({"pull_request", "pull_request_target", "workflow_dispatch"}, set(events))
        expected = {"opened", "reopened", "synchronize", "ready_for_review", "edited"}
        for event in ("pull_request", "pull_request_target"):
            self.assertEqual(["main"], events[event]["branches"])
            self.assertEqual(expected, set(events[event]["types"]))
        self.assertEqual({"type": "string", "required": True,
            "description": "Open pull request to qualify with this reviewed controller"},
            events["workflow_dispatch"]["inputs"]["pr_number"])
        self.assertIn("run_regression", events["workflow_dispatch"]["inputs"])
        initial = checkouts(self.jobs["plan"])[0]
        self.assertEqual("${{ github.event_name == 'workflow_dispatch' && github.sha || github.event.repository.default_branch }}", initial["ref"])
        bootstrap = next(step for step in self.jobs["plan"]["steps"] if step.get("id") == "bootstrap")
        self.assertIn("test -f trusted/tools/repository-checks/pr_ci.py", bootstrap["run"])
        self.assertIn("active=false", bootstrap["run"])
        self.assertNotIn("exit 1", bootstrap["run"])

    def test_drafts_and_metadata_edits_do_not_start_workers(self):
        condition = self.jobs["plan"]["if"]
        for clause in ("github.event_name != 'pull_request_target'",
                "!github.event.pull_request.draft", "github.event.action == 'edited'",
                "!github.event.changes.base"):
            self.assertIn(clause, condition)
        self.assertIn("github.event_name", self.workflow["concurrency"]["group"])
        self.assertIn("github.run_id", self.workflow["concurrency"]["group"])

    def test_context_and_plan_outputs_are_explicit_cli_transports(self):
        outputs = self.jobs["plan"]["outputs"]
        self.assertTrue({"active", "context_json", "controller", "source", "base", "head",
            "tree", "target", "plan_json", "native_mode", "npm_projects",
            "codeql_languages", "full_host", "setup_json", *(OWNERS - {"policy"})} <= set(outputs))
        steps = {step.get("id"): step for step in self.jobs["plan"]["steps"]}
        self.assertIn("--event-name \"$GITHUB_EVENT_NAME\"", steps["context"]["run"])
        self.assertIn("--controller \"$controller\"", steps["context"]["run"])
        self.assertIn("--context context.json --candidate candidate", steps["plan"]["run"])
        candidate = checkouts(self.jobs["plan"])[1]
        self.assertEqual("${{ steps.context.outputs.source }}", candidate["ref"])
        self.assertFalse(candidate["persist-credentials"])

    def test_every_selected_owner_requires_policy_and_failed_owners_reach_receipt(self):
        owners_contract(self.workflow)
        receipt = self.jobs["ci-execution"]
        self.assertIn("always()", receipt["if"])
        self.assertIn("needs.plan.outputs.active == 'true'", receipt["if"])
        command = scripts(receipt)
        self.assertIn("pr_ci.py complete", command)
        self.assertIn('--needs-json "$OWNER_RESULTS"', command)
        self.assertEqual("${{ toJSON(needs) }}", next(step for step in receipt["steps"] if "run" in step)["env"]["OWNER_RESULTS"])
        for mutation in ("missing-owner", "unconditional-owner", "policy-cycle"):
            changed = deepcopy(self.workflow)
            if mutation == "missing-owner":
                changed["jobs"]["ci-execution"]["needs"].remove("native")
            elif mutation == "unconditional-owner":
                changed["jobs"]["host"]["if"] = "always()"
            else:
                changed["jobs"]["policy"]["needs"] = ["plan", "host"]
            with self.subTest(mutation=mutation), self.assertRaises(AssertionError):
                owners_contract(changed)

    def test_downstream_controller_and_candidate_are_distinct_immutable_sources(self):
        for name in OWNERS | {"ci-execution"}:
            if name != "native":
                with self.subTest(job=name):
                    source_contract(self.jobs[name])
        changed = deepcopy(self.jobs["host"])
        next(step for step in changed["steps"] if step.get("with", {}).get("path") == "trusted")["with"]["ref"] = "${{ github.event.pull_request.head.sha }}"
        with self.assertRaises(AssertionError):
            source_contract(changed)

    def test_only_codeql_upload_gets_write_permission_and_no_secrets_are_forwarded(self):
        self.assertEqual({"contents": "read"}, self.workflow["permissions"])
        for name, job in self.jobs.items():
            for scope, permission in job.get("permissions", {}).items():
                self.assertTrue(permission == "read" or (name == "codeql" and scope == "security-events" and permission == "write"), (name, scope, permission))
        text = (WORKFLOWS / "repository-checks.yml").read_text()
        self.assertNotIn("secrets.", text)
        for name in ("host", "npm"):
            steps = [step for step in self.jobs[name]["steps"] if "pr_ci.py execute" in step.get("run", "")]
            self.assertEqual(1, len(steps))
            self.assertNotIn("GH_TOKEN", steps[0].get("env", {}))
            self.assertIn("--candidate candidate", steps[0]["run"])
            self.assertNotIn("GITHUB_TOKEN", steps[0].get("env", {}))
            self.assertFalse(any("actions/cache" in step.get("uses", "") for step in self.jobs[name]["steps"]))

    def test_host_and_npm_prepare_fixed_runtime_without_candidate_requirements(self):
        for name in ("host", "npm"):
            job = self.jobs[name]
            command = scripts(job)
            self.assertIn("sudo apt-get install --no-install-recommends -y bubblewrap", command)
            self.assertIn("unshare --user --map-root-user --net /usr/bin/true", command)
            self.assertNotIn("docker ", command)
            python = next(step for step in job["steps"] if step.get("uses", "").startswith("actions/setup-python@"))
            node = next(step for step in job["steps"] if step.get("uses", "").startswith("actions/setup-node@"))
            self.assertEqual("3.12.15", python["with"]["python-version"])
            self.assertEqual("22.23.3", node["with"]["node-version"])
            self.assertIn('readlink -f "$(command -v node)"', command)
            self.assertNotRegex(command, r"(?:pip|python).*candidate/(?:tests/)?requirements")
            self.assertLess(command.index("install --no-install-recommends -y bubblewrap"), command.index("pr_ci.py execute"))
        host = scripts(self.jobs["host"])
        self.assertIn('venv "$RUNNER_TEMP/pr-ci-venv"', host)
        self.assertIn("trusted/tests/requirements-repository.txt", host)
        dependencies = next(step for step in self.jobs["host"]["steps"]
                            if step.get("name") == "Prepare Python dependencies from trusted requirements")
        self.assertEqual("${{ needs.plan.outputs.full_host }}", dependencies["env"]["FULL_HOST"])
        self.assertIn('if test "$FULL_HOST" = true; then', dependencies["run"])
        self.assertIn("requirements=trusted/tests/requirements-host.txt", dependencies["run"])
        pillow = next(step for step in self.jobs["host"]["steps"] if "Pillow==" in step.get("run", ""))
        self.assertIn("'pillow'", pillow["if"])
        self.assertIn("needs.plan.outputs.full_host != 'true'", pillow["if"])
        self.assertIn("trusted/tests/requirements-host.txt", pillow["run"])
        java = next(step for step in self.jobs["host"]["steps"] if step.get("uses", "").startswith("actions/setup-java@"))
        self.assertEqual("21", java["with"]["java-version"])
        self.assertEqual("needs.plan.outputs.full_host == 'true'", java["if"])
        prerequisites = next(step for step in self.jobs["host"]["steps"]
                             if step.get("name") == "Install complete host prerequisites")
        self.assertIn('test -x /usr/lib/qt6/bin/qmltestrunner', prerequisites["run"])

    def test_protected_observer_never_checks_out_or_executes_candidate(self):
        job = self.jobs["required-ci"]
        observer_contract(job)
        for mutation in ("candidate-checkout", "write-token", "wrong-controller", "execute", "skipped-required-context"):
            changed = deepcopy(job)
            if mutation == "candidate-checkout":
                changed["steps"].append({"uses": CHECKOUT, "with": {"path": "candidate"}})
            elif mutation == "write-token":
                changed["permissions"]["checks"] = "write"
            elif mutation == "wrong-controller":
                changed["steps"][0]["with"]["ref"] = "${{ github.event.pull_request.head.sha }}"
            elif mutation == "skipped-required-context":
                changed["name"] = "required-ci"
            else:
                changed["steps"][-1]["run"] += "\npython3 candidate/tests/check.py"
            with self.subTest(mutation=mutation), self.assertRaises(AssertionError):
                observer_contract(changed)

    def test_codeql_analyzes_original_merge_and_publishes_native_upload_identity(self):
        job = self.jobs["codeql"]
        steps = {step.get("id"): step for step in job["steps"]}
        self.assertEqual("github/codeql-action/init@" + CODEQL, steps["init"]["uses"])
        init = steps["init"]["with"]
        self.assertIn("codeql-bundle-v2.27.2", init["tools"])
        self.assertEqual("candidate", init["source-root"])
        self.assertEqual("./trusted/.github/codeql/codeql-config.yml", init["config-file"])
        self.assertEqual("none", init["build-mode"])
        analysis = steps["analyze"]["with"]
        self.assertEqual("candidate", analysis["checkout_path"])
        self.assertEqual("${{ needs.plan.outputs.source }}", analysis["sha"])
        self.assertEqual("refs/pull/${{ fromJSON(needs.plan.outputs.context_json).number }}/merge", analysis["ref"])
        self.assertEqual("/language:${{ matrix.language }}", analysis["category"])
        self.assertIs(analysis["wait-for-processing"], False)
        self.assertIn("pr_ci.py upload-proof", scripts(job))
        upload = next(step for step in job["steps"] if step.get("uses") == UPLOAD)
        self.assertEqual("codeql-upload-${{ github.run_id }}-${{ github.run_attempt }}-${{ matrix.language }}", upload["with"]["name"])
        self.assertEqual("error", upload["with"]["if-no-files-found"])
        self.assertIs(upload["with"]["overwrite"], False)

    def test_execution_receipt_artifact_is_per_original_run_and_attempt(self):
        job = self.jobs["ci-execution"]
        self.assertEqual(["trusted"], [row["path"] for row in checkouts(job)])
        upload = next(step for step in job["steps"] if step.get("uses") == UPLOAD)
        self.assertEqual("pr-ci-${{ github.run_id }}-${{ github.run_attempt }}", upload["with"]["name"])
        self.assertEqual("result.json", upload["with"]["path"])
        self.assertEqual("error", upload["with"]["if-no-files-found"])
        self.assertIs(upload["with"]["overwrite"], False)

    def test_original_native_recipe_continues_only_for_ordinary_pr_source(self):
        self.assertEqual("c277ebda3ce3d972ffce0c3849bf817c664feef90a0b6b90df9ee428a5e576b1",
            hashlib.sha256((WORKFLOWS / "native-tests.yml").read_bytes()).hexdigest())
        native_recipe_contract(self.jobs["native"], self.native)
        job = self.native["jobs"]["build"]
        self.assertNotIn("pr_ci.py verify-native", scripts(job))
        command = scripts(job)
        for required in ("conan install .", "--build=never --no-remote",
                "bash tools/native-tests/configure.sh", "trusted/tools/native-tests/select.py",
                "trusted/tools/native-tests/run.py", "--selection build/native-selection.json --jobs 2"):
            self.assertIn(required, command)
        cache = next(step for step in job["steps"] if step.get("id") == "compiler-cache")
        self.assertIn("${{ github.sha }}", cache["with"]["key"])
        for mutation in ("manual-native", "implicit-trusted-candidate", "new-input-envelope"):
            caller, workflow = deepcopy(self.jobs["native"]), deepcopy(self.native)
            if mutation == "manual-native":
                caller["if"] = "needs.plan.outputs.native == 'true'"
            elif mutation == "implicit-trusted-candidate":
                workflow["jobs"]["build"]["steps"][1]["with"]["ref"] = "${{ github.sha }}"
            else:
                caller["with"]["source_sha"] = "${{ needs.plan.outputs.source }}"
            with self.subTest(mutation=mutation), self.assertRaises(AssertionError):
                native_recipe_contract(caller, workflow)

    def test_selected_platforms_fail_closed_through_trusted_cli(self):
        for name in ("android", "ios"):
            command = scripts(self.jobs[name])
            self.assertIn("trusted/tools/repository-checks/pr_ci.py platform", command)
            self.assertIn("--lane " + name, command)
            self.assertNotIn("continue-on-error", self.jobs[name])
            self.assertNotIn("|| true", command)

    def test_static_scanners_read_candidate_data_with_trusted_configuration(self):
        command = scripts(self.jobs["security"])
        self.assertIn("trusted/tools/workflow-security/check-action-pins.py --root candidate", command)
        self.assertIn("-config-file trusted/.github/actionlint.yaml", command)
        self.assertIn("--offline --min-severity medium candidate/.github/workflows", command)
        self.assertIn("sha256sum --check --strict", command)
        self.assertNotIn("workflow-contract-test.py", command)
        self.assertNotRegex(command, r"(?:python3|bash)\s+candidate/")

    def test_old_pr_producers_are_retired_without_removing_manual_or_scheduled_work(self):
        for name in ("codeql.yml", "browser-client.yml", "browser-direct-client.yml",
                "dependency-releases.yml", "linux_server_build.yml"):
            with self.subTest(workflow=name):
                self.assertNotIn("pull_request", load(name)["on"])
        self.assertIn("workflow_dispatch", load("browser-client.yml")["on"])
        self.assertEqual({"workflow_dispatch"}, set(load("browser-direct-client.yml")["on"]))
        self.assertIn("schedule", load("codeql.yml")["on"])
        self.assertNotIn("main", load("codeql.yml")["on"]["push"]["branches"])
        self.assertIn("schedule", load("dependency-releases.yml")["on"])
        self.assertIn("workflow_dispatch", load("dependency-releases.yml")["on"])
        self.assertIn("tags", load("linux_server_build.yml")["on"]["push"])
        self.assertIn("pull_request", load("branch-policy.yml")["on"])
        self.assertIn("pull_request_target", load("sync-test-reuse.yml")["on"])
        for name in ("parent-qualification.yml", "documentation-push-owner.yml", "dependency-releases.yml"):
            with self.subTest(retired_main_push=name):
                self.assertNotIn("main", load(name)["on"]["push"]["branches"])

    def test_every_external_action_is_pinned_to_an_immutable_commit(self):
        for workflow in (self.workflow, self.native):
            for job in workflow["jobs"].values():
                for item in [job, *job.get("steps", [])]:
                    reference = item.get("uses")
                    if reference and not reference.startswith("./"):
                        self.assertRegex(reference, r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_./-]+@[0-9a-f]{40}$")


if __name__ == "__main__":
    unittest.main()
