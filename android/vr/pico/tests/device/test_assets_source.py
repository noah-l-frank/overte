"""Real native read/getter packets joined to strict Python source consumers.

Only protocol/cache/NodeList/lifecycle and pipe delivery are host seams.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[4]
sys.path[:0]=[str(ROOT/'tests/device'),str(HERE)]
from test_assets_read_native import compile_source
from adapters.normal_ui import NativeUIError
from adapters.pico4.assets_source import PicoAssetsSource
from adapters.pico4.assets_read_retirement import AssetsReadRetirement
RUN='b'*32


class AssetsSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build=tempfile.TemporaryDirectory(prefix='pico-assets-source-originals-');cls.binary,cls.environment=compile_source(cls.build.name)
    @classmethod
    def tearDownClass(cls):cls.build.cleanup()
    def setUp(self):
        self.process=subprocess.Popen([str(self.binary),'--testScript','--serve'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True,env=self.environment)
        self.addCleanup(self.close);self.raw='';self.host=0;self.lost=False;self.mutate=None;self.operations=[];self.intents=[]
    def close(self):self.process.stdin.close();self.process.wait(timeout=3);self.process.stdout.close()
    def send(self,request):
        self.operations.append(deepcopy(request));self.process.stdin.write(json.dumps(request)+'\n');self.process.stdin.flush()
        raw=self.process.stdout.readline();self.assertTrue(raw)
        if self.mutate:
            value=json.loads(raw);self.mutate(value);raw=json.dumps(value)
        self.raw='' if self.lost else raw
    def sleep(self,seconds):self.host+=seconds
    def reader(self,**options):
        return PicoAssetsSource(self.send,lambda:self.raw,lambda:int(time.time()*1000),lambda:True,self.process.pid,
            monotonic=lambda:self.host,sleep=self.sleep,intent=self.intents.append,**options)
    def retirement(self):
        return AssetsReadRetirement(self.send,lambda:self.raw,lambda:int(time.time()*1000),lambda:True,self.process.pid,
            monotonic=lambda:self.host,sleep=self.sleep)
    def test_native_inventory_resolve_download_and_cold_exact_originals(self):
        reader=self.reader();first=reader.read(RUN);source=first['source'];self.assertTrue(source['complete']);self.assertEqual(3,len(source['mappings']))
        self.assertEqual('actual first diagnostic\nactual second diagnostic',next(row for row in source['mappings'] if row['bakeStatus']==5)['bakeError'])
        self.assertTrue(any(row['path'].startswith('/.baked/') for row in source['mappings']))
        native_raw=reader.last_raw;native_hash=reader.last_sha256;history=deepcopy(reader.history)
        restored=self.reader();restored.restore(history);self.assertEqual(native_raw,restored.last_raw);self.assertEqual(native_hash,restored.last_sha256)
        self.assertEqual(hashlib.sha256(native_raw.encode()).hexdigest(),native_hash)
        second=restored.read(RUN);self.assertGreater(second['sequence'],first['sequence']);self.assertEqual(source,second['source'])
        row=next(row for row in source['mappings'] if row['path'].startswith('/e2e-'))
        resolved=self.reader(resolve=True).read(RUN,path=row['path']);self.assertEqual(row['hash'],resolved['source']['hash'])
        downloaded=self.reader(download=True).read(RUN,row['hash']);self.assertEqual(row['hash'],downloaded['source']['hash'])
        self.assertEqual(4,len(self.intents));self.assertEqual(self.intents,self.operations)
    def test_lost_read_reply_retains_exact_command_then_native_retirement_without_replay(self):
        reader=self.reader();self.lost=True
        with self.assertRaises(NativeUIError):reader.read(RUN)
        pending=deepcopy(reader.pending);self.assertEqual(1,len(self.operations))
        restored=self.reader();restored.restore([],pending)
        with self.assertRaises(NativeUIError):restored.read(RUN)
        self.assertEqual(1,len(self.operations));self.lost=False
        retired=self.retirement().read(pending);self.assertTrue(retired['source']['retired'])
        self.assertEqual(pending['commandId'],retired['source']['originalRequestId']);self.assertEqual(2,len(self.operations))
        self.assertEqual(2,self.reader().read(RUN)['sequence'])
    def test_frozen_clock_final_host_age_refuses_packet_and_keeps_pending(self):
        reader=self.reader();epoch=int(time.time()*1000);reader.clock_ms=lambda:epoch;count=0
        def guard():
            nonlocal count
            count+=1
            if count==3:self.host+=2
            return True
        reader.guard=guard
        with self.assertRaises(NativeUIError):reader.read(RUN)
        self.assertTrue(reader.pending);self.assertFalse(reader.history);self.assertEqual(1,len(self.operations))
        self.assertTrue(self.retirement().read(reader.pending)['source']['retired'])
    def test_changed_connection_birth_or_held_native_resource_never_supplies_inventory(self):
        reader=self.reader();reader.read(RUN)
        self.mutate=lambda value:value['source']['domainSession'].update(connectionBirth='f'*32)
        with self.assertRaises(NativeUIError):reader.read(RUN)
        self.assertEqual(1,len(reader.history));self.assertTrue(reader.pending);self.mutate=None
        self.assertTrue(self.retirement().read(reader.pending)['source']['retired'])
        for fault in ('activeRequests','retainedResults'):
            reader=self.reader();self.mutate=lambda value,key=fault:value.update({key:1})
            with self.assertRaises(NativeUIError):reader.read(RUN)
            self.assertFalse(reader.history);self.mutate=None
    def test_unknown_request_or_forged_retirement_never_discards_pending_ownership(self):
        original=dict(schemaVersion=1,commandId='e'*32,action='feature-pico-assets-observe',runId=RUN)
        with self.assertRaises(NativeUIError):self.retirement().read(original)
        reader=self.reader();reader.read(RUN);request=reader.history[-1]['command']
        self.mutate=lambda value:value['source'].update(finishedCaptureAlive=True)
        with self.assertRaises(NativeUIError):self.retirement().read(request)
        self.mutate=None;self.assertTrue(self.retirement().read(request)['source']['retired'])


if __name__=='__main__':unittest.main()
