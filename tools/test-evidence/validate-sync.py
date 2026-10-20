#!/usr/bin/env python3
"""Consume exact-parent proofs against the actual isolated candidate runtime."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import xml.etree.ElementTree as ET

sys.dont_write_bytecode = True

import execution
import inputs
import runtime


ROOT = Path(__file__).resolve().parents[2]
PRODUCER = "overte-trusted-sync-validation-v1"
CI_EXECUTION_PRODUCER = "overte-trusted-sync-ci-execution-v1"
STANDALONE_CI_COMMANDS = {
    'documentation-contracts': ['python', 'tests/documentation-test.py'],
    'documentation': ['python', 'tests/check-documentation.py', '--all'],
    'policy-consistency': ['python', 'tools/repository-policy/check.py'],
    'workflow-contracts': ['python', 'tests/workflow-contract-test.py'],
}
_CANDIDATE_PRIVATE_ENVIRONMENT = (
    "GH_TOKEN", "GITHUB_TOKEN", "GITHUB_ENV", "GITHUB_OUTPUT", "GITHUB_PATH", "GITHUB_STATE",
    "GITHUB_STEP_SUMMARY", "ACTIONS_RUNTIME_TOKEN", "ACTIONS_ID_TOKEN_REQUEST_TOKEN",
    "ACTIONS_ID_TOKEN_REQUEST_URL", "ACTIONS_RUNTIME_URL", "ACTIONS_RESULTS_URL",
)


class ValidationError(ValueError):
    """The isolated candidate does not establish a complete current result."""


class NativeStandaloneCIProof(dict):
    """Same-PR command coverage from native jobs, never runtime/E authority."""


class StandalonePending(ValidationError):
    """Only a still-pending original owner may be polled before execution."""


def _standalone_ci_names(selection, registry):
    names = json.loads((ROOT / '.github/ci37-runtime.json').read_bytes())['suites']
    if selection.get('lane') != 'affected-ci' or selection.get('requested_mode') != 'fallback' \
            or selection.get('standalone_ci_schedule') is not True \
            or selection.get('suites') != names or len(names) != len(set(names)) \
            or len(names) != 37 or selection.get('full_host') is not False \
            or selection.get('external_package_set') != [] \
            or any(registry['suites'].get(name, {}).get('command') != command
                   for name, command in STANDALONE_CI_COMMANDS.items()):
        return []
    return [name for name in names if name in STANDALONE_CI_COMMANDS]


def verify_standalone_ci_owners(api, gate, request, registry, selection, *, now=None, normal_parent=None,
                                protected_source=None, protected_tree=None, observation_clock=None):
    """Verify four completed original commands without qualifying an environment.

    Only an independently selected CI37 fallback may use this finite form.
    Missing, pending or invalid native facts raise before any candidate command;
    callers must not catch those errors and execute these four commands again.
    """
    names = _standalone_ci_names(selection, registry)
    if len(names) != 4 or request.repair_paths:
        raise ValidationError('standalone native commands require the exact CI37 fallback')
    now = datetime.now(timezone.utc) if now is None else now
    if observation_clock is None:
        observation_clock = lambda: datetime.now(timezone.utc)
    config = gate.load_config()
    if request.base not in config['edges'] or config['edges'][request.base]['parent'] != request.parent:
        raise ValidationError('standalone commands are outside the protected synchronization edges')
    source = gate._dispatch_checkout_source() if protected_source is None else gate.validate_sha(
        protected_source, 'standalone protected source')
    prefix = gate._dispatch_source(api, config, request.repository, source)
    # Only these content-addressed Git objects are immutable. Mutable native,
    # registration, PR, branch and check endpoints always bypass this local memo.
    immutable, trees = {}, set()
    commits = {prefix + '/git/commits/' + revision
        for revision in (source, request.base_sha, request.merge_sha, normal_parent) if revision is not None}
    class GitObjects:
        def json(self, endpoint):
            cached = endpoint in commits or endpoint in trees
            if not cached:
                raise ValidationError('standalone immutable reader received a mutable endpoint')
            if endpoint not in immutable:
                immutable[endpoint] = api.json(endpoint)
                if endpoint in commits:
                    sha = gate.validate_sha(immutable[endpoint]['tree']['sha'], 'standalone immutable tree')
                    trees.add(prefix + '/git/trees/' + sha + '?recursive=1')
            return json.loads(json.dumps(immutable[endpoint]))
    git_objects = GitObjects()
    def inventory(revision):
        tree_sha, entries = gate.recursive_tree(git_objects, request.repository, revision)
        # The API reader retains the validated redundant path member; the local
        # immutable Git inventory uses the path only as its dictionary key.
        return tree_sha, {path: {key: entry[key] for key in ('mode', 'type', 'sha')}
                          for path, entry in entries.items()}
    source_tree, trusted = inventory(source)
    if inputs.full_tree(ROOT, 'HEAD') != trusted or protected_tree is not None and source_tree != protected_tree:
        raise ValidationError('standalone reader differs from the actual protected default')
    for path in ('tools/test-evidence/validate-sync.py', 'tools/sync-test-reuse/gate.py',
                 '.github/test-suites.json', '.github/ci37-runtime.json'):
        local = ROOT / path
        if not local.is_file() or local.resolve(strict=True) != local or local.stat().st_mode & 0o111 \
                or local.stat().st_size > 1_000_000:
            raise ValidationError('standalone physical controller/registry is not ordinary')
        raw = local.read_bytes()
        entry = {'mode': '100644', 'type': 'blob',
            'sha': hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()}
        if trusted.get(path) != entry:
            raise ValidationError('standalone physical controller/registry differs from protected source')
    controller = gate._native_parent_controller()  # Physical imports; no B/D reuse admission.
    _, before = inventory(request.base_sha)
    tree, candidate = inventory(request.merge_sha)
    if (selection.get('candidate'), selection.get('tree')) != (request.merge_sha, tree):
        raise ValidationError('standalone command coverage differs from the selected actual M/tree')
    if registry != json.loads((ROOT / '.github/test-suites.json').read_bytes()) \
            or any(snapshot.get('.github/test-suites.json') != trusted['.github/test-suites.json']
                   for snapshot in (before, candidate)):
        raise ValidationError('standalone command registry is not the exact protected inventory')
    recipes = {
        '.github/workflows/repository-checks.yml': '22fe0d6d39d120f800099136d7d1ab5280d80b41',
        '.github/workflows/documentation-checks.yml': 'a86e36287a315eed7bbadf366f923966a04bd806',
    }
    for path, sha in recipes.items():
        expected = {'mode': '100644', 'type': 'blob', 'sha': sha}
        if any(snapshot.get(path) != expected for snapshot in (before, candidate, trusted)):
            raise ValidationError('standalone command recipe is not the exact protected recipe')
    if gate.commit_parents(gate.commit(git_objects, request.repository, request.merge_sha)) != (
            request.base_sha, request.head_sha):
        raise ValidationError('standalone native candidate does not have exact B/H parents')

    def snapshot(*, closing=False):
        if closing:
            gate._dispatch_source(api, config, request.repository, source)
        pr = api.json(prefix + '/pulls/' + str(request.number))
        branch = api.json(prefix + '/branches/' + gate.quote(request.base, safe=''))
        if pr.get('number') != request.number or pr.get('head', {}).get('ref') != request.head \
                or branch.get('name') != request.base or branch.get('protected') is not True \
                or branch.get('commit', {}).get('sha') != (request.base_sha if normal_parent is None else normal_parent):
            raise ValidationError('standalone original protected target/PR identity differs')
        if normal_parent is None:
            _recheck(api, gate, request)
        else:
            normal = gate.commit(git_objects, request.repository, normal_parent)
            if pr.get('state') != 'closed' or pr.get('merged') is not True \
                    or pr.get('merge_commit_sha') != normal_parent \
                    or pr.get('head', {}).get('sha') != request.head_sha \
                    or pr.get('base', {}).get('ref') != request.base \
                    or gate.commit_parents(normal) != (request.base_sha, request.head_sha) \
                    or gate.commit_tree(normal) != tree \
                    or gate.branch_sha(api, request.repository, request.base) != normal_parent:
                raise ValidationError('standalone closed owner lacks the exact current normal geometry')
        if any((pr.get(side, {}).get('repo', {}).get('id'),
                pr.get(side, {}).get('repo', {}).get('full_name')) != (1319052603, 'noah-l-frank/overte')
               for side in ('base', 'head')):
            raise ValidationError('standalone original PR repository differs')
        registration = api.json(prefix + '/actions/workflows/repository-checks.yml')
        if type(registration.get('id')) is not int or registration['id'] <= 0 \
                or (registration.get('path'), registration.get('state')) != (
                    '.github/workflows/repository-checks.yml', 'active'):
            raise ValidationError('standalone original caller registration differs')
        runs = gate._metadata_list(api, prefix + '/actions/workflows/' + str(registration['id'])
            + '/runs?head_sha=' + request.head_sha + '&per_page=100', 'workflow_runs')
        # Metadata nonproducers have a different immutable run-name expression.
        # Authenticate them with the unchanged existing classifier, never title alone.
        ordinary, metadata = [], []
        for row in runs:
            if row.get('display_title') == 'Overte native metadata nonproducer v2':
                adapter = controller.A.Adapter(api.native_producer_api(controller))
                workflows, helpers = controller.producer.metadata_generations(
                    controller.producer._host_policy(), root=ROOT)
                policy = controller.A.MetadataPolicy(registration['id'], registration['path'], workflows, helpers)
                binding = {'repository': request.repository, 'repository_id': request.repository_id,
                    'pull_request': request.number, 'head_repository_id': request.head_repository_id,
                    'base_ref': request.base, 'base_sha': request.base_sha, 'head_ref': request.head,
                    'head_sha': request.head_sha, 'merge_sha': request.merge_sha, 'merge_tree': tree,
                    'merge_parents': [request.base_sha, request.head_sha]}
                intent = adapter._native_metadata_intent(row, binding, policy, now=now,
                    integrated=normal_parent is not None, observation_clock=observation_clock)
                if intent is None:
                    raise ValidationError('standalone owner has an unauthenticated metadata competitor')
                metadata.append(intent)
            else:
                ordinary.append(row)
        if not ordinary:
            raise StandalonePending('original standalone ordinary run has not registered yet')
        if len(ordinary) != 1:
            raise ValidationError('standalone original ordinary run is ambiguous')
        listed = ordinary[0]
        identifier = listed['id']
        latest = api.json(prefix + '/actions/runs/' + str(identifier))
        attempt = api.json(prefix + '/actions/runs/' + str(identifier) + '/attempts/1')
        expected = {'id': identifier, 'workflow_id': registration['id'], 'run_attempt': 1,
            'path': '.github/workflows/repository-checks.yml', 'event': 'pull_request',
            'head_sha': request.head_sha, 'head_branch': request.head,
            'display_title': 'Overte native ordinary qualification v2',
            'status': 'completed', 'conclusion': 'success'}
        pending = False
        for run in (listed, latest, attempt):
            progressing = run.get('status') in {'queued', 'in_progress', 'waiting', 'pending', 'requested'} \
                and run.get('conclusion') is None
            if any(type(run.get(k)) is not type(v) or run[k] != v
                   for k, v in expected.items() if k not in {'status', 'conclusion'}) \
                    or type(run.get('check_suite_id')) is not int or run['check_suite_id'] <= 0 \
                    or any((run.get(k, {}).get('id'), run.get(k, {}).get('full_name')) != (
                        1319052603, 'noah-l-frank/overte') for k in ('repository', 'head_repository')):
                raise ValidationError('standalone original run is not uniquely completed attempt1')
            associations = run.get('pull_requests')
            if not (progressing and associations in (None, [])) and (type(associations) is not list or not (
                    normal_parent is not None and associations == []
                    or len(associations) == 1 and associations[0].get('number') == request.number
                    and associations[0].get('base', {}).get('sha') == request.base_sha
                    and associations[0].get('head', {}).get('sha') == request.head_sha)):
                raise ValidationError('standalone original PR association differs')
            refs = run.get('referenced_workflows')
            doc = [r for r in refs if type(r) is dict and r.get('path') == request.repository
                + '/.github/workflows/documentation-checks.yml@' + request.merge_sha] \
                if type(refs) is list else []
            if not progressing and (len(doc) != 1 or doc[0].get('sha') != request.merge_sha
                    or doc[0].get('ref') != 'refs/pull/' + str(request.number) + '/merge'):
                raise ValidationError('standalone original reusable workflow is not the exact current M')
            if progressing and refs is None:
                refs = []
            if type(refs) is not list or any(type(ref) is not dict for ref in refs):
                raise ValidationError('standalone native reusable source inventory is malformed')
            if len({r.get('path') for r in refs}) != len(refs):
                raise ValidationError('standalone native reusable source inventory is ambiguous')
            for ref in refs:
                start, end = request.repository + '/', '@' + request.merge_sha
                path = ref.get('path', '')
                relative = path[len(start):-len(end)]
                entry = trusted.get(relative)
                if not path.startswith(start + '.github/workflows/') or not path.endswith(end) \
                        or ref.get('sha') != request.merge_sha \
                        or ref.get('ref') != 'refs/pull/' + str(request.number) + '/merge' \
                        or entry is None or entry.get('mode') != '100644' or entry.get('type') != 'blob' \
                        or candidate.get(relative) != entry:
                    raise ValidationError('standalone native reusable source chain is foreign or mixed')
            start, update = run.get('run_started_at'), run.get('updated_at')
            if start is not None or not progressing:
                if not gate.parse_time(start, 'standalone run start') \
                        <= gate.parse_time(update, 'standalone run update') <= now:
                    raise ValidationError('standalone original run chronology differs')
            elif update is not None and gate.parse_time(update, 'standalone run update') > now:
                raise ValidationError('standalone pending run update is in the future')
            if progressing:
                pending = True
            elif (run.get('status'), run.get('conclusion')) != ('completed', 'success'):
                raise ValidationError('standalone original native owner failed or has unknown status')
        if any(any(run.get(k) != latest.get(k) for k in ('check_suite_id',))
               for run in (listed, attempt)):
            raise ValidationError('standalone native endpoint identities differ')
        if pending:
            raise StandalonePending('original standalone commands are still pending')
        if any(any(run.get(k) != latest.get(k) for k in ('run_started_at', 'referenced_workflows'))
               for run in (listed, attempt)):
            raise ValidationError('standalone completed endpoint source/start identities differ')
        suite = api.json(prefix + '/check-suites/' + str(latest['check_suite_id']))
        if (suite.get('id'), suite.get('head_sha'), suite.get('app', {}).get('id'),
                suite.get('repository', {}).get('id'), suite.get('repository', {}).get('full_name')) != (
                latest['check_suite_id'], request.head_sha, 15368, 1319052603, request.repository):
            raise ValidationError('standalone original native check-suite/App differs')
        jobs = gate._metadata_list(api, prefix + '/actions/runs/' + str(identifier)
            + '/attempts/1/jobs?per_page=100', 'jobs')
        if any(j.get('run_id') != identifier or j.get('run_attempt') != 1
                or j.get('head_sha') != request.head_sha or j.get('status') != 'completed'
                or j.get('conclusion') not in {'success', 'skipped'} for j in jobs):
            raise ValidationError('standalone original job inventory is pending, failed or mixed')
        for name in ('project', 'native', 'android'):
            rows = [j for j in jobs if j.get('name') == name]
            if len(rows) != 1 or rows[0].get('conclusion') != 'skipped':
                raise ValidationError('standalone CI proof requires the actual delegated no-product route')
        for name in ('repository-checks', 'Select required repository checks'):
            rows = [j for j in jobs if j.get('name') == name]
            if len(rows) != 1 or rows[0].get('conclusion') != 'success':
                raise ValidationError('standalone original canonical aggregate/route is unavailable')
        commands = {
            'documentation / documentation': (
                'Verify documentation checker behavior', 'Check every workspace document and incoming link',
                'Verify policy-derived branch and suite displays'),
            'workflow-contracts': ('Verify remaining workflow contracts',),
        }
        if len({j.get('name') for j in jobs}) != len(jobs):
            raise ValidationError('standalone native job names are ambiguous')
        relevant = [job for job in jobs if job['name'] in {*commands, 'repository-checks', 'Select required repository checks'}]
        checks = {job['name']: gate._metadata_check(api, prefix, latest, job, request.head_sha) for job in relevant}
        if any(checks[job['name']].get('details_url') != 'https://github.com/' + request.repository
                + '/actions/runs/' + str(identifier) + '/job/' + str(job['id']) for job in relevant):
            raise ValidationError('standalone native job/check/run links differ')
        selected_jobs = {}
        for name, steps in commands.items():
            rows = [j for j in jobs if j.get('name') == name]
            if len(rows) != 1 or rows[0].get('conclusion') != 'success':
                raise ValidationError('standalone original successful command owner is unavailable')
            job = rows[0]
            for step in steps:
                gate._metadata_step(job, step)
            if not gate.parse_time(latest['run_started_at'], 'standalone run start') \
                    <= gate.parse_time(job['started_at'], 'standalone job start') \
                    <= gate.parse_time(job['completed_at'], 'standalone job completion') \
                    <= gate.parse_time(latest['updated_at'], 'standalone run completion'):
                raise ValidationError('standalone job is outside its original native run')
            selected_jobs[name] = job
        return {'listed': listed, 'run': latest, 'attempt': attempt, 'jobs': jobs,
            'checks': checks, 'selected_jobs': selected_jobs, 'registration': registration, 'check_suite': suite}

    opening = snapshot()
    # Completed whole inventories and relevant checks are reread. Live default,
    # current PR/M, target/parent refs and registration bind the unchanged SHAs;
    # refetching the same immutable Git objects would add no new bookend.
    if snapshot(closing=True) != opening:
        raise ValidationError('standalone native source/current PR closing bookend changed')
    completed = max(gate.parse_time(job['completed_at'], 'standalone completion')
        for job in opening['selected_jobs'].values())
    expires = completed + timedelta(hours=int(config['evidence_max_age_hours']))
    if not completed <= now < expires:
        raise ValidationError('standalone command coverage is stale')
    return NativeStandaloneCIProof({'kind': 'same-pr-native-standalone-ci-commands-v1',
        'qualification': False, 'reusable': False, 'source': source, 'source_tree': source_tree,
        'base': request.base_sha, 'head': request.head_sha, 'candidate': request.merge_sha, 'tree': tree,
        'suites': names, 'commands': {name: registry['suites'][name]['command'] for name in names},
        'native': opening, 'coverage_expires_at': expires.isoformat().replace('+00:00', 'Z')})


def verify_standalone_ci_provenance(reported, actual, request, *, normal_parent=None):
    """Permit only cleared associations after an independently checked normal N."""
    if not isinstance(actual, NativeStandaloneCIProof) or type(reported) is not dict:
        raise ValidationError('standalone command coverage is not a native proof')
    expected = json.loads(json.dumps(reported))
    if normal_parent is not None:
        records = [(expected['native'][name], actual['native'][name])
                   for name in ('listed', 'run', 'attempt', 'check_suite')]
        records += [(check, actual['native']['checks'][name])
                    for name, check in expected['native']['checks'].items()]
        for retained, current in records:
            associations = retained.get('pull_requests')
            if current.get('pull_requests') == [] and associations != []:
                if type(associations) is not list or len(associations) != 1 \
                        or associations[0].get('number') != request.number \
                        or associations[0].get('base', {}).get('sha') != request.base_sha \
                        or associations[0].get('head', {}).get('sha') != request.head_sha:
                    raise ValidationError('retained standalone closed PR association differs')
                retained['pull_requests'] = []
    if expected != actual:
        raise ValidationError('standalone native provenance changed')


def _native_standalone_ci_owners(api, gate, request, registry, selection):
    """Wait only before commands; pending is never successful native coverage."""
    deadline = time.monotonic() + 900
    while True:
        try:
            return verify_standalone_ci_owners(api, gate, request, registry, selection)
        except StandalonePending:
            if time.monotonic() >= deadline:
                raise ValidationError('original standalone owners did not finish before the wait bound') from None
            time.sleep(min(5, max(0, deadline - time.monotonic())))


def _standalone_ci_schedule(candidate, event, request, plan, *, base_tree, candidate_tree,
                            trusted_tree, pr_context=None):
    """Scheduling only: unsupported sources/owners keep the prior CI37 route."""
    if plan.get('package_set') or plan.get('host_mode') != 'delegated-sync':
        return False
    for path, sha in {
            '.github/workflows/repository-checks.yml': '22fe0d6d39d120f800099136d7d1ab5280d80b41',
            '.github/workflows/documentation-checks.yml': 'a86e36287a315eed7bbadf366f923966a04bd806'}.items():
        expected = {'mode': '100644', 'type': 'blob', 'sha': sha}
        if any(tree.get(path) != expected for tree in (base_tree, candidate_tree, trusted_tree)):
            return False
    registry = trusted_tree.get('.github/test-suites.json')
    if registry is None or registry.get('mode') != '100644' or registry.get('type') != 'blob' \
            or any(tree.get('.github/test-suites.json') != registry for tree in (base_tree, candidate_tree)):
        return False
    # The fixed caller's six reusable sources must also match the protected
    # candidate. Their older B versions need not match; they grant no coverage.
    for name in ('pr-metadata-context', 'native-tests', 'project-tests', 'android-required',
                 'documentation-checks', 'workflow-security'):
        path = '.github/workflows/' + name + '.yml'
        entry = trusted_tree.get(path)
        if entry is None or entry.get('mode') != '100644' or entry.get('type') != 'blob' \
                or candidate_tree.get(path) != entry:
            return False
    native = _trusted_module('sync_standalone_native_schedule', ROOT / 'tools/native-tests/check.py')
    mode = native.plan(plan['paths'], plan['regular']).get('mode')
    if mode not in {'skip', 'core', 'full'}:
        raise ValidationError('standalone native scheduling route is malformed')
    if mode != 'skip':
        return False
    android = _trusted_module('sync_standalone_android_schedule', ROOT / 'tools/repository-checks/android_gate.py')
    if not (android.activated(event) or android.has_staged_caller(candidate)):
        return True
    android.validate_execution_generation(candidate, event, pr_context=pr_context)
    selected = android.candidate_plan(candidate, event, request.merge_sha,
        event_name='pull_request', policy_root=ROOT, pr_context=pr_context)
    if selected.get('candidate') != request.merge_sha or type(selected.get('required')) is not bool:
        raise ValidationError('standalone Android scheduling route is malformed')
    return selected['required'] is False


def _trusted_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValidationError("trusted synchronization validator is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _gate():
    return _trusted_module("isolated_sync_gate", ROOT / "tools/sync-test-reuse/gate.py")


@contextmanager
def candidate_environment():
    """Keep API credentials/Actions command files out of candidate subprocesses."""
    previous = {name: os.environ.pop(name) for name in _CANDIDATE_PRIVATE_ENVIRONMENT if name in os.environ}
    try:
        yield
    finally:
        for name in _CANDIDATE_PRIVATE_ENVIRONMENT:
            os.environ.pop(name, None)
        os.environ.update(previous)


def _request(args, gate, config, api):
    if args.repository != config["repository"] or type(args.pull_request) is not int or args.pull_request < 1:
        raise ValidationError("requested synchronization repository or pull request is invalid")
    repository = api.json(f"repos/{args.repository}")
    if not isinstance(repository, dict) or repository.get("full_name") != config["repository"] \
            or repository.get("id") != config["repository_id"]:
        raise ValidationError("actual synchronization repository identity differs from trusted policy")
    pr = api.json(f"repos/{args.repository}/pulls/{args.pull_request}")
    if not isinstance(pr, dict) or pr.get("number") != args.pull_request:
        raise ValidationError("actual pull request identity is incomplete")
    event = {"number": args.pull_request, "repository": repository, "pull_request": pr}
    context = gate.effective_pr_context(event, api) if os.environ.get('GITHUB_ACTIONS') == 'true' else None
    request = (gate.classify_event(event, config, api, pr_context=context) if context is not None
               else gate.classify_event(event, config, api))
    if request is None:
        raise ValidationError("ordinary pull requests cannot use synchronization validation")
    expected = (args.repository, args.pull_request, args.base_sha, args.head_sha, args.merge_sha, args.profile)
    actual = (request.repository, request.number, request.base_sha, request.head_sha, request.merge_sha, request.profile)
    if actual != expected:
        raise ValidationError("live synchronization candidate or profile differs from dispatch identity")
    if request.repair_paths and args.mode == "reuse":
        raise ValidationError("attested product repairs require complete synchronization fallback")
    return request


def _recheck(api, gate, request):
    if getattr(request, 'event_base_sha', None) is not None:
        gate.recheck_effective_request(api, request)
        if gate.branch_sha(api, request.repository, request.parent) != request.parent_sha:
            raise ValidationError('direct parent moved during effective-base validation')
        return
    current = api.json(f"repos/{request.repository}/pulls/{request.number}")
    try:
        actual = (current["number"], current["state"], current["base"]["ref"], current["base"]["sha"],
                  current["head"]["ref"], current["head"]["sha"], current["head"]["repo"]["id"],
                  current["merge_commit_sha"])
    except (KeyError, TypeError) as error:
        raise ValidationError("live pull request identity is unavailable after validation") from error
    expected = (request.number, "open", request.base, request.base_sha, request.head, request.head_sha,
                request.head_repository_id, request.merge_sha)
    if actual != expected or current.get("mergeable") is False:
        raise ValidationError("pull request moved or became unmergeable during validation")
    if gate.branch_sha(api, request.repository, request.base) != request.base_sha \
            or gate.branch_sha(api, request.repository, request.parent) != request.parent_sha:
        raise ValidationError("target or parent branch moved during validation")


def _differential(candidate, request, documents):
    differential = _trusted_module("isolated_sync_differential", ROOT / "tools/sync-test-reuse/differential.py")
    with tempfile.TemporaryDirectory(prefix="overte-sync-inputs-") as temporary:
        path = Path(temporary) / "changed-files.json"
        path.write_bytes(execution.canonical_json(documents))
        changes = differential.load_changes(path, structured=True)
    current = differential.current_paths(candidate, changes)
    changed = [path for change in changes for path in (change.filename, change.previous_filename) if path is not None]
    differential.ensure_no_conflict_markers(candidate, current)
    differential.validate_json(candidate, current)
    differential.required_roots(candidate, request.profile, changed)
    differential.syntax_contracts(candidate, current)


def _candidate_differential(candidate, request, gate, api):
    documents = (gate.immutable_change_documents(api, request.repository, request.base_sha, request.merge_sha)
                 if getattr(request, 'event_base_sha', None) is not None
                 else gate.paginate_pull_files(api, request.repository, request.number))
    if gate.changed_paths(documents) != set(request.changed_paths):
        raise ValidationError("synchronization file inventory changed during validation")
    with candidate_environment():
        _differential(candidate, request, documents)


def _bounded_junit(path, projects):
    cases = ["sync-differential", *["tool-dependencies:" + project for project in projects]]
    root = ET.Element("testsuite", name="overte-sync-bounded", tests=str(len(cases)), failures="0", errors="0", skipped="0")
    for name in cases:
        ET.SubElement(root, "testcase", classname="overte.sync", name=name)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValidationError("bounded test report destination is unsafe")
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def _read_execution(path, returned):
    try:
        path = Path(path)
        if path.is_symlink() or path.stat().st_size > 5_000_000:
            raise ValidationError("trusted execution receipt is unavailable or unsafe")
        persisted = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=inputs._unique_object)
    except (OSError, UnicodeError, json.JSONDecodeError, inputs.InputError) as error:
        raise ValidationError("trusted execution receipt was not persisted completely") from error
    if persisted != returned:
        raise ValidationError("persisted execution receipt differs from trusted observations")
    return persisted


def _parent_provenance(evidence, reused, gate):
    if evidence is None:
        return None
    if isinstance(evidence, getattr(gate, 'NativePrEvidence', ())):
        return None  # This PR's execution must never be described as parent proof.
    if isinstance(evidence, getattr(gate, 'NativeExactTreeParentEvidence', ())):
        return {key: evidence[key] for key in ('kind', 'source', 'parent_branch', 'parent_commit',
            'parent_tree', 'original_commit', 'qualified_at', 'expires_at', 'original_proof', 'original_report')} | {
            'qualification': False, 'reusable': False, 'inherited_suites': list(reused)}
    if isinstance(evidence, getattr(gate, 'NativeParentEvidence', ())):
        return {key: evidence[key] for key in ('kind', 'parent_branch', 'parent_commit', 'parent_tree',
            'original_commit', 'original_git_context', 'qualified_at', 'expires_at', 'original_proof')} | {
            'qualification': False, 'reusable': False,
            'reused_results': {name: evidence['results']['suites'][name] for name in reused}}
    return {key: evidence[key] for key in (
        "evidence_digest", "parent_branch", "parent_commit", "parent_tree", "workflow", "qualified_at", "expires_at",
    )} | {"reused_results": {name: evidence["results"]["suites"][name] for name in reused}}


def _ci_policy():
    paths = ("tools/test-evidence/validate-sync.py", "tools/test-evidence/execution.py",
             "tools/test-evidence/inputs.py", "tools/test-evidence/runtime.py",
             "tools/sync-test-reuse/gate.py", "tools/sync-test-reuse/differential.py",
             "tools/test-evidence/producer_workflow.py", "tools/repository-checks/host_selection.py",
             "tools/repository-checks/package_checks.py",
             "tools/repository-checks/npm_consumers.py", "tests/run-project-tests.py",
             ".github/test-suites.json", ".github/package-workflow-generations.json",
             ".github/repository-checks.json", "tools/repository-checks/android_handoff.py",
             "tools/repository-checks/android_gate.py", "tools/native-tests/check.py")
    result = {}
    for relative in paths:
        path = ROOT / relative
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 1_000_000:
            if relative == ".github/repository-checks.json":
                # Bind absence/unsafe ownership configuration while selecting
                # complete fallback; it can never admit the affected lane.
                result[relative] = None
                continue
            raise ValidationError("trusted synchronization selection policy is unavailable")
        result[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def _repository_owner_policy():
    path = ROOT / ".github/repository-checks.json"
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 1_000_000 \
            or path.stat().st_mode & 0o111:
        raise ValidationError("mandatory repository owner configuration is unavailable")
    return json.loads(path.read_text(), object_pairs_hook=inputs._unique_object)


def _sync_platform_owner(args, request, candidate, api, *, native_current=False):
    """Retain the existing Pico handoff; its plan alone is never success proof."""
    if (args.mode != "fallback" and not native_current) or request.base not in {
            "android-main", "android-phone", "android-vr", "android-vr-pico"}:
        return {}
    config = _repository_owner_policy()
    if not isinstance(config, dict) or config.get("repository") != request.repository \
            or type(config.get("repository_id")) is not int or config["repository_id"] != request.repository_id \
            or not isinstance(config.get("required_contexts"), list) \
            or "repository-checks" not in config["required_contexts"]:
        raise ValidationError("pending Android ownership requires the mandatory canonical repository gate")
    handoff = _trusted_module("sync_android_platform_owner", ROOT / "tools/repository-checks/android_handoff.py")
    return handoff.sync_platform_owner(candidate, request, api)


def _ci_selection(args, request, candidate, initial, registry, api):
    """Plan from trusted policy and immutable inputs; never certify execution."""
    bounded = args.mode == "reuse" and request.profile in ("documentation", "tool-dependencies")
    result = {"schema": 1, "kind": "sync-ci-selection", "reusable": False,
              "repository": request.repository, "repository_id": request.repository_id,
              "pull_request": request.number, "base": request.base_sha, "head": request.head_sha,
              "candidate": initial[0], "tree": initial[1], "parent": request.parent_sha,
              "target": request.base, "profile": request.profile, "requested_mode": args.mode,
              "lane": "legacy-bounded" if bounded else "complete",
              "full_host": not bounded, "suites": [], "omitted_suites": [],
              "external_package_set": [], "package_plan": None,
              "registry": execution.digest(registry), "policy": _ci_policy()}
    if not request.changed_paths and not request.repair_paths:
        gate = _gate()
        checker = getattr(gate, 'verified_empty_sync', None)
        empty = checker(api, gate.load_config(), request, candidate) if callable(checker) else None
        if empty is not None:
            if type(empty) is not dict or empty.get('kind') != 'verified-empty-sync-v1' \
                    or empty.get('qualification') is not False or empty.get('reusable') is not False \
                    or empty.get('immutable', {}).get('candidate') != initial[0] \
                    or empty['immutable'].get('tree') != initial[1]:
                raise ValidationError('empty synchronization source proof is invalid')
            result.update(lane='verified-empty', full_host=False, empty_source=empty,
                omitted_suites=list(registry['suites']))
            result['selection'] = execution.digest(result)
            return result
    native_selected = False
    if not bounded and not request.repair_paths:
        try:
            host = _trusted_module("sync_ci_host_policy", ROOT / "tools/repository-checks/host_selection.py")
            packages = host.package_policy()
            packages.validate_wiring(candidate)
            if not packages.consumer_generation(candidate):
                raise ValidationError("complete required package owner is unavailable")
            event = {"repository": api.json(f"repos/{request.repository}"),
                     "pull_request": api.json(f"repos/{request.repository}/pulls/{request.number}")}
            owner_config = _repository_owner_policy()
            if not isinstance(owner_config, dict) or owner_config.get("repository") != request.repository \
                    or type(owner_config.get("repository_id")) is not int \
                    or owner_config["repository_id"] != request.repository_id \
                    or not isinstance(owner_config.get("required_contexts"), list) \
                    or "repository-checks" not in owner_config["required_contexts"] \
                    or not (packages.activated(event) or packages.has_staged_caller(candidate)):
                raise ValidationError("the exact package owner has no mandatory repository aggregate")
            context = None
            if getattr(request, 'event_base_sha', None) is not None:
                gate = _gate()
                context = gate.recheck_effective_request(api, request, event_pr=event['pull_request'])
                plan = packages.candidate_plan(candidate, event, initial[0], pr_context=context.planning())
            else:
                plan = packages.candidate_plan(candidate, event, initial[0])
            if plan.get("unknown") is not False or plan.get("consumer_generation") is not True \
                    or (plan.get("base"), plan.get("head"), plan.get("candidate"), plan.get("tree")) != (
                        request.base_sha, request.head_sha, initial[0], initial[1]) \
                    or set(plan["paths"]) != set(request.changed_paths):
                raise ValidationError("required package plan differs from the live synchronization")
            # The exact five-file caller is independently enforced by the
            # required repository aggregate, including external npm receipts.
            tree = inputs.full_tree(candidate, initial[0])
            base_tree = inputs.full_tree(candidate, request.base_sha)
            trusted_tree = inputs.full_tree(ROOT, "HEAD")
            selected = host.select(tree, plan["paths"], host.regular_ci_inventory(plan, base_tree, tree),
                unknown=plan["unknown"], trusted_tree=trusted_tree, candidate_root=candidate,
                trusted_root=ROOT, target=request.base, base_tree=base_tree,
                package_paths=host.package_owned_paths(plan))
            if plan.get('host_mode') == 'full' and args.mode != 'reuse':
                native_selected = True
                raise ValidationError('promoted native current owner cannot be replaced by a fallback mode')
            native_selected = plan.get('host_mode') == 'full' and selected['full_host'] is True
            if native_selected and not packages.load(
                    'sync_native_source_policy', 'tools/repository-checks/check.py').native_owner_policy().sync_source_ready(
                        candidate, event, {'base':request.base_sha, 'candidate':initial[0]}):
                raise ValidationError('promoted native current owner lost its protected source readiness')
            if (selected["include_platform"] is not False and not native_selected) or not selected["suites"] \
                    or host.additional_suites(host.candidate_registry(candidate), registry):
                raise ValidationError("complete product/shared fallback remains required")
            if len(set(selected["suites"])) != len(selected["suites"]) \
                    or any(name not in registry["suites"] for name in selected["suites"]):
                raise ValidationError("affected synchronization suite inventory is invalid")
            result.update(lane="native-owner" if native_selected else "affected-ci",
                full_host=selected["full_host"], suites=selected["suites"],
                omitted_suites=[name for name in registry["suites"] if name not in selected["suites"]],
                external_package_set=plan["package_set"], package_plan=plan["plan"],
                dependency_selection=selected, package_policy=plan["policy"])
            if native_selected:
                result.update(native_current_owner_required=True,
                    platform_commands=[{'name':name,'command':command}
                        for name,command in execution.platform_suites(candidate, registry['suites'])])
        except (OSError, ValueError, KeyError, TypeError, AttributeError, ImportError, subprocess.SubprocessError):
            if native_selected:
                raise ValidationError('selected native current owner cannot become duplicate fallback') from None
            # No successful diagnostic, unknown reader or missing package owner
            # can authorize omitting complete fallback and its product checks.
            pass
    pending = _sync_platform_owner(args, request, candidate, api) if result["lane"] == "complete" else {}
    if pending:
        result["pending_platform_owners"] = pending
        owner = _trusted_module("sync_android_policy_identity", ROOT / "tools/repository-checks/android_gate.py")
        result["platform_owner_policy"] = owner._policy_identity(ROOT)
    if _standalone_ci_names({**result, 'standalone_ci_schedule': True}, registry):
        # This never authorizes coverage. A positive unrelated product/Android
        # owner preserves the existing37 before the native proof is selected.
        result['standalone_ci_schedule'] = _standalone_ci_schedule(candidate, event, request, plan,
            base_tree=base_tree, candidate_tree=tree, trusted_tree=trusted_tree,
            pr_context=context.planning() if context is not None else None)
    result["selection"] = execution.digest(result)
    return result


def select_sync(args, *, api=None):
    """Early prerequisite selection with the same live topology/source bookends."""
    gate = _gate(); config = gate.load_config(); api = api or gate.GitHubApi()
    request = _request(args, gate, config, api)
    candidate = Path(args.candidate).resolve(strict=True)
    initial = execution.checkout_identity(candidate)
    if initial[0] != request.merge_sha:
        raise ValidationError("selection checkout is not the exact synchronization candidate")
    registry = inputs.load_registry(ROOT / ".github/test-suites.json")
    result = _ci_selection(args, request, candidate, initial, registry, api)
    if result['lane'] == 'verified-empty':
        result = {**result, 'consumer_setup':'none', 'empty_setup':result['selection']}
        scheduling = None
    else:
        scheduling, _ = _native_zero_setup(args, gate, api, config, request, candidate, initial, registry, result)
    if scheduling is not None:
        # Additional outputs schedule prerequisites only. The existing pure
        # source selection digest remains independent of transient API proof.
        result = {**result, 'consumer_setup': 'none', 'native_setup': scheduling}
    if execution.checkout_identity(candidate) != initial:
        raise ValidationError("candidate changed during synchronization selection")
    _recheck(api, gate, request)
    return result


def _ci_commands(selection, registry, *, suite_names=None):
    names = selection["suites"] if suite_names is None else suite_names
    if type(names) is not list or names != [name for name in selection["suites"] if name in names]:
        raise ValidationError("remaining CI commands must be an exact ordered subset of the trusted selection")
    return {name: registry["suites"][name]["command"] for name in names}


def _execute_ci(candidate, initial, selection, registry, junit, receipt_path, *, suite_names=None):
    """Observe every selected invocation without creating reusable fingerprints."""
    controller = execution._runner()
    commands = _ci_commands(selection, registry, suite_names=suite_names)
    suites = [controller.Suite(name, registry["suites"][name]["layer"], tuple(
        sys.executable if index == 0 and value == "python" else value
        for index, value in enumerate(command))) for name, command in commands.items()]
    observations, cancelled, previous = [], [], {}
    def interrupted(signum, _frame):
        if not cancelled:
            cancelled.append(signum)
    started = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    old_root = controller.ROOT
    controller.ROOT = candidate
    try:
        for signum in (signal.SIGINT, signal.SIGTERM):
            previous[signum] = signal.signal(signum, interrupted)
        with execution.candidate_process_environment():
            status = controller.run_suites(SimpleNamespace(timeout=240, host_timeout=900,
                native_build_dir=None, junit=junit, fail_fast=False), suites, cancelled,
                result_callback=observations.append)
    finally:
        controller.ROOT = old_root
        for signum, handler in previous.items():
            signal.signal(signum, handler)
    if execution.checkout_identity(candidate) != initial:
        raise ValidationError("candidate changed during affected synchronization execution")
    actual_names = [item["name"] for item in observations]
    complete = actual_names == list(commands) and all(item["status"] == "passed" for item in observations)
    status = status or (0 if complete and not cancelled else 1)
    receipt = {"schema": 1, "producer": CI_EXECUTION_PRODUCER, "reusable": False,
        "candidate_commit": initial[0], "candidate_tree": initial[1], "selection": selection["selection"],
        "registry": execution.digest(registry), "include_platform": False,
        "requested_suites": list(commands), "results": [
            {"name": item["name"], "status": item["status"], "command": commands.get(item["name"])}
            for item in observations], "conclusion": "success" if status == 0 else "failure",
        "started_at": started, "completed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")}
    receipt["receipt_digest"] = execution.digest(receipt)
    execution._write_receipt(receipt_path, receipt)
    return status, receipt


def _verify_ci_execution(observed, selection, registry, initial, *, suite_names=None):
    fields = {"schema", "producer", "reusable", "candidate_commit", "candidate_tree", "selection", "registry",
              "include_platform", "requested_suites", "results", "conclusion", "started_at", "completed_at", "receipt_digest"}
    if not isinstance(observed, dict) or set(observed) != fields:
        raise ValidationError("affected synchronization execution receipt format is invalid")
    unsigned = dict(observed); claimed = unsigned.pop("receipt_digest")
    commands = _ci_commands(selection, registry, suite_names=suite_names)
    if type(observed["schema"]) is not int or observed["schema"] != 1 \
            or observed["producer"] != CI_EXECUTION_PRODUCER or observed["reusable"] is not False \
            or observed["include_platform"] is not False or observed["conclusion"] != "success" \
            or (observed["candidate_commit"], observed["candidate_tree"]) != initial \
            or observed["selection"] != selection["selection"] or observed["registry"] != execution.digest(registry) \
            or claimed != execution.digest(unsigned) or observed["requested_suites"] != list(commands) \
            or observed["results"] != [{"name": name, "status": "passed", "command": command}
                                       for name, command in commands.items()]:
        raise ValidationError("affected synchronization execution lacks exact selected successful coverage")
    for field in ("started_at", "completed_at"):
        if not isinstance(observed[field], str):
            raise ValidationError("affected synchronization execution time is invalid")
        stamp = datetime.fromisoformat(observed[field].replace("Z", "+00:00"))
        if stamp.tzinfo is None or stamp.utcoffset().total_seconds() != 0:
            raise ValidationError("affected synchronization execution time is unqualified")
    if observed["started_at"] > observed["completed_at"]:
        raise ValidationError("affected synchronization execution time order is invalid")


def _native_ci_reuse(args, gate, api, config, request, registry, local_tree, selection, *, native_evidence=None):
    """Intersect original native proof with independently selected current work.

    No legacy JSON class or preview chooses a suite. The actual native adapter
    must validate original M/E first; current immutable inputs then determine
    which of the already selected commands still need execution.
    """
    selected = selection["suites"]
    if args.mode != "reuse" or not callable(getattr(gate, 'native_parent_evidence', None)):
        return None, [], list(selected)
    if native_evidence is None:
        exact = getattr(gate, 'native_exact_tree_parent_evidence', None)
        evidence = exact(api, config, request) if callable(exact) and not selection.get('native_current_owner_required') else None
        current = getattr(gate, 'native_pr_evidence', None)
        if evidence is None:
            evidence = current(api, config, request) if callable(current) else None
        if evidence is None:
            if selection.get('native_current_owner_required'):
                raise ValidationError('selected native current owner is unavailable; second execution is forbidden')
            try:
                evidence = gate.native_parent_evidence(api, config, request)
            except (gate.EvidenceError, gate.GateError):
                return None, [], list(selected)
    else:
        evidence = native_evidence
    if isinstance(evidence, getattr(gate, 'NativeExactTreeParentEvidence', ())):
        if evidence.get('candidate_inputs') != local_tree or evidence.get('requested_suites') != selected \
                or evidence.get('reusable') is not False or evidence.get('qualification') is not False \
                or selection.get('native_current_owner_required'):
            raise ValidationError('identical-tree original CI proof differs from selected current inputs')
        return evidence, list(selected), []
    original_pr = isinstance(evidence, getattr(gate, 'NativePrEvidence', ()))
    if selection.get('native_current_owner_required') and not original_pr:
        raise ValidationError('selected current PR cannot be replaced with parent evidence')
    if not original_pr and not isinstance(evidence, getattr(gate, 'NativeParentEvidence', ())):
        return None, [], list(selected)
    if evidence.get('candidate_inputs') != local_tree:
        raise ValidationError('local immutable CI candidate differs from verified native API inputs')
    try:
        plan = inputs.plan_reuse(registry, evidence['tested_inputs'] if original_pr else evidence['parent_inputs'], local_tree,
            evidence['results']['suites'], evidence['environment'], evidence['environment'])
    except (inputs.InputError, KeyError, TypeError):
        if original_pr:
            raise ValidationError('selected original PR input proof is invalid; duplicate execution is forbidden') from None
        # No candidate command has started. Existing real selected execution
        # remains required when proof or its input identity is unavailable.
        return None, [], list(selected)
    reused = [name for name in selected if name in plan['reused']]
    if original_pr and (reused != selected or evidence['requested_suites'] != selected):
        raise ValidationError('selected original PR proof omits Sync commands; duplicate execution is forbidden')
    if not reused:
        return None, [], list(selected)
    return evidence, reused, [name for name in selected if name not in reused]



def _native_current_platform(args, gate, api, request, candidate, registry, selection, evidence):
    """Match actual declarations to completed native roles; never mint platform E."""
    actual = [{'name':name,'command':command}
        for name,command in execution.platform_suites(candidate, registry['suites'])]
    expected = selection.get('platform_commands', actual)
    if expected != actual or evidence.get('platform_commands', []) != actual:
        raise ValidationError('original current PR omits or changes actual platform commands')
    observation = evidence.get('original_platform_observation')
    if actual:
        if not isinstance(observation, dict) or observation.get('kind') != 'original-android-platform-native-job-v1' \
                or observation.get('run_id') != evidence['original_proof']['run_id'] \
                or observation.get('attempt') != 1 or observation.get('reusable') is not False \
                or observation.get('qualification') is not False \
                or observation.get('partition') != evidence.get('platform_partition'):
            raise ValidationError('actual platform commands lack their completed same-PR native owner')
    elif observation is not None or evidence.get('platform_partition') is not None:
        raise ValidationError('unselected platform owner has an unexpected success claim')
    pending = _sync_platform_owner(args, request, candidate, api, native_current=True) if actual else {}
    if pending:
        execution._validate_platform_owner(pending, request.merge_sha)
        if set(pending) != {'pico4-device-free'} or not set(pending) <= {row['name'] for row in actual}:
            raise ValidationError('unknown independent Android ownership in the exact current PR')
    return pending


def _native_zero_setup(args, gate, api, config, request, candidate, initial, registry, selection):
    """Schedule no consumer setup only for actual native zero-command coverage.

    This stdlib-only lookup grants no execution or reusable authority. The
    validator independently reconstructs it before the differential and then
    authenticates the original proof again after that actual validation.
    """
    if args.mode != 'reuse' or selection['lane'] not in {'affected-ci','complete','native-owner'} \
            or request.repair_paths or selection.get('pending_platform_owners'):
        return None, None
    selected = selection['suites'] if selection['lane'] in {'affected-ci','native-owner'} else list(registry['suites'])
    tree = inputs.full_tree(candidate, initial[0])
    evidence, reused, required = _native_ci_reuse(args, gate, api, config, request, registry, tree,
        {**selection, 'suites': selected})
    if evidence is None or required or reused != selected:
        return None, None
    original_pr = isinstance(evidence, getattr(gate, 'NativePrEvidence', ()))
    identical = isinstance(evidence, getattr(gate, 'NativeExactTreeParentEvidence', ()))
    if original_pr:
        _native_current_platform(args, gate, api, request, candidate, registry, selection, evidence)
    if not original_pr and not identical and execution.platform_suites(candidate, registry['suites']):
        return None, None
    if gate.parse_time(evidence['expires_at'], 'expires_at') <= datetime.now(timezone.utc):
        return None, None
    value = {'schema':1, 'kind':'native-zero-command-setup-v1',
        'base':request.base_sha, 'head':request.head_sha, 'candidate':initial[0], 'tree':initial[1],
        'selection':selection['selection'], 'suites':selected,
        'original_commit':evidence['original_commit'],
        'qualified_at':evidence['qualified_at'], 'expires_at':evidence['expires_at'],
        'original_proof':evidence['original_proof']}
    if original_pr:
        value.update(kind='native-current-pr-zero-command-setup-v1',
            platform_commands=evidence.get('platform_commands', []),
            original_platform_observation=evidence.get('original_platform_observation'),
            platform_partition=evidence.get('platform_partition'))
    else:
        value['parent_commit'] = evidence['parent_commit']
        if identical:
            value.update(kind='native-exact-tree-parent-zero-command-setup-v1', source=evidence['source'])
    return execution.digest(value), evidence


def _recheck_native_ci(gate, api, config, request, evidence, registry, local_tree, reused):
    if isinstance(evidence, getattr(gate, 'NativeExactTreeParentEvidence', ())):
        final = gate.native_exact_tree_parent_evidence(api, config, request)
        if not isinstance(final, gate.NativeExactTreeParentEvidence) or final != evidence \
                or final.get('candidate_inputs') != local_tree or final.get('requested_suites') != reused \
                or gate.parse_time(final['expires_at'], 'expires_at') <= datetime.now(timezone.utc):
            raise ValidationError('identical-tree original CI proof changed after differential validation')
        return
    original_pr = isinstance(evidence, getattr(gate, 'NativePrEvidence', ()))
    try:
        final = (gate.native_pr_evidence(api, config, request, timeout=0) if original_pr
                 else gate.native_parent_evidence(api, config, request))
    except (gate.EvidenceError, gate.GateError) as error:
        raise ValidationError('original native CI proof became unavailable after selected validation') from error
    kind = 'NativePrEvidence' if original_pr else 'NativeParentEvidence'
    if not isinstance(final, getattr(gate, kind, ())) or final != evidence:
        raise ValidationError('original native CI proof changed after selected validation')
    try:
        plan = inputs.plan_reuse(registry, final['tested_inputs'] if original_pr else final['parent_inputs'], local_tree,
            final['results']['suites'], final['environment'], final['environment'])
    except (inputs.InputError, KeyError, TypeError) as error:
        raise ValidationError('original native CI input identities became unverifiable') from error
    if set(reused) - set(plan['reused']) or gate.parse_time(final['expires_at'], 'expires_at') <= datetime.now(timezone.utc):
        raise ValidationError('original native CI proof no longer covers selected current inputs or expired')


def validate_sync(args, *, api=None):
    """Validate a synchronization and return an independently checked receipt.

    The API adapter performs only trusted reads. The gate's source preview does
    not authorize skipping: authenticated original native M/E or actual current
    execution and immutable candidate inputs determine the final suite coverage.
    """
    gate = _gate()
    config = gate.load_config()
    api = api or gate.GitHubApi()
    request = _request(args, gate, config, api)
    candidate = Path(args.candidate).resolve(strict=True)
    initial = execution.checkout_identity(candidate)
    if initial[0] != request.merge_sha:
        raise ValidationError("checked-out candidate is not the exact dispatched merge commit")
    local_tree = inputs.full_tree(candidate, initial[0])
    registry = inputs.load_registry(ROOT / ".github/test-suites.json")
    started = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    evidence, observed, reused, executed, projects = None, None, [], [], []
    standalone = None
    native_parent = False
    ci_required = None
    prepared_native = None
    external_packages = []
    selection = None
    if getattr(args, "expected_selection", ""):
        selection = _ci_selection(args, request, candidate, initial, registry, api)
        if args.expected_selection != selection["selection"]:
            raise ValidationError("synchronization selection differs from the prerequisite plan")
    empty_setup = getattr(args, 'expected_empty_setup', '')
    empty_lane = selection is not None and selection['lane'] == 'verified-empty'
    if empty_setup or empty_lane:
        if not empty_lane or not empty_setup or empty_setup != selection['selection'] \
                or getattr(args, 'expected_native_setup', ''):
            raise ValidationError('empty synchronization setup does not match its exact source selection')
        # The real topology was checked by _request. No original receipt/runtime
        # or candidate test may be queried or manufactured for zero work.
        _candidate_differential(candidate, request, gate, api)
        if execution.checkout_identity(candidate) != initial \
                or _ci_selection(args, request, candidate, initial, registry, api) != selection:
            raise ValidationError('empty synchronization changed during differential validation')
        _recheck(api, gate, request)
        if _ci_selection(args, request, candidate, initial, registry, api) != selection:
            raise ValidationError('empty synchronization final source/native bookend changed')
        result = {'schema':1,'kind':'sync-no-execution-validation-v1','producer':PRODUCER,
            'reusable':False,'qualification':False,'repository':request.repository,
            'repository_id':request.repository_id,'pull_request':request.number,
            'candidate':{'base_branch':request.base,'base_commit':request.base_sha,
                'head_branch':request.head,'head_commit':request.head_sha,
                'merge_commit':initial[0],'merge_tree':initial[1],
                'parent_branch':request.parent,'parent_commit':request.parent_sha,
                'profile':request.profile,'classification':request.classification},
            'requested_mode':args.mode,'mode':'verified-empty','reused_suites':[],
            'executed_suites':[],'bounded_projects':[],'execution':None,'parent_evidence':None,
            'ci_selection':selection,'not_selected_suites':list(registry['suites']),
            'conclusion':'success','started_at':started,
            'completed_at':datetime.now(timezone.utc).isoformat().replace('+00:00','Z')}
        result['validation_digest'] = execution.digest(result)
        execution._write_receipt(args.receipt, result)
        return result
    affected = selection is not None and selection["lane"] == "affected-ci"
    native_lane = selection is not None and selection['lane'] == 'native-owner'
    current_platform = None
    bounded = args.mode == "reuse" and request.profile in ("documentation", "tool-dependencies")
    pending = _sync_platform_owner(args, request, candidate, api) if not affected and not bounded else {}
    no_setup = getattr(args, 'expected_native_setup', '')
    if no_setup:
        if selection is None:
            raise ValidationError('no-setup scheduling requires the independently bound source selection')
        scheduling, prepared_native = _native_zero_setup(args, gate, api, config, request,
            candidate, initial, registry, selection)
        if scheduling is None or scheduling != no_setup:
            raise ValidationError('native zero-command setup plan changed; prepared fallback is unavailable')
    if args.mode == "reuse" or affected or native_lane:
        # Keep every branch differential assertion even when all common suites
        # have matching proof. Bounded profiles share this one invocation.
        _candidate_differential(candidate, request, gate, api)
    if native_lane:
        if _ci_selection(args, request, candidate, initial, registry, api) != selection:
            raise ValidationError('native current owner selection changed before proof consumption')
        evidence, reused, ci_required = _native_ci_reuse(args, gate, api, config, request, registry,
            local_tree, selection, native_evidence=prepared_native)
        if not isinstance(evidence, getattr(gate, 'NativePrEvidence', ())) or ci_required:
            raise ValidationError('selected native current owner has no complete proof; second executor is forbidden')
        current_platform = _native_current_platform(args, gate, api, request, candidate, registry, selection, evidence)
        _recheck_native_ci(gate, api, config, request, evidence, registry, local_tree, reused)
        _bounded_junit(args.junit, [])
        external_packages = list(selection['external_package_set'])
        mode = 'native-current-owner'
    elif affected:
        # Recompute after the differential and again at final validation. A
        # preparation output never selects the commands or certifies execution.
        if _ci_selection(args, request, candidate, initial, registry, api) != selection:
            raise ValidationError("affected synchronization selection changed before execution")
        evidence, reused, ci_required = _native_ci_reuse(args, gate, api, config, request, registry, local_tree, selection,
            native_evidence=prepared_native)
        if no_setup and (evidence is None or ci_required):
            raise ValidationError('unprepared selected CI commands cannot run after native proof changed')
        if evidence is None and not reused and ci_required == selection['suites'] \
                and _standalone_ci_names(selection, registry):
            standalone = _native_standalone_ci_owners(api, gate, request, registry, selection)
            if not isinstance(standalone, NativeStandaloneCIProof):
                raise ValidationError('standalone owner is not authenticated native command coverage')
            reused = list(standalone['suites'])
            ci_required = [name for name in selection['suites'] if name not in reused]
        if ci_required:
            execution_path = Path(args.receipt).with_name(Path(args.receipt).name + ".ci-execution.json")
            status, returned = _execute_ci(candidate, initial, selection, registry, args.junit, execution_path,
                suite_names=ci_required)
            observed = _read_execution(execution_path, returned)
            if status != 0:
                raise ValidationError("an affected synchronization suite failed")
            _verify_ci_execution(observed, selection, registry, initial, suite_names=ci_required)
            executed = list(ci_required)
        else:
            # Differential validation actually ran above. There is no unused
            # consumer environment or execution receipt to manufacture.
            _bounded_junit(args.junit, [])
        if reused and standalone is None:
            _recheck_native_ci(gate, api, config, request, evidence, registry, local_tree, reused)
        if set(reused) & set(executed) or set(reused) | set(executed) != set(selection["suites"]):
            raise ValidationError('selected CI proof and execution do not provide exact disjoint coverage')
        external_packages = list(selection["external_package_set"])
        mode = 'native-standalone-ci' if standalone is not None else "affected-ci"
    elif bounded:
        with candidate_environment():
            if request.profile == "tool-dependencies":
                paths = list(request.changed_paths)
                s3 = "script-archive/marketplace/S3Server"
                if any(path == s3 or path.startswith(s3 + "/") for path in paths):
                    packages = gate.package_checks
                    identity = {"full_name": request.repository, "id": request.repository_id}
                    policy_event = {"repository": identity,
                                    "pull_request": {"base": {"ref": request.base, "repo": identity}}}
                    if not packages.activated(policy_event):
                        raise ValidationError("S3 bounded checks are not activated by trusted policy")
                    packages.validate_wiring(candidate)
                    selected = list(gate.tool_dependencies.affected_projects(paths, include_s3=True))
                    external_packages = [s3] if s3 in selected else []
                    projects = [project for project in selected if project != s3]
                else:
                    projects = list(gate.tool_dependencies.affected_projects(paths))
                if not projects and not external_packages:
                    raise ValidationError("bounded tool profile has no validated affected project")
                if projects:
                    gate.tool_dependencies.run(candidate, projects)
        _bounded_junit(args.junit, projects)
        mode = request.profile
    else:
        required = list(registry["suites"])
        if args.mode == "reuse":
            if prepared_native is not None:
                evidence = prepared_native
            else:
                try:
                    evidence = gate.verify_evidence(api, config, request)
                except (gate.EvidenceError, gate.GateError):
                    # Absent/expired/untrusted evidence cannot justify any omission.
                    evidence = None
            if evidence is not None:
                if evidence.get("candidate_inputs") != local_tree:
                    raise ValidationError("local immutable candidate inputs differ from verified API inputs")
                native_parent = isinstance(evidence, getattr(gate, 'NativeParentEvidence', ()))
                try:
                    # Original native schema3 E was independently admitted by
                    # the parent adapter. It is not a consumer-E measurement.
                    actual_environment = evidence['environment'] if native_parent else execution.capture_execution_environment()
                    plan = inputs.plan_reuse(
                        registry, evidence["parent_inputs"], local_tree, evidence["results"]["suites"],
                        evidence["environment"], actual_environment,
                    )
                except (runtime.RuntimeIdentityError, inputs.InputError, KeyError, TypeError):
                    plan = {"reused": [], "required": list(registry["suites"])}
                required, reused = plan["required"], plan["reused"]
        # A native proof covers the common suites independently of this
        # consumer's legacy runtime. With no remaining command or platform
        # owner there is no execution E/receipt to manufacture or measure.
        product = execution.platform_suites(candidate, registry["suites"])
        if no_setup and (not native_parent or required or product or pending):
            raise ValidationError('unprepared shared or platform commands cannot replace the scheduled native proof')
        if native_parent and not required and not product and not pending:
            _bounded_junit(args.junit, [])
        else:
            execution_path = Path(args.receipt).with_name(Path(args.receipt).name + ".execution.json")
            with candidate_environment():
                status, returned = execution.execute(
                    candidate, suite_names=required, include_platform=True, junit=args.junit, receipt_path=execution_path,
                    _platform_owner=lambda: pending,
                )
            observed = _read_execution(execution_path, returned)
            if status != 0:
                raise ValidationError("a selected shared or product suite failed")
            execution.validate_receipt(observed, registry, local_tree)
            if (observed["candidate_commit"], observed["candidate_tree"]) != initial or observed["include_platform"] is not True:
                raise ValidationError("execution receipt is not bound to the exact candidate and product suites")
            expected_product = dict(execution.platform_suites(candidate, registry["suites"]))
            if pending:
                partition = observed.get("platform_selection", {})
                if observed["schema"] != 2 or observed["reusable"] is not False or observed["environment"] is not None \
                        or partition.get("original") != list(expected_product) or partition.get("delegated") != pending:
                    raise ValidationError("pending Android owner differs from the exact observed product partition")
                expected_product = {name: command for name, command in expected_product.items() if name not in pending}
            elif observed["schema"] != 1:
                raise ValidationError("unexpected pending product ownership without authenticated source PR")
            if set(observed["platform_results"]) != set(expected_product) or any(
                observed["platform_results"][name]["command"] != command for name, command in expected_product.items()
            ):
                raise ValidationError("execution receipt omits or alters a declared product suite")
            executed = list(observed["results"])
            reused = [name for name in reused if name not in observed["results"]]
        if reused:
            if not native_parent and observed["reusable"] is not True:
                raise ValidationError("actual execution environment cannot support remaining reused proof")
            if native_parent:
                try:
                    final_evidence = gate.native_parent_evidence(api, config, request)
                except (gate.EvidenceError, gate.GateError) as error:
                    raise ValidationError('original native parent proof became unavailable after candidate execution') from error
                if not isinstance(final_evidence, gate.NativeParentEvidence) or final_evidence != evidence:
                    raise ValidationError('original native parent proof changed after candidate execution')
            try:
                final_plan = inputs.plan_reuse(
                    registry, evidence["parent_inputs"], local_tree, evidence["results"]["suites"],
                    evidence["environment"], evidence['environment'] if native_parent else observed["environment"],
                )
            except (inputs.InputError, KeyError, TypeError) as error:
                raise ValidationError("remaining reusable input identities became unverifiable") from error
            if set(reused) - set(final_plan["reused"]):
                raise ValidationError("actual execution environment no longer matches reused suite proof")
            if gate.parse_time(evidence["expires_at"], "expires_at") <= datetime.now(timezone.utc):
                raise ValidationError("parent suite evidence expired during candidate validation")
        if set(reused) & set(executed) or set(reused) | set(executed) != set(registry["suites"]):
            raise ValidationError("shared suite evidence and execution do not provide exact disjoint coverage")
        mode = "partial-reuse" if reused and executed else "reuse" if reused else "fallback"
    if execution.checkout_identity(candidate) != initial:
        raise ValidationError("candidate source changed during synchronization validation")
    if selection is not None:
        final_selection = _ci_selection(args, request, candidate, initial, registry, api)
        if final_selection != selection:
            raise ValidationError("synchronization selection changed during final validation")
        if affected or native_lane:
            if observed is not None:
                _verify_ci_execution(observed, final_selection, registry, initial, suite_names=ci_required)
            elif ci_required or set(reused) != set(final_selection['suites']):
                raise ValidationError('selected CI work has neither original native proof nor actual execution')
    if native_lane and _native_current_platform(
            args, gate, api, request, candidate, registry, final_selection, evidence) != current_platform:
        raise ValidationError('current Android/Pico source ownership changed during native proof validation')
    final_pending = _sync_platform_owner(args, request, candidate, api) if not affected and not bounded else {}
    if final_pending != pending:
        raise ValidationError("Android sync ownership or source PR labels changed during execution")
    _recheck(api, gate, request)
    if standalone is not None:
        verify_standalone_ci_provenance(dict(standalone),
            verify_standalone_ci_owners(api, gate, request, registry, selection), request)
    identical = isinstance(evidence, getattr(gate, 'NativeExactTreeParentEvidence', ()))
    if identical:
        mode = 'native-exact-tree-parent'
    result = {
        "schema": 1, "producer": PRODUCER, "repository": request.repository,
        "repository_id": request.repository_id, "pull_request": request.number,
        "candidate": {"base_branch": request.base, "base_commit": request.base_sha,
                      "head_branch": request.head, "head_commit": request.head_sha,
                      "merge_commit": initial[0], "merge_tree": initial[1],
                      "parent_branch": request.parent, "parent_commit": request.parent_sha,
                      "profile": request.profile, "classification": request.classification},
        "requested_mode": args.mode, "mode": mode, "reused_suites": reused, "executed_suites": executed,
        "bounded_projects": projects, "execution": observed, "parent_evidence": _parent_provenance(evidence, reused, gate),
        "conclusion": "success", "started_at": started,
        "completed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    if pending:
        result.update(pending_platform_owners=pending, reusable=False, qualification=False)
    if identical:
        result.update(reusable=False, qualification=False)
    if standalone is not None:
        result.update(reusable=False, qualification=False, standalone_owner_evidence=dict(standalone))
    if external_packages:
        # The required project aggregate owns these checks. This consumer does
        # not claim their execution or fabricate a successful JUnit case.
        result["external_package_set"] = external_packages
    if selection is not None:
        result["ci_selection"] = selection
        if affected or native_lane:
            result['not_selected_suites'] = [name for name in registry['suites'] if name not in selection['suites']]
    if isinstance(evidence, getattr(gate, 'NativePrEvidence', ())):
        result.update(reusable=False, qualification=False,
            original_pr_evidence={key: evidence[key] for key in (
                'kind', 'original_commit', 'qualified_at', 'expires_at', 'original_proof', 'requested_suites')},
            original_platform_observation=evidence.get('original_platform_observation'),
            original_platform_commands=evidence.get('platform_commands', []),
            external_platform_owners=current_platform if native_lane else None)
    result["receipt_digest"] = execution.digest(result)
    execution._write_receipt(args.receipt, result)
    return result


def requires_artifact_namespace(selection):
    """Schedule one utility from trusted selection; never change its authority.

    Only select_sync supplies these outputs. Existing validation independently
    rechecks empty/native-zero proofs before it can omit consumer execution.
    """
    def token(value):
        return type(value) is str and len(value) == 71 and value.startswith('sha256:') \
            and all(character in '0123456789abcdef' for character in value[7:])

    if type(selection) is not dict or type(selection.get('schema')) is not int \
            or selection['schema'] != 1 or selection.get('kind') != 'sync-ci-selection' \
            or selection.get('reusable') is not False or not token(selection.get('selection')) \
            or type(selection.get('full_host')) is not bool \
            or selection.get('requested_mode') not in ('reuse', 'fallback'):
        return True
    lane, names = selection.get('lane'), selection.get('suites')
    if lane not in ('verified-empty', 'legacy-bounded', 'affected-ci', 'complete', 'native-owner') \
            or type(names) is not list or any(type(name) is not str or not name \
                or any(character not in 'abcdefghijklmnopqrstuvwxyz0123456789-_' for character in name)
                for name in names) or len(names) != len(set(names)):
        return True
    if lane == 'verified-empty':
        return not (selection['full_host'] is False and not names \
            and selection.get('consumer_setup') == 'none' \
            and selection.get('empty_setup') == selection['selection'] \
            and 'native_setup' not in selection)
    if lane == 'affected-ci' and not names:
        return True
    if lane == 'complete' and selection['full_host'] is not True:
        return True
    if selection.get('consumer_setup', 'required') == 'none':
        return not (lane in ('affected-ci', 'complete', 'native-owner') \
            and token(selection.get('native_setup')) and 'empty_setup' not in selection)
    if lane == 'native-owner':
        return True
    if selection.get('consumer_setup', 'required') != 'required' \
            or 'native_setup' in selection or 'empty_setup' in selection:
        return True
    if lane == 'legacy-bounded':
        return not (selection['full_host'] is False and not names \
            and selection['requested_mode'] == 'reuse' \
            and selection.get('profile') in ('documentation', 'tool-dependencies'))
    if lane == 'complete' or not names:
        return True
    # affected-ci names were already authenticated against the trusted registry.
    # Candidate command variants are retained conservatively if introduced later.
    for name in names:
        for owner in ('project-runner', 'device-control-plane-full'):
            if name == owner or name.startswith(owner + '-candidate-'):
                return True
    return False


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--pull-request", type=int, required=True)
    parser.add_argument("--mode", choices=("reuse", "fallback"), required=True)
    parser.add_argument("--profile", required=True)
    for name in ("base-sha", "head-sha", "merge-sha"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--junit", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--select-only", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--expected-selection", default="")
    parser.add_argument("--expected-native-setup", default="")
    parser.add_argument("--expected-empty-setup", default="")
    args = parser.parse_args(argv)
    try:
        if args.select_only:
            if args.output is None or args.expected_selection or args.expected_native_setup or args.expected_empty_setup:
                raise ValidationError("prerequisite selection requires an output and no claimed selection")
            selected = select_sync(args)
            with args.output.open("a") as output:
                for key, value in (("selection", selected["selection"]), ("lane", selected["lane"]),
                                   ("full_host", str(selected["full_host"]).lower()),
                                   ("consumer_setup", selected.get('consumer_setup', 'required')),
                                   ("native_setup", selected.get('native_setup', '')),
                                   ("empty_setup", selected.get('empty_setup', '')),
                                   ("requires_artifact_namespace", str(requires_artifact_namespace(selected)).lower())):
                    output.write(key + "=" + value + "\n")
            print(json.dumps(selected, sort_keys=True))
            return 0
        result = validate_sync(args)
    except (ValidationError, execution.ExecutionError, inputs.InputError, runtime.RuntimeIdentityError,
            OSError, ValueError, KeyError, TypeError):
        # Errors from API/candidate processes must not expose tokens/selectors.
        print("isolated synchronization validation failed; complete current proof is unavailable", file=sys.stderr)
        return 2
    print(f"Synchronization validation: {len(result['reused_suites'])} reused, "
          f"{len(result['executed_suites'])} shared suites executed; {result['mode']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
