#!/usr/bin/env python3
"""Authenticate native CI observations and small immutable JSON artifacts.

These checks establish transport and execution provenance, never reusable test
authority. Callers must also validate the record, current PR bookends, and the
GitHub Actions check-suite app. A successful producer job is authoritative even
while the enclosing workflow is still running its observer.
"""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import stat
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

_SPEC = importlib.util.spec_from_file_location(
    "pr_ci_transport_context", Path(__file__).with_name("pr_ci_context.py"))
C = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(C)

WORKFLOW = ".github/workflows/repository-checks.yml"
API_ROOT = "https://api.github.com/repos/" + C.REPOSITORY
MAX_ZIP = 8_000_000
MAX_JSON = 4_000_000
OWNERS = frozenset(("policy", "host", "npm", "native", "codeql", "security", "android", "ios"))
LABELS = {"policy": "Authenticate candidate policy", "host": "Host contracts",
          "native": "Native C++ owner / build", "security": "Workflow security",
          "android": "Android product owner", "ios": "iOS product owner"}
SKIPPED_SOURCE_POLICY_NAMES = frozenset({
    "Source policy not applicable",
    "github.event_name == 'pull_request_target' && 'source-policy' || 'Source policy not applicable'",
})
STEPS = {
    "plan": ("Authenticate immutable PR inputs", "Select owners from complete immutable trees"),
    "policy": ("Verify exact policy and source identities",),
    "host": ("Execute selected host contracts without credentials", "Publish authenticated host task results"),
    "npm": ("Execute the selected package owner without credentials", "Publish authenticated package task results"),
    "native": ("Recheck exact candidate selection", "Configure and select affected targets",
               "Build and run selected native tests"),
    "codeql": ("Initialize the pinned CodeQL extractor", "Require the reviewed extractor version",
               "Analyze the exact PR merge source", "Record the native upload identity",
               "Publish the native upload identity"),
    "security": ("Verify immutable action references as data",
                 "Lint candidate workflow syntax with trusted configuration",
                 "Audit candidate workflow security",
                 "Scan candidate workflows for secrets with redacted output"),
    "android": ("Require the selected Android product validation",),
    "ios": ("Require the selected iOS product validation",),
    "ios-qt": (),
    "ios-handoff": ("Validate same-revision host contract handoff",),
    "ios-v8": (),
    "ios-build": ("Build experimental full client", "Verify required Interface QML plugins in full-client link",
                  "Package numbered unsigned client IPA", "Upload short-lived unsigned E2E client handoff"),
    "ios-verify": ("Verify exact iOS application artifact",),
    "receipt": ("Require every selected owner and unchanged PR identities",
                "Publish the exact native execution receipt"),
}
SOURCE_PREFIXES = (".github/workflows/", ".github/codeql/", "tools/repository-checks/",
    "tools/test-evidence/", "tools/branch-policy/", "tools/dependency-releases/",
    "tools/native-tests/", "tools/workflow-security/", "tools/ios-build-qualification/")
SOURCE_FILES = frozenset((".github/pr-ci-suites.json", ".github/pr-ci-dependencies.json",
    ".github/pr-ci-platforms.json", ".github/pr-ci-platform-inputs.json",
    ".github/pr-ci-android-native.json",
    ".github/branch-policy.json", ".github/dependency-releases.json",
    ".github/native-tests.json", ".github/actionlint.yaml"))


class TransportError(ValueError):
    pass


class Pending(TransportError):
    """Authenticated execution metadata has not yet reached a terminal state."""


def read_eventual(factory, read, *, deadline, pause=time.sleep, clock=time.monotonic):
    """Retry transient metadata GET failures within the caller's existing budget.

    Each try uses a fresh bounded read-only client. No observation is returned
    until the real response arrives; source and execution bookends stay with
    the caller. Authentication, schema and identity errors are never retried.
    """
    reported = False
    while True:
        require(clock() < deadline, "native metadata observation budget exhausted")
        try:
            value = read(factory())
        except urllib.error.HTTPError as error:
            if error.code not in {502, 503, 504}:
                raise
            error.close()
            if not reported:
                print("Waiting for GitHub execution metadata after a transient HTTP error", flush=True)
                reported = True
        else:
            require(clock() <= deadline, "native metadata response exceeded observation budget")
            return value
        remaining = deadline - clock()
        require(remaining > 0, "native metadata observation budget exhausted")
        pause(min(15, remaining))


def require_commands(steps, required):
    """Wait for absent step facts; reject actual skipped/failed commands."""
    require(type(steps) is list and len(steps) <= 100
            and all(type(step) is dict and type(step.get('name')) is str for step in steps),
            'native job steps are malformed')
    named = {}
    waiting = False
    for step in steps:
        require(step['name'] not in named, 'duplicate native execution step')
        named[step['name']] = step
        require(step.get('status') in {'queued', 'in_progress', 'completed'}, 'unknown native step status')
        if step['status'] != 'completed':
            require(step.get('conclusion') is None, 'nonterminal native step has a conclusion')
        else:
            require(step.get('conclusion') in {'success', 'skipped'}, 'native execution step failed')
    for name in required:
        step = named.get(name)
        if step is None or step['status'] != 'completed':
            waiting = True
        else:
            require(step.get('conclusion') == 'success', 'native owner did not complete its required commands')
    if waiting:
        raise Pending('required commands have not yet been indexed')
    return True


def require(condition, message):
    if not condition:
        raise TransportError(message)


def _positive(value, label):
    require(type(value) is int and value > 0, "invalid " + label)
    return value


def _sha(value):
    require(type(value) is str and re.fullmatch(r"[0-9a-f]{40}", value)
            and value != "0" * 40, "invalid native source object")
    return value


def _repository(value):
    require(type(value) is dict and value.get("full_name") == C.REPOSITORY
            and type(value.get("id")) is int and value["id"] == C.REPOSITORY_ID,
            "native observation belongs to another repository")


def validate_run(run, context, *, workflow_id, controller, execution_event):
    """Check native run identity, without promoting its lifecycle to coverage.

    Native run.head_sha is the PR head H, not the synthetic test merge M. Empty
    native PR links carry no authority; the trusted receipt must independently
    authenticate the current number/B/H/T and original M. Present links are exact.
    """
    require(type(run) is dict and type(context) is dict, "missing native run context")
    _repository(run.get("repository")); _repository(run.get("head_repository"))
    require(context.get("repository") == C.REPOSITORY
            and context.get("repository_id") == C.REPOSITORY_ID, "foreign expected native context")
    _sha(controller)
    for key in ("base", "head", "tree", "original_merge"):
        _sha(context.get(key))
    _positive(context.get("number"), "PR number")
    require(context.get("target") in C.TARGETS and type(context.get("head_ref")) is str
            and bool(context["head_ref"]), "invalid expected native branches")
    run_id = _positive(run.get("id"), "native run ID")
    attempt = _positive(run.get("run_attempt"), "native attempt")
    suite = _positive(run.get("check_suite_id"), "native check suite")
    require(type(workflow_id) is int and workflow_id > 0 and run.get("workflow_id") == workflow_id
            and run.get("path") == WORKFLOW, "native workflow registration or path changed")
    require(execution_event in {"pull_request", "workflow_dispatch"}
            and run.get("event") == execution_event, "unsupported native execution event")
    require(run.get("head_sha") == context["head"] and run.get("head_branch") == context["head_ref"],
            "native execution head or branch changed")
    for key, value in (("run_id", run_id), ("run_attempt", attempt), ("controller", controller)):
        if key in context:
            require(type(context[key]) is type(value) and context[key] == value,
                    "native run identity differs from the trusted context")
    if execution_event == "workflow_dispatch":
        require(controller == context["head"], "manual native workflow is not the reviewed head")
    links = run.get("pull_requests")
    require(type(links) is list and len(links) <= 1, "ambiguous native PR association")
    for link in links:
        require(type(link) is dict and link.get("number") == context["number"],
                "native run names another PR")
        for side, revision, ref in (("base", context["base"], context["target"]),
                                    ("head", context["head"], context["head_ref"])):
            value = link.get(side)
            require(type(value) is dict and value.get("sha") == revision and value.get("ref") == ref,
                    "native PR association source or branch changed")
            repo = value.get("repo")
            require(type(repo) is dict and repo.get("id") == C.REPOSITORY_ID,
                    "native PR association belongs to another repository")
            if "full_name" in repo:
                _repository(repo)
    status, conclusion = run.get("status"), run.get("conclusion")
    require(status in {"queued", "in_progress", "waiting", "pending", "requested", "completed"}
            and (conclusion is None if status != "completed" else conclusion in {
                "success", "failure", "cancelled", "timed_out", "action_required", "neutral", "skipped",
                "stale", "startup_failure"}), "unknown native lifecycle")
    require(run.get("url") == API_ROOT + "/actions/runs/" + str(run_id)
            and run.get("html_url") == "https://github.com/" + C.REPOSITORY + "/actions/runs/" + str(run_id),
            "native run URL changed")
    return {"run_id": run_id, "run_attempt": attempt, "check_suite_id": suite,
            "head_sha": context["head"], "workflow_id": workflow_id,
            "execution_event": execution_event, "controller": controller}


def validate_sources(actual_tree, trusted_tree, *, protected_base=None):
    """Compare complete immutable controller/launcher and workflow inventories.

    Both maps must come from authenticated complete Git trees. Candidate test and
    product inputs may differ; the programs issuing a receipt and every workflow
    capable of invoking them must exactly match the loaded trusted controller.
    """
    def inventory(tree):
        require(type(tree) is dict and len(tree) <= 100_000, "invalid complete source inventory")
        result = {}
        for path, entry in tree.items():
            require(type(path) is str and path and not path.startswith("/")
                    and all(part not in {"", ".", ".."} for part in path.split("/")),
                    "malformed complete source path")
            if path.startswith(SOURCE_PREFIXES) or path in SOURCE_FILES:
                require(type(entry) is dict and entry.get("mode") in {"100644", "100755"}
                        and entry.get("type") == "blob", "controller input is not an ordinary blob")
                result[path] = {"mode": entry["mode"], "type": "blob", "sha": _sha(entry.get("sha"))}
        essential = {WORKFLOW, "tools/repository-checks/pr_ci.py",
            "tools/repository-checks/pr_ci_context.py", "tools/repository-checks/pr_ci_plan.py",
            "tools/repository-checks/pr_ci_run.py", "tools/repository-checks/pr_ci_observer.py",
            "tools/repository-checks/pr_ci_transport.py", ".github/pr-ci-suites.json",
            ".github/pr-ci-dependencies.json"}
        require(essential <= result.keys(), "trusted controller source is incomplete")
        return result
    actual, trusted = inventory(actual_tree), inventory(trusted_tree)
    if protected_base is not None:
        base = inventory(protected_base)
        # Product workflows already installed on the protected target retain
        # their reviewed branch implementation. A PR cannot change, delete or
        # add one through this exception. Central/reusable execution recipes
        # and central maintenance recipes must always equal the current
        # protected default-branch controller, including downstream activation.
        central = {WORKFLOW, ".github/workflows/native-tests.yml",
                   ".github/workflows/branch-cleanup.yml",
                   ".github/workflows/pr-ci-ios.yml", ".github/workflows/ios-integrated.yml",
                   ".github/workflows/ios-qt-source.yml"}
        for path, entry in base.items():
            if path.startswith(".github/workflows/") and path not in central:
                if entry != trusted.get(path):
                    trusted[path] = entry
    require(actual == trusted,
            "native worker controller, launcher, policy or workflow differs from trusted source")
    return True


def validate_jobs(jobs, expected_owners, *, plan=None, context=None):
    """Require actual successful terminal commands, including each matrix member.

    The caller fetches the complete jobs listing for the authenticated attempt.
    The observer job itself may still be running; it is never execution coverage.
    """
    require(type(expected_owners) is dict and set(expected_owners) == OWNERS
            and all(type(value) is bool for value in expected_owners.values()), "invalid expected native owners")
    require(type(jobs) is list and 0 < len(jobs) <= 500, "incomplete or excessive native jobs")
    named, ids, identity = {}, set(), None
    for job in jobs:
        require(type(job) is dict and type(job.get("name")) is str and bool(job["name"]),
                "malformed native job")
        job_id = _positive(job.get("id"), "native job ID")
        require(job_id not in ids and job["name"] not in named, "duplicate native job")
        ids.add(job_id); named[job["name"]] = job
        key = (_positive(job.get("run_id"), "job run ID"),
               _positive(job.get("run_attempt"), "job attempt"), _sha(job.get("head_sha")))
        require(identity is None or key == identity, "native jobs mix runs, attempts or source heads")
        if context is not None:
            require(type(context) is dict and key == (context.get("run_id"),
                    context.get("run_attempt"), context.get("head")),
                    "native job belongs to another authenticated run, attempt or head")
        identity = key
    expected = {"Select exact candidate tasks": ("plan", True),
                "Candidate execution receipt": ("receipt", True)}
    for owner, label in LABELS.items():
        expected[label] = (owner, expected_owners[owner])
    for owner, field, label in (("npm", "npm_projects", "npm"),
                                 ("codeql", "codeql_languages", "CodeQL")):
        members = None if plan is None else plan.get(field)
        if members is not None:
            require(type(members) is list and all(type(item) is str and item for item in members)
                    and len(members) == len(set(members))
                    and bool(members) == expected_owners[owner], "native matrix differs from the trusted plan")
        matched = [name for name in named if name.startswith(label + " (") and name.endswith(")")]
        if expected_owners[owner]:
            if members is not None:
                require(set(matched) == {label + " (" + item + ")" for item in members},
                        "native matrix member inventory changed")
            require(bool(matched), "selected native matrix is missing")
            for name in matched:
                expected[name] = (owner, True)
        else:
            # Skipped matrix jobs may have an unresolved expression as their
            # display name. They still cannot contain executed commands.
            for name in matched:
                expected[name] = (owner, False)
    if "Native C++ owner" in named and not expected_owners["native"]:
        expected["Native C++ owner"] = expected.pop("Native C++ owner / build")
    if expected_owners["ios"]:
        expected.pop("iOS product owner")
        build = plan.get("ios_build_required", True) if plan is not None else True
        require(type(build) is bool, "invalid iOS build selection")
        ios_jobs = {
            "iOS product owner / iOS host contracts": ("ios", True),
            "iOS product owner / qt / qt-ios-source": ("ios-qt", build),
            "iOS product owner / client / Host contracts": ("ios-handoff", build),
            "iOS product owner / client / Static JITless V8 checkpoint": ("ios-v8", build),
            "iOS product owner / client / Toolchain, dependencies, build and package": ("ios-build", build),
            "iOS product owner / Verify iOS product qualification": ("ios-verify", True),
        }
        expected.update(ios_jobs)
        if not build:
            for label, role in (("qt", "ios-qt"), ("client", "ios-build")):
                placeholder = "iOS product owner / " + label
                if placeholder in named:
                    for name in list(expected):
                        if name.startswith(placeholder + " / "):
                            expected.pop(name)
                    expected[placeholder] = (role, False)
    # GitHub can retain the unevaluated display-name expression when a job is
    # skipped. Both exact names describe one nonexecuting placeholder, never
    # the protected source-policy check or an additional execution owner.
    require(len(set(named) & SKIPPED_SOURCE_POLICY_NAMES) <= 1,
            "native skipped source-policy inventory is ambiguous")
    for name in SKIPPED_SOURCE_POLICY_NAMES:
        expected[name] = ("source-policy", False)
    observers = {"required-ci", "Execution observer has no acceptance authority"}
    require(len(set(named) & observers) <= 1, "native observer inventory is ambiguous")
    allowed = {*expected, *observers}
    require(set(named) <= allowed, "unexpected native execution job")
    waiting = False
    for name, (owner, selected) in expected.items():
        job = named.get(name)
        if job is None:
            if selected:
                waiting = True
            continue
        status, conclusion, steps = job.get("status"), job.get("conclusion"), job.get("steps")
        require(type(steps) is list and len(steps) <= 100
                and all(type(step) is dict and type(step.get("name")) is str for step in steps),
                "native job steps are malformed")
        require(status in {"queued", "waiting", "pending", "in_progress", "completed"},
                "unknown native job status")
        if not selected:
            if status != "completed":
                require(conclusion is None and not steps, "unselected owner started executing")
                waiting = True
            else:
                require(conclusion == "skipped" and not steps, "unselected native owner executed")
            continue
        if status != "completed":
            require(conclusion is None, "nonterminal native owner has a conclusion")
            waiting = True
        else:
            require(conclusion == "success", "selected native owner failed or did not execute")
        step_map = {}
        for step in steps:
            require(step["name"] not in step_map, "duplicate native execution step")
            step_map[step["name"]] = step
            require(step.get("status") in {"queued", "in_progress", "completed"},
                    "unknown native step status")
            if step.get("status") == "completed":
                require(step.get("conclusion") in {"success", "skipped"}, "native execution step failed")
            else:
                require(step.get("conclusion") is None, "nonterminal native step has a conclusion")
                waiting = True
        if status == "completed":
            try:
                require_commands(steps, STEPS[owner])
            except Pending:
                waiting = True
    if waiting:
        raise Pending("selected native jobs have not yet completed or indexed their required commands")
    return True


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, target):
        return None


def _signed_url(value):
    require(type(value) is str and not any(character.isspace() for character in value),
            "invalid artifact download redirect")
    parsed = urllib.parse.urlsplit(value)
    host = parsed.hostname or ""
    require(parsed.scheme == "https" and not parsed.username and not parsed.password
            and parsed.port in {None, 443} and not parsed.fragment
            and (re.fullmatch(r"productionresults[a-z0-9]+\.blob\.core\.windows\.net", host)
                 or re.fullmatch(r"[a-z0-9-]+\.actions\.githubusercontent\.com", host)),
            "artifact download redirect left approved GitHub storage")
    return value


def _download(api, artifact_id):
    """GET one fixed ID; credentials never follow its signed storage redirect."""
    token = os.environ.get("GH_TOKEN", "")
    require(bool(token), "read-only artifact credential unavailable")
    deadline = min(getattr(api, "deadline", float("inf")), time.monotonic() + 45)
    url = API_ROOT + "/actions/artifacts/" + str(artifact_id) + "/zip"
    opener = urllib.request.build_opener(_NoRedirect())
    headers = {"Authorization": "Bearer " + token, "Accept": "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28"}
    try:
        remaining = deadline - time.monotonic()
        require(remaining > 0, "artifact download budget exhausted")
        try:
            response = opener.open(urllib.request.Request(url, headers=headers, method="GET"),
                                   timeout=min(15, remaining))
        except urllib.error.HTTPError as error:
            require(error.code == 302, "artifact archive GET failed")
            target = _signed_url(error.headers.get("Location"))
            error.close()
            remaining = deadline - time.monotonic()
            require(remaining > 0, "artifact download budget exhausted")
            # No token, Authorization header, cookie jar or referrer is forwarded.
            response = opener.open(urllib.request.Request(target, method="GET"), timeout=min(15, remaining))
            url = target
        with response:
            require(response.status == 200 and response.geturl() == url,
                    "artifact archive response changed")
            raw = response.read(MAX_ZIP + 1)
        require(len(raw) <= MAX_ZIP and time.monotonic() <= deadline,
                "artifact archive exceeds its time or byte bound")
        return raw
    except TransportError:
        raise
    except (OSError, ValueError, urllib.error.HTTPError) as error:
        raise TransportError("artifact archive GET unavailable; response details withheld") from None


def read_artifact(api, artifact, *, expected_name, run_id, run_attempt, head_sha):
    """Download a digest-bound small ZIP with exactly result.json or upload.json.

    GitHub artifact metadata does not expose the attempt. Its exact trusted
    producer name includes the attempt and the immutable workflow disables
    overwrite. Native successful job/source validation remains mandatory.
    """
    _positive(run_id, "artifact run ID"); _positive(run_attempt, "artifact attempt"); _sha(head_sha)
    prefix = str(run_id) + "-" + str(run_attempt)
    if expected_name == "pr-ci-" + prefix:
        member = "result.json"
    elif re.fullmatch(r"pr-ci-tasks-" + re.escape(prefix) + r"-(?:host|npm-[0-9a-f]{64})", expected_name):
        member = "tasks.json"
    else:
        require(expected_name in {"codeql-upload-" + prefix + "-" + language
                for language in ("javascript-typescript", "python")}, "unsupported native artifact name")
        member = "upload.json"
    require(type(artifact) is dict, "native artifact metadata unavailable")
    artifact_id = _positive(artifact.get("id"), "artifact ID")
    def authenticate(value):
        require(type(value) is dict and value.get("id") == artifact_id
                and value.get("name") == expected_name and value.get("expired") is False
                and type(value.get("size_in_bytes")) is int and 0 < value["size_in_bytes"] <= MAX_ZIP
                and type(value.get("digest")) is str
                and re.fullmatch(r"sha256:[0-9a-f]{64}", value["digest"]),
                "native artifact identity, expiration, size or digest changed")
        workflow = value.get("workflow_run")
        require(type(workflow) is dict and workflow.get("id") == run_id
                and workflow.get("repository_id") == C.REPOSITORY_ID
                and workflow.get("head_repository_id") == C.REPOSITORY_ID
                and workflow.get("head_sha") == head_sha, "artifact source or native run changed")
        require(value.get("url") == API_ROOT + "/actions/artifacts/" + str(artifact_id)
                and value.get("archive_download_url") == API_ROOT + "/actions/artifacts/" + str(artifact_id) + "/zip",
                "artifact endpoint changed")
    authenticate(artifact)
    endpoint = "actions/artifacts/" + str(artifact_id)
    before = api.get(endpoint)
    authenticate(before)
    require(before == artifact, "listed artifact differs from its direct native record")
    raw = _download(api, artifact_id)
    require(len(raw) == artifact["size_in_bytes"]
            and "sha256:" + hashlib.sha256(raw).hexdigest() == artifact["digest"],
            "downloaded native artifact size or digest differs")
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            entries = archive.infolist()
            require(len(entries) == 1 and entries[0].filename == member, "unexpected native artifact members")
            entry = entries[0]
            require(not entry.is_dir() and not entry.flag_bits & 1
                    and stat.S_IFMT(entry.external_attr >> 16) in {0, stat.S_IFREG}
                    and entry.compress_type in {zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED}
                    and 0 < entry.file_size <= MAX_JSON, "unsupported native artifact member")
            data = archive.read(entry)
        require(len(data) <= MAX_JSON, "native JSON receipt exceeds bound")
        value = json.loads(data, object_pairs_hook=C.unique,
                           parse_constant=lambda _: require(False, "nonfinite artifact JSON"))
        require(type(value) is dict, "native receipt must be a JSON object")
    except (zipfile.BadZipFile, UnicodeError, ValueError, RuntimeError, C.ContextError) as error:
        if isinstance(error, TransportError):
            raise
        raise TransportError("malformed native JSON artifact") from None
    after = api.get(endpoint)
    authenticate(after)
    require(after == before, "native artifact changed during observation")
    return value
