"""Cold capture custody and real host Background5/Pending3 composition.

Native/Qt are declared models. Host clocks, process identity, files and the
original readers/validators are real. These cases do not qualify Source8 or
the complete Lifecycle journey.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import sys
import unittest

from adapters.normal_ui import NativeUIError
from adapters.pico4.lifecycle_background_state5 import LifecycleBackgroundState5
from adapters.pico4.lifecycle_source_raw import REFERENCE, key
from self_tests.test_pico_lifecycle_background_state5 import LifecycleBackgroundState5Tests
from self_tests.pico_lifecycle_pending3_diagnostic import LifecyclePending3Background5Tests


class LifecycleCapture5Tests(unittest.TestCase):
    def fixture(self):
        case=LifecycleBackgroundState5Tests();case.QUIET_PERIOD=.75;case.setUp()
        self.addCleanup(case.doCleanups);case.prepare();return case

    def test_cold_capture_returns_projected_rows_with_original_custody_and_known_close(self):
        case=self.fixture();case.owner.run_owned();helper=case.owner.state5
        self.assertEqual('released',case.owner.state['phase'])
        self.assertIsNone(helper.current_capture);self.assertIsNotNone(helper.completed_capture)
        self.assertEqual(['lifecycle.background','app.launch'],case.seams.inputs)
        with case.seams.lock.held():
            for name in ('quiet','finalQuiet'):
                rows=case.owner.state[name];self.assertEqual(5,len(rows))
                self.assertGreaterEqual(rows[-1]['hostMonotonic']-rows[0]['hostMonotonic'],3)
                for row in rows:
                    for role,original in [('feature',row['native']),
                            *((role,row['world'][role]) for role in ('ui','gesture','drive'))]:
                        self.assertEqual(REFERENCE,set(original));self.assertEqual(role,key(original)[0])
                        self.assertIn(key(original),case.bank.view('background').confirmed)
            case.bank.verify();bill=case.bank.other_bill();raw=case.bank.archive.bill()
        self.assertLessEqual(bill['decodedBytes']+raw['decodedBytes'],16*1024*1024)
        self.assertTrue(case.bank.close_host());self.assertTrue(case.namespace.close())

    def test_actual_post_commit_interruption_keeps_capture_and_blocks_every_next_source(self):
        case=self.fixture();helper=case.owner.state5;seen=[];previous=sys.getprofile()
        checkpoint=LifecycleBackgroundState5.capture_checkpoint.__code__
        def interrupt(frame,event,value):
            permit=helper.current_capture
            if event=='return' and frame.f_code is checkpoint and permit is not None and permit.root_confirmed:
                seen.append(permit);raise OSError('Actual post-commit caller interruption')
        try:
            sys.setprofile(interrupt)
            with self.assertRaises(NativeUIError):case.owner.run_owned()
        finally:sys.setprofile(previous)
        self.assertEqual(1,len(seen));permit=seen[0]
        self.assertIs(permit,helper.current_capture);self.assertIs(permit,permit.stage.graph)
        self.assertTrue(helper.failed);self.assertTrue(case.bank.failed)
        before=(case.bank.archive.state['reads'],len(case.seams.history.commands))
        with self.assertRaises(NativeUIError):
            with case.seams.lock.held():case.owner.capture()
        self.assertEqual(before,(case.bank.archive.state['reads'],len(case.seams.history.commands)))
        self.assertFalse(case.bank.close_host())

    def test_changed_cold_period_refuses_before_another_original_read_or_input(self):
        case=self.fixture();before=(case.bank.archive.state['reads'],list(case.seams.inputs))
        case.owner.quiet_period=.25
        with self.assertRaises(NativeUIError):
            with case.seams.lock.held():case.owner.bound()
        self.assertEqual(before,(case.bank.archive.state['reads'],case.seams.inputs))

    def test_real_host_background_release_then_original_pending_owner_preparation(self):
        case=LifecyclePending3Background5Tests();case.BACKGROUND_QUIET_PERIOD=.75
        self.addCleanup(case.doCleanups)
        case.test_real_owner_prepared_state_body_manifest_original_bank_and_fresh_after_actual_outer_exit()
        self.assertEqual('released',case.background.owner.state['phase'])
        self.assertEqual('prepared',case.owner.state['phase'])
        for name in ('quiet','finalQuiet'):
            times=[row['hostMonotonic'] for row in case.background.owner.state[name]]
            self.assertGreaterEqual(times[-1]-times[0],3)
            self.assertTrue(all(0<b-a<=1 for a,b in zip(times,times[1:])))
        self.assertIs(case.pending.pending_native.monotonic,case.pending.pending_wire.monotonic)


if __name__=='__main__':unittest.main()
