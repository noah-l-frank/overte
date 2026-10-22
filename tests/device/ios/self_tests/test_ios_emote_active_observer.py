"""Real owner/action/observer joins over modeled native and actual source/PNGs."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from copy import deepcopy
from io import BytesIO
from PIL import Image
from adapters.normal_ui import NativeUIError
from adapters.normal_feature_state import PrivateFeatureState
from adapters.token_emote_ui import NAMES
from ios.adapters.emote_actions import IOSEmoteActions
from ios.self_tests.emote_active_observer_fixture import ActiveObserverFixture


class ActiveObserverTests(unittest.TestCase):
    def act_observe(self,f,previous,verb,**inputs):
        f.actions.act(f.activate(verb,**inputs));before=f.actions.state['current']['before']
        if verb in ('play','sit','override'):f.native.sleep(.25)
        return f.observer.observe(previous['sequence'],input_barrier=dict(index=before['revision'],sha256=before['sha256']))

    def test_ordinary_play_and_cancel_acquire_actual_caller_pose_and_changed_pngs(self):
        f=ActiveObserverFixture(self);baseline=f.observer.observe(0)
        self.assertEqual('idle',baseline['state']['animation']);self.assertEqual(1,len(baseline['artifacts']))
        f.actions.act(f.activate('open'));opened=f.observer.observe(baseline['sequence'])
        self.assertTrue(opened['state']['panel'])
        f.actions.act(f.activate('play',name='Waving'));before=f.actions.state['current']['before']
        barrier=dict(index=before['revision'],sha256=before['sha256']);f.native.sleep(.25)
        played=f.observer.observe(opened['sequence'],input_barrier=barrier)
        self.assertEqual('Waving',played['state']['animation']);self.assertTrue(played['state']['override'])
        self.assertGreater(played['state']['poseProgress'],0.);self.assertEqual(1,len(played['artifacts']))
        f.actions.act(f.activate('cancel'));before=f.actions.state['current']['before']
        restored=f.observer.observe(played['sequence'],input_barrier=dict(index=before['revision'],sha256=before['sha256']))
        self.assertTrue(restored['state']['restoredBeforeNominalEnd']);self.assertFalse(restored['state']['override'])
        self.assertEqual([],f.vm.state['timers']);self.assertEqual(4,len(f.observer.state['records']))

    def test_all_ten_ordinary_names_have_independent_original_caller_pose_and_pixels(self):
        f=ActiveObserverFixture(self);current=f.observer.observe(0)
        current=self.act_observe(f,current,'open')
        for name in NAMES:
            with self.subTest(name=name):
                current=self.act_observe(f,current,'play',name=name)
                self.assertEqual(name,current['state']['animation']);self.assertTrue(current['state']['override'])
                self.assertGreater(current['state']['poseProgress'],0.)
                original=f.observer.original(f.observer.state['records'][-1]);derived=f.observer.decoder.derive(original)
                self.assertEqual(current,derived['public']);self.assertEqual(1,len(current['artifacts']))
                current=self.act_observe(f,current,'cancel')
                self.assertTrue(current['state']['restoredBeforeNominalEnd']);self.assertFalse(current['state']['override'])
        self.assertEqual(10,sum(row['method']=='overrideAnimation' for row in f.vm.state['events']))
        self.assertEqual(20,f.rig.value['animation']['history']['callSequence'])
        self.assertEqual([],f.vm.state['timers'])

    def test_actual_script_selects_all_three_sit_results_without_requested_variant(self):
        f=ActiveObserverFixture(self);current=f.observer.observe(0);current=self.act_observe(f,current,'open');measured=[]
        for _ in range(3):
            current=self.act_observe(f,current,'sit');measured.append(current['state']['sit'])
            self.assertEqual('Sit',current['state']['animation'])
            current=self.act_observe(f,current,'cancel')
        self.assertEqual({'Sit1','Sit2','Sit3'},set(measured))
        self.assertTrue(all('variant' not in row['call']['inputs'] for row in f.actions.state['history']))

    def test_actual_natural_timer_restores_without_a_restore_input_and_close_reopens_fresh_root(self):
        f=ActiveObserverFixture(self);current=f.observer.observe(0);current=self.act_observe(f,current,'open')
        current=self.act_observe(f,current,'play',name='Waving');requests=len(f.native.requests)
        f.native.sleep(2.1);current=self.act_observe(f,current,'wait-complete')
        self.assertFalse(current['state']['override']);self.assertFalse(current['state']['restoredBeforeNominalEnd'])
        self.assertEqual(requests,len(f.native.requests));self.assertEqual([],f.vm.state['timers'])
        first_root=f.native.root.id;current=self.act_observe(f,current,'close')
        self.assertFalse(current['state']['panel']);self.assertEqual([],current['resources'])
        current=self.act_observe(f,current,'open');self.assertTrue(current['state']['panel'])
        self.assertNotEqual(first_root,f.native.root.id)
        repeated=f.observer.observe(current['sequence'])
        self.assertFalse(repeated['state']['override']);self.assertEqual(current['state'],repeated['state'])
        records=f.observer.state['records'];original=f.observer.original(records[-1])
        played=f.observer.original(records[2]);self.assertEqual(played['image'],original['imageBefore'])
        self.assertEqual(2,len(f.vm.state['events']))

    def test_lost_ordinary_delivery_retains_once_intent_and_never_replays_actual_script(self):
        f=ActiveObserverFixture(self);current=f.observer.observe(0);self.act_observe(f,current,'open')
        call=f.activate('play',name='Waving');deliver=f.native.deliver
        def lost(request):
            deliver(request)
            if f.vm.state['events']:raise NativeUIError('Modeled lost return after actual JS callback')
        f.native.deliver=lost
        with self.assertRaises(NativeUIError):f.actions.act(call)
        count=(len(f.native.requests),deepcopy(f.vm.state['events']))
        f.native.deliver=deliver
        rebuilt=IOSEmoteActions(PrivateFeatureState(f.root/'ios-emote-inputs.json'),f.sources,f.sdk)
        with self.assertRaises(NativeUIError):rebuilt.act(call)
        with self.assertRaises(NativeUIError):rebuilt.act(f.activate('play',name='Waving'))
        self.assertEqual(count,(len(f.native.requests),f.vm.state['events']))
        self.assertEqual('issuing',rebuilt.state['current']['phase']);self.assertEqual(1,len(count[1]))

    def test_actual_failed_animation_resource_does_not_become_expected_playback(self):
        f=ActiveObserverFixture(self);current=f.observer.observe(0);current=self.act_observe(f,current,'open')
        f.vm.command('resource',url=f.vm.root+'/system/assets/animations/Waving.fbx',state=4)
        current=self.act_observe(f,current,'play',name='Waving')
        self.assertEqual('idle',current['state']['animation']);self.assertFalse(current['state']['override'])
        self.assertEqual([],f.vm.state['events']);self.assertEqual('Animation failed to load',f.vm.state['states'][-1]['status'])

    def test_stale_played_pixels_cannot_prove_actual_restoration(self):
        f=ActiveObserverFixture(self);current=f.observer.observe(0);current=self.act_observe(f,current,'open')
        current=self.act_observe(f,current,'play',name='Waving')
        _frame,raw,_result=f.samples.archive(f.samples.state['rows'][-1])
        image=Image.open(BytesIO(raw));stripe=min(x for x in range(760,840) if image.getpixel((x,600))[:3]==(220,65,30))
        # Freeze the actual earlier fenced pixels, not the later Rig snapshot:
        # the real source continues to advance between its capture and return.
        played_x=.1+(stripe-760)/100;f.pixel_pose=lambda:played_x
        with self.assertRaisesRegex(AssertionError,'Actual feature subject pixels did not change'):
            self.act_observe(f,current,'cancel')
        self.assertFalse(f.rig.value['animation']['overrideActive']);self.assertIsNotNone(f.observer.state['pending'])
        self.assertEqual(3,len(f.observer.state['records']))


if __name__=='__main__':unittest.main()
