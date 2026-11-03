"""Actual canonical candidate factory/router refusal; synthetic APK/ADB only."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
from pathlib import Path
import time
import sys
import unittest
from unittest.mock import patch

from adapters.pico4.browser_operation_owner import UNRESOLVED
from adapters.pico4.operation_host import process_identity
from adapters.pico4.tablet_web_binding import archive_retained
from feature_journeys.scenarios import VERSION
sys.path.insert(0,str(Path(__file__).resolve().parents[3]/'android/vr/pico/tests/device'))
import test_native_execution_binding as native


class BrowserOperationBindingTests(unittest.TestCase):
    def setUp(self):
        self.fixture = native.NativeExecutionBindingTest('runTest')
        self.fixture.setUp(); self.addCleanup(self.fixture.doCleanups)

    def begin(self):
        now = time.monotonic()
        return dict(picoBrowserOperationRequestVersion=1, requestId='a'*32, runId='b'*32,
            fixtureUrl='http://controlled.test/feature-fixture/v1/runs/'+'b'*32+'/', operation='begin',
            wholeBudget=dict(id='c'*32, startedMonotonic=now, deadlineMonotonic=now+120),
            actionBudget=dict(id='d'*32, startedMonotonic=now, deadlineMonotonic=now+60),
            arguments=dict(artifactRoot=str(self.fixture.fixture.root), nonce='e'*32,
                foreignFixtureUrl='http://foreign.test/feature-fixture/v1'))

    def test_public_router_cannot_create_a_cold_owner_or_query_sdk_without_original_context(self):
        bound = self.fixture.instance(); fake = self.fixture.fake; fake.events.clear()
        with self.assertRaises(ValueError): bound.invoke(fake.target, 'feature.tablet-web.observe',
            dict(contractVersion=VERSION, runId='b'*32, afterSequence=0))
        self.assertEqual([], fake.events)

    def test_factory_requires_explicit_flag_and_current_native_input_profile_before_sdk(self):
        bound = self.fixture.instance(); fake = self.fixture.fake; fake.events.clear()
        with patch.dict(os.environ, OVERTE_PICO_FEATURE_TABLET_WEB='0'):
            with self.assertRaises(ValueError): bound._browser_operation_owner(fake.target, self.begin(), process_identity(os.getppid()))
        self.assertEqual([], fake.events)

    def test_actual_wrong_original_runner_leaves_marker_before_any_feature_or_sdk_input(self):
        self.fixture.navigation_setup(); request = self.begin()
        with patch.dict(os.environ, OVERTE_PICO_FEATURE_TABLET_WEB='1',
                OVERTE_PICO_FEATURE_FIXTURE_CONFIG=str(self.fixture.fixture.root/'unused-private-config.json')):
            bound = self.fixture.instance(); fake = self.fixture.fake; fake.events.clear()
            with self.assertRaises(ValueError): bound._browser_operation_owner(fake.target, request, process_identity(os.getppid()))
        self.assertEqual([], fake.events); self.assertTrue(archive_retained(bound, fake.target))
        owners = [owner for owner in UNRESOLVED if owner.adapter is bound]
        self.assertEqual(1, len(owners)); owner = owners[0]
        self.assertTrue(owner.failed); self.assertEqual('admitting', owner.store.read()['phase'])
        self.assertEqual([], owner.store.read()['calls']); self.assertIsNone(owner.feature)
        self.assertTrue(owner.file.close_host()); UNRESOLVED.remove(owner)


if __name__ == '__main__':
    unittest.main()
