"""Synthetic original camera-buffer evidence; no GL, compiler or device execution."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest

from adapters.normal_ui import NativeUIError
from self_tests.test_stereo_render_trace import TraceBoundary
from self_tests.test_stereo_world_render import identity


class CameraBoundary(TraceBoundary):
    def __init__(self,technique='doubled'):
        super().__init__();self.uniform_sequence=1000;self.technique=technique;self.mutate=self.uniforms

    def uniforms(self,packet):
        self.traced(packet);source=packet['source'];source['captureVersion']=4
        trace=source['renderTrace'];trace['traceVersion']=4;trace['cameraBatches']=[]
        for batch_index,draws in enumerate((5,7,4)):
            cameras=[]
            for eye in range(2):
                view=identity();view[12]=.032 if eye==0 else -.032;view[14]=.1
                projection=deepcopy(source['stereo']['eyes'][eye]['projection']);projection[8]=.02
                cameras.append(dict(slot=0,eye=('left','right')[eye],view=view,projection=projection,
                    viewport=[0,0,8,6],drawViewport=[0,0,8,6] if self.technique=='instanced' else [4*eye,0,4,6],
                    stereoInfo=[1,eye,1/8,1/6],drawCommands=draws))
            trace['cameraBatches'].append(dict(sequence=self.uniform_sequence+batch_index,frameIndex=self.frame,
                executionSequence=self.execution,rawDrawCommands=draws,executedDrawCommands=draws,
                role='mirror' if batch_index==2 else 'forward',technique=self.technique,cameras=cameras))

    def advance(self):super().advance();self.uniform_sequence+=3


class StereoCameraUniformTests(unittest.TestCase):
    def test_original_used_camera_views_retain_late_pose_and_projection_jitter_without_reconstruction(self):
        for technique in ('doubled','instanced'):
            with self.subTest(technique=technique):
                boundary=CameraBoundary(technique);reader=boundary.reader(stereo=True,require_cameras=True)
                packet,raw=reader.read(0);source=packet['source']
                self.assertEqual(boundary.raw,raw);left=source['renderTrace']['cameraBatches'][0]['cameras'][0]
                self.assertNotEqual(source['stereo']['cameraView'],left['view'])
                self.assertNotEqual(source['stereo']['eyes'][0]['projection'],left['projection'])
                self.assertEqual(.1,left['view'][14]);self.assertEqual(.02,left['projection'][8])
                boundary.advance();reader.read(packet['sequence'])

    def test_legacy_trace_cannot_supply_required_actual_camera_uniforms(self):
        boundary=TraceBoundary()
        with self.assertRaises(NativeUIError):boundary.reader(stereo=True,require_cameras=True).read(0)
        self.assertEqual([],boundary.reads)
        self.assertEqual(4,CameraBoundary().reader(stereo=True).read(0)[0]['source']['captureVersion'])

    def test_camera_evidence_cannot_come_from_foreign_batch_frame_or_execution(self):
        faults=[lambda batch:batch.update(frameIndex=101),lambda batch:batch.update(executionSequence=201),
            lambda batch:batch.update(sequence=0),lambda batch:batch.update(rawDrawCommands=6),
            lambda batch:batch.update(executedDrawCommands=0),lambda batch:batch.update(technique='mono')]
        for fault in faults:
            with self.subTest(fault=fault):
                boundary=CameraBoundary();original=boundary.mutate
                boundary.mutate=lambda packet:(original(packet),fault(packet['source']['renderTrace']['cameraBatches'][0]))
                with self.assertRaises(NativeUIError):boundary.reader(stereo=True,require_cameras=True).read(0)
                self.assertEqual([],boundary.reads)

    def test_missing_repeated_unbounded_or_relabelled_camera_batches_fail_before_pixels(self):
        faults=[lambda trace:trace.pop('cameraBatches'),lambda trace:trace.update(cameraBatches=[]),
            lambda trace:trace.update(cameraBatches=trace['cameraBatches']*2),lambda trace:trace.update(traceVersion=3),
            lambda trace:trace['cameraBatches'][1].update(sequence=1000)]
        for fault in faults:
            with self.subTest(fault=fault):
                boundary=CameraBoundary();original=boundary.mutate
                boundary.mutate=lambda packet:(original(packet),fault(packet['source']['renderTrace']))
                with self.assertRaises(NativeUIError):boundary.reader(stereo=True,require_cameras=True).read(0)
                self.assertEqual([],boundary.reads)

    def test_uniform_range_eye_viewport_matrix_and_draw_coverage_are_original(self):
        changes=[dict(eye='right'),dict(slot=True),dict(view=[0]*16),dict(projection=identity()),
            dict(viewport=[0,0,4,6]),dict(drawViewport=[4,0,4,6]),dict(drawViewport=[0,0,8,6]),
            dict(stereoInfo=[1,0,.5,1/6]),dict(stereoInfo=[True,0,1/8,1/6]),dict(drawCommands=0),
            dict(drawCommands=6)]
        for change in changes:
            with self.subTest(change=change):
                boundary=CameraBoundary();original=boundary.mutate
                boundary.mutate=lambda packet:(original(packet),packet['source']['renderTrace']['cameraBatches'][0]['cameras'][0].update(deepcopy(change)))
                with self.assertRaises(NativeUIError):boundary.reader(stereo=True,require_cameras=True).read(0)
                self.assertEqual([],boundary.reads)

    def test_duplicated_views_cannot_relabel_a_mono_camera_as_two_eyes(self):
        boundary=CameraBoundary();original=boundary.mutate
        def duplicate(packet):
            original(packet)
            for batch in packet['source']['renderTrace']['cameraBatches']:
                batch['cameras'][1]['view']=deepcopy(batch['cameras'][0]['view'])
        boundary.mutate=duplicate
        with self.assertRaises(NativeUIError):boundary.reader(stereo=True,require_cameras=True).read(0)
        self.assertEqual([],boundary.reads)

    def test_old_actual_uniform_cursor_cannot_advance_only_the_outer_frame(self):
        boundary=CameraBoundary();reader=boundary.reader(stereo=True,require_cameras=True)
        packet,_raw=reader.read(0);boundary.advance();boundary.uniform_sequence=1000
        with self.assertRaises(NativeUIError):reader.read(packet['sequence'])
        self.assertEqual(1,len(boundary.reads))


if __name__=='__main__':unittest.main()
