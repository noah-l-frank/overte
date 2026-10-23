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
from contextlib import ExitStack
from copy import deepcopy
import errno
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
OBSERVER_FORBIDDEN_ENV = {'OVERTE_E2E_FEATURE_READER_TOKEN', 'OVERTE_E2E_FEATURE_IMAGE_POLICY',
    'OVERTE_E2E_CREATE_CONTROL_TOKEN', 'OVERTE_E2E_SCRIPTS_CONTROL_TOKEN', 'OVERTE_PHONE_ASSETS_CONFIGURATION'}
OBSERVER_HOST_ENV = {'PATH', 'HOME', 'LANG', 'LC_ALL', 'LC_CTYPE', 'TMPDIR', 'TMP', 'TEMP',
    'ANDROID_HOME', 'ANDROID_SDK_ROOT', 'XDG_RUNTIME_DIR'}


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


def execute(argv, cwd, env, timeout, log, *, observer=None):
    """One runner at a time; retain/terminate only actually owned host children."""
    owned = {}
    require(sys.platform.startswith('linux'), 'linux-command-ownership-required')
    process = actor = None
    observer_timed_out = False
    observer_abandoned = observer_forced = False
    with owner_module(cwd).command_owner() as reap, ExitStack() as files:
        def open_log(path):
            return files.enter_context(os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb'))
        output = open_log(log)
        deadline = time.monotonic() + timeout
        timed_out = False
        try:
            if observer is not None:
                actor = subprocess.Popen(observer['argv'], cwd=cwd, env=observer['environment'],
                    stdout=open_log(log.with_name('observer.log')), stderr=subprocess.STDOUT, start_new_session=True)
                collect_children(actor.pid, owned, parent=os.getpid())
                atomic_json(log.with_name('observer-process.json'), dict(pid=actor.pid,
                    birth=owned.get(actor.pid), argv=observer['argv']))
            process = subprocess.Popen(argv, cwd=cwd, env=env, stdout=output, stderr=subprocess.STDOUT,
                                       start_new_session=True)
            collect_children(process.pid, owned, parent=os.getpid())
            while process.poll() is None:
                collect_children(process.pid, owned)
                if actor is not None:
                    collect_children(actor.pid, owned)
                adopted_children(owned)
                if time.monotonic() >= deadline:
                    timed_out = True
                    break
                try:
                    process.wait(timeout=0.25)
                except subprocess.TimeoutExpired:
                    pass
            # Retirement is the original observer's work. Never replace its
            # successful normal exit with a supervisor signal acknowledgment.
            while actor is not None and actor.poll() is None and not timed_out:
                if process.returncode != 0:
                    observer_abandoned = True
                    break  # A failed prefix may never have registered a run.
                collect_children(actor.pid, owned)
                adopted_children(owned)
                if time.monotonic() >= deadline:
                    observer_timed_out = True
                    break
                try:
                    actor.wait(timeout=min(.1, max(.001, deadline - time.monotonic())))
                except subprocess.TimeoutExpired:
                    pass
        finally:
            for child in (process, actor):
                if child is not None:
                    collect_children(child.pid, owned)
            adopted_children(owned)
            observer_forced = actor is not None and actor.poll() is None
            leaked = bool(live_owned(owned))
            stop_owned(owned)
            for child in (process, actor):
                if child is not None:
                    child.wait(timeout=5)
            # Fast double forks may escape before the first poll. The existing
            # subreaper adopts them; never mistake reparenting for termination.
            adopted_children(owned)
            leaked = leaked or bool(live_owned(owned))
            reap()
            if actor is not None:
                atomic_json(log.with_name('observer-exit.json'), dict(pid=actor.pid, birth=owned.get(actor.pid),
                    returncode=actor.returncode, timedOut=observer_timed_out or timed_out,
                    forcedCleanup=observer_forced, runnerFailedBeforeRetirement=observer_abandoned,
                    ownedChildrenLeaked=leaked))
    return dict(returncode=process.returncode, timedOut=timed_out, ownedChildrenLeaked=leaked and not timed_out,
        **(dict(observerReturncode=actor.returncode, observerTimedOut=observer_timed_out or timed_out,
                observerForcedCleanup=observer_forced, observerAbandoned=observer_abandoned) if actor is not None else {}))


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
        self.staging_errors = 0
        self.manifest_sha = manifest_sha
        runs = self.manifest['runs']
        require(type(runs) is list and runs, 'missing-target-inventory')
        self.results = []
        seen = set()
        for row in runs:
            require(type(row) is dict and set(row) in ({'id', 'setup', 'adapter', 'environment'},
                    {'id', 'setup', 'adapter', 'environment', 'observer'})
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

    def observer(self, row, primary_environment, folder):
        if 'observer' not in row:
            return None
        reference = row['observer']
        require(type(reference) is dict and set(reference) == {'config', 'environment'}, 'invalid-observer-reference')
        paths = [checked_file(self.root, reference[name]) for name in ('config', 'environment')]
        primary_path = checked_file(self.root, row['environment'])
        require(len({(p.stat().st_dev, p.stat().st_ino) for p in [*paths, primary_path]}) == 3,
                'observer-role-inputs-not-independent')
        for path in paths:
            metadata = path.stat()
            require(metadata.st_uid == os.geteuid() and stat.S_IMODE(metadata.st_mode) == 0o600
                    and metadata.st_nlink == 1, 'observer-private-input-ownership')
        config = read_json(paths[0], reference['config']['sha256'])
        role = read_json(paths[1], reference['environment']['sha256'])
        module = self.lookup[row['id']]
        require(module['command'][:2] == ['modules/feature_journey.py', '--area']
                and len(module['command']) == 3 and row['id'] == 'feature-' + module['command'][2], 'observer-target-is-not-feature-journey')
        area = module['command'][2]
        fields = {'featureObserverVersion', 'area', 'target', 'candidateArguments', 'fixtureUrl', 'actorToken', 'durationSeconds'}
        fields |= {'imagePolicy'} if area == 'emotes' else {'peerTarget', 'peerImagePolicy'} if area == 'avatar-people' else set()
        require(type(config) is dict and set(config) == fields and config.get('area') == area, 'observer-area-or-role-mismatch')
        require(type(role) is dict and set(role) == {'schemaVersion', 'environment'}
                and type(role['schemaVersion']) is int and role['schemaVersion'] == 1
                and type(role['environment']) is dict and all(type(k) is str and type(v) is str
                    and '\x00' not in k + v for k, v in role['environment'].items()), 'invalid-observer-environment')
        require(not OBSERVER_FORBIDDEN_ENV.intersection(role['environment']), 'observer-primary-credential-forbidden')
        require(type(config['actorToken']) is str and config['actorToken']
                and config['actorToken'] not in {primary_environment.get(key) for key in OBSERVER_FORBIDDEN_ENV},
                'observer-token-not-independent')
        for role_environment in (primary_environment, role['environment']):
            configured = role_environment.get('OVERTE_PHONE_FEATURE_FIXTURE_CONFIG')
            if configured:
                path = Path(configured)
                access = read_json(path if path.is_absolute() else self.source / path)
                # The original adapter-only access file is read-only. A service
                # owner/runner-writer config is never an actor substitute.
                require(type(access) is dict and set(access) == {'fixtureAdapterAccessVersion', 'fixtureUrl', 'adapterToken'}
                        and access['fixtureUrl'] == config['fixtureUrl']
                        and access['adapterToken'] != config['actorToken'], 'observer-adapter-role-not-independent')
        if 'OVERTE_DEVICE_TARGET_SELECTOR' in primary_environment:
            require(config['target'] == primary_environment['OVERTE_DEVICE_TARGET_SELECTOR'], 'observer-target-mismatch')
        if 'OVERTE_E2E_FEATURE_FIXTURE_URL' in primary_environment:
            require(config['fixtureUrl'] == primary_environment['OVERTE_E2E_FEATURE_FIXTURE_URL'], 'observer-fixture-mismatch')
        environment = {key: value for key, value in os.environ.items() if key in OBSERVER_HOST_ENV}
        environment.update(role['environment'])
        artifact_root = str(folder / 'actual/modules' / row['id'])
        require('OVERTE_DEVICE_ARTIFACT_DIR' not in environment or environment['OVERTE_DEVICE_ARTIFACT_DIR'] == artifact_root,
                'observer-artifact-root-mismatch')
        environment.update(PYTHONDONTWRITEBYTECODE='1', PYTHONNOUSERSITE='1',
            PYTHONPATH=str(self.source / 'tests/device'), OVERTE_DEVICE_ARTIFACT_DIR=artifact_root)
        # Config/candidate semantics remain the original observer's verifier.
        return dict(argv=[sys.executable, str(self.source / 'tests/device/adapters/android-phone/script_observer.py'),
                          '--config', str(paths[0])], environment=environment)

    def collect(self, row, folder, outcome):
        require(type(outcome) is dict and type(outcome.get('returncode')) is int, 'invalid-runner-exit')
        if 'observer' in row:
            require(not outcome.get('observerForcedCleanup') and not outcome.get('observerAbandoned'), 'observer-required-forced-cleanup')
            require(not outcome.get('observerTimedOut'), 'observer-retirement-timeout')
            require(type(outcome.get('observerReturncode')) is int and outcome['observerReturncode'] == 0,
                    'observer-did-not-exit-successfully')
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

    def summary(self):
        return dict(schemaVersion=1, sourceRevision=self.manifest['sourceRevision'],
                     artifactSha256=self.manifest['apk']['sha256'], manifestSha256=self.manifest_sha,
                     status='passed' if not self.staging_errors and all(r['status'] == 'passed' for r in self.results) else 'failed',
                     publicStagingErrors=self.staging_errors, plannedTargets=len(self.results), results=self.results)

    def publish(self):
        value = self.summary()
        require(self.stage.resolve() == self.stage.absolute(), 'unsafe-stage-directory')
        self.stage.mkdir(parents=True, mode=0o700, exist_ok=True)
        suite = ET.Element('testsuite', name='android-phone-sequential-campaign', tests=str(len(self.results) + bool(self.staging_errors)),
                           failures=str(sum(r['status'] == 'failed' for r in self.results)),
                           errors=str(sum(r['status'] == 'error' for r in self.results) + bool(self.staging_errors)))
        for row in self.results:
            case = ET.SubElement(suite, 'testcase', name=row['id'], classname='android-phone.campaign', time=str(row['durationSeconds']))
            if row['status'] in ('failed', 'error'):
                ET.SubElement(case, 'failure' if row['status'] == 'failed' else 'error', message=row['reason'])
        if self.staging_errors:
            case = ET.SubElement(suite, 'testcase', name='campaign-public-staging', classname='android-phone.infrastructure')
            ET.SubElement(case, 'error', message='public-aggregate-write-failed')
        path = self.stage / 'junit.xml'
        require(not path.is_symlink(), 'unsafe-junit-output')
        temporary = path.with_name('junit.' + uuid.uuid4().hex + '.tmp')
        with os.fdopen(os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb') as output:
            ET.ElementTree(suite).write(output, encoding='utf-8', xml_declaration=True)
        os.replace(temporary, path)
        # Publish the aggregate decision only after its corresponding JUnit.
        atomic_json(self.stage / 'summary.json', value)
        return value['status']

    def preserve_progress(self):
        try:
            atomic_json(self.private / 'progress.json', self.summary())
        except OSError as error:
            if error.errno in (errno.ELOOP, errno.ENOTDIR):
                raise CampaignError('unsafe-private-progress-path') from error
            print('Private campaign progress could not be written; retain sanitized console results.', file=sys.stderr)

    def publish_progress(self):
        self.preserve_progress()
        try:
            self.publish()
        except OSError as error:
            # Only publication I/O is recoverable. Path/contract validation
            # errors remain hard failures, not permission to adopt new inputs.
            if error.errno in (errno.ELOOP, errno.ENOTDIR):
                raise CampaignError('unsafe-public-output-path') from error
            self.staging_errors += 1
            self.preserve_progress()
            print('Public campaign aggregate write failed; campaign remains failed and later targets continue.', file=sys.stderr)

    def run(self):
        self.publish_progress()
        for index, row in enumerate(self.manifest['runs']):
            started = time.monotonic()
            result = self.results[index]
            folder = self.private / row['id']
            try:
                folder.mkdir(mode=0o700)
                # Do not let one module's exception abort attempts of later IDs.
                self.verify_inputs()
                argv, env, timeout = self.command(row, folder)
                observer = self.observer(row, env, folder)
                atomic_json(folder / 'argv.json', argv)  # Private: may contain target identity.
                result['attempted'] = True
                outcome = self.executor(argv, self.source, env, timeout, folder / 'runner.log',
                                        **({'observer': observer} if observer is not None else {}))
                result['returncode'] = outcome.get('returncode')
                result.update(self.collect(row, folder, outcome))
                self.verify_inputs()  # Late source/APK/receipt changes cannot leave a green verdict.
                self.observer(row, env, folder)  # Recheck exact private role inputs after actual retirement.
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
                self.publish_progress()
        self.publish_progress()
        value = self.summary()
        if self.staging_errors:
            # This contains only the same sanitized fields as the public JSON,
            # including the complete attempted-ID inventory if staging stays down.
            print('CAMPAIGN_SANITIZED_FALLBACK ' + json.dumps(value, sort_keys=True), file=sys.stderr)
        return 0 if value['status'] == 'passed' else 1


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
