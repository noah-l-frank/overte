"""Ordinary lifecycle transactions with actual owners and synthetic OS/native IO."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
from types import SimpleNamespace
import hashlib
import unittest
import uuid
from adapters.graphics_journey.lifecycle import GraphicsBackground
from adapters.normal_ui import NativeUIError
from adapters.pico4.graphics_binding import PicoGraphicsBinding
from self_tests.test_pico_graphics_preferences import Model as Base,RUN


class Model(Base):
    def __init__(self):
        super().__init__();self.foreground=True;self.backgrounds=0;self.activations=1;self.launches=1
        self.events=[];self.lifecycle_fault=None;self.status_fault=None;self.while_background=[]
    def original_native(self,packet):
        super().original_native(packet)
        packet['lifecycle'].update(backgrounds=self.backgrounds,activations=self.activations,launches=self.launches)
    def normal_feature_runtime(self,*args,**options):
        if not self.foreground:self.while_background.append('native-runtime');raise NativeUIError('Synthetic foreground source unavailable')
        return super().normal_feature_runtime(*args,**options)
    def _graphics_lifecycle_status(self,_target,binding):
        self.native.guard()
        if self.status_fault:raise NativeUIError('Synthetic OS/candidate unavailable')
        return dict(binding=deepcopy(binding),running=True,foreground=self.foreground)
    @contextmanager
    def existing_input_session(self,_target):
        self.native.guard()
        try:yield
        finally:self.native.guard()
    def invoke(self,_target,operation,values):
        assert values=={};self.events.append(operation)
        if operation=='lifecycle.background':
            if self.lifecycle_fault=='ignored-home':return dict(backgrounded=True)
            self.foreground=False;self.backgrounds+=1
            if self.lifecycle_fault=='lost-home':raise OSError('Synthetic lost applied Home reply')
        elif operation=='app.launch':
            if self.lifecycle_fault=='ignored-launch':return dict(launched=True)
            self.foreground=True;self.activations+=1
            if self.lifecycle_fault=='restarted':self.launches+=1
            if self.lifecycle_fault=='settings':self.native.graph.haze=not self.native.graph.haze
            if self.lifecycle_fault=='lost-launch':raise OSError('Synthetic lost applied activation reply')
        else:raise AssertionError('Unexpected lifecycle input')
        return dict(performed=True)
    def _graphics_lifecycle_input(self,target,operation,binding):
        self._graphics_lifecycle_status(target,binding)
        return self.invoke(target,operation,{})
    def background(self,preferences):return GraphicsBackground(preferences,monotonic=lambda:self.native.clock,sleep=self.native.sleep)
    def recover(self):return GraphicsBackground.recover(self,'owned',self.client,RUN,self.lock,
        monotonic=lambda:self.native.clock,sleep=self.native.sleep)


class PicoGraphicsBackgroundTests(unittest.TestCase):
    def setUp(self):self.model=Model();self.addCleanup(self.model.close);self.enterContext(self.model.lock.held())
    def ready(self):
        scene=self.model.factory();scene.prepare();preferences=self.model.preferences(scene);preferences.prepare()
        call=dict(contractVersion=16,runId=RUN,fixtureUrl=self.model.client.url+'/runs/'+RUN+'/',ticket=uuid.uuid4().hex,verb='background-resume',inputs={})
        return scene,preferences,call

    def test_normal_background_and_activation_preserve_process_settings_and_actual_lifecycle_counters(self):
        m=self.model;scene,preferences,call=self.ready();owner=m.background(preferences)
        self.assertEqual(dict(performed=True),owner.act(call));self.assertEqual(['lifecycle.background','app.launch'],m.events)
        self.assertEqual(1,owner.state['after']['lifecycle']['backgrounds']);self.assertEqual(2,owner.state['after']['lifecycle']['activations'])
        self.assertEqual(1,owner.state['after']['lifecycle']['launches']);self.assertEqual([],m.while_background)
        owner=m.recover();owner.act(call);self.assertEqual(2,len(m.events));owner.retire();self.assertIsNone(owner.store.read())
        owner.preferences.cleanup();scene=m.factory();scene.restore();scene.retire()

    def test_lost_applied_home_reconstructs_from_original_archives_before_any_foreground_native_read(self):
        m=self.model;scene,preferences,call=self.ready();owner=m.background(preferences);m.lifecycle_fault='lost-home'
        with self.assertRaises(OSError):owner.act(call)
        self.assertFalse(m.foreground);self.assertEqual('background-issued',owner.state['phase'])
        with self.assertRaises(NativeUIError):m.factory()
        m.while_background.clear();m.lifecycle_fault=None
        recovered=m.recover();self.assertIsNone(recovered.scene);self.assertIsNone(recovered.preferences)
        self.assertEqual(dict(performed=True),recovered.act(call))
        self.assertEqual(['lifecycle.background','app.launch'],m.events);self.assertEqual([],m.while_background)

    def test_lost_applied_activation_is_observed_without_redelivery(self):
        m=self.model;_scene,preferences,call=self.ready();owner=m.background(preferences);m.lifecycle_fault='lost-launch'
        with self.assertRaises(OSError):owner.act(call)
        self.assertTrue(m.foreground);self.assertEqual('foreground-issued',owner.state['phase'])
        m.lifecycle_fault=None;m.recover().act(call);self.assertEqual(['lifecycle.background','app.launch'],m.events)

    def test_ignored_home_or_activation_keeps_issued_ownership_and_is_never_replayed(self):
        for fault in ('ignored-home','ignored-launch'):
            m=Model();self.addCleanup(m.close)
            with m.lock.held():
                scene=m.factory();scene.prepare();preferences=m.preferences(scene);preferences.prepare()
                call=dict(contractVersion=16,runId=RUN,fixtureUrl=m.client.url+'/runs/'+RUN+'/',ticket=uuid.uuid4().hex,verb='background-resume',inputs={})
                owner=m.background(preferences);m.lifecycle_fault=fault
                with self.assertRaises(NativeUIError):owner.act(call)
                before=list(m.events)
                with self.assertRaises(NativeUIError):m.recover().act(call)
                self.assertEqual(before,m.events);self.assertNotEqual('observed',owner.state['phase'])

    def test_unexpected_restart_setting_change_or_unavailable_status_cannot_qualify_success(self):
        for fault in ('settings','restarted'):
            m=Model();self.addCleanup(m.close)
            with self.subTest(fault=fault),m.lock.held():
                scene=m.factory();scene.prepare();preferences=m.preferences(scene);preferences.prepare()
                call=dict(contractVersion=16,runId=RUN,fixtureUrl=m.client.url+'/runs/'+RUN+'/',ticket=uuid.uuid4().hex,verb='background-resume',inputs={})
                m.lifecycle_fault=fault;owner=m.background(preferences)
                with self.assertRaises(NativeUIError):owner.act(call)
                before=list(m.events);m.status_fault=True
                with self.assertRaises(NativeUIError):m.recover().act(call)
                self.assertEqual(before,m.events)

    def test_archived_lifecycle_remains_original_and_changed_owner_files_prevent_recovery_dispatch(self):
        m=self.model;scene,preferences,call=self.ready();owner=m.background(preferences);owner.act(call)
        before=list(m.events);archived=GraphicsBackground.archive(owner.previous,scene=scene)
        self.assertEqual(owner.state,archived);self.assertEqual(before,m.events)
        recovered=m.recover();old=preferences.store.read();changed=deepcopy(old);changed['fixtureUrl']+='foreign'
        preferences.store.write(changed,old)
        with self.assertRaises(NativeUIError):recovered.act(call)
        self.assertEqual(before,m.events)


class PicoGraphicsLifecycleBindingTests(unittest.TestCase):
    def boundary(self):
        configuration=('synthetic-profile','/private/synthetic')
        binding=dict(sourceRevision='a'*40,artifactSha256='b'*64,processIdentity='31:1234',sessionId='owned-bridge',generation=0,
            targetFingerprint=hashlib.sha256(('owned\0'+str(configuration)).encode()).hexdigest())
        state=dict(running=True,identity='31:1234');foreground=['com.picovr.home'];installed=dict(sourceRevision='a'*40,artifactSha256='b'*64)
        original=SimpleNamespace(pico_configuration=configuration,_installation=lambda _target:deepcopy(installed),
            require_pico_session_identity=lambda _target:state['identity'],adb=SimpleNamespace(
                process_state=lambda _target,_package:deepcopy(state),foreground_package=lambda _target:foreground[0]))
        return PicoGraphicsBinding(original),binding,state,foreground,installed
    def test_existing_kernel_identity_and_actual_foreground_are_read_without_an_app_state_substitute(self):
        flow,binding,_state,foreground,_installed=self.boundary()
        value=flow._graphics_lifecycle_status('owned',binding);self.assertFalse(value['foreground']);self.assertNotIn('appState',value)
        foreground[0]='org.overte.pico';self.assertTrue(flow._graphics_lifecycle_status('owned',binding)['foreground'])
    def test_missing_foreground_replaced_process_or_candidate_are_not_treated_as_background(self):
        for fault in ('foreground','process','candidate'):
            flow,binding,state,foreground,installed=self.boundary()
            if fault=='foreground':foreground[0]=''
            elif fault=='process':state['identity']='32:5678'
            else:installed['artifactSha256']='d'*64
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):flow._graphics_lifecycle_status('owned',binding)

    def test_normal_bound_activation_does_not_bootstrap_a_missing_controlled_process(self):
        flow,binding,state,_foreground,_installed=self.boundary();events=[]
        flow.original.require_controlled_debug_identity=lambda _target:state['identity']
        flow.original.invoke=lambda target,operation,values:events.append((operation,values))
        flow._graphics_lifecycle_input('owned','app.launch',binding);self.assertEqual([('app.launch',{})],events)
        flow.original.require_controlled_debug_identity=lambda _target:None
        with self.assertRaises(NativeUIError):flow._graphics_lifecycle_input('owned','app.launch',binding)
        self.assertEqual(1,len(events))

    def test_process_replacement_during_foreground_query_prevents_any_lifecycle_dispatch(self):
        flow,binding,state,_foreground,_installed=self.boundary();events=[]
        def foreground(_target):state['identity']='32:5678';return 'org.overte.pico'
        flow.original.adb.foreground_package=foreground
        flow.original.invoke=lambda *args:events.append(args)
        with self.assertRaises(NativeUIError):flow._graphics_lifecycle_input('owned','app.launch',binding)
        self.assertEqual([],events)


if __name__=='__main__':unittest.main()
