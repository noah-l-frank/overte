"""Original VM identities are distinct from QML, input and peer effects."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import subprocess
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters import chat_script_sources as source
from ios.self_tests.chat_script_source_fixture import packet,advance,ROOT,URL


class ChatScriptSourcesTests(unittest.TestCase):
    def query(self,value):return dict(schemaVersion=1,commandId=value['requestId'],action=source.ACTION,runId=value['runId'])
    def test_reviewed_pins_match_actual_utf16_inputs_and_admitted_rows_copy_outward(self):
        pins=source.pins();self.assertEqual(set(source.FILES),set(pins))
        for name,pin in pins.items():
            raw=(ROOT/'scripts'/name).read_bytes().decode('utf-8').encode('utf-16le')
            self.assertEqual(dict(codeUnits=len(raw)//2,sha256=hashlib.sha256(raw).hexdigest()),pin)
        value=packet();row=source.admit(value,URL);row['codeSources']['evaluations'][0]['sha256']='f'*64
        self.assertNotEqual(row,source.admit(value,URL));self.assertEqual(URL+source.FILES[0],row['membership']['url'])
    def test_actual_separate_chat_manager_and_loaded_code_identity_are_required(self):
        for fault in ('manager','main','chat','missing','incomplete','roster','root','duplicate'):
            value=packet();row=value['source']['workers'][0];expected_root=URL
            if fault=='manager':row['membership']['url']=URL+'defaultScripts.js'
            elif fault=='main':row['code']['sha256']='0'*64
            elif fault=='chat':row['codeSources']['evaluations'][0]['sha256']='0'*64
            elif fault=='missing':row['codeSources']['evaluations'].pop()
            elif fault=='incomplete':row['codeSources']['complete']=False
            elif fault=='roster':value['source']['complete']=False
            elif fault=='root':expected_root='qrc:/foreign/scripts/'
            else:
                other=deepcopy(row);other['membership']['instance']='c'*32
                value['source']['workers'].append(other);value['source']['revision']=2
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.admit(value,expected_root)
    def test_foreign_or_ambiguous_urls_and_untyped_scalars_are_refused(self):
        for fault in ('authority','query','fragment','empty-query','empty-fragment','foreign','boolean','encoding'):
            value=packet();row=value['source']['workers'][0]['codeSources']['evaluations'][0]
            if fault=='authority':row['url']='file://foreign/scripts/'+source.FILES[0]
            elif fault=='query':row['url']+='?wanted=true'
            elif fault=='fragment':row['url']+='#wanted'
            elif fault=='empty-query':row['url']+='?'
            elif fault=='empty-fragment':row['url']+='#'
            elif fault=='foreign':row['url']=URL+'system/snapshot.js'
            elif fault=='boolean':row['codeUnits']=True
            else:row['encoding']='utf-8'
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.original(value)
    def test_current_source_requires_an_actual_running_worker(self):
        for field in ('running','stopping','finished','done'):
            value=packet();value['source']['workers'][0][field]=field!='running'
            with self.subTest(field=field),self.assertRaises(NativeUIError):source.admit(value,URL)
    def test_code_and_evaluation_timestamps_must_belong_to_actual_manager_assignment(self):
        for fault in ('code','evaluation'):
            value=packet();row=value['source']['workers'][0];assigned=row['membership']['assignedEpochMs']
            if fault=='code':row['code']['submittedEpochMs']=assigned-1
            else:row['codeSources']['evaluations'][0]['submittedEpochMs']=assigned-1
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.original(value)
    def test_extra_actual_relevant_submission_cannot_be_hidden_by_correct_main_code(self):
        value=packet();row=value['source']['workers'][0];extra=deepcopy(row['codeSources']['evaluations'][0])
        extra.update(sequence=2,url='qrc:/foreign/scripts/'+source.FILES[0]);row['codeSources']['evaluations'].append(extra)
        source.original(value)
        with self.assertRaises(NativeUIError):source.admit(value,URL)
    def test_pending_first_submission_can_complete_once_without_reusing_an_old_stamp(self):
        complete=packet();before=deepcopy(complete);row=before['source']['workers'][0]
        row['code']=dict(submitted=False,encoding='utf-16le-code-units',codeUnits=0,sha256='',submittedEpochMs=0)
        row['codeSources']['evaluations']=[];source.original(before)
        after=advance(before);newer=after['source']['workers'][0];observed=deepcopy(complete['source']['workers'][0])
        newer['code']=observed['code'];newer['code']['submittedEpochMs']=before['clockAfter']['epochMs']+1
        newer['codeSources']=observed['codeSources'];newer['codeSources']['evaluations'][0]['submittedEpochMs']=before['clockAfter']['epochMs']+2
        source.validate(after,self.query(after),42,previous=before);source.admit(after,URL)
        stale=deepcopy(after);stale['source']['workers'][0]['code']['submittedEpochMs']=complete['source']['workers'][0]['code']['submittedEpochMs']
        with self.assertRaises(NativeUIError):source.validate(stale,self.query(stale),42,previous=before)
    def test_next_packet_preserves_original_submissions_membership_and_lifetimes(self):
        before=packet();after=advance(before);source.validate(after,self.query(after),42,previous=before)
        for fault in ('code','membership','nonce','pid','missing','revision'):
            changed=deepcopy(after)
            if fault=='code':changed['source']['workers'][0]['codeSources']['evaluations'][0]['sha256']='0'*64
            elif fault=='membership':changed['source']['workers'][0]['membership']['loadGeneration']+=1
            elif fault=='nonce':changed['requestId']=before['requestId']
            elif fault=='pid':changed['processId']=43
            elif fault=='missing':changed['source']['workers']=[]
            else:changed['source']['revision']=0
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.validate(changed,self.query(changed),42,previous=before)
    def test_original_clock_and_declared_source_bounds_are_not_relaxed(self):
        for fault in ('expiry','future-code','count','duplicate','complete-recovery'):
            before=packet();value=advance(before)
            if fault=='expiry':value['clockAfter']['epochMs']+=1500;value['clockAfter']['monotonicMs']+=1500
            elif fault=='future-code':value['source']['workers'][0]['codeSources']['evaluations'][0]['submittedEpochMs']=value['clockAfter']['epochMs']+1
            elif fault=='count':value['source']['workers'][0]['codeSources']['evaluations']*=33
            elif fault=='duplicate':value['source']['workers']*=2;value['source']['revision']=2
            else:before['source']['workers'][0]['codeSources']['complete']=False
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.validate(value,self.query(value),42,previous=before)
    def test_fixed_native_writer_keeps_compact_private_atomic_file_boundary(self):
        text=(ROOT/'interface/src/scripting/TestScriptingInterface.cpp').read_text();save=text[text.index('void TestScriptingInterface::saveObject'):]
        compact=save[save.index('// Preserve these passive sources'):save.index('// Append trailing slash')]
        private=save[save.index('QString filepath = QDir::cleanPath'):save.index('QSaveFile output(filepath)')]
        self.assertIn('filename=="'+source.FILE+'"',compact);self.assertIn('filename == "'+source.FILE+'"',private)
        self.assertIn('QJsonDocument::Compact',compact);self.assertIn('QFileInfo(filepath).isSymLink()',private)
        self.assertIn('output.setDirectWriteFallback(false)',save);self.assertIn('QFile::ReadOwner | QFile::WriteOwner',save)


class ChatDefaultLoaderTests(unittest.TestCase):
    def test_actual_default_loader_always_loads_chat_separately_without_changing_settings(self):
        program='''const fs=require('fs'),vm=require('vm');const source=fs.readFileSync(SOURCE,'utf8');
for(const separate of [false,true]){const included=[],loaded=[];let writes=0;
 const context=vm.createContext({Window:{interstitialModeEnabled:false},
 Settings:{getValue:(key,fallback)=>key==='_debugDefaultScriptsIsChecked'?separate:fallback,setValue:()=>{writes++;throw Error('setting changed');}},
 Menu:{menuExists:()=>false,menuItemExists:()=>false,isOptionChecked:()=>separate,menuItemEvent:{connect:()=>{}},triggerOption:()=>{throw Error('debug changed');}},
 ScriptDiscoveryService:{getRunning:()=>[]},Script:{include:path=>included.push(path),load:path=>loaded.push(path),scriptEnding:{connect:()=>{}}},console:{log:()=>{}}});
 vm.runInContext(source,context,{timeout:1000});const count=rows=>rows.filter(path=>path==='communityScripts/armored-chat/armored_chat.js').length;
 if(writes||count(included)!==0||count(loaded)!==1)throw Error('actual Chat include/load path differs');}
'''.replace('SOURCE',json.dumps(str(ROOT/'scripts/defaultScripts.js')))
        result=subprocess.run(['node','-'],input=program,capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)


if __name__=='__main__':unittest.main()
