"""Real private input leases with synthetic ordinary SDK/Qt/native sources."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'tests/device'))
sys.path.insert(0,str(ROOT/'tests/device/adapters/android-phone'))
from adapters.native_graphics_subject import NativeGraphicsSubject
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUI,NativeUIError
from adapters.token_graphics_ui import TokenGraphicsUI
from overte_phone_graphics_surface import PhoneGraphicsSurface
from overte_phone_script_lock import PhoneScriptSourceLock
from self_tests.test_native_graphics_subject import Boundary,RUN
from self_tests.test_token_graphics_ui import GraphicsBoundary
from test_account_menu import MenuClient,PACKAGE

URL='http://controlled.invalid/feature-fixture/v1/runs/'+RUN+'/tickets/'+'c'*32+'/graphics-scene.v1.json?location=/0,0,0/0,0,0,1'


class Client(MenuClient):
    def __init__(self):
        super().__init__();self.address=False;self.address_text='';self.mode='look at';self.lose='';self.settings_page=1
    def rows(self):
        if self.address:return [('PhoneAddressField',''),('PhoneAddressGoButton',''),('PhoneAddressCancelButton','')]
        common=[('nav.close',''),('nav.home','')] if self.panel is not None else [('tablet.open',''),('','Go to destination')]
        if self.panel=='home':return common+[('tabletPage.1',''),('tabletPage.2','')]+([('','MENU')] if self.page==self.menu_page else [])
        if self.panel=='menu':return common+[('','View')]
        if self.panel=='view':return common+[('','First Person'),('','Look At'),('','Selfie')]
        return common
    def call(self,method,path,body=None):
        if '/element/' in path:
            ref=path.split('/element/',1)[1].split('/')[0];resource,label=self.refs[ref]
            if path.endswith('/text'):return self.address_text
            if path.endswith('/clear') or path.endswith('/value'):
                self.inputs.append((resource,'clear' if path.endswith('/clear') else 'replace'))
                if self.ignore!='replace':self.address_text='' if path.endswith('/clear') else body['text']
                if self.lose=='replace':raise RuntimeError('Synthetic lost text input return')
                return None
            if path.endswith('/click'):
                self.inputs.append((resource,label));stage=resource or label
                if stage!=self.ignore:
                    if resource in ('tablet.open','nav.home'):self.panel='home'
                    elif resource=='nav.close':self.panel=None
                    elif resource.startswith('tabletPage.'):self.page=int(resource.rsplit('.',1)[1])
                    elif label=='Go to destination':self.address=True
                    elif resource in ('PhoneAddressGoButton','PhoneAddressCancelButton'):self.address=False
                    elif label=='MENU':self.panel='menu'
                    elif label=='View':self.panel='view'
                    elif label in ('First Person','Look At','Selfie'):self.mode={'First Person':'first person look at','Look At':'look at','Selfie':'selfie'}[label]
                    else:raise AssertionError('Unexpected synthetic ordinary input')
                if stage==self.lose:raise RuntimeError('Synthetic lost click return')
                return None
        return super().call(method,path,body)


class Qt(GraphicsBoundary):
    def __init__(self,client):super().__init__();self.client=client;self.ignore_entry=''
    def capture(self):
        value=super().capture();panel=self.client.panel
        if panel=='graphics':return value
        identifiers=(['settings.entry'] if panel=='home' and self.client.page==self.client.settings_page else
                     ['graphics.settings-entry'] if panel=='settings' else [])
        value['controls']=[dict(id=key,token=hashlib.sha256((key+panel).encode()).hexdigest()[:32],enabled=True,
            inputReady=True,viewport='visible') for key in identifiers]
        return value
    def activate(self,identifier,*,token):
        if identifier in ('settings.entry','graphics.settings-entry'):
            self.original(identifier,token);self.actions.append(identifier)
            if self.ignore_entry!=identifier:self.client.panel='settings' if identifier=='settings.entry' else 'graphics'
        else:super().activate(identifier,token=token)


class GraphicsSurfaceTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory(prefix='overte-graphics-surface-');self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.store=PrivateFeatureState(self.root/'surface.json')
        self.store.write(dict(tablet=False,address=False,menu=False,last=None),None)
        self.client=Client();self.boundary=Boundary();self.boundary.source.update(subjectVersion=2,
            avatarPose=dict(feetPosition=[0,-.2,0],orientation=[0,0,0,1],modelScale=1.25))
        self.boundary.edit=lambda packet:packet['source']['view'].update(mode=self.client.mode)
        self.source=NativeGraphicsSubject(self.boundary.send,self.boundary.original,lambda:20000,lambda:self.boundary.okay,31,
            monotonic=lambda:self.client.clock,sleep=self.sleep)
        self.ui=NativeUI(self.client,'native-session',lambda:self.boundary.okay,timeout=.6,
            monotonic=lambda:self.client.clock,sleep=self.sleep)
        self.qt=Qt(self.client);self.graphics=TokenGraphicsUI(self.qt,lambda *_:None,monotonic=lambda:self.client.clock,sleep=self.sleep)
        self.intents=[];self.fail_intent=False;self.fail_lease=False
        self.surface=PhoneGraphicsSurface(self.ui,self.source,self.graphics,RUN,self.intent,
            lambda field:self.store.read()[field],self.lease,lambda url:url==URL)
    def sleep(self,seconds):self.client.clock+=seconds
    def intent(self,stage,original,graphics,control):
        if self.fail_intent:raise OSError('Synthetic unavailable private input journal')
        value=self.store.read();updated=deepcopy(value)
        updated['last']=dict(stage=stage,source=deepcopy(original),graphics=deepcopy(graphics),control=control)
        self.store.write(updated,value);self.intents.append(updated['last'])
        if graphics is not None:self.qt.intents.append((stage,control))
    def lease(self,field,value):
        if self.fail_lease:raise OSError('Synthetic unavailable private lease')
        previous=self.store.read();updated=deepcopy(previous);updated[field]=value;self.store.write(updated,previous)

    def test_go_to_uses_only_normal_field_and_go_input_with_original_pose_barriers(self):
        old=self.boundary.source['sceneUrl'];receipt=self.surface.navigate(URL)
        self.assertEqual({'performed':True},receipt);self.assertEqual(URL,self.client.address_text)
        self.assertEqual(['Go to destination','PhoneAddressField','PhoneAddressField','PhoneAddressGoButton'],
            [resource or label for resource,label in self.client.inputs])
        self.assertFalse(self.store.read()['address']);self.assertTrue(all(item['source']['source']['subjectVersion']==2 for item in self.intents))
        self.assertEqual(old,self.source.read(RUN)['source']['sceneUrl']) # Editor dismissal proves no scene load.
        self.assertNotIn('state',receipt);self.assertNotIn('expected',repr(self.boundary.commands))

    def test_normal_settings_path_and_all_three_scalar_inputs_use_original_widgets(self):
        self.surface.open();self.surface.set_resolution(.5);self.surface.toggle('graphics.haze',True);self.surface.toggle('graphics.mirrors',True)
        self.assertEqual(.5,self.qt.resolution);self.assertTrue(self.qt.haze);self.assertTrue(self.qt.mirrors)
        self.assertIn('settings.entry',self.qt.actions);self.assertIn('graphics.settings-entry',self.qt.actions)
        self.assertTrue(any(stage.startswith('graphics-scroll-') for stage in [item['stage'] for item in self.intents]))
        self.surface.close_tablet();self.assertFalse(self.store.read()['tablet']);self.assertIsNone(self.client.panel)

    def test_original_settings_launcher_pagination_uses_actual_page_controls(self):
        self.client.settings_page=2;self.surface.open()
        self.assertIn(('tabletPage.2',''),self.client.inputs);self.assertEqual('graphics',self.client.panel)

    def test_normal_view_menu_requires_actual_camera_change_and_closes_its_owned_panel(self):
        receipt=self.surface.select_camera('first person look at')
        self.assertEqual({'performed':True},receipt);self.assertEqual('first person look at',self.client.mode)
        self.assertEqual(['tablet.open','nav.home','MENU','View','First Person','nav.close'],
            [resource or label for resource,label in self.client.inputs])
        self.assertFalse(self.store.read()['tablet']);self.assertFalse(self.store.read()['menu'])
        self.assertEqual('camera-select',self.intents[-2]['stage'])

    def test_unchanged_camera_mode_is_a_measured_no_input_case_and_unselectable_mode_is_rejected(self):
        self.assertEqual({'performed':False},self.surface.select_camera('look at'));self.assertEqual([],self.client.inputs)
        with self.assertRaises(NativeUIError):self.surface.select_camera('first person')
        self.assertEqual([],self.client.inputs)

    def test_foreign_tablet_or_address_editor_is_preserved_without_input(self):
        self.client.panel='foreign'
        with self.assertRaises(NativeUIError):self.surface.open()
        self.assertEqual([],self.client.inputs);self.client.panel=None;self.client.address=True
        with self.assertRaises(NativeUIError):self.surface.navigate(URL)
        self.assertTrue(self.client.address);self.assertEqual([],self.client.inputs)

    def test_previous_tablet_or_menu_lease_does_not_adopt_a_foreign_replacement_page(self):
        self.surface.open();self.client.panel='foreign';before=len(self.client.inputs)
        for menu in (False,True):
            self.lease('menu',menu)
            for operation in (self.surface.open,self.surface.close_tablet,lambda:self.surface.select_camera('first person look at')):
                with self.subTest(menu=menu),self.assertRaises(NativeUIError):operation()
                self.assertEqual(before,len(self.client.inputs))
        self.assertTrue(self.store.read()['tablet']);self.assertEqual('foreign',self.client.panel)

    def test_denied_url_credentials_or_control_characters_never_reach_input(self):
        for url in (URL+'foreign','https://user:secret@owned.invalid/scene.json',URL+'\n','javascript:alert(1)'):
            with self.subTest(kind='rejected'),self.assertRaises(NativeUIError):self.surface.navigate(url)
        self.assertEqual([],self.client.inputs);self.assertFalse(self.store.read()['address'])

    def test_failed_intent_or_lease_is_durable_failure_before_any_mutation(self):
        for field in ('fail_intent','fail_lease'):
            setattr(self,field,True)
            with self.subTest(field=field),self.assertRaises((NativeUIError,OSError)):self.surface.navigate(URL)
            setattr(self,field,False)
        self.assertEqual([],self.client.inputs)

    def test_ignored_go_or_text_input_retains_address_lease_without_replaying_it(self):
        for ignored in ('PhoneAddressGoButton','replace'):
            self.client.ignore=ignored;self.client.inputs=[];self.client.address_text='original unrelated destination'
            with self.subTest(ignored=ignored),self.assertRaises(NativeUIError):self.surface.navigate(URL)
            self.assertTrue(self.store.read()['address'])
            self.assertEqual(1,sum(resource=='PhoneAddressField' and label=='replace' for resource,label in self.client.inputs))
            self.assertLessEqual(sum(resource=='PhoneAddressGoButton' for resource,_ in self.client.inputs),1)
            self.client.ignore='';self.surface.close_address();self.assertFalse(self.store.read()['address'])

    def test_lost_go_return_keeps_the_scope_until_a_fresh_owned_absence_is_checked(self):
        self.client.lose='PhoneAddressGoButton'
        with self.assertRaises(NativeUIError):self.surface.navigate(URL)
        self.assertFalse(self.client.address);self.assertTrue(self.store.read()['address'])
        self.client.lose='';self.surface.close_address();self.assertFalse(self.store.read()['address'])
        self.assertEqual(1,sum(resource=='PhoneAddressGoButton' for resource,_ in self.client.inputs))

    def test_ignored_camera_menu_cannot_become_mode_success_from_its_ack(self):
        self.client.ignore='First Person'
        with self.assertRaises(NativeUIError):self.surface.select_camera('first person look at')
        self.assertEqual('look at',self.client.mode);self.assertTrue(self.store.read()['menu']);self.assertTrue(self.store.read()['tablet'])
        self.assertEqual(1,sum(label=='First Person' for _,label in self.client.inputs))
        self.client.ignore='';self.surface.close_tablet();self.assertFalse(self.store.read()['menu'])

    def test_ignored_scalar_inputs_or_missing_settings_entry_never_replay_their_click(self):
        self.qt.ignore_entry='settings.entry'
        with self.assertRaises(NativeUIError):self.surface.open()
        self.assertEqual(['settings.entry'],self.qt.actions);self.assertTrue(self.store.read()['tablet'])
        self.qt.ignore_entry='';self.surface.open();self.qt.fault='toggle'
        with self.assertRaises(NativeUIError):self.surface.toggle('graphics.haze',True)
        self.assertFalse(self.qt.haze);self.assertEqual(1,self.qt.actions.count('graphics.haze'))

    def test_foreign_package_or_ambiguous_actual_control_cannot_receive_go_to_input(self):
        for fault in ('package','duplicate'):
            self.client.package='foreign.package' if fault=='package' else PACKAGE;self.client.duplicate=fault=='duplicate'
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.surface.navigate(URL)
        self.assertEqual([],self.client.inputs)

    def test_missing_required_pose_or_lost_scope_prevents_first_input(self):
        self.boundary.source['subjectVersion']=1;self.boundary.source.pop('avatarPose')
        with self.assertRaises(NativeUIError):self.surface.navigate(URL)
        self.boundary.okay=False
        with self.assertRaises(NativeUIError):self.surface.open()
        self.assertEqual([],self.client.inputs)

    def test_input_deadline_includes_private_ownership_and_lost_guard_after_intent(self):
        original=self.surface.intent
        def late(*args):original(*args);self.client.clock+=21
        self.surface.intent=late
        with self.assertRaises(NativeUIError):self.surface.navigate(URL)
        self.assertEqual([],self.client.inputs);self.client.clock=21;self.surface.intent=original
        def lost(*args):original(*args);self.boundary.okay=False
        self.surface.intent=lost
        with self.assertRaises(NativeUIError):self.surface.navigate(URL)
        self.assertEqual([],self.client.inputs)

    def bound_factory(self):
        import test_feature_adapters as bound
        phone=bound.appium
        f=bound.FeatureAdapterTests('test_existing_input_scope_admits_normal_file_input_without_parent_session_repair')
        f.setUp();self.addCleanup(f.doCleanups)
        source,_reader=f.graphics_subject_boundaries();f.read_only_boundaries(forbid_normal_session=False)
        repairing=patch.object(bound.AppiumAdapter,'ensure_session',side_effect=AssertionError('Unexpected SDK repair'))
        repairing.start();self.addCleanup(repairing.stop)
        source.source.update(subjectVersion=2,avatarPose=dict(feetPosition=[0,-.2,0],orientation=[0,0,0,1],modelScale=1.25))
        original=f.native.call
        def call(method,path,body=None):
            if method=='GET' and path=='/session/native-session':return original(method,path,body)
            return self.client.call(method,path,body)
        boundary=patch.object(phone,'WebDriver',return_value=type('SDK',(),{'call':staticmethod(call)})())
        boundary.start();self.addCleanup(boundary.stop)
        lock=PhoneScriptSourceLock(f.state_path.with_name('phone-script-sources.lock'))
        return f,source,lock,bound.SELECTOR

    def test_bound_factory_uses_existing_session_and_requires_the_held_source_lock_for_input(self):
        f,source,lock,selector=self.bound_factory()
        with lock.held():
            surface=f.adapter._graphics_surface(selector,RUN,self.intent,lambda field:self.store.read()[field],self.lease,
                lambda url:url==URL,lock=lock)
            self.assertEqual({'performed':True},surface.navigate(URL))
        self.assertEqual(URL,self.client.address_text);before=len(self.client.inputs)
        with self.assertRaises(NativeUIError):surface.open()
        self.assertEqual(before,len(self.client.inputs));self.assertEqual([],f.native.lifecycle_inputs)
        self.assertTrue(all(command['action']=='feature-graphics-subject-observe' for command in source.commands))

    def test_factory_refuses_actor_input_unheld_lock_and_changed_candidate_before_mutation(self):
        f,_source,lock,selector=self.bound_factory()
        parameters=(selector,RUN,self.intent,lambda field:self.store.read()[field],self.lease,lambda url:url==URL)
        with self.assertRaises(NativeUIError):f.adapter._graphics_surface(*parameters,lock=lock)
        with lock.held():
            with self.assertRaises(ValueError):f.adapter._graphics_surface(*parameters,lock=lock,role='actor')
            surface=f.adapter._graphics_surface(*parameters,lock=lock)
            f.fixture.adb.digest='f'*64
            with self.assertRaises((NativeUIError,ValueError)):surface.navigate(URL)
        self.assertEqual([],self.client.inputs)
