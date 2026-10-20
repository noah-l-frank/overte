"""Synthetic widget/input boundary and real intent files; no product acceptance."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
from pathlib import Path
import sys
import tempfile
import unittest
import uuid
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.token_chat_ui import TokenChatUI,snapshot,same_reference
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from feature_journeys.fixtures import context

RUN='a'*32


class Widgets:
    """Explicit simulated widget state. Outgoing inputs are not peer receipts."""
    def __init__(self):
        self.panel=False;self.tablet=True;self.ready=True;self.focus=False;self.keyboard_request=False
        self.draft='';self.channel='local';self.local=[];self.domain=[];self.sequence=0;self.elapsed=100
        self.instance='b'*32;self.generation='c'*32;self.pid=123;self.page_life=0;self.tokens={}
        self.calls=[];self.sent=[];self.before=None;self.mutate=None
        self.ignore=False;self.ignore_effect=False;self.lose_ack=False;self.clock=0
    def sleep(self,seconds):self.clock+=seconds;self.elapsed+=int(seconds*1000)
    def capture(self):
        controls=[]
        def row(identifier,**extra):
            signature=(self.page_life,self.channel,self.draft,self.focus,self.keyboard_request)
            if identifier not in self.tokens or self.tokens[identifier][0]!=signature:
                self.tokens[identifier]=(signature,uuid.uuid4().hex)
            result=dict(id=identifier,token=self.tokens[identifier][1],enabled=True,focused=False,inputReady=True,**extra)
            controls.append(result);return result
        if self.tablet:
            row('tablet.home')
            if self.panel:
                page=row('chat.page');page.update(inputReady=False,profile='armored-chat-native-v1',channel=self.channel,
                    keyboardRequested=self.keyboard_request,localRowCount=len(self.local),domainRowCount=len(self.domain),componentSourceSha256='d'*64)
                editor=row('chat.input',text=self.draft);editor['focused']=self.focus
                for identifier in ('chat.send','chat.close','chat.local','chat.domain'):row(identifier)
            else:row('chat.entry')
        result=dict(chatControlsVersion=1,open=self.tablet,ready=self.ready,
            scope=dict(instance=self.instance,generation=self.generation,sequence=self.sequence,elapsedMs=self.elapsed,processId=self.pid),controls=controls)
        if self.mutate:self.mutate(result)
        return result
    def input(self,identifier,action,reference,value=None):
        if self.before:self.before()
        same_reference(reference,self.capture(),identifier)
        self.calls.append((identifier,action,value))
        if self.ignore:return # Successful transport ACK with no actual input.
        self.sequence+=1
        if self.ignore_effect:return # Consumed native command, no widget effect.
        if identifier=='chat.entry':
            self.panel=True;self.channel='local';self.page_life+=1;self.draft=''
        elif identifier=='chat.close':
            self.panel=False;self.page_life+=1;self.draft='';self.focus=False;self.keyboard_request=False
        elif identifier=='chat.input':
            if action=='activate':self.focus=True;self.keyboard_request=True
            elif action=='replace':self.draft=value
            else:self.sent.append((self.channel,self.draft));self.draft=''
        elif identifier=='chat.send':
            self.sent.append((self.channel,self.draft));self.draft='';self.focus=False;self.keyboard_request=False
        elif identifier in ('chat.local','chat.domain'):self.channel=identifier.split('.')[1]
        if self.lose_ack:raise NativeUIError('Input acknowledgement was lost')
    def activate(self,identifier,*,reference):self.input(identifier,'activate',reference)
    def replace(self,identifier,value,*,reference):self.input(identifier,'replace',reference,value)
    def submit(self,identifier,*,reference):self.input(identifier,'submit',reference)


class ChatControlTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);os.chmod(self.temp.name,0o700)
        self.store=PrivateFeatureState(Path(self.temp.name)/'intent.json');self.widgets=Widgets()
        self.ui=TokenChatUI(self.widgets,self.persist,RUN,monotonic=lambda:self.widgets.clock,sleep=self.widgets.sleep)
    def persist(self,value):
        previous=self.store.read();self.store.write({'intents':(previous or {'intents':[]})['intents']+[deepcopy(value)]},previous)
    def opened(self):self.ui.open();return self.ui.capture()

    def test_normal_open_unicode_type_channel_send_and_close_do_not_invent_received_rows(self):
        self.opened();self.ui.select_channel('domain');self.ui.type(context(RUN)['unicode']);self.ui.send();self.ui.close()
        self.assertEqual([('domain',context(RUN)['unicode'])],self.widgets.sent)
        self.assertEqual([],self.widgets.local);self.assertEqual([],self.widgets.domain)
        self.assertFalse(self.widgets.panel);self.assertFalse(self.widgets.focus)
        self.assertTrue(self.store.read()['intents']);self.assertNotIn(context(RUN)['unicode'],str(self.store.read()))

    def test_actual_enter_route_clears_editor_without_claiming_keyboard_visibility_or_peer_delivery(self):
        self.opened();self.ui.type(context(RUN)['retry']);self.ui.send(enter=True)
        self.assertEqual([('local',context(RUN)['retry'])],self.widgets.sent);self.assertTrue(self.widgets.focus)
        page=self.ui.page(self.ui.capture());self.assertTrue(page['keyboardRequested']);self.assertNotIn('keyboard',page)
        self.assertEqual([],self.widgets.local);self.assertEqual([],self.widgets.domain)

    def test_ignored_command_ack_is_rejected_by_fresh_consumed_input_counter(self):
        self.widgets.ignore=True
        with self.assertRaises(NativeUIError):self.ui.open()
        self.assertEqual(1,len(self.widgets.calls));self.assertEqual(0,self.widgets.sequence)
        self.assertEqual(1,len(self.store.read()['intents']))

    def test_consumed_but_ignored_widget_effect_is_not_success(self):
        self.opened();self.widgets.ignore_effect=True
        with self.assertRaises(NativeUIError):self.ui.type(context(RUN)['unicode'])
        self.assertEqual(2,len(self.widgets.calls));self.assertFalse(self.widgets.focus);self.assertEqual('',self.widgets.draft)
        self.assertLessEqual(self.widgets.clock,10.1)

    def test_original_context_change_before_backend_admission_keeps_intent_and_refuses_input(self):
        self.opened();self.widgets.before=lambda:setattr(self.widgets,'generation','e'*32)
        with self.assertRaises(NativeUIError):self.ui.type(context(RUN)['unicode'])
        self.assertEqual(1,len(self.widgets.calls));self.assertEqual(2,len(self.store.read()['intents']))

    def test_changed_draft_channel_or_focus_cannot_retarget_captured_send(self):
        for field,value in (('draft',context(RUN)['retry']),('channel','domain'),('focus',False)):
            self.widgets=Widgets();self.ui=TokenChatUI(self.widgets,self.persist,RUN,monotonic=lambda:self.widgets.clock,sleep=self.widgets.sleep)
            self.opened();self.ui.type(context(RUN)['unicode'])
            self.widgets.before=lambda:setattr(self.widgets,field,value)
            with self.subTest(field=field),self.assertRaises(NativeUIError):self.ui.send(enter=True)
            self.assertEqual([],self.widgets.sent)

    def test_five_second_reference_age_and_consumed_sequence_do_not_get_recaptured(self):
        self.opened();reference=self.ui.capture();self.widgets.elapsed+=5001
        with self.assertRaises(NativeUIError):self.widgets.activate('chat.local',reference=reference)
        reference=self.ui.capture();self.widgets.sequence+=1
        with self.assertRaises(NativeUIError):self.widgets.activate('chat.local',reference=reference)
        self.assertEqual(1,len(self.widgets.calls))

    def test_foreign_run_or_private_editor_content_fails_before_new_intent(self):
        self.opened();count=len(self.store.read()['intents'])
        for value in (context('f'*32)['unicode'],'private user message'):
            self.widgets.draft=value
            with self.assertRaises(NativeUIError):self.ui.capture()
        self.assertEqual(count,len(self.store.read()['intents']));self.assertEqual(1,len(self.widgets.calls))

    def test_failed_durable_intent_blocks_widget_input(self):
        self.opened();original=self.store.write
        def fail(*_):raise OSError('intent storage unavailable')
        self.store.write=fail
        with self.assertRaises(OSError):self.ui.type(context(RUN)['unicode'])
        self.store.write=original;self.assertEqual(1,len(self.widgets.calls));self.assertFalse(self.widgets.focus)

    def test_uncertain_send_ack_is_never_replayed(self):
        self.opened();self.ui.type(context(RUN)['retry']);self.widgets.lose_ack=True
        with self.assertRaises(NativeUIError):self.ui.send()
        self.assertEqual([('local',context(RUN)['retry'])],self.widgets.sent)
        with self.assertRaises(NativeUIError):self.ui.send()
        self.assertEqual(1,len(self.widgets.sent));self.assertEqual('chat.send',self.store.read()['intents'][-1]['controlId'])

    def test_changed_native_instance_pid_clock_and_sequence_cannot_be_fresh_snapshots(self):
        self.opened();original=self.widgets.capture()
        for key,value in (('instance','f'*32),('processId',124),('elapsedMs',99),('sequence',0)):
            def mutate(row):row['scope'][key]=value
            self.widgets.mutate=mutate
            with self.subTest(key=key),self.assertRaises(NativeUIError):self.ui.capture()
        self.widgets.mutate=None;self.assertEqual(original['scope']['processId'],self.ui.capture()['scope']['processId'])

    def test_closed_schema_rejects_duplicate_tokens_wrong_types_and_made_up_keyboard_fact(self):
        self.opened();original=self.ui.capture()
        for edit in ('duplicate','version','keyboard','count'):
            value=deepcopy(original)
            if edit=='duplicate':value['controls'][1]['token']=value['controls'][0]['token']
            elif edit=='version':value['chatControlsVersion']=True
            elif edit=='keyboard':value['controls'][1]['keyboard']=True
            else:value['controls'][1]['localRowCount']=True
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):snapshot(value)

    def test_unclosed_original_panel_is_incomplete_cleanup_even_after_consumed_close(self):
        self.opened();self.widgets.ignore_effect=True
        with self.assertRaises(NativeUIError):self.ui.close()
        self.assertTrue(self.widgets.panel);self.assertIsNotNone(self.store.read())

    def test_absent_source_or_unready_tablet_cannot_open_chat(self):
        for field in ('tablet','ready'):
            setattr(self.widgets,field,False)
            with self.subTest(field=field),self.assertRaises(NativeUIError):self.ui.open()
            setattr(self.widgets,field,True)
        self.assertEqual([],self.widgets.calls);self.assertIsNone(self.store.read())


if __name__=='__main__':unittest.main()
