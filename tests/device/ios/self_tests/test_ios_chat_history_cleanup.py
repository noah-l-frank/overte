"""Normal null-history restoration; explicit Qt/variant/Script/transport models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from contextlib import contextmanager
import hashlib
import json
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from feature_journeys.fixtures import context
from ios.adapters.chat_draft_owner import IOSChatDraftOwner
from ios.self_tests import test_ios_chat_draft_owner as draft
from ios.self_tests.test_ios_chat_message_owner import MessageModel
from ios.self_tests.test_ios_chat_settings_controls import SettingsWidgets


class RestoreModel(MessageModel):
    def __init__(self):
        super().__init__();old=self.widgets;self.widgets=SettingsWidgets()
        self.widgets.pid,self.widgets.instance,self.widgets.generation=old.pid,old.instance,old.generation
        capture=self.widgets.capture
        def original():
            value=capture()
            for row in value['controls']:
                if row['id'].startswith('tablet.'):row.pop('inputReady',None)
            return value
        self.widgets.capture=original;self.storage['kind']='null';self.script_history=[]
        self.erase_error=NativeUIError('Declared lost Erase return after its real modeled delivery')
        self.lose_erase=False;self.ignore_erase=False;self.wrong_null=False;self.stale_script=False;self.erases=0
    def value_bytes(self):
        # Deliberately modeled QVariant encoding; no actual Qt serializer runs.
        if self.storage['kind']=='null':return b'present:QString:null' if self.wrong_null and self.erases else b'present:QVariant:invalid'
        return (self.storage['kind']+':'+json.dumps(self.storage['events'],sort_keys=True)).encode()
    def send_view(self,command):
        super().send_view(command);self.view_value['chatViewVersion']=2
        self.view_value['source']['storage']['valueSha256']=hashlib.sha256(self.value_bytes()).hexdigest()
        if self.widgets.panel and self.widgets.channel=='settings':
            self.view_value['source']['ui'].update(visibleMessages=[],visibleRowCount=0)
    def accept(self):
        pending=self.pending_message is not None;super().accept()
        if pending and self.pending_message is None:self.script_history=deepcopy(self.storage['events'])
    def chat_input(self,identifier,action,*,reference,value=None):
        ignored=self.widgets.ignore_effect
        if identifier=='chat.erase':self.widgets.ignore_effect=self.ignore_erase
        try:super().chat_input(identifier,action,reference=reference,value=value)
        finally:self.widgets.ignore_effect=ignored
        if identifier=='chat.erase' and not self.ignore_erase:
            self.erases+=1;self.storage.update(kind='null',count=0,unowned=0,events=[])
            if not self.stale_script:self.script_history=[]
            if self.lose_erase:raise self.erase_error
        if identifier=='chat.entry':
            self.widgets.local=[row['text'] for row in self.script_history if row['channel']=='local']
            self.widgets.domain=[row['text'] for row in self.script_history if row['channel']=='domain']


class ScriptRestoreModel:
    @staticmethod
    def create(case):
        from ios.self_tests.chat_message_script_domain import ScriptMessageModel
        class ProductionScriptRestoreModel(ScriptMessageModel):
            def __init__(self):
                super().__init__(case,initial_history_null=True);old=self.widgets;self.widgets=SettingsWidgets()
                self.widgets.pid,self.widgets.instance,self.widgets.generation=old.pid,old.instance,old.generation
                capture=self.widgets.capture
                def original():
                    value=capture()
                    for row in value['controls']:
                        if row['id'].startswith('tablet.'):row.pop('inputReady',None)
                    return value
                self.widgets.capture=original;self.lose_erase=False
                self.erase_error=NativeUIError('Declared lost production Script Erase return')
            def send_view(self,command):
                super().send_view(command);self.view_value['chatViewVersion']=2
                # Actual returned Script values, explicitly modeled QVariant encoding.
                encoded=b'present:QVariant:invalid' if self.storage['kind']=='null' else (self.storage['kind']+':'+json.dumps(self.storage['events'],sort_keys=True)).encode()
                self.view_value['source']['storage']['valueSha256']=hashlib.sha256(encoded).hexdigest()
                if self.widgets.panel and self.widgets.channel=='settings':self.view_value['source']['ui'].update(visibleMessages=[],visibleRowCount=0)
            def chat_input(self,identifier,action,*,reference,value=None):
                super().chat_input(identifier,action,reference=reference,value=value)
                if identifier=='chat.erase' and self.lose_erase:raise self.erase_error
        return ProductionScriptRestoreModel()


class ChatHistoryCleanupTests(unittest.TestCase):
    def setUp(self):
        self.f=draft.ChatDraftOwnerTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.m=self.f.model=RestoreModel()
    def action(self,verb,inputs=None):
        self.f.phase(verb,inputs or {},format(len(self.m.activations)+1,'032x'));return self.f.act()
    def message(self):
        self.f.open();self.action('type',dict(text=context(draft.RUN)['unicode']));self.action('send')
    def phase(self):self.f.phase('cleanup',{},'9'*32)
    def restore(self):
        with self.f.owner() as owner:return owner.restore_history(self.m.ticket)
    @contextmanager
    def archive(self):
        with self.f.lock.held():
            yield IOSChatDraftOwner.archive(self.f.store,self.f.root,draft.BINDING,draft.RUN,self.f.lock,self.m.owner.fixture_url)
    def test_normal_two_channel_history_erase_rebuild_close_and_pure_replay(self):
        self.message();self.action('select-channel',dict(channel='domain'))
        self.action('type',dict(text=context(draft.RUN)['retry']));self.action('send');self.action('close')
        self.phase();result=self.restore();self.assertTrue(result['historyRestored']);self.assertFalse(result['failed'])
        self.assertEqual('null',self.m.storage['kind']);self.assertEqual([],self.m.script_history)
        self.assertEqual(1,self.m.erases);self.assertFalse(self.m.widgets.panel);self.assertGreaterEqual(self.m.widgets.page_life,6)
        files={path:(path.stat().st_ino,path.read_bytes()) for path in self.f.root.iterdir() if path.is_file()}
        calls=deepcopy(self.m.widgets.calls);queries=self.m.view_sequence;self.m.changed=True
        with self.archive() as archived,patch.object(PrivateFeatureState,'write',side_effect=AssertionError('No archival write')):
            self.assertEqual(result,archived.restore_history(self.m.ticket))
        self.assertEqual(calls,self.m.widgets.calls);self.assertEqual(queries,self.m.view_sequence)
        self.assertEqual(files,{path:(path.stat().st_ino,path.read_bytes()) for path in self.f.root.iterdir() if path.is_file()})
    def test_lost_erase_return_resolves_without_a_second_erase(self):
        self.message();self.phase();self.m.lose_erase=True
        with self.assertRaises(NativeUIError) as caught:self.restore()
        self.assertIs(self.m.erase_error,caught.exception);self.assertEqual(1,self.m.erases)
        self.m.lose_erase=False;self.assertTrue(self.restore()['historyRestored'])
        self.assertEqual(1,sum(row[0]=='chat.erase' for row in self.m.widgets.calls));self.assertEqual(1,self.m.erases)
    def test_ignored_erase_remains_owned_and_cannot_be_replayed(self):
        self.message();self.phase();self.m.ignore_erase=True
        with self.assertRaises(NativeUIError):self.restore()
        calls=deepcopy(self.m.widgets.calls)
        with self.assertRaises(NativeUIError):self.restore()
        self.assertEqual(calls,self.m.widgets.calls);self.assertEqual(1,self.m.storage['count'])
        self.assertEqual(1,sum(row[0]=='chat.erase' for row in calls))
    def test_same_null_kind_with_different_variant_hash_is_not_exact_restoration(self):
        self.message();self.phase();self.m.wrong_null=True
        with self.assertRaises(NativeUIError):self.restore()
        self.assertEqual('null',self.m.storage['kind']);self.assertEqual(0,self.m.storage['count'])
        self.assertIsNotNone(self.m.owner.state['pending']);self.assertEqual(1,self.m.erases)
    def test_script_history_retained_behind_empty_settings_and_models_fails_real_page_rebuild(self):
        self.message();self.phase();self.m.stale_script=True
        with self.assertRaises(NativeUIError):self.restore()
        self.assertEqual('null',self.m.storage['kind']);self.assertEqual(0,self.m.storage['count'])
        self.assertTrue(self.m.script_history);self.assertTrue(self.m.widgets.local)
        self.assertEqual('cleanup-rebuild-open',self.m.owner.state['pending']['verb'])
    def test_failed_later_draft_keeps_failure_status_while_restoring_prior_message(self):
        self.message();self.m.lose_after_focus=True
        with self.assertRaises(NativeUIError):self.action('type',dict(text=context(draft.RUN)['retry']))
        self.m.lose_after_focus=False;self.phase();result=self.restore()
        self.assertTrue(result['historyRestored']);self.assertTrue(result['failed']);self.assertEqual(1,self.m.erases)
        self.assertEqual(1,len(self.m.owner.state['failures']));self.assertEqual([],self.m.script_history)

    def test_exact_empty_end_cannot_replace_missing_original_rebuild_operations(self):
        self.message();self.phase();self.restore()
        from ios.adapters.chat_history_cleanup import final_result
        with self.archive() as owner:
            owner.state['operations']=[op for op in owner.state['operations'] if op['verb']!='cleanup-rebuild-open']
            with self.assertRaises(NativeUIError):final_result(owner,self.m.ticket)

    def test_unsupported_original_representation_blocks_before_any_cleanup_input(self):
        self.m.storage['kind']='unset';self.message();self.phase();calls=deepcopy(self.m.widgets.calls)
        with self.assertRaises(NativeUIError):self.restore()
        self.assertEqual(calls,self.m.widgets.calls);self.assertEqual(0,self.m.erases)
    def test_actual_production_script_normal_erase_and_rebuild_restore_original_null(self):
        self.m=self.f.model=ScriptRestoreModel.create(self);self.message()
        self.action('select-channel',dict(channel='domain'));self.action('type',dict(text=context(draft.RUN)['retry']));self.action('send')
        self.action('close');self.phase();result=self.restore();source=self.m.command('read')
        self.assertTrue(result['historyRestored']);self.assertIsNone(source['history']);self.assertTrue(source['historyPresent'])
        self.assertEqual([],source['local']);self.assertEqual([],source['domain']);self.assertEqual(2,source['sent']);self.assertEqual(1,source['erases'])
        self.assertTrue(any(row['type']=='clear_messages' for row in source['qmlEvents']))

    def test_actual_script_lost_erase_return_never_executes_its_handler_twice(self):
        self.m=self.f.model=ScriptRestoreModel.create(self);self.message();self.phase();self.m.lose_erase=True
        with self.assertRaises(NativeUIError) as caught:self.restore()
        self.assertIs(caught.exception,self.m.erase_error);self.assertEqual(1,self.m.command('read')['erases'])
        self.m.lose_erase=False;self.assertTrue(self.restore()['historyRestored'])
        self.assertEqual(1,self.m.command('read')['erases']);self.assertIsNone(self.m.command('read')['history'])

    def test_already_empty_original_needs_no_erase_or_page_open(self):
        self.phase();result=self.restore();self.assertTrue(result['historyRestored'])
        self.assertEqual([],self.m.widgets.calls);self.assertEqual(0,self.m.erases)


if __name__=='__main__':unittest.main()
