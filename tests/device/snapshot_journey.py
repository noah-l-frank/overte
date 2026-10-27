"""Normal SNAP UI actions followed by independent, fresh output-file decoding."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import math
import re

from contracts import validate_operation_arguments, validate_operation_result
from snapshot_observation import inspect_snapshot


CASES = (('still-png', 'still', 'png'), ('still-jpg', 'still', 'jpg'),
         ('animated', 'animated', 'png'), ('panorama', 'panorama', 'png'),
         ('cubemap', 'cubemap', 'png'))


def snapshot_journey(nonce, *, invoke, read_artifact, assert_session,
                     monotonic, sleep, report):
    """Exercise five capture cases; native adapters transport files, not verdicts.

    UI delivery acknowledgment cannot establish completion. Polls are bounded,
    and partial encodes may settle before decoding succeeds. Prior files, foreign
    prefixes, missing GIF companions and corrupt/truncated bytes cannot pass.
    """
    if not isinstance(nonce, str) or re.fullmatch('[0-9a-f]{16}', nonce) is None:
        raise ValueError('Snapshot journey requires a fresh 16-hex run nonce')

    def action(name, arguments=None):
        return validate_operation_result(name, invoke(
            name, validate_operation_arguments(name, arguments or {})))

    def now():
        value = monotonic()
        if type(value) not in (int, float) or not math.isfinite(value):
            raise ValueError('Finite monotonic snapshot clock required')
        return value

    results, polls = [], []
    primary_error = None
    closed = False
    try:
        for label, mode, file_format in CASES:
            prefix = f'parity-{nonce}-{label}'
            assert_session('before normal SNAP entry')
            action('snapshot.open')
            if action('snapshot.files', {'prefix': prefix})['files']:
                raise AssertionError('Snapshot run prefix already exists before capture')
            action('snapshot.capture', {'mode': mode, 'format': file_format, 'name': prefix})
            expected = {'png', 'gif'} if mode == 'animated' else {file_format}
            start = now()
            previous = start
            observations = None
            problem = 'no new saved files'
            for attempt in range(65):
                assert_session('before reading original SNAP output')
                files = action('snapshot.files', {'prefix': prefix})['files']
                assert_session('after reading original SNAP output')
                current = now()
                if current < previous:
                    raise ValueError('Snapshot clock moved backwards')
                previous = current
                row = {'case': label, 'attempt': attempt, 'monotonicSeconds': current,
                       'files': files}
                polls.append(row)
                try:
                    by_format = {}
                    for item in files:
                        match = re.fullmatch(re.escape(prefix) + r'-[A-Za-z0-9_-]{1,64}\.(png|jpg|gif)', item['basename'])
                        if match is None or match[1] in by_format:
                            raise ValueError('Original snapshot names are foreign, ambiguous or duplicated')
                        by_format[match[1]] = item
                    if set(by_format) != expected:
                        raise ValueError('Expected fresh still/GIF output set is incomplete or unexpected')
                    decoded = []
                    for extension, item in sorted(by_format.items()):
                        observed_mode = 'animated' if extension == 'gif' else 'still' if mode == 'animated' else mode
                        content = read_artifact(item['artifact'])
                        decoded.append(inspect_snapshot(content, mode=observed_mode, file_format=extension)
                                       | {'artifact': item['artifact'], 'basename': item['basename']})
                    # The GIF and still must originate from the same capture ticket.
                    if mode == 'animated' and len({item['basename'].rsplit('.', 1)[0] for item in files}) != 1:
                        raise ValueError('Animated and still outputs have different capture tickets')
                    observations = decoded
                    row['completeOutputBytesObserved'] = True
                    break
                except (ValueError, OSError, EOFError, SyntaxError) as error:
                    problem = str(error)
                    row['pendingReason'] = problem
                if current - start >= 65:
                    break
                sleep(1)
            if observations is None:
                raise AssertionError(f'Normal SNAP {label} did not produce complete fresh output: {problem}')
            results.append({'case': label, 'outputs': observations})
            assert_session('after decoded SNAP output')
        return results
    except BaseException as error:
        primary_error = error
        raise
    finally:
        try:
            action('snapshot.close')
            closed = True
        except BaseException:
            if primary_error is None:
                raise
        finally:
            report({'schemaVersion': 1, 'cases': results, 'polls': polls,
                    'normalCloseSucceeded': closed,
                    'outputSequenceCompleted': closed and primary_error is None and len(results) == len(CASES),
                    'deviceAcceptance': False,
                    'scope': 'Normal SNAP capture and independently decoded original file bytes only; no system save/share, cancellation, motion or whole-feature acceptance.'})
