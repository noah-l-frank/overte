"""Real Audio owner/native readers with explicit independent OS/audio boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.normal_ui import NativeUIError
from adapters.pico4.audio_background_owner import PicoAudioBackground
from self_tests import test_pico_audio_capture_owner as source_fixture


class AudioBackgroundTests(unittest.TestCase):
    def setUp(self):
        self.fixture=source_fixture.AudioCaptureOwnerTests(methodName='runTest');self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.native,self.capture=self.fixture.native,self.fixture.owner;self.foreground=True;self.inputs=[];self.runtime_calls=0
        self.fault='';self.counts=deepcopy(self.native.native_reader.lifecycle)
        original=self.native.native.mutate
        def metadata(packet):original(packet);packet['lifecycle']=deepcopy(self.counts)
        self.native.native.mutate=metadata
        self.fixture.start();self.fixture.activate('background-resume');self.flow=self.owner()
    def os_status(self,binding):
        self.assertEqual(self.capture.binding,binding);return dict(binding=deepcopy(binding),running=True,foreground=self.foreground)
    def os_input(self,operation,binding):
        self.assertEqual(self.capture.binding,binding);self.inputs.append(operation)
        if operation=='lifecycle.background':
            if self.fault!='home-ack-only':
                self.foreground=False;self.native.guard_okay=False;self.counts['backgrounds']+=1
                self.native.publish('cancelled',self.native.events[-1]['capturedBytes'],error='backgrounded')
            if self.fault=='lost-home':raise NativeUIError('Explicit response lost after original HOME')
        else:
            if self.fault!='resume-ack-only':self.foreground=True;self.native.guard_okay=True;self.counts['activations']+=1
            if self.fault=='lost-resume':raise NativeUIError('Explicit response lost after original activation')
    def runtime(self):
        self.assertTrue(self.foreground);self.runtime_calls+=1;return self.fixture.capture_owner()
    def owner(self):
        return PicoAudioBackground(self.fixture.path/'audio-background-cycle-01.json',self.capture.run,self.capture.binding,self.capture.lock,
            self.os_status,self.os_input,self.runtime,monotonic=lambda:self.native.clock,sleep=self.native.sleep)
    def prepare(self):self.flow.prepare();return self.flow.home()
    def test_normal_home_return_actual_native_cancellation_and_original_three_second_quiet(self):
        self.prepare();result=self.flow.resume();self.assertTrue(result['nativeCancellationObserved'])
        result=self.flow.quiet();self.assertEqual('quiet',result['phase']);self.assertTrue(result['quiet'])
        self.assertFalse(result['hiddenEditorHistoryObserved']);self.assertFalse(result['fullAudioQualified']);self.assertTrue(result['journalsRetained'])
        self.assertEqual(['lifecycle.background','app.launch'],self.inputs);self.assertEqual(1,self.native.actions.count('audio.record'))
        self.assertEqual('backgrounded',self.flow.owner.report()['state']['error'])
    def test_lost_home_recovers_os_only_while_backgrounded_without_qt_or_second_home(self):
        self.flow.prepare();self.fault='lost-home'
        with self.assertRaises(NativeUIError):self.flow.home()
        calls=self.runtime_calls;recovered=self.owner();self.assertEqual(calls,self.runtime_calls)
        recovered.observe_background();self.assertEqual(calls,self.runtime_calls);self.fault=''
        recovered.resume();self.assertEqual(['lifecycle.background','app.launch'],self.inputs)
    def test_gap_after_partial_background_window_keeps_originals_and_resets_observed_window(self):
        self.flow.prepare();original=self.flow.os_status;calls=0
        def interrupted(binding):
            nonlocal calls
            result=original(binding)
            if not self.foreground:
                calls+=1
                if calls==2:raise NativeUIError('Explicit independent OS read interruption')
            return result
        self.flow.os_status=interrupted
        with self.assertRaises(NativeUIError):self.flow.home()
        first=deepcopy(self.flow.state['background']);self.assertEqual(1,len(first));self.native.sleep(1)
        recovered=self.owner();recovered.observe_background();self.assertEqual(first,recovered.state['background'][:1])
        self.assertEqual(1,recovered.state['backgroundFirst']);recovered.resume()
        self.assertEqual(['lifecycle.background','app.launch'],self.inputs)

    def test_cold_host_clock_regression_cannot_reuse_original_os_window(self):
        self.prepare()
        with self.assertRaises(NativeUIError):
            PicoAudioBackground(self.flow.store.path,self.capture.run,self.capture.binding,self.capture.lock,
                self.os_status,self.os_input,self.runtime,monotonic=lambda:0,sleep=self.native.sleep)
        self.assertTrue(self.flow.store.path.exists());self.assertEqual(['lifecycle.background'],self.inputs)
    def test_lost_root_write_after_read_only_return_adopts_only_original_frame_prefix(self):
        self.prepare();original=self.flow.save
        def interrupted(state):
            if state['phase']=='returned':raise NativeUIError('Explicit lost root CAS after original read-only observation')
            original(state)
        with patch.object(self.flow,'save',side_effect=interrupted):
            with self.assertRaises(NativeUIError):self.flow.resume()
        recovered=self.owner();self.assertTrue(recovered.reconcile()['nativeCancellationObserved'])
        self.assertEqual(['lifecycle.background','app.launch'],self.inputs);self.assertEqual(1,self.native.actions.count('audio.record'))

    def test_lost_resume_reads_original_native_effect_without_relaunch(self):
        self.prepare();self.fault='lost-resume'
        with self.assertRaises(NativeUIError):self.flow.resume()
        self.fault='';recovered=self.owner();self.assertTrue(recovered.reconcile()['nativeCancellationObserved'])
        self.assertEqual(['lifecycle.background','app.launch'],self.inputs)
    def test_home_ack_without_os_effect_stays_unresolved_and_is_not_repeated(self):
        self.flow.prepare();self.fault='home-ack-only'
        with self.assertRaises(NativeUIError):self.flow.home()
        with self.assertRaises(NativeUIError):self.owner().observe_background()
        self.assertEqual(['lifecycle.background'],self.inputs);self.assertEqual('home-issued',self.flow.state['phase'])
    def test_resume_ack_without_original_foreground_effect_stays_unresolved(self):
        self.prepare();self.fault='resume-ack-only'
        with self.assertRaises(NativeUIError):self.flow.resume()
        calls=self.runtime_calls
        with self.assertRaises(NativeUIError):self.owner().reconcile()
        self.assertEqual(calls,self.runtime_calls);self.assertEqual(['lifecycle.background','app.launch'],self.inputs)
    def test_foreground_status_without_native_lifecycle_and_audio_effect_does_not_pass(self):
        self.prepare();self.native.phase='capturing';self.native.active=True;self.native.events.pop();self.counts['backgrounds']-=1
        with self.assertRaises(NativeUIError):self.flow.resume()
        self.assertEqual('resume-issued',self.flow.state['phase']);self.assertEqual(1,self.native.actions.count('audio.record'))
    def test_actual_native_terminal_event_before_home_fence_remains_unresolved(self):
        self.flow.prepare();original=self.native.publish
        def stale(phase,*args,**kwargs):
            original(phase,*args,**kwargs)
            if phase=='cancelled':self.native.events[-1]['publishedEpochMs']=self.native.started()+1
        self.native.publish=stale;self.flow.home()
        with self.assertRaises(NativeUIError):self.flow.resume()
        self.assertTrue(self.flow.store.path.exists());self.assertEqual('resume-issued',self.flow.state['phase'])
    def test_extra_native_lifecycle_transition_during_quiet_fails(self):
        self.prepare();self.flow.resume();original=self.native.sleep
        def extra(seconds):original(seconds);self.counts['backgrounds']+=1;self.counts['activations']+=1
        self.flow.sleep=extra
        with self.assertRaises(NativeUIError):self.flow.quiet()
        self.assertFalse(self.flow.report()['quiet']);self.assertTrue(self.flow.store.path.exists())
    def test_final_native_clock_includes_return_report_copy(self):
        self.prepare();original=self.flow.report
        def late():result=original();self.native.clock+=2;return result
        with patch.object(self.flow,'report',side_effect=late):
            with self.assertRaises(NativeUIError):self.flow.resume()
        self.assertEqual('returned',self.flow.state['phase']);self.assertEqual(['lifecycle.background','app.launch'],self.inputs)


if __name__=='__main__':unittest.main()
