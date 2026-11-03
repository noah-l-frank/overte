"""Existing GPU/storage/receipt owners at declared fresh native producers.

No GL, Qt, OpenXR, device or Domain executes. Fresh producer clocks are read
at the actual modeled operation, before its original file/packet is emitted;
no old returned observation is retimed or relabelled.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import json
import shlex
import subprocess
from types import SimpleNamespace
import uuid

from adapters.normal_feature_state import PrivateFeatureState
from adapters.owned_world_render import WorldRenderOwner
from adapters.pico4.emote_model_draws import PicoWorldModelDraws,command as model_command,FILE as MODEL_FILE
from adapters.pico4.emote_stream_cycle import PicoEmoteStreamCycle
from adapters.pico4.emote_stream_model_raw import SCRIPT as MODEL_SCRIPT
from adapters.pico4.emote_stream_world_raw import script as world_script
from adapters.pico4.graphics_binding import SerializedWorldCapture
from adapters.world_render_evidence import NativeWorldRenderCapture,image_name,FILE as WORLD_FILE
from adapters.world_render_storage import NativeWorldRenderStorage,receipt_file,command as storage_command
from adapters.world_render_receipts import NativeWorldReceiptInventory,NativeWorldReceiptBatchFiles,INVENTORY_FILE
from feature_journeys.phase_fixture import PhaseFixtureReader
from self_tests.pico_emote_stream_fixture import StreamCycleModel,ACTOR,RUN
from self_tests.test_stereo_camera_uniforms import CameraBoundary
from self_tests.test_stereo_world_render import identity
from self_tests.test_native_avatar_render import MODEL,GEOMETRY,LOADED
from self_tests.test_world_render_receipt_inventory import Boundary as InventoryBoundary


class FreshRenderer(CameraBoundary):
    def __init__(self,clock,work,root):
        super().__init__();self.epoch=clock;self.work=work;self.root=root;self.instance=uuid.uuid4().hex
        projection=identity();projection[10]=-1.01;projection[11]=-1;projection[14]=-.2;projection[15]=0
        self.recorded=dict(position=[0,0,0],rotation=[0,0,0,1],projection=[projection[column*4+row]
            for row in range(4) for column in range(4)],fieldOfViewDegrees=90,aspectRatio=4/3,nearClip=.1,farClip=100,perspective=True)

    def send(self,command):
        assert self.intents and self.intents[-1]==command
        self.commands.append(deepcopy(command))
        if self.ignore:return
        requested=self.epoch();self.work(100);captured=self.epoch();self.sequence+=1;self.acquisition+=1
        self.frame+=1;self.execution+=1;self.submission+=1;self.uniform_sequence+=3
        eyes=[];batches=[]
        for index in range(2):
            projection=identity();projection[10]=-1.01;projection[11]=-1;projection[14]=-.2;projection[15]=0
            offset=identity();offset[12]=-.032 if index==0 else .032
            eyes.append(dict(eye=('left','right')[index],projection=projection,viewOffset=offset,
                sourceViewport=[index*4,0,4,6],targetViewport=[index*8,0,8,12]))
        for index,draws in enumerate((5,7,4)):
            cameras=[]
            for eye in range(2):
                view=identity();view[12]=.032 if eye==0 else -.032;view[14]=.1
                projection=deepcopy(eyes[eye]['projection']);projection[8]=.02
                cameras.append(dict(slot=0,eye=('left','right')[eye],view=view,projection=projection,
                    viewport=[0,0,8,6],drawViewport=[4*eye,0,4,6],stereoInfo=[1,eye,1/8,1/6],drawCommands=draws))
            batches.append(dict(sequence=self.uniform_sequence+index,frameIndex=self.frame,executionSequence=self.execution,
                rawDrawCommands=draws,executedDrawCommands=draws,role='mirror' if index==2 else 'forward',technique='doubled',cameras=cameras))
        source=dict(captureVersion=4,available=True,acquisitionSequence=self.acquisition,recordedEpochMs=requested,
            startedEpochMs=captured,capturedEpochMs=captured,backend='opengl',stage='tone-map-before-hud',view='main-stereo',
            sourceExtent=[16,12],sourceViewport=[0,0,8,6],targetExtent=[16,12],pixelFormat='rgba8-top-left',
            image=dict(name=image_name(command['commandId']),bytes=len(self.raw),sha256=hashlib.sha256(self.raw).hexdigest(),
                pixelSha256=self.pixels,width=16,height=12),
            stereo=dict(frameIndex=self.frame,executionSequence=self.execution,layout='side-by-side',matrixLayout='column-major',
                cameraView=identity(),eyes=eyes),
            presentation=dict(backend='openxr',frameIndex=self.frame,submissionSequence=self.submission,submittedEpochMs=captured,
                views=[dict(eye=name,imageRect=[0,0,8,12],arrayIndex=0) for name in ('left','right')]),
            renderTrace=dict(traceVersion=4,frameId=uuid.uuid4().hex,frameIndex=self.frame,executionSequence=self.execution,
                recordedEpochMs=requested,recordedView=deepcopy(self.recorded),begunEpochMs=requested,completedEpochMs=captured,
                renderer='forward',view='main-stereo',forwardBatches=2,forwardDrawCommands=12,hazeBatches=1,hazeDrawCommands=10,
                mirrorBatches=1,mirrorDrawCommands=4,cameraBatches=batches))
        self.sample=dict(schemaVersion=1,requestId=command['commandId'],instance=self.instance,sequence=self.sequence,
            processId=31,requestedEpochMs=requested,capturedEpochMs=captured,source=source)
        path=self.root/WORLD_FILE;path.write_text(json.dumps(self.sample));path.chmod(0o600)


class FreshStorage:
    def __init__(self,root,renderer,clock):
        self.root,self.renderer,self.clock=root,renderer,clock;self.present=False;self.callbacks=0;self.sequence=0
        self.commands=[];self.files={};self.ignore_release=False
    def send(self,value):
        storage_command(value);self.commands.append(deepcopy(value));self.sequence+=1
        if value['operation']=='release' and not self.ignore_release:self.present=False
        sample=dict(storageVersion=1,commandId=value['commandId'],requestId=value['requestId'],instance=self.renderer.instance,
            sequence=self.sequence,processId=31,capturedEpochMs=self.clock(),present=self.present,callbacks=self.callbacks,
            pngBytes=len(self.renderer.raw) if self.present else 0)
        if value['operation']=='read':sample.update(offset=value['offset'],data=base64.b64encode(
            self.renderer.raw[value['offset']:value['offset']+65536]).decode())
        raw=json.dumps(sample);self.files[receipt_file(value['commandId'])]=raw
        path=self.root/receipt_file(value['commandId']);path.write_text(raw);path.chmod(0o600)
    def original(self,name):return (self.root/name).read_text()


class StreamCaptureModel(StreamCycleModel):
    def __init__(self):
        super().__init__();actor=self.streams['actor'];actor.pid=31
        self.renderer=FreshRenderer(actor.epoch,self.m.tick,actor.sample.parent);self.storage=FreshStorage(actor.sample.parent,self.renderer,actor.epoch)
        self.model_commands=[];self.model_sequence=0;self.model_source=None;self.captures=[]
        self.world_wire_fault=None
        self.scope_root=actor.sample.parent
        self.inventory=InventoryBoundary(self.scope_root)
        # Constructor-created unissued fixture receipts are retained elsewhere;
        # native capture's actual issuer arena begins empty before any IO.
        prior=actor.root/'retained-inventory-seed';prior.mkdir(mode=0o700)
        for path in self.scope_root.iterdir():path.rename(prior/path.name)
        self.inventory.issued.clear();self.inventory.owner=None
        for producer in self.streams.values():
            snapshot=producer.snapshot
            def current(epoch,snapshot=snapshot):
                source=snapshot(epoch);source['worldRenderInstance']=self.renderer.instance
                source['view']=deepcopy(self.renderer.recorded);return source
            producer.snapshot=current
        original=actor.execute_bytes
        def binary(arguments,*,target,timeout):
            argv=shlex.split(arguments[1])
            is_world=argv[4] in (world_script(WORLD_FILE),world_script(INVENTORY_FILE)) or any(
                argv[4]==world_script(receipt_file(command['commandId'])) for command in self.storage.commands)
            if argv[4]!=MODEL_SCRIPT and not is_world:return original(arguments,target=target,timeout=timeout)
            assert target=='actor-model' and argv[:4]==['run-as','org.overte.pico','sh','-c']
            wire=subprocess.run(['sh','-c',argv[4],*argv[5:]],cwd=actor.root,stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,timeout=timeout,check=False).stdout
            return self.world_wire_fault(wire) if is_world and self.world_wire_fault is not None else wire
        actor.execute_bytes=binary

    def create(self):
        # Same original Parent; use the actual declared Actor producer PID at
        # fresh birth. Equal numeric PIDs across different targets are valid.
        self.parent=self.m.owner()
        for role,model in self.streams.items():
            binding=deepcopy(self.parent.source.binding)
            if role=='actor':binding.update(processIdentity=str(model.pid)+':actor-original',targetFingerprint='e'*64,sessionId=ACTOR)
            root=self.m.s.root if role=='primary' else self.actor_root
            adapter=SimpleNamespace(kind='pico',profile=dict(package='org.overte.pico'),
                _avatar_parent_store=lambda target,run,root=root:PrivateFeatureState(root/('avatar-parent-owner-'+run+'.json')),
                adb=SimpleNamespace(execute_bytes=model.execute_bytes))
            phase=self.parent.source.phase if role=='primary' else PhaseFixtureReader(self.parent.source.phase.client,RUN,'emotes',
                epoch_ms=lambda:self.m.s.epoch,monotonic=lambda:self.m.s.clock)
            self.roles[role]=dict(adapter=adapter,target=role+'-model',native=model.native,binding=binding,phase=phase,
                lock=self.m.s.lock if role=='primary' else self.actor_lock,subject=model.subject_id)
        self.cycle=PicoEmoteStreamCycle(self.parent,self.roles);return self.cycle

    def models(self):
        actor=self.streams['actor']
        def send(request):
            model_command(request);self.model_commands.append(deepcopy(request));self.model_sequence+=1
            capture=self.renderer.sample;assert request['captureRequestId']==capture['requestId'];trace=capture['source']['renderTrace']
            batch=trace['cameraBatches'][0]
            row=dict(modelInstance=MODEL,geometryInstance=GEOMETRY,loadedSourcePresent=True,loadedSourceSha256=LOADED,
                drawCommands=1,skinnedDrawCommands=1,blendshapedDrawCommands=0,originalGeometryDrawCommands=1,indices=60,
                minimum=[-1,0,-3],maximum=[1,2,-1],cameraUses=[dict(batchSequence=batch['sequence'],slot=camera['slot'],eye=camera['eye'],
                    drawViewport=deepcopy(camera['drawViewport']),drawCommands=1) for camera in batch['cameras']])
            model_trace={key:deepcopy(trace[key]) for key in ('frameId','frameIndex','executionSequence','recordedEpochMs','begunEpochMs',
                'completedEpochMs','renderer','view')};model_trace.update(picoModelTraceVersion=1,drawCommands=1,models=[row])
            self.model_source=dict(schemaVersion=1,requestId=request['commandId'],instance=self.renderer.instance,sequence=self.model_sequence,
                processId=31,requestedEpochMs=actor.epoch(),capturedEpochMs=actor.epoch(),source=dict(picoModelCaptureVersion=1,
                    captureRequestId=capture['requestId'],captureSequence=capture['sequence'],acquisitionSequence=capture['source']['acquisitionSequence'],
                    captureCapturedEpochMs=capture['source']['capturedEpochMs'],imageSha256=capture['source']['image']['sha256'],
                    pixelSha256=capture['source']['image']['pixelSha256'],modelTrace=model_trace))
            path=actor.sample.parent/MODEL_FILE;path.write_text(json.dumps(self.model_source));path.chmod(0o600)
        return PicoWorldModelDraws(send,lambda:json.dumps(self.model_source),actor.epoch,lambda:True,31,
            monotonic=lambda:self.m.s.clock,sleep=self.m.sleep)

    def world_store(self):return PrivateFeatureState(self.actor_root/'emote-actor-world-render.json')

    def world(self):
        source=self.cycle.streams['actor'];actor=self.streams['actor'];guard=source.guard
        owner=WorldRenderOwner(self.world_store(),source.binding,guard,role='actor');options=dict(monotonic=lambda:self.m.s.clock,sleep=self.m.sleep)
        def storage_send(command):
            self.storage.send(command);path=actor.sample.parent/receipt_file(command['commandId'])
            self.inventory.issued[command['commandId']]=(command['requestId'],hashlib.sha256(path.read_bytes()).hexdigest())
            self.inventory.owner=deepcopy(owner.owned());self.inventory.retired=not self.storage.present
            self.inventory.present=self.storage.present;self.inventory.callbacks=self.storage.callbacks
            self.inventory.png_bytes=len(self.renderer.raw) if self.storage.present else 0
        storage=NativeWorldRenderStorage(storage_send,self.storage.original,actor.epoch,guard,31,receipt_intent=owner.receipt_intent,**options)
        def send(command):
            assert owner.owned()['capture']==command;self.renderer.intents.append(deepcopy(command));self.renderer.send(command);self.storage.present=True
        capture=NativeWorldRenderCapture(send,self.renderer.original,storage,actor.epoch,guard,31,intent=owner.intent,stereo=True,require_cameras=True,**options)
        def inventory_send(command):
            self.inventory.epoch=actor.epoch();self.inventory.send(command)
            if self.inventory.value.get('receiptInventoryVersion')==1:self.inventory.value['instance']=self.renderer.instance
            path=actor.sample.parent/INVENTORY_FILE;path.write_text(json.dumps(self.inventory.value));path.chmod(0o600)
        inventory=NativeWorldReceiptInventory(inventory_send,self.inventory.original,actor.epoch,guard,31,owner.owned,lambda:storage.instance,**options)
        receipts=NativeWorldReceiptBatchFiles(SimpleNamespace(read=lambda name:(self.scope_root/name).read_text()),inventory)
        return SerializedWorldCapture(capture,storage,owner,receipts,source_lock=source.lock)

    def close(self):
        for capture in self.captures:capture.close_host()
        super().close()
