"""Real action and separate observer owners share the actual native counter."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from adapters.normal_ui import NativeUIError,Locator
from ios.adapters.avatar_controls import AvatarUI
from ios.self_tests import test_ios_avatar_surface as fixture


class AvatarInterleavedInputsTests(unittest.TestCase):
    def setUp(self):
        self.surface=fixture.AvatarSurfaceTests();self.surface.setUp();self.addCleanup(self.surface.doCleanups)
        f=self.surface.f;self.actions=f.owner();self.actions.prepare()
    def test_completed_action_then_real_separate_observer_navigation_then_new_action_preserve_each_original(self):
        f=self.surface.f
        self.actions.act(f.action('avatar-url',dict(resource='avatar-a.fst'),'2'*32))
        self.surface.owner().prepare('2'*32)
        before=len(self.surface.owner().state['calls']);sequence=self.surface.widget.sequence
        self.actions.act(f.action('avatar-scale',dict(value=1.5),'3'*32))
        self.assertEqual(1.5,self.surface.widget.scale);self.assertGreater(self.surface.widget.sequence,sequence)
        self.assertEqual(before,len(self.surface.owner().state['calls']))
        reconstructed=f.owner();self.assertEqual(2,len(reconstructed.inputs.state['calls']))
        first,last=reconstructed.inputs.state['calls']
        self.assertGreater(last['events'][0]['intent']['reference']['scope']['sequence'],first['events'][-1]['observed']['scope']['sequence'])
    def test_intervening_observer_input_inside_unfinished_call_cannot_authorize_next_input(self):
        f=self.surface.f;owner=self.actions.inputs
        f.sdk.click(Locator('accessibility id','OverteTabletOpen'))
        owner.begin(f.action('avatar-url',dict(resource='avatar-a.fst'),'2'*32))
        ui=AvatarUI(f.readers['ui'],owner.intent,delivered=owner.delivered,observed=owner.observed,
            monotonic=lambda:f.fixture.clock,sleep=f.fixture.sleep)
        ui.input('avatar.url-open');self.surface.owner().prepare('2'*32)
        before=len([row for row in self.surface.widget.requests if row['operation']=='edit'])
        with self.assertRaises(NativeUIError):ui.input('tablet.home')
        self.assertEqual(before,len([row for row in self.surface.widget.requests if row['operation']=='edit']))


if __name__=='__main__':unittest.main()
