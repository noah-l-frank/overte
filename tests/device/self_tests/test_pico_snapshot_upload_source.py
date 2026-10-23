"""Explicit native DTO seams; no uploaded image or wire success qualification."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from adapters.script_journey.lock import ScriptSourceLock
from adapters.pico4 import snapshot_upload_source as source

RUN='b'*32
PATH='/data/user/0/org.overte.pico/files/Snapshots/original.png'


def packet(request,sequence=1,epoch=20000):
    file=dict(bytes=3,sha256=hashlib.sha256(b'abc').hexdigest(),device='18446744073709551614',inode='9223372036854775809',readBytes=3,
        readSha256=hashlib.sha256(b'abc').hexdigest(),mode=0o100600,uid=10001,gid=10001,links=1,mtimeSeconds=1000,mtimeNanoseconds=1,ctimeSeconds=1000,ctimeNanoseconds=2)
    body=dict(snapshotUploadObservationVersion=2,instance='3'*32,complete=True,capturedEpochMs=epoch,sequence=4,
        events=[dict(sequence=index+1,jobId='4'*32,kind=kind,capturedEpochMs=epoch) for index,kind in enumerate(('begin','file-open','terminal','file-destroyed'))],
        jobs=[dict(id='4'*32,path=PATH,href='hifi://actual/place',uploaderAlive=False,fileAlive=False,multipartAlive=False,file=file,cancelRequested=False,terminal='error',requests=[])])
    return dict(schemaVersion=1,requestId=request['commandId'],runId=request['runId'],instance='5'*32,sequence=sequence,processId=123,
        requestedEpochMs=epoch,capturedEpochMs=epoch,source=body)


class Boundary:
    def __init__(self):self.epoch=20000;self.host=1.;self.commands=[];self.raw='';self.last=None;self.checks=0;self.late=lambda:None
    def send(self,request):self.commands.append(deepcopy(request));self.last=packet(request,len(self.commands),self.epoch);self.raw=json.dumps(self.last)
    def guard(self):self.checks+=1;self.late();return True


class SnapshotUploadSourceTests(unittest.TestCase):
    def fixture(self):
        temporary=tempfile.TemporaryDirectory(prefix='pico-upload-source-');self.addCleanup(temporary.cleanup);root=Path(temporary.name);root.chmod(0o700)
        lock=ScriptSourceLock(root/'script-sources.lock');b=Boundary()
        reader=source.PicoSnapshotUploadSource(b.send,lambda:b.raw,lambda:b.epoch,b.guard,123,lock,monotonic=lambda:b.host,sleep=lambda amount:None)
        return reader,b
    def test_exact_original_reader_retains_raw_request_and_same_source_lock_without_upload_input(self):
        reader,b=self.fixture();first=reader.read(RUN);second=reader.read(RUN)
        self.assertEqual(2,len(b.commands));self.assertEqual('feature-pico-snapshot-upload',b.commands[0]['action'])
        self.assertNotEqual(first['requestId'],second['requestId']);self.assertEqual(json.loads(reader.original()['raw']),second)
        second['source']['jobs'].clear();self.assertEqual(1,len(reader.last['source']['jobs']))
        self.assertEqual('18446744073709551614',reader.last['source']['jobs'][0]['file']['device'])
    def test_closed_read_command_refuses_endpoint_setter_upload_cancel_or_requested_effect(self):
        reader,b=self.fixture();reader.read(RUN);request=b.commands[0];source.command(request)
        for key,value in (('schemaVersion',True),('url','https://foreign.invalid'),('operation','upload'),('expectedUploaded',True),('action','phone-snapshot-upload-observe')):
            with self.subTest(key=key),self.assertRaises(NativeUIError):source.command(dict(request,**{key:value}))
    def test_phone_or_host_paths_old_metadata_and_numeric_64bit_identity_are_not_pico_originals(self):
        request=source.command(dict(schemaVersion=1,commandId='a'*32,action='feature-pico-snapshot-upload',runId=RUN))
        for fault in ('phone','host','old-version','numeric-device','leadingzero','mode','links','nanoseconds','missing-stat','booluid'):
            value=packet(request);file=value['source']['jobs'][0]['file']
            if fault=='phone':value['source']['jobs'][0]['path']=PATH.replace('org.overte.pico','io.github.noah_be.overte.phone')
            elif fault=='host':value['source']['jobs'][0]['path']='/home/host/original.png'
            elif fault=='old-version':value['source']['snapshotUploadObservationVersion']=1
            elif fault=='numeric-device':file['device']=int(file['device'])
            elif fault=='leadingzero':file['inode']='01'
            elif fault=='mode':file['mode']=0o100644
            elif fault=='links':file['links']=2
            elif fault=='nanoseconds':file['mtimeNanoseconds']=1000000000
            elif fault=='missing-stat':file.pop('ctimeSeconds')
            else:file['uid']=True
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.validate(value,request,123,20000)
    def test_cold_reader_rechecks_actual_raw_types_and_never_sends_during_restore(self):
        reader,b=self.fixture();value=reader.read(RUN);request=b.commands[0];raw=b.raw;cold,cold_boundary=self.fixture()
        cold.restore(value,request,raw);self.assertEqual([],cold_boundary.commands);self.assertEqual(value,cold.last)
        bad_raw=raw.replace('"processId": 123','"processId": 123.0')
        another,_=self.fixture()
        with self.assertRaises(NativeUIError):another.restore(value,request,bad_raw)
    def test_original_file_or_history_rewrite_cannot_become_a_new_cold_baseline(self):
        reader,b=self.fixture();first=reader.read(RUN)
        for fault in ('instance','jobpath','inode','ctime','history','revival'):
            second=deepcopy(first);second['sequence']+=1;file=second['source']['jobs'][0]['file']
            if fault=='instance':second['source']['instance']='6'*32
            elif fault=='jobpath':second['source']['jobs'][0]['path']=PATH.replace('original','other')
            elif fault=='inode':file['inode']='7'
            elif fault=='ctime':file['ctimeNanoseconds']+=1
            elif fault=='history':second['source']['events'][1]['kind']='terminal'
            else:second['source']['jobs'][0]['fileAlive']=True
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.continuity(first,second)
    def test_frozen_native_or_host_clock_cannot_hide_slow_final_guard_or_return_copy(self):
        for fault in ('native-guard','host-guard','copy'):
            reader,b=self.fixture()
            if fault=='copy':
                copy=source.deepcopy
                def slow(value):
                    result=copy(value)
                    if type(value) is dict and 'source' in value:b.host+=2
                    return result
                context=patch.object(source,'deepcopy',side_effect=slow)
            else:
                def late():
                    if b.checks==3:
                        if fault=='native-guard':b.epoch+=2000
                        else:b.host+=2
                b.late=late;context=patch.object(b,'commands',b.commands)
            with context,self.subTest(fault=fault),self.assertRaises(NativeUIError):reader.read(RUN)
            self.assertIsNone(reader.last);self.assertEqual(1,len(b.commands))
    def test_raw_bound_is_checked_before_decode_and_unavailable_is_not_empty_jobs(self):
        for raw in (' '*262145,json.dumps(dict(available=False))):
            reader,b=self.fixture();send=reader.send
            def malformed(request):send(request);b.raw=raw
            reader.send=malformed
            with self.subTest(size=len(raw)),self.assertRaises(NativeUIError):reader.read(RUN)
            self.assertIsNone(reader.last)
    def test_retirement_requires_original_lifetimes_and_finished_destroyed_requests(self):
        reader,b=self.fixture();value=reader.read(RUN)['source'];source.require_retired(value)
        for key in ('uploaderAlive','fileAlive','multipartAlive'):
            changed=deepcopy(value);changed['jobs'][0][key]=True
            with self.subTest(key=key),self.assertRaises(NativeUIError):source.require_retired(changed)
