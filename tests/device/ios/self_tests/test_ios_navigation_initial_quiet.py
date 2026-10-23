"""Same-process actual PNG/input acquisitions and original quiet clocks."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
import uuid

from adapters.normal_ui import NativeUIError
from ios.adapters.navigation_initial_quiet import compose
from ios.adapters.navigation_whole_preparation import NavigationWholePreparation
from ios.self_tests import test_ios_navigation_initial_restored_image as images


class NavigationInitialQuietTests(unittest.TestCase):
    setUp=images.NavigationInitialRestoredImageTests.setUp
    acquire=images.NavigationInitialRestoredImageTests.acquire
    inputs=images.NavigationInitialRestoredImageTests.inputs
    owner=images.NavigationInitialRestoredImageTests.owner

    def test_actual_quiet_preserves_same_process_holds_and_rejects_real_later_contacts(self):
        call=self.acquire();self.inputs();h=self.h
        with h.flow.held():
            preparation=NavigationWholePreparation(h.flow);preparation.load();baselines,admission=preparation.originals()
            rows=[]
            for index in range(3):
                if index:h.sdk.gpu.sleep(1.6)
                current=self.owner(call,'ios-'+uuid.uuid4().hex);current.acquire(h.now());rows.append(current)
            proof=compose(rows,baselines['primary'],admission)
            self.assertEqual(3,len(proof['originals']));self.assertTrue(proof['lifetimeEndRequired'])
            self.assertTrue(all(row['changedPixels']==0 for row in proof['comparisons']))
            commands=deepcopy(h.gpu.commands);keys=deepcopy(self.keys.commands);pointer=deepcopy(self.pointer.requests)
            historical=[self.owner(call,row.request,historical=True) for row in rows]
            self.assertEqual(proof,compose(historical,baselines['primary'],admission))
            self.assertEqual(commands,h.gpu.commands);self.assertEqual(keys,self.keys.commands);self.assertEqual(pointer,self.pointer.requests)
            for invalid in (rows[:2],[rows[0],rows[1],rows[1]]):
                with self.assertRaises(NativeUIError):compose(invalid,baselines['primary'],admission)
            self.pointer.touch('touch-begin');self.pointer.touch('touch-end')
            later=self.owner(call,'ios-'+uuid.uuid4().hex);later.acquire(h.now())
            with self.assertRaises(NativeUIError):compose([rows[0],rows[1],later],baselines['primary'],admission)

    def test_three_genuine_cuts_without_the_original_three_second_window_are_insufficient(self):
        call=self.acquire();self.inputs();h=self.h
        with h.flow.held():
            preparation=NavigationWholePreparation(h.flow);preparation.load();baselines,admission=preparation.originals()
            rows=[]
            for _index in range(3):
                current=self.owner(call,'ios-'+uuid.uuid4().hex);current.acquire(h.now());rows.append(current)
            with self.assertRaises(NativeUIError):compose(rows,baselines['primary'],admission)


if __name__=='__main__':unittest.main()
