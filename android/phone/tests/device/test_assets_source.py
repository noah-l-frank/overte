"""Fresh actual mapping/download packet counterexamples, without a target."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(ROOT/'tests/device/adapters/android-phone')]
from overte_phone_assets_source import PhoneAssetsSource,command,validate,mapping_path
from adapters.normal_ui import NativeUIError

RUN='a'*32
DOMAIN='12345678-1234-4234-8234-123456789abc'
DATA=b'actual downloaded asset bytes'
HASH=hashlib.sha256(DATA).hexdigest()


class Boundary:
    def __init__(self):
        self.clock=0.;self.epoch=1700000000000;self.sequence=0;self.request=None;self.value=None;self.fault=None;self.guarded=True
        self.source=dict(phoneAssetsObservationVersion=1,domainId=DOMAIN,sessionId=DOMAIN,canWrite=True,complete=True,
            mappings=[dict(path='/original/main.fbx',hash=HASH,bakeStatus=4,bakeError='')])
    def send(self,request):
        self.request=deepcopy(request);self.sequence+=1
        source=deepcopy(self.source) if request['action']=='phone-assets-observe' else dict(phoneAssetsDownloadVersion=1,hash=HASH,bytes=len(DATA),base64=base64.b64encode(DATA).decode(),loadedFromCache=False)
        self.value=dict(schemaVersion=1,requestId=request['commandId'],runId=RUN,instance='b'*32,sequence=self.sequence,processId=321,
            requestedEpochMs=self.epoch,capturedEpochMs=self.epoch,source=source,activeRequests=0,retainedResults=0)
        if self.fault:self.fault(self.value)
    def read(self):return json.dumps(self.value)
    def sleep(self,seconds):self.clock+=seconds;self.epoch+=round(seconds*1000)
    def reader(self,**kwargs):return PhoneAssetsSource(self.send,self.read,lambda:self.epoch,lambda:self.guarded,321,monotonic=lambda:self.clock,sleep=self.sleep,**kwargs)


class AssetsSourceTests(unittest.TestCase):
    def test_actual_read_retains_mapping_hash_and_all_six_original_bake_statuses(self):
        b=Boundary();reader=b.reader()
        for status in range(6):
            b.source['mappings'][0]['bakeStatus']=status
            self.assertEqual(b.source,reader.read(RUN)['source'])
        self.assertEqual(6,reader.last['sequence'])
    def test_download_is_original_content_with_exact_requested_hash_and_no_live_requests(self):
        b=Boundary();value=b.reader(download=True).read(RUN,HASH)
        self.assertEqual(DATA,base64.b64decode(value['source']['base64']));self.assertEqual(0,value['activeRequests']);self.assertEqual(0,value['retainedResults'])
    def test_ack_pending_failed_or_partial_reply_never_becomes_empty_mapping_state(self):
        for change in (dict(source={}),dict(source=dict(complete=False)),dict(activeRequests=1),dict(retainedResults=1),dict(activeRequests=False)):
            with self.subTest(change=change):
                b=Boundary();b.fault=lambda value:value.update(change)
                with self.assertRaises(NativeUIError):b.reader().read(RUN)
    def test_wrong_domain_type_missing_original_hash_duplicate_and_unsorted_paths_are_red(self):
        for change in (lambda s:s.update(domainId='foreign'),lambda s:s['mappings'][0].pop('hash'),lambda s:s['mappings'].append(deepcopy(s['mappings'][0])),lambda s:s['mappings'].insert(0,s['mappings'][0]|dict(path='/zzz')),
                       lambda s:s['mappings'][0].update(bakeStatus=True),lambda s:s.update(complete=False)):
            b=Boundary();b.fault=lambda value:change(value['source'])
            with self.subTest(change=change),self.assertRaises(NativeUIError):b.reader().read(RUN)
    def test_changed_download_bytes_length_hash_or_base64_cannot_supply_original(self):
        for change in (dict(hash='0'*64),dict(bytes=len(DATA)+1),dict(base64=base64.b64encode(b'foreign').decode()),dict(base64='%%%'),dict(loadedFromCache=1)):
            b=Boundary();b.fault=lambda value:value['source'].update(change)
            with self.subTest(change=change),self.assertRaises(NativeUIError):b.reader(download=True).read(RUN,HASH)
    def test_old_process_instance_sequence_epoch_and_slow_original_stay_red(self):
        for key,value in (('processId',322),('instance','0'*32),('capturedEpochMs',1699999990000),('requestedEpochMs',1700000000001)):
            b=Boundary();b.fault=lambda packet:packet.update({key:value})
            with self.subTest(key=key),self.assertRaises(NativeUIError):b.reader().read(RUN)
        b=Boundary();reader=b.reader();reader.read(RUN);b.fault=lambda packet:packet.update(sequence=1)
        with self.assertRaises(NativeUIError):reader.read(RUN)
        b=Boundary();reader=b.reader();original=reader.original
        def slow():b.clock+=5.1;return original()
        reader.original=slow
        with self.assertRaises(NativeUIError):reader.read(RUN)
    def test_source_advancing_clock_after_payload_parse_is_rechecked(self):
        b=Boundary();reader=b.reader();calls=[0]
        def guard():
            calls[0]+=1
            if calls[0]>=4:b.epoch+=2000
            return True
        reader.guard=guard
        with self.assertRaises(NativeUIError):reader.read(RUN)
    def test_adapter_readonly_grammar_admits_only_the_exact_original_queries(self):
        from appium_adapter import readonly_feature_command
        request=dict(schemaVersion=1,commandId='c'*32,action='phone-assets-observe',runId=RUN)
        readonly_feature_command(request)
        readonly_feature_command(request|dict(action='phone-assets-download',hash=HASH))
        for addition in (dict(action='phone-assets-delete'),dict(expectedMappings=[]),dict(path='/private/owned'),dict(hash=HASH)):
            with self.subTest(addition=addition),self.assertRaises((ValueError,NativeUIError)):readonly_feature_command(request|addition)

    def test_readonly_commands_admit_no_mutations_expectations_url_or_private_path(self):
        request=dict(schemaVersion=1,commandId='c'*32,action='phone-assets-observe',runId=RUN)
        for addition in (dict(expectedMappings=[]),dict(path='/tmp/file'),dict(url='http://fixture.invalid'),dict(action='phone-assets-delete'),dict(schemaVersion=True)):
            with self.subTest(addition=addition),self.assertRaises(NativeUIError):command(request|addition)
        for path in ('relative','/a/../b','/a//b','/a/','/a\\b','/a\x00b'):
            with self.subTest(path=path),self.assertRaises(NativeUIError):mapping_path(path)


if __name__=='__main__':unittest.main()
