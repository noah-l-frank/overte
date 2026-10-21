"""No-build original executing-stereo-trace counterexamples; no GPU qualification."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
import uuid

from adapters.normal_ui import NativeUIError
from adapters.world_render_evidence import validate
from self_tests.test_stereo_world_render import StereoBoundary,identity


class TraceBoundary(StereoBoundary):
    def __init__(self):
        super().__init__();self.mutate=self.traced;self.trace_id=None

    def traced(self,packet):
        self.stereo_packet(packet);source=packet['source'];source['captureVersion']=3
        projection=source['stereo']['eyes'][0]['projection']
        recorded=dict(position=[0,0,0],rotation=[0,0,0,1],projection=[projection[column*4+row]
            for row in range(4) for column in range(4)],fieldOfViewDegrees=90,aspectRatio=4/3,
            nearClip=.1,farClip=100,perspective=True)
        source['renderTrace']=dict(traceVersion=3,frameId=self.trace_id or uuid.uuid4().hex,
            frameIndex=self.frame,executionSequence=self.execution,recordedEpochMs=20000,
            recordedView=recorded,begunEpochMs=20000,completedEpochMs=20000,renderer='forward',view='main-stereo',
            forwardBatches=2,forwardDrawCommands=12,hazeBatches=1,hazeDrawCommands=10,mirrorBatches=1,mirrorDrawCommands=4)


class StereoRenderTraceTests(unittest.TestCase):
    def test_fresh_trace_retains_original_pixels_and_separate_pass_counts_on_same_submitted_frame(self):
        boundary=TraceBoundary();packet,raw=boundary.reader(stereo=True,require_trace=True).read(0)
        self.assertEqual(boundary.raw,raw);self.assertEqual(12,packet['source']['renderTrace']['forwardDrawCommands'])
        self.assertNotIn('hazePass',packet['source']);self.assertNotIn('passed',packet)
        self.assertEqual(packet,validate(packet,packet['requestId'],31,20000,stereo=True,require_trace=True))

    def test_compatible_stereo_reader_accepts_version_three_but_mono_and_missing_trace_are_refused(self):
        self.assertEqual(3,TraceBoundary().reader(stereo=True).read(0)[0]['source']['captureVersion'])
        for boundary,options in ((TraceBoundary(),{}),(StereoBoundary(),dict(stereo=True,require_trace=True))):
            with self.subTest(options=options),self.assertRaises(NativeUIError):boundary.reader(**options).read(0)
            self.assertEqual([],boundary.reads)

    def test_foreign_execution_missing_begin_or_late_completion_never_reads_pixels(self):
        faults=[lambda t:t.update(frameIndex=101),lambda t:t.update(executionSequence=201),
            lambda t:t.update(traceVersion=2),lambda t:t.update(view='main-mono'),lambda t:t.update(renderer='deferred'),
            lambda t:t.update(recordedEpochMs=19999),lambda t:t.update(begunEpochMs=0),
            lambda t:t.update(completedEpochMs=20001),lambda t:t.update(frameIndex=True)]
        for fault in faults:
            with self.subTest(fault=fault):
                boundary=TraceBoundary();original=boundary.mutate
                boundary.mutate=lambda packet:(original(packet),fault(packet['source']['renderTrace']))
                with self.assertRaises(NativeUIError):boundary.reader(stereo=True,require_trace=True).read(0)
                self.assertEqual([],boundary.reads)

    def test_draw_counts_cannot_be_requested_flags_zero_commands_or_unbounded_counts(self):
        faults=[dict(forwardBatches=0),dict(forwardDrawCommands=0),dict(hazeDrawCommands=13),
            dict(hazeBatches=3),dict(mirrorBatches=0),dict(mirrorDrawCommands=-1),dict(hazeDrawCommands=True),
            dict(forwardDrawCommands=10**10)]
        for change in faults:
            with self.subTest(change=change):
                boundary=TraceBoundary();original=boundary.mutate
                boundary.mutate=lambda packet:(original(packet),packet['source']['renderTrace'].update(change))
                with self.assertRaises(NativeUIError):boundary.reader(stereo=True,require_trace=True).read(0)
                self.assertEqual([],boundary.reads)

    def test_reused_trace_cannot_be_relabelled_as_a_new_original_frame(self):
        boundary=TraceBoundary();boundary.trace_id='c'*32;reader=boundary.reader(stereo=True,require_trace=True)
        first,_raw=reader.read(0);boundary.advance()
        with self.assertRaises(NativeUIError):reader.read(first['sequence'])
        self.assertEqual(1,len(boundary.reads))

    def test_noncentral_rotated_original_pose_matches_its_actual_column_major_view(self):
        boundary=TraceBoundary();original=boundary.mutate
        def rotated(packet):
            original(packet);source=packet['source']
            source['renderTrace']['recordedView'].update(position=[1,2,3],rotation=[0,2**-.5,0,2**-.5])
            source['stereo']['cameraView']=[0,0,1,0,0,1,0,0,-1,0,0,0,3,-2,-1,1]
        boundary.mutate=rotated
        packet,_raw=boundary.reader(stereo=True,require_trace=True).read(0)
        self.assertEqual([1,2,3],packet['source']['renderTrace']['recordedView']['position'])
        self.assertEqual({'schemaVersion','commandId','action'},set(boundary.commands[0]))

    def test_recorded_pose_and_projection_are_original_and_match_the_stereo_camera_matrix(self):
        for change in (dict(position=[.5,0,0]),dict(rotation=[0,0,0,0]),dict(projection=identity()),dict(perspective=False)):
            with self.subTest(change=change):
                boundary=TraceBoundary();original=boundary.mutate
                boundary.mutate=lambda packet:(original(packet),packet['source']['renderTrace']['recordedView'].update(deepcopy(change)))
                with self.assertRaises(NativeUIError):boundary.reader(stereo=True,require_trace=True).read(0)
                self.assertEqual([],boundary.reads)


if __name__=='__main__':unittest.main()
