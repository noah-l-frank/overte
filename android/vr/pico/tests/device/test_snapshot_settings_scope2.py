"""Explicit Source2 on existing normal Parent; Native/Qt/SDK are models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import gc
import os
import subprocess
import time
import zlib
from unittest.mock import patch
import json
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[5]/'tests/device'))
from self_tests.pico_snapshot_settings_scope2_fixture import Scope2Boundary
from adapters.normal_ui import NativeUIError
from adapters.pico4.snapshot_settings_originals import PicoSnapshotSettingsOriginals
from adapters.pico4.snapshot_settings_query_originals import UNRESOLVED,NAME,retained
from adapters.pico4.lifecycle_process_file import LifecycleProcessFile
from adapters.native_fd_owner import OriginalDescriptor
from adapters.script_journey.history import canonical


class SnapshotSettingsScope2Tests(unittest.TestCase):
    def test_actual_factory_preinput_original_same_normal_open_and_lossless_wire(self):
        m=Scope2Boundary(self);lease=m.attach();self.assertIs(lease,m.attach())
        m.parent.prepare();before=deepcopy(lease.packet(lease.state['original']))
        self.assertEqual(2,before['snapshotSettingsOriginalsVersion']);self.assertFalse(before['source']['durationEntry']['present'])
        self.assertFalse(before['source']['durationCache']['initialized']);self.assertFalse(before['source']['durationCache']['set'])
        bits=base64.b64decode(before['source']['durationCache']['value']['base64'])
        self.assertTrue(bits.endswith(b'\x80\x00\x00\x00'));self.assertEqual([],m.h.adb.controllers)
        self.assertEqual(2,lease.disk['snapshotSettingsBaselineVersion']);self.assertEqual(2,lease.originals.scope['snapshotSettingsBaselineOriginalsVersion'])
        with m.h.lock.held():
            self.assertEqual(m.outputs[0],lease.raw.literal(dict(snapshotSettingsRawReferenceVersion=2,bundle=0,sha256=lease.raw.state['bundles'][0]['sha256'])))
        m.h.activate('open');m.parent.open();self.assertTrue(lease.report()['originalInputBound'])
        self.assertEqual(['tablet.open'],m.h.adb.controllers);self.assertEqual(2,len(m.sdk_calls))
        result=lease.observe();self.assertFalse(result['settingsRestored']);self.assertFalse(result['fullSnapshotRecipe'])
        self.assertEqual(before,lease.packet(lease.state['original']));self.assertEqual(3,len(m.sdk_calls))
        with m.h.lock.held():self.assertTrue(lease.raw.close_host())

    def test_source1_live_reader_cannot_adopt_passively_valid_source2_original(self):
        m=Scope2Boundary(self);lease=m.attach();m.parent.prepare();before=lease.packet(lease.state['original']);calls=[]
        reader=PicoSnapshotSettingsOriginals(lambda row:calls.append(row),lambda:json.dumps(before),m.h.clock,lambda:True,123,m.h.lock,
            monotonic=lambda:m.h.adb.clock,sleep=m.h.adb.sleep)
        with self.assertRaises(NativeUIError):reader.restore(before)
        self.assertEqual([],calls);self.assertIsNone(reader.previous)
        with m.h.lock.held():self.assertTrue(lease.raw.close_host())

    def test_source2_live_reader_cannot_adopt_valid_legacy1_history(self):
        from self_tests.test_pico_snapshot_settings_originals import Boundary
        m=Scope2Boundary(self);lease=m.attach();m.parent.prepare();before=deepcopy(lease.reader.previous)
        root=m.h.adb.app/'legacy-source1-reader';root.mkdir(mode=0o700)
        legacy=Boundary(root);value=legacy.reader.capture(m.parent.run)
        with lease.lock.held(),self.assertRaises(NativeUIError):lease.reader.restore(value)
        self.assertEqual(before,lease.reader.previous);self.assertEqual(1,len(m.sdk_calls));self.assertEqual([],m.h.adb.controllers)
        with lease.lock.held():self.assertTrue(lease.raw.close_host())

    def test_source1_capture_cannot_adopt_matching_nonce_scope2_output(self):
        m=Scope2Boundary(self);lease=m.attach();m.parent.prepare();value=lease.packet(lease.state['original']);sent=[]
        def send(command):sent.append(command);value['commandId']=command['commandId']
        reader=PicoSnapshotSettingsOriginals(send,lambda:json.dumps(value),m.h.clock,lambda:True,123,m.h.lock,
            monotonic=lambda:m.h.adb.clock,sleep=m.h.adb.sleep)
        with self.assertRaises(NativeUIError):reader.capture(m.parent.run)
        self.assertEqual(1,len(sent));self.assertIsNone(reader.previous);self.assertIsNone(reader.last_raw)
        self.assertEqual(1,len(m.sdk_calls));self.assertEqual([],m.h.adb.controllers)
        with lease.lock.held():self.assertTrue(lease.raw.close_host())


class SnapshotSettingsScope2FenceTests(unittest.TestCase):
    def literal(self,lease):
        with lease.lock.held():return lease.raw.literal(lease.raw.last_reference)

    def malformed(self,data):
        m=Scope2Boundary(self);lease=m.attach();m.fault=lambda _wire,nonce:m.wire_bytes(data,nonce)
        with self.assertRaises((NativeUIError,UnicodeError,ValueError)):m.parent.prepare()
        self.assertEqual(1,len(m.sdk_calls));self.assertEqual(m.outputs[0],self.literal(lease))
        self.assertIsNone(lease.reader.previous);self.assertTrue(lease.raw.failed);self.assertEqual([],m.h.adb.controllers)
        with self.assertRaises((NativeUIError,ValueError)):m.parent.prepare()
        self.assertEqual(1,len(m.sdk_calls));self.assertFalse(lease.raw.close_host())

    def test_malformed_actual_utf8_bytes_retained_before_parser_and_no_replay(self):
        self.malformed(b'actual\x00\xff malformed UTF8')

    def test_duplicate_actual_json_retained_before_refusal_and_no_replay(self):
        self.malformed(b'{"duplicate":1,"duplicate":2}')

    def test_actual_normal_cancel_then_same_scope2_read_keeps_existing_empty_mutex(self):
        m=Scope2Boundary(self);lease=m.attach();m.h.cancelled();path=m.parent.files.lock.path
        self.assertTrue(path.exists());self.assertEqual(b'',path.read_bytes());before=path.stat()
        result=lease.observe();self.assertFalse(result['settingsRestored']);self.assertEqual(3,len(m.sdk_calls))
        self.assertEqual(before,path.stat());self.assertEqual(b'',path.read_bytes())
        with lease.lock.held():self.assertTrue(lease.raw.close_host())

    def test_actual_file_owner_mutex_nonempty_refuses_before_next_settings_writer_or_getter(self):
        m=Scope2Boundary(self);lease=m.attach();m.h.cancelled();path=m.parent.files.lock.path
        path.write_bytes(b'actual foreign mutex bytes');before=len(m.sdk_calls);native=m.sequence
        with self.assertRaises(NativeUIError):lease.observe()
        self.assertEqual(before,len(m.sdk_calls));self.assertEqual(native,m.sequence)
        self.assertEqual(b'actual foreign mutex bytes',path.read_bytes());self.assertFalse(lease.raw.close_host())

    def test_ignored_scope2_request_cannot_adopt_fresh_legacy1_output(self):
        m=Scope2Boundary(self);lease=m.attach()
        def legacy(_wire,nonce):
            value=deepcopy(m.packet);value['snapshotSettingsOriginalsVersion']=1
            del value['source']['durationEntry'];del value['source']['durationCache']
            return m.wire_bytes(canonical(value),nonce)
        m.fault=legacy
        with self.assertRaises(NativeUIError):m.parent.prepare()
        self.assertEqual(m.outputs[0],self.literal(lease));self.assertIsNone(lease.reader.previous)
        self.assertEqual([],m.h.adb.controllers);self.assertEqual(1,len(m.sdk_calls))

    def test_foreign_manager_birth_after_original_refuses_actual_first_input(self):
        m=Scope2Boundary(self);lease=m.attach();m.parent.prepare();original=deepcopy(lease.packet(lease.state['original']))
        def foreign(_wire,nonce):
            value=deepcopy(m.packet);value['source']['managerInstance']='e'*32
            return m.wire_bytes(canonical(value),nonce)
        m.fault=foreign;m.h.activate('open')
        with self.assertRaises(NativeUIError):m.parent.open()
        self.assertEqual([],m.h.adb.controllers);self.assertEqual(2,len(m.sdk_calls));self.assertEqual('captured',lease.state['stage'])
        self.assertEqual(original,lease.packet(lease.state['original']));self.assertEqual(m.outputs[-1],self.literal(lease))

    def test_slow_capacity_with_frozen_native_clock_has_zero_actual_writer_or_getter(self):
        m=Scope2Boundary(self);lease=m.attach();measure=lease.raw.namespace.measure
        def delayed(context):
            value=measure(context);time.sleep(1.6);return value
        with patch.object(lease.raw.namespace,'measure',side_effect=delayed),self.assertRaises(NativeUIError):m.parent.prepare()
        self.assertEqual(0,m.sequence);self.assertEqual([],m.sdk_calls);self.assertEqual([],m.h.adb.controllers)
        self.assertTrue(lease.raw.failed);self.assertIsNone(lease.reader.previous)

    def test_actual_late_return_is_durable_before_original_real_age_refusal_and_parser(self):
        m=Scope2Boundary(self);lease=m.attach()
        def delayed(wire,_nonce):time.sleep(1.6);return wire
        m.fault=delayed
        with patch('adapters.pico4.snapshot_settings_scope2_reader.decode',side_effect=AssertionError('Parser before actual age refusal')) as decoder, self.assertRaises(NativeUIError):m.parent.prepare()
        decoder.assert_not_called();self.assertEqual(1,len(m.sdk_calls));self.assertEqual(m.outputs[0],self.literal(lease))
        self.assertIsNone(lease.reader.previous);self.assertTrue(lease.raw.failed)

    def test_partial_timeout_output_is_original_before_refusal_and_never_replayed(self):
        m=Scope2Boundary(self);lease=m.attach();partial=[]
        def timeout(wire,_nonce):
            partial.append(wire[:137]);raise subprocess.TimeoutExpired(['declared-model-sdk'],.1,output=partial[-1])
        m.fault=timeout
        with self.assertRaises(RuntimeError):m.parent.prepare()
        self.assertEqual(partial[0],self.literal(lease));self.assertEqual(1,len(m.sdk_calls));self.assertEqual([],m.h.adb.controllers)
        with self.assertRaises((ValueError,NativeUIError)):m.parent.prepare()
        self.assertEqual(1,len(m.sdk_calls))

    def test_acquired_wire_survives_codec_loss_without_foreign_fallback(self):
        m=Scope2Boundary(self);lease=m.attach();original=zlib.compress;calls=[];outputs=[]
        def foreign(*_args,**_options):calls.append('foreign');return b'false compressed bytes'
        def lost(wire,_nonce):outputs.append(wire);zlib.compress=foreign;return wire
        m.fault=lost
        try:
            with self.assertRaises(NativeUIError):m.parent.prepare()
        finally:zlib.compress=original
        gc.collect();self.assertEqual([],calls);self.assertEqual(outputs[0],lease.raw.acquired)
        self.assertIn(lease.raw,UNRESOLVED);self.assertFalse(lease.raw.close_host());self.assertIsNone(lease.reader.previous)
        self.assertEqual([],m.h.adb.controllers)

    def test_actual_raw_final_cas_lost_response_retains_full_bytes_without_interpretation(self):
        m=Scope2Boundary(self);lease=m.attach();write=LifecycleProcessFile.write;lost=[]
        def unknown(owner,value,previous):
            result=write(owner,value,previous)
            if owner is lease.raw.file and value['queries'] and value['queries'][-1]['originals'] and value['pendingArchive'] is None:
                lost.append(owner);raise OSError('Actual full raw/root CAS committed before response loss')
            return result
        with patch.object(LifecycleProcessFile,'write',unknown),self.assertRaises(NativeUIError):m.parent.prepare()
        self.assertEqual([lease.raw.file],lost);self.assertEqual(m.outputs[0],lease.raw.acquired)
        self.assertIsNone(lease.reader.previous);self.assertEqual([],m.h.adb.controllers);self.assertEqual(1,len(m.sdk_calls))
        self.assertFalse(lease.raw.close_host());self.assertIn(lease.raw,UNRESOLVED)

    def test_first_directory_ctor_loss_without_marker_blocks_canonical_cleanup_after_gc(self):
        m=Scope2Boundary(self);construct=OriginalDescriptor.__init__;opened=[]
        def unknown(owner,path,*options):
            construct(owner,path,*options)
            if Path(path)==m.h.lock.path.parent:
                opened.append(owner);raise OSError('Actual first raw directory opened before constructor response loss')
        with patch.object(OriginalDescriptor,'__init__',unknown),self.assertRaises(ValueError):m.attach()
        raw=m.parent._snapshot_scope2_raw;self.assertIn(raw,UNRESOLVED);self.assertFalse((m.h.lock.path.parent/NAME).exists())
        del m.parent._snapshot_scope2_raw;gc.collect();self.assertIs(raw.file.parent,opened[0]);opened[0].require(opened[0].fd)
        self.assertTrue(retained(m.h.adapter,m.h.adb.target));self.assertFalse(retained(m.h.adapter,m.h.adb.target+'-foreign'))
        with patch.object(m.h.adapter,'_installation',side_effect=AssertionError('Product read during retained cleanup')) as product, \
                patch.object(m.h.adb,'shell',side_effect=AssertionError('SDK read during retained cleanup')) as sdk, self.assertRaises(ValueError):
            m.h.adapter.cleanup(m.h.adb.target)
        product.assert_not_called();sdk.assert_not_called();opened[0].require(opened[0].fd)
        self.assertFalse(raw.close_host());self.assertEqual([],m.h.adb.controllers)


if __name__=='__main__':unittest.main()
