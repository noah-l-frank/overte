"""Original reference and passive E2E source in Node, synthetic DOM/OS boundaries.

Trusted positives are explicitly injected VM events, not actual browser/device
input. Counterexamples exercise ownership, read-only sampling and source history.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
from pathlib import Path
import subprocess
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from feature_journeys.fixtures import pinned_resource

ROOT=Path(__file__).resolve().parents[1]
SETUP=r'''
const assert=require('node:assert/strict'),vm=require('node:vm');
const install=require(SOURCE_PATH);
let clock=20000,click=null,disconnectFailure=false,randomByte=1,timers=new Map(),nextTimer=1,requests=[];
const nodes=new Map();
function node(id){if(!nodes.has(id))nodes.set(id,{tagName:id==='text'?'INPUT':'BUTTON',type:'text',value:'',textContent:'',
    disabled:false,isConnected:true,style:{},addEventListener(){},play(){return Promise.resolve();}});return nodes.get(id);}
let owner={content:'a'.repeat(32)},response={content:'b'.repeat(32)};
const listeners=[];
const signal={connect(fn){listeners.push(fn);},disconnect(fn){if(disconnectFailure)throw Error('injected failure');let i=listeners.indexOf(fn);if(i>=0)listeners.splice(i,1);}};
const doc={getElementById:node,activeElement:null,readyState:'complete',
    querySelectorAll(selector){return selector.includes('owner')?(owner?[owner]:[]):response?[response]:[];},
    addEventListener(name,fn,capture){assert.equal(name,'click');assert.equal(capture,true);click=fn;},
    removeEventListener(name,fn,capture){if(click!==null)assert.equal(fn,click);click=null;}};
const w={addEventListener(){},document:doc,Date:{now:()=>clock},location:{href:'http://127.0.0.1/feature-fixture/v1/runs/'+'a'.repeat(32)+'/tickets/'+'c'.repeat(32)+'/reference.html',pathname:'/reference.html',search:''},
    crypto:{getRandomValues(bytes){bytes.fill(randomByte++);return bytes;}},Promise,
    setInterval(fn,ms){const id=nextTimer++;timers.set(id,fn);return id;},clearInterval(id){timers.delete(id);},
    setTimeout(){},EventBridge:{scriptEventReceived:signal,emitWebEvent(raw){requests.push(raw);}}};
w.top=w;
BEFORE_REFERENCE
vm.runInNewContext(REFERENCE,{window:w,document:doc,URL:{},JSON,Math,Number,String});
// Run the unchanged original reference's regular bridge acquisition callback.
for(const fn of timers.values())fn();
const source=install(w),nonce='d'.repeat(32);
function input(trusted=true,target=node('bridge')){click({isTrusted:trusted,target,timeStamp:123});}
function send(){input();node('bridge').onclick();}
function echo(sequence=1,surface='tablet'){const raw=JSON.stringify({contract:'overte-web-parity-v1',action:'echo',sequence,surface});for(const fn of [...listeners])fn(raw);return raw;}
'''


class WebDOMTests(unittest.TestCase):
    def run_case(self,body,*,before_reference=""):
        setup=SETUP.replace('SOURCE_PATH',json.dumps(str(ROOT/'native/web_dom_observation.js')))
        setup=setup.replace('BEFORE_REFERENCE',before_reference)
        setup=setup.replace('REFERENCE',json.dumps(pinned_resource('web-source/reference.js').decode()))
        result=subprocess.run(['node','-e',setup+'\n(async()=>{'+body+'\n})().catch(e=>{process.stderr.write(String(e));process.exitCode=1;});'],
                              capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)

    def test_read_only_actual_text_focus_response_and_new_source_sequence(self):
        self.run_case('''node('text').value='Grüße 🌍';doc.activeElement=node('text');
const a=source.read(nonce),b=source.read('ios-'+nonce);
assert.equal(a.editor.text,'Grüße 🌍');assert.equal(a.editor.focused,true);assert.equal(a.document.responseId,'b'.repeat(32));
assert.equal(a.document.href,w.location.href);assert.equal(a.attempts.length,0);assert.equal(requests.length,0);
assert.equal(b.sequence,a.sequence+1);assert.equal(a.instance,b.instance);assert.equal(b.requestId,'ios-'+nonce);
a.editor.text='forged';a.attempts.push({});assert.equal(source.read(nonce).attempts.length,0);
assert.equal(node('text').value,'Grüße 🌍');''')

    def test_trusted_actual_button_event_is_independent_of_missing_or_accepted_echo(self):
        self.run_case('''input(false);input(true,node('text'));assert.equal(source.read(nonce).attempts.length,0);
send();let a=source.read(nonce);assert.equal(a.attempts.length,1);assert.equal(a.echoes.length,0);assert.equal(requests.length,1);
echo();await Promise.resolve();a=source.read(nonce);assert.equal(a.echoes.length,1);assert.equal(a.echoes[0].sequence,1);
assert.equal(a.echoes[0].surface,'tablet');assert.equal(a.attempts[0].eventTimeMs,123);
echo();await Promise.resolve();assert.equal(source.read(nonce).echoes.length,1);''')

    def test_outgoing_only_dom_copy_unmatched_or_missing_original_receive_cannot_make_echo(self):
        self.run_case('''send();node('bridgeStatus').textContent='Real script echo received from tablet · sequence 1';
assert.equal(source.read(nonce).echoes.length,0);
node('bridgeStatus').textContent='Waiting for actual Overte script echo 1';
echo(2);await Promise.resolve();assert.equal(source.read(nonce).echoes.length,0);
// Remove the original reference receive callback; the passive source alone
// cannot change DOM state or manufacture original reference consumption.
const own=listeners[0];signal.disconnect(own);echo(1);await Promise.resolve();assert.equal(source.read(nonce).echoes.length,0);
assert.equal(node('bridgeStatus').textContent,'Waiting for actual Overte script echo 1');''')

    def test_foreign_bridge_absence_still_records_an_actual_trusted_attempt(self):
        self.run_case('''send();const a=source.read(nonce);
assert.equal(a.attempts.length,1);assert.equal(a.echoes.length,0);assert.equal(requests.length,0);
assert.equal(node('bridgeStatus').textContent,'Native EventBridge unavailable');
assert.equal(a.document.responseId,'b'.repeat(32));''',before_reference='delete w.EventBridge;')

    def test_missing_owner_foreign_nonce_oversized_or_regressing_clock_is_unavailable(self):
        self.run_case('''source.read(nonce);clock=19999;assert.throws(()=>source.read(nonce),/UNAVAILABLE/);
source.retire();assert.throws(()=>source.read(nonce),/UNAVAILABLE/);''')
        for edit in ("owner=null;", "owner.content='private';", "response.content='bad';",
                     "node('text').value='x'.repeat(513);", "node('text').tagName='TEXTAREA';"):
            with self.subTest(edit=edit):self.run_case(edit+"assert.throws(()=>source.read(nonce),/UNAVAILABLE/);")
        self.run_case("assert.throws(()=>source.read(nonce+String.fromCharCode(10)),/UNAVAILABLE/);")

    def test_history_overflow_never_drops_original_attempts_into_a_green_partial_result(self):
        self.run_case('''for(let i=0;i<65;i++)input();assert.throws(()=>source.read(nonce),/UNAVAILABLE/);''')

    def test_new_document_has_new_instance_without_invented_native_load_count(self):
        self.run_case('''const a=source.read(nonce);source.retire();const second=install(w),b=second.read(nonce);
assert.notEqual(a.instance,b.instance);assert.equal(b.attempts.length,0);assert.equal(b.echoes.length,0);
assert.equal('documentLoads' in b,false);assert.equal('httpStatus' in b,false);second.retire();''')

    def test_failed_disconnect_retains_cleanup_failure_and_can_retry_without_source_reuse(self):
        self.run_case('''disconnectFailure=true;assert.throws(()=>source.retire(),/UNAVAILABLE/);
assert.throws(()=>source.retire(),/UNAVAILABLE/);assert.throws(()=>source.read(nonce),/UNAVAILABLE/);
disconnectFailure=false;source.retire();source.retire();assert.equal(timers.size,1);
assert.equal(click,null);assert.equal(listeners.length,1);''')

    def test_source_rejects_subframes_and_missing_actual_crypto(self):
        self.run_case('''source.retire();w.top={};assert.throws(()=>install(w),/UNAVAILABLE/);
w.top=w;delete w.crypto;assert.throws(()=>install(w),/UNAVAILABLE/);''')


if __name__=='__main__':unittest.main()
