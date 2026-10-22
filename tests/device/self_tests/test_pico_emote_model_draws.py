"""Synthetic original stereo model provenance; no GPU/device qualification."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import subprocess
import unittest
from unittest.mock import patch

from adapters.normal_ui import NativeUIError
from adapters.pico4.emote_model_draws import PicoWorldModelDraws,command,avatar_draws,ACTION,FILE
from self_tests.test_native_avatar_render import avatar_source,MODEL,GEOMETRY,LOADED
from self_tests.test_native_feature_observation import probe_source
from self_tests.test_stereo_camera_uniforms import CameraBoundary


class ModelBoundary:
    def __init__(self,epoch=20000):
        capture=CameraBoundary();produce=capture.mutate
        def timestamps(value):
            if type(value) is dict:
                for key,item in value.items():
                    if key.endswith('EpochMs'):value[key]=item+epoch-20000
                    else:timestamps(item)
            elif type(value) is list:
                for item in value:timestamps(item)
        def producer(packet):produce(packet);timestamps(packet)
        capture.mutate=producer
        reader=capture.reader(stereo=True,require_cameras=True);reader.clock_ms=lambda:epoch
        self.capture,self.raw=reader.read(0)
        self.epoch=epoch;self.clock=0.;self.okay=True;self.ignore=False;self.sequence=0;self.commands=[];self.sample=None;self.edit=None
        frame=self.capture['source']['renderTrace'];batch=frame['cameraBatches'][0]
        row=dict(modelInstance=MODEL,geometryInstance=GEOMETRY,loadedSourcePresent=True,loadedSourceSha256=LOADED,
            drawCommands=1,skinnedDrawCommands=1,blendshapedDrawCommands=0,originalGeometryDrawCommands=1,indices=60,
            minimum=[-1,0,-3],maximum=[1,2,-1],cameraUses=[dict(batchSequence=batch['sequence'],slot=c['slot'],
                eye=c['eye'],drawViewport=deepcopy(c['drawViewport']),drawCommands=1) for c in batch['cameras']])
        self.trace={k:deepcopy(frame[k]) for k in ('frameId','frameIndex','executionSequence','recordedEpochMs','begunEpochMs','completedEpochMs','renderer','view')}
        self.trace.update(picoModelTraceVersion=1,drawCommands=1,models=[row])

    def send(self,request):
        command(request);self.commands.append(deepcopy(request))
        if self.ignore:return
        self.sequence+=1;original=self.capture['source']
        self.sample=dict(schemaVersion=1,requestId=request['commandId'],instance=self.capture['instance'],sequence=self.sequence,
            processId=self.capture['processId'],requestedEpochMs=self.epoch,capturedEpochMs=self.epoch,
            source=dict(picoModelCaptureVersion=1,captureRequestId=self.capture['requestId'],captureSequence=self.capture['sequence'],
                acquisitionSequence=original['acquisitionSequence'],captureCapturedEpochMs=original['capturedEpochMs'],
                imageSha256=original['image']['sha256'],pixelSha256=original['image']['pixelSha256'],modelTrace=deepcopy(self.trace)))
        if self.edit:self.edit(self.sample)

    def original(self):return '' if self.sample is None else json.dumps(self.sample)
    def sleep(self,seconds):self.clock+=seconds
    def reader(self):return PicoWorldModelDraws(self.send,self.original,lambda:self.epoch,lambda:self.okay,self.capture['processId'],monotonic=lambda:self.clock,sleep=self.sleep)

    def avatars(self):
        source=avatar_source();source['view']=deepcopy(self.capture['source']['renderTrace']['recordedView'])
        before=dict(schemaVersion=1,requestId='1'*32,instance='f'*32,sequence=1,processId=31,requestedEpochMs=self.epoch-1,capturedEpochMs=self.epoch-1,source=source)
        after=deepcopy(before);after.update(requestId='2'*32,sequence=2,requestedEpochMs=self.epoch,capturedEpochMs=self.epoch)
        return before,after


class PicoModelDrawTests(unittest.TestCase):
    def test_actual_specific_draw_cameras_and_original_stereo_image_identity_are_preserved(self):
        b=ModelBoundary();value=b.reader().read(b.capture)
        self.assertEqual(b.sample,value);self.assertEqual(b.trace,value['source']['modelTrace'])
        self.assertEqual({'schemaVersion','commandId','action','captureRequestId'},set(b.commands[0]))
        row=avatar_draws(*b.avatars(),b.capture,value,31,20000)
        self.assertEqual(['left','right'],[r['eye'] for r in row['cameraUses']]);self.assertNotIn('visible',row)

    def test_mono_phone_trace_or_expected_model_selectors_cannot_supply_pico_evidence(self):
        b=ModelBoundary();request=dict(schemaVersion=1,commandId='3'*32,action=ACTION,captureRequestId=b.capture['requestId'])
        for change in (dict(schemaVersion=True),dict(expectedModel=MODEL),dict(commandId='ios-'+'3'*32),dict(action='feature-world-model-draws-observe')):
            with self.subTest(change=change),self.assertRaises(NativeUIError):command(request|change)
        for field,value in (('view','main-mono'),('picoModelTraceVersion',True),('executionSequence',999),('frameIndex',101)):
            b=ModelBoundary();b.trace[field]=value
            with self.subTest(field=field),self.assertRaises(NativeUIError):b.reader().read(b.capture)

    def test_model_and_image_cannot_borrow_foreign_capture_submission_or_native_birth(self):
        for change in (dict(captureSequence=99),dict(acquisitionSequence=99),dict(imageSha256='1'*64),dict(pixelSha256='1'*64),dict(captureCapturedEpochMs=19999)):
            b=ModelBoundary();b.edit=lambda packet:packet['source'].update(change)
            with self.subTest(change=change),self.assertRaises(NativeUIError):b.reader().read(b.capture)
        b=ModelBoundary();b.capture['source']['presentation']['frameIndex']+=1
        with self.assertRaises(NativeUIError):b.reader().read(b.capture)
        b=ModelBoundary();b.edit=lambda p:p.update(instance='f'*32)
        with self.assertRaises(NativeUIError):b.reader().read(b.capture)

    def test_each_model_requires_both_own_used_eye_bindings_and_actual_counts(self):
        faults=[lambda row:row['cameraUses'].pop(),lambda row:row['cameraUses'][1].update(eye='left'),
            lambda row:row['cameraUses'][1].update(slot=22),lambda row:row['cameraUses'][1].update(batchSequence=1002),
            lambda row:row['cameraUses'][1].update(drawViewport=[0,0,4,6]),
            lambda row:row['cameraUses'][1].update(drawCommands=2),lambda row:row.update(drawCommands=2),
            lambda row:row.update(cameraUses=row['cameraUses']*2)]
        for fault in faults:
            b=ModelBoundary();fault(b.trace['models'][0])
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):b.reader().read(b.capture)
        b=ModelBoundary();row=b.trace['models'][0];row['drawCommands']=6
        for use in row['cameraUses']:use['drawCommands']=6
        b.trace['drawCommands']=6
        with self.assertRaises(NativeUIError):b.reader().read(b.capture)

    def test_duplicate_models_or_aggregate_claims_cannot_reuse_an_actual_draw(self):
        for duplicate in (True,False):
            b=ModelBoundary();other=deepcopy(b.trace['models'][0]);other['drawCommands']=5
            for use in other['cameraUses']:use['drawCommands']=5
            if not duplicate:other['modelInstance']='4'*32
            b.trace['models'].append(other);b.trace['drawCommands']=6
            with self.subTest(duplicate=duplicate),self.assertRaises(NativeUIError):b.reader().read(b.capture)

    def test_loaded_geometry_rig_pose_and_central_recorded_view_cannot_be_replaced(self):
        changes=[lambda s:s.update(rigId=5),lambda s:s.update(modelInstance='4'*32),
            lambda s:s['geometry'].update(instance='4'*32),lambda s:s['geometry'].update(sourceSha256='4'*64),
            lambda s:s['pose'].update(feetPosition=[.01,0,-2]),lambda s:s['view'].update(position=[.1,0,0]),
            lambda s:s.update(visible=False)]
        for change in changes:
            b=ModelBoundary();draws=b.reader().read(b.capture);before,after=b.avatars();change(after['source'])
            with self.subTest(change=change),self.assertRaises(NativeUIError):avatar_draws(before,after,b.capture,draws,31,20000)
        for change in (dict(originalGeometryDrawCommands=0),dict(skinnedDrawCommands=0),dict(geometryInstance='4'*32)):
            b=ModelBoundary();b.trace['models'][0].update(change);draws=b.reader().read(b.capture)
            with self.subTest(change=change),self.assertRaises(NativeUIError):avatar_draws(*b.avatars(),b.capture,draws,31,20000)

    def test_ignored_input_candidate_loss_and_late_native_clock_never_return_draws(self):
        b=ModelBoundary();b.ignore=True
        with self.assertRaises(NativeUIError):b.reader().read(b.capture)
        self.assertEqual(1,len(b.commands))
        for mode in ('lost','stale'):
            b=ModelBoundary();reader=b.reader();guards=[0]
            def guard():
                guards[0]+=1
                if guards[0]==5:
                    if mode=='lost':return False
                    b.epoch+=2000
                return True
            reader.guard=guard
            with self.subTest(mode=mode),self.assertRaises(NativeUIError):reader.read(b.capture)
            self.assertIsNone(reader.last)

    def test_probe_forwards_once_and_missing_native_source_remains_unavailable(self):
        program=r'''
const objectKeysMatch=(v,keys)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(keys.sort());
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
let files=[],calls=[];const original={requestId:"a".repeat(32),source:{original:true}};
const Test={featurePicoWorldModelDrawsObservation:c=>{calls.push(c);return original;},saveObject:(v,name)=>files.push({v,name})};
SOURCE
const request={schemaVersion:1,commandId:"a".repeat(32),action:"feature-pico-world-model-draws-observe",captureRequestId:"b".repeat(32)};
applyAndroidControlCommand(request);applyAndroidControlCommand(request);
if(calls.length!==1||files.length!==1||files[0].v!==original||files[0].name!=="feature-pico-world-model-draws.json")throw Error("changed/replayed original");
applyClientCommand({...request,commandId:"c".repeat(32),expectedModel:"wanted"});if(calls.length!==1)throw Error("selector admitted");
delete Test.featurePicoWorldModelDrawsObservation;applyClientCommand({...request,commandId:"d".repeat(32)});
if(files.length!==2||files[1].v.available!==false)throw Error("missing source green");
'''.replace('SOURCE',probe_source())
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)


if __name__=='__main__':unittest.main()
