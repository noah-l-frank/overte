"""Aggregate immutable reads keep complete candidate and file boundaries.

Native/clock producers are explicit test models. Actual private files, real
locks, history codecs and mutation/read/send guards execute unchanged.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.adapters.tablet_web_source_owner import TabletWebSourceOwner
from ios.self_tests import test_ios_tablet_web_source_owner as fixture


class TabletParentStorageGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixture.TabletWebSourceOwnerTests.setUpClass()
    def setUp(self):
        self.f=fixture.TabletWebSourceOwnerTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.source=self.f.prepare()
        self.f.capture(self.source)
        self.active=True;self.guards=[]
    def guard(self):self.guards.append(self.active);return self.active
    def owner(self,*,historical=False,guard=None):
        f=self.f
        return TabletWebSourceOwner(f.root,fixture.BINDING,fixture.RUN,'actor',fixture.ROOT,31,f.lock,guard or self.guard,
            epoch_ms=lambda:int(f.boundary.host+f.boundary.mono*1000),monotonic=lambda:f.boundary.mono,historical=historical)
    def originals(self):return {p.name:p.read_bytes() for p in self.f.root.iterdir() if p.is_file()}
    def test_real_parent_and_app_files_do_not_repeat_live_candidate_checks_per_file(self):
        owner=self.owner();before=self.originals();queries=list(self.f.boundary.calls);self.guards.clear()
        self.assertEqual(1,len(owner.history()))
        # Nine child histories retain their own original entry/exit guards;
        # the aggregate adds its complete candidate check before/after reads.
        self.assertEqual(20,len(self.guards));self.assertTrue(all(self.guards))
        self.assertEqual(before,self.originals());self.assertEqual(queries,self.f.boundary.calls)
    def test_candidate_changes_after_actual_parent_file_read_refuses_result_and_all_later_writes(self):
        owner=self.owner();read=owner.originals.read;before=self.originals();queries=list(self.f.boundary.calls)
        def changed(reference):
            result=read(reference);self.active=False;return result
        with patch.object(owner.originals,'read',side_effect=changed),self.assertRaises(NativeUIError):owner.history()
        self.assertEqual(0,getattr(owner,'_stored_read_depth',0))
        with self.assertRaises(NativeUIError):owner.save()
        with self.assertRaises(NativeUIError):self.f.capture(owner)
        with self.assertRaises(NativeUIError):owner.originals.read(owner.originals.expand(owner.state['records'][0]))
        self.assertEqual(before,self.originals());self.assertEqual(queries,self.f.boundary.calls)
    def test_private_read_scope_cannot_waive_child_capture_or_parent_write_guard(self):
        owner=self.owner();before=self.originals();queries=list(self.f.boundary.calls)
        with self.assertRaises(NativeUIError):
            with owner._stored_reads():
                self.active=False
                with self.assertRaises(NativeUIError):owner.children['sources'].capture(self.f.boundary.reader('sources'))
                with self.assertRaises(NativeUIError):owner.save()
        self.assertEqual(0,owner._stored_read_depth)
        self.assertEqual(before,self.originals());self.assertEqual(queries,self.f.boundary.calls)
    def test_historical_parent_files_never_acquire_SDK_authority_and_keep_mutators_blocked(self):
        def forbidden():raise AssertionError('Historical immutable file read cannot query current process')
        owner=self.owner(historical=True,guard=forbidden);before=self.originals();queries=list(self.f.boundary.calls)
        self.assertEqual(1,len(owner.history()))
        with self.assertRaises(NativeUIError):owner.save()
        with self.assertRaises(NativeUIError):self.f.capture(owner)
        self.assertEqual(before,self.originals());self.assertEqual(queries,self.f.boundary.calls)
    def test_false_candidate_before_constructor_creates_no_journal_or_query(self):
        before=self.originals();queries=list(self.f.boundary.calls);self.active=False
        with self.assertRaises(NativeUIError):self.owner()
        self.assertEqual(before,self.originals());self.assertEqual(queries,self.f.boundary.calls)


if __name__=='__main__':unittest.main()
