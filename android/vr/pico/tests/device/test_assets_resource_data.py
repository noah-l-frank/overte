"""Original generic Resource data ownership; no geometry/render-ready inference."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import os
from pathlib import Path
import tempfile
import unittest
import test_assets_resource_manager as manager_module
import test_assets_request_lifetimes as life_module
import test_assets_cancel_effects as effects
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_journey.history import canonical


class AssetsResourceDataTests(unittest.TestCase):
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
    expected_child_same_thread=True
    @classmethod
    def setUpClass(cls):
        cls.build=tempfile.TemporaryDirectory(prefix='pico-assets-resource-data-build-')
        cls.binary,cls.environment,cls.args=effects.compile_ui(cls.build.name,persistent_tablet=True,original_server=True,original_model=True,original_entity=True,original_resources=True,request_lifetimes=True,original_resource_manager=True,original_resource_data=True)
        independent=Path(cls.build.name)/'independent';independent.mkdir()
        cls.reader_binary,cls.reader_environment=effects.compile_source(independent)
    @classmethod
    def tearDownClass(cls):cls.build.cleanup()
    def preserve(self):
        manager_module.AssetsResourceManagerTests.preserve(self)
        destination=os.environ.get('OVERTE_ASSETS_EFFECTS_EVIDENCE')
        if destination:
            PrivateFeatureState(Path(destination).resolve(strict=True)/(self._testMethodName+'-resource-data.json')).write(dict(
                assetsResourceDataHostEvidenceVersion=1,originalCppBodies=json.loads((Path(self.build.name)/'resource-data-original-provenance.json').read_text())),None)
    def exercise_cancel_home(self,baseline):
        counts,raw=life_module.AssetsRequestLifetimesTests.exercise_cancel_home(self,baseline)
        for resource in self.resource_original['resources']:
            counts+=len(resource['dataOriginals']);raw+=len(canonical(resource['dataOriginals']))
        counts+=len(self.resource_original['resourceObserverOriginals']);raw+=len(canonical(self.resource_original['resourceObserverOriginals']))
        # The complete containing raw byte packet already includes these bytes;
        # repeated dependent views are counted conservatively as copies too.
        return counts,raw
    def test_original_resource_signals_byte_ownership_self_guard_and_normal_retirement(self):
        life_module.AssetsRequestLifetimesTests.test_actual_original_request_births_child_deaths_and_unmodified_cancel_home_quiet(self)
        ids=set()
        for resource in self.resource_original['resources']:
            self.assertEqual('AssetResourceRequest',resource['actualClass']);self.assertTrue(resource['ownerMatchesClient'] and resource['ownerQueueRetired'])
            constructed,loaded,finished,retired=resource['dataOriginals']
            self.assertEqual(['constructed','loaded-signal','finished-external-reference-released','retired'],[row['phase'] for row in resource['dataOriginals']])
            self.assertEqual(1,len({row['id'] for row in resource['dataOriginals']}));self.assertNotIn(constructed['id'],ids);ids.add(constructed['id'])
            self.assertTrue(constructed['alive'] and constructed['ownerThread']);self.assertEqual('Resource',constructed['actualQtClass'])
            self.assertFalse(constructed['genericLoaded'] or constructed['genericFailed'] or constructed['started'] or constructed['requestAlive']);self.assertEqual(0,constructed['bytes'])
            self.assertTrue(loaded['alive'] and loaded['ownerThread'] and loaded['requestAlive'] and loaded['started']);self.assertFalse(loaded['genericLoaded'])
            self.assertTrue(finished['alive'] and finished['ownerThread'] and finished['requestAlive'] and finished['genericLoaded']);self.assertEqual(resource['bytes'],finished['bytes'])
            self.assertFalse(retired['alive'] or retired['requestAlive']);self.assertIsNone(retired['genericLoaded']);self.assertIsNone(retired['bytes'])
            self.assertTrue(all(b['observedEpochMs']>=a['observedEpochMs'] for a,b in zip(resource['dataOriginals'],resource['dataOriginals'][1:])))
        signals=self.resource_original['resourceObserverOriginals'];self.assertEqual(3,len(signals))
        self.assertEqual({row['url'] for row in self.resource_original['resources']},{row['url'] for row in signals})
        self.assertTrue(all(row['callerId']==-1 and row['extra']=='Resource::makeRequest => ResourceRequest::send' for row in signals))


if __name__=='__main__':unittest.main()
