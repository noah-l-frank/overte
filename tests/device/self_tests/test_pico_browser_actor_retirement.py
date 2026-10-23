"""Actual private Actor exit and journals; native/VM/SDK producers are seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from contextlib import contextmanager
import unittest
from unittest.mock import patch

from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_journey.lock import ScriptSourceLock
from adapters.script_journey.history import canonical
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
        from adapters.pico4.browser_actor_retirement import validate_original_frame
        frame=json.loads(owner.raw);queries=len(f.target.command_log);active=owner.history.last
        def check(value):return validate_original_frame(value,owner.owner,owner.state,owner.anchor,owner.vm.origin,active,
            run=f.run,fixture_url=f.actor.fixture_url)
        self.assertIs(frame,check(frame))
        mutations=(
            ('lifecycle',lambda row:row['nativeBefore']['lifecycle'].__setitem__('activations',row['nativeBefore']['lifecycle']['activations']+1)),
            ('old-native-request',lambda row:row['nativeBefore'].__setitem__('requestId',active['nativeAfter']['requestId'])),
            ('foreign-pid',lambda row:row['nativeAfter'].__setitem__('processId',row['nativeAfter']['processId']+1)),
            ('active-phase',lambda row:row['phaseAfter'].__setitem__('active',True)),
            ('old-script-request',lambda row:row['scripts'].__setitem__('requestId',owner.anchor['scripts']['requestId'])),
            ('replaced-http-anchor',lambda row:row.__setitem__('compiledHttpAnchor',{})),
            ('late-originals',lambda row:row.__setitem__('finishedEpoch',row['finishedEpoch']+2000)),
            ('backwards-host',lambda row:row.__setitem__('startedHost',row['finishedHost']+1)),
        )
        for name,mutate in mutations:
            with self.subTest(original=name):
                counter=deepcopy(frame);mutate(counter)
                with self.assertRaises((NativeUIError,ValueError)):check(counter)
        self.assertEqual(queries,len(f.target.command_log))
        from adapters.pico4.browser_actor_graph import PicoBrowserActorExport,PicoBrowserActorGraph
        from adapters.native_script_observation import original_history
        scripts=[frame['scripts'] for frame in owner.vm.frames]+[frame['scripts']]
        pure=original_history(scripts,owner.vm.scripts.pid)
        self.assertFalse(hasattr(pure,'send') or hasattr(pure,'guard'))
        for name in ('instance','sequence'):
            counter=deepcopy(scripts)
            counter[-1][name]='f'*32 if name=='instance' else counter[-2]['sequence']
            with self.assertRaises(NativeUIError):original_history(counter,owner.vm.scripts.pid)
        exported=PicoBrowserActorExport(owner,'d'*32)
        self.assertTrue(exported.verify());self.assertEqual(queries,len(f.target.command_log))
        with f.actor.lock.held():
            cold=PicoBrowserActorGraph(exported.raw,exported.source_stamp,exported.store,exported.stores,f.actor.lock,exported.expected)
            cold.verify();self.assertEqual(owner.raw,canonical(cold.inactive))
        self.assertIsNone(getattr(cold,'adapter',None));self.assertIsNone(getattr(cold,'source',None))
        with self.assertRaises(NativeUIError):PicoBrowserActorExport(owner,'e'*32)
        # A byte-identical replacement is a different original physical file.
        child=owner.history.chunks.store(0).path;replacement=child.with_name('changed-export-original.json')
        replacement.write_bytes(child.read_bytes());replacement.chmod(0o600);replacement.replace(child)
        with self.assertRaises(NativeUIError):exported.verify()
        self.assertTrue(child.exists());self.assertEqual(queries,len(f.target.command_log))
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
