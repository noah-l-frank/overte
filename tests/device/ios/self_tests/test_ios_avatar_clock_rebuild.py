"""New actual unbound readers reopen completed File/Pointer source histories."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.native_clock_source_history import restore
from adapters.normal_ui import NativeUIError
from ios.self_tests import test_ios_avatar_scene_receipts as fixture


class AvatarClockRebuildTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.AvatarSceneReceiptTests();self.f.setUp();self.addCleanup(self.f.doCleanups)

    def test_fresh_unbound_file_reader_reopens_original_prefix_without_changing_its_kind(self):
        first=self.f.file_owner();a=first.capture('bytes',self.f.ownership);self.f.owned.release()
        fresh=self.f.file_owner();self.assertIsNot(first.native,fresh.native);self.assertEqual(0,fresh.native.sequence)
        b=fresh.capture('absent',self.f.ownership);self.assertFalse(fresh.native.native_clock_bound)
        self.assertGreater(fresh.original(b)['packet']['sequence'],first.original(a)['packet']['sequence'])
        self.assertEqual(dict(exists=False,files=[]),fresh.original(b)['packet']['source'])

    def test_fresh_unbound_pointer_reader_reopens_actual_qt_and_native_prefixes(self):
        first=self.f.pointer_owner();a=first.capture();fresh=self.f.pointer_owner();self.assertEqual(0,fresh.native.sequence)
        b=fresh.capture();self.assertFalse(fresh.native.native_clock_bound)
        self.assertGreater(fresh.original(b)['packet']['sequence'],first.original(a)['packet']['sequence'])
        self.assertEqual(first.original(a)['packet']['source']['instance'],fresh.original(b)['packet']['source']['instance'])

    def test_cursor_restore_is_file_only_pristine_and_never_relabels_bound_readers_or_originals(self):
        old=self.f.clock();packet=old.read(old.sequence);raw=deepcopy(packet);requests=deepcopy(self.f.native.commands)
        fresh=self.f.clock();restore(fresh,packet);self.assertFalse(fresh.native_clock_bound)
        self.assertEqual(packet['sequence'],fresh.sequence);self.assertEqual(packet['capturedEpochMs'],fresh.captured_epoch)
        self.assertEqual(raw,packet);self.assertEqual(requests,self.f.native.commands)
        with self.assertRaises(NativeUIError):restore(fresh,packet)
        bound=self.f.clock();bound.native_clock_bound=True
        with self.assertRaises(NativeUIError):restore(bound,packet)
        foreign=deepcopy(packet);foreign['processId']=43
        with self.assertRaises(NativeUIError):restore(self.f.clock(),foreign)
        self.assertEqual(requests,self.f.native.commands)


if __name__=='__main__':unittest.main()
