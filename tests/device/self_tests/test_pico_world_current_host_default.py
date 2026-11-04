"""DefaultNone constructor remains a pure original World namespace."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import os,tempfile,unittest,uuid
from self_tests.pico_world_current_host_fixture import NamespaceOnlyAdapter
from adapters.pico4.world_web_binding import PicoWorldWebBinding
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.witness import Client

class WorldRootDefaultTests(unittest.TestCase):
    def test_default_none_preserves_original_cold_namespace_without_participant(self):
        path=Path(tempfile.mkdtemp(prefix='pico-world-default-none-'));path.chmod(0o700)
        print('Retained default World namespace:',path,flush=True)
        config={'OVERTE_PICO_NORMAL_SCRIPTS':'1','OVERTE_ANDROID_E2E_DEBUG':'1',
            'OVERTE_PICO_OPENXR_INPUT':'1','OVERTE_E2E_SCENE_URL':'https://world-resource.invalid/scene.json'}
        previous={key:os.environ.get(key) for key in config};os.environ.update(config)
        try:
            original=NamespaceOnlyAdapter(path);binding=PicoWorldWebBinding(original)
            phase=PhaseFixtureReader(Client('https://primary.invalid/feature-fixture/v1','n'*32),uuid.uuid4().hex,'world-web')
            parent=binding.prefix('namespace-target',phase,'https://foreign.invalid/feature-fixture/v1')
            self.assertIsNone(parent.resource_participant)
            self.assertFalse(hasattr(binding,'_resource_parent'))
            self.assertIsNone(parent.state);self.assertIsNone(parent.history);self.assertIsNone(parent.vm)
            self.assertEqual([],list(parent.root.iterdir()))
            self.assertEqual(0,original.sdk_calls);self.assertEqual(0,original.inputs)
        finally:
            for key,value in previous.items():
                if value is None:os.environ.pop(key,None)
                else:os.environ[key]=value
