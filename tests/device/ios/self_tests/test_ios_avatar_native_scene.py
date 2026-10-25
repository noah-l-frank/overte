"""Original Node/API/weak/file camera endpoints before paired cleanup pixels."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from ios.adapters.avatar_feature import IOSAvatarFeature
from ios.self_tests.avatar_scene_fixture import SceneDomain


class AvatarNativeSceneTests(unittest.TestCase):
    def test_real_native_endpoints_are_historical_and_supply_no_rendered_retirement(self):
        f=SceneDomain(self);scene=f.prepare();before=sum(q['operation']=='read' for gpu in f.gpus.values() for q in gpu.commands)
        scene.endpoints();owner=object.__new__(IOSAvatarFeature)
        owner.runtime,owner.root,owner.role,owner.run,owner.selector=f.runtime,f.root,'primary',f.scope.run,'target'
        owner.lock=f.lock;owner.store=PrivateFeatureState(f.root/'ios-avatar-primary-feature.json');owner.previous=None
        owner.selectors=dict(primary='target',actor='unqueried-peer');owner.policy=scene.samples.policy;owner.phase=f.phase
        owner.state=dict(bindings=dict(primary=deepcopy(f.scope.binding)),snapshots=[],cleanup=[dict(baseline=deepcopy(scene.baseline))])
        value=dict(source=deepcopy(scene.sources.previous),recovery=None,scope=scene.scope.snapshot(),samples=deepcopy(scene.samples.previous),
            endpoints=deepcopy(scene.state['endpoints']),close=deepcopy(scene.state['close']))
        event=dict(kind='native-scene',owner=owner.keep(value));commands=len(f.domain.boundary.commands);inputs=list(f.domain.io.actions)
        proof=owner.native_scene_original(event);self.assertNotIn('public',proof);self.assertNotIn('retirement',proof)
        self.assertEqual(value,proof['original']);self.assertIsNone(scene.state['image']);self.assertEqual([],scene.state['records'])
        self.assertEqual(before,sum(q['operation']=='read' for gpu in f.gpus.values() for q in gpu.commands))
        self.assertEqual(commands,len(f.domain.boundary.commands));self.assertEqual(inputs,f.domain.io.actions)


if __name__=='__main__':unittest.main()
