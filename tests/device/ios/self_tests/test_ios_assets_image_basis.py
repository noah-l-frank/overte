"""Actual retained marker/parser parents; no native pixel claim is made."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack,unpack
from ios.adapters.assets_image_basis import marker_original,parsed_original
from ios.adapters.assets_marker_owner import OwnedAssetsMarker
from ios.self_tests.test_ios_assets_marker_owner import MarkerParentFixture
from ios.self_tests.test_ios_assets_parsed_owner import AssetsParsedOwnerTests


class AssetsImageMarkerBasisTests(MarkerParentFixture):
    def test_actual_ready_marker_prefix_replays_after_cleanup_without_live_sources_or_writes(self):
        prepared=self.owner.prepare();snapshot=deepcopy(self.owner.previous);ready=marker_original(self.owner,snapshot)
        self.assertEqual(prepared.state['admission']['marker']['id'],ready['id'])
        self.owner.cleanup();scope=self.scope
        current=OwnedAssetsMarker.from_archive(self.store.read(),self.store,artifact_root=scope.root,binding=scope.binding,
            run=scope.run,role=scope.role,fixture_url=scope.fixture_url,ticket=scope.ticket,lock=scope.lock)
        before={path.name:(path.stat().st_ino,path.read_bytes()) for path in scope.root.iterdir() if path.is_file()}
        with (patch.object(self.domain.io,'observe',side_effect=AssertionError('historical SDK')),
                patch.object(PrivateFeatureState,'write',side_effect=AssertionError('historical write'))):
            self.assertEqual(ready,marker_original(current,snapshot))
            for key,value in (('artifactRoot','/foreign'),('role','actor'),('runId','f'*32)):
                bad=deepcopy(snapshot);bad[key]=value
                with self.subTest(key=key),self.assertRaises(NativeUIError):marker_original(current,bad)
            bad=deepcopy(snapshot);state=unpack(bad['payload'])[0];state['phase']='released';bad['payload']=pack([state])
            with self.assertRaises(NativeUIError):marker_original(current,bad)
        self.assertEqual(before,{path.name:(path.stat().st_ino,path.read_bytes()) for path in scope.root.iterdir() if path.is_file()})


class AssetsImageParsedBasisTests(unittest.TestCase):
    def setUp(self):
        self.fixture=AssetsParsedOwnerTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
    def test_actual_baked_parser_original_recomposes_without_sdk_http_input_or_mutation(self):
        f=self.fixture;proof=f.o.observe();snapshot=deepcopy(f.o.previous)
        before={path.name:(path.stat().st_ino,path.read_bytes()) for path in f.path.iterdir() if path.is_file()}
        with (patch.object(f.f,'open',side_effect=AssertionError('historical HTTP')),
                patch.object(f.f.boundary.native_clock,'send',side_effect=AssertionError('historical native')),
                patch.object(f.f.boundary,'exchange',side_effect=AssertionError('historical normal input')),
                patch.object(PrivateFeatureState,'write',side_effect=AssertionError('historical write'))):
            self.assertEqual(proof,parsed_original(f.o,snapshot))
            bad=deepcopy(snapshot);bad['role']='actor'
            with self.assertRaises(NativeUIError):parsed_original(f.o,bad)
            with self.assertRaises(NativeUIError):parsed_original(proof,snapshot)
        self.assertEqual(before,{path.name:(path.stat().st_ino,path.read_bytes()) for path in f.path.iterdir() if path.is_file()})
