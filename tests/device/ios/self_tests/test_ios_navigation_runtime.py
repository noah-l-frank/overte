"""Canonical candidate factories and real loopback; SDK/process ports modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
import uuid

from adapters.normal_ui import NativeUIError
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters.navigation_runtime import IOSNavigationRuntime
from ios.self_tests import test_ios_script_runtime as runtime_tests
from self_tests import test_navigation_scene as scene_tests


class NavigationRuntimeTests(unittest.TestCase):
    def setUp(self):
        runtime_tests.IOSScriptRuntimeTests.setUp(self);self.runtime=IOSNavigationRuntime(self.f.adapter)
        self.scene=scene_tests.NavigationSceneTests();self.scene.setUp();self.addCleanup(self.scene.doCleanups)
        self.run=self.scene.open();self.root=self.f.root/'navigation-images';self.root.mkdir(mode=0o700)
        self.lock=ScriptSourceLock(self.f.root/'script-feature-sources.lock')
    def owner(self,*,role='primary',stage=0,request=None,previous=None):
        return self.runtime._navigation_observation_owner('test-only',self.scene.client,self.run,role,stage,
            request or uuid.uuid4().hex,self.root,self.lock,previous=previous)

    def test_existing_candidate_session_and_native_clock_are_used_without_launch_or_input(self):
        sessions,launches=self.f.sessions,self.f.launches;scope=deepcopy(self.f.adapter._binding_store('test-only').read())
        with self.lock.held():
            owner=self.owner();self.assertEqual('42',owner.binding['processIdentity'])
            current=self.f.adapter._binding_store('test-only').read()
            for field in ('scope','process','phase','source'):self.assertEqual(scope[field],current[field])
            packet=owner.native.read(0)
            self.assertEqual(20000,packet['capturedEpochMs']);self.assertTrue(owner.native.native_clock_bound)
            child=owner.images.live_child(dict(requestId='ios-'+'f'*32))
            self.assertIs(owner.native,child.native);self.assertIs(owner.navigation,child.navigation)
            self.assertIs(owner.fixture,child.fixture)
            self.assertIsNone(child.store.read());self.assertIsNone(owner.store.read())
        self.assertEqual((sessions,launches),(self.f.sessions,self.f.launches))
        self.assertEqual([('GET','/session/test-only')],self.calls)
        self.assertFalse(any(operation in ('mobile: terminateApp','mobile: backgroundApp') for operation,_values in self.f.commands))

    def test_admission_factory_uses_same_candidate_lock_and_never_loads_a_scene(self):
        sessions,launches=self.f.sessions,self.f.launches
        with self.lock.held():
            owner=self.runtime._navigation_admission_owner('test-only',self.scene.client,self.run,self.lock)
            self.assertEqual('42',owner.binding['processIdentity']);self.assertIsNone(owner.store.read())
            self.assertEqual(8,len(owner.sources));self.assertTrue(owner.native.native_clock_bound)
            self.assertEqual(20000,owner.native.read(0)['capturedEpochMs'])
            self.f.process['pid']=43
            with self.assertRaises((NativeUIError,ValueError)):owner.bound()
        self.assertEqual((sessions,launches),(self.f.sessions,self.f.launches))
        self.assertFalse(any(operation in ('mobile: terminateApp','mobile: backgroundApp') for operation,_values in self.f.commands))

    def test_factory_and_native_reader_refuse_changed_candidate_before_input_or_new_capture(self):
        with self.lock.held():
            owner=self.owner();before=len(self.f.commands);self.f.artifact.write_bytes(b'Replaced candidate')
            with self.assertRaises((NativeUIError,ValueError)):owner.native.read(0)
            with self.assertRaises((NativeUIError,ValueError)):owner.images.live_child(dict(requestId='ios-'+'f'*32))
            self.assertEqual(before,len(self.f.commands));self.assertEqual([],owner.images.state['rows'])

    def test_source_revision_mismatch_fails_before_creating_any_navigation_owner(self):
        self.scene.provider.inputs['sourceRevision']='f'*40
        with self.lock.held():
            with self.assertRaises(NativeUIError):self.owner()
        self.assertEqual([],list(self.f.root.glob('ios-navigation-*.json')))

    def test_foreign_fixture_run_is_refused_without_attaching_its_metadata(self):
        self.run='f'*32
        with self.lock.held():
            with self.assertRaises(NativeUIError):self.owner()
        self.assertEqual([],list(self.f.root.glob('ios-navigation-*.json')))

    def test_missing_existing_sdk_session_does_not_recreate_one_or_launch(self):
        sessions,launches=self.f.sessions,self.f.launches
        self.client.call=lambda *_:(_ for _ in ()).throw(RuntimeError('Synthetic lost existing SDK session'))
        with self.lock.held():
            with self.assertRaises(RuntimeError):self.owner()
        self.assertEqual((sessions,launches),(self.f.sessions,self.f.launches))
        self.assertEqual([],list(self.f.root.glob('ios-navigation-*.json')))

    def test_actual_process_replacement_cannot_reuse_a_live_observer_or_child(self):
        with self.lock.held():
            owner=self.owner();before=deepcopy(self.f.clock.commands);self.f.process['pid']=43
            with self.assertRaises((NativeUIError,ValueError)):owner.bound()
            with self.assertRaises((NativeUIError,ValueError)):owner.images.live_child(dict(requestId='ios-'+'f'*32))
            self.assertEqual(before,self.f.clock.commands);self.assertEqual([],owner.images.state['rows'])

    def test_role_and_stage_image_ownership_remain_distinct_on_the_same_candidate(self):
        with self.lock.held():
            primary=self.owner();actor=self.owner(role='actor');later_stage=self.owner(stage=1)
            self.assertEqual(3,len({owner.images.store.path for owner in (primary,actor,later_stage)}))
            self.assertEqual(primary.binding,actor.binding)
            with self.assertRaises(NativeUIError):self.owner(role='actor',previous=primary)

