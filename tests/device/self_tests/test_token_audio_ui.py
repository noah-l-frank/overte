"""Normal Audio input recipe against an independent native-widget boundary."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from adapters.normal_ui import NativeUIError
from adapters.token_audio_ui import TokenAudioUI


class AudioBoundary:
    def __init__(self):
        self.instance, self.generation = 'a' * 32, 'b' * 32
        self.hmd, self.mode, self.cycle = False, 0, 0
        self.active, self.muted, self.echo = False, False, False
        self.phase, self.position, self.clock = 'idle', 0.0, 0.0
        self.actions, self.intents, self.fault = [], [], ''
        self.transform = lambda value: value

    def sleep(self, seconds): self.clock += seconds

    def intent(self, verb, value, identifier):
        self.intents.append((verb, identifier, self.cycle))
        if self.fault == 'intent': raise NativeUIError('Ownership journal could not be committed')

    def capture(self):
        def row(identifier, ready=True, **fields):
            key = repr((identifier, self.cycle, self.active, self.mode, self.muted, self.echo, self.position))
            return dict(id=identifier, token=hashlib.sha256(key.encode()).hexdigest()[:32],
                        enabled=True, inputReady=ready, **fields)
        matching = self.mode == int(self.hmd)
        rows = [row('audio.page',False,mode=self.mode,nativeHmd=self.hmd,uiHmd=self.hmd,cycle=self.cycle),
                row('audio.mode.desktop',not self.hmd,checked=self.mode == 0,nativeHmd=self.hmd),
                row('audio.mode.vr',self.hmd,checked=self.mode == 1,nativeHmd=self.hmd),
                row('audio.scrollbar',position=self.position,size=0.4)]
        if self.position < 0.2:
            rows.append(row('audio.mute',matching,checked=self.muted,nativeMuted=self.muted,mode=self.mode))
        if self.position >= 0.2:
            rows += [row('audio.record',matching,cycle=self.cycle,nativeActive=self.active,uiActive=self.active,
                         requested=False,phase=self.phase,label='Cancel' if self.active else 'Start'),
                     row('audio.live-echo',matching and not self.active,cycle=self.cycle,nativeActive=self.active,
                         uiActive=self.active,requested=False,checked=self.echo,nativeEcho=self.echo)]
        value = dict(audioControlsVersion=1,ready=True,instance=self.instance,generation=self.generation,controls=rows)
        return self.transform(value)

    def original(self, identifier, token):
        # This is the native boundary's independently re-resolved current item,
        # not the recipe's requested/expected result.
        row = next(row for row in self.capture()['controls'] if row['id'] == identifier)
        if token != row['token'] or not row['enabled'] or not row['inputReady']:
            raise NativeUIError('Original widget token is no longer actionable')
        assert len(self.intents) == len(self.actions) + 1

    def activate(self, identifier, *, token):
        if self.fault == 'late-cycle': self.cycle += 1
        self.original(identifier,token); self.actions.append(identifier)
        if identifier == 'audio.record':
            if self.fault == 'record': return
            if self.active:
                self.active = False
                self.phase = 'completed' if self.fault == 'natural-completion' else 'cancelled'
            else:
                self.cycle += 2 if self.fault == 'double-start' else 1
                self.active, self.phase = not self.muted, 'error' if self.muted else 'capturing'
        elif identifier == 'audio.mute':
            if self.fault != 'mute': self.muted = not self.muted
            if self.muted and self.active: self.active, self.phase = False, 'cancelled'
        elif identifier == 'audio.live-echo':
            if self.fault != 'echo': self.echo = not self.echo
        elif identifier.startswith('audio.mode.'):
            if self.fault != 'mode': self.mode = 1 if identifier.endswith('vr') else 0
        else: raise AssertionError(identifier)

    def scroll(self, identifier, direction, *, token):
        self.original(identifier,token); self.actions.append('scroll-' + direction)
        if self.fault != 'scroll': self.position = 0.0 if direction == 'up' else 0.6


class AudioUiTests(unittest.TestCase):
    def ui(self, fault=''):
        native = AudioBoundary(); native.fault = fault
        return native, TokenAudioUI(native,native.intent,monotonic=lambda: native.clock,sleep=native.sleep)

    def test_normal_start_and_cancel_use_actual_cycle_and_one_input_each(self):
        native, ui = self.ui(); observed = ui.start()
        self.assertEqual(1, observed['cycle']); self.assertTrue(observed['nativeActive'])
        cancelled = ui.cancel(observed['cycle'])
        self.assertEqual('cancelled',cancelled['phase']); self.assertFalse(native.active)
        self.assertEqual(['scroll-down','audio.record','audio.record'],native.actions)
        self.assertGreaterEqual(native.clock,0.3)

    def test_muted_start_reports_real_error_cycle_and_does_not_claim_capture(self):
        native, ui = self.ui(); ui.mute(True); observed = ui.start()
        self.assertEqual('error',observed['phase']); self.assertFalse(observed['nativeActive'])
        self.assertTrue(native.muted)

    def test_mute_unmute_and_live_echo_require_native_readback(self):
        native, ui = self.ui(); ui.mute(True); ui.mute(True); ui.mute(False)
        ui.echo(True); ui.echo(False)
        self.assertFalse(native.muted); self.assertFalse(native.echo)
        self.assertEqual(2,native.actions.count('audio.mute'))
        self.assertEqual(2,native.actions.count('audio.live-echo'))

    def test_mode_selection_targets_only_actual_current_context(self):
        native, ui = self.ui(); native.hmd = True; ui.start()
        self.assertEqual(1,native.mode); self.assertIn('audio.mode.vr',native.actions)
        self.assertNotIn('audio.mode.desktop',native.actions)

    def test_ignored_start_scroll_mode_mute_echo_fail_without_replay(self):
        for fault in ('record','scroll','mode','mute','echo'):
            with self.subTest(fault=fault):
                native, ui = self.ui(fault)
                if fault == 'mode': native.hmd = True
                with self.assertRaises(NativeUIError):
                    if fault == 'mute': ui.mute(True)
                    elif fault == 'echo': ui.echo(True)
                    else: ui.start()
                self.assertLessEqual(native.actions.count('audio.record'),1)
                self.assertLessEqual(native.actions.count('scroll-down'),1)
                self.assertLessEqual(native.clock,10.2)

    def test_ignored_cancel_and_natural_completion_do_not_prove_cancel(self):
        for fault in ('record','natural-completion'):
            with self.subTest(fault=fault):
                native, ui = self.ui(); ui.start(); native.fault = fault
                with self.assertRaises(NativeUIError): ui.cancel(1)
                self.assertEqual(2,native.actions.count('audio.record'))
                self.assertEqual(fault == 'record',native.active)

    def test_cancel_of_inactive_or_foreign_cycle_never_becomes_start(self):
        for active, cycle in ((False,1),(True,2)):
            with self.subTest(active=active,cycle=cycle):
                native, ui = self.ui(); native.position=0.6; native.cycle=1; native.active=active
                with self.assertRaises(NativeUIError): ui.cancel(cycle)
                self.assertEqual([],native.actions)

    def test_double_start_and_native_boundary_cycle_race_are_rejected(self):
        for fault in ('double-start','late-cycle'):
            with self.subTest(fault=fault):
                native, ui = self.ui(fault); native.position=0.6
                with self.assertRaises(NativeUIError): ui.start()
                self.assertLessEqual(native.actions.count('audio.record'),1)

    def test_durable_intent_failure_prevents_input(self):
        native, ui = self.ui('intent'); native.position=0.6
        with self.assertRaises(NativeUIError): ui.start()
        self.assertEqual([],native.actions); self.assertEqual(0,native.cycle)

    def test_retired_control_token_between_recipe_reads_prevents_input(self):
        native, ui = self.ui(); native.position=0.6
        row = ui.visible('audio.record'); native.cycle=1
        with self.assertRaises(NativeUIError):
            ui.activate('audio.record','record-start',token=row['token'],cycle=0)
        self.assertEqual([],native.actions)

    def test_foreign_instance_generation_hmd_and_regressed_cycle_fail(self):
        for change in ('instance','generation','hmd','cycle'):
            with self.subTest(change=change):
                native, ui = self.ui(); native.cycle=2; ui.capture()
                if change == 'cycle': native.cycle=1
                elif change == 'hmd': native.hmd=True
                else: setattr(native,change,'f' * 32)
                with self.assertRaises(NativeUIError): ui.capture()
                self.assertEqual([],native.actions)

    def test_missing_results_markers_page_duplicates_and_incoherent_metadata_fail(self):
        for fault in ('result','marker','page','duplicate','active','mode','muted','number','boolean'):
            with self.subTest(fault=fault):
                native, ui = self.ui(); native.position=0.6
                def corrupt(value):
                    if fault == 'result': return None
                    if fault == 'marker': value.pop('audioControlsVersion')
                    elif fault == 'page': value['controls']=[r for r in value['controls'] if r['id']!='audio.page']
                    elif fault == 'duplicate': value['controls'].append(deepcopy(value['controls'][0]))
                    elif fault == 'active': next(r for r in value['controls'] if r['id']=='audio.record')['uiActive']=True
                    elif fault == 'mode': value['controls'][0]['mode']=1
                    elif fault == 'muted':
                        value['controls'].append(dict(id='audio.mute',token='x',enabled=True,inputReady=True,
                            checked=True,nativeMuted=False,mode=0))
                    elif fault == 'number': next(r for r in value['controls'] if r['id']=='audio.scrollbar')['position']=float('nan')
                    elif fault == 'boolean': value['audioControlsVersion']=True
                    return value
                native.transform=corrupt
                with self.assertRaises(NativeUIError): ui.start()
                self.assertEqual([],native.actions)

    def test_missing_result_after_delivered_start_is_not_replayed(self):
        native, ui = self.ui(); native.position=0.6
        original=native.activate
        def activate(identifier,**kw):
            original(identifier,**kw); native.transform=lambda value: None
        native.activate=activate
        with self.assertRaises(NativeUIError): ui.start()
        self.assertEqual(1,native.actions.count('audio.record')); self.assertTrue(native.active)

    def test_backward_clock_and_invented_verbs_fail(self):
        native, ui = self.ui(); ui.now(); native.clock=-1
        with self.assertRaises(NativeUIError): ui.wait(lambda value: False)
        with self.assertRaises(NativeUIError): ui.activate('audio.record','save-recording')
        self.assertEqual([],native.actions)


if __name__ == '__main__': unittest.main()
