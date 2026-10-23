"""One observer's durable original-source acquisition under the real SDK lock.

Every child owns its actual query and raw bytes. This parent owns acquisition,
original app admissions and immutable associations, never product effects from
an acknowledgment. An interrupted acquisition is retained and cannot resume.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import os
import time
from pathlib import Path
from adapters.native_feature_observation import exact,integer,need,number,validate as native_original
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.history import same
from adapters.original_file_reads import record as original_read
from adapters.script_feature.lock import ScriptSourceLock
from adapters.native_clock_join import NativeClockAcquisition,digest
from feature_journeys.phase_fixture import PhaseFixtureReader,validate as phase_original
from ios.adapters.graphics_history import follow_native,restore_native
from ios.adapters.tablet_web_packets import TabletWebPackets,COMPONENTS
from ios.adapters.tablet_web_history import derive

VERSION=1
ORDER=('sources','trace','dom','buttons','uikit','state','closures','emissions','deferred')
FRAME_KEYS={'trace':'ledger','dom':'document','uikit':'touches','emissions':'emitter'}


class TabletSourcePhaseChanged(ValueError):pass


class TabletWebSourceOwner:
    def __init__(self,root,binding,run,role,fixture_url,pid,lock,guard,*,epoch_ms=lambda:int(time.time()*1000),monotonic=time.monotonic,historical=False):
        self.root=Path(root);self.binding=deepcopy(context(binding));self.run,self.role,self.fixture,self.pid=run,role,fixture_url,pid
        need(isinstance(lock,ScriptSourceLock) and lock.path==self.root/'script-feature-sources.lock' and type(historical) is bool
            and self.binding['processIdentity']==str(pid) and role in ('primary','actor') and set(ORDER)==set(COMPONENTS))
        COMPONENTS['sources'].command(dict(schemaVersion=1,action=COMPONENTS['sources'].ACTION,commandId='ios-'+'0'*32,runId=run,fixtureUrl=fixture_url))
        self.lock,self.guard,self.epoch_ms,self.monotonic,self.historical=lock,guard,epoch_ms,monotonic,historical
        need(all(callable(fn) for fn in (guard,epoch_ms,monotonic)))
        if not historical:self.bound()
        self.store=PrivateFeatureState(self.root/('tabletweb-source-owner-'+run+'-'+role+'.json'))
        self.state=self.store.read()
        if self.state is None:
            need(not historical)
            self.state=dict(tabletWebSourceOwnerVersion=VERSION,binding=self.binding,runId=run,role=role,fixtureUrl=fixture_url,processId=pid,
                apps=[],records=[],pending=None,intent=None,inspection=None,appIntent=None,appPending=None,appInspection=None)
            self.store.write(self.state,None)
        self.saved=deepcopy(self.state)
        self.originals=OriginalFrameStore(root,binding,run,role,self.original_guard,self.frame_intent,namespace='tabletweb-acquisitions',schema_prefix='tabletWebAcquisition',monotonic=monotonic)
        self.app_originals=OriginalFrameStore(root,binding,run,role,self.original_guard,self.app_intent,namespace='tabletweb-app-origins',schema_prefix='tabletWebAppAdmission',monotonic=monotonic)
        self.children={name:TabletWebPackets(root,binding,run,role,fixture_url,pid,name,self.original_guard,epoch_ms=epoch_ms,monotonic=monotonic,historical=historical) for name in ORDER}
        self.history()

    def bound(self):
        need(not self.historical);self.lock.assert_held();need(self.guard() is not False)

    def original_guard(self):
        if not self.historical:self.bound()
        return True

    def save(self):
        self.bound();self.store.write(self.state,self.saved);self.saved=deepcopy(self.state)

    def frame_intent(self,kind,value):
        need(kind=='original' and self.state['pending'] is not None);self.state['intent']=deepcopy(value);self.state['inspection']=None;self.save()

    def app_intent(self,kind,value):
        need(kind=='original' and self.state['appPending'] is not None);self.state['appIntent']=deepcopy(value);self.state['appInspection']=None;self.save()

    def inspect(self,store,reference):
        value=store.original(reference);path=store.path(value)
        if value['phase']=='planned':need(not os.path.lexists(path));return None
        descriptor=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
        with os.fdopen(descriptor,'rb') as stream:
            store.file(path,stream.fileno(),value);raw=stream.read(value['bytes']+1);store.file(path,stream.fileno(),value)
        need(len(raw)<=value['bytes']);original_read(path)
        inspection=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),complete=len(raw)==value['bytes'] and hashlib.sha256(raw).hexdigest()==value['sha256'])
        if value['phase']=='saved':need(inspection['complete'])
        return inspection

    def stamp(self):
        epoch,mono=self.epoch_ms(),self.monotonic();need(integer(epoch,1) and number(mono,0,1e15));return dict(epochMs=epoch,monotonic=mono)

    def app_sources(self,references=None):
        refs=self.state['apps'] if references is None else references
        need(type(refs) is list and self.state['apps'][:len(refs)]==refs);result=[]
        for index,ref in enumerate(refs,1):
            full=self.app_originals.expand(ref);need(full['index']==index);result.append(self.app_originals.read(full))
        return result

    def remember_app(self,value):
        self.bound();need(self.state['pending'] is self.state['intent'] is self.state['appPending'] is self.state['appIntent'] is None and len(self.state['apps'])<32)
        self.state['appPending']=deepcopy(value);self.save()
        # Full actual app-origin validation is performed by derive before any
        # observation can qualify. The input originals themselves are durable
        # before interpretation, including a later rejected app admission.
        try:ref=self.app_originals.write(len(self.state['apps'])+1,value)
        except Exception:
            if self.state['appIntent'] is not None:self.state['appInspection']=self.inspect(self.app_originals,self.state['appIntent']);self.save()
            raise
        self.state['apps'].append(ref);self.state['appIntent']=self.state['appPending']=self.state['appInspection']=None;self.save();return deepcopy(ref)

    def _clock(self,value,frame):
        exact(value,{'hostBeforeEpochMs','hostAfterEpochMs','hostBeforeMonotonic','hostAfterMonotonic','nativeBefore','nativeAfter','originalsSha256'})
        a,b,c,d=[value[key] for key in ('hostBeforeEpochMs','hostAfterEpochMs','hostBeforeMonotonic','hostAfterMonotonic')]
        need(number(a,1,1e15) and number(b,a,a+1500) and number(c,0,1e15) and number(d,c,c+1.5)
            and max(b-a,(d-c)*1000)<1500 and abs(b-a-(d-c)*1000)<=250 and value['originalsSha256']==digest(frame))
        before,after=value['nativeBefore'],value['nativeAfter'];follow_native(before,after);need(before['processId']==self.pid
            and abs(after['capturedEpochMs']-before['capturedEpochMs']-(d-c)*1000)<=250)
        for name in ORDER:
            packet=frame[FRAME_KEYS.get(name,name)]
            start,end=(packet['capturedEpochMs'],packet['capturedEpochMs']) if name=='closures' else (packet['clockBefore']['epochMs'],packet['clockAfter']['epochMs'])
            need(before['capturedEpochMs']<=start<=end<=after['capturedEpochMs'])
        return value

    def _record(self,value,index,previous):
        exact(value,{'tabletWebAcquisitionVersion','index','status','hostProcessId','apps','before','after','phaseBefore','phaseAfter','nativeBefore','nativeAfter','components','browser','clockJoin'})
        need(type(value['tabletWebAcquisitionVersion']) is int and value['tabletWebAcquisitionVersion']==VERSION and type(value['index']) is int and value['index']==index
            and value['status'] in ('acquiring','returned','failed') and integer(value['hostProcessId'],1)
            and type(value['apps']) is list and self.state['apps'][:len(value['apps'])]==value['apps']
            and type(value['components']) is list and len(value['components'])<=len(ORDER))
        before=value['before'];exact(before,{'epochMs','monotonic'});need(integer(before['epochMs'],1) and number(before['monotonic'],0,1e15))
        if value['after'] is not None:
            exact(value['after'],{'epochMs','monotonic'});need(integer(value['after']['epochMs'],before['epochMs']) and number(value['after']['monotonic'],before['monotonic'],1e15))
        for name in ('nativeBefore','nativeAfter'):
            packet=value[name]
            if packet is not None:
                native_original(packet,packet['requestId'],self.pid,packet['capturedEpochMs'])
                if previous is not None:follow_native(previous,packet)
                previous=packet
        result={}
        for ordinal,part in enumerate(value['components']):
            exact(part,{'component','index','reference'});name=part['component'];need(name==ORDER[ordinal] and integer(part['index'],1))
            child=self.children[name]
            if part['reference'] is None:need(value['status']!='returned' and ordinal==len(value['components'])-1);continue
            need(part['index']<=len(child.state['records']) and same(child.state['records'][part['index']-1],part['reference']))
            row=child.originals.read(child.originals.expand(part['reference']));need(row['index']==part['index'] and row['status']=='returned')
            need(row['before']['epochMs']>=before['epochMs'] and row['before']['monotonic']>=before['monotonic'])
            if value['after'] is not None:need(row['after']['epochMs']<=value['after']['epochMs'] and row['after']['monotonic']<=value['after']['monotonic'])
            _floor,packets=child.record(row,row['index'],None);need(packets and digest(packets[-1])==row['resultSha256']);result[FRAME_KEYS.get(name,name)]=packets[-1]
        if value['phaseBefore'] is not None:
            phase=value['phaseBefore'];phase_original(phase,run=self.run,area='tablet-web',request=phase['requestId'],epoch=phase['capturedEpochMs'])
        if value['phaseAfter'] is not None:
            phase=value['phaseAfter'];phase_original(phase,run=self.run,area='tablet-web',request=phase['requestId'],epoch=phase['capturedEpochMs'],previous=value['phaseBefore'])
        if value['status']=='returned':
            need(len(result)==len(ORDER) and value['browser'] is not None and value['after'] is not None and value['nativeAfter'] is not None
                and value['phaseBefore'] is not None and value['phaseAfter'] is not None)
            result['browser']=deepcopy(value['browser']);self._clock(value['clockJoin'],result)
            clock=value['clockJoin'];need(same(clock['nativeBefore'],value['nativeBefore']) and same(clock['nativeAfter'],value['nativeAfter'])
                and clock['hostBeforeEpochMs']>=before['epochMs'] and clock['hostBeforeMonotonic']>=before['monotonic']
                and clock['hostAfterEpochMs']==value['after']['epochMs'] and clock['hostAfterMonotonic']==value['after']['monotonic']
                and value['phaseBefore']['capturedEpochMs']<=clock['hostBeforeEpochMs'] and value['phaseAfter']['capturedEpochMs']>=clock['hostAfterEpochMs'])
        else:need(value['clockJoin'] is None)
        return previous,result

    def history(self):
        value=self.state
        exact(value,{'tabletWebSourceOwnerVersion','binding','runId','role','fixtureUrl','processId','apps','records','pending','intent','inspection','appIntent','appPending','appInspection'})
        need(type(value['tabletWebSourceOwnerVersion']) is int and value['tabletWebSourceOwnerVersion']==VERSION
            and same(value['binding'],self.binding) and value['runId']==self.run and value['role']==self.role and value['fixtureUrl']==self.fixture
            and type(value['processId']) is int and value['processId']==self.pid and type(value['apps']) is list and len(value['apps'])<=32
            and type(value['records']) is list and len(value['records'])<=128)
        for child in self.children.values():child.history()
        self.app_sources();frames=[];native=None;phase_floor=None
        self.blocked=(value['appPending'] is not None or value['appIntent'] is not None
            or any(child.blocked or child.state['pending'] is not None or child.state['recordIntent'] is not None for child in self.children.values()))
        def phase_follow(row):
            nonlocal phase_floor
            for key in ('phaseBefore','phaseAfter'):
                phase=row[key]
                if phase is not None:
                    phase_original(phase,run=self.run,area='tablet-web',request=phase['requestId'],epoch=phase['capturedEpochMs'],previous=phase_floor);phase_floor=phase
        for index,ref in enumerate(value['records'],1):
            original=self.originals.expand(ref);need(original['index']==index);row=self.originals.read(original)
            native,frame=self._record(row,index,native)
            phase_follow(row)
            if row['status']=='returned':frames.append(frame)
            else:self.blocked=True
        if value['pending'] is not None:
            native,_=self._record(value['pending'],len(value['records'])+1,native);self.blocked=True
            phase_follow(value['pending'])
        need(value['intent'] is None or value['pending'] is not None)
        for ref,pending,inspection,store in ((value['intent'],value['pending'],value['inspection'],self.originals),(value['appIntent'],value['appPending'],value['appInspection'],self.app_originals)):
            if ref is None:need(inspection is None);continue
            need(pending is not None);actual=self.inspect(store,ref)
            if inspection is not None:need(same(actual,inspection))
            if actual is not None and actual['complete']:need(same(store.read(ref),pending))
        self.native_floor,self.phase_floor=deepcopy(native),deepcopy(phase_floor);return frames

    def recover_original(self,*,app=False):
        """Adopt only the actual complete immutable file; never resend a read."""
        self.bound();self.history();need(type(app) is bool)
        key='appIntent' if app else 'intent';pending_key='appPending' if app else 'pending';inspection_key='appInspection' if app else 'inspection'
        ref=self.state[key];need(ref is not None and ref['phase'] in ('opened','saved'))
        store=self.app_originals if app else self.originals;actual=store.read(ref);need(same(actual,self.state[pending_key]))
        if not app:need(actual['status']=='returned')
        originals=self.state['apps' if app else 'records'];need(ref['index']==len(originals)+1)
        originals.append(store.compact(dict(ref,phase='saved')));self.state[key]=self.state[pending_key]=self.state[inspection_key]=None;self.save()
        return deepcopy(originals[-1])

    def capture(self,readers,native,phase,browser):
        self.bound();frames=self.history();need(not self.blocked and len(self.state['records'])<128 and set(readers)==set(ORDER)
            and isinstance(phase,PhaseFixtureReader) and phase.area=='tablet-web' and phase.run==self.run and phase.fixture_url==self.fixture and callable(browser))
        if phase.previous is None and self.phase_floor is not None:phase.previous=deepcopy(self.phase_floor)
        first=phase.read(self.phase_floor);before=self.stamp()
        self.state['pending']=dict(tabletWebAcquisitionVersion=VERSION,index=len(self.state['records'])+1,status='acquiring',hostProcessId=os.getpid(),apps=deepcopy(self.state['apps']),before=before,after=None,
            phaseBefore=first['status'],phaseAfter=None,nativeBefore=None,nativeAfter=None,components=[],browser=None,clockJoin=None);self.save();pending=self.state['pending']
        try:
            if native.instance is None and self.native_floor is not None:restore_native(native,self.native_floor)
            window=NativeClockAcquisition(native,epoch_ms=self.epoch_ms,monotonic=self.monotonic);window.begin(first['afterEpochMs'])
            pending['nativeBefore']=deepcopy(window.started['nativeBefore']);self.save();parts={}
            for name in ORDER:
                child=self.children[name];part=dict(component=name,index=len(child.state['records'])+1,reference=None);pending['components'].append(part);self.save()
                parts[FRAME_KEYS.get(name,name)]=child.capture(readers[name]);part['reference']=deepcopy(child.state['records'][-1]);self.save()
            parts['browser']=browser();pending['browser']=deepcopy(parts['browser']);self.save()
            pending['nativeAfter']=native.read(native.sequence);pending['after']=self.stamp();self.save()
            pending['phaseAfter']=phase.status(first['status']);self.save()
            pending['clockJoin']=dict(hostBeforeEpochMs=window.started['hostBeforeEpochMs'],hostBeforeMonotonic=window.started['hostBeforeMonotonic'],
                hostAfterEpochMs=pending['after']['epochMs'],hostAfterMonotonic=pending['after']['monotonic'],nativeBefore=pending['nativeBefore'],nativeAfter=pending['nativeAfter'],originalsSha256=digest(parts))
            pending['status']='returned';self.save();self._record(pending,pending['index'],self.native_floor)
            # Preserve actual originals even when the input phase changed.
            self.originals.write(pending['index'],deepcopy(pending));self.state['records'].append(self.originals.compact(self.state['intent']))
            self.state['intent']=self.state['pending']=self.state['inspection']=None;self.save()
            need(pending['phaseBefore']['active'] and pending['phaseAfter']['active'] and pending['phaseBefore']['activations'] and pending['phaseAfter']['activations'])
            if pending['phaseBefore']['activations'][-1]['ticket']!=pending['phaseAfter']['activations'][-1]['ticket']:raise TabletSourcePhaseChanged('Actual Tablet acquisition crossed an input phase')
            now=self.stamp();clock=pending['clockJoin'];need(now['epochMs']>=clock['hostAfterEpochMs'] and now['monotonic']>=clock['hostAfterMonotonic']
                and now['epochMs']-clock['hostBeforeEpochMs']<1500 and now['monotonic']-clock['hostBeforeMonotonic']<1.5)
            return deepcopy(parts),deepcopy(pending)
        except TabletSourcePhaseChanged:raise
        except Exception:
            if self.state['pending'] is not None and self.state['intent'] is None:
                pending['status']='failed';pending['clockJoin']=None;pending['after']=self.stamp();self.save()
            elif self.state['intent'] is not None:self.state['inspection']=self.inspect(self.originals,self.state['intent']);self.save()
            raise

    def facts(self,origins):
        frames=self.history();need(not self.blocked and frames);return derive(frames,self.app_sources(),self.binding,origins)

    def facts_at(self,reference,origins):
        """Historical only; later pages/apps cannot replace this actual frame."""
        need(self.historical);frames=self.history();full=self.originals.expand(reference);index=full['index']
        need(1<=index<=len(self.state['records']) and same(reference,self.state['records'][index-1]))
        rows=[self.originals.read(self.originals.expand(ref)) for ref in self.state['records'][:index]]
        need(all(row['status']=='returned' for row in rows));current=rows[-1]
        need(current['phaseBefore']['active'] and current['phaseAfter']['active'] and current['phaseBefore']['activations'] and current['phaseAfter']['activations']
            and current['phaseBefore']['activations'][-1]['ticket']==current['phaseAfter']['activations'][-1]['ticket'])
        return derive(frames[:index],self.app_sources(current['apps']),self.binding,origins),deepcopy(current),deepcopy(frames[index-1])
