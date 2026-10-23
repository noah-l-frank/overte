"""Original normal Pico first input with a passive pre-input settings lease.

Native settings/typed serialization/VM/GUI/SDK and time are explicit producers.
The original candidate verifier, factories, PhaseFixtureReader, normal QML and
controller Session, private files and baseline/parent CAS are exercised.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[5]))
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))
import test_snapshot_cancel_owner as original
from adapters.android.adapter import ANDROID_CONTROL_COMMAND
from adapters.normal_ui import NativeUIError
from adapters.pico4.snapshot_settings_originals import ACTION,FILE,KEYS


class BaselineBoundary:
    def __init__(self,test,*,host=None,entry_source=lambda:{},manager_instance='c'*32):
        if host is None:
            host=original.SnapshotCancelOwnerTests();host.setUp();test.addCleanup(host.doCleanups)
        self.h=host
        self.sequence=0;self.packet=None;self.dirty=False;self.cache=False;self.parent=self.h.owner
        write=self.h.adb.write_debug_app_file;read=self.h.adb.read_debug_app_file
        def write_source(target,package,path,raw):
            value=json.loads(raw)
            if path==ANDROID_CONTROL_COMMAND and value.get('action')==ACTION:
                self.sequence+=1;entries={key:dict(present=False,value=None) for key in KEYS}
                entries['alsoTakeAnimatedSnapshot']=dict(present=True,value=self.h.adb.mode=='animated')
                entries['snapshotFormat']=dict(present=True,value=self.h.adb.format)
                for key,entry_value in entry_source().items():
                    if key in KEYS:entries[key]=dict(present=True,value=deepcopy(entry_value))
                if self.dirty:entries['previousStillSnapPath']=dict(present=True,value='/foreign/actual-change.png')
                initialized=self.h.adb.screen=='snapshot';cache=dict(initialized=initialized,set=initialized,value=self.h.adb.format if initialized else '',defaultValue='')
                # Explicit typed-serialization seam, not a Qt binary receipt.
                blob=json.dumps(dict(entries=entries,formatCache=cache),sort_keys=True).encode()
                self.packet=dict(snapshotSettingsOriginalsVersion=1,commandId=value['commandId'],runId=value['runId'],pid=123,
                    sequence=self.sequence,capturedEpochMs=self.h.clock(),source=dict(snapshotInstance='d'*32,managerInstance=manager_instance,
                        entriesEpochMs=self.h.clock(),entries=entries,formatCache=cache,typedSerializedBase64=base64.b64encode(blob).decode(),typedSha256=hashlib.sha256(blob).hexdigest()))
                return
            return write(target,package,path,raw)
        def read_source(target,package,path,**options):
            if path=='files/overte-e2e/'+FILE:return json.dumps(self.packet) if self.packet is not None else ''
            return read(target,package,path,**options)
        for change in (patch.object(self.h.adb,'write_debug_app_file',side_effect=write_source),patch.object(self.h.adb,'read_debug_app_file',side_effect=read_source)):
            change.start();test.addCleanup(change.stop)

    def identity(self,lease):
        with self.h.lock.held():return lease.identity()

    def attach(self):
        result=self.h.adapter._snapshot_settings_baseline(self.h.adb.target,original.RUN,self.h.phase,parent=self.parent,source_lock=self.h.lock)
        result.reader.monotonic=lambda:self.h.adb.clock;result.reader.sleep=self.h.adb.sleep;return result


class SnapshotSettingsBaselineTests(unittest.TestCase):
    def test_actual_factory_new_original_before_normal_input_header_marker_and_host_only_stream_seal(self):
        m=BaselineBoundary(self,entry_source=lambda:dict(previousSnapshotHref='hifi://original/preinput'));lease=m.attach();m.parent.prepare();baseline=lease.originals.get('settings',lease.state['original'])
        self.assertEqual(dict(present=True,value='hifi://original/preinput'),lease.packet(lease.state['original'])['source']['entries']['previousSnapshotHref'])
        self.assertEqual(3,m.parent.disk['snapshotCancelOwnerVersion']);self.assertEqual(m.identity(lease),m.parent.disk['settingsBaselineOriginalSha256'])
        self.assertFalse(lease.packet(lease.state['original'])['source']['formatCache']['initialized']);self.assertEqual([],m.h.adb.controllers)
        m.h.activate('open');m.parent.open();self.assertTrue(lease.report()['originalInputBound']);self.assertEqual(['tablet.open'],m.h.adb.controllers)
        actual=[row['command'] for row in m.parent.state['deliveries'] if row['kind']=='controller'];self.assertEqual([lease.state['envelope']],actual)
        self.assertEqual(baseline,lease.originals.get('settings',lease.state['original']));result=lease.observe()
        self.assertFalse(result['currentSettingsMatchOriginal']);self.assertFalse(result['settingsRestored']);self.assertFalse(result['fullSnapshotRecipe'])
        report=lease.report;epoch=[m.h.clock()]
        def late_report():
            value=report();epoch[0]+=2000;return value
        with patch.object(m.h.adb,'epoch_milliseconds',side_effect=lambda target:epoch[0]),patch.object(lease,'report',side_effect=late_report),self.assertRaises(NativeUIError):lease.observe()
        count=m.sequence;cold=m.h.make();self.assertEqual(count,m.sequence);self.assertIsNotNone(cold.settings_baseline)
        self.assertEqual(m.identity(lease),m.identity(cold.settings_baseline));self.assertEqual(1,len(m.h.h.transport.envelopes))
        path=lease.store.path;held=path.with_suffix('.held');path.rename(held)
        try:
            with self.assertRaises(ValueError):m.h.make()
            self.assertEqual(count,m.sequence);self.assertEqual(1,len(m.h.h.transport.envelopes))
        finally:held.rename(path)

    def test_original_v3_marker_survives_normal_cancel_and_still_without_private_schema_downgrade(self):
        m=BaselineBoundary(self);lease=m.attach();m.h.cancelled();identity=m.identity(lease)
        m.parent.quiet();m.parent.retire_job();m.h.activate('capture',dict(mode='still',format='png'))
        m.parent.capture_still();result=m.parent.quiet_still()
        self.assertEqual('still-ready',result['stage']);self.assertEqual(3,m.parent.disk['snapshotCancelOwnerVersion'])
        self.assertEqual(identity,m.parent.disk['settingsBaselineOriginalSha256']);self.assertEqual(identity,m.identity(lease));self.assertFalse(result['fullSnapshotRecipe'])
        count=m.sequence;cold=m.h.make();self.assertEqual(count,m.sequence);self.assertEqual('still-ready',cold.state['stage']);self.assertEqual(identity,m.identity(cold.settings_baseline))

    def test_existing_parent_without_original_baseline_cannot_capture_a_later_one(self):
        m=BaselineBoundary(self);m.parent.prepare();self.assertEqual(2,m.parent.disk['snapshotCancelOwnerVersion'])
        with self.assertRaises(ValueError):m.attach()
        self.assertEqual(0,m.sequence);self.assertEqual([],m.h.adb.controllers);self.assertTrue(m.parent.store.path.exists())

    def test_actual_changed_settings_before_first_controller_refuse_input_without_rebasing(self):
        m=BaselineBoundary(self);lease=m.attach();m.parent.prepare();identity=m.identity(lease);original_header=lease.store.path.read_bytes();m.dirty=True;m.h.activate('open')
        with self.assertRaises(NativeUIError):m.parent.open()
        self.assertEqual([],m.h.adb.controllers);self.assertEqual([],m.h.h.transport.envelopes);self.assertEqual('open-issued',m.parent.state['stage'])
        self.assertEqual(identity,m.identity(lease));self.assertEqual(original_header,lease.store.path.read_bytes());self.assertEqual('captured',lease.state['stage'])
        with m.h.lock.held(),self.assertRaises(NativeUIError):lease.capture()


class SnapshotSettingsBaselineFenceTests(unittest.TestCase):
    def test_late_independent_phase_change_after_baseline_admission_refuses_controller(self):
        m=BaselineBoundary(self);lease=m.attach();m.parent.prepare();m.h.activate('open');guard=m.parent.native.guard;changed=[False]
        def advancing():
            if lease.state['stage']=='admitted' and not changed[0]:changed[0]=True;m.h.activate('cleanup')
            return guard()
        with patch.object(m.parent.native,'guard',side_effect=advancing),self.assertRaises(NativeUIError):m.parent.open()
        self.assertEqual([],m.h.adb.controllers);self.assertEqual([],m.h.h.transport.envelopes);self.assertEqual('admitted',lease.state['stage'])
        self.assertEqual('open-issued',m.parent.state['stage']);self.assertTrue(lease.store.path.exists())

    def test_slow_host_only_lease_envelope_cas_with_frozen_device_clock_cannot_publish(self):
        m=BaselineBoundary(self);lease=m.attach();m.parent.prepare();m.h.activate('open');save=lease.save;epoch=m.h.clock()
        def slow(state):
            save(state)
            if state['stage']=='enveloped':m.h.adb.clock+=2
        with patch.object(lease,'save',side_effect=slow),patch.object(m.parent.native,'clock_ms',return_value=epoch),self.assertRaises(NativeUIError):m.parent.open()
        self.assertEqual([],m.h.adb.controllers);self.assertEqual([],m.h.h.transport.envelopes);self.assertEqual('enveloped',lease.state['stage'])
        count=m.sequence;cold=m.h.make();self.assertEqual(count,m.sequence);self.assertEqual('open-issued',cold.state['stage'])
        with self.assertRaises(NativeUIError):cold.open()
        self.assertEqual([],m.h.h.transport.envelopes)


if __name__=='__main__':unittest.main()
