"""Original ATP URL factory and true same-owner-thread request lifetimes.

Manager startup/cache/File/HTTP/assignment remain explicit host endpoints. The
reader borrows the actual AssetClient worker; no renderer/whole manager claim.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import os
from pathlib import Path
import tempfile
import unittest
import test_assets_request_lifetimes as life_module
import test_assets_cancel_effects as effects
from adapters.normal_feature_state import PrivateFeatureState


class AssetsResourceManagerTests(unittest.TestCase):
    setUp=life_module.AssetsRequestLifetimesTests.setUp
    make=life_module.AssetsRequestLifetimesTests.make
    cancel_phase=life_module.AssetsRequestLifetimesTests.cancel_phase
    pointers=life_module.AssetsRequestLifetimesTests.pointers
    inputs=life_module.AssetsRequestLifetimesTests.inputs
    model_snapshot=life_module.AssetsRequestLifetimesTests.model_snapshot
    exercise=life_module.AssetsRequestLifetimesTests.exercise
    save_lifetimes=life_module.AssetsRequestLifetimesTests.save_lifetimes
    check=life_module.AssetsRequestLifetimesTests.check
    snapshot=life_module.AssetsRequestLifetimesTests.snapshot
    mappings=life_module.AssetsRequestLifetimesTests.mappings
    entity_snapshot=life_module.AssetsRequestLifetimesTests.entity_snapshot
    home_owner=life_module.AssetsRequestLifetimesTests.home_owner
    exercise_cancel_home=life_module.AssetsRequestLifetimesTests.exercise_cancel_home
    expected_child_same_thread=True
    @classmethod
    def setUpClass(cls):
        cls.build=tempfile.TemporaryDirectory(prefix='pico-assets-manager-build-')
        cls.binary,cls.environment,cls.args=effects.compile_ui(cls.build.name,persistent_tablet=True,original_server=True,original_model=True,original_entity=True,original_resources=True,request_lifetimes=True,original_resource_manager=True)
        independent=Path(cls.build.name)/'independent';independent.mkdir()
        cls.reader_binary,cls.reader_environment=effects.compile_source(independent)
    @classmethod
    def tearDownClass(cls):cls.build.cleanup()
    def preserve(self):
        life_module.AssetsRequestLifetimesTests.preserve(self)
        destination=os.environ.get('OVERTE_ASSETS_EFFECTS_EVIDENCE')
        if destination:
            PrivateFeatureState(Path(destination).resolve(strict=True)/(self._testMethodName+'-manager.json')).write(dict(
                assetsResourceManagerHostEvidenceVersion=1,originalCppBodies=json.loads((Path(self.build.name)/'resource-manager-original-provenance.json').read_text())),None)
    def test_original_manager_factory_same_ownerthread_bytes_and_normal_request_retirement(self):
        life_module.AssetsRequestLifetimesTests.test_actual_original_request_births_child_deaths_and_unmodified_cancel_home_quiet(self)
        for resource in self.resource_original['resources']:
            self.assertEqual('AssetResourceRequest',resource['actualClass']);self.assertTrue(resource['ownerMatchesClient'] and resource['ownerQueueRetired'])


if __name__=='__main__':unittest.main()
