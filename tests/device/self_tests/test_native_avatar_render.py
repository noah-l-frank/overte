"""Original avatar/model joins at synthetic native boundaries, never rendering."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.native_avatar_render import NativeAvatarRender,command as avatar_command,EMPTY_SHA256,LIMIT
from adapters.native_world_model_draws import NativeWorldModelDraws,command as draws_command,avatar_draws
from adapters.normal_ui import NativeUIError
from fixture.serve import FixtureState
from self_tests.test_world_render_evidence import trace_boundary,frame_view
from self_tests.test_native_feature_observation import probe_source

ROOT=Path(__file__).resolve().parents[3]
MODEL='c'*32
GEOMETRY='d'*32
LOADED='e'*64


def avatar_source():
    return dict(avatarRenderVersion=1,modelInstance=MODEL,rigId=4,loaded=True,visible=True,addedToScene=True,
        localRenderingEnabled=True,avatarShouldRender=True,geometry=dict(instance=GEOMETRY,sourcePresent=True,sourceSha256=LOADED),
        pose=dict(feetPosition=[0,0,-2],orientation=[0,0,0,1],modelScale=1),cameraMode='third person',view=frame_view())


def model_row():
    return dict(modelInstance=MODEL,geometryInstance=GEOMETRY,loadedSourcePresent=True,loadedSourceSha256=LOADED,
        drawCommands=3,skinnedDrawCommands=2,blendshapedDrawCommands=1,originalGeometryDrawCommands=3,indices=300,
        minimum=[-.3,0,-2.2],maximum=[.3,1.8,-1.8])


class Boundary:
    def __init__(self):
        world=trace_boundary(view=True);self.capture,self.png=world.reader(require_frame_view=True).read(0)
        self.epoch=20001;self.clock=0.;self.okay=True;self.ignored=False;self.sequence=0
        self.edit=None;self.commands=[];self.sample=None;self.reads=0
        self.avatar=avatar_source()
        self.trace=dict(modelTraceVersion=1,frameId=self.capture['source']['renderTrace']['frameId'],recordedEpochMs=20000,
            begunEpochMs=20000,completedEpochMs=20000,renderer='forward',view='main-mono',drawCommands=3,models=[model_row()])

    def send(self,request):
        self.commands.append(deepcopy(request))
        if self.ignored:return
        self.sequence+=1
        if request['action']=='feature-avatar-render-observe':source=deepcopy(self.avatar);instance='f'*32
        else:
            capture=self.capture;original=capture['source'];instance=capture['instance']
            source=dict(modelCaptureVersion=1,captureRequestId=capture['requestId'],captureSequence=capture['sequence'],
                acquisitionSequence=original['acquisitionSequence'],captureCapturedEpochMs=original['capturedEpochMs'],
                imageSha256=original['image']['sha256'],pixelSha256=original['image']['pixelSha256'],modelTrace=deepcopy(self.trace))
        self.sample=dict(schemaVersion=1,requestId=request['commandId'],instance=instance,sequence=self.sequence,processId=31,
            requestedEpochMs=self.epoch,capturedEpochMs=self.epoch,source=source)
        if self.edit:self.edit(self.sample)

    def original(self):self.reads+=1;return '' if self.sample is None else json.dumps(self.sample)
    def sleep(self,seconds):self.clock+=seconds
    def reader(self,*,models=False,**options):
        cls=NativeWorldModelDraws if models else NativeAvatarRender
        return cls(self.send,self.original,lambda:self.epoch,lambda:self.okay,31,monotonic=lambda:self.clock,sleep=self.sleep,**options)

    def join(self):
        self.epoch=19999;reader=self.reader();before=reader.read();self.epoch=20001;after=reader.read()
        draws=self.reader(models=True).read(self.capture)
        return [before,after,self.capture,draws,31,self.epoch]


class OriginalAvatarRenderTests(unittest.TestCase):
    def test_original_loaded_avatar_pose_view_and_source_are_not_requested_values(self):
        b=Boundary();value=b.reader().read()
        self.assertEqual(b.avatar,value['source']);self.assertEqual(b.sample,value)
        self.assertEqual({'schemaVersion','commandId','action'},set(b.commands[0]))
        self.assertNotIn('expected',json.dumps(b.commands));self.assertNotIn('passed',json.dumps(value))

    def test_unloaded_original_is_observable_but_cannot_prove_avatar_draws(self):
        b=Boundary();b.avatar.update(loaded=False,geometry=None)
        self.assertIsNone(b.reader().read()['source']['geometry'])
        values=b.join()
        with self.assertRaises(NativeUIError):avatar_draws(*values)

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

    def test_commands_are_closed_versioned_readonly_and_platform_scoped(self):
        for validator,action,extra in ((avatar_command,'feature-avatar-render-observe',{}),
                (draws_command,'feature-world-model-draws-observe',dict(captureRequestId='b'*32))):
            value=dict(schemaVersion=1,commandId='a'*32,action=action,**extra);self.assertEqual(value,validator(value))
            for change in (dict(schemaVersion=True),dict(expectedModel=MODEL),dict(commandId='ios-'+'a'*32),dict(action=action+'-set')):
                with self.subTest(action=action,change=change),self.assertRaises(NativeUIError):validator(value|change)
        with self.assertRaises(NativeUIError):draws_command(dict(schemaVersion=1,commandId='ios-'+'a'*32,
            action='feature-world-model-draws-observe',captureRequestId='b'*32),ios=True)

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


class OriginalModelDrawTests(unittest.TestCase):
    def test_model_table_matches_original_capture_image_and_frame_without_pixel_verdict(self):
        b=Boundary();value=b.reader(models=True).read(b.capture)
        self.assertEqual(b.trace,value['source']['modelTrace'])
        self.assertEqual(b.capture['source']['image']['sha256'],value['source']['imageSha256'])
        self.assertEqual({'schemaVersion','commandId','action','captureRequestId'},set(b.commands[0]))
        self.assertNotIn('passed',json.dumps(value));self.assertNotIn('expected',json.dumps(b.commands))

    def test_empty_actual_draw_table_is_a_fact_not_a_visible_avatar(self):
        b=Boundary();b.trace.update(models=[],drawCommands=0)
        self.assertEqual([],b.reader(models=True).read(b.capture)['source']['modelTrace']['models'])
        with self.assertRaises(NativeUIError):avatar_draws(*b.join())

    def test_foreign_capture_context_sequence_original_times_or_png_cannot_be_adopted(self):
        for change in (dict(captureRequestId='a'*32),dict(captureSequence=2),dict(acquisitionSequence=2),
                dict(captureCapturedEpochMs=19999),dict(imageSha256='a'*64),dict(pixelSha256='a'*64),dict(modelCaptureVersion=True)):
            b=Boundary();b.edit=lambda value:value['source'].update(change)
            with self.subTest(change=change),self.assertRaises(NativeUIError):b.reader(models=True).read(b.capture)
        b=Boundary();b.edit=lambda value:value.update(instance='b'*32)
        with self.assertRaises(NativeUIError):b.reader(models=True).read(b.capture)

    def test_foreign_frames_missing_trace_or_downgrade_cannot_qualify(self):
        for change in (dict(frameId='b'*32),dict(recordedEpochMs=19999),dict(begunEpochMs=19999),dict(completedEpochMs=20001),
                dict(view='mirror'),dict(renderer='deferred'),dict(modelTraceVersion=True),dict(drawCommands=4)):
            b=Boundary();b.trace.update(change)
            with self.subTest(change=change),self.assertRaises(NativeUIError):b.reader(models=True).read(b.capture)
        b=Boundary();b.capture['source']['renderTrace']['traceVersion']=1;b.capture['source']['renderTrace'].pop('recordedView')
        with self.assertRaises(NativeUIError):b.reader(models=True).read(b.capture)

    def test_counts_bounds_and_identity_are_closed_numeric_and_complete(self):
        for change in (dict(drawCommands=0),dict(skinnedDrawCommands=4),dict(originalGeometryDrawCommands=True),dict(indices=2),
                dict(minimum=[0,float('nan'),0]),dict(maximum=[-1,0,0]),dict(geometryInstance='bad'),dict(visible=True)):
            b=Boundary();b.trace['models'][0].update(change)
            with self.subTest(change=change),self.assertRaises(NativeUIError):b.reader(models=True).read(b.capture)

    def test_overflow_duplicates_and_unaccounted_draws_cannot_truncate_to_success(self):
        for fault in ('overflow','duplicate','missing','exceeds-forward'):
            b=Boundary()
            if fault=='overflow':b.trace['models']*=129
            elif fault=='duplicate':b.trace['models']*=2;b.trace['drawCommands']=6
            elif fault=='missing':b.trace['models']=[]
            else:b.trace['models'][0]['drawCommands']=9;b.trace['drawCommands']=9
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):b.reader(models=True).read(b.capture)

    def test_fresh_query_over_an_old_render_table_never_makes_it_fresh(self):
        b=Boundary();b.epoch+=1600
        with self.assertRaises(NativeUIError):b.reader(models=True).read(b.capture)

    def test_requery_preserves_original_gpu_times_and_cannot_bind_another_capture(self):
        b=Boundary();reader=b.reader(models=True);first=reader.read(b.capture);b.epoch+=100;second=reader.read(b.capture)
        self.assertEqual(first['source'],second['source']);self.assertGreater(second['sequence'],first['sequence'])
        other=deepcopy(b.capture);other['requestId']='b'*32;other['source']['image']['name']='world-render-image-'+other['requestId']+'.png'
        with self.assertRaises(NativeUIError):reader.read(other)

    def test_released_or_unavailable_capture_cannot_be_replaced_by_an_acknowledgement(self):
        b=Boundary();b.edit=lambda value:value.update(source={})
        with self.assertRaises(NativeUIError):b.reader(models=True).read(b.capture)
        b=Boundary();b.edit=lambda value:value.update(performed=True)
        with self.assertRaises(NativeUIError):b.reader(models=True).read(b.capture)


class AvatarDrawJoinTests(unittest.TestCase):
    def test_original_join_returns_measured_bounds_and_counts_not_visibility_or_pass(self):
        b=Boundary();row=avatar_draws(*b.join());self.assertEqual(model_row(),row)
        row['minimum'][0]=500;self.assertEqual(-.3,b.trace['models'][0]['minimum'][0])
        self.assertNotIn('visible',row);self.assertNotIn('passed',row)

    def test_drawn_foreign_model_geometry_or_loaded_asset_cannot_stand_in_for_avatar(self):
        for change in (dict(modelInstance='b'*32),dict(geometryInstance='b'*32),dict(loadedSourceSha256='b'*64),
                dict(loadedSourcePresent=False,loadedSourceSha256=EMPTY_SHA256),dict(skinnedDrawCommands=0),
                dict(originalGeometryDrawCommands=2)):
            b=Boundary();b.trace['models'][0].update(change)
            with self.subTest(change=change),self.assertRaises(NativeUIError):avatar_draws(*b.join())

    def test_mixed_geometries_for_same_model_do_not_hide_an_old_avatar_draw(self):
        b=Boundary();row=model_row();row['geometryInstance']='b'*32;b.trace['models'].append(row);b.trace['drawCommands']=6
        with self.assertRaises(NativeUIError):avatar_draws(*b.join())

    def test_hidden_unloaded_or_disabled_avatar_is_not_adopted_from_draw_counts(self):
        for key in ('visible','addedToScene','localRenderingEnabled','avatarShouldRender'):
            b=Boundary();b.avatar[key]=False
            with self.subTest(key=key),self.assertRaises(NativeUIError):avatar_draws(*b.join())

    def test_camera_pose_projection_and_subject_change_across_capture_reject(self):
        for fault in ('camera','projection','pose','scale','geometry','model','rig','birth','empty-bound'):
            b=Boundary();values=b.join();right=values[1]['source']
            if fault=='camera':right['view']['position'][0]+=.1
            elif fault=='projection':right['view']['projection'][0]+=.1
            elif fault=='pose':right['pose']['feetPosition'][0]+=.1
            elif fault=='scale':right['pose']['modelScale']=2
            elif fault=='geometry':right['geometry']['instance']='b'*32
            elif fault=='model':right['modelInstance']='b'*32
            elif fault=='rig':right['rigId']=5
            elif fault=='birth':values[1]['instance']='b'*32
            else:values[3]['source']['modelTrace']['models'][0]['maximum'][0]=-.3
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):avatar_draws(*values)

    def test_unbracketed_source_and_old_or_foreign_peer_cannot_qualify(self):
        for fault in ('before','after','cursor','pid','stale'):
            b=Boundary();values=b.join()
            if fault=='before':values[0]['capturedEpochMs']=20001;values[0]['requestedEpochMs']=20001
            elif fault=='after':values[1]['requestedEpochMs']=19999
            elif fault=='cursor':values[1]['sequence']=values[0]['sequence']
            elif fault=='pid':values[1]['processId']=32
            else:values[-1]=22000
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):avatar_draws(*values)

    def test_quaternion_sign_does_not_invent_a_camera_or_avatar_change(self):
        b=Boundary();values=b.join();right=values[1]['source']
        right['pose']['orientation']=[0,0,0,-1];right['view']['rotation']=[0,0,0,-1]
        self.assertEqual(model_row(),avatar_draws(*values))


class RenderProvenanceIntegrationTests(unittest.TestCase):
    def test_fixture_rejects_expected_subjects_and_foreign_capture_selectors(self):
        fixture=FixtureState()
        for value in (dict(schemaVersion=1,commandId='ios-'+'a'*32,action='feature-avatar-render-observe'),
                dict(schemaVersion=1,commandId='ios-'+'a'*32,action='feature-world-model-draws-observe',captureRequestId='ios-'+'b'*32)):
            self.assertEqual(value,fixture.set_client_command(value))
            with self.assertRaises(ValueError):fixture.set_client_command(value|dict(expectedModel=MODEL))
        with self.assertRaises(ValueError):fixture.set_client_command(value|dict(captureRequestId='b'*32))

    def test_actual_probe_forwards_originals_once_and_missing_hooks_stay_unavailable(self):
        program=r'''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,keys)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(keys.sort());
let files=[],calls=[];
const original={schemaVersion:1,requestId:"a".repeat(32),capturedEpochMs:17000,source:{nativeOriginal:true}};
const Test={featureAvatarRenderObservation:c=>{calls.push(c);return original;},
 featureWorldModelDrawsObservation:c=>{calls.push(c);return original;},saveObject:(v,name)=>files.push({v,name})};
SOURCE
for(const [action,name] of [["feature-avatar-render-observe","feature-avatar-render.json"],
 ["feature-world-model-draws-observe","feature-world-model-draws.json"]]){
 const request={schemaVersion:1,commandId:"a".repeat(32),action};
 if(action.includes("model-draws"))request.captureRequestId="b".repeat(32);
 const start=calls.length;applyAndroidControlCommand(request);applyAndroidControlCommand(request);
 if(calls.length!==start+1||files[files.length-1].v!==original||files[files.length-1].name!==name)throw Error("original missing/repeated/retimed");
 applyClientCommand({...request,commandId:"c".repeat(32),expectedModel:"wanted"});
 if(calls.length!==start+1)throw Error("expected value admitted");
}
delete Test.featureAvatarRenderObservation;delete Test.featureWorldModelDrawsObservation;
applyClientCommand({schemaVersion:1,commandId:"d".repeat(32),action:"feature-avatar-render-observe"});
applyClientCommand({schemaVersion:1,commandId:"e".repeat(32),captureRequestId:"b".repeat(32),action:"feature-world-model-draws-observe"});
if(files.length!==4||files[2].v.available!==false||files[3].v.available!==false||original.capturedEpochMs!==17000)throw Error("missing source green");
'''.replace('SOURCE',probe_source())
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)

    def test_native_wiring_uses_loaded_geometry_executing_backend_and_capture_retirement(self):
        # Wiring checks only. Native sources are deliberately not compiled here.
        payload=(ROOT/'libraries/render-utils/src/MeshPartPayload.cpp').read_text()
        trace=(ROOT/'libraries/gpu/src/gpu/FeatureRenderTrace.h').read_text()
        capture=(ROOT/'libraries/gpu/src/gpu/FeatureWorldRender.h').read_text()
        getter=(ROOT/'interface/src/scripting/TestScriptingInterface.cpp').read_text().split(
            'QVariantMap TestScriptingInterface::featureAvatarRenderObservation',1)[1].split(
            'QVariantMap TestScriptingInterface::featureGraphicsSubjectObservation',1)[0]
        self.assertIn('geometry->getHFMModel().originalURL',payload);self.assertIn('geometry->getHFMModel().originalURL',getter)
        self.assertNotIn('model->getURL()',getter);self.assertNotIn('setShouldRenderLocally',getter)
        self.assertLess(payload.index('drawCall(batch);'),payload.index('trace->model('))
        for text in ('_e2eOriginalDrawMesh.lock() == _drawMesh','_clusterPaletteValid && _drawPart._numIndices > 0',
                'args->_mirrorDepth == 0 && !args->isStereo()'):
            self.assertIn(text,payload)
        self.assertIn('_models.size() >= 128',trace);self.assertIn('_modelsAvailable = false; _models.clear();',trace)
        self.assertIn('backend != Backend::featureExecutingBackend()',trace)
        self.assertIn('_retired.contains(capture)',capture);self.assertGreaterEqual(capture.count('_modelResult.clear()'),3)
        self.assertIn('trace->modelSnapshot(backend)',capture)


if __name__=='__main__':unittest.main()
