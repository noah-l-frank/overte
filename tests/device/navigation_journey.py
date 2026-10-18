"""Normal Go To and history inputs judged by actual scene and avatar state."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import math

from contracts import validate_operation_arguments, validate_operation_result
from navigation_observation import FreshNavigation, arrived, viewpoint_urls


def navigation_journey(scene_url, *, invoke, observe, assert_session, monotonic, sleep, report):
    urls = viewpoint_urls(scene_url)
    fresh = FreshNavigation()
    phases, samples = [], []
    primary_error = None
    owned_scene_confirmed = False
    last_clock = None

    def now():
        nonlocal last_clock
        value = monotonic()
        if (type(value) not in (int, float) or not math.isfinite(value)
                or last_clock is not None and value < last_clock):
            raise ValueError('Go To requires a finite monotonic clock')
        last_clock = value
        return value

    def action(operation, arguments=None):
        if operation != 'places.close':
            assert_session('before ordinary Go To input')
        return validate_operation_result(operation, invoke(operation,
            validate_operation_arguments(operation, arguments or {})))

    def wait(phase, label):
        deadline = now() + 30
        stable = []
        for _attempt in range(121):
            assert_session('before actual navigation-state observation')
            value, advanced = fresh.accept(observe())
            assert_session('after actual navigation-state observation')
            captured = now()
            samples.append({'phase': phase, 'observedMonotonicSeconds': captured, 'observation': value})
            if arrived(value, urls[label], label):
                if advanced:
                    stable.append((captured, value))
                    if len(stable) >= 3 and stable[-1][0] - stable[0][0] >= 0.5:
                        phases.append({'phase': phase, 'viewpoint': label,
                            'stableAdvancingSamples': len(stable), 'lastObservation': value})
                        return
            else:
                stable = []
            if now() >= deadline:
                break
            sleep(0.25)
        raise AssertionError(f'Normal Go To {phase} did not reach its actual scene/viewpoint with fresh presentation')

    try:
        action('places.open')
        action('places.goto', {'url': urls['A']})
        wait('goto-A', 'A')
        owned_scene_confirmed = True
        for label in ('B', 'C'):
            action('places.goto', {'url': urls[label]})
            wait('goto-' + label, label)
        for operation, label in (('places.back', 'B'), ('places.back', 'A'),
                                 ('places.forward', 'B'), ('places.forward', 'C')):
            action(operation)
            wait(operation.removeprefix('places.') + '-to-' + label, label)
        return {'qualification': 'NORMAL_CONTROLLED_GOTO_AND_HISTORY_ONLY',
                'phases': phases, 'deviceAcceptance': False}
    except BaseException as error:
        primary_error = error
        raise
    finally:
        cleanup_errors = []
        if owned_scene_confirmed:
            try:
                action('places.goto', {'url': urls['A']})
                wait('cleanup-restored-A', 'A')
            except BaseException as error:
                cleanup_errors.append(error)
        try:
            # Partial entry must still release its owned panels and dialogs.
            action('places.close')
        except BaseException as error:
            cleanup_errors.append(error)
        report({'schemaVersion': 1, 'phases': phases, 'samples': samples,
            'controlledRestoreEnabled': owned_scene_confirmed,
            'cleanupSucceeded': not cleanup_errors,
            'sequenceCompleted': primary_error is None and not cleanup_errors,
            'deviceAcceptance': False,
            'scope': 'Normal controlled HTTP scene Go To, actual viewpoint arrival and Back/Forward only. Native adapters, bookmark CRUD, directory/search, failed-navigation UX and whole-feature/device acceptance remain separate.'})
        if primary_error is None and cleanup_errors:
            raise cleanup_errors[0]
