"""Actual original Parent/file/range owners; declared capacity/native issuer.

No Source4, alternate recipe, device, Qt or real renderer is bootstrapped.
The one real range archive uses the proposed scope2, for capacity-only proof.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import io
import json
import os
import uuid

from PIL import Image
from adapters.world_render_evidence import image_name,FILE as WORLD_FILE
from self_tests.pico_emote_stream_capture_fixture import FreshRenderer
from self_tests.test_stereo_world_render import identity
from types import SimpleNamespace

from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4.audio_raw_archive import AudioRawArchive,AudioRawSourceLock
from adapters.pico4.emote_stream_capacity import PicoEmoteStreamCapacity
from adapters.script_journey.history import canonical
from feature_journeys.phase_fixture import PhaseFixtureReader
from self_tests.pico_emote_stream_capture_fixture import StreamCaptureModel,ACTOR,RUN


class CapacityModel(StreamCaptureModel):
    def __init__(self):
        super().__init__();self.capacity=None;self.archive=None;self.publisher_models=[];self.external=dict(parts=0,storedBytes=0,decodedBytes=0)

    def prepare(self):
        self.parent=self.m.owner()
        for role,producer in self.streams.items():
            binding=deepcopy(self.parent.source.binding)
            if role=='actor':binding.update(processIdentity=str(producer.pid)+':actor-original',targetFingerprint='e'*64,sessionId=ACTOR)
            root=self.m.s.root if role=='primary' else self.actor_root
            adapter=SimpleNamespace(kind='pico',profile=dict(package='org.overte.pico'),
                adb=SimpleNamespace(execute_bytes=producer.execute_bytes))
            phase=self.parent.source.phase if role=='primary' else PhaseFixtureReader(self.parent.source.phase.client,RUN,'emotes',
                epoch_ms=lambda:self.m.s.epoch,monotonic=lambda:self.m.s.clock)
            self.roles[role]=dict(adapter=adapter,target=role+'-model',native=producer.native,binding=binding,phase=phase,
                lock=self.m.s.lock if role=='primary' else self.actor_lock,subject=producer.subject_id)
        hook=getattr(self,'configure_capacity_native',None)
        if hook is not None:hook()
        self.capacity=PicoEmoteStreamCapacity(self.parent,self.roles);return self.capacity

    def baseline(self):
        read=self.parent.source.read
        def before_first_source():
            self.baseline_parent_bytes=canonical(self.parent.previous)+b'\n'
            self.capacity.activate();return read()
        self.parent.source.read=before_first_source
        try:self.parent.baseline()
        finally:self.parent.source.read=read
        capacity=self.capacity
        self.archive=object.__new__(AudioRawArchive);capacity.bind_archive(self.archive,self.bill)
        scope=dict(picoEmoteStreamOriginalsVersion=2,containerFormat='audioRawJournalVersion1-raw-only',
            captureCapacitySha256=capacity.descriptor_sha,parentIdentitySha256=hashlib.sha256(canonical(self.parent.identity)).hexdigest(),
            proofScope='explicit-capacity-component-not-Policy2-or-Source4-qualification')
        path=capacity.path.with_name(self.parent.store.path.name+'.child-stream-raw.json')
        AudioRawArchive.__init__(self.archive,path,scope,AudioRawSourceLock(self.m.s.lock),capacity.host_identity,self.bill,lambda:self.m.s.clock)
        capacity.ready()

    def bill(self):
        value=self.capacity.extra_bill()
        # Existing actual Root enumeration is exercised in the integrated
        # source packet. This explicit component additionally charges EVERY
        # actual host file and fixed supplied external admission counter.
        for root in (self.m.s.root,self.actor_root):
            for path in root.rglob('*'):
                if not path.is_file():continue
                if self.archive is not None and hasattr(self.archive,'path') and path.name.startswith(self.archive.path.name):continue
                raw=path.read_bytes();value['parts']+=1;value['storedBytes']+=len(raw);value['decodedBytes']+=len(raw)
        return {key:value[key]+self.external[key] for key in value}

    def close(self):
        for publisher in self.publisher_models:
            assert publisher.close_host(),'Original host publisher model descriptors remain unresolved'
        if self.archive is not None and hasattr(self.archive,'directory'):
            assert self.archive.close_host(),'Original capacity component raw owner could not close'
        if self.capacity is not None:assert self.capacity.close_host(),'Original capacity owner could not close'
        super().close()


class CapacityRenderer(FreshRenderer):
    """Fresh declared CPU producer of an ACTUAL large original PNG.

    Its real encoded size is used; this is not a smaller invented image cap.
    Camera/viewport metadata is emitted at the operation, before the getter.
    """
    def __init__(self,clock,work,root,width,height):
        super().__init__(clock,work,root);self.width,self.height=width,height
        pixels=os.urandom(width*height*4);out=io.BytesIO()
        Image.frombytes('RGBA',(width,height),pixels).save(out,format='PNG',compress_level=0)
        self.raw=out.getvalue();self.pixels=hashlib.sha256(pixels).hexdigest()
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
                sourceViewport=[index*(self.width//2),0,self.width//2,self.height],targetViewport=[index*(self.width//2),0,self.width//2,self.height]))
        for index,draws in enumerate((5,7,4)):
            cameras=[]
            for eye in range(2):
                view=identity();view[12]=.032 if eye==0 else -.032;view[14]=.1
                projection=deepcopy(eyes[eye]['projection']);projection[8]=.02
                cameras.append(dict(slot=0,eye=('left','right')[eye],view=view,projection=projection,
                    viewport=[0,0,self.width,self.height],drawViewport=[(self.width//2)*eye,0,self.width//2,self.height],stereoInfo=[1,eye,1/self.width,1/self.height],drawCommands=draws))
            batches.append(dict(sequence=self.uniform_sequence+index,frameIndex=self.frame,executionSequence=self.execution,
                rawDrawCommands=draws,executedDrawCommands=draws,role='mirror' if index==2 else 'forward',technique='doubled',cameras=cameras))
        source=dict(captureVersion=4,available=True,acquisitionSequence=self.acquisition,recordedEpochMs=requested,
            startedEpochMs=captured,capturedEpochMs=captured,backend='opengl',stage='tone-map-before-hud',view='main-stereo',
            sourceExtent=[self.width,self.height],sourceViewport=[0,0,self.width,self.height],targetExtent=[self.width,self.height],pixelFormat='rgba8-top-left',
            image=dict(name=image_name(command['commandId']),bytes=len(self.raw),sha256=hashlib.sha256(self.raw).hexdigest(),
                pixelSha256=self.pixels,width=self.width,height=self.height),
            stereo=dict(frameIndex=self.frame,executionSequence=self.execution,layout='side-by-side',matrixLayout='column-major',
                cameraView=identity(),eyes=eyes),
            presentation=dict(backend='openxr',frameIndex=self.frame,submissionSequence=self.submission,submittedEpochMs=captured,
                views=[dict(eye=name,imageRect=[0,0,self.width//2,self.height],arrayIndex=0) for name in ('left','right')]),
            renderTrace=dict(traceVersion=4,frameId=uuid.uuid4().hex,frameIndex=self.frame,executionSequence=self.execution,
                recordedEpochMs=requested,recordedView=deepcopy(self.recorded),begunEpochMs=requested,completedEpochMs=captured,
                renderer='forward',view='main-stereo',forwardBatches=2,forwardDrawCommands=12,hazeBatches=1,hazeDrawCommands=10,
                mirrorBatches=1,mirrorDrawCommands=4,cameraBatches=batches))
        self.sample=dict(schemaVersion=1,requestId=command['commandId'],instance=self.instance,sequence=self.sequence,
            processId=31,requestedEpochMs=requested,capturedEpochMs=captured,source=source)
        if getattr(self,'publisher',None) is not None:self.publisher(WORLD_FILE,command['commandId'],json.dumps(self.sample).encode())
        else:
            path=self.root/WORLD_FILE;path.write_text(json.dumps(self.sample));path.chmod(0o600)
