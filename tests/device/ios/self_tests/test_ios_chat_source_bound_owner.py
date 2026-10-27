"""Same Chat owner, actual WAL/files and independently modeled VM originals."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from feature_journeys.fixtures import context
from feature_journeys.phase_fixture import PhaseFixtureReader
from ios.adapters.chat_controls import IOSChatIO
from ios.adapters.chat_draft_owner import IOSChatDraftOwner
from ios.self_tests.chat_source_bound_fixture import SourceBoundMessageModel,SourceBoundScriptMessageModel
import ios.self_tests.test_ios_chat_draft_owner as legacy_fixture


class ChatSourceBoundOwnerTests(unittest.TestCase):
    def setUp(self):
        self.f=legacy_fixture.ChatDraftOwnerTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.m=self.f.model=SourceBoundMessageModel();self.run=legacy_fixture.RUN;self.binding=legacy_fixture.BINDING
    @contextmanager
    def owner(self,*,source_bound=True):
        model=self.m;failure=None
        with self.f.lock.held():
            try:
                roots,code=model.code_readers() if source_bound else (None,None)
                owner=IOSChatDraftOwner(self.f.store,self.f.root,self.binding,self.run,self.f.lock,model.guard,
                    native=model.native_reader(),io=IOSChatIO(SimpleNamespace(capture=model.capture,native=model)),view=model.view_reader(),
                    phase=PhaseFixtureReader(model.client(),self.run,'chat',epoch_ms=model.epoch,monotonic=lambda:model.widgets.clock),
                    epoch_ms=model.epoch,monotonic=lambda:model.widgets.clock,sleep=model.sleep,
                    source_bound=source_bound,code_roots=roots,code_sources=code)
                model.owner=owner;yield owner
            except BaseException as error:failure=error
        if failure is not None:raise failure
    def act(self,verb,inputs=None,*,same=False):
        if not same:self.m.add_phase(verb,inputs or {},format(len(self.m.activations)+1,'032x'))
        with self.owner() as owner:return owner.act(self.m.ticket,self.m.verb,self.m.inputs)
    def census(self):
        result={}
        for path in self.f.root.iterdir():
            if path.is_file():
                info=path.lstat();result[path.name]=(info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns,info.st_ctime_ns,path.read_bytes())
        return result
    def test_normal_open_type_send_close_reopen_and_pure_source_bound_archive(self):
        self.act('open');self.act('type',dict(text=context(self.run)['unicode']));self.act('send');self.act('close');self.act('open');self.act('close')
        calls=deepcopy(self.m.widgets.calls);queries=deepcopy((self.m.root_queries,self.m.code_queries));files=self.census()
        with self.f.lock.held(),patch.object(PrivateFeatureState,'write',side_effect=AssertionError('No historical write')):
            owner=IOSChatDraftOwner.archive(self.f.store,self.f.root,self.binding,self.run,self.f.lock,self.m.owner.fixture_url,source_bound=True)
            self.assertEqual(4,owner.version);frame=owner.original(owner.state['records'][-1])
            self.assertEqual(1,len(frame['originals']['view']['source']['storage']['events']))
            self.assertIn('scriptSources',frame['originals']);self.assertIn('scriptRoots',frame['originals'])
            self.assertGreater(frame['clockJoin']['hostBeforeEpochMs']-frame['originals']['scriptSources']['clockBefore']['epochMs'],1000000)
        self.assertEqual(calls,self.m.widgets.calls);self.assertEqual(queries,(self.m.root_queries,self.m.code_queries));self.assertEqual(files,self.census())
    def test_foreign_original_code_or_script_root_refuses_before_any_normal_input(self):
        for fault in ('code','root'):
            if fault=='code':self.m.wrong_code=True
            else:self.m.wrong_code=False;self.m.root_url='qrc:/foreign/scripts/'
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):self.act('open')
            self.assertEqual([],self.m.widgets.calls)
    def test_actual_production_script_send_and_reopen_use_the_same_source_bound_owner(self):
        self.m=self.f.model=SourceBoundScriptMessageModel(self)
        self.act('open');self.act('type',dict(text=context(self.run)['unicode']));self.act('send');self.act('close')
        opened=self.act('open');self.assertEqual([context(self.run)['unicode']],opened['local']['messages']);self.act('close')
        original=self.m.command('read');self.assertEqual(1,original['sent'])
        self.assertEqual([context(self.run)['unicode']],[row['message'] for row in original['history']])
        self.assertTrue(self.m.root_queries and self.m.code_queries)
    def test_replaced_actual_manager_is_not_reanchored_before_next_input(self):
        self.act('open');calls=deepcopy(self.m.widgets.calls);self.m.replaced_manager=True
        with self.assertRaises(NativeUIError):self.act('type',dict(text=context(self.run)['unicode']))
        self.assertEqual(calls,self.m.widgets.calls)
    def test_lost_passive_source_return_retains_original_query_and_uses_a_new_read_only_nonce(self):
        self.m.lose_code_return=True
        with self.assertRaises(NativeUIError):self.act('open')
        lost=deepcopy(self.m.code_queries[0]);self.assertEqual([],self.m.widgets.calls);self.m.lose_code_return=False
        self.act('open',same=True)
        with self.owner() as owner:
            self.assertTrue(any(lost in row['queries'] for row in owner.state['interrupted']))
        ids=[row['commandId'] for row in self.m.code_queries];self.assertEqual(len(ids),len(set(ids)));self.assertEqual(lost,self.m.code_queries[0])
    def test_lost_normal_send_recovers_actual_history_without_a_second_send(self):
        self.act('open');self.act('type',dict(text=context(self.run)['unicode']));self.m.lose_send=True
        with self.assertRaises(NativeUIError):self.act('send')
        calls=deepcopy(self.m.widgets.calls);self.m.lose_send=False;self.act('send',same=True)
        self.assertEqual(calls,self.m.widgets.calls);self.assertEqual(1,len(self.m.widgets.sent))
    def test_profile_is_explicit_and_literal_three_cannot_adopt_source_bound_four(self):
        self.act('open');before=self.census()
        with self.assertRaises(NativeUIError),self.owner(source_bound=False):pass
        with self.f.lock.held(),self.assertRaises(NativeUIError):
            IOSChatDraftOwner.archive(self.f.store,self.f.root,self.binding,self.run,self.f.lock,self.m.owner.fixture_url)
        self.assertEqual(before,self.census())


if __name__=='__main__':unittest.main()
