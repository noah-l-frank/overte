"""Ordinary fake SDK input, original source models and real private scene journals."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest
import uuid
from urllib.parse import parse_qs,urlsplit

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'tests/device'))
sys.path.insert(0,str(ROOT/'tests/device/adapters/android-phone'))
from adapters.native_graphics_subject import NativeGraphicsSubject
from adapters.native_phone_scene_loads import resource_hash
from adapters.normal_ui import NativeUIError
from feature_journeys.witness import Client
from overte_phone_graphics_scene import PhoneGraphicsScene,viewpoint
from overte_phone_graphics_surface import PhoneGraphicsSurface
from overte_phone_script_history import unpack,pack
from overte_phone_script_lock import PhoneScriptSourceLock
import test_graphics_surface as surface_fixture
RUN=surface_fixture.RUN
from test_graphics_measurements import Sources
from test_graphics_images import BINDING
from self_tests.test_native_phone_scene_loads import Boundary as LoadBoundary,row as load_row

ORIGINAL='http://controlled.invalid/original-scene.json'


class Model:
    def __init__(self):
        self.fixture=surface_fixture.GraphicsSurfaceTests();self.fixture.setUp();self.root=self.fixture.root
        self.sdk=self.fixture.client;self.native=self.fixture.boundary;self.sdk.mode='first person look at'
        source=self.native.source;source['sceneUrl']=ORIGINAL
        source['avatarPose'].update(feetPosition=[1,0,2],modelScale=1.25)
        source['view'].update(mode=self.sdk.mode,position=[1,1.8,2])
        source['scan'].update(scannedEntities=1,unowned=[dict(id='11111111-1111-4111-8111-111111111111',sha256='f'*64)])
        self.original=deepcopy(source);self.controlled=Sources();self.fault=None;self.destinations=[]
        self.loads=LoadBoundary();self.loads.rows[0]['resourceSha256']=resource_hash(ORIGINAL)
        self.client=object.__new__(Client);self.client.url='http://controlled.invalid/feature-fixture/v1'
        self.client.run=RUN;self.client.area='graphics';self.client.graphics_instance=self.controlled.instance
        self.client.graphics_previous=None;self.client.graphics_status=self.provider
        self.lock=PhoneScriptSourceLock(self.root/'phone-script-sources.lock')
        original_call=self.sdk.call
        def call(method,path,body=None):
            go=False
            if path.endswith('/click'):
                ref=path.split('/element/',1)[1].split('/')[0]
                go=self.sdk.refs[ref][0]=='PhoneAddressGoButton' and self.sdk.ignore!='PhoneAddressGoButton'
            try:return original_call(method,path,body)
            finally:
                if go and self.sdk.address is False:self.load(self.sdk.address_text)
        self.sdk.call=call
    def close(self):self.fixture.doCleanups()
    def provider(self):
        value=deepcopy(self.controlled.provider);value['requestId']=uuid.uuid4().hex
        self.client.graphics_previous=deepcopy(value);return value
    def state_path(self,_selector):return self.root/'session.json'
    def normal_feature_runtime(self,_selector,*,read_only):
        assert read_only;return self.fixture.ui,None,deepcopy(BINDING),lambda:self.native.okay,None
    def _graphics_subject_observer(self,_selector,*,read_only):
        assert read_only;return NativeGraphicsSubject(self.native.send,self.native.original,lambda:20000,lambda:self.native.okay,31,
            monotonic=lambda:self.sdk.clock,sleep=self.fixture.sleep)
    def _scene_load_observer(self,_selector,*,read_only):assert read_only;return self.loads.reader()
    def _graphics_surface(self,_selector,run,intent,owns,lease,allow_url,*,lock):
        lock.assert_held()
        return PhoneGraphicsSurface(self.fixture.ui,self._graphics_subject_observer('controlled',read_only=True),
            self.fixture.graphics,run,intent,owns,lease,allow_url)
    def factory(self):return PhoneGraphicsScene(self,'controlled',self.client,RUN,self.lock,
        monotonic=lambda:self.sdk.clock,sleep=self.fixture.sleep)
    def load(self,url):
        self.destinations.append(url)
        if self.fault=='ignore-world':return
        controlled=resource_hash(url)!=resource_hash(ORIGINAL)
        source=deepcopy(self.controlled.subject_before['source'] if controlled else self.original)
        if controlled:source.update(subjectVersion=2,avatarPose=deepcopy(self.original['avatarPose']))
        location=parse_qs(urlsplit(url).query)['location'][0].split('/')
        feet=[float(v) for v in location[1].split(',')];orientation=[float(v) for v in location[2].split(',')]
        source['avatarPose'].update(feetPosition=feet,orientation=orientation)
        source['view'].update(position=[feet[0],feet[1]+1.8,feet[2]],rotation=orientation,mode=self.sdk.mode)
        source['sceneUrl']=url
        if self.fault=='wrong-position':source['view']['position'][0]+=1
        if self.fault=='foreign-change' and not controlled:source['scan']['unowned'][0]['sha256']='e'*64
        if self.fault=='leaked-entity' and not controlled:
            entity=deepcopy(self.controlled.subject_before['source']['entities'][0])
            source['entities'].append(entity);source['absentIds'].remove(entity['id'])
        self.native.source=source
        self.loads.generation+=1
        self.loads.rows.append(load_row(uuid.uuid4().hex,generation=self.loads.generation,resourceSha256=resource_hash(url)))
        if self.fault=='pending':self.loads.rows[-1].update(pending=True,releasedEpochMs=None)


class GraphicsSceneTests(unittest.TestCase):
    def setUp(self):self.model=Model();self.addCleanup(self.model.close)
    def test_viewpoint_replaces_only_location_and_preserves_original_encoded_resource_query(self):
        original=ORIGINAL+'?path=%2fopaque%2Fvalue&empty=&location=/9,8,7/0,0,0,1&raw=one+two'
        changed=viewpoint(original,[0,-.2,0],[0,0,0,1])
        self.assertEqual(resource_hash(original),resource_hash(changed))
        self.assertIn('path=%2fopaque%2Fvalue&empty=&raw=one+two',changed)
        self.assertEqual(['/0,-0.2,0/0,0,0,1'],parse_qs(urlsplit(changed).query)['location'])

    def test_ordinary_scene_and_actual_eye_offset_are_owned_and_original_scene_pose_is_restored(self):
        m=self.model
        with m.lock.held():
            owner=m.factory();proof=owner.prepare()
            for actual,wanted in zip(owner.state['targetFeet'],[0,-.2,0]):self.assertAlmostEqual(wanted,actual)
            self.assertEqual([0,1.6,0],proof['subject']['source']['view']['position'])
            self.assertEqual(2,len(m.destinations));self.assertEqual('active',owner.state['phase'])
            original=owner.restore();self.assertEqual([1,1.8,2],original['subject']['source']['view']['position'])
            self.assertEqual(3,len(m.destinations));self.assertEqual([],original['subject']['source']['entities'])
            owner.retire();self.assertFalse(owner.store.path.exists())
        self.assertTrue(all(command['action']=='feature-graphics-subject-observe' for command in m.native.commands))
        self.assertTrue(all(command['action']=='feature-scene-load-observe' for command in m.loads.commands))

    def test_recreated_active_owner_uses_new_originals_without_replaying_navigation(self):
        m=self.model
        with m.lock.held():
            m.factory().prepare();before=len(m.destinations);owner=m.factory();owner.prepare()
            self.assertEqual(before,len(m.destinations));owner.restore();m.factory().retire()

    def test_editor_dismissal_cannot_make_an_ignored_world_navigation_ready(self):
        m=self.model;m.fault='ignore-world'
        with m.lock.held():
            owner=m.factory()
            with self.assertRaises(NativeUIError):owner.prepare()
            self.assertEqual(1,len(m.destinations));self.assertEqual('preparing',owner.state['phase'])
            owner=m.factory()
            with self.assertRaises(NativeUIError):owner.prepare()
            self.assertEqual(1,len(m.destinations))
            m.fault=None;owner.restore();owner.retire()

    def test_committed_scene_with_held_native_group_remains_unready_without_input_replay(self):
        m=self.model;m.fault='pending'
        with m.lock.held():
            owner=m.factory()
            with self.assertRaises(NativeUIError):owner.prepare()
            self.assertEqual(1,len(m.destinations))
            m.fault=None
            for row in m.loads.rows:row.update(pending=False,releasedEpochMs=20000)
            owner=m.factory();owner.prepare();self.assertEqual(2,len(m.destinations));owner.restore();owner.retire()

    def test_lost_enter_response_recovers_only_from_actual_scene_without_repeating_the_go_input(self):
        m=self.model;m.sdk.lose='PhoneAddressGoButton'
        with m.lock.held():
            owner=m.factory()
            with self.assertRaises(NativeUIError):owner.prepare()
            self.assertEqual(1,len(m.destinations));m.sdk.lose=''
            owner=m.factory();owner.prepare();self.assertEqual(2,len(m.destinations));owner.restore();owner.retire()

    def test_foreign_baseline_ui_or_unrestorable_mode_is_preserved_before_any_input(self):
        m=self.model
        with m.lock.held():
            m.sdk.address=True;owner=m.factory()
            with self.assertRaises(NativeUIError):owner.prepare()
            self.assertEqual([],m.sdk.inputs);owner.restore();owner.retire();self.assertTrue(m.sdk.address)
            m.sdk.address=False;m.sdk.mode='selfie';owner=m.factory()
            with self.assertRaises(NativeUIError):owner.prepare()
            self.assertEqual([],m.sdk.inputs);owner.restore();owner.retire()

    def rejected_restoration(self,fault):
        m=self.model
        with m.lock.held():
            owner=m.factory();owner.prepare();m.fault=fault
            with self.assertRaises(NativeUIError):owner.restore()
            with self.assertRaises(NativeUIError):owner.retire()
            self.assertTrue(owner.store.path.exists())
            before=len(m.destinations);owner=m.factory()
            with self.assertRaises(NativeUIError):owner.restore()
            self.assertEqual(before,len(m.destinations))

    def test_foreign_spatial_state_change_blocks_restoration_and_retirement(self):
        self.rejected_restoration('foreign-change')

    def test_owned_entity_leak_blocks_restoration_and_retirement(self):
        self.rejected_restoration('leaked-entity')

    def test_successful_restoration_with_lost_go_response_requires_new_sources_without_replay(self):
        m=self.model
        with m.lock.held():
            owner=m.factory();owner.prepare();m.sdk.lose='PhoneAddressGoButton'
            with self.assertRaises(NativeUIError):owner.restore()
            self.assertEqual(3,len(m.destinations));m.sdk.lose='';owner=m.factory()
            owner.restore();owner.retire();self.assertEqual(3,len(m.destinations))

    def test_changed_native_subject_birth_cannot_be_adopted_after_owner_recreation(self):
        m=self.model
        with m.lock.held():
            owner=m.factory();owner.prepare();before=len(m.destinations)
            m.native.edit=lambda packet:packet.update(instance='f'*32)
            with self.assertRaises(NativeUIError):m.factory().prepare()
            self.assertEqual(before,len(m.destinations));self.assertTrue(owner.store.path.exists())

    def test_a_competing_owner_cannot_overwrite_newer_originals_or_retire_them(self):
        m=self.model
        with m.lock.held():
            first=m.factory();first.prepare();second=m.factory();second.prepare()
            before=len(m.destinations)
            with self.assertRaises(NativeUIError):first.restore()
            self.assertEqual(before,len(m.destinations));second.restore();second.retire()

    def test_unobserved_journal_discard_cannot_report_retirement(self):
        from unittest.mock import patch
        m=self.model
        with m.lock.held():
            owner=m.factory();owner.prepare();owner.restore()
            with patch.object(owner.store,'discard',return_value=None),self.assertRaises(NativeUIError):owner.retire()
            self.assertTrue(owner.store.path.exists());owner.retire()

    def test_forged_action_url_or_foreign_run_cannot_become_an_owned_navigation_allowlist(self):
        m=self.model
        with m.lock.held():
            owner=m.factory();owner.prepare();store=owner.store;value=store.read()
            changed=deepcopy(value);state=unpack(changed['payload'])[0];state['actions'][0]['url']='http://foreign.invalid/scene.json'
            changed['payload']=pack([state]);store.write(changed,value)
            before=len(m.destinations)
            with self.assertRaises(NativeUIError):m.factory()
            self.assertEqual(before,len(m.destinations));store.write(value,changed)
            owner.restore();owner.retire()
