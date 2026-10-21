"""No-build counterexamples for original Home geometry and normal VR input."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import math
import unittest

from adapters.pico4.tablet_home import PicoTabletHome,validate,validate_input,observed_grip_pose
from adapters.normal_ui import NativeUIError
from self_tests.test_pico_input_geometry import rotate


def original():
    return dict(schemaVersion=1,commandId='a'*32,action='observe',instance='b'*32,generation='b'*32,
        sourceSequence=1,lastCommandSequence=0,elapsedMs=100,capturedEpochMs=10000,processId=42,
        homeObservationVersion=1,tabletShown=True,onHomeScreen=False,tabletId='1'*32,homeId='2'*32,
        parentId='1'*32,entityType='Gizmo',entityName='homeButton',visible=True,
        ignorePickIntersection=False,hostType='local',sensorToWorld=[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1],
        headPosition=[0,1.6,0],position=[.2,1.1,-.6])


class Source:
    pid=42
    def __init__(self):self.value=original();self.clock=0
    def capture(self):return deepcopy(self.value)
    def clock_ms(self):return 10000+round(self.clock*1000)
    def monotonic(self):return self.clock
    def sleep(self,seconds):self.clock+=seconds
    def guard(self):return True


class PicoTabletHomeTests(unittest.TestCase):
    def test_calibrated_ray_intersects_actual_observed_entity_after_tracking_rotation(self):
        target=[.2,1.1,-.6];origin=[0,1.6,0]
        correction=[.6935199226610738,.1379496896414715,-.6935199226610738,-.13794968964147133]
        for yaw in (0,.42,-.42,math.pi/2):
            c,s=math.cos(yaw),math.sin(yaw)
            matrix=[c,0,-s,0,0,1,0,0,s,0,c,0,0,0,0,1]
            pose=observed_grip_pose(matrix,origin,target)
            stage_direction=rotate(pose['orientation'],rotate(correction,[0,1,0]))
            world=[c*stage_direction[0]+s*stage_direction[2],stage_direction[1],-s*stage_direction[0]+c*stage_direction[2]]
            expected=[a-b for a,b in zip(target,origin)];length=math.sqrt(sum(v*v for v in expected))
            for actual,wanted in zip(world,expected):self.assertAlmostEqual(actual,wanted/length,places=6)

    def test_stale_foreign_hidden_nonpickable_or_already_home_source_cannot_authorize_a_click(self):
        changes=[{'processId':43},{'capturedEpochMs':8000},{'capturedEpochMs':10001},
            {'parentId':'3'*32},{'homeId':'1'*32},{'entityName':'fixture-button'},
            {'entityType':'Box'},{'hostType':'domain'},{'visible':False},{'tabletShown':False},
            {'ignorePickIntersection':True},{'onHomeScreen':True},{'sensorToWorld':[0]*16}]
        for change in changes:
            with self.subTest(change=change),self.assertRaises((RuntimeError,ValueError)):
                validate_input(original()|change,42,10000,'tablet.home-ray')

    def test_actual_home_requires_no_gesture_and_does_not_toggle_the_tablet_closed(self):
        source=Source();source.value['onHomeScreen']=True
        recipe=PicoTabletHome(source,lambda _pose:self.fail('No input on actual Home'))
        self.assertTrue(recipe.ensure(lambda *_args:self.fail('No intent without input'))['onHomeScreen'])

    def test_original_intent_precedes_the_one_gesture_and_ack_is_not_a_home_verdict(self):
        source=Source();events=[]
        def stage(pose):
            self.assertEqual('intent',events[-1]);events.append('stage')
            self.assertEqual(observed_grip_pose(source.value['sensorToWorld'],source.value['headPosition'],source.value['position']),pose)
        recipe=PicoTabletHome(source,stage)
        with self.assertRaises(RuntimeError):recipe.ensure(lambda *_args:events.append('intent'))
        self.assertEqual(['intent','stage'],events)

    def test_current_home_transition_cannot_come_from_a_replacement_entity_or_process(self):
        for change in ({'homeId':'3'*32},{'instance':'c'*32},{'tabletShown':False}):
            source=Source()
            def stage(_pose):source.value.update(onHomeScreen=True,**change)
            with self.subTest(change=change),self.assertRaises(RuntimeError):PicoTabletHome(source,stage).ensure(lambda *_args:None)


if __name__=='__main__':unittest.main()
