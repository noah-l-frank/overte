"""Exact member changes cannot disappear behind bounded terminal aliases."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.native_clock_join import digest
from adapters.normal_ui import NativeUIError
from feature_journeys.terminal import held,KINDS
from ios.adapters.tablet_web_held_groups import terminal_aliases


class TabletHeldGroupsTests(unittest.TestCase):
    def rows(self,count):
        return [dict(resource='panel:tablet-object-'+format(index,'04d'),kind=KINDS[index%len(KINDS)],
            originalSha256=digest(dict(actualMember=index,actualSource='a'*32))) for index in range(count)]
    def test_small_original_aliases_remain_literal_and_larger_sets_bind_every_original_member(self):
        for count in (0,1,64):
            values=self.rows(count);self.assertEqual(values,terminal_aliases(values))
        values=self.rows(700);before=deepcopy(values);groups=terminal_aliases(values)
        self.assertEqual(5,len(groups));self.assertEqual(5,len(held(groups)));self.assertEqual(before,values)
        for group in groups:
            members=[row for row in values if row['kind']==group['kind']]
            self.assertEqual(digest(dict(tabletHeldMembersVersion=1,kind=group['kind'],members=members)),group['originalSha256'])
    def test_add_remove_source_or_member_change_always_changes_quiet_proof(self):
        original=self.rows(100);before=terminal_aliases(original)
        variants=[self.rows(101),original[:-1],deepcopy(original),deepcopy(original)]
        variants[2][7]['originalSha256']=digest(dict(actualMember=7,actualSource='b'*32))
        variants[3][7]['resource']='panel:tablet-object-0007-new'
        for value in variants:
            with self.subTest(value=value[-1]):
                after=terminal_aliases(value);self.assertNotEqual(before,after)
                self.assertNotEqual(held(before),held(after))
    def test_duplicate_reordered_or_unknown_member_cannot_be_hidden_in_a_group(self):
        original=self.rows(100)
        variants=[original+[deepcopy(original[-1])],list(reversed(original)),deepcopy(original),deepcopy(original)]
        variants[2][7]['kind']='expected-dead';variants[3][7]['originalSha256']=True
        for value in variants:
            with self.subTest(value=value[7]),self.assertRaises((ValueError,NativeUIError)):terminal_aliases(value)


if __name__=='__main__':unittest.main()
