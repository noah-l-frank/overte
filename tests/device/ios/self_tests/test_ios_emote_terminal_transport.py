"""Actual closed JS/fixture/iOS AFC routes, with native sources replaced."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
import json
import subprocess
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from adapters import native_script_terminal as terminal
from adapters.normal_ui import NativeUIError
from fixture.serve import FixtureState
from ios.adapters import feature_observation
from ios.self_tests.test_ios_feature_observation import Native
from self_tests.test_native_feature_observation import probe_source
from self_tests.test_native_script_terminal import packet
from self_tests.test_native_script_work import WorkBoundary,MANAGER


class TerminalTransportTests(unittest.TestCase):
    def test_fixture_rejects_expected_work_stop_code_and_boolean_version(self):
        fixture=FixtureState()
        for action in (terminal.ACTION,'feature-script-work-observe'):
            query=dict(schemaVersion=1,commandId='ios-'+'a'*32,action=action)
            if action.endswith('work-observe'):query['managerInstance']=MANAGER
            self.assertEqual(query,fixture.set_client_command(query))
            for edit in (dict(expectedTimers=0),dict(stop=True),dict(code='Script.stop()'),dict(schemaVersion=True)):
                with self.subTest(action=action,edit=edit),self.assertRaises(ValueError):fixture.set_client_command(query|edit)

    def test_actual_probe_keeps_original_terminal_prefix_and_never_reexecutes_an_old_nonce(self):
        script='''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,keys)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(keys.sort());
let calls=0,files=[];const original=PACKET;
const Test={featureScriptTerminal:q=>{calls++;return {...original,commandId:q.commandId};},saveObject:(v,name)=>files.push({v,name})};
SOURCE
const q={schemaVersion:1,commandId:"ios-"+"a".repeat(32),action:"feature-script-terminal-observe"};
applyClientCommand(q);applyClientCommand(q);
applyClientCommand({...q,commandId:"ios-"+"b".repeat(32)});applyClientCommand(q);
if(calls!==2||files.length!==2||files[0].name!=="feature-script-terminal.json")throw Error("native read replay");
if(JSON.stringify(files[0].v.source)!==JSON.stringify(original.source))throw Error("source retimed/rewritten");
applyClientCommand({...q,commandId:"ios-"+"c".repeat(32),expectedTimers:0});if(calls!==2)throw Error("desired state accepted");
delete Test.featureScriptTerminal;applyClientCommand({...q,commandId:"ios-"+"d".repeat(32)});
if(files.at(-1).v.available!==false||files.at(-1).v.source)throw Error("missing source green");
'''.replace('PACKET',json.dumps(packet())).replace('SOURCE',probe_source())
        result=subprocess.run(['node','-e',script],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)

    def test_actual_probe_pending_work_polls_same_native_query_without_rewriting_originals(self):
        boundary=WorkBoundary();query=dict(schemaVersion=1,commandId='ios-'+'a'*32,
            action='feature-script-work-observe',managerInstance=MANAGER);boundary.send(query)
        script='''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,keys)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(keys.sort());
let calls=[],files=[],timers=[];const original=PACKET;
const Script={setTimeout:f=>{timers.push(f);return timers.length;},clearTimeout:()=>{}};
const Test={featureScriptWork:q=>{calls.push(JSON.stringify(q));return calls.length===1?
 {schemaVersion:1,requestId:q.commandId,pending:true}:original;},saveObject:(v,name)=>files.push({v,name})};
SOURCE
const q=QUERY;applyClientCommand(q);applyClientCommand(q);
if(calls.length!==1||files.length!==0||timers.length!==1)throw Error("pending is not original work");
timers.shift()();applyClientCommand(q);
if(calls.length!==2||calls[0]!==calls[1]||files.length!==1||files[0].name!=="feature-script-work.json")throw Error("pending retry source");
if(JSON.stringify(files[0].v)!==JSON.stringify(original))throw Error("original work changed");
applyClientCommand({...q,commandId:"ios-"+"b".repeat(32),expectedTimers:0});if(calls.length!==2)throw Error("desired work accepted");
'''.replace('PACKET',json.dumps(boundary.value)).replace('QUERY',json.dumps(query)).replace('SOURCE',probe_source())
        result=subprocess.run(['node','-e',script],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)

    def test_actual_FeatureObservation_factories_use_bound_AFC_paths_and_native_clocks(self):
        for kind in ('terminal','work'):
            with self.subTest(kind=kind):
                native=Native();observer=native.observer();commands=[];reads=[]
                def post(request,timeout):
                    query=native.fixture.set_client_command(json.loads(request.data));commands.append(query)
                    native.echo=json.dumps(query).encode()
                    if kind=='terminal':
                        value=packet();value['commandId']=query['commandId'];value['source']['processId']=native.pid
                    else:
                        boundary=WorkBoundary();boundary.send(query);value=boundary.value
                    value['processId']=native.pid;native.value=value;return native
                def execute(session,operation,arguments):
                    self.assertEqual('native-session',session);self.assertEqual('mobile: pullFile',operation)
                    filename='feature-script-'+kind+'.json';self.assertEqual({'remotePath':
                        '@org.example.client:documents/owned-results/'+filename},arguments)
                    reads.append(arguments);return base64.b64encode(json.dumps(native.value).encode()).decode()
                native.execute=execute;clock=SimpleNamespace(sequence=0,read=lambda _:dict(capturedEpochMs=20000))
                with patch.object(feature_observation,'post_request',side_effect=post):
                    reader=observer.script_terminal(clock) if kind=='terminal' else observer.script_work(clock)
                    value=reader.read(0) if kind=='terminal' else reader.read(MANAGER)
                self.assertEqual(native.pid,value['processId']);self.assertEqual(20000,value['capturedEpochMs'])
                self.assertEqual(1,len(commands));self.assertEqual(1,len(reads))


if __name__=='__main__':unittest.main()
