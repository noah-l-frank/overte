"""Held Scene2 composes actual Node/weak/file/pixels with modeled native caches."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters.web_closures import drained_owned_resources
from ios.self_tests.avatar_scene_fixture import SceneDomain


class AvatarHeldSceneTests(unittest.TestCase):
    def test_actual_marker_weak_file_sampler_pixels_and_quiet_do_not_retire_live_native_caches(self):
        f=SceneDomain(self,held=True);scene=f.prepare();after=scene.endpoints()
        self.assertEqual(2,scene.previous['iosAvatarSceneVersion']);self.assertEqual('released',f.scope.state['phase'])
        image=scene.restoration(after);scene.quiet(image)
        frames=[f.scope.frames[row['scope']-1] for row in scene.state['quiet']]
        self.assertTrue(f.scope.quiet_interval(frames[0],frames[-1]))
        actual=scene.resource_quiet(frames[-1],f.scope)
        self.assertTrue(actual['web']['holders']);self.assertTrue(actual['ui']['holders'])
        self.assertTrue(all(row['kind']=='qt-root' for row in actual['ui']['holders']))
        self.assertTrue(actual['process']['original']['processId']==31)
        with self.assertRaises(NativeUIError):drained_owned_resources(frames[-1]['web'],f.scope.frames[f.scope.state['webAdmission']-1]['web'])
        self.assertEqual(1,f.domain.io.actions.count('scripts.stop.0'))
        self.assertIsNone(scene.state['pending']);self.assertFalse(scene.state['records'])


if __name__=='__main__':unittest.main()
