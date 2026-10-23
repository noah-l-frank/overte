"""Original process DTOs share pure decoding only inside the existing round."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch

from adapters.normal_ui import NativeUIError
from ios.adapters import navigation_process_context as process
from ios.adapters.navigation_observation_owner import validation_round
from ios.self_tests import test_ios_navigation_process_context as fixtures


class NavigationProcessRoundTests(unittest.TestCase):
    def setUp(self):
        self.h=fixtures.NavigationProcessContextTests();self.h.enable_context_round=False
        self.h.setUp();self.addCleanup(self.h.doCleanups)

    def test_actual_old_and_new_DTOs_decode_once_per_round_and_return_independent_copies(self):
        h=self.h;originals=deepcopy((h.initial,h.before,h.receipt,h.after,h.owners))
        with patch.object(process,'_snapshot',wraps=process._snapshot) as snapshots:
            with validation_round():
                expected=h.transfer();returned=h.transfer();returned['after']['missing']={'caller':'changed'}
                self.assertEqual(expected,h.transfer());self.assertEqual(expected,process.validate(expected,h.owners))
                self.assertEqual(2,snapshots.call_count)
            with validation_round():self.assertEqual(expected,h.transfer())
            self.assertEqual(4,snapshots.call_count)
        self.assertEqual(originals,(h.initial,h.before,h.receipt,h.after,h.owners))

    def test_changed_original_candidate_native_clock_owner_and_derived_fields_are_never_reused(self):
        h=self.h
        with validation_round():
            actual=h.transfer()
            for fault in ('candidate','clock','owner','derived','version'):
                broken=deepcopy(actual);owners=list(h.owners)
                if fault=='candidate':broken['restart']['input']['newBinding']['artifactSha256']='0'*64
                elif fault=='clock':broken['after']['clockJoin']['nativeAfter']['sequence']=0
                elif fault=='owner':owners[0]=owners[0]+'.foreign'
                elif fault=='derived':broken['currentScope']['originalsSha256']='0'*64
                else:broken['iosNavigationProcessContextVersion']=True
                with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError)):process.validate(broken,owners)
            self.assertEqual(actual,process.validate(actual,h.owners))


if __name__=='__main__':unittest.main()
