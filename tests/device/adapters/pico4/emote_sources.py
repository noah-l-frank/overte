"""Durable original Pico Emote acquisition; no action or success synthesis.

The existing shared source lock serializes the actual native query channel.
Interrupted acquisition stays owned. Historical originals restore cursors only;
they never satisfy a new read or permit replaying a product input.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import math
import time

from adapters.emote_animation_readiness import ready as animation_ready
from adapters.emote_originals import EmoteOriginals, BLOCK
from adapters.emote_rig_measurements import source, continuation
from adapters.graphics_journey.source_history import restore_native
from adapters.native_animation_history import accept as animation_history
from adapters.native_animation_inventory import NativeAnimationInventory, validate as inventory_packet
from adapters.native_feature_observation import exact, fresh, integer, need, number
from adapters.native_script_observation import NativeScriptObservation
from adapters.native_script_roots import validate as roots_packet
from adapters.normal_feature_state import context
from adapters.normal_ui import NativeUIError
from adapters.pico4.navigation import validate_snapshot
from adapters.pico4.normal_emote import project
from adapters.script_journey.history import same, pack, unpack
from adapters.script_journey.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from feature_journeys.phase_fixture import PhaseFixtureReader, validate as phase_packet

VERSION = 1
MAX_FRAMES = 512


class EmotePhaseChanged(NativeUIError):
    """The retained acquisition crossed an original fixture input boundary."""


class PicoEmoteSources:
    def __init__(self, store, binding, phase, role, lock, artifact_root, readers, guard, clock_ms,
                 *, monotonic=time.monotonic):
        need(isinstance(phase, PhaseFixtureReader) and phase.area == 'emotes'
             and role in ('primary', 'actor') and isinstance(lock, ScriptSourceLock)
             and all(callable(fn) for fn in (readers, guard, clock_ms, monotonic)))
        self.store, self.binding, self.phase, self.role = store, deepcopy(context(binding)), phase, role
        self.run = identifier(phase.run)
        self.pid = int(self.binding['processIdentity'].split(':')[0]); need(integer(self.pid, 1))
        self.lock, self.readers, self.guard, self.monotonic = lock, readers, guard, monotonic
        self.clock_ms = clock_ms
        self.frames, self.failed = [], False
        self.state = dict(phase='ready', revision=0, manifests=[], pending=None)
        self.originals = EmoteOriginals(artifact_root, self.binding, self.run, role, guard,
            self.storage_intent, monotonic=monotonic)
        self.lock.assert_held(); need(self.guard() is not False)
        started = self.monotonic(); need(number(started, 0, 1e15))
        self.previous = store.read()
        if self.previous is not None:
            self.state, self.frames = self.decode(self.previous)
        self.bound(started, started)

    def bound(self, started, previous):
        self.lock.assert_held(); need(not self.failed and self.guard() is not False)
        need(same(self.store.read(), self.previous))
        now = self.monotonic(); need(number(now, previous, started + 5))
        return now

    def save(self):
        self.lock.assert_held(); need(not self.failed and self.guard() is not False)
        self.state['revision'] = len(self.frames)
        value = dict(picoEmoteSourcesVersion=VERSION, binding=self.binding, runId=self.run,
            role=self.role, fixtureUrl=self.phase.fixture_url, artifactRoot=str(self.originals.root),
            payload=pack([self.state]))
        try:
            self.store.write(value, self.previous); need(same(self.store.read(), value))
            self.previous = deepcopy(value)
        except Exception:
            self.failed = True
            raise NativeUIError('Pico Emote source ownership could not be saved') from None

    def storage_intent(self, kind, value):
        need(self.state['phase'] == 'reading' and kind in ('original', 'manifest'))
        pending = self.state['pending']; old = pending[kind]
        if kind == 'original':
            self.originals.original(value); need(value['index'] == len(self.frames) + 1)
            if old is None: need(value['phase'] == 'planned')
            else:
                need(value['phase'] == {'planned': 'opened', 'opened': 'saved'}.get(old['phase'])
                     and all(same(value[key], old[key]) for key in value if key not in ('phase', 'file'))
                     and (old['phase'] == 'planned' or same(old['file'], value['file'])))
        else:
            exact(value, {'emoteManifestVersion', 'reference', 'phase'})
            need(type(value['emoteManifestVersion']) is int and value['emoteManifestVersion'] == 1
                 and pending['original'] is not None and pending['original']['phase'] == 'saved')
            self.originals.manifest_reference(value['reference'])
            need(value['reference']['block'] == len(self.frames) // BLOCK + 1
                 and value['reference']['count'] == len(self.frames) % BLOCK + 1)
            if old is None: need(value['phase'] == 'planned')
            else: need(old['phase'] == 'planned' and value['phase'] == 'saved'
                       and same(old['reference'], value['reference']))
        pending[kind] = deepcopy(value); self.save()

    def validate_frame(self, frame, previous=None):
        exact(frame, {'group', 'inventory', 'widgets', 'phaseBefore', 'phaseAfter', 'epochMs', 'hostEpochMs'})
        need(integer(frame['epochMs'], 1) and number(frame['hostEpochMs'], 1, 1e15))
        group = frame['group']; selected, native, _urls = source(group, self.pid, frame['epochMs'])
        # Required executable identity and the actual retained Pico chooser;
        # a Phone filename alone is never platform admission.
        need('compilation' in selected and selected['profile']['chooserAfterPlay'] == 'retained')
        animation_ready(dict(rootsBefore=group['rootsBefore'], script=group['script'],
            inventory=frame['inventory'], rootsAfter=group['rootsAfter']), pid=self.pid, epoch=frame['epochMs'])
        need(frame['inventory']['capturedEpochMs'] <= native['requestedEpochMs'])
        widgets = validate_snapshot(frame['widgets'], self.pid, frame['epochMs']); ui = project(widgets)
        need(ui['scope']['instance'] == self.binding['sessionId']
             and ui['scope']['capturedEpochMs'] >= group['rootsAfter']['capturedEpochMs'])
        fresh(ui['scope']['capturedEpochMs'], frame['epochMs'])
        before, after = frame['phaseBefore'], frame['phaseAfter']
        phase_packet(before, run=self.run, area='emotes', request=before['requestId'], epoch=frame['hostEpochMs'],
            previous=None if previous is None else previous['phaseAfter'])
        phase_packet(after, run=self.run, area='emotes', request=after['requestId'], epoch=frame['hostEpochMs'], previous=before)
        need(before['active'] and before['activations'] and after['active'] and after['activations']
             and group['rootsBefore']['requestedEpochMs'] >= before['activations'][-1]['activatedEpochMs'])
        if previous is not None:
            old = previous['group']; old_selected, _native, _urls = source(old, self.pid, previous['epochMs'])
            need(same(selected, old_selected) and frame['epochMs'] >= previous['epochMs']
                 and frame['hostEpochMs'] >= previous['hostEpochMs'])
            root = group['rootsBefore']
            roots_packet(root, dict(schemaVersion=1, commandId=root['commandId'], action='feature-script-roots-observe'),
                self.pid, frame['epochMs'], previous=old['rootsAfter'])
            inventory_packet(frame['inventory'], dict(schemaVersion=1, commandId=frame['inventory']['commandId'],
                action='feature-animation-inventory-observe'), self.pid, frame['epochMs'], previous=previous['inventory'])
            continuation(old['native'], native, self.pid)
            left, right = project(previous['widgets'])['scope'], ui['scope']
            need(all(left[key] == right[key] for key in ('instance', 'generation', 'processId'))
                 and right['sourceSequence'] > left['sourceSequence'] and right['sequence'] >= left['sequence']
                 and right['elapsedMs'] >= left['elapsedMs'] and right['capturedEpochMs'] >= left['capturedEpochMs'])
        return before['activations'][-1]['ticket'] == after['activations'][-1]['ticket']

    def replay(self, frames, script=None, inventory=None):
        # These readers never send. Replay original history including model
        # birth identities that might disappear from the latest cache survey.
        absent = lambda *_: need(False)
        script = script or NativeScriptObservation(absent, absent, absent, absent, self.pid)
        script.restore_history([frame['group']['script'] for frame in frames])
        inventory = inventory or NativeAnimationInventory(absent, absent, absent, absent, self.pid)
        history = None; previous = None
        seen = {key: set() for key in ('roots', 'script', 'native', 'inventory', 'phase')}
        for frame in frames:
            self.validate_frame(frame, previous)
            group = frame['group']
            for key, values, field in (
                    ('roots', (group['rootsBefore'], group['rootsAfter']), 'commandId'),
                    ('script', (group['script'],), 'requestId'), ('native', (group['native'],), 'requestId'),
                    ('inventory', (frame['inventory'],), 'commandId'),
                    ('phase', (frame['phaseBefore'], frame['phaseAfter']), 'requestId')):
                for value in values:
                    need(value[field] not in seen[key]); seen[key].add(value[field])
            inventory.models, inventory.urls = inventory.accept(frame['inventory'])
            history = animation_history(history, group['native']['animation']['rigId'], group['native']['animation']['history'])
            previous = frame
        if frames: inventory.last = deepcopy(frames[-1]['inventory'])
        return history

    def decode(self, value):
        exact(value, {'picoEmoteSourcesVersion', 'binding', 'runId', 'role', 'fixtureUrl', 'artifactRoot', 'payload'})
        need(type(value['picoEmoteSourcesVersion']) is int and value['picoEmoteSourcesVersion'] == VERSION
             and same(value['binding'], self.binding) and value['runId'] == self.run and value['role'] == self.role
             and value['fixtureUrl'] == self.phase.fixture_url and value['artifactRoot'] == str(self.originals.root))
        rows = unpack(value['payload']); need(len(rows) == 1); state = rows[0]
        exact(state, {'phase', 'revision', 'manifests', 'pending'})
        need(state['phase'] in ('reading', 'ready') and integer(state['revision'], 0, MAX_FRAMES))
        frames = self.originals.restore(state['manifests'], state['revision']); self.replay(frames)
        if state['phase'] == 'ready': need(state['pending'] is None)
        else:
            pending = state['pending']; exact(pending, {'startedEpochMs', 'original', 'manifest'})
            need(integer(pending['startedEpochMs'], 1) and state['revision'] < MAX_FRAMES)
            if pending['original'] is not None:
                self.originals.original(pending['original']); need(pending['original']['index'] == state['revision'] + 1)
            if pending['manifest'] is not None:
                item = pending['manifest']; exact(item, {'emoteManifestVersion', 'reference', 'phase'})
                need(type(item['emoteManifestVersion']) is int and item['emoteManifestVersion'] == 1
                     and item['phase'] in ('planned', 'saved') and pending['original'] is not None
                     and pending['original']['phase'] == 'saved')
                self.originals.manifest_reference(item['reference'])
                need(item['reference']['block'] == state['revision'] // BLOCK + 1
                     and item['reference']['count'] == state['revision'] % BLOCK + 1)
        return deepcopy(state), deepcopy(frames)

    def recover_complete(self):
        """Commit exact complete original bytes only, with no transport/input.

        Missing/partial originals remain unresolved. No historical frame is
        delivered as a current observation and no journal is retired here.
        """
        started = previous = self.monotonic(); need(number(started, 0, 1e15))
        previous = self.bound(started, previous)
        need(self.state['phase'] == 'reading'); state, frames = self.decode(self.previous)
        need(same(state, self.state) and same(frames, self.frames))
        pending = self.state['pending']; original = pending['original']; need(original is not None)
        frame = self.originals.read(original)
        need(frame['group']['rootsBefore']['requestedEpochMs'] >= pending['startedEpochMs'])
        self.replay(self.frames + [frame]); previous = self.bound(started, previous)
        if original['phase'] == 'opened':
            original = deepcopy(original); original['phase'] = 'saved'; self.storage_intent('original', original)
        reference = self.originals.compact(original)
        manifests = self.originals.resume_manifest(self.state['manifests'], reference, pending['manifest'])
        previous = self.bound(started, previous)
        self.frames.append(deepcopy(frame)); self.state.update(phase='ready', manifests=manifests, pending=None)
        self.save(); self.bound(started, previous)

    def read(self):
        started = previous = self.monotonic(); need(number(started, 0, 1e15))
        previous = self.bound(started, previous)
        need(self.state['phase'] == 'ready' and len(self.frames) < MAX_FRAMES)
        device_start = self.clock_ms(); host_start = self.phase.epoch_ms()
        need(integer(device_start, 1) and number(host_start, 1, 1e15))
        self.state.update(phase='reading', pending=dict(startedEpochMs=device_start, original=None, manifest=None)); self.save()
        previous = self.bound(started, previous)
        roots, script, inventory, native, widgets = self.readers()
        need(roots.pid == script.pid == inventory.pid == native.pid == self.pid
             and not any(reader.ios for reader in (roots, script, inventory, native)))
        history = self.replay(self.frames, script, inventory)
        last = self.frames[-1] if self.frames else None
        if last:
            roots.restore(last['group']['rootsAfter']); restore_native(native, last['group']['native'])
            native.animation_history = history
            native.rig = last['group']['native']['animation']['rigId']
            native.rig_sequence = last['group']['native']['animation']['evaluationSequence']
        phase = self.phase.read(None if last is None else last['phaseAfter'])
        before = roots.read(0 if roots.last is None else roots.last['sequence'])
        code = script.read(script.sequence, require_effects=True, require_code_identity=True,
            require_load_history=True, require_membership=True)
        cached = inventory.read(0 if inventory.last is None else inventory.last['sequence'])
        measured = native.read(native.sequence, require_animation=True, require_animation_history=True)
        after = roots.read(before['sequence']); visual = widgets.capture()
        final = self.phase.status(phase['status'])
        frame = dict(group=dict(rootsBefore=before, script=code, native=measured, rootsAfter=after),
            inventory=cached, widgets=visual, phaseBefore=phase['status'], phaseAfter=final,
            epochMs=native.clock_ms(), hostEpochMs=self.phase.epoch_ms())
        stable = self.validate_frame(frame, last); self.replay(self.frames + [frame])
        previous = self.bound(started, previous)
        self.fresh_delivery(frame, native, started, device_start, host_start, previous)
        original = self.originals.write(len(self.frames) + 1, frame)
        manifests = self.originals.append(self.state['manifests'], original)
        self.frames.append(deepcopy(frame)); self.state.update(phase='ready', manifests=manifests, pending=None); self.save()
        previous = self.bound(started, previous)
        self.fresh_delivery(frame, native, started, device_start, host_start, previous)
        if not stable: raise EmotePhaseChanged('Original Pico Emote sources crossed the input phase; retained without current facts')
        return deepcopy(frame)

    def fresh_delivery(self, frame, native, started, device_start, host_start, previous):
        epoch, host = native.clock_ms(), self.phase.epoch_ms()
        end = self.bound(started, previous)
        need(integer(epoch, frame['epochMs']) and number(host, frame['hostEpochMs'], 1e15))
        floor = frame['group']['rootsBefore']['requestedEpochMs']
        phase_floor = frame['phaseBefore']['capturedEpochMs']
        need(max(epoch - floor, device_start - floor + math.ceil((end - started) * 1000)) <= 1500
             and max(host - phase_floor, host_start - phase_floor + (end - started) * 1000) <= 1500)
