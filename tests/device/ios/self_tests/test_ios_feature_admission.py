"""All iOS feature suites must reject incomplete adapters before target IO."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

DEVICE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(DEVICE))
from ios.adapters.adapter import IOSAdapter
from feature_journeys.scenarios import SCENARIOS


class IOSFeatureAdmissionTests(unittest.TestCase):
    def test_every_incomplete_area_fails_its_existing_mandatory_gate_without_device_io(self):
        # This is the actual iOS capability producer with the existing Script
        # and voice foundations enabled. Components cannot satisfy a full
        # feature triple, even if optional foundations are present.
        target = dict(platform='ios', physical=True, appId='org.example.overte',
            probe=dict(kind='ios-documents'), nativeUiObservation=dict(kind='uikit-documents', version=1),
            testBuild=dict(fixtureOrigin='http://fixture.invalid:49121', resultsDirectory='owned-results'),
            normalScripts=dict(contractVersion=1, profile='ios-native-qt-scripts-v1'))
        with patch.dict(os.environ, {'OVERTE_E2E_VOICE_TESTS': '1'}):
            capabilities = IOSAdapter.advertised_capabilities(target)
        self.assertIn('scripts.load-url', capabilities)
        env = {**os.environ, 'PYTHONPATH': str(DEVICE),
               'OVERTE_DEVICE_CAPABILITIES_JSON': json.dumps(capabilities),
               'OVERTE_DEVICE_ADAPTER_MANIFEST': str(DEVICE/'adapters/appium/ios-bound.json'),
               'OVERTE_DEVICE_TARGET_SELECTOR': 'private-test-target',
               'OVERTE_DEVICE_ARTIFACT_DIR': str(DEVICE)}
        for area in sorted(SCENARIOS):
            with self.subTest(area=area):
                done = subprocess.run([sys.executable, str(DEVICE/'modules/feature_capability_gate.py'),
                    '--area', area], env=env, capture_output=True, text=True, timeout=10)
                self.assertEqual(75, done.returncode, done.stdout + done.stderr)
                for verb in ('act', 'observe', 'cleanup'):
                    self.assertIn('feature.' + area + '.' + verb, done.stdout)
                self.assertNotIn('private-test-target', done.stdout + done.stderr)


if __name__ == '__main__': unittest.main()
