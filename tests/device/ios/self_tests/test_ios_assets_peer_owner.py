"""Actual normal primary import and separate declared domain/loader objects."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from adapters.normal_feature_state import PrivateFeatureState
from ios.adapters.assets_peer_owner import OwnedAssetsPeer
from ios.adapters.assets_runtime import IOSAssetsRuntime
from ios.adapters.assets_session_owners import inspect_directory
from ios.adapters import assets_scene_ownership
from ios.self_tests.assets_peer_fixture import Fixture,SceneEndpoint


class AssetsPeerOwnerTests(unittest.TestCase):
    def test_original_normal_primary_uuid_reaches_independent_peer_parser_without_input_or_pixel_verdict(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);root.chmod(0o700);fixture=Fixture(root)
            try:
                with patch('adapters.asset_backend_client.build_opener',return_value=fixture):
                    parsed=fixture.prepared_peer();primary=SceneEndpoint(fixture,parsed,root,'actor-primary');peer=SceneEndpoint(fixture,parsed,root/'peer','actor')
                    try:
                        a,b=primary.owner(),peer.owner();store=PrivateFeatureState(peer.root/('ios-assets-peer-'+parsed.sources.run+'.json'))
                        runtime=object.__new__(IOSAssetsRuntime);runtime.monotonic=fixture.boundary.monotonic
                        runtime.state_path=lambda selector:(root if selector=='primary' else peer.root)/'script-runtime-state.json'
                        parts=runtime._assets_peer_components('actor','primary',parsed.sources.run,parsed.model.usage.source.files.url,peer.lock,primary.lock,fixture.backend.config,
                            primary_parts=dict(parsed=parsed,check=parsed.guard),primary_scene_parts=dict(scene=a,check=a.guard),peer_scene_parts=dict(scene=b,check=b.guard))
                        owner=parts['peer'];self.assertIs(parsed,owner.parsed);self.assertIs(a,owner.primary);self.assertIs(b,owner.peer);self.assertEqual([],primary.queries);self.assertEqual([],peer.queries)
                        inputs=deepcopy(fixture.boundary.inputs)
                        owner.reserve();result=owner.observe();self.assertEqual(parsed.state['result']['entityId'],result['entityId'])
                        self.assertEqual(inputs,fixture.boundary.inputs);self.assertEqual(1,len(fixture.boundary.peer.deliveries));self.assertEqual(6,len(primary.queries));self.assertEqual(6,len(peer.queries))
                        self.assertNotEqual(result['primaryReaderId'],result['peerReaderId']);self.assertEqual(parsed.state['result']['sha256'],result['sha256'])
                        self.assertFalse(result['renderedPixelsAvailable']);self.assertFalse(result['resourceRetirementAvailable'])
                        queries=deepcopy((primary.queries,peer.queries));restored=OwnedAssetsPeer(parsed,primary.owner(),peer.owner(),store,peer.lock)
                        self.assertEqual(result,restored.observe());self.assertEqual(queries,(primary.queries,peer.queries));self.assertEqual(inputs,fixture.boundary.inputs)
                        before={str(path.relative_to(root)):(path.stat().st_ino,path.read_bytes()) for path in root.rglob('*') if path.is_file()}
                        with (patch.object(primary,'send',side_effect=AssertionError('pure primary query')),
                              patch.object(peer,'send',side_effect=AssertionError('pure actor query'))):
                            with self.assertRaises(NativeUIError):inspect_directory(peer.root)
                            rows=inspect_directory(peer.root,primary_directory=root)
                            self.assertEqual(['peer-resource-retirement'],rows[-1]['responsibilities'])
                            envelope=store.read();envelope['primaryDirectoryIdentity']['inode']+=1
                            with self.assertRaises(NativeUIError):restored.decode(envelope)
                        self.assertEqual(before,{str(path.relative_to(root)):(path.stat().st_ino,path.read_bytes()) for path in root.rglob('*') if path.is_file()})
                        self.assertEqual(queries,(primary.queries,peer.queries));self.assertEqual(inputs,fixture.boundary.inputs)
                        legacy=deepcopy(store.read());legacy['iosAssetsPeerOwnerVersion']=1
                        store.write(legacy,store.read());historical=OwnedAssetsPeer(parsed,primary.owner(),peer.owner(),store,peer.lock)
                        self.assertEqual(result,historical.observe());self.assertEqual(1,store.read()['iosAssetsPeerOwnerVersion'])
                        self.assertEqual(queries,(primary.queries,peer.queries));self.assertEqual(inputs,fixture.boundary.inputs)
                    finally:peer.close();primary.close()
            finally:fixture.close()

    def test_saved_primary_cohort_recovers_without_resending_and_real_creation_identity_blocks_uuid_reuse(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);root.chmod(0o700);fixture=Fixture(root)
            try:
                with patch('adapters.asset_backend_client.build_opener',return_value=fixture):
                    parsed=fixture.prepared_peer();primary=SceneEndpoint(fixture,parsed,root,'actor-primary');peer=SceneEndpoint(fixture,parsed,root/'peer','actor')
                    try:
                        store=PrivateFeatureState(peer.root/('ios-assets-peer-'+parsed.sources.run+'.json'));owner=OwnedAssetsPeer(parsed,primary.owner(),peer.owner(),store,peer.lock);owner.reserve()
                        write=store.write;failure=RuntimeError('lost saved primary cohort adoption');fired=[]
                        def lost(value,previous):
                            result=write(value,previous)
                            from adapters.script_feature.history import unpack
                            pending=unpack(value['payload'])[0]['pending']
                            if pending is not None and pending['primary'] is not None and pending['peer'] is None and not fired:fired.append(True);raise failure
                            return result
                        with patch.object(store,'write',side_effect=lost),self.assertRaises(RuntimeError) as caught:owner.observe()
                        self.assertIs(failure,caught.exception);self.assertEqual(6,len(primary.queries));self.assertEqual([],peer.queries)
                        restored=OwnedAssetsPeer(parsed,primary.owner(),peer.owner(),store,peer.lock)
                        entity=fixture.boundary.peer.entities[parsed.state['result']['entityId']];created=entity.properties['createdEpochUs']
                        entity.properties['createdEpochUs']=str(int(created)+1)
                        with self.assertRaises(NativeUIError):restored.observe()
                        self.assertEqual(6,len(primary.queries));self.assertEqual(6,len(peer.queries));self.assertIsNone(restored.state['result'])
                        inputs=deepcopy(fixture.boundary.inputs);restored.freeze_failed_attempt()
                        historical=OwnedAssetsPeer(parsed,primary.owner(),peer.owner(),store,peer.lock)
                        self.assertEqual(1,len(historical.state['attempts']));self.assertIsNone(historical.state['pending']);self.assertIsNone(historical.state['result'])
                        self.assertEqual(6,len(primary.queries));self.assertEqual(6,len(peer.queries));self.assertEqual(inputs,fixture.boundary.inputs)
                        self.assertEqual(['peer-resource-retirement','peer-observation'],inspect_directory(peer.root,primary_directory=root)[-1]['responsibilities'])
                    finally:peer.close();primary.close()
            finally:fixture.close()

    def test_completed_child_original_before_parent_adoption_is_recovered_without_a_second_primary_query(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);root.chmod(0o700);fixture=Fixture(root)
            try:
                with patch('adapters.asset_backend_client.build_opener',return_value=fixture):
                    parsed=fixture.prepared_peer();primary=SceneEndpoint(fixture,parsed,root,'actor-primary');peer=SceneEndpoint(fixture,parsed,root/'peer','actor')
                    try:
                        a,b=primary.owner(),peer.owner();store=PrivateFeatureState(peer.root/('ios-assets-peer-'+parsed.sources.run+'.json'))
                        owner=OwnedAssetsPeer(parsed,a,b,store,peer.lock);owner.reserve();capture=a.capture;failure=RuntimeError('lost child return before parent adoption')
                        def lost(barrier):capture(barrier);raise failure
                        with patch.object(a,'capture',side_effect=lost),self.assertRaises(RuntimeError) as caught:owner.observe()
                        self.assertIs(failure,caught.exception);self.assertIsNone(owner.state['pending']['primary']);self.assertEqual(1,len(a.state['frames']))
                        self.assertEqual(6,len(primary.queries));self.assertEqual([],peer.queries);inputs=deepcopy(fixture.boundary.inputs)
                        restored=OwnedAssetsPeer(parsed,primary.owner(),peer.owner(),store,peer.lock);result=restored.observe()
                        self.assertEqual(parsed.state['result']['entityId'],result['entityId']);self.assertEqual(6,len(primary.queries));self.assertEqual(6,len(peer.queries))
                        self.assertEqual(inputs,fixture.boundary.inputs);self.assertEqual(a.state['frames'][0],restored.state['pending']['primary'])
                    finally:peer.close();primary.close()
            finally:fixture.close()

    def test_owner_two_joins_coincident_native_pids_only_with_distinct_actual_targets_and_instances(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);root.chmod(0o700);fixture=Fixture(root)
            try:
                with patch('adapters.asset_backend_client.build_opener',return_value=fixture):
                    parsed=fixture.prepared_peer();primary=SceneEndpoint(fixture,parsed,root,'actor-primary');peer=SceneEndpoint(fixture,parsed,root/'peer','actor',pid=42)
                    try:
                        store=PrivateFeatureState(peer.root/('ios-assets-peer-'+parsed.sources.run+'.json'));owner=OwnedAssetsPeer(parsed,primary.owner(),peer.owner(),store,peer.lock)
                        owner.reserve();result=owner.observe();self.assertEqual(2,store.read()['iosAssetsPeerOwnerVersion'])
                        self.assertEqual('42',result['primaryBinding']['processIdentity']);self.assertEqual('42',result['peerBinding']['processIdentity'])
                        self.assertNotEqual(result['primaryBinding']['targetFingerprint'],result['peerBinding']['targetFingerprint'])
                        self.assertEqual(6,len(primary.queries));self.assertEqual(6,len(peer.queries));before=deepcopy((primary.queries,peer.queries))
                        self.assertEqual(['peer-resource-retirement'],inspect_directory(peer.root,primary_directory=root)[-1]['responsibilities'])
                        restored=OwnedAssetsPeer(parsed,primary.owner(),peer.owner(),store,peer.lock);self.assertEqual(result,restored.observe())
                        legacy=deepcopy(store.read());legacy['iosAssetsPeerOwnerVersion']=1
                        with self.assertRaises(NativeUIError):restored.decode(legacy)
                        self.assertEqual(before,(primary.queries,peer.queries));self.assertFalse(result['renderedPixelsAvailable']);self.assertFalse(result['resourceRetirementAvailable'])
                    finally:peer.close();primary.close()
            finally:fixture.close()
