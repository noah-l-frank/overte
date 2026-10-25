"""Immutable auxiliary reuse still replays current rejected native floors."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from adapters.original_file_reads import scope as read_scope
from ios.adapters.tablet_web_record_cache import TabletRecordCache,scope
from ios.self_tests import test_ios_tablet_web_native_reads as fixture


class TabletAuxRecordCacheTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.TabletNativeReadsTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.owner=self.f.owner();self.packet=self.owner.capture(self.f.reader(),lambda reader:reader.read(self.f.qt.packet()['runId']))
        self.cache=TabletRecordCache()
    def test_actual_segments_double_checked_then_reused_with_complete_read_membership(self):
        with patch.object(self.owner.parts,'read',wraps=self.owner.parts.read) as reads,scope(self.cache):
            with read_scope(fresh=True) as first:value=self.owner.history()
            self.assertEqual(4,reads.call_count);value[0]['instance']='caller mutation'
            with read_scope(fresh=True) as second:again=self.owner.history()
            self.assertEqual(first,second);self.assertGreaterEqual(len(second),2);self.assertEqual(4,reads.call_count)
            self.assertEqual(self.packet,again[0]);self.assertEqual(1,len(self.f.sent))
    def test_new_wrong_source_original_remains_rejected_owned_and_blocks_new_queries(self):
        with scope(self.cache):
            self.owner.history();entries=len(self.cache.originals.rows)
            self.f.mutate=lambda value:value['source'].update(instance='0'*32)
            with self.assertRaises(NativeUIError):self.owner.capture(self.f.reader(),lambda reader:reader.read(self.packet['runId']))
            self.assertEqual([self.packet],self.owner.history());self.assertTrue(self.owner.blocked);pending=self.owner.state['pending']
            self.assertEqual('rejected',pending['raws'][0]['outcome']);self.assertEqual(entries,len(self.cache.originals.rows))
            self.assertIn('0'*32,self.owner.parts.read(pending['raws'][0]['parts']).decode())
            self.assertEqual([self.packet],self.owner.history());self.assertTrue(self.owner.blocked)
            before=len(self.f.sent)
            with self.assertRaises(NativeUIError):self.owner.capture(self.f.reader(),lambda reader:reader.read(self.packet['runId']))
            self.assertEqual(before,len(self.f.sent));self.assertEqual(2,before)
    def test_changed_original_and_same_raw_source_on_another_previous_packet_are_not_hits(self):
        with scope(self.cache):
            self.owner.history();row=self.owner.frames.read(self.owner.frames.expand(self.owner.state['records'][0]))
            changed=dict(self.packet,instance='0'*32)
            with self.assertRaises(NativeUIError):self.owner.record(row,1,changed)
            self.assertEqual(1,len(self.cache.originals.rows))
            signatures=next(iter(self.cache.originals.rows.values()))[1];path=next(iter(signatures));before=path.stat()
            path.write_bytes(path.read_bytes());os.utime(path,ns=(before.st_atime_ns,before.st_mtime_ns))
            with self.assertRaises(NativeUIError):self.owner.history()
    def test_new_native_query_still_sends_and_current_query_uniqueness_is_not_cached(self):
        with scope(self.cache):
            self.owner.history();self.owner.capture(self.f.reader(),lambda reader:reader.read(self.packet['runId']))
            self.assertEqual(2,len(self.f.sent));self.assertEqual(2,len(self.owner.history()))
            # Actual original references duplicated into the current WAL still
            # run the unmodified ordinal/query/raw-prefix history checks.
            self.owner.state['records'].append(self.owner.state['records'][0])
            with self.assertRaises(NativeUIError):self.owner.history()


if __name__=='__main__':unittest.main()
