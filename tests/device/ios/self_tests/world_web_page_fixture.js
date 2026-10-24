// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Original product input/reference/observer JavaScript; native/DOM SDKs modeled.
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '../../../..');
const source = require(path.join(root, 'tests/device/native/ios_world_web_dom.js'));
const cpp = fs.readFileSync(path.join(root, 'ios/web/IOSWebView.mm'), 'utf8');
const reference = fs.readFileSync(path.join(root, 'tests/device/fixture/parity/reference.js'), 'utf8');
function inputBody(name) {
    const section = cpp.slice(cpp.indexOf('void IOSWebView::' + name + '('));
    const start = section.indexOf('R"JS(') + 5;
    assert(start >= 5);return section.slice(start, section.indexOf(')JS"', start));
}
const pointer = inputBody('pointerEvent'), key = inputBody('keyEvent');
function page({bridge = true, url = 'http://127.0.0.1/reference.html', html = '', epoch: initialEpoch = 100000, onOutbound = null, markerScript = '', currentTicket = null} = {}) {
    let epoch = initialEpoch, birth = 0;const navigations=[];let ticket=currentTicket;
    const handlers = new Map(), intervals = [], callbacks = [], outbound = [], nodes = new Map();
    const doc = {readyState:'complete',title:(html.match(/<title>([^<]*)<\/title>/)||[])[1]||'Actual reference document',activeElement:null,
        addEventListener(kind, callback) { if (!handlers.has(kind)) handlers.set(kind, []);handlers.get(kind).push(callback); },
        getElementById(id) { return nodes.get(id) || null; },
        querySelectorAll(selector) {
            if (selector[0] === '#') return nodes.has(selector.slice(1)) ? [nodes.get(selector.slice(1))] : [];
            if (selector === 'a[href]') return [nodes.get('same-origin'),nodes.get('recovery'),nodes.get('reference')];
            if (selector === 'meta[name="overte-fixture-owner"]') return [{content:(html.match(/name="overte-fixture-owner" content="([^"]+)"/)||[])[1]||'a'.repeat(32)}];
            if (selector === 'meta[name="overte-fixture-response"]') return [{content:(html.match(/name="overte-fixture-response" content="([^"]+)"/)||[])[1]||'b'.repeat(32)}];
            throw Error('Unexpected real observer selector: ' + selector);
        },
        elementFromPoint(x,y) { return Array.from(nodes.values()).find(n => !n.layoutHidden && x >= n.rect.left && x < n.rect.right && y >= n.rect.top && y < n.rect.bottom); }
    };
    for (const id of ['increment','counter','text','number','password','multiline','inputStatus','scroll','scrollStatus',
        'file','filePreview','fileStatus','video','play','pause','seek','seekStart','mediaStatus','bridge','bridgeStatus',
        'injection','back','reload','foreign','navigate','navigationStatus','document','same-origin','recovery','reference','feature-marker']) {
        const index = birth++, column = index % 4, row = Math.floor(index / 4);
        const node = {nodeType:1,id,tagName:['text','number','password','foreign','file'].includes(id) ? 'INPUT' :
            id === 'multiline' ? 'TEXTAREA' : ['same-origin','recovery','reference'].includes(id) ? 'A' : id === 'feature-marker' ? 'IMG' : 'BUTTON',
            type:id === 'text' ? 'text' : id === 'foreign' ? 'url' : id,value:'',textContent:'',disabled:false,isConnected:true,
            src:'',getAttribute(name){return name==='src'?this.src:null;},readOnly:false,selectionStart:0,selectionEnd:0,selectionDirection:'none',style:{},paused:true,currentTime:0,volume:1,muted:true,
            rect:{left:column*180,top:row*64,right:column*180+160,bottom:row*64+48},
            getBoundingClientRect() { return {...this.rect}; },
            addEventListener() {},matches(selector) { return selector === ':disabled' && this.disabled; },
            setSelectionRange(start,end,direction) { this.selectionStart=start;this.selectionEnd=end;this.selectionDirection=direction; },
            focus() { doc.activeElement=this; },
            click() { this.dispatchEvent({type:'click',isTrusted:false,timeStamp:++epoch,clientX:0,clientY:0,button:0});if(this.href)navigations.push({kind:'navigate',url:this.href}); },
            dispatchEvent(event) {
                event.target=this;
                for (const callback of handlers.get(event.type) || []) callback(event);
                if (typeof this['on'+event.type] === 'function') this['on'+event.type].call(this,event);
                return event.defaultPrevented !== true;
            }
        };
        if (id === 'same-origin') node.href='http://127.0.0.1/feature-fixture/v1/runs/'+ 'a'.repeat(32)+'/tickets/'+ 'c'.repeat(32)+'/page-b.html';
        if (id === 'recovery') node.href='http://127.0.0.1/recovery.html';
        if (id === 'reference') node.href='http://127.0.0.1/reference.html';
        const tags=Array.from(html.matchAll(/<[^>]+>/g));
        const tag=tags.find(match => new RegExp('id=[\"\']'+id+'[\"\']').test(match[0])) || (id==='same-origin'&&tags.find(match=>/^<a\s/.test(match[0])&&/href=[\"\']page-b.html[\"\']/.test(match[0])));
        const href=tag && (tag[0].match(/href=[\"\']([^\"\']+)/)||[])[1];
        if(href)node.href=new URL(href,url).href;
        const source=tag && (tag[0].match(/src=[\"\']([^\"\']+)/)||[])[1];if(source)node.src=source;
        const compact={text:[8,118,842,160],bridge:[8,164,408,206],'bridgeStatus':[8,210,842,234],'same-origin':[8,238,408,280],recovery:[434,238,842,280],reference:[8,284,408,326],back:[434,284,842,326],reload:[8,330,408,372],foreign:[8,380,842,422],navigate:[8,426,408,468],'feature-marker':[442,8,842,108]};
        if(html.includes('owned-browser-controls-v1')){node.layoutHidden=!compact[id]&&id!=='document';if(compact[id]){const [left,top,right,bottom]=compact[id];node.rect={left,top,right,bottom}}if(id==='document')node.rect={left:8,top:34,right:420,bottom:64}}
        nodes.set(id,node);
    }
    const global = {document:doc,innerWidth:850,innerHeight:661,Date:{now:() => ++epoch},URL,
        location:{get href(){return url},set href(value){navigations.push({kind:'navigate',url:String(value)})},pathname:new URL(url).pathname,search:new URL(url).search,origin:new URL(url).origin,reload(){navigations.push({kind:'reload'})}},
        history:{back(){navigations.push({kind:'back'})}},Promise,crypto:{getRandomValues(bytes) { require('node:crypto').randomFillSync(bytes);return bytes; }},
        setInterval(callback) { intervals.push(callback);return intervals.length; },setTimeout() { return 1; },
        getComputedStyle(node) { return {display:node.layoutHidden?'none':'block',visibility:'visible'}; },
        addEventListener() {},MouseEvent:class { constructor(type,args) { Object.assign(this,args,{type,isTrusted:false,timeStamp:++epoch}); } },
        KeyboardEvent:class { constructor(type,args) { Object.assign(this,args,{type,isTrusted:false,timeStamp:++epoch}); } },
        InputEvent:class { constructor(type,args) { Object.assign(this,args,{type,isTrusted:false,timeStamp:++epoch}); } },
        fetch:async function(path){if(!path.endsWith('/current'))throw Error('Unexpected actual fixture fetch');return {ok:true,json:async()=>({ticket})}},console
    };
    global.top=global;global.window=global;
    if (bridge) global.EventBridge={emitWebEvent(message) { outbound.push(message);if(onOutbound)onOutbound(message); },scriptEventReceived:{connect(callback) { callbacks.push(callback); }}};
    const observer=source(global), context=vm.createContext(global);vm.runInContext(reference,context);if(markerScript)vm.runInContext(markerScript,context);
    function execute(body,args) { return vm.runInContext(body.replace('%1',JSON.stringify(args)),context); }
    function touch(id,type) {
        const rect=nodes.get(id).rect;
        return execute(pointer,[type,(rect.left+rect.right)/2,(rect.top+rect.bottom)/2,0]);
    }
    return {doc,nodes,global,observer,outbound,callbacks,touch,execute,key,navigations,refresh(value){ticket=value;for(const callback of intervals)callback();},clock:()=>epoch,setClock(value){epoch=Math.max(epoch,value)},
        read:(request='ios-'+'f'.repeat(32)) => observer.read(request)};
}

module.exports={page,pointer,key};
if(require.main===module){
 const readline=require('node:readline');const emitter=require('./world_web_emission_boundary');
 let current=null,worker=null,epoch=0;const created=[],deleted=[],workEvents=[],nativeEvents=[],emissionEvents=[];
 function signal(){const handlers=new Set();return{connect(fn){handlers.add(fn)},disconnect(fn){handlers.delete(fn)},emit(...args){let result;for(const fn of [...handlers])result=fn(...args);return result}}}
 function stamp(){epoch=Math.max(epoch,current?current.clock():0)+1;if(current)current.setClock(epoch);return epoch}
 function native(kind,detail,metadata={}){nativeEvents.push({kind,detail,epoch:stamp(),...metadata});return nativeEvents.length}
 function outbound(message){
  if(!worker)return;
  const envelope=native('native-envelope',{message}),delivery=native('script-delivery',{message});
  worker.received.emit(worker.entity,message);
  native('signal-return',{entry:delivery});native('signal-return',{entry:envelope});
 }
 function start(input){
  if(worker)throw Error('Actual worker already exists');const received=signal(),ending=signal();
  worker={entity:input.entity,received,ending,assignedUrl:input.assignedUrl,caller:input.caller};
  const context={Camera:input.camera,Vec3:{sum:(a,b)=>({x:a.x+b.x,y:a.y+b.y,z:a.z+b.z}),multiplyQbyV:(_q,v)=>v},
   Script:{scriptEnding:ending,require(name){if(name!=='./companion.js')throw Error('foreign actual module');const module={exports:{}};vm.runInNewContext(input.companion,{module});return module.exports}},
   Entities:{webEventReceived:received,addEntity(properties,host){created.push({id:input.entity,properties,host,epoch:stamp()});return input.entity},
    deleteEntity(id){deleted.push({id,epoch:stamp()})},emitScriptEvent(id,message){
     const call=worker.caller&&worker.assignedUrl?require('node:crypto').randomBytes(16).toString('hex'):null;
     if(call){const invoked=stamp(),stack=emitter.snapshot(worker.assignedUrl,stamp);
      emissionEvents.push({kind:'api-enter',call,target:String(id),message,caller:{...worker.caller,sequence:emissionEvents.filter(row=>row.kind==='api-enter').length+1,invokedEpochMs:invoked,emitStack:stack},epoch:stamp()});}
     try{
      const slot=native('script-event-slot',{message,active:!!current},{emissionCall:call}),page=native('page-reply',{message},{emissionCall:call});
      if(current)for(const callback of current.callbacks)callback(message);
      native('signal-return',{entry:page});native('signal-return',{entry:slot});
      if(call)emissionEvents.push({kind:'api-return',call,epoch:stamp()});
     }finally{if(call)emissionEvents.push({kind:'api-finally',call,epoch:stamp()})}
    }},Test:{featureIOSWorldWebEvent(value){workEvents.push({value:JSON.parse(JSON.stringify(value)),epoch:stamp()})}}};
  vm.runInNewContext(input.script,context,{filename:input.assignedUrl});
 }
 const lines=readline.createInterface({input:process.stdin,crlfDelay:Infinity});let chain=Promise.resolve();
 lines.on('line',line=>{chain=chain.then(async()=>{
  const input=JSON.parse(line);epoch=Math.max(epoch,input.epoch||0);
  if(input.op==='start')start(input);
  if(input.op==='open')current=page({...input,onOutbound:outbound});
  if(input.op==='stop'){if(!worker)throw Error('No actual worker');worker.ending.emit();}
  if(current)current.setClock(epoch);
  if(['pointer','key','key-batch','reply','read','dom-read'].includes(input.op)&&!current)throw Error('No actual document context');
  if(input.op==='pointer'){const entry=native('pointer-enter',{type:input.args[0],x:input.args[1],y:input.args[2],width:850,height:661,button:input.args[3],codeSha256:require('node:crypto').createHash('sha256').update(pointer.replace('%1',JSON.stringify(input.args))).digest('hex')});
   const result=current.execute(pointer,input.args);native('callback-enter',{entry,result:{error:false,result}});native('callback-return',{entry});}
  if(input.op==='key'){const entry=native('key-enter',{text:input.args[0],key:input.args[1],modifiers:input.args[2]?33554432:0});const evaluation=native('evaluation-enter',{codeSha256:require('node:crypto').createHash('sha256').update(key.replace('%1',JSON.stringify(input.args))).digest('hex')});current.execute(key,input.args);native('signal-return',{entry});native('callback-enter',{entry:evaluation,result:{error:false}});native('callback-return',{entry:evaluation});}
  if(input.op==='key-batch')for(const item of input.items){
   const executedCodeSha=require('node:crypto').createHash('sha256').update(key.replace('%1',JSON.stringify(item.args))).digest('hex');let error=false;
   try{current.execute(key,item.args)}catch(_failure){error=true}
   native('callback-enter',{entry:item.entry,result:{error}},{sourceEntry:true,executedCodeSha});native('callback-return',{entry:item.entry},{sourceEntry:true});
  }
  if(input.op==='reply')for(const callback of current.callbacks)callback(input.message);
  if(current&&input.currentTicket)current.refresh(input.currentTicket);
  await Promise.resolve();await Promise.resolve();await Promise.resolve();await Promise.resolve();
  const domEntry=input.op==='dom-read'?native('dom-read-enter',{requestId:input.requestId}):null;
  const document=current?current.read(input.requestId):null;epoch=Math.max(epoch,current?current.clock():0);
  if(domEntry!==null){native('callback-enter',{entry:domEntry,result:{error:false}});native('callback-return',{entry:domEntry});}
  const result={...(input.op==='start'?{keyProgram:key}:{}),document,epoch,outbound:current?current.outbound.splice(0):[],navigations:current?current.navigations.splice(0):[],
   created,deleted,workEvents,nativeEvents,emissionEvents,nodes:current?Array.from(current.nodes.values()).map(node=>({id:node.id,value:node.value,textContent:node.textContent,href:node.href||null,src:node.src,rect:node.rect})):[]};
  if(input.op==='close')current=null;
  process.stdout.write(JSON.stringify(result)+String.fromCharCode(10));
 }).catch(error=>{process.stdout.write(JSON.stringify({error:error.stack})+String.fromCharCode(10))})});
}
