"""Actual shared Node/Fixture/AFC routes, modeled native envelope + actual DOM JS."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from fixture.serve import FixtureState
from ios.adapters import feature_observation,tablet_web_dom as dom
from ios.self_tests.test_ios_feature_observation import Native
from ios.self_tests.tablet_web_dom_fixture import original_bodies,packet,query,RUN,ROOT,REPO
from self_tests.test_native_feature_observation import probe_source


class TabletDOMTransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.original=packet(original_bodies()[0][0])

    def test_actual_fixture_accepts_closed_passive_query_without_expected_or_text(self):
        fixture=FixtureState();self.assertEqual(query(),fixture.set_client_command(query()))
        for extra in ({'schemaVersion':True},{'expectedOpen':True},{'text':'requested value'},{'html':'desired document'},{'keys':'secret'}):
            with self.subTest(extra=extra),self.assertRaises(ValueError):fixture.set_client_command(query()|extra)

    def test_actual_probe_polls_original_pending_then_immutable_terminal_without_reissuing_js(self):
        program='''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,keys)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(keys.sort());
const page=require('./tests/device/ios/self_tests/test_ios_tablet_web_dom.js').page();
const original=PACKET;let calls=0,issued=0,files=[],cache=new Map();
const Test={featureIOSTabletWebDOM:q=>{
 calls++;let entry=cache.get(q.commandId);
 if(!entry){issued++;const body=page.read(q.commandId),epoch=body.capturedEpochMs;
 const ready={...original,commandId:q.commandId,sequence:issued,clockBefore:{epochMs:epoch,monotonicMs:epoch-80000},clockAfter:{epochMs:epoch,monotonicMs:epoch-80000},source:{...original.source,dom:body}};
 entry={ready,pending:{...ready,status:'pending',source:{}},calls:0};cache.set(q.commandId,entry);}
 return ++entry.calls===1?entry.pending:entry.ready;
},saveObject:(v,name)=>files.push({v,name})};
SOURCE
const q=QUERY;applyClientCommand(q);if(files.at(-1).v.status!=='pending')throw Error('pending replaced');
applyClientCommand(q);const terminal=JSON.stringify(files.at(-1).v);applyClientCommand(q);
if(JSON.stringify(files.at(-1).v)!==terminal||issued!==1)throw Error('terminal retimed/reissued');
const q2={...q,commandId:'ios-'+'c'.repeat(32)};applyClientCommand(q2);applyClientCommand(q2);applyClientCommand(q);
if(issued!==2||calls!==6||files.length!==6||JSON.stringify(files.at(-1).v)!==terminal)throw Error('old callback replay');
if(files[0].name!=='feature-ios-tablet-web-dom.json')throw Error('wrong original file');
applyClientCommand({...q,expectedOpen:true});if(calls!==6)throw Error('expected field accepted');
delete Test.featureIOSTabletWebDOM;applyClientCommand({...q,commandId:'ios-'+'d'.repeat(32)});
if(files.at(-1).v.status!=='unavailable'||files.at(-1).v.source)throw Error('missing source became empty success');
'''.replace('PACKET',json.dumps(self.original)).replace('QUERY',json.dumps(query())).replace('SOURCE',probe_source())
        result=subprocess.run(['node','-e',program],cwd=REPO,capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)

    def test_actual_factory_sends_query_and_preserves_original_AFC_native_dom_bytes(self):
        native=Native();observer=native.observer();commands=[];reads=[];epoch=self.original['clockAfter']['epochMs']
        def post(request,timeout):
            command=native.fixture.set_client_command(json.loads(request.data));commands.append(command);native.echo=json.dumps(command).encode()
            # Execute the actual passive JS with this exact source-read nonce.
            program="const p=require('./tests/device/ios/self_tests/test_ios_tablet_web_dom.js').page();process.stdout.write(JSON.stringify(p.read("+json.dumps(command['commandId'])+")));"
            result=subprocess.run(['node','-e',program],cwd=REPO,capture_output=True,text=True,timeout=5)
            self.assertEqual(0,result.returncode,result.stderr);body=json.loads(result.stdout)
            native.value=packet(body);native.value.update(commandId=command['commandId'],processId=native.pid);return native
        def execute(session,operation,arguments):
            self.assertEqual('native-session',session);self.assertEqual('mobile: pullFile',operation)
            self.assertEqual({'remotePath':'@org.example.client:documents/owned-results/'+dom.FILE},arguments)
            reads.append(arguments);return base64.b64encode(json.dumps(native.value).encode()).decode()
        native.execute=execute;clock=SimpleNamespace(sequence=0,read=lambda _:dict(capturedEpochMs=epoch))
        with patch.object(feature_observation,'post_request',side_effect=post):value=observer.tablet_web_dom(clock).read(RUN,ROOT)
        self.assertEqual(native.pid,value['processId']);self.assertEqual(1,len(commands));self.assertEqual(1,len(reads))
        self.assertEqual(commands[0]['commandId'],value['source']['dom']['requestId']);self.assertEqual(value,native.value)


if __name__=='__main__':unittest.main()
