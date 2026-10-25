"""Actual aggregate files retain current membership outside immutable reuse."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import os
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from adapters.original_file_reads import scope as read_scope
from ios.adapters.tablet_web_record_cache import TabletRecordCache,scope,parent_record
from ios.adapters.tablet_web_source_owner import TabletWebSourceOwner
from ios.self_tests import test_ios_tablet_web_source_owner as fixture


class TabletParentRecordCacheTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixture.TabletWebSourceOwnerTests.setUpClass()
    def setUp(self):
        self.f=fixture.TabletWebSourceOwnerTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.live=self.f.prepare();self.f.capture(self.live);self.owner=self.f.owner(historical=True)
        self.row=self.owner.originals.read(self.owner.originals.expand(self.owner.state['records'][0]))
        self.cache=TabletRecordCache()
    def parents(self):
        return [value for key,value in self.cache.originals.rows.items() if 'tabletImmutableParentVersion' in json.loads(key)]
    def test_full_double_decode_then_hit_restores_exact_file_membership_and_independent_values(self):
        original=TabletWebSourceOwner._record
        with patch.object(TabletWebSourceOwner,'_record',autospec=True,side_effect=original) as decode,scope(self.cache):
            with read_scope(fresh=True) as first:before=self.owner.history()
            self.assertEqual(2,decode.call_count);self.assertEqual(1,len(self.parents()))
            before[0]['sources']['roots'].clear()
            with read_scope(fresh=True) as second:after=self.owner.history()
            self.assertEqual(2,decode.call_count);self.assertEqual(first,second)
            self.assertTrue(after[0]['sources']['roots']);self.assertEqual(9,len(self.f.boundary.calls))
    def test_warm_parent_cannot_hide_changed_current_app_prefix_or_child_index_reference(self):
        with scope(self.cache):
            self.owner.history();self.assertEqual(1,len(self.parents()))
            saved=deepcopy(self.owner.state['apps']);self.owner.state['apps']=[]
            with self.assertRaises(NativeUIError):parent_record(self.owner,self.row,1,None,lambda:self.owner._record(self.row,1,None))
            self.owner.state['apps']=saved
            child=self.owner.children['sources'];saved=deepcopy(child.state['records'])
            for replacement in ([],[dict(saved[0],sha256='0'*64)]):
                child.state['records']=replacement
                with self.assertRaises(NativeUIError):parent_record(self.owner,self.row,1,None,lambda:self.owner._record(self.row,1,None))
            child.state['records']=saved
            self.assertEqual(1,len(self.owner.history()))
    def test_same_bytes_same_inode_rewrite_refuses_warm_immutable_frame(self):
        with scope(self.cache):
            self.owner.history();paths=self.parents()[0][1]
            path=next(path for path in paths if '-parts-' in path.name)
            before=path.stat();path.write_bytes(path.read_bytes());os.utime(path,ns=(before.st_atime_ns,before.st_mtime_ns))
            with self.assertRaises(NativeUIError):self.owner.history()
    def test_previous_native_and_actual_parser_identity_are_not_hidden_by_warm_entry(self):
        with scope(self.cache):
            self.owner.history();previous=deepcopy(self.row['nativeBefore']);previous['instance']='0'*32
            with self.assertRaises(NativeUIError):parent_record(self.owner,self.row,1,previous,lambda:self.owner._record(self.row,1,previous))
            # Actual changed decoder must run; a formerly qualified key cannot
            # bypass this new parser merely because the serialized row agrees.
            with patch.object(TabletWebSourceOwner,'_clock',side_effect=ValueError('Changed actual parser')):
                with self.assertRaises(ValueError):self.owner.history()
    def test_live_and_failed_records_always_retain_full_parent_decoder(self):
        original=TabletWebSourceOwner._record
        with patch.object(TabletWebSourceOwner,'_record',autospec=True,side_effect=original) as decode,scope(self.cache):
            self.live.history();self.live.history();self.assertEqual(2,decode.call_count);self.assertEqual([],self.parents())
            failed=deepcopy(self.row);failed.update(status='failed',clockJoin=None)
            parent_record(self.owner,failed,1,None,lambda:self.owner._record(failed,1,None))
            parent_record(self.owner,failed,1,None,lambda:self.owner._record(failed,1,None))
            self.assertEqual(4,decode.call_count);self.assertEqual([],self.parents())
    def test_new_rejected_child_original_still_blocks_current_history_after_parent_was_warmed(self):
        from ios.self_tests.test_ios_tablet_web_packets import native_sources
        with scope(self.cache):
            self.owner.history();child=self.live.children['sources']
            def wrong(index):
                value=native_sources(index);value['instance']='0'*32;return value
            from ios.self_tests.test_ios_tablet_web_packets import TabletWebPacketsTests
            boundary=TabletWebPacketsTests();boundary.setUp();self.addCleanup(boundary.doCleanups)
            with self.assertRaises(NativeUIError):child.capture(boundary.reader(wrong))
            child.archive_pending(abandon=True)
            rebuilt=self.f.owner(historical=True)
            self.assertTrue(rebuilt.blocked);self.assertEqual(1,len(rebuilt.history()))
            self.assertTrue(rebuilt.blocked);self.assertEqual(9,len(self.f.boundary.calls))
    def test_cold_parser_side_effect_on_any_blocked_flag_cannot_be_memoized(self):
        with scope(self.cache):
            def changed():
                answer=self.owner._record(self.row,1,None);self.owner.children['sources'].blocked=True;return answer
            with self.assertRaises(NativeUIError):parent_record(self.owner,self.row,1,None,changed)
            self.assertEqual([],self.parents())


if __name__=='__main__':unittest.main()
