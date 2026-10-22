"""Durable ordinary Places surface inputs, with actual original page ownership.

Input acknowledgments do not establish navigation, bookmark effects, callback
retirement or full cleanup. The enclosing Worlds owner retains those duties.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
import time

from adapters.native_feature_observation import exact, need, number
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUI
from adapters.script_feature.history import pack, unpack, same
from feature_journeys.contract import arguments
from feature_journeys.phase_fixture import validate as phase_packet
from ios.adapters.navigation_admission_owner import NavigationAdmissionOwner
from ios.adapters.navigation_process_scope import NavigationProcessScope,owner_path
from ios.adapters.navigation_observation_owner import fixture_original
from ios.adapters.normal_input import NativeInput, observation
from ios.adapters.normal_navigation import IOSNavigation, PROFILE
from ios.adapters import places_controls as controls

VERSION = 2
READS = (1, 2)
SURFACES = {'open': ('open',), 'close': ('close',),
            'directory-select': ('close',), 'bookmark-visit': ('open', 'close')}


class _SurfaceUI(NativeUI):
    def __init__(self, owner):
        source = owner.ui
        super().__init__(source.client, owner.binding['sessionId'], owner.bound,
                         timeout=source.timeout, monotonic=source.monotonic, sleep=source.sleep)
        self.owner = owner

    def _request(self, method, path, body=None):
        if method == 'POST' and path.endswith('/click'):
            self.owner.input_intent(method, path, body)
        elif method == 'DELETE' and path == '/actions':
            self.owner.input_intent(method, path, body)
        return super()._request(method, path, body)


class NavigationSurfaceActions:
    def __init__(self, store, admission, ui, native, *, monotonic=time.monotonic):
        need(isinstance(store, PrivateFeatureState) and isinstance(admission, (NavigationAdmissionOwner,NavigationProcessScope))
             and not admission.historical and isinstance(ui, NativeUI) and isinstance(native, NativeInput)
             and callable(monotonic) and store.path == owner_path(admission,'ios-navigation-surface-actions.json')
             and store.path.parent == admission.store.path.parent)
        self.store, self.admission, self.ui, self.native = store, admission, ui, native
        self.binding, self.run, self.lock = admission.binding, admission.run, admission.lock
        need(native.session == self.binding['sessionId'])
        self.monotonic = monotonic; self.started = self.last_clock = None
        self.lock.assert_held(); self.previous = store.read()
        self.state = None if self.previous is None else self.decode(self.previous)
        self.bound()

    def envelope(self, state, version=VERSION):
        return dict(iosNavigationSurfaceActionsVersion=version, binding=self.binding, runId=self.run, payload=pack([state]))

    def call(self, value):
        arguments('feature.world-navigation.act', value)
        need(value['runId'] == self.run and value['verb'] in SURFACES
             and value['fixtureUrl'] == self.admission.fixture.fixture_url)
        return value

    def packet(self, value):
        if isinstance(self.admission,NavigationProcessScope):self.admission.ui_original(value)
        observation(value, int(self.binding['processIdentity']), value.get('sampleEpochMs'))
        original = self.admission.archive()['originals']['ui']
        need(value['instance'] == original['instance'] and value['lastSequence'] >= original['lastSequence']
             and value['elapsedMs'] >= original['elapsedMs'] and value['sampleEpochMs'] >= original['sampleEpochMs']
             and value.get('placesControlsVersion') == 2)
        return value

    @staticmethod
    def follow(before, after):
        need(before['instance'] == after['instance'] and before['processId'] == after['processId']
             and before['lastSequence'] <= after['lastSequence'] and before['elapsedMs'] <= after['elapsedMs']
             and before['sampleEpochMs'] <= after['sampleEpochMs']
             and before['placesSourceSequence'] < after['placesSourceSequence'])

    @staticmethod
    def page(value):
        projected = controls.project(value)
        need(projected['open']); page = controls.reference(projected, 'places.page')['control']
        need(page['popup'] == 'none')
        return dict(rootId=page['rootId'], qmlSource=page['qmlSource'])

    def decode(self, value):
        exact(value, {'iosNavigationSurfaceActionsVersion', 'binding', 'runId', 'payload'})
        rows = unpack(value['payload'])
        version = value['iosNavigationSurfaceActionsVersion']
        need(type(version) is int and version in READS
             and len(rows) == 1 and same(value, self.envelope(rows[0], version)))
        state = rows[0]; exact(state, {'component', 'actions'})
        need(type(state['component']) is dict and set(state['component']) <= {'iosNormalNavigation'}
             and type(state['actions']) is list and 1 <= len(state['actions']) <= (8 if version == 1 else 12))
        tickets = set(); calls = {}; previous = None; owned_page = None; previous_phase = None
        for index, row in enumerate(state['actions']):
            exact(row, {'call', 'phase', 'fixture', 'before', 'intents', 'after', 'page'}
                  | ({'surface'} if version == 2 else set()))
            call = self.call(row['call']); ticket = call['ticket']
            surface = row['surface'] if version == 2 else call['verb']
            need(surface in SURFACES[call['verb']] and (ticket, surface) not in tickets)
            if ticket in calls: need(same(calls[ticket], call))
            calls[ticket] = call
            if version == 1: need(call['verb'] in ('open', 'close'))
            if index: need(surface != state['actions'][index-1].get('surface', state['actions'][index-1]['call']['verb']))
            tickets.add((ticket, surface))
            need(row['phase'] in ('checking', 'issued', 'acknowledged')
                 and (index == len(state['actions'])-1 or row['phase'] == 'acknowledged')
                 and type(row['intents']) is list and len(row['intents']) <= 32)
            if row['fixture'] is not None:
                fixture_original(row['fixture'], self.run, self.admission.fixture.inputs, self.admission.fixture.instance)
                if previous_phase is not None:
                    current_phase = row['fixture']['originals']['phaseBefore']
                    phase_packet(current_phase, run=self.run, area='world-navigation', request=current_phase['requestId'],
                                 epoch=current_phase['capturedEpochMs'], previous=previous_phase)
                previous_phase = row['fixture']['originals']['phaseAfter']
                if row['phase'] != 'checking':
                    need(row['fixture']['ticket'] == ticket and row['fixture']['verb'] == call['verb']
                         and same(row['fixture']['inputs'], call['inputs']))
            if row['phase'] != 'checking': need(row['fixture'] is not None and row['before'] is not None)
            if row['phase'] != 'checking':
                if surface == 'open': need(owned_page is None and not row['before']['tabletShown'])
                else: need(owned_page is not None and self.page(row['before']) == owned_page)
            packets = ([row['before']] if row['before'] is not None else [])
            for event_index, event in enumerate(row['intents']):
                exact(event, {'method', 'path', 'body', 'original'})
                need(event['method'] == 'POST' and re.fullmatch(r'/element/[A-Za-z0-9_.:%-]{1,480}/click', event['path'])
                     and event['body'] == {} or event['method'] == 'DELETE' and event['path'] == '/actions' and event['body'] is None)
                packets.append(event['original'])
                if surface == 'close' and version == 2:
                    self.close_intent(event, owned_page, row['intents'][:event_index])
            if row['after'] is not None: packets.append(row['after'])
            for packet in packets:
                self.packet(packet)
                if previous is not None: self.follow(previous, packet)
                previous = packet
            if row['phase'] == 'acknowledged':
                need(row['after'] is not None and row['intents'])
                if surface == 'open':
                    need(owned_page is None and row['page'] == self.page(row['after'])); owned_page = row['page']
                else:
                    need(owned_page is not None and row['page'] == owned_page
                         and not row['after']['tabletShown']); owned_page = None
            else: need(row['after'] is None and row['page'] is None)
        # Version one has no composite calls. Normalize only its explicit
        # surface label; retain every original clock, packet and input verb.
        if version == 1:
            for row in state['actions']: row['surface'] = row['call']['verb']
        return state

    def close_intent(self, event, owned_page, prior):
        packet = event['original']
        if packet['tabletShown']:
            need(self.page(packet) == owned_page)
        else:
            need(event['method'] == 'DELETE' and any(item['method'] == 'POST' for item in prior))

    def bound(self):
        self.admission.bound(); need(same(self.store.read(), self.previous))
        now = self.monotonic(); need(number(now, 0, 1e15) and (self.last_clock is None or now >= self.last_clock))
        self.last_clock = now
        if self.started is not None: need(now-self.started < 30)
        return now

    def save(self):
        self.bound(); value = self.envelope(self.state); self.decode(value)
        self.store.write(value, self.previous); need(same(self.store.read(), value)); self.previous = deepcopy(value); self.bound()

    def capture(self):
        self.bound(); value = self.native.capture(); self.packet(value); self.bound(); return value

    def directory(self, owner):
        """Join the first refresh to this actual ordinary open's originals.

        This is a historical join, never a fresh acquisition or an input ACK
        promoted to product facts. The complete failed observation remains
        responsible for validating its own image, fields and original window.
        """
        from ios.adapters.navigation_observation_owner import NavigationObservationOwner
        from ios.adapters.navigation_places_state import directory_proof
        from ios.adapters.navigation_product_state import ORIGINALS
        need(isinstance(owner, NavigationObservationOwner))
        self.bound(); self.decode(self.previous); owner.bound()
        need(same(self.envelope(self.state), self.previous)
             and same(owner.binding, self.binding) and owner.run == self.run
             and owner.lock.path == self.lock.path and owner.store.path.parent == self.store.path.parent)
        state = owner.state
        need(state is not None and state['phase'] in ('reading', 'observed', 'marker-pending') and state['phaseAfter'] is not None
             and state['clockJoin'] is not None
             and set(state['originals']) == ORIGINALS and same(owner.envelope(state), owner.previous))
        if state['phase'] == 'reading':
            need(not owner.historical and state['options']['directory'] is None); owner.interrupted()
        else:
            need(state['options']['directory'] is not None); owner.archive()
        rows = self.state['actions']
        need(rows and rows[0]['surface'] == 'open' and rows[0]['phase'] == 'acknowledged')
        opened = rows[0]
        need(opened['call']['verb'] == 'open' and opened['call']['ticket'] == state['ticket']
             and state['phaseBefore']['ticket'] == state['phaseAfter']['ticket'] == state['ticket']
             and state['phaseBefore']['verb'] == state['phaseAfter']['verb'] == 'open'
             and self.page(state['originals']['ui']) == opened['page'])
        initial = self.admission.archive()
        before = initial['originals']
        actual = state['originals']
        need(actual['http']['instance'] == before['http']['instance']
             and same(actual['http']['events'][:len(before['http']['events'])], before['http']['events'])
             and opened['before']['sampleEpochMs'] >= before['ui']['sampleEpochMs'])
        proof = directory_proof(self.binding, dict(http=actual['http'], model=actual['model'],
            provider=state['phaseAfter']['originals']['navigation']), dict(runId=self.run,
                ticket=state['ticket'], inputs=self.admission.fixture.inputs,
                origin=before['model']['preferences']['metaverseOrigin'],
                nativeAfterEpochMs=opened['before']['sampleEpochMs'],
                providerAfterEpochMs=opened['fixture']['originals']['navigation']['capturedEpochMs'],
                afterEvent=len(before['http']['events'])))
        if state['options']['directory'] is not None:need(same(proof, state['options']['directory']))
        self.bound(); owner.bound(); return proof

    def input_intent(self, method, path, body):
        self.bound(); row = self.state['actions'][-1]; need(row['phase'] == 'issued' and len(row['intents']) < 32)
        event = dict(method=method, path=path, body=deepcopy(body), original=self.capture())
        if row['surface'] == 'close':
            self.close_intent(event, self.state['actions'][-2]['page'], row['intents'])
        row['intents'].append(event); self.save()

    def act(self, call, *, surface=None):
        call = deepcopy(self.call(call)); surface = call['verb'] if surface is None else surface
        need(surface in SURFACES[call['verb']]); self.bound(); need(self.started is None); self.started = self.bound()
        try:
            if self.state is None: self.state = dict(component={}, actions=[])
            rows = self.state['actions']
            if rows:
                last = rows[-1]
                for prior in rows:
                    if prior['call']['ticket'] == call['ticket']: need(same(prior['call'], call))
                if (call['ticket'], surface) in [(row['call']['ticket'], row['surface']) for row in rows]:
                    need(last['phase'] == 'acknowledged' and last['surface'] == surface and same(last['call'], call)); self.decode(self.previous)
                    return {'performed': True}
                need(last['phase'] == 'acknowledged')
            need(len(rows) < 12 and (not rows or rows[-1]['surface'] != surface))
            row = dict(call=call, surface=surface, phase='checking', fixture=None, before=None, intents=[], after=None, page=None)
            rows.append(row); self.save()
            row['fixture'] = self.admission.fixture.read(); self.save()
            row['before'] = self.capture(); self.save()
            owned_page = rows[-2]['page'] if len(rows) > 1 and rows[-2]['surface'] == 'open' else None
            if surface == 'open': need(owned_page is None and not row['before']['tabletShown'])
            else: need(owned_page is not None and self.page(row['before']) == owned_page)
            row['phase'] = 'issued'; self.save()
            profile = dict(contractVersion=1, profile=PROFILE, sceneUrl=self.admission.fixture.inputs['sceneUrl'])
            flow = IOSNavigation(_SurfaceUI(self), self.native, profile, self.state['component'], self.save)
            if surface == 'open': flow.open_places()
            else: flow.invoke('places.close', {})
            final = self.capture()
            page = self.page(final) if surface == 'open' else owned_page
            if surface == 'close': need(not final['tabletShown'])
            row.update(phase='acknowledged', after=final, page=page); self.save()
            return {'performed': True}
        finally: self.started = None
