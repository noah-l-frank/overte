"""Historical abandoned marker originals cannot become a live owner or fact."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUIError
from adapters.original_marker_recovery import OriginalMarkerRecovery
from ios.adapters.emote_marker_scope import IOSEmoteMarkerScope
from ios.adapters.emote_retirement import Frozen
from ios.adapters.emote_marker_recovery import IOSEmoteMarkerRecovery
from ios.self_tests import test_ios_emote_marker_owner as fixture


class RecoveryArchiveTests(unittest.TestCase):
    def test_actual_lost_read_replays_retained_prefixes_without_reopening_or_mutating_scope(self):
        h=fixture.MarkerOwnerTests();h.setUp();self.addCleanup(h.doCleanups)
        h.test_lost_passive_marker_read_retains_returned_originals_and_uses_distinct_future_reads()
        h.scope.cleanup();live=IOSEmoteMarkerRecovery(h.scope);value=live.store.read();before=live.store.path.read_bytes()
        retained=IOSEmoteMarkerScope.archive(h.scope.store.read(),root=h.scope.root,binding=h.scope.binding,run=h.scope.run,role=h.scope.role,lock=h.scope.lock)
        archived=OriginalMarkerRecovery.archive(value,retained,Frozen(live.store.path,value))
        self.assertTrue(archived.follow(retained.frames[-1],historical=True))
        for operation in (archived.recover,lambda:archived.follow(retained.frames[-1])):
            with self.assertRaises(NativeUIError):operation()
        changed=deepcopy(retained.frames[-1]);changed['label']='unretained-frame'
        with self.assertRaises(NativeUIError):archived.follow(changed,historical=True)
        self.assertEqual(before,live.store.path.read_bytes());self.assertTrue(retained.failed)
