"""Normal Delete/Home + actual modeled original identity/lifetime joins.

Native/Qt/GPU behavior is an explicit SDK model; cache/holder events are external
test stimuli. This does not qualify automatic cleanup, C++ or GPU completion.
"""
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
from ios.adapters import assets_image_reader_lifecycle as lifecycle,assets_texture_release as texture_release
from ios.adapters.assets_session_owners import inspect_directory
from ios.self_tests.assets_image_reader_lifecycle_fixture import Fixture
from ios.self_tests.test_ios_assets_strong_release_flow import census


class AssetsImageReaderLifecycleFlowTests(unittest.TestCase):
    def test_normal_delete_texture_groups_gone_refuses_independent_gpu_until_actual_originals_close(self):
        root=Path(tempfile.mkdtemp(prefix='assets-image-reader-lifecycle-flow-'));root.chmod(0o700)
        print('owned original root',root,flush=True)
        fixture=Fixture(root);self.addCleanup(fixture.close)
        self.enterContext(patch('adapters.asset_backend_client.build_opener',return_value=fixture))
        parsed=fixture.prepared_removal();owner=OwnedAssetsModelRemoval(parsed,PrivateFeatureState(fixture.path('model-removal')),lock=fixture.lock)
        owner.reserve();target=owner.target();images=fixture.image_sources(parsed);images.reserve();world=fixture.scene(parsed);world.reserve()
        images.capture(images.epoch_ms());world.capture(world.epoch_ms())
        baseline=dict(image=deepcopy(images.state['frames'][-1]),scene=deepcopy(world.state['frames'][-1]))
        independent_gpu=fixture.boundary.external_gpu_consumer(target);self.assertIsNotNone(independent_gpu)
        removed=owner.remove();owner.close_context()
        self.assertNotIn(target,fixture.boundary.models)
        # Explicit external MODEL cache events, never performed by adapter,
        # getter, source capture or normal Delete/Home. Keep independent GPU.
        fixture.boundary.external_cache_eviction(target);fixture.boundary.external_image_cache_eviction(target)
        held=[]
        for _ in range(3):
            images.capture(images.epoch_ms());world.capture(world.epoch_ms())
            held.append(dict(image=deepcopy(images.state['frames'][-1]),scene=deepcopy(world.state['frames'][-1])))
            fixture.boundary.sleep(1.6)
        # All observed mesh/material/map/Source owners can be gone while an
        # independently held actual Python GPU-sharing owner still exists.
        previous=texture_release.compose(owner,world,[pair['scene'] for pair in held])
        self.assertTrue(previous['originalMeshMaterialTextureOwnersGone'])
        with self.assertRaises(NativeUIError):lifecycle.compose(owner,world,images,baseline,held)
        del independent_gpu;gc.collect();pairs=[]
        for _ in range(3):
            images.capture(images.epoch_ms());world.capture(world.epoch_ms())
            pairs.append(dict(image=deepcopy(images.state['frames'][-1]),scene=deepcopy(world.state['frames'][-1])))
            fixture.boundary.sleep(1.6)
        commands=deepcopy(fixture.boundary.native_clock.commands);inputs=deepcopy(fixture.boundary.inputs)
        requests=deepcopy(fixture.requests);files=census(root)
        with (patch.object(PrivateFeatureState,'write',side_effect=AssertionError('pure lifecycle write')),
              patch.object(images.native,'read',side_effect=AssertionError('pure lifecycle query')),
              patch.object(images.readers['queue'],'read',side_effect=AssertionError('pure lifecycle queue query')),
              patch.object(owner.native,'capture',side_effect=AssertionError('pure lifecycle UI read')),
              patch.object(owner.native,'deliver',side_effect=AssertionError('pure lifecycle input')),
              patch('subprocess.Popen',side_effect=AssertionError('pure lifecycle process')),
              patch('socket.socket',side_effect=AssertionError('pure lifecycle socket'))):
            observed=lifecycle.compose(owner,world,images,baseline,pairs)
            self.assertTrue(observed['observedImageReaderLifecycleEdgesClosed'])
            self.assertEqual(removed['inputCommandId'],observed['removalCommandId'])
            self.assertEqual(pairs,observed['sourceOriginals'])
            for key in ('eventStorageCompletionAvailable','byteCopyCompletionAvailable','basePoolCompletionAvailable',
                    'decoderCompletionAvailable','destructorCompletionAvailable','gpuCompletionAvailable','resourceRetirementAvailable'):
                self.assertFalse(observed[key])
            self.assertTrue(all(row['observedDerivedMarkersAndQtArgumentCopiesGone'] for row in observed['observations']))
            self.assertEqual(files,census(root))
        self.assertEqual(commands,fixture.boundary.native_clock.commands)
        self.assertEqual(inputs,fixture.boundary.inputs);self.assertEqual(requests,fixture.requests)
        self.assertEqual(1,len([row for row in owner.state['inputs'] if row['controlId']=='create.delete']))
        self.assertEqual('model-gone',owner.state['phase'])
        responsibilities=[value for row in inspect_directory(root) for value in row['responsibilities']]
        self.assertIn('image-reader-resource-retirement',responsibilities)
        self.assertIn('model-removal-resources',responsibilities)
