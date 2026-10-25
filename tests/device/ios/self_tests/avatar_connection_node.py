"""Actual repository peopleConnection/Pal mapping in a retained host Node VM.

The socket transports and callbacks are explicitly driven native seams. Both
protocol instances execute original code; no consent/backend result is invented.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
from pathlib import Path
import subprocess
import uuid

PROGRAM=r'''
const fs=require('node:fs'),vm=require('node:vm'),readline=require('node:readline');
let peers={},timers=new Map(),timerEvents={primary:[],actor:[]},requests=[],callbacks=new Map(),connected=[],updates=[],handle=0,rid=0,now=0,mono=0,config={};
const module={exports:{}};vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8'),{module});const library=module.exports;
const qml=fs.readFileSync(process.argv[2],'utf8'),begin=qml.indexOf('processPage: function (data) {');if(begin<0)throw Error('missing real Pal processPage');
let at=qml.indexOf('{',begin),depth=1,end=at+1;for(;depth&&end<qml.length;end++){if(qml[end]==='{')depth++;else if(qml[end]==='}')depth--;}
const processPage=vm.runInNewContext('(function(data)'+qml.slice(at,end)+')');
function event(role,id,kind,details){timerEvents[role].push({timerId:id,kind,capturedEpochMs:now,details});}
function clear(id){const row=timers.get(id);if(!row)return;timers.delete(id);event(row.role,row.identity,'destroyed',{});}
function init(values){config=values;for(const role of ['primary','actor']){const other=role==='primary'?'actor':'primary';
 peers[role]=library.create({identity:()=>config[role],peer:id=>id===config[other].self?{id,name:other,present:true,replicated:false,ignored:false}:null,
 requestId:()=>require('node:crypto').randomUUID(),now:()=>now,
 send:(channel,text)=>peers[other].receive(channel,text,config[role].self),
 setTimeout:(callback,delay)=>{const id=++handle,identity=require('node:crypto').randomBytes(16).toString('hex');timers.set(id,{role,identity,callback,due:now+delay});
 event(role,identity,'created',{handle:id,callerChain:['qrc:/scripts/system/libraries/peopleConnection.js'],active:true,singleShot:true,intervalMs:delay,remainingMs:delay});return id;},
 clearTimeout:clear,update:state=>updates.push({role,state}),connected:username=>connected.push({role,username}),
 request:(options,callback)=>{const id=++rid;callbacks.set(id,callback);requests.push({id,role,options});}});
 }}
function result(){const response={views:{primary:peers.primary.snapshot(),actor:peers.actor.snapshot()},requests,connected,updates,timers:timerEvents};requests=[];connected=[];updates=[];return response;}
readline.createInterface({input:process.stdin}).on('line',line=>{try{const q=JSON.parse(line);now=q.now;mono=q.mono;if(q.op!=='init'&&q.config)config=q.config;
 if(q.op==='init')init(q.config);
 else if(q.op==='request')peers[q.role].request(q.peer);
 else if(q.op==='respond')peers[q.role].respond(q.accept);
 else if(q.op==='cancel')peers[q.role].cancel();
 else if(q.op==='dispose')peers[q.role].dispose();
 else if(q.op==='reply'){const callback=callbacks.get(q.id);if(!callback)throw Error('unknown request');callbacks.delete(q.id);callback(null,JSON.parse(q.raw));}
 else if(q.op==='tick'){for(let count=0;count<1000;count++){let due=[...timers].find(([,row])=>row.due<=now);if(!due)break;const[id,row]=due;
 event(row.role,row.identity,'fired',{active:false,remainingMs:-1});clear(id);event(row.role,row.identity,'callback-enter',{});try{row.callback();}finally{event(row.role,row.identity,'callback-leave',{});}}}
 else if(q.op==='page'){process.stdout.write(JSON.stringify({rows:processPage(q.data)})+'\n');return;}
 else throw Error('unknown command');process.stdout.write(JSON.stringify(result())+'\n');
 }catch(error){process.stdout.write(JSON.stringify({error:String(error.stack)})+'\n');}});
'''


class ConnectionNode:
    def __init__(self,test,config,epoch_ms,monotonic):
        root=Path(__file__).resolve().parents[4];self.epoch_ms,self.monotonic=epoch_ms,monotonic
        self.process=subprocess.Popen(['node','-e',PROGRAM,str(root/'scripts/system/libraries/peopleConnection.js'),str(root/'interface/resources/qml/hifi/Pal.qml')],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,bufsize=1)
        test.addCleanup(self.close);self.request('init',config=config)
    def request(self,op,**fields):
        self.process.stdin.write(json.dumps(dict(op=op,now=round(self.epoch_ms()),mono=round(self.monotonic()*1000),**fields))+'\n');self.process.stdin.flush()
        line=self.process.stdout.readline()
        if not line:raise AssertionError('Original Node protocol terminated unexpectedly')
        result=json.loads(line)
        if 'error' in result:raise AssertionError(result['error'])
        self.latest=result;return result
    def close(self):
        if self.process.stdin:self.process.stdin.close()
        self.process.wait(timeout=5)
        error=self.process.stderr.read();self.process.stdout.close();self.process.stderr.close()
        if self.process.returncode:raise AssertionError('Original Node protocol failed: '+error)
