// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Actual generated app callbacks on host V8; Qt/Tablet/Script SDKs are models.
'use strict';
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),readline=require('node:readline');
const filename=path.resolve(process.argv[2]),url=require('node:url').pathToFileURL(filename).href;
const buttons=[],connections=new Set(),endings=[],navigations=[],emissions=[],requires=[];
let stopped=false;
let page=null,pageClock=100000;const pageEvents=[],pageRequests=[];
function signal() {
    const callbacks=new Set();
    return {connect(f){callbacks.add(f)},disconnect(f){callbacks.delete(f)},emit(...args){for(const callback of Array.from(callbacks))callback(...args)},size(){return callbacks.size}};
}
const incoming=signal();
const tablet={
    addButton(properties){const button={properties:{...properties},clicked:signal(),removed:false};buttons.push(button);return button},
    removeButton(button){if(!buttons.includes(button))throw Error('Unknown actual returned proxy');button.removed=true},
    gotoWebScreen(source){navigations.push({source,stack:new Error().stack})},
    emitScriptEvent(message){
        const record={message,stack:new Error().stack,contextObserved:++pageClock,objectObserved:++pageClock,entered:++pageClock};emissions.push(record);
        if(page){
            record.slotTraceEntered=++pageClock;record.slotEntered=++pageClock;
            record.pageTraceEntered=++pageClock;record.pageEntered=++pageClock;
            // WK evaluation/DOM delivery is asynchronous even if this host
            // model's Qt signal route uses the direct AutoConnection case.
            Promise.resolve().then(()=>{for(const callback of page.callbacks)callback(message)});
            record.pageTraceReturn=++pageClock;record.pageReturned=++pageClock;record.pageFinally=++pageClock;
            record.slotTraceReturn=++pageClock;record.slotReturned=++pageClock;record.slotFinally=++pageClock;
        }
        record.returned=++pageClock;record.finally=++pageClock;
    },
    webEventReceived:{connect(f){incoming.connect(f);connections.add(f)},disconnect(f){incoming.disconnect(f);connections.delete(f)}}
};
const Script={require(relative){
    const actual=path.resolve(path.dirname(filename),relative),module={exports:{}};
    const source=fs.readFileSync(actual,'utf8');vm.runInNewContext(source,{module},{filename:require('node:url').pathToFileURL(actual).href});
    requires.push({url:require('node:url').pathToFileURL(actual).href,bytes:Buffer.byteLength(source)});return module.exports;
},scriptEnding:{connect(callback){endings.push(callback)}}};
vm.runInNewContext(fs.readFileSync(filename,'utf8'),{Script,Tablet:{getTablet(id){
    if(id!=='com.highfidelity.interface.tablet.system')throw Error('Unexpected Tablet');return tablet;
}}},{filename:url});
function snapshot(){return {url,buttons:buttons.map(button=>({properties:button.properties,removed:button.removed,connections:button.clicked.size()})),
    connections:connections.size,navigations:navigations.map(row=>({...row})),emissions:emissions.map(row=>({...row})),requires:requires.map(row=>({...row})),
    focusedElement:page&&page.doc.activeElement?page.doc.activeElement.id:null,nativeEpoch:pageClock,pageEvents:pageEvents.map(row=>({...row})),
    pageRequests:pageRequests.map(row=>({...row})),render:page?{title:page.doc.title,href:page.global.location.href,
        markerSource:page.nodes.get('feature-marker').src||null,markerRect:page.nodes.get('feature-marker').getBoundingClientRect(),
        text:page.nodes.get('text').value,bridgeStatus:page.nodes.get('bridgeStatus').textContent}:null,stopped}}
async function command(value){
    if(value.operation==='click') {
        const actual=buttons.filter(button=>button.properties.semanticId===value.semanticId&&!button.removed);
        if(actual.length!==1)throw Error('Actual app proxy unavailable');actual[0].clicked.emit();
    } else if(value.operation==='web')incoming.emit(value.message);
    else if(value.operation==='page-create'){
        pageClock=value.epoch;page=require('./test_ios_tablet_web_dom.js').page({inline:value.inline,bridge:value.bridge,inlineToken:value.inlineToken,random:bytes=>require('node:crypto').randomFillSync(bytes)});
        const actual=new URL(value.url);page.global.location.href=actual.href;page.global.location.pathname=actual.pathname;
        page.global.location.search=actual.search;page.global.location.origin=actual.origin;page.global.Date.now=()=>++pageClock;
        let currentHref=actual.href;
        Object.defineProperty(page.global.location,'href',{get(){return currentHref},set(source){
            pageRequests.push({kind:'navigate',source:new URL(source,currentHref).href,epoch:++pageClock});
        }});
        page.global.location.reload=()=>pageRequests.push({kind:'reload',source:currentHref,epoch:++pageClock});
        page.global.history.back=()=>pageRequests.push({kind:'back',source:currentHref,epoch:++pageClock});
        const title=value.html.match(/<title>([^<]*)<\/title>/);if(title)page.doc.title=title[1];
        // Explicit layout model of the pinned compact owned-browser CSS.
        // This is a host DOM operand, never a native geometry observation.
        if(!value.html.includes('owned-browser-controls-v1'))throw Error('Unknown controlled host layout');
        page.global.scrollY=0;page.global.visualViewport={width:500,height:756,offsetLeft:0,offsetTop:0,pageLeft:0,pageTop:0,scale:1};
        const layout={'feature-marker':[330,8,490,48],text:[12,100,488,140],bridge:[12,156,240,196],'same-origin':[252,156,488,196],
            recovery:[12,210,240,250],reference:[252,210,488,250],back:[12,264,240,304],reload:[252,264,488,304],foreign:[12,320,488,360],navigate:[12,378,240,418]};
        for(const [id,rect] of Object.entries(layout)){const node=page.nodes.get(id);if(node)node.rect={left:rect[0],top:rect[1],right:rect[2],bottom:rect[3]};}
        const original=page.doc.querySelectorAll;
        page.doc.querySelectorAll=function(selector){
            if(selector==='meta[name="overte-fixture-response"]'){
                const match=value.html.match(/<meta name="overte-fixture-response" content="([0-9a-f]{32})">/);
                return match?[{content:match[1]}]:[];
            }
            if(selector==='meta[name="overte-fixture-owner"]'){
                const match=value.html.match(/<meta name="overte-fixture-owner" content="([0-9a-f]{32})">/);
                return match?[{content:match[1]}]:[];
            }
            return original.call(this,selector);
        };
        for(const tag of value.html.match(/<a\b[^>]*>/g)||[]){
            const href=tag.match(/\bhref="([^"]+)"/),id=tag.match(/\bid="([^"]+)"/);
            if(!href)continue;
            const target=id?id[1]:new URL(href[1],actual).pathname.endsWith('/page-b.html')?'same-origin':null;
            if(target&&page.nodes.has(target))page.nodes.get(target).href=new URL(href[1],actual).href;
        }
        for(const tag of value.html.match(/<img\b[^>]*>/g)||[]){
            const id=tag.match(/\bid="([^"]+)"/),src=tag.match(/\bsrc="([^"]+)"/);
            if(id&&src&&page.nodes.has(id[1]))page.nodes.get(id[1]).src=new URL(src[1],actual).href;
        }
        if(value.bridge)page.global.EventBridge.emitWebEvent=message=>{
            pageEvents.push({kind:'native-envelope',message,epoch:++pageClock});
            if(value.authorized!==false){
                pageEvents.push({kind:'script-delivery',message,epoch:++pageClock});incoming.emit(message);
                pageEvents.push({kind:'script-delivery-return',message,epoch:++pageClock});
            }
            pageEvents.push({kind:'native-envelope-return',message,epoch:++pageClock});
        };
    } else if(value.operation==='page-read'){
        if(!page)throw Error('No current actual host document');pageClock=Math.max(pageClock,value.epoch);
        const dom=page.read(value.requestId);return {...snapshot(),dom,pageEvents:pageEvents.map(row=>({...row}))};
    } else if(value.operation==='page-click'){
        if(!page)throw Error('No current actual host document');pageClock=Math.max(pageClock,value.epoch);page.click(value.id,true);
        await Promise.resolve();await Promise.resolve();await Promise.resolve();
    } else if(value.operation==='page-tap'){
        if(!page)throw Error('No current actual host document');pageClock=Math.max(pageClock,value.epoch);
        const ids=['text','bridge','back','reload','foreign','navigate','same-origin','recovery','reference'];
        const matches=ids.filter(id=>{const node=page.nodes.get(id);if(!node)return false;const rect=node.getBoundingClientRect();return rect.left<=value.x&&value.x<rect.right&&rect.top<=value.y&&value.y<rect.bottom});
        if(matches.length!==1)throw Error('Actual host hit target unavailable or ambiguous');const id=matches[0],node=page.nodes.get(id);
        for(const kind of ['pointerdown','pointerup','click'])page.event(id,kind,true,{clientX:value.x,clientY:value.y});
        if(node.tagName==='INPUT'){node.focus();page.event(id,'focusin');}
        if(node.onclick)node.onclick();
        if(node.tagName==='A'&&node.href)pageRequests.push({kind:'navigate',source:node.href,epoch:++pageClock});
        await Promise.resolve();await Promise.resolve();await Promise.resolve();
    } else if(value.operation==='page-text'){
        if(!page)throw Error('No current actual host document');pageClock=Math.max(pageClock,value.epoch);
        const node=page.nodes.get(value.id);if(!node)throw Error('Actual DOM field unavailable');node.focus();page.event(value.id,'focusin');
        node.value=value.text;page.event(value.id,'input');
    }
    else if(value.operation==='stop'){if(stopped)throw Error('Script Ending cannot be replayed');for(const callback of endings)callback();stopped=true;}
    else if(value.operation!=='read')throw Error('Unsupported host operation');
    return snapshot();
}
const lines=readline.createInterface({input:process.stdin,crlfDelay:Infinity});let work=Promise.resolve();
lines.on('line',line=>{work=work.then(async()=>{try{process.stdout.write(JSON.stringify({okay:true,value:await command(JSON.parse(line))})+'\n')}catch(error){process.stdout.write(JSON.stringify({okay:false,error:String(error)})+'\n')}})});
