"""Private normal calibration over real files/HTTP and synthetic iOS SDKs."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from unittest.mock import patch

from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack,unpack
from ios.adapters.graphics_calibration import IOSGraphicsCalibration
from ios.self_tests.test_ios_graphics_observer import CurrentObserverHarness
from ios.self_tests.test_ios_graphics_scene import RUN,TICKET
from ios.self_tests.test_ios_graphics_restart import RestartHarness


class CalibrationHarness(CurrentObserverHarness):
    def calibration(self,role='primary'):
        observer=self.observer(role)
        return IOSGraphicsCalibration(self.preferences(),observer.source),observer
    def begin(self):
        self.original_true();calibration,_observer=self.calibration();calibration.begin(0)
        self.assertFalse(calibration.advance_primary());return calibration
    def captures(self):
        refs={}
        for role in ('primary','actor'):
            calibration,observer=self.calibration(role);refs[role]=calibration.capture(observer)
        return refs


class CalibrationTests(CalibrationHarness,unittest.TestCase):
    def test_closed_original_round_restores_actual_preferences_after_both_independent_originals(self):
        with self.lock.held():
            calibration=self.begin();self.assertFalse(self.sdk.model.haze);self.assertFalse(self.sdk.model.mirrors)
            self.assertEqual(TICKET,self.client.request('/runs/'+RUN+'/active')['ticket'])
            refs=self.captures();self.assertNotEqual(refs['primary'],refs['actor'])
            calibration,_observer=self.calibration();self.assertTrue(calibration.advance_primary())
            self.assertTrue(self.sdk.model.haze);self.assertTrue(self.sdk.model.mirrors)
            self.assertEqual('closed',self.sdk.stage);self.assertEqual('complete',calibration.state['rounds'][-1]['phase'])
            for role in ('primary','actor'):
                observer=self.observer(role);self.assertEqual(0,observer.state['sequence']);self.assertIsNone(observer.state['baseline'])
                value=observer.read(0,0);self.assertTrue(value['state']['haze']);self.assertTrue(value['state']['mirror'])

    def test_open_original_and_current_nonbaseline_resolution_are_preserved(self):
        with self.lock.held():
            self.original_true();self.private_action('open');self.private_action('set-resolution',dict(value=.5))
            calibration,_observer=self.calibration();row=calibration.begin(0);self.assertTrue(row['shown'])
            calibration.advance_primary();self.captures();calibration,_observer=self.calibration();calibration.advance_primary()
            self.assertEqual('graphics',self.sdk.stage);self.assertEqual(.5,self.sdk.model.resolution)
            self.assertTrue(self.sdk.model.haze);self.assertTrue(self.sdk.model.mirrors)
            self.assertEqual(TICKET,self.client.request('/runs/'+RUN+'/active')['ticket'])

    def test_one_role_cannot_release_the_calibration_barrier_or_create_a_public_sample(self):
        with self.lock.held():
            self.begin();calibration,observer=self.calibration();calibration.capture(observer)
            calibration,_observer=self.calibration();self.assertFalse(calibration.advance_primary())
            self.assertEqual('off',calibration.state['rounds'][-1]['phase']);self.assertEqual(0,observer.state['sequence'])
            self.assertEqual([],self.client.observe()['entries']);self.assertFalse(self.sdk.model.haze)

    def test_lost_seed_return_adopts_committed_original_without_repeating_gpu_capture(self):
        with self.lock.held():
            self.begin();calibration,observer=self.calibration();original=observer.seed_off
            def lost(*args):
                original(*args);raise OSError('Synthetic lost committed private seed return')
            with patch.object(observer,'seed_off',side_effect=lost),self.assertRaises(OSError):calibration.capture(observer)
            count=sum(c['operation']=='read' for c in self.gpu.commands)
            calibration,observer=self.calibration();refs=calibration.capture(observer)
            self.assertEqual(count,sum(c['operation']=='read' for c in self.gpu.commands))
            self.assertEqual(refs,observer.state['offFrames']);self.assertEqual('observed',calibration.state['rounds'][-1]['roles']['primary']['phase'])

    def test_lost_input_return_recovers_by_reading_the_original_issued_control(self):
        with self.lock.held():
            self.original_true();self.private_action('open');calibration,_observer=self.calibration();calibration.begin(0)
            original=calibration.preferences.deliver_step
            def lost(*args):
                original(*args);raise NativeUIError('Synthetic lost ordinary toggle return')
            with patch.object(calibration.preferences,'deliver_step',side_effect=lost),self.assertRaises(NativeUIError):calibration.advance_primary()
            count=self.sdk.model.actions.count('graphics.haze')
            calibration,_observer=self.calibration();self.assertFalse(calibration.advance_primary())
            self.assertEqual(count,self.sdk.model.actions.count('graphics.haze'));self.assertFalse(self.sdk.model.haze)

    def test_lost_native_capture_stays_unresolved_without_automatic_resend(self):
        with self.lock.held():
            self.begin();self.gpu.lost=True;calibration,observer=self.calibration()
            with self.assertRaises(NativeUIError):calibration.capture(observer)
            count=sum(c['operation']=='read' for c in self.gpu.commands)
            calibration,observer=self.calibration()
            with self.assertRaises(NativeUIError):calibration.capture(observer)
            self.assertEqual(count,sum(c['operation']=='read' for c in self.gpu.commands))
            self.assertEqual('capturing',calibration.state['rounds'][-1]['roles']['primary']['phase'])

    def test_changed_phase_cannot_restore_or_capture_under_the_new_ticket(self):
        with self.lock.held():
            self.begin();self.client.activate('f'*32,'cleanup',{});self.gpu.marker='f'*32
            calibration,observer=self.calibration();count=len(self.gpu.commands)
            with self.assertRaises(NativeUIError):calibration.capture(observer)
            with self.assertRaises(NativeUIError):calibration.advance_primary()
            self.assertEqual(count,len(self.gpu.commands));self.assertEqual(0,observer.state['sequence'])
            self.preferences().cleanup();self.assertTrue(self.sdk.model.haze);self.assertTrue(self.sdk.model.mirrors)

    def test_foreign_role_reference_and_changed_original_settings_are_rejected(self):
        with self.lock.held():
            self.begin();refs=self.captures();calibration,actor=self.calibration('actor')
            with self.assertRaises(NativeUIError):calibration.verify_refs(calibration.state['rounds'][-1],actor,refs['primary'])
            changed=deepcopy(calibration.previous);state=unpack(changed['payload'])[0]
            state['rounds'][-1]['native']['graphics']['hazeSetting']=False;changed['payload']=pack([state])
            calibration.store.write(changed,calibration.previous)
            with self.assertRaises(NativeUIError):self.calibration()

    def test_failed_round_intent_persistence_prevents_all_normal_input(self):
        with self.lock.held():
            self.original_true();calibration,_observer=self.calibration();before=list(self.sdk.model.actions)
            with patch.object(calibration.store,'write',side_effect=OSError('Synthetic failed round intent')),self.assertRaises(OSError):calibration.begin(0)
            self.assertEqual(before,self.sdk.model.actions);self.assertTrue(self.sdk.model.haze)


class CalibrationRestartTests(CalibrationHarness,RestartHarness,unittest.TestCase):
    def test_completed_old_round_requires_real_restart_handoff_before_new_process_calibration(self):
        with self.lock.held():
            self.begin();self.captures();calibration,_observer=self.calibration();calibration.advance_primary()
            self.observer().read(0,0);self.observer('actor').read(0,0)
            controller=RestartHarness.prepare(self);self.gpu.marker='8'*32
            self.observer().read(0,0);self.observer('actor').read(0,0)
            controller.act(RestartHarness.call(self))
            self.observer().read(0,1);self.observer('actor').read(0,1)
            calibration,_observer=self.calibration();calibration.begin(1);calibration.advance_primary();self.captures()
            calibration,_observer=self.calibration();self.assertTrue(calibration.advance_primary())
            self.assertEqual([0,1],[r['stage'] for r in calibration.state['rounds']])
            self.assertEqual(['42','43'],[r['binding']['processIdentity'] for r in calibration.state['rounds']])
            self.assertTrue(self.sdk.model.haze);self.assertEqual(['app.stop','app.launch'],self.inputs)


if __name__=='__main__':unittest.main()
