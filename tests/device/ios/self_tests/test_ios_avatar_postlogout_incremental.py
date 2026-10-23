"""A pending-only fast path cannot weaken immutable originals or admission."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUIError
from ios.self_tests.test_ios_avatar_postlogout_reads import AvatarPostLogoutReadsTests


class AvatarPostLogoutIncrementalTests(AvatarPostLogoutReadsTests):
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
