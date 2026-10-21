"""Synthetic originals and actual JS source execution; no native build/device access."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import unittest
from adapters.native_tablet_http import NativeTabletHttp,command,continuity,released,validate
from adapters.normal_ui import NativeUIError
from self_tests.test_native_feature_observation import probe_source

RUN='b'*32
ROOT='c'*32
LEASE='d'*32
REPLY='e'*32
REPO=Path(__file__).resolve().parents[3]


def native_state(**changes):
    value=dict(readyState=4,errorCode=0,status=200,timerActive=False,readyHandler=False,timeoutHandler=False,callbackDepth=0)
    value.update(changes);return value


def root(**changes):
    value=dict(id=ROOT,sourceSha256='a'*64,helperAlive=False,rootAlive=False,inCurrentTree=False,callbackIds=None,callbackDepth=None)
    value.update(changes);return value


def request_row():
    value=dict(id=LEASE,rootId=ROOT,qmlRequestId=0,paramsSha256='f'*64,queuedEpochMs=20000,
        events=[],bound=True,requestAlive=True,state=None,replies=[],destroyed=False)
    add_event(value,'bound',native_state(readyState=0,status=None))
    add_event(value,'state',native_state(readyState=1,readyHandler=True,status=None))
    add_event(value,'reply',reply=REPLY)
    value['replies']=[dict(id=REPLY,createdEpochMs=20000,urlSha256='a'*64,alive=True,destroyed=False)]
    add_event(value,'callback-enter',native_state(readyHandler=True,callbackDepth=1))
    add_event(value,'state',native_state(callbackDepth=1))
    add_event(value,'callback-exit',native_state())
    return value


def add_event(row,kind,state=None,reply=None):
    row['events'].append(dict(sequence=len(row['events'])+1,kind=kind,occurredEpochMs=20000,
        receivedEpochMs=20000,state=deepcopy(state),replyId=reply))
    if state is not None:row['state']=deepcopy(state)
    if kind=='reply-destroyed':
        item=next(value for value in row['replies'] if value['id']==reply);item.update(alive=False,destroyed=True)
    if kind=='destroyed':row.update(destroyed=True,requestAlive=False)


class Boundary:
    def __init__(self):
        self.clock=0.;self.epoch=20000;self.okay=True;self.sequence=0;self.roots=[root()];self.rows=[request_row()]
        self.complete=True;self.sample=None;self.commands=[];self.edit=None;self.ignore=False
    def send(self,request):
        command(request);self.commands.append(deepcopy(request))
        if self.ignore:return
        self.sequence+=1
        self.sample=dict(tabletHttpVersion=1,commandId=request['commandId'],runId=request['runId'],instance='a'*32,
            sequence=self.sequence,processId=31,capturedEpochMs=self.epoch,complete=self.complete,containerPresent=True,
            roots=deepcopy(self.roots),requests=deepcopy(self.rows))
        if self.edit:self.edit(self.sample)
    def original(self):return json.dumps(self.sample) if self.sample is not None else ''
    def sleep(self,seconds):self.clock+=seconds
    def reader(self):return NativeTabletHttp(self.send,self.original,lambda:self.epoch,lambda:self.okay,31,
        monotonic=lambda:self.clock,sleep=self.sleep)
    def retire_reply(self):add_event(self.rows[0],'reply-destroyed',reply=REPLY)


class TabletHttpTests(unittest.TestCase):
    def test_completed_response_does_not_release_original_reply(self):
        source=Boundary();reader=source.reader();value=reader.read(RUN)
        self.assertEqual(source.sample,value)
        with self.assertRaises(NativeUIError):released(value)
        source.retire_reply();self.assertTrue(released(reader.read(RUN)))
        self.assertEqual(2,len(source.commands));self.assertEqual(20000,value['capturedEpochMs'])
        self.assertEqual({'schemaVersion','commandId','action','runId'},set(source.commands[0]))

    def test_hidden_retained_qml_root_empty_map_and_active_qml_callback_block_retirement(self):
        for changes in (dict(callbackIds=[]),dict(callbackIds=[0]),dict(callbackIds=[],callbackDepth=1)):
            source=Boundary();source.retire_reply();source.roots=[root(helperAlive=True,rootAlive=True,
                callbackIds=[],callbackDepth=0,**{k:v for k,v in changes.items() if k not in ('callbackIds','callbackDepth')})]
            source.roots[0].update(changes)
            reader=source.reader()
            with self.subTest(changes=changes),self.assertRaises(NativeUIError):released(reader.read(RUN))
            source.roots=[root()];self.assertTrue(released(reader.read(RUN)))

    def test_actual_native_callback_handler_timer_and_depth_are_each_required(self):
        for changes in (dict(timerActive=True),dict(readyHandler=True),dict(timeoutHandler=True)):
            source=Boundary();source.retire_reply();add_event(source.rows[0],'state',native_state(**changes));reader=source.reader()
            with self.subTest(changes=changes),self.assertRaises(NativeUIError):released(reader.read(RUN))
            add_event(source.rows[0],'state',native_state());self.assertTrue(released(reader.read(RUN)))
        source=Boundary();source.retire_reply();add_event(source.rows[0],'callback-enter',native_state(callbackDepth=1));reader=source.reader()
        with self.assertRaises(NativeUIError):released(reader.read(RUN))
        add_event(source.rows[0],'callback-exit',native_state());self.assertTrue(released(reader.read(RUN)))

    def test_destroyed_xhr_does_not_hide_reply_or_unacknowledged_destruction(self):
        source=Boundary();source.rows[0]['requestAlive']=False;reader=source.reader()
        with self.assertRaises(NativeUIError):released(reader.read(RUN))
        add_event(source.rows[0],'destroying',native_state(readyHandler=True,timerActive=True))
        add_event(source.rows[0],'destroyed')
        with self.assertRaises(NativeUIError):released(reader.read(RUN))
        source.retire_reply();self.assertTrue(released(reader.read(RUN)))

    def test_missing_binding_and_unobserved_original_reply_retirement_stay_unresolved(self):
        source=Boundary();source.rows[0].update(events=[],bound=False,state=None,replies=[],requestAlive=None)
        with self.assertRaises(NativeUIError):released(source.reader().read(RUN))
        source=Boundary();source.rows[0]['replies'][0]['alive']=False
        with self.assertRaises(NativeUIError):released(source.reader().read(RUN))

    def test_continuity_retains_request_root_reply_event_and_source_identity(self):
        changes=[lambda v:v['requests'].clear(),lambda v:v['roots'].clear(),
            lambda v:v['roots'][0].update(sourceSha256='b'*64),lambda v:v['requests'][0].update(paramsSha256='b'*64),
            lambda v:v['requests'][0]['replies'][0].update(urlSha256='b'*64),
            lambda v:v['requests'][0]['events'][0].update(receivedEpochMs=19999),
            lambda v:v.update(instance='b'*32),lambda v:v.update(sequence=1)]
        for edit in changes:
            source=Boundary();reader=source.reader();reader.read(RUN);source.edit=edit
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):reader.read(RUN)
            self.assertEqual(1,reader.last['sequence'])

    def test_callback_and_object_revival_or_broken_event_grammar_are_rejected(self):
        source=Boundary();reader=source.reader();source.roots=[root(helperAlive=True,rootAlive=True,callbackIds=[],callbackDepth=0)]
        reader.read(RUN);source.roots[0]['callbackIds']=[0]
        with self.assertRaises(NativeUIError):reader.read(RUN)
        edits=[lambda v:v['requests'][0]['events'][-1]['state'].update(callbackDepth=1),
            lambda v:v['requests'][0]['events'][0].update(kind='expected-complete'),
            lambda v:v['requests'][0]['replies'][0].update(destroyed=True),
            lambda v:v['requests'][0].update(destroyed=True),
            lambda v:v['requests'][0]['events'][0].update(sequence=2),
            lambda v:v['roots'][0].update(helperAlive=True),
            lambda v:v['requests'][0]['events'][0].update(occurredEpochMs=20001)]
        for edit in edits:
            source=Boundary();source.edit=edit
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):source.reader().read(RUN)

    def test_ignored_incomplete_foreign_stale_and_frozen_clock_timeout_cannot_publish(self):
        for edit in (lambda v:v.update(processId=32),lambda v:v.update(capturedEpochMs=19999),
                     lambda v:v.update(tabletHttpVersion=True),lambda v:v.update(complete=False),
                     lambda v:v.update(commandId='f'*32)):
            source=Boundary();source.edit=edit;reader=source.reader()
            with self.subTest(edit=edit),self.assertRaises(NativeUIError):reader.read(RUN)
            self.assertIsNone(reader.last);self.assertEqual(1,len(source.commands))
        source=Boundary();source.ignore=True;reader=source.reader()
        with self.assertRaises(NativeUIError):reader.read(RUN)
        self.assertEqual(1,len(source.commands));self.assertIsNone(reader.last)

    def test_final_guard_native_time_and_host_latency_remain_authoritative(self):
        for fault in ('guard','time','latency'):
            source=Boundary();reader=source.reader();calls=[]
            def clock():
                calls.append(1)
                if len(calls)==3:
                    if fault=='guard':source.okay=False
                    if fault=='time':return 19999
                    if fault=='latency':source.clock+=1.6
                return 20000
            reader.clock_ms=clock
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):reader.read(RUN)
            self.assertIsNone(reader.last)

    def test_closed_grammar_does_not_accept_requested_verdicts_or_other_platform_nonces(self):
        request=command(dict(schemaVersion=1,commandId='a'*32,action='feature-tablet-http-observe',runId=RUN))
        for extra in (dict(expectedCallbacks=0),dict(commandId='ios-'+'a'*32),dict(schemaVersion=True),dict(url='https://example.invalid')):
            with self.subTest(extra=extra),self.assertRaises(NativeUIError):command(request|extra)

    def test_actual_probe_preserves_original_and_deduplicates_command(self):
        program=r'''
const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,k)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.sort());
let files=[],calls=[];
const original={tabletHttpVersion:1,commandId:"a".repeat(32),capturedEpochMs:17000,requests:[{id:"live"}]};
const Test={featureTabletHttpObservation:c=>{calls.push(c);return original;},saveObject:(v,name)=>files.push({v,name})};
SOURCE
const request={schemaVersion:1,commandId:"a".repeat(32),action:"feature-tablet-http-observe",runId:"b".repeat(32)};
applyAndroidControlCommand(request);applyAndroidControlCommand(request);
if(calls.length!==1||files.length!==1||files[0].v!==original||files[0].name!=="feature-tablet-http.json")throw Error("Original changed/replayed");
applyAndroidControlCommand({...request,commandId:"c".repeat(32),expectedCallbacks:0});
if(calls.length!==1)throw Error("expected state reached native");
delete Test.featureTabletHttpObservation;applyAndroidControlCommand({...request,commandId:"d".repeat(32)});
if(files.length!==2||files[1].v.available!==false)throw Error("missing source green");
'''.replace('SOURCE',probe_source())
        self.node(program)

    def node(self,program):
        result=subprocess.run(['node','-e',program],cwd=REPO,capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)

    def test_actual_service_and_request_module_keep_original_network_and_callback_order(self):
        self.node(r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const moduleCode=fs.readFileSync('scripts/modules/request.js','utf8');
const serviceCode=fs.readFileSync('scripts/system/request-service.js','utf8');
for(const enabled of [false,true])for(const throws of [false,true]) {
 let bound=[],instances=[],responses=[],receivers=[],ending=[],trace=[];
 const error=new Error('original callback failure');
 function Xhr(){this.status=200;this.responseText='{"actual":7}';this.statusText='OK';this.readyState=0;instances.push(this);}
 Xhr.prototype.setRequestHeader=function(k,v){trace.push(['header',k,v]);};
 Xhr.prototype.open=function(...args){trace.push(['open',...args]);this.readyState=1;this.onreadystatechange();};
 Xhr.prototype.send=function(body){trace.push(['send',body]);};
 Xhr.prototype.getResponseHeader=function(){return 'application/json; charset=utf-8';};
 let env={XMLHttpRequest:Xhr,module:{exports:{}},print:()=>{}};
 if(enabled)env.Test={featureBindTabletHttpRequest:(lease,xhr)=>bound.push({lease,xhr})};
 vm.runInNewContext(moduleCode,env);
 let table={fromQml:{connect:f=>receivers.push(f),disconnect:f=>assert.strictEqual(f,receivers[0])},
   sendToQml:r=>{responses.push(r);if(throws)throw error;}};
 env.Script={require:name=>{assert.strictEqual(name,'request');return env.module.exports;},scriptEnding:{connect:f=>ending.push(f)}};
 env.Tablet={getTablet:name=>{assert.strictEqual(name,'com.highfidelity.interface.tablet.system');return table;}};
 vm.runInNewContext(serviceCode,env);
 let params={uri:'https://actual.invalid/original',headers:{'X-Original':'kept'}};
 receivers[0]({id:0,method:'http.request',params,jsonrpc:'2.0',_overteE2ETabletHttpLease:'a'.repeat(32)});
 let xhr=instances[0];assert.strictEqual(bound.length,enabled?1:0);
 if(enabled){assert.strictEqual(bound[0].xhr,xhr);assert.strictEqual(bound[0].lease,'a'.repeat(32));}
 assert.deepStrictEqual(trace,[['header','X-Original','kept'],['open','GET','https://actual.invalid/original',true],['send',null]]);
 xhr.readyState=4;
 if(throws){assert.throws(()=>xhr.onreadystatechange(),e=>e===error);assert.strictEqual(typeof xhr.onreadystatechange,'function');}
 else{xhr.onreadystatechange();assert.strictEqual(xhr.onreadystatechange,null);}
 assert.strictEqual(JSON.stringify(responses),JSON.stringify([{id:0,method:'http.response',error:false,response:{actual:7},jsonrpc:'2.0'}]));
 ending[0]();
}
// Failed observation must not suppress the normal request or response.
let ran=false,env={module:{exports:{}},Test:{featureBindTabletHttpRequest:()=>{throw Error('observer lost');}},
 XMLHttpRequest:function(){this.open=()=>{};this.send=()=>{ran=true;};}};
vm.runInNewContext(moduleCode,env);env.module.exports.request('https://actual.invalid',()=>{},'a'.repeat(32));assert(ran);
''')

    def test_original_qml_callback_clears_map_before_call_and_keeps_exception_behavior(self):
        # Run the actual function body as JS without a QML compiler/runtime.
        source=(REPO/'interface/resources/qml/hifi/RootHttpRequest.qml').read_text()
        body=source.split('    function handleHttpResponse(message) {',1)[1].rsplit('\n    }',1)[0]
        self.node('const vm=require("vm"),assert=require("assert");const body='+json.dumps(body)+r''';
for(const enabled of [false,true])for(const throws of [false,true]){
 const error=new Error('original QML failure');let seen=0;
 const env={featureObservationEnabled:enabled,featureCallbackDepth:0,httpCalls:{},console};
 env.httpCalls[3]=(e,r)=>{seen++;assert.strictEqual(env.httpCalls[3],undefined);assert.strictEqual(env.featureCallbackDepth,enabled?1:0);assert.strictEqual(r,73);if(throws)throw error;};
 vm.createContext(env);vm.runInContext('function response(message){'+body+'}',env);
 if(throws)assert.throws(()=>env.response({id:3,error:false,response:73}),e=>e===error);
 else env.response({id:3,error:false,response:73});
 assert.strictEqual(seen,1);assert.strictEqual(env.httpCalls[3],undefined);assert.strictEqual(env.featureCallbackDepth,enabled&&throws?1:0);
}
''')
