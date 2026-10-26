"""Actual world-source codec and canonical transport; native physics modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import json
import math
import subprocess
import unittest
import uuid
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from fixture.serve import FixtureState
from ios.adapters import lifecycle_world as world,scene_inventory,feature_observation
from ios.self_tests.test_ios_scene_commit_origin import Boundary as Scene
from ios.self_tests.test_ios_keyboard_runtime import KeyboardRuntimeTests
from self_tests.test_native_feature_observation import probe_source

RUN='a'*32


class NativeScene(Scene):
    # A new producer clock selected before its actual modeled import event.
    # Existing recorded origin/body/position packets are never retimed.
    def epoch(self):return 10000+round(self.clock*1000)


class Boundary:
    def __init__(self,scene_factory=NativeScene):
        self.scene=scene_factory();self.query=None;self.sequence=0;self.queries=[];self.live=True;self.mutate=None
        self.position=[0.,0.,0.];self.raw=[0.]*world.DRIVE_KEYS;self.disabled=[False]*world.DRIVE_KEYS
        self.avatar=uuid.uuid4().hex;self.domain='11111111-1111-4111-8111-111111111111'
    def send(self,query):self.query=deepcopy(query);self.queries.append(deepcopy(query))
    def original(self):
        self.sequence+=1;self.scene.clock+=.001;before=self.scene.clocks()
        self.scene.send(dict(self.query,action=scene_inventory.ACTION));scene=json.loads(self.scene.original());self.scene.clock+=.001
        source=dict(scene=scene,lifecycle=dict(backgrounds=0,activations=1,launches=1),
            domain=dict(connected=True,serverless=False,domainId=self.domain,selfSha256='b'*64,avatarMixerSha256='c'*64,addressSha256='d'*64),
            avatar=dict(objectId=self.avatar,feetPosition=deepcopy(self.position),velocity=[0.,0.,0.],orientation=[0.,0.,0.,1.],inAir=False,flying=False,modelScale=1.),
            drive=dict(raw=deepcopy(self.raw),effective=[0. if self.disabled[i] else self.raw[i] for i in range(world.DRIVE_KEYS)],disabled=deepcopy(self.disabled)))
        value=dict(iosLifecycleWorldVersion=1,requestId=self.query['commandId'],runId=self.query['runId'],instance='e'*32,
            sequence=self.sequence,processId=42,clockDomain='native-main-lifecycle-world',clockBefore=before,clockAfter=self.scene.clocks(),source=source)
        if self.mutate:self.mutate(value)
        self.packet=value;return json.dumps(value)
    def reader(self):return world.IOSLifecycleWorld(self.send,self.original,self.scene.native_clock,lambda:self.live,42,
        monotonic=lambda:self.scene.clock,sleep=self.scene.sleep)


class LifecycleWorldTests(unittest.TestCase):
    def test_measured_forward_and_3d_displacement_keep_original_foot_coordinates(self):
        b=Boundary();reader=b.reader();first=reader.read(RUN);saved=deepcopy(first)
        b.position=[.2,.01,-.9];b.raw[world.FORWARD]=.75;current=reader.read(RUN);facts=world.measure(first,current)
        self.assertEqual(['forward'],facts['heldInputs']);self.assertEqual(dict(x=.2,y=.01,z=-.9),facts['positionDelta'])
        self.assertAlmostEqual(math.sqrt(.2**2+.01**2+.9**2),facts['worldDisplacement']);self.assertEqual(saved,first)
        self.assertEqual(2,len(b.queries));self.assertTrue(all(set(q)=={'schemaVersion','commandId','action','runId'} for q in b.queries))
        self.assertNotIn('worldAttempts',facts);self.assertNotIn('gestureId',facts)

    def test_disabled_raw_input_does_not_become_effective_avatar_hold_or_movement(self):
        b=Boundary();reader=b.reader();first=reader.read(RUN);b.raw[world.FORWARD]=1.;b.disabled[world.FORWARD]=True
        current=reader.read(RUN);facts=world.measure(first,current)
        self.assertEqual([],facts['heldInputs']);self.assertEqual(0.,facts['worldDisplacement'])
        self.assertEqual(1.,current['source']['drive']['raw'][world.FORWARD])
        self.assertEqual(0.,current['source']['drive']['effective'][world.FORWARD])

    def test_changed_actual_avatar_domain_scene_or_scale_cannot_borrow_old_position_anchor(self):
        for change in ('avatar','domain','scene','scale'):
            b=Boundary();reader=b.reader();first=reader.read(RUN)
            if change=='avatar':b.avatar=uuid.uuid4().hex
            elif change=='domain':b.domain='22222222-2222-4222-8222-222222222222'
            elif change=='scene':b.scene.commit()
            else:b.mutate=lambda v:v['source']['avatar'].update(modelScale=2.)
            current=reader.read(RUN)
            with self.subTest(change=change),self.assertRaises(NativeUIError):world.measure(first,current)

    def test_missing_peer_context_airborne_or_foreign_drive_does_not_qualify_this_journey(self):
        for mutate in (lambda v:v['source']['domain'].update(serverless=True),
            lambda v:v['source']['domain'].update(avatarMixerSha256=None),lambda v:v['source']['domain'].update(connected=False),
            lambda v:v['source']['avatar'].update(inAir=True),lambda v:v['source']['avatar'].update(flying=True)):
            b=Boundary();reader=b.reader();first=reader.read(RUN);b.mutate=mutate;current=reader.read(RUN)
            with self.subTest(mutate=mutate),self.assertRaises(NativeUIError):world.measure(first,current)
        for index,value in ((0,.5),(world.FORWARD,-1.)):
            b=Boundary();reader=b.reader();first=reader.read(RUN);b.raw[index]=value;current=reader.read(RUN)
            with self.subTest(index=index),self.assertRaises(NativeUIError):world.measure(first,current)

    def window(self,positions=None,spacing=1.05):
        b=Boundary();reader=b.reader();values=[]
        for index in range(4):
            if index:b.scene.clock+=spacing
            if positions is not None:b.position=list(positions[index])
            values.append(reader.read(RUN))
        return b,values

    def test_stationary_window_requires_native_time_and_stability_about_original_3d_anchor(self):
        b,values=self.window([(1,0,0),(1.01,0,0),(1,.01,0),(1,0,.01)])
        proof=world.stationary(values);self.assertGreaterEqual(proof['nativeMilliseconds'],3000)
        self.assertEqual([1,0,0],proof['position']);self.assertEqual(4,len(b.queries))
        with self.assertRaises(NativeUIError):world.stationary(values[:3])

    def test_constant_distance_arc_and_observation_gaps_do_not_pass_stationary_release(self):
        points=[(math.cos(t),0,math.sin(t)) for t in (0,.05,.1,.15)]
        _b,values=self.window(points)
        self.assertTrue(all(abs(math.sqrt(sum(n*n for n in row['source']['avatar']['feetPosition']))-1)<1e-9 for row in values))
        with self.assertRaises(NativeUIError):world.stationary(values)
        _b,values=self.window(spacing=2.)
        with self.assertRaises(NativeUIError):world.stationary(values)

    def test_native_schema_effective_raw_clock_and_pid_faults_keep_last_original_unchanged(self):
        b=Boundary();reader=b.reader();first=reader.read(RUN)
        for mutate in (lambda v:v.update(iosLifecycleWorldVersion=True),lambda v:v.update(processId=43),
            lambda v:v.update(sequence=1000000001),lambda v:v['source']['lifecycle'].update(activations=1000001),
            lambda v:v['source']['drive']['effective'].__setitem__(2,1.),lambda v:v['source']['drive']['disabled'].__setitem__(0,1),
            lambda v:v['source']['avatar']['feetPosition'].__setitem__(0,float('nan')),
            lambda v:v['clockAfter'].update(monotonicMs=0)):
            b.mutate=mutate
            with self.subTest(mutate=mutate),self.assertRaises(NativeUIError):reader.read(RUN)
            self.assertEqual(first,reader.last)

    def test_actual_probe_and_fixture_read_only_closed_source_once_per_nonce(self):
        b=Boundary();packet=b.reader().read(RUN);query=dict(schemaVersion=1,action=world.ACTION,commandId=packet['requestId'],runId=RUN)
        fixture=FixtureState();self.assertEqual(query,fixture.set_client_command(query))
        with self.assertRaises(ValueError):fixture.set_client_command(dict(query,expectedForward=True))
        program='''const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,k)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.sort());
const original=PACKET;let calls=0,files=[];const Test={featureIOSLifecycleWorld:q=>{calls++;return {...original,requestId:q.commandId};},saveObject:(v,f)=>files.push({v,f})};
SOURCE
const q=QUERY;applyClientCommand(q);applyClientCommand(q);applyClientCommand({...q,commandId:'ios-'+'c'.repeat(32)});
if(calls!==2||files.length!==2||files[0].f!=='feature-ios-lifecycle-world.json'||JSON.stringify(files[0].v.source)!==JSON.stringify(original.source))throw Error('source replay/rewriting');
applyClientCommand({...q,commandId:'ios-'+'d'.repeat(32),expectedForward:true});if(calls!==2)throw Error('requested effect accepted');
delete Test.featureIOSLifecycleWorld;applyClientCommand({...q,commandId:'ios-'+'e'.repeat(32)});
if(files.at(-1).v.status!=='unavailable'||files.at(-1).v.source)throw Error('missing source became absence');
'''.replace('PACKET',json.dumps(packet)).replace('QUERY',json.dumps(query)).replace('SOURCE',probe_source())
        result=subprocess.run(['node','-'],input=program,capture_output=True,text=True,timeout=5);self.assertEqual(0,result.returncode,result.stderr)


class LifecycleWorldRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.k=KeyboardRuntimeTests();self.k.setUp();self.addCleanup(self.k.doCleanups);self.f=self.k.f
        self.boundary=Boundary();self.afc=[];self.raw=None
        def native_clock(packet):
            self.k.b.time=self.boundary.scene.epoch()-20000;self.k.native_clock(packet)
        self.f.clock.mutate=native_clock
        def post(request,timeout):
            query=json.loads(request.data)
            if query['action']!=world.ACTION:return self.k.post(request,timeout)
            self.boundary.send(query);self.raw=self.boundary.original();raw=json.dumps(query).encode()
            class Response:
                status=200
                def __enter__(self):return self
                def __exit__(self,*args):return False
                def read(self,limit):return raw[:limit]
            return Response()
        self.enterContext(patch.object(feature_observation,'post_request',side_effect=post))
        previous_execute=self.k.client.execute
        def execute(session,operation,values):
            if operation=='mobile: pullFile' and values['remotePath'].endswith('/'+world.FILE):
                self.afc.append(values['remotePath']);return base64.b64encode(self.raw.encode()).decode()
            return previous_execute(session,operation,values)
        self.k.client.execute=execute

    def test_existing_canonical_factory_reads_original_pose_and_clock_without_new_launch(self):
        before=(self.f.sessions,self.f.launches);reader=self.f.adapter._lifecycle_world('test-only');packet=reader.read(RUN)
        self.assertEqual([0.,0.,0.],packet['source']['avatar']['feetPosition']);self.assertEqual(1,len(self.boundary.queries))
        self.assertEqual(1,len(self.afc));self.assertEqual(before,(self.f.sessions,self.f.launches))
        self.assertIn('iosLifecycleWorldAcquisitionVersion',reader.acquisition)

    def test_changed_candidate_cannot_obtain_another_world_original(self):
        reader=self.f.adapter._lifecycle_world('test-only');self.f.artifact.write_bytes(b'Changed candidate after source construction')
        with self.assertRaises(NativeUIError):reader.read(RUN)
        self.assertEqual([],self.boundary.queries)

    def test_replaced_process_cannot_borrow_existing_world_reader(self):
        reader=self.f.adapter._lifecycle_world('test-only');self.f.process['pid']=43
        with self.assertRaises(NativeUIError):reader.read(RUN)
        self.assertEqual([],self.boundary.queries);self.assertEqual([],self.afc)

    def test_background_process_refuses_world_source_before_http_or_afc(self):
        reader=self.f.adapter._lifecycle_world('test-only');self.f.process['foreground']=False
        with self.assertRaises(NativeUIError):reader.read(RUN)
        self.assertEqual([],self.boundary.queries);self.assertEqual([],self.afc)
