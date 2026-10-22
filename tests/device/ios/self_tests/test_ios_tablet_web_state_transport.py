"""Actual shared passive route with unchanged native state originals."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
import json
import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from fixture.serve import FixtureState
from ios.adapters import feature_observation,tablet_web_state as state
from ios.self_tests.test_ios_feature_observation import Native
from ios.self_tests.test_ios_tablet_web_state import packet,query,RUN,ROOT
from self_tests.test_native_feature_observation import probe_source


class TabletWebStateTransportTests(unittest.TestCase):
    def test_fixture_only_accepts_closed_passive_query_without_a_requested_closed_state(self):
        fixture=FixtureState();self.assertEqual(query(),fixture.set_client_command(query()))
        for edit in ({'closed':True},{'expectedWindows':[]},{'tearDown':True},{'schemaVersion':True}):
            with self.subTest(edit=edit),self.assertRaises(ValueError):fixture.set_client_command(query()|edit)

    def test_actual_probe_keeps_current_weak_attached_flags_and_does_not_replay_queries(self):
        original,_=packet(attached=True)
        program='''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,keys)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(keys.sort());
const original=PACKET;let calls=0,files=[];
const Test={featureIOSTabletWebState:q=>{calls++;return {...original,commandId:q.commandId};},saveObject:(v,name)=>files.push({v,name})};
SOURCE
const q=QUERY;applyClientCommand(q);applyClientCommand(q);
applyClientCommand({...q,commandId:"ios-"+"c".repeat(32)});applyClientCommand(q);
if(calls!==2||files.length!==2||files[0].name!=="feature-ios-tablet-web-state.json")throw Error("source query replay");
if(JSON.stringify(files[0].v.targets)!==JSON.stringify(original.targets)||!files[0].v.targets[0].windowAttached)throw Error("native attached target changed");
applyClientCommand({...q,commandId:"ios-"+"d".repeat(32),closed:true});if(calls!==2)throw Error("expected closed value accepted");
delete Test.featureIOSTabletWebState;applyClientCommand({...q,commandId:"ios-"+"e".repeat(32)});
if(files.at(-1).v.complete!==false||files.at(-1).v.targets)throw Error("missing native source became detached empty inventory");
'''.replace('PACKET',json.dumps(original)).replace('QUERY',json.dumps(query())).replace('SOURCE',probe_source())
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)

    def test_actual_FeatureObservation_AFC_route_keeps_native_instance_and_detachment_original(self):
        native=Native();observer=native.observer();commands=[];reads=[]
        def post(request,timeout):
            command=native.fixture.set_client_command(json.loads(request.data));commands.append(command);native.echo=json.dumps(command).encode()
            native.value,_=packet(len(commands));native.value.update(commandId=command['commandId'],processId=native.pid);return native
        def execute(session,operation,arguments):
            self.assertEqual('native-session',session);self.assertEqual('mobile: pullFile',operation)
            self.assertEqual({'remotePath':'@org.example.client:documents/owned-results/'+state.FILE},arguments)
            reads.append(arguments);return base64.b64encode(json.dumps(native.value).encode()).decode()
        native.execute=execute;clock=SimpleNamespace(sequence=0,read=lambda _:dict(capturedEpochMs=90621))
        with patch.object(feature_observation,'post_request',side_effect=post):value=observer.tablet_web_state(clock).read(RUN,ROOT)
        self.assertEqual(1,len(commands));self.assertEqual(1,len(reads));self.assertEqual(native.value,value)
        self.assertTrue(value['targets'][0]['alive']);self.assertFalse(value['targets'][0]['windowAttached'])


if __name__=='__main__':unittest.main()
