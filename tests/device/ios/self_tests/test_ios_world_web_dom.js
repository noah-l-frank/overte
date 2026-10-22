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
function page({bridge = true} = {}) {
    let epoch = 100000, birth = 0;
    const handlers = new Map(), intervals = [], callbacks = [], outbound = [], nodes = new Map();
    const doc = {readyState:'complete',title:'Actual reference document',activeElement:null,
        addEventListener(kind, callback) { if (!handlers.has(kind)) handlers.set(kind, []);handlers.get(kind).push(callback); },
        getElementById(id) { return nodes.get(id) || null; },
        querySelectorAll(selector) {
            if (selector[0] === '#') return nodes.has(selector.slice(1)) ? [nodes.get(selector.slice(1))] : [];
            if (selector === 'a[href]') return [nodes.get('same-origin'),nodes.get('recovery'),nodes.get('reference')];
            if (selector === 'meta[name="overte-fixture-owner"]') return [{content:'a'.repeat(32)}];
            if (selector === 'meta[name="overte-fixture-response"]') return [{content:'b'.repeat(32)}];
            throw Error('Unexpected real observer selector: ' + selector);
        },
        elementFromPoint(x,y) { return Array.from(nodes.values()).find(n => x >= n.rect.left && x < n.rect.right && y >= n.rect.top && y < n.rect.bottom); }
    };
    for (const id of ['increment','counter','text','number','password','multiline','inputStatus','scroll','scrollStatus',
        'file','filePreview','fileStatus','video','play','pause','seek','seekStart','mediaStatus','bridge','bridgeStatus',
        'injection','back','reload','foreign','navigate','navigationStatus','document','same-origin','recovery','reference','feature-marker']) {
        const index = birth++, column = index % 4, row = Math.floor(index / 4);
        const node = {nodeType:1,id,tagName:['text','number','password','foreign','file'].includes(id) ? 'INPUT' :
            id === 'multiline' ? 'TEXTAREA' : ['same-origin','recovery','reference'].includes(id) ? 'A' : id === 'feature-marker' ? 'IMG' : 'BUTTON',
            type:id === 'text' ? 'text' : id === 'foreign' ? 'url' : id,value:'',textContent:'',disabled:false,isConnected:true,
            readOnly:false,selectionStart:0,selectionEnd:0,selectionDirection:'none',style:{},paused:true,currentTime:0,volume:1,muted:true,
            rect:{left:column*180,top:row*64,right:column*180+160,bottom:row*64+48},
            getBoundingClientRect() { return {...this.rect}; },
            addEventListener() {},matches(selector) { return selector === ':disabled' && this.disabled; },
            setSelectionRange(start,end,direction) { this.selectionStart=start;this.selectionEnd=end;this.selectionDirection=direction; },
            focus() { doc.activeElement=this; },
            click() { this.dispatchEvent({type:'click',isTrusted:false,timeStamp:++epoch,clientX:0,clientY:0,button:0}); },
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
        nodes.set(id,node);
    }
    const global = {document:doc,innerWidth:850,innerHeight:661,Date:{now:() => ++epoch},URL,
        location:{href:'http://127.0.0.1/reference.html',pathname:'/reference.html',search:'',origin:'http://127.0.0.1',reload() {}},
        history:{back() {}},Promise,crypto:{getRandomValues(bytes) { bytes.fill(17);return bytes; }},
        setInterval(callback) { intervals.push(callback);return intervals.length; },setTimeout() { return 1; },
        getComputedStyle() { return {display:'block',visibility:'visible'}; },
        addEventListener() {},MouseEvent:class { constructor(type,args) { Object.assign(this,args,{type,isTrusted:false,timeStamp:++epoch}); } },
        KeyboardEvent:class { constructor(type,args) { Object.assign(this,args,{type,isTrusted:false,timeStamp:++epoch}); } },
        InputEvent:class { constructor(type,args) { Object.assign(this,args,{type,isTrusted:false,timeStamp:++epoch}); } },
        console
    };
    global.top=global;global.window=global;
    if (bridge) global.EventBridge={emitWebEvent(message) { outbound.push(message); },scriptEventReceived:{connect(callback) { callbacks.push(callback); }}};
    const observer=source(global), context=vm.createContext(global);vm.runInContext(reference,context);
    function execute(body,args) { return vm.runInContext(body.replace('%1',JSON.stringify(args)),context); }
    function touch(id,type) {
        const rect=nodes.get(id).rect;
        return execute(pointer,[type,(rect.left+rect.right)/2,(rect.top+rect.bottom)/2,0]);
    }
    return {doc,nodes,global,observer,outbound,callbacks,touch,execute,key,
        read:() => observer.read('ios-'+'f'.repeat(32))};
}
(async () => {
    const p=page();assert.equal(p.touch('text','press'),true);p.touch('text','release');
    const referenceElement=p.read().elements.find(row => row.id === 'reference');
    assert.equal(referenceElement.href,'http://127.0.0.1/reference.html');assert(referenceElement.visible && referenceElement.enabled);
    p.execute(key,['Überte 🙂',0,false]);assert.equal(p.read().editor.text,'Überte 🙂');assert.equal(p.read().editor.focused,true);
    p.touch('bridge','press');p.touch('bridge','release');assert.equal(p.outbound.length,1);
    const message=JSON.parse(p.outbound[0]);assert.equal(message.action,'echo');
    const reply=JSON.stringify({...message,surface:'world'});for (const callback of p.callbacks) callback(reply);
    await Promise.resolve();await Promise.resolve();const original=p.read();
    assert.equal(original.echoes.length,1);assert.equal(original.echoes[0].message,reply);
    const click=original.events.findLast(row => row.kind === 'click');
    assert.equal(click.target.id,'bridge');assert.equal(click.trusted,false);assert.equal(click.x,0);
    const up=original.events[click.ordinal-2];assert.equal(up.kind,'mouseup');assert.deepEqual(up.target,click.target);assert(up.x>0);
    original.events[0].target.id='poison';assert.notEqual(p.read().events[0].target.id,'poison');
    p.nodes.get('text').readOnly=true;p.touch('text','press');p.execute(key,['ignored',0,false]);assert.equal(p.read().editor.text,'Überte 🙂');
    const foreign=page({bridge:false});foreign.touch('bridge','press');foreign.touch('bridge','release');
    assert.equal(foreign.outbound.length,0);assert.equal(foreign.read().echoes.length,0);
    assert.equal(foreign.read().events.filter(row => row.kind === 'click' && row.target.id === 'bridge').length,1);
    assert.equal(typeof foreign.observer.retire,'undefined');assert(Object.isFrozen(foreign.observer));
    const overflow=page();for (let i=0;i<1025;++i) overflow.nodes.get('bridge').click();
    assert.throws(() => overflow.read(),/UNAVAILABLE/);
    process.stdout.write('World Web original DOM/input/reference checks passed\n');
})().catch(error => { process.stderr.write(error.stack+'\n');process.exitCode=1; });
