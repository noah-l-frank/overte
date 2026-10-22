"""Readiness replays actual frame and scene owners; native sources are modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.adapters.emote_scene_proof import validate
from ios.self_tests import test_ios_emote_restoration_frames as raw_fixture
from ios.self_tests import test_ios_emote_marker_entities as entity_fixture
from ios.self_tests.test_ios_emote_sources import phase


class SceneProofTests(unittest.TestCase):
    def test_actual_initial_gpu_png_owner_is_required_without_new_native_query(self):
        h=raw_fixture.RawFramesTests();h.setUp();self.addCleanup(h.doCleanups)
        factory=h.fixture.native
        def idle(clock):
            reader=factory(clock);send=reader.send
            def sending(query):
                send(query);animation=h.fixture.boundary.sample['animation'];animation['overrideActive']=False;animation.pop('clip',None)
            reader.send=sending;return reader
        h.fixture.native=idle
        owner=h.owner();ref=owner.capture('initial');f=h.fixture
        original_phase=phase(1,90000);original_phase['runId']=owner.run;ticket=original_phase['activations'][-1]['ticket']
        value=dict(iosEmoteSceneProofVersion=1,stage='initial',phase=original_phase,
            restoration=owner.store.read(),reference=ref,ownerPath=str(owner.store.path))
        kwargs=dict(stage='initial',root=owner.root,binding=owner.binding,run=owner.run,role=owner.role,
            instance=original_phase['instance'],ticket=ticket,state_root=owner.store.path.parent,lock=f.lock)
        commands=sum(len(gpu.commands) for gpu in h.gpus.values());result=validate(value,**kwargs)
        self.assertEqual(result['binding'],owner.binding);self.assertEqual(commands,sum(len(gpu.commands) for gpu in h.gpus.values()))
        with self.assertRaises(NativeUIError):validate(dict(value,stage='scene-retired'),**kwargs)
        with self.assertRaises(NativeUIError):validate(value,**dict(kwargs,state_root=owner.store.path.parent/'foreign-sdk'))
        original=owner.original(ref)
        from adapters.script_feature.history import unpack
        name=unpack(original['owner'])[0]['name'];(owner.root/name).write_bytes(b'changed actual frame')
        with self.assertRaises(NativeUIError):validate(value,**kwargs)

    def test_released_camera_endpoint_still_requires_actual_tree_weak_expiry(self):
        h=entity_fixture.MarkerEntityTests();h.setUp();self.addCleanup(h.doCleanups)
        h.scope.prepare();id_=h.scope.state['admission']['marker']['id'];live=h.entities.native.items[id_]
        h.scope.cleanup();h.owner.capture();original_phase=phase(1,90000)
        original_phase['activations'][-1]['stimulus']=dict(verb='cleanup',inputs={});ticket=original_phase['activations'][-1]['ticket']
        def original():return dict(iosEmoteSceneProofVersion=1,stage='scene-retired',phase=original_phase,
            scope=h.scope.store.read(),entities=h.owner.store.read(),ownerPath=str(h.owner.store.path))
        kwargs=dict(stage='scene-retired',root=h.scope.root,binding=h.scope.binding,run=h.scope.run,role=h.scope.role,
            instance=original_phase['instance'],ticket=ticket,state_root=h.owner.store.path.parent,lock=h.scope.lock)
        with self.assertRaises(NativeUIError):validate(original(),**kwargs)
        del live
        import gc;gc.collect();h.owner.capture();before=len(h.entities.native.commands)
        result=validate(original(),**kwargs);self.assertEqual('scene-retired',result['stage'])
        self.assertEqual(before,len(h.entities.native.commands))
        changed=original();changed['phase']['instance']='f'*32
        with self.assertRaises(NativeUIError):validate(changed,**kwargs)
