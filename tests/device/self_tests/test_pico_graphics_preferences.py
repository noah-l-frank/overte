"""Ordinary Pico settings, real durable owners, synthetic independent natives."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
import uuid
from unittest.mock import patch
from adapters.graphics_journey.preferences import GraphicsPreferences
from adapters.native_feature_observation import NativeFeatureObservation
from adapters.normal_ui import NativeUIError
from adapters.script_journey.history import unpack
from self_tests.test_native_feature_observation import Boundary as FeatureBoundary
from self_tests.test_pico_graphics_scene import Model as SceneModel,RUN


class Model(SceneModel):
    def __init__(self):
        super().__init__();self.features=FeatureBoundary();self.frozen=None;self.native_fault=None
        self.features.mutate=self.original_native
    def original_native(self,packet):
        def epoch(value):
            if type(value) is dict:
                for key,item in value.items():
                    if key.endswith('EpochMs') and type(item) is int:value[key]=self.native.epoch
                    else:epoch(item)
        epoch(packet);packet['processId']=31;qt=self.native.graph
        packet['graphics'].update(requestedResolutionScale=qt.resolution,applicationResolutionScale=qt.resolution,
            hazeSetting=qt.haze,mirrorsSetting=qt.mirrors)
        if self.frozen is not None:packet['graphics']=deepcopy(self.frozen)
        if self.native_fault=='birth':packet['instance']='f'*32
        if self.native_fault=='cursor':packet['sequence']=1
        if self.native_fault=='unrelated':packet['graphics']['shadowsSetting']=True
    def _native_feature_observer(self,_target,*,read_only):
        assert read_only
        return NativeFeatureObservation(self.features.send,self.features.original,lambda:self.native.epoch,self.native.guard,31,
            monotonic=lambda:self.native.clock,sleep=self.native.sleep)
    def preferences(self,scene):return GraphicsPreferences(scene,monotonic=lambda:self.native.clock,sleep=self.native.sleep)


class PicoGraphicsPreferenceTests(unittest.TestCase):
    def setUp(self):self.model=Model();self.addCleanup(self.model.close)
    def call(self,verb,**inputs):
        return dict(contractVersion=16,runId=RUN,ticket=uuid.uuid4().hex,fixtureUrl=self.model.client.url+'/runs/'+RUN+'/',verb=verb,inputs=inputs)
    def ready(self):
        m=self.model;scene=m.factory();scene.prepare();owner=m.preferences(scene);owner.prepare();return scene,owner
    def retire(self,scene,owner):owner.cleanup();owner.retire();scene.restore();scene.retire()

    def test_ordinary_generic_settings_and_native_barriers_restore_actual_original(self):
        m=self.model
        with m.lock.held():
            scene,owner=self.ready();self.assertEqual(.6,owner.state['original']['graphics']['requestedResolutionScale'])
            for call in (self.call('open'),self.call('set-resolution',value=.5),self.call('set-haze',enabled=True),
                    self.call('set-mirrors',enabled=True),self.call('close'),self.call('open'),self.call('restore-original'),self.call('close')):
                self.assertEqual({'performed':True},owner.act(call))
            self.assertEqual(.6,m.native.graph.resolution);self.assertFalse(m.native.graph.haze);self.assertFalse(m.native.graph.mirrors)
            self.retire(scene,owner);self.assertFalse(owner.store.path.exists());self.assertEqual(3,len(m.destinations))
        self.assertTrue(all(set(command)=={'schemaVersion','commandId','action'} for command in m.features.commands))
        self.assertIn('tablet.home-ray',m.native.events)

    def test_original_off_grid_preference_is_rejected_before_any_preference_input(self):
        m=self.model
        with m.lock.held():
            scene=m.factory();scene.prepare();m.native.graph.resolution=.65;before=list(m.native.inputs)
            owner=m.preferences(scene)
            with self.assertRaises(NativeUIError):owner.prepare()
            self.assertEqual(before,m.native.inputs);self.assertIsNone(owner.store.read());scene.restore();scene.retire()

    def test_recreated_owner_pins_originals_and_repeated_ticket_sends_no_more_input(self):
        m=self.model
        with m.lock.held():
            scene,owner=self.ready();call=self.call('open');owner.act(call);before=list(m.native.inputs)
            owner=m.preferences(scene);owner.act(call);self.assertEqual(before,m.native.inputs)
            owner.act(self.call('set-resolution',value=.5));owner=m.preferences(scene);owner.prepare()
            self.assertEqual(.6,owner.state['original']['graphics']['requestedResolutionScale']);self.retire(scene,owner)

    def test_ignored_slider_stays_issued_after_recreation_and_is_never_resent(self):
        m=self.model
        with m.lock.held():
            scene,owner=self.ready();owner.act(self.call('open'));m.native.graph.fault='resolution';call=self.call('set-resolution',value=.5)
            with self.assertRaises(NativeUIError):owner.act(call)
            before=list(m.native.graph.actions);owner=m.preferences(scene)
            with self.assertRaises(NativeUIError):owner.act(call)
            self.assertEqual(before,m.native.graph.actions);self.assertEqual('issued',owner.state['phase'])
            m.native.graph.fault='';self.retire(scene,owner)

    def test_widget_readback_cannot_replace_independent_actual_native_settings(self):
        m=self.model
        with m.lock.held():
            scene,owner=self.ready();owner.act(self.call('open'));m.frozen=deepcopy(owner.state['native']['graphics'])
            call=self.call('set-resolution',value=.5)
            with self.assertRaises(NativeUIError):owner.act(call)
            self.assertEqual(.5,m.native.graph.resolution);before=list(m.native.graph.actions)
            with self.assertRaises(NativeUIError):m.preferences(scene).act(call)
            self.assertEqual(before,m.native.graph.actions);m.frozen=None;self.retire(scene,m.preferences(scene))

    def test_lost_applied_scalar_return_recovers_only_through_fresh_originals(self):
        m=self.model
        with m.lock.held():
            scene,owner=self.ready();owner.act(self.call('open'));call=self.call('set-resolution',value=.5);original=m.native.graph.set_value
            def lost(*args,**kwargs):original(*args,**kwargs);raise RuntimeError('Synthetic lost applied scalar receipt')
            with patch.object(m.native.graph,'set_value',side_effect=lost),self.assertRaises(RuntimeError):owner.act(call)
            before=list(m.native.graph.actions);owner=m.preferences(scene);owner.act(call)
            self.assertEqual(before,m.native.graph.actions);self.retire(scene,owner)

    def test_unrelated_native_setting_change_blocks_acknowledgment(self):
        m=self.model
        with m.lock.held():
            scene,owner=self.ready();owner.act(self.call('open'));original=m.native.graph.activate
            def unrelated(*args,**kwargs):original(*args,**kwargs);m.native_fault='unrelated'
            with patch.object(m.native.graph,'activate',side_effect=unrelated),self.assertRaises(NativeUIError):owner.act(self.call('set-haze',enabled=True))
            self.assertEqual('issued',owner.state['phase']);m.native_fault=None;self.retire(scene,owner)

    def test_failed_pre_input_durable_write_prevents_normal_input(self):
        m=self.model
        with m.lock.held():
            scene,owner=self.ready();before=list(m.native.inputs);write=owner.store.write
            def fail(value,previous):
                current=unpack(value['payload'])[0]['current']
                if current is not None and current['intents']:raise OSError('Synthetic failed intent write')
                return write(value,previous)
            with patch.object(owner.store,'write',side_effect=fail),self.assertRaises(OSError):owner.act(self.call('open'))
            self.assertEqual(before,m.native.inputs);self.retire(scene,m.preferences(scene))

    def test_source_birth_change_or_cursor_replay_keeps_owned_intent(self):
        for fault in ('birth','cursor'):
            m=self.model if fault=='birth' else Model()
            if fault!='birth':self.addCleanup(m.close)
            with self.subTest(fault=fault),m.lock.held():
                scene=m.factory();scene.prepare();owner=m.preferences(scene);owner.prepare();before=list(m.native.inputs);m.native_fault=fault
                call=dict(contractVersion=16,runId=RUN,ticket=uuid.uuid4().hex,fixtureUrl=m.client.url+'/runs/'+RUN+'/',verb='open',inputs={})
                with self.assertRaises(NativeUIError):owner.act(call)
                self.assertEqual(before,m.native.inputs);self.assertTrue(owner.store.path.exists())

    def test_elapsed_setup_does_not_expire_later_operation_but_late_intent_blocks_input(self):
        m=self.model
        with m.lock.held():
            scene,owner=self.ready();m.native.clock+=60;before=list(m.native.inputs);intent=owner.intent
            def late(*args,**kwargs):value=intent(*args,**kwargs);m.native.clock+=31;return value
            with patch.object(owner,'intent',side_effect=late),self.assertRaises(NativeUIError):owner.act(self.call('open'))
            self.assertEqual(before,m.native.inputs);self.retire(scene,m.preferences(scene))

    def test_partial_cleanup_rechecks_uncertain_applied_scalar_without_resending_it(self):
        m=self.model
        with m.lock.held():
            scene,owner=self.ready();owner.act(self.call('open'));owner.act(self.call('set-resolution',value=.5))
            owner.act(self.call('set-haze',enabled=True));owner.act(self.call('set-mirrors',enabled=True))
            original=m.native.graph.set_value
            def lost(*args,**kwargs):original(*args,**kwargs);raise RuntimeError('Synthetic lost original restoration receipt')
            with patch.object(m.native.graph,'set_value',side_effect=lost),self.assertRaises(RuntimeError):owner.cleanup()
            count=m.native.graph.actions.count('resolution');owner=m.preferences(scene);owner.cleanup()
            self.assertEqual(count,m.native.graph.actions.count('resolution'));self.assertEqual(.6,m.native.graph.resolution)
            self.assertFalse(m.native.graph.haze);self.assertFalse(m.native.graph.mirrors);self.retire(scene,owner)

    def test_cold_ui_history_restore_keeps_actual_retained_roots_without_another_read(self):
        from adapters.graphics_journey.source_history import restore_ui
        from adapters.pico4.graphics_source import validate
        from self_tests.test_pico_graphics_source import Boundary
        boundary=Boundary();first=boundary.source().capture();reader=boundary.source();restore_ui(reader,first,validate)
        self.assertEqual(1,len(boundary.requests));self.assertEqual(1,reader.sequence)
        boundary.controls=[];boundary.roots=[]
        with self.assertRaises(NativeUIError):reader.capture()

    def test_original_policy_or_failed_journal_discard_cannot_be_retired(self):
        m=self.model
        with m.lock.held():
            scene,owner=self.ready();value=deepcopy(owner.previous);value['scenePolicy']='phone-mono-v1'
            with self.assertRaises(NativeUIError):owner.decode(value)
            owner.cleanup()
            with patch.object(owner.store,'discard',return_value=None),self.assertRaises(NativeUIError):owner.retire()
            self.assertTrue(owner.store.path.exists());owner.retire();scene.restore();scene.retire()


if __name__=='__main__':unittest.main()
