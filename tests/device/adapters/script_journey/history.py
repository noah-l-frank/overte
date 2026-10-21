"""Private original-source transcript; stored frames never satisfy a fresh read."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import json
import re
import zlib

from adapters.native_feature_observation import exact, integer, need, number, validate as validate_lifecycle
from adapters.normal_feature_state import context
from adapters.normal_script_manager import diagnostic
from adapters.normal_ui import NativeUIError
from feature_journeys.contract import identifier
from adapters.script_journey.files import validate as validate_ui
from adapters.script_journey.measurements import ScriptMeasurements, compose
from adapters.script_journey.lock import ScriptSourceLock

VERSION = 1
MAX_FRAMES = 512
MAX_RAW = 16 * 1024 * 1024
MAX_PACKED = 48 * 1024


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def same(left, right):
    return canonical(left) == canonical(right)


def pack(frames):
    need(type(frames) is list and len(frames) <= MAX_FRAMES)
    raw = canonical(frames)
    need(len(raw) <= MAX_RAW)
    encoded = base64.b64encode(zlib.compress(raw, level=9)).decode('ascii')
    need(len(encoded) <= MAX_PACKED)
    return dict(encoding='zlib-base64-json', bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest(), data=encoded)


def unpack(value):
    exact(value, {'encoding', 'bytes', 'sha256', 'data'})
    need(value['encoding'] == 'zlib-base64-json' and integer(value['bytes'], 2, MAX_RAW)
         and type(value['sha256']) is str and re.fullmatch('[0-9a-f]{64}', value['sha256']) is not None
         and type(value['data']) is str and 0 < len(value['data']) <= MAX_PACKED)
    compressed = base64.b64decode(value['data'], validate=True)
    need(base64.b64encode(compressed).decode('ascii') == value['data'])
    decoder = zlib.decompressobj()
    raw = decoder.decompress(compressed, value['bytes'] + 1)
    need(len(raw) == value['bytes'] and decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail
         and hashlib.sha256(raw).hexdigest() == value['sha256'])
    def pairs(items):
        result = {}
        for key, item in items:
            need(key not in result)
            result[key] = item
        return result
    def invalid_constant(_value):
        need(False)
    frames = json.loads(raw.decode('utf-8'), object_pairs_hook=pairs, parse_constant=invalid_constant)
    need(type(frames) is list and len(frames) <= MAX_FRAMES and canonical(frames) == raw)
    return frames


def unique_queries(frames):
    """An advancing cursor cannot turn a reused original query into a new one."""
    seen = {source:set() for source in ('execution','ui','lifecycle')}
    for frame in frames:
        need(type(frame) is dict)
        for source, field in (('execution','requestId'),('ui','commandId'),('lifecycle','requestId')):
            need(type(frame.get(source)) is dict)
            nonce = frame[source].get(field)
            need(type(nonce) is str and re.fullmatch('[0-9a-f]{32}',nonce) is not None
                 and nonce not in seen[source])
            seen[source].add(nonce)


def restore(reader, frames):
    """Replay only historical validation/continuity, with no transport calls.

    Historical clocks validate historical data. None are retimed or returned as
    current measurements. The next read must acquire four new original sources.
    """
    need(isinstance(reader, ScriptMeasurements) and type(frames) is list and len(frames) <= MAX_FRAMES
         and reader.execution.ios is False and reader.lifecycle.ios is False
         and reader.ui.instance is None and reader.ui.generation is None and reader.ui.sequence == 0
         and reader.ui.elapsed == 0 and reader.ui.last_command == 0
         and reader.lifecycle.instance is None and reader.lifecycle.sequence == 0
         and reader.lifecycle.lifecycle is None and reader.lifecycle.voice_history is None
         and reader.lifecycle.animation_history is None and reader.lifecycle.account_history is None
         and reader.lifecycle.voice_event_sequence == 0 and reader.lifecycle.rig is None
         and reader.lifecycle.rig_sequence == 0 and reader.service_instance is None and reader.service_sequence == 0)
    unique_queries(frames)
    ui_previous = service_previous = lifecycle_previous = None
    voice_history = animation_history = account_history = None
    voice_floor = 0
    for frame in frames:
        exact(frame, {'ticket', 'afterEpochMs', 'epochMs', 'execution', 'ui', 'service', 'lifecycle'})
        identifier(frame['ticket'])
        need(integer(frame['afterEpochMs'], 1) and integer(frame['epochMs'], 1))
        ui, service, lifecycle = frame['ui'], frame['service'], frame['lifecycle']
        need(type(ui) is dict and type(lifecycle) is dict
             and type(ui.get('commandId')) is str and re.fullmatch('[0-9a-f]{32}', ui['commandId']) is not None
             and type(lifecycle.get('requestId')) is str and re.fullmatch('[0-9a-f]{32}', lifecycle['requestId']) is not None)
        validate_ui(ui, ui['commandId'], reader.ui.pid, frame['epochMs'])
        validate_lifecycle(lifecycle, lifecycle['requestId'], reader.lifecycle.pid, frame['epochMs'])
        diagnostic(service, frame['epochMs'])
        if ui_previous is not None:
            need(frame['epochMs'] >= previous_epoch)
            need(ui['instance'] == ui_previous['instance'] and ui['generation'] == ui_previous['generation']
                 and ui['sourceSequence'] > ui_previous['sourceSequence']
                 and ui['elapsedMs'] >= ui_previous['elapsedMs']
                 and ui['lastCommandSequence'] >= ui_previous['lastCommandSequence']
                 and ui['capturedEpochMs'] >= ui_previous['capturedEpochMs'])
            need(service['instance'] == service_previous['instance']
                 and service['sampleSequence'] > service_previous['sampleSequence']
                 and service['sampleEpochMs'] >= service_previous['sampleEpochMs'])
            need(lifecycle['instance'] == lifecycle_previous['instance']
                 and lifecycle['sequence'] > lifecycle_previous['sequence']
                 and lifecycle['capturedEpochMs'] >= lifecycle_previous['capturedEpochMs']
                 and all(lifecycle['lifecycle'][key] >= lifecycle_previous['lifecycle'][key]
                         for key in lifecycle_previous['lifecycle']))
        # Use the same source-owned prefix acceptors as the live native reader.
        recorded = lifecycle['audio'].get('recordedVoice', {})
        voice_sequence = recorded.get('event', {}).get('eventSequence', 0)
        need(voice_sequence >= voice_floor)
        voice_floor = voice_sequence
        if 'historyVersion' in recorded:
            from adapters.recorded_preview_history import accept_history
            voice_history = accept_history(voice_history, recorded)
        else:
            need(voice_history is None)
        animation = lifecycle['animation']
        if 'history' in animation:
            from adapters.native_animation_history import accept
            animation_history = accept(animation_history, animation['rigId'], animation['history'])
        else:
            need(animation_history is None)
        if 'observation' in lifecycle['account']:
            from adapters.native_account_observation import accept
            account_history = accept(account_history, lifecycle['account'])
        else:
            need(account_history is None)
        # Recompute the join from original metadata only; never cache its verdict.
        compose(reader.run, frame['ticket'], reader.directory, reader.fixture_url, reader.execution.pid,
                frame['execution'], ui, service, lifecycle, frame['epochMs'], frame['afterEpochMs'])
        ui_previous, service_previous, lifecycle_previous = ui, service, lifecycle
        previous_epoch = frame['epochMs']
    reader.execution.restore_history([frame['execution'] for frame in frames])
    if ui_previous is not None:
        reader.ui.instance, reader.ui.generation = ui_previous['instance'], ui_previous['generation']
        reader.ui.sequence, reader.ui.elapsed = ui_previous['sourceSequence'], ui_previous['elapsedMs']
        reader.ui.last_command = ui_previous['lastCommandSequence']
        reader.service_instance, reader.service_sequence = service_previous['instance'], service_previous['sampleSequence']
        reader.lifecycle.instance, reader.lifecycle.sequence = lifecycle_previous['instance'], lifecycle_previous['sequence']
        reader.lifecycle.lifecycle = deepcopy(lifecycle_previous['lifecycle'])
        reader.lifecycle.voice_event_sequence = voice_floor
        reader.lifecycle.voice_history = deepcopy(voice_history)
        reader.lifecycle.animation_history = deepcopy(animation_history)
        reader.lifecycle.account_history = deepcopy(account_history)


class ScriptHistory:
    """One private run/role/process transcript; interrupted acquisition is fatal.

    A pending record cannot be reset/adopted by constructing another object.
    Cleanup must keep its responsibility and use separately acquired sources.
    """
    def __init__(self, store, binding, run, role, directory, fixture_url, *, component_only=False):
        try:
            identifier(run)
            need(role in ('primary', 'actor'))
            self.binding = deepcopy(context(binding, component_only=component_only))
            self.store, self.run, self.role = store, run, role
            self.directory, self.fixture_url = directory, fixture_url
            self.previous = store.read()
            self.frames = []
            self.state = dict(schemaVersion=VERSION, sourceKind='script-history', binding=self.binding,
                runId=run, role=role, directory=directory, fixtureUrl=fixture_url,
                phase='ready', revision=0, transcript=pack([]))
            if self.previous is not None:
                exact(self.previous, set(self.state))
                for key in set(self.state) - {'phase', 'revision', 'transcript'}:
                    need(same(self.previous[key], self.state[key]))
                need(self.previous['phase'] == 'ready' and integer(self.previous['revision'], 0, 2 * MAX_FRAMES))
                self.frames = unpack(self.previous['transcript'])
                need(self.previous['revision'] == 2 * len(self.frames))
                self.state = deepcopy(self.previous)
        except Exception:
            raise NativeUIError('Script history is unavailable, foreign or interrupted') from None

    def current(self):
        need(same(self.store.read(), self.previous) and same(unpack(self.state['transcript']), self.frames))

    def write(self, value):
        self.current()
        self.store.write(value, self.previous)
        need(same(self.store.read(), value))
        self.previous = self.state = deepcopy(value)


class DurableScriptMeasurements:
    def __init__(self, reader, history, *, source_lock=None):
        try:
            need(isinstance(reader, ScriptMeasurements) and isinstance(history, ScriptHistory)
                 and reader.run == history.run and reader.directory == history.directory
                 and reader.fixture_url == history.fixture_url)
            history.current()
            restore(reader, history.frames)
            self.reader, self.history = reader, history
            self.source_lock = source_lock or ScriptSourceLock(history.store.path.with_name('script-sources.lock'))
            need(isinstance(self.source_lock,ScriptSourceLock)
                 and self.source_lock.path == history.store.path.with_name('script-sources.lock'))
        except Exception:
            raise NativeUIError('Script history cannot restore original observation continuity') from None

    def read(self, ticket, after_epoch):
        try:
            started = self.reader.monotonic()
            need(number(started,0,1e15))
            with self.source_lock.held():
                return self._read_locked(ticket,after_epoch,started)
        except Exception:
            raise NativeUIError('Script durable observation failed; original ownership is retained') from None

    def _read_locked(self,ticket,after_epoch,started):
        try:
            self.source_lock.assert_held()
            identifier(ticket)
            need(integer(after_epoch, 1))
            reader, history = self.reader, self.history
            previous = started
            def check():
                nonlocal previous
                need(reader.guard() is not False)
                now = reader.monotonic()
                need(number(now, 0, 1e15) and previous <= now and now - started < 20)
                previous = now
            check()
            history.current()
            need(history.state['phase'] == 'ready' and len(history.frames) < MAX_FRAMES)
            check()
            pending = deepcopy(history.state)
            pending.update(phase='reading', revision=pending['revision'] + 1)
            # Persist uncertainty before the first original request. A failed
            # write/ACK never starts acquisition and never clears uncertainty.
            history.write(pending)
            check()
            actual = reader.read(ticket, after_epoch)
            check()
            need(type(reader.last_sources) is dict)
            frame = dict(ticket=ticket, afterEpochMs=after_epoch, **deepcopy(reader.last_sources))
            frames = history.frames + [frame]
            # The live readers retain their prefixes; also reject clock
            # regression across persisted acquisitions.
            validate_new_frame(history.frames, frame)
            finished = deepcopy(history.state)
            finished.update(phase='ready', revision=finished['revision'] + 1, transcript=pack(frames))
            check()
            history.write(finished)
            history.frames = frames
            check()
            return actual
        except Exception:
            raise NativeUIError('Script durable observation failed; original ownership is retained') from None


def validate_new_frame(previous, frame):
    # Every current frame has already passed the live readers and full compose.
    # Preserve their accepted prefixes; check the additional persisted clocks.
    exact(frame, {'ticket', 'afterEpochMs', 'epochMs', 'execution', 'ui', 'service', 'lifecycle'})
    unique_queries(previous + [frame])
    if previous:
        old = previous[-1]
        need(frame['epochMs'] >= old['epochMs'])
        for source, field in (('execution', 'capturedEpochMs'), ('ui', 'capturedEpochMs'),
                              ('service', 'sampleEpochMs'), ('lifecycle', 'capturedEpochMs')):
            need(frame[source][field] >= old[source][field])
