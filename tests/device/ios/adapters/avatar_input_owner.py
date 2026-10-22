"""Durable Avatar normal-event ownership, never feature effects or a verdict.

The native command UUID and complete original reference are persisted before
delivery. Uncertain events remain owned across reconstruction; no whole-action
replay, reissued pointer, new nonce or metadata deletion resolves them.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re

from adapters.native_feature_observation import exact, integer, need
from adapters.normal_feature_state import PrivateFeatureState, context
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack, unpack, same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import arguments, identifier
from ios.adapters import avatar_controls as controls

VERSION = 1


class AvatarInputPending(NativeUIError):
    """A retained event/unfinished action requires original resolution."""


def intent(value, pid):
    need(type(value) is dict)
    exact(value, {'controlId', 'action', 'reference', 'nativeCommand'} | ({'value'} if 'value' in value else set()))
    control, action, reference, query = (value[key] for key in ('controlId', 'action', 'reference', 'nativeCommand'))
    controls.snapshot(reference)
    need(controls.control_id(control) and control not in ('avatar.page', 'people.page')
         and action in ('activate', 'replace', 'set-value', 'select-index'))
    rows = [row for row in reference['controls'] if row['id'] == control]; need(len(rows) == 1)
    row, scope = rows[0], reference['scope']
    need(reference['open'] and reference['ready'] and row['enabled'] and row['inputReady'] and scope['processId'] == pid)
    expected = dict(schemaVersion=1, commandId=query.get('commandId'), instance=scope['instance'],
        sequence=scope['sequence']+1, observedElapsedMs=scope['elapsedMs'], fieldToken=row['token'], operation=action)
    need(controls.nonce(expected['commandId']))
    if action == 'replace':
        need(control in controls.FIELDS and row['focused']); controls.text(value.get('value'), 4096)
        expected['text'] = value['value']
    elif action == 'set-value':
        from adapters.native_feature_observation import number
        scale = value.get('value'); need(control == 'avatar.scale' and number(scale, .1, 4) and abs(scale*10-round(scale*10)) < .0001)
        expected['value'] = scale
    elif action == 'select-index':
        need(control == 'avatar.wearable-choice' and integer(value.get('value'), 0, len(row['choices'])-1))
        expected['index'] = value['value']
    else: need('value' not in value)
    need(same(query, expected)); return value


def delivery(value, original, pid):
    intent(original, pid); exact(value, {'command', 'originalReceipt'})
    need(same(value['command'], original['nativeCommand']))
    receipt = value['originalReceipt']; exact(receipt, {'schemaVersion', 'commandId', 'status'})
    need(type(receipt['schemaVersion']) is int and receipt['schemaVersion'] == 1 and type(receipt['commandId']) is str
         and re.fullmatch('ios-[a-f0-9]{32}', receipt['commandId']))
    status = receipt['status']; exact(status, {'schemaVersion', 'commandId', 'instance', 'sequence', 'performed', 'processId', 'sampleEpochMs'})
    query = value['command']
    need(type(status['schemaVersion']) is int and status['schemaVersion'] == 1 and status['performed'] is True
         and type(status['processId']) is int and status['processId'] == pid
         and status['commandId'] == query['commandId'] and status['instance'] == query['instance']
         and type(status['sequence']) is int and status['sequence'] == query['sequence']
         and integer(status['sampleEpochMs'], original['reference']['scope']['capturedEpochMs']))
    return value


def observed(value, original, acknowledged, pid):
    delivery(acknowledged, original, pid); controls.snapshot(value)
    before, after = original['reference']['scope'], value['scope']
    need(all(before[key] == after[key] for key in ('instance', 'generation', 'processId'))
         and after['sequence'] == original['nativeCommand']['sequence']
         and after['sourceSequence'] > before['sourceSequence'] and after['elapsedMs'] >= before['elapsedMs']
         and after['capturedEpochMs'] >= acknowledged['originalReceipt']['status']['sampleEpochMs'])
    return value


class AvatarInputOwner:
    VERSION_KEY='iosAvatarInputOwnerVersion'
    WRITER_VERSION=VERSION
    READ_VERSIONS=(VERSION,)
    STORE_SUFFIX='inputs'

    def call_arguments(self,value):return arguments('feature.avatar-people.act',value)
    def call_key(self,value):return value['ticket']

    def __init__(self, store, lock, binding, run, role, fixture_url, guard):
        need(isinstance(store, PrivateFeatureState) and isinstance(lock, ScriptSourceLock) and callable(guard)
             and role in ('primary', 'actor'))
        context(binding); identifier(run)
        need(type(binding['processIdentity']) is str and re.fullmatch('[1-9][0-9]*', binding['processIdentity']))
        self.store, self.lock, self.binding, self.run, self.role = store, lock, deepcopy(binding), run, role
        self.fixture_url, self.guard, self.pid = fixture_url, guard, int(binding['processIdentity'])
        need(store.path.name == 'ios-avatar-'+role+'-'+self.STORE_SUFFIX+'.json' and store.path.parent == lock.path.parent)
        self.previous = self.state = None
    def envelope(self, state,version=None):
        version=self.WRITER_VERSION if version is None else version
        return dict({self.VERSION_KEY:version}, binding=self.binding, runId=self.run, role=self.role,
                    fixtureUrl=self.fixture_url, payload=pack([state]))
    def decode(self, value):
        exact(value, {self.VERSION_KEY, 'binding', 'runId', 'role', 'fixtureUrl', 'payload'})
        rows = unpack(value['payload']); need(len(rows) == 1 and type(value[self.VERSION_KEY]) is int
            and value[self.VERSION_KEY] in self.READ_VERSIONS and same(value, self.envelope(rows[0],value[self.VERSION_KEY])))
        state = rows[0]; exact(state, {'phase', 'calls'})
        need(state['phase'] in ('ready', 'acting', 'acknowledged') and type(state['calls']) is list and len(state['calls']) <= 128)
        tickets = set(); last_scope = None
        for index, call in enumerate(state['calls']):
            exact(call, {'arguments', 'phase', 'events'})
            query = self.call_arguments(call['arguments'])
            need(query['runId'] == self.run and query['fixtureUrl'] == self.fixture_url and self.call_key(query) not in tickets
                 and call['phase'] in ('acting', 'acknowledged') and type(call['events']) is list and len(call['events']) <= 64)
            tickets.add(self.call_key(query))
            if index < len(state['calls'])-1: need(call['phase'] == 'acknowledged')
            for event_index, event in enumerate(call['events']):
                exact(event, {'phase', 'intent', 'delivery', 'observed'})
                need(event['phase'] in ('issued', 'acknowledged', 'observed')); intent(event['intent'], self.pid)
                scope = event['intent']['reference']['scope']
                if last_scope is not None:
                    need(all(last_scope[key] == scope[key] for key in ('instance', 'generation', 'processId'))
                         and scope['sequence'] >= last_scope['sequence'] and (event_index==0 or scope['sequence']==last_scope['sequence'])
                         and scope['sourceSequence'] > last_scope['sourceSequence']
                         and scope['capturedEpochMs'] >= last_scope['capturedEpochMs'])
                if event['phase'] == 'issued': need(event['delivery'] is event['observed'] is None)
                else:
                    delivery(event['delivery'], event['intent'], self.pid)
                    if event['phase'] == 'observed': observed(event['observed'], event['intent'], event['delivery'], self.pid)
                    else: need(event['observed'] is None)
                if event_index < len(call['events'])-1 or call['phase'] == 'acknowledged': need(event['phase'] == 'observed')
                if event['observed'] is not None: last_scope = event['observed']['scope']
            if call['phase'] == 'acknowledged': need(call['events'])
        need(state['phase'] == ('ready' if not state['calls'] else state['calls'][-1]['phase']))
        return state
    def bound(self):
        self.lock.assert_held(); need(self.guard() is not False and same(self.store.read(), self.previous))
    def load(self):
        self.lock.assert_held(); need(self.guard() is not False)
        self.previous = self.store.read(); self.state = dict(phase='ready', calls=[]) if self.previous is None else self.decode(self.previous)
        return deepcopy(self.state)
    def save(self):
        self.bound(); value = self.envelope(self.state); self.decode(value)
        self.store.write(value, self.previous); need(same(value, self.store.read())); self.previous = deepcopy(value)
    def begin(self, query):
        query = deepcopy(self.call_arguments(query))
        need(query['runId'] == self.run and query['fixtureUrl'] == self.fixture_url)
        self.load()
        for call in self.state['calls']:
            if self.call_key(call['arguments']) == self.call_key(query):
                need(same(call['arguments'], query))
                if call['phase'] == 'acknowledged': return False
                raise AvatarInputPending('Existing Avatar action remains owned; its input is not replayed')
        if self.state['phase'] == 'acting': raise AvatarInputPending('An earlier Avatar action remains unresolved')
        self.state['calls'].append(dict(arguments=query, phase='acting', events=[])); self.state['phase'] = 'acting'; self.save()
        return True
    def intent(self, value):
        self.bound(); intent(value, self.pid); need(self.state['phase'] == 'acting')
        events = self.state['calls'][-1]['events']
        if events and events[-1]['phase'] != 'observed': raise AvatarInputPending('Prior Avatar event is unresolved')
        events.append(dict(phase='issued', intent=deepcopy(value), delivery=None, observed=None)); self.save()
    def delivered(self, original, receipt):
        self.bound(); event = self.state['calls'][-1]['events'][-1]
        need(event['phase'] == 'issued' and same(event['intent'], original)); delivery(receipt, original, self.pid)
        event.update(phase='acknowledged', delivery=deepcopy(receipt)); self.save()
    def observed(self, original, value):
        self.bound(); event = self.state['calls'][-1]['events'][-1]
        need(event['phase'] == 'acknowledged' and same(event['intent'], original))
        observed(value, original, event['delivery'], self.pid)
        event.update(phase='observed', observed=deepcopy(value)); self.save()
    def finish(self):
        self.bound(); call = self.state['calls'][-1]
        need(call['phase'] == 'acting' and call['events'] and all(event['phase'] == 'observed' for event in call['events']))
        call['phase'] = self.state['phase'] = 'acknowledged'; self.save()
        return {'performed': True}
