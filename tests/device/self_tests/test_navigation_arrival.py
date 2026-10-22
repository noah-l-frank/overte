"""Actual source/PNG/receipt owners; native probe/HMD/GPU/OS are simulated."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import json
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.navigation_arrival import NavigationArrival,pose_packet,stereo_frame
from adapters.navigation_stereo import NavigationStereo
from adapters.native_graphics_subject import NativeGraphicsSubject
from adapters.normal_ui import NativeUIError
from adapters.script_journey.history import unpack,pack
from navigation_observation import viewpoint_urls,POSITIONS
from feature_journeys.graphics_fixture import subject_ids
from self_tests.test_vertical_locomotion import snapshot
from self_tests.test_pico_graphics_samples import Model as WorldModel,RUN,TICKET

SCENE='http://controlled.invalid/scene.json'

class Model(WorldModel):
    def __init__(self,run=RUN):
        super().__init__();self.run_id=run;self.probe_sequence=0;self.position='A';self.fault=''
        self.source=self.subject.source;self.probe_edit=None
        self.source.update(entities=[],absentIds=list(subject_ids(self.run_id).values()))
        self.source['scan']['scannedEntities']=len(self.source['scan']['unowned'])
        self.source['hmd'].update(sensorToWorld=[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1],
            sensorPose=[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1],worldPosition=[0,1.6,0],worldRotation=[0,0,0,1])
        self.source['view'].update(position=[0,1.6,0],rotation=[0,0,0,1],mode='first person')
        self.source['avatarPose'].update(orientation=[0,0,0,1],modelScale=1)
    def epoch(self):return 20000+round(self.clock*1000)
    def probe(self,after):
        self.probe_sequence=max(self.probe_sequence+1,after+1)
        p=deepcopy(POSITIONS[self.position]);value=snapshot(feetPosition=p)
        value.update(sampleEpochMs=self.epoch(),sampleSequence=self.probe_sequence,
            nativeMotion=dict(processId=31,sampleEpochMs=self.epoch(),sampleSequence=self.probe_sequence),
            render=dict(frameCount=self.probe_sequence,lastFrameEpochMs=self.epoch()))
        value['domain']['protocol']='http';value['scene']['url']=viewpoint_urls(SCENE)[self.position]
        if self.probe_edit:self.probe_edit(value)
        return value
    def update_subject(self):
        p=POSITIONS[self.position];feet=[p[a] for a in 'xyz']
        self.subject.epoch=self.epoch();self.source['sceneUrl']=viewpoint_urls(SCENE)[self.position]
        self.source['avatarPose']['feetPosition']=feet
        # Deliberately keep a physically tracked head independent of avatar
        # feet: a fixed eye or camera-as-feet shortcut would fail this fixture.
        self.source['hmd']['sensorToWorld'][12:15]=feet
        self.source['hmd']['sensorPose'][12:15]=[-feet[0],1.6-feet[1],-feet[2]]
        if self.fault=='subject-feet':self.source['avatarPose']['feetPosition']=[99,0,4]
    def subject_reader(self):
        def send(command):self.update_subject();self.subject.send(command)
        return NativeGraphicsSubject(send,self.subject.original,self.epoch,self.guard,31,require_framework=True,
            monotonic=lambda:self.clock,sleep=self.sleep)
    def arrival(self):
        return NavigationArrival(self.probe,self.subject_reader(),self.epoch,self.guard,self.run_id,self.binding,SCENE,monotonic=lambda:self.clock)
    def stereo(self,path=None,arrival=None,*,journal_id=None):
        return NavigationStereo(arrival or self.arrival(),
            lambda:self._world_render_capture('owned',read_only=True,role='primary',require_frame_view=True,source_lock=self.lock),
            path or self.root/'navigation-stereo.json',self.artifacts,self.run_id,self.binding,self.lock,self.guard,journal_id=journal_id,ui_factory=lambda:self.ui.source(),native_factory=lambda:self._native_feature_observer('owned',read_only=True),monotonic=lambda:self.clock)

class NavigationArrivalTests(unittest.TestCase):
    def setUp(self):self.model=Model();self.addCleanup(self.model.close)
    def test_native_probe_and_original_gui_avatar_classify_measured_a_b_without_copying_camera_feet(self):
        source=self.model.arrival();a=source.read();self.assertEqual('A',pose_packet(a,RUN,self.model.binding,SCENE,self.model.epoch()))
        self.model.position='B';b=source.read();self.assertEqual('B',pose_packet(b,RUN,self.model.binding,SCENE,self.model.epoch()))
        self.assertNotEqual(b['subject']['source']['view']['position'],b['subject']['source']['avatarPose']['feetPosition'])
        self.assertNotIn('location',b);self.assertEqual(2,len(self.model.subject.commands))
    def test_address_echo_unsettled_avatar_old_renderer_foreign_pid_and_disagreeing_source_never_prove_arrival(self):
        for fault in ('echo','in-air','moving','renderer','pid','subject'):
            self.model.fault='';self.model.probe_edit=None
            def changed(v):
                if fault=='echo':v['avatar']['feetPosition']=dict(x=99,y=0,z=4)
                elif fault=='in-air':v['avatar']['inAir']=True
                elif fault=='moving':v['avatar']['velocity']['x']=1
                elif fault=='renderer':v['render']['lastFrameEpochMs']=0
                elif fault=='pid':v['nativeMotion']['processId']=32
            if fault=='subject':self.model.fault='subject-feet'
            self.model.probe_edit=changed
            try:value=self.model.arrival().read();label=pose_packet(value,RUN,self.model.binding,SCENE,self.model.epoch())
            except NativeUIError:label=None
            with self.subTest(fault=fault):self.assertIsNone(label)
    def test_original_stereo_bytes_are_saved_before_complete_native_memory_and_file_retirement(self):
        result=self.model.stereo().acquire(TICKET)
        self.assertEqual('complete',result['phase']);self.assertIsNone(self.model.owner_store('primary').read())
        self.assertEqual([],list(self.model.native_root.iterdir()));self.assertFalse(result['proof']['memory']['present'])
        raw=self.model.stereo().image_bytes();facts=stereo_frame(result['frame'],raw,RUN,self.model.binding,SCENE)
        self.assertEqual('A',facts['location']);self.assertEqual(result['image']['sha256'],facts['imageSha256'])
        self.assertNotIn('passed',facts);self.assertNotIn('marker',facts)
        commands=len(self.model.gpu.commands);self.model.stereo().acquire(TICKET)
        self.assertEqual(commands,len(self.model.gpu.commands))
    def test_mono_relabel_missing_original_camera_or_stale_native_frame_cannot_supply_stereo_source(self):
        for fault in ('mono','camera','frame'):
            model=Model()
            try:
                original=model.gpu.mutate
                def changed(packet):
                    original(packet)
                    if fault=='mono':packet['source']['view']='main-mono'
                    elif fault=='camera':packet['source']['renderTrace']['cameraBatches']=[]
                    else:packet['source']['presentation']['frameIndex']+=1
                model.gpu.mutate=changed
                with self.subTest(fault=fault),self.assertRaises(NativeUIError):model.stereo().acquire(TICKET)
                self.assertIsNotNone(model.owner_store('primary').read())
                count=len(model.gpu.commands)
                with self.assertRaises(NativeUIError):model.stereo().acquire(TICKET)
                self.assertEqual(count,len(model.gpu.commands))
            finally:model.close()
    def test_distant_recorded_head_actual_gpu_camera_or_changed_arrival_cannot_join_source(self):
        for fault in ('recorded-head','gpu-camera','arrival'):
            model=Model()
            try:
                original=model.gpu.mutate
                def changed(packet):
                    original(packet)
                    if fault=='recorded-head':packet['source']['renderTrace']['recordedView']['position'][0]+=5
                    elif fault=='gpu-camera':
                        for batch in packet['source']['renderTrace']['cameraBatches']:
                            if batch['role']=='forward':
                                for camera in batch['cameras']:camera['view'][12]+=5
                    else:model.position='B'
                model.gpu.mutate=changed
                with self.subTest(fault=fault),self.assertRaises(NativeUIError):model.stereo().acquire(TICKET)
                self.assertIsNotNone(model.owner_store('primary').read())
            finally:model.close()

    def test_lost_acquisition_or_original_pose_failure_preserves_the_original_lease_without_resending(self):
        self.model.capture_error=True
        with self.assertRaises(NativeUIError):self.model.stereo().acquire(TICKET)
        original=deepcopy(self.model.owner_store('primary').read());self.assertIsNotNone(original)
        self.model.capture_error=False
        with self.assertRaises(NativeUIError):self.model.stereo().acquire(TICKET)
        self.assertEqual(original,self.model.owner_store('primary').read());self.assertEqual(1,len(self.model.gpu.commands))
    def test_live_callbacks_and_ignored_file_remove_keep_actual_owner_and_private_evidence(self):
        for fault in ('callbacks','files'):
            model=Model()
            try:
                if fault=='callbacks':model.storage.callbacks=1
                else:model.inventory.ignore_remove=True
                with self.subTest(fault=fault),self.assertRaises(NativeUIError):model.stereo().acquire(TICKET)
                owner=model.owner_store('primary').read();self.assertIsNotNone(owner)
                stereo=model.stereo();self.assertEqual('saved',stereo.state['image']['phase'])
                self.assertNotEqual('complete',stereo.state['phase'])
                before=sum(c['operation']=='release' for c in model.storage.commands)
                with self.assertRaises(NativeUIError):model.stereo().acquire(TICKET)
                self.assertEqual(before,sum(c['operation']=='release' for c in model.storage.commands))
            finally:model.close()
    def test_original_v1_owner_and_source_stay_readable_without_reacquisition(self):
        self.model.stereo().acquire(TICKET);path=self.model.root/'navigation-stereo.json'
        disk=json.loads(path.read_text());disk['navigationStereoOwnerVersion']=1;disk.pop('journalId');path.write_text(json.dumps(disk));path.chmod(0o600)
        self.model.stereo().acquire(TICKET);self.assertEqual(1,len(self.model.gpu.commands))
        self.assertEqual(1,self.model.stereo().disk['navigationStereoOwnerVersion'])

    def test_shared_pose_core_preserves_known_navigation_proof_and_does_not_relax_navigation_scope(self):
        from adapters.navigation_arrival import stereo_pose
        owner=self.model.stereo();state=owner.acquire(TICKET);frame=state['frame'];raw=owner.image_bytes()
        expected=stereo_frame(frame,raw,RUN,self.model.binding,SCENE)
        self.assertEqual(expected,stereo_pose(frame['before'],frame['capture'],frame['after'],raw,RUN,self.model.binding,SCENE,
            frame['after']['subject']['capturedEpochMs']))
        for key in ('before','after'):
            frame[key]['probe']['scene']['url']='http://other.invalid/scene.json'
            frame[key]['subject']['source']['sceneUrl']='http://other.invalid/scene.json'
        with self.assertRaises(NativeUIError):stereo_frame(frame,raw,RUN,self.model.binding,SCENE)
        result=stereo_pose(frame['before'],frame['capture'],frame['after'],raw,RUN,self.model.binding,SCENE,
            frame['after']['subject']['capturedEpochMs'],require_location=False)
        self.assertIsNone(result['location'])
        frame['after']['probe']['scene']['url']='http://replaced.invalid/scene.json'
        frame['after']['subject']['source']['sceneUrl']='http://replaced.invalid/scene.json'
        with self.assertRaises(NativeUIError):stereo_pose(frame['before'],frame['capture'],frame['after'],raw,RUN,self.model.binding,SCENE,
            frame['after']['subject']['capturedEpochMs'],require_location=False)

    def test_changed_original_png_and_changed_retirement_headers_are_rejected_after_recreation(self):
        result=self.model.stereo().acquire(TICKET);path=self.model.artifacts/result['image']['name'];raw=path.read_bytes()
        path.write_bytes(raw[:-1])
        with self.assertRaises(NativeUIError):self.model.stereo()
        path.write_bytes(raw)
        disk_path=self.model.root/'navigation-stereo.json';disk=json.loads(disk_path.read_text());state=unpack(disk['payload'])[0]
        state['proof']['files']['absent']['source']['complete']=False;disk['payload']=pack([state]);disk_path.write_text(json.dumps(disk));disk_path.chmod(0o600)
        with self.assertRaises(NativeUIError):self.model.stereo()

if __name__=='__main__':unittest.main()
