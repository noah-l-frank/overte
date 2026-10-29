"""Actual owned appends must change the key, never mutable original pins.

Real retained Source/child files and JS; modeled native/UIKit transport only.
The same operation cache covers both captures and independent file replay.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from adapters.normal_ui import NativeUIError
from ios.adapters.tablet_web_record_cache import TabletRecordCache,scope
from ios.self_tests import test_ios_tablet_web_aggregate_root as fixture


class TabletAggregateRecordCacheEpochTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixture.TabletOwnedAggregateRootTests.setUpClass()

    def setUp(self):
        self.f=fixture.TabletOwnedAggregateRootTests();self.addCleanup(self.f.doCleanups)
        self.f.setUp();self.owner=self.f.open();self.cache=TabletRecordCache()

    def test_same_cache_two_actual_captures_accept_current_epochs_and_refuse_stale_historical_owner(self):
        with scope(self.cache):
            first_parts,first_row=self.f.capture(self.owner)
            first_ref=deepcopy(self.owner.state['records'][0]);old=self.f.historical()
            first=old.frame_at(first_ref);calls=list(self.f.boundary.calls)
            self.assertEqual(first_row,first[0]);self.assertEqual(first_parts,first[1])
            self.assertTrue(self.cache.originals.rows)
            self.assertEqual(first,old.frame_at(first_ref));self.assertEqual(calls,self.f.boundary.calls)
            second_parts,second_row=self.f.capture(self.owner)
            self.assertEqual(3,second_row['index']);self.assertEqual(calls+list(fixture.ORDER),self.f.boundary.calls)
            calls=list(self.f.boundary.calls)
            with self.assertRaises(NativeUIError):old.history()
            current=self.f.historical();actual=current.frame_at(self.owner.state['records'][-1])
            self.assertEqual(second_row,actual[0]);self.assertEqual(second_parts,actual[1])
            self.assertEqual(first_row,current.frame_at(first_ref)[0]);self.assertEqual(calls,self.f.boundary.calls)
            self.assertEqual(self.f.canonical,self.f.pins(self.f.canonical_paths))

    def test_same_epoch_changed_actual_packet_bytes_refuse_without_new_queries(self):
        with scope(self.cache):
            self.f.capture(self.owner);self.f.historical()
            child=self.owner.children['trace'];ref=child.originals.expand(child.state['records'][0])
            path=child.originals.path(ref);before=path.stat();raw=path.read_bytes();calls=list(self.f.boundary.calls)
            path.write_bytes(raw[:-1]+(b' ' if raw[-1:]!=b' ' else b'\n'))
            self.assertEqual(before.st_ino,path.stat().st_ino)
            with self.assertRaises(NativeUIError):self.f.historical()
            self.assertEqual(calls,self.f.boundary.calls)

    def test_same_epoch_same_bytes_replaced_root_inode_refuses_without_recapture(self):
        with scope(self.cache):
            self.f.capture(self.owner);historical=self.f.historical()
            reference=deepcopy(self.owner.state['records'][0]);historical.frame_at(reference)
            path=self.owner.store.path;raw=path.read_bytes();inode=path.stat().st_ino;calls=list(self.f.boundary.calls)
            # Keep the original inode OUTSIDE the source membership namespace.
            tmp=TemporaryDirectory();self.addCleanup(tmp.cleanup);outside=Path(tmp.name);outside.chmod(0o700)
            held=outside/'original-root-wal';os.replace(path,held)
            with path.open('xb') as stream:stream.write(raw)
            path.chmod(0o600)
            self.assertEqual(raw,path.read_bytes());self.assertEqual(raw,held.read_bytes())
            self.assertEqual(inode,held.stat().st_ino);self.assertNotEqual(inode,path.stat().st_ino)
            with self.assertRaises(NativeUIError):historical.frame_at(reference)
            self.assertEqual(calls,self.f.boundary.calls)

    def test_same_scope_caller_mutation_does_not_change_original_values_or_membership(self):
        with scope(self.cache):
            self.f.capture(self.owner);historical=self.f.historical();reference=self.owner.state['records'][0]
            original=historical.frame_at(reference);calls=list(self.f.boundary.calls)
            changed=historical.frame_at(reference);changed[1]['sources']['roots'].clear()
            self.assertEqual(original,historical.frame_at(reference));self.assertEqual(calls,self.f.boundary.calls)
            self.assertEqual(self.f.canonical,self.f.pins(self.f.canonical_paths))


if __name__=='__main__':unittest.main()
