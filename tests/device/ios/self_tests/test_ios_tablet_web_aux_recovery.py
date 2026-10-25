"""Actual HTTP/AFC auxiliary recovery preserves failure and readback clocks.

Native data is explicitly modeled. Ordinary sources, nonce/raw WAL, private
immutable originals and exact read-only recovery paths execute unchanged.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from unittest.mock import patch
import unittest
from adapters.normal_ui import NativeUIError
from ios.self_tests.tablet_web_whole_fixture import TabletWholeBoundary


class TabletAuxRecoveryTests(unittest.TestCase):
    def setUp(self):self.boundary=TabletWholeBoundary(self);self.runtime=self.boundary.runtime
    def pending(self):
        self.boundary.lost='feature-ios-pointer-state'
        with self.assertRaises((OSError,NativeUIError)):self.runtime.read_auxiliary('pointer')
        self.boundary.lost=None;owner=self.runtime.auxiliary('pointer');return owner,deepcopy(owner.state['pending'])
    def test_old_nonce_AFC_readback_never_resends_and_keeps_original_failed_endpoints(self):
        owner,failed=self.pending();count=len(self.boundary.commands);self.boundary.sleep(4.)
        self.runtime.recover_auxiliaries([]);self.assertEqual(count,len(self.boundary.commands));self.assertIsNone(owner.state['pending'])
        row=owner.frames.read(owner.frames.expand(owner.state['records'][-1]));packet=owner.history()[-1]
        self.assertEqual('reconciled',row['status']);self.assertEqual(failed['after'],row['after']);self.assertEqual(failed['sendReturned'],row['sendReturned'])
        self.assertEqual({key:failed[key] for key in ('status','after','sendReturned','resultSha256')},row['failure'])
        self.assertGreaterEqual(row['readbacks'][0]['before']['monotonic']-row['after']['monotonic'],4.)
        self.assertEqual(failed['query']['commandId'],packet['requestId']);self.assertLess(packet['clockAfter']['epochMs'],self.boundary.epoch())
    def test_complete_owned_raw_after_lost_return_is_requalified_without_any_AFC_read(self):
        owner=self.runtime.auxiliary('pointer');write=owner.parts.write
        def lost(*args,**kwargs):write(*args,**kwargs);raise OSError('Complete raw file saved, write return lost')
        with patch.object(owner.parts,'write',side_effect=lost),self.assertRaises((OSError,NativeUIError)):self.runtime.read_auxiliary('pointer')
        failed=deepcopy(owner.state['pending']);count=len(self.boundary.commands);self.boundary.sleep(4.)
        _owner,reader,_invoke=self.runtime.auxiliary_reader('pointer')
        reader.original=lambda:(_ for _ in ()).throw(AssertionError('Retained original recovery must not read AFC'))
        owner.reconcile(reader);self.assertEqual(count,len(self.boundary.commands));row=owner.frames.read(owner.frames.expand(owner.state['records'][-1]))
        self.assertEqual('retained',row['readbacks'][0]['mode']);self.assertEqual(failed['after'],row['after']);self.assertEqual('accepted',row['raws'][0]['outcome'])
    def test_failed_readback_remains_separate_and_later_exact_original_lookup_does_not_reset_failure(self):
        owner,failed=self.pending();count=len(self.boundary.commands);_owner,reader,_invoke=self.runtime.auxiliary_reader('pointer')
        original=reader.original;reader.original=lambda:(_ for _ in ()).throw(OSError('Modeled AFC return lost'))
        with self.assertRaises(OSError):owner.reconcile(reader)
        self.assertEqual(failed['after'],owner.state['pending']['after']);self.assertEqual('failed',owner.state['pending']['readbacks'][0]['status'])
        self.boundary.sleep(3.);reader.original=original;owner.reconcile(reader)
        row=owner.frames.read(owner.frames.expand(owner.state['records'][-1]));self.assertEqual(['failed','returned'],[item['status'] for item in row['readbacks']])
        self.assertEqual(failed['after'],row['after']);self.assertEqual(count,len(self.boundary.commands))


if __name__=='__main__':unittest.main()
