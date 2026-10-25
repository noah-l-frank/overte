#!/usr/bin/env python3
"""Admit one immutable Phone deployment before starting its original harness."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import sys

sys.dont_write_bytecode = True
SHA = re.compile(r'[0-9a-f]{64}')
REVISION = re.compile(r'[0-9a-f]{40}')


class AdmissionError(ValueError):
    """Closed admission failure; no device input has been authorized."""


def need(ok, code):
    if not ok:
        raise AdmissionError(code)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def decode(raw):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            need(key not in value, 'PHONE_DUPLICATE_JSON_KEY')
            value[key] = item
        return value
    try:
        return json.loads(raw, object_pairs_hook=unique,
                          parse_constant=lambda _: need(False, 'PHONE_NONFINITE_JSON'))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise AdmissionError('PHONE_INVALID_JSON') from error


def read_regular(path, limit=16 * 1024 * 1024, *, private=False):
    path = Path(path)
    need(path.is_absolute() and path.resolve() == path, 'PHONE_PATH_ALIAS')
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK), 'rb') as stream:
        before = os.fstat(stream.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_size <= limit, 'PHONE_REGULAR_FILE_REQUIRED')
        if private:
            need(before.st_uid == os.geteuid() and before.st_nlink == 1
                 and stat.S_IMODE(before.st_mode) == 0o600, 'PHONE_PRIVATE_FILE_REQUIRED')
        raw = stream.read(limit + 1)
        after = os.fstat(stream.fileno())
    signature = lambda item: (item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns, item.st_ctime_ns)
    need(signature(before) == signature(after) == signature(path.lstat())
         and len(raw) == before.st_size, 'PHONE_FILE_CHANGED')
    return raw


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def checked_root(value):
    need(type(value) is str, 'PHONE_ROOT_REQUIRED')
    path = Path(value)
    need(path.is_absolute() and path.resolve() == path and path.is_dir(), 'PHONE_ROOT_ALIAS')
    return path


def checked_ref(root, ref, *, limit=16 * 1024 * 1024):
    need(type(ref) is dict and set(ref) == {'path', 'sha256'}
         and type(ref['path']) is str and type(ref['sha256']) is str
         and SHA.fullmatch(ref['sha256']),
         'PHONE_REFERENCE_SCHEMA')
    relative = Path(ref['path'])
    need(not relative.is_absolute() and '..' not in relative.parts
         and relative.parts and relative.as_posix() == ref['path'], 'PHONE_REFERENCE_ESCAPE')
    path = root / relative
    need(path.resolve() == path and path.is_relative_to(root), 'PHONE_REFERENCE_ESCAPE')
    raw = read_regular(path, limit)
    need(digest(raw) == ref['sha256'], 'PHONE_REFERENCE_HASH')
    return path, raw


def verify_embedded_references(root, value):
    """Admit explicit external fixture metadata only from a pinned recipe file.

    Evolving log streams have scoped paths rather than hashes and are checked
    by the existing publisher's prefix snapshot contract at publication time.
    """
    if type(value) is list:
        for item in value:
            verify_embedded_references(root, item)
    elif type(value) is dict:
        if {'path', 'sha256'} <= set(value):
            need(type(value['path']) is str and type(value['sha256']) is str
                 and SHA.fullmatch(value['sha256']), 'PHONE_EMBEDDED_REFERENCE_SCHEMA')
            path = Path(value['path'])
            if path.is_absolute():
                raw = read_regular(path)
                need(digest(raw) == value['sha256'], 'PHONE_EMBEDDED_REFERENCE_CHANGED')
            else:
                _, raw = checked_ref(root, {'path': value['path'], 'sha256': value['sha256']})
            if 'bytes' in value:
                need(type(value['bytes']) is int and len(raw) == value['bytes'], 'PHONE_EMBEDDED_REFERENCE_SIZE')
        # The existing native-owner gate uses companion digest fields.
        for key, digest_value in value.items():
            if key.endswith('Sha256') and key[:-6] in value and type(value[key[:-6]]) is str:
                path = Path(value[key[:-6]])
                need(path.is_absolute() and type(digest_value) is str and SHA.fullmatch(digest_value),
                     'PHONE_EXTERNAL_GATE_REFERENCE')
                need(digest(read_regular(path)) == digest_value, 'PHONE_EXTERNAL_GATE_CHANGED')
        for item in value.values():
            verify_embedded_references(root, item)


def verify_tree(root, inventory):
    need(type(inventory) is dict and inventory, 'PHONE_FULL_INVENTORY_REQUIRED')
    expected = set()
    for name, value in inventory.items():
        need(type(name) is str and type(value) is str and SHA.fullmatch(value), 'PHONE_INVENTORY_SCHEMA')
        path, _ = checked_ref(root, {'path': name, 'sha256': value}, limit=1024 * 1024 * 1024)
        expected.add(path.relative_to(root).as_posix())
    actual = set()
    for directory, dirs, files in os.walk(root, followlinks=False):
        # A staged source export has no Git metadata or generated caches.
        for name in dirs:
            need(not (Path(directory) / name).is_symlink(), 'PHONE_SOURCE_SYMLINK')
        for name in files:
            path = Path(directory) / name
            need(not path.is_symlink(), 'PHONE_SOURCE_SYMLINK')
            actual.add(path.relative_to(root).as_posix())
    need(actual == expected, 'PHONE_SOURCE_INVENTORY_INCOMPLETE')


@dataclass(frozen=True)
class Admitted:
    manifest: dict
    deployment: Path
    run_root: Path
    source: Path
    client: Path
    inventory: dict
    plan: dict
    catalog: dict
    recipe: dict
    references: dict
    manifest_sha256: str
    manifest_path: Path

    def revalidate(self):
        """Recheck the original bytes and both complete source contexts."""
        need(digest(read_regular(self.manifest_path, private=True)) == self.manifest_sha256,
             'PHONE_MANIFEST_CHANGED_DURING_RUN')
        for name in ('source', 'client'):
            _, raw = checked_ref(self.deployment, self.manifest[name]['inventory'])
            verify_tree(Path(self.manifest[name]['root']), decode(raw))
        for name in ('catalog', 'planner', 'worker', 'delta'):
            checked_ref(self.deployment, self.manifest[name])
        checked_ref(self.deployment, {key: self.manifest['candidate'][key] for key in ('path', 'sha256')},
                    limit=1024 * 1024 * 1024)
        for identifier in self.plan['moduleIds']:
            _, raw = checked_ref(self.deployment, self.manifest['recipes'][identifier])
            for reference in decode(raw)['files'].values():
                checked_ref(self.deployment, reference)
        for name in ('debugTemplate', 'fixtureConfig'):
            verify_embedded_references(self.deployment, decode(read_regular(self.references[name])))


def admit(manifest_path, manifest_sha256, environment):
    """Read-only admission. Import no adapter, execute no process, create no output."""
    need(type(manifest_sha256) is str and SHA.fullmatch(manifest_sha256), 'PHONE_MANIFEST_PIN')
    raw = read_regular(manifest_path, private=True)
    need(digest(raw) == manifest_sha256, 'PHONE_MANIFEST_HASH')
    value = decode(raw)
    need(type(value) is dict and set(value) == {
        'schemaVersion', 'deploymentRoot', 'runRoot', 'source', 'client', 'delta',
        'catalog', 'planner', 'worker', 'candidate', 'recipes'}, 'PHONE_MANIFEST_SCHEMA')
    need(type(value['schemaVersion']) is int and value['schemaVersion'] == 1, 'PHONE_MANIFEST_VERSION')
    deployment = checked_root(value['deploymentRoot'])
    need(Path(manifest_path).parent == deployment, 'PHONE_MANIFEST_LOCATION')
    need(environment.get('JOB_NAME') == 'overte-pixel6a'
         and type(environment.get('BUILD_NUMBER')) is str
         and re.fullmatch(r'[1-9][0-9]{0,9}', environment.get('BUILD_NUMBER', '')),
         'PHONE_JENKINS_NAMESPACE')
    need(environment.get('OVT_PHONE_EXECUTION') == 'live'
         and environment.get('OVT_PHONE_FAILURE_POLICY') == 'debug-hold', 'PHONE_LIVE_POLICY_REQUIRED')
    run_base = checked_root(value['runRoot'])
    need(not run_base.is_relative_to(deployment), 'PHONE_OUTPUT_SOURCE_OVERLAP')
    run_root = run_base / ('overte-pixel6a-' + environment['BUILD_NUMBER'])
    need(not run_root.exists() and run_root.resolve(strict=False) == run_root, 'PHONE_FRESH_RUN_REQUIRED')
    contexts = []
    for name in ('source', 'client'):
        context = value[name]
        need(type(context) is dict and set(context) == {'root', 'revision', 'inventory'}
             and type(context['revision']) is str and REVISION.fullmatch(context['revision']), 'PHONE_SOURCE_CONTEXT')
        root = checked_root(context['root'])
        need(root.is_relative_to(deployment) and root != deployment, 'PHONE_SOURCE_ROOT_ESCAPE')
        _, inventory_raw = checked_ref(deployment, context['inventory'])
        inventory = decode(inventory_raw)
        verify_tree(root, inventory)
        contexts.append((root, inventory))
    (source, inventory), (client, client_inventory) = contexts
    need(source != client and not source.is_relative_to(client)
         and not client.is_relative_to(source), 'PHONE_SOURCE_CONTEXT_OVERLAP')
    _, delta_raw = checked_ref(deployment, value['delta'])
    expected_delta = {name: {'client': client_inventory.get(name), 'harness': inventory.get(name)}
                      for name in sorted(set(client_inventory) | set(inventory))
                      if client_inventory.get(name) != inventory.get(name)}
    need(decode(delta_raw) == expected_delta, 'PHONE_SOURCE_DELTA_MISMATCH')
    references = {}
    for name in ('catalog', 'planner', 'worker'):
        path, content = checked_ref(deployment, value[name])
        references[name] = path
        need(path.is_relative_to(source) and inventory.get(path.relative_to(source).as_posix()) == digest(content),
             'PHONE_EXECUTABLE_OUTSIDE_SOURCE')
    need(references['planner'] == source / 'tests/device/jenkins/phone_selection.py'
         and references['worker'] == source / 'tests/device/jenkins/phone_worker.py'
         and references['catalog'] == source / 'tests/device/catalog.json', 'PHONE_FIXED_ENTRY_REQUIRED')
    candidate = value['candidate']
    need(type(candidate) is dict and set(candidate) == {'path', 'sha256', 'sourceRevision'}
         and candidate['sourceRevision'] == value['client']['revision'], 'PHONE_CANDIDATE_SOURCE_MISMATCH')
    references['candidate'], _ = checked_ref(deployment, {key: candidate[key] for key in ('path', 'sha256')},
                                             limit=1024 * 1024 * 1024)
    # Only a pinned pure planner is imported after the complete source exports match.
    planner = load_module(references['planner'], '_phone_admitted_selection')
    index = planner.build_index(references['catalog'])
    need(environment.get('OVT_PHONE_AREA') in {row['id'] for row in index['featureAreas']}
         and environment.get('OVT_PHONE_CASE') in index['singleTests'], 'PHONE_PARAMETER_ENUM')
    scope = environment.get('OVT_PHONE_SCOPE')
    area = environment.get('OVT_PHONE_AREA') if scope == 'feature-area' else None
    case = environment.get('OVT_PHONE_CASE') if scope == 'single-test' else None
    try:
        plan = planner.select_plan(index, scope, area, case)
    except ValueError as error:
        raise AdmissionError('PHONE_SELECTION_REJECTED') from error
    need(type(value['recipes']) is dict, 'PHONE_RECIPES_REQUIRED')
    recipes = []
    for identifier in plan['moduleIds']:
        need(identifier in value['recipes'], 'PHONE_RECIPE_NOT_DEPLOYED')
        recipe_path, recipe_raw = checked_ref(deployment, value['recipes'][identifier])
        recipe = decode(recipe_raw)
        need(type(recipe) is dict and set(recipe) == {
            'schemaVersion', 'kind', 'moduleIds', 'sourceRevision', 'clientSourceRevision',
            'candidateSha256', 'capabilities', 'files'}, 'PHONE_RECIPE_SCHEMA')
        need(type(recipe['schemaVersion']) is int and recipe['schemaVersion'] == 1
             and recipe['kind'] == 'original-harness-v1'
             and recipe['sourceRevision'] == value['source']['revision']
             and recipe['clientSourceRevision'] == value['client']['revision']
             and recipe['candidateSha256'] == candidate['sha256'], 'PHONE_RECIPE_SOURCE_MISMATCH')
        need(type(recipe['moduleIds']) is list and all(type(item) is str for item in recipe['moduleIds'])
             and identifier in recipe['moduleIds']
             and len(recipe['moduleIds']) == len(set(recipe['moduleIds'])), 'PHONE_RECIPE_MODULE_BINDING')
        files = recipe['files']
        need(type(files) is dict and set(files) == {'originalRun', 'adapterManifest', 'environment',
             'targets', 'debugTemplate', 'fixtureHelper', 'fixtureConfig', 'tutorialHelper', 'tabletPolicy'}, 'PHONE_RECIPE_FILES')
        for key, ref in files.items():
            path, content = checked_ref(deployment, ref)
            if key in ('originalRun', 'fixtureHelper', 'tutorialHelper', 'tabletPolicy'):
                need(path.is_relative_to(source) and inventory.get(path.relative_to(source).as_posix()) == digest(content),
                     'PHONE_RECIPE_EXECUTABLE_SOURCE')
            references[key] = path
        need(references['originalRun'] == source / 'tests/device/run.py', 'PHONE_ORIGINAL_RUN_REQUIRED')
        need(references['tabletPolicy'] == source / 'tests/device/policies/android-phone-flat-touch.json',
             'PHONE_TABLET_POLICY_REQUIRED')
        for name in ('debugTemplate', 'fixtureConfig'):
            verify_embedded_references(deployment, decode(read_regular(references[name])))
        need(type(recipe['capabilities']) is list and all(type(cap) is str for cap in recipe['capabilities'])
             and set(plan['requiredCapabilities']) <= set(recipe['capabilities']), 'PHONE_CAPABILITIES_NOT_DEPLOYED')
        recipes.append(recipe)
    need(all(recipe == recipes[0] for recipe in recipes), 'PHONE_MIXED_RECIPE_CONTEXT')
    catalog = decode(read_regular(references['catalog']))
    return Admitted(value, deployment, run_root, source, client, inventory, plan, catalog,
                    recipes[0], references, manifest_sha256, Path(manifest_path))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    sub = parser.add_subparsers(dest='command', required=True)
    run = sub.add_parser('run', allow_abbrev=False)
    run.add_argument('--manifest', type=Path, required=True)
    run.add_argument('--manifest-sha256', required=True)
    args = parser.parse_args(argv)
    try:
        admission = admit(args.manifest, args.manifest_sha256, os.environ)
        worker = load_module(admission.references['worker'], '_phone_admitted_worker')
        return worker.run(admission)
    except (AdmissionError, OSError, ValueError):
        # Private inputs and their exception messages must never reach Jenkins.
        print('PHONE_ADMISSION_REJECTED', file=sys.stderr)
        return 75


if __name__ == '__main__':
    raise SystemExit(main())
