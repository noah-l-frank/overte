"""Durable iOS ordinary Graphics preferences; native/UI SDK boundary synthetic."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack,unpack
from feature_journeys.scenarios import VERSION
from ios.adapters.graphics_preferences import IOSGraphicsPreferences
from ios.self_tests.test_ios_graphics_scene import SceneHarness,RUN


class PreferencesTests(SceneHarness,unittest.TestCase):
    def prepare(self):
        scene=self.scene();scene.prepare()
        prefs=self.preferences(scene);prefs.prepare();return prefs
    def preferences(self,scene=None):
        return IOSGraphicsPreferences(scene or self.scene(),monotonic=lambda:self.sdk.clock,sleep=self.sdk.sleep)
    def call(self,verb,inputs=None,ticket=None):
        self.counter=getattr(self,'counter',100)+1
        return dict(contractVersion=VERSION,runId=RUN,fixtureUrl=self.client.url+'/runs/'+RUN+'/',
            ticket=ticket or format(self.counter,'032x'),verb=verb,inputs=inputs or {})

    def test_normal_generic_preferences_and_recreated_owner_restore_original_values_and_scene(self):
        self.sdk.model.resolution=.8;self.sdk.model.haze=True
        with self.lock.held():
            prefs=self.prepare();original=deepcopy(prefs.state['original'])
            self.assertEqual(.8,original['graphics']['requestedResolutionScale'])
            self.assertEqual(self.sdk.epoch(),original['capturedEpochMs'])
            for verb,inputs in (('open',{}),('set-resolution',{'value':.5}),('set-haze',{'enabled':False}),
                                ('set-mirrors',{'enabled':True}),('close',{}),('open',{})):
                self.assertEqual({'performed':True},prefs.act(self.call(verb,inputs)))
                prefs=self.preferences()
            self.assertEqual(.5,self.sdk.model.resolution);self.assertFalse(self.sdk.model.haze);self.assertTrue(self.sdk.model.mirrors)
            packet=prefs.cleanup();self.assertEqual(original['graphics'],packet['graphics'])
            self.assertEqual('closed',self.sdk.stage);self.assertFalse(any(prefs.scene.state['leases'].values()))
            self.preferences().cleanup();self.preferences().retire();scene=self.scene();scene.restore();scene.retire()
            self.assertEqual([4.,0.,2.],self.sdk.feet)

    def test_ignored_slider_is_not_success_and_reconstruction_never_resends_it(self):
        with self.lock.held():
            prefs=self.prepare();prefs.act(self.call('open'));self.sdk.model.fault='resolution'
            call=self.call('set-resolution',{'value':.5})
            with self.assertRaises(NativeUIError):prefs.act(call)
            self.assertEqual(1,self.sdk.model.actions.count('resolution'));self.assertEqual(.6,self.sdk.model.resolution)
            with self.assertRaises(NativeUIError):self.preferences().act(call)
            self.assertEqual(1,self.sdk.model.actions.count('resolution'))
            self.sdk.model.fault='';self.preferences().cleanup()

    def test_lost_return_after_delivered_slider_uses_original_readback_without_resend(self):
        with self.lock.held():
            prefs=self.prepare();prefs.act(self.call('open'));call=self.call('set-resolution',{'value':.5})
            original=self.sdk.model.set_value
            def lost(*args,**kwargs):original(*args,**kwargs);raise NativeUIError('Synthetic lost input return')
            with patch.object(self.sdk.model,'set_value',side_effect=lost),self.assertRaises(NativeUIError):prefs.act(call)
            self.assertEqual(.5,self.sdk.model.resolution)
            self.preferences().act(call);self.assertEqual(1,self.sdk.model.actions.count('resolution'))
            self.preferences().cleanup();self.assertEqual(.6,self.sdk.model.resolution)

    def test_off_grid_request_never_sends_a_slider(self):
        with self.lock.held():
            prefs=self.prepare();prefs.act(self.call('open'))
            with self.assertRaises(ValueError):prefs.act(self.call('set-resolution',{'value':.65}))
            self.assertNotIn('resolution',self.sdk.model.actions)

    def test_nonrestorable_original_slider_grid_fails_before_any_scalar_input(self):
        self.sdk.model.resolution=.65
        with self.lock.held():
            prefs=self.prepare();prefs.act(self.call('open'))
            with self.assertRaises(NativeUIError):prefs.act(self.call('set-haze',{'enabled':True}))
            self.assertEqual([],self.sdk.model.actions)

    def test_stale_native_clock_and_foreign_birth_prevent_preference_input(self):
        with self.lock.held():
            prefs=self.prepare();self.sdk.core_fault='stale'
            with self.assertRaises(NativeUIError):prefs.act(self.call('open'))
            self.assertEqual('closed',self.sdk.stage)
            self.sdk.core_fault='foreign'
            with self.assertRaises(NativeUIError):self.preferences().act(self.call('open'))
            self.assertEqual('closed',self.sdk.stage)

    def test_persisted_intent_failure_prevents_actual_ui_delivery(self):
        with self.lock.held():
            prefs=self.prepare();count=len(self.sdk.clicks)
            with patch.object(prefs.store,'write',side_effect=NativeUIError('Synthetic failed durable write')), \
                 self.assertRaises(NativeUIError):prefs.act(self.call('open'))
            self.assertEqual(count,len(self.sdk.clicks))

    def test_tampered_original_ui_projection_or_proof_is_rejected_during_reconstruction(self):
        with self.lock.held():
            prefs=self.prepare();prefs.act(self.call('open'));call=self.call('set-resolution',{'value':.5});prefs.act(call)
            value=deepcopy(prefs.previous);state=unpack(value['payload'])[0]
            state['current']['proof']['graphics']['originalReceipt']['observation']['sampleEpochMs']-=1
            value['payload']=pack([state]);prefs.store.write(value,prefs.previous)
            with self.assertRaises(NativeUIError):self.preferences()

    def test_retained_foreign_setting_change_prevents_a_green_restore(self):
        with self.lock.held():
            prefs=self.prepare();prefs.act(self.call('open'));prefs.act(self.call('set-resolution',{'value':.5}))
            original=self.sdk.core.mutate
            def foreign(value):original(value);value['graphics']['shadowsSetting']=True
            self.sdk.core.mutate=foreign
            with self.assertRaises(NativeUIError):prefs.cleanup()
            self.assertNotEqual('cleaned',prefs.state['phase'])


if __name__=='__main__':unittest.main()
