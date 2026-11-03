"""Actual Parent/factory/SDK dispatch; Android/native effects remain models.

Only the original SDK subprocess boundary is replaced. The old generic writer
is not replaced or enlarged. Host staged bytes and original storage are real;
Android stat/native packet producer remain declared fixtures.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import time
import traceback
import unittest
from unittest.mock import patch

from adb_transport import AdbTransport
from adapters.native_feature_observation import need
from adapters.normal_ui import NativeUIError
from adapters.pico4.assets_transport import HEADER,FOOTER
from adapters.pico4.assets_prefix_originals import AssetsPrefixOriginals
from adapters.script_journey.history import canonical
import self_tests.test_pico_assets_raw_ranges as fixture
from self_tests.pico_assets_upload_fixture import AssetsUploadModel


def stamp(path):
    s=path.stat()
    def date(ns):return datetime.fromtimestamp(ns//10**9,timezone.utc).strftime('%Y-%m-%d %H:%M:%S')+f'.{ns%10**9:09d} +0000'
    return f'{s.st_dev} {s.st_ino} {s.st_mode:x} {s.st_uid} {s.st_nlink} {s.st_size} {date(s.st_mtime_ns)} {date(s.st_ctime_ns)}'


class AssetsWireOwnerTests(unittest.TestCase):
    def setUp(self):
        self.numeric_native_identity=True
        fixture.AssetsRawRangesTests.setUp(self);m,p=self.model,self.parent
        self.assertIs(m.adapter.adb,m.native);m.real_time_start=time.monotonic();m.leases={}
        m.activate('baseline');m.send=self.native_model;self.sdk_calls=[];self.actual_commands=[];self.lost=False;self.bad_wire=False;self.foreign_instance=False
        self.native_file=self.root/'declared-android-native-original.json';self.native_file.write_bytes(b'{}');self.native_file.chmod(0o600)
        for active in (patch.object(m.native,'execute_bytes',AdbTransport.execute_bytes.__get__(m.native),create=True),
            patch.object(m.native,'command',['declared-sdk-never-executed'],create=True),
            patch('adb_transport.subprocess.run',side_effect=self.execute)):
            active.start();self.addCleanup(active.stop)
        p.bind_wire(m.adapter,m.native.target)
        with p.lock.held():
            self.files=m.adapter._assets_file_owner(m.native.target,m.run,'c'*32,m.url,stage=2)
        self.send=self.files.native.send
        def issue(command):
            p.query_anchor=(m.clock,m.epoch());p.source_intent('files',command);p.send_source(command,self.send)
        def diagnose(label,call,*args):
            try:return call(*args)
            except BaseException:
                (self.root/(label+'-failure.txt')).write_text(traceback.format_exc());raise
        self.files.native.send=lambda command:diagnose('original-send',issue,command)
        self.files.native.original=lambda:diagnose('original-read',p.raw_source,'files',lambda:p.wire.read('files'))
        guard=self.files.native.guard
        self.files.native.guard=lambda:diagnose('original-guard',guard)

    def native_model(self,command):
        m=self.model;m.query_sequence+=1
        source=AssetsUploadModel.files_source(m,command)
        packet=dict(schemaVersion=1,requestId=command['commandId'],runId=m.run,operation=command['operation'],
            instance='b'*32 if self.foreign_instance else 'a'*32,sequence=m.query_sequence,processId=123,
            requestedEpochMs=m.epoch(),capturedEpochMs=m.epoch(),source=source)
        self.native_file.write_bytes(canonical(packet));self.native_file.chmod(0o600)

    def execute(self,args,**options):
        self.assertEqual(['declared-sdk-never-executed','-s',self.model.native.target,'exec-out'],args[:4])
        self.assertNotIn('text',options);self.sdk_calls.append(deepcopy(options))
        parsed=shlex.split(args[4]);self.assertEqual(['run-as','org.overte.pico','sh','-c'],parsed[:4])
        nonce=parsed[10]
        if 'input' in options:
            raw=options['input'];self.assertIs(type(raw),bytes);command=json.loads(raw)
            self.actual_commands.append(command);self.native_model(command)
            raw_file=self.root/'actual-sdk-stdin.bin';raw_file.write_bytes(raw);raw_file.chmod(0o600)
            output=(f'OVT_PICO_ASSETS_STAGE_V1 {nonce} {len(raw)} {hashlib.sha256(raw).hexdigest()}\n'+stamp(raw_file)+'\n').encode()
            if self.lost:output=b''
        else:
            raw=self.native_file.read_bytes();description=stamp(self.native_file).encode()
            output=HEADER+nonce.encode()+b'\n'+description+b'\n'+raw+FOOTER+nonce.encode()+b'\n'+description+b'\n'
            if self.bad_wire:output=b'\xff actual malformed framing'
        return subprocess.CompletedProcess(args,0,stdout=output,stderr=b'')

    def request(self,operation='stage'):
        p=self.parent
        with p.lock.held():
            value=self.files.native.request(operation,self.model.run,self.files.state['ownerToken'],
                self.files.inputs if operation=='stage' else None)
            p.state['pendingSource']=None;p.save();return value

    def test_canonical_stage_native_query_through_actual_sdk_binary_and_one_original_parent(self):
        value=self.request();p=self.parent
        self.assertTrue(value['source']['exists']);self.assertEqual(1,len(self.actual_commands))
        self.assertEqual(37209,len(self.sdk_calls[0]['input']));self.assertEqual(2,len(self.sdk_calls))
        self.assertEqual(1,len(p.state['transportReceipts']));self.assertEqual(1,len(p.state['rawReads']))
        self.assertEqual(1,p.raw_archive.audio.state['reads']);self.assertEqual(1,len(self.files.native.history))
        with p.lock.held():
            raw=p.literal(0);self.assertEqual(self.native_file.read_bytes(),raw)
            self.assertIsNone(p.raw_archive.active);self.assertLess(p.store.path.stat().st_size,65536)
            self.assertLessEqual(p.bill()['frames'],512);self.assertLessEqual(p.bill()['decodedBytes'],16*1024*1024)
        reader=AssetsPrefixOriginals(p.store.path)
        try:self.assertEqual(raw,reader.literal(0));self.assertEqual(1,len(reader.value['transportReceipts']))
        finally:self.assertTrue(reader.close_host())

    def test_lost_receipt_raw_bundle_and_native_response_reservation_retained_without_replay(self):
        self.lost=True
        with self.assertRaises(NativeUIError):self.request()
        p=self.parent;self.assertEqual(1,len(self.sdk_calls));self.assertFalse(self.files.native.history)
        with p.lock.held():
            self.assertIsNotNone(p.disk['pendingRawRead']);self.assertEqual(1,len(p.disk['transportReceipts']))
            record=p.original(p.disk['transportReceipts'][0]);self.assertEqual(0,record['bytes'])
            self.assertTrue(p.raw_archive.audio.state['pending'])
        with self.assertRaises(NativeUIError):self.request()
        self.assertEqual(1,len(self.sdk_calls));self.assertTrue(p.wire.transport.failed)

    def test_malformed_wire_retained_once_before_any_native_json_or_view(self):
        self.bad_wire=True
        with self.assertRaises(NativeUIError):self.request()
        p=self.parent
        with p.lock.held():
            self.assertEqual(1,len(p.state['rawReads']));self.assertNotIn('wireView',p.state['rawReads'][0])
            self.assertEqual(b'\xff actual malformed framing',p.literal(0))
        self.assertFalse(self.files.native.history);self.assertTrue(p.wire.transport.failed)

    def test_same_pid_different_native_instance_retained_then_refused(self):
        # Admission is the actual NativeAssetsFiles historical instance, never
        # expected stage contents. The modeled producer then changes instance.
        self.request('observe');self.foreign_instance=True
        with self.assertRaises(NativeUIError):self.request('stage')
        self.assertEqual(1,len(self.files.native.history));self.assertEqual(2,len(self.parent.state['rawReads']))
        with self.parent.lock.held():
            self.assertEqual('b'*32,json.loads(self.parent.literal(1))['instance'])


if __name__=='__main__':unittest.main()
