"""Real generated app JS and bounded native-input file ownership on host only."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
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
        files=originals(RUN,ROOT,TICKET,NONCE);self.assertEqual(set(NAMES),set(files))
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
        replacements=dict(FILES=files,ROOT=ROOT,TICKET=TICKET,INLINE=inline_data_url(RUN,TICKET,ROOT))
        program=re.sub(r'__(FILES|ROOT|TICKET|INLINE)__',lambda match:json.dumps(replacements[match[1]]),program)
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)
        code=files['script.js']
        for forbidden in ('Entities.','MyAvatar.','Test.','Script.setInterval','Script.setTimeout','gotoHomeScreen','XMLHttpRequest','evaluateJavaScript'):
            self.assertNotIn(forbidden,code)

    def test_actual_storage_subrun_is_distinct_from_feature_run_and_originals_survive_rebuild(self):
        files=self.files();owner=files.reserve_app(RUN,ROOT,TICKET)
        self.assertNotEqual(RUN,owner['runId']);self.assertEqual(RUN,owner['featureRun'])
        self.assertEqual(owner,self.files().owned());directory=files.stage_reserved()
        self.assertEqual('file:///private/feature-script-'+owner['runId'],directory)
        self.assertEqual(directory,self.files().verify());self.assertEqual(owner,self.files().owned())
        self.assertEqual({'performed':True},files.release());self.assertIsNone(self.store.read())

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


if __name__=='__main__':unittest.main()
