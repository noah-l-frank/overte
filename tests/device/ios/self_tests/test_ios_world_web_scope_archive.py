"""Pure Scope DTO reuse keeps byte/inode/CAS and fresh membership boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from adapters.original_file_reads import scope as read_scope
from ios.adapters.world_web_identity import WorldWebLease
from ios.adapters.world_web_scope import IOSWorldWebScope
from ios.adapters.world_web_scope_archive import original_round,archived
from ios.self_tests.world_web_whole_fixture import ComposedWorldWeb


class WorldWebScopeArchiveTests(unittest.TestCase):
    def prepared(self):
        whole=ComposedWorldWeb(use_whole_snapshot=True);self.addCleanup(whole.close);actions=whole.actions();actions.act(whole.sdk.activate('open',{}))
        entry=actions.state['calls'][-1];return whole,WorldWebLease(whole.scope,whole.source,entry['before'],entry['after'])
    def test_round_reuses_only_immutable_dtos_without_alias_and_new_membership_scopes_reopen_bytes(self):
        whole,lease=self.prepared();read=IOSWorldWebScope.archive
        with patch.object(IOSWorldWebScope,'archive',wraps=read) as actual:
            with original_round():
                before=lease.packet();returned=archived(whole.scope,whole.source);returned.state['phase']='new';returned.frames.clear()
                self.assertEqual(before,lease.packet());self.assertEqual(1,actual.call_count)
                for expected in (2,3):
                    with read_scope(fresh=True) as reads:
                        self.assertEqual(before,lease.packet());self.assertTrue(reads)
                        self.assertEqual(expected,actual.call_count)
            with original_round():lease.packet()
            self.assertEqual(4,actual.call_count)
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
