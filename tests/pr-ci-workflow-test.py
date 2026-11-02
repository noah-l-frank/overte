#!/usr/bin/env python3
"""Offline contracts for central CI ownership and the protected observer.

These checks inspect real workflow data. They do not execute actions, contact
GitHub, qualify a candidate, or replace the first genuine manual bootstrap.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
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
    assert job["name"] == "${{ needs.plan.outputs.active == 'true' && 'required-ci' || 'Execution observer has no acceptance authority' }}"
    assert job["needs"] == ["plan", "ci-execution"]
    condition = job["if"]
    assert "always()" in condition and "pull_request'" in condition and "needs.plan.outputs.active == 'true'" in condition
    assert "workflow_dispatch" in condition and "!github.event.pull_request.draft" in condition
    assert all(permission == "read" for permission in job["permissions"].values())
    assert len(checkouts(job)) == 1
    checkout = checkouts(job)[0]
    assert checkout["path"] == "trusted" and checkout["persist-credentials"] is False
    assert checkout["ref"] == "${{ needs.plan.outputs.controller }}"
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


def android_runner_contract(workflow):
    jobs = workflow['jobs']
    expression = jobs['android']['runs-on']
    expected = ("${{ needs.plan.outputs.android_native_products != '[]' && "
                "fromJSON(format('[\"self-hosted\",\"Linux\",\"X64\",\"overte-native-large-disk\",\"overte-native-{0}-{1}\"]', "
                "github.run_id, github.run_attempt)) || 'ubuntu-24.04' }}")
    assert expression == expected
    # Route from the authenticated plan only after protected policy succeeds.
    assert set(jobs['android']['needs']) == {'plan', 'policy'}
    assert jobs['android']['if'] == "needs.plan.outputs.active == 'true' && needs.plan.outputs.android == 'true'"
    assert "github.event_name != 'pull_request_target'" in jobs['plan']['if']
    assert workflow['permissions'] == {'contents': 'read'}
    for name, job in jobs.items():
        if name != 'android' and 'runs-on' in job:
            assert job['runs-on'] == 'ubuntu-24.04'
    template = re.search(r"fromJSON\(format\('([^']+)'", expression)[1]
    return lambda products, run_id=123, attempt=2: json.loads(template.format(run_id, attempt)) if products != '[]' else 'ubuntu-24.04'


def native_recipe_contract(caller, workflow):
    fields = {"mode": "native_mode", "context_json": "context_json",
              "plan_json": "plan_json", "controller": "controller", "source": "source"}
    assert caller["with"] == {name: "${{ needs.plan.outputs." + output + " }}"
                              for name, output in fields.items()}
    assert "github.event_name == 'pull_request'" in caller["if"]
    assert workflow["on"]["workflow_call"]["inputs"] == {
        name: {"type": "string", "required": True} for name in fields}
    job = workflow["jobs"]["build"]
    candidate, trusted = checkouts(job)
    assert candidate["ref"] == "${{ inputs.source }}" and "path" not in candidate
    assert candidate["fetch-depth"] == 2 and candidate["persist-credentials"] is False
    assert trusted["ref"] == "${{ inputs.controller }}"
    assert trusted["path"] == "trusted" and trusted["persist-credentials"] is False
    assert set(trusted["sparse-checkout"].splitlines()) == {".github", "tools"}
    recheck = next(step for step in job["steps"] if step["name"] == "Recheck exact candidate selection")
    assert "if" not in recheck
    assert recheck["env"] == {"EXPECTED_MODE": "${{ inputs.mode }}",
        "PR_CI_SOURCE_REF": "${{ github.ref }}", "CONTEXT_JSON": "${{ inputs.context_json }}",
        "PLAN_JSON": "${{ inputs.plan_json }}"}
    assert 'trusted/tools/repository-checks/pr_ci.py verify-native' in recheck["run"]
    assert '--candidate . --context-json "$CONTEXT_JSON" --plan-json "$PLAN_JSON"' in recheck["run"]
    assert '--out build/native-plan.json' in recheck["run"]
    assert 'tools/native-tests/check.py plan' not in recheck["run"]


class WorkflowContracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = load("repository-checks.yml")
        cls.jobs = cls.workflow["jobs"]
        cls.native = load("native-tests.yml")

    def test_all_seven_targets_share_one_plan_and_manual_bootstrap_is_explicit(self):
        events = self.workflow["on"]
        self.assertEqual({"pull_request", "pull_request_target", "workflow_dispatch"}, set(events))
        expected = {"opened", "reopened", "synchronize", "ready_for_review", "edited"}
        for event in ("pull_request", "pull_request_target"):
            self.assertEqual({"main", "apple-main", "apple-ios", "android-main", "android-phone", "android-vr", "android-vr-pico"}, set(events[event]["branches"]))
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

    def test_only_selected_android_native_products_use_large_disk_runner(self):
        select = android_runner_contract(self.workflow)
        labels = yaml.safe_load((ROOT / '.github/actionlint.yaml').read_text())['self-hosted-runner']['labels']
        self.assertIn('overte-native-large-disk', labels)
        self.assertIn('overte-native-*-*', labels)
        for products in ('["common"]', '["phone"]', '["pico"]', '["common","phone"]'):
            with self.subTest(products=products):
                self.assertEqual(select(products), ['self-hosted', 'Linux', 'X64', 'overte-native-large-disk', 'overte-native-123-2'])
        self.assertNotEqual(select('["phone"]', 123, 2), select('["phone"]', 123, 3))
        self.assertNotEqual(select('["phone"]', 123, 2), select('["phone"]', 124, 2))
        # Java/resource and Groovy-only plans both have no native products.
        self.assertEqual(select('[]'), 'ubuntu-24.04')
        for mutation in ('java-routing', 'unconditional', 'missing-label', 'other-job', 'no-policy', 'pr-target', 'unbound-attempt'):
            changed = deepcopy(self.workflow)
            job = changed['jobs']['android']
            if mutation == 'java-routing':
                job['runs-on'] = job['runs-on'].replace('android_native_products', 'android_compile_products')
            elif mutation == 'unconditional':
                job['runs-on'] = ['self-hosted', 'Linux', 'X64', 'overte-native-large-disk']
            elif mutation == 'missing-label':
                job['runs-on'] = job['runs-on'].replace(',"overte-native-large-disk"', '')
            elif mutation == 'other-job':
                changed['jobs']['host']['runs-on'] = ['self-hosted', 'overte-native-large-disk']
            elif mutation == 'no-policy':
                job['needs'] = ['plan']
            elif mutation == 'unbound-attempt':
                job['runs-on'] = job['runs-on'].replace('github.run_attempt', '1')
            else:
                changed['jobs']['plan']['if'] = 'always()'
            with self.subTest(mutation=mutation), self.assertRaises(AssertionError):
                android_runner_contract(changed)

    def test_native_outputs_upload_is_mandatory_attempt_bound_and_runs_after_failure(self):
        def contract(workflow):
            job = workflow['jobs']['android']
            steps = job['steps']
            execute = next(step for step in steps if step['name'] == 'Require the selected Android product validation')
            assert execute['env']['PR_CI_ANDROID_NATIVE_EXPORT'] == '${{ runner.temp }}/pr-ci-android-export'
            assert '--out "$RUNNER_TEMP/pr-ci-android-result.json"' in execute['run']
            uploads = [step for step in steps if step.get('uses') == UPLOAD]
            assert len(uploads) == 1
            upload = uploads[0]
            assert steps.index(upload) > steps.index(execute)
            assert upload['if'] == "always() && needs.plan.outputs.android_native_products != '[]'"
            assert upload['with']['name'] == 'android-native-${{ github.run_id }}-${{ github.run_attempt }}-${{ needs.plan.outputs.target }}'
            assert upload['with']['path'].splitlines() == [
                '${{ runner.temp }}/pr-ci-android-export/', '${{ runner.temp }}/pr-ci-android-result.json']
            assert upload['with']['if-no-files-found'] == 'error'
            assert upload['with']['overwrite'] is False
            assert upload['with']['retention-days'] == 7
            assert 'continue-on-error' not in upload and 'continue-on-error' not in job
            assert 'android' in workflow['jobs']['ci-execution']['needs']
        contract(self.workflow)
        for mutation in ('success-only', 'optional', 'all-temp', 'no-result', 'no-export', 'no-final-owner'):
            changed = deepcopy(self.workflow)
            steps = changed['jobs']['android']['steps']
            upload = next(step for step in steps if step.get('uses') == UPLOAD)
            execute = next(step for step in steps if step['name'] == 'Require the selected Android product validation')
            if mutation == 'success-only':
                upload['if'] = "needs.plan.outputs.android_native_products != '[]'"
            elif mutation == 'optional':
                upload['continue-on-error'] = True
            elif mutation == 'all-temp':
                upload['with']['path'] = '${{ runner.temp }}/'
            elif mutation == 'no-result':
                execute['run'] = execute['run'].replace('--out "$RUNNER_TEMP/pr-ci-android-result.json"', '')
            elif mutation == 'no-export':
                del execute['env']['PR_CI_ANDROID_NATIVE_EXPORT']
            else:
                changed['jobs']['ci-execution']['needs'].remove('android')
            with self.subTest(mutation=mutation), self.assertRaises((AssertionError, KeyError)):
                contract(changed)

    def test_groovy_contract_transport_is_conditional_and_cannot_poison_native_cache(self):
        def contract(workflow):
            steps = workflow['jobs']['android']['steps']
            transports = {}
            for name, flag in (('groovy', "needs.plan.outputs.android_groovy_contracts == 'true'"),
                               ('native', "needs.plan.outputs.android_native_products != '[]'")):
                restore = next(step for step in steps if step.get('id') == 'android-' + name + '-cache')
                assert restore['if'] == flag
                path, key = restore['with']['path'], restore['with']['key']
                assert path == '${{ runner.temp }}/pr-ci-android-' + name + '-cache'
                assert key.startswith('pr-ci-android-' + name + '-v1-')
                save = next(step for step in steps if '/save@' in step.get('uses', '')
                            and step.get('with', {}).get('path') == path)
                assert save['with']['key'] == key
                assert save['if'].startswith(flag + ' && ')
                preparations = [step for step in steps if 'pr_ci_android_native.py' in step.get('run', '')
                                and '--capacity-only' not in step['run']
                                and '--cache "$RUNNER_TEMP/pr-ci-android-' + name + '-cache"' in step['run']]
                assert len(preparations) == 1
                assert preparations[0]['if'] == flag
                assert ('--groovy-only' in preparations[0]['run']) == (name == 'groovy')
                transports[name] = (path, key)
            assert all(left != right for left, right in zip(transports['groovy'], transports['native']))
        contract(self.workflow)
        for mutation in ('shared-cache', 'shared-key', 'unconditional-prepare', 'native-prepare'):
            changed = deepcopy(self.workflow)
            steps = changed['jobs']['android']['steps']
            restore = next(step for step in steps if step.get('id') == 'android-groovy-cache')
            prepare = next(step for step in steps if '--groovy-only' in step.get('run', ''))
            if mutation == 'shared-cache':
                restore['with']['path'] = '${{ runner.temp }}/pr-ci-android-native-cache'
            elif mutation == 'shared-key':
                restore['with']['key'] = next(step for step in steps if step.get('id') == 'android-native-cache')['with']['key']
            elif mutation == 'unconditional-prepare':
                prepare['if'] = 'always()'
            else:
                prepare['run'] = prepare['run'].replace('--groovy-only ', '')
            with self.subTest(mutation=mutation), self.assertRaises(AssertionError):
                contract(changed)

    def test_native_capacity_precedes_every_dependency_setup_and_is_native_only(self):
        def contract(workflow):
            steps = workflow['jobs']['android']['steps']
            admissions = [(index, step) for index, step in enumerate(steps)
                          if '--capacity-only' in step.get('run', '')]
            assert len(admissions) == 1
            index, admission = admissions[0]
            assert admission['if'] == "needs.plan.outputs.android_native_products != '[]'"
            assert 'trusted/tools/repository-checks/pr_ci_android_native.py' in admission['run']
            assert '--groovy-only' not in admission['run']
            assert 'candidate/' not in admission['run']
            trusted = next(position for position, step in enumerate(steps)
                           if step.get('with', {}).get('path') == 'trusted')
            assert trusted < index
            expensive = [position for position, step in enumerate(steps)
                         if position != index and (
                             step.get('uses', '').startswith(('actions/setup-', 'actions/cache/'))
                             or re.search(r'\bapt-get\b|\s-m pip\s|pr_ci_android_native\.py',
                                          step.get('run', '')))]
            assert expensive and all(index < position for position in expensive)
        contract(self.workflow)
        for mutation in ('after-apt', 'unconditional', 'groovy-only'):
            changed = deepcopy(self.workflow)
            steps = changed['jobs']['android']['steps']
            admission = next(step for step in steps if '--capacity-only' in step.get('run', ''))
            if mutation == 'after-apt':
                steps.remove(admission)
                apt = next(index for index, step in enumerate(steps) if 'apt-get install' in step.get('run', ''))
                steps.insert(apt + 1, admission)
            elif mutation == 'unconditional':
                admission['if'] = 'always()'
            else:
                admission['if'] = "needs.plan.outputs.android_groovy_contracts == 'true'"
            with self.subTest(mutation=mutation), self.assertRaises(AssertionError):
                contract(changed)

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
                self.assertTrue(permission == "read" or ((name == "codeql" and scope == "security-events" or name == "ios" and scope == "actions") and permission == "write"), (name, scope, permission))
        text = (WORKFLOWS / "repository-checks.yml").read_text()
        self.assertNotIn("secrets.", text)
        for name in ("host", "npm"):
            steps = [step for step in self.jobs[name]["steps"] if "pr_ci.py execute" in step.get("run", "")]
            self.assertEqual(1, len(steps))
            self.assertEqual("${{ github.token }}", steps[0].get("env", {}).get("GH_TOKEN"))
            self.assertTrue(all(value == 'read' for value in self.jobs[name]['permissions'].values()))
            self.assertIn("--candidate candidate", steps[0]["run"])
            self.assertNotIn("GITHUB_TOKEN", steps[0].get("env", {}))
            self.assertFalse(any("actions/cache" in step.get("uses", "") for step in self.jobs[name]["steps"]))

    def test_host_and_npm_prepare_fixed_runtime_without_candidate_requirements(self):
        for name in ("host", "npm"):
            job = self.jobs[name]
            command = scripts(job)
            self.assertIn("sudo apt-get install --no-install-recommends -y bubblewrap", command)
            self.assertIn("unshare --user --map-root-user --net /usr/bin/true", command)
            if name == 'host':
                self.assertNotIn("docker ", command)
            else:
                browser = next(step for step in job['steps'] if step.get('id') == 'browser')
                self.assertIn('needs.plan.outputs.browser_projects', browser['if'])
                self.assertIn('matrix.project', browser['if'])
                self.assertIn('docker pull ' + IMAGE, browser['run'])
                self.assertNotIn('candidate/', browser['run'])
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

    def test_fast_source_policy_uses_only_protected_source_and_no_dependencies(self):
        job = self.jobs["source-policy"]
        self.assertNotIn("needs", job)
        self.assertEqual("github.event_name == 'pull_request_target' && !github.event.pull_request.draft", job["if"])
        self.assertEqual("${{ github.event_name == 'pull_request_target' && 'source-policy' || 'Source policy not applicable' }}", job["name"])
        self.assertEqual([{"ref": "${{ github.workflow_sha }}", "path": "trusted", "persist-credentials": False}], checkouts(job))
        self.assertTrue(all(value == "read" for value in job["permissions"].values()))
        self.assertIn("pr_ci.py source-policy", scripts(job))
        self.assertNotIn(" candidate/", scripts(job))

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

    def test_native_recipe_recomputes_central_contract_only_for_ordinary_pr_source(self):
        native_recipe_contract(self.jobs["native"], self.native)
        job = self.native["jobs"]["build"]
        self.assertIn("pr_ci.py verify-native", scripts(job))
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
        self.assertEqual("./.github/workflows/pr-ci-ios.yml", self.jobs["ios"]["uses"])
        product = load("pr-ci-ios.yml")
        self.assertEqual({"workflow_call"}, set(product["on"]))
        self.assertEqual("inputs.build_required", product["jobs"]["qt"]["if"])
        self.assertEqual("inputs.build_required", product["jobs"]["client"]["if"])
        self.assertIn("pr_ci.py verify-ios", scripts(product["jobs"]["verify"]))
        self.assertEqual("${{ inputs.source }}", product["jobs"]["client"]["with"]["validated_host_contracts_sha"])
        for name in ("android", "ios"):
            job = self.jobs[name] if name == "android" else product["jobs"]["host"]
            command = scripts(job)
            self.assertIn("trusted/tools/repository-checks/pr_ci.py platform", command)
            self.assertIn("--lane " + name, command)
            self.assertNotIn("continue-on-error", self.jobs[name])
            self.assertNotIn("|| true", command)

    def test_ios_browser_runtime_reaches_the_offline_product_boundary(self):
        host = load("pr-ci-ios.yml")["jobs"]["host"]
        prepare = next(step for step in host["steps"]
                       if step["name"] == "Prepare pinned Chromium for offline iOS DOM contracts")
        command = prepare["run"]
        self.assertEqual("${{ runner.temp }}/pr-ci-ios-browser/runtime",
                         prepare["env"]["PLAYWRIGHT_BROWSERS_PATH"])
        self.assertIn("--ignore-scripts --package=playwright@1.63.0", command)
        self.assertIn("playwright install --with-deps --only-shell chromium", command)
        self.assertIn('test "${#browsers[@]}" = 1', command)
        self.assertIn('test -x "${browsers[0]}"', command)
        self.assertIn('ldd "${browsers[0]}"', command)
        self.assertIn("not found", command)
        self.assertIn('ln -s "${browsers[0]}" "$RUNNER_TEMP/pr-ci-ios-browser/bin/chrome-headless-shell"', command)
        execute = next(step["run"] for step in host["steps"]
                       if "pr_ci.py platform" in step.get("run", ""))
        self.assertIn('--prepared-root "$RUNNER_TEMP/pr-ci-ios-browser"', execute)
        self.assertNotIn("--network", execute)
        self.assertNotIn("continue-on-error", host)

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
        self.assertNotIn("push", load("codeql.yml")["on"])
        self.assertIn("schedule", load("dependency-releases.yml")["on"])
        self.assertIn("workflow_dispatch", load("dependency-releases.yml")["on"])
        self.assertIn("tags", load("linux_server_build.yml")["on"]["push"])
        self.assertNotIn("pull_request", load("branch-policy.yml")["on"])
        self.assertNotIn("pull_request_target", load("sync-test-reuse.yml")["on"])
        for name in ("parent-qualification.yml", "documentation-push-owner.yml", "dependency-releases.yml"):
            with self.subTest(retired_main_push=name):
                self.assertNotIn("push", load(name).get("on", {}))

    def test_retired_product_workflows_cannot_restart_parallel_automatic_owners(self):
        for name in ("android-tests.yml", "android-vr-tests.yml", "ios-build-qualification.yml", "ios-bootstrap.yml"):
            if not (WORKFLOWS / name).exists():
                continue
            events = load(name)["on"]
            with self.subTest(workflow=name):
                self.assertFalse({"pull_request", "pull_request_target", "push"} & set(events))
                self.assertIn("workflow_dispatch", events)

    def test_every_external_action_is_pinned_to_an_immutable_commit(self):
        for workflow in (self.workflow, self.native):
            for job in workflow["jobs"].values():
                for item in [job, *job.get("steps", [])]:
                    reference = item.get("uses")
                    if reference and not reference.startswith("./"):
                        self.assertRegex(reference, r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_./-]+@[0-9a-f]{40}$")

    def test_required_rule_templates_match_the_active_central_context_contract(self):
        expected = {'permanent-branches.json': {'source-policy', 'required-ci'},
                    'apple-target-branches.json': {'Enforce apple-main sync path'},
                    'android-target-branches.json': {'Enforce Android parent sync path'}}
        for filename, contexts in expected.items():
            manifest = json.loads((ROOT / '.github/rulesets' / filename).read_text())
            rules = [r['parameters'] for r in manifest['rules'] if r['type'] == 'required_status_checks']
            self.assertEqual(1, len(rules))
            self.assertEqual(contexts, {r['context'] for r in rules[0]['required_status_checks']})
            self.assertTrue(rules[0]['strict_required_status_checks_policy'])
            self.assertTrue(all(r['integration_id'] == 15368 for r in rules[0]['required_status_checks']))

    def test_selected_task_receipts_are_uploaded_and_bound_to_the_current_attempt(self):
        for owner in ('host', 'npm'):
            job = self.jobs[owner]
            execution = next(s for s in job['steps'] if 'pr_ci.py execute' in s.get('run', ''))
            self.assertIn('--out tasks.json', execution['run'])
            upload = next(s for s in job['steps'] if s.get('uses') == UPLOAD)
            self.assertEqual('tasks.json', upload['with']['path'])
            self.assertFalse(upload['with']['overwrite'])
            self.assertEqual(14, upload['with']['retention-days'])
        self.assertIn('github.run_attempt', next(s for s in self.jobs['host']['steps']
            if s.get('uses') == UPLOAD)['with']['name'])

    def test_android_runtime_is_prepared_only_for_selected_real_api_compilation(self):
        job = self.jobs['android']
        prepare = next(s for s in job['steps'] if 'pr_ci_android.py prepare' in s.get('run', ''))
        self.assertEqual("needs.plan.outputs.android_compile_products != '[]'", prepare['if'])
        self.assertIn('trusted/tools/repository-checks/pr_ci_android.py', prepare['run'])
        self.assertIn('platforms;android-36', prepare['run'])
        self.assertIn('build-tools;36.0.0', prepare['run'])
        execute = next(s for s in job['steps'] if 'pr_ci.py platform' in s.get('run', ''))
        self.assertIn('--android-runtime', execute['run'])
        self.assertIn('COMPILE_PRODUCTS', execute['env'])

    def test_optional_android_api_cache_has_no_alias_following_copy_or_duplicate_save(self):
        job = self.jobs['android']
        restore = next(s for s in job['steps'] if s.get('id') == 'android-qt-api-cache')
        prepare = next(s for s in job['steps'] if s.get('id') == 'android-api')
        save = next(s for s in job['steps'] if s['name'] == 'Save only the verified small Android Java API cache')
        self.assertEqual(restore['with']['key'], save['with']['key'])
        self.assertEqual(restore['with']['path'], save['with']['path'])
        self.assertNotRegex(prepare['run'], r'(?m)^\s*cp\s')
        self.assertIn('test ! -L "$qt_api_cache"', prepare['run'])
        self.assertIn('realpath -- "$qt_api_cache"', prepare['run'])
        self.assertIn('sha256sum --check --strict', prepare['run'])
        self.assertIn("steps.android-api.outputs.cache_ready == 'true'", save['if'])
        self.assertIn("steps.android-qt-api-cache.outputs.cache-hit != 'true'", save['if'])
        self.assertNotIn('restore-keys', restore['with'])

    def test_browser_worker_installs_only_trusted_runtime_then_passes_exact_executable(self):
        job = self.jobs['npm']
        prepare = next(s for s in job['steps'] if s.get('id') == 'browser')
        self.assertIn('--package=playwright@1.63.0', prepare['run'])
        self.assertIn('test -f /opt/google/chrome/chrome', prepare['run'])
        self.assertIn('ldd /opt/google/chrome/chrome', prepare['run'])
        self.assertIn('executable=/opt/google/chrome/chrome', prepare['run'])
        self.assertNotIn('candidate', prepare['run'].replace('candidate-provided', ''))
        execute = next(s for s in job['steps'] if 'pr_ci.py execute' in s.get('run', ''))
        self.assertEqual('${{ steps.browser.outputs.executable }}', execute['env']['BROWSER_EXECUTABLE'])
        self.assertIn('--browser-executable "$BROWSER_EXECUTABLE"', execute['run'])
        self.assertIn('--prepared-root "$(dirname "$BROWSER_EXECUTABLE")"', execute['run'])
        self.assertIn('browser_projects', str(job['timeout-minutes']))

    def test_actual_optional_cache_save_script_rejects_changed_bytes_and_aliases(self):
        prepare = next(s for s in self.jobs['android']['steps'] if s.get('id') == 'android-api')
        marker = 'qt_api_cache="$RUNNER_TEMP/pr-ci-android-qt-api/QtAndroid.jar"'
        code = prepare['run'][prepare['run'].index(marker):]
        published_hash = 'a9f64f066766e3908d64183a49c0722aff09495c5f17768213a2989a73edf893'
        self.assertIn(published_hash, code)
        artifact = b'reviewed dependency fixture'
        # Substitute only the fixed public artifact identity; execute the real
        # workflow cache conditions, realpath and checksum pipeline unchanged.
        code = code.replace(published_hash, hashlib.sha256(artifact).hexdigest())
        for kind in ('regular', 'changed', 'leaf-alias', 'parent-alias', 'directory'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory(prefix='pr-ci-cache-script-') as scratch:
                root = Path(scratch); cache = root / 'pr-ci-android-qt-api'; output = root / 'output'
                output.touch(); target = root / 'target'; target.mkdir()
                if kind == 'parent-alias': cache.symlink_to(target, target_is_directory=True)
                else: cache.mkdir()
                leaf = cache / 'QtAndroid.jar'
                if kind == 'leaf-alias':
                    valid = target / 'api.jar'; valid.write_bytes(artifact); leaf.symlink_to(valid)
                elif kind == 'directory': leaf.mkdir()
                else: leaf.write_bytes(b'changed dependency' if kind == 'changed' else artifact)
                result = subprocess.run(['bash', '-euo', 'pipefail', '-c', code],
                    env={'PATH': '/usr/bin:/bin', 'RUNNER_TEMP': str(root), 'GITHUB_OUTPUT': str(output)},
                    capture_output=True, text=True, timeout=10)
                self.assertEqual(0, result.returncode, result.stderr)
                self.assertEqual('cache_ready=true\n' if kind == 'regular' else '', output.read_text())


if __name__ == "__main__":
    unittest.main()
