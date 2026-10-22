"""Original fixture geometry/lifetime logic, never a native/client execution."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import math
from pathlib import Path
import subprocess
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

from adapters.native_phone_emote_fixture import NativePhoneEmoteFixture,command,input_command,input_receipt,ready,retired,layout,NULL_ID
from adapters.normal_ui import NativeUIError
from self_tests.test_native_avatar_render import Boundary as AvatarBoundary,avatar_source
from self_tests.test_native_feature_observation import probe_source

RUN='d'*32
ROOT='http://controlled.invalid/feature-fixture/v1/runs/'+RUN+'/'


def prepare():return dict(schemaVersion=1,commandId='b'*32,action='phone-emote-fixture-input',operation='prepare',runId=RUN,
    fixtureUrl=ROOT,ticket='c'*32,imageExtent=[1000,750],markerRoi=[20,20,180,60])


class Boundary(AvatarBoundary):
    def __init__(self):
        super().__init__();self.avatar=avatar_source();self.avatar['cameraMode']='selfie'
        view=deepcopy(self.avatar['view'])|dict(feetPosition=deepcopy(self.avatar['pose']['feetPosition']),modelScale=1.,boomLength=4.,mode='selfie')
        self.fixture=dict(phoneEmoteFixtureVersion=1,fixtureInstance='e'*32,runId=RUN,phase='active',createdEpochMs=19999,
            originalInput=prepare(),originalView=view,objects=[dict(role='backdrop',id='11111111-1111-4111-8111-111111111111'),
                dict(role='marker',id='22222222-2222-4222-8222-222222222222')],entities=[],absentIds=[],retainedObjects=2)
        f=1/math.tan(math.radians(30));depth=6.
        # Independent simple-FOV reference, rather than echoing layout().
        for item in self.fixture['objects']:
            marker=item['role']=='marker'
            position=[-.8*.25*(4/3)/f,1.6+(1-2*40/750)*.25/f,-.25] if marker else [0,1.6,-depth]
            dimensions=[160/1000*2*.25*(4/3)/f,40/750*2*.25/f,.01] if marker else [2*depth*1.1*(4/3)/f,2*depth*1.1/f,.01]
            self.fixture['entities'].append(dict(id=item['id'],role=item['role'],originalObject=True,name='e2e-'+RUN+'-emote-'+item['role'],
                type='Web' if marker else 'Box',parentId=NULL_ID,hostType='local',position=position,rotation=[0,0,0,1],dimensions=dimensions,
                color=[255,255,255] if marker else [128,128,128],visible=True,sourceUrl=ROOT+'tickets/'+'c'*32+'/graphics-marker.v1.html' if marker else '',
                locked=False,collisionless=True,canCastShadow=False,dpi=100 if marker else 0,lastEditedEpochUs=19999000))

    def send(self,request):
        if request['action']!='phone-emote-fixture-observe':return super().send(request)
        self.commands.append(deepcopy(request))
        if self.ignored:return
        self.sequence+=1;self.epoch+=1
        self.sample=dict(schemaVersion=1,requestId=request['commandId'],instance='f'*32,sequence=self.sequence,processId=31,
            requestedEpochMs=self.epoch,capturedEpochMs=self.epoch,source=deepcopy(self.fixture))
        if self.edit:self.edit(self.sample)

    def reader(self,**options):
        return NativePhoneEmoteFixture(self.send,self.original,lambda:self.epoch,lambda:self.okay,31,
            monotonic=lambda:self.clock,sleep=self.sleep,**options)

    def pair(self):return self.reader().read(RUN),super().reader().read()

    def drain(self):
        self.fixture.update(phase='drained',entities=[],absentIds=[row['id'] for row in self.fixture['objects']],retainedObjects=0)


class PhoneEmoteFixtureTests(unittest.TestCase):
    def test_original_dynamic_objects_and_view_are_not_fixture_input_or_readiness_verdict(self):
        b=Boundary();value=b.reader().read(RUN);self.assertEqual(b.sample,value);self.assertEqual(b.fixture,value['source'])
        self.assertEqual({'schemaVersion','commandId','action','runId'},set(b.commands[0]))
        self.assertNotIn('expected',str(b.commands));self.assertNotIn('passed',value)

    def test_separate_original_geometry_join_matches_independent_reference_projection(self):
        b=Boundary();value,avatar=b.pair();rows=ready(value,avatar)
        self.assertEqual(b.fixture['entities'],rows)
        plan=layout(b.fixture)
        for row in rows:
            for key in ('position','dimensions'):
                for actual,wanted in zip(row[key],plan[row['role']][key]):self.assertAlmostEqual(actual,wanted,places=7)

    def test_fixture_receipt_cannot_supply_created_entities_or_cleanup(self):
        request=prepare();receipt=dict(phoneEmoteFixtureInputVersion=1,commandId=request['commandId'],runId=RUN,
            fixtureInstance='e'*32,operation='prepare',recorded=True)
        self.assertEqual(receipt,input_receipt(receipt,request))
        for edit in (dict(recorded=False),dict(recorded=1),dict(commandId='0'*32),dict(expectedReady=True),dict(phoneEmoteFixtureInputVersion=True)):
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):input_receipt(receipt|edit,request)
        with self.assertRaises(NativeUIError):ready(receipt,{})

    def test_commands_are_closed_and_platform_origin_run_and_image_bounds_are_checked(self):
        valid=prepare();self.assertEqual(valid,input_command(valid))
        for edit in (dict(expectedEntities=[]),dict(schemaVersion=True),dict(commandId='ios-'+'a'*32),dict(ticket='bad'),dict(operation='delete-all'),
                dict(imageExtent=[True,750]),dict(imageExtent=[200,750]),dict(markerRoi=[20,20,179,60]),dict(markerRoi=[0,0,1000,750]),
                dict(fixtureUrl=ROOT.replace(RUN,'0'*32)),dict(fixtureUrl=ROOT+'?private=yes'),dict(fixtureUrl=ROOT.replace('controlled.invalid','user:secret@controlled.invalid'))):
            with self.subTest(edit=edit),self.assertRaises((NativeUIError,ValueError)):input_command(valid|edit)
        observe=dict(schemaVersion=1,commandId='a'*32,action='phone-emote-fixture-observe',runId=RUN)
        self.assertEqual(observe,command(observe))
        with self.assertRaises(NativeUIError):command(observe|dict(expectedAbsent=True))

    def test_valid_inventory_cannot_hide_missing_or_foreign_objects_from_readiness(self):
        for kind in ('missing','replacement','host','parent','name','geometry','color','source','hidden','locked','collision','shadow','dpi'):
            b=Boundary();row=b.fixture['entities'][-1]
            if kind=='missing':b.fixture['entities'].pop();b.fixture['absentIds'].append(row['id'])
            elif kind=='replacement':row['originalObject']=False
            elif kind=='host':row['hostType']='foreign'
            elif kind=='parent':row['parentId']='11111111-1111-4111-8111-111111111111'
            elif kind=='name':row['name']='foreign'
            elif kind=='geometry':row['position'][0]+=.1
            elif kind=='color':b.fixture['entities'][0]['color']=[0,0,0]
            elif kind=='source':row['sourceUrl']=row['sourceUrl'].replace('c'*32,'0'*32)
            elif kind=='hidden':row['visible']=False
            elif kind=='locked':row['locked']=True
            elif kind=='collision':row['collisionless']=False
            elif kind=='shadow':row['canCastShadow']=True
            else:row['dpi']=99
            pair=b.pair()
            with self.subTest(kind=kind),self.assertRaises(NativeUIError):ready(*pair)

    def test_camera_feet_scale_projection_and_process_must_match_independent_avatar_original(self):
        for kind in ('birth','pid','camera','feet','scale','projection','rotation'):
            b=Boundary();value,avatar=b.pair()
            if kind=='birth':avatar['instance']='0'*32
            elif kind=='pid':avatar['processId']=32
            elif kind=='camera':avatar['source']['cameraMode']='look at'
            elif kind=='feet':avatar['source']['pose']['feetPosition'][0]+=1
            elif kind=='scale':avatar['source']['pose']['modelScale']=2
            elif kind=='projection':avatar['source']['view']['projection'][0]*=1.01
            else:avatar['source']['view']['rotation']=[0,1,0,0]
            with self.subTest(kind=kind),self.assertRaises(NativeUIError):ready(value,avatar)

    def test_unknown_duplicate_extra_or_nonfinite_rows_are_not_a_complete_inventory(self):
        for kind in ('unknown','duplicate','extra','nan','missing','mixed','retained'):
            b=Boundary();rows=b.fixture['entities']
            if kind=='unknown':rows[0]['id']='33333333-3333-4333-8333-333333333333'
            elif kind=='duplicate':rows.append(deepcopy(rows[0]))
            elif kind=='extra':rows[0]['expectedVisible']=True
            elif kind=='nan':rows[0]['position'][0]=float('nan')
            elif kind=='missing':rows.pop()
            elif kind=='mixed':b.fixture['absentIds'].append(rows[0]['id'])
            else:b.fixture['retainedObjects']=3
            with self.subTest(kind=kind),self.assertRaises(NativeUIError):b.reader().read(RUN)

    def test_entity_absence_or_release_ack_cannot_hide_retained_original_objects(self):
        b=Boundary();b.drain();value=b.reader().read(RUN);self.assertEqual(value['source'],retired(value))
        for phase,retained in (('releasing',0),('active',0),('releasing',1)):
            b=Boundary();b.drain();b.fixture.update(phase=phase,retainedObjects=retained);value=b.reader().read(RUN)
            with self.subTest(phase=phase,retained=retained),self.assertRaises(NativeUIError):retired(value)
        b=Boundary();b.drain();b.fixture['retainedObjects']=1
        with self.assertRaises(NativeUIError):b.reader().read(RUN)

    def test_partial_failed_creation_is_observable_and_never_full_readiness(self):
        b=Boundary();b.fixture.update(phase='failed',objects=[dict(role='backdrop',id=None)],entities=[],absentIds=[],retainedObjects=0)
        pair=b.pair()
        with self.assertRaises(NativeUIError):ready(*pair)
        b.fixture['phase']='drained';self.assertEqual([],retired(b.reader().read(RUN))['entities'])

    def test_reconstruction_cannot_replace_scope_view_plan_ids_or_revive_drained_resources(self):
        for kind in ('instance','view','input','ids','revive'):
            b=Boundary();reader=b.reader()
            if kind=='revive':b.drain()
            original=reader.read(RUN)
            if kind=='instance':b.fixture['fixtureInstance']='0'*32
            elif kind=='view':b.fixture['originalView']['boomLength']=5
            elif kind=='input':b.fixture['originalInput']['ticket']='0'*32
            elif kind=='ids':b.fixture['objects'][0]['id']='33333333-3333-4333-8333-333333333333'
            else:b.fixture['phase']='active'
            with self.subTest(kind=kind),self.assertRaises(NativeUIError):reader.read(RUN)
            self.assertEqual(original,reader.last)

    def test_missing_ignored_foreign_stale_or_reused_source_is_not_adopted(self):
        for kind in ('ignore','missing','foreign','stale','cursor','birth'):
            b=Boundary();reader=b.reader();first=reader.read(RUN)
            if kind=='ignore':b.ignored=True
            elif kind=='missing':b.edit=lambda v:v.pop('source')
            elif kind=='foreign':b.edit=lambda v:v['source'].update(runId='0'*32)
            elif kind=='stale':b.edit=lambda v:v.update(requestedEpochMs=1,capturedEpochMs=1)
            elif kind=='cursor':b.edit=lambda v:v.update(sequence=1)
            else:b.edit=lambda v:v.update(instance='0'*32)
            with self.subTest(kind=kind),self.assertRaises(NativeUIError):reader.read(RUN)
            self.assertEqual(first,reader.last)

    def test_historical_restore_has_no_native_transport_or_retiming_and_cannot_resurrect(self):
        b=Boundary();reader=b.reader();first=reader.read(RUN);b.drain();last=reader.read(RUN);again=b.reader();count=len(b.commands)
        again.restore([first,last]);self.assertEqual(count,len(b.commands));self.assertEqual(last,again.last)
        revived=deepcopy(last);revived['sequence']+=1;revived['source']=deepcopy(first['source'])
        with self.assertRaises(NativeUIError):b.reader().restore([first,last,revived])

    def test_original_view_inverse_projection_does_not_accept_singular_or_other_aspect(self):
        b=Boundary();b.fixture['originalView']['projection']=[0.]*16
        with self.assertRaises(NativeUIError):layout(b.fixture)
        b=Boundary();b.fixture['originalInput']['imageExtent']=[1000,1000]
        with self.assertRaises(NativeUIError):b.reader().read(RUN)

    def test_final_original_guards_include_slow_copy_and_stopped_device_clock(self):
        b=Boundary();reader=b.reader();count=[0]
        def guard():
            count[0]+=1
            if count[0]==4:b.clock+=1.6
            return True
        reader.guard=guard
        with self.assertRaises(NativeUIError):reader.read(RUN)
        self.assertIsNone(reader.last)

    def test_actual_probe_forwards_input_and_observation_originals_without_expected_scene_facts(self):
        program=r'''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,k)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.sort());
let files=[],calls=[];
const input={phoneEmoteFixtureInputVersion:1,commandId:"b".repeat(32),recorded:true};
const original={requestId:"a".repeat(32),capturedEpochMs:17000,source:{originalEntity:true}};
const Test={phoneEmoteFixtureInput:c=>{calls.push(c);return input;},phoneEmoteFixtureObservation:c=>{calls.push(c);return original;},saveObject:(v,n)=>files.push({v,n})};
SOURCE
const p=PREPARE;
applyAndroidControlCommand(p);applyAndroidControlCommand(p);
if(calls.length!==1||files[0].v!==input||files[0].n!=="phone-emote-fixture-input.json")throw Error("input receipt replaced/replayed");
for(const extra of [{expectedReady:true},{operation:"delete-all"},{imageExtent:[true,750]}])applyAndroidControlCommand({...p,commandId:"f".repeat(32),...extra});
if(calls.length!==1)throw Error("arbitrary fixture input admitted");
const c={schemaVersion:1,commandId:"a".repeat(32),action:"phone-emote-fixture-observe",runId:p.runId};
applyAndroidControlCommand(c);applyAndroidControlCommand(c);
if(calls.length!==2||files[1].v!==original)throw Error("observation replaced/repeated");
applyAndroidControlCommand({...c,commandId:"c".repeat(32),expectedAbsent:true});
if(calls.length!==2)throw Error("expected scene admitted");
delete Test.phoneEmoteFixtureObservation;applyAndroidControlCommand({...c,commandId:"d".repeat(32)});
if(files[2].v.available!==false||original.capturedEpochMs!==17000)throw Error("missing native inventory green/retimed");
'''
        import json
        program=program.replace('SOURCE',probe_source()).replace('PREPARE',json.dumps(prepare()))
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)


if __name__=='__main__':unittest.main()
