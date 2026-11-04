"""Declared independent renderer model BEFORE genuine Actor owner creation.

Native/OpenGL/QImage/SDK/HTTP are LOWER MODELS, not compiled renderer/process/
authentication evidence. Actual PNG bytes, PFS/OFS, ScriptSourceLocks, typed
owner/factory, publication WAL and Journal logic are real host operations.
The Primary capture/WDA pixels are never read by this Actor producer.
"""
from copy import deepcopy
from io import BytesIO
import base64,hashlib,json,uuid
from unittest.mock import patch
from PIL import Image
from adapters.native_feature_observation import need
from feature_journeys.witness import Journal
from ios.adapters import feature_observation,snapshot_actor_pixels
from ios.adapters.snapshot_actor_pixel_runtime import IOSSnapshotActorPixelRuntime
from ios.self_tests.snapshot_scene_canonical_domain import CanonicalSceneDomain,RUN,TICKET

class DeclaredActorFrame:
    def __init__(self,inputs,rgba):
        self.inputs=deepcopy(inputs);self.rgba=bytes(rgba)
        need(len(self.rgba)==self.inputs['viewport'][2]*self.inputs['viewport'][3]*4)
class DeclaredActorReadback:
    def __init__(self,frame):
        need(type(frame)is DeclaredActorFrame)
        self.current=frame;self.held=None;self.latest=None;self.active=0;self.reads=0;self.before_commit=None
        self.consumed_inputs=None;self.scene_latest=None;self.attempt_identity=None;self.invalidated_identity=None
        self.greatest_index=0;self.greatest_identity=None;self.head_rejected=False;self.index_regressed=False
    def consume(self,epoch):
        held=self.current;original_inputs=deepcopy(held.inputs);inputs=deepcopy(original_inputs)
        identity=original_inputs['frameInstance'];index=original_inputs['frameIndex']
        if index==0 or index<self.greatest_index:self.index_regressed=True
        if self.index_regressed or(index==self.greatest_index and(identity!=self.greatest_identity or self.head_rejected)):
            self.head_rejected=True;self.invalidated_identity=identity
            self.latest=None;self.scene_latest=None;self.consumed_inputs=None;return
        if index>self.greatest_index:
            self.greatest_index=index;self.greatest_identity=identity;self.head_rejected=False
        if identity==self.invalidated_identity:return
        if identity==self.attempt_identity:
            # Exact actual map before any duplicate early return, matching native
            # same-ID invalidation rather than merely stricter getter validation.
            if original_inputs!=self.consumed_inputs:
                self.head_rejected=True;self.invalidated_identity=identity;self.latest=None;self.scene_latest=None;self.consumed_inputs=None
            return
        self.invalidated_identity=None;self.attempt_identity=identity
        self.consumed_inputs=deepcopy(original_inputs);self.scene_latest=deepcopy(original_inputs)
        self.latest=None;self.held=held;self.active+=1
        result=None
        try:
            with Image.frombytes('RGBA',tuple(inputs['viewport'][2:]),held.rgba)as image:
                encoded=BytesIO();image.save(encoded,format='PNG');raw=encoded.getvalue()
                rgba=image.convert('RGBA').tobytes();extent=list(image.size);self.reads+=1
                inputs.update(readback=dict(sourceExtent=extent,rectBottomLeft=[0,0,*extent],imageExtent=extent,pixelFormat='rgba8-top-left',
                    pixelSha256=hashlib.sha256(rgba).hexdigest(),readEpochMs=epoch),callbackEpochMs=epoch)
                result=dict(complete=True,frame=inputs,png=dict(format='png',encoding='base64',bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),
                    data=base64.b64encode(raw).decode('ascii'),frameBinding={key:deepcopy(inputs[key])for key in snapshot_actor_pixels.BINDING_KEYS}),
                    resource=dict(profile='single-latest-actor-frame-v1',callbackScopeRetired=False,retainedQImage=False,nativeSlotProcessLifetime=True))
                if self.before_commit is not None:self.before_commit(self,held)
        finally:self.active-=1
        # Model the exact native held object/map checks and callback retirement.
        # A new frame is discarded, never matched by a caller's requested ID.
        if self.current is not held or self.current.inputs!=original_inputs or self.active!=0:return
        if len(raw)>snapshot_actor_pixels.PNG_LIMIT:return
        result['resource']['callbackScopeRetired']=True;self.latest=result
    def original(self):
        if self.latest is None or self.current is not self.held:return dict(complete=False)
        original={key:value for key,value in self.latest['frame'].items()if key not in('readback','callbackEpochMs')}
        if original!=self.current.inputs:return dict(complete=False)
        return deepcopy(self.latest)

class ActorPixelDomain(CanonicalSceneDomain):
    def __init__(self,case,*,enabled=True,replaced_during_callback=False,changed_inputs_during_callback=False,packet_fault=None):
        super().__init__(case,enabled=False)
        self.journal=Journal(clock=self.primary.capture.epoch,snapshot_actor_pixels=enabled)
        with patch('feature_journeys.witness.secrets.token_hex',return_value=RUN):need(self.journal.register('snapshots')==RUN)
        self.journal.activate(RUN,TICKET,'capture',dict(mode='still',format='png'))
        frame=deepcopy(self.actor.frame);frame['viewport']=[0,0,32,32]
        # A separate prechosen source raster, never Primary bytes or expected
        # effects supplied to a reader. Actual PNG encoding/decoding is tested.
        rgba=bytes(component for y in range(32)for x in range(32)for component in((x*19+y*7)%256,(y*13+x*3)%256,(x*11+y*23)%256,255))
        self.renderer=DeclaredActorReadback(DeclaredActorFrame(frame,rgba))
        if replaced_during_callback:
            def replace(model,held):
                later=deepcopy(held.inputs);later.update(frameInstance=uuid.uuid4().hex,frameIndex=later['frameIndex']+1)
                model.current=DeclaredActorFrame(later,held.rgba)
            self.renderer.before_commit=replace
        if changed_inputs_during_callback:
            def change(model,held):held.inputs['camera']['position'][0]=1
            self.renderer.before_commit=change
        self.renderer.consume(self.actor.clock())
        self.pixel_queries=[];self.pixel_raw=None;self.lose_query=False;self.packet_fault=packet_fault;self.pixel_sequence=0
        original_execute=self.actor.ctx.files.execute
        def pull(session,operation,values):
            if values['remotePath'].endswith('/'+snapshot_actor_pixels.FILE):
                need(operation=='mobile: pullFile'and self.pixel_raw is not None)
                return base64.b64encode(self.pixel_raw.encode()).decode('ascii')
            return original_execute(session,operation,values)
        self.actor.ctx.files.execute=pull
        previous=feature_observation.post_request;domain=self
        def post(request,timeout):
            query=json.loads(request.data)
            if query.get('action')!=snapshot_actor_pixels.ACTION:return previous(request,timeout)
            need(timeout==5);snapshot_actor_pixels.command(query);self.pixel_queries.append(deepcopy(query));self.pixel_sequence+=1
            clock=dict(epochMs=self.actor.clock(),monotonicMs=self.actor.clock()-1700000000000+1000)
            body=dict(iosSnapshotActorPixelsVersion=1,requestId=query['commandId'],runId=query['runId'],instance='e'*32,sequence=self.pixel_sequence,processId=42,
                clockDomain='native-main-snapshot-actor-pixels',clockBefore=dict(clock),clockAfter=dict(clock),source=self.renderer.original())
            if self.packet_fault is not None:self.packet_fault(body)
            self.pixel_raw=json.dumps(body,indent=1)+'\n';self.actor.ctx.files.echo=json.dumps(query).encode()
            if self.lose_query:raise OSError('Declared native pixel query delivered; actual modeled HTTP return lost')
            return self.actor.ctx.files
        patched=patch.object(feature_observation,'post_request',post);patched.start();case.addCleanup(patched.stop)
        base=type(self.actor_runtime)
        class Actor(IOSSnapshotActorPixelRuntime,base):pass
        self.actor_runtime=Actor(self.actor_runtime.adapter)
    def pixels(self):
        return self.actor_runtime.actor_pixel_publications('actor',RUN,self.actor_client,epoch_ms=self.primary.capture.epoch,monotonic=self.primary.capture.mono)
