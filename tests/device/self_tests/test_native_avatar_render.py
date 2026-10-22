"""Original loaded-avatar sources at explicit native seams; no stereo verdict."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import subprocess
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.native_avatar_render import NativeAvatarRender,command as avatar_command,EMPTY_SHA256,LIMIT
from adapters.normal_ui import NativeUIError
from self_tests.test_native_feature_observation import probe_source
from fixture.serve import FixtureState

MODEL='c'*32
GEOMETRY='d'*32
LOADED='e'*64

def avatar_source():
    return dict(avatarRenderVersion=1,modelInstance=MODEL,rigId=4,loaded=True,visible=True,addedToScene=True,
        localRenderingEnabled=True,avatarShouldRender=True,geometry=dict(instance=GEOMETRY,sourcePresent=True,sourceSha256=LOADED),
        pose=dict(feetPosition=[0,0,-2],orientation=[0,0,0,1],modelScale=1),cameraMode='third person',
        view=dict(position=[0,1.6,0],rotation=[0,0,0,1],projection=[1,0,0,0,0,1,0,0,0,0,-1,-.2,0,0,-1,0],
            fieldOfViewDegrees=60,aspectRatio=1.6,nearClip=.1,farClip=100,perspective=True))

class Boundary:
    def __init__(self):
        self.epoch=20001;self.clock=0.;self.okay=True;self.ignored=False;self.sequence=0
        self.edit=None;self.commands=[];self.sample=None;self.reads=0;self.avatar=avatar_source()
    def send(self,request):
        self.commands.append(deepcopy(request))
        if self.ignored:return
        self.sequence+=1
        self.sample=dict(schemaVersion=1,requestId=request['commandId'],instance='f'*32,sequence=self.sequence,processId=31,
            requestedEpochMs=self.epoch,capturedEpochMs=self.epoch,source=deepcopy(self.avatar))
        if self.edit:self.edit(self.sample)
    def original(self):self.reads+=1;return '' if self.sample is None else json.dumps(self.sample)
    def sleep(self,seconds):self.clock+=seconds
    def reader(self,**options):
        return NativeAvatarRender(self.send,self.original,lambda:self.epoch,lambda:self.okay,31,
            monotonic=lambda:self.clock,sleep=self.sleep,**options)

class OriginalAvatarRenderTests(unittest.TestCase):
    def test_optional_original_hmd_boom_extension_is_closed_and_never_implied_for_legacy_sources(self):
        b=Boundary();self.assertNotIn('cameraState',b.reader().read()['source'])
        b.avatar.update(cameraStateVersion=1,cameraState=dict(hmd=True,boomLength=4.25,zoomMin=.5,zoomDefault=1.5))
        self.assertEqual(4.25,b.reader().read()['source']['cameraState']['boomLength'])
        original=deepcopy(b.avatar)
        for edit in (lambda s:s.pop('cameraState'),lambda s:s.pop('cameraStateVersion'),
                lambda s:s.update(cameraStateVersion=True),lambda s:s['cameraState'].update(hmd=1),
                lambda s:s['cameraState'].update(boomLength=False),lambda s:s['cameraState'].update(boomLength=.1),
                lambda s:s['cameraState'].update(zoomDefault=.1),lambda s:s['cameraState'].update(expectedMode='look at')):
            b.avatar=deepcopy(original);edit(b.avatar)
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):b.reader().read()

    def test_unloaded_hidden_or_disabled_original_is_observable_without_render_verdict(self):
        b=Boundary();b.avatar.update(loaded=False,geometry=None,visible=False,localRenderingEnabled=False)
        value=b.reader().read();self.assertEqual(b.avatar,value['source'])
        self.assertNotIn('stereo',value);self.assertNotIn('image',value)

    def test_closed_command_rejects_requested_models_and_coerced_versions(self):
        original=dict(schemaVersion=1,commandId='a'*32,action='feature-avatar-render-observe')
        self.assertEqual(original,avatar_command(original))
        for change in (dict(schemaVersion=True),dict(expectedModel=MODEL),dict(commandId='ios-'+'a'*32),dict(action='set-avatar')):
            with self.subTest(change=change),self.assertRaises(NativeUIError):avatar_command(original|change)

    def test_final_native_clock_after_retained_copy_cannot_hide_behind_frozen_host_time(self):
        b=Boundary();reader=b.reader();copies=[0]
        def copying(value):
            copies[0]+=1
            if copies[0]==2:b.epoch+=2000
            return deepcopy(value)
        with patch('adapters.native_avatar_render.deepcopy',side_effect=copying),self.assertRaises(NativeUIError):reader.read()
        self.assertIsNone(reader.last);self.assertEqual(0,b.clock)

    def test_candidate_guard_after_retained_copy_is_required_and_included_in_native_age(self):
        for fault in ('candidate-loss','native-clock-jump'):
            b=Boundary();reader=b.reader();calls=[0]
            def guard():
                calls[0]+=1
                if calls[0]==5:
                    if fault=='candidate-loss':return False
                    b.epoch+=2000
                return True
            reader.guard=guard
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):reader.read()
            self.assertIsNone(reader.last);self.assertEqual(0,b.clock)

    def test_actual_probe_forwards_original_once_and_missing_native_hook_stays_unavailable(self):
        program=r'''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,keys)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(keys.sort());
let files=[],calls=[];
const original={schemaVersion:1,requestId:"a".repeat(32),capturedEpochMs:17000,source:{nativeOriginal:true}};
const Test={featureAvatarRenderObservation:c=>{calls.push(c);return original;},saveObject:(v,name)=>files.push({v,name})};
SOURCE
const request={schemaVersion:1,commandId:"a".repeat(32),action:"feature-avatar-render-observe"};
applyAndroidControlCommand(request);applyAndroidControlCommand(request);
if(calls.length!==1||files.length!==1||files[0].v!==original||files[0].name!=="feature-avatar-render.json")throw Error("original changed/replayed");
applyClientCommand({...request,commandId:"b".repeat(32),expectedModel:"wanted"});
if(calls.length!==1)throw Error("requested model admitted");
delete Test.featureAvatarRenderObservation;
applyClientCommand({...request,commandId:"c".repeat(32)});
if(files.length!==2||files[1].v.available!==false||original.capturedEpochMs!==17000)throw Error("missing source green");
'''.replace('SOURCE',probe_source())
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)

    def test_shared_fixture_accepts_only_closed_observation(self):
        fixture=FixtureState();value=dict(schemaVersion=1,commandId='ios-'+'a'*32,action='feature-avatar-render-observe')
        self.assertEqual(value,fixture.set_client_command(value))
        with self.assertRaises(ValueError):fixture.set_client_command(value|dict(expectedModel=MODEL))

    def test_original_loaded_avatar_pose_view_and_source_are_not_requested_values(self):
        b=Boundary();value=b.reader().read()
        self.assertEqual(b.avatar,value['source']);self.assertEqual(b.sample,value)
        self.assertEqual({'schemaVersion','commandId','action'},set(b.commands[0]))
        self.assertNotIn('expected',json.dumps(b.commands));self.assertNotIn('passed',json.dumps(value))

    def test_source_and_pose_shapes_cannot_supply_expected_or_default_values(self):
        for change in (dict(loaded=1),dict(rigId=True),dict(modelInstance='invalid'),dict(avatarRenderVersion=True),
                dict(cameraMode='\0'),dict(expectedVisible=True),dict(geometry=None),dict(view={})):
            b=Boundary();b.avatar.update(change)
            with self.subTest(change=change),self.assertRaises(NativeUIError):b.reader().read()
        for change in (dict(feetPosition=[False,0,0]),dict(orientation=[0,0,0,0]),dict(modelScale=0),dict(modelScale=float('nan'))):
            b=Boundary();b.avatar['pose'].update(change)
            with self.subTest(change=change),self.assertRaises(NativeUIError):b.reader().read()

    def test_absent_loaded_source_preserves_actual_empty_hash_without_guessing(self):
        b=Boundary();b.avatar['geometry'].update(sourcePresent=False,sourceSha256=EMPTY_SHA256)
        self.assertFalse(b.reader().read()['source']['geometry']['sourcePresent'])
        b.avatar['geometry']['sourceSha256']=LOADED
        with self.assertRaises(NativeUIError):b.reader().read()

    def test_missing_ignored_or_unavailable_input_does_not_create_observations(self):
        for missing in ('ignored','unavailable','foreign','no-source'):
            b=Boundary();reader=b.reader()
            if missing=='ignored':b.ignored=True
            elif missing=='unavailable':b.edit=lambda value:value.update(available=False)
            elif missing=='foreign':b.edit=lambda value:value.update(requestId='b'*32)
            else:b.edit=lambda value:value.pop('source')
            with self.subTest(missing=missing),self.assertRaises(NativeUIError):reader.read()
            self.assertIsNone(reader.last);self.assertLessEqual(b.reads,51)

    def test_old_native_birth_pid_or_nonadvancing_cursor_rejects_without_consuming_it(self):
        for change in (dict(instance='a'*32),dict(processId=32),dict(sequence=1),dict(capturedEpochMs=20000,requestedEpochMs=20000)):
            b=Boundary();reader=b.reader();first=reader.read();b.edit=lambda value:value.update(change)
            with self.subTest(change=change),self.assertRaises(NativeUIError):reader.read()
            self.assertEqual(first,reader.last)

    def test_native_staleness_reverse_time_and_query_duration_do_not_retime_source(self):
        for change in (dict(capturedEpochMs=18000,requestedEpochMs=18000),dict(requestedEpochMs=20002),
                dict(requestedEpochMs=18000),dict(capturedEpochMs=20252)):
            b=Boundary();b.edit=lambda value:value.update(change)
            with self.subTest(change=change),self.assertRaises(NativeUIError):b.reader().read()

    def test_guard_loss_and_slow_read_are_included_in_final_budget(self):
        for fault in ('guard','five-second','stale-copy','stale-final-guard'):
            b=Boundary();reader=b.reader();original=reader.original;guard=reader.guard
            if fault=='guard':
                def read():value=original();b.okay=False;return value
                reader.original=read
            elif fault=='five-second':
                def read():value=original();b.clock+=5.1;return value
                reader.original=read
            elif fault=='stale-final-guard':
                calls=[0]
                def final_guard():
                    calls[0]+=1
                    if calls[0]==4:b.clock+=1.6
                    return guard()
                reader.guard=final_guard
            with self.subTest(fault=fault):
                if fault=='stale-copy':
                    def slow(value):b.clock+=1.6;return deepcopy(value)
                    with patch('adapters.native_avatar_render.deepcopy',side_effect=slow),self.assertRaises(NativeUIError):reader.read()
                else:
                    with self.assertRaises(NativeUIError):reader.read()
                self.assertIsNone(reader.last)

    def test_duplicate_json_members_nonfinite_fields_and_oversized_files_are_rejected(self):
        for raw in ('{"requestId":"a","requestId":"b"}', 'x'*(LIMIT+1)):
            b=Boundary();reader=b.reader();reader.original=lambda:raw
            with self.subTest(size=len(raw)),self.assertRaises(NativeUIError):reader.read()
        b=Boundary();b.avatar['view']['projection'][0]=float('inf')
        with self.assertRaises(NativeUIError):b.reader().read()

    def test_restore_replays_original_cursors_without_native_requests_or_retiming(self):
        b=Boundary();reader=b.reader();first=reader.read();second=reader.read();again=b.reader()
        count=len(b.commands);again.restore([first,second]);self.assertEqual(count,len(b.commands));self.assertEqual(second,again.last)
        third=again.read();self.assertGreater(third['sequence'],second['sequence'])
        bad=b.reader()
        with self.assertRaises(NativeUIError):bad.restore([second,first])

    def test_ios_nonce_and_deadline_remain_independent_of_host_wall_time(self):
        b=Boundary();reader=b.reader(ios=True);reader.clock_ms=lambda:999999999
        self.assertTrue(reader.read()['requestId'].startswith('ios-'))
        def slow():b.clock+=1.6;return b.original()
        reader.original=slow
        with self.assertRaises(NativeUIError):reader.read()
