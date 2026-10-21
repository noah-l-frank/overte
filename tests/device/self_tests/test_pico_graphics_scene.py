"""Actual Pico input composition with analytical HMD/scene/native boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import math
from pathlib import Path
import unittest
import uuid
from urllib.parse import parse_qs,urlsplit
from adapters.graphics_journey.scene import GraphicsScene,viewpoint
from adapters.native_graphics_subject import NativeGraphicsSubject
from adapters.native_scene_loads import resource_hash
from adapters.normal_ui import NativeUIError
from adapters.pico4.graphics_scene import PicoGraphicsScenePolicy
from adapters.pico4.graphics_surface import PicoGraphicsSurface
from adapters.pico4.navigation import PicoNavigation
from adapters.pico4.normal_scripts import PicoScriptIO
from adapters.pico4.tablet_home import PicoTabletHome
from adapters.script_journey.history import pack,unpack
from adapters.script_journey.lock import ScriptSourceLock
from adapters.token_script_ui import TokenScriptUI
from feature_journeys.graphics_fixture import scene as scene_document,subject_ids
from feature_journeys.graphics_resources import GraphicsResources,RESOURCE
from feature_journeys.witness import Client
from self_tests import test_pico_graphics_surface as surface_fixture
from self_tests.test_pico_graphics_surface import HomeSource,IDENTITY,RUN
from self_tests.test_native_scene_loads import Boundary as LoadBoundary,row as load_row
from self_tests.test_owned_world_render import BINDING
from self_tests.test_vr_graphics_subject import USER,TABLET

ORIGINAL='http://controlled.invalid/original-scene.json'
BASE='http://controlled.invalid/feature-fixture/v1'
TICKET='c'*32


class Model:
    graphics_scene_policy=PicoGraphicsScenePolicy()
    def __init__(self):
        self.fixture=surface_fixture.PicoGraphicsSurfaceTests();self.native,self.initial=self.fixture.surface()
        self.root=self.initial.ui.io.navigation.path.parent
        self.subject=self.initial.subject.original.__self__
        self.subject.source['sceneUrl']=ORIGINAL
        self.original=deepcopy(self.subject.source);self.fault=None;self.destinations=[]
        self.client=object.__new__(Client);self.client.url=BASE;self.client.run=RUN;self.client.area='graphics'
        self.provider=GraphicsResources(BASE,clock_ms=lambda:self.native.epoch);self.provider.provision(RUN);self.provider.activate(RUN,TICKET)
        self.client.graphics_instance=self.provider.instance;self.client.graphics_previous=None;self.client.graphics_status=self.status
        self.lock=ScriptSourceLock(self.root/'script-sources.lock')
        self.loads=LoadBoundary();self.loads.rows[0]['resourceSha256']=resource_hash(ORIGINAL)
        original=self.native.send
        def send(command):
            value=original(command)
            if command['controlId']=='navigation.address' and command['action']=='submit':
                self.load(self.native.text)
                if self.fault=='lost-go':raise NativeUIError('Synthetic lost ordinary Enter receipt')
            return value
        self.native.send=send
    def close(self):self.fixture.doCleanups()
    def status(self):
        value=self.provider.snapshot(RUN,uuid.uuid4().hex);self.client.graphics_previous=deepcopy(value);return value
    def state_path(self,_target):return self.root/'state.json'
    def normal_feature_runtime(self,_target,*,read_only):
        assert read_only;return self.initial.ui,None,deepcopy(BINDING),self.native.guard,None
    def _graphics_subject_observer(self,_target,*,read_only):
        assert read_only
        def send(command):self.subject.epoch=self.native.epoch;self.subject.send(command)
        return NativeGraphicsSubject(send,self.subject.original,lambda:self.native.epoch,self.native.guard,31,
            monotonic=lambda:self.native.clock,sleep=self.native.sleep,require_framework=True)
    def _scene_load_observer(self,_target,*,read_only):
        assert read_only;reader=self.loads.reader();send=reader.send
        def current(command):self.loads.epoch=self.native.epoch;send(command)
        reader.send=current;reader.clock_ms=lambda:self.native.epoch;reader.guard=self.native.guard
        return reader
    def _graphics_surface(self,_target,run,intent,owns,lease,allow_url,*,lock):
        lock.assert_held()
        navigation=PicoNavigation(self.native,self.root/'navigation.json',IDENTITY,'31:original-start','http://controlled.invalid/scene.json',
            monotonic=lambda:self.native.clock,sleep=self.native.sleep)
        ui=TokenScriptUI(PicoScriptIO(navigation),monotonic=lambda:self.native.clock,sleep=self.native.sleep)
        def persist(stage,subject,source,control):
            self.native.intent(stage,subject,source,control);intent(stage,subject,source,control)
        home=HomeSource(self.native)
        return PicoGraphicsSurface(ui,self._graphics_subject_observer(_target,read_only=True),PicoTabletHome(home,home.stage),
            run,persist,owns,lease,allow_url)
    def factory(self):return GraphicsScene(self,'owned',self.client,RUN,self.lock,monotonic=lambda:self.native.clock,sleep=self.native.sleep)
    def controlled(self):
        value=deepcopy(self.original);value.update(entities=[],absentIds=[])
        value['scan']['unowned']=[row for row in value['scan']['unowned'] if row['id']!=USER]
        documents=scene_document(RUN,TICKET,BASE+'/runs/'+RUN+'/')['Entities']
        for document in documents:
            # Use the native schema independently of the observation reducer.
            row=dict(id=document['id'].strip('{}'),name=document['name'],type=document['type'],hostType='local',
                position=[document['position'][a] for a in 'xyz'],dimensions=[document['dimensions'][a] for a in 'xyz'],
                rotation=[document['rotation'][a] for a in 'xyzw'],color=[128,128,128],visible=True,mirrorMode=document.get('mirrorMode','none'),
                sourceUrl=document.get('sourceUrl',''),hazeMode=0,
                haze=dict(range=1000,color=[128,154,179],altitudeEffect=False,glare=False,backgroundBlend=0),lastEditedEpochUs=20000000)
            if 'color' in document:row['color']=[document['color'][a] for a in ('red','green','blue')]
            if row['type']=='Zone':
                haze=document['haze'];row.update(hazeMode=2,haze=dict(range=haze['hazeRange'],
                    color=[haze['hazeColor'][a] for a in ('red','green','blue')],altitudeEffect=haze['hazeAltitudeEffect'],
                    glare=haze['hazeEnableGlare'],backgroundBlend=haze['hazeBackgroundBlend']))
            value['entities'].append(row)
        value['scan']['scannedEntities']=len(value['scan']['unowned'])+7
        return value
    def load(self,url):
        self.destinations.append(url)
        if self.fault=='ignored-world':return
        controlled=resource_hash(url)!=resource_hash(ORIGINAL);value=self.controlled() if controlled else deepcopy(self.original)
        location=parse_qs(urlsplit(url).query)['location'][0].split('/')
        feet=[float(x) for x in location[1].split(',')];rotation=[float(x) for x in location[2].split(',')]
        # Independent normal-navigation model: original physical sensor local
        # translation (.1,1.6,-.2), world scale 1.25, normal avatar yaw.
        angle=2*math.atan2(rotation[1],rotation[3]);c,s=math.cos(angle),math.sin(angle)
        sensor=[1.25*c,0,-1.25*s,0,0,1.25,0,0,1.25*s,0,1.25*c,0,*feet,1]
        position=[feet[0]+1.25*(c*.1+s*(-.2)),feet[1]+2,feet[2]+1.25*(-s*.1+c*(-.2))]
        value['avatarPose'].update(feetPosition=feet,orientation=rotation)
        value['hmd'].update(sensorToWorld=sensor,worldPosition=position,worldRotation=rotation)
        value['view'].update(position=position,rotation=rotation,mode='first person');value['sceneUrl']=url
        if self.fault=='wrong-position':value['hmd']['worldPosition'][0]+=1;value['view']['position'][0]+=1
        if not controlled and self.fault=='foreign-change':value['scan']['unowned'][-1]['sha256']='e'*64
        if not controlled and self.fault=='framework-change':value['framework']['entities'][0]['appearanceSha256']='e'*64
        if not controlled and self.fault=='entity-leak':
            row=self.controlled()['entities'][0];value['entities'].append(row);value['absentIds'].remove(row['id']);value['scan']['scannedEntities']+=1
        self.subject.source=value;self.loads.generation+=1
        self.loads.rows.append(load_row(uuid.uuid4().hex,generation=self.loads.generation,resourceSha256=resource_hash(url),
            startedEpochMs=self.native.epoch,updatedEpochMs=self.native.epoch,releasedEpochMs=self.native.epoch))
        if self.fault=='pending':self.loads.rows[-1].update(pending=True,releasedEpochMs=None)
        if controlled:
            with self.provider.response(RUN,TICKET,request_authority='controlled.invalid',request_scheme='http',
                    resource=getattr(self.graphics_scene_policy,'fixture_resource',RESOURCE)) as response:
                status,body,nonce,write=response;write(dict(responseId=nonce,status=status,bytes=len(body),sha256=hashlib.sha256(body).hexdigest()))


class PicoGraphicsSceneTests(unittest.TestCase):
    def setUp(self):self.model=Model();self.addCleanup(self.model.close)
    def test_real_vr_inputs_align_original_scaled_head_then_restore_original_avatar_and_scene(self):
        m=self.model
        with m.lock.held():
            owner=m.factory();proof=owner.prepare()
            for a,b in zip([-.125,-.4,.25],owner.state['targetFeet']):self.assertAlmostEqual(a,b)
            self.assertEqual([0,0,0,1],owner.state['targetOrientation'])
            for a,b in zip([0,1.6,0],proof['subject']['source']['hmd']['worldPosition']):self.assertAlmostEqual(a,b)
            self.assertEqual(2,len(m.destinations));owner.restore();owner.retire()
            self.assertFalse(owner.store.path.exists());self.assertEqual(3,len(m.destinations))
        self.assertTrue(any(event=='navigation.address:submit' for event in m.native.events))
        self.assertTrue(any(event=='tablet.open' for event in m.native.events))
        self.assertTrue(all(command['action']=='feature-graphics-subject-observe' for command in m.subject.commands))
    def test_recreated_owner_uses_actual_new_sources_without_resending_original_go(self):
        m=self.model
        with m.lock.held():
            m.factory().prepare();owner=m.factory();owner.prepare();self.assertEqual(2,len(m.destinations))
            owner.restore();m.factory().retire();self.assertEqual(3,len(m.destinations))
    def test_ignored_navigation_is_not_a_scene_and_uncertain_action_is_not_replayed(self):
        m=self.model;m.fault='ignored-world'
        with m.lock.held():
            owner=m.factory()
            with self.assertRaises(NativeUIError):owner.prepare()
            with self.assertRaises(NativeUIError):m.factory().prepare()
            self.assertEqual(1,len(m.destinations));m.fault=None;m.factory().restore();m.factory().retire()
    def test_pending_original_load_group_blocks_setup_even_with_committed_scene_entities(self):
        m=self.model;m.fault='pending'
        with m.lock.held():
            with self.assertRaises(NativeUIError):m.factory().prepare()
            self.assertEqual(1,len(m.destinations));m.fault=None
            for row in m.loads.rows:
                if row['pending']:row.update(pending=False,releasedEpochMs=m.native.epoch,updatedEpochMs=m.native.epoch)
            owner=m.factory();owner.prepare();self.assertEqual(2,len(m.destinations));owner.restore();owner.retire()
    def test_lost_enter_return_recovers_from_original_sources_without_resending_input(self):
        m=self.model;m.fault='lost-go'
        with m.lock.held():
            with self.assertRaises(NativeUIError):m.factory().prepare()
            self.assertEqual(1,len(m.destinations));m.fault=None;owner=m.factory();owner.prepare()
            self.assertEqual(2,len(m.destinations));owner.restore();owner.retire()
    def test_foreign_original_ui_is_preserved_and_no_scene_input_is_delivered(self):
        m=self.model;m.native.opened=True;m.native.page='address'
        with m.lock.held():
            owner=m.factory()
            with self.assertRaises(NativeUIError):owner.prepare()
            self.assertEqual([],m.native.inputs);owner.restore();owner.retire();self.assertTrue(m.native.opened)
    def test_restoration_rejects_foreign_scene_framework_appearance_or_owned_entity_leak(self):
        m=self.model
        for fault in ('foreign-change','framework-change','entity-leak'):
            with self.subTest(fault=fault),m.lock.held():
                owner=m.factory();owner.prepare();m.fault=fault
                with self.assertRaises(NativeUIError):owner.restore()
                before=len(m.destinations)
                with self.assertRaises(NativeUIError):m.factory().restore()
                self.assertEqual(before,len(m.destinations));self.assertTrue(owner.store.path.exists())
            # A failed durable owner is intentionally kept; isolate the next
            # counterexample instead of erasing its unresolved journal.
            if fault!='entity-leak':m=Model();self.addCleanup(m.close)
    def test_stale_competing_owner_or_changed_native_birth_cannot_overwrite_journal(self):
        m=self.model
        with m.lock.held():
            owner=m.factory();owner.prepare();newer=m.factory();newer.prepare();count=len(m.destinations)
            with self.assertRaises(NativeUIError):owner.restore()
            self.assertEqual(count,len(m.destinations));m.subject.edit=lambda packet:packet.update(instance='f'*32)
            with self.assertRaises(NativeUIError):m.factory().prepare()
            self.assertTrue(newer.store.path.exists())
    def test_alignment_intent_is_recomputed_from_original_hmd_packet_in_archive(self):
        m=self.model
        with m.lock.held():
            owner=m.factory();owner.prepare();value=deepcopy(owner.previous);state=unpack(value['payload'])[0]
            state['targetFeet'][0]+=1;value['payload']=pack([state])
            with self.assertRaises(NativeUIError):owner.decode(value)
            state=unpack(owner.previous['payload'])[0];state['targetOrientation']=[0,1,0,0];value['payload']=pack([state])
            with self.assertRaises(NativeUIError):owner.decode(value)
    def test_alignment_cancels_observed_physical_yaw_through_avatar_navigation_only(self):
        m=self.model;source=deepcopy(m.original);a=math.pi/6;c,s=math.cos(a),math.sin(a)
        source['hmd']['sensorPose']=[c,0,-s,0,0,1,0,0,s,0,c,0,.1,1.6,-.2,1]
        source['hmd']['worldRotation']=[0,math.sin(math.pi/3),0,math.cos(math.pi/3)]
        source['view']['rotation']=deepcopy(source['hmd']['worldRotation']);m.subject.source=source
        packet=m._graphics_subject_observer('owned',read_only=True).read(RUN)
        old=deepcopy(packet);feet,orientation=m.graphics_scene_policy.alignment(packet)
        self.assertAlmostEqual(-math.sin(math.pi/12),orientation[1]);self.assertAlmostEqual(math.cos(math.pi/12),orientation[3])
        # Literal geometric result for initial world offset (-.25,2,-.125)
        # rotated by -120 degrees, independently of the policy's quaternion API.
        self.assertAlmostEqual(-(.125+.125*math.sqrt(3)/2),feet[0])
        self.assertAlmostEqual(-.4,feet[1]);self.assertAlmostEqual(.25*math.sqrt(3)/2-.0625,feet[2])
        self.assertEqual(old,packet);self.assertEqual([],m.destinations)

    def test_normal_physical_head_tracking_is_not_avatar_motion_or_unowned_scene_restoration(self):
        m=self.model;reader=m._graphics_subject_observer('owned',read_only=True);before=reader.read(RUN)
        m.subject.source['hmd']['sensorPose'][12]+=.1
        m.subject.source['hmd']['worldPosition'][2]-=.125;m.subject.source['view']['position'][2]-=.125
        after=reader.read(RUN);m.graphics_scene_policy.restored(before,after)
        m.subject.source['avatarPose']['feetPosition'][0]+=.1;after=reader.read(RUN)
        with self.assertRaises(NativeUIError):m.graphics_scene_policy.restored(before,after)

    def test_unlevel_or_unmounted_head_is_not_repaired_by_camera_or_navigation_input(self):
        m=self.model
        for kind in ('tilt','unmounted','camera','keyboard'):
            m.subject.source=deepcopy(m.original)
            if kind=='tilt':
                a=.2;c,s=math.cos(a),math.sin(a);head=m.subject.source['hmd']
                head['sensorPose']=[1,0,0,0,0,c,s,0,0,-s,c,0,.1,1.6,-.2,1]
                # Avatar yaw=90 degrees times physical X rotation=.2 radians.
                q=math.sqrt(.5);head['worldRotation']=[q*math.sin(a/2),q*math.cos(a/2),-q*math.sin(a/2),q*math.cos(a/2)]
                m.subject.source['view']['rotation']=deepcopy(head['worldRotation'])
            elif kind=='unmounted':m.subject.source['hmd']['mounted']=False
            elif kind=='camera':m.subject.source['view']['mode']='first person look at'
            else:m.subject.source['framework']['keyboard']['raised']=True
            packet=m._graphics_subject_observer('owned',read_only=True).read(RUN)
            with self.subTest(kind=kind),self.assertRaises(NativeUIError):
                m.graphics_scene_policy.eligible(packet);m.graphics_scene_policy.alignment(packet)
        self.assertEqual([],m.destinations);self.assertEqual([],m.native.inputs)

    def test_scene_policy_identity_and_actual_journal_absence_are_required(self):
        from unittest.mock import patch
        m=self.model
        with m.lock.held():
            owner=m.factory();owner.prepare();value=deepcopy(owner.previous);value['scenePolicy']='phone-mono-v1'
            with self.assertRaises(NativeUIError):owner.decode(value)
            owner.restore()
            with patch.object(owner.store,'discard',return_value=None),self.assertRaises(NativeUIError):owner.retire()
            self.assertTrue(owner.store.path.exists());owner.retire();self.assertFalse(owner.store.path.exists())

    def test_original_resource_query_bytes_are_preserved_by_normal_navigation_viewpoint(self):
        original=ORIGINAL+'?opaque=%2fVALUE&location=/1,2,3/0,0,0,1&blank=&raw=one+two'
        changed=viewpoint(original,[0,-.4,0],[0,0,0,1])
        self.assertEqual(resource_hash(original),resource_hash(changed));self.assertIn('opaque=%2fVALUE&blank=&raw=one+two',changed)


if __name__=='__main__':unittest.main()
