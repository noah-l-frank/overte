"""Real generated app JS and bounded native-input file ownership on host only."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import hashlib
import re
from pathlib import Path
import subprocess
import tempfile
import unittest
from adapters.native_script_files import NAMES
from adapters.normal_feature_state import PrivateFeatureState
from adapters.normal_ui import NativeUIError
from feature_journeys.browser_fixture import inline_data_url
from ios.adapters.tablet_web_app_files import originals,OwnedTabletWebAppFiles,LABELS
from ios.self_tests.test_ios_emote_marker_files import NativeBoundary
from ios.self_tests.test_ios_emote_sources import BINDING,RUN

ROOT='http://127.0.0.1:38123/feature-fixture/v1/runs/'+RUN+'/'
TICKET='b'*32
NONCE='c'*32


class TabletWebAppFilesTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.root.chmod(0o700)
        self.native=NativeBoundary();self.store=PrivateFeatureState(self.root/'ios-tablet-web-app-files.json')
    def tearDown(self):self.temp.cleanup()
    def files(self):return OwnedTabletWebAppFiles(self.native,self.store,BINDING)

    def test_four_existing_bounded_files_reconstruct_actual_canonical_inline_input(self):
        files=originals(RUN,ROOT,TICKET,NONCE,version=2);self.assertEqual(set(NAMES),set(files))
        self.assertTrue(all(0<len(raw)<=8192 for raw in files.values()))
        self.assertGreater(len(inline_data_url(RUN,TICKET,ROOT)),8192)
        chunk=lambda key:json.loads(files[key].decode().removeprefix('module.exports=').removesuffix(';\n'))
        self.assertEqual(inline_data_url(RUN,TICKET,ROOT),chunk('companion.js')+chunk('script-bundle/main.js'))
        self.assertEqual('tablet-web-app-v1',chunk('script-bundle/companion.js')['kind'])

    def test_actual_generated_js_uses_normal_buttons_and_original_echo_without_world_mutation(self):
        files={key:value.decode() for key,value in originals(RUN,ROOT,TICKET,NONCE).items()}
        program=r'''
const vm=require('vm'),files=__FILES__,buttons=[],events=[],nav=[],removed=[],replies=[];
function signal(){return {handlers:[],connect(f){this.handlers.push(f)},disconnect(f){this.handlers=this.handlers.filter(x=>x!==f)},emit(...a){for(const f of [...this.handlers])f(...a)}}}
const web=signal(),ending=signal();
const tablet={webEventReceived:web,addButton:p=>{const b={properties:p,clicked:signal()};buttons.push(b);return b},removeButton:b=>removed.push(b),gotoWebScreen:u=>nav.push(u),emitScriptEvent:r=>replies.push(r)};
const Script={require:path=>{const module={exports:{}};vm.runInNewContext(files[path.replace(/^\.\//,'')],{module});return module.exports},scriptEnding:ending};
vm.runInNewContext(files['script.js'],{Script,Tablet:{getTablet:id=>{if(id!=='com.highfidelity.interface.tablet.system')throw Error('foreign tablet');return tablet}}});
if(buttons.some(b=>b.properties.fixtureUrl!==__ROOT__))throw Error('missing actual ordinary button fixture property');
if(buttons.length!==3||nav.length)throw Error('unexpected execution shortcut');
const button=label=>buttons.find(b=>b.properties.text===label);
button('WEB TEST').clicked.emit();button('WEB INLINE').clicked.emit();button('WEB RETURN').clicked.emit();
if(nav[0]!==__ROOT__+'tickets/'+__TICKET__+'/index.html'||nav[1]!==__INLINE__||nav[2]!==__ROOT__+'tickets/'+__TICKET__+'/reference.html')throw Error('ordinary input URL mismatch');
web.emit(JSON.stringify({contract:'overte-web-parity-v1',action:'echo',sequence:17}));
if(replies.length!==1||JSON.parse(replies[0]).surface!=='tablet'||JSON.parse(replies[0]).sequence!==17)throw Error('original echo protocol changed');
web.emit(JSON.stringify({contract:'overte-web-parity-v1',action:'echo',sequence:true}));if(replies.length!==1)throw Error('invalid echo accepted');
ending.emit();if(removed.length!==3||web.handlers.length||buttons.some(b=>b.clicked.handlers.length))throw Error('owned callbacks/buttons retained');
web.emit(JSON.stringify({contract:'overte-web-parity-v1',action:'echo',sequence:18}));if(replies.length!==1||nav.length!==3)throw Error('ending navigated/retained callback');
'''
        inline=''.join(json.loads(files[key].removeprefix('module.exports=').removesuffix(';\n')) for key in ('companion.js','script-bundle/main.js'))
        replacements=dict(FILES=files,ROOT=ROOT,TICKET=TICKET,INLINE=inline)
        program=re.sub(r'__(FILES|ROOT|TICKET|INLINE)__',lambda match:json.dumps(replacements[match[1]]),program)
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)
        code=files['script.js']
        for forbidden in ('Entities.','MyAvatar.','Test.','Script.setInterval','Script.setTimeout','gotoHomeScreen','XMLHttpRequest','evaluateJavaScript'):
            self.assertNotIn(forbidden,code)

    def test_actual_storage_subrun_is_distinct_from_feature_run_and_originals_survive_rebuild(self):
        files=self.files();owner=files.reserve_app(RUN,ROOT,TICKET)
        self.assertEqual(3,owner['tabletWebAppFilesVersion'])
        self.assertNotEqual(RUN,owner['runId']);self.assertEqual(RUN,owner['featureRun'])
        self.assertEqual(owner,self.files().owned());directory=files.stage_reserved()
        self.assertEqual('file:///private/feature-script-'+owner['runId'],directory)
        self.assertEqual(directory,self.files().verify());self.assertEqual(owner,self.files().owned())
        self.assertEqual({'performed':True},files.release());self.assertIsNone(self.store.read())

    def test_allowed_hostname_containing_template_words_is_preserved_in_actual_executed_js(self):
        root='http://RUN.REFERENCE.NONCE.invalid/feature-fixture/v1/runs/'+RUN+'/'
        files={key:value.decode() for key,value in originals(RUN,root,TICKET,NONCE).items()}
        program=r'''
const vm=require('vm'),files=__FILES__,root=__ROOT__,ticket=__TICKET__,buttons=[],nav=[];
const signal=()=>({connect:()=>{},disconnect:()=>{}});
const tablet={webEventReceived:signal(),addButton:p=>{const b={properties:p,clicked:signal()};b.clicked.connect=f=>b.click=f;buttons.push(b);return b;},gotoWebScreen:u=>nav.push(u)};
const Script={require:path=>{const module={exports:{}};vm.runInNewContext(files[path.replace(/^\.\//,'')],{module});return module.exports;},scriptEnding:signal()};
vm.runInNewContext(files['script.js'],{Script,Tablet:{getTablet:()=>tablet}});
buttons[0].click();buttons[1].click();buttons[2].click();
if(buttons.some(b=>b.properties.fixtureUrl!==root)||nav[0]!==root+'tickets/'+ticket+'/index.html'||nav[2]!==root+'tickets/'+ticket+'/reference.html'||nav[1]!==__INLINE__)throw Error('original URL changed by template replacement');
'''
        inline=''.join(json.loads(files[key].removeprefix('module.exports=').removesuffix(';\n')) for key in ('companion.js','script-bundle/main.js'))
        replacements=dict(FILES=files,ROOT=root,TICKET=TICKET,INLINE=inline)
        program=re.sub(r'__(FILES|ROOT|TICKET|INLINE)__',lambda match:json.dumps(replacements[match[1]]),program)
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)

    def test_lost_stage_is_not_retried_and_no_file_byte_tampering_is_adopted(self):
        files=self.files();owner=files.reserve_app(RUN,ROOT,TICKET);self.native.fail=True
        with self.assertRaises(NativeUIError):files.stage_reserved()
        self.assertEqual(owner,self.files().owned());self.assertEqual(1,len(self.native.calls))
        self.native.fail=False;self.native.files=originals(RUN,ROOT,TICKET,owner['nonce']);self.native.files['companion.js']+=b'/* changed */'
        with self.assertRaises(NativeUIError):self.files().verify()
        self.assertEqual(1,len([x for x in self.native.calls if x[0]=='stage']))

    def test_same_run_second_input_generation_owns_new_native_directory_and_no_schema_expansion(self):
        first=self.files().reserve_app(RUN,ROOT,TICKET);self.files().stage_reserved();self.files().release()
        second=self.files().reserve_app(RUN,ROOT,'d'*32)
        self.assertNotEqual(first['runId'],second['runId']);self.assertNotEqual(first['ownerToken'],second['ownerToken'])
        self.assertNotEqual(first['hashes'],second['hashes']);self.assertEqual(RUN,second['featureRun'])
        with self.assertRaises(NativeUIError):self.files().reserve(RUN)

    def test_independently_frozen_v1_hashes_owner_and_actual_file_bytes_remain_unchanged(self):
        run='a'*32;root='http://127.0.0.1:38123/feature-fixture/v1/runs/'+run+'/'
        # Calculated once from c75de13a9f, before the safe v2 generator existed.
        hashes={'companion.js':'c52100d3d7cc95a952417adc7108a59c13aa304ce265676e3e2002cc9adf43f3',
            'script-bundle/companion.js':'1c7c19fba8ed7d88e1e6ce40f9353c216a8498d251d9a5cdb6266ebdfa6b9604',
            'script-bundle/main.js':'675bd315167b1d72f5e2ab23f50ade1093693554cee7a66ca8a25f6a405a00bd',
            'script.js':'6f9a00c1c57027eb332c30cc07d0dbe52c3268307dad18a67850dd1cb019fb45'}
        legacy=originals(run,root,TICKET,NONCE,version=1)
        self.assertEqual(hashes,{name:hashlib.sha256(raw).hexdigest() for name,raw in legacy.items()})
        owner=dict(contractVersion=1,tabletWebAppFilesVersion=1,runId='d'*32,featureRun=run,ownerToken='e'*64,binding=BINDING,
            fixtureUrl=root,ticket=TICKET,nonce=NONCE,hashes=hashes)
        self.store.write(owner,None);self.assertEqual(owner,self.files().owned())
        self.files().stage_reserved();self.files().verify();self.assertEqual(legacy,self.native.files)
        self.assertNotEqual(legacy,originals(run,root,TICKET,NONCE));self.assertEqual({'performed':True},self.files().release())


if __name__=='__main__':unittest.main()
