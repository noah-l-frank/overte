"""Independent process framework baseline, preserving actual old scene facts."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
import uuid
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from adapters.pico4.graphics_scene import PicoGraphicsScenePolicy
from adapters.graphics_journey.scene import GraphicsScene
from adapters.native_feature_observation import NativeFeatureObservation
from adapters.normal_feature_state import PrivateFeatureState
from adapters.restart_inputs import RestartInputs
from adapters.script_journey.history import pack,unpack
from self_tests.test_pico_graphics_scene import Model,RUN
from self_tests.test_vr_graphics_subject import USER
from self_tests.test_native_feature_observation import Boundary as FeatureBoundary
from self_tests.test_native_process_presence import Boundary as PresenceBoundary
from self_tests.test_native_scene_loads import Boundary as LoadBoundary,row as load_row
from adapters.native_scene_loads import resource_hash


def new_process(original):
    result=deepcopy(original);result.update(processId=32,instance='f'*32,requestId=uuid.uuid4().hex,sequence=1)
    ids=[row['id'] for row in result['source']['framework']['entities']]
    remap={identifier:str(uuid.uuid5(uuid.UUID('abcdefab-cdef-4abc-8def-abcdefabcdef'),identifier)) for identifier in ids}
    def replace(value):
        if type(value) is dict:return {key:replace(child) for key,child in value.items()}
        if type(value) is list:return [replace(child) for child in value]
        return remap.get(value,value) if type(value) is str else value
    result=replace(result);source=result['source'];framework=source['framework']
    framework['entities'].sort(key=lambda row:row['id']);framework['keyboard']['entityIds'].sort()
    source['scan']['unowned'].sort(key=lambda row:row['id'])
    return result


class PicoGraphicsRestartFrameworkTests(unittest.TestCase):
    def setUp(self):
        self.model=Model();self.addCleanup(self.model.close)
        self.original=self.model._graphics_subject_observer('owned',read_only=True).read(RUN)
        self.baseline=new_process(self.original);self.current=deepcopy(self.baseline)
        self.current.update(requestId=uuid.uuid4().hex,sequence=2)

    def test_new_framework_ids_use_their_own_original_while_old_scene_avatar_and_scan_are_preserved(self):
        before=deepcopy(self.original);PicoGraphicsScenePolicy.restored(self.original,self.current,framework_original=self.baseline)
        self.assertEqual(before,self.original)
        self.assertNotEqual(self.original['source']['framework']['tablet']['frame'],self.current['source']['framework']['tablet']['frame'])
        with self.assertRaises(NativeUIError):PicoGraphicsScenePolicy.restored(self.original,self.current)

    def test_old_process_or_foreign_baseline_and_changed_new_process_appearance_are_rejected(self):
        for fault in ('old','foreign','future','appearance'):
            baseline=deepcopy(self.baseline);current=deepcopy(self.current)
            if fault=='old':baseline=deepcopy(self.original)
            elif fault=='foreign':baseline.update(processId=33,instance='d'*32)
            elif fault=='future':baseline['sequence']=3
            else:current['source']['framework']['entities'][0]['appearanceSha256']='d'*64
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):PicoGraphicsScenePolicy.restored(self.original,current,framework_original=baseline)

    def test_new_framework_baseline_does_not_replace_original_world_or_avatar_restoration(self):
        for fault in ('avatar','world','scan','keyboard'):
            current=deepcopy(self.current)
            if fault=='avatar':
                current['source']['avatarPose']['feetPosition'][0]+=.1
            elif fault=='world':current['source']['sceneUrl']='http://controlled.invalid/foreign.json'
            elif fault=='scan':next(row for row in current['source']['scan']['unowned'] if row['id']==USER)['sha256']='e'*64
            else:current['source']['framework']['keyboard']['raised']=True
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):PicoGraphicsScenePolicy.restored(self.original,current,framework_original=self.baseline)

    def test_world_origin_movement_cannot_pass_as_an_unchanged_sensor_to_world_scale(self):
        current=deepcopy(self.current);source=current['source'];source['hmd']['sensorToWorld'][12]+=.1
        source['hmd']['worldPosition'][0]+=.1;source['view']['position'][0]+=.1
        with self.assertRaises(NativeUIError):PicoGraphicsScenePolicy.restored(self.original,current,framework_original=self.baseline)

    def test_actual_physical_head_motion_does_not_change_the_restored_world_origin(self):
        current=deepcopy(self.current);source=current['source'];hmd=source['hmd'];hmd['sensorPose'][12]+=.1
        for axis in range(3):hmd['worldPosition'][axis]+=.1*hmd['sensorToWorld'][axis]
        source['view']['position']=deepcopy(hmd['worldPosition'])
        PicoGraphicsScenePolicy.restored(self.original,current,framework_original=self.baseline)

    def test_same_process_still_requires_its_original_framework_instead_of_an_arbitrary_replacement(self):
        current=deepcopy(self.original);current.update(sequence=current['sequence']+1,requestId=uuid.uuid4().hex)
        PicoGraphicsScenePolicy.restored(self.original,current)
        with self.assertRaises(NativeUIError):PicoGraphicsScenePolicy.restored(self.original,current,framework_original=self.baseline)

    def test_scene_archive_uses_the_qualified_restart_receipt_and_new_baseline_without_relabelling_old_facts(self):
        m=self.model
        self.enterContext(m.lock.held())
        from self_tests import test_pico_graphics_scene as source_model
        self.enterContext(patch.dict(source_model.BINDING,processIdentity='31:1111'))
        scene=m.factory();scene.prepare();original=deepcopy(scene.previous)
        m.world_render_store=lambda _target,role:PrivateFeatureState(m.root/('graphics-'+role+'-world-render-owner.json'))
        owners=[scene.store,*[m.world_render_store('owned',role=role) for role in ('primary','actor')]]
        inputs=RestartInputs(PrivateFeatureState(m.root/'graphics-restart-inputs.json'),owners,monotonic=lambda:0.)
        def native(pid,instance,launches):
            boundary=FeatureBoundary()
            def capture(value):
                epoch=m.native.epoch
                value.update(processId=pid,instance=instance,capturedEpochMs=epoch,requestedEpochMs=epoch,
                    lifecycle=dict(backgrounds=0,activations=launches,launches=launches))
                value['animationFence']['requestedEpochMs']=epoch;value['animation']['capturedEpochMs']=epoch
                value['animation']['clip']['evaluatedEpochMs']=epoch
            boundary.mutate=capture
            return NativeFeatureObservation(boundary.send,boundary.original,lambda:m.native.epoch,boundary.guard,pid,
                monotonic=lambda:boundary.clock,sleep=boundary.sleep)
        before=inputs.capture(scene.binding,native(31,self.original['instance'],1));events=[]
        inputs.stop(lambda:events.append('stop'))
        inputs.launch(lambda:dict(running=False,identity=None),lambda:events.append('launch'))
        binding=deepcopy(scene.binding);binding['processIdentity']='32:2222'
        after=inputs.observe(binding,native(32,self.baseline['instance'],2))
        presence=PresenceBoundary(pid=32,epoch_ms=lambda:m.native.epoch);presence.presence='absent'
        presence.edit=lambda value:value.update(instance=self.baseline['instance'])
        receipt=dict(input=inputs.read(),oldNative=before,native=after,exit=presence.reader().require_absent(31))
        baseline=deepcopy(self.baseline);baseline.update(requestedEpochMs=m.native.epoch,capturedEpochMs=m.native.epoch)
        loads=LoadBoundary();loads.epoch=m.native.epoch
        loads.rows=[load_row(resourceSha256=resource_hash(baseline['source']['sceneUrl']),
            startedEpochMs=m.native.epoch,updatedEpochMs=m.native.epoch,releasedEpochMs=m.native.epoch)]
        loads.mutate=lambda value:value.update(processId=32,instance=self.baseline['instance'])
        # Original new-process source packets, distinct from old originals.
        def load():
            loads.send(dict(schemaVersion=1,commandId=uuid.uuid4().hex,action='feature-scene-load-observe',runId=RUN))
            return deepcopy(loads.sample)
        proposal=GraphicsScene.restart_record(original,receipt,baseline,load())
        state=unpack(proposal['payload'])[0];current=deepcopy(self.current);latest=load()
        current.update(requestedEpochMs=m.native.epoch,capturedEpochMs=m.native.epoch)
        state.update(phase='restored',subject=current,loads=latest,proof=dict(subject=current,loads=latest))
        proposal['payload']=pack([state])
        archived=GraphicsScene.archive(proposal,adapter=m,selector='owned',client=m.client,run=RUN)
        self.assertEqual(baseline,archived['handoff']['subject']);self.assertEqual(original,scene.store.read())
        self.assertEqual(['stop','launch'],events);self.assertEqual(original,archived['handoff']['previous'])
        bad=deepcopy(proposal);state=unpack(bad['payload'])[0]
        presence.presence='unknown';state['handoff']['receipt']['exit']=presence.reader().read(31)
        bad['payload']=pack([state])
        with self.assertRaises(NativeUIError):GraphicsScene.archive(bad,adapter=m,selector='owned',client=m.client,run=RUN)


if __name__=='__main__':unittest.main()
