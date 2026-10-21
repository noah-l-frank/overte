"""Runtime source-profile selection; never animation or installed-code proof."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import subprocess
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from adapters.emote_source_profile import pins,select,select_from_roots
from adapters.normal_ui import NativeUIError
from test_native_script_observation import Boundary

ROOT='qrc:/scripts/'


def actual(profile, *, root=ROOT):
    boundary=Boundary()
    boundary.engine['url']=root+profile['sourcePath'][len('scripts/'):]
    def observed(value):
        value['source']['sourceIdentityVersion']=1
        value['source']['engines'][0]['code']=dict(submitted=True,encoding=profile['encoding'],
            codeUnits=profile['codeUnits'],sha256=profile['sha256'],submittedEpochMs=15000)
    boundary.mutate=observed
    return boundary,boundary.reader()


class EmoteSourceProfileTests(unittest.TestCase):
    def test_all_reviewed_source_variants_resolve_from_actual_submitted_code(self):
        for profile in pins():
            with self.subTest(profile=profile['id']):
                source,reader=actual(profile);value=reader.read(0,require_code_identity=True)
                result=select(value,ROOT)
                self.assertEqual(profile['id'],result['profile']['id'])
                self.assertEqual(source.engine['required']['instance'],result['engineInstance'])
                self.assertEqual(15000,result['code']['submittedEpochMs'])
                self.assertEqual(1,len(source.commands))
                self.assertEqual({'schemaVersion','commandId','action'},set(source.commands[0]))

    def test_label_url_or_platform_alone_cannot_adopt_unknown_changed_code(self):
        source,reader=actual(pins()[0]);value=reader.read(0,require_code_identity=True)
        for change in ({'sha256':'f'*64},{'codeUnits':1}):
            packet=deepcopy(value);packet['source']['engines'][0]['code'].update(change)
            with self.assertRaises(NativeUIError):select(packet,ROOT)
        with self.assertRaises(NativeUIError):select(value,ROOT+'foreign/')

    def test_ambiguous_running_sources_are_rejected_and_stopped_sources_do_not_own_input(self):
        _source,reader=actual(pins()[0]);value=reader.read(0,require_code_identity=True)
        profile=pins()[2];foreign=deepcopy(value['source']['engines'][0])
        foreign['url']=ROOT+profile['sourcePath'][len('scripts/'):]
        foreign['required']['instance']='c'*32
        foreign['code'].update({k:profile[k] for k in ('encoding','sha256','codeUnits')})
        value['source']['engines'].append(foreign)
        with self.assertRaises(NativeUIError):select(value,ROOT)
        foreign['stopping']=True
        self.assertEqual(pins()[0]['id'],select(value,ROOT)['profile']['id'])
        value['source']['engines'][0]['running']=False
        with self.assertRaises(NativeUIError):select(value,ROOT)

    def test_installed_resource_root_is_explicit_and_cannot_be_remote_or_traversed(self):
        _source,reader=actual(pins()[0]);value=reader.read(0,require_code_identity=True)
        for root in ('https://foreign/scripts/','qrc:/scripts/../scripts/','file://foreign/scripts/',
                     'file:///private/%2e%2e/scripts/','qrc:/scripts/?expected=known'):
            with self.subTest(root=root),self.assertRaises(NativeUIError):select(value,root)
        profile=pins()[1];root='file:///actual/verified/resource/scripts/'
        _source,reader=actual(profile,root=root)
        self.assertEqual(profile['id'],select(reader.read(0,require_code_identity=True),root)['profile']['id'])

    def test_reviewed_local_source_files_match_an_explicit_pin_without_regenerating_it(self):
        root=Path(__file__).resolve().parents[3]
        reviewed=pins()
        for source_path in {row['sourcePath'] for row in reviewed}:
            source=(root/source_path).read_bytes().decode('utf-8').encode('utf-16-le',errors='surrogatepass')
            matches=[row for row in reviewed if row['sourcePath']==source_path
                and row['codeUnits']==len(source)//2 and row['sha256']==hashlib.sha256(source).hexdigest()]
            self.assertEqual(1,len(matches),source_path)

    def test_reviewed_tablet_source_records_an_unresolved_sit_end_frame_at_script_boundary(self):
        # Executes the original shipped JS against explicit native boundaries.
        # The undefined end frame is a source concern, never a passing Sit test
        # or a substitute parameter for the eventual native adapter.
        root=Path(__file__).resolve().parents[3]
        source=(root/'scripts/system/emote.js').read_text()
        program=r'''
const handlers={},calls=[];
function signal(name){return {connect:f=>handlers[name]=f,disconnect:()=>{}};}
const step={peek:()=>step,to:()=>step};
const Controller={Standard:{},newMapping:()=>({from:()=>step}),keyPressEvent:signal("key"),enableMapping:()=>{},disableMapping:()=>{}};
const tablet={addButton:()=>({clicked:signal("button"),editProperties:()=>{}}),screenChanged:signal("screen"),
 webEventReceived:signal("web"),gotoHomeScreen:()=>{},gotoWebScreen:()=>{},removeButton:()=>{}};
const Tablet={getTablet:()=>tablet};
const AnimationCache={prefetch:()=>({state:3}),getAnimation:()=>({frames:Array(120)})};
const Script={resolvePath:p=>"qrc:/scripts/system/"+p,setTimeout:()=>1,clearTimeout:()=>{},scriptEnding:signal("end")};
const MyAvatar={overrideAnimation:(...args)=>calls.push(args),restoreAnimation:()=>{}};
SOURCE
handlers.web({type:"click",data:"Crying"});handlers.web({type:"click",data:"Sit"});
process.stdout.write(JSON.stringify(calls.map(args=>({url:args[0],endFrameType:typeof args[4],loop:args[2]}))));
'''.replace('SOURCE',source)
        result=subprocess.run(['node','-e',program],capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr);calls=json.loads(result.stdout)
        self.assertEqual('number',calls[0]['endFrameType']);self.assertEqual('undefined',calls[1]['endFrameType'])
        self.assertFalse(calls[0]['loop']);self.assertFalse(calls[1]['loop'])

    def rooted(self,*,alias=True):
        from test_native_script_roots import RootBoundary
        root=RootBoundary();root.instance='b'*32;reader=root.reader();before=reader.read(0)
        source,scripts=actual(pins()[0],root=root.root+'/');physical=source.engine['url']
        if alias:source.engine['url']='file:///~//system/+android_phoneInterface/phoneEmote.js'
        observe=source.mutate
        def original(value):
            observe(value)
            value['source'].update(membershipSourceVersion=1,membership=dict(complete=True,revision=1,managers=[
                dict(instance=source.engine['required']['instance'],assigned=True,url=physical,loadGeneration=1,assignedEpochMs=14000)]))
        source.mutate=original;packet=scripts.read(0,require_code_identity=True,require_membership=True)
        after=reader.read(before['sequence']);return packet,before,after

    def test_original_application_roots_and_submitted_code_jointly_select_the_actual_profile(self):
        packet,before,after=self.rooted();originals=deepcopy((packet,before,after))
        selected=select_from_roots(packet,before,after,pid=31,epoch=20000)
        self.assertEqual(pins()[0]['id'],selected['profile']['id'])
        self.assertEqual('file:///~//system/+android_phoneInterface/phoneEmote.js',selected['url'])
        self.assertEqual(before['source']['defaultScriptsUrl']+'/system/+android_phoneInterface/phoneEmote.js',selected['assignedUrl'])
        self.assertEqual(originals,(packet,before,after));self.assertNotIn('animation',selected)

    def test_root_join_refuses_a_foreign_or_changed_source_even_with_a_recognized_filename(self):
        packet,before,after=self.rooted()
        for fault in ('root','birth','pid','order','age','cursor','nonce','code','url'):
            script,left,right=deepcopy((packet,before,after))
            if fault=='root':right['source']['defaultScriptsUrl']='file:///another/scripts'
            elif fault=='birth':script['instance']='e'*32
            elif fault=='pid':right['processId']=32
            elif fault=='order':left['capturedEpochMs']=20001
            elif fault=='age':left['requestedEpochMs']=18000
            elif fault=='cursor':right['sequence']=left['sequence']
            elif fault=='nonce':right['commandId']=left['commandId']
            elif fault=='code':script['source']['engines'][0]['code']['sha256']='f'*64
            else:script['source']['engines'][0]['url']='file:///foreign/system/+android_phoneInterface/phoneEmote.js'
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):select_from_roots(script,left,right,pid=31,epoch=20000)

    def test_root_join_never_accepts_a_missing_source_or_missing_original_request_nonce(self):
        packet,before,after=self.rooted()
        for index in range(3):
            originals=[packet,before,after];originals[index]=None
            with self.subTest(index=index),self.assertRaises(NativeUIError):select_from_roots(*originals,pid=31,epoch=20000)
        packet['requestId']=None
        with self.assertRaises(NativeUIError):select_from_roots(packet,before,after,pid=31,epoch=20000)
        packet,before,after=self.rooted();before['commandId']=None
        with self.assertRaises(NativeUIError):select_from_roots(packet,before,after,pid=31,epoch=20000)

    def test_normalized_engine_key_requires_its_own_original_assignment_and_submitted_code(self):
        packet,before,after=self.rooted()
        for fault in ('missing','incomplete','foreign-manager','foreign-file','late-assignment','unassigned','unknown-alias'):
            value=deepcopy(packet)
            if fault=='missing':value['source'].pop('membership');value['source'].pop('membershipSourceVersion')
            elif fault=='incomplete':value['source']['membership']={'complete':False}
            elif fault=='unknown-alias':value['source']['engines'][0]['url']='file:///~/system/+android_phoneInterface/phoneEmote.js'
            else:
                row=value['source']['membership']['managers'][0]
                if fault=='foreign-manager':row['instance']='f'*32
                elif fault=='foreign-file':row['url']='file:///foreign/system/+android_phoneInterface/phoneEmote.js'
                elif fault=='late-assignment':row['assignedEpochMs']=16000
                else:row.update(assigned=False,url='',loadGeneration=0,assignedEpochMs=0)
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):select_from_roots(value,before,after,pid=31,epoch=20000)

    def test_physical_original_keys_are_supported_only_with_actual_assignment_in_the_root_join(self):
        packet,before,after=self.rooted(alias=False)
        selected=select_from_roots(packet,before,after,pid=31,epoch=20000)
        self.assertEqual(selected['url'],selected['assignedUrl']);self.assertEqual(14000,selected['assignedEpochMs'])
        self.assertEqual(1,selected['loadGeneration'])
        with self.assertRaises(NativeUIError):
            alias_packet,left,right=self.rooted();select(alias_packet,left['source']['defaultScriptsUrl']+'/')

    def test_source_selection_keeps_original_identity_private_and_does_not_mutate_observations(self):
        _source,reader=actual(pins()[1]);value=reader.read(0,require_code_identity=True);before=deepcopy(value)
        result=select(value,ROOT);result['code']['sha256']='f'*64;result['profile']['chooserAfterPlay']='hidden'
        self.assertEqual(before,value)
        self.assertEqual('retained',select(value,ROOT)['profile']['chooserAfterPlay'])


if __name__=='__main__':unittest.main()
