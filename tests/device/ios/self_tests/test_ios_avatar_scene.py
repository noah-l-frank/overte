"""Complete ordinary marker/API weak/file/PNG/source Scene composition."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
import gc
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.self_tests.avatar_scene_fixture import SceneDomain
from ios.adapters.avatar_scene import IOSAvatarScene,Frozen


class AvatarSceneTests(unittest.TestCase):
    def test_normal_script_real_weak_objects_files_png_and_all_quiet_sources_compose(self):
        f=SceneDomain(self);scene=f.prepare();ref=scene.capture(ticket='c'*32,phase_instance=f.journal.phase_instance,sequence=1)
        proof=scene.derive(ref);self.assertEqual(['account-session'],proof['scene']['remaining']);self.assertEqual('released',f.scope.state['phase'])
        commands=sum(len(gpu.commands) for gpu in f.gpus.values());native=len(f.domain.boundary.commands)
        archived=IOSAvatarScene.archive(scene.previous,store=Frozen(scene.store.path,scene.previous),root=f.root,binding=f.scope.binding,
            run=f.scope.run,role='primary',lock=f.lock)
        self.assertEqual(proof,archived.derive(ref));self.assertEqual(commands,sum(len(gpu.commands) for gpu in f.gpus.values()))
        self.assertEqual(native,len(f.domain.boundary.commands))

    def test_actual_retained_marker_weak_object_blocks_scene_then_distinct_read_recovers_without_repeating_stop(self):
        f=SceneDomain(self);scene=f.prepare();identity=f.scope.state['admission']['marker']['id'];retained=f.entity.native.items[identity]
        with self.assertRaises(NativeUIError):scene.capture(ticket='c'*32,phase_instance=f.journal.phase_instance,sequence=1)
        self.assertEqual('released',f.scope.state['phase']);self.assertEqual(1,f.domain.io.actions.count('scripts.stop.0'))
        del retained;gc.collect();ref=scene.capture(ticket='c'*32,phase_instance=f.journal.phase_instance,sequence=1)
        scene.derive(ref);self.assertEqual(1,f.domain.io.actions.count('scripts.stop.0'))

    def test_stale_rendered_pixels_remain_untouched_originals_before_later_distinct_clean_frame(self):
        f=SceneDomain(self);scene=f.prepare();f.stale_pixels=True
        with self.assertRaises(NativeUIError):scene.capture(ticket='c'*32,phase_instance=f.journal.phase_instance,sequence=1)
        files={path.name:(path.stat().st_ino,path.read_bytes()) for path in f.root.glob('vulkan-world-*.png')}
        f.stale_pixels=False;ref=scene.capture(ticket='c'*32,phase_instance=f.journal.phase_instance,sequence=1);scene.derive(ref)
        self.assertEqual(1,f.domain.io.actions.count('scripts.stop.0'))
        for name,(inode,raw) in files.items():self.assertEqual((inode,raw),((f.root/name).stat().st_ino,(f.root/name).read_bytes()))

    def test_lost_complete_scene_file_return_is_adopted_without_native_or_normal_input_replay(self):
        f=SceneDomain(self);scene=f.prepare();write=PrivateFeatureState.write;lost=[]
        def writing(store,value,previous):
            write(store,value,previous)
            if store.path==scene.file(1).path and not lost:lost.append(True);raise OSError('Lost completed Scene original return')
        with patch.object(PrivateFeatureState,'write',writing),self.assertRaises(OSError):scene.capture(ticket='c'*32,phase_instance=f.journal.phase_instance,sequence=1)
        commands=len(f.domain.boundary.commands);inputs=list(f.domain.io.actions)
        rebuilt=IOSAvatarScene(f.runtime,'target',f.source,f.scope,f.samples,scene.baseline,scene.clock,epoch_ms=f.scope.epoch_ms,
            monotonic=f.scope.monotonic,sleep=f.scope.sleep)
        with self.assertRaises(NativeUIError):rebuilt.capture(ticket='c'*32,phase_instance=f.journal.phase_instance,sequence=1)
        self.assertEqual(commands,len(f.domain.boundary.commands));self.assertEqual(inputs,f.domain.io.actions)
        old=rebuilt.state['records'][0];rebuilt.derive(old);fresh=rebuilt.refresh(ticket='c'*32,phase_instance=f.journal.phase_instance,sequence=2)
        self.assertNotEqual(old,fresh);self.assertEqual(2,rebuilt.derive(fresh)['scene']['sequence'])


if __name__=='__main__':unittest.main()
