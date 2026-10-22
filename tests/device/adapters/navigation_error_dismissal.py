"""Durable normal dismissal of an original owned native lookup error.

The parent owns the original Go To input, world state, source lock and whole
Navigation cleanup. This component never issues a lookup or changes a world.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
import time

from adapters.native_feature_observation import exact, integer, need, number
from adapters.native_navigation_replies import origin, validate as reply_packet, join_missing
from adapters.native_navigation_modals import validate as modal_packet, validate_continuation, presented, retired
from adapters.normal_feature_state import PrivateFeatureState, context
from adapters.normal_ui import NativeUIError
from adapters.token_create_ui import nonce, scope
from adapters.token_navigation_error_ui import TokenNavigationErrorUI
from feature_journeys.navigation_fixture import configuration, validate_status

VERSION = 2
LEGACY_FIELDS={'navigationErrorDismissalVersion','runId','binding','providerInstance','providerInputs','origin',
    'ticket','afterEpochMs','original','last','joined','phase','input','quiet','queries'}


class NavigationErrorDismissal:
    def __init__(self, ui_factory, replies, modals, status, path, run, binding, provider_instance, provider_inputs,
                 owned_origin, guard, *, monotonic=time.monotonic, sleep=time.sleep):
        need(all(callable(f) for f in (ui_factory, status, guard, monotonic, sleep))
             and type(run) is str and re.fullmatch('[0-9a-f]{32}', run)
             and type(provider_instance) is str and re.fullmatch('[0-9a-f]{32}', provider_instance))
        context(binding);configuration(provider_inputs);origin(owned_origin)
        need(provider_inputs['sourceRevision'] == binding['sourceRevision']
             and replies.pid == modals.pid == int(binding['processIdentity'].split(':', 1)[0]))
        self.replies, self.modals, self.status, self.run, self.binding = replies, modals, status, run, deepcopy(binding)
        self.provider_instance, self.inputs, self.origin = provider_instance, deepcopy(provider_inputs), owned_origin
        self.guard, self.monotonic, self.sleep = guard, monotonic, sleep
        self.last_clock = self.deadline = None
        self.store = PrivateFeatureState(path);self.disk = self.store.read();self.state = deepcopy(self.disk)
        if self.state is not None:
            version=self.state.get('navigationErrorDismissalVersion')
            need(type(version) is int and version in (1,2))
            if version==1:
                exact(self.state,LEGACY_FIELDS)
                self.state.update(navigationErrorDismissalVersion=VERSION,lookupTicket=self.state['ticket'])
            self.validate_state(self.state)
        self.ui = ui_factory(self.intent)
        need(isinstance(self.ui, TokenNavigationErrorUI) and self.ui.run == run)

    def now(self):
        need(self.guard() is not False)
        value = self.monotonic()
        need(number(value, 0, 1e15) and (self.last_clock is None or value >= self.last_clock)
             and (self.deadline is None or value <= self.deadline))
        self.last_clock = value
        return value

    def save(self, value):
        self.validate_state(value)
        self.store.write(value, self.disk);self.disk = deepcopy(value);self.state = deepcopy(value)

    def archive_group(self, value):
        exact(value, {'reply', 'modal', 'provider'})
        pid = int(self.binding['processIdentity'].split(':', 1)[0])
        for kind, validator, action in (('reply', reply_packet, 'feature-navigation-replies'),
                                        ('modal', modal_packet, 'feature-navigation-modals')):
            packet = value[kind]
            need(type(packet) is dict)
            request = dict(schemaVersion=1, commandId=packet.get('commandId'), action=action, runId=self.run)
            # Historical originals keep their timestamps; no live currentness
            # is inferred from validating retained evidence at its own epoch.
            validator(packet, request, pid, packet.get('capturedEpochMs'))
        need(value['reply']['navigationReplyVersion']==2)
        validate_status(value['provider'], instance=self.provider_instance, run=self.run, inputs=self.inputs)
        need(value['modal']['uiBridgeId'] == self.binding['sessionId'])

    def continuation(self, old, new):
        a, b = old['reply'], new['reply']
        need(a['instance'] == b['instance'] and a['processId'] == b['processId'] and b['sequence'] > a['sequence']
             and b['capturedEpochMs'] >= a['capturedEpochMs'] and b['currentLookupGeneration'] >= a['currentLookupGeneration']
             and b['events'][:len(a['events'])] == a['events'])
        validate_continuation(old['modal'], new['modal'])
        validate_status(new['provider'], instance=self.provider_instance, run=self.run, inputs=self.inputs, previous=old['provider'])

    def join(self, group, ticket, after_epoch):
        return join_missing(group['reply'],group['provider'],ticket,after_epoch,self.origin)

    def validate_state(self, value):
        exact(value, LEGACY_FIELDS|{'lookupTicket'})
        need(type(value['navigationErrorDismissalVersion']) is int and value['navigationErrorDismissalVersion'] == VERSION
             and value['runId'] == self.run and value['binding'] == self.binding
             and value['providerInstance'] == self.provider_instance and value['providerInputs'] == self.inputs and value['origin'] == self.origin
             and all(type(value[k]) is str and re.fullmatch('[0-9a-f]{32}', value[k]) for k in ('ticket','lookupTicket'))
             and integer(value['afterEpochMs'], 1)
             and value['phase'] in ('ready', 'pending', 'quiet', 'complete')
             and type(value['queries']) is list and 2 <= len(value['queries']) <= 512
             and all(type(v) is str and re.fullmatch('[0-9a-f]{32}', v) for v in value['queries'])
             and len(set(value['queries'])) == len(value['queries']))
        self.archive_group(value['original']);self.archive_group(value['last'])
        if value['last'] != value['original']:
            self.continuation(value['original'], value['last'])
        need(value['joined'] == self.join(value['original'], value['lookupTicket'], value['afterEpochMs']))
        need(value['original']['provider']['active'] and value['original']['provider']['ticket']==value['ticket']
             and value['original']['reply']['currentLookupActive']
             and value['original']['reply']['currentLookupGeneration']==value['joined']['event']['lookupGeneration'])
        original_modal = presented(value['original']['modal'], value['joined']['event'])
        need(all(value['original'][kind]['commandId'] in value['queries'] and value['last'][kind]['commandId'] in value['queries']
                 for kind in ('reply', 'modal')))
        if value['input'] is None:
            need(value['phase'] == 'ready')
        else:
            input_value = value['input']
            exact(input_value, {'navigationErrorInputVersion', 'action', 'controlId', 'controlToken', 'scope', 'modalId', 'eventId'})
            need(type(input_value['navigationErrorInputVersion']) is int and input_value['navigationErrorInputVersion'] == 1
                 and input_value['action'] == 'activate' and nonce(input_value['controlToken'])
                 and input_value['modalId'] == original_modal['modalId']
                 and input_value['controlId'] == 'navigation.error.ok.' + original_modal['modalId']
                 and input_value['eventId'] == value['joined']['event']['eventId'])
            scope(input_value['scope'])
            need(input_value['scope']['instance'] == self.binding['sessionId']
                 and input_value['scope']['processId'] == value['original']['modal']['processId']
                 and input_value['scope']['generation'] == value['original']['modal']['uiGeneration']
                 and input_value['scope']['sequence'] == value['original']['modal']['uiInputSequence'])
        need(type(value['quiet']) is list and len(value['quiet']) <= 8)
        if value['phase'] == 'complete':
            need(3 <= len(value['quiet']) <= 8)
        else:
            need(not value['quiet'])
        previous = None
        for group in value['quiet']:
            self.archive_group(group);self.effect(group, value)
            need(group['provider']['active'] and group['provider']['ticket'] == value['ticket']
                 and group['reply']['currentLookupActive']
                 and group['reply']['currentLookupGeneration'] == value['joined']['event']['lookupGeneration']
                 and self.join(group, value['lookupTicket'], value['afterEpochMs']) == value['joined'])
            if previous is not None:
                self.continuation(previous, group)
                need(0 <= group['modal']['capturedEpochMs'] - previous['modal']['capturedEpochMs'] <= 1500)
            previous = group
        if value['quiet']:
            first, last = value['quiet'][0]['modal'], value['quiet'][-1]['modal']
            need(last['capturedEpochMs'] - first['capturedEpochMs'] >= 3000
                 and last['uiEpochMs'] - first['uiEpochMs'] >= 3000 and last['uiElapsedMs'] - first['uiElapsedMs'] >= 3000)

    def intent(self, value):
        self.now()
        need(self.state is not None and self.state['phase'] == 'ready' and self.state['input'] is None)
        current = deepcopy(self.state);current['input'] = value;current['phase'] = 'pending';self.save(current)

    def sample(self, *, initial=False):
        self.now()
        provider = self.status()
        validate_status(provider, instance=self.provider_instance, run=self.run, inputs=self.inputs,
                        previous=None if self.state is None else self.state['last']['provider'])
        group = dict(provider=provider, reply=self.replies.read(self.run), modal=self.modals.read(self.run))
        self.now();self.archive_group(group)
        if self.state is not None:
            self.continuation(self.state['last'], group)
            identifiers = [group[kind]['commandId'] for kind in ('reply', 'modal')]
            need(len(set(identifiers)) == 2 and all(v not in self.state['queries'] for v in identifiers)
                 and len(self.state['queries']) <= 510)
            current = deepcopy(self.state);current['last'] = group;current['queries'] += identifiers;self.save(current)
        return group

    def current(self, group):
        need(group['provider']['active'] and group['provider']['ticket'] == self.state['ticket']
             and group['reply']['currentLookupActive']
             and group['reply']['currentLookupGeneration'] == self.state['joined']['event']['lookupGeneration']
             and self.join(group, self.state['lookupTicket'], self.state['afterEpochMs']) == self.state['joined'])

    def effect(self, group, state=None):
        state = self.state if state is None else state
        need(state['input'] is not None)
        row = retired(group['modal'], state['joined']['event'])
        old = state['input']['scope'];current = group['modal']
        need(row['modalId'] == state['input']['modalId'] and current['uiBridgeId'] == old['instance']
             and current['uiGeneration'] == old['generation'] and current['uiInputSequence'] == old['sequence'] + 1)
        return True

    def act(self, ticket, after_epoch, *, lookup_ticket=None):
        need(self.deadline is None and type(ticket) is str and re.fullmatch('[0-9a-f]{32}', ticket) and integer(after_epoch, 1))
        lookup_ticket=ticket if lookup_ticket is None else lookup_ticket
        need(type(lookup_ticket) is str and re.fullmatch('[0-9a-f]{32}',lookup_ticket))
        self.deadline = self.now() + 20
        try:
            result=self.execute(ticket, after_epoch, lookup_ticket);self.now();return result
        except NativeUIError:
            raise
        except Exception:
            raise NativeUIError('Original lookup modal operation remains unresolved') from None
        finally:
            self.deadline = None

    def execute(self, ticket, after_epoch, lookup_ticket):
        if self.state is None:
            group = self.sample(initial=True)
            joined = self.join(group, lookup_ticket, after_epoch)
            presented(group['modal'], joined['event'])
            need(group['provider']['active'] and group['provider']['ticket'] == ticket
                 and group['reply']['currentLookupActive'] and group['reply']['currentLookupGeneration'] == joined['event']['lookupGeneration'])
            self.save(dict(navigationErrorDismissalVersion=VERSION, runId=self.run, binding=self.binding,
                providerInstance=self.provider_instance, providerInputs=self.inputs, origin=self.origin, ticket=ticket, lookupTicket=lookup_ticket, afterEpochMs=after_epoch,
                original=group, last=group, joined=joined, phase='ready', input=None, quiet=[],
                queries=[group[kind]['commandId'] for kind in ('reply', 'modal')]))
        need(self.state['ticket'] == ticket and self.state['lookupTicket']==lookup_ticket and self.state['afterEpochMs'] == after_epoch)
        if self.state['phase'] == 'complete':
            group=self.sample();self.current(group);self.effect(group);return dict(performed=True)
        group = self.sample();self.current(group)
        if self.state['phase'] == 'ready':
            self.ui.dismiss(group['modal'], self.state['joined']['event'])
        need(self.state['input'] is not None)
        for attempt in range(81):
            group = self.sample();self.current(group)
            before = self.state['input']['scope']['sequence']
            need(before <= group['modal']['uiInputSequence'] <= before + 1)
            rows = [r for r in group['modal']['records'] if r['modalId'] == self.state['input']['modalId']]
            need(len(rows) == 1);row = rows[0]
            if row['callbackFinished'] and not row['rootAlive'] and not row['listenerAlive']:
                self.effect(group);break
            need(attempt < 80);self.sleep(.25)
        current = deepcopy(self.state);current['phase'] = 'quiet';self.save(current)
        start = self.now();groups = []
        for _ in range(8):
            group = self.sample();self.current(group);self.effect(group)
            if groups:
                need(group['modal']['records'] == groups[-1]['modal']['records']
                     and 0 <= group['modal']['capturedEpochMs'] - groups[-1]['modal']['capturedEpochMs'] <= 1500)
            groups.append(group)
            first, last = groups[0]['modal'], groups[-1]['modal']
            if self.now() - start >= 3 and last['capturedEpochMs'] - first['capturedEpochMs'] >= 3000:
                need(last['uiEpochMs'] - first['uiEpochMs'] >= 3000 and last['uiElapsedMs'] - first['uiElapsedMs'] >= 3000)
                current = deepcopy(self.state);current['quiet'] = groups;current['phase'] = 'complete';self.save(current)
                return dict(performed=True)
            self.sleep(.5)
        raise NativeUIError('Original lookup modal retirement remains unresolved')
