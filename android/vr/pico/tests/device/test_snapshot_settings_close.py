"""Closed raw-settings checkpoint with actual new-run source/parent journals.

The existing baseline boundary runs the actual normal first input/factories.
Closed UI/frame/neutral bookends are explicit producer seams here; ordinary
Mode/Format/Close input is separately exercised by snapshot-close-owner.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[5]))
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))
from adapters.normal_ui import NativeUIError
from adapters.pico4.snapshot_close_owner import PicoSnapshotCloseOwner
from adapters.pico4.snapshot_settings_close import PicoSnapshotSettingsClose
from test_snapshot_settings_baseline import BaselineBoundary


class ClosedSettingsBoundary:
    def __init__(self,test):
        self.m=BaselineBoundary(test);self.lease=self.m.attach();self.m.parent.prepare();self.m.h.activate('open');self.m.parent.open()
        self.close=object.__new__(PicoSnapshotCloseOwner);self.close.base=self.m.parent
        self.close.run,self.close.binding,self.close.lock,self.close.source=self.m.parent.run,self.m.parent.binding,self.m.parent.lock,self.m.parent.source
        self.close.native=self.m.parent.native;self.close.encoding_version=2;self.close.anchor=True;self.generation='a'*32;self.samples=0;self.final_guard=lambda:None
        # These are explicit closed-original producer seams. No assertion here
        # attributes closing to the first Open transport or its acknowledgement.
        self.close.state=dict(stage='closed',source=deepcopy(self.m.h.phase.status(None)),frames=[],neutrals=[],closedGeneration=self.generation,
            controller=dict(before=-1,envelope=deepcopy(self.lease.state['envelope'])))
        self.close.load=lambda:None;self.close.bound=self.bound;self.close.observe=self.observe;self.close.neutral=lambda value,row,state:None
        self.close.fence=self.fence;self.observe()
        self.path=self.close.lock.path.with_name('snapshot-settings-close.json')
    def bound(self):
        self.close.lock.assert_held();return self.close.native.monotonic()
    def fence(self):
        self.bound();self.final_guard();return self.close.native.monotonic(),0
    def observe(self):
        self.close.anchor=True;self.samples+=1;frame=dict(base=dict(native=dict(raw=json.dumps(dict(capturedEpochMs=self.m.h.clock()))),
            ui=dict(open=False,generation=self.generation)),hostMonotonic=self.close.native.monotonic())
        self.close.state['frames'].append(frame);self.close.state['neutrals'].append(dict(frame=len(self.close.state['frames'])-1,value=dict(actual='explicit-closed-neutral-producer')))
        return frame
    def owner(self):return PicoSnapshotSettingsClose(self.close,self.path)


class SnapshotSettingsCloseTests(unittest.TestCase):
    def test_actual_preinput_original_and_current_raw_difference_are_bound_to_closed_bookends_without_restore(self):
        m=ClosedSettingsBoundary(self);m.m.dirty=True;before=deepcopy(m.lease.packet(m.lease.state['original']));inputs=len(m.m.h.h.transport.envelopes)
        result=m.close.observe_settings();self.assertTrue(result['originalPreinputBaseline']);self.assertTrue(result['originalClosedBookends'])
        self.assertFalse(result['typedSettingsMatchOriginal']);self.assertIn('previousStillSnapPath',result['entryProjectionDifferences']);self.assertTrue(result['formatCacheProjectionChanged'])
        self.assertFalse(result['settingsRestored']);self.assertFalse(result['continuousQuiet']);self.assertFalse(result['fullSnapshotRecipe'])
        self.assertEqual(before,m.lease.packet(m.lease.state['original']));self.assertEqual(inputs,len(m.m.h.h.transport.envelopes))
        header=m.path.read_bytes();queries=m.m.sequence;samples=m.samples;cold=m.owner();self.assertEqual('observed',cold.state['stage'])
        self.assertEqual(result,cold.observe());self.assertEqual(queries,m.m.sequence);self.assertEqual(samples,m.samples);self.assertEqual(header,m.path.read_bytes())
        with m.close.lock.held():
            state=deepcopy(cold.state);state['after']=deepcopy(state['before'])
            with self.assertRaises(NativeUIError):cold.validate(state)
        # The exact raw original, not a projection of thirteen JSON entries,
        # remains the admission. The key list alone is no restoration proof.
        m.close.state['frames'][cold.state['before']['index']]['base']['ui']['open']=True
        with self.assertRaises(NativeUIError):m.owner()
        self.assertTrue(m.path.exists());self.assertEqual(inputs,len(m.m.h.h.transport.envelopes))

    def test_interruption_after_original_child_cas_recovers_same_raw_answer_without_another_source_or_input(self):
        m=ClosedSettingsBoundary(self);owner=m.owner();observe=m.lease.observe
        def interrupted():observe();raise OSError('Explicit interruption after baseline observation CAS')
        with patch.object(m.lease,'observe',side_effect=interrupted),self.assertRaises(NativeUIError):owner.observe()
        self.assertEqual('read-issued',owner.state['stage']);self.assertEqual(1,len(m.lease.state['observations']));queries=m.m.sequence
        cold=m.owner();result=cold.observe();self.assertTrue(result['originalClosedBookends']);self.assertEqual(queries,m.m.sequence)
        self.assertEqual(m.lease.state['observations'][0],cold.state['settings']);self.assertEqual(1,len(m.m.h.h.transport.envelopes))
        old=m.lease.state['observations'][0];m.lease.state['observations'][0]=dict(old,sha256='f'*64)
        with self.assertRaises(NativeUIError):m.owner()

    def test_late_final_guard_native_clock_jump_and_expired_frozen_clock_reopen_preserve_unaccepted_originals(self):
        m=ClosedSettingsBoundary(self);owner=m.owner();epoch=[m.m.h.clock()]
        def changed():
            if owner.state is not None and owner.state['stage']=='observed':epoch[0]+=2000
        m.final_guard=changed
        with patch.object(m.close.native,'clock_ms',side_effect=lambda:epoch[0]),self.assertRaises(NativeUIError):owner.observe()
        self.assertEqual('observed',owner.state['stage']);self.assertEqual(1,len(m.lease.state['observations']));self.assertTrue(m.path.exists())
        queries=m.m.sequence;epoch[0]=m.m.h.clock();m.final_guard=lambda:None
        # An observed checkpoint is never silently refreshed after expiry.
        m.m.h.adb.clock+=2
        with patch.object(m.close.native,'clock_ms',return_value=epoch[0]),self.assertRaises(NativeUIError):m.owner().observe()
        self.assertEqual(queries,m.m.sequence);self.assertEqual(1,len(m.m.h.h.transport.envelopes))

    def test_slow_final_cas_with_frozen_native_clock_refuses_after_preserving_the_original(self):
        m=ClosedSettingsBoundary(self);owner=m.owner();save=owner.save;epoch=m.m.h.clock()
        def slow(state):
            save(state)
            if state['stage']=='observed':m.m.h.adb.clock+=2
        with patch.object(owner,'save',side_effect=slow),patch.object(m.close.native,'clock_ms',return_value=epoch),self.assertRaises(NativeUIError):owner.observe()
        self.assertEqual('observed',owner.state['stage']);self.assertEqual(1,len(m.lease.state['observations']));self.assertTrue(m.path.exists())
        self.assertEqual(1,len(m.m.h.h.transport.envelopes))

    def test_legacy_parent_without_original_lease_refuses_before_any_native_read(self):
        m=ClosedSettingsBoundary(self);queries=m.m.sequence;identity=m.close.base.disk['settingsBaselineOriginalSha256']
        m.close.base.disk['settingsBaselineOriginalSha256']='f'*64
        with self.assertRaises(NativeUIError):m.close.observe_settings()
        self.assertEqual(queries,m.m.sequence);m.close.base.disk['settingsBaselineOriginalSha256']=identity;m.close.base.settings_baseline=None
        with self.assertRaises(NativeUIError):m.close.observe_settings()
        self.assertEqual(queries,m.m.sequence);self.assertFalse(m.path.exists());self.assertEqual(1,len(m.m.h.h.transport.envelopes))

    def test_unissued_passive_read_requires_a_fresh_close_fence_and_recovers_without_input(self):
        m=ClosedSettingsBoundary(self);queries=m.m.sequence;owner=m.owner()
        def refused():raise NativeUIError('Explicit independent Close phase refusal')
        m.final_guard=refused
        with self.assertRaises(NativeUIError):owner.observe()
        self.assertEqual('read-issued',owner.state['stage']);self.assertEqual([],m.lease.state['observations']);self.assertEqual(queries,m.m.sequence)
        m.final_guard=lambda:None;m.close.anchor=None;samples=m.samples;cold=m.owner();result=cold.observe()
        self.assertTrue(result['originalClosedBookends']);self.assertEqual(samples+2,m.samples);self.assertEqual(queries+1,m.m.sequence)
        self.assertEqual(1,len(m.m.h.h.transport.envelopes));self.assertTrue(m.path.exists())


if __name__=='__main__':unittest.main()
