"""Actual immutable key carriers under modeled Qt/native source producers.

No native/Qt/device code is executed. These cases preserve original files and
clocks while checking the bounded, one-round historical decoding reuse.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from adapters.original_file_reads import scope as file_reads
from ios.adapters import emote_archive_round as memo
from ios.adapters.emote_keys import IOSEmoteKeys
from ios.self_tests.test_ios_emote_keys import EmoteKeysTests


class FreshKeys:
    def setUp(self):
        self.fixture=EmoteKeysTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.live=self.fixture.owner;self.boundary=self.fixture.boundary
        self.references=[self.live.capture(),self.live.capture()];self.archive=self.archived()
        self.value=dict(artifactRoot=str(self.live.root),stateRoot=str(self.live.store.path.parent))
    def archived(self):
        owner=self.live
        return IOSEmoteKeys.archive(owner.store.read(),store=owner.store,root=owner.root,
            binding=owner.binding,run=owner.run,role=owner.role,lock=owner.lock)
    def round(self):return memo.scope(self.value,lock=self.live.lock,primary_lock=self.live.lock)
    def pins(self):
        result={}
        for path in self.live.root.iterdir():
            if path.is_file():
                stat=path.stat();result[path.name]=(stat.st_dev,stat.st_ino,stat.st_size,
                    stat.st_mtime_ns,stat.st_ctime_ns,hashlib.sha256(path.read_bytes()).hexdigest())
        return result


class KeysOriginalRoundTests(FreshKeys,unittest.TestCase):
    def test_real_receipt_and_raw_packet_decode_once_with_exact_membership_and_independent_values(self):
        owner=self.archive;ref=self.references[0];commands=deepcopy(self.boundary.commands)
        with patch.object(owner,'_original',wraps=owner._original) as originals,patch.object(owner,'_packet',wraps=owner._packet) as packets:
            with self.round():
                with file_reads(fresh=True) as first:receipt=owner.original(ref);packet=owner.packet(receipt)
                receipt['geometry']['observation']['nativeUi']['keyboardVisible']=True;packet['runId']='f'*32
                with file_reads(fresh=True) as second:
                    actual=owner.original(ref);current=owner.packet(actual)
                self.assertEqual(first,second);self.assertIn(owner.file(ref['index']).path,first)
                self.assertIn(owner.raw.originals.path(actual['wire']),first)
                self.assertIs(False,actual['geometry']['observation']['nativeUi']['keyboardVisible'])
                self.assertEqual(owner.run,current['runId']);self.assertEqual(1,originals.call_count);self.assertEqual(1,packets.call_count)
            with self.round():owner.original(ref)
            self.assertEqual(2,originals.call_count)
            owner.original(ref);owner.original(ref);self.assertEqual(4,originals.call_count)
        self.assertEqual(commands,self.boundary.commands)

    def test_current_owner_originals_are_not_cached_even_inside_a_historical_round(self):
        with patch.object(self.live,'_original',wraps=self.live._original) as original,self.round() as current:
            self.live.original(self.references[0]);self.live.original(self.references[0])
            self.assertEqual(2,original.call_count);self.assertEqual({},current.rows)

    def test_full_current_record_order_and_pending_shape_are_rechecked_after_warm_originals(self):
        owner=self.archive
        with self.round():
            owner.decode(owner.envelope(owner.state))
            invalid=deepcopy(owner.state);invalid['records'].append(self.references[0])
            with self.assertRaises(NativeUIError):owner.decode(owner.envelope(invalid))
            invalid=deepcopy(owner.state);invalid['pending']=dict(unowned=True)
            with self.assertRaises(NativeUIError):owner.decode(owner.envelope(invalid))

    def test_same_inode_receipt_rewrite_with_restored_mtime_cannot_borrow_warm_decode(self):
        owner=self.archive;ref=self.references[0];path=owner.file(ref['index']).path
        with self.assertRaises(NativeUIError),self.round():
            owner.original(ref);before=path.stat();path.write_bytes(path.read_bytes())
            os.utime(path,ns=(before.st_atime_ns,before.st_mtime_ns));self.assertEqual(before.st_ino,path.stat().st_ino)
            owner.original(ref)

    def test_same_inode_raw_rewrite_cannot_borrow_warm_packet(self):
        owner=self.archive;receipt=owner.original(self.references[0]);path=owner.raw.originals.path(receipt['wire'])
        with self.assertRaises(NativeUIError),self.round():
            owner.packet(receipt);before=path.stat();path.write_bytes(path.read_bytes())
            os.utime(path,ns=(before.st_atime_ns,before.st_mtime_ns));owner.packet(receipt)

    def test_new_unaccounted_original_blocks_a_warm_receipt(self):
        owner=self.archive;ref=self.references[0]
        with self.assertRaises(NativeUIError),self.round():
            owner.original(ref);PrivateFeatureState(owner.root/'new-unowned.json').write(dict(actual='new original'),None)
            owner.original(ref)

    def test_changed_actual_receipt_parser_runs_instead_of_an_old_memo(self):
        owner=self.archive;ref=self.references[0];error=ValueError('Changed original parser')
        with self.round():
            owner.original(ref)
            with patch.object(owner,'_original',side_effect=error),self.assertRaises(ValueError) as caught:owner.original(ref)
            self.assertIs(error,caught.exception)

    def test_changed_owner_binding_and_raw_profile_cannot_reuse_prior_results(self):
        owner=self.archive;ref=self.references[0]
        with self.round():
            receipt=owner.original(ref);owner.packet(receipt);binding=deepcopy(owner.binding)
            owner.binding['processIdentity']='32'
            with self.assertRaises(NativeUIError):owner.original(ref)
            owner.binding=binding;owner.raw.profile='avatar'
            with self.assertRaises(NativeUIError):owner.packet(receipt)

    def test_raw_guard_still_runs_when_the_receipt_and_packet_are_warm(self):
        owner=self.archive;ref=self.references[0]
        with self.round():
            receipt=owner.original(ref);owner.packet(receipt)
            owner.raw.originals.guard=lambda:False
            with self.assertRaises(NativeUIError):owner.original(ref)
            with self.assertRaises(NativeUIError):owner.packet(receipt)

    def test_changed_query_and_nonliteral_reference_are_rejected_after_warming(self):
        owner=self.archive;ref=self.references[0]
        with self.round():
            receipt=owner.original(ref);owner.packet(receipt)
            changed=deepcopy(receipt);changed['query']['runId']='f'*32
            with self.assertRaises(NativeUIError):owner.packet(changed)
            for wrong in (dict(ref,index=True),dict(ref,index=1.),dict(ref,sha256='A'*64),dict(ref,extra=1)):
                with self.subTest(reference=wrong),self.assertRaises(NativeUIError):owner.original(wrong)

    def test_bounded_cache_falls_back_to_complete_original_decode(self):
        owner=self.archive;ref=self.references[0]
        with patch.object(memo,'LIMIT',128),patch.object(owner,'_original',wraps=owner._original) as original,self.round() as current:
            before=owner.original(ref);self.assertEqual(before,owner.original(ref))
            self.assertEqual(2,original.call_count);self.assertEqual({},current.rows)

    def test_a_private_external_read_cannot_enter_this_round_without_its_own_inventory(self):
        directory=tempfile.TemporaryDirectory();self.addCleanup(directory.cleanup)
        external=PrivateFeatureState(Path(directory.name)/'external.json');external.write(dict(actual=1),None);calls=[]
        def decode():calls.append(True);return external.read()
        with self.round() as current:
            self.assertEqual(dict(actual=1),memo.key_original(self.archive,'receipt',self.references[0],decode,[decode]))
            external.write(dict(actual=2),external.read())
            self.assertEqual(dict(actual=2),memo.key_original(self.archive,'receipt',self.references[0],decode,[decode]))
            self.assertEqual({},current.rows);self.assertEqual(2,len(calls))


class KeysOriginalReplayMeasurement(FreshKeys,unittest.TestCase):
    def test_bounded_fresh_original_replay_measurement_preserves_every_file_and_query(self):
        for _ in range(80):
            for kind in ('key-press','key-release'):
                row=self.boundary.qt.enter(kind);self.boundary.qt.finish(row)
        ref=self.live.capture();owner=self.archived();commands=deepcopy(self.boundary.commands);before=self.pins()
        started=time.monotonic()
        # Keep the pre-existing full inventory/pure-validator round for the
        # baseline. Disable only this packet's new immutable key decoding memo.
        with patch('ios.adapters.emote_keys.key_original',side_effect=lambda _owner,_kind,_operand,decode,_parsers:decode()),self.round():
            for _ in range(8):plain=owner.original(ref)
        uncached=time.monotonic()-started;started=time.monotonic()
        with self.round():
            for _ in range(8):scoped=owner.original(ref)
        scoped_seconds=time.monotonic()-started
        self.assertEqual(plain,scoped);self.assertEqual(before,self.pins());self.assertEqual(commands,self.boundary.commands)
        print(json.dumps(dict(emoteKeyOriginalReplay=True,iterations=8,uncachedSeconds=uncached,scopedSeconds=scoped_seconds,
            files=len(before),originalsUnchanged=True,nativeQueries=0,
            scope='Fresh host key-carrier replay only; no whole journey/native/device/API timing qualification')),flush=True)


if __name__=='__main__':unittest.main()
