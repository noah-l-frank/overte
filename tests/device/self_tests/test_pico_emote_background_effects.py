"""New role-specific native effects after the owned original Pico OS cycle."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4.emote_background import PicoEmoteBackground
from adapters.pico4.emote_effects import PicoEmoteEffects
from adapters.script_journey.history import pack,unpack
from self_tests.test_pico_emote_background import BackgroundBoundary


class JoinedBoundary(BackgroundBoundary):
    def __init__(self):
        super().__init__();self.actor=None;self.played={};self.cancelled={}
        with self.s.lock.held():
            owner,effect=self.act('play',{'name':'Waving'});self.played['primary']=self.observe(owner,effect)['playbackReference']
            original=self.s.store;self.s.store=PrivateFeatureState(self.s.root/'pico-emote-actor-sources.json')
            try:self.actor=self.s.owner('actor')
            finally:self.s.store=original
            self.actor_read();self.actor_read()
            actor_effect=PicoEmoteEffects(owner,current_source=self.actor)
            self.played['actor']=actor_effect.measure(actor_effect.reference())['playbackReference']
            owner,effect=self.act('cancel');value=self.observe(owner,effect,self.played['primary'])
            self.cancelled['primary']=dict(call=deepcopy(value['call']),frame=deepcopy(value['frame']))
            self.actor_read();self.actor_read();actor_effect=PicoEmoteEffects(owner,current_source=self.actor)
            value=actor_effect.measure(actor_effect.reference(),played=self.played['actor'])
            self.cancelled['actor']=dict(call=deepcopy(value['call']),frame=deepcopy(value['frame']))
            self.call=self.input.call('background-resume')
            background=self.owner();background.act(self.call);self.background=background.store.read()
    def actor_read(self):
        original=self.s.store;self.s.store=self.actor.store
        try:return self.actor.read()
        finally:self.s.store=original
    def effect(self,role):
        owner=self.input.create()
        if role=='actor':
            self.actor_read();self.actor_read();return PicoEmoteEffects(owner,current_source=self.actor)
        owner.source.read();owner.source.read();return PicoEmoteEffects(owner)
    def context(self,role):return dict(header=deepcopy(self.background),cancel=deepcopy(self.cancelled[role]),played=deepcopy(self.played[role]))


class BackgroundEffectTests(unittest.TestCase):
    def setUp(self):self.m=JoinedBoundary();self.addCleanup(self.m.close)
    def test_each_role_reopens_its_original_early_cancel_and_acquires_new_native_sources(self):
        m=self.m
        with m.s.lock.held():
            for role in ('primary','actor'):
                effect=m.effect(role);before=m.native_queries;value=effect.measure(effect.reference(),background=m.context(role))
                self.assertEqual(role,value['role']);self.assertEqual('idle',value['state']['animation'])
                self.assertTrue(value['state']['restoredBeforeNominalEnd']);self.assertFalse(value['state']['override'])
                self.assertEqual(m.call,value['call']);self.assertEqual(before,m.native_queries)
    def test_historical_completed_cycle_is_not_a_current_native_read_or_os_input(self):
        m=self.m
        with m.s.lock.held():
            effect=m.effect('primary');queries=m.native_queries;inputs=list(m.lifecycle_inputs)
            cycle,before,after=PicoEmoteBackground.completed_archive(m.background,effect.source)
            self.assertEqual('observed',cycle['phase']);self.assertGreater(len(after),len(before))
            self.assertEqual(queries,m.native_queries);self.assertEqual(inputs,m.lifecycle_inputs)
    def test_actor_cannot_borrow_primary_original_frame_reference(self):
        m=self.m
        with m.s.lock.held():
            effect=m.effect('actor');context=m.context('actor');context['cancel']=deepcopy(m.cancelled['primary'])
            with self.assertRaises(NativeUIError):effect.measure(effect.reference(),background=context)
    def test_new_unowned_override_or_stale_source_cannot_reuse_old_restoration_state(self):
        m=self.m
        with m.s.lock.held():
            m.start('Crying');effect=m.effect('primary')
            with self.assertRaises(NativeUIError):effect.measure(effect.reference(),background=m.context('primary'))
    def test_recovery_or_wrong_original_os_edge_never_becomes_a_completed_cycle(self):
        m=self.m
        with m.s.lock.held():
            effect=m.effect('primary')
            for fault in ('recovery','foreground'):
                context=m.context('primary');state=unpack(context['header']['payload'])[0]
                if fault=='recovery':state['cleanup']={'syntheticRecoveryCannotCompleteAction':True}
                else:state['foreground']['foreground']=False
                context['header']['payload']=pack([state])
                with self.assertRaises(NativeUIError):effect.measure(effect.reference(),background=context)


if __name__=='__main__':unittest.main()
