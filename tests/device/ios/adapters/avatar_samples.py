"""Avatar-owned immutable Vulkan samples and honestly retained failed reads.

Each image request is issued once by the existing VulkanWorldFrameOwner. This
owner adds original Avatar world/renderer/clock/phase bracketing. ACKs, input
metadata and native file existence never establish a rendered Avatar effect.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import os
from pathlib import Path
import time
import uuid
from adapters.native_clock_join import NativeClockAcquisition,digest,validate_join
from adapters.native_feature_observation import exact,integer,need,number,validate as native_packet
from adapters.native_vulkan_world_frame import absent,validate as frame_packet,storage
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.original_frame_store import OriginalFrameStore
from adapters.owned_vulkan_world_frame import VulkanWorldFrameOwner
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from feature_journeys.evidence import MarkerNotReady
from feature_journeys.phase_fixture import PhaseFixtureReader,validate as phase_packet
from ios.adapters import avatar_images as images,avatar_world as world,avatar_renderers as renderers
from ios.adapters.avatar_marker_scope import IOSAvatarMarkerScope
from ios.adapters.avatar_state import session
from ios.adapters.graphics_history import restore_native,follow_native
from ios.adapters.script_runtime import IOSScriptRuntime

VERSION=1
PARTS=('phaseBefore','nativeStart','worldBefore','renderersBefore','capture','retirement','renderersAfter','worldAfter','clockJoin','phaseAfter')


class AvatarImagePending(MarkerNotReady):pass
class AvatarImagePhaseChanged(NativeUIError):pass


class IOSAvatarSamples:
    @classmethod
    def history(cls,value,*,store,root,binding,run,role,policy,lock):
        """Decode retained source/PNG/inode originals without a live runtime."""
        need(isinstance(store,PrivateFeatureState) and isinstance(lock,ScriptSourceLock));lock.assert_held()
        result=object.__new__(cls);result.store,result.root,result.binding=store,Path(root),deepcopy(context(binding))
        result.run,result.role,result.policy,result.lock=identifier(run),role,deepcopy(policy),lock
        need(role in ('primary','actor') and result.root.is_absolute() and result.root.resolve()==result.root
            and lock.path==store.path.with_name('script-feature-sources.lock'))
        result.pid=int(binding['processIdentity']);result.guard=lambda:True;result.historical=True
        result.originals=OriginalFrameStore(root,binding,run,role,lambda:True,lambda *_:need(False),
            namespace='avatar-sample',schema_prefix='avatarSample')
        result.state=result.decode(value);result.previous=deepcopy(value)
        for row in result.state['rows']:
            if row['status']!='abandoned':result.archive(row)
        return result

    def __init__(self,runtime,selector,scope,root,policy,phase,lock,*,
                 monotonic=time.monotonic,epoch_ms=lambda:time.time()*1000,sleep=time.sleep):
        need(isinstance(runtime,IOSScriptRuntime) and isinstance(scope,IOSAvatarMarkerScope)
            and isinstance(phase,PhaseFixtureReader) and phase.area=='avatar-people' and phase.run==scope.run
            and isinstance(lock,ScriptSourceLock) and all(callable(f) for f in (monotonic,epoch_ms,sleep)))
        self.runtime,self.selector,self.scope,self.root,self.policy,self.phase,self.lock=runtime,selector,scope,Path(root),deepcopy(policy),phase,lock
        self.binding,self.run,self.role=deepcopy(context(scope.binding)),identifier(scope.run),scope.role
        need(self.role in ('primary','actor') and phase.fixture_url==scope.fixture_url and policy.get('source')=='world-render-target')
        need(self.root.is_absolute() and self.root.resolve()==self.root and self.root.is_dir())
        self.pid=int(self.binding['processIdentity']);self.historical=False;self.monotonic,self.epoch_ms,self.sleep=monotonic,epoch_ms,sleep
        self.store=PrivateFeatureState(runtime.state_path(selector).with_name('ios-avatar-'+self.role+'-samples.json'))
        need(lock.path==self.store.path.with_name('script-feature-sources.lock'));lock.assert_held();scope.bound()
        self.guard=scope.guard
        self.originals=OriginalFrameStore(root,self.binding,self.run,self.role,self.guard,self.storage_intent,
            namespace='avatar-sample',schema_prefix='avatarSample',monotonic=monotonic)
        self.previous=self.store.read();self.state=dict(rows=[],pending=None,markerOwner=scope.snapshot())
        if self.previous is not None:self.state=self.decode(self.previous)

    def envelope(self,state):
        return dict(iosAvatarSamplesVersion=VERSION,binding=self.binding,runId=self.run,role=self.role,
            artifactRoot=str(self.root),imagePolicy=self.policy,payload=pack([state]))

    def decode(self,value):
        exact(value,{'iosAvatarSamplesVersion','binding','runId','role','artifactRoot','imagePolicy','payload'})
        rows=unpack(value['payload']);need(len(rows)==1 and same(value,self.envelope(rows[0])));state=rows[0]
        exact(state,{'rows','pending','markerOwner'});need(type(state['rows']) is list and len(state['rows'])<=128 and type(state['markerOwner']) is dict)
        # This original owner can be ready or already retired live; historical
        # image binding always uses its independently retained ready snapshot.
        marker=IOSAvatarMarkerScope.archive(state['markerOwner'],root=self.root,binding=self.binding,run=self.run,
            role=self.role,lock=self.lock,require_ready=True)
        seen=set();frames=set()
        for index,row in enumerate(state['rows'],1):
            exact(row,{'index','requestId','ticket','avatarId','status','original'})
            self.row(row,index);need(row['requestId'] not in seen);seen.add(row['requestId'])
            record=self.read_record(row);need(record['markerSha256']==digest(state['markerOwner']))
            if record['status']!='abandoned':
                frame=record['partial'];identity=frame['capture']['source']['renderTrace']['frameId'];need(identity not in frames);frames.add(identity)
                marker.bind_image_world(frame['worldBefore']);marker.bind_image_world(frame['worldAfter'])
        pending=state['pending']
        if pending is not None:
            self.pending(pending,len(state['rows'])+1);need(pending['requestId'] not in seen)
        return deepcopy(state)

    def row(self,value,index):
        need(type(value['index']) is int and value['index']==index and value['status'] in ('observed','marker-pending','phase-changed','abandoned'))
        self.identity(value);self.originals.expand(value['original']);need(value['original']['index']==index)

    def identity(self,value):
        need(type(value['requestId']) is str and value['requestId'].startswith('ios-'));identifier(value['requestId'][4:]);identifier(value['ticket'])
        if value['avatarId'] is not None:session(value['avatarId'])

    def pending(self,value,index):
        exact(value,{'index','requestId','ticket','avatarId','basisIndex','partial','original','record','abandonedOriginal'})
        self.identity(value);need(type(value['index']) is int and value['index']==index
            and (value['basisIndex'] is None or integer(value['basisIndex'],1,index-1)))
        self.partial(value['partial'],value['ticket'])
        if value['original'] is not None:self.originals.original(value['original']);need(value['original']['index']==index)
        if value['record'] is not None:self.validate_record(value['record'])
        if value['abandonedOriginal'] is not None:
            exact(value['abandonedOriginal'],{'priorOwner','partialFile'});need(type(value['abandonedOriginal']['priorOwner']) is dict)

    def bound(self):
        self.lock.assert_held();need(not self.historical);self.scope.bound();need(self.guard() is not False and same(self.store.read(),self.previous))

    def save(self):
        self.bound();value=self.envelope(self.state);self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value)

    def remember(self,name,value):
        self.bound();p=self.state['pending'];need(p is not None and name in PARTS and name not in p['partial'])
        p['partial'][name]=deepcopy(value);self.save();return value

    def storage_intent(self,kind,value):
        self.bound();p=self.state['pending'];need(p is not None and kind=='original' and p['record'] is not None)
        self.originals.original(value);need(value['index']==p['index']);old=p['original']
        if old is None:need(value['phase']=='planned')
        else:need(value['phase']=={'planned':'opened','opened':'saved'}.get(old['phase'])
            and all(same(value[k],old[k]) for k in value if k not in ('phase','file'))
            and (old['phase']=='planned' or same(value['file'],old['file'])))
        p['original']=deepcopy(value);self.save()

    def partial(self,value,ticket):
        need(type(value) is dict and not value.keys()-set(PARTS))
        # Retirement may be returned even when the actual capture return was
        # lost. All other source reads retain their true sequential prefix.
        for name in value:
            position=PARTS.index(name)
            if name=='retirement':need('renderersBefore' in value);continue
            for prior in PARTS[:position]:
                if prior in ('capture','retirement'):continue
                need(prior in value)
        if 'phaseBefore' in value:
            p=value['phaseBefore'];phase_packet(p,run=self.run,area='avatar-people',request=p['requestId'],epoch=p['capturedEpochMs'])
            need(p['active'] and p['activations'] and p['activations'][-1]['ticket']==ticket)
        if 'nativeStart' in value:
            p=value['nativeStart'];exact(p,{'clockJoinVersion','hostBeforeEpochMs','hostBeforeMonotonic','nativeBefore'})
            need(type(p['clockJoinVersion']) is int and p['clockJoinVersion']==1 and number(p['hostBeforeEpochMs'],1,1e15) and number(p['hostBeforeMonotonic'],0,1e15))
            n=p['nativeBefore'];native_packet(n,n['requestId'],self.pid,n['capturedEpochMs'])
        for name in ('worldBefore','worldAfter'):
            if name in value:
                p=value[name];world.original(p);need(p['runId']==self.run and p['processId']==self.pid)
        for name in ('renderersBefore','renderersAfter'):
            if name in value:
                p=value[name];renderers.original(p);need(p['runId']==self.run and p['processId']==self.pid)
        if 'worldAfter' in value:
            p=value['worldAfter'];world.validate(p,dict(schemaVersion=1,commandId=p['requestId'],action=world.ACTION,runId=self.run),self.pid,previous=value['worldBefore'])
        if 'renderersAfter' in value:
            p=value['renderersAfter'];renderers.validate(p,dict(schemaVersion=1,commandId=p['requestId'],action=renderers.ACTION,runId=self.run),self.pid,previous=value['renderersBefore'])
        if 'capture' in value:
            p=value['capture'];frame_packet(p,dict(schemaVersion=1,action='feature-vulkan-world-frame',operation='read',
                commandId=p['commandId'],requestId=p['requestId']),self.pid,p['capturedEpochMs'])
        if 'retirement' in value:
            p=value['retirement'];storage(p,dict(schemaVersion=1,action='feature-vulkan-world-frame',operation=p['operation'],
                commandId=p['commandId'],requestId=p['requestId']),self.pid,p['capturedEpochMs']);need(absent(p))
        if 'clockJoin' in value:
            frame={key:value[key] for key in images.FIELDS};clock=validate_join(frame['clockJoin'],images.originals(frame))
            need(all(same(value['nativeStart'][key],clock[key]) for key in value['nativeStart']))
            p=value['phaseBefore'];phase_packet(p,run=self.run,area='avatar-people',request=p['requestId'],epoch=clock['hostBeforeEpochMs'])
            need(p['activations'][-1]['activatedEpochMs']<=clock['hostBeforeEpochMs'])
        if 'phaseAfter' in value:
            p=value['phaseAfter'];phase_packet(p,run=self.run,area='avatar-people',request=p['requestId'],epoch=value['clockJoin']['hostAfterEpochMs'],previous=value['phaseBefore'])
        return value

    def validate_record(self,value,depth=0):
        need(integer(depth,0,8))
        exact(value,{'iosAvatarSampleVersion','index','requestId','ticket','avatarId','status','basisIndex','markerSha256','partial','owner','abandonment'})
        need(type(value['iosAvatarSampleVersion']) is int and value['iosAvatarSampleVersion']==VERSION
            and integer(value['index'],1,128) and value['status'] in ('observed','marker-pending','phase-changed','abandoned'))
        self.identity(value);self.partial(value['partial'],value['ticket'])
        need(value['basisIndex'] is None or integer(value['basisIndex'],1,value['index']-1))
        need(type(value['markerSha256']) is str and len(value['markerSha256'])==64)
        if value['status']!='abandoned':
            need(set(value['partial'])==set(PARTS) and value['abandonment'] is None and type(value['owner']) is dict)
            frame=value['partial'];need(same(value['owner']['frame'],frame['capture']) and value['owner']['ticket']==value['ticket']
                and any(same(row['receipt'],frame['retirement']) for row in unpack(value['owner']['transcript'])))
            stable=frame['phaseAfter']['active'] and frame['phaseAfter']['activations'][-1]['ticket']==value['ticket']
            need(value['status']!='observed' or stable);need(value['status']!='phase-changed' or not stable)
        else:self.abandonment(value,depth)
        return value

    def read_record(self,row,*,historical=False):
        originals=self.originals if not historical else OriginalFrameStore(self.root,self.binding,self.run,self.role,lambda:True,lambda *_:need(False),
            namespace='avatar-sample',schema_prefix='avatarSample')
        value=originals.read(originals.expand(row['original']));self.validate_record(value)
        need(all(value[key]==row[key] for key in ('index','requestId','ticket','avatarId','status')));return value

    def gpu_owner(self,pending):
        live=self.runtime._sources(self.selector);need(same(live['binding'],self.binding))
        path=self.store.path.with_name('graphics-world-frame-'+self.role+'-0-'+pending['requestId'][4:]+'.json')
        return VulkanWorldFrameOwner(PrivateFeatureState(path),self.root,self.binding,self.run,self.role,0,pending['requestId'],
            lambda intent,receipt:live['observer'].vulkan_world_frame(intent,receipt),live['check'],source_lock=self.lock,
            monotonic=self.monotonic,sleep=self.sleep)

    def cursors(self):
        result=dict(native=None,world=None,renderers=None)
        for row in self.state['rows']:
            record=self.read_record(row);parts=record['partial']
            if 'nativeStart' in parts:result['native']=parts['nativeStart']['nativeBefore']
            if 'clockJoin' in parts:result['native']=parts['clockJoin']['nativeAfter']
            for source,name in (('world','worldBefore'),('world','worldAfter'),('renderers','renderersBefore'),('renderers','renderersAfter')):
                if name in parts:result[source]=parts[name]
            if record['abandonment'] is not None:result['native']=record['abandonment']['nativeAfter']
        return deepcopy(result)

    def readers(self):
        live=self.runtime._sources(self.selector);need(same(live['binding'],self.binding));observer,clock=live['observer'],live['clock_source']
        floor=self.cursors();native=observer.bound_native_observer(clock);restore_native(native,floor['native'])
        worlds,meshes=observer.avatar_world(clock),observer.avatar_renderers(clock)
        worlds.last,meshes.last=deepcopy(floor['world']),deepcopy(floor['renderers'])
        return native,worlds,meshes

    def finish_record(self,record):
        self.bound();p=self.state['pending'];need(p is not None and record['index']==p['index'])
        self.validate_record(record)
        if p['record'] is None:p['record']=deepcopy(record);self.save()
        else:need(same(p['record'],record))
        if p['original'] is None:original=self.originals.write(p['index'],record)
        else:
            need(p['original']['phase']=='saved');original=self.originals.compact(p['original'])
            need(same(self.originals.read(p['original']),record))
        row={key:deepcopy(record[key]) for key in ('index','requestId','ticket','avatarId','status')};row['original']=original
        self.state['rows'].append(row);self.state['pending']=None;self.save();return deepcopy(row)

    def archive(self,row):
        """Only immutable original files; no SDK, guard, native request or POST."""
        self.lock.assert_held();record=self.read_record(row,historical=True);need(record['status']!='abandoned')
        need(record['markerSha256']==digest(self.state['markerOwner']))
        frame={key:deepcopy(record['partial'][key]) for key in images.FIELDS}
        self.follow(frame,phase_before=record['partial']['phaseBefore'],before_index=record['index'])
        marker=IOSAvatarMarkerScope.archive(self.state['markerOwner'],root=self.root,binding=self.binding,run=self.run,
            role=self.role,lock=self.lock,require_ready=True)
        parts=record['partial'];frame={key:deepcopy(parts[key]) for key in images.FIELDS}
        marker.bind_image_world(frame['worldBefore']);marker.bind_image_world(frame['worldAfter'])
        raw=VulkanWorldFrameOwner.archive_original(record['owner'],self.root,self.binding,self.run,self.role,0,record['requestId'],self.lock)
        basis=None
        if record['basisIndex'] is not None:
            old=self.state['rows'][record['basisIndex']-1];old_frame,old_raw,old_measurement=self.archive(old)
            need(old_measurement is not None and old_measurement['modelLoaded']);basis=(old_frame,old_raw,old['ticket'])
        try:
            measured,_subject=images.compose(self.run,record['ticket'],self.binding,frame,raw,self.policy,
                marker_nonce=marker.state['fileOwnership']['nonce'],marker_url=marker.state['admission']['marker']['sourceUrl'],
                avatar_id=record['avatarId'],absence_basis=basis)
        except MarkerNotReady:need(record['status']=='marker-pending');return frame,raw,None
        need(record['status'] in ('observed','phase-changed'));return frame,raw,measured

    def capture(self,ticket,*,avatar_id=None,absence_basis=None):
        self.bound();identifier(ticket);need(self.state['pending'] is None and len(self.state['rows'])<128 and self.scope.state['phase']=='ready')
        if avatar_id is not None:session(avatar_id)
        need(absence_basis is None or integer(absence_basis,1,len(self.state['rows'])))
        self.state['pending']=dict(index=len(self.state['rows'])+1,requestId='ios-'+uuid.uuid4().hex,ticket=ticket,avatarId=avatar_id,
            basisIndex=absence_basis,partial={},original=None,record=None,abandonedOriginal=None);self.save();p=self.state['pending']
        phase=self.phase.read();need(phase['ticket']==ticket);self.remember('phaseBefore',phase['status'])
        native,worlds,meshes=self.readers();window=NativeClockAcquisition(native,monotonic=self.monotonic,epoch_ms=self.epoch_ms)
        window.begin(phase['afterEpochMs']);self.remember('nativeStart',window.started)
        self.remember('worldBefore',worlds.read(self.run));self.remember('renderersBefore',meshes.read(self.run))
        owner=self.gpu_owner(p);need(owner.store.read() is None)
        try:
            packet,raw=owner.capture(ticket);self.remember('capture',packet)
        finally:
            if owner.store.read() is not None:self.remember('retirement',owner.release())
        self.remember('renderersAfter',meshes.read(self.run));self.remember('worldAfter',worlds.read(self.run))
        frame={key:p['partial'][key] for key in images.FIELDS-{'clockJoin'}};fields=[(name,field) for name,value in frame.items()
            for field in ('capturedEpochMs','sampleEpochMs') if field in value]
        self.remember('clockJoin',window.finish(frame,fields));self.remember('phaseAfter',self.phase.status(phase['status']))
        record=dict(iosAvatarSampleVersion=VERSION,**{key:deepcopy(p[key]) for key in ('index','requestId','ticket','avatarId','basisIndex')},
            status='observed',markerSha256=digest(self.state['markerOwner']),partial=deepcopy(p['partial']),owner=owner.store.read(),abandonment=None)
        marker=self.scope.state['admission']['marker'];basis=None
        if absence_basis is not None:
            old=self.state['rows'][absence_basis-1];old_frame,old_raw,old_result=self.archive(old);need(old_result is not None and old_result['modelLoaded'])
            basis=(old_frame,old_raw,old['ticket'])
        try:images.compose(self.run,ticket,self.binding,dict(frame,clockJoin=p['partial']['clockJoin']),raw,self.policy,
            marker_nonce=self.scope.state['fileOwnership']['nonce'],marker_url=marker['sourceUrl'],avatar_id=avatar_id,absence_basis=basis)
        except MarkerNotReady:record['status']='marker-pending'
        crossed=not p['partial']['phaseAfter']['active'] or p['partial']['phaseAfter']['activations'][-1]['ticket']!=ticket
        if crossed and record['status']=='observed':record['status']='phase-changed'
        self.scope.bind_image_world(frame['worldBefore']);self.scope.bind_image_world(frame['worldAfter'])
        self.follow(dict(frame,clockJoin=p['partial']['clockJoin']),phase_before=p['partial']['phaseBefore'])
        row=self.finish_record(record)
        if crossed:raise AvatarImagePhaseChanged('Original Avatar image acquisition crossed the active phase')
        if record['status']=='marker-pending':raise AvatarImagePending('The original current marker challenge has not painted')
        self.archive(row);self.bound();clock=p['partial']['clockJoin']
        need(number(self.epoch_ms(),clock['hostAfterEpochMs'],clock['hostBeforeEpochMs']+1500)
            and number(self.monotonic(),clock['hostAfterMonotonic'],clock['hostBeforeMonotonic']+1.5))
        return row

    def partial_file(self,original):
        if original is None:return None
        self.originals.original(original);path=self.originals.path(original)
        if original['phase']=='planned':need(not path.exists());return None
        descriptor=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
        with os.fdopen(descriptor,'rb') as stream:
            self.originals.file(path,stream.fileno(),original);raw=stream.read(original['bytes']+1);self.originals.file(path,stream.fileno(),original)
        need(len(raw)<=original['bytes'])
        if original['phase']=='saved':need(len(raw)==original['bytes'] and hashlib.sha256(raw).hexdigest()==original['sha256'])
        return dict(identity=original['file'],bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())

    def frozen_gpu(self,value,request_id):
        class Frozen(PrivateFeatureState):
            def read(_self):return deepcopy(value)
            def write(_self,*_args):need(False)
        path=self.store.path.with_name('graphics-world-frame-'+self.role+'-0-'+request_id[4:]+'.json')
        return VulkanWorldFrameOwner(Frozen(path),self.root,self.binding,self.run,self.role,0,request_id,
            lambda *_:need(False),lambda:True,source_lock=self.lock)

    def abandonment(self,record,depth):
        value=record['abandonment'];exact(value,{'priorOwner','partialFile','owner','retirement','nativeAfter','acquisition'})
        old=value['priorOwner'];exact(old,{'iosAvatarSamplesVersion','binding','runId','role','artifactRoot','imagePolicy','payload'})
        state=unpack(old['payload']);need(len(state)==1 and same(old,self.envelope(state[0])));state=state[0]
        exact(state,{'rows','pending','markerOwner'});need(type(state['rows']) is list and len(state['rows'])==record['index']-1
            and digest(state['markerOwner'])==record['markerSha256'])
        prior=state['pending'];need(type(prior) is dict and all(prior[k]==record[k] for k in ('index','requestId','ticket','avatarId','basisIndex')))
        self.partial(prior['partial'],record['ticket']);need(same(prior['partial'],record['partial']))
        original=prior['original']
        if original is None:need(value['partialFile'] is None)
        else:need(same(value['partialFile'],self.partial_file(original)))
        previous=prior['record']
        if previous is not None:self.validate_record(previous,depth+1)
        native=value['nativeAfter'];native_packet(native,native['requestId'],self.pid,native['capturedEpochMs'])
        floor=record['partial'].get('clockJoin',{}).get('nativeAfter',record['partial'].get('nativeStart',{}).get('nativeBefore'))
        if previous is not None and previous['abandonment'] is not None:floor=previous['abandonment']['nativeAfter']
        if floor is not None:follow_native(floor,native)
        a=value['acquisition'];exact(a,{'hostBeforeEpochMs','hostAfterEpochMs','hostBeforeMonotonic','hostAfterMonotonic'})
        need(number(a['hostBeforeEpochMs'],1,1e15) and number(a['hostAfterEpochMs'],a['hostBeforeEpochMs'],a['hostBeforeEpochMs']+1500)
            and number(a['hostBeforeMonotonic'],0,1e15) and number(a['hostAfterMonotonic'],a['hostBeforeMonotonic'],a['hostBeforeMonotonic']+1.5)
            and abs(a['hostAfterEpochMs']-a['hostBeforeEpochMs']-(a['hostAfterMonotonic']-a['hostBeforeMonotonic'])*1000)<=250)
        floor_host=None
        if previous is not None and previous['abandonment'] is not None:
            floor_host=previous['abandonment']['acquisition']['hostAfterEpochMs']
        elif 'clockJoin' in record['partial']:floor_host=record['partial']['clockJoin']['hostAfterEpochMs']
        elif 'nativeStart' in record['partial']:floor_host=record['partial']['nativeStart']['hostBeforeEpochMs']
        if floor is not None and floor_host is not None:
            need(abs(native['capturedEpochMs']-floor['capturedEpochMs']-(a['hostAfterEpochMs']-floor_host))<=250)
        need(same(value['owner'],record['owner']))
        if value['owner'] is None:need(value['retirement'] is None and 'capture' not in record['partial'])
        else:
            owner=self.frozen_gpu(value['owner'],record['requestId']);owner.verify_owned_artifact()
            need(same(owner.state['absence'],value['retirement']) and value['retirement']['capturedEpochMs']<=native['capturedEpochMs'])
        return True

    def recover(self):
        """Retire one uncertain GPU request; never repeat a read or a release.

        Actually returned partial packets, original failed writer inode and
        native ownership remain in an immutable abandoned sample. Fresh future
        acquisition must continue every recorded source prefix.
        """
        self.bound();p=self.state['pending']
        if p is None:return None
        if p['record'] is not None and p['original'] is not None and p['original']['phase']=='saved':
            return self.finish_record(p['record'])
        if p['abandonedOriginal'] is None or p['record'] is not None:
            p['abandonedOriginal']=dict(priorOwner=deepcopy(self.previous),partialFile=self.partial_file(p['original']))
            p['record']=None;p['original']=None;self.save()
        owner=self.gpu_owner(p);gpu=None;retirement=None
        if owner.store.read() is not None:
            retirement=owner.release();need(absent(retirement));owner.verify_owned_artifact();gpu=owner.store.read()
        # A distinct source read only inspects the actual same process. It
        # cannot create a missing capture, chunk, render frame or phase fact.
        live=self.runtime._sources(self.selector);need(same(live['binding'],self.binding))
        native=live['observer'].bound_native_observer(live['clock_source'])
        old=p['partial'].get('clockJoin',{}).get('nativeAfter',p['partial'].get('nativeStart',{}).get('nativeBefore',self.cursors()['native']))
        prior=unpack(p['abandonedOriginal']['priorOwner']['payload'])[0]['pending']
        if prior['record'] is not None and prior['record']['abandonment'] is not None:old=prior['record']['abandonment']['nativeAfter']
        restore_native(native,old)
        before_epoch,before_mono=self.epoch_ms(),self.monotonic();actual=native.read(native.sequence)
        after_epoch,after_mono=self.epoch_ms(),self.monotonic()
        need(number(after_epoch,before_epoch,before_epoch+1500) and number(after_mono,before_mono,before_mono+1.5))
        if old is not None:follow_native(old,actual)
        abandonment=dict(**p['abandonedOriginal'],owner=gpu,retirement=retirement,nativeAfter=actual,
            acquisition=dict(hostBeforeEpochMs=before_epoch,hostAfterEpochMs=after_epoch,
                hostBeforeMonotonic=before_mono,hostAfterMonotonic=after_mono))
        record=dict(iosAvatarSampleVersion=VERSION,**{key:deepcopy(p[key]) for key in ('index','requestId','ticket','avatarId','basisIndex')},
            status='abandoned',markerSha256=digest(self.state['markerOwner']),partial=deepcopy(p['partial']),owner=gpu,abandonment=abandonment)
        return self.finish_record(record)

    def follow(self,frame,*,phase_before,before_index=None):
        """All earlier actually returned prefixes constrain the new original."""
        self.lock.assert_held()
        for row in self.state['rows']:
            if before_index is not None and row['index']>=before_index:break
            record=self.read_record(row,historical=True);parts=record['partial']
            if 'phaseBefore' in parts:
                floor=parts.get('phaseAfter',parts['phaseBefore'])
                phase_packet(phase_before,run=self.run,area='avatar-people',request=phase_before['requestId'],
                    epoch=frame['clockJoin']['hostBeforeEpochMs'],previous=floor)
            old=parts.get('clockJoin',{}).get('nativeAfter',parts.get('nativeStart',{}).get('nativeBefore'))
            if record['abandonment'] is not None:old=record['abandonment']['nativeAfter']
            if old is not None:follow_native(old,frame['clockJoin']['nativeBefore'])
            if record['owner'] is not None:
                receipts=[item['receipt'] for item in unpack(record['owner']['transcript']) if item['receipt'] is not None]
                if receipts:
                    old_gpu=receipts[-1];old_gpu=old_gpu.get('packet',old_gpu);new_gpu=frame['capture']
                    need(new_gpu['instance']==old_gpu['instance'] and new_gpu['sequence']>old_gpu['sequence']
                        and new_gpu['requestedEpochMs']>=old_gpu['capturedEpochMs'])
                if 'capture' in parts:need(parts['capture']['source']['renderTrace']['frameId']!=frame['capture']['source']['renderTrace']['frameId'])
            for name in ('worldBefore','worldAfter'):
                if name in parts:
                    p=frame['worldBefore'];world.validate(p,dict(schemaVersion=1,commandId=p['requestId'],action=world.ACTION,runId=self.run),
                        self.pid,previous=parts[name])
            for name in ('renderersBefore','renderersAfter'):
                if name in parts:
                    p=frame['renderersBefore'];renderers.validate(p,dict(schemaVersion=1,commandId=p['requestId'],action=renderers.ACTION,runId=self.run),
                        self.pid,previous=parts[name])
        return True

    def drain(self):
        """Resolve uncertain captures and inspect actual retained GPU owners."""
        self.bound();self.recover()
        for row in self.state['rows']:
            record=self.read_record(row)
            if record['owner'] is None:need(record['status']=='abandoned');continue
            owner=self.gpu_owner(row);proof=owner.release();need(absent(proof));owner.verify_owned_artifact()
        return True
