"""Composed Emote owners; explicit existing Qt/Rig/VM/OpenXR/time models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from adapters.normal_ui import NativeUIError
from adapters.pico4.emote_inputs import PicoEmoteInputs
from adapters.pico4.emote_lifetime import PicoEmoteLifetime
from adapters.pico4.emote_native_cycle import create, UNRESOLVED_HOST_FILES
from adapters.pico4.lifecycle_process_file import LifecycleProcessFile
from adapters.pico4.emote_native_cycle_state import cycle_store, native_cycle_owned
from self_tests.test_pico_emote_effects import EffectsBoundary
from self_tests.test_pico_emote_lifetime import LifetimeBoundary
from self_tests.test_pico_emote_sources import RUN


class CycleBoundary(EffectsBoundary):
    """Reuse original source/input and work producer fixtures, no device service."""
    reader = LifetimeBoundary.reader
    work_send = LifetimeBoundary.work_send
    sleep = LifetimeBoundary.sleep

    def __init__(self):
        super().__init__(); self.s.widget.tablet = False
        # LifetimeBoundary's constructor deliberately enters cleanup. This cycle
        # instead retains the original baseline and reaches cleanup via normal calls.
        self.work_sequence = 0; self.work_value = None; self.work_commands = []; self.work_factories = 0
        self.work_fault = self.busy = None; self.clear_after = 0
        self.signal_calls = self.timer_calls = self.registrations = 1
        self.adapter = SimpleNamespace(_emote_input_store=lambda _target:self.input.store,
            _emote_sources=self.sources, _emote_inputs=self.inputs, _emote_lifetime=self.lifetime)
        self.hosts = []

    def sources(self, _target, phase, role, root, lock):
        assert phase is self.s.phase and role == 'primary' and root == self.s.root and lock is self.s.lock
        return self.s.owner()

    def inputs(self, _target, source):
        seam = self.input; seam.source = source
        seam.owner = PicoEmoteInputs(source, seam.store, seam.controls, seam.tablet,
            seam.session, controller=lambda:seam.controller_session)
        return seam.owner

    def lifetime(self, _target, source): return PicoEmoteLifetime(source, self.reader)

    def owner(self):
        value = create(self.adapter, 'explicit-model', self.s.phase, self.s.root, self.s.lock)
        self.hosts.append(value); return value

    def close(self):
        try:
            for value in self.hosts:
                if not value.close_host(): raise AssertionError('Original host descriptors remain unresolved')
        finally: super().close()

    def normal(self, owner):
        owner.baseline()
        values = []
        for verb, inputs in (('open', {}), ('play', {'name':'Waving'}), ('cancel', {}), ('close', {})):
            values.append(owner.act(self.input.call(verb, inputs)))
        return values


class NativeCycleTests(unittest.TestCase):
    def setUp(self): self.model = CycleBoundary(); self.addCleanup(self.model.close)

    def test_normal_parent_joins_actual_play_early_restore_neutral_and_three_second_work_quiet(self):
        m = self.model
        with m.s.lock.held():
            owner = m.owner(); values = m.normal(owner)
            self.assertEqual(['idle','playback','restoration','restoration'], [value['kind'] for value in values])
            self.assertTrue(values[2]['state']['restoredBeforeNominalEnd'])
            m.s.journal.activate(RUN, 'f'*32, 'cleanup')
            before = (list(m.input.inputs), list(m.input.controllers))
            result = owner.cleanup(sleep=m.sleep)
            self.assertGreaterEqual(result['nativeQuiet']['window']['elapsedMs'], 3000)
            self.assertEqual(before, (m.input.inputs, m.input.controllers))
            self.assertFalse(result['wholeFeatureComplete']); self.assertFalse(result['stereoQualified'])
            self.assertFalse(result['independentActorQualified']); self.assertTrue(result['originalsRetained'])
            self.assertTrue(native_cycle_owned(m.adapter, 'explicit-model'))
            self.assertIsNotNone(owner.inputs.store.read()); self.assertIsNotNone(owner.lifetime.store.read())
            calls = list(m.s.calls); commands = list(m.work_commands)
            cold = m.owner(); self.assertEqual(owner.state, cold.state)
            self.assertEqual(calls, m.s.calls); self.assertEqual(commands, m.work_commands)

    def test_parent_input_intent_is_durable_before_each_original_controller_and_qt_delivery(self):
        m = self.model; observed = []
        store = cycle_store(m.adapter, 'explicit-model')
        def require_intent(kind):
            value = store.read()['state']
            self.assertEqual('input-issued', value['phase'])
            self.assertIsNone(value['steps'][-1]['frame'])
            self.assertEqual(m.input.owner.state['current']['call'], value['steps'][-1]['call'])
            observed.append(kind)
        controller = m.input.tablet.navigation.controller
        def native_control(*args, **kwargs): require_intent('controller'); return controller(*args, **kwargs)
        qt = m.input.original.navigation.input
        def native_qt(*args, **kwargs): require_intent('qt'); return qt(*args, **kwargs)
        m.input.tablet.navigation.controller = native_control; m.input.original.navigation.input = native_qt
        with m.s.lock.held():
            owner = m.owner(); m.normal(owner)
            self.assertEqual(2, observed.count('controller')); self.assertGreaterEqual(observed.count('qt'), 4)

    def test_ignored_play_keeps_issued_parent_and_never_replays_even_after_cold_reopen(self):
        m = self.model
        with m.s.lock.held():
            owner = m.owner(); owner.baseline(); owner.act(m.input.call('open'))
            m.ignore = True; call = m.input.call('play', {'name':'Waving'})
            with self.assertRaises(NativeUIError): owner.act(call)
            self.assertEqual('input-issued', owner.store.read()['state']['phase'])
            before = (list(m.input.inputs), list(m.input.controllers), list(m.s.calls))
            cold = m.owner()
            with self.assertRaises(NativeUIError): cold.act(call)
            with self.assertRaises(NativeUIError): cold.cleanup(sleep=m.sleep)
            self.assertEqual(before, (m.input.inputs, m.input.controllers, m.s.calls))

    def test_lost_normal_reply_retains_original_delivery_and_zero_resend(self):
        m = self.model
        with m.s.lock.held():
            owner = m.owner(); owner.baseline(); m.input.fault = 'lost-controller-reply'
            call = m.input.call('open')
            with self.assertRaises(NativeUIError): owner.act(call)
            self.assertEqual(1, len(m.input.transport.envelopes))
            before = (list(m.input.controllers), list(m.s.calls))
            cold = m.owner()
            with self.assertRaises(NativeUIError): cold.act(call)
            self.assertEqual(before, (m.input.controllers, m.s.calls))
            self.assertEqual('input-issued', cold.state['phase'])

    def test_foreign_run_or_ticket_cannot_create_parent_input_intent(self):
        m = self.model
        with m.s.lock.held():
            owner = m.owner(); owner.baseline(); call = m.input.call('open')
            for key, value in (('runId', 'a'*32), ('ticket', 'b'*32)):
                altered = deepcopy(call); altered[key] = value
                before = (owner.store.path.read_bytes(), list(m.input.inputs), list(m.input.controllers))
                with self.assertRaises((ValueError, NativeUIError)): owner.act(altered)
                self.assertEqual(before, (owner.store.path.read_bytes(), m.input.inputs, m.input.controllers))

    def test_original_deadline_expires_without_any_normal_delivery_or_renewal(self):
        m = self.model
        with m.s.lock.held():
            owner = m.owner(); owner.baseline(); call = m.input.call('open')
            original = owner.store.path.read_bytes(); m.tick(120001)
            before = list(m.s.calls)
            with self.assertRaises(NativeUIError): owner.act(call)
            self.assertEqual(before, m.s.calls); self.assertEqual([], m.input.controllers)
            self.assertEqual(original, owner.store.path.read_bytes())
            with self.assertRaises(NativeUIError): m.owner()

    def test_final_pre_delegate_guard_expiry_keeps_intent_and_sends_zero_inputs(self):
        m = self.model
        with m.s.lock.held():
            owner = m.owner(); owner.baseline(); call = m.input.call('open')
            original_guard = owner.source.guard; expired = []
            def delayed_guard():
                original_guard()
                state = owner.store.read()
                if state['state']['phase'] == 'input-issued' and not expired:
                    expired.append(True); m.tick(120001)
                return True
            owner.source.guard = delayed_guard
            with self.assertRaises(NativeUIError): owner.act(call)
            self.assertEqual([True], expired); self.assertEqual([], m.input.inputs)
            self.assertEqual([], m.input.controllers); self.assertIsNone(m.input.store.read())
            self.assertEqual('input-issued', owner.store.read()['state']['phase'])

    def test_identical_parent_file_replacement_cannot_authorize_delivery(self):
        m = self.model
        with m.s.lock.held():
            owner = m.owner(); owner.baseline(); call = m.input.call('open')
            raw = owner.store.path.read_bytes(); replacement = owner.store.path.with_name('owned-test-replacement')
            replacement.write_bytes(raw); replacement.chmod(0o600); os.replace(replacement, owner.store.path)
            before = list(m.s.calls)
            with self.assertRaises(NativeUIError): owner.act(call)
            self.assertEqual(before, m.s.calls); self.assertEqual([], m.input.controllers)
            self.assertEqual(raw, owner.store.path.read_bytes())

    def test_expiry_inside_original_openxr_staging_refuses_final_publish_without_resend(self):
        m = self.model
        with m.s.lock.held():
            owner = m.owner(); owner.baseline(); call = m.input.call('open')
            stage = m.input.transport.stage; delayed = []
            def original_stage(envelope, profile, *, before_publish=None):
                delayed.append(deepcopy(envelope)); m.tick(120001)
                return stage(envelope, profile, before_publish=before_publish)
            m.input.transport.stage = original_stage
            with self.assertRaises((NativeUIError, RuntimeError)): owner.act(call)
            self.assertEqual(1, len(delayed)); self.assertEqual([], m.input.transport.envelopes)
            self.assertEqual([], m.input.controllers); self.assertEqual([], m.input.inputs)
            self.assertEqual('input-issued', owner.store.read()['state']['phase'])

    def test_expiry_inside_original_qt_before_send_refuses_control_delivery(self):
        m = self.model
        with m.s.lock.held():
            owner = m.owner(); owner.baseline(); owner.act(m.input.call('open'))
            call = m.input.call('play', {'name':'Waving'}); delivery = m.input.original.navigation.input
            before = list(m.input.inputs); delayed = []
            def original_qt(*args, **kwargs):
                delayed.append(True); m.tick(120001)
                return delivery(*args, **kwargs)
            m.input.original.navigation.input = original_qt
            with self.assertRaises(NativeUIError): owner.act(call)
            self.assertEqual([True], delayed); self.assertEqual(before, m.input.inputs)
            self.assertIsNone(m.actual); self.assertEqual('input-issued', owner.store.read()['state']['phase'])

    def test_cleanup_ticket_cannot_cancel_active_override_or_skip_normal_close(self):
        m = self.model
        with m.s.lock.held():
            owner = m.owner(); owner.baseline(); owner.act(m.input.call('open'))
            owner.act(m.input.call('play', {'name':'Waving'}))
            m.s.journal.activate(RUN, 'f'*32, 'cleanup')
            before = (list(m.s.calls), list(m.input.inputs), list(m.input.controllers))
            with self.assertRaises(NativeUIError): owner.cleanup(sleep=m.sleep)
            self.assertEqual(before, (m.s.calls, m.input.inputs, m.input.controllers)); self.assertEqual('Waving', m.actual)

    def test_actual_live_timer_prevents_retirement_and_cold_cleanup_cannot_restart_window(self):
        m = self.model
        with m.s.lock.held():
            owner = m.owner(); m.normal(owner); m.busy = 'timer'
            m.s.journal.activate(RUN, 'f'*32, 'cleanup')
            before = (list(m.input.inputs), list(m.input.controllers))
            with self.assertRaises(NativeUIError): owner.cleanup(sleep=m.sleep)
            self.assertEqual(before, (m.input.inputs, m.input.controllers))
            self.assertEqual('cleanup-issued', owner.store.read()['state']['phase'])
            self.assertIsNone(owner.lifetime.state['window']); self.assertGreater(len(m.work_commands), 1)
            calls = (list(m.s.calls), list(m.work_commands)); cold = m.owner()
            with self.assertRaises(NativeUIError): cold.cleanup(sleep=m.sleep)
            self.assertEqual(calls, (m.s.calls, m.work_commands))

    def test_missing_root_does_not_adopt_or_delete_actual_prepared_or_child_original(self):
        m = self.model; store = cycle_store(m.adapter, 'explicit-model')
        for suffix in ('.pending-original', '.frame-000.json', '.child-original'):
            with self.subTest(suffix=suffix), m.s.lock.held():
                orphan = store.path.with_name(store.path.name + suffix)
                orphan.write_bytes(b'original owned intent\n'); orphan.chmod(0o600)
                self.assertTrue(native_cycle_owned(m.adapter, 'explicit-model')); before = list(m.s.calls)
                with self.assertRaises(NativeUIError): m.owner()
                self.assertFalse(store.path.exists()); self.assertEqual(before, m.s.calls)
                self.assertEqual(b'original owned intent\n', orphan.read_bytes())
                orphan.unlink()  # Test-created artifact only, never an implementation retirement.

    def test_partial_constructor_refusal_closes_only_verified_original_parent_pair(self):
        m = self.model; owners = []; original = LifecycleProcessFile.parent_guard
        def refuse_after_open(file):
            original(file); owners.append(file)
            raise NativeUIError('Explicit refusal after the actual parent pair was acquired')
        with m.s.lock.held(), patch.object(LifecycleProcessFile, 'parent_guard', refuse_after_open):
            with self.assertRaises(NativeUIError): m.owner()
        self.assertEqual(1, len(owners)); self.assertTrue(owners[0].parent.closed)
        self.assertEqual(-1, owners[0].parent.fd); self.assertEqual(-1, owners[0].parent.anchor)
        self.assertEqual([], m.s.calls); self.assertEqual([], m.input.inputs)

    def test_uncertain_constructor_parent_pair_retains_actual_foreign_fd_without_force_close(self):
        m = self.model; owners = []; original = LifecycleProcessFile.parent_guard
        foreign = m.s.root / 'owned-test-foreign-file'; foreign.write_bytes(b'foreign descriptor remains owned\n')
        foreign.chmod(0o600)
        def refuse_after_recycling(file):
            original(file); owners.append(file)
            descriptor = file.parent.fd; os.close(descriptor)
            replacement = os.open(foreign, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
            if replacement != descriptor:
                os.dup2(replacement, descriptor); os.close(replacement)
            raise NativeUIError('Actual descriptor number was recycled after original admission')
        with m.s.lock.held(), patch.object(LifecycleProcessFile, 'parent_guard', refuse_after_recycling):
            with self.assertRaises(NativeUIError): m.owner()
        self.assertEqual(1, len(owners)); file = owners[0]
        self.assertIn(file, UNRESOLVED_HOST_FILES); self.assertTrue(file.parent.lost)
        self.assertFalse(file.parent.closed)
        self.assertEqual(b'foreign descriptor remains owned\n', os.pread(file.parent.fd, 100, 0))
        self.assertNotEqual(os.fstat(file.parent.fd).st_ino, os.fstat(file.parent.anchor).st_ino)
        self.assertEqual([], m.s.calls); self.assertEqual([], m.input.inputs)
        # Deliberately retain both uncertain handles through host finalization.


if __name__ == '__main__': unittest.main()
