"""Actual immutable segment reuse keeps fresh WALs and rejection floors live."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
import unittest
from unittest.mock import patch
from adapters.original_file_reads import scope as read_scope
from adapters.normal_ui import NativeUIError
from ios.adapters.tablet_web_record_cache import TabletRecordCache,scope
from ios.self_tests import test_ios_tablet_web_packets as fixture


class TabletRecordCacheTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.TabletWebPacketsTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.owner=self.f.owner();self.owner.capture(self.f.reader());self.cache=TabletRecordCache()
    def test_full_double_decode_then_signature_hit_preserves_original_membership_and_deepcopy(self):
        with patch.object(self.owner.segments,'read',wraps=self.owner.segments.read) as reads,scope(self.cache):
            with read_scope(fresh=True) as first:values=self.owner.history()
            self.assertEqual(4,reads.call_count);values[0]['instance']='caller-mutation'
            with read_scope(fresh=True) as second:again=self.owner.history()
            self.assertEqual(first,second);self.assertGreaterEqual(len(second),2);self.assertEqual(4,reads.call_count)
            self.assertNotEqual('caller-mutation',again[0]['instance']);self.assertEqual(1,len(self.f.sends))
    def test_new_actual_rejected_raw_is_never_memoized_and_cannot_reset_source_floor(self):
        with scope(self.cache):
            self.owner.history();count=len(self.cache.originals.rows)
            def wrong(index):
                value=fixture.native_sources(index);value['instance']='0'*32;return value
            with self.assertRaises(NativeUIError):self.owner.capture(self.f.reader(wrong))
            self.owner.archive_pending(abandon=True);self.owner.history();self.assertTrue(self.owner.blocked)
            self.assertEqual(count,len(self.cache.originals.rows));calls=len(self.f.sends)
            with self.assertRaises(NativeUIError):self.owner.capture(self.f.reader())
            self.assertEqual(calls,len(self.f.sends));self.assertEqual(2,calls)
            row=self.owner.originals.read(self.owner.originals.expand(self.owner.state['records'][-1]))
            self.assertEqual('abandoned',row['status']);self.assertEqual('rejected',row['raws'][0]['outcome'])
    def test_same_bytes_same_inode_rewrite_and_hardlink_refuse_cached_interpretation(self):
        for fault in ('rewrite','hardlink'):
            with self.subTest(fault=fault):
                # Each actual mutation gets its own independently cold cache.
                cache=TabletRecordCache()
                with scope(cache):
                    self.owner.history();paths=next(iter(cache.originals.rows.values()))[1];path=next(iter(paths))
                    if fault=='rewrite':
                        before=path.stat();path.write_bytes(path.read_bytes());os.utime(path,ns=(before.st_atime_ns,before.st_mtime_ns))
                    else:os.link(path,self.f.root/'actual-hardlink')
                    try:
                        with self.assertRaises(NativeUIError):self.owner.history()
                    finally:
                        if fault=='hardlink':(self.f.root/'actual-hardlink').unlink()
    def test_no_scope_and_exception_restore_default_decoder_and_native_work_is_not_cached(self):
        with patch.object(self.owner.segments,'read',wraps=self.owner.segments.read) as reads:
            self.owner.history();self.owner.history();self.assertEqual(4,reads.call_count)
            try:
                with scope(self.cache):self.owner.history();raise OSError('Actual caller failed after full immutable replay')
            except OSError:pass
            before=reads.call_count;self.owner.history();self.assertEqual(before+2,reads.call_count)
        with scope(self.cache):self.owner.capture(self.f.reader())
        self.assertEqual(2,len(self.f.sends));self.assertEqual(2,len(self.owner.state['records']))


if __name__=='__main__':unittest.main()
