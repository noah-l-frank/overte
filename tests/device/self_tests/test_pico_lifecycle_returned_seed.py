"""Same-invocation actual row seed; no complete born-host qualification."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import unittest
import sys
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from self_tests import test_pico_lifecycle_background_state5 as fixture_module

class LifecycleReturnedSeedTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixture_module.LifecycleBackgroundState5Tests();self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups);self.fixture.prepare()
        self.owner=self.fixture.owner;self.seams=self.fixture.seams;self.bank=self.fixture.bank

    def test_normal_first_packet_uses_actual_same_invocation_row_once_and_recovery_acquires_new_original(self):
        owner=self.owner;capture=owner.capture;captures=[];packets=[]
        # Quiet5 does not escape public packet DTOs. Observe the exact actual
        # sealed method's return without replacing its admitted instance API.
        code=type(owner.state5).__dict__['quiet_step'].__code__
        def sampled():
            row=capture();captures.append((row,owner.fresh_anchor));return row
        def stop_after_actual_quiet_return(frame,event,result):
            if event=='return' and frame.f_code is code and type(result) is tuple:
                packets.append((frame.f_locals['row'],owner.fresh_anchor,result[1]))
                raise NativeUIError('Intentional counter stops after actual quiet packet; no whole claim')
        def run_to_boundary():
            previous=sys.getprofile()
            try:
                sys.setprofile(stop_after_actual_quiet_return)
                with self.assertRaises(NativeUIError):owner.run_owned()
            finally:sys.setprofile(previous)
        with patch.object(owner,'capture',sampled):
            run_to_boundary()
            self.assertEqual(1,len(captures));self.assertEqual(1,len(packets))
            self.assertIs(captures[0][0],packets[0][0]);self.assertIs(captures[0][1],packets[0][1])
            self.assertEqual('returned',owner.state['phase']);before=self.bank.archive.state['reads']
            run_to_boundary()
        self.assertEqual(2,len(captures));self.assertEqual(2,len(packets))
        self.assertIs(captures[1][0],packets[1][0]);self.assertIs(captures[1][1],packets[1][1])
        self.assertIsNot(captures[0][0],captures[1][0]);self.assertGreater(self.bank.archive.state['reads'],before)
        self.assertIsNot(packets[0][2],packets[1][2])
        self.assertIsNot(packets[0][2].invocation,packets[1][2].invocation)
        self.assertEqual(['lifecycle.background','app.launch'],self.seams.inputs)
        self.assertEqual(['arm'],[r['operation'] for r in self.seams.history.commands if r['operation']!='observe'])
        self.assertEqual(captures[0][0]['hostMonotonic'],packets[0][0]['hostMonotonic'])

    def test_actual_returned_capture_work_does_not_renew_original_freshness_or_query_after_expiry(self):
        owner=self.owner;capture=owner.capture;save=owner.save;packet=owner.packet;captures=[];reads=[];public_packets=[]
        def sampled():
            row=capture();captures.append((row,owner.fresh_anchor));return row
        def delayed(value):
            save(value)
            if value['phase']=='returned':
                reads.append(self.bank.archive.state['reads']);self.seams.native.clock+=2
        def actual_packet(row):
            if not owner._plain5:public_packets.append(row)
            return packet(row)
        with patch.object(owner,'capture',sampled),patch.object(owner,'save',delayed),patch.object(owner,'packet',actual_packet):
            with self.assertRaises(NativeUIError):owner.run_owned()
            self.assertEqual([],public_packets)
        self.assertEqual(1,len(captures));self.assertEqual([self.bank.archive.state['reads']],reads)
        self.assertIs(captures[0][1],owner.fresh_anchor)
        self.assertEqual(['lifecycle.background','app.launch'],self.seams.inputs)
        self.assertEqual('returned',owner.state['phase'])
