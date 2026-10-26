"""Rooted worker control ordering, not native source/end authorization."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack
from ios import emote_observer as worker
from ios.self_tests.test_ios_emote_terminal_controller import TerminalControllerTests


class RootedWorkerTests(unittest.TestCase):
    def setUp(self):
        self.f=TerminalControllerTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.primary,self.actor,self.settings=self.f.factory_pair();self.events=[]
        self.value=dict(iosEmoteObserverVersion=2,target=self.actor.selector,primaryTarget=self.primary.selector,
            runId=self.actor.run,candidateArguments=['--physical-candidate-metadata','private.json'],
            fixtureUrl=self.actor.phase.fixture_url.split('/runs/')[0],actorToken='a'*64,durationSeconds=30,
            artifactRoot=str(self.actor.root),imagePolicy=self.actor.policy,
            primaryArtifactRoot=str(self.primary.root),primaryImagePolicy=self.primary.policy)
        self.actor.phase.status=lambda:self.fail('No phase/native query after sealed/end control')
        self.actor.publish=lambda:self.fail('No publication after sealed/end control')
        self.journal=PrivateFeatureState(self.primary.store.path.with_name('ios-emote-primary-'+self.actor.run+'-terminal.json'))
    def journal_value(self,phase):
        state=dict(phase=phase,description=deepcopy(self.f.f.description),references=deepcopy(self.f.f.refs),
            seal=deepcopy(self.f.f.proof['seal']),staged=None,record=None,pending=None)
        return dict(iosEmoteTerminalJournalVersion=1,runId=self.actor.run,artifactRoot=str(self.primary.root),
            bindings=dict(primary=self.actor.state['primaryBinding'],actor=self.actor.state['binding']),
            locks=dict(primary=str(self.actor.primary_lock.path),actor=str(self.actor.lock.path)),payload=pack([state]))
    def test_explicit_v2_configuration_pins_both_roots_and_preserves_legacy_v1_shape(self):
        store=PrivateFeatureState(self.f.f.root/'worker-config.json');store.write(self.value,None)
        self.assertEqual(self.value,worker.configuration(store.path))
        legacy={key:value for key,value in self.value.items() if key not in ('primaryArtifactRoot','primaryImagePolicy')}
        legacy['iosEmoteObserverVersion']=1;store.write(legacy,store.read());self.assertEqual(legacy,worker.configuration(store.path))
        for changed in (dict(primaryArtifactRoot=str(self.actor.root)),dict(primaryImagePolicy=dict(source='native-screen'))):
            store.write(self.value|changed,store.read())
            with self.subTest(changed=changed),self.assertRaises(NativeUIError):worker.configuration(store.path)
    def test_original_sealed_journal_waits_without_another_native_or_phase_query(self):
        self.journal.write(self.journal_value('sealed'),None)
        self.assertEqual('sealed',worker.rooted_step(self.actor,self.value));self.assertEqual([],self.f.sdk_calls)
    def test_a_foreign_role_binding_cannot_pause_as_an_owned_sealed_journal(self):
        value=self.journal_value('sealed');value['bindings']['actor']=dict(value['bindings']['actor'],processIdentity='999')
        self.journal.write(value,None)
        with self.assertRaises(NativeUIError):worker.rooted_step(self.actor,self.value)
        self.assertEqual([],self.f.sdk_calls)
    def test_issued_end_waits_but_a_bare_completed_end_cannot_exit_without_originals(self):
        store=PrivateFeatureState(self.primary.store.path.with_name('ios-emote-primary-'+self.actor.run+'-rooted-end.json'))
        value=dict(iosEmoteRootedEndArchiveVersion=1,runId=self.actor.run,archiveSha256='a'*64,
            seal=self.f.f.proof['seal'],payload=pack([dict(phase='retiring',pending=None)]))
        store.write(value,None);self.assertEqual('sealed',worker.rooted_step(self.actor,self.value))
        value['payload']=pack([dict(phase='complete',pending=None)]);store.write(value,store.read())
        with self.assertRaises(NativeUIError):worker.rooted_step(self.actor,self.value)
        self.assertEqual([],self.f.sdk_calls)
    def test_rooted_worker_factory_is_explicit_and_cannot_select_legacy_finalize(self):
        calls=[]
        def rooted(selector,run,**values):calls.append((selector,run,values));return self.actor
        with patch.object(self.actor.runtime,'_emote_rooted_feature',side_effect=rooted),\
             patch.object(self.actor.runtime,'_emote_feature',side_effect=AssertionError('Legacy worker selected')),\
             patch.object(worker,'run_flow',return_value=0):
            self.assertEqual(0,worker.run(self.actor.runtime,self.value))
        self.assertEqual(1,len(calls));self.assertEqual((self.actor.selector,self.actor.run),calls[0][:2])
