"""Retain actual half-propagated sources without promoting them to current state."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.chat_journey.samples import transition_ready
from adapters.normal_ui import NativeUIError
from self_tests import test_chat_journey_samples as source_seams
from feature_journeys.fixtures import context
from self_tests.test_native_chat_observation import RUN


class TransitionTests(unittest.TestCase):
    def setUp(self):
        self.h=source_seams.ChatSamplesTests();self.h.setUp();self.addCleanup(self.h.doCleanups)
    def read(self,index):return self.h.samples.read_transition(f'{index:032x}',20000)
    def test_half_propagation_then_joint_absence_and_fresh_recovery_keep_all_original_frames(self):
        self.read(1);self.h.primary.mixer=False;value=self.read(2)
        self.assertTrue(value['transition']);self.assertNotIn('state',value);self.assertNotIn('resources',value)
        self.assertFalse(transition_ready(self.h.samples));self.assertEqual('ready',self.h.store.read()['phase'])
        self.h.peer.mixer=False;self.read(3);self.assertTrue(transition_ready(self.h.samples))
        # Qualification cannot emit a cached state. A new complete acquisition
        # has its own original queries and remains the only current state path.
        queries=[self.h.samples.frames[-1][key].get('commandId',self.h.samples.frames[-1][key].get('requestId')) for key in ('primary','peer','view','lifecycle')]
        full=self.h.samples.read('f'*32,20000);self.assertFalse(full['state']['mixerConnected'])
        self.assertFalse(set(queries)&{self.h.samples.frames[-1][key].get('commandId',self.h.samples.frames[-1][key].get('requestId')) for key in ('primary','peer','view','lifecycle')})
        self.h.peer_mixer='f'*64;self.h.primary.mutate=lambda v:v['source'].update(mixerSha256='f'*64 if self.h.primary.mixer else '')
        self.h.primary.mixer=True;self.read(4);self.assertFalse(transition_ready(self.h.samples))
        self.h.peer.mixer=True;self.read(5);self.assertTrue(transition_ready(self.h.samples))
        self.assertEqual(6,len(self.h.samples.frames))
    def test_async_original_qml_lag_is_recorded_and_requires_new_full_read_after_it_catches_up(self):
        self.h.open('domain');self.read(1)
        self.h.primary.event(text=context(RUN)['reply']);storage=self.h.view.source['storage']
        storage.update(kind='array',count=1,events=[dict(channel='domain',text=context(RUN)['reply'],timestamp=20000)])
        self.read(2);self.assertFalse(transition_ready(self.h.samples));self.assertNotIn('state',self.read(3))
        self.h.open('domain');self.read(4);self.assertTrue(transition_ready(self.h.samples))
        self.assertEqual([context(RUN)['reply']],self.h.samples.read('e'*32,20000)['state']['domainMessages'])
    def test_final_durable_source_write_guard_cannot_hide_native_clock_jump_with_frozen_host(self):
        delta=0;original=self.h.samples._write
        def written(value):
            nonlocal delta
            original(value)
            if value['phase']=='ready':delta=2000
        self.h.samples._write=written
        self.h.samples.primary.clock_ms=lambda:20000+delta
        with self.assertRaises(NativeUIError):self.read(1)
        self.assertEqual(0,self.h.clock);self.assertEqual('ready',self.h.store.read()['phase'])
        # The original actual frame remains preserved but was never returned as
        # a fresh current verdict. No old sample is retimed or erased.
        self.assertEqual(1,len(self.h.samples.frames))

    def test_old_mixer_reappearance_and_hidden_storage_shrink_still_fail_and_retain_intent(self):
        self.read(1);self.h.primary.mixer=self.h.peer.mixer=False;self.read(2)
        self.h.primary.mixer=True
        with self.assertRaises(NativeUIError):self.read(3)
        self.assertEqual('reading',self.h.store.read()['phase'])
        self.setUp();self.h.accept(context(RUN)['reply']);self.read(1)
        self.h.view.source['storage'].update(kind='null',count=0,events=[])
        with self.assertRaises(NativeUIError):self.read(2)
        self.assertEqual('reading',self.h.store.read()['phase'])


if __name__=='__main__':unittest.main()
