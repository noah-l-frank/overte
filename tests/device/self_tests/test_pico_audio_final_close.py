"""Normal final X with real owner/readers and explicit controller/audio seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.normal_ui import NativeUIError
from adapters.pico4.audio_final_close import PicoAudioFinalClose
from self_tests import test_pico_audio_capture_owner as source_fixture


class AudioFinalCloseTests(unittest.TestCase):
    def setUp(self):
        self.fixture=source_fixture.AudioCaptureOwnerTests(methodName='runTest');self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.capture,self.native=self.fixture.owner,self.fixture.native
        self.fixture.start();self.fixture.cancel();self.capture.retain_originals();self.fixture.activate('close')
        self.final=self.owner()
    def owner(self):return PicoAudioFinalClose(self.fixture.path/'audio-final-close.json',self.fixture.capture_owner())
    def release(self):self.final.prepare();return self.final.release()
    def close(self):self.release();self.final.stream('back-issued');return self.final.stream('tablet-close-issued')
    def test_normal_close_restores_peak_and_closes_tablet_with_original_pcm_retained(self):
        self.close();result=self.final.quiet('closed')
        self.assertFalse(result['tabletShown']);self.assertFalse(result['pageAlive']);self.assertTrue(result['contextAlive'])
        self.assertEqual(self.native.origin_peak,result['inputPeakValuesEnabled']);self.assertTrue(result['privatePcmEmpty'])
        self.assertTrue(result['originalPcmRetained']);self.assertFalse(result['fullAudioQualified']);self.assertFalse(result['acousticObserved'])
        self.assertEqual(['home','closed'],[row['where'] for row in result['originalQuietWindows']])
        self.assertEqual(3,len(self.native.transport.envelopes));self.assertEqual(2,self.native.actions.count('audio.record'))
        self.assertEqual('retained',self.fixture.capture_owner().report()['phase'])
    def test_ack_only_x_cannot_claim_original_page_destruction(self):
        self.release();self.native.fault_effect='controller-ack-only'
        with self.assertRaises(NativeUIError):self.final.stream('back-issued')
        self.assertEqual('back-issued',self.final.state['phase']);count=len(self.native.transport.envelopes)
        with self.assertRaises(NativeUIError):self.owner().reconcile()
        self.assertEqual(count,len(self.native.transport.envelopes));self.assertTrue(self.final.store.path.exists())
    def test_hidden_retained_page_cannot_claim_normal_x_release(self):
        self.release();self.native.retain_page=True
        with self.assertRaises(NativeUIError):self.final.stream('back-issued')
        self.assertEqual('back-issued',self.final.state['phase'])
    def test_original_peak_not_restored_cannot_pass(self):
        self.release();self.native.fault_effect='peak-not-restored'
        with self.assertRaises(NativeUIError):self.final.stream('back-issued')
        self.assertEqual('back-issued',self.final.state['phase'])
    def test_lost_x_response_recovers_original_neutral_without_resending(self):
        self.release()
        with patch.object(self.native.session,'_wait_for_ack',side_effect=NativeUIError('Explicit ACK lost after original cursor commit')):
            with self.assertRaises(NativeUIError):self.final.stream('back-issued')
        count=len(self.native.transport.envelopes);result=self.owner().reconcile()
        self.assertEqual('home',result['phase']);self.assertEqual(count,len(self.native.transport.envelopes))
    def test_phase_progress_after_durable_x_intent_before_stage_blocks_input(self):
        self.release();original=self.final.save
        def changed(state,**kwargs):
            original(state,**kwargs)
            if state['phase']=='back-issued' and state['streams'][-1]['envelope'] is None:self.fixture.activate('cleanup')
        count=len(self.native.transport.envelopes)
        with patch.object(self.final,'save',side_effect=changed):
            with self.assertRaises(NativeUIError):self.final.stream('back-issued')
        self.assertEqual(count,len(self.native.transport.envelopes));self.assertEqual('back-issued',self.final.state['phase'])
    def test_native_terminal_history_cannot_disappear_after_private_tap_release(self):
        self.release();self.native.cycle=0
        with self.assertRaises(NativeUIError):self.final.stream('back-issued')
        self.assertEqual('released',self.final.state['phase']);self.assertEqual(1,len(self.native.transport.envelopes))
    def test_new_record_input_is_blocked_by_original_final_owner(self):
        self.final.prepare();self.fixture.activate('record-start')
        with self.assertRaises(NativeUIError):self.capture.phase('record-start')
        self.assertEqual(2,self.native.actions.count('audio.record'))
    def test_final_copy_and_guard_age_included_with_frozen_host_clock(self):
        self.release();original=self.final.report;frozen=self.native.clock
        self.capture.parent.settings.monotonic=lambda:frozen
        def late():value=original();self.native.clock+=2;return value
        with patch.object(self.final,'report',side_effect=late):
            with self.assertRaises(NativeUIError):self.final.stream('back-issued')
        self.assertTrue(self.final.store.path.exists());self.assertEqual('home',self.final.state['phase'])

    def test_lost_grant_commit_boundary_never_adopts_cursor_or_resends(self):
        self.release();original=self.native.transport.stage
        def lost(*args):original(*args);raise NativeUIError('Explicit grant reply lost before host cursor commit')
        with patch.object(self.native.transport,'stage',side_effect=lost):
            with self.assertRaises(NativeUIError):self.final.stream('back-issued')
        count=len(self.native.transport.envelopes)
        with self.assertRaises(NativeUIError):self.owner().reconcile()
        self.assertEqual(count,len(self.native.transport.envelopes));self.assertEqual('back-issued',self.final.state['phase'])
    def test_lost_private_release_response_inspects_absence_without_resend(self):
        self.final.prepare();self.native.fail_release=True
        with self.assertRaises(NativeUIError):self.final.release()
        self.assertEqual('release-issued',self.final.state['phase']);self.native.fail_release=False
        result=self.owner().reconcile();self.assertEqual('released',result['phase'])
        self.assertEqual(1,sum(command['action'].endswith('release') for command in self.native.evidence_commands))
    def test_controller_intent_never_reenters_native_guard_or_query(self):
        self.release();original=self.native.session.stage;parent=self.capture.parent
        def staged(*args,**kwargs):
            intent=kwargs['intent']
            def pure(value):
                with patch.object(parent,'now',side_effect=AssertionError('Native guard during session intent')), \
                     patch.object(parent,'fresh',side_effect=AssertionError('Native query during session intent')), \
                     patch.object(self.fixture.source,'status',side_effect=AssertionError('HTTP during session intent')), \
                     patch.object(self.fixture.source,'epoch_ms',side_effect=AssertionError('Fixture clock during session intent')), \
                     patch.object(parent.settings,'guard',side_effect=AssertionError('Source guard during session intent')):
                    intent(value)
            kwargs['intent']=pure;return original(*args,**kwargs)
        with patch.object(self.native.session,'stage',side_effect=staged):self.final.stream('back-issued')
        self.assertEqual('home',self.final.state['phase'])

    def test_two_second_controller_cas_is_rejected_using_saved_anchors_only(self):
        self.release();original=self.final.save;count=len(self.native.transport.envelopes)
        def slow(state,**kwargs):
            original(state,**kwargs)
            if kwargs.get('input_intent'):self.native.clock+=2
        with patch.object(self.final,'save',side_effect=slow):
            with self.assertRaises(NativeUIError):self.final.stream('back-issued')
        self.assertEqual(count,len(self.native.transport.envelopes));self.assertIsNotNone(self.final.state['streams'][-1]['envelope'])
    def test_original_pcm_replacement_during_report_cannot_claim_retained_originals(self):
        self.release();original=self.final.report
        def replace():
            result=original();path=self.capture.store.path.with_name(self.capture.state['artifacts']['input']['name'])
            raw=path.read_bytes();path.unlink();path.write_bytes(raw);path.chmod(0o600);return result
        with patch.object(self.final,'report',side_effect=replace):
            with self.assertRaises(NativeUIError):self.final.stream('back-issued')
        self.assertTrue(self.final.store.path.exists());self.assertEqual('home',self.final.state['phase'])


class AudioFinalRetirementTests(unittest.TestCase):
    setUp=AudioFinalCloseTests.setUp
    owner=AudioFinalCloseTests.owner
    release=AudioFinalCloseTests.release
    close=AudioFinalCloseTests.close
    def test_actual_retired_callbacks_get_fresh_quiet_while_new_capacity_remains_owned(self):
        self.close();self.native.retained_capacity=65536;original=self.native.sleep
        def publish(seconds):
            original(seconds)
            if self.native.cycle not in self.native.callback_events:self.native.complete_callback()
        self.capture.parent.settings.sleep=publish;result=self.final.await_deferred()
        self.assertTrue(result['nativeDeferredFunctorsRetired']);self.assertFalse(result['nativeResourceMatchesBaseline'])
        self.assertTrue(result['contextAlive']);self.assertFalse(result['fullAudioQualified']);self.assertTrue(result['journalsRetained'])
        self.assertTrue(result['originalQuietWindows'][-1]['deferred']);self.assertEqual(3,len(self.native.transport.envelopes))
    def test_elapsed_due_time_and_empty_taps_do_not_retire_unpublished_callback(self):
        self.close();self.native.sleep(60);count=len(self.native.transport.envelopes)
        with self.assertRaises(NativeUIError):self.final.await_deferred()
        self.assertFalse(self.final.report()['nativeDeferredFunctorsRetired']);self.assertTrue(self.final.store.path.exists())
        self.assertEqual(count,len(self.native.transport.envelopes))
    def test_changed_retained_resource_during_final_native_quiet_does_not_complete_window(self):
        self.close();self.native.complete_callback();original=self.native.sleep
        def grow(seconds):original(seconds);self.native.retained_capacity+=1024
        self.capture.parent.settings.sleep=grow
        with self.assertRaises(NativeUIError):self.final.await_deferred()
        self.assertFalse(any(window['deferred'] for window in self.final.state['quiet']))
        self.assertTrue(self.final.store.path.exists())


if __name__=='__main__':unittest.main()
