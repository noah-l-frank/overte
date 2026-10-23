"""Actual original PNG/source replay within one existing validation round.

File/HTTP/PNG owners are real; native/GPU acquisition producers are models.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from unittest.mock import patch
import unittest

from adapters.normal_ui import NativeUIError
from adapters.original_file_reads import scope as read_scope
from ios.adapters.navigation_observation_owner import validation_round
from ios.self_tests.navigation_baseline_image_fixture import Baseline


class NavigationImageRoundTests(unittest.TestCase):
    def setUp(self):self.f=Baseline(self);self.h=self.f.h

    def prepared(self):
        live=self.f.owner();expected=live.acquire(self.h.now())
        return live,self.f.owner(historical=True),expected

    def test_actual_decode_once_per_existing_round_returns_copies_and_new_round_reads_again(self):
        with self.h.flow.lock.held():
            live,owner,expected=self.prepared();commands=deepcopy(self.h.gpu.commands)
            with patch.object(owner,'qualify',wraps=owner.qualify) as decode:
                with validation_round():
                    first=owner.archive();first[0]['rendered']['location']='changed caller copy'
                    self.assertEqual(expected,owner.archive());self.assertEqual(1,decode.call_count)
                with validation_round():self.assertEqual(expected,owner.archive())
                self.assertEqual(2,decode.call_count)
            with patch.object(live,'qualify',wraps=live.qualify) as decode,validation_round():
                live.archive();live.archive();self.assertEqual(2,decode.call_count)
            self.assertEqual(commands,self.h.gpu.commands)

    def test_same_inode_changed_original_bytes_cannot_reuse_qualified_image(self):
        with self.h.flow.lock.held():
            _live,owner,_expected=self.prepared();path=owner.component('base').path;inode=path.stat().st_ino
            with self.assertRaises(NativeUIError),validation_round():
                owner.archive();path.write_bytes(path.read_bytes()+b'\n');self.assertEqual(inode,path.stat().st_ino)
                owner.archive()

    def test_identical_bytes_in_replaced_inode_are_rejected_even_at_round_exit(self):
        with self.h.flow.lock.held():
            _live,owner,_expected=self.prepared();path=owner.component('base').path;before=path.read_bytes();inode=path.stat().st_ino
            with self.assertRaises(NativeUIError),validation_round():
                owner.archive();path.rename(path.with_suffix('.retained-original'));path.write_bytes(before);path.chmod(0o600)
                self.assertNotEqual(inode,path.stat().st_ino)

    def test_outer_actual_read_collector_reopens_every_original_instead_of_hiding_membership(self):
        with self.h.flow.lock.held():
            _live,owner,expected=self.prepared()
            with patch.object(owner,'qualify',wraps=owner.qualify) as decode,validation_round():
                self.assertEqual(expected,owner.archive())
                with read_scope(fresh=True) as reads:self.assertEqual(expected,owner.archive())
                self.assertEqual(2,decode.call_count);self.assertIn(owner.component('base').path,reads)
                pngs=set(self.h.root.rglob('*.png'));self.assertTrue(pngs);self.assertTrue(pngs<=reads)


if __name__=='__main__':unittest.main()
