"""Normal QML/Delete ancestry plus original weak-consumer quiet sources.

Native/parser/controller/cache/scene behavior remains a declared boundary.
External cache eviction is a test event; the adapter never clears the cache.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.assets_model_removal import OwnedAssetsModelRemoval
from ios.adapters import assets_geometry_release as release
from ios.self_tests.assets_geometry_release_fixture import Fixture


def census(root):
    return {p.name:(p.stat().st_dev,p.stat().st_ino,p.stat().st_size,hashlib.sha256(p.read_bytes()).hexdigest())
        for p in root.iterdir() if p.is_file()}


class AssetsGeometryReleaseFlowTests(unittest.TestCase):
    def test_original_normal_delete_cache_survival_external_eviction_and_three_quiet_originals(self):
        root=Path(tempfile.mkdtemp(prefix='assets-geometry-release-flow-'));root.chmod(0o700)
        print('owned original root',root,flush=True)
        f=Fixture(root);self.addCleanup(f.close)
        self.enterContext(patch('adapters.asset_backend_client.build_opener',return_value=f))
        parsed=f.prepared_removal();owner=OwnedAssetsModelRemoval(parsed,PrivateFeatureState(f.path('model-removal')),lock=f.lock)
        owner.reserve();removed=owner.remove();owner.close_context()
        target=owner.target();source=f.scene(parsed);source.reserve();source.capture(source.epoch_ms())
        self.assertNotIn(target,f.boundary.models);self.assertNotIn(target,f.boundary.entities)
        self.assertFalse(removed['resources'][0]['originalLeaseAlive']);self.assertTrue(removed['resources'][0]['objectAlive'])
        with self.assertRaises(NativeUIError):release.compose(owner,source,deepcopy(source.state['frames']))
        # A separate event drops the actual last controlled cache owner. No
        # source, adapter or fixture observation sets a retirement verdict.
        f.boundary.external_cache_eviction(target)
        references=[]
        for _ in range(3):
            source.capture(source.epoch_ms());references.append(deepcopy(source.state['frames'][-1]));f.boundary.sleep(1.6)
        commands=deepcopy(f.boundary.native_clock.commands);inputs=deepcopy(f.boundary.inputs);requests=deepcopy(f.requests);files=census(root)
        with (patch.object(PrivateFeatureState,'write',side_effect=AssertionError('pure release write')),
              patch.object(source.native,'read',side_effect=AssertionError('pure release native read')),
              patch.object(owner.native,'capture',side_effect=AssertionError('pure release UI read')),
              patch.object(owner.native,'deliver',side_effect=AssertionError('pure release normal input')),
              patch('subprocess.Popen',side_effect=AssertionError('pure release process')),
              patch('socket.socket',side_effect=AssertionError('pure release socket'))):
            observed=release.compose(owner,source,references)
            self.assertTrue(observed['originalConsumersGone']);self.assertFalse(observed['resourceRetirementAvailable'])
            self.assertEqual(removed['inputCommandId'],observed['removalCommandId']);self.assertEqual(references,observed['sourceOriginals'])
            self.assertTrue(all(value['allKnownGeometryDead'] and not value['hfmAlive'] for value in observed['observations']))
            self.assertEqual(files,census(root))
            for invalid in (references[:-1],list(reversed(references)),[references[-1]]):
                with self.assertRaises(NativeUIError):release.compose(owner,source,invalid)
            old=owner.state['contextClosedBy'];owner.state['contextClosedBy']=None
            try:
                with self.assertRaises(NativeUIError):release.compose(owner,source,references)
            finally:owner.state['contextClosedBy']=old
        self.assertEqual(commands,f.boundary.native_clock.commands);self.assertEqual(inputs,f.boundary.inputs);self.assertEqual(requests,f.requests)
        self.assertEqual(1,len([row for row in owner.state['inputs'] if row['controlId']=='create.delete']))
