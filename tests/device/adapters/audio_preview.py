"""Durable normal preview-cycle ownership, without an acoustic verdict.

The caller owns an already-open Audio page and serializes the fixed native/UI
channels for this component's entire call. Native originals and normal input
remain separate sources. No method retires the journal or advertises an area.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from functools import wraps
import re
import time
import uuid

from adapters.native_feature_observation import integer, number, exact
from adapters.normal_feature_state import context, need
from adapters.recorded_preview_history import accept_history, measured_state, validate_history, TERMINAL
from adapters.recorded_preview_evidence import validate as validate_original, INPUT, SINK

VERSION = 1
HEX = r'[0-9a-f]{32}'


def identifier(value):
    need(type(value) is str and re.fullmatch(HEX, value))
    return value


def serialized(function):
    @wraps(function)
    def invoke(self, *args, **kwargs):
        with self.lock.held():
            return function(self, *args, **kwargs)
    return invoke


class AudioPreview:
    def __init__(self, store, binding, run, controls, native, evidence, guard, lock, *,
                 monotonic=time.monotonic, sleep=time.sleep):
        need(all(callable(value) for value in (controls, guard, monotonic, sleep)))
        self.store, self.binding, self.run = store, deepcopy(context(binding)), identifier(run)
        pid = self.binding['processIdentity'].split(':')[0]
        need(pid.isdigit() and integer(native.pid, 1) and native.pid == evidence.pid == int(pid))
        need(callable(getattr(lock, 'held', None)) and callable(getattr(lock, 'assert_held', None)))
        self.controls, self.native, self.evidence, self.lock = controls, native, evidence, lock
        def bound_guard():
            lock.assert_held()
            return guard()
        self.guard = bound_guard
        self.monotonic, self.sleep, self.last_clock = monotonic, sleep, None

    def _original(self, value, history):
        need(type(value) is dict)
        if not value: return
        identifier(value['requestId'])
        validate_original(value, value['requestId'], self.native.pid, value['capturedEpochMs'])
        source = value['source']
        need(not history['active'] and source['cycle'] == history['cycle']
             and source['startedEpochMs'] == history['startedEpochMs']
             and source['sampleRate'] == history['captureSampleRate']
             and source['channels'] == history['captureChannels'] and source['events'] == history['events'])

    def now(self):
        value = self.monotonic()
        need(number(value, 0, 1e15) and (self.last_clock is None or value >= self.last_clock))
        self.last_clock = value
        return value

    @serialized
    def owned(self):
        need(self.guard() is not False)
        value = self.store.read()
        exact(value, {'audioPreviewVersion', 'binding', 'runId', 'originMuted', 'uiIdentity',
            'nativeInstance', 'nativeSequence', 'nativeEpochMs', 'history', 'cycles', 'pending', 'actions',
            'previewSequence', 'original', 'releaseState', 'releaseObservation'})
        need(type(value['audioPreviewVersion']) is int and value['audioPreviewVersion'] == VERSION
             and context(value['binding']) == self.binding and value['runId'] == self.run
             and type(value['originMuted']) is bool and type(value['uiIdentity']) is list
             and len(value['uiIdentity']) == 2 and type(value['uiIdentity'][0]) is str
             and bool(value['uiIdentity'][0]) and (value['uiIdentity'][1] is None
                 or type(value['uiIdentity'][1]) is str and bool(value['uiIdentity'][1]))
             and identifier(value['nativeInstance']) and integer(value['nativeSequence'], 1)
             and integer(value['nativeEpochMs'], 1) and integer(value['previewSequence'])
             and type(value['actions']) is list and len(value['actions']) <= 32
             and value['releaseState'] in ('live', 'requested', 'verified'))
        validate_history(value['history'], value['nativeEpochMs'])
        need(type(value['cycles']) is list and len(value['cycles']) <= 8)
        previous_cycle = 0
        for cycle in value['cycles']:
            exact(cycle, {'history', 'nativeEpochMs', 'original'})
            need(integer(cycle['nativeEpochMs'], 1) and type(cycle['original']) is dict
                 and cycle['history']['cycle'] == previous_cycle + 1)
            validate_history(cycle['history'], cycle['nativeEpochMs'])
            need(not cycle['history']['active'])
            self._original(cycle['original'], cycle['history'])
            if cycle['original']:
                need(cycle['original']['instance'] == value['nativeInstance']
                     and cycle['original']['sequence'] <= value['previewSequence'])
            previous_cycle += 1
        need(value['history']['cycle'] == previous_cycle + 1 if value['cycles'] else value['history']['cycle'] in (0, 1))
        ids = []
        for action in value['actions']:
            exact(action, {'operationId', 'verb', 'cycle', 'inputs'})
            ids.append(identifier(action['operationId']))
            need(action['verb'] in ('record-start', 'record-cancel', 'mute')
                 and integer(action['cycle']) and integer(action['inputs'], 0, 16))
        need(len(ids) == len(set(ids)))
        pending = value['pending']
        if pending is not None:
            exact(pending, {'operationId', 'verb', 'beforeCycle', 'enabled', 'inputs'})
            need(identifier(pending['operationId']) not in ids
                 and pending['verb'] in ('record-start', 'record-cancel', 'mute')
                 and integer(pending['beforeCycle'])
                 and (type(pending['enabled']) is bool if pending['verb'] == 'mute' else pending['enabled'] is None)
                 and type(pending['inputs']) is list and len(pending['inputs']) <= 16)
            for intent in pending['inputs']:
                exact(intent, {'verb', 'identifier', 'token', 'cycle'})
                need(intent['verb'] in ('record-start', 'record-cancel', 'mute', 'scroll-up', 'scroll-down')
                     and intent['identifier'] in ('audio.record', 'audio.mute', 'audio.scrollbar')
                     and type(intent['token']) is str and bool(intent['token']) and integer(intent['cycle']))
        need(value['releaseState'] == 'live' or pending is None)
        self._original(value['original'], value['history'])
        if value['original']:
            need(value['original']['instance'] == value['nativeInstance']
                 and value['original']['sequence'] <= value['previewSequence'])
        released = value['releaseObservation']
        need(type(released) is dict)
        if value['releaseState'] != 'verified': need(not released)
        else:
            exact(released, {'schemaVersion', 'requestId', 'instance', 'sequence', 'requestedEpochMs',
                'capturedEpochMs', 'processId', 'files', 'memoryEmpty'})
            need(type(released['schemaVersion']) is int and released['schemaVersion'] == 1
                 and identifier(released['requestId']) and released['instance'] == value['nativeInstance']
                 and integer(released['sequence'], 1) and released['sequence'] == value['previewSequence']
                 and integer(released['processId'], 1) and released['processId'] == self.native.pid
                 and integer(released['requestedEpochMs'], 1) and integer(released['capturedEpochMs'], 1)
                 and 0 <= released['capturedEpochMs'] - released['requestedEpochMs'] < 5000
                 and released['memoryEmpty'] is True and type(released['files']) is list and len(released['files']) == 2)
            for row, name in zip(released['files'], (INPUT, SINK)):
                exact(row, {'name', 'exists'})
                need(row['name'] == name and row['exists'] is False)
        return value

    def _write(self, previous, **fields):
        need(self.guard() is not False)
        value = deepcopy(previous); value.update(deepcopy(fields))
        self.store.write(value, previous)
        return value

    def _ui(self, owner=None):
        ui = self.controls(self._intent)
        if owner is not None:
            ui.identity, ui.mode, ui.cycle_floor = tuple(owner['uiIdentity']), True, owner['history']['cycle']
        return ui

    @serialized
    def claim(self):
        need(self.guard() is not False and self.store.read() is None)
        packet = self.native.read(0, require_recorded_history=True)
        voice = packet['audio']['recordedVoice']
        # Existing history belongs to its original owner. Releasing PCM cannot
        # recreate this idle baseline; only a separately verified restart can.
        need(voice['cycle'] == 0 and not packet['audio']['recording'])
        empty = self.evidence.inspect_empty()
        need(empty['instance'] == packet['instance'])
        ui = self._ui(); capture = ui.capture(); page = ui.page(capture)
        need(page['nativeHmd'] and page['uiHmd'] and page['mode'] == 1 and page['cycle'] == 0)
        value = dict(audioPreviewVersion=VERSION, binding=self.binding, runId=self.run,
            originMuted=packet['audio']['muted'], uiIdentity=list(ui.identity),
            nativeInstance=packet['instance'], nativeSequence=packet['sequence'],
            nativeEpochMs=packet['capturedEpochMs'], history=deepcopy(voice), cycles=[], pending=None,
            actions=[], previewSequence=empty['sequence'], original={}, releaseState='live', releaseObservation={})
        need(self.guard() is not False)
        self.store.write(value, None)
        return self.read()

    def _sample(self):
        before = self.owned()
        packet = self.native.read(before['nativeSequence'], require_recorded_history=True)
        current = packet['audio']['recordedVoice']; pending = before['pending']
        need(packet['instance'] == before['nativeInstance'] and packet['sequence'] > before['nativeSequence']
             and packet['capturedEpochMs'] >= before['nativeEpochMs'] and not packet['audio']['recording'])
        expected = before['history']['cycle']
        if pending and pending['verb'] == 'record-start':
            expected = pending['beforeCycle']
            sent = any(value['verb'] == 'record-start' for value in pending['inputs'])
            need(current['cycle'] in ((expected, expected + 1) if sent else (expected,)))
        else: need(current['cycle'] == expected)
        accept_history(before['history'], current)
        fields = {}
        if current['cycle'] > before['history']['cycle']:
            need(not before['history']['active'])
            if before['history']['cycle'] > 0:
                need(len(before['cycles']) < 8)
                fields['cycles'] = before['cycles'] + [dict(history=before['history'],
                    nativeEpochMs=before['nativeEpochMs'], original=before['original'])]
            fields['original'] = {}
        self._write(before, nativeSequence=packet['sequence'], nativeEpochMs=packet['capturedEpochMs'], history=current, **fields)
        return packet

    @serialized
    def read(self):
        started = self.now()
        for _attempt in range(101):
            packet = self._sample(); owner = self.owned()
            ui = self._ui(owner); value = ui.capture(); page = ui.page(value)
            need(page['nativeHmd'] and page['uiHmd'] and page['mode'] == 1)
            voice = packet['audio']['recordedVoice']; coherent = page['cycle'] == voice['cycle']
            if not coherent:
                pending = owner['pending']
                need(pending is not None and pending['verb'] == 'record-start'
                     and voice['cycle'] == pending['beforeCycle'] and page['cycle'] == voice['cycle'] + 1)
            for row in value['controls']:
                if row['id'] == 'audio.record':
                    coherent = coherent and row['nativeActive'] == voice['active'] and row['phase'] == measured_state(packet)['phase']
                if row['id'] == 'audio.mute': coherent = coherent and row['nativeMuted'] == packet['audio']['muted']
            now = self.now(); need(now - started < 10 and self.guard() is not False)
            if coherent: return packet
            self.sleep(.1)  # Different acquisition instants may straddle a real native transition.
        need(False)

    def _intent(self, verb, observed, control):
        before = self.owned(); pending = before['pending']
        need(before['releaseState'] == 'live' and pending is not None
             and (verb.startswith('scroll-') or verb == pending['verb'])
             and len(pending['inputs']) < 16)
        identity = (observed.get('instance', observed.get('bridgeId')), observed.get('generation'))
        page = next(row for row in observed['controls'] if row['id'] == 'audio.page')
        row = next(row for row in observed['controls'] if row['id'] == control)
        need(list(identity) == before['uiIdentity'] and page['nativeHmd'] and page['uiHmd']
             and page['mode'] == 1 and page['cycle'] == pending['beforeCycle'])
        # The final primitive also re-resolves this original token. Persist it
        # before delivery, including when delivery or its response is lost.
        pending = deepcopy(pending)
        pending['inputs'].append(dict(verb=verb, identifier=control, token=row['token'], cycle=page['cycle']))
        self._write(before, pending=pending)

    def _finish(self, packet):
        before = self.owned(); pending = before['pending']; need(pending is not None)
        state = measured_state(packet); cycle = packet['audio']['recordedVoice']['cycle']
        if pending['verb'] == 'record-start':
            need(any(value['verb'] == 'record-start' for value in pending['inputs'])
                 and cycle == pending['beforeCycle'] + 1)
        elif pending['verb'] == 'record-cancel':
            need(any(value['verb'] == 'record-cancel' for value in pending['inputs'])
                 and cycle == pending['beforeCycle'] and state['phase'] == 'cancelled' and state['bufferedFrames'] == 0)
        else: need(cycle == pending['beforeCycle'] and state['muted'] is pending['enabled'])
        actions = before['actions'] + [dict(operationId=pending['operationId'], verb=pending['verb'],
            cycle=cycle, inputs=len(pending['inputs']))]
        self._write(before, pending=None, actions=actions)
        return packet

    @serialized
    def act(self, operation_id, verb, *, enabled=None):
        identifier(operation_id); before = self.owned()
        need(before['pending'] is None and before['releaseState'] == 'live'
             and len(before['actions']) < 32 and operation_id not in [a['operationId'] for a in before['actions']]
             and verb in ('record-start', 'record-cancel', 'mute')
             and (type(enabled) is bool if verb == 'mute' else enabled is None))
        packet = self.read(); before = self.owned(); voice = packet['audio']['recordedVoice']
        if verb == 'record-start': need(not voice['active'] and len(before['cycles']) < 8)
        need(voice['active'] and voice['cycle'] > 0 if verb == 'record-cancel' else True)
        self._write(before, pending=dict(operationId=operation_id, verb=verb,
            beforeCycle=voice['cycle'], enabled=enabled, inputs=[]))
        ui = self._ui(before)
        if verb == 'record-start': ui.start()
        elif verb == 'record-cancel': ui.cancel(voice['cycle'])
        else: ui.mute(enabled)
        return self._finish(self.read())

    @serialized
    def reconcile(self):
        """Read an uncertain action's effect; never re-send its original input."""
        need(self.owned()['pending'] is not None)
        return self._finish(self.read())

    @serialized
    def await_terminal(self):
        need(self.owned()['pending'] is None and self.owned()['history']['cycle'] > 0)
        started = self.now()
        for _attempt in range(151):
            packet = self.read(); now = self.now(); need(now - started < 15)
            if measured_state(packet)['phase'] in TERMINAL: return packet
            self.sleep(.1)
        need(False)

    @serialized
    def originals(self):
        packet = self.read(); before = self.owned(); voice = packet['audio']['recordedVoice']
        need(before['pending'] is None and before['releaseState'] == 'live'
             and voice['cycle'] > 0 and not voice['active'])
        self.evidence.instance = before['nativeInstance']
        actual, raw = self.evidence.read(before['previewSequence'], after_cycle=voice['cycle'] - 1)
        source = actual['source']
        need(actual['instance'] == before['nativeInstance'] and source['cycle'] == voice['cycle']
             and source['startedEpochMs'] == voice['startedEpochMs'] and source['events'] == voice['events']
             and source['sampleRate'] == voice['captureSampleRate'] and source['channels'] == voice['captureChannels'])
        if before['original']:
            need(before['original']['source'] == source)
        self._write(before, previewSequence=actual['sequence'], original=actual)
        return actual, raw  # Actual input/sink PCM; no acoustic or microphone claim.

    def _quiet(self):
        started = self.now()
        for _attempt in range(51):
            packet = self.read(); state = measured_state(packet)
            need(not state['recording'] and not state['preview'] and state['bufferedFrames'] == 0)
            now = self.now(); need(now - started < 5)
            if now - started >= 3: return packet
            self.sleep(.1)
        need(False)

    @serialized
    def release_native(self):
        """Restore mute, verify product quiet, release taps and retain ownership.

        The retained journal still owns terminal history and external role work;
        this operation cannot stand in for the full area's restart/cleanup join.
        """
        before = self.owned(); need(before['pending'] is None)
        if before['releaseState'] == 'live':
            packet = self.read()
            if packet['audio']['recordedVoice']['active']:
                self.act(uuid.uuid4().hex, 'record-cancel')
            if packet['audio']['muted'] != before['originMuted']:
                self.act(uuid.uuid4().hex, 'mute', enabled=before['originMuted'])
            self._quiet(); before = self.owned()
            self._write(before, releaseState='requested')
            # If this send/result is lost, a later call performs only inspection.
            self.evidence.instance = before['nativeInstance']
            self.evidence.sequence = before['previewSequence']
            observation = self.evidence.release()
        else:
            self._quiet()
            self.evidence.instance = before['nativeInstance']
            self.evidence.sequence = before['previewSequence']
            observation = self.evidence.inspect_empty()
        self._quiet(); before = self.owned()
        self._write(before, releaseState='verified', previewSequence=observation['sequence'],
            releaseObservation=observation)
        return observation
