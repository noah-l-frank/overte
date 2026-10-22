"""Durable read-only Create/domain/VM originals on one candidate-bound app.

Every completed frame has its original native/host bracket and phase originals.
Interrupted reads remain historical and cannot be rebracketed. A new read-only
acquisition is allowed; no action, setter, expected state or resource reset is
available here. The peer owns another instance on a distinct app/target.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import time
import uuid

from adapters.native_clock_join import NativeClockAcquisition,digest,validate_join
from adapters.native_feature_observation import NativeFeatureObservation,exact,integer,need
from adapters.native_script_work import NativeScriptWork,validate as worker_packet
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from feature_journeys.phase_fixture import PhaseFixtureReader,validate as phase_packet
from ios.adapters import create_state,create_work
from ios.adapters.create_lifecycle import worker
from ios.adapters.emote_world import IOSEmoteWorld,actual_domain,validate as domain_packet,ACTION as DOMAIN_ACTION
from ios.adapters.graphics_history import restore_native,follow_native

from ios.adapters.create_api_clock import check as api_check

VERSION=1
MAX_FRAMES=256


class CreatePhaseChanged(NativeUIError):pass


class CreateSources:
    def __init__(self,store,lock,binding,run,role,scripts_root,guard,*,phase,readers=None,historical=False,
                 epoch_ms=lambda:time.time()*1000,monotonic=time.monotonic):
        need(isinstance(store,PrivateFeatureState) and isinstance(lock,ScriptSourceLock) and type(historical) is bool
             and role in ('primary','actor','actor-primary') and callable(guard) and callable(epoch_ms) and callable(monotonic))
        self.store,self.lock,self.binding,self.run,self.role=store,lock,deepcopy(context(binding)),identifier(run),role
        self.scripts_root,self.guard,self.phase,self.readers=scripts_root,guard,phase,readers
        self.historical,self.epoch_ms,self.monotonic=historical,epoch_ms,monotonic
        self.pid=int(binding['processIdentity']);need(str(self.pid)==binding['processIdentity'] and self.pid>0
            and store.path.name=='ios-create-'+role+'-sources.json' and lock.path==store.path.with_name('script-feature-sources.lock'))
        if not historical:
            need(isinstance(phase,PhaseFixtureReader) and phase.run==run and phase.area=='create'
                and set(readers)=={'create','domain','work','worker','native'}
                and isinstance(readers['create'],create_state.IOSCreateState) and isinstance(readers['domain'],IOSEmoteWorld)
                and isinstance(readers['work'],create_work.IOSCreateWork) and isinstance(readers['worker'],NativeScriptWork)
                and isinstance(readers['native'],NativeFeatureObservation) and readers['native'].ios
                and all(reader.pid==self.pid for reader in readers.values()))
        lock.assert_held();self.previous=store.read();self.frames=[];self._record_cache={}
        self.state=dict(records=[],pending=None,interrupted=[])
        if self.previous is not None:self.state,self.frames=self.decode(self.previous)
        if not historical and self.frames:
            last=self.frames[-1];raw=last['originals'];readers['create'].last=deepcopy(raw['createAfter'])
            readers['domain'].last=deepcopy(raw['domain']);readers['work'].last=deepcopy(raw['work'])
            need(readers['worker'].last is None);readers['worker'].restore([frame['originals']['worker'] for frame in self.frames])
            restore_native(readers['native'],last['clockJoin']['nativeAfter'])
            phase.previous=deepcopy(last['phaseAfter'])
    def envelope(self,state):
        return dict(iosCreateSourcesVersion=VERSION,binding=self.binding,runId=self.run,role=self.role,scriptsRoot=self.scripts_root,payload=pack([state]))
    def record_store(self,index):
        need(integer(index,1,MAX_FRAMES));return PrivateFeatureState(self.store.path.with_name('ios-create-'+self.role+'-sources-'+str(index)+'.json'))
    def validate_frame(self,frame,previous=None):
        exact(frame,{'index','label','ticket','phaseBefore','phaseAfter','originals','clockJoin'})
        need(integer(frame['index'],1,MAX_FRAMES) and type(frame['label']) is str and len(frame['label'])<=64);identifier(frame['ticket'])
        originals=frame['originals'];exact(originals,{'createBefore','domain','work','worker','createAfter'})
        clock=validate_join(frame['clockJoin'],originals);native_first,native_last=clock['nativeBefore'],clock['nativeAfter'];epoch=native_last['capturedEpochMs']
        need(native_first['processId']==native_last['processId']==self.pid and same(native_first['lifecycle'],native_last['lifecycle']))
        previous_raw=None if previous is None else previous['originals']
        before,after=originals['createBefore'],originals['createAfter']
        for packet,old in ((before,None if previous_raw is None else previous_raw['createAfter']),(after,before)):
            create_state.validate(packet,dict(schemaVersion=1,action=create_state.ACTION,commandId=packet['requestId'],runId=self.run),self.pid,epoch,old)
            need(packet['iosCreateStateVersion']>=3)
        domain=originals['domain'];domain_packet(domain,dict(schemaVersion=1,action=DOMAIN_ACTION,commandId=domain['requestId'],runId=self.run),self.pid,epoch,
                                                None if previous_raw is None else previous_raw['domain'])
        measured=actual_domain(domain);need(measured['domainId']==before['source']['domainId']==after['source']['domainId']
            and measured['selfSha256']==hashlib.sha256(uuid.UUID(before['source']['localSessionId']).bytes).hexdigest()
            and same(before['source']['tree']['entities'],domain['source']['tree']['entities'])
            and same(before['source']['tree']['entities'],after['source']['tree']['entities']))
        work=originals['work'];create_work.validate(work,dict(schemaVersion=1,action=create_work.ACTION,commandId=work['requestId'],runId=self.run),self.pid,epoch,
                                                   None if previous_raw is None else previous_raw['work'])
        # An ordinary open picker intentionally owns its pending original
        # browse closure. Observe that state without calling it drained.
        worker(originals['worker'],work,self.scripts_root,quiet=False)
        if previous_raw is not None:
            current=originals['worker'];worker_packet(current,dict(schemaVersion=1,commandId=current['requestId'],action='feature-script-work-observe',
                managerInstance=current['source']['manager']['instance']),self.pid,epoch,previous=previous_raw['worker'])
            follow_native(previous['clockJoin']['nativeAfter'],native_first)
        times=[native_first['capturedEpochMs'],before['clockBefore']['epochMs'],before['clockAfter']['epochMs'],domain['clockBefore']['epochMs'],domain['clockAfter']['epochMs'],
            work['clockBefore']['epochMs'],work['clockAfter']['epochMs'],originals['worker']['requestedEpochMs'],originals['worker']['capturedEpochMs'],
            after['clockBefore']['epochMs'],after['clockAfter']['epochMs'],epoch]
        need(times==sorted(times))
        first,last=frame['phaseBefore'],frame['phaseAfter']
        phase_packet(first,run=self.run,area='create',request=first['requestId'],epoch=clock['hostBeforeEpochMs'],previous=None if previous is None else previous['phaseAfter'])
        phase_packet(last,run=self.run,area='create',request=last['requestId'],epoch=last['capturedEpochMs'],previous=first)
        need(first['active'] and first['activations'] and first['activations'][-1]['ticket']==frame['ticket']
             and first['activations'][-1]['activatedEpochMs']<=clock['hostBeforeEpochMs']
             and clock['hostAfterEpochMs']-250<=last['capturedEpochMs']<=clock['hostAfterEpochMs']+1500)
        if previous is not None:need(frame['index']==previous['index']+1 and clock['hostBeforeEpochMs']>=previous['clockJoin']['hostAfterEpochMs'])
        return last['active'] and last['activations'][-1]['ticket']==frame['ticket']
    def decode(self,value,*,materialize=True):
        exact(value,{'iosCreateSourcesVersion','binding','runId','role','scriptsRoot','payload'});rows=unpack(value['payload'])
        need(len(rows)==1 and type(value['iosCreateSourcesVersion']) is int and value['iosCreateSourcesVersion']==VERSION and same(value,self.envelope(rows[0])))
        state=rows[0];exact(state,{'records','pending','interrupted'});need(type(state['records']) is list and len(state['records'])<=MAX_FRAMES
            and type(state['interrupted']) is list and len(state['interrupted'])<=32)
        frames=[]
        for index,ref in enumerate(state['records'],1):
            exact(ref,{'index','sha256'});need(ref['index']==index);packet=self.record_store(index).read()
            need(packet is not None and digest(packet)==ref['sha256']);exact(packet,{'iosCreateSourceRecordVersion','binding','runId','role','payload'})
            need(type(packet['iosCreateSourceRecordVersion']) is int and packet['iosCreateSourceRecordVersion']==VERSION and same(packet['binding'],self.binding)
                and packet['runId']==self.run and packet['role']==self.role)
            key=(index,ref['sha256'],None if index==1 else state['records'][index-2]['sha256'])
            if key not in self._record_cache:
                originals=unpack(packet['payload']);need(len(originals)==1);frame=originals[0];need(frame['index']==index)
                self.validate_frame(frame,None if not frames else frames[-1]);self._record_cache[key]=deepcopy(frame)
            # Every reference still reads and hashes the actual immutable file.
            # Native schema/prefix validation is reusable only for identical
            # bytes with the identical previously validated predecessor.
            frames.append(self._record_cache[key])
        for pending in state['interrupted']+([] if state['pending'] is None else [state['pending']]):
            exact(pending,{'label','phaseBefore','start','originals'});need(type(pending['originals']) is dict and set(pending['originals'])<={'createBefore','domain','work','worker','createAfter'})
            if 'createBefore' in pending['originals']:create_state.original(pending['originals']['createBefore'])
            if 'domain' in pending['originals']:actual_domain(pending['originals']['domain'])
        if not self.historical and len(frames)<MAX_FRAMES:
            # A frame record saved before its index is adopted is responsibility,
            # never an unused index. Recovery below may only validate/adopt it.
            extra=self.record_store(len(frames)+1).read()
            need(extra is None or state['pending'] is not None)
        return (deepcopy(state),deepcopy(frames)) if materialize else None
    def bound(self):
        api_check();self.lock.assert_held();need(not self.historical and self.guard() is not False and same(self.store.read(),self.previous))
    def save(self):
        self.bound();value=self.envelope(self.state);self.decode(value,materialize=False);self.store.write(value,self.previous);need(same(self.store.read(),value));self.previous=deepcopy(value)
    def capture(self,label):
        self.bound();need(len(self.frames)<MAX_FRAMES)
        if self.state['pending'] is not None:
            extra=self.record_store(len(self.frames)+1).read()
            if extra is not None:
                # Validate the orphan record against the retained intent before
                # adoption. No app request or publication is repeated.
                rows=unpack(extra['payload']);need(len(rows)==1);frame=rows[0]
                need(frame['label']==self.state['pending']['label'] and same(frame['phaseBefore'],self.state['pending']['phaseBefore'])
                    and same(frame['originals'],self.state['pending']['originals']))
                self.validate_frame(frame,None if not self.frames else self.frames[-1])
                self.state['records'].append(dict(index=frame['index'],sha256=digest(extra)));self.state['pending']=None;self.save();self.frames.append(frame)
            else:
                self.state['interrupted'].append(deepcopy(self.state['pending']));self.state['pending']=None;self.save()
        first=self.phase.status();need(first['active'] and first['activations']);ticket=first['activations'][-1]['ticket']
        self.state['pending']=dict(label=label,phaseBefore=first,start=None,originals={});self.save()
        clock=NativeClockAcquisition(self.readers['native'],epoch_ms=self.epoch_ms,monotonic=self.monotonic);clock.begin(first['activations'][-1]['activatedEpochMs'])
        self.state['pending']['start']=deepcopy(clock.started);self.save();r=self.readers
        reads=(('createBefore',lambda:r['create'].read(self.run)),('domain',lambda:r['domain'].read(self.run)),('work',lambda:r['work'].read(self.run)),
            ('worker',lambda:r['worker'].read(next(row for row in self.state['pending']['originals']['work']['source']['roles'] if row['role']=='edit')['manager']['instance'],
                0 if r['worker'].last is None else r['worker'].last['sequence'])),('createAfter',lambda:r['create'].read(self.run)))
        for name,read in reads:self.state['pending']['originals'][name]=deepcopy(read());self.save()
        raw=self.state['pending']['originals'];joined=clock.finish(raw,[('worker','capturedEpochMs')]);last=self.phase.status()
        frame=dict(index=len(self.frames)+1,label=label,ticket=ticket,phaseBefore=first,phaseAfter=last,originals=deepcopy(raw),clockJoin=joined)
        stable=self.validate_frame(frame,None if not self.frames else self.frames[-1])
        packet=dict(iosCreateSourceRecordVersion=VERSION,binding=self.binding,runId=self.run,role=self.role,payload=pack([frame]))
        target=self.record_store(frame['index']);need(target.read() is None);target.write(packet,None)
        self.state['records'].append(dict(index=frame['index'],sha256=digest(packet)));self.state['pending']=None;self.save();self.frames.append(frame)
        if not stable:raise CreatePhaseChanged('Create phase changed during acquisition; original frame retained without publication')
        return deepcopy(frame)
