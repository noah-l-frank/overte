"""Actual generated app/reference/observer JS with explicit native boundaries.

The JS executes on host V8; UIKit, Qt and native event sources are modeled.
No WDA, native compilation, device, inferred successful counters or VM worker.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import re
import select
import subprocess
from ios.self_tests.test_ios_tablet_web_app_origin import originals_boundary,admit,EPOCH
from ios.self_tests.test_ios_tablet_web_documents import originals as document_originals
from ios.self_tests.test_ios_tablet_web_sources import stamp,RUN,ROOT

REPO=Path(__file__).resolve().parents[4]


def actual_js(*,bridge=True,trusted=True,session=False):
    values=originals_boundary();app=admit(values);url=app['profile']['assignedUrl']
    program=r'''
const vm=require('vm'),files=__FILES__,url=__URL__,root=__ROOT__,record={},page=require('./tests/device/ios/self_tests/test_ios_tablet_web_dom.js').page({bridge:__BRIDGE__});
let now=__EPOCH__+1000,callback;const tick=()=>now+=10;page.global.Date.now=tick;
page.global.location.href=root+'tickets/'+'b'.repeat(32)+'/reference.html';
const tablet={addButton:()=>({clicked:{connect(){}}}),webEventReceived:{connect(f){callback=f}},emitScriptEvent(message){
record.reply=message;record.stack=new Error().stack;record.apiEntered=tick();record.slot=tick();record.slotEntered=tick();
record.page=tick();record.pageEntered=tick();record.pageReturn=tick();record.pageReturned=tick();record.pageFinally=tick();
record.slotReturn=tick();record.slotReturned=tick();record.slotFinally=tick();record.apiReturned=tick();record.apiFinally=tick();
Promise.resolve().then(()=>{for(const received of page.callbacks)received(message)});}};
const Script={require:p=>{const module={exports:{}};vm.runInNewContext(files[p.replace(/^\.\//,'')],{module});return module.exports},scriptEnding:{connect(){}}};
vm.runInNewContext(files['script.js'],{Script,Tablet:{getTablet:()=>tablet}},{filename:url});
if(__BRIDGE__)page.global.EventBridge.emitWebEvent=message=>{record.message=message;record.envelope=tick();record.delivery=tick();
callback(message);record.deliveryReturn=tick();record.envelopeReturn=tick();};
// Real UIEvent/contact end precedes asynchronous DOM dispatch, intentionally.
record.touchBegin=tick();record.touchEnd=tick();record.touchReturned=tick();
page.click('bridge',__TRUSTED__);
(async()=>{await Promise.resolve();await Promise.resolve();await Promise.resolve();record.body=page.read('ios-'+(1).toString(16).padStart(32,'0'));
if(record.stack)record.frames=record.stack.split('\n').filter(line=>line.includes(url)).map(line=>{const m=line.match(/:(\d+):(\d+)\)?$/);return {line:Number(m[1]),column:Number(m[2])}});
process.stdout.write(JSON.stringify(record));})().catch(error=>{console.error(error);process.exitCode=1});
'''
    inputs=dict(FILES={key:raw.decode() for key,raw in values[-1].items()},URL=url,ROOT=ROOT,EPOCH=EPOCH,BRIDGE=bridge,TRUSTED=trusted)
    program=re.sub(r'__(FILES|URL|ROOT|EPOCH|BRIDGE|TRUSTED)__',lambda m:json.dumps(inputs[m[1]]),program)
    assert type(session) is bool
    if session:
        # Declared before FIRST native source capture. The same original page
        # and bridge execute once; each later command is ONLY passive read.
        original="process.stdout.write(JSON.stringify(record));"
        continuation=r'''process.stdout.write(JSON.stringify(record)+'\n');
const lines=require('node:readline').createInterface({input:process.stdin,crlfDelay:Infinity});
for await (const line of lines) {
 const request=JSON.parse(line);
 if(!Number.isSafeInteger(request.epochMs)||request.epochMs<=0||!/^ios-[a-f0-9]{32}$/.test(request.commandId))throw Error('Invalid declared passive query');
 now=Math.max(now,request.epochMs-10);
 const current=page.read(request.commandId);
 process.stdout.write(JSON.stringify(current)+'\n');
}'''
        assert program.count(original)==1;program=program.replace(original,continuation)
        return ActualDOMSession(program),app
    run=subprocess.run(['node','-e',program],cwd=REPO,capture_output=True,text=True,timeout=5)
    if run.returncode:raise AssertionError(run.stderr)
    return json.loads(run.stdout),app


class ActualDOMSession:
    """Original observer JS in one real host Node page, no repeated UI input."""
    def __init__(self,program):
        self.process=subprocess.Popen(['node','-e',program],cwd=REPO,stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,bufsize=1)
        try:self.initial=self._received()
        except BaseException:
            self.close();raise
    def _received(self):
        if not select.select([self.process.stdout],[],[],5)[0]:raise AssertionError('Actual passive DOM did not return')
        value=self.process.stdout.readline()
        if not value:raise AssertionError('Actual passive DOM source closed')
        return json.loads(value)
    def read(self,command_id,epoch_ms):
        self.process.stdin.write(json.dumps(dict(commandId=command_id,epochMs=epoch_ms))+'\n');self.process.stdin.flush()
        return self._received()
    def close(self):
        if self.process.stdin:self.process.stdin.close()
        try:self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:self.process.terminate();self.process.wait(timeout=5)
        for stream in (self.process.stdout,self.process.stderr):
            if stream:stream.close()


def fixture(*,bridge=True,trusted=True):
    js,app=actual_js(bridge=bridge,trusted=trusted);ledger,sources,document,browser=document_originals(js['body'])
    view=document['source']['nativeView'];ui_view=document['source']['presentationAfter']['view'];creation=deepcopy(ledger['events'][0]['identity'])
    def event(kind,epoch,detail):
        sequence=len(ledger['events'])+1;ledger['events'].append(dict(sequence=sequence,eventId=format(sequence,'032x'),kind=kind,clock=stamp(epoch),identity=deepcopy(view),detail=deepcopy(detail)));return sequence
    if bridge:
        envelope=event('native-envelope',js['envelope'],dict(envelope=json.dumps(dict(type=6,object='eventBridge',method='emitWebEvent',args=[js['message']])),documentNonce=view['nonce'],frame=view['url'],mainFrame=True))
        delivery=event('script-delivery',js['delivery'],dict(message=js['message']))
        slot=event('script-event-slot',js['slot'],dict(message=js['reply'],active=True));page=event('page-reply',js['page'],dict(message=js['reply']))
        event('signal-return',js['pageReturn'],dict(entry=page));event('signal-return',js['slotReturn'],dict(entry=slot))
        event('signal-return',js['deliveryReturn'],dict(entry=delivery));event('signal-return',js['envelopeReturn'],dict(entry=envelope))
    ledger['eventSequence']=len(ledger['events'])
    association=dict(view=ui_view,identity=creation,bound=stamp(99003));original_source=dict(association,ancestry=[ui_view]);end=js['body']['capturedEpochMs']
    objects=[dict(id=id_,kind=kind,born=stamp(born),expired=None,alive=True) for id_,kind,born in ((ui_view,'view',99001),('a'*32,'window',99001),('b'*32,'touch',js['touchBegin']),('c'*32,'event',js['touchBegin']))]
    contact=dict(id='d'*32,kind='touch',object='b'*32,target=ui_view,window='a'*32,source=deepcopy(original_source),began=stamp(js['touchBegin']),ended=stamp(js['touchEnd']),phase=3,active=False)
    def dispatch(index,phase,entered,returned):return dict(sequence=index,event='c'*32,entered=stamp(entered),returned=stamp(returned),**{'finally':stamp(returned)},
        phases=[dict(object='b'*32,contact=contact['id'],kind='touch',phase=phase,target=ui_view,window='a'*32,source=deepcopy(original_source))])
    touches=dict(iosUIKitInputVersion=2,commandId='ios-'+'1'*32,runId=RUN,fixtureUrl=ROOT,instance='a'*32,sequence=1,processId=31,
        clockDomain='native-main-ios-uikit-input',clockBefore=stamp(end),clockAfter=stamp(end),complete=True,installed=True,
        applicationClass='ActualRuntimeApplication',installation=stamp(90000),failure=None,dispatchSequence=2,pendingDispatches=[],objects=objects,
        targets=[association],contacts=[contact],dispatches=[dispatch(1,0,js['touchBegin'],js['touchBegin']),dispatch(2,3,js['touchEnd'],js['touchReturned'])])
    emitter=dict(iosWebScriptEmissionsVersion=1,commandId='ios-'+'2'*32,runId=RUN,fixtureUrl=ROOT,instance='e'*32,sequence=1,processId=31,
        clockDomain='native-process-ios-web-script-emissions',clockBefore=stamp(end),clockAfter=stamp(end),complete=True,
        callSequence=0,queueSequence=0,sinkSequence=0,objects=[],calls=[],queues=[],sinks=[])
    if bridge:
        emitter['objects']=[dict(id='f'*32,born=stamp(js['apiEntered']),expired=None,alive=True)]
        frames=[dict(scriptId=71,line=actual['line'],column=actual['column'],sourceUrlSha256=pin['sourceUrlSha256'],
            compiled=dict(urlSha256=pin['sourceUrlSha256'],encoding='utf-16le-code-units',codeUnits=pin['codeUnits'],sha256=pin['sha256'],firstObservedEpochMs=EPOCH+4),isEval=False,isConstructor=False)
            for actual,pin in zip(js['frames'],app['locations'])]
        call=dict(id='1'*32,sequence=1,object='f'*32,surface='tablet',target='com.highfidelity.interface.tablet.system',message=js['reply'],
            caller=dict(callerVersion=1,method='emitScriptEvent',sequence=1,invokedEpochMs=js['apiEntered'],manager=deepcopy(app['manager']),code=deepcopy(app['profile']['code']),
                emitStack=dict(emitStackVersion=1,instance='2'*32,complete=True,frames=frames)),entered=stamp(js['apiEntered']),returned=stamp(js['apiReturned']),**{'finally':stamp(js['apiFinally'])})
        emitter.update(callSequence=1,sinkSequence=2,calls=[call])
        emitter['sinks']=[dict(id=id_,sequence=index,kind=kind,call=call['id'],identity=deepcopy(view),message=js['reply'],entered=stamp(js[prefix+'Entered']),returned=stamp(js[prefix+'Returned']),**{'finally':stamp(js[prefix+'Finally'])})
            for index,(id_,kind,prefix) in enumerate((('3'*32,'script-event-slot','slot'),('4'*32,'page-reply','page')),1)]
    return dict(ledger=ledger,sources=sources,document=document,touches=touches,emitter=emitter,profile=app['profile'],locations=app['locations']),js
