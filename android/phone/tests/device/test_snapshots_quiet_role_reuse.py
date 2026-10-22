"""Bounded same-role quiet prototype over actual public host fixture cleanup.

This primary-role timing probe never publishes an independent actor sample.
Native/SDK producers are explicit seams; originals, TLS, files and locks are real.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import sys
import time
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent))
import test_snapshots_feature_journey as harness
from adapters.native_feature_observation import need
from adapters.normal_ui import NativeUIError
from overte_phone_create_actor import quiet_window
from overte_phone_script_history import same
from overte_phone_script_lock import PhoneScriptSourceLock
from overte_phone_snapshots_role import PhoneSnapshotsRole


def prepared_role(fixture,*,history=0,full=False):
    fixture.client.activate('c'*32)
    measured=fixture.invoke('feature.snapshots.observe',dict(contractVersion=harness.VERSION,runId=harness.RUN,afterSequence=0))
    commands=[('open',{}),('capture',dict(mode='still',format='png'))]
    if full:commands=[('open',{}),('capture-cancel',dict(mode='animated',format='png')),('capture',dict(mode='still',format='png')),
        ('save',{}),('share-open',{}),('share-select-owned',{}),('upload',{})]
    for verb,inputs in commands:
        fixture.act(verb,inputs)
        measured=fixture.invoke('feature.snapshots.observe',dict(contractVersion=harness.VERSION,runId=harness.RUN,afterSequence=measured['sequence']))
    for _ in range(history):
        measured=fixture.invoke('feature.snapshots.observe',dict(contractVersion=harness.VERSION,runId=harness.RUN,afterSequence=measured['sequence']))
    fixture.client.activate('f'*32,'cleanup')
    fixture.invoke('feature.snapshots.cleanup',dict(contractVersion=harness.VERSION,runId=harness.RUN))
    feature=fixture.adapter._snapshots_feature('test-only-appium',harness.RUN)
    with feature.lock.held():
        feature.load();header=deepcopy(feature.previous);phase=feature.phase.status();started=time.monotonic()
        role=PhoneSnapshotsRole(feature,'primary');constructor=time.monotonic()-started
        need(feature.state['phase']=='cleaned' and phase['active'] and phase['activations'][-1]['stimulus']['verb']=='cleanup')
        need(same(feature.store.read(),feature.previous) and same(feature.previous,header))
    return dict(feature=feature,role=role,header=header,roleHeader=deepcopy(role.previous),binding=deepcopy(feature.binding),phase=phase,constructor=constructor)


def quiet_batch(prepared):
    feature,role=prepared['feature'],prepared['role'];quiet=None;durations=[];started=time.monotonic()
    with feature.lock.held():
        # Check the pinned owner before load can adopt any foreign header.
        need(same(feature.store.read(),prepared['header']) and same(role.store.read(),prepared['roleHeader'])
            and same(feature.binding,prepared['binding']))
        feature.load()
        need(same(feature.previous,prepared['header']) and same(role.previous,prepared['roleHeader'])
            and same(feature.binding,prepared['binding']))
        feature.bound();role.bound();role.history_authority()
        current=feature.phase.status()
        need(feature.state['phase']=='cleaned' and current['active'] and same(current['activations'],prepared['phase']['activations']))
        while True:
            sample_started=time.monotonic();feature.bound();role.history_authority()
            need(same(role.restore_originals(),role.frames))
            current=feature.phase.status();need(current['active'] and same(current['activations'],prepared['phase']['activations']))
            measured=role.read(role.state['sequence']);need(measured['resources']==[])
            proof=feature.restored(snapshot=role.frames[-1]);quiet=quiet_window(quiet,feature.monotonic(),measured['sequence']);quiet['final']=proof
            durations.append(time.monotonic()-sample_started)
            if quiet['complete'] or time.monotonic()-started>=3.5:break
            feature.sleep(.1)
        feature.bound();role.history_authority()
    return dict(quiet=quiet,lockedSeconds=time.monotonic()-started,sampleSeconds=durations)


class SnapshotQuietRoleReuseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture_type=type('QuietPrototypeFixture',(harness.SnapshotJourneyTests,),{})
        cls.fixture_type.setUpClass()

    @classmethod
    def tearDownClass(cls):
        try:cls.fixture_type.tearDownClass()
        finally:cls.fixture_type.doClassCleanups()

    def setUp(self):
        self.fixture=self.fixture_type('test_original_public_baseline_before_any_input_or_capture')
        self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)

    def test_late_original_history_reused_role_proves_real_quiet_inside_original_lock_budget(self):
        prepared=prepared_role(self.fixture,history=30,full=True)
        with PhoneScriptSourceLock(prepared['feature'].lock.path,timeout=.1).held():pass
        measured=quiet_batch(prepared)
        with PhoneScriptSourceLock(prepared['feature'].lock.path,timeout=.1).held():pass
        summary=dict(constructorSeconds=round(prepared['constructor'],3),lockedSeconds=round(measured['lockedSeconds'],3),
            sampleSeconds=[round(value,3) for value in measured['sampleSeconds']],quietSpan=round(measured['quiet']['last']-measured['quiet']['started'],3),
            samples=len(measured['quiet']['sequences']),complete=measured['quiet']['complete'],retainedFrames=len(prepared['role'].frames),deviceAcceptance=False)
        print('Actual same-role quiet prototype '+json.dumps(summary,sort_keys=True),flush=True)
        self.assertLess(measured['lockedSeconds'],5);self.assertTrue(measured['quiet']['complete'])
        self.assertGreaterEqual(measured['quiet']['last']-measured['quiet']['started'],3)
        self.assertGreaterEqual(len(measured['quiet']['sequences']),3)

    def test_closed_provider_between_locks_cannot_adopt_prepared_role(self):
        prepared=prepared_role(self.fixture);self.fixture.client.close()
        with self.assertRaises(NativeUIError):quiet_batch(prepared)

    def test_foreign_owner_header_between_locks_is_preserved_and_rejected(self):
        prepared=prepared_role(self.fixture);feature=prepared['feature'];foreign=deepcopy(prepared['header']);foreign['binding']['sessionId']='foreign'
        feature.store.write(foreign,prepared['header'])
        with self.assertRaises(NativeUIError):quiet_batch(prepared)
        self.assertEqual(foreign,feature.store.read())

    def test_foreign_role_header_between_locks_is_preserved_and_rejected(self):
        prepared=prepared_role(self.fixture);role=prepared['role'];foreign=deepcopy(role.previous);foreign['role']='actor'
        role.store.write(foreign,role.previous)
        with self.assertRaises(NativeUIError):quiet_batch(prepared)
        self.assertEqual(foreign,role.store.read())

    def test_actual_sdk_pid_replacement_between_locks_cannot_sample_old_role(self):
        prepared=prepared_role(self.fixture);sequence=prepared['role'].state['sequence']
        self.fixture.setup.f.native.identity='32:foreign-start'
        with self.assertRaises(NativeUIError):quiet_batch(prepared)
        self.assertEqual(sequence,prepared['role'].state['sequence'])

    def test_actual_late_owned_file_between_locks_prevents_quiet_success(self):
        prepared=prepared_role(self.fixture)
        late=self.fixture.model.producer.directory/('e2e-'+harness.RUN+'-late.png');late.write_bytes(self.fixture.model.raw_png)
        with self.assertRaises(NativeUIError):quiet_batch(prepared)
        self.assertEqual(self.fixture.model.raw_png,late.read_bytes())
        self.assertIsNotNone(prepared['feature'].store.read())


if __name__=='__main__':unittest.main()
