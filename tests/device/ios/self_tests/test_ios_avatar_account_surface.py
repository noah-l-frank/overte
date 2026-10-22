"""Actual postlogout passive UI originals remain distinct from retirement."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUIError
from ios.self_tests import test_ios_avatar_postlogout_tail as fixture


class AvatarAccountSurfaceTests(unittest.TestCase):
    setUp=fixture.AvatarPostLogoutTailTests.setUp
    factory=fixture.AvatarPostLogoutTailTests.factory
    owner=fixture.AvatarPostLogoutTailTests.owner
    archive=fixture.AvatarPostLogoutTailTests.archive

    def test_raw_account_tablet_original_is_not_a_closed_ui_proof(self):
        self.f.f.widget.shown=True
        owner=self.owner();row=owner.read();original=owner.record(row['reference']);raw=owner.file(row['index']).path.read_bytes()
        self.assertTrue(original['widgetsReceipt']['observation']['tabletShown'])
        with self.assertRaises(NativeUIError):owner.proof(row)
        archived=self.archive(owner);queries=deepcopy(self.channel_calls)
        with self.assertRaises(NativeUIError):archived.proof(row)
        with self.assertRaises(NativeUIError):archived.read()
        self.assertEqual(queries,self.channel_calls)
        self.f.f.widget.shown=False
        later=self.owner();closed=later.capture();later.proof(closed)
        self.assertNotEqual(row['reference'],closed['reference'])
        self.assertEqual(raw,owner.file(row['index']).path.read_bytes())
        with self.assertRaises(NativeUIError):later.proof(row)

    def test_actual_keyboard_and_inset_remain_unqualified_after_passive_read(self):
        self.keyboard=True;self.inset=250
        owner=self.owner();row=owner.read();actual=owner.geometry(owner.record(row['reference']))['nativeUi']
        self.assertTrue(actual['keyboardVisible']);self.assertEqual(250,actual['imeInsetBottom'])
        with self.assertRaises(NativeUIError):owner.proof(row)
        self.keyboard=False;self.inset=0
        later=self.owner();closed=later.capture();later.proof(closed)
        self.assertNotEqual(row['reference'],closed['reference'])


if __name__=='__main__':unittest.main()
