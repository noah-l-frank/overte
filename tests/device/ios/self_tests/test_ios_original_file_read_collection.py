"""Actual read trace spans nested fresh scopes without changing membership."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import unittest
from adapters.original_file_reads import active,collect,record,scope


class OriginalFileReadCollectionTests(unittest.TestCase):
    def test_nested_fresh_membership_is_isolated_while_trace_collects_all_actual_reads(self):
        with collect() as all_reads,scope(fresh=True) as outer:
            record('/outer')
            with scope(fresh=True) as inner:record('/inner')
            record('/after');self.assertTrue(active())
        self.assertEqual({Path('/outer'),Path('/after')},outer)
        self.assertEqual({Path('/inner')},inner)
        self.assertEqual({Path('/outer'),Path('/inner'),Path('/after')},all_reads)
        self.assertFalse(active())
    def test_exception_restores_both_contexts_without_leaking_into_next_collection(self):
        with self.assertRaisesRegex(RuntimeError,'declared boundary'):
            with collect() as first,scope(fresh=True):
                record('/failed');raise RuntimeError('declared boundary')
        self.assertFalse(active());record('/outside')
        with collect() as second:record('/next')
        self.assertEqual({Path('/failed')},first);self.assertEqual({Path('/next')},second)
    def test_nested_collectors_have_independent_sets_and_outer_keeps_full_actual_trace(self):
        with collect() as outer:
            record('/before')
            with collect() as inner:record('/inside')
            record('/after')
        self.assertEqual({Path('/inside')},inner)
        self.assertEqual({Path('/before'),Path('/inside'),Path('/after')},outer)
    def test_collection_without_membership_does_not_create_or_reuse_an_active_scope(self):
        self.assertFalse(active());record('/unobserved')
        with collect() as first:record('/one');self.assertFalse(active())
        with collect() as second:self.assertFalse(active())
        self.assertEqual({Path('/one')},first);self.assertEqual(set(),second)


if __name__=='__main__':unittest.main()
