"""Local ordinary Create-token removal with actual retained weak cache state."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from copy import deepcopy
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from ios.adapters.assets_model_removal import OwnedAssetsModelRemoval
from ios.adapters.assets_session_owners import inspect_directory
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


class AssetsModelRemovalRecoveryTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup);self.path=Path(temporary.name);self.path.chmod(0o700)
        self.fixture=Fixture(self.path);self.addCleanup(self.fixture.close)
        self.enterContext(patch('adapters.asset_backend_client.build_opener',return_value=self.fixture))
        self.parsed=self.fixture.prepared_removal();self.store=PrivateFeatureState(self.fixture.path('model-removal'))
        self.owner=OwnedAssetsModelRemoval(self.parsed,self.store,lock=self.fixture.lock);self.owner.reserve()

    def restored(self):return OwnedAssetsModelRemoval(self.parsed,self.store,lock=self.fixture.lock)

    def pure(self):
        inputs=deepcopy(self.fixture.boundary.inputs);requests=deepcopy(self.fixture.requests);clocks=deepcopy(self.fixture.boundary.native_clock.commands)
        before={path.name:(path.read_bytes(),path.stat().st_ino) for path in self.path.iterdir() if path.is_file()}
        def forbidden(*_args,**_kwargs):raise AssertionError('Historical removal must not acquire fresh input or sources')
        with patch.object(self.owner.native,'capture',side_effect=forbidden),patch.object(self.owner.native,'deliver',side_effect=forbidden):
            rows=inspect_directory(self.path)
        self.assertEqual(inputs,self.fixture.boundary.inputs);self.assertEqual(requests,self.fixture.requests);self.assertEqual(clocks,self.fixture.boundary.native_clock.commands)
        self.assertEqual(before,{path.name:(path.read_bytes(),path.stat().st_ino) for path in self.path.iterdir() if path.is_file()})
        return rows[0]['responsibilities']

    def test_lost_delete_return_recovers_same_actual_removal_without_resending_and_keeps_resources_owned(self):
        fixture=self.fixture;fixture.boundary.input_lost='create.delete'
        with self.assertRaises(NativeUIError) as caught:self.owner.remove()
        self.assertIs(caught.exception,fixture.boundary.input_errors[0]);target=self.owner.target();self.assertNotIn(target,fixture.boundary.entities)
        event=deepcopy(self.owner.state['inputs'][-1]);self.assertEqual('create.delete',event['controlId']);self.assertIsNone(event['observed'])
        count=len(fixture.boundary.inputs);self.assertIn('model-removal',self.pure())
        restored=self.restored();restored.recover();proof=restored.remove()
        self.assertEqual(count,len(fixture.boundary.inputs));self.assertEqual(event['command']['commandId'],proof['inputCommandId'])
        self.assertFalse(proof['resources'][0]['originalLeaseAlive']);self.assertTrue(proof['resources'][0]['objectAlive']);self.assertTrue(proof['resources'][0]['hfmAlive'])
        responsibilities=self.pure();self.assertNotIn('model-removal',responsibilities);self.assertIn('model-removal-context',responsibilities)
        self.assertIn('model-removal-resources',responsibilities);self.assertIn('server-retirement',responsibilities)
        # A restart and repeated completed observation are purely historical.
        before=len(fixture.boundary.inputs);self.assertEqual(proof,self.restored().remove());self.assertEqual(before,len(fixture.boundary.inputs))

    def test_ignored_delete_keeps_actual_model_and_failed_originals_without_a_second_command(self):
        fixture=self.fixture;fixture.boundary.input_ignored='create.delete';fixture.boundary.input_lost='create.delete'
        with self.assertRaises(NativeUIError) as caught:self.owner.remove()
        self.assertIs(caught.exception,fixture.boundary.input_errors[0]);target=self.owner.target();self.assertIn(target,fixture.boundary.entities)
        event=deepcopy(self.owner.state['inputs'][-1]);count=len(fixture.boundary.inputs);restored=self.restored()
        with self.assertRaises(NativeUIError):restored.recover()
        saved=self.store.read();self.assertEqual(event['command'],restored.state['inputs'][-1]['command']);self.assertIsNone(restored.state['inputs'][-1]['observed'])
        self.assertIsNone(restored.state['result']);self.assertTrue(restored.state['observations']);self.assertEqual('deleting',restored.state['phase'])
        with self.assertRaises(NativeUIError):self.restored().remove()
        self.assertEqual(saved,self.store.read());self.assertEqual(count,len(fixture.boundary.inputs));self.assertIn(target,fixture.boundary.models)
        self.assertIn('model-removal',self.pure());self.assertIn('model-removal-resources',self.pure())
        with self.assertRaises(NativeUIError):restored.close_context()

    def test_replaced_parent_wal_blocks_before_any_child_input_and_orphan_removal_is_rejected(self):
        value=deepcopy(self.parsed.previous);value['unexpected']=True;self.parsed.store.write(value,self.parsed.previous)
        inputs=deepcopy(self.fixture.boundary.inputs)
        with self.assertRaises(NativeUIError):self.owner.remove()
        self.assertEqual(inputs,self.fixture.boundary.inputs)
        with self.assertRaises(NativeUIError):inspect_directory(self.path)
        self.parsed.store.write(self.parsed.previous,value);self.parsed.store.path.unlink()
        with self.assertRaises(NativeUIError):inspect_directory(self.path)


if __name__=='__main__':unittest.main()
