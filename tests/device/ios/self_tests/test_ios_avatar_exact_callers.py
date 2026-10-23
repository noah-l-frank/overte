"""Actual Node source locations plus explicit modeled native stack originals."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import unittest

from adapters.normal_ui import NativeUIError
from ios.adapters import avatar_call_stack,avatar_exact_callers as exact_calls
from ios.self_tests.avatar_callers2_fixture import EPOCH,original

ROOT=Path(__file__).resolve().parents[4]


def modeled(name):
    """Explicit boundary fixture; identities come from separate original bytes."""
    profile=exact_calls.pins()['profiles'][name];suffixes=[row['source'] for row in profile['frames']]
    known=[suffix for suffix in suffixes if suffix in avatar_call_stack.SUFFIXES]
    value,unused,code=original(known);value['frames']=[];modules=[]
    for index,pin in enumerate(profile['frames']):
        suffix=pin['source'];url='qrc:/scripts'+suffix;raw=(ROOT/'scripts'/suffix[1:]).read_text().encode('utf-16-le')
        url_sha=hashlib.sha256(url.encode()).hexdigest()
        value['frames'].append(dict(scriptId=sorted(exact_calls.SOURCES).index(suffix)+1,line=pin['line'],column=pin['column'],
            sourceUrlSha256=url_sha,compiled=dict(urlSha256=url_sha,encoding='utf-16le-code-units',codeUnits=len(raw)//2,
                sha256=hashlib.sha256(raw).hexdigest(),firstObservedEpochMs=EPOCH-50),isEval=False,isConstructor=False))
        if suffix in avatar_call_stack.SUFFIXES:modules.append(dict(frame=index,url=url))
    return value,modules,code


class AvatarExactCallersTests(unittest.TestCase):
    def test_literal_pins_independently_match_all_repository_bytes_and_utf16_callsite_tokens(self):
        value=exact_calls.pins()
        for suffix,pin in value['sources'].items():
            raw=(ROOT/'scripts'/suffix[1:]).read_text().encode('utf-16-le')
            self.assertEqual(pin,dict(codeUnits=len(raw)//2,sha256=hashlib.sha256(raw).hexdigest()))
        for name,profile in value['profiles'].items():
            for pin in profile['frames']:
                line=(ROOT/'scripts'/pin['source'][1:]).read_text().splitlines()[pin['line']-1]
                raw=line.encode('utf-16-le');tail=raw[2*(pin['column']-1):].decode('utf-16-le')
                self.assertTrue(tail.startswith(pin['token']),(name,pin,tail))

    def test_every_closed_profile_checks_every_actual_frame_and_preserves_originals(self):
        for name,profile in exact_calls.pins()['profiles'].items():
            with self.subTest(name=name):
                value,modules,code=modeled(name);before=deepcopy((value,modules,code))
                self.assertEqual(exact_calls.qualify(value,modules,EPOCH,code,kind=profile['kind']),name)
                self.assertEqual((value,modules,code),before)

    def test_right_compiled_bytes_with_wrong_line_column_or_nested_parent_are_not_exact(self):
        value,modules,code=modeled('xhr-page-request')
        for field in ('line','column'):
            changed=deepcopy(value);changed['frames'][0][field]+=1
            avatar_call_stack.evaluated(changed,modules,EPOCH,code) # weaker genuine module origin still passes
            with self.assertRaises(NativeUIError):exact_calls.qualify(changed,modules,EPOCH,code,kind='xhr-open')
        changed=deepcopy(value);changed['frames'].append(deepcopy(changed['frames'][0]))
        with self.assertRaises(NativeUIError):exact_calls.qualify(changed,modules,EPOCH,code,kind='xhr-open')

    def test_appui_unknown_module_frame_must_match_real_compiled_bytes_and_actual_same_root(self):
        value,modules,code=modeled('pal-open-refresh')
        self.assertEqual(len(modules),2);self.assertEqual(len(value['frames']),3)
        for field in ('sha256','urlSha256'):
            changed=deepcopy(value);changed['frames'][2]['compiled'][field]='b'*64
            if field=='urlSha256':changed['frames'][2]['sourceUrlSha256']='b'*64
            with self.assertRaises(NativeUIError):exact_calls.qualify(changed,modules,EPOCH,code,kind='timer')
        changed=deepcopy(value);changed['frames'][2]['isEval']=True
        with self.assertRaises(NativeUIError):exact_calls.qualify(changed,modules,EPOCH,code,kind='timer')
        with self.assertRaises(NativeUIError):exact_calls.qualify(value,modules,EPOCH,code,kind='xhr-open')

    def test_actual_full_request_and_service_modules_emit_pinned_open_and_async_read_sites_in_node(self):
        # Host V8 executes the complete unchanged source modules. Qt's native
        # callback boundary is modeled separately; this is no Qt/native run.
        program=r'''
const fs=require('node:fs'),vm=require('node:vm');
const rows=[],requests=[];let fromQml;
function capture(kind){const old=Error.prepareStackTrace;Error.prepareStackTrace=(_,frames)=>frames;
 const frames=new Error().stack;Error.prepareStackTrace=old;
 rows.push({kind,frames:frames.map(f=>({url:f.getFileName(),line:f.getLineNumber(),column:f.getColumnNumber()}))
 .filter(f=>f.url&&f.url.startsWith('qrc:/scripts/'))});}
function XHR(){requests.push(this);this.open=function(){capture('xhr-open');};this.send=function(){};
 this.setRequestHeader=function(){};this.getResponseHeader=function(){return 'application/json';};
 Object.defineProperty(this,'responseText',{get(){capture('xhr-read');return '{}';}});}
const module={exports:{}};
vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8'),{module,XMLHttpRequest:XHR},
 {filename:'qrc:/scripts/modules/request.js'});
const tablet={fromQml:{connect:fn=>{fromQml=fn;},disconnect(){}},sendToQml(){}};
vm.runInNewContext(fs.readFileSync(process.argv[2],'utf8'),{Script:{require:()=>module.exports,scriptEnding:{connect(){}}},
 Tablet:{getTablet:()=>tablet}},{filename:'qrc:/scripts/system/request-service.js'});
fromQml({id:'one',method:'http.request',params:{uri:'https://owned.invalid/api/v1/users'}});
const pending=requests[0];pending.readyState=4;pending.status=200;pending.onreadystatechange();
process.stdout.write(JSON.stringify(rows));
'''
        result=subprocess.run(['node','-e',program,str(ROOT/'scripts/modules/request.js'),str(ROOT/'scripts/system/request-service.js')],
            check=True,capture_output=True,text=True,timeout=10)
        rows=json.loads(result.stdout);self.assertEqual([row['kind'] for row in rows],['xhr-open','xhr-read'])
        for row,name in zip(rows,('xhr-page-request','xhr-response-callback')):
            expected=exact_calls.pins()['profiles'][name]['frames']
            self.assertEqual(row['frames'],[dict(url='qrc:/scripts'+pin['source'],line=pin['line'],column=pin['column']) for pin in expected])

    def test_optional_entity_component_preserves_legacy_but_strong_join_refuses_missing_or_wrong_original(self):
        from ios.adapters import avatar_entities
        from ios.self_tests.test_ios_avatar_entities import packet
        value,*_=packet();who=value['source']['events'][0]['caller'];epoch=value['source']['events'][0]['clock']['epochMs']
        avatar_entities.original(value)
        with self.assertRaises(NativeUIError):exact_calls.entity(who,epoch)
        actual,modules,code=modeled('avatar-wearable-create');who['avatarCode'].update(avatarScriptVersion=2,code=code)
        who['avatarCallers']=dict(avatarEntityCallersVersion=1,complete=True,callerStack=actual,callerModules=modules)
        avatar_entities.original(value);self.assertEqual(exact_calls.entity(who,epoch),'avatar-wearable-create')
        for fault in ('line','component-version','incomplete','method'):
            changed=deepcopy(who)
            if fault=='line':changed['avatarCallers']['callerStack']['frames'][0]['line']+=1
            elif fault=='component-version':changed['avatarCallers']['avatarEntityCallersVersion']=True
            elif fault=='incomplete':changed['avatarCallers']['complete']=False
            else:changed['method']='deleteEntity'
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):exact_calls.entity(changed,epoch)

    def test_full_unchanged_avatar_app_emits_actual_entity_and_timer_callsite_locations_in_node(self):
        program=r'''
const fs=require('node:fs'),vm=require('node:vm');let handler,screen;const rows=[];
function capture(kind){const old=Error.prepareStackTrace;Error.prepareStackTrace=(_,frames)=>frames;
 const frames=new Error().stack;Error.prepareStackTrace=old;rows.push({kind,frames:frames.map(f=>({url:f.getFileName(),line:f.getLineNumber(),column:f.getColumnNumber()}))
 .filter(f=>f.url==='qrc:/scripts/system/avatarapp.js')});}
function signal(){return {connect(fn){this.fn=fn;},disconnect(){this.fn=null;}};}
const tablet={fromQml:{connect(fn){handler=fn;},disconnect(){}},screenChanged:{connect(fn){screen=fn;}},
 sendToQml(){},addButton(){return {clicked:signal(),editProperties(){}};}};
const avatar={sessionUUID:'00000000-0000-4000-8000-000000000001',getJointNames:()=>['Hips'],getAvatarEntitiesVariant:()=>[],
 getAvatarScale:()=>1,getDominantHand:()=> 'right',getHmdAvatarAlignmentType:()=>0,getCollisionsEnabled:()=>true,
 getOtherAvatarsCollisionsEnabled:()=>true,getAnimGraphUrl:()=>'',getAnimGraphOverrideUrl:()=>''};
for(const name of ['skeletonModelURLChanged','dominantHandChanged','hmdAvatarAlignmentTypeChanged','collisionsEnabledChanged',
 'otherAvatarsCollisionsEnabledChanged','newCollisionSoundURL','animGraphUrlChanged','targetScaleChanged'])avatar[name]=signal();
const entities={addingWearable:signal(),deletingWearable:signal(),mousePressOnEntity:signal(),
 addEntity(){capture('entity-add');return '00000000-0000-4000-8000-000000000002';},deleteEntity(){capture('entity-delete');}};
const bookmarks={bookmarkLoaded:signal(),bookmarkDeleted:signal(),bookmarkAdded:signal(),getBookmarks:()=>({})};
vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8'),{
 Script:{include(){},resolvePath:x=>x,scriptEnding:signal(),setTimeout(){capture('timer');return rows.length;},clearTimeout(){}},
 Tablet:{getTablet:()=>tablet},MyAvatar:avatar,AvatarBookmarks:bookmarks,Entities:entities,Camera:{},HMD:{},Account:{},
 UserActivityLogger:{},Messages:{},print(){}},{filename:'qrc:/scripts/system/avatarapp.js'});
screen('QML','hifi/AvatarApp.qml');handler({method:'getAvatars'});
handler({method:'addWearable',url:'https://owned.invalid/wearable.gltf'});handler({method:'deleteWearable',entityID:'owned'});
entities.addingWearable.fn('owned');entities.deletingWearable.fn('owned');bookmarks.bookmarkLoaded.fn('owned');
process.stdout.write(JSON.stringify(rows));
'''
        result=subprocess.run(['node','-e',program,str(ROOT/'scripts/system/avatarapp.js')],check=True,capture_output=True,text=True,timeout=10)
        rows=json.loads(result.stdout);names=('avatar-wearable-create','avatar-wearable-added','avatar-wearable-delete','avatar-wearable-deleted',
            'avatar-native-wearable-added','avatar-native-wearable-deleted','avatar-bookmark-loaded')
        self.assertEqual(len(rows),len(names))
        for row,name in zip(rows,names):
            profile=exact_calls.pins()['profiles'][name];self.assertEqual(row['kind'],profile['kind'])
            self.assertEqual(row['frames'],[dict(url='qrc:/scripts'+pin['source'],line=pin['line'],column=pin['column']) for pin in profile['frames']])

    def test_new_owned_timer_births_require_exact_profiles_without_relabeling_preexisting_origin(self):
        from ios.self_tests.avatar_callers2_fixture import scripts2,timer2
        before=scripts2();after=scripts2(sequence=2,request='ios-'+'8'*32,capture_offset=200);timer2(after,created_epoch=EPOCH+150)
        worker=after['source']['workers'][0];manager=worker['membership']['instance']
        actual,modules,_=modeled('protocol-watch-tick')
        for component in ('avatar','uiWork'):
            caller=worker[component]['callerStacks'][0];caller.update(callerStack=deepcopy(actual),callerModules=deepcopy(modules))
        self.assertEqual(set(exact_calls.owned_timers(before,after,{manager}).values()),{'protocol-watch-tick'})
        changed=deepcopy(after);changed['source']['workers'][0]['uiWork']['callerStacks'][0]['callerStack']['frames'][0]['column']+=1
        with self.assertRaises(NativeUIError):exact_calls.owned_timers(before,changed,{manager})

    def test_native_additive_component_uses_same_admitted_scope_and_leaves_create_projection_closed(self):
        manager=(ROOT/'libraries/script-engine/src/ScriptManager.cpp').read_text()
        start=manager.index('ScriptManager::FeatureNativeCallScope::FeatureNativeCallScope(ScriptManager* manager')
        body=manager[start:manager.index('ScriptManager::FeatureNativeCallScope::~FeatureNativeCallScope',start)]
        self.assertLess(body.index('QThread::currentThread()!=manager->thread()'),body.index('manager->featureAvatarV8Stack()'))
        self.assertIn('AvatarV8Callers::resolve(manager->featureAvatarV8Stack(),original.value("code").toList())',body)
        self.assertIn('{"callerStack",avatarCallers.stack},{"callerModules",avatarCallers.modules}',body)
        self.assertIn('manager->featureAvatarTimerCallers()',body) # unchanged weak legacy field
        create=(ROOT/'libraries/entities/src/CreateEntityObservation.h')
        if not create.exists():create=ROOT/'libraries/script-engine/src/CreateEntityObservation.h'
        source=create.read_text();self.assertNotIn('avatarCallers',source)

    def test_exact_open_read_profiles_are_separate_from_real_provider_and_callback_effect_joins(self):
        from ios.adapters import avatar_scripts,avatar_social_http
        from ios.adapters.avatar_code import pins
        from ios.self_tests import avatar_callers2_fixture as current
        from self_tests import test_avatar_social_provider as provider_tests
        from feature_journeys.avatar_social_provider import USERS
        logic=provider_tests.SocialTests();logic.setUp()
        with logic.provider.response('GET',USERS,'filter=connections',b'',logic.tokens['primary']) as response:
            status,raw,response_id,written=response
            written(dict(status=status,responseId=response_id,bytes=len(raw),sha256=current.wire(raw)['sha256']))
        value=current.http2(raw=raw,response_id=response_id,run=provider_tests.RUN)
        for entry,name in zip(value['callerStacks'],('xhr-page-request','xhr-response-callback')):
            actual,modules,_=modeled(name);entry.update(callerStack=actual,callerModules=modules)
        receipt=avatar_social_http.consumed_response(value,logic.provider.snapshot(provider_tests.RUN),provider_instance=logic.provider.instance,
            owned_origin='https://owned.invalid',run=provider_tests.RUN,ticket=provider_tests.TICKET,role='primary',after_native_epoch=EPOCH-100,
            after_provider_epoch=1700000000000,after_event=0)
        scripts=current.scripts2(run=provider_tests.RUN,capture_offset=200)
        self.assertEqual(exact_calls.consumed_http(scripts,value,receipt,pins()),('xhr-page-request','xhr-response-callback'))
        changed=deepcopy(value);changed['callerStacks'][1]['callerStack']['frames'][0]['column']+=1
        avatar_scripts.join_http_code(scripts,changed,receipt,pins(),require_actual=True)
        with self.assertRaises(NativeUIError):exact_calls.consumed_http(scripts,changed,receipt,pins())

    def test_actual_http_fixture_factory_afc_preserve_new_entity_component_and_literal_legacy(self):
        from ios.adapters import avatar_entities
        from ios.self_tests.test_ios_avatar_entities import packet
        from ios.self_tests.test_ios_avatar_callers_transport import AvatarCallersTransportTests
        legacy,*_=packet();value=AvatarCallersTransportTests.transport(self,avatar_entities,legacy,'avatar_entities')
        self.assertNotIn('avatarCallers',value['source']['events'][0]['caller'])
        actual,modules,code=modeled('avatar-wearable-create');who=legacy['source']['events'][0]['caller']
        who['avatarCode'].update(avatarScriptVersion=2,code=code)
        who['avatarCallers']=dict(avatarEntityCallersVersion=1,complete=True,callerStack=actual,callerModules=modules)
        value=AvatarCallersTransportTests.transport(self,avatar_entities,legacy,'avatar_entities')
        self.assertEqual(value['source']['events'][0]['caller']['avatarCallers'],who['avatarCallers'])
        self.assertEqual(exact_calls.entity(value['source']['events'][0]['caller'],value['clockAfter']['epochMs']),'avatar-wearable-create')


if __name__=='__main__':unittest.main()
