"""Continuous G1 source join with explicit Qt/OS/GPU/SDK native models.

All fifteen normal actions and their real Python/TLS owners run first. The
synthetic GPU boundary supplies its own new-process original clocks/identity;
these are no headset pixels or changed-scene/device acceptance evidence.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import uuid

from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.pico4.navigation_generation import compose
from adapters.pico4.navigation_generation_frames import NavigationGenerationFrames
from adapters.pico4.navigation_originals import read_original
from adapters.world_render_evidence import FILE as CAPTURE_FILE
from adapters.world_render_receipts import INVENTORY_FILE
from adapters.world_render_storage import receipt_file
from self_tests import test_pico_navigation_generation_prefix as generation
from self_tests.test_navigation_frames import clock_boundary


@unittest.skipUnless(shutil.which('openssl'),'Existing ephemeral TLS fixture requires OpenSSL')
class NavigationGenerationFramesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):generation.NavigationGenerationPrefixTests.setUpClass()
    @classmethod
    def tearDownClass(cls):generation.NavigationGenerationPrefixTests.tearDownClass()

    def setUp(self):
        self.f=generation.NavigationGenerationPrefixTests();self.f.setUp();self.addCleanup(self.f.doCleanups)

    def prepare(self):
        f=self.f;launch=f.launch_receiver
        def receiver():
            launch()
            # Before ANY G1 original is acquired, both independent native
            # readers observe the one modeled application's real new birth.
            f.new_world.subject.edit=lambda value:value.update(processId=32,instance=f.native_birth)
        f.launch_receiver=receiver;f.prepare_generation()
        sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'android/vr/pico/tests/device'))
        import test_native_execution_binding as canonical
        fixture=canonical.NativeExecutionBindingTest();fixture.setUp();self.addCleanup(fixture.doCleanups)
        self.adapter=adapter=fixture.instance()
        environment=patch.dict(os.environ,dict(OVERTE_PICO_NORMAL_SCRIPTS='1',OVERTE_ANDROID_E2E_DEBUG='1',
            OVERTE_PICO_OPENXR_INPUT='1',OVERTE_E2E_SCENE_URL=generation.prefix.INPUTS['sceneUrl']))
        environment.start();self.addCleanup(environment.stop)
        for key,value in vars(f.adapter).items():setattr(adapter,key,value)
        self.raw_read=adapter.adb.read_debug_app_file
        self.native=f.native_reader
        self.gpu_birth=uuid.uuid4().hex;self.storage_birth=self.gpu_birth;self.inventory_birth=uuid.uuid4().hex
        world=f.world;m=f.model
        original_gpu=world.gpu.mutate
        def gpu(value):
            original_gpu(value);clock_boundary(value,m.epoch())
            value.update(processId=32,instance=self.gpu_birth)
        world.gpu.mutate=gpu
        world.storage.mutate=lambda value:value.update(processId=32,instance=self.storage_birth,capturedEpochMs=m.epoch())
        world.inventory.mutate=lambda value:value.update(processId=32,instance=self.inventory_birth,capturedEpochMs=m.epoch())
        world.inventory.epoch=m.epoch()
        def reader(_target):
            value=self.native();old_guard=value.guard
            def current():need(f.running and f.current_identity=='32:10002');return old_guard()
            value.guard=current;value.send=send;return value
        def owner():
            candidates=[store.read() for store in adapter._navigation_world_render_stores('owned-model')]
            candidates=[value for value in candidates if value is not None];need(len(candidates)==1)
            value=candidates[0]
            # The real WorldRenderOwner validates this retained DTO. The
            # modeled issuer reads the actual already-written input intent.
            return value['capture'],value['receipts']
        def send(command):
            action=command['action']
            if action=='feature-world-render-observe':
                capture,_receipts=owner();need(capture==command)
                world.gpu.intents.append(deepcopy(command));world.gpu.advance();world.gpu.send(command)
                world.storage.raw=world.gpu.raw;world.storage.present=True
                if world.capture_error:raise NativeUIError('Synthetic lost applied G1 acquisition')
            elif action=='feature-world-render-storage':
                world.storage.intents.append(deepcopy(command));world.storage.send(command)
                name=receipt_file(command['commandId']);path=world.native_root/name
                path.write_text(world.storage.files[name]);path.chmod(0o600)
                world.inventory.issued[command['commandId']]=(command['requestId'],hashlib.sha256(path.read_bytes()).hexdigest())
            elif action=='feature-world-render-receipts':
                world.inventory.retired=not world.storage.present;world.inventory.present=world.storage.present
                world.inventory.callbacks=world.storage.callbacks;world.inventory.png_bytes=len(world.storage.raw) if world.storage.present else 0
                world.inventory.epoch=m.epoch();world.inventory.send(command)
            else:self.native().send(command)
        def read(target,package,path,**options):
            name=path.rsplit('/',1)[-1]
            if name==CAPTURE_FILE:return world.gpu.original()
            if name==INVENTORY_FILE:return world.inventory.original()
            if name.startswith('world-render-storage-'):return (world.native_root/name).read_text()
            return self.raw_read(target,package,path,**options)
        adapter.adb.read_debug_app_file=read;adapter._native_feature_observer=reader
        adapter._scripts=lambda *_args:need(False)
        adapter._script_runtime=lambda *_args:need(False)
        adapter._script_paths=lambda _target:(f.root/'normal-script-state-modeled.json',f.root/'normal-script-ui-modeled.json')
        def lock(target,provided):
            need(target=='owned-model' and provided is f.lock);return provided
        adapter._script_journey=lambda:SimpleNamespace(state_path=lambda _target:f.root/'state.json',_lock=lock)
        f.adapter=adapter
        with f.lock.held():
            f.flow=compose(adapter,'owned-model',f.original_parent);f.actor=compose(adapter,'owned-model',f.original_actor)
        for index in range(12,15):f.flow.act(f.next_call(index));f.flow.observe();f.actor.observe()
        self.originals=[read_original(f.root/('navigation-prefix-generation-1-'+name+'.json')) for name in ('close-join','tablet-close')]
        self.controls=deepcopy(m.controller_calls);self.sdk=deepcopy(f.sdk_calls)
        return f.flow

    def preserved(self):
        f=self.f
        self.assertEqual(self.originals,[read_original(row['path']) for row in self.originals])
        self.assertEqual(self.controls,f.model.controller_calls);self.assertEqual(self.sdk,f.sdk_calls)
        self.assertEqual(f.original_prefix,f.original_parent.store.path.read_bytes())
        self.assertEqual(f.original_ui,read_original(f.original_parent.source.normal.io.original.navigation.path))

    def test_fifteen_actions_then_fresh_g1_two_eye_source_and_retirement_preserve_original_close(self):
        self.prepare();f=self.f
        frame=f.flow.frames(0)
        self.assertEqual(1,frame['sequence']);self.assertEqual(1,len(f.world.gpu.commands))
        self.assertEqual([],list(f.world.native_root.iterdir()))
        self.assertTrue(all(store.read() is None for store in self.adapter._navigation_world_render_stores('owned-model')))
        self.preserved()
        cold=f.cold_generation();frame2=cold.frames(1)
        self.assertEqual(2,frame2['sequence']);self.assertNotEqual(frame['journalId'],frame2['journalId'])
        self.assertEqual(2,len(f.world.gpu.commands));self.preserved()

    def test_lost_applied_gpu_result_keeps_original_intent_and_cold_never_reacquires(self):
        self.prepare();f=self.f;f.world.capture_error=True
        with self.assertRaises(NativeUIError):f.flow.frames(0)
        count=len(f.world.gpu.commands)
        intent=read_original(self.adapter._navigation_world_render_store('owned-model','primary',generation=1).path)
        f.world.capture_error=False
        with self.assertRaises(NativeUIError):f.cold_generation().frames(0)
        self.assertEqual(count,len(f.world.gpu.commands));self.assertEqual(intent,read_original(intent['path']));self.preserved()

    def test_original_close_same_byte_replacement_after_outer_release_refuses_publication(self):
        self.prepare();f=self.f;original=f.lock.held;changed=[]
        @contextmanager
        def released():
            with original():yield
            if not changed and f.lock._owner is None and list((f.root/'navigation-prefix-generation-1-primary-images').glob('*.png')):
                path=f.root/'navigation-prefix-generation-1-tablet-close.json';raw=path.read_bytes()
                temporary=path.with_name('synthetic-replaced-close.json');temporary.write_bytes(raw);temporary.chmod(0o600)
                temporary.replace(path);changed.append(True)
        f.lock.held=released
        with self.assertRaises(NativeUIError):f.flow.frames(0)
        self.assertTrue(changed);self.assertEqual(1,len(f.world.gpu.commands))

if __name__=='__main__':unittest.main()
