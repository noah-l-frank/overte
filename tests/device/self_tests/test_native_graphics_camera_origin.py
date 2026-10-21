"""Original camera/boom read contracts and reproducible ordinary-menu baseline."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.graphics_subject_geometry import steady_subject
from adapters.normal_ui import NativeUIError
from ios.adapters.graphics_scene import eligible,restored
from self_tests.test_native_graphics_subject import Boundary,RUN


def avatar_source(b):
    b.source.update(subjectVersion=2,avatarPose=dict(feetPosition=[0,-.2,0],orientation=[0,0,0,1],modelScale=1.25))


def source():
    b=Boundary();avatar_source(b)
    b.source.update(subjectVersion=3,cameraOrbit=dict(lookAtRotation=[0,0,0,1],boomLength=3.25,minimumBoomLength=0.,defaultBoomLength=3.25))
    b.source['sceneUrl']='http://controlled.invalid/original.json';b.source['view']['mode']='look at'
    return b


class CameraOriginTests(unittest.TestCase):
    def test_actual_orbit_boom_and_product_reset_constants_are_originals_not_commands(self):
        b=source();reader=b.reader(ios=True,native_clock_bound=True);value=reader.read(RUN,require_avatar=True,require_camera=True)
        self.assertEqual(b.source['cameraOrbit'],value['source']['cameraOrbit']);eligible(value)
        self.assertEqual({'schemaVersion','commandId','action','runId'},set(b.commands[0]))
        self.assertNotIn('cameraOrbit',b.commands[0]);self.assertEqual(3,value['source']['subjectVersion'])
        self.assertTrue(value['requestId'].startswith('ios-'))

    def test_v1_v2_remain_readable_but_cannot_replace_original_camera_state_for_scene_changes(self):
        for version in (1,2):
            b=Boundary()
            if version==2:avatar_source(b)
            self.assertEqual(version,b.reader().read(RUN)['source']['subjectVersion'])
            with self.subTest(version=version),self.assertRaises(NativeUIError):b.reader().read(RUN,require_camera=True)

    def test_camera_flag_is_strict_and_missing_unknown_or_nonfinite_originals_fail(self):
        for flag in (1,None,'true'):
            b=source()
            with self.assertRaises(NativeUIError):b.reader().read(RUN,require_camera=flag)
            self.assertEqual([],b.commands)
        faults=[lambda b:b.source.pop('cameraOrbit'),lambda b:b.source['cameraOrbit'].update(boomLength=True),
            lambda b:b.source['cameraOrbit'].update(defaultBoomLength=0),lambda b:b.source['cameraOrbit'].update(lookAtRotation=[0,0,0,0]),
            lambda b:b.source['cameraOrbit'].update(boomLength=float('inf')),lambda b:b.source['cameraOrbit'].update(expectedBoomLength=3.25)]
        for fault in faults:
            b=source();fault(b)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):b.reader().read(RUN,require_camera=True)

    def test_unreproducible_zoom_or_orbit_is_rejected_before_any_normal_scene_input(self):
        for mode in ('look at','selfie','first person look at'):
            b=source();b.source['view']['mode']=mode;value=b.reader().read(RUN,require_camera=True);eligible(value)
        for fault in ('zoom','orbit','mode'):
            b=source()
            if fault=='zoom':b.source['cameraOrbit']['boomLength']=2.25
            elif fault=='orbit':b.source['cameraOrbit']['lookAtRotation']=[0,.70710678,0,.70710678]
            else:b.source['view']['mode']='independent'
            value=b.reader().read(RUN,require_camera=True)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):eligible(value)
            self.assertEqual(1,len(b.commands));self.assertEqual('feature-graphics-subject-observe',b.commands[0]['action'])

    def test_ordinary_restoration_must_recover_actual_orbit_and_boom_not_just_mode(self):
        b=source();original=b.reader().read(RUN,require_camera=True);restored(original,deepcopy(original))
        for key,value in (('boomLength',2.25),('lookAtRotation',[0,.70710678,0,.70710678])):
            changed=deepcopy(original);changed['source']['cameraOrbit'][key]=value
            with self.subTest(key=key),self.assertRaises(NativeUIError):restored(original,changed)
            with self.assertRaises(NativeUIError):steady_subject(original,changed)


if __name__=='__main__':unittest.main()
