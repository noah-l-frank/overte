"""Original storage replay keeps live guards at entry/exit and all writes.

Local byte checks cannot create native query authority. Process loss during a
real original-file traversal refuses its result; saved bytes remain unchanged.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import tempfile
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters.tablet_web_packets import TabletWebPackets
from ios.self_tests import test_ios_tablet_web_packets as fixture


class TabletStorageGuardTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.TabletWebPacketsTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
    def owner(self,guard,storage):
        return TabletWebPackets(self.f.root,fixture.BINDING,fixture.RUN,'primary',fixture.ROOT,31,'sources',guard,
            storage_guard=storage,monotonic=lambda:0.,epoch_ms=lambda:120000)
    def test_many_actual_file_reads_have_two_full_live_history_guards_and_loss_during_read_refuses_result(self):
        source=self.f.owner();source.capture(self.f.reader());source.capture(self.f.reader())
        active=[True];calls=[];reads=[];lose=[False]
        def guard():calls.append(active[0]);return active[0]
        def storage():
            reads.append(True)
            if lose[0]:active[0]=False
            return True
        owner=self.owner(guard,storage);calls.clear();reads.clear()
        values=owner.history();self.assertEqual(2,len(values));self.assertEqual([True,True],calls);self.assertGreater(len(reads),2)
        original={p.name:p.read_bytes() for p in self.f.root.iterdir() if p.is_file()};queries=len(self.f.sends)
        calls.clear();lose[0]=True
        with self.assertRaises(NativeUIError):owner.history()
        self.assertEqual([True,False],calls);self.assertEqual(queries,len(self.f.sends))
        self.assertEqual(original,{p.name:p.read_bytes() for p in self.f.root.iterdir() if p.is_file()})
        with self.assertRaises(NativeUIError):owner.save()
        with self.assertRaises(NativeUIError):owner.capture(self.f.reader())
        self.assertEqual(queries,len(self.f.sends));self.assertEqual(original,{p.name:p.read_bytes() for p in self.f.root.iterdir() if p.is_file()})
    def test_false_live_guard_cannot_create_first_journal_even_when_private_storage_guard_passes(self):
        self.assertEqual([],list(self.f.root.iterdir()))
        with self.assertRaises(NativeUIError):self.owner(lambda:False,lambda:True)
        self.assertEqual([],list(self.f.root.iterdir()));self.assertEqual([],self.f.sends)
    def test_storage_guard_refusal_does_not_become_live_product_authority(self):
        source=self.f.owner();source.capture(self.f.reader());queries=len(self.f.sends)
        before={p.name:p.read_bytes() for p in self.f.root.iterdir() if p.is_file()}
        with self.assertRaises(NativeUIError):self.owner(lambda:True,lambda:False)
        self.assertEqual(queries,len(self.f.sends));self.assertEqual(before,{p.name:p.read_bytes() for p in self.f.root.iterdir() if p.is_file()})


if __name__=='__main__':unittest.main()
