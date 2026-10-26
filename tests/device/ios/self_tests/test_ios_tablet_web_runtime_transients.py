"""Specific actual pending signals survive only normal checked lock release."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from adapters.normal_ui import NativeUIError
from adapters.phase_witness_publisher import PublicationPending
from feature_journeys.phase_fixture import PhasePending
from ios.adapters.tablet_web_runtime import TabletObservationPending
from ios.adapters.tablet_web_source_owner import TabletSourcePhaseChanged
from ios.self_tests import test_ios_tablet_web_runtime as runtime_tests


class TabletRuntimeTransientTests(unittest.TestCase):
    def setUp(self):
        self.fixture=runtime_tests.TabletWebRuntimeTests('test_actual_existing_admission_bootstrap_and_all_source_factories_without_app_or_session_mutation')
        self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
    def test_exact_phase_and_pending_instances_survive_checked_exit_and_issue_no_new_query_on_reentry(self):
        with self.fixture.opened():pass
        before=len(self.fixture.fixture.native.commands)
        for kind in (TabletSourcePhaseChanged,TabletObservationPending,PhasePending,PublicationPending):
            actual=kind('Actual returned transient');lock=None
            try:
                with self.fixture.opened() as observer:
                    lock=observer.observer.source.lock;raise actual
            except kind as received:self.assertIs(actual,received)
            else:self.fail('Actual transient was erased')
            with self.assertRaises(NativeUIError):lock.assert_held()
        self.assertEqual(before,len(self.fixture.fixture.native.commands))
    def test_changed_actual_lock_inode_mode_still_overrides_transient_and_cannot_authorize_retry(self):
        lock=None
        try:
            with self.assertRaises(NativeUIError):
                with self.fixture.opened() as observer:
                    lock=observer.observer.source.lock;lock.path.chmod(0o640)
                    raise TabletSourcePhaseChanged('Actual overlapping phase')
        finally:
            if lock is not None:lock.path.chmod(0o600)
    def test_arbitrary_source_error_is_still_closed_and_not_converted_to_pending(self):
        actual=ValueError('Unqualified source');lock=None;entered=[];queries=None
        with self.assertRaises(ValueError) as observed:
            with self.fixture.opened() as observer:
                lock=observer.observer.source.lock;queries=len(self.fixture.fixture.native.commands);entered.append(True)
                raise actual
        self.assertIs(actual,observed.exception);self.assertEqual([True],entered)
        with self.assertRaises(NativeUIError):lock.assert_held()
        self.assertEqual(queries,len(self.fixture.fixture.native.commands))
        with self.fixture.opened():pass
        self.assertEqual(queries,len(self.fixture.fixture.native.commands))


if __name__=='__main__':unittest.main()
