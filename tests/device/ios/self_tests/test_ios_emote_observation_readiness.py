"""Readiness scheduling models plus a fresh actual immediate-input host case.

The connected case executes pinned JS, ordinary input, original PNG/source
acquisition and abandonment. Its native/WDA producers remain explicit models.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters.emote_images import EmoteImagePending
from ios.self_tests.test_ios_emote_terminal_controller import TerminalControllerTests


class RootedReadinessControlTests(unittest.TestCase):
    def setUp(self):
        self.f=TerminalControllerTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.flow,self.actor,_settings=self.f.factory_pair();self.now=0.;self.calls=[];self.sleeps=[];self.abandoned=[]
        self.flow.monotonic=lambda:self.now;self.flow.state=dict(phase='ready',lastCall=None)
        self.observer=SimpleNamespace(abandon_read=lambda:self.abandoned.append(True),observe=self.pending)
        self.flow.prepare=lambda:dict(observer=self.observer)
        self.flow.phase.read=lambda:dict(ticket='a'*32,verb='play')
        self.flow.phase.status=lambda:dict(active=True,activations=[dict(ticket='a'*32)])
        def sleep(seconds):
            self.assertIsNone(self.flow.lock._owner);self.assertIsNone(self.actor.lock._owner)
            self.sleeps.append(seconds);self.now+=seconds
        self.flow.sleep=sleep
        self.call=dict(contractVersion=16,runId=self.flow.run,afterSequence=0)
    def pending(self,*args,**kwargs):
        self.calls.append(self.flow.deadline);raise EmoteImagePending('Declared unchanged-image readiness model')
    def test_readiness_reacquires_outside_locks_under_one_original_operation_deadline(self):
        def ready(*args,**kwargs):
            self.calls.append(self.flow.deadline)
            if len(self.calls)<3:raise EmoteImagePending('Declared not-yet-moving subject')
            return dict(declaredReadinessModel=True)
        self.observer.observe=ready
        self.assertEqual(dict(declaredReadinessModel=True),self.flow.observe(self.call))
        self.assertEqual([30.,30.,30.],self.calls);self.assertEqual([.05,.05],self.sleeps)
        self.assertEqual(3,len(self.abandoned));self.assertIsNone(self.flow.deadline)
    def test_failed_pixel_readiness_cannot_renew_the_original_deadline(self):
        def late(*args,**kwargs):self.now=29.99;raise EmoteImagePending('Late model')
        self.observer.observe=late
        with self.assertRaises(NativeUIError):self.flow.observe(self.call)
        self.assertEqual([.05],self.sleeps);self.assertIsNone(self.flow.deadline)
    def test_a_real_source_error_is_not_an_effect_readiness_retry(self):
        def invalid(*args,**kwargs):raise NativeUIError('Declared malformed native source')
        self.observer.observe=invalid
        with self.assertRaises(NativeUIError):self.flow.observe(self.call)
        self.assertEqual([],self.sleeps);self.assertEqual(1,len(self.abandoned))
    def test_changed_ticket_cannot_relabel_an_unready_original_acquisition(self):
        self.flow.phase.status=lambda:dict(active=True,activations=[dict(ticket='b'*32)])
        with self.assertRaises(NativeUIError):self.flow.observe(self.call)
        self.assertEqual([],self.sleeps);self.assertEqual([30.],self.calls)


class RootedImmediateReadinessTests(unittest.TestCase):
    def test_immediate_ordinary_play_retains_unready_original_and_observes_actual_changed_pixels(self):
        from ios.self_tests.emote_rooted_whole_fixture import paired
        f=paired(self);flow=f.flow;call=dict(contractVersion=16,runId=flow.run,afterSequence=0)
        flow.observe(call);f.actor.flow.observe(call)
        f.actor.flow.sleep=f.actor.target.domain.sleep
        flow.act(f.call('play',name='Crying'))
        normal_inputs=len(f.target.native.requests)
        # No producer sleep is inserted between the actual ordinary input and
        # the first real source acquisition. The adapter owns readiness.
        public=flow.observe(call)
        self.assertEqual('Crying',public['state']['animation']);self.assertTrue(public['state']['override'])
        self.assertTrue(public['artifacts']);self.assertTrue(f.target.observer.state['abandoned'])
        self.assertIsNone(f.target.observer.state['pending'])
        self.assertEqual(1,len([row for row in f.target.vm.state['events'] if row['method']=='overrideAnimation']))
        self.assertEqual(normal_inputs,len(f.target.native.requests))


if __name__=='__main__':unittest.main()
