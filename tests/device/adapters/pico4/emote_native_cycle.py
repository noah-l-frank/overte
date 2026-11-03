"""Private ordinary Emote cycle joined to original native effects and quiet.

This bounded Parent composes existing input/source/effect/lifetime owners. It
does not provide a remote Actor, renderer/image proof or whole-feature cleanup.
All product journals remain retained after native quiet; no discard is offered.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time

from adapters.host_process_identity import host_identity
from adapters.native_feature_observation import exact, integer, need, number
from adapters.native_fd_owner import require_directory
from adapters.pico4.emote_effects import PicoEmoteEffects
from adapters.pico4.emote_inputs import PicoEmoteInputs
from adapters.pico4.emote_lifetime import PicoEmoteLifetime
from adapters.pico4.emote_native_cycle_state import cycle_store, native_cycle_owned
from adapters.pico4.lifecycle_process_file import LifecycleProcessFile
from adapters.pico4.lifecycle_back import PicoLifecycleBack
from adapters.script_journey.history import same
from feature_journeys.contract import arguments

VERSION = 1
ORDER = ('open', 'play', 'cancel', 'close')
# An uncertain OFD cannot be force-closed or disappear behind constructor failure.
UNRESOLVED_HOST_FILES = []


class PicoEmoteNativeCycle:
    def __init__(self, store, inputs, lifetime, *, common=None):
        need(isinstance(inputs, PicoEmoteInputs) and isinstance(lifetime, PicoEmoteLifetime)
             and lifetime.source is inputs.source)
        if common is not None:
            from adapters.pico4.emote_common import PicoEmoteCommon
            need(type(common) is PicoEmoteCommon)
        self.common=self._common=common;self.version=self._version=1 if common is None else 2
        self.inputs, self.lifetime = inputs, lifetime
        self.source, self.effects = inputs.source, PicoEmoteEffects(inputs)
        self.source.lock.assert_held()
        self.identity = dict(picoEmoteNativeCycleVersion=self.version, binding=deepcopy(self.source.binding),
            runId=self.source.run, fixtureUrl=self.source.phase.fixture_url,
            artifactRoot=str(self.source.artifact_root), parentHostProcessIdentity=host_identity())
        if common is not None:self.identity['commonPlanSha256']=common.plan_sha
        # Keep the actual owner reachable even if its constructor fails after
        # acquiring one of its original descriptor pairs.
        self.file = object.__new__(LifecycleProcessFile)
        self.store, self.previous = store, None
        self.failed = False; self.clock = self.epoch = self.host = None
        self.state = None
        self.original_guard = self.source.guard
        # Existing input.before_send and source/work guards now enforce this
        # SAME Parent admission budget, including inside the delegated action.
        try:
            LifecycleProcessFile.__init__(self.file, store)
            self.previous = store.read()
            self.source.guard = self.candidate_guard
            if common is not None:
                need(self.previous is None) # Explicit warm Parent2; no cold owner adoption.
                common.attach(self)
            self.guard()
            if self.previous is not None:
                exact(self.previous, set(self.identity) | {'state'})
                need(all(same(self.previous[key], value) for key, value in self.identity.items()))
                self.state = deepcopy(self.previous['state']); self.validate()
                self.bound()
        except BaseException:
            self.failed = True
            if hasattr(self.file, 'parent') and not self.file.close_host():
                UNRESOLVED_HOST_FILES.append(self.file)
            raise

    def candidate_guard(self):
        need(not self.failed and self.original_guard() is not False)
        self.file.guard(); require_directory(self.file.parent, self.store.path.parent)
        self.clocks()
        return True

    def guard(self):
        self.source.lock.assert_held()
        need(not self.failed and self.common is self._common and type(self.version) is int
            and self.version==self._version==(1 if self.common is None else 2)
            and self.identity['picoEmoteNativeCycleVersion']==self.version and self.source.guard() is not False)
        if self.common is not None:self.common.guard()
        self.file.guard(); require_directory(self.file.parent, self.store.path.parent)
        need(same(self.store.read(), self.previous)
             and same(self.source.store.read(), self.source.previous)
             and same(self.inputs.store.read(), self.inputs.previous))
        self.file.guard()

    def bound(self):
        self.guard()
        self.clocks()

    def clocks(self):
        now, epoch, host = self.source.monotonic(), self.source.clock_ms(), self.source.phase.epoch_ms()
        need(number(now, 0 if self.clock is None else self.clock, 1e15)
             and integer(epoch, 1 if self.epoch is None else self.epoch)
             and number(host, 1 if self.host is None else self.host, 1e15))
        if self.state is not None:
            state = self.state
            need(state['started'] <= now < state['started'] + 120
                 and state['epochMs'] <= epoch < state['epochMs'] + 120000
                 and state['hostEpochMs'] <= host < state['hostEpochMs'] + 120000)
        self.clock, self.epoch, self.host = now, epoch, host

    def save(self):
        self.bound()
        if self.common is not None:self.common.validate()
        value = dict(self.identity, state=deepcopy(self.state))
        self.file.write(value, self.previous); self.previous = deepcopy(value)
        self.bound()

    def validate(self):
        if self.common is not None:return self.common.validate()
        state = self.state
        exact(state, {'phase', 'started', 'epochMs', 'hostEpochMs', 'baseline', 'steps', 'cleanup'})
        need(state['phase'] in ('baseline-issued', 'ready', 'input-issued', 'cleanup-issued', 'native-quiet')
             and number(state['started'], 0, 1e15) and integer(state['epochMs'], 1)
             and number(state['hostEpochMs'], 1, 1e15) and type(state['steps']) is list and len(state['steps']) <= 4)
        if state['baseline'] is None:
            need(state['phase'] == 'baseline-issued' and not state['steps'] and state['cleanup'] is None)
            return
        baseline = self.effects.phase_recompute(state['baseline'])
        need(baseline['phase'] == 'baseline' and baseline['state']['panel'] is False)
        played = None
        for index, row in enumerate(state['steps']):
            exact(row, {'call', 'frame', 'played'})
            call = arguments('feature.emotes.act', row['call'])
            need(call['verb'] == ORDER[index] and call['runId'] == self.source.run
                 and call['fixtureUrl'] == self.source.phase.fixture_url and same(row['played'], played))
            if row['frame'] is None:
                need(index == len(state['steps']) - 1 and state['phase'] == 'input-issued')
                continue
            effect = self.effects.recompute(row['frame'], played=played, call=call)
            if call['verb'] == 'play': played = effect['playbackReference']
            if call['verb'] == 'cancel':
                need(effect['kind'] == 'restoration' and effect['state']['restoredBeforeNominalEnd'] is True)
        if state['phase'] in ('cleanup-issued', 'native-quiet'):
            need(len(state['steps']) == 4 and all(row['frame'] is not None for row in state['steps']))
            cleanup = state['cleanup']
            exact(cleanup, {'ticket', 'neutral', 'neutralFrame', 'window', 'frame'})
            if cleanup['neutral'] is None:
                need(state['phase'] == 'cleanup-issued' and cleanup['neutralFrame'] is None
                     and cleanup['window'] is None and cleanup['frame'] is None)
            else:
                frame = self.effects.current_original(cleanup['neutralFrame'])
                need(self.lifetime.cleanup_phase(frame['phaseBefore']) == cleanup['ticket'])
                self.lifetime.cleanup_phase(frame['phaseAfter'], cleanup['ticket'])
                streams = [item for row in self.inputs.state['history'] + [self.inputs.state['current']]
                    for item in row['intents'] if item['kind'] == 'controller']
                need(bool(streams))
                PicoLifecycleBack.neutral(cleanup['neutral'], streams[-1]['stream']['envelope'],
                    frame['widgets']['updatedEpochMs'])
        if state['phase'] == 'native-quiet':
            need(self.lifetime.state['phase'] == 'complete'
                 and same(state['cleanup']['window'], self.lifetime.state['window']))
            value = self.effects.phase_recompute(state['cleanup']['frame'])
            need(value['phase'] == 'cleanup' and value['ticket'] == state['cleanup']['ticket']
                 and value['state']['panel'] is False)

    def baseline(self):
        self.bound(); need(self.state is None and self.inputs.previous is None and not self.source.frames)
        self.state = dict(phase='baseline-issued', started=self.clock, epochMs=self.epoch,
            hostEpochMs=self.host, baseline=None, steps=[], cleanup=None)
        self.save()  # Ownership precedes the first original query.
        try:
            self.source.read()
            value = self.effects.phase_measure(self.effects.reference())
            need(value['phase'] == 'baseline' and value['state']['panel'] is False)
            self.bound(); self.state.update(phase='ready', baseline=deepcopy(value['frame'])); self.save()
            return deepcopy(value)
        except BaseException:
            self.failed = True; raise

    def act(self, call):
        if self.common is not None:return self.common.act(call)
        self.bound(); need(self.state is not None and self.state['phase'] == 'ready')
        call = deepcopy(arguments('feature.emotes.act', call)); rows = self.state['steps']
        need(len(rows) < len(ORDER) and call['verb'] == ORDER[len(rows)]
             and call['runId'] == self.source.run and call['fixtureUrl'] == self.source.phase.fixture_url
             and all(row['call']['ticket'] != call['ticket'] for row in rows))
        # Admission uses current provider truth, before any original input intent.
        floor = self.source.frames[-1]['phaseAfter']
        self.inputs.active(call, self.source.phase.status(floor)); self.bound()
        played = None
        if len(rows) >= 2:
            played = self.effects.recompute(rows[1]['frame'], call=rows[1]['call'])['playbackReference']
        self.state['steps'].append(dict(call=call, frame=None, played=deepcopy(played)))
        self.state['phase'] = 'input-issued'; self.save()
        try:
            self.bound(); self.inputs.act(call)  # Exactly one delegation; ACK is not effect evidence.
            self.source.read(); self.source.read()
            value = self.effects.measure(self.effects.reference(), played=played)
            if call['verb'] == 'cancel':
                need(value['kind'] == 'restoration' and value['state']['restoredBeforeNominalEnd'] is True)
            self.bound(); self.state['steps'][-1]['frame'] = deepcopy(value['frame'])
            self.state['phase'] = 'ready'; self.save(); return deepcopy(value)
        except BaseException:
            self.failed = True; raise

    def observe(self):
        need(self.common is not None);return self.common.observe()

    def cleanup(self, *, sleep=time.sleep):
        if self.common is not None:return self.common.cleanup(sleep=sleep)
        self.bound()
        need(self.state is not None and self.state['phase'] == 'ready' and len(self.state['steps']) == 4
             and callable(sleep))
        # Cleanup observes the original cleanup ticket. Never synthesize a
        # Cancel/Close against it or reissue one of the completed normal calls.
        status = self.source.phase.status(self.source.frames[-1]['phaseAfter'])
        ticket = self.lifetime.cleanup_phase(status)
        self.bound(); self.state.update(phase='cleanup-issued', cleanup=dict(ticket=ticket,
            neutral=None, neutralFrame=None, window=None, frame=None)); self.save()
        try:
            neutral = self.inputs.controller_retirement()
            self.state['cleanup'].update(neutral=deepcopy(neutral), neutralFrame=self.effects.reference()); self.save()
            window = self.lifetime.wait(sleep=sleep)
            value = self.effects.phase_measure(self.effects.reference())
            need(value['phase'] == 'cleanup' and value['ticket'] == ticket and value['state']['panel'] is False)
            self.bound(); self.state['cleanup'].update(window=deepcopy(window), frame=deepcopy(value['frame']))
            self.state['phase'] = 'native-quiet'
            self.save()
            return dict(picoEmoteNativeCycleVersion=VERSION, nativeQuiet=deepcopy(self.state['cleanup']),
                wholeFeatureComplete=False, independentActorQualified=False, stereoQualified=False,
                originalsRetained=True)
        except BaseException:
            self.failed = True; raise

    def close_host(self):
        """Close only verified original host OFDs, preserving all product journals."""
        common_closed=True if self.common is None else self.common.close_host()
        value = self.file.close_host() and common_closed
        self.failed = True
        if not value:
            self.failed = True
            if self.file not in UNRESOLVED_HOST_FILES: UNRESOLVED_HOST_FILES.append(self.file)
        return value


def create(adapter, target, phase, artifact_root, source_lock, *, common=None):
    """Existing adapter factories, exact shared held lock; no new input service."""
    source_lock.assert_held()
    store = cycle_store(adapter, target)
    # An orphan without its root is not a new baseline or an adoption authority.
    need(store.read() is not None or not native_cycle_owned(adapter, target))
    source = adapter._emote_sources(target, phase, 'primary', artifact_root, source_lock)
    inputs = adapter._emote_inputs(target, source)
    lifetime = adapter._emote_lifetime(target, source)
    options={} if common is None else dict(common=common)
    return PicoEmoteNativeCycle(store, inputs, lifetime,**options)
