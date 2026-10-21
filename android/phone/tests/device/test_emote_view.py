"""Real normal input, native readers and private journals at synthetic boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone')]
from adapters.native_avatar_render import NativeAvatarRender
from adapters.native_phone_avatar_configuration import NativePhoneAvatarConfiguration
from adapters.native_phone_touch_state import NativePhoneTouchState
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.witness import Client,Journal
from overte_phone_emote_view import PhoneEmoteView,EmoteViewSurface,PINCH
from overte_phone_graphics_surface import PhoneGraphicsSurface
from overte_phone_script_lock import PhoneScriptSourceLock
from overte_phone_script_history import pack,unpack
from self_tests.test_native_phone_avatar_configuration import Boundary as ConfigurationBoundary
from self_tests.test_native_phone_touch_state import Boundary as TouchBoundary
from test_graphics_images import BINDING
import test_graphics_surface as surface_fixture

RUN=surface_fixture.RUN


class Model:
    def __init__(self):
        self.fixture=surface_fixture.GraphicsSurfaceTests();self.fixture.setUp()
        self.root,self.sdk=self.fixture.root,self.fixture.client
        self.native=ConfigurationBoundary();self.touch=TouchBoundary()
        self.boom=1.5;self.preference=False;self.editor=False;self.lose='';self.ignore='';self.fault=None;self.actions=[];self.actions_retired=[]
        self.lock=PhoneScriptSourceLock(self.root/'phone-script-sources.lock')
        self.journal=Journal(lambda:self.native.epoch)
        with patch('feature_journeys.witness.secrets.token_hex',return_value=RUN):self.journal.register('emotes')
        self.journal.activate(RUN,'c'*32)
        self.client=Client('http://controlled.invalid/feature-fixture/v1','x'*64)
        self.client.request=lambda _path,**options:self.journal.phase(RUN,options['phase_nonce'])
        self.phase=PhaseFixtureReader(self.client,RUN,'emotes',epoch_ms=lambda:self.native.epoch,monotonic=lambda:self.sdk.clock)
        original_rows=self.sdk.rows;original_call=self.sdk.call
        def rows():
            base=original_rows()
            if self.sdk.panel=='settings':return base+[('settings.general','General')]
            if self.sdk.panel=='general':return base+[('GeneralPreferencesSave','Save changes'),('GeneralPreferencesCancel','Cancel'),('',PINCH)]
            return base
        self.sdk.rows=rows
        def call(method,path,body=None):
            stage=None
            if path.endswith('/window/rect'):return dict(x=0,y=0,width=1000,height=600)
            if path.endswith('/actions'):
                stage='pinch' if method=='POST' else 'release'
                if method=='POST':
                    self.actions.append(deepcopy(body));self.touch.touch['viewContact']=True
                    if self.ignore!='pinch':self.boom*=1.6
                elif self.ignore!='release':self.touch.touch['viewContact']=False
            elif path.endswith('/click'):
                resource,label=self.sdk.refs[path.split('/element/',1)[1].split('/')[0]];stage=resource or label
                if stage in ('settings.general','GeneralPreferencesSave','GeneralPreferencesCancel',PINCH):
                    self.sdk.inputs.append((resource,label))
                    if self.ignore!=stage:
                        if stage=='settings.general':self.sdk.panel='general';self.editor=self.preference
                        elif stage==PINCH:self.editor=not self.editor
                        elif stage=='GeneralPreferencesSave':self.preference=self.editor;self.sdk.panel='settings'
                        else:self.sdk.panel='settings'
                else:
                    old=self.sdk.mode;result=original_call(method,path,body)
                    if old!=self.sdk.mode:
                        if self.sdk.mode=='first person look at':self.boom=.5
                        elif self.boom==.5:self.boom=1.5
                    if stage==self.lose:raise RuntimeError('Synthetic lost normal input return')
                    return result
            else:
                result=original_call(method,path,body)
                if path.endswith('/source') and self.sdk.panel=='general':
                    tree=ET.fromstring(result)
                    for row in tree.iter():
                        if row.get('text')==PINCH:row.set('checkable','true');row.set('checked','true' if self.editor else 'false')
                    return ET.tostring(tree,encoding='unicode')
                return result
            if stage==self.lose:raise RuntimeError('Synthetic lost normal input return')
        self.sdk.call=call
        def subject(value):
            value['instance']='f'*32;value['source']['sceneUrl']='hifi://controlled.invalid/0,0,0'
            value['source']['view'].update(mode=self.sdk.mode)
        self.fixture.boundary.edit=subject

    def close(self):self.fixture.doCleanups()
    def state_path(self,_selector):return self.root/'session.json'
    def normal_feature_runtime(self,_selector,*,read_only):
        assert read_only;return self.fixture.ui,None,deepcopy(BINDING),lambda:self.native.okay,None
    @contextmanager
    def existing_input_session(self,_selector):yield
    def _graphics_surface(self,_selector,run,intent,owns,lease,allow_url,*,lock):
        lock.assert_held()
        def original(identifier,token):
            view=PrivateFeatureState(self.root/'phone-emote-view.json').read()
            state=unpack(view['payload'])[0];row=state['actions'][state['active']]
            assert row['phase']=='issued' and row['intents'][-1]['control']==identifier
            assert row['intents'][-1]['graphics'] is not None
            current=self.fixture.qt.capture();matches=[item for item in current['controls'] if item['id']==identifier]
            assert len(matches)==1 and matches[0]['token']==token
        self.fixture.qt.original=original
        return PhoneGraphicsSurface(self.fixture.ui,self.fixture.source,self.fixture.graphics,run,intent,owns,lease,allow_url)
    def sync(self):
        self.native.configuration.update(boomLength=self.boom,pinchZoomEnabled=self.preference)
        self.native.avatar['cameraMode']=self.sdk.mode
        self.native.avatar['view']['position']=[0,1.6,0 if self.sdk.mode=='first person look at' else self.boom]
        if self.fault=='avatar':self.native.avatar['geometry']['instance']='1'*32
        if self.fault=='pose':self.native.avatar['pose']['feetPosition'][0]=2
    def _avatar_configuration_observer(self,_selector,*,read_only):
        assert read_only;self.sync()
        return NativePhoneAvatarConfiguration(self.native.send,self.native.original,lambda:self.native.epoch,lambda:self.native.okay,31,
            monotonic=lambda:self.sdk.clock,sleep=self.fixture.sleep)
    def _avatar_render_observer(self,_selector,*,read_only):
        assert read_only;self.sync()
        return NativeAvatarRender(self.native.send,self.native.original,lambda:self.native.epoch,lambda:self.native.okay,31,
            monotonic=lambda:self.sdk.clock,sleep=self.fixture.sleep)
    def _touch_state_observer(self,_selector,*,read_only):
        assert read_only;self.touch.epoch=self.native.epoch
        return NativePhoneTouchState(self.touch.send,self.touch.original,lambda:self.native.epoch,lambda:self.native.okay,31,
            monotonic=lambda:self.sdk.clock,sleep=self.fixture.sleep)
    def cleaning(self):
        rows=self.journal.runs[RUN]['phaseActivations']
        if rows[-1]['stimulus']['verb']!='cleanup':self.journal.activate(RUN,'e'*32,verb='cleanup',inputs={})
    def cleanup(self,view):self.cleaning();return view.cleanup()
    def retire(self,view):return view.retire(lambda proof:self.actions_retired.append(deepcopy(proof)))
    def factory(self):return PhoneEmoteView(self,'controlled',self.phase,self.lock,monotonic=lambda:self.sdk.clock,sleep=self.fixture.sleep)


class EmoteViewTests(unittest.TestCase):
    def setUp(self):self.model=Model();self.addCleanup(self.model.close)
    def test_normal_preference_selfie_pinch_and_exact_original_restoration_preserve_domain(self):
        m=self.model
        with m.lock.held():
            view=m.factory();self.assertEqual({'performed':True},view.prepare());self.assertEqual('active',view.state['phase'])
            self.assertGreaterEqual(m.boom,3);self.assertEqual('selfie',m.sdk.mode);self.assertTrue(m.preference)
            self.assertTrue(m.actions);self.assertIsNone(m.sdk.panel)
            for gesture in m.actions:
                self.assertEqual(2,len(gesture['actions']))
                first=gesture['actions'][0]['actions'];self.assertEqual(1,len({row['x'] for row in first if row['type']=='pointerMove'}))
                self.assertEqual('pointerUp',first[-1]['type'])
            view=m.factory();m.cleanup(view);self.assertEqual(1.5,m.boom);self.assertFalse(m.preference);self.assertEqual('look at',m.sdk.mode)
            count=len(m.sdk.inputs);m.cleanup(view);self.assertEqual(count,len(m.sdk.inputs))
            view=m.factory();proof=m.retire(view);self.assertIsNone(view.store.read())
            self.assertFalse(proof['configuration']['source']['pinchZoomEnabled'])
        self.assertFalse(any('Address' in resource for resource,_label in m.sdk.inputs))
        self.assertTrue(all(row['action'] in ('phone-avatar-configuration-observe','feature-avatar-render-observe') for row in m.native.commands))

    def test_existing_first_person_and_enabled_preference_restore_without_guessing(self):
        m=self.model;m.sdk.mode='first person look at';m.boom=.5;m.preference=True
        with m.lock.held():
            view=m.factory();view.prepare();m.cleanup(view);self.assertEqual(.5,m.boom);self.assertTrue(m.preference)
            self.assertEqual('first person look at',m.sdk.mode);m.retire(view)
        self.assertFalse(any(resource=='GeneralPreferencesSave' for resource,_label in m.sdk.inputs))

    def test_nondefault_original_zoom_or_foreign_avatar_fails_before_any_input(self):
        for fault in ('zoom','avatar'):
            m=Model()
            try:
                if fault=='zoom':m.boom=2.
                else:m.native.configuration['configured']['bundledResource']['sha256']='0'*64
                with m.lock.held(),self.subTest(fault=fault),self.assertRaises(NativeUIError):m.factory().prepare()
                self.assertEqual([],m.sdk.inputs);self.assertEqual([],m.actions)
            finally:m.close()

    def test_ignored_saved_preference_is_not_inferred_from_checked_widget(self):
        m=self.model;m.ignore='GeneralPreferencesSave'
        with m.lock.held():
            view=m.factory()
            with self.assertRaises(NativeUIError):view.prepare()
            self.assertFalse(m.preference);self.assertTrue(m.editor);self.assertEqual([],m.actions)

    def test_ignored_pinch_or_camera_never_becomes_a_successful_view(self):
        for fault in ('pinch','camera'):
            m=Model()
            try:
                if fault=='pinch':m.ignore='pinch'
                else:m.sdk.ignore='Selfie'
                with m.lock.held(),self.subTest(fault=fault),self.assertRaises(NativeUIError):m.factory().prepare()
                state=unpack(PrivateFeatureState(m.root/'phone-emote-view.json').read()['payload'])[0]
                self.assertEqual('preparing',state['phase'])
            finally:m.close()

    def test_lost_gesture_return_is_observed_without_replaying_the_same_pinch(self):
        m=self.model;m.lose='pinch'
        with m.lock.held():
            with self.assertRaises(NativeUIError):m.factory().prepare()
            self.assertEqual(1,len(m.actions));m.lose=''
            view=m.factory();view.prepare();self.assertEqual(2,len(m.actions)) # The next distinct pinch, never the first one again.
            m.cleanup(view);m.retire(view)

    def test_lost_camera_return_keeps_ui_leases_and_recovers_by_observation_then_dismissal(self):
        m=self.model;m.lose='Selfie'
        with m.lock.held():
            with self.assertRaises(NativeUIError):m.factory().prepare()
            self.assertEqual('selfie',m.sdk.mode);self.assertIsNotNone(m.sdk.panel);m.lose=''
            view=m.factory();view.prepare()
            self.assertEqual(1,sum(label=='Selfie' for _resource,label in m.sdk.inputs));self.assertIsNone(m.sdk.panel)
            m.cleanup(view);m.retire(view)

    def test_lost_general_open_can_be_cancelled_from_durable_original_lease(self):
        m=self.model;m.lose='settings.general'
        with m.lock.held():
            with self.assertRaises(NativeUIError):m.factory().prepare()
            state=unpack(PrivateFeatureState(m.root/'phone-emote-view.json').read()['payload'])[0]
            self.assertTrue(state['leases']['general']);self.assertEqual('general',m.sdk.panel);m.lose=''
            view=m.factory();m.cleanup(view);m.retire(view);self.assertIsNone(m.sdk.panel);self.assertFalse(m.preference)

    def test_retained_native_contacts_block_view_and_independent_cleanup_retirement(self):
        m=self.model;m.ignore='release'
        with m.lock.held():
            with self.assertRaises(NativeUIError):m.factory().prepare()
            view=m.factory()
            with self.assertRaises(NativeUIError):m.cleanup(view)
            self.assertIsNotNone(view.store.read());m.ignore='';view=m.factory();m.cleanup(view);m.retire(view)

    def test_retirement_obtains_new_originals_and_refuses_changed_geometry_or_pose(self):
        for fault in ('avatar','pose'):
            m=Model()
            try:
                with m.lock.held():
                    view=m.factory();view.prepare();m.cleanup(view);before=len(m.native.commands);m.fault=fault
                    with self.subTest(fault=fault),self.assertRaises(NativeUIError):m.retire(view)
                    self.assertGreater(len(m.native.commands),before);self.assertIsNotNone(view.store.read())
            finally:m.close()

    def test_foreign_replacement_journal_and_lost_write_cannot_reuse_live_owner(self):
        m=self.model
        with m.lock.held():
            view=m.factory();view.prepare();original=view.store.read();foreign=deepcopy(original);foreign['runId']='0'*32
            view.store.write(foreign,original)
            with self.assertRaises(NativeUIError):m.cleanup(view)
            self.assertEqual(foreign,view.store.read());view.store.write(original,foreign)
            with patch.object(view.store,'write',side_effect=OSError('Synthetic lost durable write')),self.assertRaises(OSError):m.cleanup(view)
            with self.assertRaises(NativeUIError):m.cleanup(view)
            view=m.factory();m.cleanup(view);m.retire(view)

    def test_foreign_tablet_cannot_be_adopted_as_an_owned_general_preferences_page(self):
        m=self.model;m.sdk.panel='general'
        with m.lock.held(),self.assertRaises(NativeUIError):m.factory().prepare()
        self.assertEqual([],m.sdk.inputs)

    def test_wrong_fixture_phase_prevents_setup_and_cleanup_inputs(self):
        m=self.model
        with m.lock.held():
            view=m.factory();view.prepare();before=len(m.sdk.inputs)
            with self.assertRaises(NativeUIError):view.cleanup()
            self.assertEqual(before,len(m.sdk.inputs));m.cleaning()
            with self.assertRaises(NativeUIError):view.prepare()
            self.assertEqual(before,len(m.sdk.inputs));m.cleanup(view);m.retire(view)

    def test_provider_phase_change_between_step_barrier_and_pointer_input_is_rejected(self):
        m=self.model;call=m.sdk.call
        def change(method,path,body=None):
            result=call(method,path,body)
            if path.endswith('/click') and m.sdk.panel=='home':
                m.journal.activate(RUN,'1'*32,verb='open');m.sdk.call=call
            return result
        m.sdk.call=change
        with m.lock.held():
            with self.assertRaises(NativeUIError):m.factory().prepare()
        self.assertEqual([('tablet.open','')],m.sdk.inputs);self.assertFalse(m.preference);self.assertEqual([],m.actions)

    def test_slow_final_write_cannot_hide_stale_facts_behind_frozen_wall_clocks(self):
        m=self.model
        with m.lock.held():
            view=m.factory();write=view.store.write;delayed=[False]
            def slow(value,previous):
                write(value,previous)
                if previous is not None and unpack(value['payload'])[0]['phase']==unpack(previous['payload'])[0]['phase']=='active':
                    m.sdk.clock+=1.6;delayed[0]=True
            with patch.object(view.store,'write',side_effect=slow),self.assertRaises(NativeUIError):view.prepare()
            self.assertTrue(delayed[0]);count=len(m.sdk.inputs)
            view=m.factory();view.prepare();self.assertEqual(count,len(m.sdk.inputs));m.cleanup(view);m.retire(view)

    def test_ignored_restoration_keeps_responsibility_and_cannot_retire(self):
        m=self.model
        with m.lock.held():
            view=m.factory();view.prepare();m.sdk.ignore='First Person'
            with self.assertRaises(NativeUIError):m.cleanup(view)
            self.assertIsNotNone(view.store.read());self.assertEqual([],m.actions_retired)
            with self.assertRaises(NativeUIError):m.retire(view)

    def test_missing_durable_parent_receipt_prevents_child_ownership_removal(self):
        m=self.model
        with m.lock.held():
            view=m.factory();view.prepare();m.cleanup(view)
            with self.assertRaises(NativeUIError):view.retire(lambda proof:False)
            self.assertIsNotNone(view.store.read())
            with self.assertRaises(OSError):view.retire(lambda proof:(_ for _ in ()).throw(OSError('Synthetic lost parent receipt')))
            self.assertIsNotNone(view.store.read());m.retire(view);self.assertEqual(1,len(m.actions_retired))

    def test_lost_retirement_return_keeps_parent_proof_without_recreating_child_success(self):
        m=self.model
        with m.lock.held():
            view=m.factory();view.prepare();m.cleanup(view);discard=view.store.discard
            def lost(previous):discard(previous);raise OSError('Synthetic lost removal return')
            with patch.object(view.store,'discard',side_effect=lost),self.assertRaises(OSError):m.retire(view)
            self.assertIsNone(view.store.read());self.assertEqual(1,len(m.actions_retired))
            fresh=m.factory()
            with self.assertRaises(NativeUIError):m.retire(fresh)

    def test_pending_native_axis_after_cleanup_blocks_retirement(self):
        m=self.model
        with m.lock.held():
            view=m.factory();view.prepare();m.cleanup(view);m.touch.touch['axes']=[dict(channel=4,value=.1)]
            with self.assertRaises(NativeUIError):m.retire(view)
            self.assertIsNotNone(view.store.read());self.assertEqual([],m.actions_retired)


if __name__=='__main__':unittest.main()
