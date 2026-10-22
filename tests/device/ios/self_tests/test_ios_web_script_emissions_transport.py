"""Real shared probe/Fixture/AFC routes preserve the independent emitter DTO."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
import json
import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from fixture.serve import FixtureState
from ios.adapters import feature_observation,web_script_emissions as source
from ios.self_tests.test_ios_feature_observation import Native
from ios.self_tests.test_ios_web_script_emissions import Emitter,query
from ios.self_tests.test_ios_tablet_web_sources import RUN,ROOT
from self_tests.test_native_feature_observation import probe_source


class WebScriptEmissionTransportTests(unittest.TestCase):
    def test_fixture_accepts_only_actual_query_without_expected_caller_message_or_delivery(self):
        native=Emitter();q=query(native.snapshot());fixture=FixtureState();self.assertEqual(q,fixture.set_client_command(q))
        for edit in ({'caller':{}},{'message':'expected reply'},{'expectedDelivered':True},{'schemaVersion':True}):
            with self.subTest(edit=edit),self.assertRaises(ValueError):fixture.set_client_command(q|edit)

    def test_actual_probe_keeps_exact_API_stack_weak_capture_and_missing_source_unavailable_without_replay(self):
        native=Emitter();native.good();original=native.snapshot()
        program='''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,keys)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(keys.sort());
const original=PACKET;let calls=0,files=[];
const Test={featureIOSWebScriptEmissions:q=>{calls++;return {...original,commandId:q.commandId};},saveObject:(v,name)=>files.push({v,name})};
SOURCE
const q=QUERY;applyClientCommand(q);applyClientCommand(q);applyClientCommand({...q,commandId:"ios-"+"c".repeat(32)});applyClientCommand(q);
if(calls!==2||files.length!==2||files[0].name!=="feature-ios-web-script-emissions.json")throw Error("source query replay");
for(const key of ["calls","queues","sinks","objects"])if(JSON.stringify(files[0].v[key])!==JSON.stringify(original[key]))throw Error("native emitter original changed");
applyClientCommand({...q,commandId:"ios-"+"d".repeat(32),caller:{}});if(calls!==2)throw Error("expected caller accepted");
delete Test.featureIOSWebScriptEmissions;applyClientCommand({...q,commandId:"ios-"+"e".repeat(32)});
if(files.at(-1).v.complete!==false||files.at(-1).v.calls)throw Error("missing source became clean empty emissions");
'''.replace('PACKET',json.dumps(original)).replace('QUERY',json.dumps(query(original))).replace('SOURCE',probe_source())
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5);self.assertEqual(0,result.returncode,result.stderr)

    def test_actual_FeatureObservation_AFC_route_keeps_native_compiled_caller_and_distinct_instance(self):
        native=Native();observer=native.observer();commands=[];reads=[];producer=Emitter();producer.good()
        def post(request,timeout):
            command=native.fixture.set_client_command(json.loads(request.data));commands.append(command);native.echo=json.dumps(command).encode()
            native.value=producer.snapshot();native.value.update(commandId=command['commandId'],processId=native.pid);return native
        def execute(session,operation,arguments):
            self.assertEqual('native-session',session);self.assertEqual('mobile: pullFile',operation)
            self.assertEqual({'remotePath':'@org.example.client:documents/owned-results/'+source.FILE},arguments)
            reads.append(arguments);return base64.b64encode(json.dumps(native.value).encode()).decode()
        native.execute=execute;clock=SimpleNamespace(sequence=0,read=lambda _:dict(capturedEpochMs=producer.now))
        with patch.object(feature_observation,'post_request',side_effect=post):value=observer.web_script_emissions(clock).read(RUN,ROOT)
        self.assertEqual(1,len(commands));self.assertEqual(1,len(reads));self.assertEqual(native.value,value)
        self.assertEqual('e'*32,value['instance']);self.assertEqual(71,value['calls'][0]['caller']['emitStack']['frames'][0]['scriptId'])
        # producer.good() returned its only strong host capture to an ignored
        # temporary. The actual weak source therefore observes its expiry.
        self.assertFalse(value['queues'][0]['captureAlive']);self.assertIsNotNone(value['queues'][0]['expired'])


if __name__=='__main__':unittest.main()
