"""Unchanged AvatarApp JS executed at explicit host native/QML boundaries."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
from pathlib import Path
import subprocess

PROGRAM=r'''
const fs=require('node:fs'),vm=require('node:vm'),readline=require('node:readline'),crypto=require('node:crypto');
let config={},now=0,handle=10000,screen,handler,opened=false;const entities=new Map(),timers=new Map(),events=[],calls=[],messages=[];
function signal(){const handlers=new Set();return {connect(fn){handlers.add(fn);},disconnect(fn){handlers.delete(fn);},emit(...args){for(const fn of [...handlers])fn(...args);}};}
function stack(){const old=Error.prepareStackTrace;Error.prepareStackTrace=(_,frames)=>frames;const frames=new Error().stack;Error.prepareStackTrace=old;
 return frames.map(f=>({url:f.getFileName(),line:f.getLineNumber(),column:f.getColumnNumber(),isEval:f.isEval(),isConstructor:f.isConstructor()}))
 .filter(f=>f.url==='qrc:/scripts/system/avatarapp.js');}
function event(id,kind,details){events.push({timerId:id,kind,capturedEpochMs:now,details});}
function clear(id){const row=timers.get(id);if(!row)return;timers.delete(id);event(row.identity,'destroyed',{});}
const tablet={fromQml:{connect(fn){handler=fn;},disconnect(){handler=null;}},screenChanged:{connect(fn){screen=fn;},disconnect(){}},
 sendToQml(value){messages.push(value);},addButton(){return {clicked:signal(),editProperties(){}};},removeButton(){},gotoHomeScreen(){opened=false;screen('QML','hifi/TabletHome.qml');}};
const avatar={getJointNames:()=>config.joints||['Hips'],getAvatarEntitiesVariant:()=>[...entities].map(([id,properties])=>({id,properties})),
 getAvatarScale:()=>config.scale||1,getDominantHand:()=> 'right',getHmdAvatarAlignmentType:()=>0,getCollisionsEnabled:()=>true,
 getOtherAvatarsCollisionsEnabled:()=>true,getAnimGraphUrl:()=>'',getAnimGraphOverrideUrl:()=>''};
Object.defineProperty(avatar,'sessionUUID',{get:()=>config.self});Object.defineProperty(avatar,'SELF_ID',{get:()=>config.self});
Object.defineProperty(avatar,'skeletonModelURL',{get:()=>config.avatarUrl||''});
for(const name of ['skeletonModelURLChanged','dominantHandChanged','hmdAvatarAlignmentTypeChanged','collisionsEnabledChanged',
 'otherAvatarsCollisionsEnabledChanged','newCollisionSoundURL','animGraphUrlChanged','targetScaleChanged'])avatar[name]=signal();
const nativeEntities={addingWearable:signal(),deletingWearable:signal(),mousePressOnEntity:signal(),
 addEntity(properties,host){const frames=stack(),id=crypto.randomUUID();entities.set(id,{...properties,visible:true,avatarEntity:true,grab:{grabbable:false},localRotation:{x:0,y:0,z:0,w:1}});
  calls.push({ordinal:calls.length+1,method:'addEntity',id,properties,host,frames,capturedEpochMs:now});return id;},
 deleteEntity(id){const frames=stack(),properties=entities.get(id);entities.delete(id);calls.push({ordinal:calls.length+1,method:'deleteEntity',id,properties,frames,capturedEpochMs:now});},
 getEntityProperties(id){return entities.get(id)||{};},editEntity(id,value){Object.assign(entities.get(id),value);}};
const bookmarks={bookmarkLoaded:signal(),bookmarkDeleted:signal(),bookmarkAdded:signal(),getBookmarks:()=>config.bookmarks||{},
 getBookmark:name=>(config.bookmarks||{})[name],loadBookmark(name){bookmarks.bookmarkLoaded.emit(name);}};
const Script={include(){},resolvePath:x=>x,scriptEnding:signal(),
 setTimeout(callback,delay){const id=++handle,identity=crypto.randomBytes(16).toString('hex');timers.set(id,{identity,callback,due:now+delay});
  event(identity,'created',{handle:id,callerFrames:stack(),active:true,singleShot:true,intervalMs:delay,remainingMs:delay});return id;},clearTimeout:clear,
 setInterval(){throw Error('Unmodeled AvatarApp interval');},clearInterval:clear};
function result(){return {calls,events,messages,pending:[...timers.values()].map(row=>row.due),entities:[...entities].map(([id,properties])=>({id,properties}))};}
readline.createInterface({input:process.stdin}).on('line',line=>{try{const q=JSON.parse(line);now=q.now;if(q.config)config=q.config;
 if(q.op==='init')vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8'),{Script,Tablet:{getTablet:()=>tablet},MyAvatar:avatar,
  AvatarBookmarks:bookmarks,Entities:nativeEntities,Camera:{},HMD:{},Account:{},UserActivityLogger:{},Messages:{},print(){},
  Quat:{safeEulerAngles:()=>({x:0,y:0,z:0})}},{filename:'qrc:/scripts/system/avatarapp.js'});
 else if(q.op==='screen'){if(opened!==q.open){opened=q.open;screen('QML',q.open?'hifi/AvatarApp.qml':'hifi/TabletHome.qml');if(q.open)handler({method:'getAvatars'});}}
 else if(q.op==='message'){if(!handler)throw Error('Actual Avatar QML handler absent');handler(q.message);}
 else if(q.op==='tick'){for(let count=0;count<1000;count++){const entry=[...timers].find(([,row])=>row.due<=now);if(!entry)break;
  const [id,row]=entry;event(row.identity,'fired',{active:false,remainingMs:-1});clear(id);event(row.identity,'callback-enter',{});
  try{row.callback();}finally{event(row.identity,'callback-leave',{});}}}
 else if(q.op==='dispose')Script.scriptEnding.emit();else throw Error('Unknown AvatarApp command');
 process.stdout.write(JSON.stringify(result())+'\n');}catch(error){process.stdout.write(JSON.stringify({error:String(error.stack)})+'\n');}});
'''


class AvatarAppNode:
    def __init__(self,test,config,epoch_ms):
        root=Path(__file__).resolve().parents[4];self.epoch_ms=epoch_ms
        self.process=subprocess.Popen(['node','-e',PROGRAM,str(root/'scripts/system/avatarapp.js')],stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,bufsize=1)
        test.addCleanup(self.close);self.request('init',config=config)
    def request(self,op,**fields):
        self.process.stdin.write(json.dumps(dict(op=op,now=round(self.epoch_ms()),**fields))+'\n');self.process.stdin.flush()
        line=self.process.stdout.readline()
        if not line:raise AssertionError('Original full AvatarApp Node terminated unexpectedly')
        value=json.loads(line)
        if 'error' in value:raise AssertionError(value['error'])
        self.latest=value;return value
    def close(self):
        self.process.stdin.close();self.process.wait(timeout=5);error=self.process.stderr.read()
        self.process.stdout.close();self.process.stderr.close()
        if self.process.returncode:raise AssertionError('Original full AvatarApp Node failed: '+error)
