"""Original production Chat Erase/rebuild with the same v4 source ownership."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from feature_journeys.fixtures import context
from ios.adapters.chat_draft_owner import IOSChatDraftOwner
from ios.self_tests.chat_source_bound_fixture import SourceObservationModel
from ios.self_tests.chat_message_script_domain import ScriptMessageModel
from ios.self_tests.test_ios_chat_settings_controls import SettingsWidgets
import ios.self_tests.test_ios_chat_source_bound_owner as owner_fixture


class SourceBoundRestoreScriptModel(SourceObservationModel,ScriptMessageModel):
    def __init__(self,case):
        super().__init__(case,initial_history_null=True);old=self.widgets;self.widgets=SettingsWidgets()
        self.widgets.pid,self.widgets.instance,self.widgets.generation=old.pid,old.instance,old.generation
        capture=self.widgets.capture
        def original():
            value=capture()
            for row in value['controls']:
                if row['id'].startswith('tablet.'):row.pop('inputReady',None)
            return value
        self.widgets.capture=original;self.lose_erase=False;self.erase_error=NativeUIError('Declared lost source-bound Erase return')
    def send_view(self,query):
        super().send_view(query);self.view_value['chatViewVersion']=2
        # Explicit Qt-variant seam; saved values and emissions are actual Node
        # production-Script results, not data derived from an input return.
        raw=b'present:QVariant:invalid' if self.storage['kind']=='null' else (self.storage['kind']+':'+json.dumps(self.storage['events'],sort_keys=True)).encode()
        self.view_value['source']['storage']['valueSha256']=hashlib.sha256(raw).hexdigest()
        if self.widgets.panel and self.widgets.channel=='settings':self.view_value['source']['ui'].update(visibleMessages=[],visibleRowCount=0)
    def chat_input(self,identifier,action,*,reference,value=None):
        super().chat_input(identifier,action,reference=reference,value=value)
        if identifier=='chat.erase' and self.lose_erase:raise self.erase_error


class ChatSourceBoundRestorationTests(unittest.TestCase):
    def setUp(self):
        self.f=owner_fixture.ChatSourceBoundOwnerTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.m=self.f.m=self.f.f.model=SourceBoundRestoreScriptModel(self)
    def message(self):
        self.f.act('open');self.f.act('type',dict(text=context(self.f.run)['unicode']));self.f.act('send')
    def cleanup_phase(self):self.m.add_phase('cleanup',{},'9'*32)
    def restore(self):
        with self.f.owner() as owner:return owner.restore_history(self.m.ticket)
    def test_normal_production_erase_rebuild_retains_code_binding_and_replays_purely(self):
        self.message();self.cleanup_phase();result=self.restore();actual=self.m.command('read')
        self.assertTrue(result['historyRestored']);self.assertIsNone(actual['history']);self.assertEqual(1,actual['erases'])
        self.assertEqual([],actual['local']);self.assertEqual([],actual['domain'])
        files=self.f.census();queries=deepcopy((self.m.root_queries,self.m.code_queries));calls=deepcopy(self.m.widgets.calls)
        with self.f.f.lock.held(),patch.object(PrivateFeatureState,'write',side_effect=AssertionError('No historical write')):
            owner=IOSChatDraftOwner.archive(self.f.f.store,self.f.f.root,self.f.binding,self.f.run,self.f.f.lock,self.m.owner.fixture_url,source_bound=True)
            self.assertEqual(result,owner.restore_history(self.m.ticket))
        self.assertEqual(files,self.f.census());self.assertEqual(queries,(self.m.root_queries,self.m.code_queries));self.assertEqual(calls,self.m.widgets.calls)
    def test_lost_production_erase_return_cannot_reexecute_its_handler(self):
        self.message();self.cleanup_phase();self.m.lose_erase=True
        with self.assertRaises(NativeUIError) as caught:self.restore()
        self.assertIs(self.m.erase_error,caught.exception);self.assertEqual(1,self.m.command('read')['erases'])
        self.m.lose_erase=False;self.assertTrue(self.restore()['historyRestored']);self.assertEqual(1,self.m.command('read')['erases'])
    def test_changed_actual_manager_blocks_cleanup_before_erase_or_other_normal_input(self):
        self.message();self.cleanup_phase();calls=deepcopy(self.m.widgets.calls);self.m.replaced_manager=True
        with self.assertRaises(NativeUIError):self.restore()
        self.assertEqual(calls,self.m.widgets.calls);self.assertEqual(0,self.m.command('read')['erases'])


if __name__=='__main__':unittest.main()
