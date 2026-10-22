"""Actual shared JS/fixture/AFC dispatch; modeled native source only."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
import json
import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from fixture.serve import FixtureState
from ios.adapters import feature_observation
from ios.adapters import tablet_web_source as source
from ios.self_tests.test_ios_feature_observation import Native
from ios.self_tests.test_ios_tablet_web_source import packet,query,RUN,ROOT
from self_tests.test_native_feature_observation import probe_source


class TabletTraceTransportTests(unittest.TestCase):
    def test_actual_fixture_accepts_only_closed_passive_source_query(self):
        fixture=FixtureState();self.assertEqual(query(),fixture.set_client_command(query()))
        for edit in ({'expectedInlineLeases':0},{'html':'expected input'}, {'close':True},{'schemaVersion':True}):
            with self.subTest(edit=edit),self.assertRaises(ValueError):fixture.set_client_command(query()|edit)

    def test_actual_node_probe_preserves_originals_and_never_reexecutes_old_nonce(self):
        program='''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,keys)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(keys.sort());
const original=PACKET;let calls=0,files=[];
const Test={featureIOSTabletWeb:q=>{calls++;return {...original,commandId:q.commandId};},saveObject:(v,name)=>files.push({v,name})};
SOURCE
const q=QUERY;applyClientCommand(q);applyClientCommand(q);
applyClientCommand({...q,commandId:"ios-"+"c".repeat(32)});applyClientCommand(q);
if(calls!==2||files.length!==2||files[0].name!=="feature-ios-tablet-web.json")throw Error("source replay");
if(JSON.stringify(files[0].v.events)!==JSON.stringify(original.events))throw Error("native inputs rewritten/retimed");
applyClientCommand({...q,commandId:"ios-"+"d".repeat(32),expectedInlineLeases:0});if(calls!==2)throw Error("expected result accepted");
delete Test.featureIOSTabletWeb;applyClientCommand({...q,commandId:"ios-"+"e".repeat(32)});
if(files.at(-1).v.complete!==false||files.at(-1).v.events)throw Error("missing source became absence");
'''.replace('PACKET',json.dumps(packet())).replace('QUERY',json.dumps(query())).replace('SOURCE',probe_source())
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)

    def test_actual_FeatureObservation_factory_uses_original_AFC_file_and_native_clock(self):
        native=Native();observer=native.observer();commands=[];reads=[]
        def post(request,timeout):
            command=native.fixture.set_client_command(json.loads(request.data));commands.append(command);native.echo=json.dumps(command).encode()
            native.value=packet(len(commands));native.value.update(commandId=command['commandId'],processId=native.pid);return native
        def execute(session,operation,arguments):
            self.assertEqual('native-session',session);self.assertEqual('mobile: pullFile',operation)
            self.assertEqual({'remotePath':'@org.example.client:documents/owned-results/'+source.FILE},arguments)
            reads.append(arguments);return base64.b64encode(json.dumps(native.value).encode()).decode()
        native.execute=execute;clock=SimpleNamespace(sequence=0,read=lambda _:dict(capturedEpochMs=91000))
        with patch.object(feature_observation,'post_request',side_effect=post):
            value=observer.tablet_web(clock).read(RUN,ROOT)
        self.assertEqual(native.pid,value['processId']);self.assertEqual(1,len(commands));self.assertEqual(1,len(reads))
        self.assertEqual(packet()['events'],value['events'])
