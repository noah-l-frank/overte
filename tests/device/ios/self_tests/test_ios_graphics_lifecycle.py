"""One-send iOS Graphics Home/activation and original OS/native recovery facts."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import nullcontext
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from feature_journeys.scenarios import VERSION
from ios.adapters.graphics_lifecycle import IOSGraphicsBackground
from ios.adapters.graphics_preferences import IOSGraphicsPreferences
from ios.adapters.graphics_runtime import IOSGraphicsRuntime
from ios.self_tests.test_ios_graphics_scene import SceneHarness,RUN
from self_tests.test_completed_frame_lease import BINDING


class BackgroundTests(SceneHarness,unittest.TestCase):
    def setUp(self):
        super().setUp();self.inputs=[];self.fault=''
        def status(_selector,binding):
            if binding!=BINDING or self.sdk.pid!=42:raise NativeUIError('Synthetic changed OS PID')
            return dict(binding=deepcopy(BINDING),foreground=self.sdk.foreground,running=True,appState=4 if self.sdk.foreground else 3)
        self.adapter._graphics_lifecycle_status=status
        self.adapter.existing_input_session=lambda _:nullcontext()
        def invoke(_selector,operation,values):
            self.assertIsNone(base._operation)
            self.assertEqual({},values);self.inputs.append(operation)
            if operation=='lifecycle.background':
                if self.fault!='ignored-home':self.sdk.foreground=False;self.sdk.native_lifecycle['backgrounds']+=1
            else:
                self.assertEqual('app.launch',operation)
                if self.fault!='ignored-activation':self.sdk.foreground=True;self.sdk.native_lifecycle['activations']+=1
                if self.fault=='restart':self.sdk.native_lifecycle['launches']+=1
                if self.fault=='native-counters':self.sdk.native_lifecycle.update(backgrounds=0,activations=1)
            if self.fault==('lost-home' if operation=='lifecycle.background' else 'lost-activation'):
                raise OSError('Synthetic lost ordinary lifecycle return')
            return {'backgrounded':True} if operation=='lifecycle.background' else {'launched':True}
        base=SimpleNamespace(_operation='feature.graphics.act',invoke=invoke)
        runtime=object.__new__(IOSGraphicsRuntime);runtime.adapter=base
        runtime.state_path=self.adapter.state_path;runtime._graphics_lifecycle_status=status
        self.adapter.invoke=runtime.invoke;self.lifecycle_base=base
    def prepare(self):
        scene=self.scene();scene.prepare();prefs=IOSGraphicsPreferences(scene,monotonic=lambda:self.sdk.clock,sleep=self.sdk.sleep)
        prefs.prepare();return IOSGraphicsBackground(prefs,monotonic=lambda:self.sdk.clock,sleep=self.sdk.sleep)
    def recover(self):return IOSGraphicsBackground.recover(self.adapter,'owned',self.client,RUN,self.lock,
        monotonic=lambda:self.sdk.clock,sleep=self.sdk.sleep)
    def call(self):return dict(contractVersion=VERSION,runId=RUN,ticket='2'*32,verb='background-resume',inputs={},
                              fixtureUrl=self.client.url+'/runs/'+RUN+'/')

    def test_normal_background_resume_requires_os_transition_native_counters_and_unchanged_preferences(self):
        with self.lock.held():
            owner=self.prepare();before=deepcopy(owner.preferences.state['native']['graphics'])
            self.assertEqual({'performed':True},owner.act(self.call()));self.assertEqual('observed',owner.state['phase'])
            self.assertEqual(before,owner.state['after']['graphics']);self.assertEqual(1,owner.state['after']['lifecycle']['backgrounds'])
            self.assertEqual(['lifecycle.background','app.launch'],self.inputs)
            self.recover().act(self.call());self.assertEqual(2,len(self.inputs));self.recover().retire()
            self.assertEqual('feature.graphics.act',self.lifecycle_base._operation)

    def test_lost_home_return_recovers_from_archives_while_backgrounded_without_native_ui_reads(self):
        self.fault='lost-home'
        with self.lock.held():
            owner=self.prepare()
            with self.assertRaises(OSError):owner.act(self.call())
            self.assertFalse(self.sdk.foreground);count=len(self.sdk.core.commands)
            recovery=self.recover();self.assertEqual(count,len(self.sdk.core.commands))
            self.fault='';recovery.act(self.call());self.assertTrue(self.sdk.foreground)
            self.assertEqual(['lifecycle.background','app.launch'],self.inputs)

    def test_lost_activation_return_is_read_without_repeating_activation(self):
        self.fault='lost-activation'
        with self.lock.held():
            owner=self.prepare()
            with self.assertRaises(OSError):owner.act(self.call())
            self.assertTrue(self.sdk.foreground);self.fault='';self.recover().act(self.call())
            self.assertEqual(['lifecycle.background','app.launch'],self.inputs)

    def test_ignored_home_never_activates_or_replays_home_after_reconstruction(self):
        self.fault='ignored-home'
        with self.lock.held():
            owner=self.prepare()
            with self.assertRaises(NativeUIError):owner.act(self.call())
            with self.assertRaises(NativeUIError):self.recover().act(self.call())
            self.assertEqual(['lifecycle.background'],self.inputs)

    def test_ignored_activation_never_replays_and_cannot_be_a_successful_resume(self):
        self.fault='ignored-activation'
        with self.lock.held():
            owner=self.prepare()
            with self.assertRaises(NativeUIError):owner.act(self.call())
            with self.assertRaises(NativeUIError):self.recover().act(self.call())
            self.assertEqual(['lifecycle.background','app.launch'],self.inputs);self.assertFalse(self.sdk.foreground)

    def test_new_launch_counter_is_not_background_resume(self):
        self.fault='restart'
        with self.lock.held():
            owner=self.prepare()
            with self.assertRaises(NativeUIError):owner.act(self.call())
            self.assertEqual('foreground-issued',owner.state['phase'])

    def test_os_foreground_and_input_ack_without_native_transitions_are_not_a_resume(self):
        self.fault='native-counters'
        with self.lock.held():
            owner=self.prepare()
            with self.assertRaises(NativeUIError):owner.act(self.call())
            self.assertTrue(self.sdk.foreground);self.assertEqual('foreground-issued',owner.state['phase'])

    def test_failed_durable_intent_or_changed_os_pid_prevents_background_input(self):
        with self.lock.held():
            owner=self.prepare()
            with patch.object(owner.store,'write',side_effect=OSError('Synthetic failed lifecycle intent')),self.assertRaises(OSError):owner.act(self.call())
            self.assertEqual([],self.inputs)
            owner=self.recover();self.sdk.pid=43
            with self.assertRaises(NativeUIError):owner.act(self.call())
            self.assertEqual([],self.inputs)


class LifecycleRuntimeTests(unittest.TestCase):
    def test_os_status_uses_original_pid_app_state_and_same_candidate_scope_around_read(self):
        runtime=object.__new__(IOSGraphicsRuntime);scope={k:v for k,v in BINDING.items() if k!='processIdentity'}
        process=dict(bundleId='org.example.client',pid=42,foreground=False);calls=[]
        def continuity(**options):calls.append(options);return deepcopy(process)
        runtime._existing=lambda _: (None,'owned-session',{},dict(appId='org.example.client'),scope)
        runtime.adapter=SimpleNamespace(_binding=lambda *_:SimpleNamespace(continuity=continuity),_scope=lambda *_:scope,
                                       query_app_state=lambda *_:3)
        value=runtime._graphics_lifecycle_status('owned',BINDING)
        self.assertFalse(value['foreground']);self.assertEqual(3,value['appState']);self.assertEqual(BINDING,value['binding'])
        self.assertEqual([dict(allow_background=True)]*2,calls)
        runtime.adapter.query_app_state=lambda *_:4
        with self.assertRaises(NativeUIError):runtime._graphics_lifecycle_status('owned',BINDING)
        runtime.adapter.query_app_state=lambda *_:True
        with self.assertRaises(NativeUIError):runtime._graphics_lifecycle_status('owned',BINDING)
        def replaced(*_):process['pid']=43;return 3
        runtime.adapter.query_app_state=replaced
        with self.assertRaises(NativeUIError):runtime._graphics_lifecycle_status('owned',BINDING)


if __name__=='__main__':unittest.main()
