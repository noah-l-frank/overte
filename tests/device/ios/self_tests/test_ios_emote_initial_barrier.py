"""First direct action binds only a still idle same-phase original baseline."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters.emote_observer import IOSEmoteObserver
from ios.self_tests.emote_active_observer_fixture import ActiveObserverFixture


class InitialBarrierTests(unittest.TestCase):
    def fixture(self):
        f=ActiveObserverFixture(self);f.observer.observe(0);return f

    def read(self,f):f.sources.read();return f.observer.source_reference()

    def test_genuine_later_same_ticket_idle_original_keeps_baseline_image_and_all_original_clocks(self):
        f=self.fixture();reference=self.read(f);original=deepcopy(f.observer.decoder.source(reference))
        f.observer.begin_initial_input(reference)
        self.assertEqual(reference,f.observer.state['phaseBarrier']);self.assertEqual(f.observer.state['lastImage'],f.observer.state['imageBarrier'])
        self.assertEqual(original,f.observer.decoder.source(reference))
        with self.assertRaises(NativeUIError):f.observer.begin_initial_input(reference)

    def test_old_reference_and_new_actual_phase_cannot_replace_initial_baseline(self):
        f=self.fixture()
        with self.assertRaises(NativeUIError):f.observer.begin_initial_input(f.observer.state['baseline'])
        f.activate('open');reference=self.read(f)
        with self.assertRaises(NativeUIError):f.observer.begin_initial_input(reference)
        self.assertIsNone(f.observer.state['phaseBarrier'])

    def test_actual_override_then_restore_before_admission_is_rejected_live_and_after_reconstruction(self):
        f=self.fixture();f.native.tablet=True;f.ui.open();f.ui.play('Waving');f.native.sleep(.2);f.ui.cancel()
        reference=self.read(f);self.assertFalse(f.rig.value['animation']['overrideActive'])
        with self.assertRaises(NativeUIError):f.observer.begin_initial_input(reference)
        previous=f.observer.previous
        for ticket in (f.observer.state['phaseTicket'],'0'*32):
            state=deepcopy(f.observer.state);state.update(phaseBarrier=reference,phaseTicket=ticket)
            value=f.observer.envelope(state);f.observer.store.write(value,previous)
            with self.subTest(ticket=ticket),self.assertRaises(NativeUIError):
                IOSEmoteObserver(f.observer.store,f.sources,f.observer.binding,'primary',f.root,f.policy,f.phase,f.lock,lambda:True,
                    samples=f.samples,epoch_ms=f.scope.epoch_ms,monotonic=f.scope.monotonic)
            f.observer.store.write(previous,value)


if __name__=='__main__':unittest.main()
