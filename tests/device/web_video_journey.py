"""Drive normal reference Web controls and inspect independently captured pixels.

The native adapter performs actions only. It never receives pixel expectations,
the selected ROI, or the analyzer's verdict. Capture/installed-code provenance
still belongs to the runner and the actual platform adapter.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import hashlib
import math
from typing import Callable

from contracts import validate_operation_arguments, validate_operation_result
from media_observation import inspect_paused_video, inspect_playback, inspect_reference_video


def video_journey(surface: str, script_url: str, roi: tuple[int, int, int, int], *,
                  invoke: Callable, capture: Callable, retain: Callable,
                  assert_session: Callable, monotonic: Callable, sleep: Callable,
                  report: Callable) -> dict:
    """Observe play, pause, seek and resume on one normal native Web surface.

    Dependencies are explicit for hardware-free counterfactual testing. The
    production module supplies only the existing native operations and clock.
    No source, image generator, player clock or DOM fallback exists here.
    """
    open_arguments = {'surface': surface, 'scriptUrl': script_url}
    validate_operation_arguments('web.reference.open', open_arguments)
    # Geometry errors are infrastructure errors, not a product failure.
    if (not isinstance(roi, (tuple, list)) or len(roi) != 4
            or any(type(n) is not int for n in roi)):
        raise ValueError('Explicit integer native-video ROI required')

    def action(name, arguments):
        return validate_operation_result(name, invoke(
            name, validate_operation_arguments(name, arguments)))

    captures, observations = [], {}
    primary_error = None
    observation = None
    closed = False

    def sample(phase):
        assert_session('before native video capture')
        started = monotonic()
        content = capture()
        finished = monotonic()
        if (not isinstance(content, bytes) or not 0 < len(content) <= 32 * 1024 * 1024
                or any(type(n) not in (int, float) or not math.isfinite(n) for n in (started, finished))
                or finished < started):
            raise ValueError('Invalid native capture bytes or clock interval')
        artifact = retain(len(captures), content)
        captures.append({'artifact': artifact, 'phase': phase,
                         'sha256': hashlib.sha256(content).hexdigest(),
                         'captureStartedMonotonicSeconds': started,
                         'captureFinishedMonotonicSeconds': finished})
        assert_session('after native video capture')
        return finished, content

    def series(phase, count, interval, first=None):
        samples = [first] if first is not None else []
        while len(samples) < count:
            if samples:
                sleep(interval)
            samples.append(sample(phase))
        return samples

    try:
        assert_session('before normal Web entry')
        action('web.reference.open', open_arguments)
        action('web.reference.play', {'surface': surface})
        observation = inspect_playback(series('play', 17, 0.4), roi)
        observations['play'] = observation
        if observation['movingReferenceVideoPixelsObserved'] is not True:
            raise AssertionError('Native Web surface did not show the moving encoded reference video')

        action('web.reference.pause', {'surface': surface})
        sleep(0.5)  # Allow a frame already being presented at the tap to retire.
        pause_window = []
        pause_deadline = monotonic() + 6
        paused = {'pausedReferenceVideoPixelsObserved': False}
        for attempt in range(20):
            if pause_window:
                sleep(0.5)
            pause_window.append(sample('pause'))
            if len(pause_window) >= 6:
                paused = inspect_paused_video(pause_window[-6:], roi)
                if paused['pausedReferenceVideoPixelsObserved']:
                    break
            if monotonic() >= pause_deadline:
                break
        observations['pause'] = paused
        if paused['pausedReferenceVideoPixelsObserved'] is not True:
            raise AssertionError('Native Web video did not stop at a stable encoded frame')

        # Choose the opposite reference phase so a no-op seek can never pass
        # merely because playback already happened to stop on the target frame.
        target = 48 if paused['encodedFrame'] < 36 else 0
        observations['seek'] = {'expectedEncodedFrame': target,
                               'pausedReferenceVideoPixelsObserved': False, 'deviceAcceptance': False}
        action('web.reference.seek', {'surface': surface, 'seconds': target // 12})
        deadline = monotonic() + 5
        first = None
        for attempt in range(24):
            current = sample('seek-pending')
            decoded = inspect_reference_video(current[1], roi)
            if decoded['referencePixelsMatch'] and decoded['encodedFrame'] == target:
                first = current
                break
            if monotonic() >= deadline:
                break
            sleep(0.25)
        if first is None:
            raise AssertionError('Native Web seek did not show the requested encoded frame')
        sought = inspect_paused_video(series('seek', 6, 0.5, first), roi, expected_frame=target)
        observations['seek'] = sought
        if sought['pausedReferenceVideoPixelsObserved'] is not True:
            raise AssertionError('Native Web seek did not retain the requested paused video frame')

        action('web.reference.play', {'surface': surface})
        resumed = inspect_playback(series('resume', 17, 0.4), roi)
        observations['resume'] = resumed
        if resumed['movingReferenceVideoPixelsObserved'] is not True:
            raise AssertionError('Native Web video did not resume encoded motion after pause and seek')
        assert_session('after native video control sequence')
        return {'qualification': 'REFERENCE_VIDEO_CONTROL_SEQUENCE_ONLY',
                'observations': observations, 'deviceAcceptance': False}
    except BaseException as error:
        primary_error = error
        raise
    finally:
        try:
            # Also attempt cleanup if open/play failed part way through.
            action('web.reference.close', {'surface': surface})
            closed = True
        except Exception:
            if primary_error is None:
                raise
        finally:
            report({'schemaVersion': 1, 'surface': surface, 'roi': list(roi),
                    'captures': captures, 'observation': observation, 'observations': observations,
                    'controlSequenceCompleted': (closed and primary_error is None
                        and observations.get('resume', {}).get('movingReferenceVideoPixelsObserved') is True),
                    'normalCloseSucceeded': closed, 'deviceAcceptance': False,
                    'scope': 'Native reference video play/pause/seek/resume pixels only; text input, bridge, audible sound and lifecycle remain separate.'})
