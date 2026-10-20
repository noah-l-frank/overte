"""Real private input journals, ordinary fake widgets and independent native reads."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys
import unittest
import uuid
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'tests/device'))
sys.path.insert(0,str(ROOT/'tests/device/adapters/android-phone'))
from adapters.native_feature_observation import NativeFeatureObservation
from adapters.normal_ui import NativeUIError
from adapters.token_graphics_ui import TokenGraphicsUI
from overte_phone_graphics_surface import PhoneGraphicsSurface
from overte_phone_graphics_preferences import PhoneGraphicsPreferences
from overte_phone_script_history import pack,unpack
from self_tests.test_native_feature_observation import Boundary
import test_graphics_scene as scene_fixture

RUN=scene_fixture.RUN


class Model(scene_fixture.Model):
    def __init__(self):
        super().__init__();self.features=Boundary();self.frozen=None;self.native_fault=None
        self.features.mutate=self.original_native
        def surface(selector,run,intent,owns,lease,allow_url,*,lock):
            def before(stage,subject,graphics,control):
                result=intent(stage,subject,graphics,control)
                if graphics is not None:self.fixture.qt.intents.append((stage,control))
                return result
            lock.assert_held()
            graphics=TokenGraphicsUI(self.fixture.qt,lambda *_args:None,monotonic=lambda:self.sdk.clock,sleep=self.fixture.sleep)
            return PhoneGraphicsSurface(self.fixture.ui,self._graphics_subject_observer(selector,read_only=True),
                graphics,run,before,owns,lease,allow_url)
        self._graphics_surface=surface
    def original_native(self,value):
        value['processId']=31;qt=self.fixture.qt
        value['graphics'].update(requestedResolutionScale=qt.resolution,applicationResolutionScale=qt.resolution,
            hazeSetting=qt.haze,mirrorsSetting=qt.mirrors)
        if self.frozen is not None:value['graphics']=deepcopy(self.frozen)
        if self.native_fault=='birth':value['instance']='f'*32
        if self.native_fault=='cursor':value['sequence']=1
        if self.native_fault=='shadows':value['graphics']['shadowsSetting']=True
    def _native_feature_observer(self,_selector,*,read_only):
        assert read_only
        return NativeFeatureObservation(self.features.send,self.features.original,lambda:20000,lambda:self.native.okay,31,
            monotonic=lambda:self.sdk.clock,sleep=self.fixture.sleep)
    def preferences(self,scene):
        return PhoneGraphicsPreferences(scene,monotonic=lambda:self.sdk.clock,sleep=self.fixture.sleep)


class GraphicsPreferenceTests(unittest.TestCase):
    def setUp(self):self.model=Model();self.addCleanup(self.model.close)
    def call(self,verb,**inputs):
        return dict(contractVersion=16,runId=RUN,ticket=uuid.uuid4().hex,
            fixtureUrl=self.model.client.url+'/runs/'+RUN+'/',verb=verb,inputs=inputs)
    def ready(self):
        m=self.model;scene=m.factory();scene.prepare();owner=m.preferences(scene);owner.prepare();return scene,owner
    def retire(self,scene,owner):owner.cleanup();owner.retire();scene.restore();scene.retire()

    def test_all_ordinary_preferences_restore_actual_nondefault_original_without_renderer_flags(self):
        m=self.model
        with m.lock.held():
            scene,owner=self.ready();self.assertEqual(.65,owner.state['original']['graphics']['requestedResolutionScale'])
            calls=[self.call('open'),self.call('set-resolution',value=.5),self.call('close'),self.call('open'),
                self.call('set-resolution',value=.6),self.call('set-haze',enabled=False),self.call('set-haze',enabled=True),
                self.call('set-mirrors',enabled=False),self.call('set-mirrors',enabled=True),self.call('restore-original'),self.call('close')]
            for call in calls:self.assertEqual({'performed':True},owner.act(call))
            self.assertEqual(.65,m.fixture.qt.resolution);self.assertFalse(m.fixture.qt.haze);self.assertFalse(m.fixture.qt.mirrors)
            self.assertTrue(all(set(command)=={'schemaVersion','commandId','action'} for command in m.features.commands))
            self.retire(scene,owner)
            self.assertFalse(owner.store.path.exists());self.assertEqual(3,len(m.destinations))

    def test_recreated_owner_keeps_original_native_barriers_and_repeated_ticket_has_no_input(self):
        m=self.model
        with m.lock.held():
            scene,owner=self.ready();call=self.call('open');owner.act(call);before=list(m.sdk.inputs)
            owner=m.preferences(scene);owner.act(call);self.assertEqual(before,m.sdk.inputs)
            owner.act(self.call('set-resolution',value=.5));owner=m.preferences(scene);owner.prepare()
            self.assertEqual(.65,owner.state['original']['graphics']['requestedResolutionScale']);self.retire(scene,owner)

    def test_finished_scene_setup_deadline_does_not_expire_a_later_owned_preference_action(self):
        m=self.model
        with m.lock.held():
            scene,owner=self.ready();m.sdk.clock+=60
            owner.act(self.call('open'));owner.act(self.call('set-resolution',value=.5));self.retire(scene,owner)

    def test_ignored_slider_stays_issued_and_a_retry_never_replays_the_scalar(self):
        m=self.model
        with m.lock.held():
            scene,owner=self.ready();owner.act(self.call('open'));m.fixture.qt.fault='resolution';call=self.call('set-resolution',value=.5)
            with self.assertRaises(NativeUIError):owner.act(call)
            before=list(m.fixture.qt.actions);owner=m.preferences(scene)
            with self.assertRaises(NativeUIError):owner.act(call)
            self.assertEqual(before,m.fixture.qt.actions);self.assertEqual('issued',owner.state['phase'])
            m.fixture.qt.fault='';self.retire(scene,owner)

    def test_widget_readback_cannot_hide_ignored_independent_native_preferences(self):
        m=self.model
        with m.lock.held():
            scene,owner=self.ready();owner.act(self.call('open'));m.frozen=deepcopy(owner.state['native']['graphics'])
            call=self.call('set-resolution',value=.5)
            with self.assertRaises(NativeUIError):owner.act(call)
            self.assertEqual(.5,m.fixture.qt.resolution);before=list(m.fixture.qt.actions)
            with self.assertRaises(NativeUIError):m.preferences(scene).act(call)
            self.assertEqual(before,m.fixture.qt.actions);m.frozen=None
            owner=m.preferences(scene);self.retire(scene,owner)

    def test_scalar_input_cannot_change_an_unrelated_original_preference(self):
        m=self.model
        with m.lock.held():
            scene,owner=self.ready();owner.act(self.call('open'));original=m.fixture.qt.activate
            def changed(*args,**kwargs):original(*args,**kwargs);m.native_fault='shadows'
            with patch.object(m.fixture.qt,'activate',side_effect=changed),self.assertRaises(NativeUIError):owner.act(self.call('set-haze',enabled=True))
            self.assertEqual('issued',owner.state['phase']);m.native_fault=None;self.retire(scene,owner)

    def test_ownership_callback_deadline_expires_before_the_first_sdk_input(self):
        m=self.model
        with m.lock.held():
            scene,owner=self.ready();before=list(m.sdk.inputs);original=owner.intent
            def late(*args,**kwargs):result=original(*args,**kwargs);m.sdk.clock+=31;return result
            with patch.object(owner,'intent',side_effect=late),self.assertRaises(NativeUIError):owner.act(self.call('open'))
            self.assertEqual(before,m.sdk.inputs);owner=m.preferences(scene);self.retire(scene,owner)

    def test_failed_original_ui_intent_write_prevents_the_first_sdk_input(self):
        m=self.model
        with m.lock.held():
            scene,owner=self.ready();before=list(m.sdk.inputs);original=owner.store.write
            def fail(value,previous):
                state=unpack(value['payload'])[0]
                if state['current'] is not None and state['current']['intents']:raise OSError('Synthetic lost input intent write')
                return original(value,previous)
            with patch.object(owner.store,'write',side_effect=fail),self.assertRaises(OSError):owner.act(self.call('open'))
            self.assertEqual(before,m.sdk.inputs);owner=m.preferences(scene);self.retire(scene,owner)

    def test_lost_scalar_return_recovers_through_fresh_originals_without_replay(self):
        m=self.model
        with m.lock.held():
            scene,owner=self.ready();owner.act(self.call('open'));call=self.call('set-resolution',value=.5)
            original=m.fixture.qt.set_value
            def lost(*args,**kwargs):original(*args,**kwargs);raise RuntimeError('Synthetic lost scalar return')
            with patch.object(m.fixture.qt,'set_value',side_effect=lost),self.assertRaises(RuntimeError):owner.act(call)
            before=list(m.fixture.qt.actions);owner=m.preferences(scene);owner.act(call)
            self.assertEqual(before,m.fixture.qt.actions);self.retire(scene,owner)

    def test_partial_restore_does_not_reapply_observed_or_uncertain_scalar_substeps(self):
        m=self.model
        with m.lock.held():
            scene,owner=self.ready();owner.act(self.call('open'));owner.act(self.call('set-resolution',value=.5))
            owner.act(self.call('set-haze',enabled=True));owner.act(self.call('set-mirrors',enabled=True));call=self.call('restore-original')
            original=m.fixture.qt.activate
            def lost(identifier,**kwargs):
                original(identifier,**kwargs)
                if identifier=='graphics.haze':raise RuntimeError('Synthetic lost Haze return')
            with patch.object(m.fixture.qt,'activate',side_effect=lost),self.assertRaises(RuntimeError):owner.act(call)
            resolution_count=m.fixture.qt.actions.count('resolution');haze_count=m.fixture.qt.actions.count('graphics.haze')
            owner=m.preferences(scene);owner.act(call)
            self.assertEqual(resolution_count,m.fixture.qt.actions.count('resolution'))
            self.assertEqual(haze_count,m.fixture.qt.actions.count('graphics.haze'));self.retire(scene,owner)

    def test_unrestorable_original_slider_grid_fails_before_preference_mutation(self):
        m=self.model;m.fixture.qt.resolution=.63
        with m.lock.held():
            scene,owner=self.ready();owner.act(self.call('open'));before=list(m.fixture.qt.actions)
            with self.assertRaises(NativeUIError):owner.act(self.call('set-haze',enabled=True))
            self.assertEqual(before,m.fixture.qt.actions);self.retire(scene,owner)

    def test_changed_native_birth_or_cursor_cannot_replace_persisted_originals(self):
        m=self.model
        with m.lock.held():
            scene,owner=self.ready();before=list(m.sdk.inputs)
            for fault in ('birth','cursor'):
                m.native_fault=fault;owner=m.preferences(scene)
                with self.assertRaises(NativeUIError):owner.act(self.call('open'))
                self.assertEqual(before,m.sdk.inputs)
            m.native_fault=None;owner=m.preferences(scene);self.retire(scene,owner)

    def test_conflicting_ticket_arguments_or_unimplemented_lifecycle_input_are_refused_before_input(self):
        m=self.model
        with m.lock.held():
            scene,owner=self.ready();call=self.call('open');owner.act(call);before=list(m.sdk.inputs)
            for changed in (call|dict(verb='close'),self.call('restart-app'),self.call('background-resume')):
                with self.assertRaises(NativeUIError):owner.act(changed)
            self.assertEqual(before,m.sdk.inputs);self.retire(scene,owner)

    def test_cleanup_reopens_owned_settings_restores_originals_and_is_actually_idempotent(self):
        m=self.model
        with m.lock.held():
            scene,owner=self.ready();owner.act(self.call('open'));owner.act(self.call('set-resolution',value=.5));owner.act(self.call('close'))
            owner.cleanup();before=list(m.sdk.inputs),list(m.fixture.qt.actions);owner=m.preferences(scene);owner.cleanup()
            self.assertEqual(before,(m.sdk.inputs,m.fixture.qt.actions));self.retire(scene,owner)

    def test_cleanup_ignored_restore_retains_journal_and_never_replays_its_issued_scalar(self):
        m=self.model
        with m.lock.held():
            scene,owner=self.ready();owner.act(self.call('open'));owner.act(self.call('set-resolution',value=.5));m.fixture.qt.fault='resolution'
            with self.assertRaises(NativeUIError):owner.cleanup()
            before=list(m.fixture.qt.actions);m.fixture.qt.fault='';owner=m.preferences(scene)
            with self.assertRaises(NativeUIError):owner.cleanup()
            self.assertEqual(before,m.fixture.qt.actions);self.assertTrue(owner.store.path.exists())

    def test_cleanup_lost_close_response_retires_only_from_fresh_actual_absence(self):
        m=self.model
        with m.lock.held():
            scene,owner=self.ready();owner.act(self.call('open'));m.sdk.lose='nav.close'
            with self.assertRaises(NativeUIError):owner.cleanup()
            before=list(m.sdk.inputs);m.sdk.lose='';owner=m.preferences(scene);owner.cleanup()
            self.assertEqual(before,m.sdk.inputs);self.retire(scene,owner)

    def test_failed_owner_write_prevents_first_settings_input(self):
        m=self.model
        with m.lock.held():
            scene,owner=self.ready();before=list(m.sdk.inputs)
            with patch.object(owner.store,'write',side_effect=OSError('Synthetic private storage failure')),self.assertRaises(OSError):owner.act(self.call('open'))
            self.assertEqual(before,m.sdk.inputs);owner=m.preferences(scene);self.retire(scene,owner)

    def test_ignored_journal_removal_does_not_qualify_retirement(self):
        m=self.model
        with m.lock.held():
            scene,owner=self.ready();owner.cleanup()
            with patch.object(owner.store,'discard',return_value=None),self.assertRaises(NativeUIError):owner.retire()
            self.assertTrue(owner.store.path.exists());self.retire(scene,owner)
