"""Exact default factory authority and new loaded-profile immutable leases."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from functools import partial
from unittest.mock import patch
import inspect,unittest
from adapters.normal_ui import NativeUIError
from ios.adapters import chat_archive_round,chat_qml_cache_loaded
from ios.self_tests.chat_loaded_peer_fixture import LoadedPairedFixture
from ios.self_tests.chat_peer_receipt_fixture import PeerReceiptFixture

class ChatLoadedArchiveLeaseTests(unittest.TestCase):
    def test_literal_default_receipt_factory_keeps_its_original_closed_signature(self):
        base=PeerReceiptFixture(self);f=base.f
        contexts=f.pair.runtime._chat_receipt_contexts('primary','peer',f.receive.run,f.models['primary'].client(),f.receive)
        for context in contexts.values():
            self.assertEqual({'contexts','fixture_url','receive','run','self'},set(inspect.getclosurevars(context.sender_owner.__wrapped__).nonlocals))
            self.assertTrue(chat_archive_round.factory(context))
    def test_loaded_round_refuses_changed_parser_coverage_constant_and_restores_exact_authority(self):
        loaded=LoadedPairedFixture(self);loaded.f.open();draft=loaded.f.drafts['primary']
        with draft.owner() as owner:
            self.assertTrue(chat_archive_round.eligible(owner));scope=chat_archive_round.ArchiveRound(owner);scope.check()
            original=deepcopy(chat_qml_cache_loaded.COVERAGE)
            try:
                chat_qml_cache_loaded.COVERAGE['importGraphAvailable']=True
                with self.assertRaises(NativeUIError):scope.check()
            finally:
                chat_qml_cache_loaded.COVERAGE.clear();chat_qml_cache_loaded.COVERAGE.update(original)
                scope.close()
            self.assertTrue(scope.closed);self.assertEqual(original,chat_qml_cache_loaded.COVERAGE)
    def test_loaded_round_refuses_changed_actual_selected_ipa_and_preserves_original_bytes(self):
        loaded=LoadedPairedFixture(self);loaded.f.open();draft=loaded.f.drafts['primary'];path=loaded.artifacts['primary'][0]
        original=path.read_bytes();backup=draft.f.root/'counter-original-independent-selected.ipa'
        with backup.open('xb') as stream:stream.write(original)
        backup.chmod(0o600)
        with draft.owner() as owner:
            self.assertTrue(chat_archive_round.eligible(owner));scope=chat_archive_round.ArchiveRound(owner);scope.check()
            changed=bytearray(original);changed[-1]^=1;path.write_bytes(changed)
            with self.assertRaises(NativeUIError):scope.check()
            with self.assertRaises(NativeUIError):scope.close()
            self.assertTrue(scope.closed);self.assertEqual(original,backup.read_bytes());self.assertNotEqual(original,path.read_bytes())


class ChatLiteralArchivePolicyTests(unittest.TestCase):
    def test_literal_round_does_not_call_loaded_parser_authority_or_gain_loaded_memory_fields(self):
        base=PeerReceiptFixture(self);f=base.f
        contexts=f.pair.runtime._chat_receipt_contexts('primary','peer',f.receive.run,f.models['primary'].client(),f.receive)
        for role,draft in f.drafts.items():draft.owner=partial(draft.owner,peer_receipts=contexts[role])
        with f.drafts['primary'].owner() as owner:
            self.assertEqual(6,owner.version);self.assertFalse(owner.qml_bound)
            with patch.object(chat_archive_round,'qml_authority',side_effect=AssertionError('Literal profile consulted loaded parser data')):
                scope=chat_archive_round.ArchiveRound(owner);scope.check()
                self.assertIsNone(scope.qml_authority)
                memory=chat_archive_round.memory(owner)[0]
                self.assertNotIn(b'"qml_bound"',memory);self.assertNotIn(b'"qmlArtifact"',memory)
                scope.close();self.assertTrue(scope.closed)
