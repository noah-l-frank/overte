"""Original native read-only feature sources, never desired state or a verdict.

The owning platform supplies its existing bound private transport and clock.
Native animation timestamps/evaluation cursors are retained independently of
the request sampler. An absent hook or a cached pose cannot turn green here.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
from copy import deepcopy
import math
import re
import time
import uuid

from adapters.normal_ui import NativeUIError

FILE = 'feature-native-observation.json'
LIMIT = 262144


def need(condition):
    if not condition:
        raise NativeUIError('Native feature observation is unavailable or invalid')


def integer(value, minimum=0, maximum=2**53 - 1):
    return type(value) is int and minimum <= value <= maximum


def number(value, minimum=-1e9, maximum=1e9):
    return type(value) in (int, float) and math.isfinite(value) and minimum <= value <= maximum


def exact(value, fields):
    need(type(value) is dict and set(value) == set(fields))


def fresh(value, epoch):
    need(integer(value, 1) and integer(epoch, 1) and -250 <= epoch - value <= 1500)


def decode(raw):
    need(type(raw) is str and len(raw.encode('utf-8')) <= LIMIT)
    def pairs(items):
        value = {}
        for key, item in items:
            need(key not in value)
            value[key] = item
        return value
    return json.loads(raw, object_pairs_hook=pairs,
        parse_constant=lambda _value: need(False))


def validate(value, request, pid, epoch, *, require_animation=False, require_recorded_voice=False,
             require_recorded_history=False, require_animation_history=False):
    need(type(value) is dict and all(type(flag) is bool for flag in
         (require_animation, require_recorded_voice, require_recorded_history, require_animation_history)))
    optional = {'requestedEpochMs', 'animationFence'} & set(value)
    exact(value, {'schemaVersion', 'requestId', 'instance', 'sequence', 'capturedEpochMs',
                  'processId', 'lifecycle', 'animation', 'graphics', 'audio', 'account'} | optional)
    need(type(value['schemaVersion']) is int and value['schemaVersion'] == 1
         and value['requestId'] == request and integer(pid, 1)
         and integer(value['processId'], 1) and value['processId'] == pid
         and type(value['instance']) is str and re.fullmatch('[0-9a-f]{32}', value['instance'])
         and integer(value['sequence'], 1))
    fresh(value['capturedEpochMs'], epoch)
    if 'requestedEpochMs' in value:
        need(integer(value['requestedEpochMs'], 1)
             and 0 <= value['capturedEpochMs'] - value['requestedEpochMs'] <= 5000)
    fence = value.get('animationFence', {})
    need(type(fence) is dict)
    if fence:
        exact(fence, {'rigId', 'sequence', 'requestedEpochMs'})
        need(integer(fence['rigId']) and integer(fence['sequence'])
             and integer(fence['requestedEpochMs'], 1)
             and fence['requestedEpochMs'] == value.get('requestedEpochMs'))
    exact(value['lifecycle'], {'backgrounds', 'activations', 'launches'})
    need(all(integer(v, 0, 1000000) for v in value['lifecycle'].values())
         and value['lifecycle']['launches'] >= 1)
    exact(value['graphics'], {'requestedResolutionScale', 'applicationResolutionScale',
        'shadowsSetting', 'mirrorsSetting', 'hazeSetting', 'localLightingSetting',
        'proceduralMaterialsSetting', 'deferredRenderingAvailable'})
    need(all(number(value['graphics'][key], 0.01, 8) for key in
             ('requestedResolutionScale', 'applicationResolutionScale'))
         and all(type(item) is bool for key, item in value['graphics'].items()
                 if key not in {'requestedResolutionScale', 'applicationResolutionScale'}))
    audio_fields = {'recording', 'muted'}
    if type(value['audio']) is dict and 'recordedVoice' in value['audio']:
        audio_fields.add('recordedVoice')
    need(not (require_recorded_voice or require_recorded_history) or 'recordedVoice' in audio_fields)
    exact(value['audio'], audio_fields)
    need(all(type(value['audio'][key]) is bool for key in ('recording', 'muted')))
    if 'recordedVoice' in value['audio']:
        recorded = value['audio']['recordedVoice']
        from adapters.recorded_preview_history import FIELDS, validate_history
        need(type(recorded) is dict)
        history = 'historyVersion' in recorded
        need(not require_recorded_history or history)
        exact(recorded, {'active', 'capturedBytes', 'playedBytes', 'frameBytes', 'sampleRate', 'channels', 'event'}
              | (FIELDS if history else set()))
        need(type(recorded['active']) is bool
             and all(integer(recorded[key], 0, 16 * 1024 * 1024) for key in ('capturedBytes', 'playedBytes'))
             and recorded['playedBytes'] <= recorded['capturedBytes']
             and integer(recorded['frameBytes'], 0, 1024) and integer(recorded['sampleRate'], 0, 768000)
             and integer(recorded['channels'], 0, 256) and type(recorded['event']) is dict)
        event = recorded['event']
        if event:
            exact(event, {'schemaVersion', 'eventSequence', 'publishedEpochMs', 'phase', 'error',
                          'capturedBytes', 'playedBytes', 'totalBytes'})
            need(type(event['schemaVersion']) is int and event['schemaVersion'] == 1
                 and integer(event['eventSequence'], 1) and integer(event['publishedEpochMs'], 1)
                 and type(event['phase']) is str
                 and event['phase'] in {'capturing', 'playing', 'draining', 'completed', 'cancelled', 'error'}
                 and type(event['error']) is str and len(event['error']) <= 128
                 and not any(ord(c) < 32 for c in event['error'])
                 and all(integer(event[key], 0, 16 * 1024 * 1024)
                         for key in ('capturedBytes', 'playedBytes', 'totalBytes'))
                 and event['playedBytes'] <= event['capturedBytes'] <= event['totalBytes'])
        if recorded['active']:
            need(bool(event) and recorded['frameBytes'] > 0 and recorded['channels'] > 0
                 and recorded['sampleRate'] > 0 and event['phase'] in {'capturing', 'playing', 'draining'})
            fresh(event['publishedEpochMs'], epoch)
        if history: validate_history(recorded, value['capturedEpochMs'])
    exact(value['account'], {'loggedIn', 'principalSha256'})
    need(type(value['account']['loggedIn']) is bool
         and type(value['account']['principalSha256']) is str
         and re.fullmatch('[0-9a-f]{64}', value['account']['principalSha256']))
    animation = value['animation']
    need(type(animation) is dict)
    if animation:
        fields = {'rigId', 'capturedEpochMs', 'evaluationSequence', 'animationsEnabled',
                  'graphLoaded', 'overrideActive', 'joints'}
        exact(animation, fields | ({'clip'} if 'clip' in animation else set()) | ({'history'} if 'history' in animation else set()))
        need(integer(animation['rigId']) and integer(animation['evaluationSequence'])
             and integer(animation['capturedEpochMs'], 1)
             and all(type(animation[key]) is bool for key in
                     ('animationsEnabled', 'graphLoaded', 'overrideActive'))
             and type(animation['joints']) is list and len(animation['joints']) <= 256)
        need(all(type(joint) is list and len(joint) == 7 and all(number(v) for v in joint)
                 for joint in animation['joints']))
        need('clip' not in animation or animation['overrideActive'])
        if 'clip' in animation:
            from adapters.native_animation_history import clip
            clip(animation['clip'])
        if 'history' in animation:
            from adapters.native_animation_history import validate as history
            history(animation['history'],animation,value['capturedEpochMs'])
        else: need(not require_animation_history)
        if require_animation:
            fresh(animation['capturedEpochMs'], epoch)
            if fence:
                need(animation['rigId'] == fence['rigId']
                     and animation['evaluationSequence'] > fence['sequence']
                     and animation['capturedEpochMs'] >= fence['requestedEpochMs'])
            need(animation['graphLoaded'] and animation['animationsEnabled']
                 and animation['evaluationSequence'] > 0 and len(animation['joints']) > 0)
            if animation['overrideActive']:
                need('clip' in animation and animation['clip']['loadedFrames'] > 0
                     and bool(animation['clip']['url'])
                     and animation['clip']['evaluationSequence'] > 0)
                fresh(animation['clip']['evaluatedEpochMs'], epoch)
    else:
        need(not require_animation and not require_animation_history)
    return value


class NativeFeatureObservation:
    def __init__(self, send, read, clock_ms, guard, pid, *, ios=False,
                 monotonic=time.monotonic, sleep=time.sleep):
        need(all(callable(value) for value in (send, read, clock_ms, guard, monotonic, sleep))
             and integer(pid, 1) and type(ios) is bool)
        self.send, self.original, self.clock_ms, self.guard, self.pid = send, read, clock_ms, guard, pid
        self.ios, self.monotonic, self.sleep = ios, monotonic, sleep
        self.instance, self.sequence, self.rig, self.rig_sequence = None, 0, None, 0
        self.lifecycle = None
        self.voice_event_sequence = 0
        self.voice_history = None
        self.animation_history = None

    def read(self, after_sequence, *, require_animation=False, require_recorded_voice=False,
             require_recorded_history=False, require_animation_history=False):
        try:
            need(integer(after_sequence) and after_sequence >= self.sequence
                 and all(type(v) is bool for v in (require_animation,require_recorded_voice,require_recorded_history,require_animation_history))
                 and self.guard() is not False)
            requested_at = self.clock_ms()
            need(integer(requested_at, 1))
            started = previous = self.monotonic()
            need(number(started, 0, 1e15))
            request = ('ios-' if self.ios else '') + uuid.uuid4().hex
            self.send(dict(schemaVersion=1, commandId=request, action='feature-native-observe'))
            source_floor, pinned_instance, pinned_rig = after_sequence, self.instance, self.rig
            seen_lifecycle, voice_floor = self.lifecycle, self.voice_event_sequence
            seen_history = self.voice_history
            seen_animation_history = self.animation_history
            for _attempt in range(51):
                need(self.guard() is not False)
                raw = self.original()
                try:
                    value = decode(raw) if raw else None
                except json.JSONDecodeError:
                    value = None  # Original Test.saveObject may still be writing.
                epoch = self.clock_ms()
                need(self.guard() is not False)
                resample_animation = False
                if type(value) is dict and value.get('requestId') == request:
                    # HTTP/AFC provides no independent device wall clock. A
                    # unique native request fence and bounded local transport
                    # time establish this acquisition; all source ages use the
                    # original native envelope clock, never a retimed pose.
                    if self.ios:
                        need(integer(value.get('requestedEpochMs'), 1))
                        epoch = value.get('capturedEpochMs')
                    value = validate(value, request, self.pid, epoch, require_animation=False,
                                     require_recorded_voice=require_recorded_voice, require_recorded_history=require_recorded_history,
                                     require_animation_history=require_animation_history)
                    need(pinned_instance in (None, value['instance']) and value['sequence'] > source_floor
                         and (self.ios or value['capturedEpochMs'] >= requested_at))
                    pinned_instance, source_floor = value['instance'], value['sequence']
                    if seen_lifecycle is not None:
                        need(all(value['lifecycle'][key] >= seen_lifecycle[key] for key in seen_lifecycle))
                    seen_lifecycle = value['lifecycle'].copy()
                    animation = value['animation']
                    if 'history' in animation:
                        from adapters.native_animation_history import accept
                        seen_animation_history=accept(seen_animation_history,animation['rigId'],animation['history'])
                    else: need(seen_animation_history is None)
                    voice_event = value['audio'].get('recordedVoice', {}).get('event', {})
                    voice_sequence = voice_event.get('eventSequence', 0)
                    need(voice_sequence >= voice_floor)
                    voice_floor = voice_sequence
                    recorded = value['audio'].get('recordedVoice', {})
                    if 'historyVersion' in recorded:
                        from adapters.recorded_preview_history import accept_history
                        seen_history = accept_history(seen_history, recorded)
                    else: need(seen_history is None)
                    if require_animation:
                        # A current request around a 100 ms old pose may still
                        # predate the action. Await an actual later evaluation,
                        # not just a source timestamp inside the age allowance.
                        if animation:
                            need(pinned_rig in (None, animation['rigId']))
                            pinned_rig = animation['rigId']
                        try:
                            validate(value, request, self.pid, epoch, require_animation=True,
                                     require_recorded_voice=require_recorded_voice, require_recorded_history=require_recorded_history)
                            need((bool(value.get('animationFence')) if self.ios else
                                  bool(value.get('animationFence')) or animation['capturedEpochMs'] >= requested_at)
                                 and animation['evaluationSequence'] > self.rig_sequence)
                        except NativeUIError:
                            resample_animation = True
                    if not resample_animation:
                        need(self.guard() is not False)
                        completed_at = self.monotonic()
                        need(number(completed_at, 0, 1e15) and previous <= completed_at
                             and completed_at - started < 5)
                        self.instance, self.sequence = value['instance'], value['sequence']
                        self.lifecycle = value['lifecycle'].copy()
                        self.voice_event_sequence = voice_sequence
                        self.voice_history = deepcopy(seen_history)
                        self.animation_history = deepcopy(seen_animation_history)
                        if require_animation:
                            self.rig, self.rig_sequence = animation['rigId'], animation['evaluationSequence']
                        return value
                current = self.monotonic()
                need(number(current, 0, 1e15) and current >= previous)
                previous = current
                if current - started >= 5 or _attempt == 50:
                    break
                self.sleep(0.1)
                if resample_animation:
                    # Only this closed read-only sampler may be requested
                    # again. Never replay a field/click/script input here.
                    request = ('ios-' if self.ios else '') + uuid.uuid4().hex
                    self.send(dict(schemaVersion=1, commandId=request, action='feature-native-observe'))
        except Exception:
            raise NativeUIError('Native feature observation failed') from None
        raise NativeUIError('Native feature observation did not produce this request')
