"""Synthetic native GPU/fence/lifetime boundaries, no C++ or device execution."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.native_completed_frame import NativeCompletedFrame,command,validate,storage,absent
from adapters.normal_ui import NativeUIError
from self_tests.test_native_feature_observation import probe_source

REQUEST='ios-'+'a'*32


def query(operation='read',nonce='b'):
    return dict(schemaVersion=1,commandId='ios-'+nonce*32,action='feature-completed-frame',requestId=REQUEST,operation=operation)


def view():
    return dict(position=[0,1.6,0],rotation=[0,0,0,1],fieldOfViewDegrees=60,aspectRatio=1.6,
        nearClip=.1,farClip=100,perspective=True,
        projection=[1.0825,0,0,0,0,1.732,0,0,0,0,-1.002,-.2002,0,0,-1,0])


class Boundary:
    def __init__(self):
        self.clock=0.;self.offset=1700000000000+86400000;self.commands=[];self.intents=[];self.sequence=0;self.value=None
        self.started=None;self.request=None;self.partial=0;self.ignore=False;self.no_fence=False;self.change=None
        self.okay=True;self.intent_fail=False;self.retired=False;self.held=False;self.gpu_pending=False
        self.metadata=False;self.callback_due=0.;self.frame_index=42;self.source_extent=[800,500];self.target_extent=[1600,1000]
        self.actual_draws=5;self.cpu_draw_opcodes=999
    def epoch(self):return self.offset+round(self.clock*1000)
    def sleep(self,seconds):self.clock+=seconds
    def intent(self,value):
        self.intents.append(deepcopy(value))
        if self.intent_fail:raise NativeUIError('Synthetic intent persistence failure')
    def send(self,value):
        command(value);self.commands.append(deepcopy(value))
        if self.ignore:return
        operation=value['operation']
        if operation=='read':
            if self.retired:self.value=dict(commandId=value['commandId'],requestId=REQUEST,available=False);return
            self.started=self.clock;self.request=deepcopy(value);self.held=self.gpu_pending=True;self.metadata=False
            self.value=dict(completedFrameVersion=1,commandId=value['commandId'],requestId=REQUEST,pending=True)
        else:
            if operation=='release':self.retired=True;self.metadata=False;self.callback_due=self.clock+.1
            held=self.held and (self.no_fence or self.clock<self.callback_due)
            source=dict(retired=self.retired,present=not self.retired,callbacks=1 if held else 0,
                gpuPending=self.gpu_pending,metadataBytes=200 if self.metadata else 0)
            if operation=='release':source['performed']=True
            self.sequence+=1
            self.value=dict(frameStorageVersion=1,commandId=value['commandId'],requestId=REQUEST,operation=operation,
                instance='c'*32,sequence=self.sequence,processId=42,requestedEpochMs=self.epoch(),capturedEpochMs=self.epoch(),source=source)
        if self.change:self.change(self.value)
    def original(self):
        if self.partial:self.partial-=1;return '{'
        if self.request is not None and self.value.get('pending') is True and not self.no_fence and self.clock-self.started>=.05:
            self.sequence+=1;requested=self.offset+round(self.started*1000)
            trace=dict(completedDrawTraceVersion=1,frameId='d'*32,recordedEpochMs=requested+1,recordedView=view(),
                begunEpochMs=requested+2,completedEpochMs=requested+4,drawSource='vulkan-api-issued',renderer='forward',view='main-mono',
                forwardBatches=1,forwardDrawCalls=self.actual_draws,hazeBatches=0,hazeDrawCalls=0,mirrorBatches=0,mirrorDrawCalls=0)
            self.value=dict(completedFrameVersion=1,commandId=self.request['commandId'],requestId=REQUEST,instance='c'*32,
                sequence=self.sequence,processId=42,requestedEpochMs=requested,capturedEpochMs=self.epoch(),source=dict(
                    backend='vulkan',stage='tone-map-before-hud',view='main-mono',sourceExtent=list(self.source_extent),
                    targetExtent=list(self.target_extent),renderTrace=trace,frameIndex=self.frame_index,
                    submittedEpochMs=requested+5,fenceObservedEpochMs=self.epoch()))
            self.metadata=True;self.gpu_pending=False
            if self.change:self.change(self.value)
        return json.dumps(self.value) if self.value is not None else ''
    def reader(self):return NativeCompletedFrame(self.send,self.original,self.epoch,lambda:self.okay,42,self.intent,
        monotonic=lambda:self.clock,sleep=self.sleep)


class CompletedFrameTests(unittest.TestCase):
    def test_original_fence_time_allocations_and_issued_draws_are_preserved_under_host_clock_skew(self):
        b=Boundary();reader=b.reader();value=reader.perform(query())
        self.assertEqual(b.value,value);self.assertEqual(b.source_extent,value['source']['sourceExtent'])
        self.assertEqual(5,value['source']['renderTrace']['forwardDrawCalls'])
        self.assertNotEqual(b.cpu_draw_opcodes,value['source']['renderTrace']['forwardDrawCalls'])
        self.assertGreater(value['capturedEpochMs'],1700000000000+86400000)
        self.assertEqual([query()],b.commands);self.assertEqual(b.commands,b.intents)
        self.assertNotIn('expected',json.dumps(b.commands));self.assertNotIn('renderScale',json.dumps(b.commands))

    def test_submit_or_record_without_original_fence_completion_cannot_publish_a_frame_or_replay_request(self):
        b=Boundary();b.no_fence=True;reader=b.reader()
        with self.assertRaises(NativeUIError):reader.perform(query())
        with self.assertRaises(NativeUIError):reader.perform(query())
        self.assertEqual(1,len(b.commands));self.assertIsNone(reader.last);self.assertEqual(1,len(b.intents))

    def test_release_ack_is_not_original_callback_or_gpu_consumer_absence(self):
        b=Boundary();reader=b.reader();reader.perform(query())
        released=reader.perform(query('release','e'));self.assertFalse(absent(released));self.assertEqual(1,released['source']['callbacks'])
        b.sleep(.2);actual=reader.perform(query('inspect','f'));self.assertTrue(absent(actual))
        self.assertEqual(0,actual['source']['metadataBytes']);self.assertFalse(actual['source']['gpuPending'])
        with self.assertRaises(NativeUIError):reader.perform(query('read','1'))

    def test_missing_submitted_fence_proof_remains_pending_even_after_release(self):
        b=Boundary();b.no_fence=True;reader=b.reader()
        with self.assertRaises(NativeUIError):reader.perform(query())
        released=reader.perform(query('release','e'));b.sleep(.2);value=reader.perform(query('inspect','f'))
        self.assertTrue(released['source']['performed']);self.assertFalse(absent(value))
        self.assertTrue(value['source']['gpuPending']);self.assertEqual(1,value['source']['callbacks'])

    def test_changed_backend_clock_pid_nonce_or_capture_shape_cannot_become_a_completed_frame(self):
        faults=[lambda v:v.update(processId=99),lambda v:v.update(capturedEpochMs=1),lambda v:v.update(instance=True),
            lambda v:v['source'].update(backend='opengl'),lambda v:v['source'].update(sourceExtent=[True,500]),
            lambda v:v['source'].update(targetExtent=[0,1000]),lambda v:v['source'].update(fenceObservedEpochMs=1),
            lambda v:v['source'].update(performed=True),lambda v:v['source']['renderTrace'].update(drawSource='cpu-opcodes'),
            lambda v:v['source']['renderTrace'].update(forwardDrawCalls=True),
            lambda v:v['source']['renderTrace']['recordedView'].update(projection=[0]*16),
            lambda v:v['source']['renderTrace']['recordedView'].update(rotation=[0,0,0,0])]
        for fault in faults:
            b=Boundary();b.change=lambda v:fault(v) if 'source' in v else None;reader=b.reader()
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):reader.perform(query())
            self.assertIsNone(reader.last);self.assertEqual(1,len(b.commands))

    def test_pending_partial_originals_retry_only_reads_and_never_change_original_packet_time(self):
        b=Boundary();b.partial=2;value=b.reader().perform(query())
        self.assertEqual(value,b.value);stamp=value['capturedEpochMs'];b.sleep(.2)
        self.assertEqual(stamp,json.loads(b.original())['capturedEpochMs']);self.assertEqual(1,len(b.commands))

    def test_failed_intent_clock_regression_and_late_original_receipt_refuse_success(self):
        b=Boundary();b.intent_fail=True
        with self.assertRaises(NativeUIError):b.reader().perform(query())
        self.assertEqual([],b.commands)
        for fault in ('clock','guard','budget'):
            b=Boundary();reader=b.reader();original=reader.clock_ms;calls=[]
            def clock():
                calls.append(True)
                if len(calls)==3:
                    if fault=='clock':return b.offset-1
                    if fault=='guard':b.okay=False
                    else:b.clock+=2
                return original()
            reader.clock_ms=clock
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):reader.perform(query())
            self.assertIsNone(reader.last);self.assertEqual(1,len(b.commands))

    def test_closed_ios_command_and_fixture_grammar_cannot_accept_settings_or_expected_frame_values(self):
        from fixture.serve import FixtureState
        fixture=FixtureState();self.assertEqual(query(),fixture.set_client_command(query()))
        for changes in (dict(expectedScale=.5),dict(frameIndex=42),dict(commandId='a'*32),dict(schemaVersion=True),dict(operation='reset')):
            with self.subTest(changes=changes),self.assertRaises((NativeUIError,ValueError)):fixture.set_client_command(query()|changes)

    def test_boolean_or_ack_only_absence_and_regressed_fence_storage_packets_fail(self):
        b=Boundary();reader=b.reader();reader.perform(query());value=reader.perform(query('release','e'));request=query('release','e')
        for fields in (dict(callbacks=False),dict(gpuPending=0),dict(metadataBytes=False),dict(expectedAbsent=True)):
            changed=deepcopy(value);changed['source'].update(fields)
            with self.assertRaises(NativeUIError):storage(changed,request,42,b.epoch())
        with self.assertRaises(NativeUIError):absent(dict(source=dict(retired=True,present=False,callbacks=0,gpuPending=False,metadataBytes=0)))

    def test_actual_probe_keeps_original_frame_object_and_retires_queued_read_before_cleanup(self):
        program=r'''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,k)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.sort());
let calls=[],files=[],timers=[],cleared=[],ready=false;
const Script={setTimeout:f=>{timers.push(f);return timers.length;},clearTimeout:id=>cleared.push(id)};
const original={completedFrameVersion:1,commandId:"ios-"+"b".repeat(32),requestId:"ios-"+"a".repeat(32),capturedEpochMs:17000};
const Test={featureCompletedFrameObservation:c=>{calls.push(c);return c.operation==='read'?(ready?original:{commandId:c.commandId,requestId:c.requestId,pending:true}):{commandId:c.commandId,requestId:c.requestId,performed:true};},saveObject:(v,name)=>files.push({v,name})};
SOURCE
const read={schemaVersion:1,commandId:original.commandId,requestId:original.requestId,action:"feature-completed-frame",operation:"read"};
applyClientCommand(read);if(files.length!==0||timers.length!==1)throw Error("pending frame published");
ready=true;timers[0]();applyClientCommand(read);
if(calls.length!==2||files.length!==1||files[0].v!==original||files[0].v.capturedEpochMs!==17000||files[0].name!=="feature-completed-frame.json")throw Error("original frame changed or HTTP read replayed");
ready=false;const next={...read,commandId:"ios-"+"c".repeat(32),requestId:"ios-"+"d".repeat(32)};
applyClientCommand(next);const queued=timers[timers.length-1];
applyClientCommand({...next,commandId:"ios-"+"e".repeat(32),operation:"release"});
const count=calls.length,writes=files.length;queued();
if(calls.length!==count||files.length!==writes||cleared.length===0)throw Error("retired queued read entered source");
applyClientCommand({...next,commandId:"ios-"+"f".repeat(32),expectedScale:.5});
if(calls.length!==count)throw Error("expected scale reached native source");
'''.replace('SOURCE',probe_source())
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)


if __name__=='__main__':unittest.main()
