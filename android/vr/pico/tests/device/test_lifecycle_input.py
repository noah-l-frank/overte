"""Actual Pico wrapper plus explicit native/OpenXR boundaries; no device runs."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[5]))
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))
import test_normal_scripts as sources
from adapters.pico4.lifecycle_back import PicoLifecycleBack
from adapters.pico4.lifecycle_source import COMMAND,FILE
from openxr_input.adapter_session import PicoOpenXrAdapterSession
from self_tests.test_pico_lifecycle_source import Boundary,RUN,LifecycleSourceTests
from self_tests.test_pico_lifecycle_back import LifecycleBackTests
from self_tests.test_pico_lifecycle_x_mapping import PicoLifecycleXMappingTests
from self_tests.test_pico_lifecycle_drive import LifecycleDriveTests,LifecycleDriveProbeTests
from self_tests.test_pico_lifecycle_gesture import LifecycleGestureTests,LifecycleGestureProbeTests
from self_tests.test_pico_lifecycle_world import LifecycleWorldTests
from self_tests.test_pico_lifecycle_join import LifecycleJoinTests
from self_tests.test_pico_lifecycle_process import LifecycleProcessTests
from self_tests.test_pico_openxr_adapter_session import FakeTransport


class PicoLifecycleBindingTests(unittest.TestCase):
    def setUp(self):
        self.fixture=sources.PicoNormalScriptsTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.adapter,self.native=self.fixture.instance,self.fixture.native
        self.boundary=Boundary();original_write=self.native.write_debug_app_file;original_read=self.native.read_debug_app_file
        def write(target,package,path,raw):
            if path!=COMMAND:return original_write(target,package,path,raw)
            self.assertEqual('org.overte.pico',package);self.boundary.send(json.loads(raw))
            self.boundary.value['processId']=int(self.native.identity.split(':')[0])
            self.boundary.value['capturedEpochMs']=self.native.epoch_milliseconds(target)
        def read(target,package,path,**options):
            if path!='files/overte-e2e/'+FILE:return original_read(target,package,path,**options)
            self.assertEqual({'attempts':1},options);return self.boundary.read()
        for binding in (patch.object(self.native,'write_debug_app_file',side_effect=write),
                patch.object(self.native,'read_debug_app_file',side_effect=read)):
            binding.start();self.addCleanup(binding.stop)
    def test_actual_wrapper_reads_original_lifecycle_source_and_rechecks_installed_candidate(self):
        source=self.adapter._lifecycle_ui_source(self.native.target);value=source.capture(RUN)
        self.assertEqual('create',value['source']['editors'][0]['kind']);self.assertEqual(1,len(self.boundary.commands))
        self.native.digest='f'*64
        with self.assertRaises((ValueError,RuntimeError)):source.capture(RUN)
        self.assertEqual(1,len(self.boundary.commands));self.assertEqual([],self.native.inputs)
    def test_actual_drive_factory_keeps_native_originals_under_installed_candidate_guard(self):
        from self_tests.test_pico_lifecycle_drive import Boundary as DriveBoundary
        from adapters.pico4.lifecycle_drive import ACTION,FILE
        boundary=DriveBoundary();write_original=self.native.write_debug_app_file;read_original=self.native.read_debug_app_file
        def write(target,package,path,raw):
            command=json.loads(raw)
            if command.get('action')!=ACTION:return write_original(target,package,path,raw)
            boundary.send(command);boundary.value['capturedEpochMs']=self.native.epoch_milliseconds(target)
        def read(target,package,path,**options):
            if path=='files/overte-e2e/'+FILE:return boundary.read()
            return read_original(target,package,path,**options)
        with patch.object(self.native,'write_debug_app_file',side_effect=write),patch.object(self.native,'read_debug_app_file',side_effect=read):
            source=self.adapter._lifecycle_drive_source(self.native.target);packet=source.capture(RUN)
            self.assertEqual([1,2,3],packet['source']['feetPosition']);self.assertEqual(1,len(boundary.commands))
            self.native.digest='f'*64
            with self.assertRaises((ValueError,RuntimeError)):source.capture(RUN)
            self.assertEqual(1,len(boundary.commands));self.assertEqual([],self.native.inputs)

    def test_actual_gesture_factory_keeps_native_originals_under_installed_candidate_guard(self):
        from self_tests.test_pico_lifecycle_gesture import Boundary as GestureBoundary
        from adapters.pico4.lifecycle_gesture import ACTION,FILE
        boundary=GestureBoundary();write_original=self.native.write_debug_app_file;read_original=self.native.read_debug_app_file
        def write(target,package,path,raw):
            command=json.loads(raw)
            if command.get('action')!=ACTION:return write_original(target,package,path,raw)
            boundary.send(command);epoch=self.native.epoch_milliseconds(target);boundary.value['capturedEpochMs']=epoch
            boundary.value['source'].update(createdEpochMs=epoch,frameEpochMs=epoch)
            for event in boundary.value['source']['events']:event['occurredEpochMs']=epoch
        def read(target,package,path,**options):
            if path=='files/overte-e2e/'+FILE:return boundary.read()
            return read_original(target,package,path,**options)
        with patch.object(self.native,'write_debug_app_file',side_effect=write),patch.object(self.native,'read_debug_app_file',side_effect=read):
            source=self.adapter._lifecycle_gesture_source(self.native.target);packet=source.capture(RUN)
            self.assertTrue(packet['source']['known']);self.assertEqual(1,len(boundary.commands))
            self.native.digest='f'*64
            with self.assertRaises((ValueError,RuntimeError)):source.capture(RUN)
            self.assertEqual(1,len(boundary.commands));self.assertEqual([],self.native.inputs)

    def test_actual_world_factory_uses_shared_script_source_lock_and_original_installed_candidate(self):
        from adapters.pico4.lifecycle_world import PicoLifecycleWorld
        from adapters.script_journey.lock import ScriptSourceLock
        directory=self.fixture.fixture.state_root
        session=PicoOpenXrAdapterSession(FakeTransport(),'explicit-world-target',directory);session.begin(self.native.identity)
        with patch.object(self.adapter,'pico_input_session',return_value=session):
            owner=self.adapter._lifecycle_world(self.native.target,RUN)
            self.assertIsInstance(owner,PicoLifecycleWorld);self.assertIs(owner.session,session)
            self.assertEqual(self.adapter._script_journey()._lock(self.native.target).path,owner.lock.path)
            self.assertTrue(all(reader.source_lock is owner.lock for reader in (owner.source,owner.axes,owner.avatar)))
            self.assertEqual('lifecycle-world-owner.json',owner.store.path.name);self.assertIsNone(owner.state)
            self.assertEqual(self.native.identity,owner.binding['processIdentity'])
            self.native.digest='f'*64
            with self.assertRaises((ValueError,RuntimeError)):owner.prepare()
            self.assertIsNone(owner.store.read());self.assertEqual([],session.transport.envelopes)
        self.assertFalse(any(cap.startswith('feature.lifecycle-input.') for cap in self.adapter.capabilities(self.native.target)))
        self.assertEqual([],self.native.inputs)

    def test_actual_x_join_factory_keeps_original_world_back_bindings_and_shared_source_lock(self):
        from adapters.pico4.lifecycle_join import PicoLifecycleXJoin
        directory=self.fixture.fixture.state_root
        session=PicoOpenXrAdapterSession(FakeTransport(),'explicit-world-target',directory);session.begin(self.native.identity)
        with patch.object(self.adapter,'pico_input_session',return_value=session):
            join=self.adapter._lifecycle_x_join(self.native.target,RUN)
            self.assertIsInstance(join,PicoLifecycleXJoin);self.assertIs(join.world.session,join.back.session)
            self.assertEqual(join.world.binding,join.back.binding);self.assertIsNone(join.state)
            self.assertIs(join.world.lock,join.back.source_lock);self.assertIs(join.back.source.source_lock,join.world.lock)
            self.assertEqual(join.world.store.path.with_name('lifecycle-x-back-owner.json'),join.back.store.path)
            self.assertEqual(join.world.lock.path,self.adapter._script_journey()._lock(self.native.target).path)
            self.assertEqual('lifecycle-x-join.json',join.store.path.name)
        self.assertEqual([],self.native.inputs)

    def test_base_cleanup_keeps_original_world_journal_after_process_teardown(self):
        original=dict(explicitSyntheticBoundary='unresolved lifecycle world ownership')
        store=self.adapter._lifecycle_world_store(self.native.target);store.write(original,None)
        with self.assertRaises((ValueError,RuntimeError)):self.adapter.cleanup(self.native.target)
        self.assertEqual(original,store.read());self.assertIn(('am','force-stop','org.overte.pico'),self.native.events)

    def test_base_cleanup_keeps_unresolved_lifecycle_ownership_after_actual_teardown(self):
        store=self.adapter._lifecycle_back_store(self.native.target)
        original=dict(explicitSyntheticBoundary='unresolved lifecycle proof')
        store.write(original,None)
        with self.assertRaises((ValueError,RuntimeError)):self.adapter.cleanup(self.native.target)
        self.assertEqual(original,store.read())
        self.assertIn(('am','force-stop','org.overte.pico'),self.native.events)

    def test_actual_process_factory_keeps_existing_three_original_owners_and_candidate_pins(self):
        from adapters.pico4.lifecycle_process import PicoLifecycleProcessRetirement,PicoLifecycleDomain
        from adapters.script_journey.lock import ScriptSourceLock
        directory=self.fixture.fixture.state_root
        session=PicoOpenXrAdapterSession(FakeTransport(),'explicit-process-target',directory);session.begin(self.native.identity)
        lock=self.adapter._script_journey()._lock(self.native.target)
        with patch.object(self.adapter,'pico_input_session',return_value=session):
            owner=self.adapter._lifecycle_process_retirement(self.native.target,RUN,source_lock=lock)
            self.assertIsInstance(owner,PicoLifecycleProcessRetirement);self.assertIs(owner.lock,lock)
            self.assertEqual(['lifecycle-world-owner.json','lifecycle-x-back-owner.json','lifecycle-x-join.json'],
                [store.path.name for store in owner.inputs.owners])
            domain=self.adapter._lifecycle_domain_source(self.native.target,source_lock=lock)
            self.assertIsInstance(domain,PicoLifecycleDomain);self.assertIs(domain.source_lock,lock)
            self.native.digest='f'*64
            with self.assertRaises((ValueError,RuntimeError)):owner.now()
            self.assertIsNone(owner.store.read());self.assertIsNone(owner.inputs.store.read())
        self.assertEqual([],self.native.inputs)
    def test_new_process_binding_reads_original_bridge_without_reopening_original_script_owner(self):
        directory=self.fixture.fixture.state_root
        session=PicoOpenXrAdapterSession(FakeTransport(),'explicit-process-target',directory);session.begin(self.native.identity)
        with patch.object(self.adapter,'pico_input_session',return_value=session):
            owner=self.adapter._lifecycle_process_retirement(self.native.target,RUN)
            with patch.object(self.adapter,'_scripts',side_effect=AssertionError('Original manager cannot be reopened')):
                binding=self.adapter._lifecycle_process_new_binding(self.native.target,owner)
            self.assertEqual(self.native.identity,binding['processIdentity']);self.assertEqual(0,binding['generation'])
            self.assertEqual(self.native.bridge_id,binding['sessionId'])
            self.assertEqual([],session.transport.envelopes)
        self.assertEqual([],self.native.inputs)

    def test_actual_back_factory_shares_original_process_session_and_private_candidate_binding(self):
        directory=self.fixture.fixture.state_root
        session=PicoOpenXrAdapterSession(FakeTransport(),'explicit-synthetic-target',directory)
        session.begin(self.native.identity)
        with patch.object(self.adapter,'pico_input_session',return_value=session):
            owner=self.adapter._lifecycle_back(self.native.target,RUN)
            self.assertIsInstance(owner,PicoLifecycleBack);self.assertIs(owner.session,session)
            self.assertEqual(self.native.identity,owner.binding['processIdentity'])
            self.assertEqual(directory,owner.store.path.parent);self.assertIsNone(owner.state)
            self.assertFalse(any(cap.startswith('feature.lifecycle-input.') for cap in self.adapter.capabilities(self.native.target)))
        self.assertEqual([],self.native.inputs)


if __name__=='__main__':unittest.main()
