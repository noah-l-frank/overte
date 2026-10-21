"""One role's original restored-world Vulkan image before final process stop.

No fixture marker, feature projection or post-death resource counts are minted.
An unresolved capture remains owned and cannot be replayed by reconstruction.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import time
import uuid

from adapters.native_clock_join import NativeClockAcquisition,digest,validate_join
from adapters.native_feature_observation import exact,need,number,validate as native_packet
from adapters.native_graphics_subject import validate as subject_packet
from adapters.native_scene_loads import validate as loads_packet,continuity,committed
from adapters.native_vulkan_world_frame import validate as capture_packet,storage,absent,original_pixels
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.owned_vulkan_world_frame import VulkanWorldFrameOwner
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from ios.adapters.graphics_history import follow_native,restore_native
from ios.adapters.graphics_scene import restored,eligible,near,rotation_equal
from ios.adapters.graphics_restart_proof import validate as restart_packet

VERSION=1
FIELDS={'subjectBefore','loadsBefore','capture','retirement','subjectAfter','loadsAfter'}


class IOSGraphicsRestoredFrame:
    def __init__(self,adapter,selector,run,role,stage,lock,root,binding,original,floors,graphics,*,
                 epoch_ms=lambda:time.time()*1000,monotonic=time.monotonic):
        need(isinstance(lock,ScriptSourceLock) and role in ('primary','actor') and type(stage) is int and stage in (0,1))
        lock.assert_held();self.adapter,self.selector=adapter,selector
        self.run,self.role,self.stage,self.lock=identifier(run),role,stage,lock
        self.root=Path(root);need(self.root.is_absolute() and self.root.resolve()==self.root and self.root.is_dir())
        PrivateFeatureState(self.root/'graphics-restored-root-check')._parent()
        self.binding,self.original,self.floors,self.graphics=deepcopy(context(binding)),deepcopy(original),deepcopy(floors),deepcopy(graphics)
        self.pid=int(binding['processIdentity']);need(str(self.pid)==binding['processIdentity'] and self.pid>0)
        self.epoch_ms,self.monotonic=epoch_ms,monotonic;need(callable(epoch_ms) and callable(monotonic))
        self.store=PrivateFeatureState(lock.path.with_name('ios-graphics-'+role+'-'+str(stage)+'-restored-frame.json'))
        self.record=PrivateFeatureState(self.root/('graphics-restored-'+run+'-'+role+'-'+str(stage)+'.json'))
        self.previous=self.store.read();self.state=dict(phase='planned',requestId='ios-'+uuid.uuid4().hex,ticket=None,record=None)
        if self.previous is not None:self.state=self.decode(self.previous)
        else:self.save()

    def original_scope(self):
        exact(self.original,{'subject','restart'});old=self.original['subject']
        subject_packet(old,dict(schemaVersion=1,action='feature-graphics-subject-observe',commandId=old['requestId'],runId=self.run),
            old['processId'],old['capturedEpochMs'],require_avatar=True,require_camera=True);eligible(old)
        if self.stage==0:need(self.original['restart'] is None and old['processId']==self.pid and old['instance']==self.floors['native']['instance'])
        else:
            proof=restart_packet(self.original['restart'])
            need(same(proof['input']['newBinding'],self.binding) and old['processId']==proof['oldNative']['processId']
                and old['instance']==proof['oldNative']['instance'] and old['capturedEpochMs']<=proof['oldNative']['requestedEpochMs']
                and proof['input']['ownerFiles']==[str(self.lock.path.with_name(n)) for n in
                    ('ios-graphics-scene.json','ios-graphics-primary-0-samples.json','ios-graphics-actor-0-samples.json')])
            follow_native(proof['native'],self.floors['native'])
        exact(self.floors,{'native','subject','loads'})
        need(all(type(v) is dict and v['processId']==self.pid for v in self.floors.values())
             and same(self.graphics,self.floors['native']['graphics']))
        p=self.floors['native'];native_packet(p,p['requestId'],self.pid,p['capturedEpochMs'])
        p=self.floors['subject'];subject_packet(p,dict(schemaVersion=1,action='feature-graphics-subject-observe',
            commandId=p['requestId'],runId=self.run),self.pid,p['capturedEpochMs'],require_avatar=True,require_camera=True)
        p=self.floors['loads'];loads_packet(p,dict(schemaVersion=1,action='feature-scene-load-observe',
            commandId=p['commandId'],runId=self.run),self.pid,p['capturedEpochMs']);need(p['complete'])

    def envelope(self,state):
        return dict(iosGraphicsRestoredFrameVersion=VERSION,runId=self.run,role=self.role,stage=self.stage,
            binding=self.binding,artifactRoot=str(self.root),payload=pack([dict(original=self.original,floors=self.floors,graphics=self.graphics,state=state)]))

    def decode(self,value):
        exact(value,{'iosGraphicsRestoredFrameVersion','runId','role','stage','binding','artifactRoot','payload'})
        rows=unpack(value['payload']);need(len(rows)==1)
        exact(rows[0],{'original','floors','graphics','state'});state=rows[0]['state']
        need(type(value['iosGraphicsRestoredFrameVersion']) is int and type(value['stage']) is int and same(value,self.envelope(state)))
        exact(state,{'phase','requestId','ticket','record'});identifier(state['requestId'][4:]);need(state['requestId'].startswith('ios-')
            and state['phase'] in ('planned','reading','ready'))
        self.original_scope()
        if state['phase']=='planned':need(state['ticket'] is None)
        else:identifier(state['ticket'])
        if state['phase']=='ready':
            need(type(state['record']) is str and len(state['record'])==64)
            self.validate_record(self.record.read(),state)
        else:need(state['record'] is None)
        return state

    def save(self):
        self.lock.assert_held();need(same(self.store.read(),self.previous))
        value=self.envelope(self.state);self.decode(value);self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value)

    def owner(self):
        return self.adapter._vulkan_world_frame_owner(self.selector,self.run,self.role,self.stage,
            self.state['requestId'],self.root,source_lock=self.lock)

    def validate_record(self,value,state=None):
        state=self.state if state is None else state
        exact(value,{'iosGraphicsRestoredRecordVersion','scopeSha256','requestId','payload'})
        need(type(value['iosGraphicsRestoredRecordVersion']) is int and value['iosGraphicsRestoredRecordVersion']==VERSION
             and value['scopeSha256']==digest(self.envelope(dict(phase='reading',requestId=state['requestId'],ticket=state['ticket'],record=None)))
             and value['requestId']==state['requestId'] and (state['record'] is None or digest(value)==state['record']))
        rows=unpack(value['payload']);need(len(rows)==1);row=rows[0];exact(row,FIELDS|{'clockJoin','owner'})
        packets={key:row[key] for key in FIELDS};clock=validate_join(row['clockJoin'],packets);epoch=clock['nativeAfter']['capturedEpochMs']
        before,after=clock['nativeBefore'],clock['nativeAfter'];follow_native(self.floors['native'],before);follow_native(before,after)
        need(before['processId']==self.pid and same(before['graphics'],self.graphics) and same(after['graphics'],self.graphics)
            and same(before['lifecycle'],after['lifecycle']))
        old=self.floors['subject']
        for key in ('subjectBefore','subjectAfter'):
            packet=row[key];subject_packet(packet,dict(schemaVersion=1,action='feature-graphics-subject-observe',
                commandId=packet['requestId'],runId=self.run),self.pid,epoch,require_avatar=True,require_camera=True)
            need(packet['instance']==old['instance']==before['instance'] and packet['sequence']>old['sequence']
                 and packet['requestedEpochMs']>=old['capturedEpochMs'] and packet['requestId']!=old['requestId'])
            restored(self.original['subject'],packet);old=packet
        old=self.floors['loads']
        for key in ('loadsBefore','loadsAfter'):
            packet=row[key];loads_packet(packet,dict(schemaVersion=1,action='feature-scene-load-observe',commandId=packet['commandId'],runId=self.run),self.pid,epoch)
            need(packet['complete']);continuity(old,packet,self.pid);committed(packet,row['subjectBefore']['source']['sceneUrl']);old=packet
        frame,release=row['capture'],row['retirement'];query=dict(schemaVersion=1,action='feature-vulkan-world-frame',operation='read',
            commandId=frame['commandId'],requestId=state['requestId'])
        capture_packet(frame,query,self.pid,epoch);storage(release,dict(query,operation=release['operation'],commandId=release['commandId']),self.pid,epoch)
        need(absent(release) and release['instance']==frame['instance'] and release['sequence']>frame['sequence'])
        raw=VulkanWorldFrameOwner.archive_original(row['owner'],self.root,self.binding,self.run,self.role,self.stage,state['requestId'],self.lock)
        need(same(row['owner']['frame'],frame) and same(row['owner']['absence'],release) and row['owner']['ticket']==state['ticket']);original_pixels(frame,raw)
        live=row['subjectBefore']['source']['view'];source=frame['source'];trace=source['renderTrace'];view=trace['recordedView']
        need(near(view['position'],live['position'],.001) and rotation_equal(view['rotation'],live['rotation'],.0001)
             and near(view['fieldOfViewDegrees'],live['fieldOfViewDegrees'],.001) and near(view['aspectRatio'],live['aspectRatio'],.0001)
             and near(live['aspectRatio'],source['targetExtent'][0]/source['targetExtent'][1],.01))
        ordered=[before['capturedEpochMs'],row['subjectBefore']['requestedEpochMs'],row['subjectBefore']['capturedEpochMs'],
            row['loadsBefore']['capturedEpochMs'],frame['requestedEpochMs'],trace['recordedEpochMs'],
            source['submittedEpochMs'],source['fenceObservedEpochMs'],source['pixelsReadEpochMs'],frame['capturedEpochMs'],
            release['requestedEpochMs'],release['capturedEpochMs'],row['subjectAfter']['requestedEpochMs'],row['subjectAfter']['capturedEpochMs'],
            row['loadsAfter']['capturedEpochMs'],after['requestedEpochMs'],after['capturedEpochMs']]
        need(ordered==sorted(ordered));return deepcopy(row),raw

    def capture(self,ticket):
        self.lock.assert_held();identifier(ticket);need(same(self.store.read(),self.previous))
        # A committed immutable record is recoverable; an unknown acquisition is
        # never repeated. Returning an archive does not grant a new current fact.
        if self.state['phase']!='planned':need(self.state['ticket']==ticket)
        if self.state['phase']=='ready':return self.validate_record(self.record.read())
        if self.state['phase']=='reading':
            value=self.record.read();self.validate_record(value)
            self.state.update(phase='ready',record=digest(value));self.save();return self.validate_record(value)
        need(self.state['phase']=='planned' and self.record.read() is None);self.state.update(phase='reading',ticket=ticket);self.save()
        native=self.adapter._native_feature_observer(self.selector,read_only=True);restore_native(native,self.floors['native'])
        subject=self.adapter._graphics_subject_observer(self.selector,read_only=True);subject.last=deepcopy(self.floors['subject'])
        loads=self.adapter._scene_load_observer(self.selector,read_only=True);loads.last=deepcopy(self.floors['loads'])
        window=NativeClockAcquisition(native,epoch_ms=self.epoch_ms,monotonic=self.monotonic);window.begin(self.epoch_ms())
        row={};owner=self.owner();need(owner.store.read() is None)
        row['subjectBefore']=subject.read(self.run,require_avatar=True,require_camera=True);row['loadsBefore']=loads.read(self.run)
        try:row['capture'],_raw=owner.capture(ticket)
        finally:
            if owner.store.read() is not None:row['retirement']=owner.release()
        row['subjectAfter']=subject.read(self.run,require_avatar=True,require_camera=True);row['loadsAfter']=loads.read(self.run)
        row['clockJoin']=window.finish(row,[(key,'capturedEpochMs') for key in row]);row['owner']=owner.store.read()
        value=dict(iosGraphicsRestoredRecordVersion=VERSION,scopeSha256=digest(self.previous),requestId=self.state['requestId'],payload=pack([row]))
        self.validate_record(value);self.record.write(value,None);need(same(self.record.read(),value))
        self.state.update(phase='ready',record=digest(value));self.save()
        result=self.validate_record(value);clock=row['clockJoin'];now,epoch=self.monotonic(),self.epoch_ms()
        need(number(now,clock['hostAfterMonotonic'],clock['hostBeforeMonotonic']+1.5) and now-clock['hostBeforeMonotonic']<1.5
             and number(epoch,clock['hostAfterEpochMs'],clock['hostBeforeEpochMs']+1500) and epoch-clock['hostBeforeEpochMs']<1500
             and abs(epoch-clock['hostBeforeEpochMs']-(now-clock['hostBeforeMonotonic'])*1000)<=250)
        return result

    @classmethod
    def archive(cls,value,record,*,path,lock,root,run,role,stage,binding,original,floors,graphics):
        """Pure validation from exact originals, after runtime metadata removal."""
        scope=object.__new__(cls);scope.run,scope.role,scope.stage,scope.lock=identifier(run),role,stage,lock
        need(isinstance(lock,ScriptSourceLock) and role in ('primary','actor') and type(stage) is int and stage in (0,1));lock.assert_held()
        scope.root=Path(root);scope.store=PrivateFeatureState(path)
        need(scope.root.is_absolute() and scope.root.resolve()==scope.root and scope.root.is_dir()
             and scope.store.path==lock.path.with_name('ios-graphics-'+role+'-'+str(stage)+'-restored-frame.json'))
        scope.binding,scope.original,scope.floors,scope.graphics=deepcopy(context(binding)),deepcopy(original),deepcopy(floors),deepcopy(graphics)
        scope.pid=int(binding['processIdentity']);need(str(scope.pid)==binding['processIdentity'] and scope.pid>0)
        scope.record=type('Original',(),{'read':lambda _:deepcopy(record)})();scope.state=scope.decode(value)
        need(scope.state['phase']=='ready');return scope.validate_record(record)
