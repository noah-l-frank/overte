#!/usr/bin/env python3
"""Run selected original catalog modules, preserving the first failure in place.

Fixture helpers supply existing owned services; they never supply test verdicts.
The sole verdict source is the admitted standard tests/device/run.py harness.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations
import contextlib
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import sys
import time
import uuid
from types import SimpleNamespace

TUTORIAL_URL = 'file:///~/serverless/tutorial.json'
TUTORIAL_FEET = (1985.26, 1994.1357422, 1994.25)
RELEASED = 77


class WorkerError(ValueError):
    pass


def need(ok, code):
    if not ok:
        raise WorkerError(code)


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def write_json(path, value):
    raw = (json.dumps(value, indent=2, sort_keys=True) + '\n').encode()
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    return hashlib.sha256(raw).hexdigest()


def finite_vector(value):
    return (type(value) is list and len(value) == 3
            and all(type(item) in (int, float) and math.isfinite(item) for item in value))


def validate_tutorial(samples, nonce, started_ms, ended_ms):
    """Require independent fresh client observations, never a click acknowledgement.

    The built-in scene contains40 definitions but the client observes a local
    spatial subset. Its old domain UUID and fixture-specific scene.ready field
    are intentionally irrelevant to tutorial readiness.
    """
    need(type(samples) is list and len(samples) >= 3, 'PHONE_TUTORIAL_SAMPLES_REQUIRED')
    previous = None
    identity = None
    counts = []
    for row in samples:
        need(type(row) is dict and set(row) == {
            'runNonce', 'observedEpochMs', 'processIdentity', 'sceneUrl', 'protocol',
            'serverless', 'connected', 'entityCount', 'feet', 'inAir', 'flying', 'velocity'},
            'PHONE_TUTORIAL_SAMPLE_SCHEMA')
        stamp = row['observedEpochMs']
        need(type(stamp) is int and started_ms <= stamp <= ended_ms
             and row['runNonce'] == nonce, 'PHONE_TUTORIAL_STALE_OBSERVATION')
        need(previous is None or stamp - previous >= 250, 'PHONE_TUTORIAL_INDEPENDENT_SAMPLES')
        previous = stamp
        need(type(row['processIdentity']) is str and row['processIdentity'], 'PHONE_TUTORIAL_PROCESS_REQUIRED')
        identity = identity or row['processIdentity']
        need(row['processIdentity'] == identity, 'PHONE_TUTORIAL_PROCESS_CHANGED')
        need(row['sceneUrl'] == TUTORIAL_URL and row['protocol'] == 'file'
             and row['serverless'] is True and row['connected'] is False, 'PHONE_TUTORIAL_SCENE_NOT_OBSERVED')
        need(type(row['entityCount']) is int and row['entityCount'] > 0, 'PHONE_TUTORIAL_ENTITIES_MISSING')
        counts.append(row['entityCount'])
        need(finite_vector(row['feet']) and finite_vector(row['velocity']), 'PHONE_TUTORIAL_VECTOR_REQUIRED')
        need(all(abs(actual - expected) <= .75 for actual, expected in zip(row['feet'], TUTORIAL_FEET))
             and row['inAir'] is False and row['flying'] is False
             and math.sqrt(sum(value * value for value in row['velocity'])) <= .1,
             'PHONE_TUTORIAL_GROUNDED_SPAWN_REQUIRED')
    need(max(counts) - min(counts) <= 1, 'PHONE_TUTORIAL_SCENE_UNSTABLE')
    need(all(math.dist(samples[0]['feet'], row['feet']) <= .05 for row in samples),
         'PHONE_TUTORIAL_AVATAR_UNSTABLE')
    return True


def install_first_failure(runner, policy, tutorial):
    """Hold inside run_module, before run.py can recover/cleanup/advance."""
    original = runner.run_module
    launched = False
    prepared = False

    def checked(row, *args, **kwargs):
        nonlocal launched, prepared
        if row['id'] != 'launch-smoke':
            try:
                need(launched, 'PHONE_LAUNCH_SETUP_NOT_PASSED')
                if not prepared:
                    tutorial()
                    prepared = True
            except BaseException as error:
                if policy.cleanup_authorized:
                    raise
                policy.record_exception(error, 'PHONE_PREPARATION_FAILED')
                policy.hold('PHONE_PREPARATION_FAILED', module_id=row['id'])
        result = original(row, *args, **kwargs)
        if result.get('status') != 'passed' or result.get('returncode') != 0:
            policy.hold('PHONE_FIRST_MODULE_NONPASS', module_id=row['id'])
        if row['id'] == 'launch-smoke':
            launched = True
        return result
    runner.run_module = checked
    return runner


def assert_complete(summary, planned_ids):
    need(type(summary) is dict and summary.get('status') == 'passed'
         and type(summary.get('results')) is list, 'PHONE_ORIGINAL_HARNESS_NOT_PASSED')
    rows = summary['results']
    need([row.get('id') for row in rows] == planned_ids
         and all(row.get('status') == 'passed' and row.get('returncode') == 0 for row in rows),
         'PHONE_ORIGINAL_RESULTS_INCOMPLETE')


def install_native_log_guard(admission, policy):
    """Guard fixed publication slots without changing or stopping their producer."""
    required = set(policy.config['domainRequiredModules']) & set(admission.plan['moduleIds'])
    if not required:
        return lambda: None
    original = policy.publish_full_logs
    def unadmitted_publication():
        raise WorkerError('PHONE_NATIVE_LOG_GUARD_NOT_ADMITTED')
    policy.publish_full_logs = unadmitted_publication
    reference = policy.config.get('nativeLogCoverage')
    need(type(reference) is dict and set(reference) == {'path', 'sha256', 'root'},
         'PHONE_NATIVE_LOG_COVERAGE_REQUIRED')
    path = admission.source / 'tests/device/jenkins/phone_native_log_coverage.py'
    need(reference['path'] == str(path) and path.resolve() == path
         and admission.inventory.get('tests/device/jenkins/phone_native_log_coverage.py') == reference['sha256']
         and hashlib.sha256(path.read_bytes()).hexdigest() == reference['sha256'],
         'PHONE_NATIVE_LOG_COVERAGE_SOURCE')
    root = Path(reference['root'])
    streams = policy.config['publicLogStreams']
    memory = streams['native-memory']
    scope = Path(memory['scopeRoot'])
    need(root.is_absolute() and root.resolve() == root and root.name == 'debug-hold'
         and scope.is_absolute() and scope.resolve() == scope and root.is_relative_to(scope)
         and Path(memory['path']) == root / 'MEMORY_TIMELINE.private.jsonl',
         'PHONE_NATIVE_LOG_COVERAGE_ROOT')
    coverage = load(path, '_phone_native_log_coverage')
    # Configuration must enumerate every supported slot and the committed index.
    wanted = {root / filename for filename in coverage.FILES.values()}
    wanted.add(root / coverage.INDEX)
    observed = {Path(value['path']) for value in streams.values() if type(value) is dict and 'path' in value}
    need(wanted <= observed, 'PHONE_NATIVE_LOG_STREAMS_INCOMPLETE')
    for native_path in wanted:
        matches = [value for value in streams.values() if type(value) is dict
                   and value.get('path') == str(native_path)]
        kind = 'text' if native_path.name == coverage.INDEX else 'memory'
        need(len(matches) == 1 and matches[0].get('kind') == kind
             and matches[0].get('scopeRoot') == str(scope), 'PHONE_NATIVE_LOG_STREAM_SCHEMA')
    baseline = None
    def guard():
        nonlocal baseline
        result = coverage.check(baseline, require_headroom=baseline is None, root=root)
        if baseline is None:
            baseline = result
            write_json(policy.root / 'native-log-coverage-before.private.json', {
                'contextSha256': policy.context, 'coverage': baseline})
        return result
    def publish_full_logs():
        before = guard()
        original()
        after = guard()
        need(before['partSet'] == after['partSet'], 'PHONE_NATIVE_LOG_ROTATED_DURING_PUBLICATION')
        write_json(policy.root / 'native-log-coverage-publication.private.json', {
            'contextSha256': policy.context, 'before': before, 'after': after})
    policy.publish_full_logs = publish_full_logs
    return guard


def export_public(policy, destination):
    """Copy only the audited publisher's sealed public files into this build."""
    policy.validate_public_data()
    index_raw = (policy.stage / 'artifact-index.json').read_bytes()
    index = json.loads(index_raw)
    need(type(index) is dict and type(index.get('files')) is list, 'PHONE_PUBLIC_INDEX_REQUIRED')
    payloads = {}
    for row in index['files']:
        name = row['path']
        relative = Path(name)
        need(type(name) is str and relative.parts and relative.as_posix() == name
             and not relative.is_absolute() and '..' not in relative.parts
             and name not in ('export-index.json', 'EXPORT_READY', '.EXPORT_READY.tmp'),
             'PHONE_PUBLIC_PATH_ESCAPE')
        source = policy.stage / relative
        need(source.resolve() == source and source.is_file(), 'PHONE_PUBLIC_FILE_ALIAS')
        raw = source.read_bytes()
        need(len(raw) == row['bytes'] and hashlib.sha256(raw).hexdigest() == row['sha256'],
             'PHONE_PUBLIC_FILE_HASH')
        payloads[name] = raw
    for name in ('debug-state.json',):
        source = policy.stage / name
        need(source.resolve() == source and source.is_file(), 'PHONE_PUBLIC_FILE_ALIAS')
        payloads[name] = source.read_bytes()
    payloads['artifact-index.json'] = index_raw
    state = json.loads(payloads['debug-state.json'])
    need(state.get('artifacts', {}).get('artifact-index.json') == {
        'sha256': hashlib.sha256(index_raw).hexdigest(), 'bytes': len(index_raw)},
        'PHONE_PUBLIC_STATE_INDEX_MISMATCH')
    need(not destination.exists() and destination.resolve(strict=False) == destination,
         'PHONE_PUBLIC_EXPORT_EXISTS')
    destination.mkdir(mode=0o700, parents=True)
    exported = {}
    for name, raw in sorted(payloads.items()):
        target = destination / name
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with os.fdopen(os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        exported[name] = {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
    build = os.environ['BUILD_NUMBER']
    index_sha = write_json(destination / 'export-index.json', {
        'schemaVersion': 1, 'job': 'overte-pixel6a', 'build': int(build),
        'runNamespace': 'overte-pixel6a-' + build, 'files': exported})
    pending = destination / '.EXPORT_READY.tmp'
    with os.fdopen(os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb') as stream:
        stream.write((index_sha + '\n').encode('ascii'))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(pending, destination / 'EXPORT_READY')


def run(admission):
    """Called only after phone_runtime's complete read-only admission succeeds."""
    os.umask(0o077)
    sys.dont_write_bytecode = True
    run_root = admission.run_root
    run_root.mkdir(mode=0o700)
    refs = admission.references
    config = json.loads(refs['debugTemplate'].read_bytes())
    config.update(schemaVersion=1, enabled=True, runId=run_root.name, nonce=uuid.uuid4().hex,
                  privateRoot=str(run_root / 'debug-private'), publicStage=str(run_root / 'public'),
                  sourceRoot=str(admission.source), moduleIds=admission.plan['moduleIds'],
                  inventory={'path': str(admission.deployment / admission.manifest['source']['inventory']['path']),
                             'sha256': admission.manifest['source']['inventory']['sha256']})
    private_values = list(config.get('privateValues', []))
    if config.get('privateValuesFile'):
        reference = config['privateValuesFile']
        path = Path(reference['path'])
        need(path.is_absolute() and path.resolve() == path, 'PHONE_REDACTION_INPUT_ALIAS')
        raw = path.read_bytes()
        need(hashlib.sha256(raw).hexdigest() == reference['sha256'], 'PHONE_REDACTION_INPUT_CHANGED')
        original_values = json.loads(raw)
        need(type(original_values) is list and all(type(value) is str for value in original_values),
             'PHONE_REDACTION_INPUT_SCHEMA')
        private_values.extend(original_values)
    target_mapping = json.loads(refs['targets'].read_bytes())
    for target in target_mapping.get('targets', []):
        for key in ('selector', 'reservationKey'):
            if type(target.get(key)) is str:
                private_values.append(target[key])
        for key in ('appium:udid', 'udid', 'deviceUDID', 'deviceSerial'):
            if type(target.get('capabilities', {}).get(key)) is str:
                private_values.append(target['capabilities'][key])
    private_values.extend((config['nonce'], str(run_root)))
    private_path = run_root / 'private-values.private.json'
    private_sha = write_json(private_path, sorted(set(private_values)))
    config['privateValuesFile'] = {'path': str(private_path), 'sha256': private_sha}
    config['privateValues'] = []
    streams = dict(config.get('publicLogStreams', {}))
    streams.update({
        'phone-runtime': {'path': str(run_root / 'runtime.private.log'),
                          'scopeRoot': str(run_root), 'maxRawBytes': 128 * 1024 * 1024},
        'phone-scene-server': {'path': str(run_root / 'scene-runtime/server.private.log'),
                               'scopeRoot': str(run_root), 'maxRawBytes': 128 * 1024 * 1024}})
    config['publicLogStreams'] = streams
    config_path = run_root / 'debug-hold-config.private.json'
    config_sha = write_json(config_path, config)
    sys.path.insert(0, str(admission.source / 'tests/device'))
    sys.path.insert(0, str(admission.source / 'tests/device/jenkins/debugging'))
    debug = load(admission.source / 'tests/device/jenkins/debugging/debug_failure_hold.py', '_phone_run_debug')
    policy = debug.Policy(config_path, config_sha)
    policy.source_guard()  # Initialize inventory before any observer can reject an exception.
    workspace = Path(os.environ['WORKSPACE'])
    public_root = workspace / 'pixel-job-public' / os.environ['BUILD_NUMBER']
    need(workspace.is_absolute() and workspace.resolve() == workspace
         and os.environ.get('OVT_PHONE_PUBLIC_ROOT') == str(public_root)
         and public_root.resolve(strict=False) == public_root and not public_root.exists(),
         'PHONE_PUBLIC_BUILD_NAMESPACE')
    original_publish = policy.publish
    def publish(*args, **kwargs):
        result = original_publish(*args, **kwargs)
        export_public(policy, public_root)
        return result
    policy.publish = publish
    log = run_root / 'runtime.private.log'
    with log.open('x', encoding='utf-8', buffering=1) as output, contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
        try:
            environment_value = json.loads(refs['environment'].read_bytes())
            need(type(environment_value) is dict and set(environment_value) == {'schemaVersion', 'environment'}
                 and environment_value['schemaVersion'] == 1 and type(environment_value['environment']) is dict,
                 'PHONE_ENVIRONMENT_SCHEMA')
            environment = environment_value['environment']
            need(all(type(key) is str and type(value) is str for key, value in environment.items()), 'PHONE_ENVIRONMENT_VALUES')
            need(not set(environment) & {'PYTHONHOME', 'PYTHONPATH', 'ANDROID_SERIAL', 'ADB_SERVER_SOCKET',
                                         'OVERTE_DEVICE_CONTINUE_AFTER_MODULE_ERROR'}, 'PHONE_ENVIRONMENT_OVERRIDE')
            targets = json.loads(refs['targets'].read_bytes())
            candidates = [row for row in targets['targets'] if row.get('enabled') is True
                          and row.get('physical') is True and row.get('platform') == 'android']
            need(len(candidates) == 1, 'PHONE_EXACT_PHYSICAL_TARGET_REQUIRED')
            target = candidates[0]
            caps = target['capabilities']
            need(type(target.get('selector')) is str and target['selector']
                 and caps.get('appium:noReset') is True and caps.get('appium:autoLaunch') is False
                 and 'appium:app' not in caps and type(caps.get('appium:adbPort')) is int
                 and 1 <= caps['appium:adbPort'] <= 65535, 'PHONE_NO_INSTALL_TRANSPORT_REQUIRED')
            environment = dict(environment)
            environment.update(OVERTE_APPIUM_TARGETS=str(refs['targets']),
                               ANDROID_ADB_SERVER_PORT=str(caps['appium:adbPort']),
                               OVERTE_DEVICE_STATE_ROOT=str(run_root / 'fresh-state'),
                               OVERTE_DEVICE_DEBUG_HOLD_CONFIG=str(config_path),
                               OVERTE_DEVICE_DEBUG_HOLD_CONFIG_SHA256=config_sha)
            (run_root / 'fresh-state').mkdir(mode=0o700)
            context = SimpleNamespace(admission=admission, run_root=run_root, policy=policy,
                                      environment=environment, target=target, nonce=config['nonce'],
                                      fixture_config=refs['fixtureConfig'], source_guard=admission.revalidate)
            context.native_log_guard = install_native_log_guard(admission, policy)
            context.native_log_guard()
            fixture = load(refs['fixtureHelper'], '_phone_owned_fixture')
            overrides = fixture.prepare(context)
            context.native_log_guard()
            need(type(overrides) is dict and all(type(key) is str and type(value) is str for key, value in overrides.items()),
                 'PHONE_FIXTURE_ENVIRONMENT_REQUIRED')
            need(not set(overrides) & {'PYTHONHOME', 'PYTHONPATH', 'ANDROID_SERIAL', 'ADB_SERVER_SOCKET',
                                      'OVERTE_DEVICE_CONTINUE_AFTER_MODULE_ERROR'}, 'PHONE_FIXTURE_ENVIRONMENT_OVERRIDE')
            environment.update(overrides)
            # Newly generated owned-fixture tokens were unknowable when the
            # immutable hold context was created. Additional in-memory values
            # only strengthen redaction; the original pinned list stays intact.
            policy.config['privateValues'].extend(value for key, value in environment.items()
                                                  if re.search(r'TOKEN|SECRET|PASSWORD|ACCOUNT|SELECTOR', key))
            tutorial_helper = load(refs['tutorialHelper'], '_phone_tutorial_preparation')
            def tutorial():
                policy.source_guard()
                started = time.time_ns() // 1_000_000
                samples = tutorial_helper.prepare_tutorial(context)
                ended = time.time_ns() // 1_000_000
                validate_tutorial(samples, context.nonce, started, ended)
                write_json(run_root / 'tutorial-observations.private.json', samples)
                policy.event('adapter', 'observation', status='passed', reason='PHONE_TUTORIAL_FRESHLY_OBSERVED')
            # Keep original commands/requirements/timeouts, merely select rows.
            by_id = {row['id']: row for row in admission.catalog['modules']}
            selected = []
            for identifier in admission.plan['moduleIds']:
                row = dict(by_id[identifier])
                row['command'] = [str(admission.source / 'tests/device' / row['command'][0]), *row['command'][1:]]
                selected.append(row)
            catalog = run_root / 'catalog.private.json'
            write_json(catalog, {'schemaVersion': 1, 'modules': selected})
            runner = load(refs['originalRun'], '_phone_original_harness')
            debug.install_run_hooks(runner, policy)
            debug.install_admission_hooks(runner, policy)
            install_first_failure(runner, policy, tutorial)
            original_discover = runner.discover
            def discover(*discovery_args, **discovery_kwargs):
                target_description = original_discover(*discovery_args, **discovery_kwargs)
                if not set(admission.plan['requiredCapabilities']) <= set(target_description['capabilities']):
                    policy.hold('PHONE_ACTUAL_CAPABILITIES_MISSING')
                return target_description
            runner.discover = discover
            args = [str(refs['originalRun']), '--adapter-manifest', str(refs['adapterManifest']),
                    '--catalog', str(catalog), '--suite', 'all', '--require-complete',
                    '--candidate-artifact', str(refs['candidate']),
                    '--expected-source-sha', admission.manifest['client']['revision'],
                    '--expected-artifact-sha256', admission.manifest['candidate']['sha256'],
                    '--target', target['selector'], '--output-dir', str(run_root / 'actual')]
            for identifier in admission.plan['setupModuleIds']:
                args += ['--required-setup', identifier]
            if 'tablet-e2e' in admission.plan['moduleIds']:
                args += ['--tablet-policy', str(refs['tabletPolicy'])]
            previous_argv, previous_environment = sys.argv, os.environ.copy()
            try:
                sys.argv = args
                # Discard inherited lab/session selectors; use the admitted namespace.
                for key in list(os.environ):
                    if key.startswith('OVERTE_') or key in ('PYTHONPATH', 'PYTHONHOME', 'ANDROID_SERIAL',
                                                          'ADB_SERVER_SOCKET', 'ANDROID_ADB_SERVER_PORT'):
                        del os.environ[key]
                os.environ.update(environment)
                result = runner.main()
            finally:
                sys.argv = previous_argv
                os.environ.clear()
                os.environ.update(previous_environment)
            need(result == 0, 'PHONE_ORIGINAL_HARNESS_NONZERO')
            assert_complete(json.loads((run_root / 'actual/summary.json').read_bytes()), admission.plan['moduleIds'])
            admission.revalidate()
            context.native_log_guard()
            fixture.finish(context)
            policy.stage.mkdir(mode=0o700)
            for name in ('summary.json', 'junit.xml'):
                with os.fdopen(os.open(policy.stage / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), 'wb') as stream:
                    stream.write((run_root / 'actual' / name).read_bytes())
            policy.publish_terminal()
            export_public(policy, public_root)
            return 0
        except debug.DebugCleanupRequested:
            return RELEASED
        except BaseException as error:
            policy.record_exception(error, 'PHONE_RUNTIME_FAILURE')
            try:
                policy.hold('PHONE_RUNTIME_FAILURE')
            except debug.DebugCleanupRequested:
                return RELEASED
