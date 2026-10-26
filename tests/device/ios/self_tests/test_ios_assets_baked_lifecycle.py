"""New fresh upload/parser/namespace/Model/client/server host composition."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from feature_journeys.fixtures import pinned_resource
from ios.adapters.assets_baked_tree import OwnedAssetsBakedTree
from ios.adapters.assets_model_removal import OwnedAssetsModelRemoval
from ios.adapters.assets_runtime import IOSAssetsRuntime
from ios.adapters.assets_session_owners import inspect_directory
from ios.self_tests.assets_baked_tree_fixture import Fixture,RUN


class AssetsBakedLifecycleTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.path=Path(temporary.name);self.path.chmod(0o700)
        self.fixture=Fixture(self.path);self.addCleanup(self.fixture.close);self.fixture.boundary.reads.resource='asset-stand.fbx'
        self.enterContext(patch('adapters.asset_backend_client.build_opener',return_value=self.fixture))
        self.runtime=IOSAssetsRuntime(SimpleNamespace(_candidate_guard=lambda:True,_binding=lambda:None),monotonic=self.fixture.boundary.monotonic)

    def prepare(self,parts):
        return self.runtime._assets_upload_model_bytes('test-only',RUN,'primary',self.fixture.files.url,'b'*32,self.fixture.lock,self.fixture.backend.config,parts=parts)

    def test_existing_foreign_hash_blocks_before_upload_and_implicit_bake(self):
        fixture=self.fixture;fixture.shared_original(pinned_resource('asset-stand.fbx'));parts=fixture.parts()
        with self.assertRaises(NativeUIError):self.prepare(parts)
        self.assertEqual(0,fixture.boundary.host_state['uploads']);self.assertEqual([],fixture.implicit_jobs)
        self.assertEqual('ready',parts['upload'].state['phase']);self.assertIn('/foreign/shared.fbx',fixture.backend.mappings)
        self.assertFalse(any(event['kind']=='baking-started' for event in fixture.boundary.host_state['bundleInfo']['serviceEvents']))

    def test_fresh_baked_namespace_and_model_remove_with_actual_clients_and_backend_restored_but_live_cache(self):
        fixture=self.fixture;parts=fixture.parts();self.prepare(parts);backend=parts['backend'];parsed=parts['parsed']
        tree=OwnedAssetsBakedTree(parsed,PrivateFeatureState(fixture.path('baked-tree')),lock=fixture.lock)
        tree.reserve();tree.browse();tree.rename();tree.delete();delta=tree.deletion()
        self.assertEqual('deleted',tree.state['phase']);self.assertEqual(2,len(delta['mappings']['derived']));self.assertFalse(delta['resourceRetirementAvailable'])
        self.assertEqual(fixture.backend.initial,fixture.backend.mappings)
        self.assertEqual(fixture.backend.initial_names,{path.name for path in fixture.backend.b.files.iterdir()})
        # The original Model still exists and retains its actual accepted input
        # after namespace removal. Its cache is not deleted by the test adapter.
        target=parsed.state['result']['entityId'];self.assertIn(target,fixture.boundary.entities)
        fixture.boundary.attach_create();removal=OwnedAssetsModelRemoval(parsed,PrivateFeatureState(fixture.path('model-removal')),lock=fixture.lock)
        removal.reserve();proof=removal.remove();removal.close_context();removal.close_parent_clients();tree.close_clients()
        first=self.runtime._assets_backend_checkpoint(backend,'baked-restore-first','b'*32);self.assertTrue(backend.quiescent_baseline(first))
        fixture.boundary.sleep(3.1);last=self.runtime._assets_backend_checkpoint(backend,'baked-restore-last','b'*32);self.assertTrue(backend.quiescent_baseline(last))
        restored=backend.restore('baked-restore-first','baked-restore-last');self.assertIsNotNone(restored);self.assertEqual('restored',backend.state['phase'])
        self.assertTrue(proof['resources'][0]['objectAlive']);self.assertTrue(proof['resources'][0]['hfmAlive'])
        self.assertIsNotNone(fixture.boundary.origin_weaks[target]['object']());self.assertIsNotNone(fixture.boundary.origin_weaks[target]['hfm']())
        self.assertEqual('primary-chosen',fixture.picker.state['phase']);self.assertEqual('retired',parts['upload'].state['phase'])
        inputs=deepcopy(fixture.boundary.inputs);requests=deepcopy(fixture.requests);clocks=deepcopy(fixture.boundary.native_clock.commands)
        rows=inspect_directory(self.path);responsibilities=rows[0]['responsibilities']
        self.assertNotIn('server-retirement',responsibilities);self.assertNotIn('baked-mapping-actions',responsibilities);self.assertNotIn('baked-mapping-client',responsibilities)
        self.assertIn('model-removal-resources',responsibilities);self.assertIn('parsed-resource-retirement',responsibilities)
        self.assertEqual(inputs,fixture.boundary.inputs);self.assertEqual(requests,fixture.requests);self.assertEqual(clocks,fixture.boundary.native_clock.commands)
