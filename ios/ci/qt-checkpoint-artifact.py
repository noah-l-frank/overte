#!/usr/bin/env python3
"""Create and restore validated iOS toolchain prefixes via workflow artifacts."""

# Copyright 2026 Overte e.V.
# SPDX-License-Identifier: Apache-2.0

from __future__ import annotations

import argparse
import base64
from contextlib import contextmanager
import datetime as dt
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import signal
import shutil
import stat
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile


SCHEMA = 1
ARCHIVE_NAME = "checkpoint.tar.gz"
MANIFEST_NAME = "manifest.json"
API_JSON_LIMIT = 16 * 1024 * 1024
ARTIFACT_INDEX_SCHEMA = 1
ARTIFACT_INDEX_TTL_SECONDS = 120
DOWNLOAD_LIMITS = {
    "host": 512 * 1024 * 1024,
    "ios": 512 * 1024 * 1024,
    "v8": 512 * 1024 * 1024,
    "conan": 2 * 1024 * 1024 * 1024,
    "client-sccache": 6 * 1024 * 1024 * 1024,
    "qt-sccache": 6 * 1024 * 1024 * 1024,
    "qt-source": 3 * 1024 * 1024 * 1024,
}
MANIFEST_LIMIT = 64 * 1024
ARCHIVE_LIMITS = {
    "host": 384 * 1024 * 1024,
    "ios": 384 * 1024 * 1024,
    "v8": 384 * 1024 * 1024,
    "conan": 1536 * 1024 * 1024,
    "client-sccache": 5 * 1024 * 1024 * 1024,
    "qt-sccache": 5 * 1024 * 1024 * 1024,
    "qt-source": 2 * 1024 * 1024 * 1024,
}
MEMBER_LIMITS = {"host": 100_000, "ios": 100_000, "v8": 100_000, "conan": 500_000, "client-sccache": 100_000, "qt-sccache": 100_000, "qt-source": 1}
EXPANDED_LIMITS = {
    "host": 2 * 1024 * 1024 * 1024,
    "ios": 2 * 1024 * 1024 * 1024,
    "v8": 2 * 1024 * 1024 * 1024,
    "conan": 10 * 1024 * 1024 * 1024,
    "client-sccache": 5 * 1024 * 1024 * 1024,
    "qt-sccache": 5 * 1024 * 1024 * 1024,
    "qt-source": 2 * 1024 * 1024 * 1024,
}

# Additional compiler DATA admission is deliberately fork/protected-branch only.
# These are reviewed historical writer recipes, not artifact/run exceptions.
COMPILER_REPOSITORY = "noah-l-frank/overte"
COMPILER_REPOSITORY_ID = 1319052603
COMPILER_BRANCH = "apple-ios"
COMPILER_WORKFLOW = ".github/workflows/ios-build-qualification.yml"
COMPILER_JOB = "client / Toolchain, dependencies, build and package"
COMPILER_UPLOAD = "Upload durable full-client compiler checkpoint"
COMPILER_UPLOAD_ACTION = "actions/upload-artifact@b7c566a772e6b6bfb58ed0dc250532a479d7789f"
COMPILER_LEGACY_WRITERS = {
    COMPILER_WORKFLOW: {"aac9051e1bc89fe71e2f1be4331706f9acfe5b38"},
    ".github/workflows/ios-integrated.yml": {"1004d282c847655be7deafced0108ee291e8250c"},
    "ios/ci/qt-checkpoint-artifact.py": {"4e5ccd1fec2df26a2337bae3fad40e1e48a510a1"},
}
COMPILER_WRITER_PATHS = (
    COMPILER_WORKFLOW, ".github/workflows/ios-integrated.yml",
    ".github/workflows/ios-qt-source.yml", "ios/ci/qt-checkpoint-artifact.py",
    "ios/ci/client-compiler-cache-key.py", "ios/ci/merge-compiler-checkpoint.py",
    "ios/ci/xcode-compiler-launcher.sh", "ios/ci/compiler-watchdog.py",
    "ios/ci/runner-telemetry.py", "ios/build-ios.sh",
)
COMPILER_LOG_LIMIT = 45 * 1024 * 1024
COMPILER_CANDIDATE_LIMIT = 8
COMPILER_ARCHIVE_SECONDS = 600


class CompilerUnavailable(ValueError):
    """An optional compiler DATA candidate lacks a complete origin proof."""


def _require(value: bool, message: str) -> None:
    if not value:
        raise CompilerUnavailable(message)


def _oid(value) -> str:
    _require(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}", value) is not None,
             "invalid immutable source")
    return value


def _positive(value) -> int:
    _require(type(value) is int and value > 0, "invalid native identifier")
    return value


def _timestamp(value) -> dt.datetime:
    _require(isinstance(value, str), "missing native timestamp")
    try:
        result = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise CompilerUnavailable("invalid native timestamp") from error
    _require(result.tzinfo is not None, "native timestamp lacks timezone")
    return result


@contextmanager
def _compiler_deadline(deadline: float, operation: str):
    """Hard wall-clock bound for only the new macOS main-thread API path."""
    _require(deadline > time.monotonic(), f"compiler {operation} deadline exhausted")
    _require(signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0),
             "compiler transport cannot replace another deadline")
    previous = signal.getsignal(signal.SIGALRM)

    def expired(*unused):
        # A socket timeout alone permits a peer to trickle bytes forever.
        raise CompilerUnavailable(f"compiler {operation} deadline exhausted")

    signal.signal(signal.SIGALRM, expired)
    try:
        signal.setitimer(signal.ITIMER_REAL, deadline - time.monotonic())
        yield
        _require(time.monotonic() < deadline, f"compiler {operation} deadline exhausted")
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


class _CompilerResponse:
    """Enforce the same deadline before/after every streamed read as well."""

    def __init__(self, incoming, deadline: float, operation: str):
        self.incoming, self.deadline, self.operation = incoming, deadline, operation
        self.headers = incoming.headers

    def read(self, size):
        _require(time.monotonic() < self.deadline, f"compiler {self.operation} deadline exhausted")
        raw = self.incoming.read(size)
        _require(time.monotonic() < self.deadline, f"compiler {self.operation} deadline exhausted")
        return raw

    def close(self):
        self.incoming.close()

    def __enter__(self):
        return self

    def __exit__(self, *unused):
        self.close()


class _CompilerAPI:
    """Fixed-fork read-only transport; no serialized claims select authority."""

    def __init__(self, token: str):
        self.token = token
        self.remaining = 200
        # Includes the single large archive and staged extraction between native
        # bookends. Individual HTTP operations still have short timeouts.
        self.deadline = time.monotonic() + 1800
        self.opener = urllib.request.build_opener(_NoRedirect()).open

    def _open(self, request, deadline: float, operation: str):
        remaining = deadline - time.monotonic()
        _require(remaining > 0, f"compiler {operation} deadline exhausted")
        return _CompilerResponse(self.opener(request, timeout=min(30, remaining)), deadline, operation)

    def get(self, endpoint: str) -> dict:
        _require(self.remaining > 0 and time.monotonic() < self.deadline,
                 "compiler provenance request budget exhausted")
        self.remaining -= 1
        request = urllib.request.Request(
            f"https://api.github.com/repos/{COMPILER_REPOSITORY}/{endpoint}",
            headers={"Accept": "application/vnd.github+json", "Authorization": f"Bearer {self.token}",
                     "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "overte-compiler-data"})
        deadline = min(self.deadline, time.monotonic() + 30)
        with _compiler_deadline(deadline, "JSON"), self._open(request, deadline, "JSON") as response:
            result = json.loads(_read_limited(response, API_JSON_LIMIT))
        _require(isinstance(result, dict), "invalid native API object")
        return result

    def log(self, job_id: int) -> bytes:
        _require(self.remaining > 0 and time.monotonic() < self.deadline,
                 "compiler provenance request budget exhausted")
        self.remaining -= 1
        # The authenticated API URL is fixed. The storage hop is anonymous and
        # cannot redirect again, just like the archive transport below.
        url = f"https://api.github.com/repos/{COMPILER_REPOSITORY}/actions/jobs/{_positive(job_id)}/logs"
        with tempfile.TemporaryDirectory(prefix="overte-compiler-origin-") as temporary:
            destination = Path(temporary) / "job.log"
            deadline = min(self.deadline, time.monotonic() + 60)

            with _compiler_deadline(deadline, "origin log"):
                download_artifact(url, self.token, destination, COMPILER_LOG_LIMIT,
                                  opener=lambda request: self._open(request, deadline, "origin log"))
            return destination.read_bytes()

    def archive(self, artifact: dict, destination: Path) -> None:
        """Bound only the new protected archive path, including a slow copy."""
        deadline = min(self.deadline, time.monotonic() + COMPILER_ARCHIVE_SECONDS)
        with _compiler_deadline(deadline, "archive"):
            download_artifact(artifact["archive_download_url"], self.token, destination,
                              DOWNLOAD_LIMITS["client-sccache"],
                              opener=lambda request: self._open(request, deadline, "archive"))


def _compiler_commit(api, sha: str) -> dict:
    sha = _oid(sha)
    commit = api.get("git/commits/" + sha)
    _require(commit.get("sha") == sha and isinstance(commit.get("parents"), list),
             "immutable commit unavailable")
    _oid(commit.get("tree", {}).get("sha"))
    for parent in commit["parents"]:
        _oid(parent.get("sha"))
    return commit


def _compiler_ancestor(api, ancestor: str, protected: str) -> None:
    if _oid(ancestor) == _oid(protected):
        return
    comparison = api.get(f"compare/{ancestor}...{protected}?per_page=1")
    _require(comparison.get("status") == "ahead" and type(comparison.get("ahead_by")) is int
             and comparison["ahead_by"] > 0 and comparison.get("behind_by") == 0
             and comparison.get("base_commit", {}).get("sha") == ancestor
             and comparison.get("merge_base_commit", {}).get("sha") == ancestor,
             "compiler source is not fully integrated")


def _compiler_tree(api, tree: str) -> dict:
    result = api.get(f"git/trees/{_oid(tree)}?recursive=1")
    _require(result.get("sha") == tree and result.get("truncated") is False
             and isinstance(result.get("tree"), list) and len(result["tree"]) <= 100_000,
             "complete immutable source inventory unavailable")
    entries = {}
    for entry in result["tree"]:
        name = entry.get("path")
        _require(isinstance(name, str) and name not in entries and name
                 and not name.startswith("/") and ".." not in name.split("/"),
                 "invalid immutable source membership")
        entries[name] = entry
    return entries


def _compiler_blob(api, entry: dict) -> bytes:
    _require(entry.get("type") == "blob" and entry.get("mode") in ("100644", "100755"),
             "compiler writer is not an ordinary file")
    oid = _oid(entry.get("sha"))
    blob = api.get("git/blobs/" + oid)
    _require(blob.get("sha") == oid and blob.get("encoding") == "base64"
             and type(blob.get("size")) is int and 0 < blob["size"] <= 512 * 1024,
             "invalid immutable writer blob")
    try:
        raw = base64.b64decode("".join(blob["content"].split()), validate=True)
    except (KeyError, TypeError, ValueError) as error:
        raise CompilerUnavailable("invalid immutable writer bytes") from error
    actual = hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest()
    _require(actual == oid and len(raw) == blob["size"], "immutable writer bytes changed")
    return raw


def _compiler_run(api, run_id: int) -> dict:
    run = api.get(f"actions/runs/{_positive(run_id)}")
    _require(run.get("id") == run_id and run.get("run_attempt") == 1
             and run.get("repository", {}).get("id") == COMPILER_REPOSITORY_ID
             and run.get("repository", {}).get("full_name") == COMPILER_REPOSITORY
             and run.get("head_repository", {}).get("id") == COMPILER_REPOSITORY_ID,
             "foreign or retried compiler run")
    _oid(run.get("head_sha"))
    _positive(run.get("workflow_id"))
    _positive(run.get("check_suite_id"))
    return run


def _compiler_consumer(api) -> dict:
    env = os.environ
    sha = _oid(env.get("GITHUB_SHA"))
    _require(env.get("GITHUB_ACTIONS") == "true"
             and env.get("GITHUB_REPOSITORY") == COMPILER_REPOSITORY
             and env.get("GITHUB_REPOSITORY_ID") == str(COMPILER_REPOSITORY_ID)
             and env.get("GITHUB_REF") == "refs/heads/apple-ios"
             and env.get("GITHUB_REF_PROTECTED") == "true"
             and env.get("GITHUB_EVENT_NAME") in ("push", "workflow_dispatch")
             and env.get("GITHUB_JOB") == "integrated-configure"
             and env.get("GITHUB_RUN_ATTEMPT") == "1"
             and env.get("GITHUB_WORKFLOW_SHA") == sha,
             "integrated compiler DATA requires a protected apple-ios consumer")
    workflow = env.get("GITHUB_WORKFLOW_REF", "")
    allowed = (".github/workflows/ios-integrated.yml", ".github/workflows/ios-bootstrap.yml")
    paths = [name for name in allowed
             if workflow == f"{COMPILER_REPOSITORY}/{name}@refs/heads/apple-ios"]
    _require(len(paths) == 1, "unsupported compiler consumer recipe")
    run_id = env.get("GITHUB_RUN_ID", "")
    _require(re.fullmatch(r"[1-9][0-9]*", run_id) is not None, "invalid consumer run")
    run = _compiler_run(api, int(run_id))
    _require(run.get("head_sha") == sha and run.get("head_branch") == COMPILER_BRANCH
             and run.get("event") == env["GITHUB_EVENT_NAME"] and run.get("path") == paths[0]
             and run.get("status") == "in_progress", "consumer native source changed")
    registration = api.get("actions/workflows/" + paths[0].rsplit("/", 1)[1])
    _require(registration.get("id") == run.get("workflow_id")
             and registration.get("path") == paths[0] and registration.get("state") == "active",
             "consumer workflow registration changed")
    branch = api.get("branches/apple-ios")
    _require(branch.get("name") == COMPILER_BRANCH and branch.get("protected") is True
             and branch.get("commit", {}).get("sha") == sha, "protected compiler branch advanced")
    commit = _compiler_commit(api, sha)
    tree = _compiler_tree(api, commit["tree"]["sha"])
    own = tree.get("ios/ci/qt-checkpoint-artifact.py", {})
    raw = _compiler_blob(api, own)
    path = Path(__file__)
    _require(not path.is_symlink() and path.read_bytes() == raw,
             "compiler verifier is not the protected source")
    jobs = api.get(f"actions/runs/{run_id}/attempts/1/jobs?per_page=100")
    _require(isinstance(jobs.get("jobs"), list) and jobs.get("total_count") == len(jobs["jobs"]) <= 100,
             "consumer native jobs unavailable")
    names = {"Toolchain, dependencies, build and package"} if paths[0] == allowed[0] else {
        "integrated-ios-after-qt / Toolchain, dependencies, build and package",
        "integrated-ios-from-checkpoints / Toolchain, dependencies, build and package"}
    owners = [job for job in jobs["jobs"] if job.get("name") in names and job.get("status") == "in_progress"]
    _require(len(owners) == 1, "protected compiler consumer owner is ambiguous")
    job = owners[0]
    _positive(job.get("id"))
    check_url = job.get("check_run_url", "")
    match = re.fullmatch(re.escape(f"https://api.github.com/repos/{COMPILER_REPOSITORY}/check-runs/")
                         + r"([1-9][0-9]*)", check_url)
    _require(job.get("run_id") == int(run_id) and job.get("run_attempt") == 1
             and job.get("head_sha") == sha and match is not None, "consumer native job source changed")
    check = api.get("check-runs/" + match[1])
    _require(check.get("id") == int(match[1]) and check.get("app", {}).get("id") == 15368
             and check.get("head_sha") == sha and check.get("name") == job["name"]
             and check.get("check_suite", {}).get("id") == run["check_suite_id"]
             and check.get("status") == "in_progress" and check.get("conclusion") is None,
             "consumer is not the current native Actions owner")
    return {"sha": sha, "run": run_id, "path": paths[0], "tree": tree, "job": job["id"]}


def _compiler_upload_binding(raw: bytes, artifact: dict, step: dict) -> None:
    """Read only native action output; never emit commands, env or storage URLs."""
    _require(len(raw) <= COMPILER_LOG_LIMIT, "compiler origin log exceeds limit")
    text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", raw.decode("utf-8", "strict"))
    groups = []
    active = None
    for line in text.splitlines():
        match = re.match(r"^(\d{4}-\d\d-\d\dT\S+Z) (.*)$", line)
        if not match:
            continue
        when, body = _timestamp(match[1]), match[2]
        if body == "##[group]Run " + COMPILER_UPLOAD_ACTION:
            active = []
            groups.append(active)
        if active is not None:
            active.append((when, body))
        # The action's input group ends before its upload output. The next
        # runner-generated step group ends this action's observation window.
        if active is not None and body.startswith("##[group]Run ") and body != "##[group]Run " + COMPILER_UPLOAD_ACTION:
            active = None
    matching = [group for group in groups
                if any(body.strip() == "name: " + artifact["name"] for _, body in group)]
    _require(len(matching) == 1, "specific native compiler upload not observed")
    start = _timestamp(step["started_at"])
    # Actions native completion timestamps are whole seconds; log timestamps
    # retain subsecond precision. No tolerance applies to source ordering.
    end = _timestamp(step["completed_at"]) + dt.timedelta(seconds=1)
    ids, hashes = [], []
    for when, body in matching[0]:
        digest = re.fullmatch(r"SHA256 digest of uploaded artifact zip is ([0-9a-f]{64})", body)
        identity = re.search(r"(?:Artifact ID |Artifact ID: |Artifact ID is )([1-9][0-9]*)\b", body)
        if digest or identity:
            _require(start <= when < end, "upload output lies outside its native step")
        if digest:
            hashes.append("sha256:" + digest[1])
        if identity:
            ids.append(int(identity[1]))
    _require(hashes == [artifact["digest"]] and ids and set(ids) == {artifact["id"]},
             "native upload does not bind the selected artifact and whole digest")


def _compiler_origin(api, artifact: dict, consumer: dict, *, read_log: bool) -> dict:
    workflow_run = artifact["workflow_run"]
    run_id = _positive(workflow_run.get("id"))
    run = _compiler_run(api, run_id)
    _require(run.get("event") == "pull_request" and run.get("path") == COMPILER_WORKFLOW
             and run.get("head_sha") == workflow_run.get("head_sha")
             and run.get("head_branch") == workflow_run.get("head_branch")
             and run.get("status") == "completed" and run.get("conclusion") in ("success", "failure"),
             "unsupported original compiler run")
    registration = api.get("actions/workflows/ios-build-qualification.yml")
    _require(registration.get("id") == run.get("workflow_id")
             and registration.get("path") == COMPILER_WORKFLOW
             and registration.get("name") == "iOS device build qualification"
             and registration.get("state") == "active", "original workflow registration changed")
    references = run.get("referenced_workflows")
    _require(isinstance(references, list) and len(references) == 2,
             "original local workflow source unavailable")
    sources, refs, paths = set(), set(), set()
    for reference in references:
        source = _oid(reference.get("sha"))
        _require(reference.get("path") in {
            f"{COMPILER_REPOSITORY}/.github/workflows/ios-integrated.yml@{source}",
            f"{COMPILER_REPOSITORY}/.github/workflows/ios-qt-source.yml@{source}"},
            "foreign original reusable workflow")
        sources.add(source)
        refs.add(reference.get("ref"))
        paths.add(reference["path"].split("@", 1)[0])
    _require(len(sources) == len(refs) == 1, "mixed original workflow source")
    _require(paths == {f"{COMPILER_REPOSITORY}/.github/workflows/ios-integrated.yml",
                       f"{COMPILER_REPOSITORY}/.github/workflows/ios-qt-source.yml"},
             "incomplete original reusable workflow inventory")
    source, ref = next(iter(sources)), next(iter(refs))
    _require(isinstance(ref, str) and re.fullmatch(r"refs/pull/[1-9][0-9]*/merge", ref) is not None,
             "original source is not a native PR merge")
    merge = _compiler_commit(api, source)
    head = _compiler_commit(api, run["head_sha"])
    parents = [item["sha"] for item in merge["parents"]]
    _require(len(parents) == 2 and parents[1] == run["head_sha"]
             and merge["tree"] == head["tree"], "original tested source is not the integrated head tree")
    _compiler_ancestor(api, run["head_sha"], consumer["sha"])
    pr = api.get("pulls/" + ref.split("/")[2])
    _require(pr.get("state") == "closed" and pr.get("merged") is True
             and pr.get("head", {}).get("sha") == run["head_sha"]
             and pr.get("head", {}).get("repo", {}).get("id") == COMPILER_REPOSITORY_ID
             and pr.get("base", {}).get("repo", {}).get("id") == COMPILER_REPOSITORY_ID
             and pr.get("base", {}).get("ref") == COMPILER_BRANCH,
             "original compiler PR is not integrated into apple-ios")
    integrated = _compiler_commit(api, _oid(pr.get("merge_commit_sha")))
    _require(integrated["tree"] == merge["tree"]
             and [item["sha"] for item in integrated["parents"]] == parents,
             "normal integration does not retain the original tested tree")
    _compiler_ancestor(api, integrated["sha"], consumer["sha"])
    tree = _compiler_tree(api, merge["tree"]["sha"])
    writer = {}
    for name in COMPILER_WRITER_PATHS:
        old, current = tree.get(name, {}), consumer["tree"].get(name, {})
        _require(old.get("mode") == current.get("mode") and old.get("type") == "blob"
                 and old.get("sha") in {current.get("sha"), *COMPILER_LEGACY_WRITERS.get(name, ())},
                 "unreviewed original compiler writer")
        _compiler_blob(api, old)
        writer[name] = old["sha"]
    jobs_payload = api.get(f"actions/runs/{run_id}/attempts/1/jobs?per_page=100")
    jobs = jobs_payload.get("jobs")
    _require(isinstance(jobs, list) and jobs_payload.get("total_count") == len(jobs) <= 100,
             "incomplete original native jobs")
    matching = [job for job in jobs if job.get("name") == COMPILER_JOB]
    _require(len(matching) == 1, "original native compiler owner is ambiguous")
    job = matching[0]
    _positive(job.get("id"))
    _require(job.get("run_id") == run_id and job.get("run_attempt") == 1
             and job.get("head_sha") == run["head_sha"] and job.get("status") == "completed"
             and job.get("conclusion") in ("success", "failure"), "invalid original native compiler job")
    check_url = job.get("check_run_url", "")
    match = re.fullmatch(re.escape(f"https://api.github.com/repos/{COMPILER_REPOSITORY}/check-runs/")
                         + r"([1-9][0-9]*)", check_url)
    _require(match is not None, "foreign compiler native check")
    check = api.get("check-runs/" + match[1])
    _require(check.get("id") == int(match[1]) and check.get("app", {}).get("id") == 15368
             and check.get("name") == job["name"] and check.get("head_sha") == run["head_sha"]
             and check.get("status") == job["status"] and check.get("conclusion") == job["conclusion"]
             and check.get("started_at") == job.get("started_at")
             and check.get("completed_at") == job.get("completed_at")
             and check.get("check_suite", {}).get("id") == run.get("check_suite_id"),
             "original compiler check is not the native Actions owner")
    steps = job.get("steps")
    required = ("Verify full-client compiler checkpoint activity", "Stop full-client compiler checkpoint server",
                "Save reusable full-client compiler checkpoint", COMPILER_UPLOAD)
    _require(isinstance(steps, list), "missing native compiler steps")
    selected = []
    for name in required:
        matches = [step for step in steps if step.get("name") == name]
        _require(len(matches) == 1 and matches[0].get("status") == "completed"
                 and matches[0].get("conclusion") == "success", "compiler DATA publication step failed")
        _positive(matches[0].get("number"))
        _require(_timestamp(matches[0].get("started_at")) <= _timestamp(matches[0].get("completed_at")),
                 "invalid native publication step chronology")
        selected.append(matches[0])
    _require([step["number"] for step in selected] == sorted({step["number"] for step in selected}),
             "compiler publication steps are out of order")
    _require(all(_timestamp(before["completed_at"]) <= _timestamp(after["started_at"])
                 for before, after in zip(selected, selected[1:])), "native DATA publication steps overlap")
    created = _timestamp(artifact["created_at"])
    upload = selected[-1]
    _require(_timestamp(job["started_at"]) <= _timestamp(upload["started_at"]) <= created
             < _timestamp(upload["completed_at"]) + dt.timedelta(seconds=1)
             <= _timestamp(job["completed_at"]) + dt.timedelta(seconds=1),
             "artifact chronology does not match the original native upload")
    _require(created <= _timestamp(pr.get("merged_at")), "compiler artifact postdates integration")
    if read_log:
        _compiler_upload_binding(api.log(job["id"]), artifact, upload)
    # Keep byte-origin authority separate from unrelated mutable repository/PR
    # presentation fields. Every snapshot still independently validates the
    # live protected ref, integration and all required native facts above.
    return {
        "run": {key: run[key] for key in ("id", "workflow_id", "run_attempt", "head_sha", "head_branch",
                "event", "path", "status", "conclusion", "check_suite_id", "referenced_workflows")},
        "job": {key: job[key] for key in ("id", "run_id", "run_attempt", "head_sha", "name", "status",
                "conclusion", "started_at", "completed_at", "check_run_url")},
        "steps": selected,
        "check": {"id": check["id"], "app": check["app"]["id"], "suite": check["check_suite"]["id"]},
        "integration": {"commit": integrated["sha"], "tree": integrated["tree"]["sha"],
                        "parents": parents, "merged_at": pr["merged_at"]},
        "writer": writer, "source": source,
    }


def fail(message: str) -> "None":
    raise SystemExit(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tar_info(path: Path, relative: Path) -> tarfile.TarInfo:
    info = tarfile.TarInfo(relative.as_posix())
    metadata = path.lstat()
    info.mode = stat.S_IMODE(metadata.st_mode)
    info.mtime = 0
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    if stat.S_ISDIR(metadata.st_mode):
        info.type = tarfile.DIRTYPE
    elif stat.S_ISLNK(metadata.st_mode):
        info.type = tarfile.SYMTYPE
        info.linkname = os.readlink(path)
    elif stat.S_ISREG(metadata.st_mode):
        info.type = tarfile.REGTYPE
        info.size = metadata.st_size
    else:
        fail(f"unsupported file type in Qt prefix: {path}")
    return info


def create_archive(prefix: Path, archive: Path, kind: str) -> None:
    archive.parent.mkdir(parents=True, exist_ok=True)
    temporary = archive.with_suffix(archive.suffix + ".tmp")
    with temporary.open("wb") as raw:
        # Qt source is already XZ-compressed; store it without recompression.
        # Compiler objects are also compressed, so use only a light gzip pass.
        compression = 0 if kind == "qt-source" else (1 if kind in ("client-sccache", "qt-sccache") else 9)
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0,
                           compresslevel=compression) as compressed:
            with tarfile.open(fileobj=compressed, mode="w") as output:
                paths = sorted(prefix.rglob("*"), key=lambda item: item.relative_to(prefix).as_posix())
                if len(paths) > MEMBER_LIMITS[kind]:
                    fail("checkpoint prefix exceeds the member limit")
                expanded = sum(path.lstat().st_size for path in paths if path.is_file() and not path.is_symlink())
                if expanded > EXPANDED_LIMITS[kind]:
                    fail("checkpoint prefix exceeds the expanded-size limit")
                for path in paths:
                    relative = path.relative_to(prefix)
                    info = _tar_info(path, relative)
                    if info.isreg():
                        with path.open("rb") as source:
                            output.addfile(info, source)
                    else:
                        output.addfile(info)
    os.replace(temporary, archive)
    if archive.stat().st_size > ARCHIVE_LIMITS[kind]:
        archive.unlink()
        fail("checkpoint archive exceeds the compressed-size limit")


def create(args: argparse.Namespace) -> None:
    prefix = Path(args.prefix).resolve()
    if not prefix.is_dir():
        fail(f"{args.kind} checkpoint prefix is not a directory: {prefix}")
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    archive = output / ARCHIVE_NAME
    create_archive(prefix, archive, args.kind)
    manifest = {
        "schema": SCHEMA,
        "kind": args.kind,
        "cacheKey": args.cache_key,
        "producerRepositoryId": int(args.producer_repository_id),
        "producerBranch": args.producer_branch,
        "archive": ARCHIVE_NAME,
        "sha256": sha256(archive),
        "size": archive.stat().st_size,
    }
    (output / MANIFEST_NAME).write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def select_artifact(
    artifacts: list[dict], prefix: str, expected_repository_id: int, expected_branch: str
) -> dict | None:
    candidates = [
        artifact
        for artifact in artifacts
        if artifact.get("name", "").startswith(prefix + "-")
        and not artifact.get("expired", False)
        and artifact.get("workflow_run", {}).get("repository_id") == expected_repository_id
        and artifact.get("workflow_run", {}).get("head_repository_id") == expected_repository_id
        and artifact.get("workflow_run", {}).get("head_branch") == expected_branch
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda item: (item.get("created_at", ""), int(item.get("id", 0))))


def _read_limited(response, limit: int, output=None) -> bytes:
    collected = bytearray()
    total = 0
    while True:
        chunk = response.read(min(1024 * 1024, limit + 1 - total))
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            fail("GitHub response exceeds its safety limit")
        if output is None:
            collected.extend(chunk)
        else:
            output.write(chunk)
    return bytes(collected)


def _github_request(url: str, token: str, limit: int = API_JSON_LIMIT) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "overte-qt-checkpoint",
        },
    )
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return _read_limited(response, limit)
        except urllib.error.HTTPError:
            raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == 3:
                fail("GitHub artifact API remained unavailable after four verified-TLS attempts")
            time.sleep(2 ** attempt)
    raise AssertionError("unreachable")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, file_pointer, code, message, headers, new_url):
        return None


def download_artifact(url: str, token: str, destination: Path, limit: int, opener=None) -> None:
    opener = opener or urllib.request.build_opener(_NoRedirect()).open
    authenticated = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "overte-qt-checkpoint",
        },
    )
    try:
        first = opener(authenticated)
    except urllib.error.HTTPError as error:
        if error.code not in (301, 302, 303, 307, 308):
            raise
        first = error
    try:
        location = first.headers.get("Location")
        if not location:
            fail("GitHub artifact download did not provide a redirect")
    finally:
        first.close()
    parsed = urllib.parse.urlparse(location)
    if parsed.scheme != "https" or not parsed.netloc:
        fail("GitHub artifact redirect is not a safe HTTPS URL")
    anonymous = urllib.request.Request(location, headers={"User-Agent": "overte-qt-checkpoint"})
    with opener(anonymous) as response, destination.open("wb") as output:
        _read_limited(response, limit, output)


def _read_artifact_index(path: Path, repository: str) -> list[dict] | None:
    try:
        if path.stat().st_size > API_JSON_LIMIT:
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return None
        if payload.get("schema") != ARTIFACT_INDEX_SCHEMA or payload.get("repository") != repository:
            return None
        fetched_at = payload.get("fetchedAt")
        if not isinstance(fetched_at, (int, float)) or isinstance(fetched_at, bool):
            return None
        if not 0 <= time.time() - fetched_at <= ARTIFACT_INDEX_TTL_SECONDS:
            return None
        artifacts = payload.get("artifacts")
        if not isinstance(artifacts, list) or len(artifacts) > 10_000:
            return None
        for artifact in artifacts:
            if not isinstance(artifact, dict) or not isinstance(artifact.get("name"), str):
                return None
            if not isinstance(artifact.get("workflow_run", {}), dict):
                return None
            if not isinstance(artifact.get("id"), int) or isinstance(artifact["id"], bool):
                return None
            if not isinstance(artifact.get("created_at", ""), str):
                return None
            if not isinstance(artifact.get("expired", False), bool):
                return None
        return artifacts
    except (OSError, ValueError):
        return None


def _write_artifact_index(path: Path, repository: str, artifacts: list[dict]) -> None:
    # This opt-in index is job-local metadata, never a replacement for artifact
    # provenance selection or archive/manifest validation. Publish only complete
    # API results atomically so failed pagination cannot poison later probes.
    temporary = None
    try:
        data = json.dumps({"schema": ARTIFACT_INDEX_SCHEMA, "repository": repository,
                           "fetchedAt": time.time(), "artifacts": artifacts})
        if len(data.encode("utf-8")) > API_JSON_LIMIT:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=path.name + ".", delete=False) as output:
            temporary = Path(output.name)
            output.write(data)
        os.replace(temporary, path)
    except OSError:
        # A metadata cache failure must not prevent a validated native build.
        pass
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


def _artifact_listing() -> tuple[list[dict], str]:
    token = os.environ.get("GITHUB_TOKEN", "") or os.environ.get("GH_TOKEN", "")
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    if not token or repository.count("/") != 1:
        fail("GITHUB_TOKEN (or GH_TOKEN) and owner/repository GITHUB_REPOSITORY are required")
    cache_setting = os.environ.get("OVERTE_ARTIFACT_INDEX_CACHE", "")
    cache_path = Path(cache_setting) if cache_setting else None
    artifacts = _read_artifact_index(cache_path, repository) if cache_path else None
    if artifacts is None:
        encoded_repo = "/".join(urllib.parse.quote(part, safe="") for part in repository.split("/"))
        artifacts = []
        for page in range(1, 101):
            url = f"https://api.github.com/repos/{encoded_repo}/actions/artifacts?per_page=100&page={page}"
            payload = json.loads(_github_request(url, token))
            batch = payload.get("artifacts", [])
            artifacts.extend(batch)
            if len(batch) < 100:
                if cache_path is not None:
                    _write_artifact_index(cache_path, repository, artifacts)
                break
    return artifacts, token


def find_latest(prefix: str, expected_repository_id: int, expected_branch: str) -> tuple[dict | None, str]:
    artifacts, token = _artifact_listing()
    artifact = select_artifact(artifacts, prefix, expected_repository_id, expected_branch)
    return artifact, token


def _compiler_artifact(value: dict, prefix: str) -> dict:
    _positive(value.get("id"))
    run = value.get("workflow_run", {})
    _positive(run.get("id"))
    _require(value.get("name") == f"{prefix}-{run['id']}-1" and value.get("expired") is False
             and run.get("repository_id") == COMPILER_REPOSITORY_ID
             and run.get("head_repository_id") == COMPILER_REPOSITORY_ID
             and isinstance(run.get("head_branch"), str) and bool(run["head_branch"])
             and type(value.get("size_in_bytes")) is int
             and 0 < value["size_in_bytes"] <= DOWNLOAD_LIMITS["client-sccache"]
             and isinstance(value.get("digest"), str)
             and re.fullmatch(r"sha256:[0-9a-f]{64}", value["digest"]) is not None
             and value.get("archive_download_url") ==
                 f"https://api.github.com/repos/{COMPILER_REPOSITORY}/actions/artifacts/{value['id']}/zip",
             "invalid compiler artifact metadata")
    _oid(run.get("head_sha"))
    _timestamp(value.get("created_at"))
    return value


class _SelectedCompilerData:
    """Private in-process selection; JSON/manifest fields cannot mint this proof."""

    def __init__(self, api, consumer: dict, artifact: dict, origin: dict | None):
        self.api, self.consumer, self.artifact, self.origin = api, consumer, artifact, origin

    def recheck(self) -> None:
        _require(_compiler_consumer(self.api) == self.consumer, "protected compiler consumer changed")
        current = self.api.get(f"actions/artifacts/{self.artifact['id']}")
        _require(current == self.artifact, "selected compiler artifact changed")
        if self.origin is not None:
            _require(_compiler_origin(self.api, current, self.consumer, read_log=False) == self.origin,
                     "original compiler source or native owner changed")


def _select_compiler_data(prefix: str) -> _SelectedCompilerData | None:
    artifacts, token = _artifact_listing()
    api = _CompilerAPI(token)
    consumer = _compiler_consumer(api)
    # An old protected checkpoint remains eligible under its existing branch
    # policy. Untrusted branch names never grant the new integrated admission.
    protected = select_artifact(artifacts, prefix, COMPILER_REPOSITORY_ID, COMPILER_BRANCH)
    floor = (protected.get("created_at", ""), protected["id"]) if protected else ("", 0)
    candidates = sorted((item for item in artifacts
                         if isinstance(item.get("name"), str) and item["name"].startswith(prefix + "-")
                         and not item.get("expired") and isinstance(item.get("workflow_run"), dict)
                         and item["workflow_run"].get("repository_id") == COMPILER_REPOSITORY_ID
                         and item["workflow_run"].get("head_repository_id") == COMPILER_REPOSITORY_ID
                         and (item.get("created_at", ""), item.get("id", 0)) > floor),
                        key=lambda item: (item.get("created_at", ""), item.get("id", 0)), reverse=True)
    # Decline unsupported candidates before any large archive download. A bounded
    # search may conservatively retain the existing protected checkpoint.
    for candidate in candidates[:COMPILER_CANDIDATE_LIMIT]:
        try:
            artifact = _compiler_artifact(api.get(f"actions/artifacts/{_positive(candidate.get('id'))}"), prefix)
            _require(artifact == candidate, "artifact listing changed")
            origin = _compiler_origin(api, artifact, consumer, read_log=True)
            result = _SelectedCompilerData(api, consumer, artifact, origin)
            result.recheck()
            return result
        except (CompilerUnavailable, urllib.error.HTTPError, UnicodeError, KeyError, TypeError):
            # Optional DATA, never a reason to suppress the actual build.
            continue
    if protected is None:
        return None
    artifact = _compiler_artifact(api.get(f"actions/artifacts/{_positive(protected.get('id'))}"), prefix)
    _require(artifact == protected and artifact["workflow_run"]["head_branch"] == COMPILER_BRANCH,
             "protected artifact listing changed")
    result = _SelectedCompilerData(api, consumer, artifact, None)
    result.recheck()
    return result


def download_latest(
    prefix: str, expected_repository_id: int, expected_branch: str, destination: Path, kind: str
) -> dict | None:
    artifact, token = find_latest(prefix, expected_repository_id, expected_branch)
    if artifact is None:
        return None
    download_artifact(artifact["archive_download_url"], token, destination, DOWNLOAD_LIMITS[kind])
    return artifact



# A PR may consume only protected-branch DATA through this reviewed recipe.
# The protected consumer's older integrated-feature discovery is unchanged.
COMPILER_PR_RECIPE = "9367feef078a9311919ad920bf15b0d61800cf94"
COMPILER_PR_CHECKOUT = "Check out protected compiler DATA verifier"
COMPILER_PR_RESTORE = "Restore verified protected compiler DATA for feature and fix PRs"
COMPILER_PR_NAMESPACE = "Select protected full-client compiler cache namespace"
COMPILER_PR_DIRECTORY = "build-ios/compiler-data-protected"


def _compiler_pr_local(api, tree: dict) -> None:
    """The PR never executes its own checkpoint parser or ambient imports."""
    _require(sys.flags.isolated == 1 and sys.flags.ignore_environment == 1
             and sys.flags.no_site == 1 and sys.dont_write_bytecode is True,
             "PR compiler verifier requires isolated Python startup")
    workspace = Path(os.environ.get("GITHUB_WORKSPACE", ""))
    _require(workspace.is_absolute(), "missing native workspace")
    expected = workspace / COMPILER_PR_DIRECTORY / "ios/ci/qt-checkpoint-artifact.py"
    _require(Path(__file__).absolute() == expected, "PR compiler parser is not the protected checkout")
    for path in (expected, *expected.parents):
        _require(not path.is_symlink(), "protected compiler parser path is aliased")
        if path == workspace:
            break
    for name in ("ios/ci/qt-checkpoint-artifact.py", "ios/ci/client-compiler-cache-key.py"):
        path = workspace / COMPILER_PR_DIRECTORY / name
        _require(not path.is_symlink(), "protected compiler helper is aliased")
        metadata = path.lstat()
        entry = tree.get(name, {})
        _require(stat.S_ISREG(metadata.st_mode) and metadata.st_nlink == 1
                 and ("100755" if metadata.st_mode & 0o111 else "100644") == entry.get("mode")
                 and path.read_bytes() == _compiler_blob(api, entry),
                 "PR compiler parser or namespace helper differs from protected source")


def _compiler_pr_consumer(api) -> dict:
    env = os.environ
    merge_sha = _oid(env.get("GITHUB_SHA"))
    reference = env.get("GITHUB_REF", "")
    match = re.fullmatch(r"refs/pull/([1-9][0-9]*)/merge", reference)
    _require(env.get("GITHUB_ACTIONS") == "true" and match is not None
             and env.get("GITHUB_REPOSITORY") == COMPILER_REPOSITORY
             and env.get("GITHUB_REPOSITORY_ID") == str(COMPILER_REPOSITORY_ID)
             and env.get("GITHUB_EVENT_NAME") == "pull_request"
             and env.get("GITHUB_JOB") == "integrated-configure"
             and env.get("GITHUB_RUN_ATTEMPT") == "1"
             and env.get("GITHUB_WORKFLOW_SHA") == merge_sha
             and env.get("GITHUB_WORKFLOW_REF") ==
                 f"{COMPILER_REPOSITORY}/{COMPILER_WORKFLOW}@{reference}",
             "unsupported original PR compiler consumer")
    number = int(match[1])
    pr = api.get(f"pulls/{number}")
    base, head = _oid(pr.get("base", {}).get("sha")), _oid(pr.get("head", {}).get("sha"))
    branch = pr.get("head", {}).get("ref", "")
    _require(pr.get("number") == number and pr.get("state") == "open" and pr.get("merged") is False
             and pr.get("merge_commit_sha") == merge_sha
             and pr.get("base", {}).get("ref") == COMPILER_BRANCH
             and env.get("GITHUB_BASE_REF") == COMPILER_BRANCH
             and env.get("GITHUB_HEAD_REF") == branch
             and re.fullmatch(r"(?:feature|fix)/[a-z0-9]+(?:-[a-z0-9]+)*/[a-z0-9]+(?:-[a-z0-9]+)*", branch)
             and all(pr.get(role, {}).get("repo", {}).get("id") == COMPILER_REPOSITORY_ID
                     and pr[role]["repo"].get("full_name") == COMPILER_REPOSITORY for role in ("base", "head")),
             "PR compiler source is foreign, stale or not a feature/fix PR")
    protected = api.get("branches/apple-ios")
    _require(protected.get("name") == COMPILER_BRANCH and protected.get("protected") is True
             and protected.get("commit", {}).get("sha") == base, "PR protected base advanced")
    merge = _compiler_commit(api, merge_sha)
    _require([item["sha"] for item in merge["parents"]] == [base, head],
             "PR native merge does not have the current exact B/H parents")
    base_commit = _compiler_commit(api, base)
    tree = _compiler_tree(api, base_commit["tree"]["sha"])
    candidate = _compiler_tree(api, merge["tree"]["sha"])
    for name in COMPILER_WRITER_PATHS:
        current, proposed = tree.get(name, {}), candidate.get(name, {})
        _require(current.get("type") == "blob" and current.get("mode") in ("100644", "100755")
                 and all(current.get(key) == proposed.get(key) for key in ("mode", "type", "sha")),
                 "PR changed compiler recipe, parser, key or launcher inputs")
    _require(tree[".github/workflows/ios-integrated.yml"]["sha"] == COMPILER_PR_RECIPE,
             "PR compiler recipe is not the reviewed protected consumer")
    _compiler_pr_local(api, tree)
    run_id = env.get("GITHUB_RUN_ID", "")
    _require(re.fullmatch(r"[1-9][0-9]*", run_id) is not None, "invalid PR consumer run")
    run = _compiler_run(api, int(run_id))
    _require(run.get("head_sha") == head and run.get("head_branch") == branch
             and run.get("event") == "pull_request" and run.get("path") == COMPILER_WORKFLOW
             and run.get("status") == "in_progress" and run.get("conclusion") is None,
             "PR compiler native run is not current")
    attempt = api.get(f"actions/runs/{run_id}/attempts/1")
    _require(all(attempt.get(key) == run.get(key) for key in ("id", "run_attempt", "head_sha",
                 "head_branch", "event", "path", "workflow_id", "check_suite_id", "repository",
                 "head_repository", "status", "conclusion")), "PR original attempt differs")
    pulls = run.get("pull_requests")
    _require(isinstance(pulls, list) and len(pulls) == 1 and pulls[0].get("number") == number
             and pulls[0].get("base", {}).get("sha") == base
             and pulls[0].get("head", {}).get("sha") == head, "PR native association differs")
    registration = api.get("actions/workflows/ios-build-qualification.yml")
    _require(registration.get("id") == run.get("workflow_id")
             and registration.get("path") == COMPILER_WORKFLOW
             and registration.get("name") == "iOS device build qualification"
             and registration.get("state") == "active", "PR workflow registration changed")
    references = run.get("referenced_workflows")
    _require(isinstance(references, list) and len(references) == 2
             and {item.get("path") for item in references} == {
                 f"{COMPILER_REPOSITORY}/.github/workflows/{name}@{merge_sha}"
                 for name in ("ios-integrated.yml", "ios-qt-source.yml")}
             and all(item.get("sha") == merge_sha and item.get("ref") == reference for item in references),
             "PR reusable compiler recipe source differs")
    jobs = api.get(f"actions/runs/{run_id}/attempts/1/jobs?per_page=100")
    _require(isinstance(jobs.get("jobs"), list) and jobs.get("total_count") == len(jobs["jobs"]) <= 100,
             "PR native jobs unavailable")
    owners = [job for job in jobs["jobs"] if job.get("name") == COMPILER_JOB]
    _require(len(owners) == 1, "PR compiler owner is ambiguous")
    job = owners[0]
    _positive(job.get("id"))
    check_match = re.fullmatch(re.escape(f"https://api.github.com/repos/{COMPILER_REPOSITORY}/check-runs/")
                              + r"([1-9][0-9]*)", job.get("check_run_url", ""))
    _require(job.get("run_id") == int(run_id) and job.get("run_attempt") == 1
             and job.get("head_sha") == head and job.get("status") == "in_progress"
             and job.get("conclusion") is None and check_match is not None,
             "PR compiler owner is not the current original job")
    check = api.get("check-runs/" + check_match[1])
    _require(check.get("id") == int(check_match[1]) and check.get("app", {}).get("id") == 15368
             and check.get("head_sha") == head and check.get("name") == COMPILER_JOB
             and check.get("check_suite", {}).get("id") == run["check_suite_id"]
             and check.get("status") == "in_progress" and check.get("conclusion") is None,
             "PR compiler check is not the native Actions owner")
    steps = job.get("steps")
    _require(isinstance(steps, list), "PR compiler step context unavailable")
    checkout = [step for step in steps if step.get("name") == COMPILER_PR_CHECKOUT]
    namespace = [step for step in steps if step.get("name") == COMPILER_PR_NAMESPACE]
    restore_step = [step for step in steps if step.get("name") == COMPILER_PR_RESTORE]
    _require(len(checkout) == len(namespace) == len(restore_step) == 1
             and all(step.get("status") == "completed" and step.get("conclusion") == "success"
                     for step in (checkout[0], namespace[0]))
             and restore_step[0].get("status") == "in_progress" and restore_step[0].get("conclusion") is None
             and 0 < _positive(checkout[0].get("number")) < _positive(namespace[0].get("number"))
                 < _positive(restore_step[0].get("number"))
             and _timestamp(checkout[0].get("started_at")) <= _timestamp(checkout[0].get("completed_at"))
                 <= _timestamp(namespace[0].get("started_at")) <= _timestamp(namespace[0].get("completed_at"))
                 <= _timestamp(restore_step[0].get("started_at"))
             and all(step.get("name") in {"Set up job", "Check out requested revision", COMPILER_PR_CHECKOUT,
                         COMPILER_PR_NAMESPACE} for step in steps
                     if _positive(step.get("number")) < restore_step[0]["number"]),
             "protected PR restore did not precede all candidate script execution")
    return {"sha": base, "tree": tree, "run": run_id, "path": COMPILER_WORKFLOW,
            "job": job["id"], "PR": number, "head": head, "merge": merge_sha, "branch": branch,
            "suite": run["check_suite_id"], "check": check["id"], "checkout": checkout[0], "namespace": namespace[0]}


def _compiler_protected_origin(api, artifact: dict, consumer: dict, *, read_log: bool) -> dict:
    """A branch label cannot replace the actual protected native writer."""
    run_id = _positive(artifact["workflow_run"].get("id"))
    run = _compiler_run(api, run_id)
    allowed = (".github/workflows/ios-integrated.yml", ".github/workflows/ios-bootstrap.yml")
    _require(run.get("head_sha") == artifact["workflow_run"].get("head_sha")
             and artifact["workflow_run"].get("head_branch") == run.get("head_branch") == COMPILER_BRANCH
             and run.get("event") in ("push", "workflow_dispatch") and run.get("path") in allowed
             and run.get("status") == "completed" and run.get("conclusion") in ("success", "failure"),
             "unsupported protected compiler producer")
    source = run["head_sha"]
    _compiler_ancestor(api, source, consumer["sha"])
    registration = api.get("actions/workflows/" + run["path"].rsplit("/", 1)[1])
    _require(registration.get("id") == run.get("workflow_id") and registration.get("path") == run["path"]
             and registration.get("state") == "active", "protected writer registration changed")
    tree = _compiler_tree(api, _compiler_commit(api, source)["tree"]["sha"])
    writer = {}
    for name in (*COMPILER_WRITER_PATHS, *((allowed[1],) if run["path"] == allowed[1] else ())):
        original, current = tree.get(name, {}), consumer["tree"].get(name, {})
        _require(original.get("mode") == current.get("mode") and original.get("type") == "blob"
                 and original.get("sha") in {current.get("sha"), *COMPILER_LEGACY_WRITERS.get(name, ())},
                 "unreviewed protected compiler writer")
        _compiler_blob(api, original)
        writer[name] = original["sha"]
    if run["path"] == allowed[1]:
        references = run.get("referenced_workflows")
        _require(isinstance(references, list) and 1 <= len(references) <= 2
                 and len({item.get("path") for item in references}) == len(references)
                 and f"{COMPILER_REPOSITORY}/{allowed[0]}@{source}" in {item.get("path") for item in references}
                 and all(item.get("path") in {
                     f"{COMPILER_REPOSITORY}/{name}@{source}"
                     for name in (allowed[0], ".github/workflows/ios-qt-source.yml")}
                     and item.get("sha") == source and item.get("ref") == "refs/heads/apple-ios"
                     for item in references), "protected reusable writer graph differs")
    jobs = api.get(f"actions/runs/{run_id}/attempts/1/jobs?per_page=100")
    _require(isinstance(jobs.get("jobs"), list) and jobs.get("total_count") == len(jobs["jobs"]) <= 100,
             "protected compiler jobs unavailable")
    names = {"Toolchain, dependencies, build and package"} if run["path"] == allowed[0] else {
        "integrated-ios-after-qt / Toolchain, dependencies, build and package",
        "integrated-ios-from-checkpoints / Toolchain, dependencies, build and package"}
    owners = [job for job in jobs["jobs"] if job.get("name") in names]
    _require(len(owners) == 1, "protected compiler producer owner is ambiguous")
    job = owners[0]
    _positive(job.get("id"))
    _require(job.get("run_id") == run_id and job.get("run_attempt") == 1
             and job.get("head_sha") == source and job.get("status") == "completed"
             and job.get("conclusion") in ("success", "failure"), "invalid protected compiler producer job")
    check_match = re.fullmatch(re.escape(f"https://api.github.com/repos/{COMPILER_REPOSITORY}/check-runs/")
                              + r"([1-9][0-9]*)", job.get("check_run_url", ""))
    _require(check_match is not None, "foreign protected compiler check URL")
    check = api.get("check-runs/" + check_match[1])
    _require(check.get("id") == int(check_match[1]) and check.get("app", {}).get("id") == 15368
             and check.get("head_sha") == source and check.get("name") == job["name"]
             and check.get("check_suite", {}).get("id") == run["check_suite_id"]
             and all(check.get(key) == job.get(key) for key in ("status", "conclusion", "started_at", "completed_at")),
             "protected compiler check is not the original native owner")
    selected = []
    for name in ("Verify full-client compiler checkpoint activity", "Stop full-client compiler checkpoint server",
                 "Save reusable full-client compiler checkpoint", COMPILER_UPLOAD):
        found = [step for step in job.get("steps", []) if step.get("name") == name]
        _require(len(found) == 1 and found[0].get("status") == "completed"
                 and found[0].get("conclusion") == "success", "protected compiler DATA publication step failed")
        _positive(found[0].get("number"))
        _require(_timestamp(found[0].get("started_at")) <= _timestamp(found[0].get("completed_at")),
                 "invalid protected compiler step chronology")
        selected.append(found[0])
    _require([step["number"] for step in selected] == sorted({step["number"] for step in selected})
             and all(_timestamp(left["completed_at"]) <= _timestamp(right["started_at"])
                     for left, right in zip(selected, selected[1:])), "protected compiler publication steps overlap")
    upload = selected[-1]
    _require(_timestamp(job["started_at"]) <= _timestamp(upload["started_at"])
             <= _timestamp(artifact["created_at"]) < _timestamp(upload["completed_at"]) + dt.timedelta(seconds=1)
             <= _timestamp(job["completed_at"]) + dt.timedelta(seconds=1), "protected artifact is outside its native upload")
    if read_log:
        _compiler_upload_binding(api.log(job["id"]), artifact, upload)
    return {"source": source, "writer": writer,
            "run": {key: run[key] for key in ("id", "run_attempt", "head_sha", "head_branch", "event", "path",
                "workflow_id", "check_suite_id", "status", "conclusion")},
            "job": {key: job[key] for key in ("id", "run_id", "run_attempt", "head_sha", "name", "status",
                "conclusion", "check_run_url", "started_at", "completed_at")},
            "check": {"id": check["id"], "app": check["app"]["id"], "suite": check["check_suite"]["id"]},
            "steps": selected}


class _SelectedPRCompilerData(_SelectedCompilerData):
    def __init__(self, api, consumer: dict, artifact: dict, origin: dict):
        # Preserve the old restore/report contract: this is protected-branch
        # DATA, never a direct integrated-feature selection for a PR.
        super().__init__(api, consumer, artifact, None)
        self.protected_origin = origin

    def recheck(self) -> None:
        _require(_compiler_pr_consumer(self.api) == self.consumer, "PR compiler consumer changed")
        artifact = self.api.get(f"actions/artifacts/{self.artifact['id']}")
        _require(artifact == self.artifact, "selected protected compiler artifact changed")
        _require(_compiler_protected_origin(self.api, artifact, self.consumer, read_log=False) == self.protected_origin,
                 "protected compiler source or original upload owner changed")


def _select_pr_compiler_data(prefix: str) -> _SelectedPRCompilerData | None:
    artifacts, token = _artifact_listing()
    api = _CompilerAPI(token)
    consumer = _compiler_pr_consumer(api)
    candidates = sorted((item for item in artifacts
                         if isinstance(item.get("name"), str) and item["name"].startswith(prefix + "-")
                         and item.get("expired") is False and isinstance(item.get("workflow_run"), dict)
                         and item["workflow_run"].get("head_branch") == COMPILER_BRANCH),
                        key=lambda item: (item.get("created_at", ""), item.get("id", 0)), reverse=True)
    for candidate in candidates[:COMPILER_CANDIDATE_LIMIT]:
        try:
            artifact = _compiler_artifact(api.get(f"actions/artifacts/{_positive(candidate.get('id'))}"), prefix)
            _require(artifact == candidate, "protected compiler listing changed")
            origin = _compiler_protected_origin(api, artifact, consumer, read_log=True)
            selected = _SelectedPRCompilerData(api, consumer, artifact, origin)
            selected.recheck()
            return selected
        except (CompilerUnavailable, urllib.error.HTTPError, UnicodeError, KeyError, TypeError):
            continue
    return None


def restore_pr_compiler(args: argparse.Namespace) -> None:
    _require(re.fullmatch(r"overte-ios-client-objects-v2-[A-Za-z0-9_+-]+-" + re.escape(args.cache_key),
                         args.artifact_prefix) is not None
             and re.fullmatch(r"[0-9a-f]{64}", args.cache_key) is not None,
             "PR compiler namespace is not the actual toolchain namespace")
    selection = _select_pr_compiler_data(args.artifact_prefix)
    if selection is None:
        set_outputs(Path(args.github_output), available=False, fresh=False, restored=False)
        return
    restore(args, selection=selection)


def _safe_name(name: str) -> PurePosixPath:
    path = PurePosixPath(name)
    if not name or path.is_absolute() or ".." in path.parts or "\\" in name:
        fail(f"unsafe archive path: {name!r}")
    return path


def unpack_payload(workflow_zip: Path, destination: Path, kind: str) -> None:
    with zipfile.ZipFile(workflow_zip) as source:
        infos = source.infolist()
        names = [info.filename for info in infos]
        if names.count(ARCHIVE_NAME) != 1 or names.count(MANIFEST_NAME) != 1 or len(infos) != 2:
            fail("workflow artifact must contain exactly two unique root files")
        entries = {info.filename: info for info in infos}
        for name in (ARCHIVE_NAME, MANIFEST_NAME):
            info = entries[name]
            if info.is_dir():
                fail(f"workflow artifact entry is not a file: {name}")
            limit = MANIFEST_LIMIT if name == MANIFEST_NAME else ARCHIVE_LIMITS[kind]
            if info.file_size > limit:
                fail(f"workflow artifact entry exceeds its safety limit: {name}")
            with source.open(info) as incoming, (destination / name).open("wb") as outgoing:
                _read_limited(incoming, limit, outgoing)


def validate_manifest(directory: Path, kind: str, cache_key: str) -> Path:
    try:
        manifest_path = directory / MANIFEST_NAME
        if manifest_path.stat().st_size > MANIFEST_LIMIT:
            fail("checkpoint manifest exceeds its safety limit")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        fail(f"invalid checkpoint manifest: {error}")
    if manifest.get("schema") != SCHEMA:
        fail("unsupported checkpoint manifest schema")
    if manifest.get("kind") != kind or manifest.get("cacheKey") != cache_key:
        fail("checkpoint kind or cache key does not match the request")
    if manifest.get("archive") != ARCHIVE_NAME:
        fail("checkpoint manifest names an unexpected archive")
    archive = directory / ARCHIVE_NAME
    if sha256(archive) != manifest.get("sha256"):
        fail("checkpoint archive SHA-256 mismatch")
    if archive.stat().st_size != manifest.get("size"):
        fail("checkpoint archive size mismatch")
    return archive


def _safe_link(member: tarfile.TarInfo) -> None:
    target = PurePosixPath(member.linkname)
    combined = PurePosixPath(member.name).parent / target
    depth = 0
    if target.is_absolute() or "\\" in member.linkname:
        fail(f"unsafe link target: {member.linkname!r}")
    for part in combined.parts:
        depth += -1 if part == ".." else (0 if part in ("", ".") else 1)
        if depth < 0:
            fail(f"link escapes checkpoint root: {member.name!r}")


def safe_extract(archive: Path, destination: Path, kind: str = "host") -> None:
    with tarfile.open(archive, "r:gz") as source:
        members = []
        expanded = 0
        for member in source:
            if len(members) >= MEMBER_LIMITS[kind]:
                fail("checkpoint archive exceeds the member limit")
            if member.isreg():
                expanded += member.size
                if expanded > EXPANDED_LIMITS[kind]:
                    fail("checkpoint archive exceeds the expanded-size limit")
            _safe_name(member.name)
            if member.issym() or member.islnk():
                _safe_link(member)
            elif not (member.isdir() or member.isreg()):
                fail(f"unsupported checkpoint archive member: {member.name!r}")
            members.append(member)
        for member in members:
            target = destination.joinpath(*PurePosixPath(member.name).parts)
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                os.chmod(target, member.mode & 0o777)
            elif member.isreg():
                target.parent.mkdir(parents=True, exist_ok=True)
                incoming = source.extractfile(member)
                if incoming is None:
                    fail(f"cannot read checkpoint member: {member.name!r}")
                with incoming, target.open("wb") as outgoing:
                    shutil.copyfileobj(incoming, outgoing)
                os.chmod(target, member.mode & 0o777)
            elif member.issym():
                target.parent.mkdir(parents=True, exist_ok=True)
                os.symlink(member.linkname, target)
            else:
                fail("hard links are not accepted in checkpoint archives")


def set_outputs(path: Path, **values: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as output:
        for key, value in values.items():
            output.write(f"{key}={'true' if value else 'false'}\n")


def is_fresh(artifact: dict, max_age_days: int) -> bool:
    try:
        created = dt.datetime.fromisoformat(artifact["created_at"].replace("Z", "+00:00"))
    except (KeyError, ValueError):
        return False
    age = dt.datetime.now(dt.timezone.utc) - created
    return dt.timedelta(0) <= age <= dt.timedelta(days=max_age_days)


def probe(args: argparse.Namespace) -> None:
    artifact, _ = find_latest(
        args.artifact_prefix, int(args.expected_repository_id), args.expected_branch
    )
    available = artifact is not None
    set_outputs(
        Path(args.github_output),
        available=available,
        fresh=available and is_fresh(artifact, args.max_age_days),
    )


def restore(args: argparse.Namespace, *, selection: _SelectedCompilerData | None = None) -> None:
    output = Path(args.github_output)
    install_root = Path(args.install_root)
    target_name = {
        "host": "macos", "ios": "ios", "v8": "v8-ios", "conan": "conan-home",
        "client-sccache": "client-sccache", "qt-sccache": "qt-sccache",
        "qt-source": "downloads",
    }[args.kind]
    target_root = install_root / target_name
    with tempfile.TemporaryDirectory(prefix="overte-qt-checkpoint-") as temporary_name:
        temporary = Path(temporary_name)
        workflow_zip = temporary / "artifact.zip"
        try:
            if selection is None:
                artifact = download_latest(
                    args.artifact_prefix, int(args.expected_repository_id), args.expected_branch,
                    workflow_zip, args.kind,
                )
            else:
                artifact = selection.artifact
                selection.api.archive(artifact, workflow_zip)
                _require(workflow_zip.stat().st_size == artifact["size_in_bytes"]
                         and "sha256:" + sha256(workflow_zip) == artifact["digest"],
                         "selected compiler ZIP size or whole digest changed")
        except urllib.error.HTTPError as error:
            fail(f"GitHub artifact API failed with HTTP {error.code}")
        if artifact is None:
            set_outputs(output, available=False, fresh=False, restored=False)
            return
        fresh = is_fresh(artifact, args.max_age_days)
        payload = temporary / "payload"
        payload.mkdir()
        unpack_payload(workflow_zip, payload, args.kind)
        archive = validate_manifest(payload, args.kind, args.cache_key)
        manifest = json.loads((payload / MANIFEST_NAME).read_text(encoding="utf-8"))
        if manifest.get("producerRepositoryId") != int(args.expected_repository_id):
            fail("checkpoint manifest repository does not match the request")
        expected_branch = (selection.artifact["workflow_run"]["head_branch"]
                           if selection is not None else args.expected_branch)
        if manifest.get("producerBranch") != expected_branch:
            fail("checkpoint manifest branch does not match the request")
        install_root.mkdir(parents=True, exist_ok=True)
        staged = install_root / f".{target_root.name}.restore-{os.getpid()}"
        if target_root.exists() or staged.exists():
            fail(f"Qt install root already exists: {target_root}")
        staged.mkdir(parents=True)
        try:
            safe_extract(archive, staged, args.kind)
            if selection is not None:
                selection.recheck()
            os.replace(staged, target_root)
        finally:
            if staged.exists():
                shutil.rmtree(staged)
    set_outputs(output, available=True, fresh=fresh, restored=True)
    if selection is not None:
        print(json.dumps({"kind": "compiler-checkpoint-data", "artifactId": artifact["id"],
                          "runId": artifact["workflow_run"]["id"], "attempt": 1,
                          "source": artifact["workflow_run"]["head_sha"],
                          "producerBranch": expected_branch, "zipDigest": artifact["digest"],
                          "cacheKey": args.cache_key,
                          "selection": "integrated-native-writer" if selection.origin else "protected-branch"},
                         sort_keys=True))


def restore_protected_compiler(args: argparse.Namespace) -> None:
    _require(re.fullmatch(r"overte-ios-client-objects-v2-[A-Za-z0-9_+-]+-" + re.escape(args.cache_key),
                         args.artifact_prefix) is not None
             and re.fullmatch(r"[0-9a-f]{64}", args.cache_key) is not None,
             "compiler namespace is not the actual toolchain namespace")
    selection = _select_compiler_data(args.artifact_prefix)
    if selection is None:
        set_outputs(Path(args.github_output), available=False, fresh=False, restored=False)
        return
    restore(args, selection=selection)


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser()
    commands = result.add_subparsers(dest="command", required=True)
    create_parser = commands.add_parser("create")
    create_parser.add_argument("--prefix", required=True)
    create_parser.add_argument("--kind", choices=tuple(DOWNLOAD_LIMITS), required=True)
    create_parser.add_argument("--cache-key", required=True)
    create_parser.add_argument("--producer-repository-id", required=True)
    create_parser.add_argument("--producer-branch", required=True)
    create_parser.add_argument("--output-dir", required=True)
    create_parser.set_defaults(handler=create)
    restore_parser = commands.add_parser("restore")
    restore_parser.add_argument("--artifact-prefix", required=True)
    restore_parser.add_argument("--kind", choices=tuple(DOWNLOAD_LIMITS), required=True)
    restore_parser.add_argument("--cache-key", required=True)
    restore_parser.add_argument("--expected-repository-id", required=True, type=int)
    restore_parser.add_argument("--expected-branch", required=True)
    restore_parser.add_argument("--max-age-days", type=int, default=21)
    restore_parser.add_argument("--install-root", required=True)
    restore_parser.add_argument("--github-output", required=True)
    restore_parser.set_defaults(handler=restore)
    compiler_parser = commands.add_parser("restore-protected-compiler")
    for name in ("artifact-prefix", "cache-key", "install-root", "github-output"):
        compiler_parser.add_argument("--" + name, required=True)
    compiler_parser.add_argument("--max-age-days", type=int, default=21)
    compiler_parser.set_defaults(handler=restore_protected_compiler, kind="client-sccache",
                                 expected_repository_id=COMPILER_REPOSITORY_ID,
                                 expected_branch=COMPILER_BRANCH)
    pr_parser = commands.add_parser("restore-pr-compiler")
    for name in ("artifact-prefix", "cache-key", "install-root", "github-output"):
        pr_parser.add_argument("--" + name, required=True)
    pr_parser.add_argument("--max-age-days", type=int, default=21)
    pr_parser.set_defaults(handler=restore_pr_compiler, kind="client-sccache",
                           expected_repository_id=COMPILER_REPOSITORY_ID,
                           expected_branch=COMPILER_BRANCH)
    probe_parser = commands.add_parser("probe")
    probe_parser.add_argument("--artifact-prefix", required=True)
    probe_parser.add_argument("--expected-repository-id", required=True, type=int)
    probe_parser.add_argument("--expected-branch", required=True)
    probe_parser.add_argument("--max-age-days", type=int, default=21)
    probe_parser.add_argument("--github-output", required=True)
    probe_parser.set_defaults(handler=probe)
    return result


def main() -> None:
    args = parser().parse_args()
    args.handler(args)


if __name__ == "__main__":
    main()
