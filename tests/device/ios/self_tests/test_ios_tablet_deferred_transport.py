"""Actual shared JS/fixture/AFC dispatch; modeled native source only."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import json
import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from fixture.serve import FixtureState
from ios.adapters import feature_observation
from ios.adapters import tablet_web_deferred as source
from ios.self_tests.test_ios_feature_observation import Native
from ios.self_tests.test_ios_tablet_web_deferred import packet,query,fault,RUN,ROOT
from self_tests.test_native_feature_observation import probe_source


class TabletDeferredTransportTests(unittest.TestCase):
    def test_actual_fixture_accepts_only_closed_passive_source_query(self):
        fixture=FixtureState();self.assertEqual(query(),fixture.set_client_command(query()))
        for edit in ({'expectedDeferredMessages':0},{'html':'expected input'}, {'close':True},{'schemaVersion':True}):
            with self.subTest(edit=edit),self.assertRaises(ValueError):fixture.set_client_command(query()|edit)

    def test_actual_node_probe_preserves_originals_and_never_reexecutes_old_nonce(self):
        program='''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,keys)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(keys.sort());
const original=PACKET;let calls=0,files=[];
const Test={featureIOSTabletWebDeferred:q=>{calls++;return {...original,commandId:q.commandId};},saveObject:(v,name)=>files.push({v,name})};
SOURCE
const q=QUERY;applyClientCommand(q);applyClientCommand(q);
applyClientCommand({...q,commandId:"ios-"+"c".repeat(32)});applyClientCommand(q);
if(calls!==2||files.length!==2||files[0].name!=="feature-ios-tablet-web-deferred.json")throw Error("source replay");
if(JSON.stringify(files[0].v.records)!==JSON.stringify(original.records))throw Error("native inputs rewritten/retimed");
applyClientCommand({...q,commandId:"ios-"+"d".repeat(32),expectedDeferredMessages:0});if(calls!==2)throw Error("expected result accepted");
delete Test.featureIOSTabletWebDeferred;applyClientCommand({...q,commandId:"ios-"+"e".repeat(32)});
if(files.at(-1).v.complete!==false||files.at(-1).v.records)throw Error("missing source became absence");
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
        native.execute=execute;clock=SimpleNamespace(sequence=0,read=lambda _:dict(capturedEpochMs=90650))
        with patch.object(feature_observation,'post_request',side_effect=post):
            value=observer.tablet_web_deferred(clock).read(RUN,ROOT)
        self.assertEqual(native.pid,value['processId']);self.assertEqual(1,len(commands));self.assertEqual(1,len(reads))
        self.assertEqual(packet()['records'],value['records'])


class TabletDeferFaultTransportTests(unittest.TestCase):
    def test_actual_fixture_closed_fault_request_accepts_owned_record_but_no_expected_bytes(self):
        fixture=FixtureState()
        for operation in ('arm','deliver','discard'):
            value=fault(operation);self.assertEqual(value,fixture.set_client_command(value))
        for value in (fault('deliver')|{'recordId':None},fault('arm')|{'recordId':'c'*32},
                fault('deliver')|{'envelope':'expected'},fault('discard')|{'expectedPending':0}):
            with self.subTest(value=value),self.assertRaises(ValueError):fixture.set_client_command(value)

    def test_actual_node_fault_once_nonce_preserves_original_receipt_and_unknown_never_replays(self):
        program='''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,keys)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(keys.sort());
const original=RECEIPT;let calls=0,files=[];
const Test={featureIOSTabletWebDefer:q=>{calls++;return {...original,command:q};},saveObject:(v,name)=>files.push({v,name})};
SOURCE
const q=QUERY;applyClientCommand(q);applyClientCommand(q);
if(calls!==1||files.length!==1||files[0].name!=="feature-ios-tablet-web-defer.json")throw Error("fault replay");
if(JSON.stringify(files[0].v.issued)!==JSON.stringify(original.issued)||files[0].v.record!==original.record)throw Error("fault retimed/relabelled");
applyClientCommand({...q,commandId:"ios-"+"d".repeat(32),envelope:"expected"});if(calls!==1)throw Error("supplied replay payload accepted");
Test.featureIOSTabletWebDefer=q=>{calls++;throw Error("original command return lost")};
const lost={...q,commandId:"ios-"+"e".repeat(32)};applyClientCommand(lost);applyClientCommand(lost);
if(calls!==2||files.at(-1).v.status!=="unavailable"||files.at(-1).v.record)throw Error("unknown fault retried/forged empty");
'''.replace('RECEIPT',json.dumps(packet(2,'delivered')['commands'][1])).replace('QUERY',json.dumps(fault('deliver',2))).replace('SOURCE',probe_source())
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)

    def test_actual_fault_factory_reads_original_AFC_receipt_and_native_epoch_without_invented_timer(self):
        native=Native();observer=native.observer();calls=[];reads=[]
        def post(request,timeout):
            value=native.fixture.set_client_command(json.loads(request.data));calls.append(value);native.echo=json.dumps(value).encode()
            native.value=deepcopy(packet(2,'delivered')['commands'][1]);native.value['command']=value;return native
        def execute(session,operation,arguments):
            self.assertEqual('native-session',session);self.assertEqual('mobile: pullFile',operation)
            self.assertEqual({'remotePath':'@org.example.client:documents/owned-results/'+source.FAULT_FILE},arguments)
            reads.append(arguments);return base64.b64encode(json.dumps(native.value).encode()).decode()
        native.execute=execute;epochs=iter((90699,90702));clock=SimpleNamespace(sequence=0,read=lambda _:dict(capturedEpochMs=next(epochs)))
        before=packet();before['processId']=native.pid
        with patch.object(feature_observation,'post_request',side_effect=post):
            value=observer.tablet_web_defer(clock).issue(fault('deliver',2),before)
        self.assertEqual('delivered',value['status']);self.assertEqual(fault('deliver',2),calls[0]);self.assertEqual(1,len(calls));self.assertEqual(1,len(reads))


if __name__=='__main__':unittest.main()
