"""Actual operation/lock/file flow; paired measurements and SDK are models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from feature_journeys.witness import Client
from ios.adapters.emote_observer import EmoteObservationPending
from ios.adapters.emote_rooted_feature import IOSEmoteRootedFeature
from ios.adapters.emote_runtime import IOSEmoteRuntime
from ios.adapters.emote_terminal import IOSEmoteTerminal
from ios.adapters.emote_terminal_journal import IOSEmoteTerminalJournal
from ios.self_tests import test_ios_emote_terminal_journal as journal_tests


class TerminalControllerTests(unittest.TestCase):
    def setUp(self):
        self.fixture=journal_tests.TerminalJournalTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.f=self.fixture;self.now=0
        for role,owner in self.f.roles.items():owner.state=dict(records=[self.f.refs[role]])
        def forbidden(*_args,**_kwargs):raise AssertionError('No SDK/candidate query belongs in the model operation seam')
        adapter=SimpleNamespace(_candidate_guard=forbidden,_binding=forbidden,
            state_path=lambda selector:self.f.root/selector/'session.json')
        self.runtime=IOSEmoteRuntime(adapter);client=Client('http://127.0.0.1:9/feature-fixture/v1','a'*64)
        self.flows={}
        for role in ('primary','actor'):
            flow=IOSEmoteRootedFeature(self.runtime,role,client,self.f.description['runId'],role,self.f.artifacts,
                dict(source='world-render-target'),actor_selector='actor' if role=='primary' else None,
                primary_selector='primary' if role=='actor' else None,monotonic=lambda:self.now,
                epoch_ms=lambda:100000+self.now*1000,sleep=lambda _:None)
            flow.lock=self.f.roles[role].lock;flow.primary_lock=self.f.roles['primary'].lock;self.flows[role]=flow
        self.controller=IOSEmoteTerminal(self.flows['primary'],self.flows['actor'])

    def call(self,stage,**values):
        return dict(contractVersion=1,runId=self.f.description['runId'],stage=stage,**values)

    def test_inspect_and_seal_use_same_actual_role_locks_and_durable_original(self):
        with patch.object(self.controller,'window',return_value=self.f.window):
            inspected=self.controller.invoke(self.call('inspect'))
            self.assertEqual(self.f.description,inspected['description'])
            result=self.controller.invoke(self.call('seal',description=inspected['description'],samples=self.f.samples))
            self.assertEqual(self.f.proof['seal'],result['seal'])
        journal=IOSEmoteTerminalJournal(self.f.window);self.assertEqual('sealed',journal.state['phase'])
        self.assertEqual(self.f.proof,journal.originals.read(journal.originals.expand(journal.state['record'])))

    def test_unimplemented_finish_and_foreign_request_never_open_a_live_component(self):
        with patch.object(self.controller,'window',side_effect=AssertionError('Live component opened after Stop')):
            for _ in range(2):
                with self.assertRaises(EmoteObservationPending):self.controller.invoke(self.call('finish',seal=self.f.proof['seal']))
            wrong=self.call('inspect');wrong['runId']='f'*32
            with self.assertRaises(NativeUIError):self.controller.invoke(wrong)
        self.assertIsNone(IOSEmoteTerminalJournal(self.f.window).state)

    def test_missing_current_feature_cannot_borrow_a_historical_window(self):
        with self.assertRaises(NativeUIError):self.controller.invoke(self.call('inspect'))
        self.assertIsNone(IOSEmoteTerminalJournal(self.f.window).state)

    def test_pure_window_read_past_deadline_cannot_create_inspection_metadata(self):
        def expired():self.now+=31;return self.f.window
        with patch.object(self.controller,'window',side_effect=expired),self.assertRaises(NativeUIError):
            self.controller.invoke(self.call('inspect'))
        self.assertIsNone(IOSEmoteTerminalJournal(self.f.window).state)

    def test_pure_qualification_past_deadline_cannot_stage_or_write_a_seal(self):
        with patch.object(self.controller,'window',return_value=self.f.window):
            self.controller.invoke(self.call('inspect'));original=self.f.window.qualify
            def expired(*args,**kwargs):
                value=original(*args,**kwargs);self.now+=31;return value
            with patch.object(self.f.window,'qualify',side_effect=expired),self.assertRaises(NativeUIError):
                self.controller.invoke(self.call('seal',description=self.f.description,samples=self.f.samples))
        journal=IOSEmoteTerminalJournal(self.f.window);self.assertEqual('inspected',journal.state['phase'])
        self.assertEqual([],list(self.f.artifacts.glob('emote-terminal-frame-inputs-*')))

    def test_foreign_or_unshared_actor_is_rejected_before_any_operation(self):
        actor=self.flows['actor'];actor.primary_lock=actor.lock
        with self.assertRaises(NativeUIError):IOSEmoteTerminal(self.flows['primary'],actor)

    def test_explicit_runtime_factories_preserve_legacy_selection_and_share_actual_lock(self):
        fields=dict(artifactRoot=str(self.f.artifacts),actorTarget='actor',
            imagePolicy=dict(source='world-render-target',marker=[4,4,132,36],subject=[0,48,160,144]))
        primary=self.runtime._emote_rooted_feature('primary',self.f.description['runId'],role='primary',
            client=self.flows['primary'].client,settings=fields)
        self.assertIs(type(primary),IOSEmoteRootedFeature)
        controller=self.runtime._emote_rooted_terminal(primary)
        self.assertIs(controller.actor.primary_lock,primary.lock)
        self.assertIs(controller.actor.runtime,self.runtime)
        from ios.adapters.emote_feature import IOSEmoteFeature
        legacy=self.runtime._emote_feature('primary',primary.run,role='primary',client=primary.client,settings=fields)
        self.assertIs(type(legacy),IOSEmoteFeature)


if __name__=='__main__':unittest.main()
