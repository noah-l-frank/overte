#!/usr/bin/env python3
"""Plan registered Phone tests from the common catalog; never execute a test."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import sys

DEVICE_ROOT = Path(__file__).resolve().parents[1]
if str(DEVICE_ROOT) not in sys.path:
    sys.path.insert(0, str(DEVICE_ROOT))
from contracts import load_capability_registry, validate_capabilities, validate_identifier
from feature_journeys.scenarios import FOUNDATIONS, SCENARIOS

SCOPES = ('readiness', 'baseline', 'feature-area', 'single-test', 'all-features')
QUALIFICATION = {'source': 'registered', 'device': 'not-qualified-for-this-run'}


class SelectionError(ValueError):
    """Closed planning error; no device qualification or fallback is implied."""


def require(value, code):
    if not value:
        raise SelectionError(code)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'PHONE_SELECTION_DUPLICATE_JSON_KEY')
        result[key] = value
    return result


def _catalog(path):
    path = Path(path)
    require(path.is_file() and not path.is_symlink(), 'PHONE_SELECTION_CATALOG_REQUIRED')
    with path.open('rb') as stream:
        before = os.fstat(stream.fileno())
        require(0 < before.st_size <= 4 * 1024 * 1024, 'PHONE_SELECTION_CATALOG_SIZE')
        raw = stream.read(4 * 1024 * 1024 + 1)
        after = os.fstat(stream.fileno())
    signature = lambda value: (value.st_dev, value.st_ino, value.st_size,
                               value.st_mtime_ns, value.st_ctime_ns)
    require(signature(before) == signature(after) == signature(path.stat())
            and len(raw) == before.st_size, 'PHONE_SELECTION_CATALOG_CHANGED')
    try:
        value = json.loads(raw, object_pairs_hook=_unique_object,
                           parse_constant=lambda _value: (_ for _ in ()).throw(
                               SelectionError('PHONE_SELECTION_NONFINITE_JSON')))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise SelectionError('PHONE_SELECTION_INVALID_JSON') from error
    require(type(value) is dict and set(value) == {'schemaVersion', 'modules'}
            and type(value['schemaVersion']) is int and value['schemaVersion'] == 1
            and type(value['modules']) is list and value['modules'],
            'PHONE_SELECTION_CATALOG_SCHEMA')
    registry = load_capability_registry()
    modules, seen = [], set()
    for module in value['modules']:
        require(type(module) is dict and set(module) == {
            'id', 'description', 'command', 'suites', 'requires', 'timeoutSeconds'},
            'PHONE_SELECTION_MODULE_SCHEMA')
        try:
            validate_identifier(module['id'], 'module id')
            validate_capabilities(module['requires'], registry)
        except ValueError as error:
            raise SelectionError('PHONE_SELECTION_MODULE_CONTRACT') from error
        require(module['id'] not in seen, 'PHONE_SELECTION_DUPLICATE_MODULE')
        seen.add(module['id'])
        require(type(module['description']) is str and bool(module['description'])
                and type(module['timeoutSeconds']) is int and module['timeoutSeconds'] > 0,
                'PHONE_SELECTION_MODULE_METADATA')
        for field in ('command', 'suites'):
            require(type(module[field]) is list and module[field]
                    and all(type(item) is str and item for item in module[field]),
                    'PHONE_SELECTION_MODULE_LIST')
        script = Path(module['command'][0])
        require(not script.is_absolute() and script.parts[0] == 'modules'
                and '..' not in script.parts and script.suffix == '.py',
                'PHONE_SELECTION_COMMAND_PATH')
        require(module['suites'] == sorted(set(module['suites'])),
                'PHONE_SELECTION_SUITE_ORDER')
        modules.append(module)
    return modules, hashlib.sha256(raw).hexdigest()


def build_index(catalog_path):
    """Return all immutable-source selection plans without importing a runner.

    setupModuleIds is the required ordered prefix. A single foundation test
    needs launch-smoke; an area journey also retains its capability gate. Full
    area plans retain every foundation registered by the shared scenarios.
    """
    modules, catalog_sha = _catalog(catalog_path)
    by_id = {module['id']: module for module in modules}
    require('launch-smoke' in by_id, 'PHONE_SELECTION_LAUNCH_SETUP_MISSING')
    require(set(SCENARIOS) == set(FOUNDATIONS) and bool(SCENARIOS),
            'PHONE_SELECTION_SCENARIO_REGISTRY')
    areas, area_modules, gates = [], {}, []
    for area, scenario in SCENARIOS.items():
        suite, gate, journey = 'feature-' + area, 'feature-' + area + '-required', 'feature-' + area
        require(gate in by_id and journey in by_id, 'PHONE_SELECTION_AREA_GATE_OR_JOURNEY_MISSING')
        require(by_id[gate]['command'] == ['modules/feature_capability_gate.py', '--area', area]
                and by_id[journey]['command'] == ['modules/feature_journey.py', '--area', area],
                'PHONE_SELECTION_AREA_COMMAND_CHANGED')
        selected = [module['id'] for module in modules if suite in module['suites']]
        expected = {'launch-smoke', gate, journey, *FOUNDATIONS[area]}
        require(set(selected) == expected, 'PHONE_SELECTION_AREA_FOUNDATION_MISMATCH')
        require(selected[:2] == ['launch-smoke', gate], 'PHONE_SELECTION_AREA_SETUP_PREFIX')
        areas.append({'id': area, 'title': scenario['title'], 'suite': suite})
        area_modules[area] = selected
        gates.append(gate)

    def plan(key, scope, selected, setup, area=None, test=None):
        require(bool(selected) and len(selected) == len(set(selected)),
                'PHONE_SELECTION_EMPTY_OR_DUPLICATE_SELECTION')
        require(selected[:len(setup)] == setup, 'PHONE_SELECTION_SETUP_PREFIX')
        rows = [{field: deepcopy(by_id[name][field])
                 for field in ('id', 'description', 'timeoutSeconds', 'requires')}
                for name in selected]
        return {'id': key, 'scope': scope, 'featureArea': area, 'testCase': test,
                'moduleIds': list(selected), 'setupModuleIds': list(setup), 'modules': rows,
                'requiredCapabilities': sorted({capability for row in rows for capability in row['requires']}),
                'qualification': dict(QUALIFICATION)}

    plans = {'readiness': plan('readiness', 'readiness', ['launch-smoke'], ['launch-smoke'])}
    baseline = [module['id'] for module in modules if 'phone-baseline' in module['suites']]
    require(baseline and baseline[0] == 'launch-smoke', 'PHONE_SELECTION_BASELINE_EMPTY_OR_SETUP_MISSING')
    plans['baseline'] = plan('baseline', 'baseline', baseline, ['launch-smoke'])
    for area, selected in area_modules.items():
        key = 'feature-area:' + area
        plans[key] = plan(key, 'feature-area', selected, ['launch-smoke', 'feature-' + area + '-required'], area)
    setup_ids = {'launch-smoke', *gates}
    for module in modules:
        identifier = module['id']
        if identifier == 'launch-smoke':
            selected, setup, area = [identifier], [identifier], None
        elif identifier in gates:
            selected, setup, area = ['launch-smoke', identifier], ['launch-smoke', identifier], identifier[len('feature-'):-len('-required')]
        elif identifier.startswith('feature-') and identifier[len('feature-'):] in SCENARIOS:
            area = identifier[len('feature-'):]
            setup = ['launch-smoke', 'feature-' + area + '-required']
            selected = [*setup, identifier]
        else:
            selected, setup, area = ['launch-smoke', identifier], ['launch-smoke'], None
        key = 'single-test:' + identifier
        plans[key] = plan(key, 'single-test', selected, setup, area, identifier)
    all_selected = [module['id'] for module in modules if 'feature-journeys' in module['suites']]
    require(set(all_selected) == set().union(*map(set, area_modules.values())),
            'PHONE_SELECTION_ALL_FEATURES_MISMATCH')
    setup = [identifier for identifier in all_selected if identifier in setup_ids]
    require(set(setup) == setup_ids, 'PHONE_SELECTION_ALL_FEATURE_GATES_MISSING')
    plans['all-features'] = plan('all-features', 'all-features', all_selected, setup)
    return {'schemaVersion': 1, 'catalogSha256': catalog_sha, 'scopes': list(SCOPES),
            'featureAreas': areas, 'singleTests': list(by_id), 'plans': plans}


def select_plan(index, scope, feature_area=None, test_case=None):
    """Perform a closed lookup only; never guess or fall back to another scope."""
    require(scope in SCOPES, 'PHONE_SELECTION_UNKNOWN_SCOPE')
    require((scope == 'feature-area') == (feature_area is not None)
            and (scope == 'single-test') == (test_case is not None),
            'PHONE_SELECTION_UNSUPPORTED_ARGUMENT_COMBINATION')
    require((feature_area is None or type(feature_area) is str and feature_area)
            and (test_case is None or type(test_case) is str and test_case),
            'PHONE_SELECTION_INVALID_AREA_OR_TEST')
    key = scope + ':' + (feature_area if scope == 'feature-area' else test_case) if scope in ('feature-area', 'single-test') else scope
    require(key in index['plans'], 'PHONE_SELECTION_UNKNOWN_AREA_OR_TEST')
    return deepcopy(index['plans'][key])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--catalog', type=Path, required=True)
    parser.add_argument('--scope', choices=SCOPES, required=True)
    parser.add_argument('--feature-area')
    parser.add_argument('--test-case')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        index = build_index(args.catalog)
        selected = select_plan(index, args.scope, args.feature_area, args.test_case)
        output = {'schemaVersion': 1, 'catalogSha256': index['catalogSha256'], **selected}
        with args.output.open('x', encoding='utf-8') as stream:
            stream.write(json.dumps(output, indent=2, sort_keys=True) + '\n')
    except (SelectionError, OSError) as error:
        parser.exit(2, str(error) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
