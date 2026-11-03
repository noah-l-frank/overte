"""Declared GUI-clock/remote-commit model around the ORIGINAL normal Parent.

Samples advance only on the modeled native GUI clock, never on a Host getter
or requested pose. This does not execute the new uncompiled Qt publisher.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import hashlib
import json
from pathlib import Path
import shlex
import struct
import subprocess
import tempfile
from types import SimpleNamespace
from unittest.mock import patch
import uuid

from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4 import joint_interpolation
from adapters.pico4.emote_stream_cycle import PicoEmoteStreamCycle
from adapters.pico4 import emote_stream_wire
from adapters.script_journey.lock import ScriptSourceLock
from feature_journeys.phase_fixture import PhaseFixtureReader
from self_tests.test_native_avatar_render import avatar_source
from self_tests.test_pico_emote_native_cycle import CycleBoundary
from self_tests.test_pico_emote_model_draws import ModelBoundary
from self_tests.test_pico_emote_sources import RUN

PRIMARY='11111111-1111-4111-8111-111111111111'
ACTOR='22222222-2222-4222-8222-222222222222'
DOMAIN='33333333-3333-4333-8333-333333333333'


def committed_pose(subject,epoch,sequence,position):
    """Same existing explicit remote committed-wire/interpolation leaf model."""
    raw=bytes([1,1,0xbf,0xff,0xbf,0xff,0x3f,0xff,1])+struct.pack('<fhhh',1.,*(round(v*16384) for v in position))
    received=dict(kind='joint-data',sequence=sequence,subjectSessionId=subject['sessionId'],jointCount=1,
        parsedEpochMs=epoch-5,committedEpochMs=epoch-4,parseTimestampUs=(epoch-5)*1000,
        bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),base64=base64.b64encode(raw).decode())
    q=joint_interpolation.wire_value(received,0,0);p=joint_interpolation.wire_value(received,0,1)
    q=[struct.unpack('>f',struct.pack('>f',v))[0] for v in q]
    channels=[[struct.pack('>f',v).hex() for v in q],[struct.pack('>f',v).hex() for v in p],False,False]
    nodes=[dict(id=c+1,joint=0,channel=c,op='wire',value=deepcopy(value),parents=[],source=sequence,detail={})
        for c,value in enumerate(channels)]
    for c in range(2):nodes.append(dict(id=c+5,joint=0,channel=c,op='interpolate',value=deepcopy(channels[c]),
        parents=[c+1,c+1],source=None,detail=dict(thetaBits='3f800000')))
    pose=dict(remoteJointPoseVersion=2,instance=('7' if subject['sessionId']==PRIMARY else '6')*32,
        copySequence=sequence,copiedSequence=sequence,externalSequence=sequence,subjectSessionId=subject['sessionId'],
        avatarInstance=subject['avatarInstance'],modelInstance=subject['modelInstance'],rigId=subject['rigId'],
        geometryInstance=subject['geometry']['instance'],available=True,inputJointCount=1,skeletonJointCount=1,
        begunEpochMs=epoch-3,copiedEpochMs=epoch-2,capturedEpochMs=epoch-1,
        relativeJoints=[q+p],joints=[q+p],received=dict(jointData=received,defaultFlags=None),
        interpolation=dict(jointInterpolationVersion=1,available=True,assignmentPending=False,failure='',nowUs=epoch*1000,
            historyResets=1,historyAppends=sequence,historyPrunes=0,roots=[[5,6,3,4]],nodes=nodes,sections=[deepcopy(received)],
            selection=[dict(joint=0,mode='newest-clamp',historySize=1,historyStart=0,oldIndex=0,newIndex=0,
                oldTimeUs=epoch*1000-1000,newTimeUs=epoch*1000-1000,latencyUs=0,timePointUs=epoch*1000,
                thetaBits='3f800000',old=[1,2,3,4],new=[1,2,3,4],output=[5,6,3,4])]),
        rigInput=dict(inputs=[channels],rotationZeroThreshold=1e-6,rigToGeometryRotation=[0.,0.,0.,1.],
            decisions=[dict(joint=0,parent=-1,rotationChoice='rig-input',absoluteRotation=q,defaultRotation=[0.,0.,0.,1.],
                translationChoice='rig-input',relativeRotation=q,translation=p,defaultTranslation=[0.,0.,0.])]))
    offset=sequence*10
    for node in nodes:node['id']+=offset;node['parents']=[parent+offset for parent in node['parents']]
    pose['interpolation']['roots']=[[node+offset for node in row] for row in pose['interpolation']['roots']]
    for row in pose['interpolation']['selection']:
        for field in ('old','new','output'):row[field]=[node+offset for node in row[field]]
    return pose


class NativeStreamModel:
    def __init__(self,owner,role):
        self.owner=owner;self.role=role;self.pid=31 if role=='primary' else 32;self.offset=0 if role=='primary' else 1000
        self.self_id=PRIMARY if role=='primary' else ACTOR;self.subject_id=ACTOR if role=='primary' else PRIMARY
        self.root=Path(tempfile.mkdtemp(prefix='pico-emote-stream4-native-'+role+'-'))
        (self.root/'files').mkdir(mode=0o700);(self.root/'files/overte-e2e').mkdir(mode=0o700)
        self.sample=self.root/'files/overte-e2e/feature-pico-remote-avatar-stream.json'
        self.ack=self.sample.with_name('feature-pico-remote-avatar-stream-control.json')
        self.controls=[];self.issued=self.published=0;self.used=False;self.stopped=self.drained=False
        self.unavailable=False;self.arm_original=None
        self.timer=self.deadline_timer=False;self.pending_timers=0;self.deadline=self.next_epoch=None
        self.policy_sha=self.stream=self.arm=None;self.due_calls=self.getters=0;self.fault=None
        self.render=ModelBoundary();self.native=SimpleNamespace(send=self.send,clock_ms=self.epoch,guard=lambda:True)

    def epoch(self):return self.owner.m.s.epoch+self.offset
    def write(self,path,raw):
        with path.open('wb') as output:output.write(raw)
        path.chmod(0o600)
    def client(self,session,epoch):
        return dict(requestedEpochMs=epoch,capturedEpochMs=epoch,identity=dict(domainId=DOMAIN,sessionId=session,connected=True,
            domainSession=dict(domainSessionVersion=1,instance=('9' if session==PRIMARY else '8')*32,revision=1,connected=True,
                domainSha256=hashlib.sha256((RUN+':').encode()+uuid.UUID(DOMAIN).bytes).hexdigest(),
                connectionBirth=('7' if session==PRIMARY else '6')*32,connectedEpochMs=10000)))
    def snapshot(self,epoch):
        visual=avatar_source();subject={key:deepcopy(value) for key,value in visual.items()
            if key in ('modelInstance','rigId','loaded','visible','addedToScene','avatarShouldRender','geometry','pose')}
        subject.update(sessionId=self.subject_id,avatarInstance=('5' if self.role=='primary' else '4')*32,rig={})
        position=[.1,.2,.3]
        # The Actor receives the actual committed modeled Rig pose AFTER the
        # original normal input/effect producer; no Emote name is requested.
        if self.role=='actor' and self.owner.m.frames:position=self.owner.m.frames[-1]['joints'][0]['pose'][4:]
        subject['remoteJointPose']=committed_pose(subject,epoch,self.issued,position)
        return dict(picoRemoteAvatarVersion=4,runId=RUN,clientBefore=self.client(self.self_id,epoch),
            clientAfter=self.client(self.self_id,epoch),selfSessionId=self.self_id,subjectSessionId=self.subject_id,
            subject=subject,worldRenderInstance=('3' if self.role=='primary' else '4')*32,cameraMode='third person',
            view=deepcopy(self.render.capture['source']['renderTrace']['recordedView']))
    def due(self):
        self.due_calls+=1;now=self.epoch()
        if not self.timer:return
        if now>=self.deadline or self.issued>=256:self.stop();return
        if now<self.next_epoch:return
        self.next_epoch=now+500;self.issued+=1
        value=dict(schemaVersion=1,picoRemoteAvatarStreamFrameVersion=4,streamId=self.stream,sampleSequence=self.issued,
            processId=self.pid,requestedEpochMs=now,capturedEpochMs=now,ownerPolicySha256=self.policy_sha,source=self.snapshot(now))
        self.write(self.sample,json.dumps(value,separators=(',',':')).encode());self.published=self.issued
    def stop(self):
        self.timer=self.deadline_timer=False;self.stopped=True;self.pending_timers=2
    def event_loop_turn(self):self.pending_timers=0
    def send(self,request):
        self.native.phase_fence.check();self.controls.append(deepcopy(request));operation=request['operation'];now=self.epoch()
        if operation=='arm':
            assert not self.used and not self.sample.exists();self.used=True;self.arm=request['commandId']
            policy=json.loads(request['ownerPolicy']);assert policy['processId']==self.pid
            assert policy['originalNativeEpochMs']<=now<policy['deadlineNativeEpochMs']<=policy['originalNativeEpochMs']+120000
            self.deadline=policy['deadlineNativeEpochMs'];self.policy_sha=hashlib.sha256(request['ownerPolicy'].encode()).hexdigest()
            self.stream=('a' if self.role=='primary' else 'b')*32;self.timer=self.deadline_timer=True;self.next_epoch=now;self.due()
            def node(info):return [str(field) for field in (info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_nlink)]
            info=self.sample.stat();body=self.sample.read_bytes()
            self.arm_original=dict(rootNode=node(self.sample.parent.stat()),sampleNode=node(info),
                sampleStamp=node(info)+[str(info.st_size),str(info.st_mtime_ns),str(info.st_ctime_ns)],
                sha256=hashlib.sha256(body).hexdigest(),bytes=len(body),sampleSequence=self.published)
        elif operation=='stop':self.stop()
        else:
            if not self.stopped or self.pending_timers:self.unavailable=True
            else:self.drained=True
        reply=dict(schemaVersion=1,picoRemoteAvatarStreamControlVersion=4,requestId=request['commandId'],available=not self.unavailable,
            processId=self.pid,requestedEpochMs=now,capturedEpochMs=self.epoch(),runId=RUN,streamId=self.stream,
            armCommandId=self.arm,ownerPolicySha256=self.policy_sha,nativeFrameLimit=256,sampleIntervalMs=500,
            issuedFrames=self.issued,publishedFrames=self.published,timerActive=self.timer,deadlineTimerActive=self.deadline_timer,
            controlCount=len(self.controls),pendingTimerObjects=self.pending_timers,nativeQueueQuiet=True,inFlightTick=False,
            stopped=self.stopped,drained=self.drained,pendingWrite=False,armOriginal=deepcopy(self.arm_original))
        self.write(self.ack,json.dumps(reply,separators=(',',':')).encode())
        if self.fault=='lost-arm':raise OSError('Declared actual ARM return lost')
    def execute_bytes(self,arguments,*,target,timeout):
        assert target==self.role+'-model' and arguments[0]=='exec-out';argv=shlex.split(arguments[1])
        assert argv[:4]==['run-as','org.overte.pico','sh','-c'] and argv[4] in emote_stream_wire.SCRIPTS.values()
        self.getters+=1
        completed=subprocess.run(['sh','-c',argv[4],*argv[5:]],cwd=self.root,stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,timeout=timeout,check=False)
        return completed.stdout


class StreamCycleModel:
    def __init__(self):
        original=tempfile.TemporaryDirectory
        def retained(*args,**options):
            value=original(*args,**options);value._finalizer.detach();value.cleanup=lambda:None;return value
        with patch('self_tests.test_pico_emote_sources.tempfile.TemporaryDirectory',side_effect=retained):self.m=CycleBoundary()
        # Pin original normal source context; this does not overwrite a packet.
        from self_tests.test_pico_emote_sources import BINDING
        self.m.s.owner_binding=deepcopy(BINDING);self.streams={};self.cycle=None
        for role in ('primary','actor'):self.streams[role]=NativeStreamModel(self,role)
        self.actor_root=Path(tempfile.mkdtemp(prefix='pico-emote-stream4-actor-owner-'))
        self.actor_lock=ScriptSourceLock(self.actor_root/'script-sources.lock')
        self.roots=[self.m.s.root,self.actor_root,*[model.root for model in self.streams.values()]]
        tick=self.m.tick
        def native_tick(ms):
            tick(ms)
            for model in self.streams.values():model.due()
        self.m.tick=native_tick
        self.parent=None;self.roles={}
    def create(self):
        self.parent=self.m.owner()
        for role,model in self.streams.items():
            binding=deepcopy(self.parent.source.binding)
            if role=='actor':binding.update(processIdentity='32:original',targetFingerprint='e'*64,sessionId=ACTOR)
            root=self.m.s.root if role=='primary' else self.actor_root
            adapter=SimpleNamespace(kind='pico',profile=dict(package='org.overte.pico'),
                _avatar_parent_store=lambda target,run,root=root:PrivateFeatureState(root/('avatar-parent-owner-'+run+'.json')),
                adb=SimpleNamespace(execute_bytes=model.execute_bytes))
            phase=self.parent.source.phase if role=='primary' else PhaseFixtureReader(self.parent.source.phase.client,RUN,'emotes',
                epoch_ms=lambda:self.m.s.epoch,monotonic=lambda:self.m.s.clock)
            self.roles[role]=dict(adapter=adapter,target=role+'-model',native=model.native,binding=binding,phase=phase,
                lock=self.m.s.lock if role=='primary' else self.actor_lock,subject=model.subject_id)
        self.cycle=PicoEmoteStreamCycle(self.parent,self.roles);return self.cycle
    def close(self):
        if self.cycle is not None:self.cycle.close_host()
        self.m.close()
