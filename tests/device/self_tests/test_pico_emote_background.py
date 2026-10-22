"""Actual Pico original owners with explicit synthetic OS/lifecycle boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUIError
from adapters.pico4.emote_background import PicoEmoteBackground
from self_tests.test_pico_emote_effects import EffectsBoundary


class BackgroundBoundary(EffectsBoundary):
    def __init__(self):
        super().__init__();self.foreground=True;self.lifecycle_inputs=[];self.backgrounds=0;self.activations=1
        self.fault=None;self.native_lost=False;self.native_queries=0
        original_send=self.send;original_readers=self.s.readers
        def send(request):
            self.native_queries+=1
            if not self.foreground:raise NativeUIError('Synthetic native read while backgrounded')
            original_send(request);self.value['lifecycle'].update(backgrounds=self.backgrounds,activations=self.activations)
            if self.native_lost:raise NativeUIError('Synthetic lost post-activation source')
        self.send=send
        def readers():
            if not self.foreground:raise NativeUIError('Synthetic native factory while backgrounded')
            return original_readers()
        self.s.readers=readers
        with self.s.lock.held():self.input_owner,_effect=self.act('cancel')
        self.call=self.input.call('background-resume')
    def sleep(self,seconds):self.tick(round(seconds*1000))
    def _graphics_lifecycle_status(self,target,binding):
        return dict(binding=deepcopy(binding),foreground=self.foreground,running=True)
    def _graphics_lifecycle_input(self,target,operation,binding):
        self.lifecycle_inputs.append(operation)
        if operation=='lifecycle.background':
            if self.fault!='ignored-background':self.foreground=False;self.backgrounds+=1
            if self.fault=='lost-background':raise NativeUIError('Synthetic lost background ACK')
        else:
            self.foreground=True
            if self.fault!='no-native-activation':self.activations+=1
            if self.fault=='lost-activation':raise NativeUIError('Synthetic lost activation ACK')
    @contextmanager
    def session(self):yield
    def owner(self):
        return PicoEmoteBackground(self.s.phase,self.s.lock,self.s.store,self.input.store,self.s.owner,self,
            'synthetic-target',self.session,artifact_root=self.s.root,monotonic=lambda:self.s.clock,sleep=self.sleep)


class BackgroundTests(unittest.TestCase):
    def setUp(self):self.m=BackgroundBoundary();self.addCleanup(self.m.close)
    def test_original_os_and_native_counters_both_prove_same_process_cycle(self):
        m=self.m
        with m.s.lock.held():
            owner=m.owner();self.assertEqual({'performed':True},owner.act(m.call))
            self.assertEqual(['lifecycle.background','app.launch'],m.lifecycle_inputs)
            self.assertEqual('observed',owner.state['phase']);self.assertTrue(m.foreground)
            self.assertIsNotNone(owner.store.read());self.assertIsNotNone(m.s.store.read())
    def test_lost_background_or_activation_ack_cannot_repeat_original_inputs(self):
        for fault in ('lost-background','lost-activation'):
            with self.subTest(fault=fault):
                m=BackgroundBoundary();self.addCleanup(m.close);m.fault=fault
                with m.s.lock.held():
                    owner=m.owner()
                    with self.assertRaises(NativeUIError):owner.act(m.call)
                    m.fault=None;recovered=m.owner();recovered.act(m.call)
                    self.assertEqual(['lifecycle.background','app.launch'],m.lifecycle_inputs)
                    self.assertEqual('observed',recovered.state['phase'])
    def test_ignored_background_is_not_replayed_after_timeout(self):
        m=self.m;m.fault='ignored-background'
        with m.s.lock.held():
            owner=m.owner()
            with self.assertRaises(NativeUIError):owner.act(m.call)
            with self.assertRaises(NativeUIError):m.owner().act(m.call)
            self.assertEqual(['lifecycle.background'],m.lifecycle_inputs);self.assertIsNotNone(owner.store.read())
    def test_os_activation_ack_cannot_supply_missing_original_native_activation(self):
        m=self.m;m.fault='no-native-activation'
        with m.s.lock.held():
            owner=m.owner()
            with self.assertRaises(NativeUIError):owner.act(m.call)
            self.assertEqual('observing',owner.state['phase']);self.assertIsNotNone(owner.store.read())
    def test_separate_cleanup_activation_is_once_only_and_never_completes_retired_action(self):
        m=self.m;m.fault='lost-background'
        with m.s.lock.held():
            owner=m.owner()
            with self.assertRaises(NativeUIError):owner.act(m.call)
            m.s.journal.activate(m.s.phase.run,'e'*32,'cleanup')
            cleanup=dict(contractVersion=m.call['contractVersion'],runId=m.call['runId'])
            m.fault='lost-activation'
            with self.assertRaises(NativeUIError):m.owner().recover_foreground(cleanup)
            m.fault=None;recovered=m.owner();result=recovered.recover_foreground(cleanup)
            self.assertEqual(1,result['picoEmoteForegroundRecoveryVersion']);self.assertTrue(m.foreground)
            self.assertEqual(['lifecycle.background','app.launch'],m.lifecycle_inputs)
            self.assertEqual('background-issued',recovered.state['phase'])
            with self.assertRaises(NativeUIError):recovered.act(m.call)
            self.assertIsNotNone(recovered.store.read())

    def test_lost_source_after_activation_keeps_source_and_background_responsibility(self):
        m=self.m;original=m._graphics_lifecycle_input
        def lost(target,operation,binding):
            original(target,operation,binding)
            if operation=='app.launch':m.native_lost=True
        m._graphics_lifecycle_input=lost
        with m.s.lock.held():
            owner=m.owner()
            with self.assertRaises(NativeUIError):owner.act(m.call)
            queries=m.native_queries
            with self.assertRaises(NativeUIError):m.owner().act(m.call)
            self.assertEqual(queries,m.native_queries);self.assertEqual(['lifecycle.background','app.launch'],m.lifecycle_inputs)
            self.assertIsNotNone(m.s.store.read());self.assertIsNotNone(owner.store.read())


if __name__=='__main__':unittest.main()
