"""Actual private file/Parent ownership; host-clock policy is an explicit model."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import contextlib
import io
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from adapters.host_process_identity import host_identity
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4 import feature_observer
from adapters.pico4.browser_actor import run
from adapters.pico4.browser_actor_admission import BrowserActorAdmission, UNRESOLVED
from adapters.pico4.browser_execution_budget import BrowserExecutionBudget
from adapters.pico4.operation_host import process_identity


class BrowserActorAdmissionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='pico-browser-actor-budget-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name); self.root.chmod(0o700)
        self.clock = 100.
        self.value = dict(picoFeatureObserverVersion=6, area='tablet-web', target='synthetic',
            candidateArguments=['--apk', 'owned.apk'],
            fixtureUrl='http://127.0.0.1:32001/feature-fixture/v1',
            foreignFixtureUrl='http://127.0.0.1:32002/feature-fixture/v1',
            actorToken='b'*64, artifactRoot=str(self.root), durationSeconds=120,
            runId='a'*32, originalRequestId='c'*32,
            browserOwnerBudget=dict(id='d'*32, startedMonotonic=100., deadlineMonotonic=220.),
            browserParentHostProcessIdentity=process_identity(os.getppid()))
        self.store = PrivateFeatureState(self.root/'actor.json'); self.store.write(self.value, None)

    def create(self):
        owner = BrowserActorAdmission(self.store.path, self.value, monotonic=lambda:self.clock)
        self.addCleanup(lambda:self.assertTrue(owner.close_host()))
        self.addCleanup(lambda:UNRESOLVED.__setitem__(slice(None), [row for row in UNRESOLVED if row is not owner]))
        return owner

    def test_actual_original_configuration_and_parent_keep_the_same_unrenewable_deadline(self):
        owner = self.create(); self.assertEqual(100., owner.now())
        self.clock = 219.999; self.assertEqual(self.clock, owner.now())
        self.clock = 220.
        with self.assertRaises(NativeUIError): owner.now()
        self.clock = 101.
        with self.assertRaises(NativeUIError): owner.now()

    def test_same_bytes_configuration_replacement_is_not_an_original_owner(self):
        owner = self.create(); replacement = self.root/'foreign.json'
        replacement.write_bytes(self.store.path.read_bytes()); replacement.chmod(0o600)
        self.store.path.rename(self.root/'retained-original.json'); replacement.rename(self.store.path)
        with self.assertRaises(NativeUIError): owner.now()

    def test_current_parent_claim_cannot_change_to_this_actor_itself(self):
        value = dict(self.value, browserParentHostProcessIdentity=host_identity())
        with self.assertRaises(NativeUIError): BrowserActorAdmission(self.store.path, value, monotonic=lambda:self.clock)

    def test_configuration_six_is_explicit_and_old_four_rejects_new_budget_fields(self):
        self.assertEqual(self.value, feature_observer.configuration(self.store.path))
        previous = self.value
        for value in (dict(self.value, picoFeatureObserverVersion=4),
                dict(self.value, readerToken='e'*64),
                dict(self.value, browserOwnerBudget=dict(self.value['browserOwnerBudget'], deadlineMonotonic=221.))):
            self.store.write(value, previous); previous = value
            with self.assertRaises((ValueError, NativeUIError)): feature_observer.configuration(self.store.path)

    def test_new_actor_cannot_start_any_source_or_clock_without_its_actual_admission(self):
        calls = []
        with self.assertRaises(NativeUIError): run(object(), self.value, monotonic=lambda:calls.append('clock'))
        self.assertEqual([], calls)

    def test_legacy_actor_does_not_promote_an_injected_new_admission(self):
        calls = []
        with self.assertRaises(NativeUIError): run(object(), dict(self.value, picoFeatureObserverVersion=4),
            monotonic=lambda:calls.append('clock'), admission=self.create())
        self.assertEqual([], calls)

    def test_budget_replacement_failure_is_sticky_even_after_original_value_returns(self):
        owner = BrowserExecutionBudget(self.value['browserOwnerBudget'], monotonic=lambda:self.clock)
        changed = dict(owner.value, id='e'*32)
        with self.assertRaises(NativeUIError): owner.same(changed)
        with self.assertRaises(NativeUIError): owner.same(self.value['browserOwnerBudget'])

    def test_expired_whole_budget_refuses_before_opening_configuration_descriptors(self):
        self.clock = 220.
        with patch('adapters.pico4.browser_actor_admission.LifecycleProcessFile',
                side_effect=AssertionError('Expired policy must not open a source')):
            with self.assertRaises(NativeUIError): self.create()

    def test_real_main_closes_known_admission_pairs_when_cold_candidate_admission_fails(self):
        # The original real entrypoint runs; only candidate admission is the
        # explicit failing seam, before any SDK/device construction.
        value = deepcopy(self.value)
        import time
        start = time.monotonic(); value['browserOwnerBudget'].update(startedMonotonic=start, deadlineMonotonic=start+120)
        self.store.write(value, self.value)
        closed = []; original = BrowserActorAdmission.close_host
        def close(owner):
            result = original(owner); closed.append((owner, result)); return result
        with patch('adapters.android.adapter.cli', side_effect=ValueError('Declared cold candidate refusal')), \
                patch.object(BrowserActorAdmission, 'close_host', close), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(2, feature_observer.main(['--config', str(self.store.path)]))
        self.assertEqual(1, len(closed)); owner, success = closed[0]
        self.assertTrue(success); self.assertTrue(owner.file.parent.closed); self.assertTrue(owner.file.file.closed)


if __name__ == '__main__':
    unittest.main()
