"""Normal Delete/Home ancestry with independent actual model sharing holders.

Native/parser/cache/renderer behavior is explicitly modeled. Two external
model events release cache and renderer references; neither is an adapter input.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import gc
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.assets_model_removal import OwnedAssetsModelRemoval
from ios.adapters import assets_strong_release as release,assets_model_origin as origin
from ios.self_tests.assets_strong_release_fixture import Fixture


def census(root):
    result={}
    for path in root.rglob('*'):
        if not path.is_file():continue
        value=path.stat();result[str(path.relative_to(root))]=(value.st_dev,value.st_ino,value.st_mode,value.st_uid,
            value.st_gid,value.st_nlink,value.st_size,value.st_mtime_ns,value.st_ctime_ns,hashlib.sha256(path.read_bytes()).hexdigest())
    return result


class AssetsStrongReleaseFlowTests(unittest.TestCase):
    def test_normal_delete_cached_geometry_end_still_blocks_on_external_mesh_material_then_quiet_originals(self):
        root=Path(tempfile.mkdtemp(prefix='assets-strong-release-flow-'));root.chmod(0o700)
        print('owned original root',root,flush=True)
        f=Fixture(root);self.addCleanup(f.close)
        self.enterContext(patch('adapters.asset_backend_client.build_opener',return_value=f))
        parsed=f.prepared_removal();owner=OwnedAssetsModelRemoval(parsed,PrivateFeatureState(f.path('model-removal')),lock=f.lock)
        owner.reserve();target=owner.target();external=f.boundary.external_renderer_consumer(target)
        removed=owner.remove();owner.close_context()
        source=f.scene(parsed);source.reserve();source.capture(source.epoch_ms())
        self.assertTrue(removed['resources'][0]['objectAlive']);self.assertNotIn(target,f.boundary.models)
        # Explicit external modeled cache eviction, without releasing the
        # independent renderer's actual mesh/material shared model holders.
        f.boundary.external_cache_eviction(target)
        held=[]
        for _ in range(3):
            source.capture(source.epoch_ms());held.append(deepcopy(source.state['frames'][-1]));f.boundary.sleep(1.6)
        packet=source.originals.read(source.originals.expand(held[-1]))['scene']['originals']['origin']
        reader=parsed.state['result']['readerId'];geometry=origin.geometry_consumers(packet,reader)
        self.assertTrue(geometry['allKnownGeometryDead']);self.assertFalse(geometry['resourceObjectAlive']);self.assertFalse(geometry['hfmAlive'])
        strong=origin.strong_consumers(packet,reader);self.assertFalse(strong['allKnownStrongOwnersGone'])
        self.assertTrue(any(row['kind']=='material' and row['strongOwnersAlive'] for row in strong['consumers']))
        with self.assertRaises(NativeUIError):release.compose(owner,source,held)
        # A second, separately declared model stimulus drops the independent
        # consumer. No source/getter/adapter invents or performs this release.
        del external;gc.collect();references=[]
        for _ in range(3):
            source.capture(source.epoch_ms());references.append(deepcopy(source.state['frames'][-1]));f.boundary.sleep(1.6)
        commands=deepcopy(f.boundary.native_clock.commands);inputs=deepcopy(f.boundary.inputs);requests=deepcopy(f.requests);files=census(root)
        with (patch.object(PrivateFeatureState,'write',side_effect=AssertionError('pure strong release write')),
              patch.object(source.native,'read',side_effect=AssertionError('pure strong release native read')),
              patch.object(owner.native,'capture',side_effect=AssertionError('pure strong release UI read')),
              patch.object(owner.native,'deliver',side_effect=AssertionError('pure strong release input')),
              patch('subprocess.Popen',side_effect=AssertionError('pure strong release process')),
              patch('socket.socket',side_effect=AssertionError('pure strong release socket'))):
            observed=release.compose(owner,source,references)
            self.assertTrue(observed['originalMeshMaterialOwnersGone']);self.assertFalse(observed['destructorCompletionAvailable'])
            self.assertFalse(observed['resourceRetirementAvailable'])
            self.assertEqual(removed['inputCommandId'],observed['geometryRelease']['removalCommandId'])
            self.assertEqual(references,observed['geometryRelease']['sourceOriginals'])
            self.assertTrue(all(row['allKnownStrongOwnersGone'] for row in observed['observations']))
            self.assertEqual(files,census(root))
        self.assertEqual(commands,f.boundary.native_clock.commands);self.assertEqual(inputs,f.boundary.inputs);self.assertEqual(requests,f.requests)
        self.assertEqual(1,len([row for row in owner.state['inputs'] if row['controlId']=='create.delete']))
        self.assertEqual('observed',parsed.state['phase']);self.assertEqual('model-gone',owner.state['phase'])
