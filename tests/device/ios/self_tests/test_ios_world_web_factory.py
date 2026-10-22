"""Actual command/AFC codecs; native/WK/clock boundaries are explicit models."""
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
from ios.adapters import feature_observation,world_web_source,world_web_dom
from ios.self_tests.test_ios_feature_observation import Native
from ios.self_tests.world_web_source_fixture import OriginalSources,RUN,URL
from self_tests.test_native_feature_observation import probe_source


class WorldWebFactoryTests(unittest.TestCase):
    def test_actual_probe_delivers_one_transcript_nonce_and_polls_only_the_same_native_DOM_query(self):
        probe=(Path(__file__).resolve().parents[2]/'probe/overte_e2e_probe.js').read_text()
        keys=probe[probe.index('    function objectKeysMatch('):probe.index('    function httpUrl(')]
        program=r'''
const assert=require('node:assert/strict');const Uuid={generate:()=> '00000000-0000-4000-8000-000000000001'};let ledger=0,dom=0,files=[];
const Test={featureIOSWorldWeb:c=>{ledger++;return {commandId:c.commandId,original:true};},
featureIOSWorldWebDOM:c=>{dom++;return {commandId:c.commandId,status:dom===1?'pending':'ready'};},
saveObject:(value,name)=>files.push({value,name})};
'''+keys+probe_source()+r'''
const base={schemaVersion:1,commandId:'ios-'+'a'.repeat(32),action:'feature-ios-world-web',runId:'a'.repeat(32),
fixtureUrl:'http://127.0.0.1:43210/feature-fixture/v1/runs/'+'a'.repeat(32)+'/'};
applyClientCommand(base);applyClientCommand(base);
applyClientCommand({...base,commandId:'ios-'+'b'.repeat(32)});applyClientCommand(base);
assert.equal(ledger,2);assert.equal(files[0].name,'feature-ios-world-web.json');assert.equal(files[0].value.original,true);
const query={...base,commandId:'ios-'+'c'.repeat(32),action:'feature-ios-world-web-dom'};
applyClientCommand(query);applyClientCommand(query);assert.equal(dom,2);
assert.equal(files.at(-2).value.status,'pending');assert.equal(files.at(-1).value.status,'ready');
assert.equal(files.at(-1).name,'feature-ios-world-web-dom.json');
const count=files.length;applyClientCommand({...query,expected:true});assert.equal(files.length,count);assert.equal(dom,2);
'''
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=10)
        self.assertEqual(0,result.returncode,result.stderr)

    def test_existing_session_factories_pull_each_exact_original_and_bracket_the_native_clock(self):
        for kind,module in (('world_web',world_web_source),('world_web_dom',world_web_dom)):
            with self.subTest(kind=kind):
                f=OriginalSources();native=Native();clock_reads=[]
                class Clock:
                    sequence=0
                    def read(self,after):
                        self.sequence+=1;clock_reads.append(after);return dict(capturedEpochMs=f.clock())
                clock=Clock();last={}
                observer=native.observer();observer.monotonic=lambda:f.epoch/1000
                def post(request,timeout):
                    query=native.fixture.set_client_command(json.loads(request.data));native.commands.append(deepcopy(query))
                    native.echo=json.dumps(query).encode();last['value']=f.ledger(query) if kind=='world_web' else f.document(query)
                    return native
                def execute(session,operation,values):
                    self.assertEqual(('native-session','mobile: pullFile'),(session,operation))
                    self.assertEqual('@org.example.client:documents/owned-results/'+module.FILE,values['remotePath'])
                    native.reads.append(deepcopy(values));return base64.b64encode(json.dumps(last['value']).encode()).decode()
                with patch.object(feature_observation,'post_request',side_effect=post),patch.object(native,'execute',side_effect=execute):
                    reader=getattr(observer,kind)(clock);value=reader.read(RUN,URL)
                self.assertEqual(last['value'],value);self.assertEqual(module.ACTION,native.commands[0]['action'])
                self.assertEqual(1,len(native.commands));self.assertEqual(1,len(native.reads));self.assertGreaterEqual(len(clock_reads),3)
                self.assertEqual(42,reader.pid)

    def test_invalid_source_inputs_are_refused_before_actual_post_and_fixture_matches_closed_grammar(self):
        native=Native();observer=native.observer()
        for module in (world_web_source,world_web_dom):
            valid=dict(schemaVersion=1,action=module.ACTION,commandId='ios-'+'f'*32,runId=RUN,fixtureUrl=URL)
            self.assertEqual(valid,native.fixture.set_client_command(valid))
            for invalid in (valid|dict(expected=True),valid|dict(fixtureUrl=URL+'elsewhere'),valid|dict(surface='world')):
                with self.subTest(action=module.ACTION),patch.object(feature_observation,'post_request') as send:
                    with self.assertRaises(NativeUIError):observer.send(invalid)
                    send.assert_not_called()
                with self.assertRaises(ValueError):native.fixture.set_client_command(invalid)


if __name__=='__main__':unittest.main()
