"""ONE actual Policy2/Cycle/Raw aggregate with bounded declared native files.

Source production and GPU/rendering remain explicit host models. Real existing
Parent/Role4/Policy2/range/PNG/retirement owners execute without another recipe.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import shlex
import subprocess
from types import SimpleNamespace

from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.owned_world_render import WorldRenderOwner
from adapters.pico4.emote_stream_cycle import PicoEmoteStreamCycle
from adapters.pico4.emote_model_draws import PicoWorldModelDraws,command as model_command,FILE as MODEL_FILE
from self_tests.test_native_avatar_render import MODEL,GEOMETRY,LOADED
from adapters.pico4.emote_stream_capacity import descriptor
from adapters.pico4.emote_stream_model_raw import SCRIPT2 as MODEL_SCRIPT2
from adapters.pico4.emote_stream_world_raw import script as world_script
from adapters.pico4.graphics_binding import SerializedWorldCapture
from adapters.world_render_evidence import NativeWorldRenderCapture,FILE as WORLD_FILE
from adapters.world_render_storage import NativeWorldRenderStorage,command as storage_command,receipt_file
from adapters.world_render_receipts import NativeWorldReceiptInventory,NativeWorldReceiptBatchFiles,INVENTORY_FILE,inventory_command
from self_tests.pico_emote_capacity_fixture import CapacityModel,CapacityRenderer
from self_tests.pico_emote_capacity_publisher_model import NativePublisherModel
from self_tests.pico_emote_stream_capture_fixture import StreamCaptureModel


class CapacityStorage:
    def __init__(self,owner,old):self.owner=owner;self.__dict__.update(old.__dict__)
    def send(self,value):
        import base64
        storage_command(value);self.commands.append(deepcopy(value));self.sequence+=1
        if value['operation']=='release' and not self.ignore_release:self.present=False
        sample=dict(storageVersion=1,commandId=value['commandId'],requestId=value['requestId'],instance=self.renderer.instance,
            sequence=self.sequence,processId=31,capturedEpochMs=self.clock(),present=self.present,callbacks=self.callbacks,
            pngBytes=len(self.renderer.raw) if self.present else 0)
        if value['operation']=='read':sample.update(offset=value['offset'],data=base64.b64encode(
            self.renderer.raw[value['offset']:value['offset']+65536]).decode())
        raw=json.dumps(sample);self.files[receipt_file(value['commandId'])]=raw
        self.owner.publishers['actor'].publish(receipt_file(value['commandId']),value['commandId'],raw.encode())
    def original(self,name):return (self.root/name).read_text()


class CapacityInventory:
    def __init__(self,owner,old):self.owner=owner;self.__dict__.update(old.__dict__);self.fixture_owner=owner
    def send(self,request):
        import os
        inventory_command(request,ios=self.ios);self.commands.append(deepcopy(request));self.sequence+=1
        capture=request['requestId'];wanted=set(request['receiptIds'])
        valid=self.retired and not self.present and not self.callbacks and not self.png_bytes
        valid=valid and all(nonce in wanted for nonce,(origin,_digest) in self.issued.items() if origin==capture)
        for nonce in wanted:
            path=self.root/receipt_file(nonce);issued=self.issued.get(nonce)
            if (issued is not None and issued[0]!=capture or path.is_symlink()
                    or path.exists() and (not path.is_file() or path.stat().st_nlink!=1 or path.stat().st_uid!=os.geteuid()
                        or path.stat().st_mode&0o7777!=0o600
                        or issued is None or hashlib.sha256(path.read_bytes()).hexdigest()!=issued[1])):valid=False
        if not valid:self.value=dict(commandId=request['commandId'],available=False);return
        if request['operation']=='remove' and not self.ignore_remove:
            for nonce in wanted:
                if nonce in self.issued:self.fixture_owner.publishers['actor'].remove_receipt(nonce,self.issued[nonce][1])
        rows=[]
        for nonce in request['receiptIds']:
            path=self.root/receipt_file(nonce);exists=path.exists() or path.is_symlink();issued=self.issued.get(nonce)
            rows.append(dict(receiptId=nonce,issued=issued is not None,exists=exists,
                originalMatches=issued is not None and exists and hashlib.sha256(path.read_bytes()).hexdigest()==issued[1]))
        source=dict(retired=self.retired,present=self.present,callbacks=self.callbacks,pngBytes=self.png_bytes,complete=True,receipts=rows)
        if request['operation']=='remove':source['performed']=True
        self.value=dict(receiptInventoryVersion=1,commandId=request['commandId'],requestId=capture,
            operation=request['operation'],instance=self.fixture_owner.renderer.instance,sequence=self.sequence,processId=31,
            capturedEpochMs=self.fixture_owner.streams['actor'].epoch(),source=source)
        if self.mutate:self.mutate(self.value)
        self.fixture_owner.publishers['actor'].publish(INVENTORY_FILE,request['commandId'],json.dumps(self.value).encode())

    def original(self):return (self.root/INVENTORY_FILE).read_text()


class CapacityCycleModel(CapacityModel):
    def __init__(self):
        super().__init__();self.publishers={}
        self.renderer=CapacityRenderer(self.streams['actor'].epoch,self.m.tick,self.scope_root,16,12)
        self.renderer.publisher=lambda name,nonce,raw:self.publishers['actor'].publish(name,nonce,raw)
        self.storage=CapacityStorage(self,self.storage);self.storage.renderer=self.renderer
        self.inventory=CapacityInventory(self,self.inventory)

    def configure_capacity_native(self):
        for role,config in self.roles.items():
            producer=self.streams[role];root=self.m.s.root if role=='primary' else self.actor_root
            config['adapter']._avatar_parent_store=lambda target,run,root=root:PrivateFeatureState(root/('avatar-parent-owner-'+run+'.json'))
            original=config['native'].send
            def send(request,role=role,producer=producer,original=original):
                if request['operation']=='arm':
                    policy=json.loads(request['ownerPolicy']);need(policy['picoRemoteAvatarStreamPolicyVersion']==2)
                    need(all(type(policy.get(key)) is int and policy[key]==value for key,value in descriptor().items()))
                    publisher=object.__new__(NativePublisherModel);self.publishers[role]=publisher;self.publisher_models.append(publisher)
                    NativePublisherModel.__init__(publisher,producer.sample.parent,self.capacity.guard)
                elif request['operation']=='stop':self.publishers[role].stop()
                else:self.publishers[role].drain()
                return original(request)
            config['native'].send=send
        producer=self.streams['actor'];original=producer.execute_bytes
        def binary(arguments,*,target,timeout):
            argv=shlex.split(arguments[1]);allowed=argv[4] in (MODEL_SCRIPT2,world_script(WORLD_FILE,capacity=True),world_script(INVENTORY_FILE,capacity=True))
            allowed=allowed or any(argv[4]==world_script(receipt_file(value['commandId']),capacity=True) for value in self.storage.commands)
            if not allowed:return original(arguments,target=target,timeout=timeout)
            assert target=='actor-model' and argv[:4]==['run-as','org.overte.pico','sh','-c']
            wire=subprocess.run(['sh','-c',argv[4],*argv[5:]],cwd=producer.root,stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,timeout=timeout,check=False).stdout
            return self.world_wire_fault(wire) if argv[4]!=MODEL_SCRIPT2 and self.world_wire_fault is not None else wire
        producer.execute_bytes=binary;self.roles['actor']['adapter'].adb.execute_bytes=binary

    def create(self):
        self.prepare();self.cycle=PicoEmoteStreamCycle(self.parent,self.roles,capacity=self.capacity);return self.cycle

    def close(self):
        for publisher in self.publisher_models:assert publisher.close_host()
        StreamCaptureModel.close(self)

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
            self.publishers['actor'].publish(MODEL_FILE,request['commandId'],json.dumps(self.model_source).encode())
        return PicoWorldModelDraws(send,lambda:json.dumps(self.model_source),actor.epoch,lambda:True,31,
            monotonic=lambda:self.m.s.clock,sleep=self.m.sleep)


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

        inventory=NativeWorldReceiptInventory(inventory_send,self.inventory.original,actor.epoch,guard,31,owner.owned,lambda:storage.instance,**options)
        receipts=NativeWorldReceiptBatchFiles(SimpleNamespace(read=lambda name:(self.scope_root/name).read_text()),inventory)
        return SerializedWorldCapture(capture,storage,owner,receipts,source_lock=source.lock)
