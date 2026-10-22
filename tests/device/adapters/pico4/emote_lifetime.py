"""Owned Pico cleanup work observations; journals remain until whole retirement."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import time
from adapters.emote_rig_measurements import source as source_group
from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.native_script_work import NativeScriptWork,validate as work_packet,members,scope as work_scope
from adapters.native_script_compilations import accept as compiled_accept
from adapters.normal_feature_state import PrivateFeatureState,context
from feature_journeys.phase_fixture import validate as phase_packet
from adapters.pico4.emote_sources import PicoEmoteSources
from adapters.emote_originals import BLOCK,EmoteOriginals
from adapters.script_journey.history import canonical,pack,unpack,same

VERSION=1
LIMIT=40


class PicoEmoteLifetime:
    def __init__(self,source,work_reader):
        need(isinstance(source,PicoEmoteSources) and not source.historical and callable(work_reader));source.lock.assert_held()
        self.work_reader=work_reader
        self.source=source;self.store=PrivateFeatureState(source.store.path.with_name(source.store.path.stem+'-lifetime.json'))
        self.previous=self.store.read();self.failed=False;self.started=self.clock=None
        self.state=dict(phase='ready',records=[],pending=None,window=None)
        self.originals=EmoteOriginals(source.artifact_root,source.binding,source.run,source.role,
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
        frame=self.original(row['source'])
        ticket=self.cleanup_phase(frame['phaseBefore']);self.cleanup_phase(frame['phaseAfter'],ticket)
        value=row['work'];self.validate_work(frame,value,row['epochMs'],previous['work'] if previous else None)
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


    def validate_work(self,frame,value,epoch,previous=None):
        need(type(value) is dict)
        selected,native,_urls=source_group(frame['group'],self.source.pid,frame['epochMs'])
        request=dict(schemaVersion=1,commandId=value.get('requestId'),action='feature-script-work-observe',managerInstance=selected['engineInstance'])
        work_packet(value,request,self.source.pid,epoch,previous=previous)
        actual=value['source'];manager=actual['manager']
        need(value['instance']==native['instance'] and value['requestedEpochMs']>=PicoEmoteSources.ui(frame)['scope']['capturedEpochMs']
            and manager['url']==selected['assignedUrl'] and manager['loadGeneration']==selected['loadGeneration']
            and manager['assignedEpochMs']==selected['assignedEpochMs'] and same(actual['code'],selected['code']))
        if 'compilation' in selected:
            need(actual['work']['scriptWorkVersion']==2)
            engine=next(row for row in frame['group']['script']['source']['engines'] if row['required']['instance']==selected['engineInstance'])
            compiled_accept(engine['compiled'],actual['compiled'],epoch);work_scope(value,selected['compilation'])
        else:need(actual['work']['scriptWorkVersion']==1)
        # Match independently observed all-known membership without imposing an
        # array order absent from the native contract. No expected member IDs.
        before=frame['group']['script']['source']['membership'];after=members(actual)
        need(before['complete'] and before['revision']==after['revision']
            and {r['instance']:r for r in before['managers']}=={r['instance']:r for r in after['managers']})


    def quiet(self,row):return self.quiet_frame(self.original(row['source']),row['work'])


    def quiet_frame(self,frame,value):
        work=value['source']['work']
        selected,_native,_urls=source_group(frame['group'],self.source.pid,frame['epochMs'])
        if 'compilation' in selected:
            actual=work_scope(value,selected['compilation'])
            return (frame['group']['native']['animation']['overrideActive'] is False
                and PicoEmoteSources.ui(frame)['open'] is False and not PicoEmoteSources.ui(frame)['controls']
                and not actual['timers'] and not actual['unknownTimers'] and actual['evaluating'] is False
                and actual['signalCallbacks']==actual['timerCallbacks']==actual['unknownSignalCallbacks']==actual['unknownTimerCallbacks']==0)
        return (frame['group']['native']['animation']['overrideActive'] is False
            and PicoEmoteSources.ui(frame)['open'] is False and not PicoEmoteSources.ui(frame)['controls']
            and not work['timers'] and work['signalCallbacks']==work['timerCallbacks']==0 and work['evaluating'] is False)


    def activity(self,row):return self.activity_frame(self.original(row['source']),row['work'])


    def activity_frame(self,frame,value):
        selected,_native,_urls=source_group(frame['group'],self.source.pid,frame['epochMs'])
        if 'compilation' not in selected:return None
        actual=work_scope(value,selected['compilation'])
        return dict(selected=[actual[key] for key in ('signalInvocations','timerInvocations','timerRegistrations')],
            unknown=[[item['scriptId']]+[item[key] for key in ('signalInvocations','timerInvocations','timerRegistrations')]
                for item in actual['unknownActivity']])


    def window(self,records):
        start=None;floor=None;previous=None
        def clocks(row):
            frame=self.original(row['source'])
            return (row['monotonicMs'],row['epochMs'],row['hostEpochMs'],
                row['work']['source']['work']['capturedEpochMs'],
                frame['group']['native']['capturedEpochMs'],PicoEmoteSources.ui(frame)['scope']['elapsedMs'])
        for index,row in enumerate(records):
            frame=self.original(row['source']);native=frame['group']['native']
            scope=dict(rig=native['animation']['rigId'],history=native['animation']['history']['instance'],
                calls=native['animation']['history']['callSequence'],override=native['animation']['history']['overrideSequence'],
                lifecycle=native['lifecycle'],input=PicoEmoteSources.ui(frame)['scope']['sequence'],activity=self.activity(row))
            current=clocks(row)
            continuous=previous is None or all(0<=new-old<=1500 for old,new in zip(previous,current))
            previous=current
            if not self.quiet(row):start=floor=None;continue
            if start is None or not continuous or not same(scope,floor):start=index;floor=scope
        if start is None:return None
        first,last=records[start],records[-1]
        if len(records)-start>=3 and all(end-begin>=3000 for begin,end in zip(clocks(first),clocks(last))):
            return dict(first=start+1,last=len(records),elapsedMs=last['monotonicMs']-first['monotonicMs'])
        return None

    def decode(self,value):
        exact(value,{'picoEmoteLifetimeVersion','runId','fixtureUrl','role','binding','artifactRoot','payload'})
        source=self.source
        need(type(value['picoEmoteLifetimeVersion']) is int and value['picoEmoteLifetimeVersion']==VERSION
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
            value=dict(picoEmoteLifetimeVersion=VERSION,runId=source.run,fixtureUrl=source.phase.fixture_url,role=source.role,
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
        reader=self.work_reader();need(isinstance(reader,NativeScriptWork) and reader.pid==source.pid and reader.ios is False)
        reader.restore([row['work'] for row in self.state['records']]);epoch=reader.clock_ms();epoch_clock=source.monotonic()
        work=reader.read(selected['engineInstance'],reader.last['sequence'] if reader.last else 0)
        status=source.phase.status(frame['phaseAfter']);self.bound()
        row=dict(source=dict(revision=len(source.frames),sha256=hashlib.sha256(canonical(frame)).hexdigest()),work=work,
            providerAfter=status,epochMs=reader.clock_ms(),hostEpochMs=source.phase.epoch_ms(),monotonicMs=source.monotonic()*1000)
        self.validate_record(row,self.state['records'][-1] if self.state['records'] else None);self.bound()
        self.state['records'].append(deepcopy(row));window=self.window(self.state['records'])
        self.state.update(phase='complete' if window else 'ready',pending=None,window=window);self.save()
        self.bound();returned=deepcopy(row)
        final_epoch=reader.clock_ms();final_host=source.phase.epoch_ms();final=source.monotonic()
        need(number(final,started,1e15) and final-started<5)
        floor=frame['group']['rootsBefore']['requestedEpochMs'];phase=frame['phaseBefore']['capturedEpochMs']
        fresh(floor,final_epoch);fresh(phase,final_host)
        need(max(final_epoch-floor,epoch-floor+(final-epoch_clock)*1000)<=1500
            and max(final_host-phase,host-phase+(final-host_clock)*1000)<=1500)
        return returned


    def wait(self,*,sleep=time.sleep):
        source=self.source
        need(callable(sleep));self.started=source.monotonic()
        try:
            self.bound()
            for attempt in range(32):
                self.read();self.bound()
                if self.state['phase']=='complete':return deepcopy(self.state['window'])
                if attempt==31:break
                sleep(.25);self.bound()
            need(False)
        finally:self.started=None
