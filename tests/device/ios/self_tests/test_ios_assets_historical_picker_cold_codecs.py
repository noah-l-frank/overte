"""Genuine cold stdlib compilation, exact originals, and later policy refusal."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import re
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.self_tests.test_ios_assets_historical_picker_snapshots import AssetsHistoricalPickerSnapshotTests

class AssetsHistoricalPickerColdCodecsTests(AssetsHistoricalPickerSnapshotTests):
    def test_actual_cold_regex_compilation_precedes_policy_birth_and_snapshot_scope_closes_with_equal_originals(self):
        before=self.files();re.purge()
        self.assertEqual({},re._cache);self.assertEqual({},re._cache2)
        with patch.object(self.f.boundary,'exchange',side_effect=self.forbidden):
            with self.archived() as (owner,picker,memo):
                self.assertTrue(memo.enabled);self.assertTrue(memo.cache)
                self.assertTrue(memo.parser_policy.unchanged())
                for ref in owner.state['records']:owner.read(ref)
                self.assertTrue(memo.enabled);self.assertTrue(memo.parser_policy.unchanged())
        self.assertFalse(memo.active);self.assertEqual({},memo.cache);self.assertIsNone(owner.snapshot_scope)
        self.assertEqual(before,self.files())

    def test_changed_actual_regex_memo_after_policy_birth_never_reuses_old_snapshot_or_closes_successfully(self):
        before=self.files();saved=None
        try:
            with patch.object(self.f.boundary,'exchange',side_effect=self.forbidden),self.assertRaises(NativeUIError):
                with self.archived() as (owner,picker,memo):
                    self.assertTrue(memo.cache);self.assertTrue(memo.parser_policy.unchanged())
                    saved=(dict(re._cache),dict(re._cache2))
                    foreign=re.compile('owned-counter-foreign-regex')
                    self.assertTrue(re._cache)
                    key=next(iter(re._cache));re._cache[key]=foreign
                    self.assertFalse(memo.parser_policy.unchanged())
                    for ref in owner.state['records']:owner.read(ref)
        finally:
            if saved is not None:
                re._cache.clear();re._cache.update(saved[0]);re._cache2.clear();re._cache2.update(saved[1])
        self.assertIsNotNone(saved);self.assertFalse(memo.active);self.assertEqual({},memo.cache)
        self.assertEqual(before,self.files())
