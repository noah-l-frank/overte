"""Original native dialog DTOs; native instrumentation remains uncompiled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import json
import subprocess
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from fixture.serve import FixtureState
from ios.adapters import script_dialogs as dialogs,feature_observation
from ios.self_tests.test_ios_feature_observation import Native
from ios.self_tests.test_ios_emote_sources import RUN
from self_tests.test_native_feature_observation import probe_source


def packet(sequence=1,events=None):
    return dict(iosScriptDialogVersion=1,requestId='ios-'+format(sequence,'032x'),runId=RUN,instance='e'*32,sequence=sequence,
        processId=31,clockDomain='native-main-script-dialog',clockBefore=dict(epochMs=20000+sequence,monotonicMs=1000+sequence),
        clockAfter=dict(epochMs=20000+sequence,monotonicMs=1000+sequence),source=dict(scriptDialogLedgerVersion=1,instance='f'*32,
            processId=31,complete=True,eventSequence=len(events or []),events=deepcopy(events or [])))


def events(text='',exists=False,manager=None):
    rows=[]
    for kind in ('listener-created','response-entered','response-returned','listener-destroyed'):
        rows.append(dict(eventSequence=len(rows)+1,capturedEpochMs=20001,monotonicMs=1001,dialogInstance='a'*32,
            kind=kind,response=dict(text=text,encoding='utf-16le-code-units',codeUnits=len(text.encode('utf-16le'))//2,
            sha256=hashlib.sha256(text.encode('utf-16le')).hexdigest()) if kind=='response-entered' else None,
            fileExists=exists if kind=='response-entered' else None,manager=manager if kind=='response-returned' else None))
    return rows


class ScriptDialogTests(unittest.TestCase):
    def test_cancelled_original_response_returns_without_inventing_a_manager(self):
        before=packet();after=packet(2,events())
        result=dialogs.completed(after,before,after_epoch=20001)
        self.assertEqual('',result['entered']['response']['text']);self.assertIsNone(result['returned']['manager'])
    def test_destroyed_listener_alone_is_not_a_drained_response_callback(self):
        rows=events();rows=[rows[0],rows[-1]];rows[-1]['eventSequence']=2
        with self.assertRaises(NativeUIError):dialogs.completed(packet(2,rows),packet(),after_epoch=20001)
    def test_changed_prefix_retimed_callback_or_ambiguous_listener_cannot_be_adopted(self):
        before=packet(1,events()[:1]);after=packet(2,events())
        for fault in ('rewrite','retime','incomplete','duplicate','foreignpid'):
            current=deepcopy(after);prior=packet() if fault!='rewrite' else before
            if fault=='rewrite':current['source']['events'][0]['capturedEpochMs']=20000
            elif fault=='retime':current['source']['events'][1]['response']['text']='requested.js'
            elif fault=='incomplete':current['source']['complete']=False
            elif fault=='foreignpid':current['source']['processId']=32
            else:
                row=deepcopy(current['source']['events'][0]);row.update(eventSequence=5,dialogInstance='b'*32)
                current['source']['events'].append(row);current['source']['eventSequence']=5
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):dialogs.completed(current,prior,after_epoch=20001)
    def test_empty_response_never_has_a_real_existing_selected_file(self):
        with self.assertRaises(NativeUIError):dialogs.completed(packet(2,events(exists=True)),packet(),after_epoch=20001)
    def test_actual_fixture_and_probe_keep_closed_read_and_never_reissue_nonce(self):
        query=dict(schemaVersion=1,commandId='ios-'+'a'*32,action=dialogs.ACTION,runId=RUN);fixture=FixtureState()
        self.assertEqual(query,fixture.set_client_command(query))
        for edit in (dict(expected='cancelled'),dict(sourceUrl='file:///wanted.js'),dict(schemaVersion=True)):
            with self.assertRaises(ValueError):fixture.set_client_command(query|edit)
        script='''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,keys)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(keys.sort());
let calls=0,files=[];const original=PACKET;
const Test={featureIOSScriptDialogs:q=>{calls++;return {...original,requestId:q.commandId};},saveObject:(v,name)=>files.push({v,name})};
SOURCE
const q=QUERY;applyClientCommand(q);applyClientCommand(q);
if(calls!==1||files.length!==1||files[0].name!=="feature-ios-script-dialogs.json")throw Error("read replay/source");
if(JSON.stringify(files[0].v.source)!==JSON.stringify(original.source))throw Error("rewritten original");
applyClientCommand({...q,commandId:"ios-"+"b".repeat(32),expected:"cancelled"});if(calls!==1)throw Error("wanted result");
delete Test.featureIOSScriptDialogs;applyClientCommand({...q,commandId:"ios-"+"c".repeat(32)});
if(files.at(-1).v.status!=="unavailable")throw Error("missing source green");
'''.replace('PACKET',json.dumps(packet(2,events()))).replace('QUERY',json.dumps(query)).replace('SOURCE',probe_source())
        result=subprocess.run(['node','-e',script],capture_output=True,text=True,timeout=5);self.assertEqual(0,result.returncode,result.stderr)
    def test_existing_observer_factory_reads_actual_AFC_path_and_native_clock(self):
        native=Native();observer=native.observer();native.value=None
        def post(request,timeout):
            query=native.fixture.set_client_command(json.loads(request.data));native.echo=json.dumps(query).encode()
            native.value=packet(2,events());native.value.update(requestId=query['commandId'],processId=native.pid)
            native.value['source']['processId']=native.pid;return native
        def execute(session,operation,arguments):
            self.assertEqual('native-session',session);self.assertEqual('mobile: pullFile',operation)
            self.assertEqual({'remotePath':'@org.example.client:documents/owned-results/'+dialogs.FILE},arguments)
            return base64.b64encode(json.dumps(native.value).encode()).decode()
        native.execute=execute;clock=SimpleNamespace(sequence=0,read=lambda _:dict(capturedEpochMs=20002))
        with patch.object(feature_observation,'post_request',side_effect=post):value=observer.script_dialogs(clock).read(RUN)
        self.assertEqual(4,value['source']['eventSequence'])


if __name__=='__main__':unittest.main()
