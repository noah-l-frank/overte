"""Actual original collector, strict native protocols and explicit source seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.chat_journey.samples import ChatSamples,ChatCacheAbsence,compose
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.chat_journey.normal_input import ChatNormalInput
from self_tests import test_chat_journey_samples as seams
from self_tests.test_native_chat_observation import RUN,BINDING
from self_tests.test_chat_domain_session import session


class CacheAbsenceTests(unittest.TestCase):
    def setUp(self):
        self.h=seams.ChatSamplesTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
        self.h.primary.present=self.h.peer.present=False;self.h.primary.opened=self.h.peer.opened=0
        self.store=PrivateFeatureState(self.h.root/'initial-cache-absence.json');self.samples=self.sampler()
    def sampler(self):
        peer=self.h.peer.reader();peer.pid=456
        return ChatCacheAbsence(RUN,'primary',BINDING,self.h.peer_binding,self.h.primary.reader(),peer,
            self.h.view.reader(vr=True),self.h.native.reader(),self.store,self.h.primary_lock,self.h.peer_lock,
            vr=True,component_only=True,monotonic=lambda:self.h.clock)
    def read(self):return self.samples.read('b'*32,20000)
    def test_initial_actual_passive_absence_has_empty_scoped_resources_without_opening_or_retiring_cache(self):
        value=self.read();self.assertEqual([],value['resources']);self.assertFalse(value['state']['open'])
        self.assertEqual([],value['state']['peerMessages']);self.assertEqual([],value['state']['localMessages'])
        self.assertEqual(1,self.store.read()['chatCacheAbsenceVersion']);self.assertNotIsInstance(self.samples,ChatSamples)
        self.assertEqual(['inspect'],[row['operation'] for row in self.h.primary.commands]);self.assertFalse(self.h.primary.retired)
        self.assertEqual(['inspect'],[row['operation'] for row in self.h.peer.commands]);self.assertFalse(self.h.peer.retired)
        with self.assertRaises(NativeUIError):compose(RUN,self.samples.frames[-1],123,456,vr=True)
    def test_actual_retired_empty_caches_can_be_observed_without_adopting_active_history(self):
        self.h.primary.retired=self.h.peer.retired=True
        value=self.read();self.assertEqual([],value['resources']);self.assertTrue(self.samples.frames[-1]['primary']['source']['retired'])
        before=len(self.h.primary.commands);rebuilt=self.sampler();self.assertEqual(before,len(self.h.primary.commands));self.assertEqual([],rebuilt.read('c'*32,20000)['resources'])
        self.assertEqual(['inspect','inspect'],[row['operation'] for row in self.h.primary.commands])
    def test_one_actual_live_cache_cannot_be_hidden_as_zero_resources(self):
        for side in ('primary','peer'):
            with self.subTest(side=side):
                self.setUp();boundary=getattr(self.h,side);boundary.present=True;boundary.opened=20000
                with self.assertRaises(NativeUIError):self.read()
                self.assertEqual('reading',self.store.read()['phase']);self.assertTrue(boundary.present)
    def test_actual_chat_page_editor_keyboard_or_retained_history_refuses_absence(self):
        for fault in ('page','focus','keyboard','storage'):
            with self.subTest(fault=fault):
                self.setUp()
                if fault=='page':self.h.open()
                elif fault=='focus':self.h.view.source['editorFocused']=True
                elif fault=='keyboard':
                    from self_tests.test_pico_chat_keyboard import keyboard
                    self.h.view.source['keyboard']=keyboard(True)
                else:self.h.view.source['storage'].update(kind='array',count=1,unowned=1)
                with self.assertRaises(NativeUIError):self.read()
                self.assertEqual('reading',self.store.read()['phase'])
    def test_absence_cannot_reset_or_adopt_an_existing_active_v4_journal(self):
        self.h.primary.present=self.h.peer.present=True;self.h.primary.opened=self.h.peer.opened=20000
        self.h.read();original=self.h.store.read();self.store=self.h.store
        with self.assertRaises(NativeUIError):self.sampler()
        self.assertEqual(original,self.store.read());self.assertEqual(4,original['chatSamplesVersion'])
    def test_absence_type_cannot_be_used_by_an_active_input_owner(self):
        self.read();actor=self.sampler();actor.role='actor'
        with self.assertRaises(NativeUIError):ChatNormalInput((self.samples,actor),lambda _intent:None,PrivateFeatureState(self.h.root/'input.json'))
        self.assertEqual(['inspect'],[row['operation'] for row in self.h.primary.commands])
    def test_reopened_original_cache_cannot_reuse_an_old_absence_frame(self):
        self.read();original=deepcopy(self.samples.frames[-1]);self.h.primary.present=True;self.h.primary.opened=20000
        with self.assertRaises(NativeUIError):self.samples.read('c'*32,20000)
        self.assertEqual(original,self.samples.frames[-1]);self.assertEqual('reading',self.store.read()['phase'])
        self.assertTrue(self.h.primary.present)

    def test_full_candidate_absence_requires_original_native_domain_v2(self):
        primary={key:value for key,value in BINDING.items() if key!='scope'}|dict(sourceRevision='1'*40,artifactSha256='2'*64)
        peer_binding={key:value for key,value in self.h.peer_binding.items() if key!='scope'}|dict(sourceRevision='1'*40,artifactSha256='2'*64)
        def create(path):
            peer=self.h.peer.reader();peer.pid=456
            return ChatCacheAbsence(RUN,'primary',primary,peer_binding,self.h.primary.reader(),peer,
                self.h.view.reader(vr=True),self.h.native.reader(),PrivateFeatureState(self.h.root/path),self.h.primary_lock,self.h.peer_lock,
                vr=True,monotonic=lambda:self.h.clock)
        with self.assertRaises(NativeUIError):create('legacy-full.json').read('b'*32,20000)
        self.h.primary.mutate=session;original=self.h.peer.mutate
        def actual_peer(value):original(value);session(value,instance='3'*32)
        self.h.peer.mutate=actual_peer
        value=create('actual-full.json').read('c'*32,20000);self.assertEqual([],value['resources'])
        self.assertTrue(value['state']['mixerConnected']);self.assertFalse(value['state']['open'])

    def test_changed_domain_birth_cannot_replace_the_original_absent_source(self):
        self.h.primary.mutate=session;original=self.h.peer.mutate
        def peer(value):original(value);session(value,instance='3'*32)
        self.h.peer.mutate=peer;self.read()
        def reconnect(value):peer(value);value['source']['session'].update(revision=4,connectionBirth='9'*32)
        self.h.peer.mutate=reconnect
        with self.assertRaises(NativeUIError):self.samples.read('c'*32,20000)
        self.assertEqual('reading',self.store.read()['phase'])


if __name__=='__main__':unittest.main()
