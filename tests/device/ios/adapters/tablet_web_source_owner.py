"""One observer's durable original-source acquisition under the real SDK lock.

Every child owns its actual query and raw bytes. This parent owns acquisition,
original app admissions and immutable associations, never product effects from
an acknowledgment. An interrupted acquisition is retained and cannot resume.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from contextlib import contextmanager
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
from ios.adapters.tablet_web_record_cache import parent_record

VERSION=2
READS=(1,2)
ACQUISITION_VERSION=2
ACQUISITION_READS=(1,2)
ORDER=('sources','trace','dom','buttons','uikit','state','closures','emissions','deferred')
FRAME_KEYS={'trace':'ledger','dom':'document','uikit':'touches','emissions':'emitter'}


def active_browser(value):
    """An active acquisition cannot consume a retired-only fixture inventory."""
    need(type(value) is dict and type(value.get('browserFixtureVersion')) is int
        and value['browserFixtureVersion']==1)
    from ios.adapters.world_web_measurements import browser_original
    return browser_original(value)


class TabletSourcePhaseChanged(ValueError):pass


class TabletWebSourceOwner:
    def __init__(self,root,binding,run,role,fixture_url,pid,lock,guard,*,epoch_ms=lambda:int(time.time()*1000),monotonic=time.monotonic,historical=False,admission=None):
        self.root=Path(root);self.binding=deepcopy(context(binding));self.run,self.role,self.fixture,self.pid=run,role,fixture_url,pid
        need(isinstance(lock,ScriptSourceLock) and lock.path==self.root/'script-feature-sources.lock' and type(historical) is bool
            and self.binding['processIdentity']==str(pid) and role in ('primary','actor') and set(ORDER)==set(COMPONENTS))
        COMPONENTS['sources'].command(dict(schemaVersion=1,action=COMPONENTS['sources'].ACTION,commandId='ios-'+'0'*32,runId=run,fixtureUrl=fixture_url))
        self.lock,self.guard,self.epoch_ms,self.monotonic,self.historical=lock,guard,epoch_ms,monotonic,historical
        self.admission=deepcopy(admission);self._stored_read_depth=0
        if admission is not None:
            from ios.adapters.tablet_web_admission import validate as admission_original
            admission_original(admission,self.binding)
            if not historical:need(admission['hostProcessId']==os.getpid())
        need(all(callable(fn) for fn in (guard,epoch_ms,monotonic)))
        if not historical:self.bound()
        self.store=PrivateFeatureState(self.root/('tabletweb-source-owner-'+run+'-'+role+'.json'))
        self.state=self.store.read()
        if self.state is not None:
            from ios.adapters.tablet_web_rotation_fence import read_barrier,scope
            read_barrier(self.state,scope(self.binding,self.run,self.role,self.fixture,self.pid))
        if self.state is None:
            need(not historical)
            self.state=dict(tabletWebSourceOwnerVersion=VERSION,binding=self.binding,runId=run,role=role,fixtureUrl=fixture_url,processId=pid,
                apps=[],records=[],pending=None,intent=None,inspection=None,appIntent=None,appPending=None,appInspection=None,reconciled=[])
            self.store.write(self.state,None)
        self.saved=deepcopy(self.state)
        self._original_storage()
        self.history()

    def _original_storage(self):
        self.originals=OriginalFrameStore(self.root,self.binding,self.run,self.role,self.stored_original_guard,self.frame_intent,
            namespace='tabletweb-acquisitions',schema_prefix='tabletWebAcquisition',monotonic=self.monotonic)
        self.app_originals=OriginalFrameStore(self.root,self.binding,self.run,self.role,self.stored_original_guard,self.app_intent,
            namespace='tabletweb-app-origins',schema_prefix='tabletWebAppAdmission',monotonic=self.monotonic)
        self.children={name:TabletWebPackets(self.root,self.binding,self.run,self.role,self.fixture,self.pid,name,self.original_guard,
            storage_guard=self.local_original_guard,epoch_ms=self.epoch_ms,monotonic=self.monotonic,historical=self.historical) for name in ORDER}

    @classmethod
    def _closed_snapshot(cls,root,binding,run,role,fixture_url,pid,lock,state,*,monotonic=time.monotonic):
        """Literal old header for a guarded closed-prefix reader, never live.

        The caller validates its actual immutable copy and all current child
        signatures. This does not route around the constructor's live fence.
        Every old row/native/phase/child continuation still runs in history.
        """
        owner=object.__new__(cls);owner.root=Path(root);owner.binding=deepcopy(context(binding))
        owner.run,owner.role,owner.fixture,owner.pid=run,role,fixture_url,pid
        need(isinstance(lock,ScriptSourceLock) and lock.path==owner.root/'script-feature-sources.lock'
            and owner.binding['processIdentity']==str(pid) and role in ('primary','actor') and callable(monotonic))
        lock.assert_held()
        COMPONENTS['sources'].command(dict(schemaVersion=1,action=COMPONENTS['sources'].ACTION,
            commandId='ios-'+'0'*32,runId=run,fixtureUrl=fixture_url))
        def forbidden(*_args,**_kwargs):need(False)
        owner.lock,owner.guard,owner.epoch_ms,owner.monotonic=lock,forbidden,forbidden,monotonic
        owner.historical=True;owner.admission=None;owner._stored_read_depth=0
        owner.store=PrivateFeatureState(owner.root/('tabletweb-source-owner-'+run+'-'+role+'.json'))
        owner.state=deepcopy(state);owner.saved=deepcopy(state)
        need(type(state.get('tabletWebSourceOwnerVersion')) is int and state['tabletWebSourceOwnerVersion'] in (1,2))
        owner._original_storage();owner.history();return owner

    def bound(self):
        need(not self.historical);self.lock.assert_held();need(self.guard() is not False)

    def original_guard(self):
        if not self.historical:self.bound()
        return True

    def stored_original_guard(self):
        # This guard belongs only to the two immutable aggregate file stores.
        # Child capture/save/send keep original_guard, independently of depth.
        if not self.historical:
            self.lock.assert_held()
            if not self._stored_read_depth:self.bound()
        return True

    @contextmanager
    def _stored_reads(self):
        outer=self._stored_read_depth==0
        if not self.historical:
            self.lock.assert_held()
            if outer:self.bound()
        self._stored_read_depth+=1
        try:yield
        finally:
            self._stored_read_depth-=1
            if not self.historical:
                self.lock.assert_held()
                if outer:self.bound()

    def local_original_guard(self):
        # Immutable private-byte replay does not acquire product data. The
        # component retains its full original_guard at entry/exit, every WAL
        # write and native capture. Only nested stored-file reads use this
        # local lock guard, as the independent native auxiliary store does.
        if not self.historical:self.lock.assert_held()
        return True

    def save(self):
        self.bound()
        if self.state['tabletWebSourceOwnerVersion']==1:self.state['tabletWebSourceOwnerVersion']=VERSION;self.state['reconciled']=[]
        self.store.write(self.state,self.saved);self.saved=deepcopy(self.state)

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
        with self._stored_reads():return self._app_sources(references)

    def _app_sources(self,references=None):
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
        version=value.get('tabletWebAcquisitionVersion') if type(value) is dict else None
        need(type(version) is int and version in ACQUISITION_READS)
        fields={'tabletWebAcquisitionVersion','index','status','hostProcessId','apps','before','after','phaseBefore','phaseAfter','nativeBefore','nativeAfter','components','browser','clockJoin'}
        exact(value,fields|({'admission'} if version>=2 else set()))
        if version>=2:
            from ios.adapters.tablet_web_admission import validate as admission_original
            admission_original(value['admission'],self.binding)
            need(value['admission']['hostProcessId']==value['hostProcessId'])
        need(type(value['tabletWebAcquisitionVersion']) is int and value['tabletWebAcquisitionVersion'] in ACQUISITION_READS and type(value['index']) is int and value['index']==index
            and value['status'] in ('acquiring','returned','failed') and integer(value['hostProcessId'],1)
            and type(value['apps']) is list and self.state['apps'][:len(value['apps'])]==value['apps']
            and type(value['components']) is list and len(value['components'])<=len(ORDER))
        before=value['before'];exact(before,{'epochMs','monotonic'});need(integer(before['epochMs'],1) and number(before['monotonic'],0,1e15))
        if version>=2:
            acquired=value['admission']['acquisition']
            need(before['epochMs']>=acquired['hostAfterEpochMs'] and before['monotonic']>=acquired['hostAfterMonotonic'])
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
            active_browser(value['browser'])
            result['browser']=deepcopy(value['browser']);self._clock(value['clockJoin'],result)
            clock=value['clockJoin'];need(same(clock['nativeBefore'],value['nativeBefore']) and same(clock['nativeAfter'],value['nativeAfter'])
                and clock['hostBeforeEpochMs']>=before['epochMs'] and clock['hostBeforeMonotonic']>=before['monotonic']
                and clock['hostAfterEpochMs']==value['after']['epochMs'] and clock['hostAfterMonotonic']==value['after']['monotonic']
                and value['phaseBefore']['capturedEpochMs']<=clock['hostBeforeEpochMs'] and value['phaseAfter']['capturedEpochMs']>=clock['hostAfterEpochMs'])
        else:need(value['clockJoin'] is None)
        return previous,result

    def history(self):
        with self._stored_reads():return self._history()

    def _history(self):
        value=self.state
        version=value.get('tabletWebSourceOwnerVersion');need(type(version) is int and version in READS)
        exact(value,({'reconciled'} if version>=2 else set())|{'tabletWebSourceOwnerVersion','binding','runId','role','fixtureUrl','processId','apps','records','pending','intent','inspection','appIntent','appPending','appInspection'})
        need(type(value['tabletWebSourceOwnerVersion']) is int and value['tabletWebSourceOwnerVersion'] in READS
            and same(value['binding'],self.binding) and value['runId']==self.run and value['role']==self.role and value['fixtureUrl']==self.fixture
            and type(value['processId']) is int and value['processId']==self.pid and type(value['apps']) is list and len(value['apps'])<=32
            and type(value['records']) is list and len(value['records'])<=128)
        for child in self.children.values():child.history()
        self.app_sources();frames=[];native=None;phase_floor=None;admission_floor=None
        self.blocked=(value['appPending'] is not None or value['appIntent'] is not None
            or any(child.blocked or child.state['pending'] is not None or child.state['recordIntent'] is not None for child in self.children.values()))
        def phase_follow(row):
            nonlocal phase_floor,admission_floor
            if row['tabletWebAcquisitionVersion']>=2:
                from ios.adapters.tablet_web_admission import follows
                if admission_floor is not None:follows(admission_floor,row['admission'],self.binding)
                admission_floor=deepcopy(row['admission'])
            for key in ('phaseBefore','phaseAfter'):
                phase=row[key]
                if phase is not None:
                    phase_original(phase,run=self.run,area='tablet-web',request=phase['requestId'],epoch=phase['capturedEpochMs'],previous=phase_floor);phase_floor=phase
        reconciled=value.get('reconciled',[]);need(type(reconciled) is list and len(reconciled)<=128)
        recovered={}
        for entry in reconciled:
            exact(entry,{'acquisition','component','leaf'})
            full=self.originals.expand(entry['acquisition']);index=full['index']
            need(index not in recovered and 1<=index<=len(value['records']) and same(value['records'][index-1],entry['acquisition']))
            self._reconciled(self.originals.read(full),entry['component'],entry['leaf']);recovered[index]=entry
        for index,ref in enumerate(value['records'],1):
            original=self.originals.expand(ref);need(original['index']==index);row=self.originals.read(original)
            previous=native
            native,frame=parent_record(self,row,index,previous,lambda:self._record(row,index,previous))
            phase_follow(row)
            if row['status']=='returned':frames.append(frame)
            else:
                need(row['status']=='failed')
                if index not in recovered:self.blocked=True
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

    def _reconciled(self,row,name,reference):
        """A failed frame stays failed; the old nonce contributes raw floors only."""
        need(row['status']=='failed' and row['nativeBefore'] is not None and row['nativeAfter'] is None
            and row['after'] is not None and row['components'] and row['components'][-1]['reference'] is None
            and row['components'][-1]['component']==name and name in ORDER)
        child=self.children[name];full=child.originals.expand(reference);index=full['index']
        need(index==row['components'][-1]['index'] and 1<=index<=len(child.state['records'])
            and same(reference,child.state['records'][index-1]))
        leaf=child.originals.read(full)
        need(leaf['status']=='failed' and leaf['tabletWebSourcePacketVersion']>=2 and leaf['query'] is not None
            and not leaf['unsafe'] and leaf['resultSha256'] is None and leaf['after'] is not None
            and leaf['raws'] and all(raw['outcome']=='accepted' for raw in leaf['raws'])
            and leaf['readbacks'] and leaf['readbacks'][0]['startRaw']==0
            and leaf['readbacks'][-1]['after'] is not None
            and row['before']['epochMs']<=leaf['before']['epochMs']<=leaf['after']['epochMs']<=row['after']['epochMs']
            and row['before']['monotonic']<=leaf['before']['monotonic']<=leaf['after']['monotonic']<=row['after']['monotonic']
            and leaf['readbacks'][0]['before']['epochMs']>=row['after']['epochMs']
            and leaf['readbacks'][0]['before']['monotonic']>=row['after']['monotonic'])
        _floor,packets=child.record(leaf,index,None);need(packets);return leaf

    def reconcile_unanswered(self,reader):
        """Read an already-issued passive nonce; never send it or resume a frame.

        Freeze the actual failed parent before reading the old AFC response.
        Both failed endpoints remain immutable. A typed, accepted old response
        contributes continuity floors only; a later acquisition is separate.
        Missing, unsafe, rejected and partial originals remain blocking.
        """
        self.bound();self.history();row=self.state['pending']
        need(row is not None and row['status']=='failed' and self.state['appIntent'] is self.state['appPending'] is None
            and row['nativeBefore'] is not None and row['nativeAfter'] is None and row['components']
            and row['components'][-1]['reference'] is None)
        name=row['components'][-1]['component'];child=self.children[name];leaf=child.state['pending']
        need(not any(other.blocked or other.state['pending'] is not None or other.state['recordIntent'] is not None
            for key,other in self.children.items() if key!=name))
        if self.state['intent'] is None:reference=self.originals.write(row['index'],deepcopy(row))
        else:
            full=self.state['intent'];need(full['phase'] in ('opened','saved') and full['index']==row['index'])
            need(same(self.originals.read(full),row));reference=self.originals.compact(dict(full,phase='saved'))
        if leaf is not None:
            need(leaf['status']=='failed' and leaf['query'] is not None and leaf['after'] is not None
                and leaf['index']==row['components'][-1]['index'] and not leaf['unsafe']
                and row['before']['epochMs']<=leaf['before']['epochMs']<=leaf['after']['epochMs']<=row['after']['epochMs']
                and row['before']['monotonic']<=leaf['before']['monotonic']<=leaf['after']['monotonic']<=row['after']['monotonic'])
            if child.state['recordIntent'] is not None:leaf_reference=child.recover_record()
            else:
                child.reconcile(reader);leaf_reference=child.archive_pending()
        else:
            index=row['components'][-1]['index'];need(1<=index<=len(child.state['records']))
            leaf_reference=deepcopy(child.state['records'][index-1])
        self._reconciled(row,name,leaf_reference)
        self.state['records'].append(reference)
        if self.state['tabletWebSourceOwnerVersion']==1:self.state['tabletWebSourceOwnerVersion']=VERSION;self.state['reconciled']=[]
        self.state['reconciled'].append(dict(acquisition=deepcopy(reference),component=name,leaf=deepcopy(leaf_reference)))
        self.state['pending']=self.state['intent']=self.state['inspection']=None;self.save();self.history()
        return deepcopy(reference)

    def capture(self,readers,native,phase,browser):
        self.bound();frames=self.history();need(not self.blocked and len(self.state['records'])<128 and set(readers)==set(ORDER)
            and isinstance(phase,PhaseFixtureReader) and phase.area=='tablet-web' and phase.run==self.run and phase.fixture_url==self.fixture and callable(browser))
        if phase.previous is None and self.phase_floor is not None:phase.previous=deepcopy(self.phase_floor)
        first=phase.read(self.phase_floor);before=self.stamp()
        self.state['pending']=dict(tabletWebAcquisitionVersion=ACQUISITION_VERSION if self.admission is not None else 1,index=len(self.state['records'])+1,status='acquiring',hostProcessId=os.getpid(),apps=deepcopy(self.state['apps']),before=before,after=None,
            phaseBefore=first['status'],phaseAfter=None,nativeBefore=None,nativeAfter=None,components=[],browser=None,clockJoin=None)
        if self.admission is not None:self.state['pending']['admission']=deepcopy(self.admission)
        self.save();pending=self.state['pending']
        try:
            if native.instance is None and self.native_floor is not None:restore_native(native,self.native_floor)
            window=NativeClockAcquisition(native,epoch_ms=self.epoch_ms,monotonic=self.monotonic);window.begin(first['afterEpochMs'])
            pending['nativeBefore']=deepcopy(window.started['nativeBefore']);self.save();parts={}
            for name in ORDER:
                child=self.children[name];part=dict(component=name,index=len(child.state['records'])+1,reference=None);pending['components'].append(part);self.save()
                parts[FRAME_KEYS.get(name,name)]=child.capture(readers[name]);part['reference']=deepcopy(child.state['records'][-1]);self.save()
            parts['browser']=browser();pending['browser']=deepcopy(parts['browser']);self.save()
            active_browser(pending['browser'])
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

    def frame_at(self,reference):
        """Original native frame only, including incomplete app setup/disposal.

        This performs no page/app fact derivation. A selected failed frame can
        never be read as returned; accepted failed originals remain prefix
        floors and ownership rather than a replacement observation.
        """
        need(self.historical);frames=self.history();full=self.originals.expand(reference);index=full['index']
        need(1<=index<=len(self.state['records']) and same(reference,self.state['records'][index-1]))
        rows=[self.originals.read(self.originals.expand(ref)) for ref in self.state['records'][:index]]
        current=rows[-1];need(current['status']=='returned')
        recovered={self.originals.expand(entry['acquisition'])['index'] for entry in self.state.get('reconciled',[])}
        need(all(row['status']=='returned' or ordinal in recovered for ordinal,row in enumerate(rows,1)))
        count=sum(row['status']=='returned' for row in rows);need(count>=1)
        need(current['phaseBefore']['active'] and current['phaseAfter']['active'] and current['phaseBefore']['activations'] and current['phaseAfter']['activations']
            and current['phaseBefore']['activations'][-1]['ticket']==current['phaseAfter']['activations'][-1]['ticket'])
        return deepcopy(current),deepcopy(frames[count-1]),deepcopy(frames[:count])

    def facts_at(self,reference,origins):
        """Historical facts require the separate complete actual app joins."""
        current,frame,frames=self.frame_at(reference)
        return derive(frames,self.app_sources(current['apps']),self.binding,origins),current,frame
