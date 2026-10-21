"""Original native motion evidence for brief, non-looping Emote checkpoints.

This private file contains original source packets, not public expected state.
Reading it recomputes source/caller/loaded-data/pose provenance. It supplies
neither the required original image nor the independent observer's facts.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json

from adapters.emote_rig_measurements import playback, source
from adapters.native_animation_history import moving_pose
from adapters.native_feature_observation import exact, integer, need, number
from adapters.normal_ui import NativeUIError
from .contract import arguments, identifier, typed_equal, json_document
from .phase_fixture import validate as phase_packet

VERSION = 1
LIMIT = 2 * 1024 * 1024
PART = {'group', 'phaseBefore', 'phaseAfter', 'epochMs', 'hostEpochMs'}
FACTS = {'animation', 'sit', 'override', 'poseProgress', 'restoredBeforeNominalEnd'}


def original(frame):
    """Copy existing originals; never query, redate or infer input delivery."""
    need(type(frame) is dict and PART <= frame.keys())
    return deepcopy({key: frame[key] for key in PART})


def packet(call, before, after, *, role):
    value = dict(emoteMotionVersion=VERSION, role=role, call=deepcopy(call),
                 before=original(before), after=original(after))
    # Do not let a producer persist an invalid proof for a later reader to adopt.
    measure(value, call=call, role=role, epoch=after['hostEpochMs'])
    raw = json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    need(len(raw) <= LIMIT)
    return raw


def read(raw, *, call, role, epoch, captured, state):
    try:
        return _read(raw, call=call, role=role, epoch=epoch, captured=captured, state=state)
    except (ValueError, NativeUIError, KeyError, TypeError) as error:
        raise AssertionError('Original native Emote motion evidence is invalid') from error


def _read(raw, *, call, role, epoch, captured, state):
    need(type(raw) is bytes and 0 < len(raw) <= LIMIT)
    value = json_document(raw)
    result = measure(value, call=call, role=role, epoch=epoch)
    need(type(captured) in (int, float) and captured == value['after']['hostEpochMs'])
    need(type(state) is dict and FACTS <= state.keys()
         and typed_equal({key: state[key] for key in FACTS}, result['state']))
    return {key: item for key, item in result.items() if key != 'state'}


def measure(value, *, call, role, epoch):
    """Recompute a bounded original native history window, with host freshness.

    Native epochs stay on the native clock. The original native/host pair at
    acquisition bridges elapsed age; no host timestamp is passed as a native
    epoch. A current active result is mandatory: completed clips stay idle.
    """
    exact(value, {'emoteMotionVersion', 'role', 'call', 'before', 'after'})
    need(type(value['emoteMotionVersion']) is int and value['emoteMotionVersion'] == VERSION
         and role in ('primary', 'actor') and value['role'] == role)
    arguments('feature.emotes.act', call)
    need(call['verb'] in ('play', 'sit', 'override') and typed_equal(value['call'], call))
    identifier(call['runId']); identifier(call['ticket'])
    previous = None
    for part in (value['before'], value['after']):
        exact(part, PART)
        need(integer(part['epochMs'], 1) and number(part['hostEpochMs'], 1, 1e15))
        for key in ('phaseBefore', 'phaseAfter'):
            status = part[key]
            need(type(status) is dict and type(status.get('requestId')) is str)
            phase_packet(status, run=call['runId'], area='emotes', request=status['requestId'],
                         epoch=part['hostEpochMs'], previous=previous)
            need(status['active'] and status['activations'])
            activation = status['activations'][-1]
            need(activation['ticket'] == call['ticket']
                 and typed_equal(activation['stimulus'], dict(verb=call['verb'], inputs=call['inputs'])))
            previous = status
        need(part['group']['rootsBefore']['requestedEpochMs'] >= activation['activatedEpochMs'])
    before, after = value['before'], value['after']
    need(after['epochMs'] >= before['epochMs'] and after['hostEpochMs'] >= before['hostEpochMs']
         and number(epoch, 1, 1e15) and -250 <= epoch - after['hostEpochMs'] <= 1500)
    native = after['group']['native']; need(type(native) is dict)
    pid = native.get('processId'); need(integer(pid, 1))
    selected, current, urls = source(after['group'], pid, after['epochMs'])
    need('compilation' in selected)
    prior, _native, _urls = source(before['group'], pid, before['epochMs'])
    need(typed_equal(prior, selected))
    proof = playback(after['group'], before['group']['native'], pid=pid, epoch=after['epochMs'])
    state = proof['state']; need(state['override'] is True)
    name = urls[proof['event']['request']['url']]
    chosen = 'Sit' if call['verb'] == 'sit' else call['inputs']['name']
    need(name.startswith('Sit') if chosen == 'Sit' else name == chosen)
    request = proof['event']['request']
    need(request['loop'] is False and request['framesPerSecond'] == 60.)
    nominal = 1000 * (request['lastFrame'] - request['firstFrame']) / request['framesPerSecond']
    required = max(150., min(500., nominal / 4))
    # A longer clip may retain an older valid prefix in the bounded history.
    # Retain/validate it above, but qualify the window from fresh originals only.
    age = max(0., epoch - after['hostEpochMs'])
    frames = [row for row in current['animation']['history']['frames']
              if row['frameSequence'] in proof['frameSequences']
              and 0 <= after['epochMs'] - row['capturedEpochMs'] <= 1500 - age]
    need(len(frames) >= 3)
    pairs = list(zip(frames, frames[1:]))
    need(all(right['capturedEpochMs'] > left['capturedEpochMs']
             and right['evaluationSequence'] > left['evaluationSequence']
             and right['clip']['evaluationSequence'] > left['clip']['evaluationSequence']
             and right['clip']['frame'] > left['clip']['frame'] for left, right in pairs)
         and sum(bool(moving_pose(left, right)) for left, right in pairs) >= 2)
    span = frames[-1]['capturedEpochMs'] - frames[0]['capturedEpochMs']
    need(span >= required)
    return dict(emoteMotionVersion=VERSION, nativeSamples=len(frames), nativeSpanMs=span,
                requiredSpanMs=required, nominalDurationMs=nominal,
                firstFrameSequence=frames[0]['frameSequence'], lastFrameSequence=frames[-1]['frameSequence'],
                state=deepcopy(state))
