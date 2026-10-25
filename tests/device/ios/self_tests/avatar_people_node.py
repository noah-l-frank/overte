"""Whole original Pal/People/request JS in host V8; native transport is modeled.

Queued message delivery crosses the modeled native boundary only after the
sender returned. No sender VM frames are manufactured as receiver parents.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
from pathlib import Path
import subprocess

PROGRAM=r'''
const fs=require('node:fs'),vm=require('node:vm'),readline=require('node:readline'),crypto=require('node:crypto');
let config={},now=0,handle=0,rid=0,peers={},timers=new Map(),queue=[],requests=[],updates=[],connected=[],nativeCalls=[];
const sources={};for(const name of ['system/pal.js','system/libraries/peopleConnection.js','modules/request.js'])sources[name]=fs.readFileSync(process.argv[1]+'/'+name,'utf8');
const qml=fs.readFileSync(process.argv[2],'utf8'),start=qml.indexOf('processPage: function (data) {');
if(start<0)throw Error('missing original Pal page parser');let begin=qml.indexOf('{',start),end=begin+1,depth=1;
for(;depth&&end<qml.length;end++){if(qml[end]==='{')depth++;else if(qml[end]==='}')depth--;}
const page=vm.runInNewContext('(function(data)'+qml.slice(begin,end)+')');
function signal(){return {connect(fn){this.fn=fn;},disconnect(){this.fn=null;}};}
function stack(){const old=Error.prepareStackTrace;Error.prepareStackTrace=(_,frames)=>frames;const frames=new Error().stack;Error.prepareStackTrace=old;
 return frames.map(f=>({url:f.getFileName(),line:f.getLineNumber(),column:f.getColumnNumber(),isEval:f.isEval(),isConstructor:f.isConstructor()}))
 .filter(f=>f.url&&f.url.startsWith('qrc:/scripts/'));}
function event(role,id,kind,details){peers[role].timerEvents.push({timerId:id,kind,capturedEpochMs:now,details});}
function clear(id){const row=timers.get(id);if(!row)return;timers.delete(id);event(row.role,row.identity,'destroyed',{});}
function initialize(values){config=values;for(const role of ['primary','actor']){const other=role==='primary'?'actor':'primary';
 const peer={timerEvents:[],callbacks:new Map(),view:{phase:'idle',message:'',peerName:'',peer:'',requestId:''}};peers[role]=peer;
 const account={metaverseServerURL:config[role].endpoint,isLoggedIn:()=>config[role].loggedIn,
  myUsernameChanged:signal(),loggedInChanged:signal(),connected:signal(),disconnected:signal()};
 Object.defineProperty(account,'username',{get:()=>config[role].account});
 const avatar={};Object.defineProperty(avatar,'sessionUUID',{get:()=>config[role].self});
 const messages={subscribe(){},unsubscribe(){},messageReceived:signal(),sendMessage(channel,text){queue.push({role:other,channel,text,sender:config[role].self});}};
 const mapping={from(){return this;},peek(){return this;},to(){return this;},enable(){},disable(){}};
 function AppUi(properties){Object.assign(this,properties);peer.ui=this;this.isOpen=true;this.tablet={tabletShown:true,tabletShownChanged:signal()};
  this.sendMessage=function(message){if(message.method==='connectionState'){peer.view=message.params;updates.push({role,state:peer.view});}
   if(message.method==='refreshConnections')connected.push({role});};this.open=function(){this.isOpen=true;};this.close=function(){this.isOpen=false;this.onClosed();};}
 function XHR(){this.id=++rid;this.headers={};this.open=function(method,url){this.method=method;this.url=url;this.openStack=stack();};
  this.send=function(body){peer.callbacks.set(this.id,this);requests.push({id:this.id,role,options:{uri:this.url,method:this.method,
   ...(body?{body:JSON.parse(body)}:{})},openStack:this.openStack});};this.setRequestHeader=function(name,value){this.headers[name]=value;};
  this.getResponseHeader=function(){return 'application/json';};Object.defineProperty(this,'responseText',{get(){nativeCalls.push({id:this.id,role,kind:'text-read',stack:stack()});return this.raw;}});}
 const modules={};function load(name){const module={exports:{}};vm.runInNewContext(sources[name],{...context,module},{filename:'qrc:/scripts/'+name});return module.exports;}
 const tablet={fromQml:{connect(fn){peer.qml=fn;},disconnect(){}},sendToQml(){}};
 const context={print(){},XMLHttpRequest:XHR,Tablet:{getTablet:()=>tablet},MyAvatar:avatar,location:{domainID:config[role].domain},Account:account,
  Script:{include(){},resolvePath:x=>x,scriptEnding:signal(),require(name){if(name==='request')return modules.request;if(name==='appUi')return AppUi;
   if(name==='./libraries/peopleConnection.js')return modules.protocol;throw Error('unknown original dependency');},
   setTimeout(callback,delay){const id=++handle,identity=crypto.randomBytes(16).toString('hex');timers.set(id,{role,identity,callback,due:now+delay});
    event(role,identity,'created',{handle:id,callerFrames:stack(),active:true,singleShot:true,intervalMs:delay,remainingMs:delay});return id;},clearTimeout:clear,
   setInterval(){throw Error('unmodeled Pal interval entry');},clearInterval:clear},
  AvatarList:{getAvatarIdentifiers:()=>[config[other].self],getAvatar:id=>({sessionUUID:id,displayName:other,isReplicated:false}),
   avatarAddedEvent:signal(),avatarRemovedEvent:signal(),avatarSessionChangedEvent:signal()},
  Users:{getIgnoreStatus:()=>false,requestsDomainListData:false,avatarDisconnected:signal(),usernameFromIDReply:signal()},
  Controller:{Standard:{},newMapping:()=>mapping},Uuid:{generate:()=>crypto.randomUUID()},Messages:messages,
  Window:{domainChanged:signal(),domainConnectionRefused:signal()},Entities:{},Overlays:{},Vec3:{},Quat:{},HMD:{}};
 modules.request=load('modules/request.js');modules.protocol=load('system/libraries/peopleConnection.js');
 vm.runInNewContext(fs.readFileSync(process.argv[1]+'/system/request-service.js','utf8'),context,{filename:'qrc:/scripts/system/request-service.js'});
 vm.runInNewContext(sources['system/pal.js'],context,{filename:'qrc:/scripts/system/pal.js'});peer.context=context;
 }}
function drain(){for(let count=0;queue.length;count++){if(count>=100)throw Error('message bound');const q=queue.shift();peers[q.role].context.Messages.messageReceived.fn(q.channel,q.text,q.sender);}}
function result(){const value={views:{primary:peers.primary.view,actor:peers.actor.view},requests,updates,connected,nativeCalls,
 timers:{primary:peers.primary.timerEvents,actor:peers.actor.timerEvents}};requests=[];updates=[];connected=[];nativeCalls=[];return value;}
readline.createInterface({input:process.stdin}).on('line',line=>{try{const q=JSON.parse(line);now=q.now;if(q.config)config=q.config;
 if(q.op==='init')initialize(q.config);
 else if(q.op==='request')peers[q.role].ui.onMessage({method:'connectionRequest',params:q.peer});
 else if(q.op==='respond')peers[q.role].ui.onMessage({method:'connectionRespond',params:q.accept});
 else if(q.op==='cancel')peers[q.role].ui.onMessage({method:'connectionCancel'});
 else if(q.op==='remove')peers[q.role].ui.onMessage({method:'removeConnection',params:q.peer});
 else if(q.op==='qml-request')peers[q.role].qml({id:'owned',method:'http.request',params:q.options});
 else if(q.op==='dispose')peers[q.role].context.Script.scriptEnding.fn();
 else if(q.op==='reply'){let found;for(const role of ['primary','actor']){const xhr=peers[role].callbacks.get(q.id);if(xhr){peers[role].callbacks.delete(q.id);found=xhr;break;}}
  if(!found)throw Error('unknown original XHR');found.readyState=4;found.status=200;found.raw=q.raw;found.onreadystatechange();}
 else if(q.op==='tick'){for(let count=0;count<1000;count++){const entry=[...timers].find(([,row])=>row.due<=now);if(!entry)break;
  const [id,row]=entry;event(row.role,row.identity,'fired',{active:false,remainingMs:-1});clear(id);event(row.role,row.identity,'callback-enter',{});
  try{row.callback();}finally{event(row.role,row.identity,'callback-leave',{});}}}
 else if(q.op==='page'){process.stdout.write(JSON.stringify({rows:page(q.data)})+'\n');return;}
 else throw Error('unknown command');drain();process.stdout.write(JSON.stringify(result())+'\n');
 }catch(error){process.stdout.write(JSON.stringify({error:String(error.stack)})+'\n');}});
'''


class PeopleNode:
    def __init__(self,test,config,epoch_ms,monotonic):
        root=Path(__file__).resolve().parents[4];self.epoch_ms,self.monotonic=epoch_ms,monotonic
        self.process=subprocess.Popen(['node','-e',PROGRAM,str(root/'scripts'),str(root/'interface/resources/qml/hifi/Pal.qml')],
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,bufsize=1)
        test.addCleanup(self.close);self.request('init',config=config)
    def request(self,op,**fields):
        self.process.stdin.write(json.dumps(dict(op=op,now=round(self.epoch_ms()),mono=round(self.monotonic()*1000),**fields))+'\n');self.process.stdin.flush()
        line=self.process.stdout.readline()
        if not line:raise AssertionError('Original full Pal Node terminated unexpectedly')
        result=json.loads(line)
        if 'error' in result:raise AssertionError(result['error'])
        self.latest=result;return result
    def close(self):
        if self.process.stdin:self.process.stdin.close()
        self.process.wait(timeout=5);error=self.process.stderr.read();self.process.stdout.close();self.process.stderr.close()
        if self.process.returncode:raise AssertionError('Original full Pal Node failed: '+error)
