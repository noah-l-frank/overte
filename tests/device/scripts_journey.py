"""Normal Running Scripts lifecycle with independently observed execution."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import math
from urllib.parse import urlsplit

from contracts import validate_operation_arguments, validate_operation_result
from scripts_observation import FreshJournal, script_url


def scripts_journey(source, missing, *, invoke, observe, assert_session,
                    monotonic, sleep, report):
    nonce = script_url(source)
    if script_url(missing, missing=True) != nonce or urlsplit(source).netloc != urlsplit(missing).netloc:
        raise ValueError('Script sources must belong to the same fixture session')
    if missing != source.removesuffix('client.js') + 'missing.js':
        raise ValueError('Script failure source must use the same exact owned origin')
    journal = FreshJournal(nonce)
    snapshots, phases = [], []
    primary_error = None
    cleanup_delivered = False
    last_clock = None

    def now():
        nonlocal last_clock
        value = monotonic()
        if (type(value) not in (int, float) or not math.isfinite(value)
                or last_clock is not None and value < last_clock):
            raise ValueError('Script journey requires a finite monotonic clock')
        last_clock = value
        return value

    def action(name, arguments=None):
        return validate_operation_result(name, invoke(
            name, validate_operation_arguments(name, arguments or {})))

    def sample(phase):
        assert_session('before script execution observation')
        value = journal.accept(observe())
        assert_session('after script execution observation')
        snapshots.append({'phase': phase, 'observedMonotonicSeconds': now(), 'journal': value})
        return value

    def instances(value):
        return {row['id']: row['events'] for row in value['instances']}

    def new_instance(previous_ids, phase):
        deadline = now() + 20
        for _attempt in range(41):
            state = sample(phase)
            current = instances(state)
            added = set(current) - previous_ids
            if len(added) > 1:
                raise AssertionError('Normal script action created duplicate executing instances')
            if len(added) == 1:
                identifier = next(iter(added))
                events = current[identifier]
                if (len(events) >= 3 and events[-1]['receivedMonotonicSeconds']
                        - events[0]['receivedMonotonicSeconds'] >= 0.5
                        and state['sourceGets'] >= 1 and state['companionGets'] >= 1):
                    phases.append({'phase': phase, 'instance': identifier,
                                   'sampleSequence': state['sampleSequence']})
                    return identifier, state
            if now() >= deadline:
                break
            sleep(0.5)
        raise AssertionError(f'Normal script {phase} did not execute with its actual companion')

    def quiet(stopped, active, phase, *, missing_after=None):
        # A bounded sliding window allows a request already in flight to retire.
        # A continuously running old script must never qualify as stopped.
        state = sample(phase)
        allowed = set(stopped) | set(active)
        baseline = {key: len(value) for key, value in instances(state).items()}
        started = now()
        quiet_since = state['sampleMonotonicSeconds']
        for _attempt in range(33):
            sleep(0.5)
            state = sample(phase)
            events = instances(state)
            current = {key: len(value) for key, value in events.items()}
            if set(current) != allowed:
                raise AssertionError('Unexpected script instance appeared during stop/restart')
            if any(current[key] != baseline[key] for key in stopped):
                quiet_since = state['sampleMonotonicSeconds']
                for key in stopped:
                    baseline[key] = current[key]
            # Activity must be recent at the actual server capture, not merely
            # two early ticks accumulated before the restarted engine died.
            # Compare one server clock; slow adapter continuity reads must not
            # manufacture a long quiet observation after an earlier snapshot.
            active_progress = all(current[key] >= baseline[key] + 2
                and state['sampleMonotonicSeconds'] - events[key][-1]['receivedMonotonicSeconds'] <= 1.5
                for key in active)
            missing_seen = missing_after is None or state['missingGets'] > missing_after
            quiet_seconds = state['sampleMonotonicSeconds'] - quiet_since
            if quiet_seconds >= 3 and active_progress and missing_seen:
                phases.append({'phase': phase, 'quietSeconds': quiet_seconds,
                               'sampleSequence': state['sampleSequence']})
                return state
            if now() - started >= 12:
                break
        raise AssertionError(f'Script {phase} did not establish stopped instances and required execution/delivery')

    try:
        assert_session('before normal Running Scripts entry')
        action('scripts.manager.open')
        baseline = sample('baseline')
        if baseline['instances'] or any(baseline[key] for key in ('sourceGets', 'companionGets', 'missingGets')):
            raise AssertionError('Script fixture session was already used')
        action('scripts.load-url', {'url': source})
        first, _state = new_instance(set(), 'initial-load')
        action('scripts.restart', {'url': source})
        second, _state = new_instance({first}, 'restart')
        quiet({first}, {second}, 'restart-old-stopped-new-active')
        action('scripts.stop', {'url': source})
        quiet({first, second}, set(), 'stop')
        action('scripts.load-url', {'url': source})
        third, _state = new_instance({first, second}, 'load-after-stop')
        quiet({first, second}, {third}, 'reloaded-old-stopped-new-active')
        action('scripts.stop', {'url': source})
        stopped = quiet({first, second, third}, set(), 'final-stop')
        action('scripts.load-url', {'url': missing})
        quiet({first, second, third}, set(), 'failed-load-remains-stopped',
              missing_after=stopped['missingGets'])
        return {'qualification': 'SCRIPT_MANAGER_URL_LIFECYCLE_ONLY',
                'phases': phases, 'deviceAcceptance': False}
    except BaseException as error:
        primary_error = error
        raise
    finally:
        cleanup_errors = []
        for name, arguments in (('scripts.stop', {'url': source}), ('scripts.manager.close', {})):
            try:
                action(name, arguments)
            except BaseException as error:
                cleanup_errors.append(error)
        cleanup_delivered = not cleanup_errors
        report({'schemaVersion': 1, 'phases': phases, 'snapshots': snapshots,
                'cleanupInputsDelivered': cleanup_delivered,
                'lifecycleSequenceCompleted': primary_error is None and cleanup_delivered,
                'deviceAcceptance': False,
                'scope': 'Normal URL script load/restart/stop/reload and failed HTTP load only. Native adapter qualification, folder imports, persistence and complete script-management acceptance remain separate.'})
        if primary_error is None and cleanup_errors:
            raise cleanup_errors[0]
