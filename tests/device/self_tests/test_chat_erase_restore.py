"""Normal control/source composition on declared synthetic product boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import json
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.chat_journey.erase_restore import ChatEraseRestore
from adapters.native_chat_profile import OwnedChatProfile
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.token_chat_ui import TokenChatUI
from adapters.script_journey.history import unpack
from self_tests import test_chat_journey_samples as source_seams
from self_tests.test_chat_profile_owner import Boundary as ProfileBoundary
from self_tests.test_chat_erase_controls import CleanupWidgets
from self_tests.test_native_chat_observation import RUN
from self_tests.test_pico_chat_keyboard import keyboard
from feature_journeys.fixtures import context


class EraseRestoreTests(unittest.TestCase):
    def setUp(self):
        self.h=source_seams.ChatSamplesTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
        self.clock=0.;self.fault=None;self.script_history=[];self.profile_native=ProfileBoundary()
        self.profile_native.hashes['cache']['ArmoredChat-Config']=self.h.view.source['storage']['configSha256']
        self.profile_native.hashes['worker']['ArmoredChat-Config']=self.h.view.source['storage']['configSha256']
        self.before=(self.h.samples,self.h.sampler(role='actor',store=PrivateFeatureState(self.h.root/'actor.json')))
        self.after=(self.h.sampler(store=PrivateFeatureState(self.h.root/'erased-primary.json')),
            self.h.sampler(role='actor',store=PrivateFeatureState(self.h.root/'erased-actor.json')))
        for boundary in (self.h.primary,self.h.peer,self.h.view,self.h.native):
            original=boundary.mutate
            def mutate(value,original=original):
                if original:original(value)
                value['capturedEpochMs']=self.epoch()
                if 'requestedEpochMs' in value:
                    value['requestedEpochMs']=self.epoch();value['animationFence']['requestedEpochMs']=self.epoch()
                if 'chatViewVersion' in value and value['source']['ui']['present']:
                    value['source']['ui']['historySha256']=self.widgets.digest()
                    if self.fault=='wrong-digest':value['source']['ui']['historySha256']='0'*64
            boundary.mutate=mutate
        for role in self.before+self.after:
            role.monotonic=lambda:self.clock
            for reader in (role.primary,role.peer,role.view,role.lifecycle):
                reader.clock_ms=self.epoch;reader.monotonic=lambda:self.clock;reader.sleep=self.sleep
        reader=self.profile_native.reader();reader.clock_ms=self.epoch;reader.monotonic=lambda:self.clock;reader.sleep=self.sleep
        original_send=self.profile_native.send
        def profile_send(request):
            self.profile_native.epoch=self.epoch()
            if request['operation']=='restore' and (self.h.view.source['ui']['present'] or self.h.view.source['storage']['count']):
                self.profile_native.requests.append(deepcopy(request));self.profile_native.raw=json.dumps(dict(commandId=request['commandId'],available=False));return
            original_send(request)
            if request['operation']=='restore':self.h.view.source['storage'].update(kind='unset',count=0,events=[])
        self.profile_native.send=profile_send;reader.send=profile_send
        self.profile_native.mutate=lambda value:value['settings'].update(mutationSequence=2 if value['restoreAttempted'] else 0)
        self.profile=OwnedChatProfile(reader,PrivateFeatureState(self.h.root/'profile.json'),self.h.samples.binding,RUN,
            self.h.primary_lock,component_only=True)
        self.profile.perform('acquire')
        self.widgets=CleanupWidgets();self.widgets.panel=True;self.widgets.page_life=1
        original_input=self.widgets.input
        def input(identifier,action,reference,value=None):
            self.widgets.lose_ack=self.fault=='lost-erase-ack' and identifier=='chat.erase'
            try:return original_input(identifier,action,reference,value)
            finally:
                self.widgets.lose_ack=False
                if identifier=='chat.erase' and self.widgets.erased:
                    self.h.view.source['storage'].update(kind='null',count=0,events=[])
                    if self.fault!='retained-script':self.script_history=[]
                if identifier=='chat.entry':
                    self.widgets.local=[row['text'] for row in self.script_history if row['channel']=='local']
                    self.widgets.domain=[row['text'] for row in self.script_history if row['channel']=='domain']
                self.sync()
        self.widgets.input=input
        self.h.accept(context(RUN)['unicode']);self.script_history=deepcopy(self.h.view.source['storage']['events'])
        self.widgets.domain=[context(RUN)['unicode']];self.sync()
        self.store=PrivateFeatureState(self.h.root/'erase-restore.json')
        self.owner=ChatEraseRestore(self.profile,self.before,self.after,
            lambda intent:TokenChatUI(self.widgets,intent,RUN,monotonic=lambda:self.clock,sleep=self.sleep),
            self.store,monotonic=lambda:self.clock,sleep=self.sleep)

    def epoch(self):return 20000+int(self.clock*1000)
    def sleep(self,seconds):
        self.clock+=seconds;self.widgets.elapsed+=int(seconds*1000)
        if self.fault=='late-history' and self.profile_native.attempted and not self.h.view.source['storage']['events']:
            self.h.accept(context(RUN)['reply'])
    def sync(self):
        if not self.widgets.panel:self.h.close();return
        self.h.view.source.update(editorFocused=False,editorHasDraft=False,keyboard=keyboard(False))
        local,domain=self.widgets.local,self.widgets.domain;channel=self.widgets.channel
        visible=local if channel=='local' else domain if channel=='domain' else []
        self.h.view.source['ui']=self.h.ui_template|dict(generation=f'{self.widgets.page_life:032x}',channel=channel,draft='',
            keyboardRequested=False,localMessages=list(local),domainMessages=list(domain),localRowCount=len(local),domainRowCount=len(domain),
            visibleMessages=list(visible),visibleRowCount=len(visible))

    def test_normal_erase_actual_empty_models_new_page_original_restore_and_three_source_quiet(self):
        result=self.owner.run(20000);self.assertEqual('complete',result['phase']);self.assertEqual(1,self.widgets.erased)
        self.assertEqual(['chat.settings','chat.erase','chat.close','chat.entry','chat.close'],[row[0] for row in self.widgets.calls])
        self.assertEqual(['acquire','restore','inspect'],[row['operation'] for row in self.profile_native.requests])
        self.assertEqual(['Overte ä Ω 東京 '+RUN],self.before[0].frames[-1]['view']['source']['ui']['domainMessages'])
        self.assertTrue(all(not role.frames[-1]['view']['source']['storage']['events'] for role in self.after))
        self.assertTrue(all(role.store.path.exists() for role in self.before+self.after));self.assertTrue(self.profile.store.path.exists())
        self.assertGreaterEqual(self.clock,9);self.assertTrue(self.store.path.exists())
        with self.assertRaises(NativeUIError):self.owner.run(20000)

    def test_final_closed_chat_is_reopened_normally_before_original_settings_erase(self):
        self.widgets.panel=False;self.widgets.page_life+=1;self.sync()
        result=self.owner.run(20000)
        self.assertEqual('complete',result['phase']);self.assertEqual(2,result['chatEraseRestoreVersion'])
        self.assertEqual(['chat.entry','chat.settings','chat.erase','chat.close','chat.entry','chat.close'],
            [row[0] for row in self.widgets.calls])
        self.assertEqual([],result['controllerEnvelopes']);self.assertEqual(1,self.widgets.erased)

    def test_closed_tablet_keeps_exact_original_controller_envelope_before_one_gesture_and_never_replays_loss(self):
        for lost in (False,True):
            if lost:self.setUp()
            self.widgets.panel=self.widgets.tablet=False;self.sync();gestures=[]
            envelope=dict(schemaVersion=1,sessionNonce='d'*64,sequence=7,
                commands=[dict(id='tablet-open-7',operation='tablet.open',arguments=dict(holdMilliseconds=1000))])
            def open_tablet(*,reference):
                self.assertFalse(reference['open']);self.assertEqual('controller-open',self.store.read()['inputs'][-1]['action'])
                self.owner.controller_intent(envelope);self.assertEqual([envelope],self.store.read()['controllerEnvelopes'])
                gestures.append(deepcopy(reference))
                if lost:raise NativeUIError('Explicit lost original controller receipt')
                self.widgets.tablet=True
            self.widgets.open_tablet=open_tablet
            if lost:
                with self.assertRaises(NativeUIError):self.owner.run(20000)
                with self.assertRaises(NativeUIError):self.owner.run(20000)
                self.assertEqual(0,self.widgets.erased);self.assertNotEqual('complete',self.store.read()['phase'])
            else:
                self.assertEqual('complete',self.owner.run(20000)['phase']);self.assertEqual(1,self.widgets.erased)
            self.assertEqual(1,len(gestures));self.assertEqual([envelope],self.store.read()['controllerEnvelopes'])

    def test_retained_script_array_is_discovered_only_after_ordinary_new_page_reconstruction(self):
        self.fault='retained-script'
        with self.assertRaises(NativeUIError):self.owner.run(20000)
        self.assertEqual(1,self.widgets.erased);self.assertIn('chat.entry',[row[0] for row in self.widgets.calls])
        self.assertNotEqual('complete',self.store.read()['phase']);self.assertTrue(self.before[0].store.path.exists())

    def test_wrong_independent_model_digest_never_erases_the_original_history(self):
        self.fault='wrong-digest'
        with self.assertRaises(NativeUIError):self.owner.run(20000)
        self.assertEqual(0,self.widgets.erased);self.assertEqual(1,self.h.view.source['storage']['count'])
        self.assertNotIn('chat.erase',[row[0] for row in self.widgets.calls])

    def test_lost_erase_ack_keeps_exact_intent_and_cannot_repeat_erase_or_restore(self):
        self.fault='lost-erase-ack'
        with self.assertRaises(NativeUIError):self.owner.run(20000)
        self.assertEqual(1,self.widgets.erased)
        with self.assertRaises(NativeUIError):self.owner.run(20000)
        self.assertEqual(1,self.widgets.erased)
        self.assertEqual(1,sum(row['controlId']=='chat.erase' for row in self.store.read()['inputs']))
        self.assertLessEqual(sum(row['operation']=='restore' for row in self.profile_native.requests),1)
        self.assertTrue(unpack(self.profile.store.read()['transcript']))

    def test_late_original_history_after_restore_fails_quiet_without_retiring_any_transcript(self):
        self.fault='late-history'
        with self.assertRaises(NativeUIError):self.owner.run(20000)
        self.assertEqual(1,self.widgets.erased);self.assertNotEqual('complete',self.store.read()['phase'])
        self.assertTrue(all(role.store.path.exists() for role in self.before+self.after))


if __name__=='__main__':unittest.main()
