"""Original selected Emote timer/callback/Rig/UI quiet-window ownership.

This owns diagnostic observations only. Whole fixture/image/actor retirement
and ordinary cleanup inputs remain the complete feature owner's obligations.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from types import SimpleNamespace
import hashlib
import time

from adapters.emote_rig_measurements import source as source_group
from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.native_script_work import NativeScriptWork,validate as work_packet,members,scope as work_scope
from adapters.native_script_compilations import accept as compiled_accept
from adapters.normal_feature_state import PrivateFeatureState,context
from feature_journeys.phase_fixture import validate as phase_packet
from overte_phone_emote_sources import PhoneEmoteSources
from overte_phone_emote_originals import BLOCK,PhoneEmoteOriginals
from overte_phone_script_history import canonical,pack,unpack,same

VERSION=2
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
        need(value['instance']==native['instance'] and value['requestedEpochMs']>=frame['widgets']['capturedEpochMs']
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
                and frame['ui']['open'] is False and not frame['ui']['controls']
                and not actual['timers'] and not actual['unknownTimers'] and actual['evaluating'] is False
                and actual['signalCallbacks']==actual['timerCallbacks']==actual['unknownSignalCallbacks']==actual['unknownTimerCallbacks']==0)
        return (frame['group']['native']['animation']['overrideActive'] is False
            and frame['ui']['open'] is False and not frame['ui']['controls']
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
        start=None;floor=None
        for index,row in enumerate(records):
            frame=self.original(row['source']);native=frame['group']['native']
            scope=dict(rig=native['animation']['rigId'],history=native['animation']['history']['instance'],
                calls=native['animation']['history']['callSequence'],override=native['animation']['history']['overrideSequence'],
                lifecycle=native['lifecycle'],input=frame['ui']['scope']['sequence'],activity=self.activity(row))
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
        need(type(value['emoteLifetimeVersion']) is int and value['emoteLifetimeVersion'] in (1,2)
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

    @classmethod
    def _archive(cls,value,source,*,field,required):
        """Historical originals only; no live owner, query or current verdict."""
        need(isinstance(source,PhoneEmoteSources));source.lock.assert_held()
        started=source.monotonic();clock=started
        def bound():
            nonlocal clock
            source.lock.assert_held();need(source.guard() is not False)
            now=source.monotonic();need(number(now,clock,1e15) and now-started<5);clock=now
        bound();exact(value,{field,'segment','header','sourceHeader','cleanup'})
        need(type(value[field]) is int and value[field]==1
            and type(value['segment']) is int and value['segment']==source.segment)
        header=value['sourceHeader'];need(type(header) is dict and header.get('role')==source.role
            and same(header.get('admissionPolicy'),source.admission))
        state,frames=PhoneEmoteSources.archive(header,phase=source.phase,artifact_root=source.artifact_root,
            binding=source.binding,guard=bound,monotonic=source.monotonic)
        need(state['phase']=='ready' and state['pending'] is None
            and len(source.frames)>=len(frames) and same(source.frames[:len(frames)],frames))
        view=object.__new__(cls)
        view.source=SimpleNamespace(frames=frames,state=state,pid=source.pid,phase=source.phase,run=source.run,
            role=source.role,binding=source.binding,artifact_root=source.artifact_root)
        view.originals=PhoneEmoteOriginals(source.artifact_root,source.binding,source.run,source.role,
            bound,lambda *_:need(False),monotonic=source.monotonic)
        result=view.decode(value['header']);need(result['phase']==required)
        if required=='complete':
            # A saved worker packet cannot borrow a later unrelated source frame.
            need(result['records'] and result['records'][-1]['source']['revision']==len(frames))
        cleanup=value['cleanup'];previous=result['records'][-1]['providerAfter'] if result['records'] else frames[-1]['phaseAfter'] if frames else None
        phase_packet(cleanup,run=source.run,area='emotes',request=cleanup.get('requestId'),
            epoch=cleanup.get('capturedEpochMs'),previous=previous)
        view.cleanup_phase(cleanup,view.cleanup_phase(previous) if result['records'] else None);bound()
        return deepcopy(result)

    @classmethod
    def retirement_archive(cls,value,source):
        return cls._archive(value,source,field='emoteLifetimeRetirementVersion',required='complete')

    @classmethod
    def failure_archive(cls,value,source):
        return cls._archive(value,source,field='emoteLifetimeFailureArchiveVersion',required='reading')

    def transfer_failed(self,retain,*,retained=None):
        """Transfer interrupted work without a new sample or a quiet verdict."""
        need(callable(retain));started=self.source.monotonic();self.started=started
        try:
            self.current();need(self.source.state['phase']=='ready' and self.source.state['pending'] is None)
            if retained is None:
                need(self.state['phase']=='reading')
                cleanup=self.source.phase.status();self.cleanup_phase(cleanup)
                proof=dict(emoteLifetimeFailureArchiveVersion=1,segment=self.source.segment,header=deepcopy(self.previous),
                    sourceHeader=deepcopy(self.source.previous),cleanup=cleanup)
            else:proof=deepcopy(retained)
            failed=self.failure_archive(proof,self.source)
            ready=dict(phase='ready',records=deepcopy(failed['records']),pending=None,window=None)
            need(same(self.previous,proof['header']) or self.previous is not None and same(self.state,ready))
            self.retirement_phase(proof);self.bound();need(retain(deepcopy(proof)) is not False)
            self.bound();self.failure_archive(proof,self.source);self.retirement_phase(proof);self.bound()
            need(self.source.monotonic()-started<5)
            if self.state['phase']=='reading':self.state=ready;self.save()
            self.bound();need(self.source.monotonic()-started<5)
            return deepcopy(proof)
        finally:self.started=None

    def retirement_phase(self,proof):
        previous=proof['cleanup'];current=self.source.phase.status(previous)
        self.cleanup_phase(current,self.cleanup_phase(previous))
        # Provider birth and complete activation history remain authoritative.
        need(same(current['activations'],previous['activations']))
        return current

    def retirement_delivery(self,row,started):
        source=self.source;self.bound()
        native=source.adapter._native_feature_observer(source.selector,read_only=True)
        need(native.pid==source.pid and native.ios is False and native.guard() is not False)
        epoch,host=native.clock_ms(),source.phase.epoch_ms()
        frame=self.original(row['source']);end=source.monotonic();floor=frame['group']['rootsBefore']['requestedEpochMs']
        provider=frame['phaseBefore']['capturedEpochMs'];fresh(floor,epoch)
        need(number(end,started,1e15) and end-started<5 and number(end,row['monotonicMs']/1000,1e15))
        elapsed=end*1000-row['monotonicMs']
        need(-250<=host-provider<=1500 and max(epoch-floor,row['epochMs']-floor+elapsed)<=1500
            and row['hostEpochMs']-provider+elapsed<=1500)

    def retire(self,retain,*,retained=None):
        """Retain originals before journal removal, including a lost return.

        Reusing an exact retained packet transfers historical ownership only;
        it never refreshes the old quiet window or makes a current idle claim.
        """
        need(callable(retain));started=self.source.monotonic();self.started=started
        try:
            self.current()
            if retained is None:
                need(self.state['phase']=='complete');self.read();need(self.state['phase']=='complete')
                previous=self.state['records'][-1]['providerAfter'];cleanup=self.source.phase.status(previous)
                self.cleanup_phase(cleanup,self.cleanup_phase(previous))
                proof=dict(emoteLifetimeRetirementVersion=1,segment=self.source.segment,header=deepcopy(self.previous),
                    sourceHeader=deepcopy(self.source.previous),cleanup=cleanup)
            else:
                proof=deepcopy(retained)
                need(self.previous is None or same(self.previous,proof.get('header')))
            state=self.retirement_archive(proof,self.source);self.retirement_phase(proof);self.bound()
            need(retain(deepcopy(proof)) is not False)
            self.bound();self.retirement_archive(proof,self.source);self.retirement_phase(proof);self.bound()
            need(self.source.monotonic()-started<5)
            if retained is None:self.retirement_delivery(state['records'][-1],started)
            if self.previous is not None:
                self.store.discard(self.previous);need(self.store.read() is None);self.previous=None
            self.bound();need(self.source.monotonic()-started<5)
            if retained is None:self.retirement_delivery(state['records'][-1],started)
            self.failed=True # A retired owner cannot create another measurement.
            return deepcopy(proof)
        finally:self.started=None


    @classmethod
    def final_archive(cls,value,source):
        """Revalidate final native/work originals against the actual quiet tail."""
        need(isinstance(source,PhoneEmoteSources));source.lock.assert_held()
        started=clock=source.monotonic();need(number(started,0,1e15))
        def bound():
            nonlocal clock
            source.lock.assert_held();need(source.guard() is not False)
            now=source.monotonic();need(number(now,clock,1e15) and now-started<5);clock=now
        bound();exact(value,{'emoteFinalWorkVersion','role','segment','phase','lifetimeHeader','source','work',
            'providerAfter','epochMs','hostEpochMs','startedMonotonicMs','observedMonotonicMs'})
        need(type(value['emoteFinalWorkVersion']) is int and value['emoteFinalWorkVersion']==1
            and value['role']==source.role and type(value['segment']) is int and value['segment']==source.segment
            and value['phase'] in ('source','work','complete') and number(value['startedMonotonicMs'],0,1e18))
        proof=value['source'];PhoneEmoteSources.closed_archive(proof,phase=source.phase,role=source.role,segment=source.segment,
            artifact_root=source.artifact_root,binding=source.binding,guard=bound,monotonic=source.monotonic)
        need(proof['phase']==('reading' if value['phase']=='source' else 'complete'))
        state,frames=PhoneEmoteSources.archive(proof['sourceHeader'],phase=source.phase,artifact_root=source.artifact_root,
            binding=source.binding,guard=bound,monotonic=source.monotonic)
        view=object.__new__(cls)
        view.source=SimpleNamespace(frames=frames,state=state,pid=source.pid,phase=source.phase,run=source.run,role=source.role,
            binding=source.binding,artifact_root=source.artifact_root)
        view.originals=PhoneEmoteOriginals(source.artifact_root,source.binding,source.run,source.role,bound,
            lambda *_:need(False),monotonic=source.monotonic)
        lifetime=view.decode(value['lifetimeHeader']);need(lifetime['phase']=='complete' and lifetime['records'])
        last=lifetime['records'][-1];need(value['startedMonotonicMs']>=last['monotonicMs'])
        if value['phase']!='complete':
            need(all(value[key] is None for key in ('work','providerAfter','epochMs','hostEpochMs','observedMonotonicMs')))
        else:
            frame=proof['frame'];work=value['work']
            need(integer(value['epochMs'],frame['epochMs']) and number(value['hostEpochMs'],frame['hostEpochMs'],1e15)
                and number(value['observedMonotonicMs'],value['startedMonotonicMs'],1e18)
                and value['observedMonotonicMs']-value['startedMonotonicMs']<5000)
            view.validate_work(frame,work,value['epochMs'],last['work'])
            provider=value['providerAfter'];phase_packet(provider,run=source.run,area='emotes',request=provider.get('requestId'),
                epoch=value['hostEpochMs'],previous=frame['phaseAfter'])
            need(not provider['active'] and same(provider['activations'],frame['phaseAfter']['activations'])
                and frame['group']['rootsBefore']['requestedEpochMs']<=work['requestedEpochMs']<=work['capturedEpochMs']<=value['epochMs']
                and value['epochMs']-frame['group']['rootsBefore']['requestedEpochMs']<=1500)
            fresh(frame['phaseBefore']['capturedEpochMs'],value['hostEpochMs'])
            original=view.original(last['source']);a,b=original['group']['native'],frame['group']['native']
            need(a['instance']==b['instance'] and same(a['lifecycle'],b['lifecycle'])
                and a['animation']['rigId']==b['animation']['rigId']
                and all(a['animation']['history'][key]==b['animation']['history'][key]
                    for key in ('instance','callSequence','overrideSequence'))
                and original['ui']['scope']['sequence']==frame['ui']['scope']['sequence']
                and view.quiet_frame(frame,work)
                and same(view.activity(last),view.activity_frame(frame,work)))
        bound();return deepcopy(value)

    def final_work(self,retain):
        """Obtain new actual work after provider closure, without a new input.

        The parent retains source intent, work intent and exact completed data.
        Neither the quiet journal nor its active source originals are changed.
        """
        source=self.source;need(callable(retain));self.current()
        need(self.previous is not None and self.state['phase']=='complete' and self.state['records'])
        started=clock=source.monotonic();need(number(started,0,1e15))
        def bound():
            nonlocal clock
            self.bound();source.configuration_bound();source.predecessor_bound()
            now=source.monotonic();need(number(now,clock,1e15) and now-started<5);clock=now
        bound()
        value=dict(emoteFinalWorkVersion=1,role=source.role,segment=source.segment,phase='source',lifetimeHeader=deepcopy(self.previous),
            source=None,work=None,providerAfter=None,epochMs=None,hostEpochMs=None,startedMonotonicMs=started*1000,observedMonotonicMs=None)
        def source_retained(packet):
            value.update(source=deepcopy(packet),phase='work' if packet['phase']=='complete' else 'source')
            self.final_archive(value,source);need(retain(deepcopy(value)) is not False);bound()
        proof=source.read_closed(source_retained);bound();frame=proof['frame']
        selected,_native,_urls=source_group(frame['group'],source.pid,frame['epochMs'])
        reader=source.adapter._script_work(source.selector,read_only=True)
        need(isinstance(reader,NativeScriptWork) and reader.pid==source.pid and reader.ios is False)
        reader.restore([row['work'] for row in self.state['records']])
        work=reader.read(selected['engineInstance'],reader.last['sequence']);bound()
        provider=source.phase.status(frame['phaseAfter']);bound()
        value.update(phase='complete',work=work,providerAfter=provider,epochMs=reader.clock_ms(),hostEpochMs=source.phase.epoch_ms(),
            observedMonotonicMs=source.monotonic()*1000)
        self.final_archive(value,source);need(retain(deepcopy(value)) is not False);bound();result=deepcopy(value)
        source.closed_delivery(frame);bound();return result
