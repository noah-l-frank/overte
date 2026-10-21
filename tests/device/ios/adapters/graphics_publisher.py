"""Durable independent Graphics publication with no uncertain POST redelivery.

Original observer frames and original server journal receipts stay historical.
Only a newly acquired role-owned frame can supply a new publication intent.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy

from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact, integer, need, number
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import pack, unpack, same
from feature_journeys.contract import identifier, result, state as feature_state
from feature_journeys.scenarios import SCENARIOS
from feature_journeys.witness import projection, WITNESS_KEYS
from feature_journeys.graphics_resources import validate_status
from ios.adapters.graphics_fixture import GraphicsPhasePending
from ios.adapters.graphics_observer import IOSGraphicsObserver

VERSION = 1
RECORD_VERSION = 2
RECORD_READS = (1, 2)


class IOSGraphicsPublisher:
    def __init__(self, observer):
        need(isinstance(observer, IOSGraphicsObserver) and observer.role == 'actor' and not observer.historical)
        self.observer, self.lock, self.source = observer, observer.lock, observer.source
        self.run, self.root, self.policy = observer.run, observer.root, observer.policy
        self.store = PrivateFeatureState(observer.store.path.with_name('ios-graphics-actor-publication.json'))
        self.previous = self.store.read(); self.bound()
        self.state = dict(records=[], pending=None) if self.previous is None else self.decode(self.previous)
        if self.previous is None:self.save()

    @classmethod
    def archive(cls,value,observer_value,**original_scope):
        """Validate retained publication receipts without a live app or SDK."""
        need(original_scope.get('role')=='actor')
        observer=IOSGraphicsObserver._archive_scope(observer_value,**original_scope)
        observer.current_binding=deepcopy(observer.state['binding'])
        scope=object.__new__(cls);scope.observer,scope.lock,scope.source=observer,observer.lock,observer.source
        scope.run,scope.root,scope.policy=observer.run,observer.root,observer.policy
        scope.store=PrivateFeatureState(observer.store.path.with_name('ios-graphics-actor-publication.json'))
        return deepcopy(scope.decode(value))

    def envelope(self, state):
        return dict(iosGraphicsPublisherVersion=VERSION, runId=self.run, fixtureUrl=self.source.client.url,
                    providerInstance=self.source.instance, artifactRoot=str(self.root), imagePolicy=self.policy, payload=pack([state]))

    def bound(self):
        self.lock.assert_held(); need(self.observer.guard() is not False and same(self.store.read(), self.previous))

    def save(self):
        self.bound(); value = self.envelope(self.state); self.decode(value)
        self.store.write(value, self.previous); need(same(self.store.read(), value)); self.previous = deepcopy(value)

    def record_store(self, ordinal):
        need(integer(ordinal, 1, 512))
        return PrivateFeatureState(self.root/('graphics-publication-'+self.run+'-actor-'+str(ordinal)+'.json'))

    def intent(self, value):
        exact(value, {'ordinal', 'observer', 'value', 'body', 'phase'})
        need(integer(value['ordinal'], 1, 512) and value['phase'] in ('planned', 'issued'))
        scope = IOSGraphicsObserver._archive_scope(value['observer'], path=self.observer.store.path,
            run=self.run, fixture_url=self.source.client.url, provider_instance=self.source.instance,
            role='actor', lock=self.lock, artifact_root=self.root, image_policy=self.policy)
        saved = scope.state; need(saved['phase'] == 'ready' and saved['last'] is not None)
        need(all(same(saved['binding'][k], self.observer.current_binding[k])
                 for k in saved['binding'] if k != 'processIdentity'))
        frame, _raw, actual, name = scope.frame(saved['last'], saved['binding'])
        public = result('feature.graphics.observe', value['value'])
        expected = dict(schemaVersion=1, contractVersion=public['contractVersion'], runId=self.run,
            sequence=saved['sequence'], capturedEpochMs=actual['capturedEpochMs'], state=actual['state'],
            resources=actual['resources'], lifecycle=actual['lifecycle'], artifacts=[dict(kind='image', name=name,
                sequence=saved['sequence'], capturedEpochMs=actual['capturedEpochMs'], ticket=frame['provider']['ticket'],
                source='world-render-target')])
        need(same(public, expected))
        body = dict(ticket=frame['provider']['ticket'], actor='owned-observer', actorSequence=public['sequence'],
                    capturedEpochMs=public['capturedEpochMs'], facts=projection('graphics', actual['state']))
        need(same(body, value['body'])); return saved

    def journal(self, value):
        exact(value, {'schemaVersion', 'runId', 'area', 'ticket', 'sampleEpochMs', 'entries'})
        need(type(value['schemaVersion']) is int and value['schemaVersion'] == 1
             and value['runId'] == self.run and value['area'] == 'graphics' and number(value['sampleEpochMs'], 1, 10**15)
             and type(value['entries']) is list and len(value['entries']) <= 512)
        identifier(value['ticket']); sequence = actor = 0
        for row in value['entries']:
            exact(row, {'ticket', 'actor', 'actorSequence', 'capturedEpochMs', 'facts', 'sequence', 'receivedEpochMs'})
            identifier(row['ticket']); exact(row['facts'], WITNESS_KEYS['graphics'])
            feature_state('graphics', dict(SCENARIOS['graphics']['baseline'], **row['facts']), self.run)
            need(integer(row['sequence'], sequence+1) and integer(row['actorSequence'], actor+1)
                 and row['actor'] == 'owned-observer' and number(row['capturedEpochMs'], 1, value['sampleEpochMs']+250)
                 and number(row['receivedEpochMs'], 1, value['sampleEpochMs'])
                 and -250 <= row['receivedEpochMs']-row['capturedEpochMs'] <= 1500)
            sequence, actor = row['sequence'], row['actorSequence']
        return value

    def receipt(self, row):
        if row.get('mode')=='run-retired':
            exact(row,{'intent','mode','runRetirement'})
            from ios.adapters.graphics_run_retirement import validate as retired
            saved=self.intent(row['intent']);closure=row['runRetirement']
            retired(closure,run=self.run,url=self.source.client.url,instance=self.source.instance)
            packet=closure['provider']
            validate_status(packet,instance=self.source.instance,run=self.run,url=self.source.client.url,
                request=packet['requestId'],previous=saved['backend'])
            need(any(a['ticket']==row['intent']['body']['ticket'] for a in closure['authorityAfter']['activations']))
            return row # Retired responsibility only; no publication outcome.
        exact(row, {'intent', 'journal', 'entry', 'mode', 'providerBefore', 'providerAfter', 'acquisition'})
        self.intent(row['intent']); journal = self.journal(row['journal']); body = row['intent']['body']
        before,after=row['providerBefore'],row['providerAfter']
        for packet in (before,after):
            validate_status(packet,instance=self.source.instance,run=self.run,url=self.source.client.url,request=packet['requestId'])
        validate_status(after,instance=self.source.instance,run=self.run,url=self.source.client.url,request=after['requestId'],previous=before)
        need(before['active'] and after['active'] and before['ticket']==journal['ticket']==after['ticket']
             and before['capturedEpochMs']<=journal['sampleEpochMs']<=after['capturedEpochMs'])
        acq=row['acquisition'];exact(acq,{'hostBeforeEpochMs','hostAfterEpochMs','hostBeforeMonotonic','hostAfterMonotonic'})
        left,right,start,end=[acq[k] for k in ('hostBeforeEpochMs','hostAfterEpochMs','hostBeforeMonotonic','hostAfterMonotonic')]
        need(number(left,1,10**15) and number(right,left,left+1500) and right-left<1500
             and number(start,0,10**15) and number(end,start,start+1.5) and end-start<1.5
             and abs(right-left-(end-start)*1000)<=250 and left-250<=before['capturedEpochMs']
             and after['capturedEpochMs']<=right+250 and right-before['capturedEpochMs']<1500)
        matches = [entry for entry in journal['entries'] if entry['actorSequence'] == body['actorSequence']]
        need(row['mode'] in ('published', 'phase-retired'))
        if row['mode'] == 'published':
            need(row['intent']['phase'] == 'issued')
            need(len(matches) == 1 and same(row['entry'], matches[0])
                 and same({k:row['entry'][k] for k in body}, body))
        else:need(not matches and row['entry'] is None and journal['ticket'] != body['ticket'])
        return row

    def load(self, reference):
        exact(reference, {'ordinal', 'sha256'}); value = self.record_store(reference['ordinal']).read()
        need(value is not None and digest(value) == reference['sha256'])
        exact(value, {'iosGraphicsPublicationRecordVersion', 'runId', 'fixtureUrl', 'providerInstance', 'payload'})
        need(type(value['iosGraphicsPublicationRecordVersion']) is int and value['iosGraphicsPublicationRecordVersion'] in RECORD_READS
             and value['runId'] == self.run and value['fixtureUrl'] == self.source.client.url and value['providerInstance'] == self.source.instance)
        rows = unpack(value['payload']); need(len(rows) == 1)
        need(rows[0].get('mode')!='run-retired' or value['iosGraphicsPublicationRecordVersion']>=2)
        row = self.receipt(rows[0]); need(row['intent']['ordinal'] == reference['ordinal']); return row

    def decode(self, value):
        exact(value, {'iosGraphicsPublisherVersion', 'runId', 'fixtureUrl', 'providerInstance', 'artifactRoot', 'imagePolicy', 'payload'})
        rows = unpack(value['payload']); need(len(rows) == 1 and type(value['iosGraphicsPublisherVersion']) is int
                                            and same(value, self.envelope(rows[0])))
        state = rows[0]; exact(state, {'records', 'pending'})
        need(type(state['records']) is list and len(state['records']) <= 512)
        previous = None
        for ordinal, ref in enumerate(state['records'], 1):
            need(type(ref.get('ordinal')) is int and ref['ordinal'] == ordinal)
            row = self.load(ref); current = row['intent']['value']
            if previous is not None:
                need(current['sequence'] > previous['sequence'] and current['capturedEpochMs'] >= previous['capturedEpochMs'])
            previous = current
        if state['pending'] is not None:
            self.intent(state['pending']); current = state['pending']['value']
            need(state['pending']['ordinal'] == len(state['records'])+1
                 and (previous is None or current['sequence'] > previous['sequence'] and current['capturedEpochMs'] >= previous['capturedEpochMs']))
        return state

    def store_record(self, row):
        self.receipt(row); ordinal = row['intent']['ordinal']
        value = dict(iosGraphicsPublicationRecordVersion=RECORD_VERSION, runId=self.run,
            fixtureUrl=self.source.client.url, providerInstance=self.source.instance, payload=pack([row]))
        store = self.record_store(ordinal); previous = store.read()
        if previous is None:store.write(value, None)
        else:need(same(previous, value))
        need(same(store.read(), value)); return dict(ordinal=ordinal, sha256=digest(value))

    def adopt(self, ref):
        row = self.load(ref); need(same(row['intent'], self.state['pending']))
        self.state['records'].append(deepcopy(ref)); self.state['pending'] = None; self.save()

    def retire_run(self):
        """Retire an uncertain POST after original authority deletion.

        Planned and issued intents retain their exact original values. No
        live journal, new capture, POST or claimed publication is supplied.
        """
        from ios.adapters.graphics_run_retirement import IOSGraphicsRunRetirement
        self.bound();pending=self.state['pending']
        if pending is None:return True
        value=self.record_store(pending['ordinal']).read()
        if value is not None:
            self.adopt(dict(ordinal=pending['ordinal'],sha256=digest(value)));return True
        closure=IOSGraphicsRunRetirement(self.source,monotonic=self.observer.monotonic).read();self.bound()
        ref=self.store_record(dict(intent=deepcopy(pending),mode='run-retired',runRetirement=closure))
        self.adopt(ref);return True

    def resolve(self):
        """Read original journal history; an uncertain POST is never sent again."""
        self.bound(); pending = self.state['pending']
        if pending is None:return True
        value = self.record_store(pending['ordinal']).read()
        if value is not None:
            self.adopt(dict(ordinal=pending['ordinal'], sha256=digest(value))); return True
        epoch,started=self.source.clock(),self.observer.monotonic()
        before=self.source.status(self.observer.state['backend'])
        if not before['active']:return self.retire_run()
        journal=deepcopy(self.source.client.observe());self.journal(journal);self.bound()
        after=self.source.status(before);self.bound();now,ended=self.source.clock(),self.observer.monotonic()
        need(number(epoch,1,10**15) and number(now,epoch,epoch+1500) and now-epoch<1500
             and number(started,0,10**15) and number(ended,started,started+1.5) and ended-started<1.5
             and abs(now-epoch-(ended-started)*1000)<=250 and -250<=now-journal['sampleEpochMs']<=1500)
        if before['ticket']!=journal['ticket'] or after['ticket']!=journal['ticket']:
            raise GraphicsPhasePending('Original Graphics publication lookup crossed a fixture phase')
        acq=dict(hostBeforeEpochMs=epoch,hostAfterEpochMs=now,hostBeforeMonotonic=started,hostAfterMonotonic=ended)
        body = pending['body']; matches = [r for r in journal['entries'] if r['actorSequence'] == body['actorSequence']]
        if pending['phase'] == 'planned' and journal['ticket'] == body['ticket']:
            need(not matches);return False
        if matches:
            need(pending['phase'] == 'issued')
            need(len(matches) == 1 and same({k:matches[0][k] for k in body}, body))
            mode, entry = 'published', matches[0]
        elif journal['ticket'] != body['ticket']:mode, entry = 'phase-retired', None
        else:raise GraphicsPhasePending('Original Graphics publication has an unresolved issued POST')
        ref = self.store_record(dict(intent=deepcopy(pending), journal=journal, entry=entry, mode=mode,
            providerBefore=before,providerAfter=after,acquisition=acq)); self.adopt(ref)
        return True

    def publish(self, stage):
        self.bound(); self.resolve()
        if self.state['pending'] is None:
            need(len(self.state['records']) < 512)
            value = self.observer.read(0, stage)
            frame = self.observer.frame(self.observer.state['last'], self.observer.state['binding'])[0]
            body = dict(ticket=frame['provider']['ticket'], actor='owned-observer', actorSequence=value['sequence'],
                        capturedEpochMs=value['capturedEpochMs'], facts=projection('graphics', value['state']))
            self.state['pending'] = dict(ordinal=len(self.state['records'])+1, observer=deepcopy(self.observer.previous),
                                       value=deepcopy(value), body=body, phase='planned'); self.save()
        pending = self.state['pending']; need(pending['phase'] == 'planned')
        self.intent(pending); active = self.source.read(self.observer.state['backend'])
        need(active['ticket'] == pending['body']['ticket'])
        frame = self.observer.frame(self.observer.state['last'], self.observer.state['binding'])[0]
        clock = frame['clockJoin']; now, epoch = self.observer.monotonic(), self.source.clock()
        need(same(self.observer.previous, pending['observer']) and stage == self.observer.state['stage']
             and clock['hostAfterMonotonic'] <= now and now-clock['hostBeforeMonotonic'] < 1.5
             and clock['hostAfterEpochMs'] <= epoch and epoch-clock['hostBeforeEpochMs'] < 1500
             and abs(epoch-clock['hostBeforeEpochMs']-(now-clock['hostBeforeMonotonic'])*1000) <= 250)
        # Persist before delivery. Losing this return leaves exactly one owned
        # issued POST; only a separately read original journal may resolve it.
        pending['phase'] = 'issued'; self.save(); self.bound()
        self.source.client.request('/runs/'+self.run+'/samples', deepcopy(pending['body']))
        self.bound(); sequence = pending['body']['actorSequence']; self.resolve(); self.bound(); return sequence
