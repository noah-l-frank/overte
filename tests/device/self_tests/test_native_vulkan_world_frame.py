"""Original Vulkan pixel transport model; no compiler or actual GPU execution."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
from io import BytesIO
import json
from pathlib import Path
import random
import subprocess
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PIL import Image
from adapters.native_vulkan_world_frame import NativeVulkanWorldFrame,command,validate,storage,absent,original_pixels
from adapters.normal_ui import NativeUIError
from self_tests.test_native_completed_frame import Boundary,query
from self_tests.test_native_feature_observation import probe_source


def request(operation='read',nonce='b',**extra):
    return dict(query(operation,nonce),action='feature-vulkan-world-frame',**extra)


class World(Boundary):
    def __init__(self):
        super().__init__();self.source_extent=[160,100];self.target_extent=[320,200]
        self.raw_pixels=random.Random(42).randbytes(320*200*4)
        image=Image.frombytes('RGBA',(320,200),self.raw_pixels);stream=BytesIO();image.save(stream,format='PNG');self.png=stream.getvalue()
        self.fault=None
    def send(self,value):
        command(value)
        # Original GPU completion progresses independently of reading the
        # observation carrier, including after a lost read response/release.
        if self.request is not None and not self.no_fence and self.clock-self.started>=.05:
            self.gpu_pending=False
        if value['operation']=='read-bytes':
            self.commands.append(deepcopy(value));self.sequence+=1;offset=value['offset']
            self.value=dict(vulkanWorldStorageVersion=1,commandId=value['commandId'],requestId=value['requestId'],
                operation='read-bytes',instance='c'*32,sequence=self.sequence,processId=42,
                requestedEpochMs=self.epoch(),capturedEpochMs=self.epoch(),source=dict(retired=self.retired,
                present=not self.retired,callbacks=1 if self.held else 0,gpuPending=self.gpu_pending,
                metadataBytes=1000 if self.metadata else 0,pngBytes=0 if self.retired else len(self.png),
                gpuBufferBytes=262144 if self.gpu_pending else 0,offset=offset,data=base64.b64encode(self.png[offset:offset+65536]).decode()))
            if self.fault:self.fault(self.value)
        else:
            super().send(dict(value,action='feature-completed-frame'));self.commands[-1]=deepcopy(value)
            if 'frameStorageVersion' in self.value:
                self.value['vulkanWorldStorageVersion']=self.value.pop('frameStorageVersion')
                present=self.request is not None and not self.retired
                self.value['source'].update(present=present,pngBytes=len(self.png) if present and self.metadata else 0,
                                           gpuBufferBytes=262144 if self.gpu_pending else 0)
                if self.fault:self.fault(self.value)
    def original(self):
        raw=super().original()
        if self.value is not None:self.value['requestId']=self.commands[-1]['requestId'];raw=json.dumps(self.value)
        if 'completedFrameVersion' in self.value and self.value.get('pending') is not True:
            self.value['vulkanWorldFrameVersion']=self.value.pop('completedFrameVersion')
            source=self.value['source'];self.clock+=.002;self.value['capturedEpochMs']=self.epoch()
            source.update(pixelFormat='rgba8-top-left',pixelsReadEpochMs=self.epoch(),image=dict(bytes=len(self.png),
                sha256=hashlib.sha256(self.png).hexdigest(),pixelSha256=hashlib.sha256(self.raw_pixels).hexdigest(),width=320,height=200))
            if self.fault:self.fault(self.value)
            raw=json.dumps(self.value)
        return raw
    def reader(self):return NativeVulkanWorldFrame(self.send,self.original,self.epoch,lambda:self.okay,42,self.intent,
                                                  monotonic=lambda:self.clock,sleep=self.sleep)


class WorldFrameTests(unittest.TestCase):
    def test_original_fence_rgba_png_and_multiple_chunks_keep_original_hashes_and_clocks(self):
        b=World();reader=b.reader();frame=reader.perform(request());raw=reader.image(frame)
        self.assertEqual(b.png,raw);self.assertEqual(b.raw_pixels,Image.open(BytesIO(raw)).tobytes())
        self.assertEqual(hashlib.sha256(raw).hexdigest(),frame['source']['image']['sha256'])
        self.assertGreater(frame['capturedEpochMs'],frame['source']['fenceObservedEpochMs'])
        reads=[c for c in b.commands if c['operation']=='read-bytes']
        self.assertGreater(len(reads),1);self.assertEqual(list(range(0,len(raw),65536)),[c['offset'] for c in reads])
        self.assertEqual(b.commands,b.intents);stamp=frame['capturedEpochMs'];b.sleep(.1)
        self.assertEqual(stamp,frame['capturedEpochMs']);self.assertGreater(reader.last['capturedEpochMs'],stamp-1)
        release=reader.perform(request('release','e'));self.assertFalse(absent(release));b.sleep(.2)
        self.assertTrue(absent(reader.perform(request('inspect','f'))))

    def test_missing_fence_or_retained_copy_allocation_cannot_become_pixels_or_absence(self):
        b=World();b.no_fence=True;reader=b.reader()
        with self.assertRaises(NativeUIError):reader.perform(request())
        with self.assertRaises(NativeUIError):reader.perform(request())
        released=reader.perform(request('release','e'))
        self.assertFalse(absent(released));self.assertGreater(released['source']['gpuBufferBytes'],0)
        self.assertEqual(1,sum(c['operation']=='read' for c in b.commands))

    def test_png_hash_pixel_hash_format_size_pid_and_chunk_corruption_fail_independently(self):
        for fault in ('png','pixels','format','extent','pid','offset','data','bytes','late'):
            b=World();reader=b.reader();frame=reader.perform(request())
            if fault=='png':frame['source']['image']['sha256']='0'*64
            elif fault=='pixels':frame['source']['image']['pixelSha256']='0'*64
            elif fault=='format':frame['source']['pixelFormat']='opengl-bottom-left'
            elif fault=='extent':frame['source']['image']['width']=321
            elif fault=='pid':frame['processId']=99
            elif fault=='offset':b.fault=lambda v:v['source'].update(offset=True)
            elif fault=='data':b.fault=lambda v:v['source'].update(data=base64.b64encode(b'wrong').decode())
            elif fault=='bytes':b.fault=lambda v:v['source'].update(pngBytes=1)
            else:b.sleep(2)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):reader.image(frame)

    def test_lost_chunk_delivery_is_not_retried_and_failed_intent_cannot_start_it(self):
        b=World();reader=b.reader();frame=reader.perform(request());original=b.send
        def lost(value):
            original(value)
            if value['operation']=='read-bytes':raise OSError('Synthetic lost byte receipt')
        reader.send=lost
        with self.assertRaises(NativeUIError):reader.image(frame)
        self.assertEqual(1,sum(c['operation']=='read-bytes' for c in b.commands))
        b=World();reader=b.reader();frame=reader.perform(request());b.intent_fail=True
        with self.assertRaises(NativeUIError):reader.image(frame)
        self.assertEqual(0,sum(c['operation']=='read-bytes' for c in b.commands))

    def test_closed_fixture_cannot_select_expected_settings_or_accept_boolean_offsets(self):
        from fixture.serve import FixtureState
        fixture=FixtureState();self.assertEqual(request(),fixture.set_client_command(request()))
        valid=request('read-bytes','c',offset=0);self.assertEqual(valid,fixture.set_client_command(valid))
        for changed in (valid|dict(offset=True),valid|dict(offset=1.2),request()|dict(offset=0),request()|dict(expectedScale=.5)):
            with self.assertRaises((NativeUIError,ValueError)):fixture.set_client_command(changed)

    def test_actual_probe_publishes_unmodified_world_frame_and_bytes_in_one_retired_carrier(self):
        program=r'''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,k)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.sort());
let calls=[],files=[],timers=[],cleared=[],ready=false;
const Script={setTimeout:f=>{timers.push(f);return timers.length;},clearTimeout:id=>cleared.push(id)};
const frame={vulkanWorldFrameVersion:1,commandId:"ios-"+"b".repeat(32),requestId:"ios-"+"a".repeat(32),capturedEpochMs:17000};
const bytes={vulkanWorldStorageVersion:1,commandId:"ios-"+"c".repeat(32),requestId:frame.requestId,capturedEpochMs:17010,source:{data:"actual-original-byte-chunk"}};
const Test={featureCompletedFrameObservation:c=>{calls.push(c);return c.operation==='read'?(ready?frame:{commandId:c.commandId,requestId:c.requestId,pending:true}):c.operation==='read-bytes'?bytes:{commandId:c.commandId,requestId:c.requestId,source:{retired:true}};},saveObject:(v,name)=>files.push({v,name})};
SOURCE
const read={schemaVersion:1,commandId:frame.commandId,requestId:frame.requestId,action:"feature-vulkan-world-frame",operation:"read"};
applyClientCommand(read);if(files.length||timers.length!==1)throw Error("uncompleted world pixels published");
ready=true;timers[0]();applyClientCommand({...read,commandId:bytes.commandId,operation:"read-bytes",offset:0});
if(files[0].v!==frame||files[1].v!==bytes||files.some(f=>f.name!=="feature-vulkan-world-frame.json"))throw Error("world originals changed or private carrier split");
const count=calls.length;applyClientCommand({...read,commandId:"ios-"+"d".repeat(32),operation:"read-bytes",offset:true});
if(calls.length!==count)throw Error("boolean offset reached native source");
ready=false;const next={...read,requestId:"ios-"+"e".repeat(32),commandId:"ios-"+"f".repeat(32)};
applyClientCommand(next);const queued=timers[timers.length-1];
applyClientCommand({...next,commandId:"ios-"+"1".repeat(32),operation:"release"});
const final=calls.length;queued();if(calls.length!==final)throw Error("retired world read reentered source");
'''.replace('SOURCE',probe_source())
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)


if __name__=='__main__':unittest.main()
