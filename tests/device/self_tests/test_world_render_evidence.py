"""Original world-target reader boundaries; no renderer or device execution."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import sys
import subprocess
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from PIL import Image
from adapters.normal_ui import NativeUIError
from adapters.world_render_evidence import NativeWorldRenderCapture,image_name,measured_scale


def png(size=(16,12),mode='RGBA',color=(25,90,210,255)):
    image=Image.new(mode,size,color);output=io.BytesIO();image.save(output,format='PNG')
    return output.getvalue(),hashlib.sha256(image.tobytes()).hexdigest()


class Boundary:
    def __init__(self):
        self.sequence=self.acquisition=0;self.clock=0.0
        self.commands,self.reads,self.intents=[],[],[];self.sample=None
        self.block_intent=False
        self.raw,self.pixels=png();self.okay=True;self.ignore=False;self.ignore_gpu=False
        self.mutate=None;self.file_delay=0.0;self.file_guard_loss=False
        self.file_source=self

    def intent(self,command):
        self.intents.append(deepcopy(command))
        if self.block_intent:raise NativeUIError('Original acquisition intent could not be saved')

    def send(self,command):
        assert self.intents and self.intents[-1]==command
        self.commands.append(deepcopy(command))
        if self.ignore:return
        self.sequence+=1
        if not self.ignore_gpu:self.acquisition+=1
        source=dict(captureVersion=1,available=True,acquisitionSequence=self.acquisition,
            recordedEpochMs=20000,startedEpochMs=20000,capturedEpochMs=20000,backend='opengl',
            stage='tone-map-before-hud',view='main-mono',sourceExtent=[16,12],sourceViewport=[0,0,8,6],
            targetExtent=[16,12],pixelFormat='rgba8-top-left',image=dict(name=image_name(command['commandId']),bytes=len(self.raw),
                sha256=hashlib.sha256(self.raw).hexdigest(),pixelSha256=self.pixels,width=16,height=12))
        self.sample=dict(schemaVersion=1,requestId=command['commandId'],instance='a'*32,sequence=self.sequence,
            requestedEpochMs=20000,capturedEpochMs=20000,processId=31,source=source)
        if self.mutate:self.mutate(self.sample)

    def original(self):return json.dumps(self.sample) if self.sample is not None else ''
    def read(self,name):
        self.reads.append(name);self.clock+=self.file_delay
        if self.file_guard_loss:self.okay=False
        return self.raw
    def sleep(self,seconds):self.clock+=seconds
    def reader(self,**options):
        return NativeWorldRenderCapture(self.send,self.original,self.file_source,lambda:20000,lambda:self.okay,31,
            intent=self.intent,monotonic=lambda:self.clock,sleep=self.sleep,**options)


class WorldRenderEvidenceTests(unittest.TestCase):
    def test_original_rgba_pixels_and_actual_viewport_scale_are_distinct_from_preferences(self):
        source=Boundary();value,raw=source.reader().read(0)
        self.assertEqual(source.raw,raw);self.assertEqual({'x':0.5,'y':0.5},measured_scale(value))
        self.assertEqual([image_name(source.commands[0]['commandId'])],source.reads)
        self.assertEqual({'schemaVersion','commandId','action'},set(source.commands[0]))
        self.assertEqual('feature-world-render-observe',source.commands[0]['action'])
        self.assertNotIn('expected',json.dumps(source.commands));self.assertNotIn('marker',json.dumps(source.commands))

    def test_ignored_gpu_acquisition_cannot_hide_behind_fresh_control_ack_or_sequence(self):
        source=Boundary();reader=source.reader();value,_=reader.read(0);source.ignore_gpu=True
        with self.assertRaises(NativeUIError):reader.read(value['sequence'])
        self.assertEqual(1,len(source.reads));self.assertEqual(2,len(source.commands))

    def test_unchanged_original_pixels_are_valid_acquisition_but_not_an_effect_verdict(self):
        source=Boundary();reader=source.reader();first,pixels=reader.read(0);second,again=reader.read(first['sequence'])
        self.assertEqual(pixels,again);self.assertGreater(second['source']['acquisitionSequence'],first['source']['acquisitionSequence'])
        self.assertNotIn('passed',second);self.assertNotIn('hazePass',second['source'])

    def test_unavailable_vulkan_stereo_or_post_ui_source_never_reads_default_image(self):
        for change in ({'available':False},{'backend':'vulkan'},{'view':'main-stereo'},{'stage':'ui-composite'}):
            with self.subTest(change=change):
                source=Boundary();source.mutate=lambda packet:packet['source'].update(change)
                with self.assertRaises(NativeUIError):source.reader().read(0)
                self.assertEqual([],source.reads)

    def test_foreign_file_stale_original_and_swapped_pixel_channels_cannot_pass(self):
        for fault in ('missing','bytes','pixels','name'):
            with self.subTest(fault=fault):
                source=Boundary();original=source.read
                def read(name):
                    value=original(name)
                    if fault=='missing':return b''
                    if fault=='bytes':return value[:-8]
                    if fault=='pixels':return png(color=(210,90,25,255))[0]
                    return value
                source.read=read
                if fault=='name':source.mutate=lambda v:v['source']['image'].update(name='foreign-user.png')
                with self.assertRaises(NativeUIError):source.reader().read(0)

    def test_png_digest_cannot_substitute_original_rgba_digest_or_dimensions(self):
        for fault in ('raw-pixels','dimensions','mode','non-png'):
            with self.subTest(fault=fault):
                source=Boundary()
                if fault=='raw-pixels':source.pixels='f'*64
                elif fault=='dimensions':source.raw,source.pixels=png(size=(8,6))
                elif fault=='mode':source.raw,source.pixels=png(mode='RGB',color=(25,90,210))
                else:source.raw=b'not a PNG'
                with self.assertRaises(NativeUIError):source.reader().read(0)

    def test_old_foreign_or_contradictory_acquisition_times_cannot_be_retimed(self):
        for change in ({'capturedEpochMs':18000},{'recordedEpochMs':19999},{'startedEpochMs':19999},{'capturedEpochMs':20001}):
            with self.subTest(change=change):
                source=Boundary();source.mutate=lambda v:v['source'].update(change)
                with self.assertRaises(NativeUIError):source.reader().read(0)
                self.assertEqual([],source.reads)

    def test_malformed_viewport_extent_digest_and_extra_expected_state_are_rejected(self):
        for change in ({'sourceViewport':[0,0,32,12]},{'sourceViewport':[0,0,True,12]},
            {'targetExtent':[4096,4096]},{'sourceExtent':[0,12]},{'captureVersion':True},{'expectedScale':0.5}):
            with self.subTest(change=change):
                source=Boundary();source.mutate=lambda v:v['source'].update(change)
                with self.assertRaises(NativeUIError):source.reader().read(0)
                self.assertEqual([],source.reads)

    def test_process_or_native_instance_replacement_never_adopts_new_image_context(self):
        for change in ({'processId':99},{'instance':'f'*32}):
            with self.subTest(change=change):
                source=Boundary();reader=source.reader();first,_=reader.read(0)
                source.mutate=lambda v:v.update(change)
                with self.assertRaises(NativeUIError):reader.read(first['sequence'])
                self.assertEqual(1,len(source.reads))

    def test_missing_or_foreign_replies_retry_reads_only_and_bound_the_request(self):
        for ignored in (False,True):
            source=Boundary();source.ignore=ignored
            if not ignored:source.mutate=lambda v:v.update(requestId='f'*32)
            with self.assertRaises(NativeUIError):source.reader().read(0)
            self.assertEqual(1,len(source.commands));self.assertEqual([],source.reads)
            self.assertLessEqual(source.clock,5.1)

    def test_partial_json_reads_do_not_replay_or_retime_native_acquisition(self):
        source=Boundary();reader=source.reader();original=source.original;reads=[]
        def partial():
            reads.append(1);return '{' if len(reads)==1 else original()
        reader.original=partial
        value,_=reader.read(0)
        self.assertEqual(20000,value['source']['capturedEpochMs']);self.assertEqual(1,len(source.commands))
        self.assertEqual(2,len(reads))

    def test_file_transfer_guard_and_total_deadline_include_binary_transfer(self):
        for loss in (False,True):
            source=Boundary();source.file_guard_loss=loss;source.file_delay=0 if loss else 6
            with self.assertRaises(NativeUIError):source.reader().read(0)
            self.assertEqual(1,len(source.commands))

    def test_ios_nonce_causality_bounds_age_without_equal_native_host_clocks(self):
        source=Boundary();reader=source.reader(ios=True);reader.clock_ms=lambda:999999999
        value,_=reader.read(0);self.assertTrue(source.commands[0]['commandId'].startswith('ios-'))
        source.file_delay=1.6
        with self.assertRaises(NativeUIError):reader.read(value['sequence'])
        self.assertEqual(2,len(source.commands))

    def test_failed_durable_acquisition_intent_prevents_native_request_and_file_creation(self):
        source=Boundary();source.block_intent=True
        with self.assertRaises(NativeUIError):source.reader().read(0)
        self.assertEqual([],source.commands);self.assertEqual([],source.reads)
        self.assertEqual(1,len(source.intents))

    def test_existing_fixture_admits_only_closed_read_only_world_requests(self):
        from fixture.serve import FixtureState
        fixture=FixtureState();request=dict(schemaVersion=1,commandId='ios-'+'a'*32,action='feature-world-render-observe')
        self.assertEqual(request,fixture.set_client_command(request))
        for change in ({'expected':{}},{'source':'user-image.png'},{'schemaVersion':True},{'width':640}):
            with self.subTest(change=change),self.assertRaises(ValueError):fixture.set_client_command(request|change)

    def test_actual_probe_preserves_original_or_unavailable_results_and_bounds_pending_reads(self):
        from self_tests.test_native_feature_observation import probe_source
        program=r'''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,keys)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(keys.sort());
let files=[],calls=[],queue=[];
const Script={setTimeout:f=>{queue.push(f);return queue.length;},clearTimeout:()=>{}};
const Test={featureWorldRenderCapture:id=>{calls.push(id);return {requestId:id,pending:true};},saveObject:(v,name)=>files.push({v,name})};
SOURCE
const request={schemaVersion:1,commandId:"a".repeat(32),action:"feature-world-render-observe"};
applyAndroidControlCommand(request);applyAndroidControlCommand(request);
while(queue.length)queue.shift()();
if(calls.length!==51||files.length!==1||files[0].v.available!==false)throw Error("pending result was green or replayed");
const actual={requestId:"b".repeat(32),capturedEpochMs:17000,source:{acquisitionSequence:7}};
Test.featureWorldRenderCapture=id=>{calls.push(id);return actual;};
applyClientCommand({...request,commandId:"b".repeat(32)});
if(files[1].name!=="world-render-observation.json"||files[1].v!==actual||actual.capturedEpochMs!==17000)throw Error("original was retimed");
const before=calls.length;
applyClientCommand({...request,commandId:"c".repeat(32),expected:{pixels:"desired"}});
if(calls.length!==before)throw Error("expected input reached native source");
delete Test.featureWorldRenderCapture;applyClientCommand({...request,commandId:"d".repeat(32)});
if(files[2].v.available!==false)throw Error("missing hook green");
'''.replace('SOURCE',probe_source())
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)

    def test_decode_and_post_decode_guard_are_inside_the_acquisition_budget(self):
        source=Boundary();reader=source.reader()
        from adapters.world_render_evidence import original_pixels
        def delayed(value,raw):
            actual=original_pixels(value,raw);source.clock+=6;return actual
        with patch('adapters.world_render_evidence.original_pixels',side_effect=delayed),self.assertRaises(NativeUIError):reader.read(0)
        self.assertEqual(0,reader.sequence)
        source=Boundary();source.file_delay=1;reader=source.reader()
        def regressed(value,raw):
            actual=original_pixels(value,raw);source.clock=0.5;return actual
        with patch('adapters.world_render_evidence.original_pixels',side_effect=regressed),self.assertRaises(NativeUIError):reader.read(0)
        self.assertEqual(0,reader.sequence)


class RenderTraceTests(unittest.TestCase):
    def boundary(self):
        source=Boundary()
        def trace(packet):
            packet['source'].update(captureVersion=2,renderTrace=dict(traceVersion=1,
                frameId=format(source.acquisition,'032x'),recordedEpochMs=20000,begunEpochMs=20000,
                completedEpochMs=20000,renderer='forward',view='main-mono',forwardBatches=2,
                forwardDrawCommands=8,hazeBatches=2,hazeDrawCommands=8,mirrorBatches=1,mirrorDrawCommands=1))
        source.mutate=trace
        return source

    def rejects(self,change):
        source=self.boundary();original=source.mutate
        def fault(packet):original(packet);packet['source']['renderTrace'].update(change)
        source.mutate=fault
        with self.assertRaises(NativeUIError):source.reader(require_trace=True).read(0)
        self.assertEqual([],source.reads)

    def test_same_view_trace_preserves_original_facts_and_pixels(self):
        source=self.boundary();reader=source.reader(require_trace=True);value,raw=reader.read(0)
        self.assertEqual(source.raw,raw);self.assertEqual(2,value['source']['captureVersion'])
        self.assertEqual(8,value['source']['renderTrace']['hazeDrawCommands'])
        self.assertNotIn('hazePass',value['source']);self.assertNotIn('passed',value['source']['renderTrace'])
        second,_=reader.read(value['sequence'])
        self.assertNotEqual(value['source']['renderTrace']['frameId'],second['source']['renderTrace']['frameId'])

    def test_legacy_acquisition_is_readable_but_cannot_supply_required_trace(self):
        source=Boundary();source.reader().read(0)
        source=Boundary()
        with self.assertRaises(NativeUIError):source.reader(require_trace=True).read(0)
        self.assertEqual([],source.reads)

    def test_missing_trace_or_version_downgrade_does_not_fall_back(self):
        for fault in ('missing','downgrade','unknown'):
            source=self.boundary();original=source.mutate
            def change(packet):
                original(packet)
                if fault=='missing':packet['source'].pop('renderTrace')
                elif fault=='downgrade':packet['source']['captureVersion']=1
                else:packet['source']['captureVersion']=3
            source.mutate=change
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.reader().read(0)
            self.assertEqual([],source.reads)

    def test_new_capture_nonce_and_cursor_cannot_reuse_a_previous_frame(self):
        source=self.boundary();reader=source.reader(require_trace=True);first,_=reader.read(0);original=source.mutate
        def old(packet):original(packet);packet['source']['renderTrace']['frameId']=first['source']['renderTrace']['frameId']
        source.mutate=old
        with self.assertRaises(NativeUIError):reader.read(first['sequence'])
        self.assertEqual(1,len(source.reads));self.assertEqual(first['sequence'],reader.sequence)

    def test_stale_trace_cannot_hide_behind_a_fresh_image(self):
        self.rejects(dict(recordedEpochMs=18000))

    def test_trace_recording_must_precede_its_capture_ticket(self):
        self.rejects(dict(recordedEpochMs=20001,begunEpochMs=20001,completedEpochMs=20001))

    def test_execution_must_begin_before_completion_and_end_before_readback(self):
        for change in (dict(begunEpochMs=20001),dict(completedEpochMs=20001),dict(begunEpochMs=19999)):
            with self.subTest(change=change):self.rejects(change)

    def test_foreign_renderer_view_or_frame_identity_is_not_a_primary_trace(self):
        for change in (dict(renderer='deferred'),dict(view='mirror'),dict(frameId=''),dict(frameId='user-frame')):
            with self.subTest(change=change):self.rejects(change)

    def test_trace_contract_is_closed_and_does_not_accept_feature_verdicts(self):
        for change in (dict(traceVersion=True),dict(traceVersion=2),dict(hazePass=True),dict(expectedMirror=True)):
            with self.subTest(change=change):self.rejects(change)

    def test_draw_counts_are_actual_integers_not_flags_or_unbounded_claims(self):
        for change in (dict(hazeDrawCommands=True),dict(mirrorBatches=-1),dict(forwardDrawCommands=1000001),
                dict(mirrorBatches=65537,mirrorDrawCommands=65537),dict(hazeDrawCommands='8')):
            with self.subTest(change=change):self.rejects(change)

    def test_haze_batch_counts_cannot_exceed_the_actual_forward_subset(self):
        for change in (dict(hazeBatches=3),dict(hazeDrawCommands=9),dict(forwardBatches=3,forwardDrawCommands=9)):
            with self.subTest(change=change):self.rejects(change)

    def test_acknowledged_empty_batches_cannot_claim_draws_or_hide_missing_batches(self):
        for change in (dict(mirrorBatches=0),dict(mirrorDrawCommands=0),dict(mirrorBatches=2)):
            with self.subTest(change=change):self.rejects(change)

    def test_no_haze_or_mirror_draws_remain_valid_zero_facts_not_inferred_success(self):
        source=self.boundary();original=source.mutate
        def empty(packet):
            original(packet)
            packet['source']['renderTrace'].update(hazeBatches=0,hazeDrawCommands=0,mirrorBatches=0,mirrorDrawCommands=0)
        source.mutate=empty;value,_=source.reader(require_trace=True).read(0)
        self.assertEqual(0,value['source']['renderTrace']['hazeDrawCommands'])
        self.assertEqual(0,value['source']['renderTrace']['mirrorDrawCommands'])

    def test_unique_frame_inventory_is_bounded_without_forgetting_old_frames(self):
        source=self.boundary();reader=source.reader(require_trace=True);reader.frames={format(i+100,'032x') for i in range(256)}
        with self.assertRaises(NativeUIError):reader.read(0)
        self.assertEqual(256,len(reader.frames));self.assertEqual([],source.reads)



if __name__=='__main__':unittest.main()
