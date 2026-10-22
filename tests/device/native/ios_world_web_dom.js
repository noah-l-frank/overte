// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// iOS world input is normally translated by IOSWebView into DOM MouseEvents.
// Preserve that actual untrusted input, without granting it trusted authority.
// A separate native dispatch transcript must qualify every such attempt.
function overteIOSWorldWebDOM(global) {
    'use strict';
    const doc = global.document;
    if (!doc || global !== global.top || !global.crypto || typeof global.crypto.getRandomValues !== 'function')
        throw Error('OVT_IOS_WORLD_WEB_DOM_UNAVAILABLE');
    const random = new Uint8Array(16);global.crypto.getRandomValues(random);
    const instance = Array.from(random, b => b.toString(16).padStart(2, '0')).join('');
    const events = [], echoes = [], pending = [], bridges = [], births = new WeakMap();
    let failed = false, epoch = 0, sequence = 0, nextBirth = 0;
    function need(okay) { if (!okay) { failed = true;throw Error('OVT_IOS_WORLD_WEB_DOM_UNAVAILABLE'); } }
    function now() {
        const value = global.Date.now();
        need(!failed && Number.isSafeInteger(value) && value > 0 && value >= epoch);epoch = value;return value;
    }
    function birth(node) {
        need(node && typeof node === 'object');
        if (!births.has(node)) { need(nextBirth < 1024);births.set(node, ++nextBirth); }
        return births.get(node);
    }
    function append(list, value, limit) { need(list.length < limit);list.push(value); }
    function selected() {
        const nodes = {};
        for (const id of ['text','bridge','back','reload','foreign','navigate','recovery','reference','feature-marker']) {
            const found = doc.querySelectorAll('#' + id);need(found.length === 1);nodes[id] = found[0];
        }
        const links = Array.from(doc.querySelectorAll('a[href]')).filter(node => {
            try { return new global.URL(node.href).pathname.endsWith('/page-b.html'); } catch (_) { return false; }
        });
        need(links.length === 1);nodes['same-origin'] = links[0];
        return nodes;
    }
    function label(target) {
        if (!target || target.nodeType !== 1) return {id:null,birth:null};
        const nodes = selected();
        for (const id of Object.keys(nodes)) if (target === nodes[id]) return {id,birth:birth(target)};
        return {id:null,birth:birth(target)};
    }
    function observed(event) {
        if (failed || !event) return;
        try {
            need(typeof event.type === 'string' && Number.isFinite(event.timeStamp) && event.timeStamp >= 0
                 && typeof event.isTrusted === 'boolean');
            const target = label(event.target);
            const point = ['mousedown','mouseup','click'].includes(event.type);
            const key = event.type === 'keydown';
            if (point) need(Number.isFinite(event.clientX) && Number.isFinite(event.clientY) && Number.isInteger(event.button));
            if (key) need(typeof event.key === 'string' && event.key.length <= 512);
            append(events, {ordinal:events.length + 1,kind:event.type,capturedEpochMs:now(),
                eventTimeMs:event.timeStamp,trusted:event.isTrusted,target,
                x:point ? event.clientX : null,y:point ? event.clientY : null,button:point ? event.button : null,
                key:key ? event.key : null}, 1024);
        } catch (_) { failed = true; }
    }
    for (const kind of ['mousedown','mouseup','click','keydown','input']) doc.addEventListener(kind, observed, true);
    function settle() {
        if (failed) return;
        try {
            const status = doc.getElementById('bridgeStatus');need(status && typeof status.textContent === 'string');
            for (const packet of pending) {
                if (status.textContent !== 'Real script echo received from ' + packet.surface + ' · sequence ' + packet.sequence) continue;
                if (!echoes.some(old => old.sequence === packet.sequence)) append(echoes, {...packet,observedEpochMs:now()}, 64);
            }
            pending.length = 0;
        } catch (_) { failed = true; }
    }
    function received(message) {
        if (failed || typeof message !== 'string' || message.length > 4096) return;
        let value;try { value = JSON.parse(message); } catch (_) { return; }
        if (!value || value.contract !== 'overte-web-parity-v1' || value.action !== 'echo' || value.surface !== 'world'
            || !Number.isSafeInteger(value.sequence) || value.sequence < 1 || value.sequence > 1000000) return;
        try {
            append(pending, {sequence:value.sequence,surface:value.surface,message,receivedEpochMs:now()}, 64);
            global.Promise.resolve().then(settle);
        } catch (_) { failed = true; }
    }
    function acquire() {
        const bridge = global.EventBridge;
        if (!bridge || bridges.includes(bridge) || typeof bridge.emitWebEvent !== 'function'
            || !bridge.scriptEventReceived || typeof bridge.scriptEventReceived.connect !== 'function') return;
        need(bridges.length < 4);bridge.scriptEventReceived.connect(received);bridges.push(bridge);
    }
    global.setInterval(() => { if (!failed) { try { acquire(); } catch (_) { failed = true; } } }, 50);
    acquire();
    return Object.freeze({read(requestId) {
        need(typeof requestId === 'string' && /^ios-[0-9a-f]{32}$/.test(requestId));
        const owners = doc.querySelectorAll('meta[name="overte-fixture-owner"]');
        const responses = doc.querySelectorAll('meta[name="overte-fixture-response"]');
        need(owners.length === 1 && responses.length === 1 && /^[0-9a-f]{32}$/.test(owners[0].content)
             && /^[0-9a-f]{32}$/.test(responses[0].content) && doc.readyState === 'complete');
        const nodes = selected(), elements = [];
        need(nodes.text.tagName === 'INPUT' && nodes.text.type === 'text' && typeof nodes.text.value === 'string'
             && nodes.text.value.length <= 512 && Number.isFinite(global.innerWidth) && global.innerWidth > 0
             && Number.isFinite(global.innerHeight) && global.innerHeight > 0);
        for (const id of Object.keys(nodes)) {
            const node = nodes[id], rect = node.getBoundingClientRect();
            need([rect.left,rect.top,rect.right,rect.bottom].every(Number.isFinite));
            const style = global.getComputedStyle(node);
            elements.push({id,birth:birth(node),tag:node.tagName,type:typeof node.type === 'string' ? node.type : '',
                focused:doc.activeElement === node,value:typeof node.value === 'string' ? node.value : null,
                rect:[rect.left,rect.top,rect.right,rect.bottom],enabled:!node.disabled,
                visible:node.isConnected && style.visibility !== 'hidden' && style.display !== 'none'
                    && rect.right > rect.left && rect.bottom > rect.top && rect.left >= 0 && rect.top >= 0
                    && rect.right <= global.innerWidth && rect.bottom <= global.innerHeight,
                href:typeof node.href === 'string' ? node.href : null});
        }
        acquire();settle();need(!failed && sequence < Number.MAX_SAFE_INTEGER);
        return {iosWorldWebDOMVersion:2,requestId,instance,sequence:++sequence,capturedEpochMs:now(),
            document:{runId:owners[0].content,href:String(global.location.href),responseId:responses[0].content,
                readyState:doc.readyState,title:String(doc.title),width:global.innerWidth,height:global.innerHeight},
            editor:{text:nodes.text.value,focused:doc.activeElement === nodes.text},elements,
            events:events.map(row => ({...row,target:{...row.target}})),echoes:echoes.map(row => ({...row}))};
    }});
}
if (typeof module !== 'undefined' && module.exports) module.exports = overteIOSWorldWebDOM;
