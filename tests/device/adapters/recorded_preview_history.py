"""Atomic native preview metadata and measured Audio state, not input receipts."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import exact, integer, need

FIELDS = {'historyVersion', 'cycle', 'startedEpochMs', 'captureSampleRate',
          'captureChannels', 'historyComplete', 'events'}
ACTIVE = {'capturing', 'playing', 'draining'}
TERMINAL = {'completed', 'cancelled', 'error'}
NEXT = {'capturing': {'capturing', 'playing', 'cancelled', 'error'},
        'playing': {'playing', 'draining', 'cancelled', 'error'},
        'draining': {'draining', 'completed', 'cancelled', 'error'}}


def phases(events):
    result = []
    for event in events:
        if not result or result[-1] != event['phase']: result.append(event['phase'])
    return result


def validate_history(value, epoch):
    need(type(value['historyVersion']) is int and value['historyVersion'] == 1
         and integer(value['cycle']) and integer(value['startedEpochMs'])
         and integer(value['captureSampleRate'], 0, 768000) and integer(value['captureChannels'], 0, 256)
         and value['historyComplete'] is True and type(value['events']) is list and len(value['events']) <= 64)
    events = value['events']
    if value['cycle'] == 0:
        need(not events and value['event'] == {} and not value['active']
             and value['capturedBytes'] == value['playedBytes'] == value['startedEpochMs'] == 0
             and value['captureSampleRate'] == value['captureChannels'] == 0)
        return value
    need(0 < value['startedEpochMs'] <= epoch and events and events[-1] == value['event'])
    rate, channels = value['captureSampleRate'], value['captureChannels']
    supported = 8000 <= rate <= 48000 and 1 <= channels <= 2
    limit = rate * channels * 2 * 3 if supported else 0
    previous = None
    for event in events:
        exact(event, {'schemaVersion', 'eventSequence', 'publishedEpochMs', 'phase', 'error',
                      'capturedBytes', 'playedBytes', 'totalBytes'})
        need(type(event['schemaVersion']) is int and event['schemaVersion'] == 1
             and integer(event['eventSequence'], 1) and integer(event['publishedEpochMs'], value['startedEpochMs'], epoch)
             and event['phase'] in ACTIVE | TERMINAL and type(event['error']) is str and len(event['error']) <= 128
             and not any(ord(c) < 32 for c in event['error'])
             and all(integer(event[key], 0, limit) for key in ('capturedBytes', 'playedBytes', 'totalBytes'))
             and event['playedBytes'] <= event['capturedBytes'] <= event['totalBytes']
             and event['totalBytes'] in (0, limit))
        if previous is None: need(event['phase'] in {'capturing', 'error'})
        else:
            need(event['eventSequence'] == previous['eventSequence'] + 1
                 and event['publishedEpochMs'] >= previous['publishedEpochMs']
                 and event['phase'] in NEXT.get(previous['phase'], set())
                 and event['capturedBytes'] >= previous['capturedBytes']
                 and event['playedBytes'] >= previous['playedBytes'])
        if event['phase'] in ACTIVE | {'completed'}: need(event['error'] == '')
        if event['phase'] == 'error': need(bool(event['error']))
        if not supported: need(event['phase'] == 'error' and event['totalBytes'] == 0)
        previous = event
    last = events[-1]
    need(value['active'] == (last['phase'] in ACTIVE))
    if value['active']:
        need(supported and value['frameBytes'] == channels * 2 and value['sampleRate'] == rate
             and value['channels'] == channels and last['capturedBytes'] <= value['capturedBytes'] <= limit
             and last['playedBytes'] <= value['playedBytes'] <= value['capturedBytes'])
    else: need(value['capturedBytes'] == value['playedBytes'] == 0)
    if supported:
        frame = channels * 2
        need(all(event[key] % frame == 0 for event in events for key in ('capturedBytes', 'playedBytes', 'totalBytes'))
             and value['capturedBytes'] % frame == value['playedBytes'] % frame == 0)
    if last['phase'] == 'completed':
        need(phases(events) == ['capturing', 'playing', 'draining', 'completed']
             and last['capturedBytes'] == last['playedBytes'] == limit > 0)
    return value


def accept_history(previous, current):
    """Preserve original events; a new read cannot rewrite or restart a cycle."""
    need(type(current) is dict and 'historyVersion' in current)
    if previous is not None:
        need(current['cycle'] >= previous['cycle'])
        if current['cycle'] == previous['cycle']:
            need(all(current[key] == previous[key] for key in
                     ('startedEpochMs', 'captureSampleRate', 'captureChannels'))
                 and current['events'][:len(previous['events'])] == previous['events'])
            # Live counters can advance between timer publications. A later
            # live or terminal sample may not regress behind those real bytes.
            for key in ('capturedBytes', 'playedBytes'):
                before = previous[key] if previous['active'] else previous['event'].get(key, 0)
                after = current[key] if current['active'] else current['event'].get(key, 0)
                need(after >= before)
        else:
            need(current['startedEpochMs'] >= previous['startedEpochMs'])
            if previous['events']:
                need(current['events'][0]['eventSequence'] > previous['events'][-1]['eventSequence']
                     and current['startedEpochMs'] >= previous['events'][-1]['publishedEpochMs'])
    return deepcopy(current)


def measured_state(packet):
    """Project validated original native facts, leaving UI presence to its owner."""
    value, muted = packet['audio']['recordedVoice'], packet['audio']['muted']
    need(type(muted) is bool and type(value.get('historyVersion')) is int and value['historyVersion'] == 1)
    events = value['events']
    phase = events[-1]['phase'] if events else 'idle'
    captured = value['capturedBytes'] if value['active'] else events[-1]['capturedBytes'] if events else 0
    played = value['playedBytes'] if value['active'] else events[-1]['playedBytes'] if events else 0
    frame = value['captureChannels'] * 2
    need(frame > 0 or captured == played == value['capturedBytes'] == 0)
    count = lambda size: size // frame if frame else 0
    return dict(recording=phase == 'capturing', preview=phase in ('playing', 'draining'), muted=muted,
        recordedFrames=count(captured), playedFrames=count(played), bufferedFrames=count(value['capturedBytes']),
        phase=phase, history=phases(events), error=(events[-1]['error'] or 'none') if events else 'none')
