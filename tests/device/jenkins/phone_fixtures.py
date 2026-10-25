#!/usr/bin/env python3
"""Bind the original Phone adapter and owned fixtures, never test verdicts."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit
import uuid


def need(value, code):
    if not value:
        raise ValueError(code)


def load(path, name):
    existing = sys.modules.get(name)
    if existing is not None:
        need(Path(existing.__file__) == path, 'PHONE_FIXTURE_IMPORT_CHANGED')
        return existing
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def checked_reference(context, reference, *, external=False):
    need(type(reference) is dict and set(reference) == {'path', 'sha256'},
         'PHONE_FIXTURE_REFERENCE_SCHEMA')
    path = Path(reference['path'])
    if not external:
        need(not path.is_absolute() and '..' not in path.parts, 'PHONE_FIXTURE_REFERENCE_ESCAPE')
        path = context.admission.deployment / path
    need(path.is_absolute() and path.resolve() == path and path.is_file(),
         'PHONE_FIXTURE_REFERENCE_ALIAS')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        before = os.fstat(stream.fileno())
        raw = stream.read(16 * 1024 * 1024 + 1)
        after = os.fstat(stream.fileno())
    signature = lambda item: (item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns, item.st_ctime_ns)
    need(signature(before) == signature(after) == signature(path.lstat())
         and len(raw) <= 16 * 1024 * 1024
         and hashlib.sha256(raw).hexdigest() == reference['sha256'], 'PHONE_FIXTURE_REFERENCE_CHANGED')
    return path, raw


def domain_environment(original, scene_ready, domain_ready, manifest):
    """Validate original native READY, after the independent active-owner gate."""
    parsed = urlsplit(domain_ready['domainUrl'])
    need(domain_ready.get('schemaVersion') == 1 and parsed.scheme == 'hifi'
         and parsed.hostname == domain_ready['domainHost'] and parsed.port is not None
         and parsed.username is None and parsed.password is None
         and not parsed.query and not parsed.fragment,
         'PHONE_FIXTURE_DOMAIN_URL')
    need(str(uuid.UUID(domain_ready['domainId'])) == domain_ready['domainId']
         and domain_ready['requiredMarkers'] == manifest['requiredMarkers']
         and domain_ready['expectedEntityCount'] == manifest['expectedEntityCount']
         and parsed.path == manifest['spawnPath'], 'PHONE_FIXTURE_DOMAIN_SEMANTICS')
    values = original.environment(scene_ready, domain_ready)
    keys = ('OVERTE_E2E_DOMAIN_URL', 'OVERTE_E2E_DOMAIN_HOST', 'OVERTE_E2E_DOMAIN_ID',
            'OVERTE_E2E_DOMAIN_MARKERS_JSON', 'OVERTE_E2E_DOMAIN_CONTROL_URL',
            'OVERTE_E2E_DOMAIN_CONTROL_TOKEN')
    need(all(type(values.get(key)) is str and values[key] for key in keys),
         'PHONE_FIXTURE_DOMAIN_ENVIRONMENT')
    return {key: values[key] for key in keys}


def prepare(context):
    """Prepare host infrastructure only; no SDK/ADB operation is allowed here."""
    context.source_guard()
    config = json.loads(context.fixture_config.read_bytes())
    need(type(config) is dict and set(config) == {
        'schemaVersion', 'candidateArguments', 'sceneConfiguration', 'nativeReady'}
         and config['schemaVersion'] == 1, 'PHONE_FIXTURE_CONFIG_SCHEMA')
    _, raw = checked_reference(context, config['candidateArguments'])
    arguments = json.loads(raw)
    need(type(arguments) is list and all(type(item) is str for item in arguments)
         and arguments and all(item not in ('discover', 'invoke', 'cleanup', 'describe')
                               for item in arguments), 'PHONE_FIXTURE_CANDIDATE_ARGUMENTS')
    source = context.admission.source
    phone = source / 'tests/device/adapters/android-phone'
    sys.path[:0] = [str(phone), str(source / 'tests/device'),
                   str(source / 'android/phone/tests/candidate')]
    binding = load(phone / 'adapter.py', 'adapter')
    parameters = binding.parse_args(['describe', *arguments])
    candidate = binding.VerifiedCandidate(parameters)
    verified = candidate.verify()  # Original SH-009 and optional SH-002 checks.
    need(verified['sourceRevision'] == context.admission.manifest['client']['revision']
         and verified['artifactSha256'] == context.admission.manifest['candidate']['sha256'],
         'PHONE_FIXTURE_CANDIDATE_IDENTITY')
    appium = load(phone / 'appium_adapter.py', 'appium_adapter')
    previous = os.environ.copy()
    try:
        for key in list(os.environ):
            if key.startswith('OVERTE_') or key in ('ANDROID_SERIAL', 'ADB_SERVER_SOCKET'):
                del os.environ[key]
        os.environ.update(context.environment)
        context.phone_adapter = appium.PhoneAppiumAdapter(candidate)
    finally:
        os.environ.clear()
        os.environ.update(previous)
    # Readiness only launches and verifies the installed client; it needs no
    # scene listener or native domain. Keep that scope genuinely lightweight.
    if context.admission.plan['moduleIds'] == ['launch-smoke']:
        return {}
    scene_config, _ = checked_reference(context, config['sceneConfiguration'])
    owner = load(source / 'tests/device/jenkins/phone_owned_scene.py', '_phone_owned_scene')
    inventory = context.admission.manifest['source']['inventory']
    service = owner.OwnedScene(source, context.admission.deployment / inventory['path'],
                              inventory['sha256'], scene_config,
                              config['sceneConfiguration']['sha256'], context.run_root / 'scene-runtime')
    context.scene_service = service  # Retain the exact owner even on startup failure.
    service.__enter__()
    approved = context.target.get('controls', {}).get('normalNavigation', {}).get('sceneUrl')
    need(service.ready['sceneUrl'] == approved, 'PHONE_FIXTURE_APPROVED_SCENE_CHANGED')
    values = dict(service.environment)
    if config['nativeReady'] is not None:
        gate = context.policy.config['nativeGate']
        required = context.policy.config['domainRequiredModules']
        selected = [identifier for identifier in context.admission.plan['moduleIds'] if identifier in required]
        if selected:
            context.native_modules = selected
            context.policy.native_gate(selected[0])
            path, ready_raw = checked_reference(context, config['nativeReady'], external=True)
            start = json.loads(Path(gate['startResult']).read_bytes())
            need(start['originalReady'] == {'path': str(path), 'sha256': config['nativeReady']['sha256']},
                 'PHONE_FIXTURE_NATIVE_READY_BINDING')
            manifest = json.loads((source / 'tests/device/fixture/domain-manifest.json').read_bytes())
            values.update(domain_environment(service.original, service.ready, json.loads(ready_raw), manifest))
    context.source_guard()
    return values


def finish(context):
    """Dispose only this run's exact service, and only after every test passed."""
    context.source_guard()
    for identifier in getattr(context, 'native_modules', [])[-1:]:
        context.policy.native_gate(identifier)
    service = getattr(context, 'scene_service', None)
    if service is not None:
        cleanup = service.stop()
        need(cleanup['complete'], 'PHONE_FIXTURE_OWNED_SERVICE_CLEANUP_INCOMPLETE')
