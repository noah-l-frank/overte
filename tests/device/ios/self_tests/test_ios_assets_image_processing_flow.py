"""Normal Delete/Home with an independent actual Python input-buffer owner.

Qt/native/ResourceCache behavior is an explicit SDK model. External model-cache
and holder release are test stimuli, never adapter cleanup or physical GPU end.
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
from ios.adapters import assets_image_reader_lifecycle as image_lifecycle
from ios.adapters import assets_image_processing_lifecycle as processing_lifecycle
from ios.adapters.assets_session_owners import inspect_directory
from ios.self_tests.assets_image_processing_fixture import Fixture
from ios.self_tests.test_ios_assets_strong_release_flow import census


class AssetsImageProcessingFlowTests(unittest.TestCase):
    def test_normal_delete_image_edges_closed_refuses_independent_input_until_actual_originals_close(self):
        root=Path(tempfile.mkdtemp(prefix='assets-image-processing-flow-'));root.chmod(0o700)
        print('owned original root',root,flush=True)
        fixture=Fixture(root);self.addCleanup(fixture.close)
        self.enterContext(patch('adapters.asset_backend_client.build_opener',return_value=fixture))
        parsed=fixture.prepared_removal();owner=OwnedAssetsModelRemoval(parsed,PrivateFeatureState(fixture.path('model-removal')),lock=fixture.lock)
        owner.reserve();target=owner.target();images=fixture.image_sources(parsed);images.reserve()
        processing=fixture.processing_sources(parsed);processing.reserve();world=fixture.scene(parsed);world.reserve()
        def capture():
            images.capture(images.epoch_ms());processing.capture(processing.epoch_ms());world.capture(world.epoch_ms())
            return dict(image=deepcopy(images.state['frames'][-1]),processing=deepcopy(processing.state['frames'][-1]),
                scene=deepcopy(world.state['frames'][-1]))
        baseline=capture();independent_input=fixture.boundary.take_test_input(target)
        self.assertIsNotNone(independent_input)
        removed=owner.remove();owner.close_context();self.assertNotIn(target,fixture.boundary.models)
        # Explicit external MODEL cache events; the independent buffer remains
        # held by this test caller after the observed image/source owners expire.
        fixture.boundary.external_cache_eviction(target);fixture.boundary.external_image_cache_eviction(target)
        held=[]
        for _ in range(3):held.append(capture());fixture.boundary.sleep(1.6)
        image_edges=image_lifecycle.compose(owner,world,images,{key:baseline[key] for key in ('image','scene')},
            [{key:pair[key] for key in ('image','scene')} for pair in held])
        self.assertTrue(image_edges['observedImageReaderLifecycleEdgesClosed'])
        last=processing._cached[-1]['sample']['originals']['processing']['source']
        self.assertTrue(any(row['deviceOwnersAlive'] for row in last['calls']))
        with self.assertRaises(NativeUIError):processing_lifecycle.compose(owner,world,images,processing,baseline,held)
        del independent_input;gc.collect();pairs=[]
        for _ in range(3):pairs.append(capture());fixture.boundary.sleep(1.6)
        commands=deepcopy(fixture.boundary.native_clock.commands);inputs=deepcopy(fixture.boundary.inputs)
        requests=deepcopy(fixture.requests);files=census(root)
        with (patch.object(PrivateFeatureState,'write',side_effect=AssertionError('pure processing write')),
              patch.object(images.native,'read',side_effect=AssertionError('pure image query')),
              patch.object(processing.native,'read',side_effect=AssertionError('pure processing clock')),
              patch.object(processing.readers['processing'],'read',side_effect=AssertionError('pure processing query')),
              patch.object(processing.readers['reader'],'read',side_effect=AssertionError('pure processing parent query')),
              patch.object(owner.native,'capture',side_effect=AssertionError('pure processing UI read')),
              patch.object(owner.native,'deliver',side_effect=AssertionError('pure processing input')),
              patch('subprocess.Popen',side_effect=AssertionError('pure processing process')),
              patch('socket.socket',side_effect=AssertionError('pure processing socket'))):
            observed=processing_lifecycle.compose(owner,world,images,processing,baseline,pairs)
            self.assertTrue(observed['observedProcessingAndInputDeviceEdgesClosed'])
            self.assertEqual(removed['inputCommandId'],observed['removalCommandId'])
            self.assertEqual(pairs,observed['sourceOriginals'])
            for key in ('byteCopyCompletionAvailable','basePoolCompletionAvailable','decoderCompletionAvailable',
                    'gpuCompletionAvailable','resourceRetirementAvailable'):self.assertFalse(observed[key])
            self.assertTrue(all(row['observations'] for row in observed['observations']))
            self.assertEqual(files,census(root))
        self.assertEqual(commands,fixture.boundary.native_clock.commands)
        self.assertEqual(inputs,fixture.boundary.inputs);self.assertEqual(requests,fixture.requests)
        self.assertEqual(1,len([row for row in owner.state['inputs'] if row['controlId']=='create.delete']))
        self.assertEqual('model-gone',owner.state['phase'])
        responsibilities=[value for row in inspect_directory(root) for value in row['responsibilities']]
        for value in ('image-reader-resource-retirement','image-processing-resource-retirement','model-removal-resources'):
            self.assertIn(value,responsibilities)
