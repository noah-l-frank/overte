"""Explicit source/transport seams, never fake capture-file acceptance evidence."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.pico4 import snapshot_capture_source as source
from adapters.script_journey.lock import ScriptSourceLock
from adapters.normal_ui import NativeUIError


class IO(source.PicoSnapshotCaptureFileIO):
    def __init__(self):
        self._before_send=lambda value:None;self.commands=[];self.epoch=20000;self.host=1.;self.count=0;self.checks=0;self.late=lambda:None
    def bind_input(self):pass
    def guard(self):
        self.checks+=1
        if self.checks==3:self.late()
    def send(self,command):
        self.guard();self._before_send(deepcopy(command));self.commands.append(command);self.count+=1
        self.value=dict(schemaVersion=1,requestId=command['commandId'],runId=command['runId'],instance='a'*32,sequence=self.count,
            processId=31,requestedEpochMs=self.epoch,capturedEpochMs=self.epoch,accepted=True,
            source=dict(picoSnapshotCaptureFilesVersion=1,instance='b'*32,complete=True,sequence=self.count,
                capturedEpochMs=self.epoch,rows=[],captures=[],plans=[]))
    def raw(self):return json.dumps(self.value)


class SnapshotCaptureSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.io=IO();self.lock=ScriptSourceLock(Path(self.temp.name)/'source.lock')
    def reader(self,**options):
        return source.PicoSnapshotCaptureFileSource(self.io,lambda:self.io.epoch,31,self.lock,
            monotonic=lambda:self.io.host,sleep=lambda _:None,**options)
    def test_readonly_source_cannot_plan_retire_or_seal_and_ack_is_not_a_plan(self):
        reader=self.reader();value=reader.request('c'*32)
        self.assertEqual([],value['source']['plans']) # accepted alone cannot establish owned preflight.
        for operation in ('plan','retire','seal'):
            with self.subTest(operation=operation),self.assertRaises(NativeUIError):
                reader.request('c'*32,operation,prefix='parity-'+('c'*16)+'-animated' if operation=='plan' else '',
                    file_id='' if operation=='plan' else 'd'*32,operation_id='e'*32)
        self.assertEqual(1,len(self.io.commands))
        self.assertEqual(value,reader.last);self.assertEqual(value,json.loads(reader.original()['raw']))
    def test_closed_control_never_accepts_requested_path_body_digest_or_effect(self):
        value=source.PicoSnapshotCaptureFileSource.envelope('c'*32,'plan',prefix='parity-'+('c'*16)+'-animated',operation_id='d'*32)
        source.command(value)
        for field,item in (('schemaVersion',True),('path','/foreign/file.png'),('expectedSha256','e'*64),('expectedClosed',True),('fileId','f'*32)):
            changed=deepcopy(value);changed[field]=item
            with self.subTest(field=field),self.assertRaises(NativeUIError):source.command(changed)
    def test_final_guard_uses_both_clock_lower_bounds_after_final_copies(self):
        for native,host in ((2000,0),(0,2)):
            self.io=IO()
            def late():self.io.epoch+=native;self.io.host+=host
            self.io.late=late
            with self.subTest(native=native,host=host),self.assertRaises(NativeUIError):self.reader().request('c'*32)
            self.assertEqual(1,len(self.io.commands))
    def test_new_observation_preserves_original_prefix_without_control_resend(self):
        reader=self.reader();first=reader.request('c'*32);second=reader.request('c'*32)
        self.assertGreater(second['source']['sequence'],first['source']['sequence'])
        self.assertNotEqual(first['requestId'],second['requestId'])
        self.assertTrue(all(item['action']=='pico-snapshot-files-observe' for item in self.io.commands))
        cold=self.reader();cold.restore(second,reader.original()['request']);cold.request('c'*32)
        self.assertEqual(3,len(self.io.commands))
        broken=deepcopy(second);broken['source']['instance']='f'*32
        with self.assertRaises(NativeUIError):source.continuity(first,broken)


if __name__=='__main__':unittest.main()
