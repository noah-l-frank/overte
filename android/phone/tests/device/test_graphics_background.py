"""Normal fake Home/activation, actual private intent and independent source states."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
import sys
import unittest
import uuid
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'tests/device'))
sys.path.insert(0,str(ROOT/'tests/device/adapters/android-phone'))
from adapters.normal_ui import NativeUIError
from overte_phone_graphics_lifecycle import PhoneGraphicsBackground
import test_graphics_preferences as preferences_fixture


class Model(preferences_fixture.Model):
    def __init__(self):
        super().__init__();self.foreground=True;self.lifecycle=dict(backgrounds=0,activations=1,launches=1)
        self.normal_inputs=[];self.ignore='';self.lose='';self.no_native_change=False;self.foreign_status=False;self.status_unavailable=False
    def original_native(self,value):
        super().original_native(value);value['lifecycle']=deepcopy(self.lifecycle)
    def normal_feature_runtime(self,selector,*,read_only):
        if not self.foreground:raise NativeUIError('Synthetic original native source is unavailable in background')
        ui,observer,binding,_guard,installed=super().normal_feature_runtime(selector,read_only=read_only)
        return ui,observer,binding,lambda:self.native.okay and self.foreground,installed
    @contextmanager
    def existing_input_session(self,_selector):yield
    def _graphics_lifecycle_status(self,_selector,binding):
        if self.status_unavailable:raise NativeUIError('Synthetic original OS status unavailable')
        result=dict(binding=deepcopy(binding),foreground=self.foreground,running=True,appState=4 if self.foreground else 3)
        if self.foreign_status:result['binding']['processIdentity']='32:19'
        return result
    def invoke(self,_selector,operation,values):
        assert values=={};self.normal_inputs.append(operation)
        if operation!=self.ignore:
            if operation=='lifecycle.background':
                self.foreground=False
                if not self.no_native_change:self.lifecycle['backgrounds']+=1
            elif operation=='app.launch':
                self.foreground=True
                if not self.no_native_change:self.lifecycle['activations']+=1
            else:raise AssertionError('Unexpected synthetic normal lifecycle input')
        if self.lose==operation:raise RuntimeError('Synthetic lost lifecycle input response')
        return {'backgrounded':True} if operation=='lifecycle.background' else {'launched':True}
    def background(self,preferences):
        return PhoneGraphicsBackground(preferences,monotonic=lambda:self.sdk.clock,sleep=self.fixture.sleep)


class GraphicsBackgroundTests(unittest.TestCase):
    def setUp(self):self.model=Model();self.addCleanup(self.model.close)
    def call(self):
        return dict(contractVersion=16,runId=preferences_fixture.RUN,ticket=uuid.uuid4().hex,
            fixtureUrl=self.model.client.url+'/runs/'+preferences_fixture.RUN+'/',verb='background-resume',inputs={})
    def ready(self):
        m=self.model;scene=m.factory();scene.prepare();preferences=m.preferences(scene);preferences.prepare()
        return scene,preferences,m.background(preferences)
    def retire(self,scene,preferences,background):
        preferences.cleanup();background.retire();preferences.retire();scene.restore();scene.retire()

    def test_normal_background_and_activation_require_original_os_and_native_persistence(self):
        m=self.model
        with m.lock.held():
            scene,preferences,background=self.ready();m.sdk.clock+=60
            call=self.call();before=deepcopy(preferences.state['native']['graphics'])
            self.assertEqual({'performed':True},background.act(call))
            self.assertEqual(['lifecycle.background','app.launch'],m.normal_inputs)
            self.assertEqual(before,background.state['after']['graphics'])
            self.assertEqual(dict(backgrounds=1,activations=2,launches=1),background.state['after']['lifecycle'])
            self.assertFalse(background.state['background']['foreground']);self.retire(scene,preferences,background)

    def test_ignored_background_cannot_become_success_or_receive_a_second_home_input(self):
        m=self.model;m.ignore='lifecycle.background'
        with m.lock.held():
            _scene,preferences,background=self.ready();call=self.call()
            with self.assertRaises(NativeUIError):background.act(call)
            m.ignore='';background=m.background(preferences)
            with self.assertRaises(NativeUIError):background.act(call)
            self.assertEqual(['lifecycle.background'],m.normal_inputs);self.assertTrue(background.store.path.exists())

    def test_lost_background_response_resumes_only_from_actual_background_without_replaying_home(self):
        m=self.model;m.lose='lifecycle.background'
        with m.lock.held():
            scene,preferences,background=self.ready();call=self.call()
            with self.assertRaises(RuntimeError):background.act(call)
            self.assertFalse(m.foreground);m.lose='';background=m.background(preferences);background.act(call)
            self.assertEqual(['lifecycle.background','app.launch'],m.normal_inputs);self.retire(scene,preferences,background)

    def test_lost_activation_response_uses_fresh_native_results_without_second_activation(self):
        m=self.model;m.lose='app.launch'
        with m.lock.held():
            scene,preferences,background=self.ready();call=self.call()
            with self.assertRaises(RuntimeError):background.act(call)
            self.assertTrue(m.foreground);m.lose='';background=m.background(preferences);background.act(call)
            self.assertEqual(['lifecycle.background','app.launch'],m.normal_inputs);self.retire(scene,preferences,background)

    def test_os_success_without_native_lifecycle_changes_remains_failed(self):
        m=self.model;m.no_native_change=True
        with m.lock.held():
            _scene,preferences,background=self.ready();call=self.call()
            with self.assertRaises(NativeUIError):background.act(call)
            with self.assertRaises(NativeUIError):m.background(preferences).act(call)
            self.assertEqual(['lifecycle.background','app.launch'],m.normal_inputs)
            with self.assertRaises(NativeUIError):background.retire()

    def test_ignored_activation_keeps_owned_background_and_does_not_repeat_activation(self):
        m=self.model;m.ignore='app.launch'
        with m.lock.held():
            _scene,preferences,background=self.ready();call=self.call()
            with self.assertRaises(NativeUIError):background.act(call)
            m.ignore=''
            with self.assertRaises(NativeUIError):m.background(preferences).act(call)
            self.assertFalse(m.foreground);self.assertEqual(['lifecycle.background','app.launch'],m.normal_inputs)

    def test_foreign_process_status_prevents_activation_and_preserves_intent(self):
        m=self.model;m.lose='lifecycle.background'
        with m.lock.held():
            _scene,preferences,background=self.ready();call=self.call()
            with self.assertRaises(RuntimeError):background.act(call)
            m.lose='';m.foreign_status=True
            with self.assertRaises(NativeUIError):m.background(preferences).act(call)
            self.assertEqual(['lifecycle.background'],m.normal_inputs)

    def test_missing_os_result_stays_owned_and_cannot_synthesize_background_success(self):
        m=self.model;m.lose='lifecycle.background'
        with m.lock.held():
            scene,preferences,background=self.ready();call=self.call()
            with self.assertRaises(RuntimeError):background.act(call)
            m.lose='';m.status_unavailable=True
            with self.assertRaises(NativeUIError):m.background(preferences).act(call)
            self.assertEqual(['lifecycle.background'],m.normal_inputs)
            m.status_unavailable=False;background=m.background(preferences);background.act(call);self.retire(scene,preferences,background)

    def test_foreign_open_owned_ui_requires_ordinary_close_before_background(self):
        m=self.model
        with m.lock.held():
            scene,preferences,background=self.ready();preferences.act(dict(self.call(),verb='open'))
            with self.assertRaises(NativeUIError):background.act(self.call())
            self.assertEqual([],m.normal_inputs);self.assertFalse(background.store.path.exists())
            preferences.cleanup();preferences.retire();scene.restore();scene.retire()

    def test_repeated_ticket_reacquires_original_proof_without_input_and_refuses_different_ticket(self):
        m=self.model
        with m.lock.held():
            scene,preferences,background=self.ready();call=self.call();background.act(call);before=background.state['after']['sequence']
            background=m.background(preferences);background.act(call)
            self.assertGreater(background.state['after']['sequence'],before)
            with self.assertRaises(NativeUIError):background.act(self.call())
            self.assertEqual(['lifecycle.background','app.launch'],m.normal_inputs);self.retire(scene,preferences,background)

    def test_input_intent_write_failure_prevents_home_input(self):
        m=self.model
        with m.lock.held():
            _scene,_preferences,background=self.ready()
            with patch.object(background.store,'write',side_effect=OSError('Synthetic lost private intent')),self.assertRaises(OSError):background.act(self.call())
            self.assertEqual([],m.normal_inputs);self.assertFalse(background.store.path.exists())

    def test_foreign_preference_mutation_during_resume_is_not_persistence(self):
        m=self.model
        with m.lock.held():
            _scene,_preferences,background=self.ready();base=m.invoke
            def changed(*args):
                value=base(*args)
                if args[1]=='app.launch':m.fixture.qt.resolution=.5
                return value
            with patch.object(m,'invoke',side_effect=changed),self.assertRaises(NativeUIError):background.act(self.call())
            self.assertEqual('foreground-issued',background.state['phase'])

    def test_ignored_journal_removal_cannot_qualify_completed_retirement(self):
        m=self.model
        with m.lock.held():
            scene,preferences,background=self.ready();background.act(self.call());preferences.cleanup()
            with patch.object(background.store,'discard',return_value=None),self.assertRaises(NativeUIError):background.retire()
            self.assertTrue(background.store.path.exists());self.retire(scene,preferences,background)

    def test_completed_background_metadata_can_retire_before_restart_without_resetting_preferences(self):
        m=self.model
        with m.lock.held():
            scene,preferences,background=self.ready()
            preferences.act(dict(self.call(),verb='open'))
            preferences.act(dict(self.call(),verb='set-resolution',inputs=dict(value=.5)))
            preferences.act(dict(self.call(),verb='close'));background.act(self.call());background.retire()
            self.assertEqual(.5,m.fixture.qt.resolution);self.assertFalse(background.store.path.exists())
            preferences.cleanup();preferences.retire();scene.restore();scene.retire()
