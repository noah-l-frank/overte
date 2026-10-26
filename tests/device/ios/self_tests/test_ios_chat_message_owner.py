"""Ordinary Chat controls and original journals; modeled Qt/message callbacks.

Local model/history acceptance never represents an independent remote receipt.
No native compilation, product process, SDK, mixer or actual network is used.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from feature_journeys.fixtures import context
from ios.adapters.chat_draft_owner import IOSChatDraftOwner
from ios.self_tests.test_ios_chat_draft_owner import ChatDraftOwnerTests,DraftModel,RUN,BINDING


class MessageModel(DraftModel):
    def __init__(self):
        super().__init__();self.pending_message=None;self.delay=0.;self.acceptance='both';self.lose_send=False;self.duplicate=False
        self.wrong_text=False;self.stale_stamp=False
    def accept(self):
        if self.pending_message is None or self.widgets.clock<self.pending_message['due'] or self.acceptance=='none':return
        row=self.pending_message;self.pending_message=None;count=2 if self.duplicate else 1
        text=context(RUN)['hidden'] if self.wrong_text else row['text']
        for _index in range(count):
            if self.acceptance!='storage-only':getattr(self.widgets,row['channel']).append(text)
            if self.acceptance!='model-only':
                self.storage['events'].append(dict(channel=row['channel'],text=text,timestamp=1 if self.stale_stamp else self.native_epoch()))
                self.storage.update(kind='array',count=len(self.storage['events']))
    def capture(self):self.accept();return super().capture()
    def chat_input(self,identifier,action,*,reference,value=None):
        previous=len(self.widgets.sent);super().chat_input(identifier,action,reference=reference,value=value)
        if len(self.widgets.sent)>previous:
            channel,text=self.widgets.sent[-1]
            self.pending_message=dict(channel=channel,text=text,due=self.widgets.clock+self.delay);self.accept()
            if self.lose_send:raise NativeUIError('Declared lost normal Send return after delivery')


class ChatMessageOwnerTests(unittest.TestCase):
    def setUp(self):
        self.f=ChatDraftOwnerTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.m=self.f.model=MessageModel()
    def action(self,verb,inputs=None,*,ticket=None):
        ticket=ticket or format(len(self.m.activations)+1,'032x');self.f.phase(verb,inputs or {},ticket);return self.f.act()
    def typed(self):self.f.open();self.action('type',dict(text=context(RUN)['unicode']))
    def send(self):return self.action('send')

    def test_normal_local_send_domain_send_hidden_history_close_reopen_and_pure_replay(self):
        self.typed();result=self.send();self.assertEqual([context(RUN)['unicode']],result['local']['messages'])
        self.action('select-channel',dict(channel='domain'));self.assertEqual([],self.m.widgets.domain)
        self.action('type',dict(text=context(RUN)['retry']));self.send()
        self.action('select-channel',dict(channel='local'));self.assertEqual([context(RUN)['unicode']],self.m.widgets.local)
        self.action('close');reopened=self.action('open');self.assertEqual([context(RUN)['unicode']],reopened['local']['messages'])
        self.action('close');commands=deepcopy(self.m.widgets.calls);views=self.m.view_sequence
        files={path:(path.stat().st_ino,path.read_bytes()) for path in self.f.root.iterdir() if path.is_file()}
        with self.f.lock.held(),patch.object(PrivateFeatureState,'write',side_effect=AssertionError('No historical writes')):
            owner=IOSChatDraftOwner.archive(self.f.store,self.f.root,BINDING,RUN,self.f.lock,self.m.owner.fixture_url)
            self.assertEqual(2,owner.version);self.assertEqual(2,len(owner.original(owner.state['records'][-1])['originals']['view']['source']['storage']['events']))
            self.assertFalse(owner.local(owner.original(owner.state['records'][-1]))['open'])
        self.assertEqual(commands,self.m.widgets.calls);self.assertEqual(views,self.m.view_sequence)
        self.assertEqual(files,{path:(path.stat().st_ino,path.read_bytes()) for path in self.f.root.iterdir() if path.is_file()})
        self.assertEqual(2,len(self.m.widgets.sent));self.assertNotIn('peerMessages',result['local'])

    def test_lost_send_result_uses_actual_model_without_second_send(self):
        self.typed();self.m.lose_send=True
        with self.assertRaises(NativeUIError):self.send()
        calls=deepcopy(self.m.widgets.calls);self.m.lose_send=False
        self.assertEqual([context(RUN)['unicode']],self.f.act()['local']['messages'])
        self.assertEqual(calls,self.m.widgets.calls);self.assertEqual(1,len(self.m.widgets.sent))

    def test_delayed_real_callback_keeps_empty_cuts_and_waits_without_another_input(self):
        self.typed();self.m.delay=.6;self.send()
        with self.f.owner() as owner:
            rows=[owner.original(ref) for ref in owner.state['records'] if owner.original(ref)['verb']=='send']
            counts=[row['originals']['view']['source']['storage']['count'] for row in rows]
            self.assertGreater(counts.count(0),1);self.assertEqual(1,counts[-1])
        self.assertEqual(1,len(self.m.widgets.sent))

    def test_consumed_send_and_empty_editor_without_message_never_pass_or_replay(self):
        self.typed();self.m.acceptance='none'
        with self.assertRaises(NativeUIError):self.send()
        calls=deepcopy(self.m.widgets.calls)
        with self.assertRaises(NativeUIError):self.f.act()
        self.assertEqual(calls,self.m.widgets.calls);self.assertEqual(1,len(self.m.widgets.sent))
        self.assertIsNotNone(self.m.owner.state['pending']);self.assertEqual('',self.m.widgets.draft)

    def test_one_source_only_wrong_text_duplicate_or_old_stamp_cannot_replace_actual_acceptance(self):
        for fault in ('model-only','storage-only','wrong_text','duplicate','stale_stamp'):
            with self.subTest(fault=fault):
                self.setUp();self.typed()
                if fault in ('model-only','storage-only'):self.m.acceptance=fault
                else:setattr(self.m,fault,True)
                with self.assertRaises(NativeUIError):self.send()
                self.assertEqual(1,len(self.m.widgets.sent));self.assertIsNotNone(self.m.owner.state['pending'])

    def test_ignored_channel_change_does_not_authorize_a_send_in_another_channel(self):
        self.f.open();self.m.widgets.ignore_effect=True
        with self.assertRaises(NativeUIError):self.action('select-channel',dict(channel='domain'))
        calls=deepcopy(self.m.widgets.calls);self.m.widgets.ignore_effect=False
        with self.assertRaises(NativeUIError):self.f.act()
        self.assertEqual(calls,self.m.widgets.calls);self.assertEqual('local',self.m.widgets.channel)

    def test_failed_send_wal_write_prevents_delivery(self):
        self.typed();self.f.phase('send',{},'9'*32)
        with self.f.owner() as owner:
            write=owner.store.write
            def fail(value,previous):
                from adapters.script_feature.history import unpack
                pending=unpack(value['payload'])[0]['pending']
                if pending is not None and pending['intents']:raise OSError('Declared failed Send WAL')
                return write(value,previous)
            with patch.object(owner.store,'write',side_effect=fail):
                with self.assertRaises(OSError):owner.act(self.m.ticket,'send',{})
        self.assertEqual([],self.m.widgets.sent)

    def test_unowned_append_between_operations_is_not_adopted_as_a_controlled_message(self):
        self.f.open();self.m.pending_message=dict(channel='local',text=context(RUN)['hidden'],due=0);self.m.accept()
        with self.assertRaises(NativeUIError):self.action('type',dict(text=context(RUN)['unicode']))
        self.assertEqual([],self.m.widgets.sent)

    def test_literal_one_preserves_exact_draft_grammar_and_cannot_admit_send(self):
        with patch('ios.adapters.chat_draft_owner.VERSION',1):self.typed()
        files={path:(path.stat().st_ino,path.read_bytes()) for path in self.f.root.iterdir() if path.is_file()}
        with self.f.owner() as owner:
            self.assertEqual(1,owner.version)
            with self.assertRaises(NativeUIError):owner.act(self.m.ticket,'send',{})
        self.assertEqual(files,{path:(path.stat().st_ino,path.read_bytes()) for path in self.f.root.iterdir() if path.is_file()})

    def test_actual_production_script_in_node_drives_normal_send_and_original_settings_history(self):
        from ios.self_tests.chat_message_script_domain import ScriptMessageModel
        self.m=self.f.model=ScriptMessageModel(self);self.typed();self.send()
        self.action('select-channel',dict(channel='domain'));self.action('type',dict(text=context(RUN)['retry']));self.send()
        self.action('close');opened=self.action('open')
        self.assertEqual([context(RUN)['unicode']],opened['local']['messages']);self.action('close')
        source=self.m.command('read');self.assertEqual(2,source['sent'])
        self.assertEqual([context(RUN)['unicode'],context(RUN)['retry']],[row['message'] for row in source['history']])
        self.assertEqual(['local','domain'],[row['channel'] for row in source['history']])
        self.assertEqual(self.m.storage['events'],[dict(text=row['message'],channel=row['channel'],timestamp=row['timestamp']) for row in source['history']])
        self.assertTrue(any(row['type']=='show_message' for row in source['qmlEvents']))

    def test_actual_script_send_without_modeled_native_receipt_cannot_use_an_empty_editor_as_history(self):
        from ios.self_tests.chat_message_script_domain import ScriptMessageModel
        self.m=self.f.model=ScriptMessageModel(self);self.typed();self.m.command('echo',enabled=False)
        with self.assertRaises(NativeUIError):self.send()
        self.assertEqual('',self.m.widgets.draft);self.assertEqual([],self.m.storage['events'])
        self.assertEqual(1,self.m.command('read')['sent']);calls=deepcopy(self.m.widgets.calls)
        with self.assertRaises(NativeUIError):self.f.act()
        self.assertEqual(calls,self.m.widgets.calls);self.assertEqual(1,self.m.command('read')['sent'])

    def test_actual_script_history_survives_failed_later_draft_cleanup_without_a_success_claim(self):
        from ios.self_tests.chat_message_script_domain import ScriptMessageModel
        self.m=self.f.model=ScriptMessageModel(self);self.typed();self.send()
        history=deepcopy(self.m.command('read')['history']);self.m.lose_after_focus=True
        with self.assertRaises(NativeUIError):self.action('type',dict(text=context(RUN)['retry']))
        self.m.lose_after_focus=False;self.f.phase('cleanup',{},'9'*32)
        with self.f.owner() as owner:
            result=owner.cleanup(self.m.ticket);self.assertTrue(result['failed']);self.assertFalse(result['local']['open'])
            self.assertEqual(1,len(owner.state['failures']));self.assertEqual(1,len(owner.state['failures'][0]['intents']))
            owner.quiet(owner.state['operations'][-1])
        self.assertEqual(history,self.m.command('read')['history']);self.assertEqual(1,len(self.m.widgets.sent))


if __name__=='__main__':unittest.main()
