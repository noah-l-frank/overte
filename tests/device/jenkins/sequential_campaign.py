#!/usr/bin/env python3
"""Run each frozen catalog target once through the current reserved-device runner.

Private campaign manifest v1 binds a separately staged source tree/archive, APK,
SOURCE_BINDING receipt and all per-target adapter/environment files. This glue
creates no fixtures, installs no APK and weakens no capability/identity checks.
Each target gets one invocation with its reviewed existing setup rows. Raw
outputs stay private; only fixed IDs/statuses/digests enter staged JSON/JUnit.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import signal
import stat
import subprocess
import sys
import time
import traceback
import uuid
import xml.etree.ElementTree as ET

HEX = re.compile(r'[0-9a-f]{64}')
IDENTIFIER = re.compile(r'[a-z0-9][a-z0-9-]{0,79}')


class CampaignError(ValueError):
    """A fixed, public-safe failure code; private exception text stays private."""


def require(value, code):
    if not value:
        raise CampaignError(code)


def digest(path):
    """Hash actual regular-file bytes without following links or accepting drift."""
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode), 'input-not-regular')
        value = hashlib.file_digest(stream, 'sha256').hexdigest()
        after = os.fstat(stream.fileno())
        signature = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        require(signature(before) == signature(after) == signature(Path(path).lstat()), 'input-changed')
        return value


def inside(root, relative):
    require(type(relative) is str and relative and '\\' not in relative, 'invalid-relative-path')
    parts = PurePosixPath(relative)
    require(not parts.is_absolute() and all(p not in ('.', '..') for p in parts.parts), 'invalid-relative-path')
    result = root.joinpath(*parts.parts)
    require(result.resolve() == result.absolute() and result.is_relative_to(root), 'input-path-escaped')
    return result


def checked_file(root, reference):
    require(type(reference) is dict and set(reference) == {'path', 'sha256'}
            and type(reference['sha256']) is str and HEX.fullmatch(reference['sha256']), 'invalid-file-reference')
    path = inside(root, reference['path'])
    require(digest(path) == reference['sha256'], 'input-hash-mismatch')
    return path


def read_json(path, expected=None):
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_size <= 16 * 1024 * 1024, 'invalid-json-input-file')
        data = stream.read(16 * 1024 * 1024 + 1)
        after = os.fstat(stream.fileno())
        signature = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        require(signature(before) == signature(after) == signature(Path(path).lstat())
                and len(data) == before.st_size, 'json-input-changed')
    require(expected is None or hashlib.sha256(data).hexdigest() == expected, 'json-input-hash-mismatch')
    return json.loads(data)


def atomic_json(path, value):
    require(path.parent.resolve() == path.parent.absolute(), 'output-path-escaped')
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if path.exists():
        require(stat.S_ISREG(path.lstat().st_mode) and not path.is_symlink(), 'unsafe-output')
    temporary = path.with_name(path.name + '.' + uuid.uuid4().hex + '.tmp')
    with os.fdopen(os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'w') as output:
        json.dump(value, output, indent=2, sort_keys=True)
        output.write('\n')
        output.flush()
        os.fsync(output.fileno())
    os.replace(temporary, path)


def current_runner(source):
    """Use the original catalog validator and command resolver, not copies."""
    sys.dont_write_bytecode = True
    original = list(sys.path)
    names = ('adapter_client', 'execution_identity', 'contracts')
    previous = {name: sys.modules.pop(name) for name in names if name in sys.modules}
    sys.path.insert(0, str(source / 'tests/device'))
    try:
        spec = importlib.util.spec_from_file_location('campaign_current_runner', source / 'tests/device/run.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path[:] = original
        for name in names:
            sys.modules.pop(name, None)
        sys.modules.update(previous)


def process_identity(pid):
    try:
        raw = Path(f'/proc/{pid}/stat').read_text()
        fields = raw[raw.rfind(')') + 2:].split()
        # Birth time is stable across reparenting and setsid; PPID/PGID are not.
        return fields[19], fields[0], int(fields[1])
    except (OSError, ValueError, IndexError):
        return None


def collect_children(pid, owned, parent=None):
    identity = process_identity(pid)
    if identity is None:
        return
    if pid in owned:
        if owned[pid] != identity[0]:
            return  # A reused PID never acquires the old child's authority.
    else:
        if parent is None or identity[2] != parent:
            return
        owned[pid] = identity[0]
    try:
        children = Path(f'/proc/{pid}/task/{pid}/children').read_text().split()
    except OSError:
        return
    for child in children:
        child = int(child)
        collect_children(child, owned, parent=pid)


def live_owned(owned):
    return [pid for pid, token in owned.items()
            if (actual := process_identity(pid)) is not None and actual[0] == token and actual[1] != 'Z']


def adopted_children(owned):
    # command_owner admits only a child-free, single-threaded standalone scope.
    # Thus every newly adopted child here belongs to this one runner invocation.
    children = Path(f'/proc/self/task/{os.getpid()}/children')
    for pid in children.read_text().split():
        collect_children(int(pid), owned, parent=os.getpid())


def owner_module(source):
    spec = importlib.util.spec_from_file_location('campaign_command_owner', source / 'tests/device/run_control_plane_tests.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def stop_owned(owned):
    for sig, seconds in ((signal.SIGTERM, 5), (signal.SIGKILL, 5)):
        for pid in reversed(live_owned(owned)):
            try:
                os.kill(pid, sig)
            except ProcessLookupError:
                pass
        deadline = time.monotonic() + seconds
        while live_owned(owned) and time.monotonic() < deadline:
            time.sleep(0.05)
        if not live_owned(owned):
            return
    require(not live_owned(owned), 'owned-process-survived')


def execute(argv, cwd, env, timeout, log):
    """One runner at a time; retain/terminate only actually owned host children."""
    owned = {}
    require(sys.platform.startswith('linux'), 'linux-command-ownership-required')
    with owner_module(cwd).command_owner() as reap, os.fdopen(
            os.open(log, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb') as output:
        process = subprocess.Popen(argv, cwd=cwd, env=env, stdout=output, stderr=subprocess.STDOUT,
                                   start_new_session=True)
        collect_children(process.pid, owned, parent=os.getpid())
        deadline = time.monotonic() + timeout
        timed_out = False
        try:
            while process.poll() is None:
                collect_children(process.pid, owned)
                adopted_children(owned)
                if time.monotonic() >= deadline:
                    timed_out = True
                    break
                try:
                    process.wait(timeout=0.25)
                except subprocess.TimeoutExpired:
                    pass
        finally:
            collect_children(process.pid, owned)
            adopted_children(owned)
            leaked = bool(live_owned(owned))
            stop_owned(owned)
            process.wait(timeout=5)
            # Fast double forks may escape before the first poll. The existing
            # subreaper adopts them; never mistake reparenting for termination.
            adopted_children(owned)
            leaked = leaked or bool(live_owned(owned))
            reap()
    return {'returncode': process.returncode, 'timedOut': timed_out, 'ownedChildrenLeaked': leaked and not timed_out}


class Campaign:
    def __init__(self, root, manifest_sha, source_revision, *, stage, executor=execute):
        self.root = Path(root).absolute()
        require(self.root.resolve() == self.root and self.root.is_dir(), 'unsafe-campaign-root')
        require(type(source_revision) is str and re.fullmatch(r'[0-9a-f]{40}', source_revision), 'invalid-source-revision')
        self.manifest_path = checked_file(self.root, {'path': 'incoming/manifest/artifact', 'sha256': manifest_sha})
        self.manifest = read_json(self.manifest_path, manifest_sha)
        expected = {'campaignVersion', 'sourceRevision', 'sourceRoot', 'sourceArchive', 'sourceFiles',
                    'apk', 'buildReceipt', 'catalog', 'tabletPolicy', 'runs'}
        require(type(self.manifest) is dict and set(self.manifest) == expected
                and type(self.manifest['campaignVersion']) is int and self.manifest['campaignVersion'] == 1
                and self.manifest['sourceRevision'] == source_revision, 'invalid-campaign-manifest')
        self.source = inside(self.root, self.manifest['sourceRoot'])
        self.stage = Path(stage).absolute()
        require(self.stage.resolve() == self.stage and self.stage != self.source
                and not self.stage.is_relative_to(self.source), 'unsafe-stage-directory')
        self.private = self.root / 'private-sequential-results'
        self.private.mkdir(mode=0o700, exist_ok=False)
        self.executor = executor
        self.manifest_sha = manifest_sha
        runs = self.manifest['runs']
        require(type(runs) is list and runs, 'missing-target-inventory')
        self.results = []
        seen = set()
        for row in runs:
            require(type(row) is dict and set(row) == {'id', 'setup', 'adapter', 'environment'}
                    and type(row['id']) is str and IDENTIFIER.fullmatch(row['id'])
                    and row['id'] not in seen, 'invalid-or-duplicate-target')
            seen.add(row['id'])
            require(type(row['setup']) is list and len(row['setup']) == len(set(row['setup']))
                    and row['id'] not in row['setup']
                    and all(type(x) is str and IDENTIFIER.fullmatch(x) for x in row['setup']), 'invalid-setup-inventory')
            self.results.append(dict(id=row['id'], status='error', reason='not-attempted', attempted=False,
                                     returncode=None, durationSeconds=0, setup=[]))

    def verify_inputs(self):
        require(digest(self.manifest_path) == self.manifest_sha, 'manifest-changed')
        m = self.manifest
        checked_file(self.root, m['sourceArchive'])
        self.apk = checked_file(self.root, m['apk'])
        receipt = read_json(checked_file(self.root, m['buildReceipt']), m['buildReceipt']['sha256'])
        files = m['sourceFiles']
        require(type(files) is dict and files and all(type(k) is str for k in files), 'missing-source-inventory')
        actual = {str(p.relative_to(self.source)) for p in self.source.rglob('*') if p.is_file() or p.is_symlink()}
        require(actual == set(files), 'source-inventory-mismatch')
        for path, expected in files.items():
            checked_file(self.source, {'path': path, 'sha256': expected})
        build, package = receipt['build'], receipt['verifiedPackage']
        require(build['sourceRevision'] == m['sourceRevision'] and build['apkSha256'] == m['apk']['sha256']
                and build['sourceArchiveSha256'] == m['sourceArchive']['sha256']
                and package['sha256'] == m['apk']['sha256'] and package['source_revision'] == m['sourceRevision']
                and package['debuggable'] is True and package['signature_verified'] is True, 'build-receipt-mismatch')
        require(type(build['sourceFilesSha256']) is dict and build['sourceFilesSha256']
                and all(files.get(k) == v for k, v in build['sourceFilesSha256'].items()), 'build-source-mismatch')
        self.catalog = checked_file(self.source, m['catalog'])
        self.runner = current_runner(self.source)
        self.modules = self.runner.load_modules(self.catalog, 'all')
        require({row['id'] for row in self.manifest['runs']} == {row['id'] for row in self.modules}, 'incomplete-target-inventory')
        self.lookup = {row['id']: row for row in self.modules}
        for row in self.manifest['runs']:
            require(set(row['setup']) <= set(self.lookup), 'unknown-setup-module')
        self.policy = checked_file(self.source, m['tabletPolicy'])

    def command(self, row, folder):
        selected = row['setup'] + [row['id']]
        modules = []
        for name in selected:
            module = deepcopy(self.lookup[name])
            module['command'] = self.runner.resolve_module_command(self.catalog, module['command'])
            modules.append(module)
        catalog = folder / 'catalog.json'
        atomic_json(catalog, dict(schemaVersion=1, modules=modules))
        adapter = checked_file(self.root, row['adapter'])
        environment = read_json(checked_file(self.root, row['environment']), row['environment']['sha256'])
        require(type(environment) is dict and set(environment) == {'schemaVersion', 'environment'}
                and type(environment['schemaVersion']) is int and environment['schemaVersion'] == 1
                and type(environment['environment']) is dict
                and all(type(k) is str and type(v) is str and '\x00' not in k + v
                        for k, v in environment['environment'].items()), 'invalid-private-environment')
        env = os.environ | environment['environment'] | {
            'OVERTE_DEVICE_CONTINUE_AFTER_MODULE_ERROR': '1', 'PYTHONDONTWRITEBYTECODE': '1',
            'PYTHONNOUSERSITE': '1', 'PYTHONPATH': str(self.source / 'tests/device')}
        argv = [sys.executable, str(self.source / 'tests/device/run.py'), '--catalog', str(catalog),
                '--adapter-manifest', str(adapter), '--suite', 'all', '--require-complete',
                '--tablet-policy', str(self.policy), '--candidate-artifact', str(self.apk),
                '--expected-source-sha', self.manifest['sourceRevision'],
                '--expected-artifact-sha256', self.manifest['apk']['sha256'], '--output-dir', str(folder / 'actual')]
        if env.get('OVERTE_DEVICE_TARGET_SELECTOR'):
            argv += ['--target', env['OVERTE_DEVICE_TARGET_SELECTOR']]
        for identifier in row['setup']:
            argv += ['--required-setup', identifier]
        return argv, env, sum(m['timeoutSeconds'] for m in modules) + 120 * len(modules) + 300

    def collect(self, row, folder, outcome):
        require(type(outcome) is dict and type(outcome.get('returncode')) is int, 'invalid-runner-exit')
        if outcome.get('timedOut'):
            raise CampaignError('runner-timeout')
        require(not outcome.get('ownedChildrenLeaked'), 'runner-left-owned-children')
        output = folder / 'actual'
        require((output / 'summary.json').is_file(), 'missing-summary')
        value = read_json(output / 'summary.json')
        require(type(value) is dict and value.get('schemaVersion') == 1 and type(value.get('results')) is list, 'invalid-summary')
        wanted = row['setup'] + [row['id']]
        found = {}
        for item in value['results']:
            require(type(item) is dict and type(item.get('id')) is str and item['id'] not in found
                    and item.get('status') in ('passed', 'failed', 'error', 'skipped'), 'invalid-summary-row')
            found[item['id']] = item
        require(set(wanted) <= set(found) and set(found) - set(wanted) <= {'target-execution', 'target-cleanup', 'target-reservation'}, 'missing-or-foreign-summary-row')
        setup = [dict(id=name, status=found[name]['status']) for name in row['setup']]
        target = found[row['id']]
        status = target['status']
        reason = 'module-result'
        if any(item['status'] != 'passed' for item in setup):
            status, reason = 'error', 'setup-not-passed'
        if any(item['status'] != 'passed' for name, item in found.items() if name not in wanted):
            status, reason = 'error', 'runner-infrastructure-or-cleanup-error'
        if status == 'skipped':
            status, reason = 'error', 'required-target-skipped'
        if status == 'passed':
            require(outcome['returncode'] == 0, 'runner-nonzero-after-pass')
            identity = read_json(output / 'result-identity.json')
            require(identity.get('contract') == 'overte-sh004-result-v1'
                    and identity.get('sourceRevision') == self.manifest['sourceRevision']
                    and identity.get('artifactSha256') == self.manifest['apk']['sha256'], 'missing-or-foreign-result-identity')
            for key, filename in [('runSha256', 'run-manifest.json'), ('summarySha256', 'summary.json'), ('junitSha256', 'junit.xml')]:
                require(identity.get(key) == digest(output / filename), 'result-identity-content-mismatch')
        return dict(status=status, reason=reason, setup=setup)

    def publish(self):
        value = dict(schemaVersion=1, sourceRevision=self.manifest['sourceRevision'],
                     artifactSha256=self.manifest['apk']['sha256'], manifestSha256=self.manifest_sha,
                     status='passed' if all(r['status'] == 'passed' for r in self.results) else 'failed',
                     plannedTargets=len(self.results), results=self.results)
        atomic_json(self.stage / 'summary.json', value)
        suite = ET.Element('testsuite', name='android-phone-sequential-campaign', tests=str(len(self.results)),
                           failures=str(sum(r['status'] == 'failed' for r in self.results)),
                           errors=str(sum(r['status'] == 'error' for r in self.results)))
        for row in self.results:
            case = ET.SubElement(suite, 'testcase', name=row['id'], classname='android-phone.campaign', time=str(row['durationSeconds']))
            if row['status'] in ('failed', 'error'):
                ET.SubElement(case, 'failure' if row['status'] == 'failed' else 'error', message=row['reason'])
        path = self.stage / 'junit.xml'
        require(not path.is_symlink(), 'unsafe-junit-output')
        temporary = path.with_name('junit.' + uuid.uuid4().hex + '.tmp')
        with os.fdopen(os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb') as output:
            ET.ElementTree(suite).write(output, encoding='utf-8', xml_declaration=True)
        os.replace(temporary, path)
        return value['status']

    def run(self):
        self.publish()
        for index, row in enumerate(self.manifest['runs']):
            started = time.monotonic()
            result = self.results[index]
            folder = self.private / row['id']
            try:
                folder.mkdir(mode=0o700)
                # Do not let one module's exception abort attempts of later IDs.
                self.verify_inputs()
                argv, env, timeout = self.command(row, folder)
                atomic_json(folder / 'argv.json', argv)  # Private: may contain target identity.
                result['attempted'] = True
                outcome = self.executor(argv, self.source, env, timeout, folder / 'runner.log')
                result['returncode'] = outcome.get('returncode')
                result.update(self.collect(row, folder, outcome))
                self.verify_inputs()  # Late source/APK/receipt changes cannot leave a green verdict.
            except Exception as error:
                # Even a broken per-target directory must not abort later IDs.
                try:
                    atomic_json(self.private / (row['id'] + '-error.json'),
                                {'traceback': traceback.format_exc()})
                except OSError:
                    pass
                result.update(status='error', reason=str(error) if isinstance(error, CampaignError)
                              else 'campaign-input-or-runner-error')
            finally:
                result['durationSeconds'] = round(time.monotonic() - started, 3)
                self.publish()
        return 0 if self.publish() == 'passed' else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign-root', required=True, type=Path)
    parser.add_argument('--manifest-sha256', required=True)
    parser.add_argument('--source-revision', required=True)
    arguments = parser.parse_args()
    os.umask(0o077)
    stage = None
    try:
        stage = Path(os.environ['WORKSPACE']) / 'campaign-results'
        return Campaign(arguments.campaign_root, arguments.manifest_sha256, arguments.source_revision, stage=stage).run()
    except Exception:
        # No admitted inventory exists here. Report admission itself as ERROR;
        # never manufacture per-target attempts from an untrusted manifest.
        if stage is not None:
            try:
                require(stage.resolve() == stage.absolute(), 'unsafe-admission-output')
                atomic_json(stage / 'summary.json', dict(schemaVersion=1, status='failed',
                    admissionFailed=True, plannedTargets=0, results=[dict(id='campaign-admission',
                    status='error', reason='campaign-admission-or-staging-failed', attempted=False)]))
                path = stage / 'junit.xml'
                require(not path.is_symlink(), 'unsafe-admission-junit')
                with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600), 'w') as output:
                    output.write('<testsuite name="android-phone-sequential-campaign" tests="1" errors="1">'
                                 '<testcase name="campaign-admission"><error message="campaign-admission-or-staging-failed"/>'
                                 '</testcase></testsuite>\n')
            except Exception:
                pass  # Jenkins' nonempty-archive requirement also fails closed.
        print('Campaign admission/staging failed; no successful campaign result is claimed.', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
