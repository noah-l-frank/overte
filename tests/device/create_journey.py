"""Ordinary Create operations judged by fresh, read-only entity observations."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import math

from contracts import validate_operation_arguments, validate_operation_result
from create_observation import FreshCreate, PREFIX, owned_url

INITIAL = {'color': {'red': 35, 'green': 125, 'blue': 220},
           'dimensions': {'x': 0.5, 'y': 0.6, 'z': 0.7}}
EDITED = {'color': {'red': 220, 'green': 65, 'blue': 110},
          'dimensions': {'x': 0.8, 'y': 0.9, 'z': 1.0}}
IMPORTED = {'import-parent': {'color': {'red': 210, 'green': 40, 'blue': 70},
                            'dimensions': {'x': 0.5, 'y': 0.5, 'z': 0.5}},
            'import-child': {'color': {'red': 30, 'green': 180, 'blue': 230},
                            'dimensions': {'x': 0.25, 'y': 0.25, 'z': 0.25}}}


def matches(rows, expected, *, parented=False):
    if len(rows) != len(expected) or {row['name'] for row in rows} != set(expected):
        return False
    for row in rows:
        # Native ShapeEntityItem maps Cube to legacy EntityTypes::Box. Both
        # serialization names denote this exact Cube; a Sphere never qualifies.
        if (row['type'] not in {'Shape', 'Box'} or row['shape'] != 'Cube'
                or row['host'] != 'avatar' or row['ownedByCurrentAvatar'] is not True):
            return False
        wanted = expected[row['name']]
        if row['color'] != wanted['color'] or any(
                abs(row['dimensions'][key] - wanted['dimensions'][key]) > 0.0001 for key in ('x', 'y', 'z')):
            return False
    if parented:
        parent = next(row for row in rows if row['name'].endswith('_import-parent'))
        child = next(row for row in rows if row['name'].endswith('_import-child'))
        if (parent['parentId'] is not None or parent['hasExternalParent']
                or child['parentId'] != parent['id'] or child['hasExternalParent']):
            return False
    elif any(row['parentId'] is not None or row['hasExternalParent'] for row in rows):
        return False
    return True


def create_journey(observer_url, import_url, missing_url, *, invoke, observe,
                   assert_session, monotonic, sleep, report):
    nonce = owned_url(observer_url, {'observer.js'})
    base = observer_url.removesuffix('observer.js')
    if (import_url != base + 'entities.json' or missing_url != base + 'missing.json'
            or owned_url(import_url, {'entities.json'}) != nonce
            or owned_url(missing_url, {'missing.json'}) != nonce):
        raise ValueError('Create resources must belong to the same exact owned session')
    prefix = PREFIX + nonce + '_'
    cube = prefix + 'cube'
    names = [cube, prefix + 'import-child', prefix + 'import-parent']
    fresh = FreshCreate(nonce)
    phases, samples = [], []
    primary_error = None
    may_have_created = False
    last_clock = None

    def now():
        nonlocal last_clock
        value = monotonic()
        if (type(value) not in (int, float) or not math.isfinite(value)
                or last_clock is not None and value < last_clock):
            raise ValueError('Create journey requires a finite monotonic clock')
        last_clock = value
        return value

    def action(name, arguments=None):
        return validate_operation_result(name, invoke(
            name, validate_operation_arguments(name, arguments or {})))

    def wait(phase, expected, *, parented=False, import_after=None, missing_after=None):
        deadline = now() + 20
        consistent = []
        last = None
        for _attempt in range(81):
            assert_session('before Create native-state observation')
            value, is_new = fresh.accept(observe())
            assert_session('after Create native-state observation')
            samples.append({'phase': phase, 'observedMonotonicSeconds': now(), 'observation': value})
            last = value
            frame = value['frame']
            if is_new and frame is not None:
                recent = value['sampleMonotonicSeconds'] - frame['receivedMonotonicSeconds'] <= 1.5
                delivered = (value['sourceGets'] >= 1
                    and (import_after is None or value['importGets'] > import_after)
                    and (missing_after is None or value['missingGets'] > missing_after))
                if recent and delivered and matches(frame['entities'], expected, parented=parented):
                    consistent.append(frame)
                    if (len(consistent) >= 3 and consistent[-1]['receivedMonotonicSeconds']
                            - consistent[0]['receivedMonotonicSeconds'] >= 0.5):
                        phases.append({'phase': phase, 'sequence': frame['sequence'],
                            'entities': frame['entities'], 'stableNativeSamples': len(consistent)})
                        return value
                else:
                    consistent = []
            if now() >= deadline:
                break
            sleep(0.25)
        raise AssertionError(f'Normal Create {phase} did not produce its required fresh owned entity state')

    try:
        assert_session('before normal Create observer and panel entry')
        action('create.reference.open', {'scriptUrl': observer_url})
        baseline = wait('baseline-live-empty', {})
        if baseline['importGets'] or baseline['missingGets']:
            raise AssertionError('Create fixture session was already used')
        # Cleanup may target these unpredictable names only after an empty live
        # baseline. A pre-existing matching object must never be deleted.
        may_have_created = True
        action('create.cube', {'name': cube, 'properties': INITIAL})
        wait('create-cube', {cube: INITIAL})
        action('create.update', {'name': cube, 'properties': EDITED})
        wait('edit-color-and-dimensions', {cube: EDITED})
        action('create.undo')
        wait('undo-edit', {cube: INITIAL})
        action('create.redo')
        wait('redo-edit', {cube: EDITED})
        action('create.delete', {'names': [cube]})
        wait('delete', {})
        action('create.undo')
        wait('undo-delete', {cube: EDITED})
        action('create.redo')
        before_import = wait('redo-delete', {})
        expected_import = {prefix + name: properties for name, properties in IMPORTED.items()}
        action('create.import', {'url': import_url})
        wait('json-import-parent-and-child', expected_import, parented=True,
             import_after=before_import['importGets'])
        action('create.undo')
        wait('undo-import', {})
        action('create.redo')
        wait('redo-import', expected_import, parented=True)
        action('create.undo')
        before_missing = wait('remove-owned-import', {})
        action('create.import', {'url': missing_url})
        wait('failed-import-remains-empty', {}, missing_after=before_missing['missingGets'])
        return {'qualification': 'CREATE_CUBE_EDIT_HISTORY_JSON_IMPORT_ONLY',
                'phases': phases, 'deviceAcceptance': False}
    except BaseException as error:
        primary_error = error
        raise
    finally:
        cleanup_errors = []
        cleanup_observed_empty = False
        actions = [('create.delete', {'names': names})] if may_have_created else []
        actions.append(('create.reference.close', {'scriptUrl': observer_url}))
        for name, arguments in actions:
            try:
                action(name, arguments)
                if name == 'create.delete':
                    wait('cleanup-live-empty', {})
                    cleanup_observed_empty = True
            except BaseException as error:
                cleanup_errors.append(error)
        report({'schemaVersion': 1, 'phases': phases, 'samples': samples,
            'cleanupInputsDelivered': not cleanup_errors,
            'cleanupObservedEmpty': cleanup_observed_empty,
            'ownedObjectCleanupEnabled': may_have_created,
            'sequenceCompleted': primary_error is None and not cleanup_errors,
            'deviceAcceptance': False,
            'scope': 'Normal owned avatar Cube creation/edit/history/delete and parent-child JSON import only. Native adapter qualification, visual geometry, local/model/voxel imports and complete Create acceptance remain separate.'})
        if primary_error is None and cleanup_errors:
            raise cleanup_errors[0]
