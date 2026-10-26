"""Local ordinary Create-token removal with actual retained weak cache state."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from ios.adapters.assets_model_removal import OwnedAssetsModelRemoval
from ios.self_tests.assets_model_removal_fixture import Fixture


class AssetsModelRemovalTests(unittest.TestCase):
    def test_ordinary_create_delete_removes_actual_model_but_retains_live_cached_object_and_hfm(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary);path.chmod(0o700);fixture=Fixture(path)
            try:
                with patch('adapters.asset_backend_client.build_opener',return_value=fixture):
                    parsed=fixture.prepared_removal();owner=OwnedAssetsModelRemoval(parsed,PrivateFeatureState(fixture.path('model-removal')),lock=fixture.lock)
                    owner.reserve();proof=owner.remove()
                    self.assertNotIn(proof['entityId'],fixture.boundary.entities);self.assertNotIn(proof['entityId'],fixture.boundary.models)
                    self.assertEqual(1,len(proof['resources']));resource=proof['resources'][0]
                    self.assertFalse(resource['originalLeaseAlive']);self.assertTrue(resource['objectAlive']);self.assertTrue(resource['hfmAlive'])
                    self.assertFalse(proof['resourceRetirementAvailable']);self.assertEqual('model-gone',owner.state['phase'])
                    self.assertEqual(1,len([event for event in owner.state['inputs'] if event['controlId']=='create.delete']))
                    self.assertFalse(fixture.boundary.host_state['pageAlive']);self.assertEqual('primary-chosen',fixture.picker.state['phase'])
                    closed=owner.close_context();self.assertIsNotNone(closed);owner.close_parent_clients()
                    self.assertEqual('retired',parsed.model.usage.source.state['phase']);self.assertIsNotNone(parsed.model.usage.state['clientClosedBy'])
                    self.assertEqual('primary-chosen',fixture.picker.state['phase']);self.assertIsNotNone(fixture.boundary.origin_weaks[proof['entityId']]['object']())
                    self.assertIsNotNone(fixture.boundary.origin_weaks[proof['entityId']]['hfm']())
            finally:fixture.close()


if __name__=='__main__':unittest.main()
