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
from ios.adapters.navigation_observation_owner import fixture_original
from ios.adapters.normal_input import NativeInput, observation
from ios.adapters.normal_navigation import IOSNavigation, PROFILE
from ios.adapters import places_controls as controls

VERSION = 1


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
        need(isinstance(store, PrivateFeatureState) and isinstance(admission, NavigationAdmissionOwner)
             and not admission.historical and isinstance(ui, NativeUI) and isinstance(native, NativeInput)
             and callable(monotonic) and store.path.name == 'ios-navigation-surface-actions.json'
             and store.path.parent == admission.store.path.parent)
        self.store, self.admission, self.ui, self.native = store, admission, ui, native
        self.binding, self.run, self.lock = admission.binding, admission.run, admission.lock
        need(native.session == self.binding['sessionId'])
        self.monotonic = monotonic; self.started = self.last_clock = None
        self.lock.assert_held(); self.previous = store.read()
        self.state = None if self.previous is None else self.decode(self.previous)
        self.bound()

    def envelope(self, state):
        return dict(iosNavigationSurfaceActionsVersion=VERSION, binding=self.binding, runId=self.run, payload=pack([state]))

    def call(self, value):
        arguments('feature.world-navigation.act', value)
        need(value['runId'] == self.run and value['verb'] in ('open', 'close')
             and value['fixtureUrl'] == self.admission.fixture.fixture_url)
        return value

    def packet(self, value):
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
        need(type(value['iosNavigationSurfaceActionsVersion']) is int and value['iosNavigationSurfaceActionsVersion'] == VERSION
             and len(rows) == 1 and same(value, self.envelope(rows[0])))
        state = rows[0]; exact(state, {'component', 'actions'})
        need(type(state['component']) is dict and set(state['component']) <= {'iosNormalNavigation'}
             and type(state['actions']) is list and 1 <= len(state['actions']) <= 8)
        tickets = set(); previous = None; owned_page = None; previous_phase = None
        for index, row in enumerate(state['actions']):
            exact(row, {'call', 'phase', 'fixture', 'before', 'intents', 'after', 'page'})
            call = self.call(row['call']); ticket = call['ticket']
            need(ticket not in tickets); tickets.add(ticket)
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
            packets = ([row['before']] if row['before'] is not None else [])
            for event in row['intents']:
                exact(event, {'method', 'path', 'body', 'original'})
                need(event['method'] == 'POST' and re.fullmatch(r'/element/[A-Za-z0-9_.:%-]{1,480}/click', event['path'])
                     and event['body'] == {} or event['method'] == 'DELETE' and event['path'] == '/actions' and event['body'] is None)
                packets.append(event['original'])
            if row['after'] is not None: packets.append(row['after'])
            for packet in packets:
                self.packet(packet)
                if previous is not None: self.follow(previous, packet)
                previous = packet
            if row['phase'] == 'acknowledged':
                need(row['after'] is not None and row['intents'])
                if call['verb'] == 'open':
                    need(owned_page is None and row['page'] == self.page(row['after'])); owned_page = row['page']
                else:
                    need(owned_page is not None and row['page'] == owned_page
                         and not row['after']['tabletShown']); owned_page = None
            else: need(row['after'] is None and row['page'] is None)
        return state

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

    def input_intent(self, method, path, body):
        self.bound(); row = self.state['actions'][-1]; need(row['phase'] == 'issued' and len(row['intents']) < 32)
        row['intents'].append(dict(method=method, path=path, body=deepcopy(body), original=self.capture())); self.save()

    def act(self, call):
        call = deepcopy(self.call(call)); self.bound(); need(self.started is None); self.started = self.bound()
        try:
            if self.state is None: self.state = dict(component={}, actions=[])
            rows = self.state['actions']
            if rows:
                last = rows[-1]
                if call['ticket'] in [row['call']['ticket'] for row in rows]:
                    need(last['phase'] == 'acknowledged' and same(last['call'], call)); self.decode(self.previous)
                    return {'performed': True}
                need(last['phase'] == 'acknowledged')
            need(len(rows) < 8 and (not rows or rows[-1]['call']['verb'] != call['verb']))
            row = dict(call=call, phase='checking', fixture=None, before=None, intents=[], after=None, page=None)
            rows.append(row); self.save()
            row['fixture'] = self.admission.fixture.read(); self.save()
            row['before'] = self.capture(); self.save()
            owned_page = rows[-2]['page'] if len(rows) > 1 else None
            if call['verb'] == 'open': need(owned_page is None and not row['before']['tabletShown'])
            else: need(owned_page is not None and self.page(row['before']) == owned_page)
            row['phase'] = 'issued'; self.save()
            profile = dict(contractVersion=1, profile=PROFILE, sceneUrl=self.admission.fixture.inputs['sceneUrl'])
            flow = IOSNavigation(_SurfaceUI(self), self.native, profile, self.state['component'], self.save)
            if call['verb'] == 'open': flow.open_places()
            else: flow.invoke('places.close', {})
            final = self.capture()
            page = self.page(final) if call['verb'] == 'open' else owned_page
            if call['verb'] == 'close': need(not final['tabletShown'])
            row.update(phase='acknowledged', after=final, page=page); self.save()
            return {'performed': True}
        finally: self.started = None
