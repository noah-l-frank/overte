"""Actual closed Snapshot HTTP/AFC/probe routing; native getters are models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import json
from pathlib import Path
import secrets
import subprocess
import unittest
from unittest.mock import patch
from adapters.native_feature_observation import decode
from adapters.normal_ui import NativeUIError
from ios.adapters import feature_observation,world_web_whole_snapshot as snapshot
from ios.self_tests.test_ios_feature_observation import Native
from ios.self_tests.world_web_whole_snapshot_fixture import WholeSnapshotNative as SnapshotNative
from ios.self_tests.world_web_source_boundary import RUN,URL
from self_tests.test_native_feature_observation import probe_source


class WorldWebWholeSnapshotTransportTests(unittest.TestCase):
    def transport(self,batch,*,fault=None):
        native=Native();observer=native.observer();observer.monotonic=lambda:batch.sdk.time;observer.sleep=batch.sdk.sleep
        reads=[];clock_reads=[]
        class Clock:
            sequence=0
            def read(self,after):
                self.sequence+=1;clock_reads.append(after);return dict(capturedEpochMs=batch.sdk.tick())
        clock=Clock()
        def post(request,timeout):
            query=native.fixture.set_client_command(json.loads(request.data));native.commands.append(deepcopy(query));native.echo=json.dumps(query).encode()
            batch.send(query)
            if fault=='lost-post':raise OSError('Modeled delivery unknown after actual command acceptance')
            return native
        def execute(session,operation,arguments):
            self.assertEqual(('native-session','mobile: pullFile'),(session,operation))
            self.assertEqual('@org.example.client:documents/owned-results/'+snapshot.FILE,arguments['remotePath'])
            raw=batch.raw()
            if fault=='oversize':raw+=' '*snapshot.LIMIT
            elif fault=='pid':
                value=json.loads(raw);value['processId']=43;raw=json.dumps(value)
            reads.append(raw);return base64.b64encode(raw.encode()).decode()
        with patch.object(feature_observation,'post_request',side_effect=post),patch.object(native,'execute',side_effect=execute):
            if fault:
                with self.assertRaises(NativeUIError):observer.world_web_whole_snapshot(clock).read(RUN,URL)
            else:value=observer.world_web_whole_snapshot(clock).read(RUN,URL)
        self.assertEqual(1,len(native.commands));self.assertEqual(1,len(batch.commands))
        if fault=='lost-post':self.assertEqual([],reads)
        return (None if fault else value),reads,clock_reads

    def test_actual_factory_polls_same_pending_originals_without_resending_post_or_inner_DOM_request(self):
        batch=SnapshotNative(document=True,pending_polls=2,held_callback=True)
        value,raws,clock_reads=self.transport(batch)
        self.assertEqual(3,len(raws));self.assertGreaterEqual(len(clock_reads),4)
        self.assertEqual(['pending','pending','ready'],[json.loads(raw)['status'] for raw in raws])
        self.assertEqual(1,batch.dom_issued);self.assertTrue(batch.callback_pending)
        self.assertEqual(json.loads(raws[-1]),value)
        first=snapshot.unpack(json.loads(raws[0])['payload']);last=snapshot.unpack(value['payload'])
        self.assertEqual(first['calls'],last['calls'][:len(first['calls'])])
        self.assertEqual(first['queries']['document'],last['queries']['document'])

    def test_large_actual_AFC_bytes_keep_exact_plain_originals_and_strict_old_decoder_bound(self):
        batch=SnapshotNative(document=True)
        for _ in range(115):
            entry=batch.page.event('key-enter',dict(text=secrets.token_hex(4096),key=0,modifiers=0));batch.page.event('signal-return',dict(entry=entry['sequence']))
        value,raws,_clock_reads=self.transport(batch);raw=raws[0]
        self.assertGreater(len(raw.encode()),1048576);self.assertLess(len(raw.encode()),snapshot.LIMIT)
        self.assertGreater(value['payload']['plainBytes'],2097152)
        with self.assertRaises(NativeUIError):decode(raw)
        self.assertEqual(value,decode(raw,limit=snapshot.LIMIT))
        self.assertEqual(batch.page.events,snapshot.body(value)[1]['ledgerAfter']['events'])
        print('WorldWeb WholeSnapshot actual AFC bytes:',len(raw.encode()),'compressed:',value['payload']['compressedBytes'],'plain:',value['payload']['plainBytes'],flush=True)

    def test_unknown_delivery_transport_overflow_and_foreign_native_process_never_resend(self):
        for fault in ('lost-post','oversize','pid'):
            with self.subTest(fault=fault):self.transport(SnapshotNative(),fault=fault)

    def test_closed_real_fixture_and_send_reject_wanted_effect_or_other_root_before_POST(self):
        native=Native();observer=native.observer();query=dict(schemaVersion=1,commandId='ios-'+'f'*32,action=snapshot.ACTION,runId=RUN,fixtureUrl=URL)
        self.assertEqual(query,native.fixture.set_client_command(query))
        for bad in (query|dict(expected=True),query|dict(fixtureUrl=URL+'elsewhere'),query|dict(surface='world'),query|dict(schemaVersion=True)):
            with self.subTest(bad=bad),patch.object(feature_observation,'post_request') as post:
                with self.assertRaises(NativeUIError):observer.send(bad)
                post.assert_not_called()
            with self.assertRaises(ValueError):native.fixture.set_client_command(bad)

    def test_actual_probe_reuses_one_outer_command_for_pending_poll_and_preserves_all_original_bytes(self):
        probe=(Path(__file__).resolve().parents[2]/'probe/overte_e2e_probe.js').read_text()
        keys=probe[probe.index('    function objectKeysMatch('):probe.index('    function httpUrl(')]
        program=r'''
const assert=require('node:assert/strict');const Uuid={generate:()=> '00000000-0000-4000-8000-000000000001'};
let calls=[],files=[];const Test={featureIOSWorldWebWholeSnapshot:c=>{
 calls.push(structuredClone(c));return {iosWorldWebSnapshotVersion:2,commandId:c.commandId,status:calls.length===1?'pending':'ready',payload:{actual:'untouched-original'}};
},saveObject:(value,name)=>files.push({value,name})};
'''+keys+probe_source()+r'''
const query={schemaVersion:1,commandId:'ios-'+'a'.repeat(32),action:'feature-ios-world-web-whole-snapshot',runId:'a'.repeat(32),
fixtureUrl:'http://127.0.0.1:43210/feature-fixture/v1/runs/'+'a'.repeat(32)+'/'};
applyClientCommand(query);applyClientCommand(query);assert.deepEqual(calls,[query,query]);
assert.equal(files[0].value.status,'pending');assert.equal(files[1].value.status,'ready');
assert.deepEqual(files[1].value.payload,{actual:'untouched-original'});assert.equal(files[1].name,'feature-ios-world-web-whole-snapshot.json');
applyClientCommand({...query,expected:true});applyClientCommand({...query,schemaVersion:true});
assert.equal(calls.length,2);assert.equal(files.length,2);
'''
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=10)
        self.assertEqual(0,result.returncode,result.stderr)


if __name__=='__main__':unittest.main()
