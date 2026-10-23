"""Actual read-only retired fixture sources never stand in for product facts."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.adapters.navigation_run_retirement import NavigationRunRetirement,validate
from ios.self_tests import test_ios_navigation_fixture as fixture

TICKET='c'*32


class NavigationRunRetirementTests(unittest.TestCase):
    setUp=fixture.NavigationFixtureTests.setUp
    reader=fixture.NavigationFixtureTests.reader

    def test_exact_retired_authority_replays_without_any_source_request(self):
        source=self.reader();self.harness.client.activate(TICKET,'cleanup',{});self.harness.client.close()
        original=NavigationRunRetirement(source,TICKET).read();before=deepcopy(original)
        with patch.object(source.client,'request',side_effect=AssertionError('Historical request')):
            self.assertEqual(original,validate(original,run=self.run,instance=source.instance,inputs=source.inputs,ticket=TICKET))
        self.assertEqual(before,original);self.assertFalse(original['scene']['active'])
        self.assertNotIn('state',original);self.assertNotIn('processId',original)

    def test_live_run_or_wrong_terminal_ticket_cannot_authorize_stop(self):
        source=self.reader();self.harness.client.activate(TICKET,'cleanup',{})
        with self.assertRaises((NativeUIError,ValueError)):NavigationRunRetirement(source,TICKET).read()
        self.harness.client.close()
        with self.assertRaises((NativeUIError,ValueError)):NavigationRunRetirement(source,'d'*32).read()

    def test_original_provider_phase_and_clock_context_cannot_be_relabelled(self):
        source=self.reader();self.harness.client.activate(TICKET,'cleanup',{});self.harness.client.close()
        original=NavigationRunRetirement(source,TICKET).read()
        for fault in ('provider','area','ticket','active','clock'):
            value=deepcopy(original)
            if fault=='provider':value['scene']['instance']='f'*32
            elif fault=='area':value['authorityAfter']['area']='graphics'
            elif fault=='ticket':value['authorityAfter']['activations'][-1]['ticket']='d'*32
            elif fault=='active':value['navigation']['active']=True
            else:value['acquisition']['hostBeforeMonotonic']-=2
            with self.subTest(fault=fault),self.assertRaises((NativeUIError,ValueError)):
                validate(value,run=self.run,instance=source.instance,inputs=source.inputs,ticket=TICKET)
