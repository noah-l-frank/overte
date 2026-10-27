"""One primary Assets image attempt with actual original/GPU child ownership.

Draft composition: no public capability or actor receipt is provided. Every
native response is retained before parsing; an interrupted attempt is never
silently captured again. The current GPU child remains a separate obligation.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
import time
from adapters.native_clock_join import NativeClockAcquisition,validate_join
from adapters.native_feature_observation import NativeFeatureObservation,decode,exact,integer,need,validate as native_packet
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.original_frame_store import OriginalFrameStore
from adapters.owned_vulkan_world_frame import VulkanWorldFrameOwner
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from ios.adapters import assets_model_images as images,assets_model_renderers,avatar_renderers,create_state
from ios.adapters.assets_budget import operation
from ios.adapters.assets_image_basis import marker_original,parsed_original
from ios.adapters.assets_marker_owner import OwnedAssetsMarker
from ios.adapters.assets_model_raw_sources import ModelRawSources
from ios.adapters.assets_model_sources import AssetsModelSources
from ios.adapters.assets_parsed_owner import OwnedAssetsParsedInput
from ios.adapters.graphics_history import follow_native

VERSION=1
BODY={'requestId','ticket','hostBarrier','start','originals','clockJoin','frameOwnership','parsedSnapshot','markerSnapshot','queries','rawRefs'}


class ImageRawSources(ModelRawSources):
    NAMESPACE='assets-image-native'
    SCHEMA_PREFIX='iosAssetsImageRawSource'
    MIGRATION_PREFIX='assets-image-native-migration-'
    RECORD_KEY='iosAssetsImageRawSourceRecordVersion'
    MIGRATION_KEY='iosAssetsImageRawSourceMigrationVersion'


class AssetsImageSample:
    def __init__(self,store,lock,binding,run,request_id,guard,*,parsed,marker,native,state,models,avatars,frame_owner,
                 epoch_ms=lambda:time.time()*1000,monotonic=time.monotonic):
        need(isinstance(store,PrivateFeatureState) and isinstance(lock,ScriptSourceLock) and callable(guard)
            and isinstance(parsed,OwnedAssetsParsedInput) and isinstance(marker,OwnedAssetsMarker)
            and isinstance(native,NativeFeatureObservation) and native.ios and native.native_clock_bound
            and isinstance(state,create_state.IOSCreateState) and isinstance(models,assets_model_renderers.IOSAssetsModelRenderers)
            and isinstance(avatars,avatar_renderers.IOSAvatarRenderers) and isinstance(frame_owner,VulkanWorldFrameOwner)
            and callable(epoch_ms) and callable(monotonic))
        self.store,self.lock,self.binding,self.run,self.role=store,lock,deepcopy(context(binding)),identifier(run),'primary'
        need(type(request_id) is str and request_id.startswith('ios-'));identifier(request_id[4:])
        self.request,self.guard,self.native,self.parsed,self.marker=request_id,guard,native,parsed,marker
        self.readers=dict(create=state,models=models,avatars=avatars);self.frame_owner=frame_owner
        self.epoch_ms,self.monotonic=epoch_ms,monotonic;self.pid=int(binding['processIdentity']);self.active=False
        need(store.path.name=='ios-assets-image-'+run+'-primary-'+request_id[4:]+'.json'
            and lock.path==store.path.with_name('script-feature-sources.lock') and parsed.lock is marker.lock is frame_owner.lock is lock
            and all(reader.pid==self.pid for reader in (native,state,models,avatars))
            and same(parsed.sources.binding,binding) and same(marker.scope.binding,binding)
            and parsed.sources.run==marker.run==frame_owner.run==run and parsed.sources.role==marker.role==frame_owner.role=='primary'
            and same(frame_owner.binding,binding) and frame_owner.request_id==request_id and frame_owner.stage==0
            and parsed.store.path.parent==marker.store.path.parent==frame_owner.store.path.parent==store.path.parent
            and frame_owner.store.path.name=='graphics-world-frame-primary-0-'+request_id[4:]+'.json')
        lock.assert_held();self.previous=store.read();self.state=None
        self.raws=ImageRawSources(self,'primary',self.local_guard,self.save)
        self.frames=OriginalFrameStore(store.path.parent,binding,run,'primary',self.local_guard,self.intent,
            namespace='assets-image-source',schema_prefix='iosAssetsImageSource',monotonic=monotonic)
        self.originals=self.frames
        if self.previous is not None:self.state=self.decode(self.previous)

    def local_guard(self):self.lock.assert_held();PrivateFeatureState(self.store.path)._parent();return True
    def check(self):
        self.local_guard();need(self.guard() is not False and same(self.store.read(),self.previous));return True
    def module(self,kind):
        need(kind in ('create','models','avatars'));return {'create':create_state,'models':assets_model_renderers,'avatars':avatar_renderers}[kind]
    def query(self,row):
        exact(row,{'kind','command'})
        if row['kind']=='clock':
            exact(row['command'],{'schemaVersion','action','commandId'});need(type(row['command']['schemaVersion']) is int and row['command']['schemaVersion']==1
                and row['command']['action']=='feature-native-observe' and type(row['command']['commandId']) is str
                and re.fullmatch('ios-[a-f0-9]{32}',row['command']['commandId']))
        else:self.module(row['kind']).command(row['command'])
    def envelope(self):
        self.state['rawSources']=self.raws.manifest()
        return dict(iosAssetsImageOwnerVersion=VERSION,binding=self.binding,runId=self.run,role='primary',requestId=self.request,payload=pack([self.state]))
    def body(self,state):return {key:deepcopy(state[key]) for key in BODY}
    def intent(self,kind,reference):
        need(kind=='original' and self.state is not None and self.state['phase']=='reading' and reference['index']==1)
        self.state['original']=deepcopy(reference);self.save();return True
    def save(self):
        self.check();value=self.envelope();self.decode(value);self.store.write(value,self.previous);self.previous=deepcopy(value)

    def source_frame(self,state):
        frame=dict(state['originals'],clockJoin=state['clockJoin']);exact(frame,images.FIELDS)
        join=validate_join(state['clockJoin'],images.originals(frame));records=[self.raws.read_record(ref) for ref in state['rawRefs']]
        clocks=[];external=[]
        for row in state['queries']:
            query=row['command'];matches=[record['raw'] for record in records if same(record['query'],query)
                and decode(record['raw'],limit=262144).get('requestId')==query['commandId']]
            need(matches and all(raw==matches[0] for raw in matches));packet=decode(matches[0],limit=262144)
            if row['kind']=='clock':native_packet(packet,query['commandId'],self.pid,packet['capturedEpochMs']);clocks.append(packet)
            else:self.module(row['kind']).validate(packet,query,self.pid);external.append(packet)
        need(same(external,[state['originals'][key] for key in ('createBefore','modelsBefore','avatarsBefore','avatarsAfter','modelsAfter','createAfter')])
            and len(clocks)>=2 and same(clocks[0],join['nativeBefore']) and same(clocks[-1],join['nativeAfter']))
        for before,after in zip(clocks,clocks[1:]):follow_native(before,after)
        raw=VulkanWorldFrameOwner.archive_original(state['frameOwnership'],self.frame_owner.root,self.binding,self.run,'primary',0,self.request,self.lock)
        need(same(state['frameOwnership']['frame'],state['originals']['capture']) and same(state['frameOwnership']['absence'],state['originals']['retirement']))
        return frame,raw

    def decode(self,value):
        exact(value,{'iosAssetsImageOwnerVersion','binding','runId','role','requestId','payload'})
        need(type(value['iosAssetsImageOwnerVersion']) is int and value['iosAssetsImageOwnerVersion']==VERSION
            and same(value['binding'],self.binding) and value['runId']==self.run and value['role']=='primary' and value['requestId']==self.request)
        rows=unpack(value['payload']);need(len(rows)==1);state=rows[0]
        exact(state,BODY|{'phase','rawSources','original','originalSnapshot','gpuStarted','qualificationInputs','qualification'})
        need(state['phase'] in ('reading','captured','qualified','failed') and state['requestId']==self.request and type(state['gpuStarted']) is bool
            and type(state['originals']) is dict and set(state['originals'])<=images.FIELDS-{'clockJoin'}
            and type(state['queries']) is list and len(state['queries'])<=24 and type(state['rawRefs']) is list and len(state['rawRefs'])<=24)
        identifier(state['ticket']);self.raws.load(state['rawSources']);seen=set()
        for row in state['queries']:
            self.query(row);need(row['command']['commandId'] not in seen);seen.add(row['command']['commandId'])
        need(same(state['rawRefs'],self.raws.refs))
        for reference in state['rawRefs']:
            record=self.raws.read_record(reference);need(record['kind']=='native' and any(same(record['query'],row['command']) for row in state['queries']))
        if self.raws.pending is not None:need(self.raws.pending['queryId'] in seen and state['phase']=='reading')
        if state['original'] is not None:
            self.frames.original(state['original']);need(state['original']['index']==1)
            actual=AssetsModelSources.prefix(self,state['original'])
            if state['originalSnapshot'] is not None:need(same(actual,state['originalSnapshot']))
        else:need(state['originalSnapshot'] is None)
        if state['phase']!='reading':
            need(state['gpuStarted'] and state['original'] is not None and state['original']['phase']=='saved'
                and same(self.frames.read(state['original']),self.body(state)))
            self.source_frame(state)
        if state['phase']=='qualified':
            need(state['qualificationInputs'] is not None and same(state['qualification'],self.measure(state)))
        return state

    def remember(self,name,value):
        need(self.state['phase']=='reading' and name not in self.state['originals']);self.state['originals'][name]=deepcopy(value);self.save()

    @operation
    def capture(self,ticket,host_barrier):
        self.check();need(self.state is None and not self.active and integer(host_barrier,1));identifier(ticket)
        need(self.parsed.state is not None and self.parsed.state['phase']=='observed'
            and self.marker.state is not None and self.marker.state['phase']=='ready'
            and self.frame_owner.store.read() is None and not (self.frame_owner.root/self.frame_owner.name).exists()
            and not (self.frame_owner.root/self.frame_owner.name).is_symlink())
        self.parsed.guard();self.parsed.authoritative();self.marker.guard()
        parsed_original(self.parsed,self.parsed.previous);marker_original(self.marker,self.marker.previous)
        self.state=dict(phase='reading',requestId=self.request,ticket=ticket,hostBarrier=host_barrier,start=None,originals={},clockJoin=None,frameOwnership=None,
            parsedSnapshot=deepcopy(self.parsed.previous),markerSnapshot=deepcopy(self.marker.previous),queries=[],rawRefs=[],rawSources=self.raws.manifest(),
            original=None,originalSnapshot=None,gpuStarted=False,qualificationInputs=None,qualification=None);self.save();wrappers=[];self.active=True
        for kind,reader in [('clock',self.native),*self.readers.items()]:
            old_send,old_original=reader.send,reader.original;wrappers.append((reader,old_send,old_original))
            def send(query,kind=kind,old_send=old_send):
                need(len(self.state['queries'])<24);self.state['queries'].append(dict(kind=kind,command=deepcopy(query)));self.save();return old_send(query)
            def read(kind=kind,old_original=old_original):
                raw=old_original()
                if raw:
                    matches=[row for row in self.state['queries'] if row['kind']==kind];need(matches and len(self.state['rawRefs'])<24)
                    self.raws.capture(matches[-1]['command'],raw);self.raws.accept_capture();self.state['rawRefs'].append(deepcopy(self.raws.refs[-1]));self.save()
                return raw
            reader.send,reader.original=send,read
        try:
            clock=NativeClockAcquisition(self.native,epoch_ms=self.epoch_ms,monotonic=self.monotonic);clock.begin(host_barrier)
            self.state['start']=deepcopy(clock.started);self.save()
            for key,kind in (('createBefore','create'),('modelsBefore','models'),('avatarsBefore','avatars')):self.remember(key,self.readers[kind].read(self.run))
            self.state['gpuStarted']=True;self.save();capture,_raw=self.frame_owner.capture(ticket);self.remember('capture',capture)
            self.remember('retirement',self.frame_owner.release())
            for key,kind in (('avatarsAfter','avatars'),('modelsAfter','models'),('createAfter','create')):self.remember(key,self.readers[kind].read(self.run))
            self.state['clockJoin']=clock.finish(self.state['originals'],[(key,'capturedEpochMs') for key in ('capture','retirement')])
            self.state['frameOwnership']=deepcopy(self.frame_owner.store.read());self.save();self.frames.write(1,self.body(self.state))
            self.state['phase']='captured';self.save();return deepcopy(dict(self.state['originals'],clockJoin=self.state['clockJoin']))
        except BaseException as primary:
            if self.state['original'] is not None:
                try:self.state['originalSnapshot']=AssetsModelSources.prefix(self,self.state['original']);self.save()
                except BaseException as secondary:primary.add_note('Retaining Assets image source prefix also failed: '+type(secondary).__name__)
            raise
        finally:
            self.active=False
            for reader,send,original in wrappers:reader.send,reader.original=send,original

    @operation
    def recover_completed_capture(self):
        self.check();need(not self.active and self.state is not None and self.state['phase']=='reading' and self.raws.pending is None
            and self.state['original'] is not None and self.state['original']['phase']=='saved'
            and same(self.frames.read(self.state['original']),self.body(self.state)))
        self.source_frame(self.state);self.state['phase']='captured';self.save()

    def measure(self,state):
        inputs=state['qualificationInputs'];exact(inputs,{'policy'})
        frame,raw=self.source_frame(state);proof=parsed_original(self.parsed,state['parsedSnapshot']);mark=marker_original(self.marker,state['markerSnapshot'])
        observed,_subject=images.compose(self.run,state['ticket'],self.binding,frame,raw,inputs['policy'],proof,mark,after_epoch=state['hostBarrier'])
        return observed

    @operation
    def qualify(self,policy):
        self.check();need(self.state is not None and self.state['phase']=='captured');self.state['qualificationInputs']=dict(policy=deepcopy(policy));self.save()
        try:result=self.measure(self.state)
        except BaseException as primary:
            self.state['phase']='failed'
            try:self.save()
            except BaseException as secondary:primary.add_note('Retaining failed Assets image also failed: '+type(secondary).__name__)
            raise
        self.state.update(phase='qualified',qualification=deepcopy(result));self.save();return result

    @operation
    def retire_runtime(self):
        self.check();need(self.state is not None and not self.active)
        if self.frame_owner.store.read() is not None:return self.frame_owner.release()
        need(not self.state['gpuStarted']);return None
