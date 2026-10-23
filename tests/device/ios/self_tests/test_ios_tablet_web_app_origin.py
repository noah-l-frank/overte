"""Generated original JS, real host V8 call sites and explicit native VM DTOs."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import json
import re
import subprocess
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters import tablet_web_app_origin as origin
from ios.adapters.tablet_web_app_files import originals
from ios.adapters.web_script_emissions import selected
from ios.self_tests.test_ios_emote_sources import BINDING
from ios.self_tests.test_ios_tablet_web_buttons import Boundary
from ios.self_tests.test_ios_tablet_web_sources import RUN,ROOT
from ios.self_tests.test_ios_web_script_emissions import Emitter

EPOCH=1700000000000
TICKET='7'*32
NONCE='b'*32


def originals_boundary():
    raw=originals(RUN,ROOT,TICKET,NONCE);storage='8'*32;directory='file:///private/feature-script-'+storage;url=directory+'/script.js'
    owner=dict(contractVersion=1,tabletWebAppFilesVersion=2,runId=storage,featureRun=RUN,ownerToken='9'*64,binding=BINDING,
        fixtureUrl=ROOT,ticket=TICKET,nonce=NONCE,hashes={key:hashlib.sha256(data).hexdigest() for key,data in raw.items()})
    files=dict(schemaVersion=1,requestId='ios-'+'1'*32,instance='2'*32,sequence=1,requestedEpochMs=EPOCH+1,capturedEpochMs=EPOCH+2,
        processId=31,runId=storage,operation='observe',source=dict(exists=True,directory=directory,files=[dict(name=key,exists=True,bytes=len(data),
            sha256=hashlib.sha256(data).hexdigest(),base64=base64.b64encode(data).decode()) for key,data in raw.items()]))
    encoded=raw['script.js'].decode().encode('utf-16le');code=dict(submitted=True,encoding='utf-16le-code-units',codeUnits=len(encoded)//2,
        sha256=hashlib.sha256(encoded).hexdigest(),submittedEpochMs=EPOCH+4)
    manager=dict(instance='3'*32,assigned=True,url=url,loadGeneration=1,assignedEpochMs=EPOCH+3)
    engine=dict(url=url,running=True,stopping=False,finished=False,code=code,required=dict(instance=manager['instance'],sequence=3,
        modules=[dict(url=directory+'/'+name,loaded=True,cached=False,sequence=index,capturedEpochMs=EPOCH+4+index) for index,name in enumerate(origin.MODULES,1)]))
    scripts=dict(schemaVersion=1,requestId='ios-'+'4'*32,instance='5'*32,sequence=1,requestedEpochMs=EPOCH+90,capturedEpochMs=EPOCH+100,
        processId=31,source=dict(complete=True,sourceIdentityVersion=1,membershipSourceVersion=1,membership=dict(complete=True,revision=1,managers=[manager]),engines=[engine]))
    native=Boundary();native.manager=deepcopy(manager);native.code=deepcopy(code);controls={}
    for verb in ('open','inline','return'):controls[verb]=native.bind(native.add(verb))
    return owner,files,scripts,native.snapshot(),controls,raw


def admit(values):return origin.admitted(*values[:5],BINDING,after_epoch=EPOCH)


class TabletWebAppOriginTests(unittest.TestCase):
    def test_actual_four_readback_files_and_running_vm_join_original_returned_controls(self):
        values=originals_boundary();before=deepcopy(values);result=admit(values)
        self.assertEqual(values,before);self.assertEqual(3,len(result['controls']))
        self.assertEqual(values[2]['source']['engines'][0]['code'],result['profile']['code'])
        self.assertEqual([18,14,18],[row['line'] for row in result['locations']])
        self.assertNotIn('httpStatus',result);self.assertNotIn('open',result)

    def test_same_label_same_url_and_same_vm_do_not_replace_original_bytes_generation_or_control(self):
        for fault in ('readback','hash-only','code','units','generation','caller','nonce','module','extra-unloaded','stopped','pid','old-assignment','early-readback','extra-button','legacy','boolean'):
            values=list(originals_boundary());owner,files,scripts,buttons,controls,_raw=values;engine=scripts['source']['engines'][0]
            if fault=='readback':files['source']['files'][0]['base64']=base64.b64encode(b'wrong actual source').decode()
            elif fault=='hash-only':owner['hashes']['script.js']='0'*64
            elif fault=='code':engine['code']['sha256']='0'*64
            elif fault=='units':engine['code']['codeUnits']+=1
            elif fault=='generation':scripts['source']['membership']['managers'][0]['loadGeneration']+=1
            elif fault=='caller':buttons['buttons'][0]['caller']['manager']['instance']='0'*32
            elif fault=='nonce':controls['open']['nonce']='0'*32
            elif fault=='module':engine['required']['modules'][0]['url']='file:///foreign/companion.js'
            elif fault=='extra-unloaded':
                engine['required']['sequence']=4;engine['required']['modules'].append(dict(url='file:///foreign/missing.js',loaded=False,cached=False,sequence=4,capturedEpochMs=EPOCH+10))
            elif fault=='stopped':engine['stopping']=True
            elif fault=='pid':files['processId']=32
            elif fault=='old-assignment':scripts['source']['membership']['managers'][0]['assignedEpochMs']=EPOCH
            elif fault=='early-readback':files['requestedEpochMs']=EPOCH-1
            elif fault=='extra-button':
                item=deepcopy(buttons['buttons'][0]);item['id']='6'*32;item['uuid']='00000000-0000-4000-8000-000000000001';buttons['buttons'].append(item)
            elif fault=='legacy':owner['tabletWebAppFilesVersion']=1
            else:files['processId']=True
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):admit(values)

    def test_independent_pins_match_real_generated_host_v8_frames_without_expected_frames_in_emitter(self):
        values=originals_boundary();result=admit(values);url=result['profile']['assignedUrl'];files={key:data.decode() for key,data in values[-1].items()}
        program=r'''
const vm=require('vm'), files=__FILES__, url=__URL__;let callback, observed;
const tablet={addButton:()=>({clicked:{connect(){}}}),webEventReceived:{connect(f){callback=f}},emitScriptEvent(){observed=new Error().stack}};
const Script={require:p=>{const module={exports:{}};vm.runInNewContext(files[p.replace(/^\.\//,'')],{module});return module.exports},scriptEnding:{connect(){}}};
vm.runInNewContext(files['script.js'],{Script,Tablet:{getTablet:()=>tablet}},{filename:url});
callback(JSON.stringify({contract:'overte-web-parity-v1',action:'echo',sequence:1}));
console.log(JSON.stringify(observed.split('\n').filter(line=>line.includes(url)).map(line=>{const m=line.match(/:(\d+):(\d+)\)?$/);return {line:Number(m[1]),column:Number(m[2])}})));
'''
        program=re.sub(r'__(FILES|URL)__',lambda m:json.dumps({'FILES':files,'URL':url}[m[1]]),program)
        observed=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,observed.returncode,observed.stderr)
        self.assertEqual([{key:row[key] for key in ('line','column')} for row in result['locations']],json.loads(observed.stdout))

    def test_actual_emitter_requires_whole_pinned_closure_stack_in_addition_to_admitted_root_code(self):
        values=originals_boundary();result=admit(values);emitter=Emitter();emitter.buttons.manager=deepcopy(result['manager']);emitter.buttons.code=deepcopy(result['profile']['code'])
        emitter.frames=[dict(scriptId=71,line=pin['line'],column=pin['column'],sourceUrlSha256=pin['sourceUrlSha256'],
            compiled=dict(urlSha256=pin['sourceUrlSha256'],encoding='utf-16le-code-units',codeUnits=pin['codeUnits'],sha256=pin['sha256'],firstObservedEpochMs=EPOCH+4),isEval=False,isConstructor=False) for pin in result['locations']]
        call,queue,life=emitter.good();packet=emitter.snapshot();sink=packet['sinks'][-1]
        self.assertEqual(call,selected(packet,sink,result['profile'],result['locations']))
        for fault in ('nested','line','same-url-different-bytes','same-bytes-different-url'):
            changed=deepcopy(packet);stack=changed['calls'][0]['caller']['emitStack']['frames']
            if fault=='nested':stack.append(deepcopy(stack[-1]))
            elif fault=='line':stack[0]['line']+=1
            elif fault=='same-url-different-bytes':stack[0]['compiled']['sha256']='0'*64
            else:
                stack[0]['sourceUrlSha256']='0'*64;stack[0]['compiled']['urlSha256']='0'*64
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):selected(changed,changed['sinks'][-1],result['profile'],result['locations'])


if __name__=='__main__':unittest.main()
