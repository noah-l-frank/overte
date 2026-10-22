"""Actual JS/fixture/FeatureObservation/AFC routes; no native execution."""
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
from ios.adapters import tablet_web_buttons as source
from ios.self_tests.test_ios_feature_observation import Native
from ios.self_tests.test_ios_tablet_web_buttons import Boundary,RUN,ROOT
from self_tests.test_native_feature_observation import probe_source


def query(index=1):return dict(schemaVersion=1,action=source.ACTION,commandId='ios-'+format(index,'032x'),runId=RUN,fixtureUrl=ROOT)


class TabletWebButtonsTransportTests(unittest.TestCase):
    def test_real_fixture_requires_closed_passive_query_and_no_expected_button_properties(self):
        fixture=FixtureState();self.assertEqual(query(),fixture.set_client_command(query()))
        for edit in ({'expectedButtons':[]},{'semanticId':'tablet-web-app.open'},{'remove':True},{'schemaVersion':True},{'fixtureUrl':ROOT+'foreign/'}):
            with self.subTest(edit=edit),self.assertRaises(ValueError):fixture.set_client_command(query()|edit)

    def test_actual_node_probe_keeps_returned_caller_and_weak_lives_without_replaying_nonce(self):
        boundary=Boundary();key=boundary.add();boundary.bind(key);original=boundary.snapshot()
        program='''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,keys)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(keys.sort());
const original=PACKET;let calls=0,files=[];
const Test={featureIOSTabletAppButtons:q=>{calls++;return {...original,commandId:q.commandId};},saveObject:(v,name)=>files.push({v,name})};
SOURCE
const q=QUERY;applyClientCommand(q);applyClientCommand(q);
applyClientCommand({...q,commandId:"ios-"+"c".repeat(32)});applyClientCommand(q);
if(calls!==2||files.length!==2||files[0].name!=="feature-ios-tablet-app-buttons.json")throw Error("source query replay");
if(JSON.stringify(files[0].v.buttons)!==JSON.stringify(original.buttons)||JSON.stringify(files[0].v.controls)!==JSON.stringify(original.controls))throw Error("native button/VM/weak original changed");
applyClientCommand({...q,commandId:"ios-"+"d".repeat(32),expectedButtons:[]});if(calls!==2)throw Error("expected button result accepted");
delete Test.featureIOSTabletAppButtons;applyClientCommand({...q,commandId:"ios-"+"e".repeat(32)});
if(files.at(-1).v.complete!==false||files.at(-1).v.buttons)throw Error("missing source became empty button inventory");
'''.replace('PACKET',json.dumps(original)).replace('QUERY',json.dumps(query())).replace('SOURCE',probe_source())
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)

    def test_real_FeatureObservation_factory_preserves_AFC_source_and_independent_native_clock(self):
        native=Native();observer=native.observer();commands=[];reads=[];boundary=Boundary();key=boundary.add();boundary.bind(key)
        def post(request,timeout):
            command=native.fixture.set_client_command(json.loads(request.data));commands.append(command);native.echo=json.dumps(command).encode()
            native.value=boundary.snapshot();native.value.update(commandId=command['commandId'],processId=native.pid);return native
        def execute(session,operation,arguments):
            self.assertEqual('native-session',session);self.assertEqual('mobile: pullFile',operation)
            self.assertEqual({'remotePath':'@org.example.client:documents/owned-results/'+source.FILE},arguments)
            reads.append(arguments);return base64.b64encode(json.dumps(native.value).encode()).decode()
        native.execute=execute;clock=SimpleNamespace(sequence=0,read=lambda _:dict(capturedEpochMs=boundary.tick()['epochMs']))
        with patch.object(feature_observation,'post_request',side_effect=post):value=observer.tablet_web_buttons(clock).read(RUN,ROOT)
        self.assertEqual(native.pid,value['processId']);self.assertEqual(1,len(commands));self.assertEqual(1,len(reads))
        self.assertEqual(native.value['buttons'],value['buttons']);self.assertEqual(native.value['rootInstance'],value['rootInstance'])


if __name__=='__main__':unittest.main()
