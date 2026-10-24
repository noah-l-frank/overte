#!/usr/bin/env python3
"""Plan PR work once, execute its owners, and keep acceptance outside candidate code."""
from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import urllib.parse
import zipfile
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import pr_ci_context as C
import pr_ci_plan as P


def read_json(value):
    return json.loads(value, object_pairs_hook=C.unique,
                      parse_constant=lambda _: C.require(False, "nonfinite JSON"))


def git(root, *args, limit=16_000_000):
    value = subprocess.check_output(["git", "--no-replace-objects", *args], cwd=root,
        stderr=subprocess.PIPE, timeout=60, env={**os.environ,
        "GIT_OPTIONAL_LOCKS": "0", "GIT_NO_LAZY_FETCH": "1"})
    C.require(len(value) <= limit, "immutable Git input exceeds limit")
    return value


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(C.canonical(value))


def outputs(path, values):
    if path:
        with Path(path).open("a") as stream:
            for key, value in values.items():
                C.require(re.fullmatch(r"[a-z_]+", key), "invalid CI output name")
                encoded = ("true" if value else "false") if type(value) is bool else str(value)
                C.require("\n" not in encoded and "\r" not in encoded, "multiline CI output refused")
                stream.write(key + "=" + encoded + "\n")


class API(C.GitHub):
    json_types = (dict, list)
    max_calls = 96
    extra_endpoints = (
        r"(?:git/trees/[0-9a-f]{40}\?recursive=1|git/blobs/[0-9a-f]{40}"
        r"|commits/[0-9a-f]{40}/pulls\?per_page=100&page=[1-5]"
        r"|compare/[0-9a-f]{40}\.\.\.[0-9a-f]{40}"
        r"|actions/workflows/repository-checks\.yml(?:/runs\?event=pull_request&head_sha=[0-9a-f]{40}&per_page=100&page=[1-5])?"
        r"|check-suites/[1-9][0-9]*"
        r"|actions/runs/[1-9][0-9]*(?:/attempts/[1-9][0-9]*(?:/jobs\?per_page=100&page=[1-5])?"
        r"|/artifacts\?per_page=100&page=[1-5])?"
        r"|actions/artifacts/[1-9][0-9]*"
        r"|code-scanning/sarifs/[0-9a-f-]{36}"
        r"|code-scanning/analyses\?sarif_id=[0-9a-f-]{36}(?:&per_page=100&page=[1-5])?"
        r"|code-scanning/alerts\?ref=refs%2Fpull%2F[1-9][0-9]*%2Fmerge&state=open&tool_name=CodeQL(?:&per_page=100&page=[1-5])?"
        r"|code-scanning/alerts/[1-9][0-9]*/instances\?ref=refs%2Fpull%2F[1-9][0-9]*%2Fmerge(?:&per_page=100&page=[1-5])?)")

    def pages(self, endpoint, *, field=None):
        result = []
        for page in range(1, 6):
            suffix = ("&" if "?" in endpoint else "?") + "per_page=100&page=" + str(page)
            value = self.get(endpoint + suffix)
            rows = value if field is None else value.get(field)
            C.require(type(rows) is list, "native metadata listing is incomplete")
            result.extend(rows)
            if len(rows) < 100:
                return result
        raise C.ContextError("native metadata listing exceeds bound")



class ReuseAPI(API):
    """Independent, bounded provenance budget for at most three ancestor levels.

    Parent authentication must not spend the current execution observer's API
    allowance. Only immutable Git object reads may be shared across origins;
    run, attempt, suite, PR and artifact bookends always reach GitHub again.
    """
    max_calls = 192

    def __init__(self, deadline=None):
        super().__init__(deadline=deadline)
        self.immutable = {}

    def get(self, endpoint):
        immutable = type(endpoint) is str and re.fullmatch(
            r"git/(?:commits/[0-9a-f]{40}|blobs/[0-9a-f]{40}|trees/[0-9a-f]{40}\?recursive=1)", endpoint)
        if not immutable:
            return super().get(endpoint)
        if endpoint not in self.immutable:
            self.immutable[endpoint] = super().get(endpoint)
        # A consumer cannot mutate another origin's validated object snapshot.
        return json.loads(C.canonical(self.immutable[endpoint]))


def expected_owners(plan):
    host = any("suite:" + name not in plan.get("covered_tasks", {}) for name in plan["host_suites"])
    return {"policy": True, "host": host,
            "npm": bool(plan["npm_projects"]), "native": plan["native"]["mode"] != "skip",
            "codeql": bool(plan["codeql_languages"]), "security": bool(plan["workflow_security"]),
            "android": bool(plan["android_required"]), "ios": bool(plan["ios_required"])}


def validate_execution_scope(context, plan):
    if context.get("execution_event") == "workflow_dispatch":
        C.require(plan["native"]["mode"] == "skip" and not plan["android_required"]
                  and not plan["ios_required"],
                  "manual controller bootstrap cannot replace an ordinary native or platform PR execution")


def selection(candidate, context):
    candidate = Path(candidate).resolve(strict=True)
    C.require(git(candidate, "rev-parse", "HEAD").decode().strip() == context["original_merge"],
              "candidate checkout differs from the recorded execution commit")
    C.require(git(candidate, "rev-parse", "HEAD^{tree}").decode().strip() == context["tree"],
              "candidate checkout tree differs from authenticated PR inputs")
    before = P._INPUTS.full_tree(candidate, context["base"])
    after = P._INPUTS.full_tree(candidate, context["original_merge"])
    trusted = P._INPUTS.full_tree(ROOT, "HEAD")
    def blob(oid):
        try:
            return git(ROOT, "cat-file", "blob", oid)
        except subprocess.CalledProcessError:
            return git(candidate, "cat-file", "blob", oid)
    plan = P.plan(before, after, trusted, read_blob=blob, target=context["target"])
    # The workflow scanner is another owner of this same immutable plan.
    plan["workflow_security"] = any(path.startswith((".github/", "tools/workflow-security/",
        "tools/repository-checks/", "tools/native-tests/", "tools/branch-policy/")) for path in plan["paths"])
    plan["controller"] = git(ROOT, "rev-parse", "HEAD").decode().strip()
    plan["owners"] = expected_owners(plan)
    return plan


def source_context(event, event_name, number, controller):
    C.require(event_name in {"pull_request", "pull_request_target", "workflow_dispatch"},
              "unsupported CI invocation")
    C.require(os.environ.get("GITHUB_REPOSITORY") == C.REPOSITORY
              and os.environ.get("GITHUB_REPOSITORY_ID") == str(C.REPOSITORY_ID),
              "native CI invocation belongs to another repository")
    api = API()
    event_pr = event.get("pull_request") if event_name != "workflow_dispatch" else None
    number = int(number or event.get("number", 0))
    original = os.environ.get("GITHUB_SHA") if event_name == "pull_request" else None
    context = C.capture(api, number, event_pr=event_pr, original_merge=original)
    C.require(git(ROOT, "rev-parse", "HEAD").decode().strip() == C.sha(controller),
              "loaded CI controller differs from selected immutable source")
    caller = C.sha(os.environ.get("GITHUB_WORKFLOW_SHA"))
    if event_name == "pull_request":
        C.require(caller == original and os.environ.get("GITHUB_REF") == f"refs/pull/{number}/merge",
                  "native PR caller differs from its original execution context")
    elif event_name == "workflow_dispatch":
        C.require(caller == context["head"] and os.environ.get("GITHUB_SHA") == context["head"],
                  "manual bootstrap must use the exact reviewed PR head")
    context.update(controller=controller, caller_source=caller, execution_event=event_name,
                   run_id=int(os.environ["GITHUB_RUN_ID"]), run_attempt=int(os.environ["GITHUB_RUN_ATTEMPT"]))
    return context


def policy(candidate, context, plan):
    import pr_ci_android_preflight
    import pr_ci_android_native
    prerequisites = pr_ci_android_preflight.classify(plan['paths'], target=context['target'])
    C.require(prerequisites['native_qualification_required'] == bool(
        pr_ci_android_native.products(plan, context['target'])), 'Android native prerequisite selection differs')
    pr_ci_android_native.prerequisites(candidate, plan, context['target'])
    # These programs are loaded from the protected controller, and inspect only
    # supplied branch metadata and candidate files. They never import candidate code.
    pr = API().get("pulls/" + str(context["number"]))
    author = pr.get("user", {})
    command = [sys.executable, "-I", "-S", "-B", str(ROOT / "tools/branch-policy/check.py"),
        "check-pr", "--base", context["target"], "--head", context["head_ref"],
        "--repository-id", str(C.REPOSITORY_ID), "--base-repository-id", str(C.REPOSITORY_ID),
        "--head-repository-id", str(C.REPOSITORY_ID), "--repository", C.REPOSITORY,
        "--head-sha", context["head"], "--expected-head-sha", context["head"],
        "--pr-author-login", author.get("login", ""), "--pr-author-type", author.get("type", ""),
        "--changed-files-stdin"]
    subprocess.run(command, cwd=ROOT, input="\n".join(plan["paths"]) + "\n", text=True, check=True, timeout=60)
    subprocess.run([sys.executable, "-I", "-S", "-B", str(ROOT / "tools/dependency-releases/check.py"),
                    "--root", str(Path(candidate).resolve()), "check"], check=True, timeout=60)
    C.bookend(API(), context)


def execute(candidate, plan, lane, project, prepared_roots, *, context=None, browser_executable=None):
    import pr_ci_run
    candidate = Path(candidate).resolve(strict=True)
    tasks = [task for task in plan["tasks"] if task["kind"] == lane]
    if project:
        tasks = [task for task in tasks if task["id"] == "npm:" + project]
    C.require(bool(tasks), "unselected or empty execution owner")
    receipts = []
    runtime, reusable = None, {}
    if context is not None:
        native_identity(context)
        C.require(C.canonical(selection(candidate, context)) == C.canonical(plan),
                  "command execution plan differs from its authenticated source")
        C.bookend(API(), context)
        import pr_ci_reuse
        try:
            runtime = pr_ci_reuse.observed_runtime(prepared_roots)
            evidence = pr_ci_reuse.Evidence(API(deadline=time.monotonic() + 30), context, remote_selection)
            reusable = evidence.discover(tasks, runtime, lane, project)
        except (OSError, ValueError, KeyError, TypeError, AttributeError, subprocess.SubprocessError) as error:
            # Optional stale/missing parent evidence never causes a failing PR
            # or a false successful test. Run the selected commands instead.
            print("Parent task evidence unavailable; executing selected commands (" + type(error).__name__ + ")", flush=True)
    original = git(candidate, "rev-parse", "HEAD").decode().strip()
    C.require(not git(candidate, "diff", "HEAD", "--"), "candidate tracked inputs were changed before execution")
    for task in tasks:
        C.require(not task["missing_inputs"], "selected test has missing inputs: " + task["id"])
        commands = task["command"] if lane == "npm" else [task["command"]]
        origin = reusable.get(task['id'])
        for index, arguments in enumerate(commands):
            command = list(arguments)
            if command[0] == "python":
                command[0] = sys.executable
            command = ["/tmp/overte-jsdoc-output" if argument == "{temporary_output}" else argument
                       for argument in command]
            # The dependency owner may fetch public packages. Test/build commands
            # execute without a network, credentials, or runner control files.
            fetch = lane == "npm" and command[:2] in (["npm", "ci"], ["npm", "audit"])
            if origin and not fetch:
                continue
            browser = (lane == 'npm' and 'browser' in task.get('setup', [])
                       and (command == ['npm', 'run', 'test:browser']
                            or command == ['node', 'node_modules/@playwright/test/cli.js',
                                           'test', '--config', 'playwright.config.ts']))
            if browser:
                executable = Path(browser_executable or '').resolve(strict=True)
                C.require(browser_executable and executable.is_file()
                          and any(executable.is_relative_to(Path(root).resolve(strict=True))
                                  for root in prepared_roots),
                          'selected browser journey has no prepared browser runtime')
                command = ['/usr/bin/env', 'OVERTE_BROWSER_CI_ISOLATED=1',
                           'OVERTE_BROWSER_CHROME_EXECUTABLE=' + str(executable), *command]
            if lane == "npm":
                command = ["/usr/bin/env", "--chdir=/work/" + project, *command]
            status = pr_ci_run.run(candidate, command, prepared_roots=prepared_roots,
                network=fetch, timeout=1200,
                boundary="docker" if browser else "user-namespace")
            C.require(status == 0, f"selected command failed: {task['id']} [{index}] exit={status}")
            C.require(git(candidate, "rev-parse", "HEAD").decode().strip() == original
                      and not git(candidate, "diff", "HEAD", "--"),
                      "selected command changed its immutable tracked source")
        receipt = {"task": task["id"], "input_key": task["reuse_key"], "result": "success"}
        if context is not None:
            receipt.update(command=task['command'], runtime=runtime, executed=not bool(origin), origin=origin)
        receipts.append(receipt)
    if context is None:
        return receipts
    C.bookend(API(), context)
    return {"kind": "pr-ci-task-results-v1", "context": context, "lane": lane,
            "project": project, "results": receipts}


def native_identity(context):
    C.require(os.environ.get("GITHUB_REPOSITORY") == C.REPOSITORY
              and os.environ.get("GITHUB_REPOSITORY_ID") == str(C.REPOSITORY_ID),
              "execution belongs to another repository")
    C.require(str(context["run_id"]) == os.environ.get("GITHUB_RUN_ID")
              and str(context["run_attempt"]) == os.environ.get("GITHUB_RUN_ATTEMPT")
              and context["caller_source"] == os.environ.get("GITHUB_WORKFLOW_SHA"),
              "execution run, attempt or workflow source changed")


def upload_proof(context, language, sarif):
    native_identity(context)
    C.require(language in ("javascript-typescript", "python")
              and str(uuid.UUID(sarif)) == sarif, "invalid native CodeQL upload identity")
    return {"schema": 1, "repository": C.REPOSITORY, "repository_id": C.REPOSITORY_ID,
            "run_id": context["run_id"], "run_attempt": context["run_attempt"],
            "language": language, "source_commit": context["original_merge"],
            "ref": f"refs/pull/{context['number']}/merge",
            "workflow": ".github/workflows/repository-checks.yml",
            "workflow_sha": context["caller_source"], "sarif_id": sarif}


def verify_native(candidate, context, plan):
    native_identity(context)
    C.require(context.get("execution_event") == "pull_request"
              and git(ROOT, "rev-parse", "HEAD").decode().strip() == context.get("controller")
              and os.environ.get("GITHUB_SHA") == context.get("original_merge"),
              "native controller or execution source differs from its authenticated invocation")
    C.require(os.environ.get("PR_CI_SOURCE_REF") == f"refs/pull/{context['number']}/merge",
              "native candidate source reference changed")
    C.require(plan["native"]["mode"] in {"core", "full"}
              and plan["native"]["mode"] == os.environ.get("EXPECTED_MODE"),
              "native execution does not match the selected owner")
    C.require(C.canonical(selection(candidate, context)) == C.canonical(plan),
              "native selection differs from the independently recomputed plan")
    return {**plan["native"], 'sha': context['original_merge']}


def complete(context, plan, needs):
    native_identity(context)
    C.require(type(needs) is dict and needs.get("plan", {}).get("result") == "success",
              "the immutable execution plan did not succeed")
    owners = {name: value for name, value in needs.items() if name != "plan"}
    C.require_jobs(owners, expected_owners(plan))
    current = C.bookend(API(), context)
    return {"kind": "pr-ci-execution-v1", "result": "success", "context": context,
            "plan": plan, "owners": owners, "run_id": context["run_id"],
            "run_attempt": context["run_attempt"], "observed_context": current,
            "task_results": "required"}


def remote_tree(api, tree):
    tree = C.sha(tree)
    value = api.get("git/trees/" + tree + "?recursive=1")
    C.require(value.get("sha") == tree and value.get("truncated") is False
              and type(value.get("tree")) is list, "complete immutable tree unavailable")
    result = {}
    for entry in value["tree"]:
        C.require(type(entry) is dict and type(entry.get("path")) is str,
                  "malformed immutable tree entry")
        if entry.get("type") == "tree":
            C.require(entry.get("mode") == "040000", "invalid immutable directory mode")
            continue
        path = entry["path"]
        C.require(path not in result, "duplicate immutable tree entry")
        result[path] = {key: entry.get(key) for key in ("mode", "type", "sha")}
    P._INPUTS._validate_tree(result)
    return result


def remote_selection(api, context):
    commit = api.get("git/commits/" + C.sha(context["base"]))
    C.require(commit.get("sha") == context["base"], "immutable base metadata changed")
    before = remote_tree(api, commit["tree"]["sha"])
    after = remote_tree(api, context["tree"])
    trusted = P._INPUTS.full_tree(ROOT, "HEAD")
    cache = {}
    def blob(oid):
        oid = C.sha(oid)
        if oid not in cache:
            try:
                raw = git(ROOT, "cat-file", "blob", oid)
            except subprocess.CalledProcessError:
                value = api.get("git/blobs/" + oid)
                C.require(value.get("sha") == oid and value.get("encoding") == "base64"
                          and type(value.get("content")) is str, "immutable blob unavailable")
                raw = base64.b64decode(value["content"].replace("\n", ""), validate=True)
                C.require(value.get("size") == len(raw), "immutable blob size differs")
            C.require(hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest() == oid,
                      "immutable blob content differs")
            cache[oid] = raw
        return cache[oid]
    plan = P.plan(before, after, trusted, read_blob=blob, target=context["target"])
    plan["workflow_security"] = any(path.startswith((".github/", "tools/workflow-security/",
        "tools/repository-checks/", "tools/native-tests/", "tools/branch-policy/")) for path in plan["paths"])
    plan["controller"] = git(ROOT, "rev-parse", "HEAD").decode().strip()
    plan["owners"] = expected_owners(plan)
    return plan, after, trusted


def current_controller(api, controller):
    """Allow a newer protected main only when its complete CI program is unchanged."""
    import pr_ci_transport as transport
    default = api.get("branches/main")
    C.require(default.get("protected") is True, "default controller is not protected")
    revision = C.sha(default.get("commit", {}).get("sha"))
    if revision == controller:
        return
    commit = api.get("git/commits/" + revision)
    C.require(commit.get("sha") == revision, "default controller metadata changed")
    current = remote_tree(api, commit["tree"]["sha"])
    loaded = P._INPUTS.full_tree(ROOT, "HEAD")
    transport.validate_sources(current, loaded)
    C.require(all(current.get(path) == loaded.get(path) for path in P.RUNTIME_INPUTS),
              "protected controller runtime inputs changed")


def source_policy(event, event_name, number, controller):
    """Authenticate candidate workflow sources early without executing them."""
    import pr_ci_transport as transport
    C.require(event_name == "pull_request_target", "source policy requires the protected event")
    C.require(os.environ.get("GITHUB_REPOSITORY") == C.REPOSITORY
              and os.environ.get("GITHUB_REPOSITORY_ID") == str(C.REPOSITORY_ID)
              and controller == os.environ.get("GITHUB_WORKFLOW_SHA")
              and git(ROOT, "rev-parse", "HEAD").decode().strip() == C.sha(controller),
              "source policy repository or protected controller differs")
    api = API()
    current_controller(api, controller)
    context = C.capture(api, int(number or event.get("number", 0)), event_pr=event.get("pull_request"))
    context["controller"] = controller
    _, actual, trusted = remote_selection(api, context)
    if context["target"] == "main":
        transport.validate_sources(actual, trusted)
    else:
        base = api.get("git/commits/" + context["base"])
        C.require(base.get("sha") == context["base"], "protected base metadata changed")
        transport.validate_sources(actual, trusted, protected_base=remote_tree(api, base["tree"]["sha"]))
    C.bookend(api, context)
    current_controller(API(), controller)
    print(json.dumps({"result": "success", "head": context["head"], "tree": context["tree"]}))


def gate(event, event_name, number, controller, *, timeout=5700, pause=time.sleep):
    import pr_ci_observer as observer
    import pr_ci_transport as transport
    C.require(event_name in {"pull_request", "pull_request_target", "workflow_dispatch"},
              "only an authenticated native final job or protected observer can accept CI")
    C.require(os.environ.get("GITHUB_REPOSITORY") == C.REPOSITORY
              and os.environ.get("GITHUB_REPOSITORY_ID") == str(C.REPOSITORY_ID)
              and git(ROOT, "rev-parse", "HEAD").decode().strip() == C.sha(controller),
              "observer repository or loaded controller differs")
    number = int(number or event.get("number", 0))
    first = C.capture(API(), number,
        event_pr=event.get("pull_request") if event_name != "workflow_dispatch" else None,
        original_merge=os.environ.get("GITHUB_SHA") if event_name == "pull_request" else None)
    if event_name == "workflow_dispatch":
        C.require(controller == first["head"] and controller == os.environ.get("GITHUB_WORKFLOW_SHA"),
                  "manual bootstrap must use the exact reviewed PR head")
    else:
        if event_name == "pull_request_target":
            C.require(controller == os.environ.get("GITHUB_WORKFLOW_SHA"),
                      "observer does not use the protected event controller")
        else:
            C.require(first["original_merge"] == os.environ.get("GITHUB_WORKFLOW_SHA")
                      and os.environ.get("GITHUB_REF") == f"refs/pull/{number}/merge",
                      "native final job differs from its original PR caller")
        current_controller(API(), controller)
    workflow = API().get("actions/workflows/repository-checks.yml")
    C.require(type(workflow.get("id")) is int
              and workflow.get("path") == ".github/workflows/repository-checks.yml",
              "native worker workflow registration changed")
    deadline, run, last_state = time.monotonic() + timeout, None, None
    def read_jobs(run_id, attempt):
        return transport.read_eventual(lambda: API(deadline=deadline),
            lambda client: client.pages(f"actions/runs/{run_id}/attempts/{attempt}/jobs", field="jobs"),
            deadline=deadline, pause=pause)

    while time.monotonic() < deadline:
        api = API(deadline=deadline)
        if run is None:
            if event_name in {"workflow_dispatch", "pull_request"}:
                run = api.get("actions/runs/" + str(int(os.environ["GITHUB_RUN_ID"])))
            else:
                listing = api.pages("actions/workflows/repository-checks.yml/runs?event=pull_request&head_sha="
                                    + first["head"], field="workflow_runs")
                candidates = sorted((row for row in listing if row.get("head_sha") == first["head"]),
                                    key=lambda row: row.get("id", 0), reverse=True)
                for candidate in candidates:
                    jobs = read_jobs(candidate['id'], candidate['run_attempt'])
                    # A title/body event has no execution owner. It may observe
                    # the original result, but cannot invent a replacement PASS.
                    if jobs and all(job.get("conclusion") == "skipped" for job in jobs):
                        continue
                    run = candidate
                    break
        if run is None:
            state = "waiting for the original candidate worker"
        else:
            identity = api.get("actions/runs/" + str(run["id"]))
            C.require(identity.get("run_attempt") == run.get("run_attempt"),
                      "native execution attempt changed while observing it")
            execution_event = identity.get("event")
            transport.validate_run(identity, first, workflow_id=workflow["id"],
                                   controller=controller, execution_event=execution_event)
            suite = api.get("check-suites/" + str(identity["check_suite_id"]))
            C.require(suite.get("id") == identity["check_suite_id"]
                      and suite.get("head_sha") == first["head"]
                      and suite.get("app", {}).get("id") == 15368
                      and suite.get("repository", {}).get("id") == C.REPOSITORY_ID,
                      "native worker check suite or GitHub Actions app changed")
            jobs = read_jobs(identity['id'], identity['run_attempt'])
            C.require(not any(job.get("conclusion") in {"failure", "cancelled", "timed_out", "action_required"}
                              for job in jobs),
                      "a native candidate worker job failed; no new execution was requested")
            if jobs and all(job.get("status") == "completed"
                            and job.get("conclusion") == "skipped" for job in jobs):
                # The jobs endpoint may initially be empty for a metadata-only
                # event. Once its nonexecution is explicit, find the original
                # producer instead of waiting for a receipt it cannot publish.
                run = None
                continue
            producers = [job for job in jobs if job.get("name") == "Candidate execution receipt"]
            C.require(len(producers) <= 1, "ambiguous native execution producer")
            if not producers or producers[0].get("status") != "completed":
                state = "waiting for the original execution receipt publisher to finish"
                if state != last_state:
                    print(state, flush=True)
                    last_state = state
                pause(15)
                continue
            C.require(producers[0].get("conclusion") == "success",
                      "native execution receipt publisher did not succeed")
            artifacts = api.pages(f"actions/runs/{identity['id']}/artifacts", field="artifacts")
            name = f"pr-ci-{identity['id']}-{identity['run_attempt']}"
            matches = [item for item in artifacts if item.get("name") == name]
            C.require(len(matches) <= 1, "ambiguous native execution receipts")
            if not matches:
                C.require(identity.get("conclusion") not in {"failure", "cancelled", "timed_out", "action_required"},
                          "candidate worker failed before producing its execution receipt")
                state = "waiting for selected native execution owners"
            else:
                record = transport.read_artifact(api, matches[0], expected_name=name,
                    run_id=identity["id"], run_attempt=identity["run_attempt"], head_sha=first["head"])
                original = C.sha(record.get("context", {}).get("original_merge"))
                context = C.capture(api, number, original_merge=original)
                C.require(all(context[k] == first[k] for k in C.FIXED_FIELDS if k != "original_merge"),
                          "PR inputs changed during native execution")
                context.update(controller=controller, run_id=identity["id"],
                    run_attempt=identity["run_attempt"], execution_event=execution_event,
                    caller_source=context["head"] if execution_event == "workflow_dispatch" else original)
                plan, actual_tree, trusted_tree = remote_selection(api, context)
                validate_execution_scope(context, plan)
                if context["target"] == "main":
                    transport.validate_sources(actual_tree, trusted_tree)
                else:
                    base_commit = api.get("git/commits/" + context["base"])
                    C.require(base_commit.get("sha") == context["base"], "protected base metadata changed")
                    transport.validate_sources(actual_tree, trusted_tree,
                        protected_base=remote_tree(api, base_commit["tree"]["sha"]))
                jobs = read_jobs(identity['id'], identity['run_attempt'])
                try:
                    transport.validate_jobs(jobs, expected_owners(plan), plan=plan, context=context)
                except transport.Pending:
                    state = "waiting for terminal native job conclusions"
                else:
                    observer.validate_record(record, plan, context,
                        run_id=identity["id"], run_attempt=identity["run_attempt"])
                    if record.get('task_results') == 'required':
                        import pr_ci_reuse
                        reuse_api = ReuseAPI(deadline=min(deadline, time.monotonic() + 60))
                        pr_ci_reuse.verify_current(reuse_api, context, plan, artifacts, remote_selection)
                    uploads = {}
                    for language in plan["codeql_languages"]:
                        upload_name = f"codeql-upload-{identity['id']}-{identity['run_attempt']}-{language}"
                        choices = [item for item in artifacts if item.get("name") == upload_name]
                        C.require(len(choices) == 1, "missing or ambiguous native CodeQL upload proof")
                        uploads[language] = transport.read_artifact(api, choices[0], expected_name=upload_name,
                            run_id=identity["id"], run_attempt=identity["run_attempt"], head_sha=first["head"])
                    codeql = observer.verify_codeql(api, context, plan["codeql_languages"], uploads)
                    if codeql["state"] == "complete":
                        closing = API(deadline=deadline)
                        final_run = closing.get("actions/runs/" + str(identity["id"]))
                        transport.validate_run(final_run, context, workflow_id=workflow["id"],
                                               controller=controller, execution_event=execution_event)
                        C.require(all(final_run.get(key) == identity.get(key) for key in (
                            "id", "workflow_id", "check_suite_id", "path", "event", "head_sha",
                            "head_branch", "run_attempt")), "native worker identity changed before acceptance")
                        C.require(final_run.get("status") != "completed"
                                  or final_run.get("conclusion") == "success",
                                  "native worker failed before final acceptance")
                        final_suite = closing.get("check-suites/" + str(identity["check_suite_id"]))
                        C.require(final_suite.get("id") == suite.get("id")
                                  and final_suite.get("head_sha") == context["head"]
                                  and final_suite.get("app", {}).get("id") == 15368
                                  and final_suite.get("repository", {}).get("id") == C.REPOSITORY_ID,
                                  "native worker check suite changed before acceptance")
                        final_jobs = read_jobs(identity['id'], identity['run_attempt'])
                        try:
                            transport.validate_jobs(final_jobs, expected_owners(plan), plan=plan, context=context)
                        except transport.Pending:
                            state = "waiting for indexed final native step metadata"
                            if state != last_state:
                                print(state, flush=True)
                                last_state = state
                            pause(15)
                            continue
                        C.bookend(API(), context)
                        if event_name != "workflow_dispatch":
                            current_controller(API(), controller)
                        C.require(time.monotonic() < deadline, "native execution observation budget exhausted")
                        print(json.dumps({"result": "success", "run_id": identity["id"],
                            "run_attempt": identity["run_attempt"], "source": original,
                            "tree": context["tree"], "owners": expected_owners(plan)}, sort_keys=True))
                        return
                    state = "waiting for the original CodeQL upload processing"
        if state != last_state:
            print(state, flush=True)
            last_state = state
        pause(15)
    raise C.ContextError("native execution observation budget exhausted; no result was accepted")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    local_cli = sub.add_parser('preflight', help='Inspect local immutable inputs; never issue execution evidence')
    local_cli.add_argument('--candidate', type=Path, default=ROOT)
    local_cli.add_argument('--base', required=True)
    local_cli.add_argument('--revision', default='HEAD')
    local_cli.add_argument('--target', choices=P.TARGETS, required=True)
    local_cli.add_argument('--out', type=Path)
    local_cli.add_argument('--allow-controller-transition', action='store_true',
        help='Report an explicitly reviewed local controller rollout; never bypass a GitHub gate')
    context_cli = sub.add_parser("context")
    context_cli.add_argument("--event", type=Path, required=True)
    context_cli.add_argument("--event-name", required=True)
    context_cli.add_argument("--number", default="")
    context_cli.add_argument("--controller", required=True)
    context_cli.add_argument("--out", type=Path, required=True)
    context_cli.add_argument("--output", type=Path)
    for name in ("gate", "source-policy"):
        gate_cli = sub.add_parser(name)
        gate_cli.add_argument("--event", type=Path, required=True)
        gate_cli.add_argument("--event-name", required=True)
        gate_cli.add_argument("--number", default="")
        gate_cli.add_argument("--controller", required=True)
    upload_cli = sub.add_parser("upload-proof")
    upload_cli.add_argument("--context-json", required=True)
    upload_cli.add_argument("--language", required=True)
    upload_cli.add_argument("--sarif", required=True)
    upload_cli.add_argument("--out", type=Path, required=True)
    plan_cli = sub.add_parser("plan")
    plan_cli.add_argument("--context", type=Path, required=True)
    plan_cli.add_argument("--candidate", type=Path, required=True)
    plan_cli.add_argument("--out", type=Path, required=True)
    plan_cli.add_argument("--output", type=Path)
    for name in ("policy", "execute", "complete", "verify-native", "platform", "verify-ios"):
        command = sub.add_parser(name)
        command.add_argument("--context-json", required=True)
        command.add_argument("--plan-json", required=True)
        command.add_argument("--candidate", type=Path)
        command.add_argument("--out", type=Path)
        if name in ("execute", "platform"):
            command.add_argument("--lane", choices=("host", "npm") if name == "execute" else ("android", "ios"), required=True)
            command.add_argument("--project", default="")
            command.add_argument("--prepared-root", action="append", default=[])
            if name == 'execute':
                command.add_argument('--output', type=Path)
                command.add_argument('--browser-executable', type=Path)
            else:
                command.add_argument('--android-runtime', type=Path)
                command.add_argument('--android-native-runtime', type=Path)
                command.add_argument('--android-groovy-runtime', type=Path)
        if name == "complete":
            command.add_argument("--needs-json", required=True)
        if name == "verify-ios":
            command.add_argument("--needs-json", required=True)
            command.add_argument("--artifacts", type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'preflight':
        import pr_ci_android_preflight
        before = P._INPUTS.full_tree(args.candidate, args.base)
        after = P._INPUTS.full_tree(args.candidate, args.revision)
        trusted = P._INPUTS.full_tree(ROOT, 'HEAD')
        def blob(oid):
            try:
                return git(ROOT, 'cat-file', 'blob', oid)
            except subprocess.CalledProcessError:
                return git(args.candidate, 'cat-file', 'blob', oid)
        plan = P.plan(before, after, trusted, read_blob=blob, target=args.target)
        prerequisites = pr_ci_android_preflight.classify(plan['paths'], target=args.target)
        native_unavailable = prerequisites['native_qualification_required']
        if native_unavailable:
            import pr_ci_android_native
            try:
                revision = C.sha(git(args.candidate, 'rev-parse', '--verify', '--end-of-options',
                                     args.revision + '^{commit}').decode().strip())
                pr_ci_android_native.prerequisites(args.candidate, plan, args.target, revision=revision)
                native_unavailable = False
                prerequisites.update(status='qualified-runtime-available', missing=[])
            except ValueError as error:
                prerequisites['readiness_error'] = str(error)
        import pr_ci_transport
        source_policy_status = 'compatible'
        try:
            pr_ci_transport.validate_sources(after, trusted,
                protected_base=before if args.target != 'main' else None)
        except pr_ci_transport.TransportError:
            source_policy_status = 'requires-reviewed-controller-transition'
        result = {'kind': 'pr-ci-local-preflight-v1', 'execution': False, 'plan': plan,
                  'platform_prerequisites': prerequisites, 'source_policy': source_policy_status}
        if args.out:
            write_json(args.out, result)
        print(json.dumps({'target': args.target, 'tasks': [t['id'] for t in plan['tasks']],
                          'platform_prerequisites': prerequisites, 'source_policy': source_policy_status}, sort_keys=True))
        return 2 if native_unavailable or (
            source_policy_status != 'compatible' and not args.allow_controller_transition) else 0
    elif args.command == "context":
        context = source_context(read_json(args.event.read_text()), args.event_name, args.number, args.controller)
        write_json(args.out, context)
        outputs(args.output, {**{k: context[k] for k in ("number", "base", "head", "target", "tree", "controller")},
                             "source": context["original_merge"], "context_json": C.canonical(context).decode().strip()})
    elif args.command in {"gate", "source-policy"}:
        (gate if args.command == "gate" else source_policy)(read_json(args.event.read_text()), args.event_name, args.number, args.controller)
    elif args.command == "upload-proof":
        write_json(args.out, upload_proof(read_json(args.context_json), args.language, args.sarif))
    elif args.command == "plan":
        context = read_json(args.context.read_text())
        plan = selection(args.candidate, context)
        validate_execution_scope(context, plan)
        C.bookend(API(), context)
        write_json(args.out, plan)
        values = {**plan["owners"], "native_mode": plan["native"]["mode"],
                  "plan_json": C.canonical(plan).decode().strip(),
                  "npm_projects": json.dumps(plan["npm_projects"]),
                  "codeql_languages": json.dumps(plan["codeql_languages"]),
                  "full_host": "host-full" in plan["setup"],
                  "setup_json": json.dumps(plan["setup"]),
                  "browser_projects": json.dumps([t['id'][4:] for t in plan['tasks']
                      if t['kind'] == 'npm' and 'browser' in t['setup']]),
                  "android_compile_products": json.dumps(plan.get('android_compile_products', [])),
                  "android_native_products": json.dumps(plan.get('android_native_products', [])),
                  "android_groovy_contracts": plan.get('android_groovy_contracts', False),
                  "ios_build": plan["ios_build_required"]}
        outputs(args.output, values)
        print(json.dumps({"target": context["target"], "tasks": [t["id"] for t in plan["tasks"]],
                          "native": plan["native"]["mode"], "setup": plan["setup"]}))
    else:
        context, plan = read_json(args.context_json), read_json(args.plan_json)
        if args.command == "policy":
            policy(args.candidate, context, plan)
        elif args.command == "execute":
            receipt = execute(args.candidate, plan, args.lane, args.project, args.prepared_root,
                              context=context, browser_executable=args.browser_executable)
            if args.out:
                write_json(args.out, receipt)
            import pr_ci_reuse
            outputs(args.output, {'artifact_name': pr_ci_reuse.artifact_name(context, args.lane, args.project)})
        elif args.command == "complete":
            write_json(args.out, complete(context, plan, read_json(args.needs_json)))
        elif args.command == "verify-native":
            native = verify_native(args.candidate, context, plan)
            if args.out:
                write_json(args.out, native)
        elif args.command == "platform":
            import pr_ci_platform
            receipt = pr_ci_platform.execute(args.candidate, context, plan, args.lane,
                args.prepared_root, recompute=selection, android_runtime=args.android_runtime,
                android_native_runtime=args.android_native_runtime, android_groovy_runtime=args.android_groovy_runtime)
            if args.out:
                write_json(args.out, receipt)
        elif args.command == "verify-ios":
            import pr_ci_platform
            write_json(args.out, pr_ci_platform.verify_ios(args.candidate, context, plan,
                args.artifacts, read_json(args.needs_json), API(deadline=time.monotonic() + 660), recompute=selection))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (C.ContextError, P.PlanError, OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        print("PR CI refused acceptance: " + str(error), file=sys.stderr)
        raise SystemExit(1)
