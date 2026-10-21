"""Original selected Emote timer/callback/Rig/UI quiet-window ownership.

This owns diagnostic observations only. Whole fixture/image/actor retirement
and ordinary cleanup inputs remain the complete feature owner's obligations.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import time

from adapters.emote_rig_measurements import source as source_group
from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.native_script_work import NativeScriptWork,validate as work_packet,members
from adapters.normal_feature_state import PrivateFeatureState,context
from feature_journeys.phase_fixture import validate as phase_packet
from overte_phone_emote_sources import PhoneEmoteSources
from overte_phone_emote_originals import BLOCK,PhoneEmoteOriginals
from overte_phone_script_history import canonical,pack,unpack,same

VERSION=1
LIMIT=40


class PhoneEmoteLifetime:
    def __init__(self,source):
        need(isinstance(source,PhoneEmoteSources));source.lock.assert_held()
        self.source=source;self.store=PrivateFeatureState(source.store.path.with_name('phone-emote-'+source.role+'-lifetime.json'))
        self.previous=self.store.read();self.failed=False;self.started=self.clock=None
        self.state=dict(phase='ready',records=[],pending=None,window=None)
        self.originals=PhoneEmoteOriginals(source.artifact_root,source.binding,source.run,source.role,
            self.local_bound,lambda *_args:need(False),monotonic=source.monotonic)
        self.bound()
        if self.previous is not None:self.state=self.decode(self.previous)
        self.bound()

    def original(self,reference):
        exact(reference,{'revision','sha256'});need(integer(reference['revision'],1,len(self.source.frames)))
        index=reference['revision'];frame=self.source.frames[index-1]
        need(reference['sha256']==hashlib.sha256(canonical(frame)).hexdigest())
        entries=self.originals.manifest(self.source.state['manifests'][(index-1)//BLOCK])
        original=self.originals.read(self.originals.expand(entries[(index-1)%BLOCK]))
        need(same(original,frame));return frame

    @staticmethod
    def cleanup_phase(status,ticket=None):
        need(status['active'] and status['activations'])
        current=status['activations'][-1]
        need(current['stimulus']==dict(verb='cleanup',inputs={}) and (ticket is None or current['ticket']==ticket))
        return current['ticket']

    def validate_record(self,row,previous=None):
        exact(row,{'source','work','providerAfter','epochMs','hostEpochMs','monotonicMs'})
        need(integer(row['epochMs'],1) and number(row['hostEpochMs'],1,1e15) and number(row['monotonicMs'],0,1e15))
        frame=self.original(row['source']);selected,native,_urls=source_group(frame['group'],self.source.pid,frame['epochMs'])
        ticket=self.cleanup_phase(frame['phaseBefore']);self.cleanup_phase(frame['phaseAfter'],ticket)
        value=row['work'];need(type(value) is dict)
        request=dict(schemaVersion=1,commandId=value.get('requestId'),action='feature-script-work-observe',managerInstance=selected['engineInstance'])
        work_packet(value,request,self.source.pid,row['epochMs'],previous=previous['work'] if previous else None)
        actual=value['source'];manager=actual['manager']
        need(value['instance']==native['instance'] and value['requestedEpochMs']>=frame['widgets']['capturedEpochMs']
            and manager['url']==selected['assignedUrl'] and manager['loadGeneration']==selected['loadGeneration']
            and manager['assignedEpochMs']==selected['assignedEpochMs'] and same(actual['code'],selected['code']))
        # Match independently observed all-known membership without imposing an
        # array order absent from the native contract. No expected member IDs.
        before=frame['group']['script']['source']['membership'];after=members(actual)
        need(before['complete'] and before['revision']==after['revision']
            and {r['instance']:r for r in before['managers']}=={r['instance']:r for r in after['managers']})
        phase_packet(row['providerAfter'],run=self.source.run,area='emotes',request=row['providerAfter']['requestId'],
            epoch=row['hostEpochMs'],previous=frame['phaseAfter'])
        self.cleanup_phase(row['providerAfter'],ticket)
        need(frame['group']['rootsBefore']['requestedEpochMs']<=value['requestedEpochMs']<=value['capturedEpochMs']<=row['epochMs']
            and row['epochMs']-frame['group']['rootsBefore']['requestedEpochMs']<=1500)
        fresh(frame['phaseBefore']['capturedEpochMs'],row['hostEpochMs'])
        if previous is not None:
            old=self.original(previous['source']);self.cleanup_phase(old['phaseAfter'],ticket)
            need(row['source']['revision']>previous['source']['revision'] and row['monotonicMs']>=previous['monotonicMs']
                and row['epochMs']>=previous['epochMs'] and row['hostEpochMs']>=previous['hostEpochMs'])
        return row

    def quiet(self,row):
        frame=self.original(row['source']);work=row['work']['source']['work']
        return (frame['group']['native']['animation']['overrideActive'] is False
            and frame['ui']['open'] is False and not frame['ui']['controls']
            and not work['timers'] and work['signalCallbacks']==work['timerCallbacks']==0 and work['evaluating'] is False)

    def window(self,records):
        start=None;floor=None
        for index,row in enumerate(records):
            frame=self.original(row['source']);native=frame['group']['native']
            scope=dict(rig=native['animation']['rigId'],history=native['animation']['history']['instance'],
                calls=native['animation']['history']['callSequence'],override=native['animation']['history']['overrideSequence'],
                lifecycle=native['lifecycle'],input=frame['ui']['scope']['sequence'])
            if not self.quiet(row):start=floor=None;continue
            if start is None or not same(scope,floor):start=index;floor=scope
        if start is None:return None
        first,last=records[start],records[-1]
        if len(records)-start>=3 and last['monotonicMs']-first['monotonicMs']>=3000 \
                and last['work']['source']['work']['capturedEpochMs']-first['work']['source']['work']['capturedEpochMs']>=3000:
            return dict(first=start+1,last=len(records),elapsedMs=last['monotonicMs']-first['monotonicMs'])
        return None

    def decode(self,value):
        exact(value,{'emoteLifetimeVersion','runId','fixtureUrl','role','binding','artifactRoot','payload'})
        source=self.source
        need(type(value['emoteLifetimeVersion']) is int and value['emoteLifetimeVersion']==VERSION
            and value['runId']==source.run and value['fixtureUrl']==source.phase.fixture_url and value['role']==source.role
            and same(context(value['binding']),source.binding) and value['artifactRoot']==str(source.artifact_root))
        rows=unpack(value['payload']);need(len(rows)==1);state=rows[0]
        exact(state,{'phase','records','pending','window'})
        need(state['phase'] in ('ready','reading','complete') and type(state['records']) is list and len(state['records'])<=LIMIT)
        previous=None
        for row in state['records']:self.validate_record(row,previous);previous=row
        reader=NativeScriptWork(lambda *_:need(False),lambda:need(False),lambda:need(False),lambda:need(False),source.pid)
        reader.restore([row['work'] for row in state['records']])
        if state['phase']=='reading':
            exact(state['pending'],{'afterRevision','index'})
            need(integer(state['pending']['afterRevision'],0,len(source.frames)) and integer(state['pending']['index'],1,LIMIT)
                and state['pending']['index']==len(state['records'])+1)
        else:need(state['pending'] is None)
        need(same(state['window'],self.window(state['records'])) if state['phase']=='complete' else state['window'] is None)
        if state['phase']=='complete':need(state['window'] is not None)
        return deepcopy(state)

    def local_bound(self):
        source=self.source;source.lock.assert_held();need(not self.failed
            and same(self.store.read(),self.previous) and same(source.store.read(),source.previous)
            and (source.previous is None or same(unpack(source.previous['payload']),[source.state])))
        now=source.monotonic();need(number(now,0,1e15) and (self.clock is None or now>=self.clock)
            and (self.started is None or now-self.started<30));self.clock=now

    def bound(self):
        self.local_bound();need(self.source.guard() is not False);self.local_bound()

    def current(self):
        self.bound()
        if self.previous is None:need(same(self.state,dict(phase='ready',records=[],pending=None,window=None)))
        else:need(same(self.decode(self.previous),self.state))

    def save(self):
        try:
            self.bound();source=self.source
            value=dict(emoteLifetimeVersion=VERSION,runId=source.run,fixtureUrl=source.phase.fixture_url,role=source.role,
                binding=deepcopy(source.binding),artifactRoot=str(source.artifact_root),payload=pack([self.state]))
            self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value);self.bound()
        except Exception:
            self.failed=True
            raise

    def read(self):
        source=self.source;started=source.monotonic();self.current()
        need(self.state['phase'] in ('ready','complete') and len(self.state['records'])<LIMIT)
        self.state.update(phase='reading',pending=dict(afterRevision=len(source.frames),index=len(self.state['records'])+1),window=None);self.save()
        frame=source.read();ticket=self.cleanup_phase(frame['phaseBefore']);self.cleanup_phase(frame['phaseAfter'],ticket)
        selected,_native,_urls=source_group(frame['group'],source.pid,frame['epochMs'])
        host=source.phase.epoch_ms();host_clock=source.monotonic()
        reader=source.adapter._script_work(source.selector,read_only=True);need(isinstance(reader,NativeScriptWork) and reader.pid==source.pid and reader.ios is False)
        reader.restore([row['work'] for row in self.state['records']]);epoch=reader.clock_ms();epoch_clock=source.monotonic()
        work=reader.read(selected['engineInstance'],reader.last['sequence'] if reader.last else 0)
        status=source.phase.status(frame['phaseAfter']);self.bound()
        row=dict(source=dict(revision=len(source.frames),sha256=hashlib.sha256(canonical(frame)).hexdigest()),work=work,
            providerAfter=status,epochMs=reader.clock_ms(),hostEpochMs=source.phase.epoch_ms(),monotonicMs=source.monotonic()*1000)
        self.validate_record(row,self.state['records'][-1] if self.state['records'] else None);self.bound()
        self.state['records'].append(deepcopy(row));window=self.window(self.state['records'])
        self.state.update(phase='complete' if window else 'ready',pending=None,window=window);self.save()
        final_epoch=reader.clock_ms();final_host=source.phase.epoch_ms();self.bound();returned=deepcopy(row);final=source.monotonic()
        need(number(final,started,1e15) and final-started<5)
        floor=frame['group']['rootsBefore']['requestedEpochMs'];phase=frame['phaseBefore']['capturedEpochMs']
        fresh(floor,final_epoch);fresh(phase,final_host)
        need(max(final_epoch-floor,epoch-floor+(final-epoch_clock)*1000)<=1500
            and max(final_host-phase,host-phase+(final-host_clock)*1000)<=1500)
        return returned

    def wait(self,*,sleep=time.sleep):
        source=self.source
        need(callable(sleep));self.started=source.monotonic();self.bound()
        for attempt in range(32):
            self.read();self.bound()
            if self.state['phase']=='complete':return deepcopy(self.state['window'])
            if attempt==31:break
            sleep(.25);self.bound()
        need(False)

    def retire(self):
        self.started=self.source.monotonic();self.current();need(self.state['phase']=='complete')
        self.decode(self.previous);self.read();need(self.state['phase']=='complete');self.bound()
        self.store.discard(self.previous);need(self.store.read() is None)
