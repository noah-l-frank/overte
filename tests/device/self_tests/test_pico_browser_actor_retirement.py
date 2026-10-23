"""Actual private Actor exit and journals; native/VM/SDK producers are seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from contextlib import contextmanager
import unittest
from unittest.mock import patch

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_journey.lock import ScriptSourceLock
from feature_journeys.phase_fixture import PhaseRetired
from feature_journeys.scenarios import VERSION
from self_tests import test_pico_tablet_web_stereo_flow as seams


class PicoBrowserActorRetirementTests(unittest.TestCase):
    def setUp(self):
        base=seams.PicoTabletWebStereoFlowTests();base.setUp();self.addCleanup(base.doCleanups)
        self.f=base.fixture

    def baseline(self):
        f=self.f;f.activate();f.primary.prepare();f.act('open');f.actor.publish();f.act('close')
        f.activate('cleanup');f.primary.cleanup(dict(contractVersion=VERSION,runId=f.run))
        for _ in range(14):f.actor.publish();f.clock.sleep(.25)
        with f.actor.lock.held():
            state=f.actor.role_state();self.assertTrue(state['quiet']['complete'])
            self.active=deepcopy(state);self.history=f.actor.source_history(f.actor.owner())
            self.history.matches(state)
        self.count=len(f.target.command_log);self.role_bytes=f.actor.role_store.path.read_bytes()
        f.client.close()

    def test_actual_inactive_exit_preserves_active_history_and_collects_fresh_retired_originals(self):
        self.baseline();f=self.f
        with self.assertRaises(PhaseRetired):f.actor.publish()
        owner=f.actor.actor_retirement;self.assertTrue(owner.completed)
        self.assertEqual('ready',owner.receipt()['phase']);self.assertEqual(self.role_bytes,f.actor.role_store.path.read_bytes())
        with f.actor.lock.held():self.history.matches(f.actor.role_state())
        self.assertNotIn(f.run,f.server.browser_resources.runs);self.assertTrue(owner.store.path.exists())
        self.assertTrue(all(row['operation']=='observe' for row in f.target.command_log[self.count:]))
        with self.assertRaises((ValueError,RuntimeError)):f.primary.finalize()
        owner.state['sequence']+=1
        with self.assertRaises((ValueError,RuntimeError)):owner.receipt()

    def retained(self):
        f=self.f;owner=f.actor.actor_retirement
        self.assertFalse(owner.completed);self.assertTrue(owner.failed);self.assertTrue(owner.store.path.exists())
        with self.assertRaises((ValueError,RuntimeError)):owner.receipt()
        self.assertEqual(self.role_bytes,f.actor.role_store.path.read_bytes())
        with f.actor.lock.held():self.history.matches(f.actor.role_state())
        before=len(f.target.command_log)
        cold=f.flow(f.actor.source.client,'actor')
        with self.assertRaises((ValueError,RuntimeError)):cold.publish()
        self.assertEqual(before,len(f.target.command_log))

    def test_native_live_worker_after_inactive_phase_never_qualifies_actor_exit(self):
        self.baseline();f=self.f
        f.target.vm.objects.row.update(workerAlive=True,workerDestroyedEpochMs=0)
        with self.assertRaises((ValueError,RuntimeError)):f.actor.publish()
        self.assertEqual('reading',f.actor.actor_retirement.store.read()['phase']);self.retained()

    def late_cas(self,phase):
        self.baseline();f=self.f;write=PrivateFeatureState.write;fired=[]
        def late(store,value,previous):
            write(store,value,previous)
            if store.path.name=='pico-tablet-web-actor-retirement.json' and value['phase']==phase:
                fired.append(True);f.clock.base+=2000
        with patch.object(PrivateFeatureState,'write',late),self.assertRaises((ValueError,RuntimeError)):f.actor.publish()
        self.assertEqual([True],fired);self.assertEqual(phase,f.actor.actor_retirement.store.read()['phase'])
        if phase=='reading':self.assertEqual(self.count,len(f.target.command_log))
        self.retained()

    def test_original_intent_cas_native_jump_cannot_acquire_new_sources(self):self.late_cas('reading')

    def test_original_ready_cas_native_jump_cannot_authorize_exit_or_cold_adoption(self):self.late_cas('ready')

    def test_actual_source_lock_exit_cost_cannot_escape_original_final_clocks(self):
        self.baseline();f=self.f;held=ScriptSourceLock.held;fired=[]
        @contextmanager
        def late(lock):
            with held(lock):yield
            owner=f.actor.actor_retirement
            if lock is f.actor.lock and owner is not None and owner.previous is not None and owner.previous['phase']=='ready' and not fired:
                fired.append(True);f.clock.base+=2000
        with patch.object(ScriptSourceLock,'held',late),self.assertRaises((ValueError,RuntimeError)):f.actor.publish()
        self.assertEqual([True],fired);self.retained()

    def test_same_byte_active_chunk_replacement_after_final_target_guard_is_retained(self):
        self.baseline();f=self.f;runtime=f.actor.runtime;fired=[]
        def replaced(owner):
            result=runtime(owner);retirement=f.actor.actor_retirement
            if retirement is not None and retirement.previous is not None and retirement.previous['phase']=='ready' and not fired:
                fired.append(True);child=self.history.chunks.store(0).path
                replacement=child.with_name('late-original-replacement');replacement.write_bytes(child.read_bytes())
                replacement.chmod(0o600);replacement.replace(child)
            return result
        with patch.object(f.actor,'runtime',side_effect=replaced),self.assertRaises((ValueError,RuntimeError)):f.actor.publish()
        self.assertEqual([True],fired);self.assertFalse(f.actor.actor_retirement.completed)
        self.assertTrue(f.actor.actor_retirement.store.path.exists());self.assertEqual(self.role_bytes,f.actor.role_store.path.read_bytes())


if __name__=='__main__':unittest.main()
