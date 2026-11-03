"""Packed-memory admission and actual journal-CAS failure boundaries.

The small host models exercise the original owning methods and filesystem;
they grant no Native, recipe, restoration or whole-flow qualification.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from adapters.chat_journey.source_chunks import json_digest
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4.navigation_generation_flow import NavigationGenerationFlow
from adapters.pico4.navigation_generation_restoration import NavigationGenerationRestoration
from adapters.pico4.navigation_originals import read_original
from adapters.pico4.navigation_restart import NavigationRestart
from adapters.pico4.navigation_scene_relation import NavigationMemoryRelation
from adapters.script_journey.history import pack,same


class NavigationSceneRelationTests(unittest.TestCase):
    def example(self):
        state=dict(phase='ready',binding=dict(processIdentity='31:10001'),rows=[dict(sequence=1,ready=True)])
        return dict(payload=pack([state])),state

    def test_original_relation_is_admitted_once_then_never_unpacked_again(self):
        disk,state=self.example()
        from adapters.pico4 import navigation_scene_relation as source
        original=source.unpack
        with patch.object(source,'unpack',wraps=original) as unpacked:
            seal=NavigationMemoryRelation(disk,state)
            for _ in range(5):seal.require(disk,state)
        self.assertEqual(1,unpacked.call_count)

    def test_equal_graph_substitution_is_refused_on_both_sides(self):
        disk,state=self.example();seal=NavigationMemoryRelation(disk,state)
        for left,right in ((deepcopy(disk),state),(disk,deepcopy(state))):
            with self.assertRaises(NativeUIError):seal.require(left,right)

    def test_payload_swap_cannot_reseal_a_coherently_changed_state(self):
        disk,state=self.example();seal=NavigationMemoryRelation(disk,state)
        state['phase']='acting';disk['payload']=pack([state])
        with self.assertRaises(NativeUIError):seal.require(disk,state)

    def test_nested_mutation_tuple_boolean_and_subclass_aliases_are_refused(self):
        class Foreign(dict):pass
        for mutation in (lambda v:v['rows'][0].update(sequence=2),
                         lambda v:v.update(rows=tuple(v['rows'])),
                         lambda v:v['rows'][0].update(ready=1),
                         lambda v:v.update(binding=Foreign(v['binding']))):
            with self.subTest(mutation=mutation):
                disk,state=self.example();seal=NavigationMemoryRelation(disk,state);mutation(state)
                with self.assertRaises(NativeUIError):seal.require(disk,state)

    def test_nonfinite_foreign_key_and_wrong_relation_fail_at_admission(self):
        disk,state=self.example();state['phase']='foreign'
        with self.assertRaises(NativeUIError):NavigationMemoryRelation(disk,state)
        for value in (dict(value=float('nan')),{1:'foreign-key'}):
            with self.assertRaises((NativeUIError,ValueError,TypeError)):NavigationMemoryRelation(dict(payload=pack([value])),value)

    def test_equal_seal_tuple_replacement_is_refused(self):
        disk,state=self.example();seal=NavigationMemoryRelation(disk,state)
        seal.seal=tuple(item for item in seal.seal)
        with self.assertRaises(NativeUIError):seal.require(disk,state)

    def restart(self):
        root=Path(tempfile.mkdtemp(prefix='pico-navigation-relation-'));os.chmod(root,0o700)
        self.addCleanup(lambda:print('Retained Navigation relation filesystem fixture:',root))
        owner=NavigationRestart.__new__(NavigationRestart)
        owner.parent=SimpleNamespace();owner.store=PrivateFeatureState(root/'navigation-prefix-restart.json')
        owner.run='a'*32;owner.binding=dict(processIdentity='31:10001');owner.scope_sha='1'*64
        owner._scene_relation_owner=object();owner._scene_relation=owner._original_scene_relation=None
        owner._scene_relation_failed=False
        owner.state=owner.disk=None
        # Deliberately host-only CAS unit model: complete Native/source
        # validation belongs to the separate existing owning journeys.
        owner.validate=lambda value:self.assertEqual('ready',value['phase'])
        self.enterContext(patch('adapters.pico4.navigation_scene_generation.scene_owner',return_value=owner._scene_relation_owner))
        return owner

    def test_actual_successful_cas_readback_installs_only_new_admitted_relation(self):
        owner=self.restart();value=dict(phase='ready',sequence=1);owner.save(value)
        old=owner._scene_relation;owner.memory_relation();owner.save(dict(phase='ready',sequence=2))
        self.assertIsNot(old,owner._scene_relation);owner.memory_relation()
        self.assertTrue(same(owner.store.read(),owner.disk))

    def test_actual_load_admits_once_and_cannot_adopt_arbitrary_later_graphs(self):
        owner=self.restart();owner.save(dict(phase='ready',sequence=1))
        loaded=NavigationRestart.__new__(NavigationRestart);loaded.__dict__.update(owner.__dict__)
        loaded.disk=loaded.state=loaded._scene_relation=loaded._original_scene_relation=None
        loaded.load();loaded.memory_relation()
        self.assertIsNot(owner.disk,loaded.disk);self.assertIsNot(owner.state,loaded.state)
        loaded.state['sequence']=2;old=loaded._scene_relation
        with self.assertRaises(NativeUIError):loaded.load()
        self.assertIs(old,loaded._scene_relation);self.assertEqual(2,loaded.state['sequence'])

    def test_actual_primary_cas_can_advance_original_actor_typed_load(self):
        for cls in (NavigationRestart,NavigationGenerationFlow):
            with self.subTest(owner=cls.__name__):
                seed=self.restart();primary=cls.__new__(cls);primary.__dict__.update(seed.__dict__)
                primary.scope=lambda:dict(runId=seed.run);primary.control=primary.memory_control=lambda:None
                primary.save(dict(phase='ready',sequence=1))
                actor=cls.__new__(cls);actor.__dict__.update(primary.__dict__)
                actor.disk=actor.state=actor._scene_relation=actor._original_scene_relation=None
                actor.load();original=actor._scene_relation
                primary.save(dict(phase='ready',sequence=2))
                self.assertFalse(same(actor.disk,actor.store.read()));actor.memory_relation()
                actor.load();actor.memory_relation()
                self.assertEqual(2,actor.state['sequence']);self.assertIsNot(original,actor._scene_relation)

    def test_unknown_actual_first_cas_cannot_load_or_reseal_failed_owner(self):
        for cls in (NavigationRestart,NavigationGenerationFlow,NavigationGenerationRestoration):
            with self.subTest(owner=cls.__name__):
                seed=self.restart();owner=cls.__new__(cls);owner.__dict__.update(seed.__dict__)
                owner.packet_version=2
                owner.scene_owner=seed._scene_relation_owner;owner.scope=lambda:dict(runId=seed.run)
                owner.control=owner.memory_control=owner.host=lambda:None
                write=owner.store.write
                def unknown(value,previous):write(value,previous);raise RuntimeError('first CAS reply lost')
                with patch.object(owner.store,'write',side_effect=unknown):
                    with self.assertRaises(RuntimeError):
                        owner.save(dict(phase='ready',sequence=1),**({} if cls is NavigationRestart else dict(host_only=True)))
                self.assertTrue(owner._scene_relation_failed);self.assertIsNone(owner._scene_relation)
                retained=owner.store.path.read_bytes()
                with patch.object(owner.store,'read',wraps=owner.store.read) as read:
                    with self.assertRaises(NativeUIError):
                        if cls is NavigationGenerationRestoration:cls.host(owner)
                        else:owner.load()
                    self.assertEqual(0,read.call_count)
                self.assertEqual(retained,owner.store.path.read_bytes());self.assertIsNone(owner._scene_relation)

    def test_actual_unknown_cas_keeps_old_relation_and_blocks_retry(self):
        owner=self.restart();owner.save(dict(phase='ready',sequence=1));old=owner._scene_relation
        write=owner.store.write
        def unknown(value,previous):write(value,previous);raise RuntimeError('issued CAS reply lost')
        with patch.object(owner.store,'write',side_effect=unknown):
            with self.assertRaises(RuntimeError):owner.save(dict(phase='ready',sequence=2))
        self.assertIs(old,owner._scene_relation);self.assertFalse(same(owner.store.read(),owner.disk))
        retained=owner.store.path.read_bytes()
        with self.assertRaises(NativeUIError):owner.save(dict(phase='ready',sequence=3))
        self.assertEqual(retained,owner.store.path.read_bytes());self.assertIs(old,owner._scene_relation)

    def test_failed_actual_readback_does_not_install_a_new_relation(self):
        owner=self.restart();owner.save(dict(phase='ready',sequence=1));old=owner._scene_relation
        original=owner.store.read;prior=deepcopy(owner.disk)
        def stale_readback():
            current=original()
            return prior if not same(current,prior) else current
        with patch.object(owner.store,'read',side_effect=stale_readback):
            with self.assertRaises(NativeUIError):owner.save(dict(phase='ready',sequence=2))
        self.assertIs(old,owner._scene_relation)
        with self.assertRaises(NativeUIError):owner.memory_relation()
        self.assertEqual(2,owner.state['sequence']);self.assertTrue(json.loads(owner.store.path.read_bytes())['payload']['bytes']>0)

    def test_replaced_relation_object_is_refused_by_each_actual_owner_guard(self):
        disk,state=self.example();parent=SimpleNamespace();scene=object()
        with patch('adapters.pico4.navigation_scene_generation.scene_owner',return_value=scene):
            for cls in (NavigationRestart,NavigationGenerationFlow,NavigationGenerationRestoration):
                owner=cls.__new__(cls);owner.disk=disk;owner.state=state
                owner.parent=parent;owner.flow=SimpleNamespace(parent=parent);owner.scene_owner=scene;owner._scene_relation_owner=scene
                owner._scene_relation=owner._original_scene_relation=NavigationMemoryRelation(disk,state)
                owner._scene_relation_failed=False
                owner.memory_relation();owner._scene_relation=NavigationMemoryRelation(disk,state)
                with self.assertRaises(NativeUIError):owner.memory_relation()

    def test_default_owner_relation_keeps_original_unpack_validation(self):
        disk,state=self.example();owner=NavigationGenerationFlow.__new__(NavigationGenerationFlow)
        owner.parent=SimpleNamespace();owner._scene_relation_owner=None;owner.disk=disk;owner.state=state
        with patch('adapters.pico4.navigation_scene_generation.scene_owner',return_value=None):
            owner.memory_relation();owner.state=deepcopy(state);owner.memory_relation()
            owner.state['phase']='foreign'
            with self.assertRaises(NativeUIError):owner.memory_relation()

    def test_restoration_host_still_checks_latest_original_full_stamp(self):
        seed=self.restart();seed.save(dict(phase='ready',sequence=1));scene=seed._scene_relation_owner
        owner=NavigationGenerationRestoration.__new__(NavigationGenerationRestoration)
        owner.scene_owner=scene;owner.flow=SimpleNamespace(parent=seed.parent,control=lambda:None,
            validate_links=lambda value:None,state=dict(phase='ready',completed=[dict(verb=v) for v in ('open','bookmark-delete','close')]))
        owner.lock=SimpleNamespace(assert_held=lambda:None);owner.scope=lambda:dict(runId=seed.run);owner.scope_sha=json_digest(owner.scope())
        owner.store=seed.store;owner.disk=seed.disk;owner.state=seed.state;owner.origin=None;owner.physical=read_original(seed.store.path)
        owner._scene_relation_failed=False
        owner._scene_relation=owner._original_scene_relation=NavigationMemoryRelation(owner.disk,owner.state);owner.host()
        path=owner.store.path;replacement=path.with_name('equal-replacement.json');replacement.write_bytes(path.read_bytes());os.chmod(replacement,0o600);os.replace(replacement,path)
        self.assertTrue(same(owner.store.read(),owner.disk))
        with self.assertRaises(NativeUIError):owner.host()


if __name__=='__main__':unittest.main()
