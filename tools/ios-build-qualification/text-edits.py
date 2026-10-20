#!/usr/bin/env python3
"""Retain one actual iOS result after an inert text edit; never execute tests."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tempfile
import time
import zipfile

ROOT = Path(__file__).resolve().parents[2]
REPOSITORY = 'noah-l-frank/overte'
RID = 1319052603
WORKFLOW = '.github/workflows/ios-build-qualification.yml'
CONTEXT = 'ios-device-build'
APP = 15368
PENDING = {'queued', 'in_progress', 'waiting', 'pending', 'requested'}
WAIT_SECONDS = 7200


def require(value, message):
    if not value:
        raise ValueError(message)


def load(name, path):
    source = ROOT / path
    require(source.is_file() and not any(p.is_symlink() for p in (source, *source.parents)
            if p.is_relative_to(ROOT)), 'trusted iOS metadata reader unavailable')
    spec = importlib.util.spec_from_file_location(name, source)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


HOST = load('ios_text_edit_host', 'tools/ios-build-qualification/host.py')
MARKER = load('ios_text_edit_marker', 'tools/repository-checks/metadata_context.py')


def text_edit(event, event_name):
    if event.get('pull_request', {}).get('base', {}).get('ref') != 'apple-ios':
        return False
    if event.get('action') == 'edited':
        return MARKER.event_only(event, event_name)
    # The shared marker deliberately has no readiness case. Do not forge an
    # edited event for it: independently recognize only this native notification.
    pr = event.get('pull_request', {})
    return (event_name == 'pull_request' and event.get('action') == 'ready_for_review'
        and own(event.get('repository')) and type(event.get('number')) is int and event['number'] > 0
        and type(pr.get('number')) is int and pr['number'] == event['number']
        and pr.get('state') == 'open' and pr.get('draft') is False and event.get('changes') in (None, {})
        and all(own(pr.get(side, {}).get('repo')) and isinstance(pr.get(side, {}).get('ref'), str)
                and pr[side]['ref'] and isinstance(pr[side].get('sha'), str) and HOST.SHA.fullmatch(pr[side]['sha'])
                and pr[side]['sha'] != '0' * 40 for side in ('base', 'head')))


def trusted_source():
    """Bind loaded code to the actual protected checkout, not candidate bytes."""
    revision = HOST.git(ROOT, 'rev-parse', '--verify', 'HEAD^{commit}').decode().strip()
    for path in ('tools/ios-build-qualification/text-edits.py', 'tools/ios-build-qualification/host.py',
                 'tools/ios-build-qualification/check.py', 'tools/ios-build-qualification/inputs.py',
                 HOST.POLICY, HOST.TEMPLATE,
                 'tools/repository-checks/metadata_context.py', 'tools/repository-checks/check.py',
                 'tools/test-evidence/source_admission.py'):
        source = HOST.trusted_file(ROOT, path)
        row = HOST.git(ROOT, 'ls-tree', '-z', revision, '--', ':(literal)' + path).split(b'\0')
        require(len(row) == 2 and not row[1], 'trusted iOS metadata closure missing')
        fields, actual = row[0].split(b'\t')
        mode, kind, oid = fields.decode().split()
        raw = source.read_bytes()
        require(actual.decode() == path and mode == '100644' and kind == 'blob'
                and hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest() == oid,
                'trusted iOS metadata closure differs from protected source')
    return revision


def native(event, environment):
    require(text_edit(event, environment.get('GITHUB_EVENT_NAME')), 'not an inert iOS title/body edit')
    number, pr = event['number'], event['pull_request']
    expected = {'GITHUB_ACTIONS': 'true', 'GITHUB_REPOSITORY': REPOSITORY,
        'GITHUB_REPOSITORY_ID': str(RID), 'GITHUB_EVENT_NAME': 'pull_request',
        'GITHUB_REF': f'refs/pull/{number}/merge', 'GITHUB_BASE_REF': 'apple-ios',
        'GITHUB_HEAD_REF': pr['head']['ref'], 'GITHUB_RUN_ATTEMPT': '1',
        'RUNNER_ENVIRONMENT': 'github-hosted', 'ImageOS': 'ubuntu24'}
    require(all(environment.get(k) == v for k, v in expected.items())
            and environment.get('GITHUB_JOB') in {'route', 'ios-device-build'}
            and re.fullmatch(r'[1-9][0-9]*', environment.get('GITHUB_RUN_ID', '')),
            'iOS text retention requires its original native role')
    source = environment.get('GITHUB_SHA', '')
    require(HOST.SHA.fullmatch(source) and source != '0' * 40
            and environment.get('GITHUB_WORKFLOW_SHA') == source
            and environment.get('GITHUB_WORKFLOW_REF') == REPOSITORY + '/' + WORKFLOW + '@' + expected['GITHUB_REF'],
            'iOS text retention native source differs')
    return int(environment['GITHUB_RUN_ID']), source


def own(value):
    return isinstance(value, dict) and value.get('full_name') == REPOSITORY and type(value.get('id')) is int and value['id'] == RID


def utcnow():
    return datetime.now(timezone.utc)


def complete(value, key, count='total_count'):
    rows = value.get(key)
    require(type(rows) is list and type(value.get(count)) is int and value[count] == len(rows)
            and len(rows) <= 100 and all(type(r) is dict for r in rows), 'incomplete iOS native inventory')
    return rows


def run_identity(row, identifier, workflow, event, head):
    require(type(row.get('id')) is int and row['id'] == identifier and row.get('workflow_id') == workflow
            and row.get('path') == WORKFLOW and row.get('event') == 'pull_request'
            and row.get('head_sha') == head and row.get('head_branch') == event['pull_request']['head']['ref']
            and type(row.get('run_attempt')) is int and row['run_attempt'] == 1
            and own(row.get('repository')) and own(row.get('head_repository'))
            and type(row.get('check_suite_id')) is int and row['check_suite_id'] > 0
            and row.get('html_url') == f'https://github.com/{REPOSITORY}/actions/runs/{identifier}',
            'iOS original run/source/attempt differs')
    associated = row.get('pull_requests')
    require(type(associated) is list and len(associated) == 1 and associated[0].get('number') == event['number']
            and all(associated[0].get(side, {}).get('sha') == event['pull_request'][side]['sha']
                    and associated[0].get(side, {}).get('ref') == event['pull_request'][side]['ref']
                    and type(associated[0].get(side, {}).get('repo', {}).get('id')) is int
                    and associated[0][side]['repo']['id'] == RID
                    and associated[0][side]['repo'].get('url') == 'https://api.github.com/repos/' + REPOSITORY
                    for side in ('base', 'head')),
            'iOS original PR association differs')
    HOST.stamp(row.get('created_at'))


def snapshot(event, environment, candidate, *, get=None, policy_root=ROOT):
    """Fresh source/candidate/run bookends, also while the original is pending."""
    get = HOST._api_get if get is None else get
    current_id, source = native(event, environment)
    prefix = 'repos/' + REPOSITORY + '/'
    require(own(get('repos/' + REPOSITORY)), 'foreign iOS metadata repository')
    default = trusted_source()
    require(get(prefix + 'git/ref/heads/main').get('object', {}).get('sha') == default,
            'iOS metadata protected source moved')
    # This is the same existing API/Git merge-base resolver used by normal iOS qualification.
    current = HOST.fresh_context(event, candidate, source, policy_root=policy_root)
    generation, _ = HOST.resolve(candidate, source, policy_root=policy_root)
    approved = {'host-v1', HOST.COMPILER_DATA_GENERATION, HOST.COMPILER_PR_DATA_GENERATION}
    require(generation in approved
            and HOST.resolve(candidate, current['base'], policy_root=policy_root)[0] in approved,
            'iOS text retention requires a reviewed owner recipe on both sides')
    planned = HOST.route(event, candidate, source, policy_root=policy_root)
    live = get(prefix + 'pulls/' + str(event['number']))
    require(all(live.get(k) == event['pull_request'].get(k) for k in ('title', 'body')),
            'iOS text edit no longer describes the current PR')
    require(event['action'] != 'ready_for_review' or live.get('draft') is False,
            'iOS readiness notification is no longer current')
    workflow = get(prefix + 'actions/workflows/ios-build-qualification.yml')
    require(type(workflow.get('id')) is int and workflow['id'] > 0 and workflow.get('path') == WORKFLOW
            and workflow.get('name') == 'iOS device build qualification' and workflow.get('state') == 'active',
            'iOS qualification workflow registration differs')
    run = get(prefix + 'actions/runs/' + str(current_id))
    attempt = get(prefix + 'actions/runs/' + str(current_id) + '/attempts/1')
    for row in (run, attempt):
        run_identity(row, current_id, workflow['id'], event, current['head'])
        require(row.get('status') in PENDING, 'iOS metadata consumer is not active')
    inventory = complete(get(prefix + f'actions/workflows/{workflow["id"]}/runs?event=pull_request&head_sha={current["head"]}&per_page=100'), 'workflow_runs')
    related = [r for r in inventory if r.get('head_branch') == current['headRef']]
    require(len({r.get('id') for r in related}) == len(related) and any(r.get('id') == current_id for r in related),
            'iOS metadata consumer missing or duplicated')
    for row in related:
        run_identity(row, row.get('id'), workflow['id'], event, current['head'])
    previous = [r for r in related if r['id'] < current_id]
    require(previous, 'original iOS qualification has not registered')
    require(all(r.get('status') != 'completed' or r.get('conclusion') == 'success' for r in previous),
            'an earlier same-source iOS owner did not succeed')
    original_id = min(previous, key=lambda r: (HOST.stamp(r['created_at']), r['id']))['id']
    original = get(prefix + 'actions/runs/' + str(original_id))
    original_attempt = get(prefix + 'actions/runs/' + str(original_id) + '/attempts/1')
    for row in (original, original_attempt):
        run_identity(row, original_id, workflow['id'], event, current['head'])
    require(original['status'] == original_attempt['status'] and original.get('conclusion') == original_attempt.get('conclusion')
            and HOST.stamp(original['created_at']) < HOST.stamp(run['created_at']),
            'original iOS status or chronology differs')
    return {'context': current, 'default': default, 'plan': planned, 'current_run_id': current_id,
            'original_run_id': original_id, 'original': original, 'original_attempt': original_attempt,
            'workflow_id': workflow['id']}


def artifact_bytes(endpoint):
    """Read only the authenticated bounded archive, preserving the raw digest."""
    token = os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN')
    executable = Path('/usr/bin/gh')
    info = executable.stat()
    require(token and stat.S_ISREG(info.st_mode) and info.st_uid == 0 and not info.st_mode & 0o022,
            'trusted iOS artifact reader unavailable')
    with tempfile.TemporaryDirectory(prefix='ios-original-artifact-') as directory:
        result = subprocess.run([str(executable), 'api', '--hostname', 'github.com', '--method', 'GET', endpoint],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30,
            env={'PATH':'/usr/bin:/bin', 'LANG':'C.UTF-8', 'GH_TOKEN':token, 'HOME':directory,
                 'GH_CONFIG_DIR':directory, 'GH_PROMPT_DISABLED':'1'})
    require(result.returncode == 0 and 0 < len(result.stdout) <= 2_000_000 and len(result.stderr) <= 65536,
            'original iOS evidence archive unavailable')
    return result.stdout


def original_success(observed, *, get=None, read=artifact_bytes):
    get = HOST._api_get if get is None else get
    run, context, plan = observed['original'], observed['context'], observed['plan']
    identifier, head = observed['original_run_id'], context['head']
    require(run.get('status') == 'completed' and run.get('conclusion') == 'success',
            'original iOS qualification did not succeed')
    prefix = 'repos/' + REPOSITORY + '/'
    jobs = complete(get(prefix + f'actions/runs/{identifier}/attempts/1/jobs?per_page=100'), 'jobs')
    require(len({j.get('id') for j in jobs}) == len(jobs) and all(type(j.get('id')) is int and j['id'] > 0
            and j.get('run_id') == identifier and type(j.get('run_attempt')) is int and j['run_attempt'] == 1
            and j.get('head_sha') == head and j.get('status') == 'completed'
            and j.get('conclusion') in {'success', 'skipped'} for j in jobs), 'original iOS jobs differ or did not succeed')
    canonical = [j for j in jobs if j.get('name') == CONTEXT]
    require(len(canonical) == 1 and canonical[0].get('conclusion') == 'success', 'original iOS canonical job missing')
    canonical = canonical[0]
    steps = canonical.get('steps', [])
    selected = [s for s in steps if s.get('name') == 'Require selected jobs and verify exact IPA provenance']
    uploads = [s for s in steps if s.get('name') == 'Upload qualified build evidence']
    require(len(selected) == 1 and selected[0].get('status') == 'completed' and selected[0].get('conclusion') == 'success'
            and len(uploads) == 1 and uploads[0].get('status') == 'completed' and uploads[0].get('conclusion') == 'success',
            'original iOS job did not verify and upload provenance')
    check_url = f'https://api.github.com/repos/{REPOSITORY}/check-runs/{canonical["id"]}'
    require(canonical.get('check_run_url') == check_url, 'original iOS native check URL differs')
    check = get(prefix + 'check-runs/' + str(canonical['id']))
    require(check.get('id') == canonical['id'] and check.get('name') == CONTEXT and check.get('head_sha') == head
            and check.get('app', {}).get('id') == APP and check.get('check_suite', {}).get('id') == run['check_suite_id']
            and check.get('details_url') == canonical.get('html_url')
            and check.get('status') == 'completed' and check.get('conclusion') == 'success'
            and all(check.get(k) == canonical.get(k) for k in ('started_at', 'completed_at')),
            'original iOS native App/check differs')
    artifacts = complete(get(prefix + f'actions/runs/{identifier}/artifacts?per_page=100'), 'artifacts')
    matches = [a for a in artifacts if a.get('name') == f'ios-build-evidence-{identifier}-1']
    require(len(matches) == 1, 'original iOS evidence missing or ambiguous')
    artifact = matches[0]
    require(type(artifact.get('id')) is int and artifact['id'] > 0 and artifact.get('expired') is False
            and artifact.get('workflow_run', {}).get('id') == identifier
            and artifact.get('workflow_run', {}).get('head_sha') == head
            and type(artifact.get('size_in_bytes')) is int and 0 < artifact['size_in_bytes'] <= 2_000_000
            and re.fullmatch(r'sha256:[0-9a-f]{64}', artifact.get('digest', '')),
            'original iOS artifact identity differs')
    require(HOST.stamp(artifact.get('created_at')) <= utcnow() < HOST.stamp(artifact.get('expires_at')),
            'original iOS artifact is stale or not yet valid')
    raw = read(prefix + f'actions/artifacts/{artifact["id"]}/zip')
    require('sha256:' + hashlib.sha256(raw).hexdigest() == artifact['digest'], 'original iOS archive digest differs')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        entries = archive.infolist()
        require(len(entries) == 1 and entries[0].filename == 'ios-build-evidence.json'
                and not entries[0].is_dir() and entries[0].file_size <= 100_000
                and not stat.S_ISLNK(entries[0].external_attr >> 16), 'unexpected original iOS archive members')
        def unique(pairs):
            result = {}
            for key, value in pairs:
                require(key not in result, 'duplicate original iOS evidence field')
                result[key] = value
            return result
        report = json.loads(archive.read(entries[0]), object_pairs_hook=unique)
    expected = {'schema':1, 'repository':REPOSITORY, 'repositoryId':RID, 'context':CONTEXT,
        'sourceRevision':context['candidate'], 'sourceTree':plan['tree'], 'baseRevision':context['base'],
        'headRevision':head, 'runId':identifier, 'runAttempt':1, 'checks':'passed', 'reason':plan['reason']}
    require(all(type(report.get(k)) is type(v) and report[k] == v for k, v in expected.items()),
            'original iOS evidence does not bind this exact B/H/M/tree')
    host = report.get('hostSelection', {})
    require(host.get('generation') == plan['generation'] and host.get('plan') == plan['selection']
            and host.get('inputs') == plan['host_inputs']
            and host.get('applicationBuildRequired') is (plan['required'] == 'true')
            and host.get('iosHostRequired') is (plan['host_required'] == 'true'), 'original iOS selection differs')
    if host['iosHostRequired']:
        require(host.get('producer') == HOST.verify_execution(jobs, run, identifier, 1, head),
                'original iOS host provenance differs')
    else:
        require(host.get('producer') is None, 'unexpected original iOS host proof')
    if host['applicationBuildRequired']:
        checks = load('ios_text_edit_build', 'tools/ios-build-qualification/check.py')
        require(report.get('producer') == checks.verify_build_execution(jobs, identifier, 1, head)
                and report.get('ipa') == 'verified' and type(report.get('artifact')) is dict
                and re.fullmatch(r'[0-9a-f]{64}', report['artifact'].get('sha256', '')),
                'original iOS application provenance differs')
    else:
        require(report.get('producer') is None and report.get('artifact') is None and report.get('ipa') == 'not-required',
                'unexpected original iOS application proof')
    require(HOST.stamp(run['run_started_at']) <= HOST.stamp(canonical['started_at'])
            <= HOST.stamp(selected[0]['started_at']) < HOST.stamp(selected[0]['completed_at'])
            <= HOST.stamp(canonical['completed_at']), 'original iOS chronology differs')
    return {'original_run_id':identifier, 'original_canonical_job_id':canonical['id'],
            'original_artifact_id':artifact['id'], 'original_artifact_digest':artifact['digest']}


def route_fields(observed):
    """The existing workflow outputs schedule zero work; they certify no test."""
    return {**observed['plan'], 'required':'false', 'host_required':'false', 'reason':'retained-original-ios-result'}


def result(event, environment, candidate, needs, *, get=None, read=artifact_bytes, clock=time.monotonic,
           sleep=time.sleep, wait_seconds=WAIT_SECONDS, policy_root=ROOT):
    require(environment.get('GITHUB_JOB') == 'ios-device-build', 'only the native iOS canonical role retains results')
    require(type(wait_seconds) in (int, float) and 0 <= wait_seconds <= WAIT_SECONDS, 'invalid iOS result wait bound')
    started = clock()
    first = snapshot(event, environment, candidate, get=get, policy_root=policy_root)
    require(type(needs) is dict and set(needs) == {'route', 'host', 'qt', 'client'}
            and needs['route'].get('result') == 'success'
            and needs['route'].get('outputs') == route_fields(first)
            and all(needs[name].get('result') == 'skipped' for name in ('host', 'qt', 'client')),
            'iOS metadata callback must execute no host/Qt/client jobs')
    while True:
        observed = snapshot(event, environment, candidate, get=get, policy_root=policy_root)
        require(all(observed[k] == first[k] for k in ('context', 'default', 'plan', 'current_run_id', 'original_run_id', 'workflow_id')),
                'iOS original or protected context changed while waiting')
        state = observed['original']['status']
        require(clock() - started <= wait_seconds, 'original iOS result wait expired')
        if state == 'completed':
            proof = original_success(observed, get=get, read=read)
            closing = snapshot(event, environment, candidate, get=get, policy_root=policy_root)
            require(all(closing[k] == observed[k] for k in ('context', 'default', 'plan', 'current_run_id', 'original_run_id', 'workflow_id'))
                    and closing['original']['status'] == 'completed' and closing['original'].get('conclusion') == 'success'
                    and original_success(closing, get=get, read=read) == proof, 'original iOS success changed before acceptance')
            require(clock() - started <= wait_seconds, 'original iOS result admission exceeded its bound')
            return {'schema':1, 'kind':'ios-text-edit-original-result', 'qualification':False, 'new_E':False,
                    'repository':REPOSITORY, 'repositoryId':RID, 'context':CONTEXT,
                    'tests_executed':0, 'application_builds_executed':0, **proof, **observed['context']}
        require(state in PENDING, 'unknown original iOS state')
        remaining = wait_seconds - (clock() - started)
        require(remaining > 0, 'original iOS result wait expired')
        sleep(min(15, remaining))


