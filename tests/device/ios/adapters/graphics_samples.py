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

from adapters.native_clock_join import NativeClockAcquisition,digest,validate_join
from adapters.native_feature_observation import exact,integer,need,number,validate as native_packet
from adapters.native_graphics_subject import validate as subject_packet
from adapters.native_vulkan_world_frame import absent,validate as capture_packet
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.owned_vulkan_world_frame import VulkanWorldFrameOwner
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

VERSION=2
READS=(1,2)
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
        self.epoch_ms,self.monotonic,self.cleanup_only=epoch_ms,monotonic,cleanup_only;self.historical=False
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
        self.ready_history()

    def ready_history(self):
        if self.previous is not None and self.state['phase']=='ready' and self.state['owners']:
            records=[self.record(row)[1] for row in self.state['owners']];seen=[]
            for record in records:
                capture=record['capture']
                if capture is not None:
                    identity=capture['source']['renderTrace']['frameId']
                    if identity not in seen:seen.append(identity)
            need(self.state['seenFrames']==seen)
            last=records[-1]
            if self.state['owners'][-1]['phase']=='abandoned':expected=last['cursors']
            else:
                expected={key:last[field] for key,field in (('subject','subjectAfter'),('graphics','graphics'),
                    ('tablet','tablet'),('capture','capture'),('retirement','retirement'),('provider','provider'))}
                expected['native']=last['clockJoin']['nativeAfter']
            need(same(expected,self.state['cursors']))

    @classmethod
    def archive_index(cls,value,*,adapter,selector,client,run,role,stage,lock,binding,artifact_root,image_policy):
        """Validate retained old-process sources/files without SDK admission.

        This cannot construct a usable live reader, issue a native command or
        authorize new-process input. The exact old index must remain owned.
        """
        need(isinstance(lock,ScriptSourceLock) and role in ('primary','actor') and type(stage) is int and stage in (0,1))
        lock.assert_held();identifier(run);scope=object.__new__(cls)
        scope.adapter,scope.selector,scope.run,scope.role,scope.stage=adapter,selector,run,role,stage
        scope.lock,scope.root,scope.policy=lock,Path(artifact_root),deepcopy(image_policy)
        need(scope.root.is_absolute() and scope.root.is_dir() and scope.root.resolve()==scope.root)
        PrivateFeatureState(scope.root/'graphics-artifact-root-check')._parent()
        scope.client=client;scope.fixture=GraphicsFixtureReader(client,run);scope.fixture.attach()
        scope.instance=scope.fixture.instance;identifier(scope.instance)
        scope.store=adapter.graphics_samples_store(selector,role,stage)
        need(lock.path==scope.store.path.with_name('script-feature-sources.lock'))
        scope.binding=deepcopy(context(binding));scope.pid=int(binding['processIdentity'])
        need(str(scope.pid)==binding['processIdentity'])
        scope.historical=scope.cleanup_only=True;scope.guard=lambda:True;scope.previous=deepcopy(value)
        scope.bound();scope.state=scope.decode(value);need(scope.state['phase']=='ready');scope.ready_history()
        for row in scope.state['owners']:
            if row['phase']!='abandoned':scope.archive(row)
            else:
                _value,proof=scope.record(row);owner=scope.owner(row)
                if owner.store.read() is None:
                    need(proof['capture'] is None and proof['retirement'] is None)
                    try:(scope.root/owner.name).lstat()
                    except FileNotFoundError:pass
                    else:need(False)
                else:
                    owner.verify_owned_artifact()
                    need(same(owner.state['frame'],proof['capture'])
                         and any(same(event['receipt'],proof['retirement']) for event in owner.events))
        scope.bound();return deepcopy(scope.state)

    def envelope(self,state):
        return dict(iosGraphicsSamplesVersion=VERSION,runId=self.run,role=self.role,stage=self.stage,
            providerInstance=self.instance,fixtureUrl=self.client.url,artifactRoot=str(self.root),imagePolicy=self.policy,payload=pack([state]))

    def decode(self,value):
        exact(value,{'iosGraphicsSamplesVersion','runId','role','stage','providerInstance','fixtureUrl','artifactRoot','imagePolicy','payload'})
        rows=unpack(value['payload']);version=value['iosGraphicsSamplesVersion']
        need(type(version) is int and version in READS and len(rows)==1
             and same(value,self.envelope(rows[0])|dict(iosGraphicsSamplesVersion=version)))
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
            need(row['phase'] in ('reserved','observed','marker-pending','abandoned') and (version>=2 or row['phase']!='abandoned'))
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
        path=self.store.path.with_name('graphics-world-frame-'+self.role+'-'+str(self.stage)+'-'+row['requestId'][4:]+'.json')
        if self.historical:
            owner=VulkanWorldFrameOwner(PrivateFeatureState(path),self.root,self.binding,self.run,self.role,self.stage,
                row['requestId'],lambda *_:need(False),lambda:True,source_lock=self.lock)
        else:owner=self.adapter._vulkan_world_frame_owner(self.selector,self.run,self.role,self.stage,row['requestId'],self.root,source_lock=self.lock)
        need(owner.store.path==path)
        return owner

    def sample_store(self,row):
        return PrivateFeatureState(self.store.path.with_name('ios-graphics-'+self.role+'-'+str(self.stage)+'-'+row['requestId'][4:]+'-sample.json'))

    def absent_artifact(self,owner):
        try:(self.root/owner.name).lstat()
        except FileNotFoundError:return True
        need(False)

    def record(self,row):
        need(row['phase']!='reserved')
        value=self.sample_store(row).read();exact(value,{'iosGraphicsSamplesVersion','binding','runId','role','stage','requestId','ticket','afterEpochMs','payload'})
        need(type(value['iosGraphicsSamplesVersion']) is int and value['iosGraphicsSamplesVersion'] in READS
             and same(value['binding'],self.binding) and value['runId']==self.run and value['role']==self.role
             and type(value['stage']) is int and value['stage']==self.stage and value['requestId']==row['requestId']
             and value['ticket']==row['ticket'] and digest(value)==row['sampleSha256'])
        frames=unpack(value['payload']);need(len(frames)==1)
        if row['phase']=='abandoned':
            need(value['iosGraphicsSamplesVersion']>=2);self.validate_abandonment(row,frames[0])
        return value,frames[0]

    def validate_abandonment(self,row,proof):
        from feature_journeys.graphics_resources import validate_status
        exact(proof,{'native','retirement','capture','clockJoin','phase','provider','cursors'})
        self.fixture.active(proof['phase']);need(proof['phase']['ticket']!=row['ticket'])
        provider=proof['provider'];validate_status(provider,instance=self.instance,run=self.run,url=self.client.url,request=provider['requestId'])
        need(provider['active'] and provider['ticket']==proof['phase']['ticket'])
        packets={'native':proof['native']}
        native_packet(proof['native'],nonce(proof['native']['requestId']),self.pid,proof['native']['capturedEpochMs'])
        if proof['retirement'] is not None:
            need(absent(proof['retirement']) and proof['retirement']['requestId']==row['requestId']
                 and proof['retirement']['processId']==self.pid);packets['retirement']=proof['retirement']
        capture=proof['capture']
        if capture is not None:
            capture_packet(capture,dict(schemaVersion=1,action='feature-vulkan-world-frame',operation='read',
                commandId=capture['commandId'],requestId=row['requestId']),self.pid,capture['capturedEpochMs'])
            need(proof['retirement'] is not None and capture['instance']==proof['retirement']['instance'])
        clock=validate_join(proof['clockJoin'],packets);self.validate_cursors(proof['cursors'])
        need(clock['nativeBefore']['processId']==self.pid
             and clock['nativeBefore']['instance']==proof['native']['instance']
             and clock['nativeBefore']['sequence']<proof['native']['sequence']<clock['nativeAfter']['sequence']
             and clock['hostBeforeEpochMs']<=provider['capturedEpochMs']<=clock['hostAfterEpochMs']
             and provider['activations'][-1]['activatedEpochMs']<=clock['hostBeforeEpochMs'])
        need(same(proof['cursors']['native'],proof['clockJoin']['nativeAfter'])
             and same(proof['cursors']['provider'],provider)
             and (proof['retirement'] is None or same(proof['cursors']['retirement'],proof['retirement'])))

    def archive(self,row):
        """Historical originals only; never a fresh observation or repair."""
        self.bound();need(row['phase']!='abandoned' and any(same(row,item) for item in self.state['owners']))
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
        identifier(ticket);need(integer(after_epoch,1) and not self.historical and not self.cleanup_only and self.state['phase']=='ready'
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
        self.finish_window(frame['clockJoin'])
        self.bound()
        if missing:raise GraphicsMarkerPending('Original current Graphics marker is not yet rendered')
        return deepcopy(dict(sequence=self.state['sequence'],imagePath=str(self.root/owner.name),**result))

    def finish_window(self,start):
        ended,epoch=self.monotonic(),self.epoch_ms()
        need(number(ended,start['hostBeforeMonotonic'],start['hostBeforeMonotonic']+1.5) and ended-start['hostBeforeMonotonic']<1.5
             and number(epoch,start['hostAfterEpochMs'],start['hostBeforeEpochMs']+1500)
             and epoch-start['hostBeforeEpochMs']<1500 and abs(epoch-start['hostBeforeEpochMs']-(ended-start['hostBeforeMonotonic'])*1000)<=250)
        self.bound()

    def retire_crossed_phase(self):
        """Retire an old acquisition after a separately observed phase change.

        This publishes no image or product fact. Unknown commands are released
        once, original callbacks/buffers must actually drain, and all original
        files/transcripts remain owned. No native capture is replayed.
        """
        self.bound();need(not self.historical and self.state['phase']=='reading' and self.state['owners'][-1]['phase']=='reserved')
        row=self.state['owners'][-1];phase=self.fixture.read(self.state['cursors']['provider'])
        need(phase['ticket']!=row['ticket'] and self.sample_store(row).read() is None)
        reader=self.adapter._native_feature_observer(self.selector,read_only=True);restore_native(reader,self.state['cursors']['native'])
        window=NativeClockAcquisition(reader,epoch_ms=self.epoch_ms,monotonic=self.monotonic);window.begin(phase['afterEpochMs'])
        native=reader.read(reader.sequence);self.remember('native',native)
        owner=self.owner(row);retirement=capture=None
        if owner.store.read() is not None:
            retirement=owner.release();self.remember('retirement',retirement);capture=deepcopy(owner.state['frame'])
        else:self.absent_artifact(owner)
        provider=self.fixture.status(phase['status']);need(provider['active'] and provider['ticket']==phase['ticket'])
        self.remember('provider',provider)
        packets={'native':native}
        if retirement is not None:packets['retirement']=retirement
        clock=window.finish(packets,[(key,'capturedEpochMs') for key in packets]);self.remember('native',clock['nativeAfter'])
        proof=dict(native=native,retirement=retirement,capture=capture,clockJoin=clock,phase=dict(schemaVersion=1,
            runId=self.run,area='graphics',ticket=phase['ticket'],stimulus=dict(verb=phase['verb'],inputs=phase['inputs'])),
            provider=provider,cursors=deepcopy(self.state['cursors']))
        self.validate_abandonment(row,proof)
        if capture is not None:
            identity=capture['source']['renderTrace']['frameId']
            if identity not in self.state['seenFrames']:self.state['seenFrames'].append(identity)
        value=dict(iosGraphicsSamplesVersion=VERSION,binding=self.binding,runId=self.run,role=self.role,stage=self.stage,
            requestId=row['requestId'],ticket=row['ticket'],afterEpochMs=phase['afterEpochMs'],payload=pack([proof]))
        self.sample_store(row).write(value,None);need(same(self.sample_store(row).read(),value))
        row.update(phase='abandoned',sampleSha256=digest(value));self.state['phase']='ready';self.save();self.bound()
        self.finish_window(clock)
        return deepcopy(proof) # Retirement originals only, never a feature observation.

    def drain(self):
        """Fresh actual native absence; does not retire metadata or prove quiet."""
        self.bound();need(not self.historical);proofs=[]
        for row in self.state['owners']:
            owner=self.owner(row)
            if owner.store.read() is not None:
                proof=owner.release();need(absent(proof));proofs.append(proof)
            else:need(row['phase']=='reserved');self.absent_artifact(owner)
            self.bound()
        return deepcopy(proofs)
