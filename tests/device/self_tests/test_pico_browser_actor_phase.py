"""Actual phase/owner files and normal inputs; Native/VR remain declared models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from adapters.normal_ui import NativeUIError
from feature_journeys.phase_fixture import PhasePending
from feature_journeys.scenarios import VERSION
from self_tests import test_pico_tablet_web_stereo_flow as existing


class BrowserActorPhaseTests(unittest.TestCase):
    def fixture(self):
        h=existing.PicoTabletWebStereoFlowTests();h.setUp();self.addCleanup(h.doCleanups)
        f=h.fixture;f.activate();f.primary.prepare();return f

    def act(self,f,ticket,verb,inputs=None):
        return f.primary.act(dict(contractVersion=VERSION,runId=f.run,fixtureUrl=f.fixture_url,
            ticket=ticket,verb=verb,inputs=inputs or {}))

    def pending(self,f):
        history=f.actor.history_cache;before=None if history is None else history.store.path.read_bytes()
        commands=len(f.target.command_log)
        with self.assertRaises(PhasePending):f.actor.publish()
        self.assertEqual(commands,len(f.target.command_log))
        if before is not None:self.assertEqual(before,history.store.path.read_bytes())
        else:self.assertIsNone(f.actor.history_cache.store.read())
        self.assertIsNone(f.actor.actor_retirement)

    def test_new_actor_waits_before_first_source_intent_then_observes_actual_committed_open(self):
        f=self.fixture();f.actor.require_new_actor=True;ticket=f.activate('open')
        self.pending(f);self.assertFalse(f.actor._actor_started);self.assertIsNone(f.actor.role_store.read())
        self.act(f,ticket,'open');observed=f.actor.publish()
        self.assertTrue(observed['state']['open']);self.assertTrue(f.actor._actor_started)
        self.assertEqual('ready',f.actor.history_cache.disk['phase'])

    def test_warm_actor_keeps_original_ready_history_unchanged_during_announced_next_phase(self):
        f=self.fixture();baseline=f.actor.publish();ticket=f.activate('open')
        history=f.actor.history_cache;pin=history.chunks.signature(0)
        self.pending(f);self.assertEqual(pin,history.chunks.signature(0))
        self.act(f,ticket,'open');observed=f.actor.publish()
        self.assertGreater(observed['sequence'],baseline['sequence']);self.assertTrue(observed['state']['open'])

    def test_preexisting_unknown_source_is_never_reclassified_as_pending_or_replayed(self):
        f=self.fixture();f.actor.publish();history=f.actor.history_cache
        with f.target.lock.held():
            state=f.actor.role_state();history.begin('sample',state['sequence']+1)
        original=history.store.path.read_bytes();f.activate('open');commands=len(f.target.command_log)
        for _attempt in range(2):
            with self.assertRaises(NativeUIError):f.actor.publish()
            self.assertEqual(original,history.store.path.read_bytes())
            self.assertEqual(commands,len(f.target.command_log))
        self.assertEqual('reading',history.disk['phase'])

    def test_cleanup_activation_waits_for_actual_normal_cleanup_before_acquiring_another_sample(self):
        f=self.fixture();f.act('open');f.actor.publish();f.act('close');f.actor.publish()
        f.activate('cleanup');self.pending(f)
        f.primary.cleanup(dict(contractVersion=VERSION,runId=f.run));observed=f.actor.publish()
        self.assertFalse(observed['state']['open']);self.assertEqual([],observed['resources'])
        self.assertEqual('ready',f.actor.history_cache.disk['phase'])

    def test_committed_ignored_input_still_publishes_contradictory_actual_facts(self):
        f=self.fixture();f.act('open');f.actor.publish();f.target.fail='ignored-input'
        text='Overte ä Ω 東京 '+f.run;ticket=f.activate('focus-type',dict(text=text))
        self.pending(f);self.act(f,ticket,'focus-type',dict(text=text));observed=f.actor.publish()
        self.assertTrue(observed['state']['open']);self.assertEqual('',observed['state']['text'])
        self.assertNotEqual(text,observed['state']['text'])


if __name__=='__main__':unittest.main()
