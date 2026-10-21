"""Private Pico Graphics configuration; no device, transport or service runs."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from adapters.pico4 import graphics_journey as binding
from adapters.normal_ui import NativeUIError
from adapters.graphics_journey.fixture import GraphicsFixtureReader
from self_tests.test_pico_graphics_feature import Model,RUN


class PicoGraphicsConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.addCleanup(self.temporary.cleanup)
        self.root=Path(self.temporary.name);self.root.chmod(0o700);self.config=self.root/'access.json'
        self.config.write_text(json.dumps(dict(fixtureAdapterAccessVersion=1,
            fixtureUrl='http://controlled.invalid/feature-fixture/v1',adapterToken='b'*64)));self.config.chmod(0o600)
        self.environment=dict(OVERTE_PICO_FEATURE_GRAPHICS='1',OVERTE_PICO_NORMAL_SCRIPTS='1',
            OVERTE_ANDROID_E2E_DEBUG='1',OVERTE_PICO_OPENXR_INPUT='1',OVERTE_E2E_SCENE_URL='http://controlled.invalid/scene.json',
            OVERTE_DEVICE_ARTIFACT_DIR=str(self.root),OVERTE_PICO_FEATURE_FIXTURE_CONFIG=str(self.config),
            OVERTE_E2E_FEATURE_FIXTURE_URL='http://controlled.invalid/feature-fixture/v1')
    def test_explicit_configuration_requires_normal_vr_private_artifacts_and_adapter_only_authority(self):
        self.assertTrue(binding.configured(self.environment))
        for change in (dict(OVERTE_PICO_NORMAL_SCRIPTS='0'),dict(OVERTE_PICO_OPENXR_INPUT='0'),
                dict(OVERTE_DEVICE_ARTIFACT_DIR='relative'),dict(OVERTE_PICO_FEATURE_FIXTURE_CONFIG=''),
                dict(OVERTE_E2E_FEATURE_READER_TOKEN='x'*64),dict(OVERTE_E2E_FEATURE_FIXTURE_URL='http://foreign.invalid/feature-fixture/v1')):
            with self.subTest(change=list(change)),self.assertRaises((RuntimeError,ValueError)):
                binding.configured(self.environment|change)
        self.assertFalse(binding.configured(self.environment|dict(OVERTE_PICO_FEATURE_GRAPHICS='0')))
    def test_unsafe_artifact_directory_is_rejected_without_creating_files_or_repairing_mode(self):
        before=set(self.root.iterdir());self.root.chmod(0o755)
        with self.assertRaises(NativeUIError):binding.configured(self.environment)
        self.assertEqual(0o755,self.root.stat().st_mode&0o777);self.assertEqual(before,set(self.root.iterdir()))
        self.root.chmod(0o700)
    def test_actor_fixture_factory_uses_explicit_pico_surface_and_never_inputs_or_activates_a_run(self):
        m=Model();self.addCleanup(m.close)
        journey=binding.PicoGraphicsJourney(m.original_adapter,artifact_root=m.root/'artifacts')
        def source(client,run):return GraphicsFixtureReader(client,run,epoch_ms=lambda:m.native.epoch)
        before=list(m.native.inputs);activations=len(m.provider.runs[RUN]['activations'])
        with patch.object(binding,'GraphicsFixtureReader',side_effect=source):
            flow=journey._graphics_feature('owned',RUN,role='actor',client=m.client)
        self.assertEqual('actor',flow.role);self.assertEqual('pico-stereo-graphics-v2',flow.image_policy['profile'])
        self.assertEqual(before,m.native.inputs);self.assertEqual(activations,len(m.provider.runs[RUN]['activations']))
    def test_legacy_provider_is_rejected_before_any_normal_input(self):
        m=Model();self.addCleanup(m.close);journey=binding.PicoGraphicsJourney(m.original_adapter,artifact_root=m.root/'artifacts')
        original=m.client.graphics_status
        def legacy():
            value=original();value.pop('profile');value['graphicsProviderVersion']=1;return value
        m.client.graphics_status=legacy;before=list(m.native.inputs)
        def source(client,run):return GraphicsFixtureReader(client,run,epoch_ms=lambda:m.native.epoch)
        with patch.object(binding,'GraphicsFixtureReader',side_effect=source),self.assertRaises((NativeUIError,ValueError)):
            journey._graphics_feature('owned',RUN,role='actor',client=m.client)
        self.assertEqual(before,m.native.inputs)
    def test_cleanup_namespace_inspection_does_not_create_an_unused_owner_directory(self):
        m=Model();self.addCleanup(m.close);journey=binding.PicoGraphicsJourney(m.original_adapter,artifact_root=m.root/'artifacts')
        before=set(m.root.iterdir());self.assertIsNone(journey.existing_state_path('never-owned'))
        self.assertEqual(before,set(m.root.iterdir()))
        path=journey.state_path('never-owned');self.assertEqual(path,journey.existing_state_path('never-owned'))


if __name__=='__main__':unittest.main()
