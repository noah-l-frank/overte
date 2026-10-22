"""Actual staged Script/companion execute in Node; native Script/Qt are models."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import subprocess
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters.world_web_files import originals
from ios.adapters import world_web_work as work
from ios.self_tests.world_web_source_fixture import RUN,TICKET,URL

EPOCH=1700000000000
ENTITY='11111111-1111-4111-8111-111111111111'
DIRECTORY='file:///private/owned-world-web'
NONCE='b'*32
PROGRAM=r'''
const fs=require('node:fs'),vm=require('node:vm');
const input=JSON.parse(fs.readFileSync(0,'utf8')),events=[],sent=[],deleted=[],created=[];
function signal(){const calls=new Set();return{connect(fn){calls.add(fn)},disconnect(fn){calls.delete(fn)},
emit(...args){let result;for(const fn of [...calls])result=fn(...args);return result}}}
const received=signal(),ending=signal();let companion;
const context={Camera:{position:{x:0,y:1.6,z:0},orientation:{x:0,y:0,z:0,w:1}},
Vec3:{sum:(a,b)=>({x:a.x+b.x,y:a.y+b.y,z:a.z+b.z}),multiplyQbyV:(_q,v)=>v},
Entities:{webEventReceived:received,addEntity(properties,host){created.push({properties,host});return input.entity},
deleteEntity(id){deleted.push(id)},emitScriptEvent(id,message){sent.push({id,message});if(input.throwReply)throw Error('Actual native API boundary failed')}},
Script:{scriptEnding:ending,require(name){if(name!=='./companion.js')throw Error('Unexpected actual module');
const module={exports:{}};vm.runInNewContext(input.companion,{module});companion=module.exports;return companion}},console};
if(input.observer)context.Test={featureIOSWorldWebEvent(value){events.push(JSON.parse(JSON.stringify(value)))}};
vm.runInNewContext(input.script,context);let returned,error=null;
try{returned=received.emit(input.entity,JSON.stringify({contract:'overte-web-parity-v1',action:'echo',sequence:1}))}
catch(problem){error=problem.message}
ending.emit();process.stdout.write(JSON.stringify({events,sent,deleted,created,companion,error,returnedUndefined:returned===undefined}));
'''


def execute(*,observer=True,throw_reply=False):
    raw=originals(RUN,URL,TICKET,NONCE)
    value=dict(script=raw['script-bundle/main.js'].decode(),companion=raw['script-bundle/companion.js'].decode(),
        entity=ENTITY,observer=observer,throwReply=throw_reply)
    result=subprocess.run(['node','-e',PROGRAM],input=json.dumps(value),text=True,capture_output=True,check=True,timeout=10)
    return json.loads(result.stdout)


def packet(events):
    raw=originals(RUN,URL,TICKET,NONCE)['script-bundle/main.js'].decode().encode('utf-16le')
    manager=dict(instance='c'*32,assigned=True,url=DIRECTORY+'/script-bundle/main.js',loadGeneration=1,assignedEpochMs=EPOCH-200)
    code=dict(submitted=True,encoding='utf-16le-code-units',submittedEpochMs=EPOCH-100,codeUnits=len(raw)//2,sha256=hashlib.sha256(raw).hexdigest())
    native=[];calls=[]
    for index,value in enumerate(events,1):
        native.append(dict(sequence=index,event=value['event'],call=value['call'],payload=value['payload'],callerSequence=index,
            invokedEpochMs=EPOCH-90+index,capturedEpochMs=EPOCH-90+index))
        if value['event']=='loaded':continue
        prefix,phase=value['event'].rsplit('-',1)
        if phase=='enter':calls.append(dict(call=value['call'],kind=prefix,payload=deepcopy(value['payload']),returned=False))
        elif phase=='return':calls[-1]['returned']=True
        else:calls.pop()
    row=dict(runId=RUN,nonce=NONCE,manager=manager,code=code,calls=calls,events=native,ended=bool(events and events[-1]['event']=='ending-finally'))
    return dict(iosWorldWebWorkVersion=1,requestId='ios-'+'e'*32,runId=RUN,instance='f'*32,sequence=1,processId=42,
        clockDomain='native-main-ios-world-web-work',clockBefore=dict(epochMs=EPOCH,monotonicMs=1),clockAfter=dict(epochMs=EPOCH+1,monotonicMs=2),
        source=dict(complete=True,eventSequence=len(events),workers=[row]))


class WorldWebWorkTests(unittest.TestCase):
    def test_actual_original_world_only_source_companion_and_real_callback_receipts(self):
        value=execute();self.assertEqual({'kind':'world-web-v1'},value['companion']);self.assertEqual([ENTITY],value['deleted'])
        self.assertEqual(1,len(value['sent']));self.assertEqual('world',json.loads(value['sent'][0]['message'])['surface'])
        self.assertTrue(value['returnedUndefined']);self.assertIsNone(value['error']);self.assertEqual('local',value['created'][0]['host'])
        original=packet(value['events']);work.original(original)
        ownership=dict(runId=RUN,nonce=NONCE,fixtureUrl=URL,ticket=TICKET)
        row=work.owned_worker(original,ownership,DIRECTORY,ENTITY)
        completed=work.worker(row,EPOCH+1,len(value['events']));self.assertTrue(all(entry['returned'] for entry in completed));self.assertTrue(row['ended'])
        row['events'][0]['payload']['entityId']='mutated';self.assertEqual(ENTITY,original['source']['workers'][0]['events'][0]['payload']['entityId'])
    def test_absent_test_api_does_not_change_the_normal_script_protocol_or_effects(self):
        traced,ordinary=execute(),execute(observer=False)
        self.assertEqual([],ordinary['events'])
        for key in ('sent','deleted','created','companion','returnedUndefined','error'):self.assertEqual(traced[key],ordinary[key])
    def test_actual_throw_keeps_both_finally_boundaries_without_fabricated_return(self):
        value=execute(throw_reply=True);self.assertEqual('Actual native API boundary failed',value['error'])
        original=packet(value['events']);work.original(original)
        finished=work.worker(original['source']['workers'][0],EPOCH+1,len(value['events']))
        self.assertEqual([False,False,True],[row['returned'] for row in finished])
        self.assertEqual(['script-reply','world-event','ending'],[row['kind'] for row in finished])
    def test_pending_callback_cannot_borrow_a_closed_stack_or_another_worker_code(self):
        actual=execute()['events'];prefix=actual[:3];original=packet(prefix);work.original(original)
        self.assertEqual(2,len(original['source']['workers'][0]['calls']))
        forged=deepcopy(original);forged['source']['workers'][0]['calls']=[]
        with self.assertRaises(NativeUIError):work.original(forged)
        full=packet(actual);full['source']['workers'][0]['code']['sha256']='a'*64
        with self.assertRaises(NativeUIError):work.owned_worker(full,dict(runId=RUN,nonce=NONCE,fixtureUrl=URL,ticket=TICKET),DIRECTORY,ENTITY)
    def test_warm_history_code_header_and_original_event_prefix_cannot_roll_over(self):
        before=packet(execute()['events']);after=deepcopy(before);after['sequence']=2;after['requestId']='ios-'+'1'*32
        for key in ('clockBefore','clockAfter'):
            after[key]['epochMs']+=10;after[key]['monotonicMs']+=10
        query=dict(schemaVersion=1,action=work.ACTION,commandId=after['requestId'],runId=RUN);work.validate(after,query,42,previous=before)
        for fault in ('history','source','ended','sequence'):
            value=deepcopy(after);row=value['source']['workers'][0]
            if fault=='history':row['events'][0]['payload']['entityId']='22222222-2222-4222-8222-222222222222'
            elif fault=='source':row['manager']['url']=DIRECTORY+'/foreign.js'
            elif fault=='ended':row['ended']=False
            else:row['events'][1]['callerSequence']=row['events'][0]['callerSequence']
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):work.validate(value,query,42,previous=before)


if __name__=='__main__':unittest.main()
