"""Real initial Worlds publication and modeled worker-only seal scheduling.

The scheduling cases do not qualify a live seal or final process/SDK evidence.
The separate connected journey must qualify the actual terminal owner graph.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import Mock,patch
from adapters.normal_feature_state import PrivateFeatureState
from ios import navigation_observer as worker
from ios.self_tests import test_ios_navigation_whole_feature as fixture


class NavigationWorkerConfigurationTests(unittest.TestCase):
    def test_private_configuration_has_only_actor_authority_and_existing_candidate_arguments(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);root=Path(temporary.name)
        value=dict(iosNavigationObserverWorkerVersion=1,target='owned',runId='a'*32,
            candidateArguments=['--artifact-root','/private/candidate'],fixtureUrl='http://127.0.0.1:12345/feature-fixture/v1',
            actorToken='a'*64,durationSeconds=30,artifactRoot=str(root))
        store=PrivateFeatureState(root/'config.json');store.write(value,None);self.assertEqual(value,worker.configuration(store.path))
        for changed in (dict(iosNavigationObserverWorkerVersion=True),dict(readerToken='b'*64),dict(candidateArguments=[]),
                        dict(artifactRoot='relative'),dict(target='a/b'),dict(durationSeconds=True),dict(durationSeconds=0)):
            store.write(value|changed,store.read())
            with self.assertRaises((RuntimeError,ValueError,TypeError)):worker.configuration(store.path)


class NavigationWorkerTests(unittest.TestCase):
    actor=fixture.NavigationWholeFeatureTests.actor
    setUp=fixture.NavigationWholeFeatureTests.setUp

    def owned(self):
        self.whole.prepare();self.peer=self.actor();self.config=dict(target='owned',durationSeconds=30)
        return self.peer

    def modeled_terminal(self,*,sealed):
        return SimpleNamespace(state=dict(seal={'modeledSeal':True}) if sealed else None,finish=Mock())

    def test_actual_actor_publication_retains_own_source_and_real_canonical_receipt(self):
        peer=self.owned();before=deepcopy(self.h.flow.store.read())
        self.assertIsNone(worker.step(peer,self.config))
        with peer.flow.held():
            peer.flow.load();observer=peer.flow.observer();self.assertEqual(1,observer.state['sequence'])
            publications=peer.flow.publications(observer);self.assertIsNone(publications.state()['pending'])
            self.assertTrue(publications.state()['records']);self.assertFalse(worker.failure(peer.flow,self.config))
        self.assertEqual(before,self.h.flow.store.read())

    def test_sealed_pause_does_not_acquire_or_publish_or_refresh_failure_marker(self):
        peer=self.owned();terminal=self.modeled_terminal(sealed=True);before=deepcopy(peer.flow.store.read())
        with (patch.object(worker,'NavigationTerminal',return_value=terminal),patch.object(peer,'publish',side_effect=AssertionError('Sealed publication')),
             patch.object(peer.flow.runtime,'_sources',side_effect=AssertionError('Sealed source')),
             patch.object(peer.flow.client,'request',side_effect=AssertionError('Sealed HTTP'))):
            self.assertIsNone(worker.step(peer,self.config));self.assertIsNone(worker.step(peer,self.config))
        terminal.finish.assert_not_called();self.assertEqual(before,peer.flow.store.read())
        self.assertIsNone(PrivateFeatureState(peer.flow.store.path.with_name('ios-navigation-worker-failure.json')).read())

    def test_unknown_publication_failure_survives_reconstruction_and_final_receipt(self):
        peer=self.owned();unsealed=self.modeled_terminal(sealed=False)
        with patch.object(worker,'NavigationTerminal',return_value=unsealed),patch.object(peer,'publish',side_effect=RuntimeError('Unknown publication return')):
            self.assertIsNone(worker.step(peer,self.config))
        with peer.flow.held():self.assertTrue(worker.failure(peer.flow,self.config))
        terminal=self.modeled_terminal(sealed=True);archive=PrivateFeatureState(peer.flow.store.path.with_name('ios-navigation-final-archive.json'))
        archive.write({'modeledHistoricalEnd':True},None)
        with patch.object(worker,'NavigationTerminal',return_value=terminal),patch.object(peer,'publish',side_effect=AssertionError('Sealed publication')):
            self.assertEqual(2,worker.step(peer,self.config))
        terminal.finish.assert_called_once_with(terminal.state['seal'])

    def test_existing_archive_requires_actual_terminal_verifier_success(self):
        peer=self.owned();terminal=self.modeled_terminal(sealed=True);terminal.finish.side_effect=RuntimeError('Rejected original end')
        PrivateFeatureState(peer.flow.store.path.with_name('ios-navigation-final-archive.json')).write({'model':True},None)
        with patch.object(worker,'NavigationTerminal',return_value=terminal):
            self.assertEqual(2,worker.run_flow(peer,self.config,monotonic=lambda:1,sleep=lambda _seconds:None))
        terminal.finish.assert_called_once();self.assertIsNone(PrivateFeatureState(peer.flow.store.path.with_name('ios-navigation-worker-failure.json')).read())

    def test_timeout_and_clock_regression_retain_graph_without_publication_or_end(self):
        peer=self.owned();before=deepcopy(peer.flow.store.read())
        for values in ([1,31],[1,0]):
            clock=iter(values)
            with patch.object(worker,'step',side_effect=AssertionError('Expired worker step')):
                self.assertEqual(2,worker.run_flow(peer,self.config,monotonic=lambda:next(clock),sleep=lambda _seconds:None))
        self.assertEqual(before,peer.flow.store.read())


if __name__=='__main__':unittest.main()
