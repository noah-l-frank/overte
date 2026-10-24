"""Original first fourteen steps → authorized normal Script Stop, not retirement."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch

from adapters.normal_ui import NativeUIError
from feature_journeys.phase_fixture import PhasePending
from feature_journeys.scenarios import VERSION
from self_tests import test_pico_world_web_recovery_prefix as previous


class WorldWebNormalCloseTests(unittest.TestCase):
    setUp=previous.WorldWebRecoveryPrefixTests.setUp
    run=previous.WorldWebRecoveryPrefixTests.run
    stop=previous.WorldWebRecoveryPrefixTests.stop
    activate=previous.WorldWebRecoveryPrefixTests.activate
    call=previous.WorldWebRecoveryPrefixTests.call
    baseline=previous.WorldWebRecoveryPrefixTests.baseline
    prefix=previous.WorldWebRecoveryPrefixTests.prefix

    def cleanup_call(self):
        self.activate('cleanup',{})
        return dict(contractVersion=VERSION,runId=self.run)

    def test_first_fourteen_then_normal_owned_stop_closes_ui_and_keeps_original_vm_resources(self):
        self.prefix(14);old=[]
        for role in (self.primary,self.actor):
            with role.lock.held():old.append([path.read_bytes() for path in [role.history.chunks.store(i).path for i in range(len(role.history.rows))]])
        self.primary.normal_close(self.cleanup_call())
        self.assertEqual('source-stopped',self.primary.state['phase']);self.assertEqual(14,len(self.primary.state['completed']))
        self.assertEqual(1,len([row for row in self.target.normal_inputs if row['controlId']=='scripts.stop.0']))
        self.assertFalse(self.target.qt.opened);self.assertEqual([],self.target.qt.rows);self.assertIsNone(self.target.current)
        first=self.primary.observe();second=self.actor.observe();self.assertEqual(first['state'],second['state'])
        self.assertFalse(first['state']['open']);self.assertIn('script:world-web-client',first['resources'])
        self.assertEqual([],first['artifacts']);self.assertTrue(self.primary.store.path.is_file())
        diagnostic=self.primary.state['inputs'][-1]['original']['closureDiagnostic'];self.assertEqual([],diagnostic['scripts'])
        for index,role in enumerate((self.primary,self.actor)):
            with role.lock.held():self.assertEqual(old[index],[path.read_bytes() for path in [role.history.chunks.store(i).path for i in range(len(old[index]))]])
        commands=deepcopy(self.target.transport.envelopes);inputs=deepcopy(self.target.normal_inputs)
        cold=self.facade.prefix(self.target.selector,self.primary.source,self.foreign)
        cold.normal_close(dict(contractVersion=VERSION,runId=self.run))
        self.assertEqual(commands,self.target.transport.envelopes);self.assertEqual(inputs,self.target.normal_inputs)

    def test_applied_lost_stop_retains_closing_and_cold_never_replays(self):
        self.prefix(14);call=self.cleanup_call();self.target.fail_stop_reply=True
        with self.assertRaises(NativeUIError):self.primary.normal_close(call)
        self.assertEqual([],self.target.qt.rows);self.assertIsNone(self.target.current)
        inputs=deepcopy(self.target.normal_inputs);commands=deepcopy(self.target.transport.envelopes)
        cold=self.facade.prefix(self.target.selector,self.primary.source,self.foreign)
        with self.assertRaises(NativeUIError):cold.normal_close(call)
        with self.assertRaises(PhasePending):cold.observe()
        self.assertEqual('closing',cold.state['phase']);self.assertEqual(inputs,self.target.normal_inputs)
        self.assertEqual(commands,self.target.transport.envelopes)

    def test_normal_stop_row_absence_does_not_manufacture_script_ending_or_entity_release(self):
        self.prefix(14);self.target.ignore_script_ending=True
        self.primary.normal_close(self.cleanup_call());self.assertEqual([],self.target.qt.rows)
        self.assertIsNotNone(self.target.current)
        with self.assertRaises(NativeUIError):self.primary.observe()
        self.assertTrue(self.primary.store.path.exists());self.assertEqual('reading',self.primary.history.disk['phase'])

    def test_without_original_cleanup_ticket_no_stop_or_tablet_input_is_delivered(self):
        self.prefix(14);inputs=deepcopy(self.target.normal_inputs);commands=deepcopy(self.target.transport.envelopes)
        with self.assertRaises(NativeUIError):self.primary.normal_close(dict(contractVersion=VERSION,runId=self.run))
        self.assertEqual(inputs,self.target.normal_inputs);self.assertEqual(commands,self.target.transport.envelopes)
        self.assertEqual('ready',self.primary.state['phase'])

    def test_frozen_native_clock_cannot_hide_slow_landed_source_stopped_cas(self):
        self.prefix(14);call=self.cleanup_call();write=self.primary.store.write;now=self.primary.source.monotonic;extra=[0]
        def save(value,previous):
            write(value,previous)
            from adapters.script_journey.history import unpack
            if unpack(value['payload'])[0]['phase']=='source-stopped':extra[0]+=2
        with patch.object(self.primary.source,'monotonic',side_effect=lambda:now()+extra[0]),patch.object(self.primary.store,'write',side_effect=save):
            with self.assertRaises(NativeUIError):self.primary.normal_close(call)
        self.assertEqual(2,extra[0]);self.assertTrue(self.primary.failed)
        self.assertEqual('source-stopped',self.primary.state['phase']);self.assertTrue(self.primary.store.path.exists())


if __name__=='__main__':unittest.main()
