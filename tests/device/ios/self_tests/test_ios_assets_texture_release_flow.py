"""Normal removal plus declared external model events; no native/GPU test."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import gc
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.assets_model_removal import OwnedAssetsModelRemoval
from ios.adapters import assets_model_origin as origin,assets_texture_ownership as texture,assets_texture_release as release
from ios.self_tests.assets_texture_release_fixture import Fixture
from ios.self_tests.test_ios_assets_strong_release_flow import census


class AssetsTextureReleaseFlowTests(unittest.TestCase):
    def test_normal_delete_all_mesh_material_map_groups_gone_still_refuses_independent_source_until_quiet_originals(self):
        root=Path(tempfile.mkdtemp(prefix='assets-texture-release-flow-'));root.chmod(0o700)
        print('owned original root',root,flush=True)
        f=Fixture(root);self.addCleanup(f.close)
        self.enterContext(patch('adapters.asset_backend_client.build_opener',return_value=f))
        parsed=f.prepared_removal();owner=OwnedAssetsModelRemoval(parsed,PrivateFeatureState(f.path('model-removal')),lock=f.lock)
        owner.reserve();target=owner.target();independent_source=f.boundary.external_source_consumer(target)
        removed=owner.remove();owner.close_context()
        source=f.scene(parsed);source.reserve();source.capture(source.epoch_ms())
        self.assertTrue(removed['resources'][0]['objectAlive']);self.assertNotIn(target,f.boundary.models)
        # This is an explicit external MODEL cache event, not adapter/user/
        # product cleanup. The independent actual Source holder stays alive.
        f.boundary.external_cache_eviction(target);held=[]
        for _ in range(3):
            source.capture(source.epoch_ms());held.append(deepcopy(source.state['frames'][-1]));f.boundary.sleep(1.6)
        packet=source.originals.read(source.originals.expand(held[-1]))['scene']['originals']['origin']
        reader=parsed.state['result']['readerId'];geometry=origin.geometry_consumers(packet,reader)
        self.assertTrue(geometry['allKnownGeometryDead']);self.assertFalse(geometry['resourceObjectAlive']);self.assertFalse(geometry['hfmAlive'])
        self.assertTrue(origin.strong_consumers(packet,reader)['allKnownStrongOwnersGone'])
        facts=texture.consumers(packet,reader)
        self.assertEqual({'map':False,'source':True},{row['kind']:row['strongOwnersAlive'] for row in facts['nodes']})
        self.assertFalse(facts['allKnownTextureOwnersGone'])
        with self.assertRaises(NativeUIError):release.compose(owner,source,held)
        # Separate external MODEL holder release, followed by new originals.
        # A dead map or earlier mesh/material absence cannot perform this step.
        del independent_source;gc.collect();references=[]
        for _ in range(3):
            source.capture(source.epoch_ms());references.append(deepcopy(source.state['frames'][-1]));f.boundary.sleep(1.6)
        commands=deepcopy(f.boundary.native_clock.commands);inputs=deepcopy(f.boundary.inputs);requests=deepcopy(f.requests);files=census(root)
        with (patch.object(PrivateFeatureState,'write',side_effect=AssertionError('pure texture release write')),
              patch.object(source.native,'read',side_effect=AssertionError('pure texture release native read')),
              patch.object(owner.native,'capture',side_effect=AssertionError('pure texture release UI read')),
              patch.object(owner.native,'deliver',side_effect=AssertionError('pure texture release input')),
              patch('subprocess.Popen',side_effect=AssertionError('pure texture release process')),
              patch('socket.socket',side_effect=AssertionError('pure texture release socket'))):
            observed=release.compose(owner,source,references)
            self.assertTrue(observed['originalMeshMaterialTextureOwnersGone'])
            self.assertEqual(1,observed['assetModelTextureReleaseVersion'])
            self.assertNotIn('assetModelGeometryReleaseVersion',observed)
            for key in ('decoderCompletionAvailable','destructorCompletionAvailable','gpuCompletionAvailable','resourceRetirementAvailable'):
                self.assertFalse(observed[key])
            self.assertEqual(removed['inputCommandId'],observed['removalCommandId'])
            self.assertEqual(references,observed['sourceOriginals'])
            self.assertTrue(all(row['allKnownTextureOwnersGone'] for row in observed['textureObservations']))
            self.assertEqual(files,census(root))
        self.assertEqual(commands,f.boundary.native_clock.commands);self.assertEqual(inputs,f.boundary.inputs);self.assertEqual(requests,f.requests)
        self.assertEqual(1,len([row for row in owner.state['inputs'] if row['controlId']=='create.delete']))
        self.assertEqual('observed',parsed.state['phase']);self.assertEqual('model-gone',owner.state['phase'])
