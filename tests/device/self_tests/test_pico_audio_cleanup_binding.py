"""Canonical cleanup selection with explicit native and PC SDK models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time,unittest
from pathlib import Path
from adapters.host_process_identity import host_identity
from adapters.pico4.audio_cleanup_profile import AudioCleanupBudget1
from adapters.script_journey.lock import ScriptSourceLock

class CanonicalCleanupBinding(unittest.TestCase):
    def setUp(self):
        from self_tests.test_pico_audio_pc_start_binding import AudioPCBindingTests
        self.fixture=AudioPCBindingTests();self.addCleanup(self.fixture.doCleanups);self.fixture.setUp()
        self.assertEqual(Path(__file__).resolve().parents[1]/'adapters/pico4/binding.py',
            Path(self.fixture.adapter._audio_pc_start_coordinator.__wrapped__.__code__.co_filename))
    def budget(self,*,run='a'*32,lock=None):
        f=self.fixture;binding=deepcopy(f.adapter._scripts(f.sdk.target).binding);began=time.monotonic()
        return AudioCleanupBudget1(dict(picoAudioCleanupProfileVersion=1,runId=run,binding=binding,
            hostProcessIdentity=host_identity(),startedMonotonic=began,deadlineMonotonic=began+120),
            f.lock if lock is None else lock)
    def test_actual_canonical_factory_attaches_original_cold_budget_and_coordinator_before_io(self):
        f=self.fixture;budget=self.budget();owner=f.make(cleanup_budget=budget);self.addCleanup(owner.actor.raws.close_host)
        self.assertIs(owner.actor.cleanup_budget,budget);self.assertIs(budget.actor,owner.actor)
        self.assertIs(budget.recipe,owner.recipe);self.assertIs(budget.lock,owner.lock)
        self.assertIs(budget.factory_hold,budget._original_factory_hold)
        self.assertEqual((owner,owner.recipe,owner.actor),budget.factory_hold)
        self.assertEqual([],f.sdk.inputs);self.assertEqual(2,len(f.calls));self.assertIsNone(budget.factory_failure)
        self.assertIsNone(owner.recipe.store.read());self.assertIsNone(owner.actor.native.instance)
    def test_invalid_optional_budget_type_and_wrong_run_refuse_before_pc_or_input(self):
        f=self.fixture
        for invalid in (False,1,{},object()):
            with self.subTest(kind=type(invalid).__name__),self.assertRaises(ValueError):f.make(cleanup_budget=invalid)
        budget=self.budget(run='c'*32)
        with self.assertRaises(ValueError):f.make(cleanup_budget=budget)
        self.assertEqual([],f.calls);self.assertEqual([],f.sdk.inputs)
        self.assertIsNone(budget.actor);self.assertIsNone(budget.recipe);self.assertIsNone(budget.factory_hold)
    def test_foreign_budget_lock_refuses_without_actor_or_coordinator_adoption(self):
        f=self.fixture;foreign=ScriptSourceLock(f.lock.path.with_name('foreign-cleanup.lock'));budget=self.budget(lock=foreign)
        with self.assertRaises(ValueError):f.make(cleanup_budget=budget)
        self.assertEqual([],f.calls);self.assertEqual([],f.sdk.inputs)
        self.assertIsNone(budget.actor);self.assertIsNone(budget.factory_hold)

    def test_existing_family_file_keeps_partial_actor_and_first_failure_without_retry(self):
        from adapters.normal_feature_state import PrivateFeatureState
        import gc
        f=self.fixture;budget=self.budget()
        path=f.lock.path.with_name('audio-recipe-pc-start.json')
        PrivateFeatureState(path).write({},None)
        with self.assertRaises(ValueError):f.make(cleanup_budget=budget)
        failure=budget.factory_failure
        self.assertTrue(budget.failed);self.assertIsNotNone(failure)
        actor,recipe=budget.actor,budget.recipe
        self.assertIsNotNone(actor);self.assertIs(actor.recipe,recipe)
        self.assertIsNone(budget.factory_hold);self.assertIsNotNone(failure[1])
        self.assertEqual({},PrivateFeatureState(path).read())
        self.assertEqual([],f.sdk.inputs);self.assertEqual([],f.calls)
        del recipe,actor;gc.collect()
        self.assertIs(budget.factory_failure,failure)
        with self.assertRaises(ValueError):f.make(cleanup_budget=budget)
        self.assertEqual([],f.calls);self.assertIs(budget.factory_failure,failure)
