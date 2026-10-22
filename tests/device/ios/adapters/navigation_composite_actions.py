"""Ordinary Places selection, independent native arrival, then owned close.

This coordinator does not establish the subsequent image/actor verdict or
whole-run cleanup. Every failed or uncertain stage retains its responsibility.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time

from adapters.native_clock_join import NativeClockAcquisition, digest, validate_join
from adapters.native_feature_observation import exact, need, number
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack, unpack, same
from ios.adapters.graphics_history import follow_native
from ios.adapters.navigation_observation_owner import fixture_original
from ios.adapters.navigation_places_actions import NavigationPlacesActions
from ios.adapters.navigation_surface_actions import NavigationSurfaceActions
from ios.adapters.navigation_process_scope import owner_path
from ios.adapters import navigation_state as source
from navigation_observation import viewpoint_urls

VERSION = 1


class NavigationArrivalPending(NativeUIError):
    """An original read completed, but genuine scene/pose arrival is pending."""


class NavigationCompositeActions:
    def __init__(self, store, surfaces, places, navigation, *,
                 epoch_ms=lambda: time.time()*1000, monotonic=time.monotonic):
        need(isinstance(store, PrivateFeatureState) and isinstance(surfaces, NavigationSurfaceActions)
             and isinstance(places, NavigationPlacesActions) and isinstance(navigation, source.IOSNavigationState)
             and callable(epoch_ms) and callable(monotonic)
             and store.path == owner_path(surfaces.admission,'ios-navigation-composite-actions.json')
             and store.path.parent == surfaces.store.path.parent == places.store.path.parent
             and same(surfaces.binding, places.binding) and surfaces.run == places.run
             and surfaces.lock.path == places.lock.path and surfaces.admission.fixture is places.fixture
             and navigation.pid == int(surfaces.binding['processIdentity']))
        self.store, self.surfaces, self.places, self.navigation = store, surfaces, places, navigation
        self.admission = surfaces.admission
        self.binding, self.run, self.lock = surfaces.binding, surfaces.run, surfaces.lock
        self.epoch_ms, self.monotonic = epoch_ms, monotonic
        self.last_clock = None; self.lock.assert_held(); self.previous = store.read()
        self.state = None if self.previous is None else self.decode(self.previous)
        self.bound()

    def envelope(self, state):
        return dict(iosNavigationCompositeActionsVersion=VERSION, binding=self.binding,
                    runId=self.run, payload=pack([state]))

    def call(self, value):
        self.places.validate_call(value)
        need(value['verb'] in ('directory-select', 'bookmark-visit')); return value

    def selected(self, row):
        need(row['selection'] is not None and row['surface'] is not None)
        selected = self.places.decode(row['selection'])['actions']
        need(selected and selected[-1]['phase'] == 'acknowledged' and same(selected[-1]['call'], row['call']))
        surface = self.surfaces.decode(row['surface'])['actions']
        need(surface and surface[-1]['phase'] == 'acknowledged' and surface[-1]['surface'] == 'open')
        need(self.places.state is not None and self.surfaces.state is not None
             and same(selected, self.places.state['actions'][:len(selected)])
             and same(surface, self.surfaces.state['actions'][:len(surface)]))
        if row['call']['verb'] == 'bookmark-visit': need(same(surface[-1]['call'], row['call']))
        return selected[-1], surface[-1]['page']

    def frame(self, frame, row, previous):
        exact(frame, {'hostBarrier', 'phaseBefore', 'nativeStart', 'originals', 'nativeEnd', 'clockJoin', 'phaseAfter', 'ready'})
        need(number(frame['hostBarrier'], row['startedEpochMs'], 1e15)
             and type(frame['originals']) is dict and set(frame['originals']) <= {'navigation', 'ui'}
             and (frame['ready'] is None or type(frame['ready']) is bool))
        if frame['clockJoin'] is None: need(frame['ready'] is None); return
        selected, page = self.selected(row); originals = frame['originals']; exact(originals, {'navigation', 'ui'})
        clock = validate_join(frame['clockJoin'], originals)
        need(same(frame['nativeStart'], {key:clock[key] for key in
            ('clockJoinVersion', 'hostBeforeEpochMs', 'hostBeforeMonotonic', 'nativeBefore')})
             and same(frame['nativeEnd'], {key:clock[key] for key in
             ('nativeAfter', 'hostAfterEpochMs', 'hostAfterMonotonic')}))
        for phase in (frame['phaseBefore'], frame['phaseAfter']):
            fixture_original(phase, self.run, self.places.fixture.inputs, self.places.fixture.instance)
            need((phase['ticket'], phase['verb']) == (row['call']['ticket'], row['call']['verb'])
                 and same(phase['inputs'], row['call']['inputs']))
        first_phase, last_phase = frame['phaseBefore'], frame['phaseAfter']
        need(same(first_phase['originals']['phaseAfter']['activations'], last_phase['originals']['phaseAfter']['activations'])
             and first_phase['providerReadEpochMs'] <= last_phase['originals']['phaseBefore']['capturedEpochMs'])
        native_first, native_last = clock['nativeBefore'], clock['nativeAfter']
        need(native_first['lifecycle'] == native_last['lifecycle']
             and native_first['processId'] == int(self.binding['processIdentity']))
        old = self.admission.archive()
        if previous is None:
            follow_native(old['clockJoin']['nativeAfter'], native_first)
            prior = old['originals']['navigation']
        else:
            follow_native(previous['clockJoin']['nativeAfter'], native_first)
            prior = previous['originals']['navigation']
        packet = originals['navigation']
        source.validate(packet, dict(schemaVersion=1, commandId=packet['requestId'], action=source.ACTION, runId=self.run),
                        int(self.binding['processIdentity']), native_last['capturedEpochMs'], prior)
        need(native_first['capturedEpochMs'] <= packet['clockBefore']['epochMs']
             <= packet['clockAfter']['epochMs'] <= native_last['capturedEpochMs']
             and packet['clockBefore']['epochMs'] >= selected['observed']['scope']['sampleEpochMs'])
        ui = self.surfaces.packet(originals['ui'])
        need(self.surfaces.page(ui) == page and ui['lastSequence'] >= selected['observed']['scope']['sequence']
             and ui['sampleEpochMs'] >= selected['observed']['scope']['sampleEpochMs'])
        if previous is not None: self.surfaces.follow(previous['originals']['ui'], ui)
        label = 'B' if row['call']['verb'] == 'directory-select' else 'A'
        try: source.pose_ready(packet, viewpoint_urls(self.places.fixture.inputs['sceneUrl'])[label], label)
        except NativeUIError: ready = False
        else: ready = True
        if frame['ready'] is not None: need(frame['ready'] == ready)
        return ready

    def decode(self, value):
        exact(value, {'iosNavigationCompositeActionsVersion', 'binding', 'runId', 'payload'})
        rows = unpack(value['payload']); need(type(value['iosNavigationCompositeActionsVersion']) is int
            and value['iosNavigationCompositeActionsVersion'] == VERSION and len(rows) == 1
            and same(value, self.envelope(rows[0])))
        state = rows[0]; exact(state, {'actions'}); need(type(state['actions']) is list and 1 <= len(state['actions']) <= 2)
        tickets = set()
        for index, row in enumerate(state['actions']):
            exact(row, {'call', 'phase', 'startedEpochMs', 'startedMonotonic', 'selection', 'surface', 'frames', 'close'})
            self.call(row['call']); need(row['call']['ticket'] not in tickets); tickets.add(row['call']['ticket'])
            need(row['phase'] in ('opening', 'selecting', 'arriving', 'closing', 'delivered')
                 and (index == len(state['actions'])-1 or row['phase'] == 'delivered')
                 and number(row['startedEpochMs'], 1, 1e15) and number(row['startedMonotonic'], 0, 1e15)
                 and type(row['frames']) is list and len(row['frames']) <= 32)
            if row['phase'] in ('arriving', 'closing', 'delivered'): self.selected(row)
            previous = None
            for frame_index, frame in enumerate(row['frames']):
                need(frame_index == len(row['frames'])-1 or type(frame['ready']) is bool)
                self.frame(frame, row, previous)
                if frame['clockJoin'] is not None: previous = frame
                else: need(frame_index == len(row['frames'])-1)
            if row['phase'] in ('closing', 'delivered'):
                need(row['frames'] and row['frames'][-1]['ready'] is True)
            if row['phase'] == 'delivered':
                closed = self.surfaces.decode(row['close'])['actions'][-1]
                need(closed['phase'] == 'acknowledged' and closed['surface'] == 'close'
                     and same(closed['call'], row['call'])
                     and closed['before']['sampleEpochMs'] >= row['frames'][-1]['originals']['ui']['sampleEpochMs'])
            else: need(row['close'] is None)
        return state

    def bound(self):
        self.lock.assert_held(); self.surfaces.bound(); self.places.bound()
        need(same(self.store.read(), self.previous))
        now = self.monotonic(); need(number(now, 0, 1e15) and (self.last_clock is None or now >= self.last_clock))
        self.last_clock = now; return now

    def deadline(self, row):
        now = self.bound(); epoch = self.epoch_ms()
        need(number(now, row['startedMonotonic'], row['startedMonotonic']+30)
             and now-row['startedMonotonic'] < 30 and number(epoch, row['startedEpochMs'], row['startedEpochMs']+30000)
             and abs(epoch-row['startedEpochMs']-(now-row['startedMonotonic'])*1000) <= 250)

    def save(self):
        self.bound(); value = self.envelope(self.state); self.decode(value)
        self.store.write(value, self.previous); need(same(self.store.read(), value)); self.previous = deepcopy(value); self.bound()

    def act(self, call):
        call = deepcopy(self.call(call)); self.bound()
        if self.state is None: self.state = dict(actions=[])
        rows = self.state['actions']
        if rows:
            last = rows[-1]
            if any(row['call']['ticket'] == call['ticket'] for row in rows):
                need(last['phase'] == 'delivered' and same(last['call'], call)); return {'performed':True}
            need(last['phase'] == 'delivered')
        need(len(rows) < 2)
        row = dict(call=call, phase='opening' if call['verb'] == 'bookmark-visit' else 'selecting',
            startedEpochMs=self.epoch_ms(), startedMonotonic=self.bound(), selection=None, surface=None, frames=[], close=None)
        rows.append(row); self.save()
        if row['phase'] == 'opening':
            self.surfaces.act(call, surface='open'); self.deadline(row); row['phase'] = 'selecting'; self.save()
        self.places.act(call); self.deadline(row)
        row.update(selection=deepcopy(self.places.store.read()), surface=deepcopy(self.surfaces.store.read()), phase='arriving')
        self.save(); return self.settle()

    def settle(self):
        """Read new arrival originals only; never repeat an uncertain selection."""
        self.bound(); need(self.state is not None); row = self.state['actions'][-1]
        need(row['phase'] == 'arriving' and len(row['frames']) < 32
             and (not row['frames'] or type(row['frames'][-1]['ready']) is bool)); self.deadline(row)
        frame = dict(hostBarrier=self.epoch_ms(), phaseBefore=None, nativeStart=None, originals={},
                     nativeEnd=None, clockJoin=None, phaseAfter=None, ready=None)
        row['frames'].append(frame); self.save()
        frame['phaseBefore'] = self.places.fixture.read(); self.save()
        window = NativeClockAcquisition(self.admission.native, epoch_ms=self.epoch_ms, monotonic=self.monotonic)
        window.begin(frame['hostBarrier']); frame['nativeStart'] = deepcopy(window.started); self.save()
        frame['originals']['navigation'] = self.navigation.read(self.run); self.save()
        frame['originals']['ui'] = self.surfaces.capture(); self.save()
        frame['nativeEnd'] = dict(nativeAfter=self.admission.native.read(self.admission.native.sequence),
            hostAfterEpochMs=self.epoch_ms(), hostAfterMonotonic=self.monotonic()); self.save()
        frame['phaseAfter'] = self.places.fixture.read(); self.save()
        frame['clockJoin'] = dict(window.started, **frame['nativeEnd'], originalsSha256=digest(frame['originals']),
            sourceTimes=[dict(source='ui', field='sampleEpochMs', epochMs=frame['originals']['ui']['sampleEpochMs'])])
        self.save(); frame['ready'] = self.frame(frame, row, row['frames'][-2] if len(row['frames']) > 1 else None); self.save()
        self.deadline(row)
        if not frame['ready']: raise NavigationArrivalPending('Actual native scene/pose has not arrived')
        # Closing follows the newly acquired original only, within its original
        # acquisition deadline. An old retained ready frame is never retimed.
        clock = frame['clockJoin']
        need(number(self.monotonic(), clock['hostAfterMonotonic'], clock['hostBeforeMonotonic']+1.5)
             and self.monotonic()-clock['hostBeforeMonotonic'] < 1.5
             and number(self.epoch_ms(), clock['hostAfterEpochMs'], clock['hostBeforeEpochMs']+1500)
             and self.epoch_ms()-clock['hostBeforeEpochMs'] < 1500)
        row['phase'] = 'closing'; self.save(); self.surfaces.act(row['call'], surface='close'); self.deadline(row)
        row.update(close=deepcopy(self.surfaces.store.read()), phase='delivered'); self.save(); return {'performed':True}

    def recover_arrival(self):
        """Seal a fully retained read without new sources, input or retiming.

        A subsequent settle always reads a new frame before authorizing close.
        An interrupted partial acquisition remains owned and cannot be replaced.
        """
        self.bound(); need(self.state is not None); row = self.state['actions'][-1]
        need(row['phase'] == 'arriving' and row['frames']); frame = row['frames'][-1]
        need(frame['ready'] is None and frame['clockJoin'] is not None)
        frame['ready'] = self.frame(frame, row, row['frames'][-2] if len(row['frames']) > 1 else None)
        self.save(); return frame['ready']

    def recover_close(self):
        """Recover only an already retained child acknowledgment, without input."""
        self.bound(); need(self.state is not None); row = self.state['actions'][-1]; need(row['phase'] == 'closing')
        close = deepcopy(self.surfaces.store.read()); closed = self.surfaces.decode(close)['actions'][-1]
        need(closed['phase'] == 'acknowledged' and closed['surface'] == 'close' and same(closed['call'], row['call']))
        row.update(close=close, phase='delivered'); self.save(); return {'performed':True}
