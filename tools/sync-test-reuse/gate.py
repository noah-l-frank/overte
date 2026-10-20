#!/usr/bin/env python3
"""Fail-closed live verifier for exact-parent qualification reuse."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from fnmatch import fnmatch
from pathlib import Path
from urllib.parse import quote
import argparse
import hashlib
import importlib.util
import io
import json
import os
import re
import stat
import subprocess
import sys
import time
import zipfile
import xml.etree.ElementTree as ET

# Native source admission includes every import lookup member. Do not create
# bytecode in that protected lookup before it is independently authenticated.
sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = ROOT / ".github/sync-test-reuse.json"
SHA_RE = re.compile(r"[0-9a-f]{40}")
_policy_spec = importlib.util.spec_from_file_location("sync_branch_policy", ROOT / "tools/branch-policy/check.py")
assert _policy_spec and _policy_spec.loader
branch_policy = importlib.util.module_from_spec(_policy_spec)
sys.modules[_policy_spec.name] = branch_policy
_policy_spec.loader.exec_module(branch_policy)
_tool_spec = importlib.util.spec_from_file_location(
    "sync_tool_dependencies", ROOT / "tools/repository-checks/tool_dependencies.py")
tool_dependencies = importlib.util.module_from_spec(_tool_spec)
_tool_spec.loader.exec_module(tool_dependencies)
_package_spec = importlib.util.spec_from_file_location(
    "sync_package_checks", ROOT / "tools/repository-checks/package_checks.py")
package_checks = importlib.util.module_from_spec(_package_spec)
_package_spec.loader.exec_module(package_checks)
_input_spec = importlib.util.spec_from_file_location(
    "sync_suite_inputs", ROOT / "tools/test-evidence/inputs.py")
suite_inputs = importlib.util.module_from_spec(_input_spec)
_input_spec.loader.exec_module(suite_inputs)


class GateError(ValueError):
    """The request cannot be authorized as a sync."""


class _DispatchRegistrationPending(GateError):
    """The owned run is nonterminal and native registration is incomplete."""

    def __init__(self, message, check_suite_id=None):
        super().__init__(message)
        self.check_suite_id = check_suite_id


class EvidenceError(ValueError):
    """Qualification evidence is absent or unusable, requiring full fallback."""


class NativeSyncOwnerError(GateError):
    """A selected original PR owner must not fall through to another executor."""


class NativePrEvidence(dict):
    """Authenticated completed execution of this exact PR, never parent proof."""


def canonical_json(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def digest_entries(entries: list[dict[str, str]]) -> str:
    return "sha256:" + hashlib.sha256(canonical_json(entries)).hexdigest()


def parse_time(value: object, label: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise EvidenceError(f"{label} is not a UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise EvidenceError(f"{label} is invalid") from error
    return parsed


def validate_sha(value: object, label: str, error_type=GateError) -> str:
    if not isinstance(value, str) or not SHA_RE.fullmatch(value):
        raise error_type(f"{label} must be a full lowercase SHA")
    return value


def safe_api_error(error: Exception) -> str:
    """Classify a failed CLI request without emitting commands or response text."""
    if isinstance(error, subprocess.CalledProcessError):
        stderr = error.stderr or ""
        if isinstance(stderr, bytes):
            stderr = stderr.decode("utf-8", errors="replace")
        statuses = re.findall(r"\(HTTP ([1-5][0-9]{2})\)", stderr)
        status = statuses[-1] if statuses else "unknown"
        return f"command exit={error.returncode} http={status}"
    if isinstance(error, json.JSONDecodeError):
        return "invalid-json"
    if isinstance(error, OSError):
        return f"os-error errno={error.errno if error.errno is not None else 'unknown'}"
    return "unknown-error"


class GitHubApi:
    """Small gh-backed API adapter; errors never degrade into authorization."""

    def json(self, endpoint: str, *, method: str = "GET", fields: dict[str, str] | None = None,
             dispatch_details: bool = False) -> object:
        command = ["gh", "api"]
        if method != "GET":
            command += ["--method", method]
        command.append(endpoint)
        if dispatch_details:
            if method != "POST" or endpoint != "repos/noah-l-frank/overte/actions/workflows/sync-validation.yml/dispatches":
                raise GateError("run details are only supported for the fixed validation dispatch")
            command += ["-H", "X-GitHub-Api-Version: 2022-11-28",
                        "-F", "return_run_details=true"]
        for key, value in (fields or {}).items():
            command += ["-f", f"{key}={value}"]
        try:
            result = subprocess.run(
                command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True,
            )
            return json.loads(result.stdout) if result.stdout.strip() else {}
        except (OSError, subprocess.CalledProcessError, json.JSONDecodeError) as error:
            raise GateError(f"GitHub API request failed: {endpoint} ({safe_api_error(error)})") from error

    def bytes(self, endpoint: str) -> bytes:
        try:
            return subprocess.run(
                ["gh", "api", endpoint], check=True, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            ).stdout
        except (OSError, subprocess.CalledProcessError) as error:
            raise EvidenceError(f"qualification artifact download failed ({safe_api_error(error)})") from error

    def native_producer_api(self, controller):
        """Use the existing fixed-fork, versioned, bounded GET transport."""
        return controller.A.GitHubReadOnly()


@dataclass(frozen=True)
class SyncRequest:
    repository: str
    repository_id: int
    number: int
    base: str
    base_sha: str
    head: str
    head_sha: str
    head_repository_id: int
    merge_sha: str
    classification: str
    parent: str
    parent_sha: str
    profile: str
    changed_paths: tuple[str, ...]
    parent_changed_paths: tuple[str, ...]
    repair_paths: tuple[str, ...] = ()
    event_base_sha: str | None = None


@dataclass(frozen=True)
class EffectivePRContext:
    base: str
    head: str
    candidate: str
    event_base: str

    def planning(self):
        return {key: getattr(self, key) for key in ('base', 'head', 'candidate', 'event_base')}


def _base_source():
    spec = importlib.util.spec_from_file_location('sync_effective_base_source', ROOT / 'tools/test-evidence/source_admission.py')
    if spec is None or spec.loader is None:
        raise GateError('trusted live-base source resolver unavailable')
    source = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(source)
    return source


def _base_reader(api, repository):
    if repository != 'noah-l-frank/overte':
        raise GateError('effective base source is outside the reviewed fork')
    class Reader:
        def get(self, endpoint):
            return api.json('repos/' + repository + ('/' + endpoint if endpoint else ''))
    return Reader()


def _native_effective_role(api, event, live_base):
    """Authenticate fixed gate/validator roles before stale-base resolution."""
    env = os.environ
    if any(env.get(key) != value for key, value in {
            'GITHUB_ACTIONS': 'true', 'GITHUB_REPOSITORY': 'noah-l-frank/overte',
            'GITHUB_REPOSITORY_ID': '1319052603', 'GITHUB_RUN_ATTEMPT': '1'}.items()):
        raise GateError('target snapshot drifted; stale-base resolution needs an actual native synchronization role')
    repo = 'noah-l-frank/overte'
    pr = event['pull_request']; target = pr['base']['ref']
    try:
        identifier = int(env.get('GITHUB_RUN_ID', ''))
    except ValueError as error:
        raise GateError('native synchronization run unavailable') from error
    if identifier <= 0:
        raise GateError('native synchronization run unavailable')
    manual = env.get('GITHUB_EVENT_NAME') == 'workflow_dispatch'
    if manual:
        path, workflow, job, ref = '.github/workflows/sync-validation.yml', 350930895, 'validate', 'refs/heads/main'
        default = api.json(f'repos/{repo}/branches/main')
        if default.get('name') != 'main' or default.get('protected') is not True:
            raise GateError('native validation default source unavailable')
        source_sha = validate_sha(default.get('commit', {}).get('sha'), 'native validation source')
    else:
        path, workflow, job, ref = '.github/workflows/sync-test-reuse.yml', 350930894, 'sync-test-reuse', 'refs/heads/' + target
        # The native caller may retain an older base snapshot. Authenticate its
        # actual source separately; only current M.parent0/ref defines live B.
        source_sha = validate_sha(env.get('GITHUB_SHA'), 'native synchronization caller source')
        if env.get('GITHUB_EVENT_NAME') != 'pull_request_target':
            raise GateError('unknown native synchronization role')
        if env.get('GITHUB_BASE_REF') != target or env.get('GITHUB_HEAD_REF') != pr['head']['ref']:
            raise GateError('native synchronization PR branch refs differ')
    if (env.get('GITHUB_JOB') != job or env.get('GITHUB_REF') != ref
            or env.get('GITHUB_SHA') != source_sha or env.get('GITHUB_WORKFLOW_SHA') != source_sha
            or env.get('GITHUB_WORKFLOW_REF') != repo + '/' + path + '@' + ref):
        raise GateError('native synchronization source/ref differs')

    def native_run(run_id, expected_source, expected_path, expected_workflow, expected_event):
        run = api.json(f'repos/{repo}/actions/runs/{run_id}')
        attempt = api.json(f'repos/{repo}/actions/runs/{run_id}/attempts/1')
        fields = ('id', 'workflow_id', 'check_suite_id', 'event', 'path', 'head_sha', 'head_branch',
                  'run_attempt', 'run_started_at', 'status', 'conclusion')
        if (any(run.get(key) != attempt.get(key) for key in fields)
                or (run.get('id'), run.get('workflow_id'), run.get('event'), run.get('path'), run.get('head_sha'), run.get('run_attempt')) !=
                   (run_id, expected_workflow, expected_event, expected_path, expected_source, 1)
                or run.get('head_branch') != ('main' if expected_event == 'workflow_dispatch' else pr['head']['ref'])
                or not (run.get('status') in {'queued', 'in_progress', 'waiting', 'pending'} and run.get('conclusion') is None
                        or run.get('status') == 'completed' and run.get('conclusion') == 'success')
                or any(document.get(key, {}).get('id') != 1319052603 or document[key].get('full_name') != repo
                       for document in (run, attempt) for key in ('repository', 'head_repository'))):
            raise GateError('native synchronization run/attempt/source unavailable')
        registration = api.json(f'repos/{repo}/actions/workflows/{expected_workflow}')
        suite = api.json(f'repos/{repo}/check-suites/{run["check_suite_id"]}')
        if (registration.get('id') != expected_workflow or registration.get('path') != expected_path or registration.get('state') != 'active'
                or suite.get('id') != run['check_suite_id'] or suite.get('head_sha') != expected_source or suite.get('app', {}).get('id') != 15368
                or suite.get('repository', {}).get('id') != 1319052603):
            raise GateError('native synchronization registration/App unavailable')
        try:
            started = parse_time(run.get('run_started_at'), 'native synchronization start')
        except EvidenceError as error:
            raise GateError('native synchronization start unavailable') from error
        if started > datetime.now(timezone.utc):
            raise GateError('native synchronization starts in the future')
        return run, attempt

    run, attempt = native_run(identifier, source_sha if manual else pr['head']['sha'], path, workflow, env['GITHUB_EVENT_NAME'])
    if manual:
        manual_started = parse_time(run.get('run_started_at'), 'native validation start')
        match = re.fullmatch(r'Sync validation gate-([1-9][0-9]*)-attempt-1', run.get('display_title', ''))
        if match is None:
            raise GateError('native validation gate handoff unavailable')
        run, attempt = native_run(int(match[1]), pr['head']['sha'], '.github/workflows/sync-test-reuse.yml', 350930894, 'pull_request_target')
        if parse_time(run.get('run_started_at'), 'native gate start') > manual_started:
            raise GateError('native validation precedes its original gate')
    associations = []
    for document in (run, attempt):
        associated = [row for row in document.get('pull_requests', []) if row.get('number') == pr['number']]
        if len(associated) != 1 or associated[0].get('base', {}).get('ref') != target or any(
                associated[0].get('head', {}).get(key) != pr['head'][key] for key in ('ref', 'sha')):
            raise GateError('native synchronization PR association unavailable')
        associations.append(associated[0])
    source = _base_source()
    try:
        reader = _base_reader(api, repo)
        if not manual:
            source.validate_base_snapshot(reader, source_sha, live_base)
        for association in associations:
            source.validate_base_snapshot(reader, association.get('base', {}).get('sha'), live_base)
        default = reader.get('branches/main')
        if default.get('name') != 'main' or default.get('protected') is not True:
            raise GateError('trusted synchronization controller source unavailable')
        default_sha = validate_sha(default.get('commit', {}).get('sha'), 'trusted default source')
        actual = subprocess.check_output(['git', '--no-replace-objects', 'rev-parse', 'HEAD'], cwd=ROOT,
                                         stderr=subprocess.PIPE, timeout=30).decode().strip()
        if actual != default_sha:
            raise GateError('synchronization controller checkout differs from current default')
        for revision, recipe in ((source_sha, path), (live_base, '.github/workflows/sync-test-reuse.yml')):
            inventory = source.api_tree(reader, revision)
            row = subprocess.check_output(['git', '--no-replace-objects', 'ls-tree', default_sha, '--', recipe],
                                          cwd=ROOT, stderr=subprocess.PIPE, timeout=30).split()
            if len(row) != 4 or row[:2] != [b'100644', b'blob'] or inventory.get(recipe) != {
                    'mode': '100644', 'type': 'blob', 'sha': row[2].decode()}:
                raise GateError('native synchronization workflow recipe differs from protected controller source')
    except (source.SourceUnavailable, KeyError, TypeError, ValueError, OSError, subprocess.SubprocessError) as error:
        raise GateError('native synchronization base snapshot unavailable') from error


def effective_pr_context(event, api):
    """Return internal scheduling context only after fresh native/API proof."""
    pr = event['pull_request']; repo = event['repository']['full_name']
    snapshot = validate_sha(pr['base']['sha'], 'event base snapshot')
    live = branch_sha(api, repo, pr['base']['ref'])
    current = api.json(f'repos/{repo}/pulls/{pr["number"]}')
    if not isinstance(current, dict):
        raise GateError('current synchronization PR observation unavailable')
    if live == snapshot and current.get('base', {}).get('sha') == live:
        return None
    _native_effective_role(api, event, live)
    merge = api.json(f'repos/{repo}/commits/refs/pull/{pr["number"]}/merge')
    if commit_parents(merge) != (live, pr['head']['sha']):
        raise GateError('current synchronization merge does not use live base/head')
    source = _base_source()
    try:
        resolved = source.resolve_pr_base(_base_reader(api, repo), current, merge, event_pr=pr)
    except (source.SourceUnavailable, KeyError, TypeError, ValueError, OSError) as error:
        raise GateError('live synchronization base cannot be independently resolved') from error
    if resolved['base'] != live:
        raise GateError('protected synchronization base moved')
    return EffectivePRContext(resolved['base'], resolved['head'], resolved['source'], snapshot)


def immutable_change_documents(api, repository, base, candidate):
    """Complete B-to-M membership/mode/byte delta, never capped PR files."""
    _, before = recursive_tree(api, repository, base, error_type=GateError)
    _, after = recursive_tree(api, repository, candidate, error_type=GateError)
    return [{'filename': path, 'status': 'added' if path not in before else 'removed' if path not in after else 'modified'}
            for path in sorted(before.keys() | after.keys()) if before.get(path) != after.get(path)]


def recheck_effective_request(api, request, *, event_pr=None):
    """Reconstruct current source after work without editing an event snapshot."""
    repo = request.repository
    if branch_sha(api, repo, request.base) != request.base_sha:
        raise GateError('protected synchronization base ref changed after execution')
    current = api.json(f'repos/{repo}/pulls/{request.number}')
    event = {'repository': {'full_name': repo, 'id': request.repository_id}, 'pull_request': current}
    _native_effective_role(api, event, request.base_sha)
    source = _base_source()
    try:
        merge = api.json(f'repos/{repo}/commits/refs/pull/{request.number}/merge')
        if commit_parents(merge) != (request.base_sha, request.head_sha):
            raise GateError('current synchronization merge parents changed after execution')
        reader = _base_reader(api, repo)
        resolved = source.resolve_pr_base(reader, current, merge, event_pr=event_pr)
        source.validate_base_snapshot(reader, request.event_base_sha, resolved['base'])
    except (source.SourceUnavailable, KeyError, TypeError, ValueError, OSError) as error:
        raise GateError('effective synchronization context changed after execution') from error
    if (resolved['base'], resolved['head'], resolved['target'], resolved['head_ref'], resolved['source']) != (
            request.base_sha, request.head_sha, request.base, request.head, request.merge_sha):
        raise GateError('effective synchronization context changed after execution')
    if branch_sha(api, repo, request.base) != request.base_sha:
        raise GateError('protected synchronization base ref changed during recheck')
    observation = current if event_pr is None else event_pr
    return EffectivePRContext(request.base_sha, request.head_sha, request.merge_sha, observation['base']['sha'])


def load_config(path: Path = DEFAULT_CONFIG) -> dict:
    document = json.loads(path.read_text(encoding="utf-8"))
    if document.get("schema") != 1 or not isinstance(document.get("edges"), dict):
        raise GateError("unsupported sync-test-reuse configuration")
    return document


def api_list(api: GitHubApi, endpoint: str, key: str) -> list[dict]:
    value = api.json(endpoint)
    if not isinstance(value, dict) or not isinstance(value.get(key), list):
        raise GateError(f"GitHub API omitted {key}")
    return value[key]


def branch_sha(api: GitHubApi, repository: str, branch: str) -> str:
    value = api.json(f"repos/{repository}/git/ref/heads/{quote(branch, safe='')}")
    try:
        return validate_sha(value["object"]["sha"], f"current {branch} SHA")  # type: ignore[index]
    except (KeyError, TypeError) as error:
        raise GateError(f"GitHub API omitted current {branch} SHA") from error


def commit(api: GitHubApi, repository: str, sha: str) -> dict:
    value = api.json(f"repos/{repository}/git/commits/{sha}")
    if not isinstance(value, dict) or value.get("sha") != sha:
        raise GateError("GitHub API returned mismatched commit metadata")
    return value


def commit_parents(document: dict) -> tuple[str, ...]:
    try:
        parents = tuple(validate_sha(item["sha"], "commit parent SHA") for item in document["parents"])
    except (KeyError, TypeError) as error:
        raise GateError("GitHub API returned invalid commit parents") from error
    return parents


def commit_tree(document: dict) -> str:
    try:
        return validate_sha(document["tree"]["sha"], "commit tree SHA")
    except (KeyError, TypeError) as error:
        raise GateError("GitHub API returned invalid commit tree") from error


def paginate_pull_files(api: GitHubApi, repository: str, number: int) -> list[dict]:
    files: list[dict] = []
    for page in range(1, 31):
        value = api.json(f"repos/{repository}/pulls/{number}/files?per_page=100&page={page}")
        if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
            raise GateError("GitHub API returned invalid pull-request file data")
        files.extend(value)
        if len(value) < 100:
            return files
    raise GateError("pull request exceeds the bounded changed-file audit")


def changed_paths(documents: list[dict]) -> set[str]:
    """Audit both sides of renames; path spelling never grants authorization."""
    paths = set()
    for item in documents:
        if not isinstance(item, dict) or "filename" not in item:
            raise GateError("changed-file metadata is malformed")
        if item.get("status") == "renamed" and "previous_filename" not in item:
            raise GateError("renamed file is missing its source path")
        for key in ("filename", "previous_filename"):
            if key not in item:
                continue
            path = item[key]
            if (not isinstance(path, str) or not path or "\\" in path or "\x00" in path
                    or path.startswith("/") or any(part in ("", ".", "..") for part in path.split("/"))):
                raise GateError("changed-file path is unsafe")
            paths.add(path)
    return paths


def allowed_repair_paths(config: dict, base: str) -> set[str]:
    """Exact, nonprivileged paths from the trusted default-branch configuration."""
    mapping = config.get("reconciliation_repair_paths", {})
    if not isinstance(mapping, dict) or set(mapping) - set(config["edges"]):
        raise GateError("invalid reconciliation repair targets")
    paths = mapping.get(base, [])
    if (not isinstance(paths, list) or any(not isinstance(path, str) for path in paths)
            or len(paths) != len(set(paths))):
        raise GateError("invalid reconciliation repair paths")
    changed_paths([{"filename": path} for path in paths])
    if (any(any(char in path for char in "*?[]") for path in paths)
            or branch_policy.changes_privileged_policy(tuple(paths))):
        raise GateError("repair paths must be exact and nonprivileged")
    return set(paths)


def attest_product_repair(api, repository, repository_id, pr, current_pr,
                          base, parent, head, base_sha, parent_sha, head_sha, merge_sha, *, pr_context=None):
    """Reuse the unchanged branch-policy attestation, including its drift checks."""
    class BranchApi(branch_policy.GitHubBranchApi):
        def _request(self, endpoint, label):
            value = api.json(endpoint)
            if not isinstance(value, dict):
                raise branch_policy.PolicyError(f"invalid API object for {label}")
            return value

    try:
        if pr_context is not None:
            if not isinstance(pr_context, EffectivePRContext) or pr_context.planning() != {
                    'base': base_sha, 'head': head_sha, 'candidate': merge_sha,
                    'event_base': pr['base']['sha']}:
                raise GateError('repair effective base context differs from the current candidate')
            source = _base_source()
            try:
                for document in (pr, current_pr):
                    source.validate_base_snapshot(_base_reader(api, repository), document['base']['sha'], base_sha)
            except (source.SourceUnavailable, KeyError, TypeError, ValueError, OSError) as error:
                raise GateError('repair base snapshot is not an ancestor of the current target') from error
        for document in (pr, current_pr):
            for side, ref, sha in (("base", base, base_sha), ("head", head, head_sha)):
                identity = document[side]
                if (identity["repo"]["id"] != repository_id
                        or identity["repo"]["full_name"] != repository
                        or identity["ref"] != ref
                        or ((side == 'head' or pr_context is None) and identity["sha"] != sha)):
                    raise GateError("repair pull-request identity does not match the current event")
        adapter = BranchApi()
        branches = branch_policy.load_policy(branch_policy.DEFAULT_POLICY)
        if branches[base].parent != parent:
            raise GateError("repair parent does not match the trusted branch policy")
        attestation = branch_policy.attest_reconciliation(
            branches, base=base, head=head,
            repository=repository, repository_id=repository_id,
            base_repository_id=pr["base"]["repo"]["id"], head_repository_id=pr["head"]["repo"]["id"],
            head_sha=head_sha, api=adapter,
        )
        if attestation.base_sha != base_sha or attestation.parent_sha != parent_sha:
            raise GateError("repair attestation does not match the current sync parents")
        if adapter.tree_entries(repository, merge_sha) != adapter.tree_entries(repository, parent_sha):
            raise GateError("repair candidate privileged tree does not match the current direct parent")
    except (KeyError, TypeError, branch_policy.PolicyError) as error:
        raise GateError(f"product repair attestation failed: {error}") from error


def compare_files(api: GitHubApi, repository: str, base: str, head: str) -> tuple[str, set[str]]:
    value = api.json(f"repos/{repository}/compare/{base}...{head}")
    if not isinstance(value, dict) or not isinstance(value.get("files"), list):
        raise GateError("GitHub API returned incomplete ancestry comparison")
    try:
        merge_base = validate_sha(value["merge_base_commit"]["sha"], "merge-base SHA")
        files = changed_paths(value["files"])
    except (KeyError, TypeError) as error:
        raise GateError("GitHub API returned malformed ancestry comparison") from error
    if any(not isinstance(path, str) for path in files):
        raise GateError("GitHub API returned an invalid comparison path")
    if len(value["files"]) >= 300:
        if value.get("base_commit", {}).get("sha") != base:
            raise GateError("GitHub API returned a mismatched comparison base")
        # The compare endpoint caps file lists. Compare complete immutable
        # trees instead; never treat the truncated list as authorization.
        before = comparison_entries(api, repository, merge_base)
        after = comparison_entries(api, repository, head)
        files = {path for path in before.keys() | after.keys()
                 if before.get(path) != after.get(path)}
    return merge_base, files


def comparison_entries(api: GitHubApi, repository: str, sha: str) -> dict:
    tree_sha = commit_tree(commit(api, repository, sha))
    value = api.json(f"repos/{repository}/git/trees/{tree_sha}?recursive=1")
    if (not isinstance(value, dict) or value.get("sha") != tree_sha
            or value.get("truncated") is not False or not isinstance(value.get("tree"), list)):
        raise GateError("GitHub API returned an incomplete comparison tree")
    entries = {}
    for item in value["tree"]:
        if not isinstance(item, dict):
            raise GateError("GitHub API returned a malformed comparison entry")
        if item.get("type") == "tree":
            continue
        path = item.get("path")
        if (not isinstance(path, str) or not path or path.startswith("/")
                or ".." in path.split("/") or path in entries
                or item.get("type") not in ("blob", "commit")
                or item.get("mode") not in ("100644", "100755", "120000", "160000")):
            raise GateError("GitHub API returned an invalid comparison entry")
        entries[path] = {key: item[key] for key in ("mode", "type", "sha")}
        validate_sha(item.get("sha"), "comparison blob SHA")
    return entries


def authorize_retired_paths(api, repository, config, unexpected, changed_documents,
                            base_sha, parent_sha, merge_sha):
    """Allow only a named, exact legacy blob to disappear under parent policy."""
    retired = config.get("retired_parent_paths", {})
    changes = {item["filename"]: item for item in changed_documents}
    if any(path not in retired or path not in changes or changes[path].get("status") != "removed" for path in unexpected):
        raise GateError("sync changes paths absent from the exact parent delta: " + ", ".join(unexpected[:10]))
    base = comparison_entries(api, repository, base_sha)
    parent = comparison_entries(api, repository, parent_sha)
    merged = comparison_entries(api, repository, merge_sha)
    for path in unexpected:
        expected = {"mode": "100644", "type": "blob", "sha": retired[path]}
        validate_sha(retired[path], "retired parent-owned blob SHA")
        if base.get(path) != expected or path in parent or path in merged:
            raise GateError("retired parent-owned path does not match its exact deletion contract: " + path)


def compare_merge_base(api: GitHubApi, repository: str, base: str, head: str) -> str:
    """Read the exact merge base without trusting the capped comparison file list."""
    value = api.json(f"repos/{repository}/compare/{base}...{head}")
    if not isinstance(value, dict):
        raise GateError("GitHub API returned invalid ancestry comparison")
    try:
        compared_base = validate_sha(value["base_commit"]["sha"], "comparison base SHA")
        merge_base = validate_sha(value["merge_base_commit"]["sha"], "merge-base SHA")
    except (KeyError, TypeError) as error:
        raise GateError("GitHub API returned malformed ancestry comparison") from error
    if compared_base != base:
        raise GateError("GitHub API returned a mismatched comparison base")
    return merge_base


def classify_event(event: dict, config: dict, api: GitHubApi, *, pr_context=None) -> SyncRequest | None:
    try:
        repository = event["repository"]["full_name"]
        repository_id = int(event["repository"]["id"])
        pr = event["pull_request"]
        number = int(pr["number"])
        base = pr["base"]["ref"]
        base_sha = validate_sha(pr["base"]["sha"], "event base SHA")
        head = pr["head"]["ref"]
        head_sha = validate_sha(pr["head"]["sha"], "event head SHA")
        head_repository_id = int(pr["head"]["repo"]["id"])
    except (KeyError, TypeError, ValueError) as error:
        raise GateError("invalid pull_request_target event identity") from error
    if repository != config["repository"] or repository_id != config["repository_id"]:
        raise GateError("event repository does not match the trusted configuration")
    edge = config["edges"].get(base)
    if edge is None:
        return None
    parent = edge["parent"]
    scope = edge["scope"]
    direct = head == parent
    reconciliation = head.startswith(f"reconcile/{scope}/") and head.count("/") == 2
    if not direct and not reconciliation:
        return None
    if head_repository_id != repository_id:
        raise GateError("sync head must originate in the event repository")
    current_base = branch_sha(api, repository, base)
    current_parent = branch_sha(api, repository, parent)
    if current_base != base_sha:
        if pr_context is None:
            pr_context = effective_pr_context(event, api)
        if not isinstance(pr_context, EffectivePRContext) or (pr_context.base, pr_context.head, pr_context.event_base) != (current_base, head_sha, base_sha):
            raise GateError("target head drifted after the pull-request event")
    elif pr_context is not None and (not isinstance(pr_context, EffectivePRContext)
            or (pr_context.base, pr_context.head, pr_context.event_base) != (current_base, head_sha, base_sha)):
        raise GateError('independently resolved synchronization context differs from the event')
    if direct and head_sha != current_parent:
        raise GateError("direct synchronization does not use the current parent head")
    head_commit = commit(api, repository, head_sha)
    if reconciliation and commit_parents(head_commit) != (current_base, current_parent):
        raise GateError("reconciliation head is not the exact current base/parent merge")
    current_pr: object = None
    for attempt in range(6):
        current_pr = api.json(f"repos/{repository}/pulls/{number}")
        if (
            isinstance(current_pr, dict)
            and current_pr.get("mergeable") is not None
            and (isinstance(current_pr.get("merge_commit_sha"), str)
                 or isinstance(pr_context, EffectivePRContext))
        ):
            break
        if attempt < 5:
            time.sleep(3)
    if not isinstance(current_pr, dict):
        raise GateError("GitHub API returned invalid pull request metadata")
    if current_pr.get("state") != "open" or current_pr.get("mergeable") is False:
        raise GateError("pull request is closed or has merge conflicts")
    merge_sha = (pr_context.candidate if isinstance(pr_context, EffectivePRContext)
                 else validate_sha(current_pr.get("merge_commit_sha"), "pull-request merge SHA"))
    merge_commit = commit(api, repository, merge_sha)
    if commit_parents(merge_commit) != (current_base, head_sha):
        raise GateError("pull-request merge parents do not match current target and head")
    merge_base = compare_merge_base(api, repository, current_parent, current_base)
    _, parent_delta = compare_files(api, repository, merge_base, current_parent)
    changed_documents = (immutable_change_documents(api, repository, current_base, merge_sha)
                         if isinstance(pr_context, EffectivePRContext) else paginate_pull_files(api, repository, number))
    changed = tuple(sorted(changed_paths(changed_documents)))
    allowed = allowed_repair_paths(config, base)
    repairs = tuple(sorted(set(changed) & allowed)) if reconciliation else ()
    if repairs:
        repair_context = {} if pr_context is None else {'pr_context': pr_context}
        attest_product_repair(api, repository, repository_id, pr, current_pr,
                              base, parent, head, current_base, current_parent, head_sha, merge_sha, **repair_context)
    unexpected = sorted(set(changed) - parent_delta - set(repairs))
    if unexpected:
        authorize_retired_paths(api, repository, config, unexpected, changed_documents,
                                current_base, current_parent, merge_sha)
        parent_delta.update(unexpected)
    if branch_sha(api, repository, base) != current_base or branch_sha(api, repository, parent) != current_parent:
        raise GateError("target or parent head moved during topology validation")
    doc_only = bool(changed) and all(
        item["filename"].endswith(".md")
        and item.get("previous_filename", item["filename"]).endswith(".md")
        for item in changed_documents
    )
    if doc_only and isinstance(pr_context, EffectivePRContext):
        _, before = recursive_tree(api, repository, current_base, error_type=GateError)
        _, after = recursive_tree(api, repository, merge_sha, error_type=GateError)
        doc_only = all(path not in inventory or (inventory[path]['mode'] == '100644' and inventory[path]['type'] == 'blob')
                       for inventory in (before, after) for path in changed)
    tool_only = False
    package_enabled = package_checks.activated(event)
    bounded_projects = (tool_dependencies.affected_projects(list(changed), include_s3=True)
                        if package_enabled else tool_dependencies.affected_projects(list(changed)))
    if not repairs and bounded_projects:
        # Both sides must be regular blobs. Include rename sources in `changed`
        # so an unrelated source/build path cannot disappear into this lane.
        tool_only = True
        for sha in (current_base, merge_sha):
            _, tree = recursive_tree(api, repository, sha, error_type=GateError)
            if package_checks.S3 in bounded_projects:
                try:
                    package_checks.validate_tree_wiring(tree)
                except ValueError as error:
                    raise GateError(str(error)) from error
            if any(path in tree and (tree[path]["mode"] != "100644" or tree[path]["type"] != "blob")
                   for path in changed):
                tool_only = False
        if branch_sha(api, repository, base) != current_base or branch_sha(api, repository, parent) != current_parent:
            raise GateError("target or parent head moved during tool manifest validation")
    profile = "documentation" if doc_only and not repairs else edge["differential"]
    if tool_only:
        profile = "tool-dependencies"
    if isinstance(pr_context, EffectivePRContext) and effective_pr_context(event, api) != pr_context:
        raise GateError('effective synchronization candidate changed during topology validation')
    return SyncRequest(
        repository=repository, repository_id=repository_id, number=number,
        base=base, base_sha=current_base, head=head, head_sha=head_sha,
        head_repository_id=head_repository_id, merge_sha=merge_sha,
        classification="direct" if direct else "reconciliation", parent=parent,
        parent_sha=current_parent, profile=profile,
        changed_paths=changed, parent_changed_paths=tuple(sorted(parent_delta)),
        repair_paths=repairs,
        event_base_sha=base_sha if isinstance(pr_context, EffectivePRContext) else None,
    )


def recursive_tree(api: GitHubApi, repository: str, commit_sha: str, error_type=EvidenceError) -> tuple[str, dict[str, dict[str, str]]]:
    try:
        commit_document = commit(api, repository, commit_sha)
        tree_sha = commit_tree(commit_document)
        value = api.json(f"repos/{repository}/git/trees/{tree_sha}?recursive=1")
        if not isinstance(value, dict) or value.get("truncated") is not False or not isinstance(value.get("tree"), list):
            raise error_type("GitHub API returned an incomplete recursive tree")
        entries: dict[str, dict[str, str]] = {}
        for item in value["tree"]:
            if not isinstance(item, dict):
                raise error_type("GitHub API returned malformed tree data")
            if item.get("type") == "tree":
                continue
            if item.get("type") not in {"blob", "commit"}:
                raise error_type("GitHub API returned an unsupported tree object")
            try:
                entry = {key: item[key] for key in ("path", "mode", "type", "sha")}
            except KeyError as error:
                raise error_type("GitHub API omitted tree entry metadata") from error
            if not all(isinstance(entry[key], str) for key in entry) or entry["path"] in entries:
                raise error_type("GitHub API returned malformed or duplicate tree entries")
            changed_paths([{"filename": entry["path"]}])
            validate_sha(entry["sha"], "tree object SHA", error_type)
            if {"100644": "blob", "100755": "blob", "120000": "blob", "160000": "commit"}.get(entry["mode"]) != entry["type"]:
                raise error_type("GitHub API returned a mismatched tree mode and object type")
            entries[entry["path"]] = entry
        return tree_sha, entries
    except GateError as error:
        raise error_type(str(error)) from error


def validate_required_codeql_workflow(event: dict, api: GitHubApi, policy_root: Path = ROOT, *, pr_context=None) -> bool:
    """Protect result-verifier invocation before even an ordinary PR can pass.

    Activation and the finite approved workflow blobs belong to the trusted default
    checkout. A candidate config, job name or successful result cannot authorize
    replacing this workflow with an exit-only or fabricated security job.
    """
    policy = json.loads((policy_root / '.github/repository-checks.json').read_text(encoding='utf-8'))
    if not isinstance(policy, dict):
        raise GateError('invalid trusted CodeQL result activation policy')
    targets = policy.get('codeql_results_required_branches', [])
    permanent = {'main', 'apple-main', 'apple-ios', 'android-main', 'android-phone', 'android-vr', 'android-vr-pico'}
    if (policy.get('schema') != 1 or policy.get('repository') != 'noah-l-frank/overte'
            or policy.get('repository_id') != 1319052603 or not isinstance(targets, list)
            or any(not isinstance(target, str) or target not in permanent for target in targets)
            or len(targets) != len(set(targets))):
        raise GateError('invalid trusted CodeQL result activation policy')
    if not targets:
        return False
    try:
        pr = event['pull_request']
        base = pr['base']
        target = base['ref']
        if target not in permanent:
            raise GateError('invalid CodeQL result target')
        if target not in targets:
            return False
        head = pr['head']
        repository, repository_id = 'noah-l-frank/overte', 1319052603
        number = pr['number']
        if (type(number) is not int or number <= 0 or type(event.get('number')) is not int
                or event['number'] != number):
            raise GateError('invalid CodeQL result PR number')
        for identity in (event['repository'], base['repo'], head['repo']):
            if identity.get('full_name') != repository or identity.get('id') != repository_id:
                raise GateError('CodeQL result PR must belong to the reviewed fork')
        base_sha = validate_sha(base['sha'], 'CodeQL event base')
        head_sha = validate_sha(head['sha'], 'CodeQL event head')
        head_ref = head['ref']
        if (base_sha == '0' * 40 or head_sha == '0' * 40 or not isinstance(head_ref, str)
                or not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_./-]*', head_ref)
                or '..' in head_ref or '//' in head_ref or head_ref.endswith(('/', '.', '.lock'))
                or any(part.startswith('.') for part in head_ref.split('/'))):
            raise GateError('invalid CodeQL result head identity')
    except (KeyError, TypeError, AttributeError) as error:
        raise GateError('invalid CodeQL result event identity') from error
    spec = importlib.util.spec_from_file_location('sync_required_codeql_policy', policy_root / 'tools/repository-checks/codeql.py')
    if spec is None or spec.loader is None:
        raise GateError('trusted CodeQL workflow policy unavailable')
    trusted = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(trusted)
    generations = tuple(validate_sha(value, 'approved CodeQL result workflow')
                        for value in trusted.result_workflow_blobs())
    pairs = trusted.result_workflow_sources()
    if (type(pairs) is not tuple or len(pairs) != 8
            or any(type(row) is not tuple or len(row) != 2 for row in pairs)):
        raise GateError('approved CodeQL workflow/helper pairs unavailable')
    sources = {validate_sha(row[0], 'approved CodeQL result workflow'):
               None if row[1] is None else validate_sha(row[1], 'approved CodeQL metadata source')
               for row in pairs}
    approved = set(generations)
    metadata_workflow = validate_sha(trusted._METADATA_RESULTS_WORKFLOW, 'approved CodeQL metadata workflow')
    metadata_source = validate_sha(trusted._METADATA_SOURCE_WORKFLOW, 'approved CodeQL metadata source')
    if len(generations) != 8 or len(approved) != 8 or tuple(sources) != generations \
            or '0' * 40 in approved or any(sources[oid] is not None for oid in generations[:3]) \
            or pairs[3] != (metadata_workflow, metadata_source) \
            or pairs[4] != (trusted._SCHEDULING_RESULTS_WORKFLOW, trusted._SCHEDULING_SOURCE_WORKFLOW) \
            or pairs[5] != (trusted._BOOLEAN_RESULTS_WORKFLOW, trusted._SCHEDULING_SOURCE_WORKFLOW) \
            or pairs[6] != (trusted._REQUIRED_CONTEXT_RESULTS_WORKFLOW, trusted._SCHEDULING_SOURCE_WORKFLOW) \
            or pairs[7] != (trusted._UPLOAD_RESULTS_WORKFLOW, trusted._SCHEDULING_SOURCE_WORKFLOW) \
            or any(value == '0' * 40 for value in sources.values()):
        raise GateError('approved CodeQL workflow identity is unavailable')
    refs = {f'repos/{repository}/git/ref/heads/{quote(ref, safe="")}': 'refs/heads/' + ref
            for ref in (target, head_ref)}

    class FixedForkReadOnly:
        def json(self, endpoint):
            if not isinstance(endpoint, str) or not endpoint.startswith('repos/' + repository + '/'):
                raise GateError('CodeQL invocation lookup escaped the reviewed fork')
            value = api.json(endpoint)
            if endpoint in refs and (not isinstance(value, dict) or value.get('ref') != refs[endpoint]
                                     or not isinstance(value.get('object'), dict) or value['object'].get('type') != 'commit'):
                raise GateError('CodeQL invocation branch reference identity mismatch')
            tree_prefix = 'repos/' + repository + '/git/trees/'
            if endpoint.startswith(tree_prefix):
                requested = endpoint[len(tree_prefix):].split('?', 1)[0]
                if not isinstance(value, dict) or value.get('sha') != requested:
                    raise GateError('CodeQL invocation tree identity mismatch')
            return value

    readonly = FixedForkReadOnly()
    snapshot = base_sha
    if pr_context is None and (branch_sha(readonly, repository, target) != snapshot
            or os.environ.get('GITHUB_ACTIONS') == 'true'):
        pr_context = effective_pr_context(event, api)
    if pr_context is not None:
        if not isinstance(pr_context, EffectivePRContext) or (pr_context.event_base, pr_context.head) != (snapshot, head_sha):
            raise GateError('invalid independently resolved CodeQL base context')
        base_sha = pr_context.base

    def fresh():
        if pr_context is not None and effective_pr_context(event, api) != pr_context:
            raise GateError('effective CodeQL base changed during verification')
        current = readonly.json(f'repos/{repository}/pulls/{number}')
        if (not isinstance(current, dict) or type(current.get('number')) is not int
                or current['number'] != number or current.get('state') != 'open'):
            raise GateError('CodeQL result PR is closed or unavailable')
        for side, ref, revision in (('base', target, base_sha), ('head', head_ref, head_sha)):
            value = current.get(side)
            if (not isinstance(value, dict) or value.get('ref') != ref
                    or ((side == 'head' or pr_context is None) and value.get('sha') != revision)
                    or not isinstance(value.get('repo'), dict) or value['repo'].get('full_name') != repository
                    or value['repo'].get('id') != repository_id
                    or branch_sha(readonly, repository, ref) != revision):
                raise GateError('CodeQL result PR or branch head changed')
        if current.get('mergeable') is False:
            raise GateError('CodeQL result PR has merge conflicts')
        if current.get('mergeable') is None or (pr_context is None and current.get('merge_commit_sha') is None):
            return None
        if current.get('mergeable') is not True:
            raise GateError('CodeQL result mergeability is unknown')
        candidate = (pr_context.candidate if pr_context is not None
                     else validate_sha(current.get('merge_commit_sha'), 'current CodeQL candidate'))
        if candidate == '0' * 40:
            raise GateError('invalid current CodeQL candidate')
        return candidate

    candidate = None
    for attempt in range(6):
        candidate = fresh()
        if candidate is not None:
            break
        if attempt < 5:
            time.sleep(3)
    if candidate is None:
        raise GateError('CodeQL candidate merge computation did not complete')
    merge = commit(readonly, repository, candidate)
    if commit_parents(merge) != (base_sha, head_sha):
        raise GateError('CodeQL candidate ordered parents differ from the current PR')
    tree_sha, tree = recursive_tree(readonly, repository, candidate, error_type=GateError)
    if tree_sha == '0' * 40 or tree_sha != commit_tree(merge):
        raise GateError('CodeQL candidate tree changed')
    actual = tree.get('.github/workflows/codeql.yml', {})
    if actual.get('mode') != '100644' or actual.get('type') != 'blob' or actual.get('sha') not in approved:
        raise GateError('candidate must retain the exact approved CodeQL security-result workflow')
    # The metadata successor invokes this relative reusable workflow. Its
    # exact caller blob cannot authorize candidate-controlled helper contents.
    if sources[actual['sha']] is not None and tree.get('.github/workflows/pr-metadata-context.yml') != {
            'path': '.github/workflows/pr-metadata-context.yml',
            'mode': '100644', 'type': 'blob', 'sha': sources[actual['sha']]}:
        raise GateError('candidate must retain the exact approved CodeQL metadata source workflow')
    _, base_tree = recursive_tree(readonly, repository, base_sha, error_type=GateError)
    previous = base_tree.get('.github/workflows/codeql.yml', {})
    if previous.get('mode') != '100644' or previous.get('type') != 'blob':
        raise GateError('CodeQL base workflow identity is unavailable or nonregular')
    if previous.get('sha') in approved and generations.index(actual['sha']) < generations.index(previous['sha']):
        raise GateError('deployed CodeQL result workflow cannot be reverted')
    if fresh() != candidate:
        raise GateError('CodeQL candidate changed during invocation verification')
    return True


def select_entries(tree: dict[str, dict[str, str]], patterns: list[str]) -> list[dict[str, str]]:
    return sorted(
        (entry for path, entry in tree.items() if any(fnmatch(path, pattern) for pattern in patterns)),
        key=lambda item: item["path"],
    )


def input_registry() -> dict:
    """Only default-branch policy may define the inputs of a reusable suite."""
    return suite_inputs.load_registry(ROOT / ".github/test-suites.json")


def input_tree(tree: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
    return {path: {key: item[key] for key in ("mode", "type", "sha")}
            for path, item in tree.items()}


def artifact_evidence(api: GitHubApi, config: dict, request: SyncRequest) -> tuple[dict, dict]:
    workflow = quote(config["qualification_workflow"], safe="")
    endpoint = (
        f"repos/{request.repository}/actions/workflows/{workflow}/runs"
        f"?branch={quote(request.parent, safe='')}&event=push&status=success&per_page=100"
    )
    try:
        runs = [
            run for run in api_list(api, endpoint, "workflow_runs")
            if run.get("head_sha") == request.parent_sha and run.get("conclusion") == "success"
        ]
    except GateError as error:
        raise EvidenceError("qualification run lookup failed") from error
    if len(runs) != 1:
        raise EvidenceError("expected exactly one successful qualification run for the parent commit")
    run = runs[0]
    if run.get("event") != "push" or run.get("path") != config["qualification_workflow"]:
        raise EvidenceError("qualification run has an untrusted event or workflow path")
    try:
        suite = api.json(run.get("check_suite_url", ""))
    except GateError as error:
        raise EvidenceError("qualification check suite lookup failed") from error
    try:
        if suite["app"]["id"] != config["trusted_actions_app_id"] or suite["conclusion"] != "success":
            raise EvidenceError("qualification check suite is not a successful GitHub Actions run")
    except (KeyError, TypeError) as error:
        raise EvidenceError("qualification check suite identity is incomplete") from error
    try:
        artifacts = api_list(api, f"repos/{request.repository}/actions/runs/{run['id']}/artifacts", "artifacts")
    except GateError as error:
        raise EvidenceError("qualification artifact lookup failed") from error
    expected_name = config["evidence_artifact_prefix"] + request.parent_sha
    artifacts = [item for item in artifacts if item.get("name") == expected_name and not item.get("expired")]
    if len(artifacts) != 1:
        raise EvidenceError("expected exactly one live qualification artifact")
    raw = api.bytes(f"repos/{request.repository}/actions/artifacts/{artifacts[0]['id']}/zip")
    if len(raw) > 5_000_000:
        raise EvidenceError("qualification artifact exceeds the size limit")
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            if archive.namelist() != ["qualification.json"]:
                raise EvidenceError("qualification artifact has unexpected members")
            evidence = json.loads(archive.read("qualification.json"))
    except (zipfile.BadZipFile, KeyError, json.JSONDecodeError) as error:
        raise EvidenceError("qualification artifact is malformed") from error
    if not isinstance(evidence, dict):
        raise EvidenceError("qualification artifact root is not an object")
    return run, evidence


def _verify_legacy_evidence(api: GitHubApi, config: dict, request: SyncRequest, now: datetime | None = None) -> dict:
    run, evidence = artifact_evidence(api, config, request)
    expected = {
        "schema": 2,
        "repository": request.repository,
        "repository_id": request.repository_id,
        "parent_branch": request.parent,
        "parent_commit": request.parent_sha,
    }
    for key, value in expected.items():
        if evidence.get(key) != value:
            raise EvidenceError(f"qualification evidence has mismatched {key}")
    if evidence.get("reusable") is not True:
        raise EvidenceError("parent verification has no reusable runtime identity")
    if not isinstance(evidence.get("execution_receipt_digest"), str) or not re.fullmatch(
            r"sha256:[0-9a-f]{64}", evidence["execution_receipt_digest"]):
        raise EvidenceError("parent qualification omits its actual execution receipt identity")
    parent_tree_sha, parent_tree = recursive_tree(api, request.repository, request.parent_sha)
    if evidence.get("parent_tree") != parent_tree_sha:
        raise EvidenceError("qualification evidence has a mismatched parent tree")
    entries = select_entries(parent_tree, config["qualified_inputs"])
    if evidence.get("qualified_inputs") != entries or evidence.get("qualified_inputs_digest") != digest_entries(entries):
        raise EvidenceError("qualification input manifest does not match the exact parent tree")
    if not set(config["required_qualified_inputs"]).issubset(parent_tree):
        raise EvidenceError("exact parent tree is missing required qualification inputs")
    workflow_entry = parent_tree.get(config["qualification_workflow"])
    workflow = evidence.get("workflow")
    if not isinstance(workflow, dict) or workflow_entry is None:
        raise EvidenceError("qualification workflow binding is incomplete")
    workflow_expected = {
        "path": config["qualification_workflow"],
        "blob_sha": workflow_entry["sha"],
        "ref": f"refs/heads/{request.parent}",
        "run_id": run["id"],
        "run_attempt": run["run_attempt"],
        "event": "push",
        "trusted_app_id": config["trusted_actions_app_id"],
    }
    if workflow != workflow_expected:
        raise EvidenceError("qualification workflow/run binding is mismatched")
    results = evidence.get("results")
    if not isinstance(results, dict) or results.get("conclusion") != "success" or not isinstance(results.get("suites"), dict):
        raise EvidenceError("qualification suite result is incomplete")
    try:
        registry = input_registry()
    except suite_inputs.InputError as error:
        raise EvidenceError("trusted suite input registry is unavailable") from error
    if set(results["suites"]) != set(registry["suites"]):
        raise EvidenceError("qualification does not contain the actual complete shared suite inventory")
    now = now or datetime.now(timezone.utc)
    qualified = parse_time(evidence.get("qualified_at"), "qualified_at")
    expires = parse_time(evidence.get("expires_at"), "expires_at")
    max_age = int(config["evidence_max_age_hours"]) * 3600
    if qualified > now or expires <= now or (now - qualified).total_seconds() > max_age:
        raise EvidenceError("qualification evidence is stale or outside its validity window")
    unsigned = dict(evidence)
    actual_digest = unsigned.pop("evidence_digest", None)
    expected_digest = "sha256:" + hashlib.sha256(canonical_json(unsigned)).hexdigest()
    if actual_digest != expected_digest:
        raise EvidenceError("qualification evidence digest is invalid")
    _, merge_tree = recursive_tree(api, request.repository, request.merge_sha)
    try:
        parent_inputs = input_tree(parent_tree)
        candidate_inputs = input_tree(merge_tree)
        environment = evidence.get("environment")
        for name, proof in results["suites"].items():
            if (not isinstance(proof, dict) or set(proof) != {"status", "fingerprint"}
                    or proof["status"] != "passed"
                    or proof["fingerprint"] != suite_inputs.suite_fingerprint(
                        registry, name, parent_inputs, environment)):
                raise EvidenceError("parent suite proof does not match its actual trusted input closure")
        # This is a source-only preview. The isolated validator compares its
        # actual installed runtime before consuming any reusable suite result.
        candidate_plan = suite_inputs.plan_reuse(
            registry, parent_inputs, candidate_inputs, results["suites"],
            environment, environment)
    except (suite_inputs.InputError, KeyError, TypeError) as error:
        raise EvidenceError("complete shared suite inputs or runtime identity are unavailable") from error
    if not candidate_plan["reused"]:
        raise EvidenceError("no shared suite has matching complete candidate inputs")
    if branch_sha(api, request.repository, request.base) != request.base_sha or branch_sha(api, request.repository, request.parent) != request.parent_sha:
        raise EvidenceError("target or parent head moved during evidence validation")
    return {**evidence, "candidate_plan": candidate_plan,
            "parent_inputs": parent_inputs, "candidate_inputs": candidate_inputs}


NATIVE_PARENT_KIND = 'original-native-parent-v1'


class NativeParentEvidence(dict):
    """Internal native API result; an artifact JSON field cannot create this."""



class NativeExactTreeParentEvidence(dict):
    """Successful original Sync CI data on this identical tree; never E."""

def _native_parent_controller():
    """Close the real protected import lookup before importing proof modules.

    ROOT is the trusted checkout, never the synchronization candidate. The
    immutable local source is subsequently bound to the live protected default
    by _native_sync_context; local Git metadata alone supplies no authority.
    """
    tree = suite_inputs.full_tree(ROOT, 'HEAD')
    name = 'tools/test-evidence/source_admission.py'
    path = ROOT / name
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current /= part
        if current.is_symlink():
            raise EvidenceError('native parent source contains an alias')
    info = path.stat()
    if not path.is_file() or info.st_mode & 0o111 or info.st_size > 1_000_000:
        raise EvidenceError('native parent source helper is unavailable')
    raw = path.read_bytes()
    expected = {'mode': '100644', 'type': 'blob',
        'sha': hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest()}
    if len(raw) > 1_000_000 or tree.get(name) != expected:
        raise EvidenceError('native parent source helper differs from immutable ROOT')
    guard = type(sys)('sync_native_parent_source_guard')
    guard.__file__ = str(path)
    exec(compile(raw, str(path), 'exec'), guard.__dict__)
    imports = {name: entry for name, entry in tree.items()
        if any(name == prefix or name.startswith(prefix+'/') for prefix in guard.IMPORT_ROOTS)}
    directories = sorted({str(parent) for name in imports for parent in Path(name).parents
        if any(str(parent) == prefix or str(parent).startswith(prefix+'/') for prefix in guard.IMPORT_ROOTS)})
    if set(imports) != set(guard.IMPORT_MEMBERS) or guard.actual_import_inventory(ROOT) != {
            'files': imports, 'directories': directories}:
        raise EvidenceError('native parent protected import lookup is not immutable')
    directory = str(ROOT / 'tools/test-evidence')
    sys.path.insert(0, directory)
    try:
        spec = importlib.util.spec_from_file_location('sync_native_parent_consumer', ROOT / 'tools/test-evidence/postmerge.py')
        controller = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(controller)
    finally:
        sys.path.remove(directory)
    for name in ('attested', 'ci_profile', 'execution', 'inputs', 'producer', 'producer_api',
                 'producer_workflow', 'runtime_ci', 'sandbox', 'source_admission'):
        module = sys.modules.get(name)
        if module is None or Path(module.__file__).resolve() != ROOT / ('tools/test-evidence/'+name+'.py'):
            raise EvidenceError('native parent proof module is outside actual protected ROOT')
    return controller


def _native_sync_context(controller, adapter, request):
    binding, references = adapter.current(request.number)
    expected = {'repository': request.repository, 'repository_id': request.repository_id,
        'pull_request': request.number, 'head_repository_id': request.head_repository_id,
        'base_ref': request.base, 'base_sha': request.base_sha, 'head_ref': request.head,
        'head_sha': request.head_sha, 'merge_sha': request.merge_sha,
        'merge_parents': [request.base_sha, request.head_sha]}
    controller.A.require(all(binding.get(key) == value for key, value in expected.items())
        and references['default_ref'] == 'main', 'native parent consumer source PR changed')
    branch = adapter._object('branches/'+quote(request.base, safe=''))
    controller.A.require(branch.get('name') == request.base and branch.get('protected') is True
        and branch.get('commit', {}).get('sha') == request.base_sha,
        'native parent consumer protected target changed')
    controller.default_authority(adapter, references)
    default_tree, local = controller.full_tree(adapter, references['default'])
    controller.A.require(controller.execution.checkout_identity(ROOT) == (references['default'], default_tree)
        and controller.inputs.full_tree(ROOT, references['default']) == local,
        'native parent actual ROOT differs from current default authority')
    return binding, references, local


def native_pr_evidence(api, config, request, *, timeout=1800, clock=None, monotonic=time.monotonic, sleep=time.sleep):
    """Consume one completed Repository producer without a second Sync runner.

    Only source non-enrollment returns None. Once the exact native owner is
    selected, pending waits boundedly and every failure/unknown proof blocks.
    No in-progress run is promoted to reusable authority.
    """
    if os.environ.get('GITHUB_ACTIONS') != 'true' or request.repair_paths \
            or request.profile in {'documentation', 'tool-dependencies'} \
            or not callable(getattr(api, 'native_producer_api', None)):
        return None
    controller = _native_parent_controller()
    A, P = controller.A, controller.P
    clock = clock or (lambda: datetime.now(timezone.utc))
    adapter = A.Adapter(api.native_producer_api(controller))
    binding, references, local = _native_sync_context(controller, adapter, request)
    _, previous = controller.full_tree(adapter, request.base_sha)
    tree_sha, current = controller.full_tree(adapter, request.merge_sha)
    event = {'number': request.number, 'repository': {'full_name': request.repository, 'id': request.repository_id},
        'pull_request': {'number': request.number,
            'base': {'ref': request.base, 'sha': request.base_sha,
                     'repo': {'full_name': request.repository, 'id': request.repository_id}},
            'head': {'ref': request.head, 'sha': request.head_sha,
                     'repo': {'full_name': request.repository, 'id': request.head_repository_id}}}}
    if not controller.producer.sync_source_admission(previous, current, local, event, read_blob=adapter.api.immutable_blob):
        return None
    try:
        _native_effective_role(api, event, request.base_sha)
        A.require(type(timeout) in (int, float) and 0 <= timeout <= 1800, 'invalid original PR wait bound')
        A.require(controller._source_qualified() and config['trusted_actions_app_id'] == 15368,
            'selected original PR source is unavailable')
        policy = controller.producer._host_policy()
        source = controller.integrated_controller(policy, previous, current, local, request.base, ROOT)
        registry = controller.inputs.load_registry(ROOT / '.github/test-suites.json')
        profile = controller.producer.selection_profile(policy, registry, current, previous, local,
            root=ROOT, target=request.base, read_blob=adapter.api.immutable_blob)
        partition = controller.producer.platform_partition(policy, profile, registry, current, previous, local,
            root=ROOT, target=request.base, read_blob=adapter.api.immutable_blob)
        A.require(profile['profile'] in {controller.ci_profile.PROFILE, controller.producer.FULL_PROFILE}
            and (partition is not None or controller.source_admission.shared_platform_supported(
                profile['selection'], request.base, current.get(controller.source_admission.PROFILE))),
            'selected original PR no longer has its independently admitted shared/platform owner')
        owner = controller.producer.common_owner(profile, partition)
        plan, api_policy = controller._policy(policy, registry, binding, source, adapter, ROOT, profile['selection'],
            common_owner=owner, template=controller.producer.PLATFORM_TEMPLATE)
        def completed_roles(snapshot, authority):
            # Only this exact current-PR Sync consumer may admit completed
            # selected jobs while an unrelated native build is still pending.
            # It produces no overall run qualification or cross-run authority.
            if authority['state'] not in {'pending', 'proof-required'}:
                return None
            selected = next(item for item in snapshot.observations if item.run.run_id == authority['run_id'])
            run = selected.run
            A.require(run.attempt == run.latest_attempt == 1 and run.workflow_commit == request.merge_sha
                and snapshot.source_chains[run.run_id]['producer_commit'] == request.merge_sha,
                'selected shared owner is not the exact original current PR')
            latest = adapter._object('actions/runs/'+str(run.run_id))
            attempt = adapter._object(f'actions/runs/{run.run_id}/attempts/1')
            keys = ('id','workflow_id','check_suite_id','path','event','head_sha','head_branch',
                'run_attempt','status','conclusion','run_started_at')
            A.require(all(latest.get(key) == attempt.get(key) for key in keys)
                and latest.get('id') == run.run_id and latest.get('run_attempt') == 1
                and latest.get('workflow_id') == api_policy.caller_workflow_id
                and latest.get('path') == api_policy.caller_path and latest.get('event') == 'pull_request'
                and latest.get('head_sha') == binding['head_sha'] and latest.get('head_branch') == binding['head_ref']
                and latest.get('status') == run.status and latest.get('conclusion') == run.conclusion,
                'current PR native run changed while checking completed shared roles')
            jobs = adapter._pages(f'actions/runs/{run.run_id}/attempts/1/jobs', 'jobs')
            identities = [A.positive(row.get('id')) for row in jobs]
            A.require(len(identities) == len(set(identities))
                and all(row.get('run_id') == run.run_id and row.get('run_attempt') == 1
                    and row.get('head_sha') == binding['head_sha']
                    and ((row.get('status') in P._PENDING and row.get('conclusion') is None)
                        or row.get('status') == 'completed' and row.get('conclusion') in {'success','skipped','neutral'})
                    for row in jobs),
                'current PR has a failed, cancelled, unknown or mixed native job')
            roles = [run.publisher, *run.owners.values(),
                run.final_publisher.job if run.final_publisher is not None else None]
            A.require(all(job is None or job.job_id in identities for job in roles),
                'selected native jobs disappeared from the current attempt')
            names = ({run.publisher.job_id:api_policy.publisher_job} if run.publisher is not None else {})
            names.update({job.job_id:api_policy.owner_jobs[name] for name,job in run.owners.items()})
            if run.final_publisher is not None:
                names[run.final_publisher.job.job_id] = api_policy.final_publisher_prefix + run.final_publisher.receipt_sha256
            for job in roles:
                if job is not None:
                    row = next(row for row in jobs if row['id'] == job.job_id)
                    A.require(adapter._job(row, attempt, 15368, final_name=names[job.job_id]) == job,
                        'selected native job changed after the full source snapshot')
            ready = bool(roles) and all(job is not None and job.status == 'completed'
                and job.conclusion == 'success' for job in roles)
            platform = None
            if ready and partition is not None:
                matches = [row for row in jobs if row.get('name') == controller.producer.PLATFORM_JOB]
                A.require(len(matches) <= 1, 'current PR platform job is ambiguous')
                ready = len(matches) == 1 and matches[0].get('status') == 'completed'
                if ready:
                    observed = controller.producer._completed_platform_job(
                        adapter, attempt, jobs, controller.producer.PLATFORM_JOB, clock())
                    platform = {'kind':'original-android-platform-native-job-v1','job_id':observed['job_id'],
                        'run_id':run.run_id,'attempt':1,'partition':partition['digest'],'job':observed['job'],
                        'reusable':False,'qualification':False}
            if not ready:
                A.require(authority['state'] == 'pending', 'completed current PR omits successful selected native jobs')
                return None
            return selected, platform, jobs

        def scheduling_hint(watched):
            # Read-only progress controls polling ONLY. It cannot authenticate
            # or reuse a result: the outer loop always rebuilds a full snapshot.
            rows = adapter._pages('actions/workflows/'+str(api_policy.caller_workflow_id)
                +'/runs?head_sha='+binding['head_sha'], 'workflow_runs', search=True)
            fields = (*A._SCHEDULING_RUN_FIELDS, 'status','conclusion','run_started_at')
            runs = [{key:row.get(key) for key in fields} for row in rows]
            jobs = (adapter._pages(f'actions/runs/{watched}/attempts/1/jobs','jobs') if watched else [])
            job_fields = ('id','run_id','run_attempt','head_sha','name','status','conclusion')
            progress = [{key:row.get(key) for key in job_fields} for row in jobs]
            final = [row for row in progress if isinstance(row['name'],str)
                and row['name'].startswith(api_policy.final_publisher_prefix)]
            required = [api_policy.publisher_job, *api_policy.owner_jobs.values()]
            if partition is not None:
                required.append(controller.producer.PLATFORM_JOB)
            ready = bool(final) and all(any(row['name'] == name and row['status'] == 'completed'
                for row in progress) for name in required) and all(row['status'] == 'completed' for row in final)
            terminal = any(row['status'] == 'completed' and row['conclusion'] not in {'success','skipped','neutral'}
                for row in progress)
            return (runs, progress), ready or terminal

        deadline = monotonic() + timeout
        while True:
            snapshot = adapter.capture(request.number, plan, api_policy, now=clock())
            A.require(snapshot.binding == binding and snapshot.references == references,
                'selected original PR source changed while waiting')
            authority = P.select_authority(snapshot.observations, binding, plan, api_policy.producer,
                inventory_complete=snapshot.inventory_complete, now=clock())
            completed = completed_roles(snapshot, authority)
            if completed is not None:
                break
            # An early run can precede its descriptor. Its authenticated native
            # pending state is scheduling, never a proof or a failure fallback.
            runs = [item.run for item in snapshot.observations]
            newest = max((P._time(run.attempt_started_at) for run in runs), default=None)
            latest = [run for run in runs if P._time(run.attempt_started_at) == newest]
            waiting = authority['state'] in {'pending', 'absent'} or (
                authority['state'] == 'unresolved' and len(latest) == 1
                and latest[0].status in {'queued', 'in_progress', 'waiting', 'pending', 'requested'}
                and latest[0].conclusion is None)
            A.require(snapshot.inventory_complete and waiting,
                'selected original PR failed or has unknown source/attempt/proof')
            remaining = deadline - monotonic()
            A.require(remaining > 0, 'selected original PR did not complete within the wait bound')
            watched = latest[0].run_id if len(latest) == 1 else None
            hint, changed = scheduling_hint(watched)
            while not changed:
                remaining = deadline - monotonic()
                A.require(remaining > 0, 'selected original PR did not complete within the wait bound')
                sleep(min(30, remaining))
                fresh, terminal = scheduling_hint(watched)
                changed = terminal or fresh != hint
        observation, platform_observation, native_jobs = completed
        raw, facts = adapter._artifact(observation.run, 'aggregate',
            snapshot.artifact_inventories[observation.run.run_id], clock(), binding['head_sha'])
        aggregate = P.read_artifact(raw, 'aggregate', facts, observation.run, now=clock())
        receipt = aggregate['results']['shared-host']['receipt']
        git_context = controller.producer.expected_git_context(adapter, binding)
        affected = controller._affected_receipt_selection(profile, registry, request.base)
        controller.execution.validate_receipt(receipt, registry, current,
            require_all=profile['profile'] != controller.ci_profile.PROFILE and not affected,
            expected_git_context=git_context)
        A.require(receipt['requested_suites'] == owner['suites']
            and receipt['include_platform'] == owner['include_platform']
            and (partition is None or receipt['platform_results'] == {}),
            'original PR receipt differs from its actual shared/platform ownership')
        retained = controller.producer.retained_receipt_source(receipt, binding, adapter, registry,
            profile['selection'], observation.run.run_id, root=ROOT)
        git_context = controller.producer.expected_git_context(adapter, binding)
        context = P.SharedContext(registry, current, receipt['environment'], request.merge_sha, tree_sha,
            git_context, retained)
        if authority['state'] == 'proof-required':
            verified = adapter.verify(request.number, plan, api_policy, {'shared-host': context}, clock=clock)
        else:
            verified = P._verify_original_payload(raw, facts, binding, plan, api_policy.producer,
                observation, contexts={'shared-host':context}, now=clock())
            verified = {**verified, 'source_chain':snapshot.source_chains[observation.run.run_id]}
        verified = {**verified, 'purpose':'current-pr-sync-selected-owners-only',
            'overall_run_complete':authority['state'] == 'proof-required', 'qualification':False, 'reusable':False}
        A.require(verified['run_id'] == observation.run.run_id,
            'selected original PR authority changed before consumption')
        if profile['profile'] == controller.ci_profile.PROFILE:
            controller.runtime_ci.validate_environment(receipt['environment'], verified['qualified_at'],
                verified['expires_at'], clock(), profile['selection'], current, local, registry, root=ROOT,
                read_blob=adapter.api.immutable_blob, target=request.base, base_tree=previous)
        else:
            controller.attested.validate_environment(receipt['environment'], verified['qualified_at'],
                verified['expires_at'], clock(), root=ROOT, isolated=True)
        final_snapshot = adapter.capture(request.number, plan, api_policy, now=clock())
        final_authority = P.select_authority(final_snapshot.observations, binding, plan, api_policy.producer,
            inventory_complete=final_snapshot.inventory_complete, now=clock())
        A.require(final_authority == authority and completed_roles(final_snapshot, final_authority) == completed
            and final_snapshot == snapshot,
            'original PR native jobs, attempts, artifacts or authority changed after runtime admission')
        A.require(_native_sync_context(controller, adapter, request) == (binding, references, local)
            and controller.integrated_controller(policy, previous, current, local, request.base, ROOT) == source
            and controller.producer.sync_source_admission(previous, current, local, event, read_blob=adapter.api.immutable_blob)
            and clock() < P._time(verified['expires_at']), 'original PR/default context changed before Sync acceptance')
        return NativePrEvidence(kind='native-current-pr', original_commit=request.merge_sha,
            candidate_inputs=current, tested_inputs=current, requested_suites=list(owner['suites']),
            environment=receipt['environment'], results={'suites': receipt['results']},
            qualified_at=verified['qualified_at'], expires_at=verified['expires_at'],
            original_proof=verified, qualification=False, reusable=False,
            platform_commands=partition['commands'] if partition else [],
            original_platform_observation=platform_observation,
            platform_partition=partition['digest'] if partition else None)
    except (OSError, ValueError, KeyError, TypeError, AttributeError, ImportError, subprocess.SubprocessError) as error:
        raise NativeSyncOwnerError('selected original PR proof unavailable; duplicate Sync execution is forbidden') from error



def _empty_sync_invocation(controller, adapter, references, environment):
    """Authenticate the current dispatch, separately from its candidate PR M."""
    A = controller.A
    source = references['default']
    required = {'GITHUB_ACTIONS':'true','GITHUB_REPOSITORY':A.REPOSITORY,
        'GITHUB_REPOSITORY_ID':'1319052603','GITHUB_EVENT_NAME':'workflow_dispatch',
        'GITHUB_RUN_ATTEMPT':'1','GITHUB_JOB':'validate','GITHUB_REF':'refs/heads/main',
        'GITHUB_SHA':source,'GITHUB_WORKFLOW_SHA':source,
        'GITHUB_WORKFLOW_REF':A.REPOSITORY+'/.github/workflows/sync-validation.yml@refs/heads/main',
        'RUNNER_ENVIRONMENT':'github-hosted','ImageOS':'ubuntu24'}
    A.require(all(environment.get(key)==value for key,value in required.items()),
        'empty sync must use its actual protected native dispatch')
    run_id = A.positive(int(environment.get('GITHUB_RUN_ID','0')))
    registration = adapter._object('actions/workflows/sync-validation.yml')
    A.require(registration.get('id')==350930895 and registration.get('path')=='.github/workflows/sync-validation.yml'
        and registration.get('state')=='active' and registration.get('name')=='Sync validation',
        'empty sync workflow registration changed')
    latest = adapter._object('actions/runs/'+str(run_id))
    attempt = adapter._object(f'actions/runs/{run_id}/attempts/1')
    keys = ('id','workflow_id','check_suite_id','path','event','head_sha','head_branch',
        'run_attempt','status','conclusion','run_started_at')
    A.require(all(latest.get(key)==attempt.get(key) for key in keys)
        and attempt.get('id')==run_id and attempt.get('run_attempt')==1
        and attempt.get('workflow_id')==registration['id'] and attempt.get('path')==registration['path']
        and attempt.get('event')=='workflow_dispatch' and attempt.get('head_sha')==source
        and attempt.get('head_branch')=='main'
        and (attempt.get('status'),attempt.get('conclusion'))==('in_progress',None)
        and all(row.get(key,{}).get('id')==1319052603
            and row[key].get('full_name')==A.REPOSITORY
            for row in (latest,attempt) for key in ('repository','head_repository')),
        'empty sync is not its original current native attempt')
    suite = adapter._object('check-suites/'+str(A.positive(attempt.get('check_suite_id'))))
    A.require(suite.get('id')==attempt['check_suite_id'] and suite.get('head_sha')==source
        and suite.get('repository',{}).get('id')==1319052603 and suite.get('app',{}).get('id')==15368,
        'empty sync native check suite is foreign')
    jobs = adapter._pages(f'actions/runs/{run_id}/attempts/1/jobs','jobs')
    if _callback_sync_recipe():
        A.require(all(type(row) is dict and type(row.get('id')) is int and row['id']>0 for row in jobs)
            and len({row['id'] for row in jobs})==len(jobs),
            'empty callback sync native job identities are invalid or duplicated')
        names = [row.get('name') for row in jobs]
        A.require(len(jobs) in (1,2) and len(set(names))==len(jobs)
            and set(names) in ({'Validate exact synchronization'},
                {'Validate exact synchronization','Notify completed synchronization cleanup'}),
            'empty callback sync native roles are incomplete or ambiguous')
        notifier = [row for row in jobs if row.get('name')=='Notify completed synchronization cleanup']
        if notifier:
            item = notifier[0]
            A.require(type(item.get('id')) is int and item['id']>0
                and type(item.get('run_id')) is int and item['run_id']==run_id
                and type(item.get('run_attempt')) is int and item['run_attempt']==1
                and item.get('head_sha')==source
                and item.get('status') in {'queued','waiting','pending','requested'}
                and item.get('conclusion') is item.get('started_at') is item.get('completed_at') is None
                and item.get('steps')==[], 'empty sync notifier is not needs-blocked')
        validator = next(row for row in jobs if row.get('name')=='Validate exact synchronization')
    else:
        A.require(len(jobs)==1 and jobs[0].get('name')=='Validate exact synchronization',
            'empty sync native job inventory is incomplete or ambiguous')
        validator = jobs[0]
    job = adapter._job(validator,attempt,15368,final_name='Validate exact synchronization')
    A.require((job.status,job.conclusion)==('in_progress',None) and job.completed_at is None
        and controller.P._time(attempt.get('run_started_at'))<=controller.P._time(job.started_at)
        <=datetime.now(timezone.utc), 'empty sync native job is not currently executing')
    return {'registration':registration,'run':{key:attempt.get(key) for key in keys},'job':vars(job)}


def verified_empty_sync(api, config, request, candidate, *, environment=None):
    """Validation-only source proof; never original test/runtime qualification.

    The raw helper supplies immutable arithmetic only. Actual gate topology,
    native dispatch, protected default/controller and current PR bookends supply
    its authority. An unavailable proof leaves the existing execution route.
    """
    if request.changed_paths or request.repair_paths:
        return None
    try:
        controller = _native_parent_controller()
        A = controller.A
        A.require(config.get('repository')==A.REPOSITORY and config.get('repository_id')==1319052603
            and config.get('trusted_actions_app_id')==15368
            and config.get('validation_workflow')=='sync-validation.yml'
            and config['edges'][request.base]['parent']==request.parent,
            'empty sync requires the exact configured protected edge')
        adapter = A.Adapter(api.native_producer_api(controller))
        native = os.environ if environment is None else environment
        def observe():
            binding, refs, local = _native_sync_context(controller,adapter,request)
            invocation = _empty_sync_invocation(controller,adapter,refs,native)
            policy = controller.producer._host_policy()
            source = controller.producer.reuse_source_context(adapter,binding,refs,policy)
            tree_sha, current = controller.full_tree(adapter,request.merge_sha)
            before_sha, previous = controller.full_tree(adapter,request.base_sha)
            A.require(tree_sha==before_sha==binding['merge_tree'] and current==previous
                and controller.execution.checkout_identity(candidate)==(request.merge_sha,tree_sha)
                and suite_inputs.full_tree(candidate,request.merge_sha)==current,
                'empty sync complete immutable candidate inventory differs')
            package = policy.package_policy()
            A.require(package.validate_tree_wiring(current) in controller.ci_profile.RETAINED_SOURCE_GENERATIONS
                and current.get('.github/workflows/sync-validation.yml')==local.get(
                    'tools/repository-checks/workflows/sync-ci-selection.yml')
                and local.get('.github/workflows/sync-validation.yml')==local.get(
                    'tools/repository-checks/workflows/sync-ci-selection.yml'),
                'empty sync is not the complete reviewed future recipe')
            pr = adapter._object('pulls/'+str(request.number))
            labels = pr.get('labels')
            A.require(isinstance(labels,list) and all(type(label) is dict and type(label.get('name')) is str
                for label in labels) and not any(label['name']=='android-long-diagnostics' for label in labels),
                'explicit diagnostics cannot select an empty sync')
            checks = package.load('sync_empty_immutable_math','tools/repository-checks/check.py')
            proof = checks.immutable_empty_candidate(candidate,base_sha=request.base_sha,
                head_sha=request.head_sha,candidate_sha=request.merge_sha,
                merge_parents=(request.base_sha,request.head_sha))
            A.require(type(proof) is dict and proof.get('tree')==tree_sha,
                'empty sync raw immutable source proof is unavailable')
            return {'schema':1,'kind':'verified-empty-sync-v1','qualification':False,'reusable':False,
                'immutable':proof,'binding':binding,'references':refs,'source':source,'native':invocation}
        first = observe()
        A.require(observe()==first,'empty sync source or native context changed')
        return first
    except (EvidenceError,GateError,ValueError,OSError,KeyError,TypeError,AttributeError,ImportError,
            subprocess.SubprocessError):
        return None

def _native_parent_run(controller, adapter, request, now):
    endpoint = ('actions/workflows/350930890/runs?branch='+quote(request.parent, safe='')
        +'&event=push&head_sha='+request.parent_sha)
    rows = adapter._pages(endpoint, 'workflow_runs', search=True)
    controller.A.require(bool(rows) and all(row.get('head_sha') == request.parent_sha
        and row.get('head_branch') == request.parent and row.get('event') == 'push'
        and row.get('workflow_id') == 350930890
        and row.get('path') == '.github/workflows/parent-qualification.yml' for row in rows),
        'native parent run inventory is incomplete or foreign')
    times = [controller.P._time(row.get('run_started_at')) for row in rows]
    newest = max(times)
    controller.A.require(newest <= now and times.count(newest) == 1,
        'native parent newest run ordering is ambiguous')
    run = rows[times.index(newest)]
    controller.A.require(run.get('run_attempt') == 1 and run.get('status') == 'completed'
        and run.get('conclusion') == 'success', 'native parent newest push is not successful attempt one')
    return controller.A.positive(run.get('id')), rows


def native_parent_evidence(api, config, request, now=None):
    """Authenticate original native M, actual parent P and current child M.

    This is not a newly executed or renewed parent qualification artifact.
    The original receipt/E/lifetime stay attached to their real original M.
    """
    try:
        controller = _native_parent_controller()
        A, P = controller.A, controller.P
        A.require(controller._source_qualified() and request.repository == A.REPOSITORY
            and request.repository_id == 1319052603 and config['trusted_actions_app_id'] == 15368
            and config['qualification_workflow'] == '.github/workflows/parent-qualification.yml'
            and request.parent in {'main', 'android-main', 'android-vr', 'apple-main'}
            and config['edges'][request.base]['parent'] == request.parent and not request.repair_paths,
            'native parent source capability or exact direct edge is unavailable')
        clock = (lambda: now) if now is not None else lambda: datetime.now(timezone.utc)
        now = clock()
        P._now(now)
        adapter = A.Adapter(api.native_producer_api(controller))
        child_binding, child_refs, local = _native_sync_context(controller, adapter, request)
        push_id, push_inventory = _native_parent_run(controller, adapter, request, now)
        policy = controller.producer._host_policy()
        workflows, helpers = controller.producer.metadata_generations(policy, root=ROOT)
        metadata = None
        if workflows is not None:
            caller = adapter._object('actions/workflows/repository-checks.yml')
            A.require(caller.get('path') == '.github/workflows/repository-checks.yml',
                'retained original caller registration differs')
            metadata = A.MetadataPolicy(A.positive(caller.get('id')), '.github/workflows/repository-checks.yml',
                workflows, helpers)
        origin = adapter.integrated_origin(push_id, 15368, metadata, now=now)
        binding, references = origin.binding, origin.references
        A.require(binding['base_ref'] == request.parent and references['target'] == request.parent_sha
            and references['default'] == child_refs['default']
            and references['integration']['push_status'] == 'completed'
            and references['integration']['push_conclusion'] == 'success',
            'native parent/default completed context changed')
        tree_sha, parent = controller.full_tree(adapter, request.parent_sha)
        _, previous = controller.full_tree(adapter, binding['base_sha'])
        generation=policy.package_policy().validate_tree_wiring(parent)
        future=generation in controller.producer.PLATFORM_GENERATIONS
        parent_template=controller.producer.PLATFORM_PARENT_TEMPLATE if future else controller.TEMPLATE
        project_template=controller.producer.project_template(policy,parent)
        A.require(generation in controller.GENERATIONS
            and parent.get('.github/workflows/parent-qualification.yml') == local.get(parent_template),
            'native parent workflow is not a complete trusted consumer recipe')
        controller_check=controller.integrated_controller_for_reuse if future else controller.integrated_controller
        source = controller_check(policy, previous, parent, local, request.parent, ROOT)
        registry = controller.inputs.load_registry(ROOT / '.github/test-suites.json')
        A.require(all(suite['scope'] == 'content' for suite in registry['suites'].values())
            and all(tree.get('.github/test-suites.json') == local.get('.github/test-suites.json')
                    for tree in (previous, parent)), 'native parent command registry differs from protected source')
        context = previous if request.parent == 'main' else local
        read_blob = adapter.api.immutable_blob
        selector=controller.producer.selection_profile_for_reuse if future else controller.producer.selection_profile
        profile = selector(policy, registry, parent, previous, context,
            root=ROOT, target=request.parent, read_blob=read_blob)
        selected = profile['selection']
        affected = controller._affected_receipt_selection(profile, registry, request.parent)
        partition=controller.producer.platform_partition(policy,profile,registry,parent,previous,local,
            target=request.parent,root=ROOT,read_blob=read_blob)
        if partition is None:
            A.require(controller.source_admission.shared_platform_supported(selected, request.parent,
                parent.get(controller.source_admission.PROFILE)), 'native parent product ownership is unavailable')
        owner=controller.producer.common_owner(profile,partition)
        plan, api_policy = controller._policy(policy, registry, binding, source, adapter, ROOT, selected,
            common_owner=owner,template=project_template)
        snapshot = adapter.capture_integrated(push_id, plan, api_policy, now=now)
        A.require(snapshot.references == references, 'native parent integration changed before proof selection')
        if future:
            profile,context=controller.producer.reuse_source_profile(snapshot,adapter,api_policy,policy,registry,
                parent,previous,root=ROOT,target=request.parent,read_blob=read_blob,now=clock())
            selected=profile['selection'];affected=controller._affected_receipt_selection(profile,registry,request.parent)
            partition=controller.producer.platform_partition(policy,profile,registry,parent,previous,local,
                target=request.parent,root=ROOT,read_blob=read_blob)
            owner=controller.producer.common_owner(profile,partition)
            plan,api_policy=controller._policy(policy,registry,binding,source,adapter,ROOT,selected,
                common_owner=owner,template=project_template)
        original_tree, original = controller.full_tree(adapter, snapshot.binding['merge_sha'])
        A.require(original_tree == tree_sha == snapshot.binding['merge_tree'] and original == parent
            and selector(policy, registry, original, previous, context,
                root=ROOT, target=request.parent, read_blob=read_blob) == profile,
            'native original source differs from exact parent inputs')
        A.require(controller.producer.platform_partition(policy,profile,registry,original,previous,local,
            target=request.parent,root=ROOT,read_blob=read_blob)==partition,
            'native original and current parent platform ownership differs')
        authority = P.select_authority(snapshot.observations, snapshot.binding, plan, api_policy.producer,
            inventory_complete=snapshot.inventory_complete, now=now)
        A.require(authority['state'] == 'proof-required', 'native parent original producer is unresolved')
        observation = next(item for item in snapshot.observations if item.run.run_id == authority['run_id'])
        platform_observation=(controller.original_platform_owner(adapter,observation.run,partition,now=clock())
            if partition is not None else None)
        raw, facts = adapter._artifact(observation.run, 'aggregate',
            snapshot.artifact_inventories[authority['run_id']], now, snapshot.binding['head_sha'])
        aggregate = P.read_artifact(raw, 'aggregate', facts, observation.run, now=now)
        receipt = aggregate.get('results', {}).get('shared-host', {}).get('receipt')
        A.require(type(receipt) is dict and receipt.get('schema') == api_policy.producer.required_execution_schema,
            'native parent versioned original receipt unavailable')
        git_context = controller.producer.expected_git_context(adapter, snapshot.binding)
        controller.execution.validate_receipt(receipt, registry, original,
            require_all=profile['profile'] != controller.ci_profile.PROFILE and not affected,
            expected_git_context=git_context)
        A.require(receipt['requested_suites'] == selected['suites']
            and receipt['include_platform'] == owner['include_platform']
            and (partition is None or receipt['platform_results']=={}), 'native parent selected owner differs')
        environment = receipt['environment']
        retained=controller.producer.retained_receipt_source(receipt,snapshot.binding,adapter,registry,selected,
            authority['run_id'],root=ROOT)
        shared = P.SharedContext(registry, original, environment, snapshot.binding['merge_sha'], tree_sha, git_context,retained)
        original_source=None
        if receipt['schema']==4:
            verified,original_source=controller.producer.verify_original_source(adapter,push_id,plan,api_policy,
                shared,receipt,snapshot.binding,integrated=True,root=ROOT,clock=clock)
        if profile['profile'] == controller.ci_profile.PROFILE:
            ci_context = ({'base_tree': previous}
                if profile['binding'].get('generation_kind') == controller.ci_profile.SEVEN_CONTROLLER_KIND else {})
            validator=(controller.runtime_ci.validate_environment if original_source is None else
                lambda *args,**kwargs:controller.runtime_ci.validate_original_environment(original_source,*args,**kwargs))
            admission = validator(environment, aggregate.get('qualified_at'),
                aggregate.get('expires_at'), now, selected, original, context, registry,
                root=ROOT, target=request.parent, read_blob=read_blob, **ci_context)
        else:
            admission = controller.attested.validate_environment(environment, aggregate.get('qualified_at'),
                aggregate.get('expires_at'), now, root=ROOT, isolated=True)
        if original_source is None:
            verified=adapter.verify_integrated(push_id,plan,api_policy,{'shared-host':shared},clock=clock)
        else:
            A.require(A.Adapter.verify_integrated(adapter,push_id,plan,api_policy,{'shared-host':shared},clock=clock)==verified,
                'native parent original proof changed during runtime/source admission')
        if partition is not None:
            A.require(controller.original_platform_owner(adapter,observation.run,partition,now=clock())==platform_observation,
                'native original Android platform job changed during common proof verification')
        A.require(verified['integration'] == references['integration']
            and verified['receipt_sha256'] == hashlib.sha256(P.canonical(receipt)).hexdigest()
            and verified['aggregate_digest'] == aggregate['aggregate_digest']
            and 0 <= (clock() - P._time(verified['qualified_at'])).total_seconds()
                <= int(config['evidence_max_age_hours']) * 3600,
            'native parent whole proof or allowed lifetime changed')
        _, candidate = controller.full_tree(adapter, request.merge_sha)
        A.require(candidate.get(controller.source_admission.PROFILE)==controller.source_admission.ordinary(
            controller.source_admission.TARGET_PROFILES[request.base]),
            'current child platform declaration needs its actual known owner')
        A.require(all(entry['mode'] in {'100644', '100755'} and entry['type'] == 'blob'
            for tree in (parent, candidate) for entry in tree.values()), 'native parent reuse requires ordinary complete inputs')
        candidate_plan = controller.inputs.plan_reuse(registry, parent, candidate, receipt['results'], environment, environment)
        final = _native_sync_context(controller, adapter, request)
        A.require(final == (child_binding, child_refs, local)
            and _native_parent_run(controller, adapter, request, clock()) == (push_id, push_inventory)
            and adapter.integrated_origin(push_id, 15368, metadata, now=clock()) == origin
            and controller_check(policy, previous, parent, local, request.parent, ROOT) == source
            and controller.producer.retained_receipt_source(receipt,snapshot.binding,adapter,registry,selected,authority['run_id'],root=ROOT)==retained
            and controller.producer.platform_partition(policy,profile,registry,parent,previous,local,
                target=request.parent,root=ROOT,read_blob=read_blob)==partition
            and (partition is None or controller.original_platform_owner(adapter,observation.run,partition,now=clock())==platform_observation)
            and clock() < P._time(verified['expires_at']),
            'native parent/default/source context changed before completion')
        A.require(bool(candidate_plan['reused']), 'native parent has no matching child suite source')
        return NativeParentEvidence({'kind': NATIVE_PARENT_KIND, 'parent_branch': request.parent, 'parent_commit': request.parent_sha,
            'parent_tree': tree_sha, 'original_commit': snapshot.binding['merge_sha'], 'original_git_context': git_context,
            'qualified_at': verified['qualified_at'], 'expires_at': verified['expires_at'],
            'environment': environment, 'results': {'conclusion': 'success', 'suites': receipt['results']},
            'child_platform_profile':candidate[controller.source_admission.PROFILE], 'platform_reused':False,
            'original_platform_observation':platform_observation,
            'original_proof': verified, 'original_protected_source':retained, 'runtime_admission': admission, 'candidate_plan': candidate_plan,
            'parent_inputs': parent, 'candidate_inputs': candidate})
    except EvidenceError:
        raise
    except (OSError, ValueError, KeyError, TypeError, AttributeError, ImportError, subprocess.SubprocessError) as error:
        raise EvidenceError('original native parent proof unavailable; actual synchronization execution is required') from error


def verify_evidence(api: GitHubApi, config: dict, request: SyncRequest, now: datetime | None = None) -> dict:
    try:
        return _verify_legacy_evidence(api, config, request, now)
    except EvidenceError:
        # Preserve legacy2 routes exactly. The native path requires the fixed
        # bounded transport explicitly, never an arbitrary JSON/proof fallback.
        if not callable(getattr(api, 'native_producer_api', None)):
            raise
        return native_parent_evidence(api, config, request, now)


def write_outputs(path: Path | None, values: dict[str, object]) -> None:
    lines = [f"{key}={str(value).lower() if isinstance(value, bool) else value}" for key, value in values.items()]
    if path:
        with path.open("a", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
    for line in lines:
        print(line)


def pure_metadata_event(event, event_name):
    """Only complete same-fork title/body edits; base or unknown edits stay work."""
    if event_name != 'pull_request_target' or type(event) is not dict or event.get('action') != 'edited':
        return False
    changes, pr, repository = event.get('changes'), event.get('pull_request'), event.get('repository')
    if type(changes) is not dict or not changes or not set(changes) <= {'title', 'body'} \
            or type(pr) is not dict or type(repository) is not dict \
            or (repository.get('full_name'), repository.get('id')) != ('noah-l-frank/overte', 1319052603) \
            or type(event.get('number')) is not int or event['number'] <= 0 \
            or type(pr.get('number')) is not int or pr['number'] != event['number'] or pr.get('state') != 'open':
        return False
    for side in ('base', 'head'):
        row = pr.get(side)
        if type(row) is not dict or type(row.get('ref')) is not str or not row['ref'] \
                or type(row.get('sha')) is not str or not SHA_RE.fullmatch(row['sha']) \
                or row['sha'] == '0' * 40 or type(row.get('repo')) is not dict \
                or (row['repo'].get('full_name'), row['repo'].get('id')) != ('noah-l-frank/overte', 1319052603):
            return False
    for name, change in changes.items():
        allowed = (str, type(None)) if name == 'body' else (str,)
        if type(change) is not dict or set(change) != {'from'} \
                or not isinstance(change['from'], allowed) or name not in pr or not isinstance(pr[name], allowed):
            return False
    return True


def classify_metadata(args):
    event = json.loads(args.event.read_bytes(), object_pairs_hook=suite_inputs._unique_object)
    metadata = pure_metadata_event(event, os.environ.get('GITHUB_EVENT_NAME'))
    edge = load_config(args.config)['edges'].get(event.get('pull_request', {}).get('base', {}).get('ref')) if metadata else None
    head = event['pull_request']['head']['ref'] if metadata else ''
    relevant = bool(edge and (head == edge['parent'] or
        head.startswith('reconcile/' + edge['scope'] + '/') and head.count('/') == 2))
    write_outputs(args.output, {'metadata_only': metadata and relevant})
    return 0


def _metadata_list(api, endpoint, key):
    value = api.json(endpoint)
    if type(value) is not dict or type(value.get('total_count')) is not int \
            or type(value.get(key)) is not list or not 0 <= value['total_count'] <= 100 \
            or len(value[key]) != value['total_count'] \
            or any(type(row) is not dict or type(row.get('id')) is not int or row['id'] <= 0 for row in value[key]) \
            or len({row['id'] for row in value[key]}) != len(value[key]):
        raise GateError('metadata original native inventory is truncated/malformed: ' + key)
    return value[key]


def _metadata_check(api, prefix, run, job, source):
    url = job.get('check_run_url', '')
    start = 'https://api.github.com/' + prefix + '/check-runs/'
    if not url.startswith(start) or not re.fullmatch('[1-9][0-9]*', url[len(start):]):
        raise GateError('metadata original native job check is unavailable')
    check = api.json(prefix + '/check-runs/' + url[len(start):])
    expected = {'id': int(url[len(start):]), 'head_sha': source, 'name': job['name'],
                'status': job['status'], 'conclusion': job['conclusion']}
    if not isinstance(check, dict) or any(type(check.get(k)) is not type(v) or check[k] != v for k, v in expected.items()) \
            or type(check.get('app', {}).get('id')) is not int or check['app']['id'] != 15368 \
            or type(check.get('check_suite', {}).get('id')) is not int or check['check_suite']['id'] != run['check_suite_id'] \
            or type(job.get('run_id')) is not int or job['run_id'] != run['id'] \
            or type(job.get('run_attempt')) is not int or job['run_attempt'] != 1 or job.get('head_sha') != source:
        raise GateError('metadata original native job/App/source differs')
    return check


def _metadata_gate_run(api, prefix, identifier, request, *, normal_parent=None):
    run = api.json(prefix + '/actions/runs/' + str(identifier))
    attempt = api.json(prefix + '/actions/runs/' + str(identifier) + '/attempts/1')
    integrated = False
    if normal_parent is not None:
        normal = commit(api, request.repository, normal_parent)
        integrated = commit_parents(normal) == (request.base_sha, request.head_sha)
        if not integrated:
            raise GateError('original gate has no exact normal integration')
    fields = {'id': identifier, 'workflow_id': 350930894, 'run_attempt': 1,
        'path': '.github/workflows/sync-test-reuse.yml', 'event': 'pull_request_target',
        'head_sha': request.head_sha, 'head_branch': request.head}
    for value in (run, attempt):
        if type(value) is not dict or any(type(value.get(k)) is not type(v) or value[k] != v for k, v in fields.items()) \
                or type(value.get('check_suite_id')) is not int or value['check_suite_id'] <= 0 \
                or any(type(value.get(k)) is not dict or type(value[k].get('id')) is not int or (value[k].get('id'), value[k].get('full_name')) !=
                       (1319052603, 'noah-l-frank/overte') for k in ('repository', 'head_repository')) \
                or type(value.get('pull_requests')) is not list \
                or not all(type(p) is dict for p in value['pull_requests']) \
                or not (any(type(p.get('number')) is int and p['number'] == request.number
                    and p.get('base', {}).get('sha') == request.base_sha
                    and p.get('head', {}).get('sha') == request.head_sha for p in value.get('pull_requests', []))
                    or integrated and value['pull_requests'] == []):
            raise GateError('metadata original gate source/attempt/PR association differs')
        if integrated and value['pull_requests']:
            association = value['pull_requests'][0]
            if len(value['pull_requests']) != 1 or type(association.get('number')) is not int \
                    or association['number'] != request.number \
                    or association.get('base', {}).get('sha') != request.base_sha \
                    or association.get('head', {}).get('sha') != request.head_sha:
                raise GateError('exact normal parent has mixed or mismatched original PR associations')
    pending = {'queued', 'in_progress', 'waiting', 'pending', 'requested'}
    if any(run.get(k) != attempt.get(k) for k in (*fields, 'check_suite_id')) or (
            (run.get('status'), run.get('conclusion')) != (attempt.get('status'), attempt.get('conclusion'))
            and not all(v.get('status') in pending and v.get('conclusion') is None for v in (run, attempt))):
        raise GateError('metadata original gate native attempt changed')
    return run, attempt


def _metadata_step(job, name):
    steps = [s for s in job.get('steps', []) if s.get('name') == name]
    if len(steps) != 1 or steps[0].get('status') != 'completed' or steps[0].get('conclusion') != 'success':
        raise GateError('metadata original successful step unavailable: ' + name)
    value = steps[0]
    if not parse_time(job['started_at'], 'job start') <= parse_time(value['started_at'], 'step start') \
            <= parse_time(value['completed_at'], 'step completion') <= parse_time(job['completed_at'], 'job completion'):
        raise GateError('metadata original step chronology differs')
    return value


def _metadata_report(api, prefix, run, item, request, source, validator, registry, selected, tree, now,
                     *, normal_parent=None):
    """Read exact independent or inherited-CI data; grant no E/reuse."""
    expected_owner = {'id': run['id'], 'repository_id': 1319052603, 'head_repository_id': 1319052603,
                      'head_branch': 'main', 'head_sha': source}
    if type(item.get('id')) is not int or item['id'] <= 0 or item.get('expired') is not False \
            or type(item.get('size_in_bytes')) is not int or not 0 < item['size_in_bytes'] < 5_000_000 \
            or item.get('workflow_run') != expected_owner \
            or not re.fullmatch('sha256:[0-9a-f]{64}', item.get('digest', '')):
        raise GateError('metadata original validation artifact ownership/expiry/digest differs')
    if not parse_time(item['created_at'], 'artifact creation') < parse_time(item['expires_at'], 'artifact expiry') \
            or parse_time(item['expires_at'], 'artifact expiry') <= now:
        raise GateError('metadata original validation artifact has expired')
    raw = api.bytes(prefix + '/actions/artifacts/' + str(item['id']) + '/zip')
    if len(raw) != item['size_in_bytes'] or 'sha256:' + hashlib.sha256(raw).hexdigest() != item['digest']:
        raise GateError('metadata original artifact byte digest differs')
    xml_path = 'build/test-results/sync-selected.xml'
    report_path = 'build/test-results/sync-validation.json'
    allowed = {xml_path, report_path, report_path + '.ci-execution.json'}
    payload = {}
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries = archive.infolist()
        if len(entries) > 12 or sum(i.file_size for i in entries) > 10_000_000:
            raise GateError('metadata original archive exceeds bound')
        seen = set()
        for entry in entries:
            path = Path(entry.filename)
            if entry.filename in seen or path.is_absolute() or '..' in path.parts or '\\' in entry.filename \
                    or path.as_posix() != entry.filename.rstrip('/') or entry.flag_bits & 1 \
                    or stat.S_IFMT(entry.external_attr >> 16) not in (0, stat.S_IFREG, stat.S_IFDIR):
                raise GateError('metadata original artifact member is unsafe')
            seen.add(entry.filename)
            if entry.is_dir():
                if not any(name.startswith(entry.filename) for name in allowed):
                    raise GateError('metadata original unrelated archive directory')
            elif entry.filename not in allowed:
                raise GateError('metadata original unknown artifact member')
            else:
                payload[entry.filename] = archive.read(entry)
    if not {xml_path, report_path} <= set(payload):
        raise GateError('metadata original artifact incomplete')
    def decode(data):
        def bad(_): raise GateError('metadata original nonfinite JSON')
        return json.loads(data, object_pairs_hook=suite_inputs._unique_object, parse_constant=bad)
    report = decode(payload[report_path])
    inherited = report.get('mode') == 'native-exact-tree-parent'
    standalone = report.get('mode') == 'native-standalone-ci'
    if inherited and normal_parent is not None:
        raise GateError('an inherited Sync report cannot become a recursive normal-parent proof')
    expected_members = {xml_path, report_path} if inherited else allowed
    if set(payload) != expected_members:
        raise GateError('metadata original artifact form is incomplete or mixed')
    observed = None if inherited else decode(payload[report_path + '.ci-execution.json'])
    requested_mode = 'reuse' if inherited else 'fallback'
    expected_mode = 'native-exact-tree-parent' if inherited else 'native-standalone-ci' if standalone else 'affected-ci'
    if normal_parent is not None:
        # Keep the original temporary M in its report. The current normal N is
        # a separate immutable commit with precisely the same tree and parents.
        original_merge = validate_sha(report['candidate']['merge_commit'], 'original Sync merge')
        for revision in (normal_parent, original_merge):
            actual = commit(api, request.repository, revision)
            if commit_parents(actual) != (request.base_sha, request.head_sha) or commit_tree(actual) != tree:
                raise GateError('original Sync tested merge differs from exact normal parent')
        request = replace(request, merge_sha=original_merge)
    selection = report['ci_selection']
    for value, field in ((report, 'receipt_digest'), (selection, 'selection')):
        unsigned = dict(value); claimed = unsigned.pop(field)
        if claimed != 'sha256:' + hashlib.sha256(canonical_json(unsigned)).hexdigest():
            raise GateError('metadata original whole report/selection digest differs')
    candidate = dict(base_branch=request.base, base_commit=request.base_sha, head_branch=request.head,
        head_commit=request.head_sha, merge_commit=request.merge_sha, merge_tree=tree,
        parent_branch=request.parent, parent_commit=request.parent_sha, profile=request.profile,
        classification=request.classification)
    names = selected['suites']; omitted = [n for n in registry['suites'] if n not in names]
    if type(report.get('schema')) is not int or type(report.get('repository_id')) is not int or type(report.get('pull_request')) is not int \
            or (report['schema'], report['producer'], report['repository'], report['repository_id'], report['pull_request'],
            report['requested_mode'], report['mode'], report['conclusion']) != (
            1, 'overte-trusted-sync-validation-v1', request.repository, request.repository_id, request.number,
            requested_mode, expected_mode, 'success') or report['candidate'] != candidate \
            or report['execution'] != observed \
            or report['not_selected_suites'] != omitted or report.get('pending_platform_owners') \
            or report.get('external_package_set'):
        raise GateError('metadata original independently executed context/mode differs')
    if inherited:
        expected_fields = {'schema','producer','repository','repository_id','pull_request','candidate',
            'requested_mode','mode','reused_suites','executed_suites','bounded_projects','execution',
            'parent_evidence','conclusion','started_at','completed_at','reusable','qualification',
            'ci_selection','not_selected_suites','receipt_digest'}
        if set(report) != expected_fields or report.get('qualification') is not False or report.get('reusable') is not False \
                or report['executed_suites'] != [] or report['reused_suites'] != names or report['bounded_projects'] != []:
            raise GateError('metadata inherited report claims unknown or new execution authority')
    elif standalone:
        expected_fields = {'schema','producer','repository','repository_id','pull_request','candidate',
            'requested_mode','mode','reused_suites','executed_suites','bounded_projects','execution',
            'parent_evidence','conclusion','started_at','completed_at','reusable','qualification',
            'ci_selection','not_selected_suites','receipt_digest','standalone_owner_evidence'}
        reused = validator._standalone_ci_names(selection, registry)
        remaining = [name for name in names if name not in reused]
        if set(report) != expected_fields or len(reused) != 4 or len(remaining) != 33 \
                or report.get('qualification') is not False or report.get('reusable') is not False \
                or report['reused_suites'] != reused or report['executed_suites'] != remaining \
                or report['parent_evidence'] is not None or report['bounded_projects'] != []:
            raise GateError('metadata standalone report lacks exact disjoint four-plus33 coverage')
        _metadata_standalone_owners(api, request, source, validator, registry, report, now,
            normal_parent=normal_parent)
    elif report['executed_suites'] != names or report['reused_suites'] != [] or report['parent_evidence'] is not None:
        raise GateError('metadata original independent execution coverage differs')
    if type(selection.get('schema')) is not int or selection['schema'] != 1 or selection.get('kind') != 'sync-ci-selection' \
            or type(selection.get('repository_id')) is not int or type(selection.get('pull_request')) is not int \
            or (selection['repository'], selection['repository_id'], selection['pull_request'], selection['base'],
            selection['head'], selection['candidate'], selection['tree'], selection['parent'], selection['target'],
            selection['profile'], selection['requested_mode']) != (
            request.repository, request.repository_id, request.number, request.base_sha, request.head_sha,
            request.merge_sha, tree, request.parent_sha, request.base, request.profile, requested_mode) \
            or selection['lane'] != 'affected-ci' or selection['full_host'] is not False \
            or selection['reusable'] is not False or selection['suites'] != names \
            or selection['omitted_suites'] != omitted or selection['external_package_set'] != [] \
            or selection['registry'] != validator.execution.digest(registry) or selection['dependency_selection'] != selected:
        raise GateError('metadata original selected commands/source differ')
    if inherited:
        _metadata_inherited_parent(api, config=load_config(), request=request, source=source,
            validator=validator, names=names, tree=tree, report=report, now=now)
    else:
        validator._verify_ci_execution(observed, selection, registry, (request.merge_sha, tree),
            suite_names=report['executed_suites'] if standalone else None)
    xml_raw = payload[xml_path]
    if b'<!DOCTYPE' in xml_raw.upper() or b'<!ENTITY' in xml_raw.upper():
        raise GateError('metadata original XML entities forbidden')
    xml = ET.fromstring(xml_raw); cases = list(xml.iter('testcase'))
    junit_names = ['sync-differential'] if inherited else report['executed_suites'] if standalone else names
    if [c.get('name') for c in cases] != junit_names or int(xml.get('tests')) != len(junit_names) \
            or any(int(xml.get(k, '0')) for k in ('failures', 'errors', 'skipped')) \
            or any(c.find(k) is not None for c in cases for k in ('failure', 'error', 'skipped')):
        raise GateError('metadata original ordered JUnit incomplete/failed/skipped')
    return report, observed


def _metadata_standalone_owners(api, request, source, validator, registry, report, now, *, normal_parent=None):
    proof = validator.verify_standalone_ci_owners(api, sys.modules[__name__], request, registry,
        report['ci_selection'], now=now, normal_parent=normal_parent, protected_source=source,
        protected_tree=commit_tree(commit(api, request.repository, source)))
    validator.verify_standalone_ci_provenance(report['standalone_owner_evidence'], proof,
        request, normal_parent=normal_parent)
    if max(parse_time(job['completed_at'], 'standalone owner completion')
            for job in proof['native']['selected_jobs'].values()) > parse_time(
                report['execution']['started_at'], 'remaining commands start'):
        raise GateError('standalone commands were not completed before the remaining CI execution')
    return proof


def _metadata_inherited_parent(api, *, config, request, source, validator, names, tree, report, now):
    """Reauthenticate the finite current VR parent proof, never a JSON claim."""
    if (request.base,request.parent,request.profile) != ('android-vr','android-main','android-vr') \
            or len(names) != 37 or len(set(names)) != 37:
        raise GateError('metadata inherited report is outside the exact Android CI37 edge')
    protected_tree = commit_tree(commit(api,request.repository,source))
    proof = verify_exact_tree_parent_evidence(api,config,request,protected_source=source,
        protected_tree=protected_tree,now=now)
    if not isinstance(proof,NativeExactTreeParentEvidence) or proof.get('qualification') is not False \
            or proof.get('reusable') is not False or proof.get('source') != source \
            or proof.get('parent_branch') != request.parent or proof.get('parent_commit') != request.parent_sha \
            or proof.get('parent_tree') != tree or proof.get('requested_suites') != names \
            or not _original_ci_command_coverage(proof.get('original_report', {}), names) \
            or parse_time(proof['expires_at'],'original inherited expiry') <= now \
            or parse_time(proof['qualified_at'],'original inherited completion') > parse_time(report['started_at'],'inheriting report start') \
            or validator._parent_provenance(proof,names,sys.modules[__name__]) != report['parent_evidence']:
        raise GateError('metadata inherited parent execution/provenance is unavailable or changed')
    return proof


def _original_ci_command_coverage(report, names):
    """Only after native/report verification: original execution, never recursion."""
    if report.get('requested_mode') != 'fallback':
        return False
    if report.get('mode') == 'affected-ci':
        return report.get('executed_suites') == names and report.get('reused_suites') == []
    if report.get('mode') != 'native-standalone-ci':
        return False
    four = {'documentation-contracts', 'documentation', 'policy-consistency', 'workflow-contracts'}
    reused = [name for name in names if name in four]
    return (len(names) == len(set(names)) == 37 and len(reused) == 4
        and report.get('reused_suites') == reused
        and report.get('executed_suites') == [name for name in names if name not in four]
        and report.get('parent_evidence') is None and report.get('qualification') is False
        and report.get('reusable') is False
        and report.get('standalone_owner_evidence', {}).get('kind') == 'same-pr-native-standalone-ci-commands-v1')


def _completed_sync_report(api, prefix, original, check, request, source,
                           before, candidate, trusted, tree, now, *, normal_parent=None):
    """Verify original native execution data; do not create reusable evidence."""
    if (original.get('status'), original.get('conclusion'), check.get('status'), check.get('conclusion')) != (
            'completed', 'success', 'completed', 'success'):
        raise GateError('original independent Sync owner is not successful')
    jobs = _metadata_list(api, prefix + '/actions/runs/' + str(original['id']) + '/attempts/1/jobs?per_page=100', 'jobs')
    rows = [j for j in jobs if j.get('name') == 'sync-test-reuse']
    if len(rows) != 1 or rows[0].get('conclusion') != 'success':
        raise GateError('metadata original canonical native job unavailable')
    job = rows[0]
    if _metadata_check(api, prefix, original, job, request.head_sha) != check:
        raise GateError('metadata original canonical native check differs')
    for name in ('Inspect topology and exact parent evidence', 'Dispatch isolated read-only validation', 'Publish decision'):
        _metadata_step(job, name)
    log = api.bytes(prefix + '/actions/jobs/' + str(job['id']) + '/logs')
    if len(log) > 8_000_000:
        raise GateError('metadata original gate log exceeds bound')
    child_ids = set(re.findall(rb'\bvalidation_run_id=([1-9][0-9]*)\b', log))
    if len(child_ids) != 1:
        raise GateError('metadata original lacks one authenticated validator ID')
    child = int(child_ids.pop()); correlation = 'gate-' + str(original['id']) + '-attempt-1'
    if ('validation_url=https://github.com/' + request.repository + '/actions/runs/' + str(child)).encode() not in log:
        raise GateError('metadata original validator URL differs')
    run = api.json(prefix + '/actions/runs/' + str(child))
    identity = _dispatch_run(run, child, source, correlation)
    if (run['status'], run['conclusion']) != ('completed', 'success'):
        raise GateError('metadata original validator did not succeed')
    _dispatch_native(api, prefix, run, source, correlation, identity)
    child_jobs = _metadata_list(api, prefix + '/actions/runs/' + str(child) + '/attempts/1/jobs?per_page=100', 'jobs')
    validators = [j for j in child_jobs if j.get('name') == 'Validate exact synchronization']
    if len(validators) != 1:
        raise GateError('metadata original validator native role missing')
    validator_job = validators[0]; validator_check = _metadata_check(api, prefix, run, validator_job, source)
    executed = _metadata_step(validator_job, 'Verify exact candidate suites and complete runtime identity')
    upload = _metadata_step(validator_job, 'Upload validation test reports')
    artifacts = _metadata_list(api, prefix + '/actions/runs/' + str(child) + '/artifacts?per_page=100', 'artifacts')
    if len(artifacts) != 1 or artifacts[0].get('name') != 'sync-validation-reports-' + str(child) + '-1':
        raise GateError('metadata original sole validation artifact unavailable')
    item = artifacts[0]
    if not parse_time(upload['started_at'], 'upload start') <= parse_time(item['created_at'], 'artifact creation') \
            <= parse_time(upload['completed_at'], 'upload completion'):
        raise GateError('metadata original artifact outside native upload')
    host = package_checks.load('sync_metadata_host', 'tools/repository-checks/host_selection.py')
    registry = suite_inputs.load_registry(ROOT / '.github/test-suites.json')
    regular = all(entry is None or entry['type'] == 'blob' and entry['mode'] in {'100644', '100755'}
        for name in request.changed_paths for entry in (before.get(name), candidate.get(name)))
    selected = host.select(candidate, list(request.changed_paths), regular, base_tree=before, trusted_tree=trusted,
                           candidate_root=ROOT, trusted_root=ROOT, target=request.base)
    if selected.get('full_host') is not False or selected.get('include_platform') is not False \
            or not selected.get('suites') or len(selected['suites']) != len(set(selected['suites'])) \
            or any(name not in registry['suites'] for name in selected['suites']):
        raise GateError('metadata original selection is not independently bounded CI')
    directory = str(ROOT / 'tools/test-evidence'); search = list(sys.path)
    try:
        sys.path.insert(0, directory)
        validator = package_checks.load('sync_metadata_validator', 'tools/test-evidence/validate-sync.py')
    finally:
        sys.path[:] = search
    report, observed = _metadata_report(api, prefix, run, item, request, source, validator, registry, selected, tree, now, normal_parent=normal_parent)
    if observed is None:
        chronology = (report['mode'] == 'native-exact-tree-parent'
            and parse_time(executed['started_at'], 'execution start') <= parse_time(report['started_at'], 'report start')
                <= parse_time(report['completed_at'], 'report completion')
                < parse_time(executed['completed_at'], 'execution completion') + timedelta(seconds=1))
    else:
        chronology = (parse_time(executed['started_at'], 'execution start') <= parse_time(report['started_at'], 'report start')
            <= parse_time(observed['started_at'], 'observed start') <= parse_time(observed['completed_at'], 'observed completion')
            <= parse_time(report['completed_at'], 'report completion')
            < parse_time(executed['completed_at'], 'execution completion') + timedelta(seconds=1))
    if not chronology:
        raise GateError('metadata original report outside native execution')
    return {name: value for name, value in locals().items() if name in {
        'jobs', 'job', 'child', 'correlation', 'run', 'identity', 'validator_job',
        'validator_check', 'artifacts', 'item', 'report', 'observed', 'selected', 'validator'}}


def _metadata_pending_owner(api, prefix, original, attempt, request, source, event, current_id, tree):
    """Keep pending scheduling pending; no original M/result is invented."""
    suite = api.json(prefix + '/check-suites/' + str(original['check_suite_id']))
    if type(suite) is not dict or suite.get('id') != original['check_suite_id'] \
            or suite.get('head_sha') != request.head_sha or suite.get('app', {}).get('id') != 15368 \
            or (suite.get('repository', {}).get('id'), suite.get('repository', {}).get('full_name')) != (
                request.repository_id, request.repository):
        raise GateError('pending metadata original native suite/App differs')
    created = original.get('created_at')
    parse_time(created, 'pending original creation')
    endpoint = prefix + '/actions/workflows/350930895/runs?event=workflow_dispatch&created=' + quote('>=' + created, safe='') + '&per_page=100'
    rows = _metadata_list(api, endpoint, 'workflow_runs')
    correlation = 'gate-' + str(original['id']) + '-attempt-1'
    children = [r for r in rows if r.get('display_title') == 'Sync validation ' + correlation]
    if len(children) > 1:
        raise GateError('pending metadata original validator correlation is ambiguous')
    child = None
    if children:
        child = children[0]['id']; run = api.json(prefix + '/actions/runs/' + str(child))
        identity = _dispatch_run(run, child, source, correlation, allow_pending=True)
        if run.get('status') == 'completed' and run.get('conclusion') != 'success':
            raise GateError('pending metadata original validator failed/cancelled')
        _dispatch_native(api, prefix, run, source, correlation, identity, allow_pending=True)
    closing, closing_attempt = _metadata_gate_run(api, prefix, original['id'], request)
    fields = ('id', 'workflow_id', 'run_attempt', 'path', 'event', 'head_sha', 'head_branch',
              'check_suite_id', 'repository', 'head_repository', 'pull_requests', 'created_at')
    if any(a.get(k) != b.get(k) for a, b in zip((original, attempt), (closing, closing_attempt)) for k in fields):
        raise GateError('pending metadata original immutable source changed')
    if closing.get('status') not in {'queued', 'in_progress', 'waiting', 'pending', 'requested'} or closing.get('conclusion') is not None:
        raise _DispatchRegistrationPending('original Sync completed during metadata scheduling admission')
    closing_suite = api.json(prefix + '/check-suites/' + str(original['check_suite_id']))
    if any(closing_suite.get(k) != suite.get(k) for k in ('id', 'head_sha', 'app', 'repository')) \
            or classify_event(event, load_config(), api) != request or _dispatch_checkout_source() != source:
        raise GateError('pending metadata original topology/source/App changed')
    _dispatch_source(api, load_config(), request.repository, source)
    return {'metadata_authenticated': True, 'original_gate_run': original['id'], 'validation_run': child,
            'original_state': 'pending', 'original_status': closing['status'], 'original_tested_merge': None,
            'current_candidate': request.merge_sha, 'current_tree': tree, 'new_dispatches': 0,
            'new_execution': False, 'qualification': False}


def retain_metadata_owner(event, config, api, *, environment=None, now=None):
    """Retain one actual original owner; never dispatch, normalize or mint E."""
    env = os.environ if environment is None else environment
    now = datetime.now(timezone.utc) if now is None else now
    if not pure_metadata_event(event, env.get('GITHUB_EVENT_NAME')) or any(env.get(k) != v for k, v in {
            'GITHUB_ACTIONS': 'true', 'GITHUB_REPOSITORY': 'noah-l-frank/overte',
            'GITHUB_REPOSITORY_ID': '1319052603', 'GITHUB_JOB': 'metadata-owner', 'GITHUB_RUN_ATTEMPT': '1'}.items()):
        raise GateError('metadata retention requires its exact native read-only role')
    if not re.fullmatch('[1-9][0-9]*', env.get('GITHUB_RUN_ID', '')):
        raise GateError('metadata current native run unavailable')
    request = classify_event(event, config, api)
    if request is None or request.repair_paths or request.profile in {'documentation', 'tool-dependencies'}:
        raise GateError('metadata retention requires the exact independently selected Sync context')
    if any(env.get(k) != v for k, v in {'GITHUB_REF': 'refs/heads/' + request.base,
            'GITHUB_SHA': request.base_sha, 'GITHUB_WORKFLOW_SHA': request.base_sha,
            'GITHUB_WORKFLOW_REF': request.repository + '/.github/workflows/sync-test-reuse.yml@refs/heads/' + request.base}.items()):
        raise GateError('metadata current native caller recipe/base differs')
    prefix = 'repos/' + request.repository
    source = _dispatch_checkout_source()
    _dispatch_source(api, config, request.repository, source)
    registration = api.json(prefix + '/actions/workflows/350930894')
    if (registration.get('id'), registration.get('path'), registration.get('state')) != (
            350930894, '.github/workflows/sync-test-reuse.yml', 'active'):
        raise GateError('metadata original gate registration differs')
    current_id = int(env['GITHUB_RUN_ID'])
    current, current_attempt = _metadata_gate_run(api, prefix, current_id, request)
    if current['status'] not in {'queued', 'in_progress', 'waiting', 'pending', 'requested'} or current.get('conclusion') is not None:
        raise GateError('metadata current run is not an active never-dispatch role')
    current_jobs = _metadata_list(api, prefix + '/actions/runs/' + str(current_id) + '/attempts/1/jobs?per_page=100', 'jobs')
    current_roles = [j for j in current_jobs if j.get('name') == 'Retain original Sync owner']
    if len(current_roles) != 1 or current_roles[0].get('status') != 'in_progress' or current_roles[0].get('conclusion') is not None:
        raise GateError('metadata current read-only native role unavailable')
    current_job = current_roles[0]
    _metadata_check(api, prefix, current, current_job, request.head_sha)
    tree, candidate = recursive_tree(api, request.repository, request.merge_sha)
    _, before = recursive_tree(api, request.repository, request.base_sha)
    _, trusted = recursive_tree(api, request.repository, source)
    workflow_path = '.github/workflows/sync-test-reuse.yml'
    for relative in ('tools/sync-test-reuse/gate.py', workflow_path):
        raw_source = (ROOT / relative).read_bytes()
        expected = {'mode': '100644', 'type': 'blob',
                    'sha': hashlib.sha1(b'blob ' + str(len(raw_source)).encode() + b'\0' + raw_source).hexdigest()}
        if trusted.get(relative) != expected:
            raise GateError('metadata actual protected gate/recipe differs from immutable default')
    if before.get(workflow_path) != trusted[workflow_path]:
        raise GateError('metadata original gate recipe differs from protected default')
    if candidate.get('.github/test-suites.json') != trusted.get('.github/test-suites.json'):
        raise GateError('metadata original candidate registry differs from protected validator')
    checks = _metadata_list(api, prefix + '/commits/' + request.head_sha + '/check-runs?filter=all&per_page=100', 'check_runs')
    canonical = [c for c in checks if c.get('name') == 'sync-test-reuse' and c.get('app', {}).get('id') == 15368]
    if len(canonical) > 1 or any(c.get('head_sha') != request.head_sha for c in canonical):
        raise GateError('metadata original canonical Sync owner missing/ambiguous')
    runs = _metadata_list(api, prefix + '/actions/workflows/350930894/runs?head_sha=' + request.head_sha + '&per_page=100', 'workflow_runs')
    check = canonical[0] if canonical else None
    owners = ([r for r in runs if r.get('check_suite_id') == check.get('check_suite', {}).get('id')] if check else
        [r for r in runs if type(r.get('id')) is int and r['id'] < current_id and r.get('event') == 'pull_request_target'
         and r.get('head_sha') == request.head_sha and r.get('head_branch') == request.head
         and r.get('display_title') == 'Sync test reuse for PR ' + str(request.number)])
    if len(owners) != 1 or type(owners[0].get('id')) is not int or not 0 < owners[0]['id'] < current_id:
        raise GateError('metadata original native owner is not unique/earlier')
    original, attempt = _metadata_gate_run(api, prefix, owners[0]['id'], request)
    if original['status'] in {'queued', 'in_progress', 'waiting', 'pending', 'requested'} and original['conclusion'] is None:
        if check is not None and (check.get('status') not in {'queued', 'in_progress', 'waiting', 'pending', 'requested'}
                                  or check.get('conclusion') is not None):
            raise GateError('metadata original pending canonical state differs')
        result = _metadata_pending_owner(api, prefix, original, attempt, request, source, event, current_id, tree)
        closing_current = _metadata_gate_run(api, prefix, current_id, request)
        if any(a.get(k) != b.get(k) for a, b in zip((current, current_attempt), closing_current)
                for k in ('id', 'workflow_id', 'run_attempt', 'path', 'event', 'head_sha', 'head_branch',
                          'check_suite_id', 'repository', 'head_repository', 'pull_requests')):
            raise GateError('pending metadata current native invocation changed')
        _metadata_check(api, prefix, closing_current[0], current_job, request.head_sha)
        closing_checks = _metadata_list(api, prefix + '/commits/' + request.head_sha + '/check-runs?filter=all&per_page=100', 'check_runs')
        closing_canonical = [c for c in closing_checks if c.get('name') == 'sync-test-reuse' and c.get('app', {}).get('id') == 15368]
        if len(closing_canonical) > 1 or any(c.get('head_sha') != request.head_sha
                or c.get('check_suite', {}).get('id') != original['check_suite_id'] for c in closing_canonical):
            raise GateError('pending metadata canonical owner identity changed')
        if any(c.get('status') not in {'queued', 'in_progress', 'waiting', 'pending', 'requested'}
               or c.get('conclusion') is not None for c in closing_canonical):
            raise _DispatchRegistrationPending('original Sync canonical result advanced during scheduling admission')
        return result
    if check is None:
        raise GateError('completed metadata original canonical check unavailable')
    if (original['status'], original['conclusion'], check.get('status'), check.get('conclusion')) != (
            'completed', 'success', 'completed', 'success'):
        # No waiting runner, fallback, status conversion or new canonical PASS.
        raise GateError('metadata original Sync owner remains pending/failed/cancelled')
    proof = _completed_sync_report(api, prefix, original, check, request, source,
        before, candidate, trusted, tree, now)
    jobs, job, child, correlation, run, identity, validator_check, artifacts = (
        proof[key] for key in ('jobs', 'job', 'child', 'correlation', 'run', 'identity', 'validator_check', 'artifacts'))
    _dispatch_native(api, prefix, run, source, correlation, identity)
    immutable = ('id', 'workflow_id', 'run_attempt', 'path', 'event', 'head_sha', 'head_branch',
                 'check_suite_id', 'repository', 'head_repository', 'pull_requests')
    closing_current = _metadata_gate_run(api, prefix, current_id, request)
    if any(a.get(k) != b.get(k) for a, b in zip((current, current_attempt), closing_current) for k in immutable) \
            or _metadata_gate_run(api, prefix, original['id'], request) != (original, attempt) \
            or _metadata_list(api, prefix + '/actions/runs/' + str(original['id']) + '/attempts/1/jobs?per_page=100', 'jobs') != jobs \
            or api.json(prefix + '/check-runs/' + str(check['id'])) != check \
            or api.json(prefix + '/check-runs/' + str(validator_check['id'])) != validator_check \
            or api.json(prefix + '/actions/runs/' + str(child)) != run \
            or _metadata_list(api, prefix + '/actions/runs/' + str(child) + '/artifacts?per_page=100', 'artifacts') != artifacts \
            or classify_event(event, config, api) != request or _dispatch_checkout_source() != source:
        raise GateError('metadata original native/source/report bookend changed')
    closing_jobs = _metadata_list(api, prefix + '/actions/runs/' + str(current_id) + '/attempts/1/jobs?per_page=100', 'jobs')
    closing_roles = [j for j in closing_jobs if j.get('name') == 'Retain original Sync owner']
    if len(closing_roles) != 1 or any(closing_roles[0].get(k) != current_job.get(k)
            for k in ('id', 'run_id', 'run_attempt', 'head_sha', 'name', 'status', 'conclusion', 'check_run_url')):
        raise GateError('metadata current native read-only role changed')
    _metadata_check(api, prefix, closing_current[0], closing_roles[0], request.head_sha)
    _dispatch_source(api, config, request.repository, source)
    if proof['report']['mode'] == 'native-exact-tree-parent':
        _metadata_inherited_parent(api, config=config, request=request, source=source,
            validator=proof['validator'], names=proof['selected']['suites'], tree=tree, report=proof['report'], now=now)
    elif proof['report']['mode'] == 'native-standalone-ci':
        _metadata_standalone_owners(api, request, source, proof['validator'],
            suite_inputs.load_registry(ROOT / '.github/test-suites.json'), proof['report'], now)
    return {'metadata_authenticated': True, 'original_gate_run': original['id'], 'validation_run': child,
            'original_state': 'success', 'new_dispatches': 0, 'new_execution': False, 'qualification': False}


def metadata_owner(args):
    event = json.loads(args.event.read_bytes(), object_pairs_hook=suite_inputs._unique_object)
    deadline = time.monotonic() + 60
    while True:
        try:
            value = retain_metadata_owner(event, load_config(args.config), GitHubApi())
            break
        except _DispatchRegistrationPending:
            if time.monotonic() >= deadline:
                raise GateError('metadata original registration did not stabilize; no dispatch') from None
            time.sleep(min(2, max(0, deadline - time.monotonic())))
    write_outputs(args.output, value)
    return 0


def _exact_tree_required_owners(api, prefix, parent_pr, before, trusted):
    """Read every current required native owner on the real introducing H."""
    rules = api.json(prefix + '/rules/branches/android-main')
    if type(rules) is not list or len(rules) > 100 or any(type(r) is not dict for r in rules):
        raise EvidenceError('exact-tree parent rules unavailable')
    required = []
    for rule in rules:
        if rule.get('type') == 'required_status_checks':
            parameters = rule.get('parameters', {})
            if parameters.get('strict_required_status_checks_policy') is not True:
                raise EvidenceError('exact-tree parent checks are not strict')
            required.extend(parameters.get('required_status_checks', []))
    paths = {'dependency-release-policy': '.github/workflows/dependency-releases.yml',
        'branch-policy': '.github/workflows/branch-policy.yml',
        'sync-test-reuse': '.github/workflows/sync-test-reuse.yml',
        'repository-checks': '.github/workflows/repository-checks.yml',
        'codeql-security-results': '.github/workflows/codeql.yml'}
    if len(required) != len(paths) or any(type(r) is not dict or r.get('integration_id') != 15368
            or type(r.get('integration_id')) is not int for r in required) \
            or {r.get('context') for r in required} != set(paths):
        raise EvidenceError('exact-tree parent mandatory native contexts differ')
    head = parent_pr['head']['sha']
    checks = _metadata_list(api, prefix + '/commits/' + head + '/check-runs?filter=all&per_page=100', 'check_runs')
    owners = {}
    for name, path in paths.items():
        found = [c for c in checks if c.get('name') == name and c.get('app', {}).get('id') == 15368]
        if len(found) != 1 or (found[0].get('status'), found[0].get('conclusion')) != ('completed', 'success'):
            raise EvidenceError('exact-tree parent required native owner is not uniquely successful')
        check = found[0]
        match = re.fullmatch(r'https://github\.com/noah-l-frank/overte/actions/runs/([1-9][0-9]*)/job/([1-9][0-9]*)',
                            check.get('details_url', ''))
        if match is None:
            raise EvidenceError('exact-tree parent native job URL differs')
        identifier, job_id = map(int, match.groups())
        run = api.json(prefix + '/actions/runs/' + str(identifier))
        attempt = api.json(prefix + '/actions/runs/' + str(identifier) + '/attempts/1')
        fields = {'id':identifier, 'head_sha':head, 'head_branch':parent_pr['head']['ref'],
            'path':path, 'run_attempt':1, 'status':'completed', 'conclusion':'success'}
        for value in (run, attempt):
            if type(value) is not dict or any(type(value.get(k)) is not type(v) or value[k] != v for k,v in fields.items()) \
                    or value.get('event') not in {'pull_request', 'pull_request_target'} \
                    or any(type(value.get(k)) is not dict or type(value[k].get('id')) is not int
                        or (value[k]['id'],value[k].get('full_name')) != (1319052603,'noah-l-frank/overte')
                        for k in ('repository','head_repository')):
                raise EvidenceError('exact-tree parent native source/attempt differs')
        if any(run.get(k) != attempt.get(k) for k in ('workflow_id','check_suite_id','event','run_started_at')):
            raise EvidenceError('exact-tree parent native attempt identity differs')
        registration = api.json(prefix + '/actions/workflows/' + str(run['workflow_id']))
        if (registration.get('id'), registration.get('path'), registration.get('state')) != (run['workflow_id'],path,'active'):
            raise EvidenceError('exact-tree parent native recipe registration differs')
        expected = trusted.get(path)
        legacy = {'mode':'100644','type':'blob','sha':'6229491872ac60ce2149b68eb53b3e67055c354c'}
        if expected is None or before.get(path) != expected and not (name == 'sync-test-reuse' and before.get(path) == legacy):
            raise EvidenceError('exact-tree parent native recipe was not reviewed')
        jobs = _metadata_list(api, prefix + '/actions/runs/' + str(identifier) + '/attempts/1/jobs?per_page=100', 'jobs')
        found_jobs = [j for j in jobs if j.get('id') == job_id and j.get('name') == name]
        if len(found_jobs) != 1 or _metadata_check(api,prefix,run,found_jobs[0],head) != check:
            raise EvidenceError('exact-tree parent native job/App differs')
        owners[name] = {'run':run,'attempt':attempt,'jobs':jobs,'check':check,'registration':registration}
    return {'rules':rules,'checks':checks,'owners':owners}


def native_exact_tree_parent_evidence(api, config, request, now=None):
    """Native runtime entry; the separate read-only proof API grants no E."""
    if os.environ.get('GITHUB_ACTIONS') != 'true' or (request.base,request.parent,request.profile) != (
            'android-vr','android-main','android-vr') or request.repair_paths or not request.changed_paths:
        return None
    try:
        source = _dispatch_checkout_source()
        event = {'repository': api.json('repos/' + request.repository), 'number': request.number,
                 'pull_request': api.json('repos/' + request.repository + '/pulls/' + str(request.number))}
        _native_effective_role(api, event, request.base_sha)
        return verify_exact_tree_parent_evidence(api, config, request, protected_source=source,
            protected_tree=commit_tree(commit(api,request.repository,source)), now=now)
    except (EvidenceError,GateError,ValueError,OSError,KeyError,TypeError,AttributeError,ImportError,
            subprocess.SubprocessError):
        return None


def verify_exact_tree_parent_evidence(api, config, request, *, protected_source, protected_tree, now=None):
    """Only AndroidMain -> VR may inherit actual CI37 on the identical whole T.

    This independently executed schema1 report remains nonreusable data. No
    consumer environment, fingerprints, receipt/E or successful push is made.
    Missing proof before setup retains the mandatory selected execution route.
    """
    if (request.base,request.parent,request.profile) != (
            'android-vr','android-main','android-vr') or request.repair_paths or not request.changed_paths:
        return None
    try:
        now = datetime.now(timezone.utc) if now is None else now
        source = validate_sha(protected_source, 'exact-tree protected source')
        validate_sha(protected_tree, 'exact-tree protected source tree')
        prefix = _dispatch_source(api,config,request.repository,source)
        source_tree,trusted = recursive_tree(api,request.repository,source)
        if source_tree != protected_tree or suite_inputs.full_tree(ROOT,'HEAD') != trusted:
            raise EvidenceError('exact-tree actual reader is not the complete protected source tree')
        _native_parent_controller()  # Authenticate the existing physical import closure, not B/D reuse/E.

        repo = api.json(prefix); current_pr = api.json(prefix + '/pulls/' + str(request.number))
        event = {'repository':repo,'number':request.number,'pull_request':current_pr}
        if classify_event(event,config,api) != request:
            raise EvidenceError('exact-tree current synchronization changed')
        current = commit(api,request.repository,request.merge_sha)
        head = commit(api,request.repository,request.head_sha)
        parent = commit(api,request.repository,request.parent_sha)
        if commit_parents(head) != (request.base_sha,request.parent_sha) \
                or commit_parents(current) != (request.base_sha,request.head_sha) \
                or len(commit_parents(parent)) != 2 or commit_tree(current) != commit_tree(head) \
                or commit_tree(parent) != commit_tree(current):
            raise EvidenceError('exact-tree direct normal/candidate topology differs')
        if branch_sha(api,request.repository,'android-main') != request.parent_sha:
            raise EvidenceError('exact-tree protected parent moved')
        branch = api.json(prefix + '/branches/android-main')
        if branch.get('name') != 'android-main' or branch.get('protected') is not True \
                or branch.get('commit',{}).get('sha') != request.parent_sha:
            raise EvidenceError('exact-tree parent is not the current protected normal')
        rows = api.json(prefix + '/commits/' + request.parent_sha + '/pulls?per_page=100')
        if type(rows) is not list or len(rows) >= 100 or any(type(r) is not dict for r in rows):
            raise EvidenceError('exact-tree normal introducing PR inventory unavailable')
        numbers = [r.get('number') for r in rows]
        if any(type(n) is not int or n <= 0 for n in numbers) or len(set(numbers)) != len(numbers):
            raise EvidenceError('exact-tree normal introducing PR numbers differ')
        # Commit associations can omit merge_commit_sha; only the full native
        # PR detail supplies the actual normal integration identity.
        details = [api.json(prefix + '/pulls/' + str(n)) for n in numbers]
        introduced = [r for r in details if r.get('merge_commit_sha') == request.parent_sha and r.get('base',{}).get('ref') == 'android-main']
        if len(introduced) != 1:
            raise EvidenceError('exact-tree normal introducing PR is ambiguous')
        parent_pr = introduced[0]
        bp,hp = commit_parents(parent)
        if parent_pr.get('state') != 'closed' or parent_pr.get('merged') is not True \
                or parent_pr.get('merge_commit_sha') != request.parent_sha or parent_pr.get('base',{}).get('ref') != 'android-main' \
                or parent_pr.get('head',{}).get('sha') != hp \
                or any((parent_pr.get(k,{}).get('repo',{}).get('id'),parent_pr.get(k,{}).get('repo',{}).get('full_name')) != (
                    1319052603,'noah-l-frank/overte') for k in ('base','head')):
            raise EvidenceError('exact-tree introducing native PR differs')
        if commit_parents(commit(api,request.repository,hp)) != (bp,source):
            raise EvidenceError('exact-tree parent was not the current source reconciliation')
        tree,candidate = recursive_tree(api,request.repository,request.merge_sha)
        parent_tree,parent_inputs = recursive_tree(api,request.repository,request.parent_sha)
        _,before = recursive_tree(api,request.repository,bp)
        _,child_before = recursive_tree(api,request.repository,request.base_sha)
        profile = {'mode':'100644','type':'blob','sha':suite_inputs._AFFECTED_TARGET_PROFILES['android-main']}
        if tree != parent_tree or candidate != parent_inputs \
                or any(t.get('tests/platform-profile.json') != profile for t in (candidate,before,child_before)) \
                or any(e['type'] != 'blob' or e['mode'] not in {'100644','100755'} for e in candidate.values()) \
                or any(t.get('.github/test-suites.json') != trusted.get('.github/test-suites.json') for t in (before,candidate)):
            raise EvidenceError('exact-tree complete inputs/profile/registry differ')
        host = package_checks.load('sync_identical_tree_host','tools/repository-checks/host_selection.py')
        registry = suite_inputs.load_registry(ROOT/'.github/test-suites.json')
        names = json.loads((ROOT/'.github/ci37-runtime.json').read_bytes())['suites']
        if len(names) != 37 or len(set(names)) != 37 or any(registry['suites'][n]['scope'] != 'content' for n in names):
            raise EvidenceError('exact-tree ordered content-scoped CI37 differs')
        parent_paths = tuple(sorted(p for p in before.keys() | candidate.keys() if before.get(p) != candidate.get(p)))
        original_request = SyncRequest(request.repository,request.repository_id,parent_pr['number'],'android-main',bp,
            parent_pr['head']['ref'],hp,request.head_repository_id,request.parent_sha,'reconciliation','main',source,
            'android-family',parent_paths,parent_paths)
        for target,base,paths in (('android-main',before,parent_paths),('android-vr',child_before,request.changed_paths)):
            selected = host.select(candidate,list(paths),True,base_tree=base,trusted_tree=trusted,
                candidate_root=ROOT,trusted_root=ROOT,target=target)
            if selected.get('suites') != names or selected.get('full_host') is not False or selected.get('include_platform') is not False:
                raise EvidenceError('exact-tree current and original commands are not independent CI37')
        packages = package_checks.select(list(request.changed_paths),True,include_browser=True)
        if packages['package_set'] or packages['tool_projects']:
            raise EvidenceError('exact-tree package/product owner is not covered')
        native = package_checks.load('sync_identical_tree_native','tools/native-tests/check.py')
        if native.plan(list(request.changed_paths),True)['mode'] != 'skip':
            raise EvidenceError('exact-tree native product owner is not covered')
        owners = _exact_tree_required_owners(api,prefix,parent_pr,before,trusted)
        native_owner = owners['owners']['sync-test-reuse']
        original,attempt = _metadata_gate_run(api,prefix,native_owner['run']['id'],original_request,normal_parent=request.parent_sha)
        if original != native_owner['run'] or attempt != native_owner['attempt']:
            raise EvidenceError('exact-tree original gate changed')
        proof = _completed_sync_report(api,prefix,original,native_owner['check'],original_request,source,
            before,candidate,trusted,tree,now,normal_parent=request.parent_sha)
        report = proof['report']; completed = parse_time(report['completed_at'],'original CI completion')
        expires = min(parse_time(proof['item']['expires_at'],'original artifact expiry'),
            completed + timedelta(hours=int(config['evidence_max_age_hours'])))
        if not completed < now < expires or completed >= parse_time(parent_pr['merged_at'],'normal integration') + timedelta(seconds=1):
            raise EvidenceError('exact-tree original execution is expired or was not premerge')
        _dispatch_native(api,prefix,proof['run'],source,proof['correlation'],proof['identity'])
        if _exact_tree_required_owners(api,prefix,parent_pr,before,trusted) != owners \
                or _metadata_gate_run(api,prefix,original['id'],original_request,normal_parent=request.parent_sha) != (original,attempt) \
                or _metadata_list(api,prefix+'/actions/runs/'+str(proof['child'])+'/artifacts?per_page=100','artifacts') != proof['artifacts'] \
                or api.json(prefix+'/check-runs/'+str(proof['validator_check']['id'])) != proof['validator_check'] \
                or api.json(prefix+'/actions/runs/'+str(proof['child'])) != proof['run'] \
                or api.json(prefix+'/pulls/'+str(parent_pr['number'])) != parent_pr \
                or api.json(prefix+'/pulls/'+str(request.number)) != current_pr \
                or api.json(prefix+'/commits/'+request.parent_sha+'/pulls?per_page=100') != rows \
                or classify_event(event,config,api) != request or branch_sha(api,request.repository,'android-main') != request.parent_sha \
                or suite_inputs.full_tree(ROOT,'HEAD') != trusted:
            raise EvidenceError('exact-tree native/source/normal closing bookend changed')
        _dispatch_source(api,config,request.repository,source)
        if report['mode'] == 'native-standalone-ci':
            _metadata_standalone_owners(api, replace(original_request,
                merge_sha=report['candidate']['merge_commit']), source, proof['validator'], registry,
                report, now, normal_parent=request.parent_sha)
        return NativeExactTreeParentEvidence({'kind':'original-sync-identical-android-tree-v1',
            'qualification':False,'reusable':False,'source':source,'parent_branch':request.parent,
            'parent_commit':request.parent_sha,'parent_tree':tree,'candidate_inputs':candidate,
            'requested_suites':names,'original_commit':report['candidate']['merge_commit'],
            'qualified_at':report['completed_at'],'expires_at':expires.isoformat().replace('+00:00','Z'),
            'original_proof':{'parent_pr':parent_pr['number'],'gate_run_id':original['id'],
                'run_id':proof['child'],'attempt':1,'artifact_id':proof['item']['id'],
                'artifact_digest':proof['item']['digest'],'receipt_digest':report['receipt_digest']},
            'original_report':report})
    except (EvidenceError,GateError,ValueError,OSError,KeyError,TypeError,AttributeError,ImportError,
            subprocess.SubprocessError,zipfile.BadZipFile,ET.ParseError):
        return None


def inspect(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    event = json.loads(args.event.read_text(encoding="utf-8"))
    api = GitHubApi()
    context = (effective_pr_context(event, api) if os.environ.get('GITHUB_ACTIONS') == 'true'
               and os.environ.get('GITHUB_EVENT_NAME') == 'pull_request_target' else None)
    if context is None:
        validate_required_codeql_workflow(event, api)
        request = classify_event(event, config, api)
    else:
        validate_required_codeql_workflow(event, api, pr_context=context)
        request = classify_event(event, config, api, pr_context=context)
    if request is None:
        write_outputs(args.output, {"classification": "ordinary", "mode": "ordinary"})
        return 0
    if pure_metadata_event(event, os.environ.get('GITHUB_EVENT_NAME')):
        raise GateError('pure synchronization metadata edit requires the authenticated noncanonical retention role; no dispatch')
    mode, reason, evidence_run = "reuse", "exact qualification accepted", ""
    if request.repair_paths:
        mode, reason = "fallback", "attested product repair requires complete fallback"
    elif request.profile == "documentation":
        reason = "documentation-only delta; no executable inputs require qualification"
    elif request.profile == "tool-dependencies":
        reason = "bounded tool manifest delta; affected tool checks required"
    else:
        identical = native_exact_tree_parent_evidence(api, config, request)
        current = native_pr_evidence(api, config, request) if identical is None else None
        if identical is not None:
            mode, reason, evidence_run = 'reuse', 'original native CI37 on the identical Android parent tree; differential remains required', str(identical['original_proof']['run_id'])
        elif current is not None:
            mode, reason, evidence_run = 'reuse', 'completed original PR owner accepted; Sync keeps its differential checks', str(current['original_proof']['run_id'])
        else:
            try:
                evidence = verify_evidence(api, config, request)
                plan = evidence["candidate_plan"]
                if isinstance(evidence, NativeParentEvidence):
                    evidence_run = str(evidence['original_proof']['run_id'])
                    reason = (f"original native parent proofs accepted; {len(plan['reused'])} source matches, "
                              f"{len(plan['required'])} suites require candidate execution; original proof rechecked in validation")
                else:
                    evidence_run = str(evidence["workflow"]["run_id"])
                    reason = (f"exact parent suite proofs accepted; {len(plan['reused'])} source matches, "
                              f"{len(plan['required'])} suites require candidate execution; runtime rechecked in validation")
            except EvidenceError as error:
                mode, reason = "fallback", str(error).replace("\n", " ")
    values = {
        "classification": request.classification,
        "mode": mode,
        "profile": request.profile,
        "repository": request.repository,
        "pr": request.number,
        "base": request.base,
        "base_sha": request.base_sha,
        "head_sha": request.head_sha,
        "parent": request.parent,
        "parent_sha": request.parent_sha,
        "merge_sha": request.merge_sha,
        "evidence_run_id": evidence_run,
        "reason": reason,
    }
    write_outputs(args.output, values)
    return 0


def _dispatch_checkout_source() -> str:
    """Bind the actual default-branch checkout, not the parent run's PR head."""
    try:
        result = subprocess.run(
            ["git", "--no-optional-locks", "--no-replace-objects", "rev-parse", "--verify", "HEAD^{commit}"],
            cwd=ROOT, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as error:
        raise GateError("trusted dispatch checkout source is unavailable") from error
    return validate_sha(result.stdout.strip(), "trusted dispatch checkout source")


def _dispatch_source(api, config, repository, checkout_source):
    if (repository != "noah-l-frank/overte" or config.get("repository") != repository
            or config.get("repository_id") != 1319052603
            or config.get("trusted_actions_app_id") != 15368
            or config.get("validation_workflow") != "sync-validation.yml"):
        raise GateError("validation dispatch is outside the fixed native configuration")
    prefix = "repos/" + repository
    repo = api.json(prefix)
    branch = api.json(prefix + "/branches/main")
    workflow = api.json(prefix + "/actions/workflows/sync-validation.yml")
    if (not isinstance(repo, dict) or repo.get("id") != 1319052603
            or repo.get("full_name") != repository or repo.get("default_branch") != "main"
            or not isinstance(branch, dict) or branch.get("name") != "main" or branch.get("protected") is not True
            or not isinstance(branch.get("commit"), dict) or branch["commit"].get("sha") != checkout_source
            or not isinstance(workflow, dict) or workflow.get("id") != 350930895
            or workflow.get("path") != ".github/workflows/sync-validation.yml"
            or workflow.get("name") != "Sync validation" or workflow.get("state") != "active"):
        raise GateError("validation dispatch repository, protected source or workflow changed")
    _callback_sync_recipe()  # Complete ordinary source tuple must be known before the only POST.
    return prefix


CALLBACK_SYNC_RECIPE_ENTRIES = ({'mode': '100644', 'type': 'blob', 'sha': 'ccc75d37c4f8b5012299bf864bf48dd45ead389b'}, {'mode': '100644', 'type': 'blob', 'sha': '747bd6424d1e9b533ae35a81b524ceefc06b286b'})


def _callback_sync_recipe():
    """Classify only an ordinary, complete trusted-catalog Sync recipe."""
    try:
        tree = suite_inputs.full_tree(ROOT, 'HEAD')
        generation = package_checks.validate_tree_wiring(tree)
        rows = [row for row in package_checks.workflow_generations() if row['name'] == generation]
        if len(rows) != 1:
            raise ValueError('trusted source generation is not unique')
        entry = rows[0]['workflows']['.github/workflows/sync-validation.yml']
        if tree.get('.github/workflows/sync-validation.yml') != entry:
            raise ValueError('trusted complete Sync recipe changed')
    except (ValueError, KeyError, TypeError, OSError, subprocess.SubprocessError) as error:
        raise GateError('native synchronization workflow has no exact complete trusted recipe') from error
    return entry in CALLBACK_SYNC_RECIPE_ENTRIES


def _dispatch_terminal_roles(api, prefix, run, source):
    """Validator success is mandatory; notifier result is administrative data."""
    response = api.json(f"{prefix}/actions/runs/{run['id']}/attempts/1/jobs?per_page=100")
    if (not isinstance(response, dict) or type(response.get('total_count')) is not int
            or response['total_count'] != 2 or not isinstance(response.get('jobs'), list)
            or len(response['jobs']) != 2 or not all(isinstance(job, dict) for job in response['jobs'])
            or {job.get('name') for job in response['jobs']} != {
                'Validate exact synchronization', 'Notify completed synchronization cleanup'}
            or len({job.get('id') for job in response['jobs']}) != 2):
        raise GateError('validation callback generation requires its exact two native roles')
    roles = {}
    for job in response['jobs']:
        identifier = job.get('id')
        if (type(identifier) is not int or identifier <= 0
                or type(job.get('run_id')) is not int or job['run_id'] != run['id']
                or type(job.get('run_attempt')) is not int or job['run_attempt'] != 1
                or job.get('head_sha') != source or job.get('status') != 'completed'
                or job.get('url') != f'{prefix.replace("repos/", "https://api.github.com/repos/", 1)}/actions/jobs/{identifier}'
                or job.get('html_url') != f'https://github.com/noah-l-frank/overte/actions/runs/{run["id"]}/job/{identifier}'):
            raise GateError('validation callback native job source or identity changed')
        check_url = job.get('check_run_url')
        match = (re.fullmatch(r'https://api\.github\.com/repos/noah-l-frank/overte/check-runs/([1-9][0-9]*)', check_url)
                 if type(check_url) is str else None)
        if match is None:
            raise GateError('validation callback native job check URL changed')
        check = api.json(prefix + '/check-runs/' + match[1])
        if (not isinstance(check, dict) or type(check.get('id')) is not int
                or check['id'] != int(match[1]) or check['id'] != identifier
                or check.get('head_sha') != source
                or check.get('name') != job['name'] or check.get('status') != 'completed'
                or check.get('conclusion') != job.get('conclusion')
                or not isinstance(check.get('app'), dict) or type(check['app'].get('id')) is not int
                or check['app']['id'] != 15368
                or not isinstance(check.get('check_suite'), dict)
                or type(check['check_suite'].get('id')) is not int
                or check['check_suite']['id'] != run['check_suite_id']
                or check.get('details_url') != job['html_url']
                or not {'started_at','completed_at'} <= set(job) & set(check)
                or check.get('started_at') != job.get('started_at')
                or check.get('completed_at') != job.get('completed_at')):
            raise GateError('validation callback native job check or App changed')
        not_started = (job['name'] == 'Notify completed synchronization cleanup'
            and job.get('conclusion') in {'failure','cancelled','skipped','timed_out','startup_failure'}
            and job.get('started_at') is None and job.get('steps') == [])
        try:
            if not_started:
                if job.get('completed_at') is not None:
                    parse_time(job['completed_at'], 'unstarted notification completion')
            elif parse_time(job.get('started_at'), 'native callback job start') > parse_time(
                    job.get('completed_at'), 'native callback job completion'):
                raise EvidenceError('native callback job chronology is reversed')
        except EvidenceError as error:
            raise GateError('validation callback native job chronology is invalid') from error
        roles[job['name']] = job
    validator = roles['Validate exact synchronization']
    if validator.get('conclusion') != 'success':
        raise GateError('validation workload did not succeed')
    notifier = roles['Notify completed synchronization cleanup']
    if notifier.get('conclusion') not in {
            'success', 'failure', 'cancelled', 'skipped', 'timed_out', 'neutral', 'action_required', 'startup_failure'}:
        raise GateError('validation cleanup notification native result is unknown')
    steps = notifier.get('steps')
    if not isinstance(steps, list) or not all(isinstance(step, dict) for step in steps):
        raise GateError('validation cleanup notification native steps are unknown')
    dispatch = [step for step in steps if step.get('name') == 'Dispatch exact synchronization completion']
    if len(dispatch) > 1 or any(step.get('status') != 'completed'
            or step.get('conclusion') not in {'success', 'failure', 'cancelled', 'skipped',
                'timed_out', 'neutral', 'action_required', 'startup_failure'} for step in dispatch):
        raise GateError('validation cleanup notification native dispatch step is ambiguous')
    if not dispatch and notifier['conclusion'] not in {'failure', 'cancelled', 'timed_out', 'startup_failure', 'skipped'}:
        raise GateError('successful validation cleanup notifier omitted its actual dispatch step')
    # No cleanup conclusion or receipt grants test/qualification authority.
    # A tolerated administrative failure stays explicit and observable.
    value = {'run_id': run['id'], 'job_id': notifier['id'], 'status': notifier['status'],
        'conclusion': notifier['conclusion'], 'qualification': False,
        'execution_state': 'not-started' if notifier.get('started_at') is None else 'executed',
        'dispatch_step': ({key: dispatch[0].get(key) for key in ('name', 'status', 'conclusion')}
                          if dispatch else None)}
    print('sync_cleanup_notification=' + json.dumps(value, sort_keys=True, separators=(',', ':')))
    return value


def _dispatch_run(value, run_id, source, correlation, *, allow_pending=False, endpoint="run", known_suite_id=None):
    prefix = "https://api.github.com/repos/noah-l-frank/overte"
    invalid, missing = [], []
    if not isinstance(value, dict):
        raise GateError(f"validation run identity or state differs from its own dispatch (endpoint={endpoint}; fields=response)")
    anchors = {"id": run_id, "url": prefix + "/actions/runs/" + str(run_id),
               "html_url": "https://github.com/noah-l-frank/overte/actions/runs/" + str(run_id)}
    for key, expected in anchors.items():
        if type(value.get(key)) is not type(expected) or value[key] != expected:
            invalid.append(key)
    pending = (value.get("status") in ("queued", "in_progress", "waiting", "pending", "requested")
               and value.get("conclusion") is None)
    if not pending and value.get("status") != "completed":
        invalid.append("status/conclusion")
    expected = {"workflow_id": 350930895, "run_attempt": 1,
                "path": ".github/workflows/sync-validation.yml", "event": "workflow_dispatch",
                "head_branch": "main", "head_sha": source, "display_title": "Sync validation " + correlation}
    for key, wanted in expected.items():
        # GitHub initially exposes the workflow name before expanding run-name.
        # Only this exact observed placeholder may wait; foreign titles remain conflicts.
        if (key == "display_title" and allow_pending and pending
                and type(value.get(key)) is str and value[key] == "Sync validation"):
            missing.append(key)
        elif value.get(key) is None:
            missing.append(key)
        elif type(value[key]) is not type(wanted) or value[key] != wanted:
            invalid.append(key)
    if value.get("check_suite_id") is None:
        missing.append("check_suite_id")
    elif type(value["check_suite_id"]) is not int or value["check_suite_id"] <= 0:
        invalid.append("check_suite_id")
    elif known_suite_id is not None and value["check_suite_id"] != known_suite_id:
        raise GateError(f"validation run identity changed (endpoint={endpoint}; fields=check_suite_id)")
    for key in ("repository", "head_repository"):
        repository = value.get(key)
        if repository is None:
            missing.append(key)
        elif not isinstance(repository, dict):
            invalid.append(key)
        else:
            for field, wanted in (("id", 1319052603), ("full_name", "noah-l-frank/overte")):
                if repository.get(field) is None:
                    missing.append(key + "." + field)
                elif type(repository[field]) is not type(wanted) or repository[field] != wanted:
                    invalid.append(key + "." + field)
    if invalid or missing and not (allow_pending and pending):
        fields = ",".join(sorted(set(invalid + missing)))
        raise GateError(f"validation run identity or state differs from its own dispatch (endpoint={endpoint}; fields={fields})")
    if missing:
        fields = ",".join(sorted(missing))
        raise _DispatchRegistrationPending(f"validation registration incomplete (endpoint={endpoint}; fields={fields})", value.get("check_suite_id"))
    return tuple(value[key] for key in ("id", "workflow_id", "check_suite_id", "path", "event",
                                       "head_branch", "head_sha", "run_attempt", "display_title", "url", "html_url"))


def _dispatch_native(api, prefix, run, source, correlation, identity, *, allow_pending=False, deadline=None):
    run_id = run["id"]
    attempt = api.json(f"{prefix}/actions/runs/{run_id}/attempts/1")
    if deadline is not None and time.monotonic() >= deadline:
        raise GateError("validation initial registration did not complete before timeout (endpoint=attempts/1; fields=registration_deadline)")
    current = _dispatch_run(attempt, run_id, source, correlation,
                            allow_pending=allow_pending, endpoint="attempts/1", known_suite_id=identity[2])
    if current != identity:
        keys = ("id", "workflow_id", "check_suite_id", "path", "event", "head_branch", "head_sha",
                "run_attempt", "display_title", "url", "html_url")
        fields = ",".join(key for key, before, after in zip(keys, identity, current) if before != after)
        raise GateError(f"validation native attempt identity changed (endpoint=attempts/1; fields={fields})")
    suite = api.json(f"{prefix}/check-suites/{run['check_suite_id']}")
    if deadline is not None and time.monotonic() >= deadline:
        raise GateError("validation initial registration did not complete before timeout (endpoint=check-suite; fields=registration_deadline)")
    invalid, missing = [], []
    if not isinstance(suite, dict):
        raise GateError("validation native suite or App differs (endpoint=check-suite; fields=response)")
    for key, wanted in (("id", run["check_suite_id"]), ("head_sha", source)):
        if suite.get(key) is None:
            missing.append(key)
        elif type(suite[key]) is not type(wanted) or suite[key] != wanted:
            invalid.append(key)
    for key, fields in (("app", (("id", 15368),)),
                        ("repository", (("id", 1319052603), ("full_name", "noah-l-frank/overte")))):
        value = suite.get(key)
        if value is None:
            missing.append(key)
        elif not isinstance(value, dict):
            invalid.append(key)
        else:
            for field, wanted in fields:
                if value.get(field) is None:
                    missing.append(key + "." + field)
                elif type(value[field]) is not type(wanted) or value[field] != wanted:
                    invalid.append(key + "." + field)
    pending = run.get("status") in ("queued", "in_progress", "waiting", "pending", "requested")
    if invalid or missing and not (allow_pending and pending):
        fields = ",".join(sorted(set(invalid + missing)))
        raise GateError(f"validation native suite or App differs (endpoint=check-suite; fields={fields})")
    if missing:
        fields = ",".join(sorted(missing))
        raise _DispatchRegistrationPending(f"validation registration incomplete (endpoint=check-suite; fields={fields})", run["check_suite_id"])
    if run["status"] == "completed" and (attempt.get("status"), attempt.get("conclusion")) != ("completed", "success"):
        raise GateError("validation terminal native attempt did not succeed (endpoint=attempts/1; fields=status/conclusion)")
    if run['status'] == 'completed' and _callback_sync_recipe():
        _dispatch_terminal_roles(api, prefix, run, source)


def dispatch_and_wait(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    gate_run_attempt = args.gate_run_attempt
    if gate_run_attempt is None:
        # Older workflow definitions still load this trusted code from main.
        try:
            gate_run_attempt = int(os.environ["GITHUB_RUN_ATTEMPT"])
        except (KeyError, ValueError) as error:
            raise GateError("gate run attempt must be an integer argument or GITHUB_RUN_ATTEMPT") from error
    if args.gate_run_id <= 0 or gate_run_attempt <= 0:
        raise GateError("gate run ID and attempt must be positive")
    api = GitHubApi()
    source = _dispatch_checkout_source()
    prefix = _dispatch_source(api, config, args.repository, source)
    # The PRT parent can still be running at PR H; the child executes main D.
    correlation = f"gate-{args.gate_run_id}-attempt-{gate_run_attempt}"
    fields = {
        "ref": "main",
        "inputs[correlation]": correlation,
        "inputs[mode]": args.mode,
        "inputs[profile]": args.profile,
        "inputs[pull_request]": str(args.pull_request),
        "inputs[expected_base_sha]": args.base_sha,
        "inputs[expected_head_sha]": args.head_sha,
        "inputs[expected_merge_sha]": args.merge_sha,
    }
    dispatched = api.json(
        f"{prefix}/actions/workflows/{config['validation_workflow']}/dispatches",
        method="POST", fields=fields, dispatch_details=True,
    )
    if not isinstance(dispatched, dict) or type(dispatched.get("workflow_run_id")) is not int or dispatched["workflow_run_id"] <= 0:
        raise GateError("validation dispatch did not return a positive run ID; it must not be redispatched")
    run_id = dispatched["workflow_run_id"]
    run_endpoint = f"{prefix}/actions/runs/{run_id}"
    html_url = f"https://github.com/{args.repository}/actions/runs/{run_id}"
    if (dispatched.get("run_url") != "https://api.github.com/" + run_endpoint
            or dispatched.get("html_url") != html_url):
        raise GateError("validation dispatch returned foreign or malformed run URLs")
    deadline = time.monotonic() + args.timeout
    registration_deadline = min(deadline, time.monotonic() + 30)
    identity, observed_identity, known_suite_id, registration_error = None, None, None, None
    while time.monotonic() < deadline:
        if identity is None and registration_error is not None and time.monotonic() >= registration_deadline:
            raise GateError("validation initial registration did not complete before timeout: " + registration_error)
        run = api.json(run_endpoint)
        if time.monotonic() >= deadline:
            raise GateError("validation run did not reach a terminal success before timeout (endpoint=run; fields=deadline)")
        if identity is None and time.monotonic() >= registration_deadline:
            raise GateError("validation initial registration did not complete before timeout (endpoint=run; fields=registration_deadline)")
        native_checked = False
        try:
            current = _dispatch_run(run, run_id, source, correlation, allow_pending=identity is None,
                                    endpoint="run", known_suite_id=known_suite_id)
            if observed_identity is None:
                observed_identity = current
            elif current != observed_identity:
                raise GateError("validation run identity changed during monitoring (endpoint=run; fields=check_suite_id)")
            known_suite_id = current[2]
            if identity is None:
                if run["status"] == "completed" and run.get("conclusion") != "success":
                    raise GateError(f"{args.mode} validation did not succeed")
                _dispatch_native(api, prefix, run, source, correlation, current,
                                 allow_pending=run["status"] != "completed", deadline=registration_deadline)
                if time.monotonic() >= registration_deadline or time.monotonic() >= deadline:
                    raise GateError("validation initial registration did not complete before timeout (endpoint=native; fields=registration_deadline)")
                identity = current
                native_checked = True
            elif current != identity:
                raise GateError("validation run identity changed during monitoring (endpoint=run; fields=check_suite_id)")
        except _DispatchRegistrationPending as error:
            # A supplied suite identity is immutable even before all native metadata is ready.
            if error.check_suite_id is not None:
                if known_suite_id is not None and error.check_suite_id != known_suite_id:
                    raise GateError("validation run identity changed during registration (endpoint=run; fields=check_suite_id)") from error
                known_suite_id = error.check_suite_id
            registration_error = str(error)
            remaining = min(deadline, registration_deadline) - time.monotonic()
            if remaining <= 0:
                raise GateError("validation initial registration did not complete before timeout: " + registration_error) from error
            time.sleep(min(2, remaining))
            continue
        if run["status"] == "completed":
            if run.get("conclusion") != "success":
                raise GateError(f"{args.mode} validation did not succeed")
            if not native_checked:
                _dispatch_native(api, prefix, run, source, correlation, identity)
            if _dispatch_checkout_source() != source:
                raise GateError("trusted dispatch checkout source changed")
            _dispatch_source(api, config, args.repository, source)
            final = api.json(run_endpoint)
            if (_dispatch_run(final, run_id, source, correlation, endpoint="terminal run", known_suite_id=known_suite_id) != identity
                    or (final.get("status"), final.get("conclusion")) != ("completed", "success")):
                raise GateError("validation terminal run changed during native source bookends")
            if time.monotonic() >= deadline:
                raise GateError("validation run did not reach a terminal success before timeout (endpoint=terminal run; fields=deadline)")
            write_outputs(args.output, {"validation_run_id": run_id, "validation_url": html_url})
            return 0
        time.sleep(10)
    if identity is None and registration_error is not None:
        raise GateError("validation initial registration did not complete before timeout: " + registration_error)
    raise GateError("validation run did not reach a terminal success before timeout")


def cancel_redundant(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    wanted = set(config["redundant_pull_request_workflows"])
    if not wanted:
        # Older descendant workflows still call this trusted default-branch
        # helper with --window 60. Modern routing owns the selected executions;
        # an empty retired inventory needs neither API calls nor a polling wait.
        print("cancelled_redundant_runs=0")
        return 0
    api = GitHubApi()
    cancelled: set[int] = set()
    deadline = time.monotonic() + args.window
    while time.monotonic() < deadline:
        runs = api_list(
            api,
            f"repos/{args.repository}/actions/runs?event=pull_request&head_sha={args.head_sha}&per_page=100",
            "workflow_runs",
        )
        for run in runs:
            path = str(run.get("path", "")).rsplit("/", 1)[-1]
            pull_numbers = {item.get("number") for item in run.get("pull_requests", [])}
            if path not in wanted or args.pull_request not in pull_numbers:
                continue
            if run.get("status") in ("queued", "in_progress", "waiting", "pending") and run["id"] not in cancelled:
                try:
                    api.json(f"repos/{args.repository}/actions/runs/{run['id']}/cancel", method="POST")
                    cancelled.add(run["id"])
                except GateError as error:
                    print(f"warning: redundant run {run['id']} could not be cancelled: {error}", file=sys.stderr)
        time.sleep(5)
    print(f"cancelled_redundant_runs={len(cancelled)}")
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    sub = result.add_subparsers(dest="command", required=True)
    for command, handler in (('classify-metadata', classify_metadata), ('retain-metadata-owner', metadata_owner)):
        metadata = sub.add_parser(command)
        metadata.add_argument('--event', type=Path, required=True)
        metadata.add_argument('--output', type=Path)
        metadata.set_defaults(handler=handler)
    inspect_parser = sub.add_parser("inspect")
    inspect_parser.add_argument("--event", type=Path, required=True)
    inspect_parser.add_argument("--output", type=Path)
    inspect_parser.set_defaults(handler=inspect)
    dispatch = sub.add_parser("dispatch-and-wait")
    dispatch.add_argument("--repository", required=True)
    dispatch.add_argument("--pull-request", type=int, required=True)
    dispatch.add_argument("--mode", choices=("reuse", "fallback"), required=True)
    dispatch.add_argument("--profile", required=True)
    dispatch.add_argument("--base-sha", required=True)
    dispatch.add_argument("--head-sha", required=True)
    dispatch.add_argument("--merge-sha", required=True)
    dispatch.add_argument("--gate-run-id", type=int, required=True)
    dispatch.add_argument("--gate-run-attempt", type=int,
                          help="gate attempt; defaults to GITHUB_RUN_ATTEMPT when omitted")
    dispatch.add_argument("--timeout", type=int, default=1800)
    dispatch.add_argument("--output", type=Path)
    dispatch.set_defaults(handler=dispatch_and_wait)
    cancel = sub.add_parser("cancel-redundant")
    cancel.add_argument("--repository", required=True)
    cancel.add_argument("--pull-request", type=int, required=True)
    cancel.add_argument("--head-sha", required=True)
    cancel.add_argument("--window", type=int, default=60)
    cancel.set_defaults(handler=cancel_redundant)
    return result


def main() -> int:
    args = parser().parse_args()
    try:
        return args.handler(args)
    except (GateError, OSError, json.JSONDecodeError) as error:
        print(f"sync gate error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
