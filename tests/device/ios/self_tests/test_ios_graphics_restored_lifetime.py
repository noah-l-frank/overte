"""Original restored-world evidence must retain real cached resource holders."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch

from adapters.normal_ui import NativeUIError
from ios.adapters.graphics_lifetime import IOSGraphicsLifetime
from ios.self_tests.test_ios_graphics_lifetime import LifetimeHarness
from ios.self_tests.test_ios_graphics_scene import RUN


class RestoredLifetimeTests(LifetimeHarness, unittest.TestCase):
    def test_cached_original_software_image_is_retained_without_claiming_resource_absence(self):
        with self.lock.held():
            owner, original = self.prepare(); admitted = deepcopy(owner.load(owner.state['records'][0]))
            self.web.held = 'offscreen-image'; self.restore(); count = len(self.web.commands)
            owner = self.lifetime(); ref = owner.observe_restored(original); row = owner.load(ref)
            self.assertEqual(count+1, len(self.web.commands)); self.assertEqual('held', row['mode'])
            self.assertEqual(1, row['web']['contexts'][0]['resources']['offscreen-image']['pending'])
            self.assertEqual(42, row['web']['processId']); self.assertEqual('releasing', owner.state['phase'])
            self.assertFalse(owner.state['windows'][-1]['complete']); self.assertEqual([ref['ordinal']], owner.state['windows'][-1]['samples'])
            self.assertEqual(admitted, owner.load(owner.state['records'][0]))
            archive = IOSGraphicsLifetime.archive(owner.previous, path=owner.store.path, run=RUN,
                fixture_url=self.client.url, provider_instance=owner.source.instance, role='primary', stage=0, binding=owner.binding)
            self.assertEqual(owner.state, archive); self.assertFalse(archive['windows'][-1]['complete'])

    def test_no_pending_resources_in_one_snapshot_still_cannot_establish_a_quiet_window(self):
        with self.lock.held():
            _owner, original = self.prepare(); self.restore(); owner = self.lifetime()
            row = owner.load(owner.observe_restored(original)); self.assertEqual('released', row['mode'])
            self.assertEqual('releasing', owner.state['phase']); self.assertFalse(owner.state['windows'][-1]['complete'])
            self.assertEqual(0, owner.state['windows'][-1]['elapsedMs'])
            self.assertIsNotNone(owner.store.read())

    def test_each_role_observes_its_own_original_world_and_web_ledger_before_stop(self):
        with self.lock.held():
            primary, original = self.prepare(); self.lifetime('actor').observe_active()
            self.web.held = 'offscreen-image'; self.restore(); rows = []
            for role in ('primary', 'actor'):
                owner = self.lifetime(role); rows.append(owner.load(owner.observe_restored(original)))
            self.assertNotEqual(rows[0]['web']['commandId'], rows[1]['web']['commandId'])
            self.assertGreater(rows[1]['web']['sequence'], rows[0]['web']['sequence'])
            self.assertNotEqual(rows[0]['clockJoin']['nativeBefore']['requestId'], rows[1]['clockJoin']['nativeBefore']['requestId'])
            self.assertEqual(['held', 'held'], [r['mode'] for r in rows]); self.assertTrue(primary.state['activeProofs'])

    def test_fixture_retirement_without_actual_world_restoration_is_rejected(self):
        with self.lock.held():
            _owner, original = self.prepare(); self.client.close(); owner = self.lifetime()
            with self.assertRaises(NativeUIError):owner.observe_restored(original)
            self.assertIsNotNone(owner.state['pending']); self.assertFalse(owner.state['windows'][-1]['complete'])
            self.assertEqual(1, len(owner.state['records']))

    def test_lost_committed_snapshot_return_preserves_original_and_recovers_without_input_replay(self):
        with self.lock.held():
            _owner, original = self.prepare(); self.web.held = 'offscreen-image'; self.restore(); owner = self.lifetime()
            actual = owner.store_record; actions = list(self.sdk.model.actions)
            def lost(row):
                actual(row); raise OSError('Synthetic lost restored-world record return')
            with patch.object(owner, 'store_record', side_effect=lost), self.assertRaises(OSError):owner.observe_restored(original)
            self.assertIsNotNone(owner.state['pending']); commands = len(self.web.commands)
            recovered = self.lifetime(); ref = recovered.observe_restored(original)
            self.assertEqual(commands+1, len(self.web.commands)); self.assertEqual(actions, self.sdk.model.actions)
            self.assertEqual(['active', 'held', 'held'], [recovered.load(r)['mode'] for r in recovered.state['records']])
            self.assertEqual(3, ref['ordinal']); self.assertFalse(recovered.state['windows'][-1]['complete'])

    def test_missing_active_or_abort_audit_cannot_manufacture_a_restoration_receipt(self):
        with self.lock.held():
            owner = self.lifetime(); self.scene().prepare(); original = deepcopy(self.scene().state['original']['subject'])
            self.restore(); commands = len(self.web.commands)
            with self.assertRaises(NativeUIError):owner.observe_restored(original)
            self.assertEqual(commands, len(self.web.commands)); self.assertFalse(owner.state['records'])


if __name__ == '__main__':unittest.main()
