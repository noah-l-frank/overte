"""Current-phase effect proof from original PNGs and synthetic native SDKs."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch
import unittest

from adapters.normal_ui import NativeUIError
from feature_journeys.scenarios import VERSION
from ios.adapters.graphics_current_effects import compare
from ios.adapters.graphics_preferences import IOSGraphicsPreferences
from ios.adapters.graphics_world_effects import GraphicsWorldEffectPending
from ios.self_tests.test_ios_graphics_samples import SamplesHarness,POLICY,raster as render_original
from ios.self_tests.test_ios_graphics_scene import RUN,TICKET
from ios.self_tests.test_ios_graphics_restart import RestartHarness


class CurrentEffectsHarness(SamplesHarness):
    def preferences(self):
        return IOSGraphicsPreferences(self.scene(),monotonic=lambda:self.sdk.clock,sleep=self.sdk.sleep)
    def action(self,verb,inputs=None):
        self.counter=getattr(self,'counter',200)+1
        self.preferences().act(dict(contractVersion=VERSION,runId=RUN,ticket=format(self.counter,'032x'),verb=verb,
            inputs=inputs or {},fixtureUrl=self.client.url+'/runs/'+RUN+'/'))
    def setup_pair(self,feature,*,effects=True,other=False,resolution=False):
        self.sdk.model.haze=self.sdk.model.mirrors=True # Original product configuration at the synthetic boundary.
        self.scene().prepare();self.preferences().prepare();self.action('open')
        self.action('set-haze',dict(enabled=False));self.action('set-mirrors',dict(enabled=False))
        before=self.grab();self.gpu.effects=effects
        self.action('set-haze' if feature=='haze' else 'set-mirrors',dict(enabled=True))
        if other:self.action('set-mirrors' if feature=='haze' else 'set-haze',dict(enabled=True))
        if resolution:self.action('set-resolution',dict(value=.5))
        return before,self.grab()
    def grab(self):
        samples=self.samples();samples.read(TICKET,self.sdk.host_epoch());frame,raw,_actual=samples.archive(samples.state['owners'][-1])
        return deepcopy(samples.binding),frame,raw
    def qualify(self,feature,pair,*,restart=None):
        (old,before,a),(binding,current,b)=pair
        return compare(RUN,feature,self.client.url+'/runs/'+RUN+'/',old,before,a,binding,current,b,POLICY,
            self.client.graphics_instance,lambda:round(self.sdk.host_epoch()),lambda:True,restart=restart,monotonic=lambda:self.sdk.clock)


class CurrentEffectsTests(CurrentEffectsHarness,unittest.TestCase):
    def test_original_true_settings_can_be_qualified_under_the_same_baseline_ticket(self):
        with self.lock.held():
            pair=self.setup_pair('haze');result=self.qualify('haze',pair)
            self.assertEqual(TICKET,result['referenceTicket']);self.assertEqual(TICKET,result['currentTicket'])
            self.assertGreater(result['changedFraction'],.05);self.assertIsNone(result['restartSha256'])
            self.assertEqual('baseline',self.client.request('/runs/'+RUN+'/active')['stimulus']['verb'])

    def test_same_phase_mirror_uses_its_actual_orange_reflection_pixels(self):
        with self.lock.held():
            result=self.qualify('mirror',self.setup_pair('mirror'))
            self.assertGreater(result['orangeFractionAfter']-result['orangeFractionBefore'],.005)

    def test_native_settings_and_draws_without_effect_pixels_cannot_qualify_current_state(self):
        with self.lock.held():
            pair=self.setup_pair('haze',effects=False)
            with self.assertRaises(GraphicsWorldEffectPending):self.qualify('haze',pair)

    def test_resolution_and_other_effect_changes_keep_independent_target_pixel_proof(self):
        with self.lock.held():
            pair=self.setup_pair('haze',other=True,resolution=True);result=self.qualify('haze',pair)
            self.assertGreater(result['blueDominanceAfter']-result['blueDominanceBefore'],10)
            self.assertNotEqual(pair[0][1]['capture']['source']['sourceExtent'],pair[1][1]['capture']['source']['sourceExtent'])

    def test_changed_resolution_and_other_setting_cannot_replace_actual_effect_pixels(self):
        with self.lock.held():
            pair=self.setup_pair('mirror',effects=False,other=True,resolution=True)
            with self.assertRaises(GraphicsWorldEffectPending):self.qualify('mirror',pair)

    def assert_selective_pixel_fault(self,feature):
        with self.lock.held():
            before,_current=self.setup_pair(feature,other=True,resolution=True)
            def selective(ticket,*,sdk=None,effects=True):
                if sdk is not None:
                    model=SimpleNamespace(haze=sdk.model.haze if feature!='haze' else False,
                        mirrors=sdk.model.mirrors if feature!='mirror' else False)
                    sdk=SimpleNamespace(model=model,scene_rows=sdk.scene_rows)
                return render_original(ticket,sdk=sdk,effects=effects)
            with patch('ios.self_tests.test_ios_graphics_samples.raster',side_effect=selective):current=self.grab()
            with self.assertRaises(GraphicsWorldEffectPending):self.qualify(feature,(before,current))
            other='mirror' if feature=='haze' else 'haze'
            self.assertGreater(self.qualify(other,(before,current))['changedFraction'],.05)

    def test_actual_reflection_pixels_cannot_fill_missing_haze_effect(self):
        self.assert_selective_pixel_fault('haze')

    def test_actual_haze_pixels_cannot_fill_missing_reflection_effect(self):
        self.assert_selective_pixel_fault('mirror')

    def test_same_frame_foreign_candidate_and_rewritten_original_image_fail(self):
        with self.lock.held():
            pair=self.setup_pair('haze')
            with self.assertRaises(NativeUIError):self.qualify('haze',(pair[0],pair[0]))
            changed=deepcopy(pair);changed[1][0]['artifactSha256']='f'*64
            with self.assertRaises(NativeUIError):self.qualify('haze',changed)
            old,before,a=pair[0];binding,current,b=pair[1]
            with self.assertRaises(NativeUIError):self.qualify('haze',((old,before,a),(binding,current,a)))

    def test_stale_current_frame_or_expired_off_reference_is_not_retimed(self):
        with self.lock.held():
            pair=self.setup_pair('haze');saved=deepcopy(pair)
            self.sdk.sleep(1.6)
            with self.assertRaises(NativeUIError):self.qualify('haze',pair)
            self.assertEqual(saved,pair)
            self.sdk.sleep(44);current=self.grab()
            with self.assertRaises(NativeUIError):self.qualify('haze',(pair[0],current))

    def test_real_background_transition_can_preserve_recent_off_reference_without_relabelling(self):
        with self.lock.held():
            pair=self.setup_pair('haze');before=deepcopy(pair[0]);self.sdk.native_lifecycle['backgrounds']+=1
            self.sdk.native_lifecycle['activations']+=1;after=self.grab()
            self.assertGreater(self.qualify('haze',(pair[0],after))['changedFraction'],.05)
            self.assertEqual(before,pair[0])

    def test_background_counters_and_current_draws_without_pixels_remain_insufficient(self):
        with self.lock.held():
            pair=self.setup_pair('haze');self.sdk.native_lifecycle['backgrounds']+=1
            self.sdk.native_lifecycle['activations']+=1;self.gpu.effects=False;current=self.grab()
            with self.assertRaises(GraphicsWorldEffectPending):self.qualify('haze',(pair[0],current))

    def test_same_pid_launch_count_change_cannot_masquerade_as_background_preservation(self):
        with self.lock.held():
            pair=self.setup_pair('haze');self.sdk.native_lifecycle['launches']+=1;current=self.grab()
            with self.assertRaises(NativeUIError):self.qualify('haze',(pair[0],current))

    def test_late_processing_or_lost_guard_cannot_mint_fresh_effect_evidence(self):
        with self.lock.held():
            pair=self.setup_pair('haze');(old,before,a),(binding,current,b)=pair
            calls=[0]
            def mono():
                calls[0]+=1
                return 0. if calls[0]<4 else 1.6
            args=(RUN,'haze',self.client.url+'/runs/'+RUN+'/',old,before,a,binding,current,b,POLICY,
                  self.client.graphics_instance,lambda:round(self.sdk.host_epoch()))
            with self.assertRaises(NativeUIError):compare(*args,lambda:True,monotonic=mono)
            with self.assertRaises(NativeUIError):compare(*args,lambda:False,monotonic=lambda:0.)


class CurrentRestartHarness(RestartHarness):
    def preferences(self):
        return IOSGraphicsPreferences(self.scene(),monotonic=lambda:self.sdk.clock,sleep=self.sdk.sleep)
    def action(self,verb,inputs=None):
        self.counter=getattr(self,'counter',500)+1
        self.preferences().act(dict(contractVersion=VERSION,runId=RUN,ticket=format(self.counter,'032x'),verb=verb,
            inputs=inputs or {},fixtureUrl=self.client.url+'/runs/'+RUN+'/'))
    def grab(self,stage,ticket):
        samples=self.adapter._graphics_samples('owned',self.client,RUN,'primary',stage,self.lock,self.root/'pixels',POLICY)
        samples.read(ticket,self.sdk.host_epoch())
        frame,raw,_actual=samples.archive(samples.state['owners'][-1]);return deepcopy(samples.binding),frame,raw
    def restarted_pair(self):
        self.scene().prepare();self.preferences().prepare();before=self.grab(0,TICKET)
        restart=self.prepare();restart.act(self.call());self.gpu.marker='8'*32
        self.action('open');self.action('set-haze',dict(enabled=True));self.action('set-mirrors',dict(enabled=True))
        for row in self.sdk.scene_rows:row['lastEditedEpochUs']+=1
        return before,self.grab(1,'8'*32),restart.state['receipt']
    def qualify(self,feature,pair,receipt):
        (old,before,a),(binding,current,b)=pair
        return compare(RUN,feature,self.client.url+'/runs/'+RUN+'/',old,before,a,binding,current,b,POLICY,
            self.client.graphics_instance,lambda:round(self.sdk.host_epoch()),lambda:True,restart=receipt,monotonic=lambda:self.sdk.clock)


class CurrentRestartTests(CurrentRestartHarness,unittest.TestCase):
    def test_current_pixels_cross_only_actual_proven_process_replacement_and_preserve_original_edit_times(self):
        with self.lock.held():
            before,current,receipt=self.restarted_pair();saved=deepcopy(before)
            result=self.qualify('haze',(before,current),receipt)
            self.assertIsNotNone(result['restartSha256']);self.assertGreater(result['blueDominanceAfter']-result['blueDominanceBefore'],10)
            self.assertEqual(saved,before);self.assertNotEqual(before[1]['subjectAfter']['source']['entities'][0]['lastEditedEpochUs'],
                current[1]['subjectBefore']['source']['entities'][0]['lastEditedEpochUs'])
            self.assertEqual(['app.stop','app.launch'],self.inputs)

    def test_missing_kernel_death_foreign_candidate_and_relabelled_pid_cannot_join_effect_sources(self):
        with self.lock.held():
            before,current,receipt=self.restarted_pair()
            with self.assertRaises(NativeUIError):self.qualify('haze',(before,current),None)
            bad=deepcopy(receipt);bad['exit']['presence']='present'
            with self.assertRaises(NativeUIError):self.qualify('haze',(before,current),bad)
            bad=deepcopy(receipt);bad['input']['newBinding']['artifactSha256']='f'*64
            with self.assertRaises(NativeUIError):self.qualify('haze',(before,current),bad)
            changed=deepcopy(before);changed[0]['processIdentity']=current[0]['processIdentity']
            with self.assertRaises(NativeUIError):self.qualify('haze',(changed,current),receipt)

    def test_restarted_settings_and_draws_cannot_replace_current_reflection_pixels(self):
        with self.lock.held():
            before,_current,receipt=self.restarted_pair();self.gpu.effects=False;current=self.grab(1,'8'*32)
            with self.assertRaises(GraphicsWorldEffectPending):self.qualify('mirror',(before,current),receipt)


if __name__=='__main__':unittest.main()
