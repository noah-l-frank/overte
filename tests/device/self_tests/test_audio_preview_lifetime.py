"""Original native callback/timer metadata boundaries, never requested effects."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters import audio_preview_lifetime as lifetime
from adapters.native_feature_observation import need
from adapters.normal_ui import NativeUIError
from self_tests.test_pico_audio_settings_source import Boundary,RUN


def sample(cycle=0):
    return dict(audioPreviewLifetimeVersion=1,deferred=dict(complete=True,receiverId='8'*32,
        callbacks=[dict(id=f'{index:032x}',cycle=index,registeredEpochMs=19000,scheduledDelayMs=30000,
            enteredEpochMs=0,completedEpochMs=0,retiredEpochMs=0,receiverAlive=True,active=False,retired=False) for index in range(1,cycle+1)]),
        previewTimer=dict(created=False,id='',createdEpochMs=0,alive=False,active=False),pendingLoopbackBytes=0,pendingLoopbackCapacityBytes=0,
        loopbackDeviceAssigned=False,retainedPreviewBytes=0,previewBufferCapacityBytes=0,previewTapStateEmpty=True)


class AudioPreviewLifetimeTests(unittest.TestCase):
    def test_original_pending_callback_cannot_be_retired_by_empty_pcm_receiver_death_or_passing_due_time(self):
        origin=sample();value=sample(1);lifetime.validate(value,20000,1)
        self.assertFalse(lifetime.deferred_retired(value));self.assertFalse(lifetime.restored(value,origin))
        lifetime.validate(value,90000,1);self.assertFalse(lifetime.deferred_retired(value))
        value['deferred']['callbacks'][0]['receiverAlive']=False
        lifetime.validate(value,90000,1);self.assertFalse(lifetime.deferred_retired(value))
        value['deferred']['callbacks'][0].update(enteredEpochMs=49000,completedEpochMs=49001,retiredEpochMs=49002,retired=True)
        lifetime.validate(value,50000,1);self.assertTrue(lifetime.restored(value,origin))
    def test_missing_original_callback_fake_flag_bad_clock_or_size_only_release_fails(self):
        faults=(lambda v:v['deferred'].update(callbacks=[]),lambda v:v['deferred'].update(complete=False),
            lambda v:v['deferred']['callbacks'][0].update(retired=True),lambda v:v['deferred']['callbacks'][0].update(enteredEpochMs=18000),
            lambda v:v['deferred']['callbacks'][0].update(active=True),lambda v:v.update(previewBufferCapacityBytes=True),
            lambda v:v['previewTimer'].update(active=True),lambda v:v['deferred']['callbacks'][0].update(expectedRetirement=True))
        for fault in faults:
            value=sample(1);fault(value)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):lifetime.validate(value,50000,1)
        original=sample();value=sample();value['previewBufferCapacityBytes']=65536
        lifetime.validate(value,50000,0);self.assertFalse(lifetime.restored(value,original))
    def test_original_event_times_ids_and_timer_lifetimes_never_rewrite_or_revive(self):
        old=sample(1);old['deferred']['callbacks'][0].update(enteredEpochMs=49000,completedEpochMs=49001,retiredEpochMs=49002,retired=True)
        old['previewTimer'].update(created=True,id='7'*32,createdEpochMs=20000,alive=False,active=False)
        faults=(lambda v:v['deferred'].update(receiverId='f'*32),lambda v:v['deferred'].update(callbacks=[]),
            lambda v:v['deferred']['callbacks'][0].update(registeredEpochMs=18000),lambda v:v['deferred']['callbacks'][0].update(retired=False,retiredEpochMs=0),
            lambda v:v['deferred']['callbacks'][0].update(enteredEpochMs=49001),lambda v:v['previewTimer'].update(id='f'*32),
            lambda v:v['previewTimer'].update(alive=True),lambda v:v['previewTimer'].update(created=False,id='',createdEpochMs=0))
        for fault in faults:
            value=deepcopy(old);fault(value)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):lifetime.accept(old,value)
    def test_v2_native_source_reads_originals_and_legacy_v1_cannot_be_adopted_as_lifetime_source(self):
        native=Boundary();reader=native.reader();old=reader.capture(RUN)
        def upgrade(value):value.update(audioSettingsVersion=2);value['source']['previewLifetime']=sample()
        native.mutate=upgrade
        with self.assertRaises(NativeUIError):reader.capture(RUN)
        self.assertEqual(old,reader.previous)
        reader=native.reader();value=reader.capture(RUN);self.assertEqual(2,value['audioSettingsVersion'])
        native.mutate=lambda value:(upgrade(value),value['source']['native'].update(previewCycle=1))
        with self.assertRaises(NativeUIError):reader.capture(RUN)
        self.assertEqual(value,reader.previous)


if __name__=='__main__':unittest.main()
