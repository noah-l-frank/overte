"""Primary's read-only committed retirement join to an earlier admitted actor.

This reader consumes no actor feature facts and never sends a POST. Its caller
must release the primary source lock before waiting for the independent actor.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.phase_retirement_publisher import PhaseRetirementPublisher,PublicationPending
from adapters.script_feature.history import pack,unpack,same
from feature_journeys.phase_fixture import PhaseFixtureReader,validate as phase_packet
from feature_journeys.retirement_receipts import binding_from_context,summary as retirement_summary,stage as retirement_stage,SCENE_STAGE,WEB_SCENE_STAGE,WEB_SCENE_AREAS

VERSION=2
READS=(1,2,3)


class PhaseRetirementReader:
    def __init__(self,store,binding,phase,guard,admitted_original,validate_admission,*,epoch_ms=lambda:time.time()*1000,monotonic=time.monotonic,stage='complete'):
        need(isinstance(store,PrivateFeatureState) and isinstance(phase,PhaseFixtureReader) and phase.previous is not None
            and all(callable(fn) for fn in (guard,validate_admission,epoch_ms,monotonic)))
        self.store,self.binding,self.phase=store,deepcopy(context(binding)),phase
        self.guard,self.admitted_original,self.validate_admission=guard,deepcopy(admitted_original),validate_admission
        self.run,self.area,self.instance,self.url=phase.run,phase.area,phase.previous['instance'],phase.client.url
        self.epoch_ms,self.monotonic=epoch_ms,monotonic
        need(stage=='complete' or stage==SCENE_STAGE and self.area=='avatar-people' or stage==WEB_SCENE_STAGE and self.area in WEB_SCENE_AREAS);self.stage=stage
        self.previous=store.read();self.state=dict(records=[])
        self.actor=self.admission()
        if self.previous is not None:self.state=self.decode(self.previous)

    def admission(self):
        actual=self.validate_admission(deepcopy(self.admitted_original));exact(actual,{'runId','phaseInstance','binding'})
        actor=context(actual['binding']);need(actual['runId']==self.run and actual['phaseInstance']==self.instance
            and actor['targetFingerprint']!=self.binding['targetFingerprint'] and actor['sessionId']!=self.binding['sessionId']
            and all(actor[key]==self.binding[key] for key in ('artifactSha256','sourceRevision')))
        return binding_from_context(actor)

    def envelope(self,state,version=None):
        if version is None:version=max([3 if self.stage==WEB_SCENE_STAGE else VERSION]+[row['journal']['phaseRetirementJournalVersion'] for row in state['records']])
        value=dict(phaseRetirementReaderVersion=version,runId=self.run,area=self.area,phaseInstance=self.instance,
            fixtureUrl=self.url,binding=self.binding,admittedOriginal=self.admitted_original,payload=pack([state]))
        if version>=2:value['stage']=self.stage
        else:need(self.stage=='complete')
        return value

    def journal(self,value):
        checker=object.__new__(PhaseRetirementPublisher);checker.run,checker.area,checker.instance=self.run,self.area,self.instance
        return checker.journal(value)

    def record(self,value):
        exact(value,{'phaseBefore','journal','phaseAfter','acquisition','entry','sha256'})
        first,last=value['phaseBefore'],value['phaseAfter'];clock=PhaseRetirementPublisher.acquisition(value['acquisition'])
        phase_packet(first,run=self.run,area=self.area,request=first['requestId'],epoch=first['capturedEpochMs'])
        phase_packet(last,run=self.run,area=self.area,request=last['requestId'],epoch=last['capturedEpochMs'],previous=first)
        need(first['instance']==last['instance']==self.instance and first['active'] and last['active']
            and same(first['activations'],last['activations']) and first['activations']
            and first['activations'][-1]['stimulus']==dict(verb='cleanup',inputs={}))
        journal=self.journal(value['journal']);entry=value['entry']
        need(first['activations'][-1]['ticket']==journal['ticket']==entry['ticket']
            and first['activations'][-1]['activatedEpochMs']<=entry['quiet']['hostAfterFirstEpochMs']
            and first['capturedEpochMs']<=journal['sampleEpochMs']<=last['capturedEpochMs']
            and clock['hostBeforeEpochMs']-250<=first['capturedEpochMs']<=last['capturedEpochMs']<=clock['hostAfterEpochMs']+250
            and clock['hostAfterEpochMs']-first['capturedEpochMs']<1500 and entry in journal['entries']
            and same(entry,journal['entries'][-1]) and retirement_stage(entry)==self.stage and same(entry['binding'],self.actor)
            and value['sha256']==digest({key:item for key,item in value.items() if key!='sha256'}))
        return value

    def decode(self,value):
        need(type(value) is dict and type(value.get('phaseRetirementReaderVersion')) is int and value['phaseRetirementReaderVersion'] in READS)
        version=value['phaseRetirementReaderVersion']
        exact(value,{'phaseRetirementReaderVersion','runId','area','phaseInstance','fixtureUrl','binding','admittedOriginal','payload'}|({'stage'} if version>=2 else set()))
        rows=unpack(value['payload']);need(len(rows)==1 and same(value,self.envelope(rows[0],version)));state=rows[0];exact(state,{'records'})
        need(type(state['records']) is list and len(state['records'])<=128);before=None
        for row in state['records']:
            self.record(row);need(row['entry']['phaseRetirementVersion']<=version and row['journal']['phaseRetirementJournalVersion']<=version)
            if before is not None:
                a,b=before['entry'],row['entry'];need(b['actorSequence']>=a['actorSequence'])
                if b['actorSequence']==a['actorSequence']:need(same(a,b))
                phase_packet(row['phaseBefore'],run=self.run,area=self.area,request=row['phaseBefore']['requestId'],
                    epoch=row['phaseBefore']['capturedEpochMs'],previous=before['phaseAfter'])
            before=row
        return deepcopy(state)

    def read(self):
        need(self.guard() is not False and same(self.store.read(),self.previous) and same(self.admission(),self.actor)
            and len(self.state['records'])<128)
        epoch,started=self.epoch_ms(),self.monotonic();floor=self.state['records'][-1]['phaseAfter'] if self.state['records'] else None
        before=self.phase.status(floor);journal=self.phase.client.request('/runs/'+self.run+'/retirements');after=self.phase.status(before)
        self.journal(journal)
        if not journal['entries'] or retirement_stage(journal['entries'][-1])!=self.stage:
            raise PublicationPending('No independent committed retirement of the required stage is present')
        record=dict(phaseBefore=before,journal=journal,phaseAfter=after,acquisition=dict(hostBeforeEpochMs=epoch,hostAfterEpochMs=self.epoch_ms(),
            hostBeforeMonotonic=started,hostAfterMonotonic=self.monotonic()),entry=deepcopy(journal['entries'][-1]))
        record['sha256']=digest(record);self.record(record)
        need(number(self.epoch_ms(),record['acquisition']['hostAfterEpochMs'],1e15)
            and -250<=record['acquisition']['hostAfterEpochMs']-retirement_summary(record['entry'])['capturedEpochMs']<=1500
            and self.guard() is not False and same(self.admission(),self.actor) and same(self.store.read(),self.previous))
        self.state['records'].append(record);value=self.envelope(self.state);self.decode(value);self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value)
        end,mono=self.epoch_ms(),self.monotonic();need(number(end,record['acquisition']['hostAfterEpochMs'],1e15)
            and number(mono,record['acquisition']['hostAfterMonotonic'],started+1.5) and mono-started<1.5
            and max(end-retirement_summary(record['entry'])['capturedEpochMs'],epoch-retirement_summary(record['entry'])['capturedEpochMs']+(mono-started)*1000)<=1500)
        return deepcopy(record)
