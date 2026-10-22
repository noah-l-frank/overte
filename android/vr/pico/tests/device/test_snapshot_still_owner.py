"""Actual Pico normal controls/session/file scripts; renderer/native Qt are seams."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import unittest
import uuid
from unittest.mock import patch
import test_native_execution_binding as original
ROOT=Path(__file__).resolve().parents[5]
sys.path.insert(0,str(ROOT/'tests/device'))
from adapters.android.adapter import ANDROID_CONTROL_COMMAND
from adapters.normal_feature_state import PrivateFeatureState
from adapters.pico4 import snapshot_originals as source
from adapters.script_journey.history import pack,unpack
from feature_journeys.phase_fixture import PhaseFixtureReader
from feature_journeys.witness import Client,Journal
from openxr_input.adapter_session import PicoOpenXrAdapterSession
from self_tests.test_pico_openxr_adapter_session import FakeTransport
from self_tests.test_pico_snapshot_originals import Boundary
from self_tests.test_snapshot_journey import encoded
from self_tests.test_android_snapshot_files import OriginalAndroidSnapshotFiles

RUN='a'*32


class SnapshotStillOwnerTests(unittest.TestCase):
    def setUp(self):
        self.h=original.NativeExecutionBindingTest();self.h.setUp();self.addCleanup(self.h.doCleanups)
        self.h.snapshot_setup(images={'still-png':encoded()});self.adb=self.h.fake;self.adapter=self.h.instance()
        self.adb.clock=0.;self.adb.sleep=lambda amount:setattr(self.adb,'clock',self.adb.clock+amount)
        self.adb.epoch_milliseconds=lambda _target:20000+round(self.adb.clock*1000)
        self.native=Boundary();self.native.clock=lambda:self.adb.epoch_milliseconds(self.adb.target)
        self.journal=Journal(clock=self.native.clock);registered=self.journal.register('snapshots')
        self.journal.runs[RUN]=self.journal.runs.pop(registered);self.activate('baseline')
        test=self
        class PhaseClient(Client):
            def request(self,path,*args,phase_nonce=None,**kwargs):return test.journal.phase(RUN,phase_nonce)
        self.source=PhaseFixtureReader(PhaseClient('http://127.0.0.1:9876/feature-fixture/v1','f'*64),RUN,'snapshots',
            monotonic=lambda:self.adb.clock,epoch_ms=self.native.clock)
        class Transport(FakeTransport):
            delay=0
            def stage(self,envelope,profile,*,before_publish=None):
                test.adb.clock+=self.delay
                if before_publish is not None:
                    # The final transport callback may inspect retained memory
                    # and a monotonic clock only; no private-file/phase/native IO.
                    with (patch.object(test.source,'status',side_effect=AssertionError('phase under publication')),
                            patch.object(test.owner.native,'guard',side_effect=AssertionError('native under publication')),
                            patch.object(test.owner.store,'read',side_effect=AssertionError('file IO under publication'))):
                        before_publish(deepcopy(envelope));before_publish(deepcopy(envelope))
                self.envelopes.append(deepcopy(envelope));test.adb.opened=envelope['commands'][0]['operation']=='tablet.open'
                test.adb.controllers.append(envelope['commands'][0]['operation']);return dict(sequence=envelope['sequence'])
        self.transport=Transport();self.session=PicoOpenXrAdapterSession(self.transport,self.adb.target,self.h.state_root)
        self.session.begin(self.adb.identity)
        self.changes=[patch.object(self.adapter,'pico_input_session',return_value=self.session),
            patch('time.time',side_effect=lambda:self.native.clock()/1000)]
        original_write=self.adb.write_debug_app_file;original_read=self.adb.read_debug_app_file;original_take=self.adb.take
        def take():
            original_take()
            if self.adb.mutation=='ack-only':return
            request=self.native.request();request.update(requestId='snap_1792368000000_1',registeredEpochMs=self.native.clock(),alive=False,nativeState='')
            basename=self.adb.text+'-'+request['requestId']+'.png'
            request['events']=[dict(sequence=1,phase='complete',publishedEpochMs=self.native.clock(),
                basenameSha256=hashlib.sha256((RUN+'\0'+basename).encode()).hexdigest(),
                pathSha256=hashlib.sha256((RUN+'\0'+str(self.adb.files/basename)).encode()).hexdigest(),error='')]
            self.native.requests=[request];self.adb.opened=True # Explicit original native/script-return boundary.
        def write(target,package,path,raw):
            command=json.loads(raw)
            if path==ANDROID_CONTROL_COMMAND and command.get('action')==source.ACTION:
                self.native.send(command);return
            return original_write(target,package,path,raw)
        def read(target,package,path,**options):
            if path=='files/overte-e2e/'+source.FILE:return self.native.read()
            return original_read(target,package,path,**options)
        self.changes += [patch.object(self.adb,'take',side_effect=take),patch.object(self.adb,'write_debug_app_file',side_effect=write),
            patch.object(self.adb,'read_debug_app_file',side_effect=read)]
        original_factory=self.adapter._snapshot_native_originals
        def factory(*args,**kwargs):
            reader=original_factory(*args,**kwargs);reader.monotonic=lambda:self.adb.clock;reader.sleep=self.adb.sleep;return reader
        self.changes.append(patch.object(self.adapter,'_snapshot_native_originals',side_effect=factory))
        for change in self.changes:change.start();self.addCleanup(change.stop)
        self.lock=self.adapter._script_journey()._lock(self.adb.target);self.owner=self.create()
    def create(self):return self.adapter._snapshot_still_owner(self.adb.target,RUN,self.source,source_lock=self.lock)
    def activate(self,verb,inputs=None):self.journal.activate(RUN,uuid.uuid4().hex,verb,inputs or {})
    def opened(self):
        self.owner.prepare();self.activate('open');self.owner.open()
    def captured(self):
        self.opened();self.activate('capture',dict(mode='still',format='png'));return self.owner.take()
    def test_actual_normal_still_png_original_complete_file_native_quiet_restore_and_close(self):
        report=self.captured();self.assertEqual('captured',report['stage']);self.assertEqual('PNG',report['png']['format'].upper())
        self.assertIs(self.owner.lock,self.lock);self.assertEqual('native-quiet',self.owner.quiet()['stage'])
        self.activate('close');self.assertEqual('closed',self.owner.close()['stage']);report=self.owner.quiet()
        self.assertEqual('partial-closed',report['stage']);self.assertFalse(report['deviceAcceptance']);self.assertFalse(report['fullSnapshotRecipe'])
        self.assertEqual(('animated','webp'),(self.adb.mode,self.adb.format));self.assertFalse(self.adb.opened)
        self.assertEqual(1,self.adb.captures);self.assertTrue(self.owner.store.path.exists())
        self.assertTrue(self.owner.snapshot.path.exists());self.assertTrue(self.owner.snapshot.ui.path.exists())
        self.assertEqual(1,len(list(self.adb.files.glob('*.png'))));self.assertEqual(2,len(self.owner.state['quiet']))
        before=(len(self.adb.inputs),len(self.transport.envelopes));cold=self.create();self.assertEqual(report,cold.report())
        self.assertEqual(before,(len(self.adb.inputs),len(self.transport.envelopes)))
    def test_acknowledged_ignored_capture_and_cold_recovery_never_reissue_input(self):
        self.opened();self.adb.mutation='ack-only';self.activate('capture',dict(mode='still',format='png'))
        self.assertEqual('capture-issued',self.owner.take()['stage']);before=(len(self.adb.inputs),len(self.transport.envelopes))
        cold=self.create();self.assertEqual('capture-issued',cold.reconcile()['stage'])
        with self.assertRaises((ValueError,RuntimeError)):cold.take()
        self.assertEqual(before,(len(self.adb.inputs),len(self.transport.envelopes)));self.assertEqual(1,self.adb.captures)
        self.assertIsNone(cold.state['capture']);self.assertTrue(cold.store.path.exists())
    def test_lost_response_after_actual_capture_reconciles_original_bytes_without_resend(self):
        self.opened();self.activate('capture',dict(mode='still',format='png'));original_write=self.adb.write_debug_app_file
        def lost(target,package,path,raw):
            result=original_write(target,package,path,raw)
            if json.loads(raw).get('controlId')=='snapshot.capture':raise RuntimeError('explicit lost transport response')
            return result
        with patch.object(self.adb,'write_debug_app_file',side_effect=lost):
            with self.assertRaises(RuntimeError):self.owner.take()
        before=(len(self.adb.inputs),len(self.transport.envelopes));cold=self.create()
        self.assertEqual('captured',cold.reconcile()['stage']);self.assertEqual(before,(len(self.adb.inputs),len(self.transport.envelopes)))
        self.assertEqual(1,self.adb.captures)
        self.assertEqual(2,cold.file_source()['snapshotFileOriginalVersion'])
        cold.snapshot.files.last_original['snapshotFileOriginalVersion']=1
        with self.assertRaises((ValueError,RuntimeError)):cold.file_source()
    def test_last_parent_cas_phase_advance_prevents_actual_capture_writer(self):
        self.opened();self.activate('capture',dict(mode='still',format='png'));original_write=self.owner.store.write
        def changed(value,previous):
            original_write(value,previous);state=unpack(value['payload'])[0]
            if state['deliveries'] and state['deliveries'][-1]['command'].get('controlId')=='snapshot.capture':self.activate('close')
        with patch.object(self.owner.store,'write',side_effect=changed):
            with self.assertRaises((ValueError,RuntimeError)):self.owner.take()
        self.assertEqual(0,self.adb.captures);self.assertFalse(any(row['controlId']=='snapshot.capture' for row in self.adb.inputs))
        self.assertEqual('snapshot.capture',self.owner.state['deliveries'][-1]['command']['controlId'])
        self.assertEqual('capture-issued',self.owner.state['stage'])
    def test_frozen_native_clock_slow_final_parent_cas_refuses_actual_capture(self):
        self.opened();self.activate('capture',dict(mode='still',format='png'));original_write=self.owner.store.write
        def slow(value,previous):
            original_write(value,previous);state=unpack(value['payload'])[0]
            if state['deliveries'] and state['deliveries'][-1]['command'].get('controlId')=='snapshot.capture':self.adb.clock+=2
        with patch.object(self.owner.store,'write',side_effect=slow),patch.object(self.owner.native,'clock_ms',return_value=20000):
            with self.assertRaises((ValueError,RuntimeError)):self.owner.take()
        self.assertEqual(0,self.adb.captures);self.assertTrue(self.owner.store.path.exists())
    def test_slow_original_controller_transport_refuses_publication_after_durable_intent(self):
        self.owner.prepare();self.activate('open');self.transport.delay=2
        with self.assertRaises((ValueError,RuntimeError)):self.owner.open()
        self.assertEqual([],self.transport.envelopes);self.assertEqual([],self.adb.inputs);self.assertFalse(self.adb.opened)
        self.assertEqual('open-issued',self.owner.state['stage']);self.assertEqual('controller',self.owner.state['deliveries'][-1]['kind'])
        self.assertEqual('tablet.open',self.owner.state['deliveries'][-1]['command']['commands'][0]['operation'])
        self.assertTrue(self.owner.store.path.exists())
    def test_original_file_replacement_or_host_copy_replacement_cannot_become_quiet(self):
        self.captured();file=self.owner.state['capture']['file'];path=self.adb.files/file['basename']
        replacement=path.with_suffix('.replacement');replacement.write_bytes(path.read_bytes());replacement.replace(path)
        with self.assertRaises((ValueError,RuntimeError)):self.owner.quiet()
        self.assertTrue(self.owner.store.path.exists());self.assertEqual('quiet-issued',self.owner.state['stage'])
    def test_host_original_inode_replacement_blocks_cold_load_even_with_identical_png(self):
        self.captured();file=self.owner.state['capture']['file'];path=self.adb.artifacts/file['artifact']
        replacement=path.with_suffix('.replacement');replacement.write_bytes(path.read_bytes());replacement.chmod(0o600);replacement.replace(path)
        with self.assertRaises((ValueError,RuntimeError)):self.create()
        self.assertTrue(self.owner.store.path.exists())
    def test_actual_callback_path_mismatch_refuses_same_basename_png(self):
        self.opened();self.activate('capture',dict(mode='still',format='png'))
        self.native.mutate=lambda value:[event.update(pathSha256='e'*64) for row in value['requests'] for event in row['events']]
        with self.assertRaises((ValueError,RuntimeError)):self.owner.take()
        self.assertEqual(1,self.adb.captures);self.assertIsNone(self.owner.state['capture']);self.assertTrue(self.owner.store.path.exists())
    def test_archived_quiet_window_cannot_accept_a_living_original_timer(self):
        self.captured();self.owner.quiet();disk=self.owner.store.read();state=unpack(disk['payload'])[0]
        index=state['quiet'][0]['first'];frame=state['frames'][index];value=json.loads(frame['native']['raw'])
        value['resources']['projectionTimerActive']=True;frame['native']['raw']=json.dumps(value)
        frame['native']['sha256']=hashlib.sha256(frame['native']['raw'].encode()).hexdigest();changed=deepcopy(disk);changed['payload']=pack([state])
        self.owner.store.write(changed,disk)
        with self.assertRaises((ValueError,RuntimeError)):self.create()
        self.assertEqual(changed,self.owner.store.read())
    def test_orphan_owner_preserves_child_journals_after_actual_base_stop_and_blocks_public_resend(self):
        self.opened();before=self.owner.snapshot.path.read_bytes()
        with self.assertRaises((ValueError,RuntimeError)):self.adapter.invoke(self.adb.target,'snapshot.open',{})
        with self.assertRaises((ValueError,RuntimeError)):self.adapter.cleanup(self.adb.target)
        self.assertFalse(self.adb.running);self.assertEqual(before,self.owner.snapshot.path.read_bytes());self.assertTrue(self.owner.store.path.exists())
        self.assertTrue(self.owner.snapshot.ui.path.exists())
    def test_cold_journal_rejects_boolean_command_version_and_foreign_original_controller_id(self):
        self.opened();disk=self.owner.store.read()
        for kind in ('qml','controller'):
            state=unpack(disk['payload'])[0];delivery=next(row for row in state['deliveries'] if row['kind']==kind)
            if kind=='qml':delivery['command']['schemaVersion']=True
            else:delivery['command']['commands'][0]['id']='foreign-original-id'
            changed=deepcopy(disk);changed['payload']=pack([state]);self.owner.store.write(changed,disk)
            with self.subTest(kind=kind),self.assertRaises((ValueError,RuntimeError)):self.create()
            self.owner.store.write(disk,changed)


if __name__=='__main__':unittest.main()
