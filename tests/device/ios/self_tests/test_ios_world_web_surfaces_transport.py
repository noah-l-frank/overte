"""Actual closed fixture/POST/AFC/probe route; native cache getter is modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.adapters import feature_observation,world_web_surfaces as surfaces
from ios.self_tests.test_ios_feature_observation import Native
from ios.self_tests.world_web_surfaces_fixture import CacheOriginals
from self_tests.test_native_feature_observation import probe_source

RUN='a'*32


class WorldWebSurfacesTransportTests(unittest.TestCase):
    def transport(self,*,fault=None):
        native=Native();observer=native.observer();model=CacheOriginals();model.reserve();reads=[];clocks=[];packets=[]
        observer.monotonic=lambda:model.now/1000;observer.sleep=lambda seconds:setattr(model,'now',model.now+round(seconds*1000))
        class Clock:
            sequence=0
            def read(self,after):
                self.sequence+=1;clocks.append(after);model.now+=1;return dict(capturedEpochMs=model.now)
        def post(request,timeout):
            query=native.fixture.set_client_command(json.loads(request.data));native.commands.append(deepcopy(query));native.echo=json.dumps(query).encode()
            before=dict(epochMs=model.now,monotonicMs=model.now-20000);original=model.read();model.now+=1
            value=dict(iosWorldWebSurfacesVersion=1,requestId=query['commandId'],runId=RUN,instance='c'*32,sequence=len(packets)+1,
                processId=42,clockDomain='native-main-ios-world-web-surfaces',clockBefore=before,
                clockAfter=dict(epochMs=model.now,monotonicMs=model.now-20000),source=original)
            packets.append(value)
            if fault=='lost-post':raise OSError('Modeled lost transport return after native query acceptance')
            return native
        def execute(session,operation,values):
            self.assertEqual(('native-session','mobile: pullFile'),(session,operation))
            self.assertEqual('@org.example.client:documents/owned-results/'+surfaces.FILE,values['remotePath'])
            value=deepcopy(packets[-1]);reads.append(value)
            if fault=='pid':value['processId']=43
            raw=json.dumps(value,separators=(',',':'))
            if fault=='oversize':raw+=' '*surfaces.LIMIT
            return base64.b64encode(raw.encode()).decode()
        with patch.object(feature_observation,'post_request',side_effect=post),patch.object(native,'execute',side_effect=execute):
            if fault:
                with self.assertRaises(NativeUIError):observer.world_web_surfaces(Clock()).read(RUN)
            else:
                value=observer.world_web_surfaces(Clock()).read(RUN);self.assertEqual(packets[-1],value)
                self.assertTrue(value['source']['surfaces'][0]['cached']);self.assertTrue(value['source']['surfaces'][0]['rootAlive'])
        self.assertEqual(1,len(native.commands));self.assertEqual(1,len(packets));self.assertGreaterEqual(len(clocks),1)
        if fault=='lost-post':self.assertEqual([],reads)
    def test_actual_factory_preserves_cached_root_and_all_original_counters(self):self.transport()
    def test_unknown_POST_foreign_process_and_oversized_actual_AFC_never_reissue(self):
        for fault in ('lost-post','pid','oversize'):
            with self.subTest(fault=fault):self.transport(fault=fault)
    def test_closed_fixture_and_send_refuse_wanted_cache_state_or_foreign_id_before_POST(self):
        native=Native();observer=native.observer();query=dict(schemaVersion=1,commandId='ios-'+'f'*32,action=surfaces.ACTION,runId=RUN)
        self.assertEqual(query,native.fixture.set_client_command(query))
        for edit in (dict(expectedAlive=False),dict(clear=True),dict(entityId='1'*32),dict(schemaVersion=True),dict(commandId='ios-'+'f'*32+'\n')):
            command=query|edit
            with self.subTest(edit=edit),patch.object(feature_observation,'post_request') as post:
                with self.assertRaises(NativeUIError):observer.send(command)
                post.assert_not_called()
            with self.assertRaises(ValueError):native.fixture.set_client_command(command)
    def test_actual_probe_consumes_nonce_once_and_never_supplies_an_empty_success_after_missing_getter(self):
        probe=(Path(__file__).resolve().parents[2]/'probe/overte_e2e_probe.js').read_text()
        keys=probe[probe.index('    function objectKeysMatch('):probe.index('    function httpUrl(')]
        program=r'''
const assert=require('node:assert/strict');const Uuid={generate:()=> '00000000-0000-4000-8000-000000000001'};
let calls=[],files=[];const Test={featureIOSWorldWebSurfaces:c=>{calls.push(structuredClone(c));
 return {iosWorldWebSurfacesVersion:1,requestId:c.commandId,source:{actual:true,cached:true,rootAlive:true}};},saveObject:(value,name)=>files.push({value,name})};
'''+keys+probe_source()+r'''
const query={schemaVersion:1,commandId:'ios-'+'a'.repeat(32),action:'feature-ios-world-web-surfaces',runId:'a'.repeat(32)};
applyClientCommand(query);applyClientCommand(query);assert.deepEqual(calls,[query]);
assert.equal(files.length,1);assert.deepEqual(files[0].value.source,{actual:true,cached:true,rootAlive:true});
assert.equal(files[0].name,'feature-ios-world-web-surfaces.json');
applyClientCommand({...query,commandId:'ios-'+'b'.repeat(32),clear:true});assert.equal(calls.length,1);
delete Test.featureIOSWorldWebSurfaces;applyClientCommand({...query,commandId:'ios-'+'c'.repeat(32)});
assert.equal(files.length,2);assert.equal(files[1].value.status,'unavailable');assert.equal(files[1].value.source,undefined);
'''
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=10)
        self.assertEqual(0,result.returncode,result.stderr)


if __name__=='__main__':unittest.main()
