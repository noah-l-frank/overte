"""Current lease dataflow keeps literal historical Scope and file guards.

Script/Node, original files and normal marker input run. Native/Qt/WK/SDK
remain explicit models; no terminal or real CPU qualification is supplied.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.original_file_reads import scope as read_scope
from ios.adapters.world_web_identity import WorldWebLease
from ios.adapters.world_web_observer import WorldWebObserver
from ios.adapters.world_web_scope import IOSWorldWebScope
from ios.adapters.world_web_scope_archive import original_round
from ios.self_tests.world_web_whole_fixture import ComposedWorldWeb


class WorldWebObserverCurrentScopeTests(unittest.TestCase):
    def setUp(self):
        self.whole=whole=ComposedWorldWeb(use_whole_snapshot=True);self.addCleanup(whole.close)
        source,scope=whole.source,whole.scope;before=source.capture('before-owned-load')
        scope.prepare();scope.admit_rendered();after=source.capture('after-owned-load')
        self.lease=WorldWebLease(scope,source,before,after)
        self.observer=WorldWebObserver(PrivateFeatureState(scope.root/'ios-world-web-primary-observer.json'),source,
            whole.sdk.origins,lambda:True,lease=self.lease)
        self.reference,self.expected=self.observer.capture()

    def test_current_exact_scope_reuses_the_already_validated_lease_without_outward_aliases(self):
        observer,lease=self.observer,self.lease;queries=deepcopy(self.whole.sdk.counts)
        with observer.validation_round():
            with patch.object(IOSWorldWebScope,'archive',side_effect=AssertionError('Same current Scope decoded a second time')):
                self.assertEqual(self.expected,observer.validate_original(self.reference))
                projected=lease.scope_state();projected['phase']='unqualified-outward-mutation'
                self.assertEqual('ready',lease.scope_state()['phase'])
                self.assertEqual(self.expected,observer.validate_original(self.reference))
        self.assertEqual(queries,self.whole.sdk.counts)

    def test_actual_older_scope_still_executes_its_literal_reader_after_current_cleanup(self):
        self.whole.sdk.activate('cleanup',{});self.whole.scope.cleanup()
        self.assertEqual('released',self.whole.scope.state['phase'])
        queries=deepcopy(self.whole.sdk.counts);observer=self.observer;archive=IOSWorldWebScope.archive
        with observer.validation_round():
            with patch.object(IOSWorldWebScope,'archive',wraps=archive) as literal:
                self.assertEqual(self.expected,observer.validate_original(self.reference))
                self.assertGreaterEqual(literal.call_count,1)
                self.assertTrue(any(call.args[0]==observer.entries()[0]['scope'] for call in literal.call_args_list))
        self.assertEqual(queries,self.whole.sdk.counts)

    def test_new_actual_file_census_executes_literal_scope_and_cannot_inherit_old_membership(self):
        observer=self.observer;archive=IOSWorldWebScope.archive;queries=deepcopy(self.whole.sdk.counts)
        with observer.validation_round():
            self.assertEqual(self.expected,observer.validate_original(self.reference))
            for _attempt in range(2):
                with read_scope(fresh=True) as reads,patch.object(IOSWorldWebScope,'archive',wraps=archive) as literal:
                    self.assertEqual(self.expected,observer.validate_original(self.reference));self.assertGreaterEqual(literal.call_count,1)
                    self.assertTrue(any(path.name.startswith('world-web-frame-inputs-') for path in reads))
                    count=literal.call_count;originals=set(reads)
                    self.assertEqual(self.expected,observer.validate_original(self.reference))
                    self.assertEqual(count,literal.call_count);self.assertEqual(originals,reads)
        self.assertEqual(queries,self.whole.sdk.counts)

    def test_actual_source_append_does_not_turn_unrelated_mutable_head_into_a_scope_pin(self):
        source=self.whole.source;scope=self.whole.scope
        with read_scope(fresh=True) as reads,original_round():
            source.frame(source.state['records'][-1]);self.assertIn(source.store.path,reads)
            original=self.lease.packet();before=source.store.path.stat().st_ino
            source.capture('actual-after-scope-proof')
            self.assertNotEqual(before,source.store.path.stat().st_ino)
            self.assertEqual(original,self.lease.packet())
            self.assertTrue(any(path.name.startswith('world-web-frame-inputs-') for path in reads))
            self.assertEqual('ready',scope.state['phase'])


if __name__=='__main__':unittest.main()
