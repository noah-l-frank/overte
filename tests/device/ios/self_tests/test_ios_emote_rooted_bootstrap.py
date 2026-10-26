"""Real retained configuration copies; effect qualification remains closed.

Archive creation's effect qualifier is an explicit model. These cases test only
configuration reopening, not a process absence or successful end proof.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.emote_canonical_end import completed
from ios.adapters.emote_rooted_bootstrap import primary as bootstrap
from ios.adapters.emote_rooted_end_lock import held_existing
from ios.adapters.emote_rooted_final_archive import IOSEmoteRootedFinalArchive
from ios.self_tests.test_ios_emote_sources import phase
from ios.self_tests.test_ios_emote_terminal_controller import TerminalControllerTests


class RootedBootstrapTests(unittest.TestCase):
    def setUp(self):
        self.f=TerminalControllerTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.flow,self.actor,self.settings=self.f.factory_pair()
        # Real frozen bytes deliberately contain no native effect graph.
        self.feature=self.flow.envelope(dict(declaredConfigurationOnly=True))
        self.flow.store.write(self.feature,None)
        self.store=PrivateFeatureState(self.flow.store.path.with_name('ios-emote-primary-'+self.flow.run+'-rooted-final.json'))
        self.status=phase(3,95000);self.status.update(runId=self.flow.run,active=False,retiredEpochMs=94900)
        with held_existing(self.actor.lock),held_existing(self.flow.lock):
            self.archive=IOSEmoteRootedFinalArchive(self.store,self.flow.root,self.f.f.roles['primary'].binding,
                self.flow.run,'primary',self.flow.lock,self.flow.lock,[self.flow.store],lambda:True,lambda _copies:True)
            self.archive.begin(self.status);self.archive.freeze()
        self.originals={path:path.read_bytes() for path in (self.store.path,self.archive.record_store(1).path,self.flow.store.path)}
    def reopen(self,**chosen):
        return bootstrap(self.flow.runtime,self.flow.selector,self.flow.run,self.settings|chosen)
    def test_exact_retained_configuration_constructs_only_a_passive_reader(self):
        reader=self.reopen()
        self.assertEqual(self.flow.root,reader.root);self.assertEqual(self.flow.phase.fixture_url,reader.phase.fixture_url)
        self.assertEqual(self.actor.selector,reader.actor_selector);self.assertIsNone(reader.state)
        with self.assertRaises(NativeUIError):reader.client.request('/runs/'+reader.run)
        with self.assertRaises(NativeUIError):completed(reader,self.f.f.proof['seal'])
        self.assertEqual([],self.f.sdk_calls)
        self.assertEqual(self.originals,{path:path.read_bytes() for path in self.originals})
    def test_configured_root_or_policy_cannot_adopt_an_unrelated_copy(self):
        for values in (dict(artifactRoot=str(self.actor.root)),dict(imagePolicy=self.actor.policy)):
            with self.subTest(values=values),self.assertRaises(NativeUIError):self.reopen(**values)
        self.assertEqual([],self.f.sdk_calls)
    def test_changed_actual_copy_bytes_cannot_supply_configuration(self):
        store=self.archive.record_store(1);value=store.read();changed=deepcopy(value);changed['path']=str(self.actor.store.path)
        store.write(changed,value)
        with self.assertRaises(NativeUIError):self.reopen()
        self.assertEqual([],self.f.sdk_calls)
    def test_missing_original_source_lock_is_not_recreated(self):
        self.flow.lock.path.unlink()
        with self.assertRaises(NativeUIError):self.reopen()
        self.assertFalse(self.flow.lock.path.exists());self.assertEqual([],self.f.sdk_calls)


if __name__=='__main__':unittest.main()
