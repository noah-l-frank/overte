"""Original normal marker/import/Delete ordering, with retained live caches."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import tempfile
import unittest
from adapters.normal_feature_state import PrivateFeatureState
from ios.adapters.assets_model_removal import OwnedAssetsModelRemoval
from ios.self_tests.assets_image_removal_fixture import Fixture


class AssetsImageRemovalParentsTests(unittest.TestCase):
    def test_original_marker_before_model_keeps_unchanged_cleanup_baseline_after_normal_model_delete(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);root=Path(temporary.name);root.chmod(0o700)
        f=Fixture(self,root);baseline=f.scope.frames[f.scope.state['baseline']-1]['create']['source']
        self.assertEqual([],baseline['entities']);target=f.proof['entityId'];marker=f.scope.state['admission']['marker']['id']
        self.assertEqual({target,marker},{row['id'] for row in f.domain.current()['source']['entities']})
        f.attach_removal();owner=OwnedAssetsModelRemoval(f.parsed,PrivateFeatureState(f.f.path('model-removal')),lock=f.f.lock)
        owner.reserve();proof=owner.remove();owner.close_context()
        self.assertEqual(target,proof['entityId']);self.assertNotIn(target,f.f.boundary.models)
        self.assertEqual({marker},{row['id'] for row in f.domain.current()['source']['entities']})
        self.assertFalse(proof['resources'][0]['originalLeaseAlive']);self.assertTrue(proof['resources'][0]['objectAlive']);self.assertTrue(proof['resources'][0]['hfmAlive'])
        f.marker.cleanup();self.assertEqual('released',f.marker.state['phase'])
        self.assertEqual([],f.domain.current()['source']['entities']);self.assertEqual(3,f.scope._version)
        self.assertEqual(1,len([row for row in owner.state['inputs'] if row['controlId']=='create.delete']))
        self.assertEqual(1,f.domain.io.actions.count('script-file.confirm'));self.assertEqual(1,f.domain.io.actions.count('scripts.stop.0'))
