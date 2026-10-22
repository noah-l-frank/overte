"""Explicit native/physics/tracking boundaries; no Pico or independent peer run."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.pico4 import lifecycle_drive
from adapters.pico4.lifecycle_drive import PicoLifecycleDrive,AvatarDisplacement,AvatarReleaseWindow
from adapters.normal_ui import NativeUIError
RUN='a'*32
ROOT=Path(__file__).resolve().parents[3]


def sample():
    return dict(sceneUrl='file:///controlled/scene.json',feetPosition=[1,2,3],bodyPosition=[1,3,3],orientation=[0,0,0,1],modelScale=1,
        sensorToWorld=[1,0,0,0,0,1,0,0,0,0,1,0,1,2,3,1],driveKeys=[0]*12,rawDriveKeys=[0]*12,disabledDriveKeys=[False]*12,
        physics=dict(ready=True,state=0,seated=False,stuck=False,linearVelocity=[0,0,0]),
        motors=dict(advancedMovement=True,actionEnabled=True,scriptedEnabled=True,actionVelocity=[0,0,0],scriptedVelocity=[0,0,0],
            scriptedTimescale=1000000,thrust=[0,0,0],pushing=False,braking=False,beingPushed=False),
        tracking={key:dict(valid=True,position=[0,1,0],rotation=[0,0,0,1]) for key in ('head','leftHand','rightHand')})


class Boundary:
    def __init__(self):
        self.clock,self.sequence,self.value,self.alive,self.ignore=0.,0,None,True,False
        self.commands,self.source,self.mutate=[],sample(),None
    def send(self,request):
        self.commands.append(deepcopy(request))
        if self.ignore:return
        self.sequence+=1
        self.value=dict(lifecycleDriveVersion=1,commandId=request['commandId'],runId=request['runId'],instance='b'*32,
            sequence=self.sequence,processId=123,capturedEpochMs=20000+round(self.clock*1000),source=deepcopy(self.source))
        if self.mutate:self.mutate(self.value)
    def read(self):return json.dumps(self.value) if self.value else ''
    def sleep(self,value):self.clock+=value
    def reader(self):return PicoLifecycleDrive(self.send,self.read,lambda:20000+round(self.clock*1000),lambda:self.alive,123,
        monotonic=lambda:self.clock,sleep=self.sleep)


class LifecycleDriveTests(unittest.TestCase):
    def test_original_drive_mask_raw_bytes_and_three_dimensional_feet_are_preserved(self):
        native=Boundary();reader=native.reader();initial=reader.capture(RUN);anchor=AvatarDisplacement(initial)
        native.source['rawDriveKeys'][2]=.8;native.source['driveKeys'][2]=.8
        native.source['feetPosition']=[1.125,2.25,3.5];current=reader.capture(RUN)
        actual=anchor.measure(current)
        self.assertEqual(['forward'],actual['heldInputs']);self.assertEqual([.125,.25,.5],actual['positionDelta'])
        self.assertAlmostEqual((.125**2+.25**2+.5**2)**.5,actual['worldDisplacement'])
        self.assertEqual(native.read(),reader.last_raw);self.assertEqual(hashlib.sha256(native.read().encode()).hexdigest(),reader.last_sha256)
        self.assertEqual([1,2,3],anchor.original['source']['feetPosition'])
        native.source['disabledDriveKeys'][2]=True;native.source['driveKeys'][2]=0
        self.assertEqual([],anchor.measure(reader.capture(RUN))['heldInputs'])
        self.assertEqual(.8,reader.previous['source']['rawDriveKeys'][2])
        native.source['disabledDriveKeys'][2]=False
        native.source['driveKeys'][2]=native.source['rawDriveKeys'][2]=-.8
        self.assertEqual(['backward'],anchor.measure(reader.capture(RUN))['heldInputs'])
    def test_disabled_advanced_movement_or_action_motor_is_not_effective_held_input(self):
        for key in ('advancedMovement','actionEnabled'):
            native=Boundary();reader=native.reader();anchor=AvatarDisplacement(reader.capture(RUN))
            native.source['driveKeys'][2]=native.source['rawDriveKeys'][2]=.8;native.source['motors'][key]=False
            self.assertEqual([],anchor.measure(reader.capture(RUN))['heldInputs'])
    def test_unavailable_tracking_or_ground_never_becomes_grounded_movement(self):
        faults=(lambda v:v['source']['tracking']['head'].update(valid=False),lambda v:v['source']['physics'].update(ready=False),
            lambda v:v['source']['physics'].update(state=2),lambda v:v['source']['physics'].update(seated=True),
            lambda v:v['source']['physics'].update(stuck=True),lambda v:v['source'].update(sceneUrl='file:///other-scene.json'),
            lambda v:v['source'].update(modelScale=2))
        for fault in faults:
            native=Boundary();reader=native.reader();anchor=AvatarDisplacement(reader.capture(RUN));native.mutate=fault
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):anchor.measure(reader.capture(RUN))
    def test_raw_mask_inconsistency_nonfinite_physics_malformed_transform_and_fake_expected_effect_fail(self):
        faults=(lambda v:v['source']['driveKeys'].__setitem__(2,-.8),lambda v:v['source']['feetPosition'].__setitem__(0,float('nan')),
            lambda v:v['source']['sensorToWorld'].__setitem__(0,-1),lambda v:v['source']['sensorToWorld'].__setitem__(15,0),
            lambda v:v['source']['orientation'].__setitem__(3,0),lambda v:v['source'].update(worldAttempts=2),
            lambda v:v.update(worldDisplacement=.8),lambda v:v['source']['physics'].update(state=True),
            lambda v:v['source']['disabledDriveKeys'].__setitem__(0,0))
        for fault in faults:
            native=Boundary();native.mutate=fault
            with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError)):native.reader().capture(RUN)
    def test_host_reconstruction_keeps_actual_avatar_instance_pid_run_and_native_cursors(self):
        for fault in (dict(instance='f'*32),dict(processId=124),dict(runId='f'*32),dict(sequence=1),dict(capturedEpochMs=1)):
            native=Boundary();reader=native.reader();first=reader.capture(RUN);restored=native.reader();restored.restore(first)
            native.mutate=lambda value:value.update(fault)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):restored.capture(RUN)
            self.assertEqual(first,restored.previous)
    def test_final_guard_and_continuity_cannot_age_a_sample_under_a_frozen_device_clock(self):
        for fault in ('accept','guard'):
            native=Boundary();reader=native.reader();reader.clock_ms=lambda:20000
            if fault=='accept':
                original=lifecycle_drive.continuity
                def slow(*args):
                    value=original(*args);native.clock+=2;return value
                with mock.patch.object(lifecycle_drive,'continuity',side_effect=slow):
                    with self.assertRaises(NativeUIError):reader.capture(RUN)
            else:
                calls=0
                def guard():
                    nonlocal calls
                    calls+=1
                    if calls==4:native.clock+=2
                    return True
                reader.guard=guard
                with self.assertRaises(NativeUIError):reader.capture(RUN)
            self.assertIsNone(reader.previous)
    def test_ignored_query_oversize_bytes_and_lost_process_fail_without_reissuing(self):
        native=Boundary();native.ignore=True
        with self.assertRaises(NativeUIError):native.reader().capture(RUN)
        self.assertEqual(1,len(native.commands));self.assertLessEqual(native.clock,5.1)
        native=Boundary();reader=native.reader();reader.original=lambda:' '*262145
        with mock.patch.object(lifecycle_drive,'decode') as decoder:
            with self.assertRaises(NativeUIError):reader.capture(RUN)
            decoder.assert_not_called()
        native=Boundary();native.alive=False
        with self.assertRaises(NativeUIError):native.reader().capture(RUN)
        self.assertEqual([],native.commands)
    def test_current_three_axis_stability_needs_three_seconds_on_both_original_clocks(self):
        native=Boundary();reader=native.reader();anchor=AvatarDisplacement(reader.capture(RUN));quiet=AvatarReleaseWindow(anchor)
        self.assertFalse(quiet.observe(reader.capture(RUN),0))
        for index in range(1,6):
            native.clock=index*.5;self.assertFalse(quiet.observe(reader.capture(RUN),native.clock))
        native.clock=3.;self.assertTrue(quiet.observe(reader.capture(RUN),3.))
        native.source['feetPosition'][0]+=.026;native.clock=3.1
        self.assertFalse(quiet.observe(reader.capture(RUN),3.1))
        for index in range(1,6):
            native.clock=3.1+index*.5;self.assertFalse(quiet.observe(reader.capture(RUN),native.clock))
        native.clock=6.101;self.assertTrue(quiet.observe(reader.capture(RUN),6.101))
    def test_constant_distance_arc_resets_quiet_and_original_norm_does_not_hide_movement(self):
        native=Boundary();reader=native.reader();anchor=AvatarDisplacement(reader.capture(RUN));quiet=AvatarReleaseWindow(anchor)
        native.source['feetPosition']=[2,2,3];first=reader.capture(RUN);self.assertFalse(quiet.observe(first,0))
        native.clock=.5;native.source['feetPosition']=[1,2,4];second=reader.capture(RUN)
        self.assertEqual(anchor.measure(first)['worldDisplacement'],anchor.measure(second)['worldDisplacement'])
        self.assertNotEqual(anchor.measure(first)['positionDelta'],anchor.measure(second)['positionDelta'])
        self.assertFalse(quiet.observe(second,.5))
        for index in range(2,7):
            native.clock=index*.5;self.assertFalse(quiet.observe(reader.capture(RUN),native.clock))
        native.clock=3.5;self.assertTrue(quiet.observe(reader.capture(RUN),3.5))
    def test_release_never_borrows_a_previous_held_frame_or_an_unobserved_gap(self):
        native=Boundary();reader=native.reader();anchor=AvatarDisplacement(reader.capture(RUN));quiet=AvatarReleaseWindow(anchor)
        self.assertFalse(quiet.observe(reader.capture(RUN),0))
        native.clock=.5;native.source['driveKeys'][2]=native.source['rawDriveKeys'][2]=.8
        self.assertFalse(quiet.observe(reader.capture(RUN),.5))
        native.clock=.75;native.source['driveKeys'][2]=native.source['rawDriveKeys'][2]=0
        self.assertFalse(quiet.observe(reader.capture(RUN),.75))
        for index in range(1,6):
            native.clock=.75+index*.5;self.assertFalse(quiet.observe(reader.capture(RUN),native.clock))
        native.clock=3.75;self.assertTrue(quiet.observe(reader.capture(RUN),3.75))
        native.clock=5.25;self.assertFalse(quiet.observe(reader.capture(RUN),5.25)) # Missing observations reset quiet.

    def test_future_native_window_cannot_replace_host_time_or_a_replayed_sample(self):
        native=Boundary();reader=native.reader();anchor=AvatarDisplacement(reader.capture(RUN));quiet=AvatarReleaseWindow(anchor)
        first=reader.capture(RUN);self.assertFalse(quiet.observe(first,0))
        native.clock=4;last=reader.capture(RUN);self.assertFalse(quiet.observe(last,0))
        with self.assertRaises(NativeUIError):quiet.observe(last,4)


class LifecycleDriveProbeTests(unittest.TestCase):
    def test_original_probe_forwards_only_original_native_payload_or_explicit_unavailable(self):
        source=(ROOT/'tests/device/probe/overte_e2e_probe.js').read_text();action=source.index('command.action === "feature-lifecycle-drive-observe"')
        start=source.rfind('        if (command &&',0,action);end=source.index('        if (command &&',action)
        harness=r'''
const assert=require('node:assert/strict');let lastLifecycleDriveRequest='',saved=[],calls=[],result;
const objectKeysMatch=(value,keys)=>Object.keys(value).sort().join('|')===keys.sort().join('|');
const Test={featureLifecycleDriveObservation:value=>{calls.push(value);return result;},saveObject:(value,file)=>saved.push({value,file})};
function apply(command){BODY}
const command={schemaVersion:1,commandId:'a'.repeat(32),runId:'b'.repeat(32),action:'feature-lifecycle-drive-observe'};
result={...command,original:true};apply(command);assert.strictEqual(saved[0].value,result);
apply(command);assert.equal(calls.length,1);
for (const bad of [{...command,commandId:'c'.repeat(32),expected:[]},{...command,commandId:'c'.repeat(32),schemaVersion:true}])apply(bad);
assert.equal(calls.length,1);result=null;apply({...command,commandId:'c'.repeat(32)});
assert.equal(saved[1].value.available,false);assert.equal(saved[1].file,'feature-lifecycle-drive.json');
'''.replace('BODY',source[start:end])
        subprocess.run(['node','-e',harness],check=True,timeout=5)


if __name__=='__main__':unittest.main()
