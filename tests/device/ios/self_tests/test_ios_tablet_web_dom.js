// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Actual passive observer and reference handler; UIKit/DOM SDKs are modeled.
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const root=path.resolve(__dirname,'../../../..');
const source=require(path.join(root,'tests/device/native/ios_tablet_web_dom.js'));
const reference=fs.readFileSync(path.join(root,'tests/device/fixture/parity/reference.js'),'utf8');
function page({inline=false,bridge=true,inlineToken='c'.repeat(32),random=null}={}) {
    let epoch=100000,reading=false;const nodes=new Map(),handlers=new Map(),callbacks=[],outbound=[];
    const doc={readyState:'complete',title:inline?'Actual owned inline':'Actual original HTTP',activeElement:null,
        addEventListener(kind,callback) { if (!handlers.has(kind)) handlers.set(kind,[]);handlers.get(kind).push(callback); },
        getElementById(id) { return nodes.get(id)||null; },querySelectorAll(selector) {
            if (selector[0]==='#') return nodes.has(selector.slice(1))?[nodes.get(selector.slice(1))]:[];
            if (selector==='a[href]') return Array.from(nodes.values()).filter(n=>n.href);
            if (selector==='meta[name="overte-fixture-owner"]') return [{content:'a'.repeat(32)}];
            if (selector==='meta[name="overte-fixture-response"]') return inline?[]:[{content:'b'.repeat(32)}];
            throw Error('Unexpected selector '+selector);
        }};
    const ids=['increment','counter','text','number','password','multiline','inputStatus','scroll','scrollStatus','file','filePreview','fileStatus',
        'video','play','pause','seek','seekStart','mediaStatus','bridge','bridgeStatus','injection','back','reload','foreign','navigate','navigationStatus','document',
        'same-origin','feature-marker',...(inline?[]:['recovery','reference'])];
    for (const id of ids) {
        let value='';const node={nodeType:1,id,tagName:['text','number','password','foreign','file'].includes(id)?'INPUT':id==='multiline'?'TEXTAREA':
            ['same-origin','recovery','reference'].includes(id)?'A':id==='feature-marker'?'IMG':'BUTTON',type:id==='text'?'text':id==='foreign'?'url':id,
            textContent:'',disabled:false,isConnected:true,style:{},paused:true,currentTime:0,volume:1,muted:true,
            rect:{left:20,top:120,right:220,bottom:160},getBoundingClientRect() { return {...this.rect}; },
            getAttribute(name) { assert.equal(name,'aria-label');return ['text','foreign'].includes(id)?'Owned Tablet '+id:null; },
            addEventListener() {},focus() { assert(!reading);doc.activeElement=this; },click() { throw Error('Observer must never click'); }};
        Object.defineProperty(node,'value',{get() { if (id==='password' && reading) throw Error('Password read');return value; },set(v) { assert(!reading);value=v; }});
        if (id==='same-origin') node.href='http://fixture.invalid/'+(inline?'index.html?page=second':'page-b.html');
        if (id==='recovery'||id==='reference') node.href='http://fixture.invalid/'+id+'.html';
        nodes.set(id,node);
    }
    const global={document:doc,Date:{now:()=>++epoch},URL,Promise,innerWidth:500,innerHeight:800,scrollX:0,scrollY:100,
        visualViewport:{width:500,height:400,offsetLeft:0,offsetTop:100,pageLeft:0,pageTop:100,scale:1},
        crypto:{getRandomValues(bytes) { if(random)random(bytes);else bytes.fill(17);return bytes; }},setInterval() { return 1; },setTimeout() { return 1; },
        getComputedStyle() { return {display:'block',visibility:'visible'}; },addEventListener() {},
        location:{href:inline?'http://'+inlineToken+'.overte-inline.invalid/index.html':'http://fixture.invalid/reference.html',pathname:'/reference.html',search:'',origin:'http://fixture.invalid',reload() {}},
        history:{back() {}},console};global.window=global;global.top=global;
    if (bridge) global.EventBridge={emitWebEvent(message) { assert(!reading);outbound.push(message); },scriptEventReceived:{connect(callback) { callbacks.push(callback); }}};
    const observer=source(global);vm.runInContext(reference,vm.createContext(global));
    function event(id,kind,trusted=true,extra={}) {
        const current={type:kind,target:nodes.get(id),timeStamp:++epoch,isTrusted:trusted,clientX:120,clientY:140,pointerId:7,pointerType:'touch'};
        Object.defineProperties(current,Object.getOwnPropertyDescriptors(extra));
        for (const callback of handlers.get(kind)||[]) callback(current);
        return current;
    }
    return {nodes,doc,global,callbacks,outbound,observer,event,
        click(id,trusted=true) { event(id,'pointerdown',trusted);event(id,'pointerup',trusted);event(id,'click',trusted);const node=nodes.get(id);if(node.onclick) node.onclick(); },
        read(requestId='ios-'+'f'.repeat(32)) { reading=true;try{return observer.read(requestId);}finally{reading=false;} }};
}
module.exports={page};
if (require.main===module) (async()=>{
    for (const inline of [false,true]) {
        const p=page({inline});const initial=p.read();assert.equal(initial.document.responseId,inline?null:'b'.repeat(32));
        assert.equal(initial.elements.some(n=>n.id==='recovery'),!inline);assert.equal(initial.document.visualViewport.offsetTop,100);
        p.nodes.get('text').value='Überte 🙂';p.doc.activeElement=p.nodes.get('text');p.event('text','focusin');p.event('text','input');
        assert.equal(p.read().editor.text,'Überte 🙂');assert(p.read().editor.focused);
        p.click('bridge');assert.equal(p.outbound.length,1);const sent=JSON.parse(p.outbound[0]);const reply=JSON.stringify({...sent,surface:'tablet'});
        for (const callback of p.callbacks) callback(reply);await Promise.resolve();await Promise.resolve();
        const result=p.read();assert.equal(result.echoes.length,1);assert.equal(result.echoes[0].message,reply);
        const click=result.events.find(n=>n.kind==='click');assert(click.trusted);assert.equal(click.target.id,'bridge');
        assert.equal(click.x,120);assert.equal(click.pointerId,null);assert(!('key' in click));
        result.events[0].target.id='poison';assert.notEqual(p.read().events[0].target.id,'poison');
        const hostile={};for(const key of ['key','data','inputType'])Object.defineProperty(hostile,key,{get(){throw Error('Private '+key+' read');},enumerable:true});
        p.event('password','compositionstart',true,hostile);
        // Invoke actual installed observers with throwing secret accessors.
        p.event('password','input',true,hostile);p.event('password','compositionend',true,hostile);
        const privacy=p.read();assert(privacy.compositions.every(n=>n.active===false));
        assert(!JSON.stringify(privacy).includes('secret-password'));assert(privacy.events.filter(n=>n.target.id===null).length>=3);
        p.nodes.get('text').rect.top=50;p.nodes.get('text').rect.bottom=90;assert(!p.read().elements.find(n=>n.id==='text').visible);
        assert(Object.isFrozen(p.observer));assert.equal(typeof p.observer.retire,'undefined');
    }
    const foreign=page({bridge:false});foreign.click('bridge');assert.equal(foreign.outbound.length,0);assert.equal(foreign.read().echoes.length,0);
    const untrusted=page();untrusted.click('bridge',false);assert(untrusted.read().events.every(n=>n.trusted===false));
    const pw=page();pw.nodes.get('text').type='password';assert.throws(()=>pw.read(),/UNAVAILABLE/);
    const overflow=page();for(let n=0;n<1025;n++)overflow.event('text','input');assert.throws(()=>overflow.read(),/UNAVAILABLE/);
    process.stdout.write('Tablet original passive DOM, reference echo, trust, viewport and privacy boundaries passed\n');
})().catch(error=>{process.stderr.write(error.stack+'\n');process.exitCode=1;});
