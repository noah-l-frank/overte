"""Real Parent/archive methods on explicit Pico/native/input identity seams.

No full restart or archive repetition: only the new warm baseline and complete
original catalog extension run. Native/V8/SDK/Pico parent identity are seams.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from types import SimpleNamespace
import unittest

from adapters.chat_journey.evidence_archive import ChatArchiveCatalog
from adapters.chat_journey.observation import ChatObservationOwner
from adapters.chat_journey.source_seal import ChatSourceSeal
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4.chat_archive import PicoChatArchivePlan
from adapters.pico4.chat_composition import PicoChatComposition
from adapters.pico4.chat_cleanup_witness import PicoChatCleanupWitness
from adapters.script_journey.lock import ScriptSourceLock
from self_tests import test_chat_cleanup_baseline as seams
from self_tests import test_chat_cleanup_witness as witness_seams


class ChatBaselineCompositionTests(unittest.TestCase):
    def setUp(self):
        if self._testMethodName=='test_parent_releases_its_actual_flock_before_independent_actor_factory_then_consumes_baseline':
            fixture=witness_seams.ChatCleanupWitnessTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
            self.h=SimpleNamespace(h=fixture,primary=fixture.observers['primary'],actor=fixture.publisher,
                store=PrivateFeatureState(fixture.root/'baseline.json'),seals=tuple(SimpleNamespace(
                    store=PrivateFeatureState(fixture.root/('baseline-'+role+'-seal.json'))) for role in ('primary','actor')))
            request=fixture.h.w.actor.request
            def received(path,*args,**kwargs):
                return fixture.h.w.journal.snapshot(fixture.original.source.run) if path=='/runs/'+fixture.original.source.run else request(path,*args,**kwargs)
            fixture.h.w.actor.request=received;return
        self.h=seams.ChatCleanupBaselineTests();self.h.setUp();self.addCleanup(self.h.doCleanups)

    def plan(self):
        h=self.h;owner=h.owner
        parent=SimpleNamespace(cleanup_baseline=owner,cleanup_baseline_receipt=owner.previous,
            cache_release=SimpleNamespace(roles=(h.primary.samples,)),source=h.primary.source,
            binding=h.primary.samples.binding,peer=SimpleNamespace(binding=h.primary.samples.peer_binding))
        adapter=SimpleNamespace(_chat_cleanup_baseline_store=lambda _target:h.store,
            _chat_cleanup_source_seal_store=lambda _target,*,witness:h.seals[int(witness)].store)
        plan=PicoChatArchivePlan.__new__(PicoChatArchivePlan);plan.parent=parent;plan.adapter=adapter;plan.target='projected-pico'
        plan.state=h.h.root/'projected-script-state.json';plan.peer_directory=h.h.root/'peer'
        plan.catalog=ChatArchiveCatalog(hold_files=False);self.addCleanup(plan.catalog.close_host);return plan

    def test_complete_new_baseline_source_and_seal_roots_and_chunks_join_actual_original_catalog(self):
        self.h.owner.run(self.h.h.native.epoch);plan=self.plan();metadata=plan.add_cleanup_baseline()
        plan.catalog.verify_all();self.assertEqual(2,len(metadata['chatCleanupSourceSeals']))
        expected={self.h.store.path}
        for index,seal in enumerate(self.h.seals):
            expected.add(seal.store.path)
            for owner in seal.owners:
                expected.add(owner.store.path)
                expected.update(owner.history.store(i).path for i in range(len(owner.history.identities)))
        expected.update(self.h.owner.history.store(i).path for i in range(len(self.h.owner.history.identities)))
        self.assertEqual(expected,{row['store'].path for row in plan.catalog.rows.values()})
        self.assertTrue(all(path.exists() for path in expected));self.assertGreater(len(expected),50)

    def test_identical_root_replacement_after_received_seal_before_catalog_capture_is_refused(self):
        self.h.owner.run(self.h.h.native.epoch);plan=self.plan();add=plan.add_owner;source=self.h.primary.samples;fired=[]
        def replaced(owner):
            if owner is source and not fired:
                fired.append(True);source.store.write(source.previous,source.previous)
            return add(owner)
        plan.add_owner=replaced
        with self.assertRaises(NativeUIError):plan.add_cleanup_baseline()
        self.assertEqual([True],fired);self.assertTrue(self.h.store.path.exists());self.assertTrue(source.store.path.exists())

    def test_parent_releases_its_actual_flock_before_independent_actor_factory_then_consumes_baseline(self):
        h=self.h;source=h.h.observers['primary'].source;target='projected-pico'
        # This fixture has no prior seal callbacks: Parent constructs the
        # actual first owner graph without resetting/adopting any old guard.
        source_sample=h.primary.samples;actor=h.actor;checked=[];seals={}
        parent=PicoChatComposition.__new__(PicoChatComposition)
        parent.failed=False;parent.target=target;parent.source=source;parent.lock=source_sample.locks[0]
        parent.peer=SimpleNamespace(lock=source_sample.locks[1]);parent.cache_release=SimpleNamespace(defer_ipc=True,roles=(source_sample,))
        parent.previous=dict(phase='caches-retired');parent.native=SimpleNamespace(sleep=h.h.h.sleep)
        parent.guard=lambda:True
        def observation(_target,actual_source,samples,**_kwargs):
            return ChatObservationOwner(actual_source,samples,h.h.h.flow.store,h.primary.store,stage='cleanup',
                cleanup_store=h.h.admission.store,monotonic=lambda:h.h.native.host)
        def seal(_target,owner,*,witness):
            if witness:
                # A genuinely separate owner at each same OS inode would
                # contend if Parent.held were incorrectly still active.
                for lock in source_sample.locks:
                    with ScriptSourceLock(lock.path,timeout=.05).held():checked.append(lock.path)
            value=ChatSourceSeal(owner,h.seals[int(witness)].store);seals[int(witness)]=value;return value
        parent.adapter=SimpleNamespace(_chat_observation=observation,_chat_source_seal=seal,
            _chat_cleanup_baseline_store=lambda _target:h.store)
        independent=PicoChatCleanupWitness.__new__(PicoChatCleanupWitness)
        independent.adapter=parent.adapter;independent.target=target;independent.parent_value=deepcopy(parent.previous);independent.publisher=actor
        value=parent.measure_cleanup_baseline(independent,h.h.native.epoch)
        self.assertEqual([lock.path for lock in source_sample.locks],checked);self.assertFalse(parent.failed)
        self.assertEqual(value,parent.cleanup_baseline_receipt);self.assertEqual('complete',value['stage'])
        self.assertTrue(all(value.completed for value in seals.values()))


if __name__=='__main__':unittest.main()
