"""Durable per-role original Graphics samples; no input or public verdict.

Each acquisition owns a new original Vulkan PNG and an immutable sample file.
An interrupted acquisition cannot be retried by recreating this component.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import time
import uuid

from adapters.native_clock_join import NativeClockAcquisition,digest
from adapters.native_feature_observation import exact,integer,need,number,validate as native_packet
from adapters.native_graphics_subject import validate as subject_packet
from adapters.native_vulkan_world_frame import absent,validate as capture_packet
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from adapters.script_feature.ui_source import validate as tablet_packet
from feature_journeys.contract import identifier
from feature_journeys.evidence import MarkerNotReady
from ios.adapters.graphics_fixture import GraphicsFixtureReader,GraphicsPhasePending
from ios.adapters.graphics_history import restore_native
from ios.adapters.graphics_source import validate as graphics_packet
from ios.adapters.graphics_world_measurements import compose,originals
from ios.adapters.login_source import nonce

VERSION=1
CURSORS={'native','subject','graphics','tablet','capture','retirement','provider'}


class GraphicsMarkerPending(NativeUIError):
    """A fully retained original image does not yet contain the current marker."""


def restore_ui(reader,previous,validator):
    if previous is None:return
    validator(previous,previous['commandId'],reader.pid,previous['capturedEpochMs'])
    need(reader.instance is None and reader.generation is None and reader.sequence==0)
    reader.instance,reader.generation=previous['instance'],previous['generation']
    reader.sequence,reader.elapsed=previous['sourceSequence'],previous['elapsedMs']
    reader.last_command=previous['lastCommandSequence']
    if hasattr(reader,'epoch_floor'):reader.epoch_floor=previous['capturedEpochMs']
    else:reader.captured_epoch=previous['capturedEpochMs']


class IOSGraphicsSamples:
    def __init__(self,adapter,selector,client,run,role,stage,lock,artifact_root,image_policy,*,
                 cleanup_only=False,epoch_ms=lambda:time.time()*1000,monotonic=time.monotonic):
        need(role in ('primary','actor') and type(stage) is int and stage in (0,1)
             and isinstance(lock,ScriptSourceLock) and type(cleanup_only) is bool
             and callable(epoch_ms) and callable(monotonic) and type(image_policy) is dict
             and image_policy.get('source')=='world-render-target')
        identifier(run);lock.assert_held()
        self.adapter,self.selector,self.run,self.role,self.stage=adapter,selector,run,role,stage
        self.lock,self.root,self.policy=lock,Path(artifact_root),deepcopy(image_policy)
        need(self.root.is_absolute() and self.root.is_dir() and self.root==self.root.resolve())
        PrivateFeatureState(self.root/'graphics-artifact-root-check')._parent()
        self.epoch_ms,self.monotonic,self.cleanup_only=epoch_ms,monotonic,cleanup_only
        self.fixture=GraphicsFixtureReader(client,run,epoch_ms=epoch_ms);self.fixture.attach()
        identifier(self.fixture.instance);self.client,self.instance=client,self.fixture.instance
        self.store=adapter.graphics_samples_store(selector,role,stage)
        need(isinstance(self.store,PrivateFeatureState) and lock.path==self.store.path.with_name('script-feature-sources.lock'))
        _ui,_service,binding,self.guard,_installed=adapter.normal_feature_runtime(selector,read_only=True)
        self.binding=deepcopy(context(binding));self.pid=int(binding['processIdentity']);need(str(self.pid)==binding['processIdentity'])
        self.previous=self.store.read()
        self.state=dict(binding=self.binding,phase='ready',sequence=0,cursors={key:None for key in CURSORS},owners=[],seenFrames=[])
        if self.previous is not None:self.state=self.decode(self.previous)
        need(cleanup_only or self.state['phase']=='ready')
        if self.previous is not None and self.state['phase']=='ready' and self.state['owners']:
            frames=[self.record(row)[1] for row in self.state['owners']]
            need(self.state['seenFrames']==[frame['capture']['source']['renderTrace']['frameId'] for frame in frames])
            last=frames[-1];expected={key:last[field] for key,field in (('subject','subjectAfter'),('graphics','graphics'),
                ('tablet','tablet'),('capture','capture'),('retirement','retirement'),('provider','provider'))}
            expected['native']=last['clockJoin']['nativeAfter'];need(same(expected,self.state['cursors']))

    def envelope(self,state):
        return dict(iosGraphicsSamplesVersion=VERSION,runId=self.run,role=self.role,stage=self.stage,
            providerInstance=self.instance,fixtureUrl=self.client.url,artifactRoot=str(self.root),imagePolicy=self.policy,payload=pack([state]))

    def decode(self,value):
        exact(value,{'iosGraphicsSamplesVersion','runId','role','stage','providerInstance','fixtureUrl','artifactRoot','imagePolicy','payload'})
        rows=unpack(value['payload']);need(len(rows)==1 and same(value,self.envelope(rows[0])))
        state=rows[0];exact(state,{'binding','phase','sequence','cursors','owners','seenFrames'})
        need(same(state['binding'],self.binding) and state['phase'] in ('ready','reading')
             and integer(state['sequence'],0,512) and type(state['owners']) is list and len(state['owners'])<=512
             and type(state['seenFrames']) is list and len(state['seenFrames'])<=512
             and len(set(state['seenFrames']))==len(state['seenFrames']))
        for frame in state['seenFrames']:identifier(frame)
        seen=set();published=0
        for index,row in enumerate(state['owners']):
            exact(row,{'requestId','ticket','phase','sampleSha256'})
            nonce(row['requestId']);identifier(row['ticket']);need(row['requestId'] not in seen);seen.add(row['requestId'])
            need(row['phase'] in ('reserved','observed','marker-pending'))
            if row['phase']=='reserved':need(state['phase']=='reading' and index==len(state['owners'])-1 and row['sampleSha256'] is None)
            else:
                need(type(row['sampleSha256']) is str and len(row['sampleSha256'])==64)
                if row['phase']=='observed':published+=1
        need(published==state['sequence'] and (state['phase']!='reading' or bool(state['owners'])))
        self.validate_cursors(state['cursors'])
        if not state['owners']:need(not state['seenFrames'] and state['sequence']==0 and all(v is None for v in state['cursors'].values()))
        return state

    def validate_cursors(self,cursors):
        exact(cursors,CURSORS)
        if cursors['native'] is not None:
            p=cursors['native'];nonce(p['requestId']);native_packet(p,p['requestId'],self.pid,p['capturedEpochMs'])
        if cursors['subject'] is not None:
            p=cursors['subject'];subject_packet(p,dict(schemaVersion=1,action='feature-graphics-subject-observe',
                commandId=p['requestId'],runId=self.run),self.pid,p['capturedEpochMs'],require_avatar=True,require_camera=True)
        for key,validator in (('graphics',graphics_packet),('tablet',tablet_packet)):
            p=cursors[key]
            if p is not None:validator(p,p['commandId'],self.pid,p['capturedEpochMs'])
        if cursors['capture'] is not None:
            p=cursors['capture'];capture_packet(p,dict(schemaVersion=1,action='feature-vulkan-world-frame',operation='read',
                commandId=p['commandId'],requestId=p['requestId']),self.pid,p['capturedEpochMs'])
        if cursors['retirement'] is not None:need(absent(cursors['retirement']))
        if cursors['provider'] is not None:
            from feature_journeys.graphics_resources import validate_status
            p=cursors['provider'];validate_status(p,instance=self.instance,run=self.run,url=self.client.url,request=p['requestId'])

    def bound(self):
        self.lock.assert_held();need(self.guard() is not False and same(self.store.read(),self.previous))

    def save(self):
        self.bound();value=self.envelope(self.state);self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value);self.bound()

    def remember(self,key,value):
        old=self.state['cursors'][key]
        if old is not None:
            if key=='provider':
                from feature_journeys.graphics_resources import validate_status
                validate_status(value,instance=self.instance,run=self.run,url=self.client.url,request=value['requestId'],previous=old)
            else:
                sequence='sourceSequence' if key in ('graphics','tablet') else 'sequence'
                need(value['instance']==old['instance'] and value[sequence]>old[sequence]
                     and value['capturedEpochMs']>=old['capturedEpochMs'])
        self.state['cursors'][key]=deepcopy(value);self.save()

    def owner(self,row):
        owner=self.adapter._vulkan_world_frame_owner(self.selector,self.run,self.role,self.stage,row['requestId'],self.root,source_lock=self.lock)
        need(owner.store.path==self.store.path.with_name('graphics-world-frame-'+self.role+'-'+str(self.stage)+'-'+row['requestId'][4:]+'.json'))
        return owner

    def sample_store(self,row):
        return PrivateFeatureState(self.store.path.with_name('ios-graphics-'+self.role+'-'+str(self.stage)+'-'+row['requestId'][4:]+'-sample.json'))

    def record(self,row):
        need(row['phase']!='reserved')
        value=self.sample_store(row).read();exact(value,{'iosGraphicsSamplesVersion','binding','runId','role','stage','requestId','ticket','afterEpochMs','payload'})
        need(value['iosGraphicsSamplesVersion']==VERSION and type(value['iosGraphicsSamplesVersion']) is int
             and same(value['binding'],self.binding) and value['runId']==self.run and value['role']==self.role
             and type(value['stage']) is int and value['stage']==self.stage and value['requestId']==row['requestId']
             and value['ticket']==row['ticket'] and digest(value)==row['sampleSha256'])
        frames=unpack(value['payload']);need(len(frames)==1)
        return value,frames[0]

    def archive(self,row):
        """Historical originals only; never a fresh observation or repair."""
        self.bound();need(any(same(row,item) for item in self.state['owners']))
        value,frame=self.record(row);owner=self.owner(row);raw=owner.archive();stored=owner.state
        need(same(stored['frame'],frame['capture']) and stored['phase']=='released'
             and any(same(event['receipt'],frame['retirement']) for event in owner.events)
             and frame['capture']['source']['renderTrace']['frameId'] in self.state['seenFrames'])
        try:
            result=compose(self.run,row['ticket'],self.fixture.fixture_url,self.binding,frame,raw,self.policy,
                           provider_instance=self.instance,after_epoch=value['afterEpochMs'])
        except MarkerNotReady:
            need(row['phase']=='marker-pending');result=None
        else:need(row['phase']=='observed')
        self.bound();return deepcopy(frame),raw,deepcopy(result)

    def read(self,ticket,after_epoch):
        identifier(ticket);need(integer(after_epoch,1) and not self.cleanup_only and self.state['phase']=='ready'
                                and len(self.state['owners'])<512 and self.state['sequence']<512)
        self.bound();phase=self.fixture.read(self.state['cursors']['provider']);need(phase['ticket']==ticket)
        native=self.adapter._native_feature_observer(self.selector,read_only=True);restore_native(native,self.state['cursors']['native'])
        subject=self.adapter._graphics_subject_observer(self.selector,read_only=True);subject.last=deepcopy(self.state['cursors']['subject'])
        graphics=self.adapter._graphics_ui_source(self.selector,read_only=True);restore_ui(graphics,self.state['cursors']['graphics'],graphics_packet)
        tablet=self.adapter._script_file_io(self.selector,read_only=True);restore_ui(tablet,self.state['cursors']['tablet'],tablet_packet)
        row=dict(requestId='ios-'+uuid.uuid4().hex,ticket=ticket,phase='reserved',sampleSha256=None)
        self.state['phase']='reading';self.state['owners'].append(row);self.save()
        owner=self.owner(row);need(owner.store.read() is None and self.sample_store(row).read() is None)
        window=NativeClockAcquisition(native,epoch_ms=self.epoch_ms,monotonic=self.monotonic);window.begin(after_epoch)
        frame={}
        try:
            frame['nativeBefore']=native.read(native.sequence);self.remember('native',frame['nativeBefore'])
            frame['subjectBefore']=subject.read(self.run,require_avatar=True,require_camera=True);self.remember('subject',frame['subjectBefore'])
            frame['graphics']=graphics.capture();self.remember('graphics',frame['graphics'])
            frame['tablet']=tablet.capture();self.remember('tablet',frame['tablet'])
            frame['capture'],raw=owner.capture(ticket);self.remember('capture',frame['capture'])
            identity=frame['capture']['source']['renderTrace']['frameId'];need(identity not in self.state['seenFrames'])
            self.state['seenFrames'].append(identity);self.save()
        finally:
            if owner.store.read() is not None:
                frame['retirement']=owner.release();self.remember('retirement',frame['retirement'])
        frame['subjectAfter']=subject.read(self.run,require_avatar=True,require_camera=True);self.remember('subject',frame['subjectAfter'])
        frame['nativeAfter']=native.read(native.sequence);self.remember('native',frame['nativeAfter'])
        frame['provider']=self.fixture.status(phase['status']);self.remember('provider',frame['provider'])
        if not frame['provider']['active'] or frame['provider']['ticket']!=ticket:
            raise GraphicsPhasePending('Graphics phase changed; durable acquisition responsibility is retained')
        packets=originals(frame);fields=[(name,field) for name,p in packets.items() for field in ('capturedEpochMs','sampleEpochMs') if field in p]
        frame['clockJoin']=window.finish(packets,fields);self.remember('native',frame['clockJoin']['nativeAfter'])
        missing=False
        try:result=compose(self.run,ticket,self.fixture.fixture_url,self.binding,frame,raw,self.policy,provider_instance=self.instance,after_epoch=after_epoch)
        except MarkerNotReady:missing=True
        sample=dict(iosGraphicsSamplesVersion=VERSION,binding=self.binding,runId=self.run,role=self.role,stage=self.stage,
                    requestId=row['requestId'],ticket=ticket,afterEpochMs=after_epoch,payload=pack([frame]))
        self.sample_store(row).write(sample,None);need(same(self.sample_store(row).read(),sample) and owner.archive()==raw)
        row.update(phase='marker-pending' if missing else 'observed',sampleSha256=digest(sample))
        self.state.update(phase='ready',sequence=self.state['sequence']+(0 if missing else 1));self.save()
        ended,epoch=self.monotonic(),self.epoch_ms();start=frame['clockJoin']
        need(number(ended,start['hostBeforeMonotonic'],start['hostBeforeMonotonic']+1.5) and ended-start['hostBeforeMonotonic']<1.5
             and number(epoch,start['hostAfterEpochMs'],start['hostBeforeEpochMs']+1500)
             and epoch-start['hostBeforeEpochMs']<1500 and abs(epoch-start['hostBeforeEpochMs']-(ended-start['hostBeforeMonotonic'])*1000)<=250)
        self.bound()
        if missing:raise GraphicsMarkerPending('Original current Graphics marker is not yet rendered')
        return deepcopy(dict(sequence=self.state['sequence'],imagePath=str(self.root/owner.name),**result))

    def drain(self):
        """Fresh actual native absence; does not retire metadata or prove quiet."""
        self.bound();proofs=[]
        for row in self.state['owners']:
            owner=self.owner(row)
            if owner.store.read() is not None:
                proof=owner.release();need(absent(proof));proofs.append(proof)
            else:need(row['phase']=='reserved' and not (self.root/owner.name).exists())
            self.bound()
        return deepcopy(proofs)
