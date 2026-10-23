"""A pending-only fast path cannot weaken immutable originals or admission."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUIError
from ios.self_tests.test_ios_avatar_postlogout_reads import AvatarPostLogoutReadsTests


class AvatarPostLogoutIncrementalTests(AvatarPostLogoutReadsTests):
    def test_incremental_mutable_candidate_observation_is_rechecked_without_becoming_an_immutable_original(self):
        from adapters.normal_feature_state import PrivateFeatureState
        journal=PrivateFeatureState(self.root/'installed-candidate-observation.json')
        journal.write(dict(candidate='a'*40,sequence=1),None);checks=[]
        owner=self.owner();original_guard=owner.guard;factory=owner.accounts_factory
        def bound():
            value=journal.read();self.assertEqual(value['candidate'],'a'*40);checks.append(value['sequence']);return original_guard()
        owner.guard=bound
        def accounts():
            value=journal.read();journal.write(dict(value,sequence=value['sequence']+1),value)
            return factory()
        owner.accounts_factory=accounts;first=owner.capture();owner.proof(first);second=owner.capture();owner.proof(second)
        self.assertGreater(max(checks),min(checks));self.assertEqual([1,2],[row['index'] for row in owner.state['rows']])

    def test_incremental_nested_original_reader_executes_live_candidate_guard_without_freezing_its_journal(self):
        from adapters.normal_feature_state import PrivateFeatureState
        journal=PrivateFeatureState(self.root/'original-reader-candidate-observation.json')
        journal.write(dict(candidate='a'*40,sequence=1),None);checks=[]
        owner=self.owner();guard=owner.guard;factory=owner.accounts_factory
        def bound():
            value=journal.read();self.assertEqual('a'*40,value['candidate']);checks.append(value['sequence']);return guard()
        owner.guard=bound;owner.originals.guard=bound
        def accounts():
            value=journal.read();journal.write(dict(value,sequence=value['sequence']+1),value);return factory()
        owner.accounts_factory=accounts
        first=owner.capture();owner.proof(first);before=len(checks)
        second=owner.capture();owner.proof(second)
        self.assertGreater(len(checks),before);self.assertGreater(max(checks),min(checks))
        self.assertEqual([1,2],[row['index'] for row in owner.state['rows']])

    def test_incremental_changed_candidate_seen_only_by_nested_original_guard_blocks_every_later_query(self):
        from adapters.native_feature_observation import need
        from adapters.normal_feature_state import PrivateFeatureState
        journal=PrivateFeatureState(self.root/'nested-original-candidate.json');journal.write(dict(candidate='a'*40),None)
        owner=self.owner();checks=[]
        def original_guard():
            actual=journal.read();checks.append(actual['candidate']);need(actual['candidate']=='a'*40);return True
        # The outer guard stays unchanged and deliberately knows nothing about
        # this boundary. Only the original reader can refuse this real change.
        owner.originals.guard=original_guard;owner.capture();calls=deepcopy(self.calls)
        journal.write(dict(candidate='b'*40),journal.read())
        with self.assertRaises(NativeUIError):owner.capture()
        self.assertEqual('b'*40,checks[-1]);self.assertEqual(calls,self.calls);self.assertIsNone(owner._pending_round)

    def test_incremental_changed_actual_candidate_still_fails_before_any_later_query(self):
        from adapters.native_feature_observation import need
        from adapters.normal_feature_state import PrivateFeatureState
        journal=PrivateFeatureState(self.root/'installed-candidate-observation.json');journal.write(dict(candidate='a'*40),None)
        owner=self.owner();original=owner.guard;factory=owner.accounts_factory;calls=[]
        def bound():need(journal.read()['candidate']=='a'*40);return original()
        owner.guard=bound
        def accounts():
            result=factory();value=journal.read();journal.write(dict(candidate='b'*40),value);calls.append(deepcopy(self.calls));return result
        owner.accounts_factory=accounts
        with self.assertRaises(NativeUIError):owner.capture()
        self.assertEqual(calls[-1],self.calls);self.assertIsNone(owner._pending_round)

    def test_incremental_old_row_change_is_rejected_before_the_next_transport(self):
        owner=self.owner();owner.capture();intent=owner.segments.intent;at_change=[]
        def actual(parent):
            if not at_change:
                at_change.append(deepcopy(self.calls));owner.state['rows'][0]['status']='abandoned'
            return intent(parent)
        owner.segments.intent=actual
        with self.assertRaises(NativeUIError):owner.capture()
        self.assertEqual(at_change[0],self.calls);self.assertIsNone(owner._pending_round)

    def test_incremental_nested_account_original_rewrite_precedes_another_query(self):
        owner=self.owner();first=owner.capture();before=owner.record(first)['before'];account=owner.accounts()
        path=account.originals.path(before['row']['original']);factory=owner.accounts_factory;at_change=[]
        def actual():
            result=factory()
            if not at_change:
                raw=path.read_bytes();path.write_bytes(raw);at_change.append(deepcopy(self.calls))
            return result
        owner.accounts_factory=actual
        with self.assertRaises(NativeUIError):owner.capture()
        self.assertEqual(at_change[0],self.calls);self.assertIsNone(owner._pending_round)

    def test_incremental_context_change_is_closed_before_another_query(self):
        owner=self.owner();owner.capture();factory=owner.accounts_factory;at_change=[]
        def actual():
            result=factory()
            if not at_change:
                owner.inputs['ticket']='d'*32;at_change.append(deepcopy(self.calls))
            return result
        owner.accounts_factory=actual
        with self.assertRaises(NativeUIError):owner.capture()
        self.assertEqual(at_change[0],self.calls);self.assertIsNone(owner._pending_round)

    def test_incremental_planned_absence_rechecks_a_new_dangling_symlink(self):
        owner=self.owner();intent=owner.segments.intent;lost=[]
        def interrupted(parent):
            intent(parent)
            if parent['label']=='parts' and parent['chunks'] and parent['chunks'][-1]['phase']=='planned' and not lost:
                lost.append(True);raise OSError('Actual planned carrier return lost')
        owner.segments.intent=interrupted
        with self.assertRaises(OSError):owner.capture()
        owner.segments.intent=intent;old=owner.recover();partial=owner.row_partial(old)
        path=owner.segments.store.path(partial['parts']['before']['chunks'][0]);factory=owner.accounts_factory;at_change=[]
        def actual():
            result=factory()
            if not at_change:
                path.symlink_to(path.with_name('missing-actual-original'));at_change.append(deepcopy(self.calls))
            return result
        owner.accounts_factory=actual
        with self.assertRaises(NativeUIError):owner.capture()
        self.assertEqual(at_change[0],self.calls);self.assertIsNone(owner._pending_round)

    def test_incremental_unsaved_pending_mutation_cannot_precede_a_query(self):
        owner=self.owner();owner.capture();factory=owner.accounts_factory;at_change=[]
        def actual():
            result=factory()
            if not at_change:
                owner.state['pending']['orphanPartials']=[{}];at_change.append(deepcopy(self.calls))
            return result
        owner.accounts_factory=actual
        with self.assertRaises(NativeUIError):owner.capture()
        self.assertEqual(at_change[0],self.calls);self.assertIsNone(owner._pending_round)

    def test_incremental_capture_reentry_cannot_issue_or_abandon_the_active_query(self):
        owner=self.owner();factory=owner.accounts_factory;at_reentry=[]
        def actual():
            if not at_reentry:
                at_reentry.append(deepcopy(self.calls));owner.capture()
            return factory()
        owner.accounts_factory=actual
        with self.assertRaises(NativeUIError):owner.capture()
        self.assertEqual(at_reentry[0],self.calls);self.assertIsNone(owner._pending_round)
        self.assertEqual([],owner.state['rows']);self.assertEqual({},owner.state['pending']['parts'])

    def test_incremental_external_proof_redecodes_older_row_metadata(self):
        owner=self.owner();first=owner.capture();second=owner.capture();owner.proof(second)
        # The selected second packet is unchanged. An unrelated older row is
        # not permission to reuse a previously computed whole-prefix verdict.
        owner.state['rows'][0]['status']='abandoned';calls=deepcopy(self.calls)
        with self.assertRaises(NativeUIError):owner.proof(second)
        self.assertEqual(calls,self.calls);self.assertEqual('observed',first['status'])


def load_tests(loader,tests,pattern):
    return unittest.TestSuite(AvatarPostLogoutIncrementalTests(name) for name in loader.getTestCaseNames(AvatarPostLogoutIncrementalTests)
        if name.startswith('test_incremental_'))


if __name__=='__main__':unittest.main()
