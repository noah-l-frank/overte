"""Repeated real historical rows reuse only their already-qualified owner."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from unittest.mock import patch
import unittest

from adapters.normal_ui import NativeUIError
from ios.adapters.navigation_observation_owner import NavigationObservationOwner,validation_round
from ios.self_tests import test_ios_navigation_observer as fixtures


class NavigationObserverRoundTests(unittest.TestCase):
    def setUp(self):
        self.h=fixtures.NavigationObserverTests();self.h.setUp();self.addCleanup(self.h.doCleanups)

    def test_actual_qualified_carrier_is_constructed_once_and_reopened_without_new_queries(self):
        h=self.h
        with h.held():
            observer=h.observer();h.take(observer);commands=list(h.gpu.commands);calls=[];original=NavigationObservationOwner.__init__
            def constructing(owner,*args,**kwargs):calls.append(args[0].path);original(owner,*args,**kwargs)
            with patch.object(NavigationObservationOwner,'__init__',constructing),validation_round(fresh=True):
                historical=h.observer(historical=True);a=historical.owners();b=historical.owners()
                self.assertEqual(1,len(calls));self.assertIs(a[0],b[0]);self.assertEqual(commands,h.gpu.commands)
            with validation_round(fresh=True):
                self.assertIsNot(a[0],h.observer(historical=True).owners()[0])

    def test_mutated_cached_owner_cannot_borrow_the_same_original_hash(self):
        h=self.h
        with h.held():
            observer=h.observer();h.take(observer);commands=list(h.gpu.commands)
            with self.assertRaises(NativeUIError),validation_round(fresh=True):
                historical=h.observer(historical=True);owner=historical.owners()[0]
                owner.state['result']['state']['location']='B'
                with self.assertRaises(NativeUIError):historical.owners()
                # Restore no original. The outer reader must still reject this
                # failed in-memory owner at its unchanged final guard.
                with self.assertRaises(NativeUIError):owner.archive()
            self.assertEqual(commands,h.gpu.commands)


if __name__=='__main__':unittest.main()
