// Copyright 2026 Overte contributors.
// SPDX-License-Identifier: Apache-2.0
// Execute the real ordinary app handler against actual loopback fixture inputs.
// Tablet/UI signals and the Script XMLHttpRequest boundary are synthetic.
'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const [source,url]=process.argv.slice(2);
class Signal {
    constructor(){this.handlers=[];}
    connect(handler){this.handlers.push(handler);}
    disconnect(handler){this.handlers=this.handlers.filter(item=>item!==handler);}
    emit(...args){for(const handler of [...this.handlers])handler(...args);}
}
const requests=[],calls=[],replies=[],buttons=[],removed=[];
class XMLHttpRequest {
    constructor(){this.DONE=4;this.readyState=0;}
    open(method,url){assert.equal(method,'GET');this.url=url;this.readyState=1;}
    send(){requests.push(this.url);fetch(this.url).then(async response=>{
        this.status=response.status;this.responseText=await response.text();this.readyState=this.DONE;this.onreadystatechange();
    }).catch(error=>{this.status=0;this.readyState=this.DONE;this.onreadystatechange();});}
}
const tablet={webEventReceived:new Signal(),addButton(options){const button={text:options.text,clicked:new Signal()};buttons.push(button);return button;},
    gotoWebScreen(...args){calls.push(args);},emitScriptEvent(message){replies.push(JSON.parse(message));},
    gotoHomeScreen(){calls.push(['HOME']);},removeButton(button){removed.push(button.text);}};
const ending=new Signal();
vm.runInNewContext(fs.readFileSync(source,'utf8'),{XMLHttpRequest,Tablet:{getTablet(name){assert.equal(name,'com.highfidelity.interface.tablet.system');return tablet;}},
    Script:{resolvePath(path){return new URL(path,url).href;},scriptEnding:ending}}, {filename:source});
(async()=>{
    buttons.find(button=>button.text==='WEB TEST').clicked.emit();
    assert.deepEqual(calls[0],[new URL('index.html',url).href,new URL('injected.js',url).href]);
    buttons.find(button=>button.text==='INLINE TEST').clicked.emit();
    const deadline=Date.now()+4000;
    while(calls.length<2 && Date.now()<deadline)await new Promise(resolve=>setTimeout(resolve,10));
    assert.equal(calls.length,2);assert.equal(requests.length,2);
    assert.equal(requests[0],new URL('../../current',url).href);
    assert.match(requests[1],/\/tickets\/[0-9a-f]{32}\/inline-input\.json$/);
    assert.match(calls[1][0],/^data:text\/html;charset=utf-8;base64,/);
    const html=Buffer.from(calls[1][0].split(',')[1],'base64').toString('utf8');
    assert.match(html,/<title>Overte owned inline parity<\/title>/);
    assert.match(html,/<meta name="overte-fixture-inline-input" content="[0-9a-f]{32}">/);
    assert.equal(calls[1][1],new URL('injected.js',url).href);
    tablet.webEventReceived.emit(JSON.stringify({contract:'overte-web-parity-v1',action:'echo',sequence:7}));
    assert.deepEqual(replies,[{contract:'overte-web-parity-v1',action:'echo',sequence:7,surface:'tablet'}]);
    ending.emit();assert.deepEqual(removed.sort(),['INLINE TEST','WEB TEST']);
    tablet.webEventReceived.emit(JSON.stringify({contract:'overte-web-parity-v1',action:'echo',sequence:8}));assert.equal(replies.length,1);
    console.log('PASS: original ordinary Tablet app consumes real loopback phase/inline input and retires its signals');
})().catch(error=>{console.error(error);process.exitCode=1;});
