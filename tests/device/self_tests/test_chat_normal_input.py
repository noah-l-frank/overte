"""Normal Chat controls versus independently supplied native/UI/storage seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys
import unittest
import uuid
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.chat_journey.normal_input import ChatNormalInput,stored_attempts
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.token_chat_ui import TokenChatUI
from adapters.script_journey.history import unpack
from feature_journeys.fixtures import context
from self_tests import test_chat_journey_samples as source_seams
from self_tests.test_token_chat_ui import Widgets
from self_tests.test_native_chat_observation import RUN,SELF
from self_tests.test_pico_chat_keyboard import keyboard


class NormalInputTests(unittest.TestCase):
    def setUp(self):
        self.h=source_seams.ChatSamplesTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
        self.roles=(self.h.samples,self.h.sampler(role='actor',store=PrivateFeatureState(self.h.root/'actor.json')))
        self.widgets=Widgets();self.clock=0.;self.fault=None;self.enter=False
        self.store=PrivateFeatureState(self.h.root/'normal-input.json')
        for boundary in (self.h.primary,self.h.peer,self.h.view,self.h.native):
            original=boundary.mutate
            def mutate(value,original=original):
                if original:original(value)
                value['capturedEpochMs']=self.epoch()
                if 'requestedEpochMs' in value:
                    value['requestedEpochMs']=self.epoch();value['animationFence']['requestedEpochMs']=self.epoch()
                    value['animation']['capturedEpochMs']=self.epoch();value['animation']['clip']['evaluatedEpochMs']=self.epoch()
            boundary.mutate=mutate
        for role in self.roles:
            role.monotonic=lambda:self.clock
            for reader in (role.primary,role.peer,role.view,role.lifecycle):
                reader.clock_ms=self.epoch;reader.monotonic=lambda:self.clock;reader.sleep=self.sleep
        for boundary in (self.h.primary,self.h.peer):
            old_event=boundary.event
            def event(*,old_event=old_event,boundary=boundary,**values):
                old_event(**values);boundary.events[-1]['capturedEpochMs']=self.epoch()
            boundary.event=event
        ordinary=self.widgets.input
        def input(identifier,action,reference,value=None):
            sent=len(self.widgets.sent)
            try:return ordinary(identifier,action,reference,value)
            finally:
                if len(self.widgets.sent)>sent and self.fault!='ack-only':
                    channel,text=self.widgets.sent[-1]
                    self.h.accept(text,sender=SELF,channel=channel,local=not self.h.primary.mixer)
                    if self.h.peer.mixer and self.fault!='missing-peer':
                        self.h.peer.event(text=text,channel=channel,sender=SELF,local=self.fault=='local-only-peer')
                    for key in ('local','domain'):
                        setattr(self.widgets,key,[row['text'] for row in self.h.view.source['storage']['events'] if row['channel']==key])
                self.sync()
        self.widgets.input=input;self.owner=self.make()
    def epoch(self):return 20000+int(self.clock*1000)
    def sleep(self,seconds):self.clock+=seconds;self.widgets.elapsed+=int(seconds*1000)
    def sync(self):
        self.h.view.source.update(tabletShown=self.widgets.tablet,editorFocused=self.widgets.focus,
            editorHasDraft=bool(self.widgets.draft),keyboard=keyboard(self.widgets.keyboard_request))
        if self.widgets.panel:self.h.open(self.widgets.channel,self.widgets.draft)
        else:self.h.close()
        self.h.view.source.update(editorFocused=self.widgets.focus,editorHasDraft=bool(self.widgets.draft),keyboard=keyboard(self.widgets.keyboard_request))
    def make(self):
        return ChatNormalInput(self.roles,lambda intent:TokenChatUI(self.widgets,intent,RUN,
            monotonic=lambda:self.clock,sleep=self.sleep),self.store,enter=self.enter,monotonic=lambda:self.clock,sleep=self.sleep)
    def attempts(self):return stored_attempts(self.store,self.owner.scope)[0]
    def act(self,verb,**inputs):return self.owner.perform(uuid.uuid4().hex,verb,inputs,20000)
    def prepared(self):
        self.act('open');self.act('select-channel',channel='domain');self.act('type',text=context(RUN)['unicode'])
    def test_normal_button_send_requires_original_local_storage_and_independent_peer_receipt(self):
        self.prepared();observed=self.act('send')
        self.assertEqual([context(RUN)['unicode']],observed[0]['state']['peerMessages'])
        self.assertEqual([context(RUN)['unicode']],observed[1]['state']['domainMessages'])
        self.assertEqual('observed',self.attempts()[-1]['phase'])
        self.assertEqual('chat.send',self.attempts()[-1]['inputIntents'][0]['controlId'])
        before=len(self.widgets.calls);rebuilt=self.make();self.assertEqual(before,len(self.widgets.calls))
        ticket=self.attempts()[-1]['ticket']
        with self.assertRaises(NativeUIError):rebuilt.perform(ticket,'send',{},20000)
        self.assertEqual(before,len(self.widgets.calls))
    def test_normal_return_uses_original_submit_and_measures_retained_focus_and_real_keyboard(self):
        self.enter=True;self.owner=self.make();self.prepared();observed=self.act('send')
        self.assertTrue(observed[0]['state']['focused']);self.assertTrue(observed[0]['state']['keyboard'])
        self.assertEqual('submit',self.attempts()[-1]['inputIntents'][0]['action'])
        self.assertEqual(1,len(self.widgets.sent))
    def test_cancelled_original_draft_and_close_three_second_window_preserve_empty_peer_history(self):
        self.act('open');self.act('type',text=context(RUN)['unicode']);observed=self.act('close')
        self.assertFalse(observed[0]['state']['open']);self.assertFalse(observed[1]['state']['keyboard'])
        self.assertEqual([],observed[0]['state']['peerMessages']);self.assertEqual([],self.widgets.sent)
        self.assertGreaterEqual(self.clock,3);self.assertTrue(self.attempts()[-1]['quiet'])
        self.make();self.assertTrue(self.store.path.exists())
    def test_ack_editor_clear_missing_peer_or_local_echo_cannot_supply_remote_delivery(self):
        for fault in ('ack-only','missing-peer','local-only-peer'):
            with self.subTest(fault=fault):
                self.setUp();self.prepared();self.fault=fault
                with self.assertRaises(NativeUIError):self.act('send')
                self.assertEqual(1,len(self.widgets.sent));self.assertNotEqual('observed',self.attempts()[-1]['phase'])
                owner=self.make()
                with self.assertRaises(NativeUIError):owner.perform(uuid.uuid4().hex,'send',{},20000)
                self.assertEqual(1,len(self.widgets.sent))
    def test_offline_fallback_requires_actual_native_local_only_and_no_peer_arrival_for_three_seconds(self):
        self.prepared();self.h.primary.mixer=self.h.peer.mixer=False
        observed=self.act('send');self.assertFalse(observed[0]['state']['mixerConnected'])
        self.assertEqual([],observed[1]['state']['peerMessages']);self.assertGreaterEqual(self.clock,3)
        self.assertTrue(self.h.samples.frames[-1]['primary']['source']['events'][0]['localOnly'])
        self.assertTrue(self.attempts()[-1]['quiet']);self.make()
    def test_same_retry_text_is_sent_only_by_explicit_normal_second_input_after_actual_recovery(self):
        from adapters.chat_journey.no_replay import ChatNoReplay
        self.prepared();self.act('send');self.h.primary.mixer=self.h.peer.mixer=False
        self.act('type',text=context(RUN)['retry']);self.act('send')
        self.assertEqual([context(RUN)['unicode']],[row['text'] for row in self.h.peer.events])
        old=self.h.primary.mutate
        def recovered(value):old(value);value['source']['mixerSha256']='f'*64
        self.h.primary.mutate=recovered;self.h.peer_mixer='f'*64;self.h.primary.mixer=self.h.peer.mixer=True
        for role in self.roles:role.read(uuid.uuid4().hex,20000)
        quiet=ChatNoReplay(*self.roles,PrivateFeatureState(self.h.root/'no-replay.json'),monotonic=lambda:self.clock,sleep=self.sleep)
        quiet.wait(uuid.uuid4().hex,20000)
        self.assertEqual(2,len(self.widgets.sent));self.act('type',text=context(RUN)['retry']);observed=self.act('send')
        self.assertEqual([context(RUN)['unicode'],context(RUN)['retry'],context(RUN)['retry']],observed[0]['state']['domainMessages'])
        self.assertEqual([context(RUN)['unicode'],context(RUN)['retry']],observed[1]['state']['peerMessages'])
        self.assertEqual(3,len(self.widgets.sent));self.make()

    def test_retained_old_receive_time_and_last_persistence_clock_jump_cannot_seal_success(self):
        self.prepared();old_event=self.h.peer.event
        def stale_event(**values):old_event(**values);self.h.peer.events[-1]['capturedEpochMs']=19999
        self.h.peer.event=stale_event
        with self.assertRaises(NativeUIError):self.act('send')
        self.assertEqual(1,len(self.widgets.sent));self.assertNotEqual('observed',self.attempts()[-1]['phase'])
        self.setUp();write=self.owner.store.write;delta=0
        for role in self.roles:role.primary.clock_ms=lambda:self.epoch()+delta
        def persisted(value,previous):
            nonlocal delta
            write(value,previous)
            if unpack(value['attempts'])[-1]['phase']=='observed':delta=2000
        self.owner.store.write=persisted
        with self.assertRaises(NativeUIError):self.act('open')
        self.assertEqual(1,len(self.widgets.calls));self.assertEqual(0,self.clock)

    def test_next_distinct_input_has_a_new_budget_after_idle_without_resetting_original_source_floors(self):
        self.act('open');self.sleep(30)
        observed=self.act('type',text=context(RUN)['unicode'])
        self.assertEqual(context(RUN)['unicode'],observed[0]['state']['draft'])
        self.assertEqual(3,len(self.widgets.calls));self.assertEqual(2,len(self.attempts()))

    def test_final_return_copy_clock_jump_is_not_fresh_with_a_frozen_host_timer(self):
        from adapters.chat_journey import normal_input
        original=normal_input.deepcopy;delta=0
        for role in self.roles:role.primary.clock_ms=lambda:self.epoch()+delta
        def copied(value):
            nonlocal delta
            result=original(value)
            if type(value) is list and len(value)==2 and all(type(row) is dict and 'state' in row and 'capturedEpochMs' in row for row in value):
                delta=2000
            return result
        with patch.object(normal_input,'deepcopy',side_effect=copied):
            with self.assertRaises(NativeUIError):self.act('open')
        self.assertEqual(0,self.clock);self.assertEqual(1,len(self.widgets.calls))
        self.assertTrue(self.store.path.exists());self.assertEqual(2000,delta)

    def test_lost_normal_send_ack_cannot_repeat_after_a_new_owner(self):
        self.prepared();self.widgets.lose_ack=True
        with self.assertRaises(NativeUIError):self.act('send')
        self.assertEqual(1,len(self.widgets.sent));self.widgets.lose_ack=False
        owner=self.make()
        with self.assertRaises(NativeUIError):owner.perform(uuid.uuid4().hex,'send',{},20000)
        self.assertEqual(1,len(self.widgets.sent));self.assertEqual('issuing',self.attempts()[-1]['phase'])
    def test_lost_original_controller_input_and_failed_initial_persistence_cannot_replay_or_dispatch(self):
        self.widgets.tablet=False;self.sync();gestures=[]
        def uncertain(*,reference):
            gestures.append(reference);self.widgets.tablet=True;self.sync()
            raise NativeUIError('lost original controller response')
        self.widgets.open_tablet=uncertain
        with self.assertRaises(NativeUIError):self.act('open')
        owner=self.make()
        with self.assertRaises(NativeUIError):owner.perform(uuid.uuid4().hex,'open',{},20000)
        self.assertEqual(1,len(gestures));self.assertEqual([],self.widgets.calls)
        self.setUp();self.owner.store.write=lambda value,previous:None
        with self.assertRaises(NativeUIError):self.act('open')
        self.assertEqual([],self.widgets.calls);self.assertEqual([],self.h.primary.commands)
        self.assertEqual([],self.h.peer.commands)

    def test_closed_tablet_uses_existing_controller_route_then_actual_chat_entry(self):
        self.widgets.tablet=False;self.sync();gestures=[]
        def open_tablet(*,reference):
            gestures.append(reference);self.widgets.tablet=True;self.sync()
        self.widgets.open_tablet=open_tablet;observed=self.act('open')
        self.assertTrue(observed[0]['state']['open']);self.assertEqual(1,len(gestures))
        self.assertEqual(['controller-open','activate'],[value['action'] for value in self.attempts()[0]['inputIntents']])

    def test_completed_attempts_are_original_immutable_chunks_and_reconstruction_is_passive(self):
        self.prepared();before=[len(source.commands) for source in (self.h.primary,self.h.peer,self.h.view,self.h.native)]
        original=self.attempts();disk=self.store.read();self.assertEqual(3,len(disk['chunks']))
        self.assertEqual([original[-1]],unpack(disk['attempts']))
        rebuilt=self.make();self.assertEqual(original,rebuilt.base['attempts'])
        self.assertEqual(before,[len(source.commands) for source in (self.h.primary,self.h.peer,self.h.view,self.h.native)])
        self.assertEqual(original,rebuilt.chunks.load(disk['chunks']))

    def test_lost_original_archive_or_reading_write_stays_unknown_without_new_input(self):
        for fault in ('reading-write','archive'):
            with self.subTest(fault=fault):
                self.setUp();write=self.store.write;append=self.owner.chunks.append
                def lost_write(value,previous):
                    write(value,previous)
                    if value['phase']=='reading':raise OSError('Original reading intent landed; receipt lost')
                def lost_archive(frame,manifest):
                    append(frame,manifest);raise OSError('Original immutable child landed; receipt lost')
                if fault=='reading-write':self.store.write=lost_write
                else:self.owner.chunks.append=lost_archive
                with self.assertRaises(NativeUIError):self.act('open')
                self.assertEqual(1,len(self.widgets.calls));self.assertEqual('reading',self.store.read()['phase'])
                original=self.store.path.read_bytes()
                with self.assertRaises(NativeUIError):self.make()
                with self.assertRaises(NativeUIError):self.act('open')
                self.assertEqual(1,len(self.widgets.calls));self.assertEqual(original,self.store.path.read_bytes())

    def test_replaced_completed_chunk_and_old_v1_root_cannot_be_adopted_or_dispatch(self):
        self.act('open');chunk=self.owner.chunks.store(0);old=chunk.read();chunk.write({**old,'scopeSha256':'f'*64},old)
        before=len(self.widgets.calls)
        with self.assertRaises(NativeUIError):self.make()
        with self.assertRaises(NativeUIError):self.act('type',text=context(RUN)['unicode'])
        self.assertEqual(before,len(self.widgets.calls))
        self.setUp();self.act('open');old=self.store.read();self.store.write({**old,'chatNormalInputVersion':1},old)
        original=self.store.path.read_bytes();before=len(self.widgets.calls)
        with self.assertRaises(NativeUIError):self.make()
        self.assertEqual(original,self.store.path.read_bytes());self.assertEqual(before,len(self.widgets.calls))


if __name__=='__main__':unittest.main()
