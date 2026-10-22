#!/usr/bin/env python3
"""Reuse successful immutable task execution, never a cache hit or job title.

Discovery is optional and bounded. Missing, expired or incompatible evidence
causes execution. Supplied evidence is authenticated again before a command is
skipped. Only content-scoped tasks with the same observed runtime can match.
Mutable npm vulnerability data is always queried again.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import time
import stat

import pr_ci_context as C
import pr_ci_observer as O
import pr_ci_transport as T

PARENTS = {"apple-main": "main", "apple-ios": "apple-main",
           "android-main": "main", "android-phone": "android-main",
           "android-vr": "android-main", "android-vr-pico": "android-vr"}
MAX_AGE = 14 * 86400


def artifact_name(context, lane, project=""):
    C.require(lane in {"host", "npm"}, "unsupported reusable command owner")
    suffix = lane if lane == "host" else "npm-" + hashlib.sha256(project.encode()).hexdigest()
    return f"pr-ci-tasks-{context['run_id']}-{context['run_attempt']}-{suffix}"


def _bytes(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def observed_runtime(prepared_roots):
    """Measure the actual mounted host/tool packages, not just requested versions."""
    def run(argv):
        return subprocess.check_output(argv, timeout=30, stderr=subprocess.PIPE).decode().strip()
    C.require(platform.system() == "Linux", "reusable host runtime must be Linux")
    packages = (run(["/usr/bin/dpkg-query", "-W", "-f=${binary:Package}=${Version}:${Architecture}\\n"])
        if Path('/usr/bin/dpkg-query').is_file() else run(['/usr/bin/rpm', '-qa', '--qf', '%{NAME}=%{VERSION}-%{RELEASE}:%{ARCH}\\n']))
    facts = {"system": platform.system(), "machine": platform.machine(),
             "uid": os.getuid(), "gid": os.getgid(),
             "kernel": platform.release(), "os_release": Path('/etc/os-release').read_text(),
             "runner_image": {k: os.environ.get(k, "") for k in ("ImageOS", "ImageVersion")},
             "packages": sorted(packages.splitlines()), "python": sys.version, "python_binary": _bytes(sys.executable),
             "roots": []}
    # Hash prepared tools and the invoked virtual environment as ordinary files.
    # Paths are relative within each root so per-run scratch names are irrelevant.
    import pr_ci_run
    roots = [str(p) for p in pr_ci_run._roots(prepared_roots)]
    def portable(value):
        for index, root in sorted(enumerate(roots), key=lambda row: len(row[1]), reverse=True):
            value = re.sub(re.escape(root) + r'''(?=$|[/\s'\"])''',
                           lambda _: f'<root:{index}>', value)
        return value
    for root in roots:
        base = Path(root)
        # System Python is represented by its binary, OS package inventory and
        # runner image. A prepared venv/tool bundle must be measured completely.
        if root in {"/usr", "/usr/local"}:
            continue
        entries = []
        for path in sorted(base.rglob('*')):
            if path.is_symlink():
                entries.append([str(path.relative_to(base)), "link", portable(os.readlink(path))])
            elif path.is_file() and path.suffix != '.pyc':
                C.require(len(entries) < 200_000, "prepared runtime exceeds inventory bound")
                digest = (_bytes(path) if path.name != 'pyvenv.cfg' else
                          hashlib.sha256(portable(path.read_text()).encode()).hexdigest())
                entries.append([str(path.relative_to(base)), "file", stat.S_IMODE(path.stat().st_mode), digest])
        facts['roots'].append({"files": len(entries), "digest": C.digest(entries)})
    return {"schema": 1, "digest": C.digest(facts)}


def matches(result, task, runtime):
    return (type(result) is dict and result.get('result') == 'success'
            and result.get('task') == task['id']
            and result.get('input_key') == task['reuse_key']
            and result.get('command') == task['command']
            and result.get('runtime') == runtime)


def same_context(left, right):
    fields = (*C.FIXED_FIELDS, 'run_id', 'run_attempt', 'controller', 'caller_source', 'execution_event')
    return (type(left) is dict and type(right) is dict
            and all(type(left.get(k)) is type(right.get(k)) and left.get(k) == right.get(k) for k in fields))


class Evidence:
    """Read-only provenance boundary, shared by execution and final acceptance."""
    def __init__(self, api, context, recompute):
        self.api, self.context, self.recompute = api, context, recompute
        self.loaded = {}
        self.command_records = {}

    def ancestors(self):
        result, target = [], self.context['target']
        while target in PARENTS:
            target = PARENTS[target]
            result.append(target)
        return result

    def load(self, run_id):
        C.require(type(run_id) is int and run_id > 0, 'invalid reusable execution run')
        if run_id in self.loaded:
            return self.loaded[run_id]
        api = self.api
        run = api.get('actions/runs/' + str(run_id))
        C.require(run.get('status') == 'completed' and run.get('conclusion') == 'success',
                  'reusable execution was not completely successful')
        created = datetime.fromisoformat(run['created_at'].replace('Z', '+00:00')).timestamp()
        C.require(0 <= time.time() - created <= MAX_AGE, 'reusable execution expired')
        workflow = api.get('actions/workflows/repository-checks.yml')
        artifacts = api.pages(f'actions/runs/{run_id}/artifacts', field='artifacts')
        attempt = run.get('run_attempt')
        name = f'pr-ci-{run_id}-{attempt}'
        choices = [a for a in artifacts if a.get('name') == name]
        C.require(len(choices) == 1, 'missing or ambiguous successful execution record')
        record = T.read_artifact(api, choices[0], expected_name=name,
            run_id=run_id, run_attempt=attempt, head_sha=run['head_sha'])
        source = record.get('context', {})
        C.require(source.get('target') in self.ancestors(), 'reusable source is not an owning ancestor')
        C.require(source.get('execution_event') == 'pull_request', 'manual runs cannot enroll reusable PR evidence')
        T.validate_run(run, source, workflow_id=workflow['id'],
                       controller=source['controller'], execution_event='pull_request')
        suite = api.get('check-suites/' + str(run['check_suite_id']))
        C.require(suite.get('id') == run['check_suite_id']
                  and suite.get('head_sha') == source['head']
                  and suite.get('repository', {}).get('id') == C.REPOSITORY_ID
                  and suite.get('app', {}).get('id') == 15368,
                  'reusable execution check suite or application differs')
        pr = api.get('pulls/' + str(source['number']))
        C.require(pr.get('state') == 'closed' and pr.get('merged') is True
                  and pr.get('base', {}).get('ref') == source['target']
                  and pr.get('head', {}).get('sha') == source['head'],
                  'reusable producer was not integrated into its owning target')
        for side in ('base', 'head'):
            C.repository(pr[side]['repo'])
        merged = C.sha(pr.get('merge_commit_sha'))
        comparison = api.get('compare/' + merged + '...' + self.context['head'])
        C.require(comparison.get('status') in {'ahead', 'identical'}
                  and comparison.get('base_commit', {}).get('sha') == merged
                  and comparison.get('merge_base_commit', {}).get('sha') == merged,
                  'reusable producer is not in the propagated protected history')
        C.require(C.immutable_merge(api, source['original_merge'], source['base'], source['head'])
                  == source['tree'], 'reusable source merge/tree differs')
        integrated = api.get('git/commits/' + merged)
        C.require(integrated.get('sha') == merged and integrated.get('tree', {}).get('sha') == source['tree'],
                  'integrated parent tree differs from its tested source')
        expected, actual, trusted = self.recompute(api, source)
        expected['controller'] = source['controller']
        base = api.get('git/commits/' + source['base'])
        # recompute exposes complete immutable trees; authenticate the original
        # controller against current protected controls as well as candidate.
        import pr_ci
        controller_commit = api.get('git/commits/' + C.sha(source['controller']))
        T.validate_sources(pr_ci.remote_tree(api, controller_commit['tree']['sha']), trusted,
                           protected_base=pr_ci.remote_tree(api, base['tree']['sha']))
        T.validate_sources(actual, trusted,
                           protected_base=pr_ci.remote_tree(api, base['tree']['sha']))
        jobs = api.pages(f'actions/runs/{run_id}/attempts/{attempt}/jobs', field='jobs')
        final = [j for j in jobs if j.get('name') == 'required-ci']
        C.require(len(final) == 1 and final[0].get('status') == 'completed'
                  and final[0].get('conclusion') == 'success', 'reusable merge gate did not succeed')
        T.validate_jobs(jobs, O.expected_owners(expected), plan=expected, context=source)
        O.validate_record(record, expected, source, run_id=run_id, run_attempt=attempt)
        C.require(api.get('actions/runs/' + str(run_id)) == run
                  and api.get('check-suites/' + str(run['check_suite_id'])) == suite
                  and api.get('pulls/' + str(source['number'])) == pr,
                  'reusable source changed during authentication')
        result = (source, expected, artifacts, run)
        self.loaded[run_id] = result
        return result

    def command_results(self, run_id, lane, project=''):
        key = (run_id, lane, project)
        if key in self.command_records:
            return self.command_records[key]
        source, plan, artifacts, run = self.load(run_id)
        name = artifact_name(source, lane, project)
        choices = [a for a in artifacts if a.get('name') == name]
        C.require(len(choices) == 1, 'reusable command receipt unavailable')
        record = T.read_artifact(self.api, choices[0], expected_name=name,
            run_id=run_id, run_attempt=source['run_attempt'], head_sha=source['head'])
        C.require(record.get('kind') == 'pr-ci-task-results-v1'
                  and same_context(record.get('context'), source) and record.get('lane') == lane
                  and record.get('project') == project and type(record.get('results')) is list,
                  'reusable command receipt context changed')
        tasks = {t['id']: t for t in plan['tasks'] if t['kind'] == lane
                 and (not project or t['id'] == 'npm:' + project)}
        ids = [r.get('task') for r in record['results']]
        C.require(len(ids) == len(set(ids)) and set(ids) == set(tasks),
                  'reusable command receipt is incomplete or duplicated')
        C.require(all(r.get('input_key') == tasks[r['task']]['reuse_key']
                      and r.get('command') == tasks[r['task']]['command']
                      and r.get('result') == 'success' for r in record['results']),
                  'reusable command differs from its authenticated original plan')
        self.command_records[key] = record['results']
        return record['results']

    def command(self, proof, task, runtime, lane, project=''):
        C.require(type(runtime) is dict and runtime.get('schema') == 1
                  and type(runtime.get('digest')) is str
                  and re.fullmatch('[0-9a-f]{64}', runtime['digest']), 'unmeasured command runtime')
        C.require(type(proof) is dict and set(proof) == {'run_id', 'run_attempt'}, 'invalid command origin')
        source, _, _, run = self.load(proof['run_id'])
        C.require(proof['run_attempt'] == run['run_attempt'], 'reusable attempt changed')
        rows = self.command_results(proof['run_id'], lane, project)
        result = next((r for r in rows if r['task'] == task['id']), None)
        C.require(matches(result, task, runtime) and result.get('executed') is True
                  and result.get('origin') is None, 'no matching original command execution')
        return dict(proof)

    def discover(self, tasks, runtime, lane, project=''):
        context, api = self.context, self.api
        if context.get('head_ref') != PARENTS.get(context.get('target')):
            return {}
        pulls = api.pages('commits/' + context['head'] + '/pulls')
        parents = [p for p in pulls if p.get('merged_at') and p.get('merge_commit_sha') == context['head']
                   and p.get('base', {}).get('ref') == context['head_ref']]
        if len(parents) != 1:
            return {}
        listing = api.pages('actions/workflows/repository-checks.yml/runs?event=pull_request&head_sha='
                            + parents[0]['head']['sha'], field='workflow_runs')
        selected = sorted((r for r in listing if r.get('status') == 'completed'
                           and r.get('conclusion') == 'success'), key=lambda r:r['id'], reverse=True)[:2]
        for run in selected:
            rows = self.command_results(run['id'], lane, project)
            found = {}
            for task in tasks:
                row = next((r for r in rows if matches(r, task, runtime)), None)
                if row:
                    origin = row.get('origin') or {'run_id':run['id'], 'run_attempt':run['run_attempt']}
                    found[task['id']] = self.command(origin, task, runtime, lane, project)
            if found:
                return found
        return {}


def verify_current(api, context, plan, artifacts, recompute):
    """Independently reauthenticate every skipped command in the final gate."""
    evidence = Evidence(api, context, recompute)
    for lane, project in [('host', ''), *[('npm', p) for p in plan['npm_projects']]]:
        tasks = [t for t in plan['tasks'] if t['kind'] == lane
                 and (not project or t['id'] == 'npm:' + project)]
        if not tasks:
            continue
        name = artifact_name(context, lane, project)
        choices = [a for a in artifacts if a.get('name') == name]
        C.require(len(choices) == 1, 'selected task execution receipt unavailable')
        record = T.read_artifact(api, choices[0], expected_name=name,
            run_id=context['run_id'], run_attempt=context['run_attempt'], head_sha=context['head'])
        C.require(record.get('kind') == 'pr-ci-task-results-v1'
                  and same_context(record.get('context'), context)
                  and record.get('lane') == lane and record.get('project') == project
                  and type(record.get('results')) is list, 'selected task receipt identity differs')
        rows = record['results'];ids = [r.get('task') for r in rows]
        C.require(len(ids) == len(set(ids)) and set(ids) == {t['id'] for t in tasks},
                  'selected task receipt is incomplete or duplicated')
        for task in tasks:
            row = next(r for r in rows if r['task'] == task['id'])
            C.require(matches(row, task, row.get('runtime')), 'selected task receipt command differs')
            if row.get('executed') is True:
                C.require(row.get('origin') is None, 'executed command cannot claim another origin')
            else:
                C.require(row.get('executed') is False and type(row.get('runtime')) is dict
                          and row['runtime'].get('schema') == 1
                          and type(row['runtime'].get('digest')) is str
                          and len(row['runtime']['digest']) == 64,
                          'reused command has no observed runtime')
                evidence.command(row.get('origin'), task, row['runtime'], lane, project)
