"""Actual operation/lock/file flow; paired measurements and SDK are models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
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
        actor_root=self.f.root/'controller-actor-originals';actor_root.mkdir(mode=0o700)
        self.f.roles['actor'].root=actor_root;self.f.roles['actor'].originals.root=actor_root
        self.sdk_calls=[]
        def forbidden(*_args,**_kwargs):
            self.sdk_calls.append(True);raise AssertionError('No SDK/candidate query belongs in the model operation seam')
        adapter=SimpleNamespace(_candidate_guard=forbidden,_binding=forbidden,
            state_path=lambda selector:self.f.root/selector/'session.json')
        self.runtime=IOSEmoteRuntime(adapter);client=Client('http://127.0.0.1:9/feature-fixture/v1','a'*64)
        self.flows={}
        for role in ('primary','actor'):
            flow=IOSEmoteRootedFeature(self.runtime,role,client,self.f.description['runId'],role,self.f.roles[role].root,
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

    def test_new_responsibility_after_pure_qualification_prevents_seal_persistence(self):
        current=dict(unchanged=True)
        def guard():
            if not current['unchanged']:raise NativeUIError('Actual new responsibility')
        self.controller.responsibilities=[SimpleNamespace(guard=guard)]
        with patch.object(self.controller,'window',return_value=self.f.window):
            self.controller.invoke(self.call('inspect'));original=self.f.window.qualify
            def changed(*args,**kwargs):
                value=original(*args,**kwargs);current['unchanged']=False;return value
            with patch.object(self.f.window,'qualify',side_effect=changed),self.assertRaises(NativeUIError):
                self.controller.invoke(self.call('seal',description=self.f.description,samples=self.f.samples))
        journal=IOSEmoteTerminalJournal(self.f.window);self.assertEqual('inspected',journal.state['phase'])
        self.assertEqual([],list(self.f.artifacts.glob('emote-terminal-frame-inputs-*')))

    def test_foreign_or_unshared_actor_is_rejected_before_any_operation(self):
        actor=self.flows['actor'];actor.primary_lock=actor.lock
        with self.assertRaises(NativeUIError):IOSEmoteTerminal(self.flows['primary'],actor)

    def test_explicit_actor_cannot_borrow_primary_artifact_root(self):
        actor=self.flows['actor'];actor.root=self.flows['primary'].root
        with self.assertRaises(NativeUIError):IOSEmoteTerminal(self.flows['primary'],actor)
        self.assertEqual([],self.sdk_calls)

    def factory_pair(self):
        for selector in ('factory-primary','factory-actor'):(self.f.root/selector).mkdir(mode=0o700)
        actor_root=self.f.root/'actor-originals';actor_root.mkdir(mode=0o700)
        fields=dict(artifactRoot=str(self.f.artifacts),actorTarget='factory-actor',
            imagePolicy=dict(source='world-render-target',marker=[4,4,132,36],subject=[0,48,160,144]))
        primary=self.runtime._emote_rooted_feature('factory-primary',self.f.description['runId'],role='primary',
            client=self.flows['primary'].client,settings=fields)
        actor_fields=dict(artifactRoot=str(actor_root),primaryTarget=primary.selector,
            imagePolicy=dict(source='world-render-target',marker=[8,8,128,32],subject=[1,48,160,144]))
        actor=self.runtime._emote_rooted_feature('factory-actor',primary.run,role='actor',client=primary.client,settings=actor_fields)
        actor.state=dict(phase='preparing',binding=deepcopy(self.f.roles['actor'].binding),primaryBinding=deepcopy(self.f.roles['primary'].binding),
            actorAdmission=None,phaseInstance='5'*32,initialTicket='6'*32,lastCall=None,inputBarrier=None,cleanup=[],retirement=None)
        actor.store.write(actor.envelope(actor.state),None)
        return primary,actor,fields

    def test_explicit_runtime_factories_preserve_actual_actor_root_policy_and_legacy_selection(self):
        primary,actual_actor,fields=self.factory_pair()
        self.assertIs(type(primary),IOSEmoteRootedFeature)
        controller=self.runtime._emote_rooted_terminal(primary)
        self.assertIs(controller.actor.primary_lock,primary.lock)
        self.assertIs(controller.actor.runtime,self.runtime)
        self.assertEqual(actual_actor.root,controller.actor.root)
        self.assertEqual(actual_actor.policy,controller.actor.policy)
        self.assertEqual(actual_actor.state,controller.actor.state)
        self.assertNotEqual(primary.root,controller.actor.root)
        self.assertEqual([],self.sdk_calls)
        from ios.adapters.emote_feature import IOSEmoteFeature
        legacy=self.runtime._emote_feature(primary.selector,primary.run,role='primary',client=primary.client,settings=fields)
        self.assertIs(type(legacy),IOSEmoteFeature)

    def test_missing_foreign_or_legacy_actor_metadata_never_prepares_a_replacement(self):
        primary,actor,_fields=self.factory_pair();saved=actor.store.read()
        for fault in ('missing','boolean-version','legacy','run','role','fixture','same-root','policy'):
            changed=deepcopy(saved)
            if fault=='missing':changed=None
            elif fault=='boolean-version':changed['iosEmoteFeatureVersion']=True
            elif fault=='legacy':changed['iosEmoteFeatureVersion']=1
            elif fault=='run':changed['runId']='f'*32
            elif fault=='role':changed['role']='primary'
            elif fault=='fixture':changed['fixtureUrl']+='foreign/'
            elif fault=='same-root':changed['artifactRoot']=str(primary.root)
            else:changed['imagePolicy']['marker']=[-1,0,128,32]
            if changed is None:actor.store.discard(saved)
            else:actor.store.write(changed,saved)
            with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError)):
                self.runtime._emote_rooted_terminal(primary)
            self.assertEqual([],self.sdk_calls);self.assertEqual(changed,actor.store.read())
            actor.store.write(saved,changed)

    def test_factory_refuses_primary_lease_before_acquiring_an_actor_lock(self):
        primary,_actor,_fields=self.factory_pair()
        with primary.lock.held(),patch('ios.adapters.emote_terminal.ScriptSourceLock',side_effect=AssertionError('Reversed lock order')):
            with self.assertRaises(NativeUIError):self.runtime._emote_rooted_terminal(primary)
        self.assertEqual([],self.sdk_calls)


if __name__=='__main__':unittest.main()
