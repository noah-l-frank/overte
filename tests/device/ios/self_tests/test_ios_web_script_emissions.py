"""Original emitter/compiled-stack schema and actual host weak-capture model.

The native Qt/V8 hooks are inspected as source, never compiled or executed.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import gc
import hashlib
import json
from pathlib import Path
import re
import subprocess
import unittest
import uuid
import weakref
from adapters.normal_ui import NativeUIError
from ios.adapters import web_script_emissions as source
from ios.self_tests.test_ios_tablet_web_buttons import Boundary as Buttons
from ios.self_tests.test_ios_tablet_web_source import packet as tablet_packet
from ios.self_tests.test_ios_tablet_web_sources import ROOT,RUN


class Object:pass


class Emitter:
    def __init__(self):
        self.now=1700000000120;self.sequence=0;self.calls=[];self.queues=[];self.sinks=[];self.objects=[];self.strong={};self.weak={}
        self.buttons=Buttons();self.frames=[dict(scriptId=71,line=15,column=84,sourceUrlSha256=hashlib.sha256(b'qrc:/scripts/defaultScripts.js').hexdigest(),
            compiled=dict(urlSha256=hashlib.sha256(b'qrc:/scripts/defaultScripts.js').hexdigest(),encoding='utf-16le-code-units',codeUnits=10,sha256='d'*64,firstObservedEpochMs=1700000000002),
            isEval=False,isConstructor=False)]
    def tick(self):self.now+=1;return dict(epochMs=self.now,monotonicMs=self.now-1700000000000)
    def api(self,*,qualified=True,surface='tablet',message=None,frames=None):
        key=uuid.uuid4().hex;obj=Object();self.strong[key]=obj;self.weak[key]=weakref.ref(obj)
        self.objects.append(dict(id=key,born=self.tick(),expired=None,alive=True))
        actual=dict(callerVersion=1,method='emitScriptEvent',sequence=len(self.calls)*3+1,invokedEpochMs=self.tick()['epochMs'],
            manager=deepcopy(self.buttons.manager),code=deepcopy(self.buttons.code),
            emitStack=dict(emitStackVersion=1,instance='f'*32,complete=True,frames=deepcopy(self.frames if frames is None else frames)))
        row=dict(id=uuid.uuid4().hex,sequence=len(self.calls)+1,object=key,surface=surface,target='com.highfidelity.interface.tablet.system' if surface=='tablet' else '11111111-2222-3333-4444-555555555555',
            message=message or json.dumps(dict(contract='overte-web-parity-v1',action='echo',sequence=7,surface=surface)),caller=actual if qualified else None,
            entered=self.tick(),returned=None,finally_=None)
        row['finally']=row.pop('finally_');self.calls.append(row);return row
    def queue(self,call,route='tablet-surface'):
        life=Object();row=dict(id=uuid.uuid4().hex,sequence=len(self.queues)+1,call=call['id'] if call else None,route=route,
            created=self.tick(),entered=None,returned=None,finally_=None,captureAlive=True,expired=None)
        row['finally']=row.pop('finally_');self.queues.append(row);self.weak[row['id']]=weakref.ref(life);return row,life
    def leave(self,row,*,exception=False):
        if not exception:row['returned']=self.tick()
        row['finally']=self.tick()
    def deliver(self,row,call,*,exception=False):
        row['entered']=self.tick();identity=tablet_packet()['events'][0]['identity']
        for kind in ('script-event-slot','page-reply'):
            sink=dict(id=uuid.uuid4().hex,sequence=len(self.sinks)+1,kind=kind,call=call['id'] if call else None,identity=deepcopy(identity),
                message=deepcopy(call['message']) if call else json.dumps(dict(contract='overte-web-parity-v1',action='echo',sequence=7,surface='tablet')),
                entered=self.tick(),returned=None,finally_=None)
            sink['finally']=sink.pop('finally_');self.sinks.append(sink);self.leave(sink,exception=exception)
        self.leave(row,exception=exception)
    def snapshot(self):
        self.sequence+=1;before=self.tick()
        for row in self.objects+self.queues:
            if self.weak[row['id']]() is None and row['expired'] is None:
                row['expired']=self.tick();row['alive' if row in self.objects else 'captureAlive']=False
        return dict(iosWebScriptEmissionsVersion=1,commandId='ios-'+format(self.sequence,'032x'),runId=RUN,fixtureUrl=ROOT,instance='e'*32,sequence=self.sequence,processId=31,
            clockDomain='native-process-ios-web-script-emissions',clockBefore=before,clockAfter=self.tick(),complete=True,
            callSequence=len(self.calls),queueSequence=len(self.queues),sinkSequence=len(self.sinks),objects=deepcopy(self.objects),calls=deepcopy(self.calls),queues=deepcopy(self.queues),sinks=deepcopy(self.sinks))
    def locations(self):return [{**{key:row[key] for key in ('sourceUrlSha256','line','column')},**{key:row['compiled'][key] for key in ('sha256','codeUnits')}} for row in self.frames]
    def good(self):
        call=self.api();row,life=self.queue(call);self.leave(call);self.deliver(row,call);return call,row,life


def query(value):return dict(schemaVersion=1,action=source.ACTION,commandId=value['commandId'],runId=RUN,fixtureUrl=ROOT)


class WebScriptEmissionTests(unittest.TestCase):
    def test_actual_propagated_caller_code_and_compiled_location_are_required(self):
        native=Emitter();call,row,life=native.good();value=native.snapshot();source.original(value)
        self.assertEqual(call,source.selected(value,value['sinks'][-1],native.buttons.profile(),native.locations()))
        with self.assertRaises(NativeUIError):source.settled(value,native.buttons.profile())
        del life;gc.collect();gone=native.snapshot();source.validate(gone,query(gone),31,previous=value)
        self.assertEqual([call['id']],source.settled(gone,native.buttons.profile()))
        for fault in ('manager','code','missing-context','same-url-different-compiled-code','same-vm-untracked-line','extra-nested-frame'):
            bad=deepcopy(gone);actual=bad['calls'][0]['caller']
            if fault=='manager':actual['manager']['instance']='0'*32
            elif fault=='code':actual['code']['sha256']='0'*64
            elif fault=='missing-context':bad['calls'][0]['caller']=None
            elif fault=='same-url-different-compiled-code':actual['emitStack']['frames'][0]['compiled']['sha256']='0'*64
            elif fault=='same-vm-untracked-line':actual['emitStack']['frames'][0]['line']+=1
            else:actual['emitStack']['frames'].append(deepcopy(actual['emitStack']['frames'][0]))
            source.original(bad)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.selected(bad,bad['sinks'][-1],native.buttons.profile(),native.locations())
        changed=deepcopy(gone);changed['calls'][0]['caller']['emitStack']['frames'][0]['line']+=1
        self.assertEqual(call['id'],source.selected_vm(changed,changed['sinks'][0],native.buttons.profile())['id'])

    def test_same_shaped_unknown_or_concurrent_native_emitter_never_inherits_another_caller(self):
        native=Emitter();qualified=native.api();unknown=native.api(qualified=False);row,life=native.queue(unknown)
        native.leave(qualified);native.leave(unknown);native.deliver(row,unknown);value=native.snapshot();source.original(value)
        with self.assertRaises(NativeUIError):source.selected_vm(value,value['sinks'][-1],native.buttons.profile())
        value['sinks'][-1]['call']=None;source.original(value)
        with self.assertRaises(NativeUIError):source.selected_vm(value,value['sinks'][-1],native.buttons.profile())
        self.assertEqual(qualified['message'],unknown['message'])

    def test_receiver_deletion_cancels_real_queue_capture_without_inventing_body_return(self):
        native=Emitter();call=native.api();row,life=native.queue(call);native.leave(call);before=native.snapshot()
        with self.assertRaises(NativeUIError):source.settled(before,native.buttons.profile())
        del life;gc.collect();after=native.snapshot();source.validate(after,query(after),31,previous=before)
        self.assertEqual([call['id']],source.settled(after,native.buttons.profile()))
        self.assertIsNone(after['queues'][0]['entered']);self.assertIsNone(after['queues'][0]['returned']);self.assertEqual([],after['sinks'])

    def test_actual_exception_finally_is_distinct_from_normal_return_or_weak_death(self):
        native=Emitter();call=native.api();row,life=native.queue(call);native.leave(call);native.deliver(row,call,exception=True)
        value=native.snapshot();source.original(value)
        with self.assertRaises(NativeUIError):source.selected_vm(value,value['sinks'][-1],native.buttons.profile())
        del life;gc.collect();gone=native.snapshot();source.original(gone)
        with self.assertRaises(NativeUIError):source.settled(gone,native.buttons.profile())
        self.assertIsNotNone(gone['queues'][0]['finally']);self.assertIsNone(gone['queues'][0]['returned'])

    def test_raw_history_rejects_birth_reset_retiming_prefix_rewrite_and_compiled_alias(self):
        native=Emitter();call,row,life=native.good();before=native.snapshot();del life;gc.collect();after=native.snapshot()
        for fault in ('source','counter','call','queue','sink','retime','reappear','compiled-rewrite','stack-birth'):
            bad=deepcopy(after)
            if fault=='source':bad['instance']='0'*32
            elif fault=='counter':bad['callSequence']=0
            elif fault=='call':bad['calls']=[]
            elif fault=='queue':bad['queues']=[]
            elif fault=='sink':bad['sinks'][0]['call']=None
            elif fault=='retime':bad['queues'][0]['expired']=before['clockBefore']
            elif fault=='reappear':bad['queues'][0].update(captureAlive=True)
            elif fault=='compiled-rewrite':bad['calls'][0]['caller']['emitStack']['frames'][0]['compiled']['sha256']='0'*64
            else:bad['calls'][0]['caller']['emitStack']['instance']='0'*32
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.validate(bad,query(bad),31,previous=before)
        # A second actual call may skip unrelated global native-call sequences,
        # but cannot rewrite one actual engine's compiled script ID or birth.
        native.api();native.leave(native.calls[-1]);current=native.snapshot();source.original(current)
        for fault in ('compiled','instance'):
            bad=deepcopy(current);actual=bad['calls'][-1]['caller']['emitStack']
            if fault=='compiled':actual['frames'][0]['compiled']['sha256']='0'*64
            else:actual['instance']='0'*32
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.original(bad)

    def test_only_closed_parity_reply_bytes_are_accepted_without_private_fields(self):
        valid=' { "surface":"tablet", "sequence":7, "action":"echo", "contract":"overte-web-parity-v1" } '
        self.assertEqual(7,source.echo(valid)['sequence'])
        for raw in (valid.replace('7','true'),valid.replace('7','1.0'),valid.replace('7','-1'),valid[:-2]+',"text":"private"}',valid.replace('"surface"','"sequence"'),valid.replace('echo','ech\\u006f')):
            with self.subTest(raw=raw[:30]),self.assertRaises(NativeUIError):source.echo(raw)

    def test_actual_host_V8_reuses_compiled_scriptID_across_execution_but_not_same_URL_changed_code(self):
        program=r'''const vm=require('vm'),inspector=require('inspector'),crypto=require('crypto'),session=new inspector.Session();
const parsed=[],seen=[];session.connect();session.post('Debugger.enable');
session.on('Debugger.scriptParsed',m=>{if(m.params.url==='file:///private/pinned.js')parsed.push(m.params.scriptId)});
session.on('Debugger.paused',m=>{const frame=m.params.callFrames.find(f=>parsed.includes(f.location.scriptId));
if(!frame)throw Error('missing actual compiled frame');const id=frame.location.scriptId;
session.post('Debugger.getScriptSource',{scriptId:id},(error,reply)=>{if(error)throw error;seen.push({id,location:frame.location,hash:crypto.createHash('sha256').update(Buffer.from(reply.scriptSource,'utf16le')).digest('hex')})});
session.post('Debugger.resume')});
const first='function response(){debugger;} response();',second='function other(){debugger;} other();';
const script=new vm.Script(first,{filename:'file:///private/pinned.js'});script.runInNewContext({});script.runInNewContext({});
new vm.Script(second,{filename:'file:///private/pinned.js'}).runInNewContext({});session.disconnect();
if(seen.length!==3||seen[0].id!==seen[1].id||seen[0].id===seen[2].id||seen[0].hash!==seen[1].hash||seen[0].hash===seen[2].hash)throw Error('compiled IDs/bytes were not original');
process.stdout.write(JSON.stringify(seen));'''
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr);rows=json.loads(result.stdout)
        self.assertEqual(rows[0],rows[1]);self.assertNotEqual(rows[0]['hash'],rows[2]['hash'])

    def test_transport_owns_its_real_action_and_retains_exact_source_instance(self):
        native=Emitter();native.good();raw=[None];sent=[]
        def send(q):
            source.command(q);sent.append(deepcopy(q));value=native.snapshot();value['commandId']=q['commandId'];raw[0]=json.dumps(value)
        reader=source.IOSWebScriptEmissions(send,lambda:raw[0],lambda:native.now,lambda:True,31,monotonic=lambda:0)
        first=reader.read(RUN,ROOT);second=reader.read(RUN,ROOT)
        self.assertEqual([source.ACTION]*2,[v['action'] for v in sent]);self.assertEqual(first['calls'],second['calls']);self.assertEqual(second,json.loads(raw[0]))

    def test_actual_generated_app_synchronous_stack_differs_from_same_vm_untracked_emit(self):
        from ios.adapters.tablet_web_app_files import originals
        files={key:value.decode() for key,value in originals(RUN,ROOT,'b'*32,'c'*32).items()}
        program=r'''
const vm=require('vm'),files=__FILES__,handlers=[],stacks=[];
const signal=()=>({connect:f=>handlers.push(f),disconnect:()=>{}});
const tablet={webEventReceived:signal(),addButton:()=>({clicked:{connect:()=>{},disconnect:()=>{}}}),emitScriptEvent:m=>{stacks.push(new Error().stack)}};
const context={Tablet:{getTablet:()=>tablet},Script:{require:p=>{const module={exports:{}};vm.runInNewContext(files[p.replace(/^\.\//,'')],{module});return module.exports},scriptEnding:{connect:()=>{}}}};
vm.createContext(context);vm.runInContext(files['script.js'],context,{filename:'file:///private/script.js'});
const message=JSON.stringify({contract:'overte-web-parity-v1',action:'echo',sequence:7});handlers[0](message);
vm.runInContext('Tablet.getTablet().emitScriptEvent(JSON.stringify({contract:"overte-web-parity-v1",action:"echo",sequence:7,surface:"tablet"}))',context,{filename:'file:///private/untracked.js'});
if(stacks.length!==2||!stacks[0].includes('respond')||!stacks[0].includes('tabletEvent')||!stacks[1].includes('untracked.js')||stacks[1].includes('tabletEvent'))throw Error('actual paths indistinguishable');
console.log(JSON.stringify(stacks.map(s=>s.split('\n').filter(x=>x.includes('file:///private/')))));
'''
        program=program.replace('__FILES__',json.dumps(files));result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr);frames=json.loads(result.stdout)
        self.assertGreaterEqual(len(frames[0]),3);self.assertEqual(1,len(frames[1]))
        code=files['script.js']
        for forbidden in ('processEvents','Script.update','setTimeout','setInterval','Test.','eval('):self.assertNotIn(forbidden,code)


if __name__=='__main__':unittest.main()
