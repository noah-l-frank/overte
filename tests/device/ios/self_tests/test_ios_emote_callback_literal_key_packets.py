"""Literal actual key packets replace only the explicit Callback packet memo.

Genuine file/raw owners and declared native key fixture run; no source/native
clock, SDK/device or whole Window/end qualification follows from these cases.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.script_feature.lock import ScriptSourceLock
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.original_file_reads import scope as file_reads
from ios.adapters import emote_archive_round as rounds
from ios.self_tests.test_ios_emote_key_original_round import FreshKeys


class CallbackLiteralKeyPacketTests(FreshKeys,unittest.TestCase):
    def literal(self):
        return rounds.scope(self.value,lock=self.live.lock,primary_lock=self.live.lock,key_packet_policy=rounds.LITERAL_PACKETS)

    def test_explicit_packet_reads_actual_bytes_each_time_with_same_membership_and_detached_values(self):
        owner=self.archive;receipt=owner.original(self.references[0]);commands=deepcopy(self.boundary.commands);pins=self.pins()
        with patch.object(owner,'_packet',wraps=owner._packet) as actual,self.literal():
            with file_reads(fresh=True) as first:a=owner.packet(receipt)
            a['runId']='f'*32
            with file_reads(fresh=True) as second:b=owner.packet(receipt)
            self.assertEqual(2,actual.call_count);self.assertEqual(first,second)
            self.assertIn(owner.raw.originals.path(receipt['wire']),first);self.assertEqual(owner.run,b['runId'])
        self.assertEqual(commands,self.boundary.commands);self.assertEqual(pins,self.pins())

    def test_default_none_keeps_existing_packet_memo_and_fresh_scopes_are_independent(self):
        owner=self.archive;receipt=owner.original(self.references[0])
        with patch.object(owner,'_packet',wraps=owner._packet) as actual:
            with self.round():owner.packet(receipt);owner.packet(receipt)
            self.assertEqual(1,actual.call_count)
            with self.literal():owner.packet(receipt);owner.packet(receipt)
            self.assertEqual(3,actual.call_count)
            with self.round():owner.packet(receipt);owner.packet(receipt)
            self.assertEqual(4,actual.call_count)

    def test_receipt_memo_and_its_full_guards_remain_even_with_literal_packets(self):
        owner=self.archive;reference=self.references[0]
        with self.assertRaises(NativeUIError),patch.object(owner,'_original',wraps=owner._original) as actual,self.literal() as current:
            a=owner.original(reference);b=owner.original(reference)
            self.assertEqual(a,b);self.assertEqual(1,actual.call_count);self.assertTrue(current.rows)
            PrivateFeatureState(owner.root/'unowned-original.json').write(dict(actual='orphan'),None)
            with self.assertRaises(NativeUIError):owner.original(reference)
            # Exit must refuse too; catching the inner failure grants no result.
            with self.assertRaises(NativeUIError):current.guard()
        # The enclosing context intentionally refuses the same inventory.

    def test_same_inode_changed_raw_bytes_are_reopened_and_refused_by_original_codec(self):
        owner=self.archive;receipt=owner.original(self.references[0]);path=owner.raw.originals.path(receipt['wire'])
        with self.assertRaises(NativeUIError),self.literal():
            owner.packet(receipt);before=path.stat();path.write_bytes(path.read_bytes()+b' ')
            self.assertEqual(before.st_ino,path.stat().st_ino)
            with self.assertRaises(NativeUIError):owner.packet(receipt)

    def test_same_body_replaced_raw_inode_is_refused_instead_of_a_prior_packet_result(self):
        owner=self.archive;receipt=owner.original(self.references[0]);path=owner.raw.originals.path(receipt['wire'])
        with self.assertRaises(NativeUIError),self.literal():
            owner.packet(receipt);before=path.stat();body=path.read_bytes();path.rename(path.with_name('retained-before-replacement'))
            path.write_bytes(body);path.chmod(0o600);self.assertNotEqual(before.st_ino,path.stat().st_ino)
            with self.assertRaises(NativeUIError):owner.packet(receipt)

    def test_original_raw_guard_and_replaced_packet_parser_are_called_without_old_result(self):
        owner=self.archive;receipt=owner.original(self.references[0]);error=ValueError('Actual replaced packet parser')
        with self.literal():
            owner.packet(receipt)
            with patch.object(owner,'_packet',side_effect=error),self.assertRaises(ValueError) as caught:owner.packet(receipt)
            self.assertIs(error,caught.exception)
            with patch.object(owner.raw.originals,'guard',return_value=False),self.assertRaises(NativeUIError):owner.packet(receipt)

    def test_changed_query_and_owner_binding_still_fail_actual_typed_decoder(self):
        owner=self.archive;receipt=owner.original(self.references[0])
        with self.literal():
            owner.packet(receipt);wrong=deepcopy(receipt);wrong['query']['runId']='f'*32
            with self.assertRaises(NativeUIError):owner.packet(wrong)
            before=deepcopy(owner.binding);owner.binding['processIdentity']='999' if before['processIdentity']!='999' else '998'
            try:
                with self.assertRaises(NativeUIError):owner.original(self.references[0])
            finally:owner.binding=before

    def test_foreign_held_owner_lock_refuses_before_any_literal_packet_decoder(self):
        owner=self.archive;receipt=owner.original(self.references[0]);directory=owner.root/'foreign-sdk';directory.mkdir(mode=0o700)
        foreign=ScriptSourceLock(directory/'script-feature-sources.lock');original=owner.lock
        with foreign.held(),self.literal(),patch.object(owner,'_packet',wraps=owner._packet) as actual:
            owner.lock=foreign
            try:
                with self.assertRaises(NativeUIError):owner.packet(receipt)
                self.assertEqual(0,actual.call_count)
            finally:owner.lock=original

    def test_noncallable_parser_list_refuses_before_literal_decoder(self):
        owner=self.archive;receipt=owner.original(self.references[0]);entered=[]
        with self.literal():
            for parsers in ([],[None],(owner._packet,)):
                with self.subTest(parsers=type(parsers).__name__),self.assertRaises(NativeUIError):
                    rounds.key_original(owner,'packet',dict(wire=receipt['wire'],query=receipt['query']),lambda:entered.append(True),parsers)
            self.assertEqual([],entered)

    def test_noncanonical_owner_boundary_and_false_raw_guard_refuse_before_decoder(self):
        owner=self.archive;receipt=owner.original(self.references[0]);root=owner.root
        with self.literal(),patch.object(owner,'_packet',wraps=owner._packet) as actual:
            owner.root=root/'..'
            try:
                with self.assertRaises(NativeUIError):owner.packet(receipt)
                self.assertEqual(0,actual.call_count)
            finally:owner.root=root
            with patch.object(owner.raw.originals,'guard',return_value=False),self.assertRaises(NativeUIError):owner.packet(receipt)
            self.assertEqual(0,actual.call_count)

    def test_literal_policy_still_requires_complete_unchanged_exit_inventory(self):
        owner=self.archive;receipt=owner.original(self.references[0]);entered=[]
        with self.assertRaises(NativeUIError),self.literal():
            owner.packet(receipt);PrivateFeatureState(owner.root/'unexpected-after-original.json').write(dict(actual=1),None)
            # This literal codec must actually run, but no successful complete
            # archive can return through the changed outer inventory.
            with patch.object(owner,'_packet',wraps=owner._packet) as actual:owner.packet(receipt);entered.append(actual.call_count)
        self.assertEqual([1],entered)


if __name__=='__main__':unittest.main()
