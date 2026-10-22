// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// E2E-only passive source. Native backends must supply their own document,
// frame/origin/admission/PID envelopes; DOM fields do not prove native loading.
function overteWebDOMSource(global) {
    'use strict';
    const doc = global.document;
    if (!doc || global !== global.top || !global.crypto || typeof global.crypto.getRandomValues !== 'function')
        throw Error('OVT_WEB_DOM_SOURCE_UNAVAILABLE');
    const random = new Uint8Array(16);global.crypto.getRandomValues(random);
    const instance = Array.from(random, b => b.toString(16).padStart(2, '0')).join('');
    let alive = true, retired = false, failed = false, epoch = 0, sequence = 0, bridge = null;
    const attempts = [], echoes = [], pending = [], connected = [];
    const CAP = 64;
    function need(okay) { if (!okay) { failed = true;throw Error('OVT_WEB_DOM_SOURCE_UNAVAILABLE'); } }
    function now() {
        const value = global.Date.now();
        need(Number.isSafeInteger(value) && value > 0 && value >= epoch);epoch = value;return value;
    }
    function node(id) { return doc.getElementById(id); }
    function original() {
        need(alive && !failed);
        const editor = node('text'), button = node('bridge'), status = node('bridgeStatus');
        need(editor && button && status && editor.tagName === 'INPUT' && editor.type === 'text'
             && button.tagName === 'BUTTON' && typeof editor.value === 'string'
             && editor.value.length <= 512 && typeof status.textContent === 'string' && status.textContent.length <= 512);
        const owners = doc.querySelectorAll('meta[name="overte-fixture-owner"]');
        const responses = doc.querySelectorAll('meta[name="overte-fixture-response"]');
        need(owners.length === 1 && /^[0-9a-f]{32}$/.test(owners[0].content)
             && responses.length <= 1 && (!responses.length || /^[0-9a-f]{32}$/.test(responses[0].content)));
        const href = String(global.location.href);
        need(href.length > 0 && href.length <= 131072);
        return {editor, button, status, runId:owners[0].content,
            responseId:responses.length ? responses[0].content : null, href};
    }
    function append(list, value) { need(list.length < CAP);list.push(value); }
    function clicked(event) {
        if (!alive || failed || !event || event.isTrusted !== true) return;
        try {
            const actual = original();
            if (event.target !== actual.button || actual.button.disabled || actual.button.isConnected === false) return;
            need(Number.isFinite(event.timeStamp) && event.timeStamp >= 0);
            append(attempts, {ordinal:attempts.length + 1, capturedEpochMs:now(), eventTimeMs:event.timeStamp});
        } catch (_) { failed = true; }
    }
    function settle() {
        if (!alive || failed) return;
        try {
            const actual = original();
            // Read the original reference handler's actual displayed result.
            // Merely receiving an outgoing/native ACK cannot fill this history.
            for (let i = 0; i < pending.length; ++i) {
                const packet = pending[i];
                const text = 'Real script echo received from ' + packet.surface + ' · sequence ' + packet.sequence;
                if (actual.status.textContent !== text) continue;
                if (!echoes.some(old => old.sequence === packet.sequence)) {
                    append(echoes, {...packet, observedEpochMs:now()});
                }
            }
            pending.length = 0;
        } catch (_) { failed = true; }
    }
    function received(message) {
        if (!alive || failed || typeof message !== 'string' || message.length > 4096) return;
        let packet;try { packet = JSON.parse(message); } catch (_) { return; }
        if (!packet || packet.contract !== 'overte-web-parity-v1' || packet.action !== 'echo'
            || !Number.isSafeInteger(packet.sequence) || packet.sequence < 1 || packet.sequence > 1000000
            || !['world','tablet'].includes(packet.surface)) return;
        try {
            append(pending, {sequence:packet.sequence,surface:packet.surface,message,
                receivedEpochMs:now()});
            global.Promise.resolve().then(settle);
        } catch (_) { failed = true; }
    }
    function acquire() {
        const current = global.EventBridge;
        if (!current || current === bridge || typeof current.emitWebEvent !== 'function'
            || !current.scriptEventReceived || typeof current.scriptEventReceived.connect !== 'function'
            || typeof current.scriptEventReceived.disconnect !== 'function') return;
        need(connected.length < 4);current.scriptEventReceived.connect(received);
        connected.push(current);bridge = current;
    }
    doc.addEventListener('click', clicked, true);
    // Acquisition retries only attach a passive listener. They never request a
    // bridge grant, invoke a page handler, send a packet or edit an element.
    const timer = global.setInterval(() => { if (alive && !failed) { try { acquire(); } catch (_) { failed = true; } } }, 50);
    acquire();
    function read(requestId) {
            need(typeof requestId === 'string' && [32,36].includes(requestId.length)
                 && /^(?:ios-)?[0-9a-f]{32}$/.test(requestId));
            const actual = original();acquire();settle();need(!failed && sequence < Number.MAX_SAFE_INTEGER);
            const captured = now();
            return {webDOMVersion:1,requestId,instance,sequence:++sequence,capturedEpochMs:captured,
                document:{runId:actual.runId,href:actual.href,responseId:actual.responseId,readyState:doc.readyState},
                editor:{text:actual.editor.value,focused:doc.activeElement === actual.editor},
                attempts:attempts.map(v => ({...v})),echoes:echoes.map(v => ({...v}))};
    }
    return Object.freeze({
        read,
        // Separate owned-browser profile. The original HTTP-only read packet
        // remains v1; title is an original document property, not a verdict.
        readOwned(requestId) {
            const result = read(requestId);
            need(typeof doc.title === 'string' && doc.title.length > 0 && doc.title.length <= 512);
            result.document.title = doc.title;return result;
        },
        // This reads only a fixed fixture control. Geometry is consumed inside
        // the native input producer, never accepted as caller coordinates.
        readGeometry(requestId, control) {
            need(['text','bridge','reference','second','recovery','back','reload','foreign','navigate',
                  'play','pause','seekStart','seek','scroll-up','scroll-down'].includes(control));
            const actual = read(requestId), scrolling = control === 'scroll-up' || control === 'scroll-down',
                item = scrolling ? doc.documentElement : node(control);
            need(item && typeof item.getBoundingClientRect === 'function');
            const rect = scrolling ? {left:0,top:0,width:global.innerWidth,height:global.innerHeight} : item.getBoundingClientRect(),
                x = rect.left + rect.width / 2,
                y = rect.top + rect.height / 2, hit = doc.elementFromPoint(x, y), viewport = global.visualViewport;
            need([rect.left,rect.top,rect.width,rect.height,x,y,global.innerWidth,global.innerHeight].every(Number.isFinite)
                 && rect.width > 0 && rect.height > 0 && global.innerWidth > 0 && global.innerHeight > 0);
            const editable = control === 'text' || control === 'foreign';
            need(scrolling || (editable ? item.tagName === 'INPUT' && ['text','url'].includes(item.type)
                          : ['BUTTON','A','INPUT'].includes(item.tagName)));
            return {webGeometryVersion:1,requestId,instance:actual.instance,sequence:actual.sequence,capturedEpochMs:actual.capturedEpochMs,
                document:actual.document,control,
                editor:{focused:doc.activeElement === item,text:editable ? item.value : null,
                    cursor:editable ? (item.selectionDirection === 'backward' ? item.selectionStart : item.selectionEnd) : null,
                    anchor:editable ? (item.selectionDirection === 'backward' ? item.selectionEnd : item.selectionStart) : null},
                viewport:{width:global.innerWidth,height:global.innerHeight,
                    scale:viewport ? viewport.scale : 1,offsetLeft:viewport ? viewport.offsetLeft : 0,
                    offsetTop:viewport ? viewport.offsetTop : 0},
                rect:{x:rect.left,y:rect.top,width:rect.width,height:rect.height},center:{x,y},
                hit:hit === item || !!(hit && item.contains(hit)),
                enabled:!item.disabled && !item.readOnly,connected:item.isConnected === true};
        },
        retire() {
            if (retired) return;alive = false;
            let okay = true;
            try { global.clearInterval(timer); } catch (_) { okay = false; }
            try { doc.removeEventListener('click', clicked, true); } catch (_) { okay = false; }
            const unresolved = [];
            for (const value of connected) {
                try { value.scriptEventReceived.disconnect(received); }
                catch (_) { okay = false;unresolved.push(value); }
            }
            connected.length = 0;connected.push(...unresolved);
            if (!okay) { failed = true;throw Error('OVT_WEB_DOM_SOURCE_UNAVAILABLE'); }
            pending.length = attempts.length = echoes.length = 0;bridge = null;retired = true;
        }
    });
}
if (typeof module !== 'undefined' && module.exports) module.exports = overteWebDOMSource;
