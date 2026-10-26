"""Closed original bundle-control grammar, with malformed producer packets."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters.assets_bundle_controls import manifest,destination,inventory
from ios.adapters.normal_input import observation
from ios.self_tests.assets_upload_fixture import Fixture


class AssetsBundleControlsTests(unittest.TestCase):
    def test_only_a_real_relative_manifest_index_and_local_urls_are_admitted(self):
        original=dict(root='file:///owned/root',urls=['file:///owned/root/main.gltf','file:///owned/root/mesh/a.bin'],
            relativePaths=['main.gltf','mesh/a.bin'],primaryIndex=0,primaryPath='main.gltf');self.assertIs(original,manifest(original))
        for change in (dict(primaryIndex=True),dict(primaryPath='mesh/a.bin'),dict(relativePaths=['main.gltf','../a.bin']),
                dict(urls=['file:///foreign/main.gltf','file:///owned/root/mesh/a.bin']),dict(relativePaths=[{},'mesh/a.bin'])):
            with self.subTest(change=change),self.assertRaises(NativeUIError):manifest(dict(original,**change))

    def test_destination_rejects_shared_paths_whitespace_and_foreign_suffixes(self):
        self.assertEqual('/e2e-'+'a'*32+'/',destination('/e2e-'+'a'*32+'/'))
        for value in ('/',' /e2e-'+'a'*32+'/','/e2e-'+'a'*32+'/../','/e2e-'+'a'*32+'/more','/ordinary/'):
            with self.subTest(value=value),self.assertRaises(NativeUIError):destination(value)

    def test_bundle_extension_cannot_stand_in_for_the_original_weak_ui_inventory(self):
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary);path.chmod(0o700);fixture=Fixture(path)
            try:
                original=fixture.boundary.normal();self.assertIs(original,observation(original,42,fixture.boundary.clock()))
                wrong=deepcopy(original);wrong.pop('assetControlsVersion');wrong.pop('assetInventory')
                with self.assertRaises(NativeUIError):observation(wrong,42,fixture.boundary.clock())
                wrong=deepcopy(original);wrong['assetBundleInventory']['iosAssetsBundleUiVersion']=True
                with self.assertRaises(NativeUIError):observation(wrong,42,fixture.boundary.clock())
            finally:fixture.close()
