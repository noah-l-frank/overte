// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Passive original DOM source for the actual UIKit WK Tablet presentation.
// No DOM mutation, synthetic input, key text/codes or password values.
function overteIOSTabletWebDOM(global) {
    'use strict';
    const doc = global.document;
    if (!doc || global !== global.top || !global.crypto || typeof global.crypto.getRandomValues !== 'function')
        throw Error('OVT_IOS_TABLET_WEB_DOM_UNAVAILABLE');
    const random = new Uint8Array(16);global.crypto.getRandomValues(random);
    const instance = Array.from(random, byte => byte.toString(16).padStart(2,'0')).join('');
    const events = [], echoes = [], pending = [], bridges = [], births = new WeakMap(), composing = new Map();
    let failed = false, epoch = 0, sequence = 0, nextBirth = 0;
    function need(value) { if (!value) { failed = true;throw Error('OVT_IOS_TABLET_WEB_DOM_UNAVAILABLE'); } }
    function now() { const value=global.Date.now();need(!failed && Number.isSafeInteger(value) && value>0 && value>=epoch);epoch=value;return value; }
    function birth(node) {
        need(node && typeof node === 'object');
        if (!births.has(node)) { need(nextBirth<2048);births.set(node,++nextBirth); }
        return births.get(node);
    }
    function append(list,value,limit) { need(list.length<limit);list.push(value); }
    function selected() {
        const nodes={};
        for (const id of ['text','bridge','back','reload','foreign','navigate','feature-marker','recovery','reference']) {
            const found=doc.querySelectorAll('#'+id);need(found.length<=1);
            if (found.length) nodes[id]=found[0];
            else need(id==='recovery' || id==='reference');
        }
        const links=Array.from(doc.querySelectorAll('a[href]')).filter(node => {
            try { const url=new global.URL(node.href);return url.pathname.endsWith('/page-b.html')
                || (url.pathname.endsWith('/index.html') && url.search==='?page=second'); } catch (_) { return false; }
        });
        need(links.length===1);nodes['same-origin']=links[0];return nodes;
    }
    function label(target) {
        if (!target || target.nodeType!==1) return {id:null,birth:null};
        const nodes=selected();for (const id of Object.keys(nodes)) if (target===nodes[id]) return {id,birth:birth(target)};
        return {id:null,birth:birth(target)};
    }
    function observed(event) {
        if (failed || !event) return;
        try {
            need(typeof event.type==='string' && Number.isFinite(event.timeStamp) && event.timeStamp>=0 && typeof event.isTrusted==='boolean');
            const target=label(event.target),point=['pointerdown','pointerup','pointercancel','click'].includes(event.type);
            if (point) need(Number.isFinite(event.clientX) && Number.isFinite(event.clientY));
            const pointer=event.type.startsWith('pointer');
            if (pointer) need(Number.isSafeInteger(event.pointerId) && event.pointerId>=0 && ['touch','mouse','pen',''].includes(event.pointerType));
            const active=event.type==='compositionstart' || event.type==='compositionupdate';
            if (event.type.startsWith('composition') && target.birth!==null) composing.set(target.birth,active);
            // Deliberately never read event.data, event.key, inputType or text
            // from arbitrary targets (including the disposable password test).
            append(events,{ordinal:events.length+1,kind:event.type,capturedEpochMs:now(),eventTimeMs:event.timeStamp,
                trusted:event.isTrusted,target,x:point?event.clientX:null,y:point?event.clientY:null,
                pointerId:pointer?event.pointerId:null,pointerType:pointer?event.pointerType:null,
                composing:event.type.startsWith('composition')?active:null},1024);
        } catch (_) { failed=true; }
    }
    for (const kind of ['pointerdown','pointerup','pointercancel','click','input','focusin','focusout','compositionstart','compositionupdate','compositionend'])
        doc.addEventListener(kind,observed,true);
    function settle() {
        if (failed) return;
        try {
            const status=doc.getElementById('bridgeStatus');need(status && typeof status.textContent==='string');
            for (const packet of pending) {
                if (status.textContent!=='Real script echo received from '+packet.surface+' · sequence '+packet.sequence) continue;
                if (!echoes.some(old=>old.sequence===packet.sequence)) append(echoes,{...packet,observedEpochMs:now()},64);
            }
            pending.length=0;
        } catch (_) { failed=true; }
    }
    function received(message) {
        if (failed || typeof message!=='string' || message.length>4096) return;
        let value;try { value=JSON.parse(message); } catch (_) { return; }
        if (!value || value.contract!=='overte-web-parity-v1' || value.action!=='echo' || value.surface!=='tablet'
            || !Number.isSafeInteger(value.sequence) || value.sequence<1 || value.sequence>1000000) return;
        try { append(pending,{sequence:value.sequence,surface:value.surface,message,receivedEpochMs:now()},64);global.Promise.resolve().then(settle); }
        catch (_) { failed=true; }
    }
    function acquire() {
        const bridge=global.EventBridge;
        if (!bridge || bridges.includes(bridge) || typeof bridge.emitWebEvent!=='function' || !bridge.scriptEventReceived
            || typeof bridge.scriptEventReceived.connect!=='function') return;
        need(bridges.length<4);bridge.scriptEventReceived.connect(received);bridges.push(bridge);
    }
    global.setInterval(()=>{ if (!failed) { try { acquire(); } catch (_) { failed=true; } } },50);acquire();
    return Object.freeze({read(requestId) {
        need(typeof requestId==='string' && /^ios-[0-9a-f]{32}$/.test(requestId));
        const owners=doc.querySelectorAll('meta[name="overte-fixture-owner"]'),responses=doc.querySelectorAll('meta[name="overte-fixture-response"]');
        need(owners.length===1 && /^[0-9a-f]{32}$/.test(owners[0].content) && responses.length<=1
            && (!responses.length || /^[0-9a-f]{32}$/.test(responses[0].content)) && doc.readyState==='complete');
        const nodes=selected(),elements=[],viewport=global.visualViewport;
        need(nodes.text.tagName==='INPUT' && nodes.text.type==='text' && typeof nodes.text.value==='string' && nodes.text.value.length<=512
            && nodes.foreign.tagName==='INPUT' && nodes.foreign.type==='url' && typeof nodes.foreign.value==='string' && nodes.foreign.value.length<=8192
            && viewport && [global.innerWidth,global.innerHeight,viewport.width,viewport.height,viewport.scale].every(v=>Number.isFinite(v) && v>0)
            && [viewport.offsetLeft,viewport.offsetTop,viewport.pageLeft,viewport.pageTop,global.scrollX,global.scrollY].every(Number.isFinite));
        const left=viewport.offsetLeft,top=viewport.offsetTop,right=left+viewport.width,bottom=top+viewport.height;
        for (const id of Object.keys(nodes)) {
            const node=nodes[id],rect=node.getBoundingClientRect(),style=global.getComputedStyle(node);
            need([rect.left,rect.top,rect.right,rect.bottom].every(Number.isFinite));
            // Only the two controlled, type-checked ordinary fixture fields.
            const value=id==='text'?nodes.text.value:id==='foreign'?nodes.foreign.value:null;
            elements.push({id,birth:birth(node),tag:node.tagName,type:typeof node.type==='string'?node.type:'',value,focused:doc.activeElement===node,
                rect:[rect.left,rect.top,rect.right,rect.bottom],enabled:!node.disabled,
                visible:node.isConnected && style.visibility!=='hidden' && style.display!=='none' && rect.right>rect.left && rect.bottom>rect.top
                    && rect.left>=left && rect.top>=top && rect.right<=right && rect.bottom<=bottom,
                href:typeof node.href==='string'?node.href:null,accessibilityLabel:node.getAttribute('aria-label')});
        }
        acquire();settle();need(!failed && sequence<Number.MAX_SAFE_INTEGER);
        return {iosTabletWebDOMVersion:1,requestId,instance,sequence:++sequence,capturedEpochMs:now(),
            document:{runId:owners[0].content,href:String(global.location.href),responseId:responses.length?responses[0].content:null,
                readyState:doc.readyState,title:String(doc.title),width:global.innerWidth,height:global.innerHeight,scroll:[global.scrollX,global.scrollY],
                visualViewport:{width:viewport.width,height:viewport.height,offsetLeft:viewport.offsetLeft,offsetTop:viewport.offsetTop,
                    pageLeft:viewport.pageLeft,pageTop:viewport.pageTop,scale:viewport.scale}},
            editor:{text:nodes.text.value,focused:doc.activeElement===nodes.text},elements,
            compositions:Array.from(composing,([target,active])=>({target,active})),
            events:events.map(row=>({...row,target:{...row.target}})),echoes:echoes.map(row=>({...row}))};
    }});
}
if (typeof module!=='undefined' && module.exports) module.exports=overteIOSTabletWebDOM;
