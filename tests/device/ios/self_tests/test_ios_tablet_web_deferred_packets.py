"""Ninth original source uses the same durable once-query byte owner."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters import tablet_web_deferred as deferred
from ios.self_tests import test_ios_tablet_web_packets as packet_tests
from ios.self_tests.test_ios_tablet_web_deferred import packet


class TabletWebDeferredPacketTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.raw=packet()
    def setUp(self):
        self.helper=packet_tests.TabletWebPacketsTests('test_actual_queries_and_raw_bytes_reconstruct_with_new_reader_and_unchanged_callbacks');self.helper.setUp();self.addCleanup(self.helper.doCleanups)
    def producer(self,index):
        value=deepcopy(self.raw);value['sequence']=index;return value
    def test_actual_deferred_query_original_raw_and_inode_reconstruct_without_relabel_or_resend(self):
        owner=self.helper.owner('deferred');reader=self.helper.reader(self.producer,deferred.IOSTabletWebDeferred,epoch=self.raw['clockAfter']['epochMs'])
        actual=owner.capture(reader);rebuilt=self.helper.owner('deferred',historical=True)
        self.assertEqual([actual],rebuilt.history());record=rebuilt.originals.read(rebuilt.originals.expand(rebuilt.state['records'][0]))
        self.assertEqual(deferred.ACTION,record['query']['action']);self.assertEqual(actual,deferred.original(actual));self.assertEqual(1,len(self.helper.sends))
        with self.assertRaises(NativeUIError):rebuilt.capture(reader)
        self.assertEqual(1,len(self.helper.sends))
    def test_later_forged_source_reset_is_preserved_rejected_and_blocks_new_queries(self):
        owner=self.helper.owner('deferred');reader=self.helper.reader(self.producer,deferred.IOSTabletWebDeferred,epoch=self.raw['clockAfter']['epochMs']);owner.capture(reader)
        def wrong(index):
            value=self.producer(index);value['instance']='0'*32
            for receipt in value['commands']:receipt['instance']=value['instance']
            return value
        with self.assertRaises(NativeUIError):owner.capture(self.helper.reader(wrong,deferred.IOSTabletWebDeferred,epoch=self.raw['clockAfter']['epochMs']))
        rebuilt=self.helper.owner('deferred');self.assertTrue(rebuilt.blocked);self.assertEqual('rejected',rebuilt.state['pending']['raws'][0]['outcome'])
        self.assertEqual(2,len(self.helper.sends))


if __name__=='__main__':unittest.main()
