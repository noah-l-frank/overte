"""Persistent host VM for actual pinned Emote callbacks, not native execution."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import select
import subprocess
import uuid
import weakref
from adapters.native_feature_observation import need
from adapters.emote_source_profile import pins

PROGRAM=r'''
const readline=require('node:readline'),vm=require('node:vm');
let now=0,serial=0,random=0,events=[],states=[],timers=new Map(),resources=new Map(),ended=false;
function signal(){const slots=[];return{connect:f=>slots.push(f),disconnect:f=>{const i=slots.indexOf(f);if(i>=0)slots.splice(i,1);},
 emit:(...args)=>{for(const f of [...slots])f(...args);}};}
const button={clicked:signal()},tablet={screenChanged:signal(),fromQml:signal(),addButton:()=>button,removeButton:()=>{},
 sendToQml:value=>states.push(value),loadQMLSource:source=>{tablet.screenChanged.emit('QML',source);tablet.fromQml.emit({method:'phoneEmote.ready'});},
 gotoHomeScreen:()=>tablet.screenChanged.emit('Home','')};
const ending=signal();
readline.createInterface({input:process.stdin}).on('line',line=>{
 try{const input=JSON.parse(line);now=input.epochMs;
 if(input.operation==='init'){
  const math=Object.create(Math);math.random=()=>[0,.42,.84][random++%3];
  vm.runInNewContext(input.code,{Math:math,isFinite,AnimationCache:{prefetch:url=>{const value={state:3};resources.set(url,value);return value;},
   getAnimation:()=>({frames:Array.from({length:120},()=>({}))})},MyAvatar:{
   overrideAnimation:(url,framesPerSecond,loop,firstFrame,lastFrame)=>events.push({method:'overrideAnimation',epochMs:now,
    request:{url,framesPerSecond,loop,firstFrame,lastFrame}}),restoreAnimation:()=>events.push({method:'restoreAnimation',epochMs:now})},
   Script:{resolvePath:path=>new URL(path,input.scriptUrl).href,setTimeout:(callback,delay)=>{const id=++serial;timers.set(id,{callback,due:now+delay});return id;},
    clearTimeout:id=>timers.delete(id),scriptEnding:ending},Tablet:{getTablet:()=>tablet}},{timeout:1000});
 }else if(input.operation==='entry')button.clicked.emit();
 else if(input.operation==='play')tablet.fromQml.emit({method:'phoneEmote.play',name:input.name});
 else if(input.operation==='home')tablet.gotoHomeScreen();
 else if(input.operation==='advance'){
  for(const [id,timer] of [...timers.entries()].sort((a,b)=>a[1].due-b[1].due)){
   if(timer.due<=now&&timers.has(id)){timers.delete(id);timer.callback();}
  }
 }else if(input.operation==='resource')resources.get(input.url).state=input.state;
 else if(input.operation==='ending'){ending.emit();ended=true;}
 else throw Error('unknown operation');
 process.stdout.write(JSON.stringify({events,states,timers:[...timers.entries()].map(([id,t])=>({id,due:t.due})),ended})+'\n');
 }catch(error){process.stdout.write(JSON.stringify({error:String(error)})+'\n');}
});
'''


class ActualEmoteVM:
    def __init__(self,test,*,epoch=20000,root='qrc:/scripts'):
        path=Path(__file__).resolve().parents[4]/'scripts/system/+android_phoneInterface/phoneEmote.js'
        code=path.read_bytes();utf16=code.decode().encode('utf-16le');sha=hashlib.sha256(utf16).hexdigest()
        matching=[row for row in pins() if row['sourcePath'].endswith('/phoneEmote.js') and row['sha256']==sha and row['codeUnits']==len(utf16)//2]
        need(len(matching)==1);self.pin=deepcopy(matching[0])
        self.process=subprocess.Popen(['node','-e',PROGRAM],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,bufsize=1)
        test.addCleanup(self.close);self.root=root;self.epoch=epoch;self.original_code=code;self.state=None
        self.command('init',code=code.decode(),scriptUrl=root+'/system/+android_phoneInterface/phoneEmote.js')

    def command(self,operation,**fields):
        need(self.process.poll() is None)
        self.process.stdin.write(json.dumps(dict(operation=operation,epochMs=self.epoch,**fields))+'\n');self.process.stdin.flush()
        readable,_,_=select.select([self.process.stdout],[],[],3);need(bool(readable))
        raw=self.process.stdout.readline();need(bool(raw));value=json.loads(raw);need('error' not in value)
        self.state=deepcopy(value);return value

    def advance(self,epoch):
        need(epoch>=self.epoch);self.epoch=epoch;return self.command('advance')

    def close(self):
        if self.process.poll() is None:
            self.process.stdin.close()
            try:self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:self.process.terminate();self.process.wait(timeout=2)
        self.process.stdout.close();self.process.stderr.close()


def normal_ui(test,*,clock=None):
    """Ordinary token UI dispatches actual pinned JS callbacks exactly once."""
    from adapters.token_emote_ui import TokenEmoteUI
    from ios.adapters.emote_controls import IOSEmoteIO,project
    from ios.self_tests.test_ios_emote_controls import NativeBoundary
    vm=ActualEmoteVM(test)
    class Root:
        def __init__(self):self.id=str(uuid.uuid4())
    class Native(NativeBoundary):
        def __init__(self):
            self.root=None;self.roots=[];super().__init__()
        @property
        def clock(self):return self._clock if clock is None else clock.time
        @clock.setter
        def clock(self,value):
            if clock is None:self._clock=value
            else:clock.time=value
        def sleep(self,seconds):
            super().sleep(seconds);vm.advance(20000+round(self.clock*1000));self.sync()
        def sync(self):
            self.active=vm.state['states'][-1]['active'] if self.page and vm.state['states'] else ''
            if self.page and self.root is None:self.root=Root();self.roots.append(weakref.ref(self.root))
            elif not self.page:self.root=None
        def capture(self):
            value=super().capture();value['emoteControlsVersion']=2
            roots=[]
            for ref in self.roots:
                root=ref()
                if root is not None:roots.append(dict(rootId=root.id,qmlSource=vm.root+'/system/+android_phoneInterface/PhoneEmote.qml',
                    activeName=self.active,visible=self.tablet and self.page,enabled=True,attached=self.page,windowPresent=self.tablet))
            value['emoteInventory']=dict(iosEmoteUiInventoryVersion=1,complete=True,roots=roots)
            return value
        def deliver(self,request):
            rows=project(self.capture())['controls'];identifier=next(row['id'] for row in rows if row['token']==request['fieldToken'])
            super().deliver(request);vm.advance(20000+round(self.clock*1000))
            if identifier=='emote.entry':vm.command('entry')
            elif identifier=='tablet.home':vm.command('home')
            elif identifier.startswith('emote.play.'):vm.command('play',name=identifier[len('emote.play.'):])
            self.sync()
    native=Native();io=IOSEmoteIO(native)
    def original_source(value):
        for row in value['controls']:
            if row['id']=='emote.page':row['componentSourceSha256']=hashlib.sha256((vm.root+'/system/+android_phoneInterface/PhoneEmote.qml').encode()).hexdigest()
        return value
    native.transform=original_source
    return vm,native,TokenEmoteUI(io,native.intent,monotonic=lambda:native.clock,sleep=native.sleep)
