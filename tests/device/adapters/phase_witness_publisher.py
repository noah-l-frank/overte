"""Durable actor publication from independently validated historical originals.

The shared phase journal supplies input/authority metadata only. Retiring a
publication responsibility never establishes product or provider cleanup.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time

from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact, integer, need, number
from adapters.normal_feature_state import PrivateFeatureState, context
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack, unpack, same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier, result, state as feature_state
from feature_journeys.phase_fixture import PhaseFixtureReader, validate as phase_packet
from feature_journeys.scenarios import SCENARIOS
from feature_journeys.witness import projection, WITNESS_KEYS

VERSION = 1


class PublicationPending(NativeUIError):
    """An issued sample has no independently resolved journal receipt yet."""


class PhaseWitnessPublisher:
    @classmethod
    def archive(cls, value, *, store, binding, run, area, fixture_url, phase_instance, validate_original):
        """Validate retained records without an app, live authority or input."""
        need(isinstance(store, PrivateFeatureState) and area in SCENARIOS and callable(validate_original))
        scope = object.__new__(cls)
        scope.store, scope.binding, scope.run, scope.area = store, deepcopy(context(binding)), identifier(run), area
        scope.url, scope.instance, scope.validate_original = fixture_url, identifier(phase_instance), validate_original
        scope.live = False
        need(store.path.name == 'phase-publication-'+area+'-'+run+'-actor.json')
        return deepcopy(scope.decode(value))

    def __init__(self, store, binding, phase, lock, guard, validate_original, *,
                 epoch_ms=lambda: time.time()*1000, monotonic=time.monotonic):
        need(isinstance(store, PrivateFeatureState) and isinstance(phase, PhaseFixtureReader)
             and isinstance(lock, ScriptSourceLock) and phase.previous is not None
             and all(callable(fn) for fn in (guard, validate_original, epoch_ms, monotonic)))
        self.store, self.binding, self.phase, self.lock = store, deepcopy(context(binding)), phase, lock
        self.run, self.area, self.url = phase.run, phase.area, phase.client.url
        self.instance = identifier(phase.previous['instance'])
        phase_packet(phase.previous, run=self.run, area=self.area,
                     request=phase.previous['requestId'], epoch=phase.previous['capturedEpochMs'])
        self.guard, self.validate_original, self.epoch_ms, self.monotonic = guard, validate_original, epoch_ms, monotonic
        need(store.path.name == 'phase-publication-'+self.area+'-'+self.run+'-actor.json'
             and lock.path == store.path.parent/'script-feature-sources.lock')
        self.live = True; self.clock = None; lock.assert_held(); self.previous = store.read()
        if self.previous is None:
            need(not any(store.path.parent.glob('phase-publication-'+self.area+'-'+self.run+'-actor-*.json')))
        self.state = dict(records=[], pending=None) if self.previous is None else self.decode(self.previous)
        self.bound()
        if self.previous is None: self.save()

    def envelope(self, state):
        return dict(phaseWitnessPublisherVersion=VERSION, binding=self.binding, runId=self.run, area=self.area,
                    fixtureUrl=self.url, phaseInstance=self.instance, payload=pack([state]))

    def bound(self):
        self.lock.assert_held()
        need(self.guard() is not False and same(self.store.read(), self.previous)
             and self.phase.run == self.run and self.phase.area == self.area and self.phase.client.url == self.url
             and self.phase.previous is not None and self.phase.previous['instance'] == self.instance)
        now = self.monotonic(); need(number(now, 0, 1e15) and (self.clock is None or now >= self.clock))
        self.clock = now; return now

    def save(self):
        self.bound(); value = self.envelope(self.state); self.decode(value)
        self.store.write(value, self.previous); need(same(self.store.read(), value)); self.previous = deepcopy(value)

    @staticmethod
    def acquisition(value):
        exact(value, {'hostBeforeEpochMs', 'hostAfterEpochMs', 'hostBeforeMonotonic', 'hostAfterMonotonic'})
        a, b, c, d = [value[key] for key in ('hostBeforeEpochMs', 'hostAfterEpochMs', 'hostBeforeMonotonic', 'hostAfterMonotonic')]
        need(number(a, 1, 1e15) and number(b, a, a+1500) and b-a < 1500
             and number(c, 0, 1e15) and number(d, c, c+1.5) and d-c < 1.5
             and abs(b-a-(d-c)*1000) <= 250)
        return value

    def original(self, value):
        """The callback must validate source bytes/history without live reads."""
        need(type(value) is dict)
        derived = deepcopy(self.validate_original(deepcopy(value)))
        exact(derived, {'ticket', 'public', 'acquisition'}); identifier(derived['ticket'])
        public = result('feature.'+self.area+'.observe', derived['public'])
        need(public['runId'] == self.run)
        clock = self.acquisition(derived['acquisition'])
        need(number(public['capturedEpochMs'], clock['hostBeforeEpochMs'], clock['hostAfterEpochMs']))
        body = dict(ticket=derived['ticket'], actor='owned-observer', actorSequence=public['sequence'],
                    capturedEpochMs=public['capturedEpochMs'], facts=projection(self.area, public['state']))
        return derived, body

    def intent(self, value):
        exact(value, {'ordinal', 'original', 'derived', 'body', 'phase'})
        need(integer(value['ordinal'], 1, 512) and value['phase'] in ('planned', 'issued'))
        derived, body = self.original(value['original'])
        need(same(derived, value['derived']) and same(body, value['body'])); return value

    def phase_original(self, value, previous=None):
        phase_packet(value, run=self.run, area=self.area, request=value['requestId'],
                     epoch=value['capturedEpochMs'], previous=previous)
        need(value['instance'] == self.instance); return value

    def journal(self, value):
        exact(value, {'schemaVersion', 'runId', 'area', 'ticket', 'sampleEpochMs', 'entries'})
        need(type(value['schemaVersion']) is int and value['schemaVersion'] == 1
             and value['runId'] == self.run and value['area'] == self.area
             and number(value['sampleEpochMs'], 1, 1e15) and type(value['entries']) is list and len(value['entries']) <= 512)
        identifier(value['ticket']); sequence = actor = 0
        for row in value['entries']:
            exact(row, {'ticket', 'actor', 'actorSequence', 'capturedEpochMs', 'facts', 'sequence', 'receivedEpochMs'})
            identifier(row['ticket']); exact(row['facts'], WITNESS_KEYS[self.area])
            feature_state(self.area, dict(SCENARIOS[self.area]['baseline'], **row['facts']), self.run)
            need(integer(row['sequence'], sequence+1) and integer(row['actorSequence'], actor+1)
                 and row['actor'] == 'owned-observer' and number(row['capturedEpochMs'], 1, value['sampleEpochMs']+250)
                 and number(row['receivedEpochMs'], 1, value['sampleEpochMs'])
                 and -250 <= row['receivedEpochMs']-row['capturedEpochMs'] <= 1500)
            sequence, actor = row['sequence'], row['actorSequence']
        return value

    def receipt(self, row):
        exact(row, {'intent', 'phaseBefore', 'phaseAfter', 'acquisition', 'mode', 'journal', 'entry'})
        self.intent(row['intent']); body = row['intent']['body']; clock = self.acquisition(row['acquisition'])
        first = self.phase_original(row['phaseBefore']); last = self.phase_original(row['phaseAfter'], first)
        need(clock['hostBeforeEpochMs']-250 <= first['capturedEpochMs'] <= last['capturedEpochMs'] <= clock['hostAfterEpochMs']+250
             and clock['hostAfterEpochMs']-first['capturedEpochMs'] < 1500
             and same(first['activations'], last['activations']) and first['active'] == last['active']
             and any(item['ticket'] == body['ticket'] for item in last['activations']))
        if row['mode'] == 'run-retired':
            need(not first['active'] and not last['active'] and row['journal'] is row['entry'] is None)
            return row
        need(first['active'] and last['active'] and first['activations'] and last['activations'])
        journal = self.journal(row['journal'])
        need(first['activations'][-1]['ticket'] == journal['ticket'] == last['activations'][-1]['ticket']
             and first['capturedEpochMs'] <= journal['sampleEpochMs'] <= last['capturedEpochMs'])
        matches = [entry for entry in journal['entries'] if entry['actorSequence'] == body['actorSequence']]
        if row['mode'] == 'published':
            need(row['intent']['phase'] == 'issued' and len(matches) == 1 and same(row['entry'], matches[0])
                 and same({key:row['entry'][key] for key in body}, body)
                 and any(item['ticket'] == body['ticket'] and item['activatedEpochMs'] <= body['capturedEpochMs']
                         for item in last['activations']))
        else:
            need(row['mode'] == 'phase-retired' and not matches and row['entry'] is None and journal['ticket'] != body['ticket'])
        return row

    def record_store(self, ordinal):
        need(integer(ordinal, 1, 512))
        return PrivateFeatureState(self.store.path.parent/('phase-publication-'+self.area+'-'+self.run+'-actor-'+str(ordinal)+'.json'))

    def load(self, reference):
        exact(reference, {'ordinal', 'sha256'}); value = self.record_store(reference['ordinal']).read()
        need(value is not None and digest(value) == reference['sha256'])
        exact(value, {'phaseWitnessPublicationRecordVersion', 'binding', 'runId', 'area', 'fixtureUrl', 'phaseInstance', 'payload'})
        need(type(value['phaseWitnessPublicationRecordVersion']) is int and value['phaseWitnessPublicationRecordVersion'] == VERSION
             and same(value['binding'], self.binding) and (value['runId'], value['area'], value['fixtureUrl'], value['phaseInstance'])
             == (self.run, self.area, self.url, self.instance))
        rows = unpack(value['payload']); need(len(rows) == 1)
        row = self.receipt(rows[0]); need(row['intent']['ordinal'] == reference['ordinal']); return row

    def decode(self, value):
        exact(value, {'phaseWitnessPublisherVersion', 'binding', 'runId', 'area', 'fixtureUrl', 'phaseInstance', 'payload'})
        rows = unpack(value['payload']); need(len(rows) == 1 and type(value['phaseWitnessPublisherVersion']) is int
            and value['phaseWitnessPublisherVersion'] == VERSION and same(value, self.envelope(rows[0])))
        state = rows[0]; exact(state, {'records', 'pending'})
        need(type(state['records']) is list and len(state['records']) <= 512)
        previous = None; previous_phase = None
        for ordinal, ref in enumerate(state['records'], 1):
            need(ref.get('ordinal') == ordinal); row = self.load(ref); current = row['intent']['body']
            if previous is not None:
                need(current['actorSequence'] > previous['actorSequence'] and current['capturedEpochMs'] >= previous['capturedEpochMs'])
                self.phase_original(row['phaseBefore'], previous_phase)
            previous, previous_phase = current, row['phaseAfter']
        if state['pending'] is not None:
            pending = self.intent(state['pending']); current = pending['body']
            need(pending['ordinal'] == len(state['records'])+1
                 and (previous is None or current['actorSequence'] > previous['actorSequence']
                      and current['capturedEpochMs'] >= previous['capturedEpochMs']))
        elif self.live and len(state['records']) < 512:
            # A forgotten receipt is unresolved responsibility, not permission
            # to reuse its ordinal and send another sample.
            need(self.record_store(len(state['records'])+1).read() is None)
        return state

    def store_record(self, row):
        self.receipt(row); ordinal = row['intent']['ordinal']
        value = dict(phaseWitnessPublicationRecordVersion=VERSION, binding=self.binding, runId=self.run, area=self.area,
                     fixtureUrl=self.url, phaseInstance=self.instance, payload=pack([row]))
        store = self.record_store(ordinal); previous = store.read()
        if previous is None: store.write(value, None)
        else: need(same(previous, value))
        need(same(store.read(), value)); return dict(ordinal=ordinal, sha256=digest(value))

    def adopt(self, reference):
        row = self.load(reference); need(same(row['intent'], self.state['pending']))
        self.state['records'].append(deepcopy(reference)); self.state['pending'] = None; self.save()

    def resolve(self):
        """Read original receipts; never send an uncertain POST again."""
        self.bound(); pending = self.state['pending']
        if pending is None: return True
        retained = self.record_store(pending['ordinal']).read()
        if retained is not None:
            self.adopt(dict(ordinal=pending['ordinal'], sha256=digest(retained))); return True
        floor = self.load(self.state['records'][-1])['phaseAfter'] if self.state['records'] else None
        epoch, started = self.epoch_ms(), self.bound(); before = self.phase.status(floor)
        journal = self.phase.client.request('/runs/'+self.run) if before['active'] else None
        self.bound(); after = self.phase.status(before); self.bound()
        clock = dict(hostBeforeEpochMs=epoch, hostAfterEpochMs=self.epoch_ms(), hostBeforeMonotonic=started,
                     hostAfterMonotonic=self.monotonic())
        self.acquisition(clock); body = pending['body']
        if before['active'] != after['active'] or not same(before['activations'], after['activations']):
            raise PublicationPending('Original publication lookup crossed a fixture phase')
        if not before['active']: mode, entry = 'run-retired', None
        else:
            self.journal(journal)
            need(before['activations'] and after['activations'])
            if journal['ticket'] != before['activations'][-1]['ticket']: raise PublicationPending('Original journal crossed a fixture phase')
            matches = [entry for entry in journal['entries'] if entry['actorSequence'] == body['actorSequence']]
            if pending['phase'] == 'planned' and journal['ticket'] == body['ticket']:
                need(not matches); return False
            if matches:
                need(pending['phase'] == 'issued' and len(matches) == 1 and same({key:matches[0][key] for key in body}, body))
                mode, entry = 'published', matches[0]
            elif journal['ticket'] != body['ticket']: mode, entry = 'phase-retired', None
            else: raise PublicationPending('Original issued publication remains unresolved')
        reference = self.store_record(dict(intent=deepcopy(pending), phaseBefore=before, phaseAfter=after,
            acquisition=clock, mode=mode, journal=journal, entry=entry))
        self.adopt(reference); return True

    def publish(self, original):
        self.bound(); self.resolve(); derived, body = self.original(original)
        if self.state['pending'] is None:
            if self.state['records']:
                latest = self.load(self.state['records'][-1])
                if same(latest['intent']['original'], original):
                    need(latest['mode'] == 'published'); return latest['intent']['body']['actorSequence']
            need(len(self.state['records']) < 512)
            self.state['pending'] = dict(ordinal=len(self.state['records'])+1, original=deepcopy(original),
                derived=derived, body=body, phase='planned'); self.save()
        pending = self.intent(self.state['pending'])
        need(pending['phase'] == 'planned' and same(pending['original'], original))
        floor = self.load(self.state['records'][-1])['phaseAfter'] if self.state['records'] else None
        active = self.phase.read(floor); self.bound(); clock = pending['derived']['acquisition']
        now, epoch = self.monotonic(), self.epoch_ms()
        need(active['ticket'] == pending['body']['ticket']
             and active['afterEpochMs'] <= pending['body']['capturedEpochMs']
             and number(now, clock['hostAfterMonotonic'], clock['hostBeforeMonotonic']+1.5)
             and now-clock['hostBeforeMonotonic'] < 1.5
             and number(epoch, clock['hostAfterEpochMs'], clock['hostBeforeEpochMs']+1500)
             and epoch-clock['hostBeforeEpochMs'] < 1500
             and abs(epoch-clock['hostBeforeEpochMs']-(now-clock['hostBeforeMonotonic'])*1000) <= 250)
        pending['phase'] = 'issued'; self.save(); self.bound()
        # Durable intent storage is part of delivery time. A slow journal
        # cannot turn an expired original into a new actor publication.
        now, epoch = self.monotonic(), self.epoch_ms()
        need(number(now, clock['hostAfterMonotonic'], clock['hostBeforeMonotonic']+1.5)
             and now-clock['hostBeforeMonotonic'] < 1.5
             and number(epoch, clock['hostAfterEpochMs'], clock['hostBeforeEpochMs']+1500)
             and epoch-clock['hostBeforeEpochMs'] < 1500
             and abs(epoch-clock['hostBeforeEpochMs']-(now-clock['hostBeforeMonotonic'])*1000) <= 250)
        from adapters.original_publication_delivery import delivery
        with delivery(self,clock):
            self.phase.client.request('/runs/'+self.run+'/samples', deepcopy(pending['body']))
        self.bound(); sequence = pending['body']['actorSequence']; self.resolve(); return sequence
