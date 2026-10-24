"""Actual Lifecycle owners/token readers over explicit original native/UI seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[3]))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.normal_ui import NativeUIError
from adapters.pico4.lifecycle_chat import PicoLifecycleChatDraft,run_chat_draft
from adapters.pico4.lifecycle_editor import run_create_world_back
from adapters.script_journey.history import unpack
from adapters.token_chat_ui import TokenChatUI
from feature_journeys.fixtures import context
from self_tests import test_pico_lifecycle_editor as original_editor
from self_tests.test_pico_lifecycle_source import editor,RUN
from self_tests.test_token_chat_ui import Widgets


class LifecycleChatTests(unittest.TestCase):
    def setUp(self):
        self.fixture=original_editor.LifecycleEditorTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.root,self.native,self.lock=self.fixture.root,self.fixture.native,self.fixture.lock
        self.joined=self.fixture.joined();run_create_world_back(self.fixture.owner,self.joined)
        self.initialize_from_editor(self.fixture,self.joined);self.owner.prepare()
    def initialize_from_editor(self,fixture,joined):
        self.fixture,self.joined=fixture,joined
        self.root,self.native,self.lock=fixture.root,fixture.native,fixture.lock
        self.path=self.root/'lifecycle-chat-owner.json';self.widgets=Widgets()
        self.widgets.instance=self.fixture.binding['sessionId'];self.widgets.generation='2'*32;self.widgets.sequence=self.fixture.field.sequence
        original=self.widgets.input
        def native_input(identifier,action,reference,value=None):
            state=unpack(json.loads(self.path.read_text())['payload'])[0];saved=state['inputs'][-1]
            self.assertEqual(identifier,saved['intent']['controlId']);self.assertIsNone(saved['consumed'])
            self.assertEqual(reference,saved['reference'])
            try:return original(identifier,action,reference,value)
            finally:
                if self.widgets.panel:
                    if not any(row['kind']=='chat' for row in self.native.ui.rows):self.native.ui.rows.append(editor(2,'chat'))
                    self.native.ui.rows[-1].update(focused=self.widgets.focus,text=self.widgets.draft)
                    self.native.ui.home=False;self.native.ui.raised=self.widgets.focus
        self.widgets.input=native_input;self.owner=self.make()
    def make(self):
        source=self.native.sources()[0];source.source_lock=self.lock
        route=TokenChatUI(self.widgets,lambda _v:None,RUN,monotonic=lambda:self.native.clock,sleep=self.native.sleep)
        return PicoLifecycleChatDraft(self.joined,source,route,self.path)
    def focused(self):self.owner.open_chat();return self.owner.focus_chat()
    def test_original_create_x_history_joins_new_empty_chat_generation_and_actual_reply_without_send(self):
        opened=self.owner.open_chat();self.assertEqual(('chat','',2,False,False),(opened['editor'],opened['text'],opened['generation'],opened['focused'],opened['keyboard']))
        focused=self.owner.focus_chat();self.assertEqual((True,True),(focused['focused'],focused['keyboard']))
        result=self.owner.type_chat();self.assertEqual(context(RUN)['reply'],result['text']);self.assertEqual(2,result['generation'])
        self.assertNotEqual(self.fixture.owner.state['originalId'],result['originalId']);self.assertEqual([],self.widgets.sent)
        self.assertEqual([],self.widgets.local);self.assertEqual([],self.widgets.domain);self.assertTrue(self.path.exists())
        self.assertEqual(result,run_chat_draft(self.make()));self.assertEqual(3,len(self.widgets.calls))
        self.assertTrue(self.native.ui.rows[0]['contextAlive']);self.assertFalse(self.native.ui.rows[0]['fieldAlive'])
    def test_lost_normal_chat_entry_ack_only_reconciles_same_actual_original(self):
        self.widgets.lose_ack=True
        with self.assertRaises(NativeUIError):self.owner.open_chat()
        self.widgets.lose_ack=False;result=self.make().reconcile()
        self.assertEqual('chat',result['editor']);self.assertEqual(2,result['generation']);self.assertEqual(1,len(self.widgets.calls))
    def test_lost_reply_ime_ack_recovers_original_text_without_retyping_or_sending(self):
        self.focused();self.widgets.lose_ack=True
        with self.assertRaises(NativeUIError):self.owner.type_chat()
        self.widgets.lose_ack=False;result=run_chat_draft(self.make())
        self.assertEqual(context(RUN)['reply'],result['text']);self.assertEqual(3,len(self.widgets.calls));self.assertEqual([],self.widgets.sent)
    def test_consumed_focus_without_actual_vr_keyboard_cannot_become_focused_generation(self):
        self.owner.open_chat();self.widgets.ignore_effect=True
        with self.assertRaises(NativeUIError):self.owner.focus_chat()
        with self.assertRaises(NativeUIError):run_chat_draft(self.make())
        self.assertEqual('focusing',self.owner.state['phase']);self.assertEqual(2,len(self.widgets.calls))
    def test_consumed_ime_without_independent_native_text_is_not_a_typed_reply(self):
        self.focused();self.widgets.ignore_effect=True
        with self.assertRaises(NativeUIError):self.owner.type_chat()
        with self.assertRaises(NativeUIError):run_chat_draft(self.make())
        self.assertEqual('',self.widgets.draft);self.assertEqual(3,len(self.widgets.calls))
    def test_foreign_original_chat_context_cannot_receive_an_owned_reply(self):
        self.focused();self.native.ui.rows[-1]['current']=False;self.native.ui.rows[-1].update(text='',focused=False,visible=False,attached=False)
        self.native.ui.rows.append(editor(3,'chat'))
        with self.assertRaises(NativeUIError):self.owner.type_chat()
        self.assertEqual(2,len(self.widgets.calls));self.assertEqual('',self.widgets.draft)
    def test_source_replaced_during_normal_intent_is_rejected_before_ime_delivery(self):
        self.focused();capture=self.owner.route.capture;count=0
        def replaced():
            nonlocal count
            count+=1
            if count==2:
                self.native.ui.rows[-1].update(current=False,text='',focused=False,visible=False,attached=False)
                self.native.ui.rows.append(editor(3,'chat'))
            return capture()
        with patch.object(self.owner.route,'capture',side_effect=replaced),self.assertRaises(NativeUIError):self.owner.type_chat()
        self.assertEqual(2,len(self.widgets.calls));self.assertEqual('',self.widgets.draft)
    def test_new_chat_alias_with_original_create_context_cannot_establish_generation_two(self):
        source=self.owner.source.send
        def reused(request):
            if len(self.native.ui.rows)>1:self.native.ui.rows[-1]['contextId']=self.native.ui.rows[0]['contextId']
            return source(request)
        self.owner.source.send=reused
        with self.assertRaises(NativeUIError):self.owner.open_chat()
        self.assertEqual('opening',self.owner.state['phase']);self.assertEqual(1,len(self.widgets.calls))
    def test_changed_x_owner_archive_prevents_adopting_an_unrelated_prior_route(self):
        with self.lock.held():self.joined.reconcile()
        with self.assertRaises(NativeUIError):self.make()
        self.assertEqual([],self.widgets.calls)
    def test_failed_durable_normal_input_write_prevents_chat_entry(self):
        with patch.object(self.owner.store,'write',side_effect=OSError('Explicit fsync failure')),self.assertRaises((OSError,NativeUIError)):self.owner.open_chat()
        self.assertEqual([],self.widgets.calls);self.assertFalse(self.widgets.panel)
    def test_final_native_clock_jump_during_report_copy_rejects_result_with_frozen_host_clock(self):
        self.focused();report=self.owner.report;clock=self.owner.source.clock_ms;before=self.native.clock
        def late():
            value=report();self.owner.source.clock_ms=lambda:clock()+2000;return value
        with patch.object(self.owner,'report',side_effect=late),self.assertRaises(NativeUIError):self.owner.type_chat()
        self.assertEqual(before,self.native.clock);self.assertEqual(3,len(self.widgets.calls));self.assertEqual('typed',self.owner.state['phase'])


if __name__=='__main__':unittest.main()
