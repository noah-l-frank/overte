"""Scene2 immutable record composition; modeled native/Qt/GPU boundaries.

The test requires the separately integrated held-scene protocol constants. A
draft-only subprocess may load that protocol in memory; it is not a claim that
the repository transport has been integrated.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.native_clock_join import digest
from adapters.normal_ui import NativeUIError
from ios.adapters.avatar_held_scene import IOSAvatarHeldScene
from ios.adapters.avatar_marker_lifetime import AvatarMarkerLifetime
from ios.adapters.avatar_scene import IOSAvatarScene
from ios.self_tests.avatar_scene_fixture import SceneDomain


class AvatarHeldSceneRecordTests(unittest.TestCase):
    def test_actual_scene_record_keeps_weak_cache_and_process_originals(self):
        f=SceneDomain(self,held=True);scene=f.prepare()
        reference=scene.capture(ticket='c'*32,phase_instance=f.phase.previous['instance'],sequence=1)
        proof,joined=scene.joined(reference)
        self.assertEqual(1,proof['scene']['avatarHeldMarkerSceneQuietVersion'])
        self.assertIn('native-process-resources',proof['scene']['remaining'])
        self.assertIn('marker-gpu-sampler',proof['scene']['quiet'])
        self.assertNotIn('marker-gpu',proof['scene']['quiet'])
        originals=scene.held_originals(reference)
        self.assertTrue({'qt-root','qimage','qsg-root','native-holder'}<={r['kind'] for r in originals})
        owned={path:(path.stat().st_ino,path.read_bytes()) for path in scene.root.rglob('*') if path.is_file()}
        archive=IOSAvatarHeldScene.archive(scene.previous,store=scene.store,root=scene.root,binding=scene.binding,
            run=scene.run,role=scene.role,lock=scene.lock)
        self.assertEqual(proof,archive.derive(reference));self.assertEqual(originals,archive.held_originals(reference))
        self.assertEqual(owned,{path:(path.stat().st_ino,path.read_bytes()) for path in owned})
        frame=joined['scope'].frames[joined['original']['quiet'][-1]['scope']-1]
        lifetime=AvatarMarkerLifetime(joined['scope'],frame,scene_reference=reference,binding=scene.binding,run=scene.run)
        self.assertEqual(reference,lifetime.scene_reference)
        wrong=deepcopy(frame);wrong['web']['sequence']+=1
        with self.assertRaises(NativeUIError):AvatarMarkerLifetime(joined['scope'],wrong,scene_reference=reference,binding=scene.binding,run=scene.run)
        self.assertEqual(digest(frame),digest(lifetime.scene))
        with self.assertRaises(NativeUIError):IOSAvatarScene.archive(scene.previous,store=scene.store,root=scene.root,
            binding=scene.binding,run=scene.run,role=scene.role,lock=scene.lock)


if __name__=='__main__':unittest.main()
