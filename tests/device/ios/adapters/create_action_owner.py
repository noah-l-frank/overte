"""Durable whole Create recipes and original normal Qt input ownership.

The channel persists the exact command UUID and original control reference
before delivery. Lost input may only be observed and cleaned up, never replayed.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_clock_join import digest
import re
import uuid

from adapters.native_feature_observation import exact, integer, need
from adapters.normal_feature_state import PrivateFeatureState, context
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack, unpack, same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import arguments, identifier
from ios.adapters import create_controls_v2 as controls
from ios.adapters.normal_input import NativeInput, observation as native_ui_packet

from ios.adapters.create_api_clock import check as api_check

VERSION = 2
READS = (1,2)


class CreateInputPending(NativeUIError):
    """An existing recipe/event has an unresolved actual outcome."""


def intent(value, pid):
    exact(value, {'reference', 'admission', 'controlId', 'action', 'value', 'command'})
    reference = controls.snapshot(value['reference']); scope = reference['scope']; command = value['command']
    admission = value['admission']; native_ui_packet(admission,pid,admission.get('sampleEpochMs'))
    controls.same_reference(reference,controls.project(admission),value['controlId'])
    need(scope['processId'] == pid and reference['open'] and reference['ready'])
    control, action, supplied = value['controlId'], value['action'], value['value']
    rows = [row for row in reference['controls'] if row['id'] == control]; need(len(rows) == 1)
    row = rows[0]; need(row['enabled'] and row.get('inputReady', True) and control != 'create.page')
    expected = dict(schemaVersion=1, commandId=command.get('commandId'), instance=scope['instance'],
                    sequence=scope['sequence']+1, observedElapsedMs=scope['elapsedMs'], fieldToken=row['token'], operation=action)
    need(type(expected['commandId']) is str and controls.base.nonce(expected['commandId']))
    if action == 'replace':
        need(controls.field(control) and row['focused']); controls.base.ascii_text(supplied); expected['text'] = supplied
    elif action == 'select-index':
        need(controls.choice(control) and integer(supplied, 0, row['count']-1)); expected['index'] = supplied
    elif action == 'scroll':
        need(control == 'create.scrollbar' and supplied in ('up', 'down')); expected['direction'] = supplied
    else: need(action == 'activate' and supplied is None and control != 'create.scrollbar')
    need(same(expected, command)); return value


def receipt(value, intended, pid):
    intent(intended, pid); command = intended['command']
    exact(value, {'schemaVersion', 'commandId', 'status'})
    need(type(value['schemaVersion']) is int and value['schemaVersion'] == 1 and type(value['commandId']) is str
         and re.fullmatch('ios-[a-f0-9]{32}',value['commandId']))
    status = value['status']; exact(status, {'schemaVersion', 'commandId', 'instance', 'sequence', 'performed', 'processId', 'sampleEpochMs'})
    need(type(status['schemaVersion']) is int and status['schemaVersion'] == 1 and status['performed'] is True
         and type(status['processId']) is int and status['processId'] == pid and status['commandId'] == command['commandId']
         and status['instance'] == command['instance'] and type(status['sequence']) is int and status['sequence'] == command['sequence']
         and integer(status['sampleEpochMs'],intended['admission']['sampleEpochMs']))
    return value


class CreateActionOwner:
    def __init__(self, store, lock, binding, run, fixture_url, guard):
        need(isinstance(store, PrivateFeatureState) and isinstance(lock, ScriptSourceLock) and callable(guard))
        self.store, self.lock, self.binding = store, lock, deepcopy(context(binding))
        self.run, self.fixture_url, self.guard = identifier(run), fixture_url, guard
        self.pid = int(binding['processIdentity']); need(self.pid > 0 and store.path.parent == lock.path.parent)
        self.previous = self.state = None

    def event_packet(self,event):
        return dict(iosCreateActionEventVersion=1,binding=self.binding,runId=self.run,fixtureUrl=self.fixture_url,
            owner=self.store.path.name,payload=pack([event]))

    def event_store(self,sha):
        need(type(sha) is str and re.fullmatch('[a-f0-9]{64}',sha))
        return PrivateFeatureState(self.store.path.with_name('ios-create-event-'+self.store.path.stem+'-'+sha+'.json'))

    def compact(self,state,*,retain=False):
        compact=deepcopy(state)
        for call in compact['calls']:
            references=[]
            for event in call['events']:
                packet=self.event_packet(event);sha=digest(packet);store=self.event_store(sha)
                if retain:
                    api_check();previous=store.read()
                    if previous is None:api_check();store.write(packet,None)
                    need(same(store.read(),packet))
                references.append(dict(sha256=sha))
            call['events']=references
        return compact

    def expand(self,state):
        expanded=deepcopy(state)
        for call in expanded['calls']:
            exact(call,{'arguments','phase','events'});need(type(call['events']) is list and len(call['events'])<=512)
            events=[]
            for reference in call['events']:
                exact(reference,{'sha256'});packet=self.event_store(reference['sha256']).read()
                need(packet is not None and digest(packet)==reference['sha256'])
                exact(packet,{'iosCreateActionEventVersion','binding','runId','fixtureUrl','owner','payload'})
                rows=unpack(packet['payload']);need(len(rows)==1 and same(packet,self.event_packet(rows[0])));events.append(rows[0])
            call['events']=events
        return expanded

    def envelope(self, state, *, version=VERSION,retain=False):
        need(type(version) is int and version in READS)
        stored=state if version==1 else self.compact(state,retain=retain)
        return dict(iosCreateActionOwnerVersion=version, binding=self.binding, runId=self.run,
                    fixtureUrl=self.fixture_url, payload=pack([stored]))

    def decode(self, value):
        exact(value, {'iosCreateActionOwnerVersion', 'binding', 'runId', 'fixtureUrl', 'payload'})
        version=value['iosCreateActionOwnerVersion'];need(type(version) is int and version in READS)
        entries = unpack(value['payload']); need(len(entries)==1)
        exact(entries[0],{'calls'});need(type(entries[0]['calls']) is list and len(entries[0]['calls'])<=128)
        state=entries[0] if version==1 else self.expand(entries[0])
        need(same(value,self.envelope(state,version=version)))
        exact(state, {'calls'}); need(type(state['calls']) is list and len(state['calls']) <= 128)
        tickets = set(); previous_scope = None
        for index, call in enumerate(state['calls']):
            exact(call, {'arguments', 'phase', 'events'}); query = call['arguments']
            if query.get('verb') == 'cleanup':
                exact(query, {'runId', 'ticket', 'fixtureUrl', 'verb', 'inputs'}); identifier(query['ticket']); need(query['inputs'] == {})
            else: arguments('feature.create.act', query)
            need(query['runId'] == self.run and query['fixtureUrl'] == self.fixture_url and query['ticket'] not in tickets
                 and call['phase'] in ('acting', 'acknowledged') and type(call['events']) is list and len(call['events']) <= 512)
            tickets.add(query['ticket'])
            if index < len(state['calls'])-1: need(call['phase'] == 'acknowledged')
            for event_index, event in enumerate(call['events']):
                exact(event, {'phase', 'intent', 'receipt', 'observed'}); intent(event['intent'], self.pid)
                need(event['phase'] in ('issued', 'acknowledged', 'observed'))
                scope = event['intent']['reference']['scope']
                if previous_scope is not None:
                    need(all(previous_scope[key] == scope[key] for key in ('instance', 'generation', 'processId'))
                         and scope['sequence'] == previous_scope['sequence'] and scope['elapsedMs'] >= previous_scope['elapsedMs'])
                if event['phase'] == 'issued': need(event['receipt'] is event['observed'] is None)
                else:
                    receipt(event['receipt'], event['intent'], self.pid)
                    if event['phase'] == 'observed':
                        observed = controls.snapshot(event['observed']); after = observed['scope']
                        need(all(scope[key] == after[key] for key in ('instance', 'generation', 'processId'))
                             and after['sequence'] == event['intent']['command']['sequence'] and after['elapsedMs'] >= scope['elapsedMs'])
                        previous_scope = after
                    else: need(event['observed'] is None)
                if event_index < len(call['events'])-1 or call['phase'] == 'acknowledged': need(event['phase'] == 'observed')
        return state

    def load(self):
        self.lock.assert_held(); need(self.guard() is not False)
        self.previous = self.store.read(); self.state = dict(calls=[]) if self.previous is None else self.decode(self.previous)
        return deepcopy(self.state)

    def bound(self):
        api_check();self.lock.assert_held(); need(self.guard() is not False and same(self.store.read(), self.previous))

    def save(self):
        self.bound(); value = self.envelope(self.state,retain=True); self.decode(value);api_check()
        self.store.write(value, self.previous); need(same(self.store.read(), value)); self.previous = deepcopy(value);api_check()

    def begin(self, query):
        self.bound(); need(self.state is not None)
        if any(call['arguments']['ticket'] == query['ticket'] for call in self.state['calls']):
            raise CreateInputPending('Create recipe already owns this ticket; observe its originals instead of repeating input')
        if self.state['calls'] and self.state['calls'][-1]['phase'] != 'acknowledged':
            raise CreateInputPending('Earlier Create recipe remains unresolved')
        self.state['calls'].append(dict(arguments=deepcopy(query), phase='acting', events=[])); self.save()

    def before(self, value):
        self.bound(); intent(value, self.pid); call = self.state['calls'][-1]
        need(call['phase'] == 'acting' and (not call['events'] or call['events'][-1]['phase'] == 'observed'))
        call['events'].append(dict(phase='issued', intent=deepcopy(value), receipt=None, observed=None)); self.save()

    def delivered(self, original):
        event = self.state['calls'][-1]['events'][-1]; need(event['phase'] == 'issued')
        receipt(original, event['intent'], self.pid); event.update(phase='acknowledged', receipt=deepcopy(original)); self.save()

    def capture(self, value):
        self.bound(); controls.snapshot(value)
        if self.state['calls'] and self.state['calls'][-1]['phase'] == 'acting' and self.state['calls'][-1]['events']:
            event = self.state['calls'][-1]['events'][-1]
            if event['phase'] == 'acknowledged': event.update(phase='observed', observed=deepcopy(value)); self.save()
        return value

    def finish(self):
        call = self.state['calls'][-1]; need(call['phase'] == 'acting' and all(event['phase'] == 'observed' for event in call['events']))
        call['phase'] = 'acknowledged'; self.save(); return {'performed': True}


class CreateBoundIO:
    """Original NativeInput channel with durable command admission at delivery."""
    def __init__(self, native, owner):
        need(isinstance(native, NativeInput) and isinstance(owner, CreateActionOwner)); self.native, self.owner = native, owner
        self.last_original = None
    def capture(self):
        raw = self.native.capture(); self.last_original = deepcopy(raw)
        return self.owner.capture(controls.project(raw))
    def input(self, identifier, action, reference, value=None):
        current = self.capture(); row = controls.same_reference(reference, current, identifier); scope = reference['scope']
        command = dict(schemaVersion=1, commandId=str(uuid.uuid4()), instance=scope['instance'], sequence=scope['sequence']+1,
                       observedElapsedMs=scope['elapsedMs'], fieldToken=row['token'], operation=action)
        if action == 'replace': command['text'] = value
        elif action == 'select-index': command['index'] = value
        elif action == 'scroll': command['direction'] = value
        intended = dict(reference=deepcopy(reference), admission=deepcopy(self.last_original),controlId=identifier, action=action, value=value, command=command)
        self.owner.before(intended)
        self.native.deliver(command,before_send=api_check)  # Exactly one delivery; exceptions preserve issued intent.
        self.owner.delivered(deepcopy(self.native.last_receipt)); return {'performed': True}
    def activate(self, identifier, *, reference): return self.input(identifier, 'activate', reference)
    def replace(self, identifier, value, *, reference): return self.input(identifier, 'replace', reference, value)
    def select_index(self, identifier, value, *, reference): return self.input(identifier, 'select-index', reference, value)
    def scroll(self, identifier, value, *, reference): return self.input(identifier, 'scroll', reference, value)
