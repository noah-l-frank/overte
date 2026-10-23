"""Actual normal Cancel owner reply grammar and late-commit recovery, no devices."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[5]))
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))
from adapters.normal_ui import NativeUIError
from adapters.pico4.snapshot_cancel_owner import validate_reply
from self_tests.test_pico_snapshot_reply_grammar import SnapshotReplyGrammarTests
import test_snapshot_cancel_owner as prefix


class SnapshotReplyOwnerTests(unittest.TestCase):
    def model(self):
        h=prefix.SnapshotCancelOwnerTests();h.setUp();self.addCleanup(h.doCleanups);return h

    def test_actual_normal_cancel_commits_after_exit_preserves_physical_fences_and_cold_load_has_no_admission(self):
        h=self.model()
        with patch('adapters.pico4.snapshot_cancel_owner.validate_reply',wraps=validate_reply) as decoder:
            h.cancelled();self.assertEqual('cancel-observed',h.owner.state['stage']);self.assertEqual(1,len(h.started))
            self.assertIsNotNone(h.owner.reply_grammar.previous);count=decoder.call_count;inputs=(len(h.adb.inputs),len(h.h.transport.envelopes))
            with h.lock.held():h.owner.load()
            self.assertEqual(count,decoder.call_count);self.assertEqual(inputs,(len(h.adb.inputs),len(h.h.transport.envelopes)))
            h.owner.reconcile();self.assertGreater(decoder.call_count,count);count=decoder.call_count
            with h.lock.held():h.owner.load()
            self.assertEqual(count,decoder.call_count);cold=h.make();self.assertGreater(decoder.call_count,count)
            self.assertIsNone(cold.reply_grammar.previous);self.assertEqual(inputs,(len(h.adb.inputs),len(h.h.transport.envelopes)))
            self.assertEqual(1,len(h.started));self.assertTrue(cold.store.path.exists())
            count=decoder.call_count;chunk=h.owner.originals.history.store(0).path;chunk.write_bytes(chunk.read_bytes()+b' ')
            with h.lock.held(),self.assertRaises(NativeUIError):h.owner.load()
            self.assertEqual(count,decoder.call_count);self.assertEqual(inputs,(len(h.adb.inputs),len(h.h.transport.envelopes)))

    def test_late_actual_reply_commit_refuses_return_keeps_originals_and_cold_reconcile_never_replays_input(self):
        h=self.model();commit=h.owner.reply_grammar.commit
        def slow(candidate):
            commit(candidate)
            if candidate['rows']:h.adb.clock+=2
        with patch.object(h.owner.reply_grammar,'commit',side_effect=slow),self.assertRaises(NativeUIError):h.cancelled()
        self.assertEqual(1,len(h.started));self.assertEqual('cancel-observed',h.owner.state['stage']);self.assertTrue(h.owner.reply_grammar.failed)
        self.assertIsNone(h.owner.reply_grammar.previous);inputs=(len(h.adb.inputs),len(h.h.transport.envelopes));cold=h.make()
        self.assertEqual('cancel-observed',cold.reconcile()['stage']);self.assertEqual(inputs,(len(h.adb.inputs),len(h.h.transport.envelopes)))
        self.assertEqual(1,len(h.started));self.assertTrue(cold.originals.root.path.exists())


if __name__=='__main__':unittest.main()
