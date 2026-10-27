"""Pure Scope DTO reuse keeps byte/inode/CAS and fresh membership boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import cProfile
import unittest
from adapters.normal_ui import NativeUIError
from adapters.original_file_reads import scope as read_scope
from ios.adapters.world_web_identity import WorldWebLease
from ios.adapters.world_web_scope import IOSWorldWebScope
from ios.adapters.world_web_scope_archive import original_round,archived
from ios.self_tests.world_web_whole_fixture import ComposedWorldWeb


class WorldWebScopeArchiveTests(unittest.TestCase):
    def archive_count(self,profile,code):
        # getstats() observes the still-running profiler without disabling it.
        return sum(row.callcount for row in profile.getstats() if row.code is code)
    def prepared(self):
        whole=ComposedWorldWeb(use_whole_snapshot=True);self.addCleanup(whole.close);actions=whole.actions();actions.act(whole.sdk.activate('open',{}))
        entry=actions.state['calls'][-1];return whole,WorldWebLease(whole.scope,whole.source,entry['before'],entry['after'])
    def test_round_reuses_only_immutable_dtos_without_alias_and_new_membership_scopes_reopen_bytes(self):
        whole,lease=self.prepared();code=IOSWorldWebScope.archive.__func__.__code__
        with cProfile.Profile() as profile:
            with original_round():
                before=lease.packet();returned=archived(whole.scope,whole.source);returned.state['phase']='new';returned.frames.clear()
                self.assertEqual(before,lease.packet());self.assertEqual(1,self.archive_count(profile,code))
                for expected in (2,3):
                    with read_scope(fresh=True) as reads:
                        self.assertEqual(before,lease.packet());self.assertTrue(reads)
                        self.assertEqual(expected,self.archive_count(profile,code))
                        retained=set(reads)
                        self.assertEqual(before,lease.packet());self.assertEqual(expected,self.archive_count(profile,code))
                        self.assertEqual(retained,reads)
            with original_round():lease.packet()
            self.assertEqual(4,self.archive_count(profile,code))

    def test_clearing_same_census_membership_reopens_originals_instead_of_inventing_reads(self):
        whole,lease=self.prepared();code=IOSWorldWebScope.archive.__func__.__code__
        with cProfile.Profile() as profile,original_round(),read_scope(fresh=True) as reads:
            before=lease.packet();self.assertTrue(reads);self.assertEqual(1,self.archive_count(profile,code))
            reads.clear();self.assertEqual(before,lease.packet());self.assertTrue(reads)
            self.assertEqual(2,self.archive_count(profile,code))
    def test_warm_scope_CAS_context_and_same_bytes_different_inode_cannot_qualify(self):
        whole,lease=self.prepared()
        with original_round():
            lease.packet();saved=deepcopy(whole.scope.previous)
            whole.scope.previous['payload']='changed'
            with self.assertRaises(NativeUIError):lease.packet()
            whole.scope.previous=saved;old=whole.source.binding['sessionId'];whole.source.binding['sessionId']='foreign-session'
            with self.assertRaises(NativeUIError):lease.packet()
            whole.source.binding['sessionId']=old
        with self.assertRaises(NativeUIError):
            with original_round():
                lease.packet();path=whole.scope.store.path;replacement=path.with_suffix('.replacement')
                replacement.write_bytes(path.read_bytes());replacement.chmod(0o600);replacement.replace(path);lease.packet()


if __name__=='__main__':unittest.main()
