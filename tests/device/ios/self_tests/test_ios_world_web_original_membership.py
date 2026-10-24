"""Actual-read scope identity never promotes a pin into a new census read."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import unittest
from adapters.original_file_reads import record,scope
from ios.adapters.world_web_original_membership import OriginalMembership


class WorldWebOriginalMembershipTests(unittest.TestCase):
    def test_new_nested_or_later_scope_cannot_inherit_a_successful_decode(self):
        outside=OriginalMembership();self.assertTrue(outside.matches())
        with scope(fresh=True) as reads:
            self.assertFalse(outside.matches());record(Path('/original-one'))
            marker=OriginalMembership();self.assertTrue(marker.matches())
            with scope(fresh=True) as fresh:
                self.assertFalse(marker.matches());self.assertEqual(set(),fresh)
            self.assertTrue(marker.matches());self.assertEqual({Path('/original-one')},reads)
        self.assertFalse(marker.matches());self.assertTrue(outside.matches())
        with scope(fresh=True) as fresh:
            record(Path('/original-one'));self.assertFalse(marker.matches())
            self.assertEqual({Path('/original-one')},fresh)

    def test_lost_membership_forces_decode_and_marker_never_repopulates_it(self):
        with scope(fresh=True) as reads:
            record(Path('/original-one'));marker=OriginalMembership()
            record(Path('/original-two'));self.assertTrue(marker.matches())
            reads.remove(Path('/original-one'));self.assertFalse(marker.matches())
            self.assertEqual({Path('/original-two')},reads)


if __name__=='__main__':unittest.main()
