"""Strict optional cache/object/transport logic; all native producers modeled."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json,subprocess,unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from fixture.serve import FixtureState
from ios.adapters import chat_qml_sources as source,chat_qml_cache_loaded as cached
from ios.self_tests.chat_qml_cache_source_fixture import Boundary,RUN,URL,cache_packet,advance,unit,compiler
from ios.self_tests import test_ios_chat_qml_source_transport as legacy_transport
from ios.self_tests.retained_host_roots import retain_owned_root
from self_tests.test_native_feature_observation import probe_source


class ChatQmlCacheLoadedTests(unittest.TestCase):
    def test_actual_reviewed_root_input_pin_does_not_admit_missing_import_aot_or_installed_sources(self):
        value=cache_packet();original=deepcopy(value);source.original(value)
        actual=cached.pin_observed_unit(value,URL);self.assertEqual(cached.COVERAGE,actual['coverage'])
        self.assertTrue(all(flag is False for flag in actual['coverage'].values()))
        with self.assertRaises(NativeUIError):source.admit_direct_unit(value,URL)
        self.assertEqual(original,value)
        changed=deepcopy(value)
        for field in ('cacheAtLoad','cacheAtRead'):
            changed['source'][field]['unit']['mappingOriginal']['writeOriginal']['compilerInput']['sha256']='0'*64
        source.original(changed)
        with self.assertRaises(NativeUIError):cached.pin_observed_unit(changed,URL)

    def test_same_load_preserves_old_compiler_write_map_origins_and_reads_the_actual_unit_again(self):
        first=cache_packet();later=advance(first);query=dict(schemaVersion=1,action=source.ACTION,commandId=later['requestId'],runId=RUN)
        source.validate(later,query,42,previous=first)
        self.assertEqual(first['source']['cacheAtLoad'],later['source']['cacheAtLoad'])
        self.assertEqual(compiler(first),compiler(later))
        for fault in ('unit-owner','generation','mapping','context','old-current'):
            changed=deepcopy(later)
            if fault=='unit-owner':unit(changed,True)['unitOwnerId']='0'*32
            elif fault=='generation':unit(changed,True)['unitGeneration']+=1
            elif fault=='mapping':unit(changed,True)['mappingOriginal']['mappingId']='0'*32
            elif fault=='context':changed['source']['objectContextId']='0'*32
            else:changed['source']['cacheAtRead']=deepcopy(first['source']['cacheAtRead'])
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.validate(changed,query,42,previous=first)

    def test_recreated_root_can_consume_the_old_actual_mapping_without_inventing_a_new_compilation(self):
        first=cache_packet();later=advance(first);loaded=later['source']
        loaded.update(loadSequence=2,loadId='0'*32,objectId='1'*32)
        for field in ('loadBefore','loadCompleted'):
            loaded[field]['epochMs']+=100;loaded[field]['monotonicMs']+=100
        for field in ('unitReadBefore','unitReadAfter'):
            unit(later)[field]['epochMs']+=100;unit(later)[field]['monotonicMs']+=100
        query=dict(schemaVersion=1,action=source.ACTION,commandId=later['requestId'],runId=RUN)
        source.validate(later,query,42,previous=first)
        self.assertEqual(compiler(first),compiler(later))
        self.assertEqual(unit(first)['mappingOriginal'],unit(later)['mappingOriginal'])
        for fault in ('same-object','old-load-unit-read','loader-instance'):
            changed=deepcopy(later)
            if fault=='same-object':changed['source']['objectId']=first['source']['objectId']
            elif fault=='old-load-unit-read':changed['source']['cacheAtLoad']=deepcopy(first['source']['cacheAtLoad'])
            else:changed['source']['instance']='0'*32
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.validate(changed,query,42,previous=first)

    def test_component_and_actual_unit_binding_cannot_be_replaced_by_urls_or_equal_digests(self):
        for fault in ('component','executable','unit-source','unit-final','inode','map-digest','empty'):
            changed=cache_packet();loaded=changed['source']
            if fault=='component':loaded['cacheAtLoad']['componentMatched']=False
            elif fault=='executable':loaded['cacheAtRead']['executableUnitId']='0'*32
            elif fault=='unit-source':loaded['cacheAtLoad']['unitSourceUrl']='qrc:/foreign.qml'
            elif fault=='unit-final':loaded['cacheAtRead']['unitFinalUrl']='qrc:/foreign.qml'
            elif fault=='inode':unit(changed)['mappingOriginal']['mappedFile']['inode']='1002'
            elif fault=='map-digest':unit(changed,True)['mappingOriginal']['mappedSha256']='0'*64
            else:loaded['cacheAtRead']={}
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.original(changed)

    def test_missing_or_unknown_optional_versions_and_self_claimed_complete_sources_stay_unavailable(self):
        for fault in ('missing-cache','unknown-load','unknown-object','unknown-unit','complete','direct-confusion'):
            changed=cache_packet();loaded=changed['source']
            if fault=='missing-cache':del loaded['cacheAtLoad']
            elif fault=='unknown-load':loaded['iosLoadedQmlSourceVersion']=3
            elif fault=='unknown-object':loaded['cacheAtLoad']['qtOverteQmlObjectCacheReceiptVersion']=2
            elif fault=='unknown-unit':unit(changed)['qtOverteQmlCacheUnitVersion']=2
            elif fault=='complete':loaded['coverage']['installedQtSourceAvailable']=True
            else:loaded['iosLoadedQmlSourceVersion']=1
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.original(changed)

    def test_load_and_query_must_contain_separate_actual_unit_reads_without_retiming_the_mapping(self):
        for fault in ('before-load','after-load','before-query','after-query','clock-domain','read-reused'):
            changed=cache_packet()
            if fault=='before-load':unit(changed)['unitReadBefore']['epochMs']-=100
            elif fault=='after-load':unit(changed)['unitReadAfter']['epochMs']+=100
            elif fault=='before-query':unit(changed,True)['unitReadBefore']['epochMs']-=100
            elif fault=='after-query':unit(changed,True)['unitReadAfter']['epochMs']+=100
            elif fault=='clock-domain':unit(changed,True)['clockDomain']='host-afc-file-clock'
            else:changed['source']['cacheAtRead']=deepcopy(changed['source']['cacheAtLoad'])
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):source.original(changed)


class ChatQmlCacheExistingTransportTests(unittest.TestCase):
    def runtime(self):
        case=legacy_transport.ChatQmlSourceRuntimeTests();self.addCleanup(case.doCleanups);case.setUp()
        installed=case.f;temporary=installed.temp
        root=retain_owned_root(temporary,expected_root=installed.root)
        for index,(callback,args,kwargs) in enumerate(installed._cleanups):
            if getattr(callback,'__self__',None) is temporary:installed._cleanups[index]=(temporary.cleanup,args,kwargs)
        print('retained cache transport root',root,flush=True);case.boundary=Boundary();return case

    def test_existing_http_afc_factory_reads_v2_original_without_new_sessions_or_commands(self):
        case=self.runtime();before=case.f.sessions,case.f.launches;reader=case.reader();value=reader.read(RUN)
        cached.pin_observed_unit(value,URL)
        self.assertEqual(before,(case.f.sessions,case.f.launches));self.assertEqual((1,1),(len(case.boundary.queries),len(case.afc)))
        self.assertEqual(source.FILE,case.afc[-1].rsplit('/',1)[-1])
        self.assertEqual(value,json.loads(case.boundary.raw));self.assertEqual(1,reader.acquisition['iosChatQmlSourcesAcquisitionVersion'])

    def test_lost_http_or_later_unavailable_cache_never_resubmits_or_returns_previous_good_root(self):
        case=self.runtime();reader=case.reader();first=reader.read(RUN)
        def unavailable(value):value['source']['cacheAtRead']={}
        case.boundary.mutate=unavailable
        with self.assertRaises(NativeUIError):reader.read(RUN)
        self.assertEqual(first,reader.last);self.assertEqual(2,len(case.boundary.queries))
        case.boundary.mutate=None;case.lose_return=True;before=len(case.boundary.queries)
        with self.assertRaises(NativeUIError):case.reader().read(RUN)
        self.assertEqual(before+1,len(case.boundary.queries));self.assertEqual(2,len(case.afc))

    def test_actual_existing_probe_preserves_v2_original_and_lost_native_or_save_delivery_is_not_replayed(self):
        query=dict(schemaVersion=1,commandId='ios-'+'a'*32,action=source.ACTION,runId=RUN)
        original=cache_packet();self.assertEqual(query,FixtureState().set_client_command(query))
        program='''const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,k)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.sort());
const original=PACKET;let calls=0,files=[];
const Test={featureIOSChatQmlSources:q=>{calls++;return {...original,requestId:q.commandId}},saveObject:(v,f)=>files.push({v,f})};
SOURCE
const q=QUERY;applyClientCommand(q);applyClientCommand(q);
if(calls!==1||files.length!==1||files[0].f!=="feature-ios-chat-qml-sources.json"||JSON.stringify(files[0].v.source)!==JSON.stringify(original.source))throw Error("cache original replaced/replayed");
Test.featureIOSChatQmlSources=()=>{calls++;throw Error("declared unknown native result")};
const lostNative={...q,commandId:"ios-"+"b".repeat(32)};applyClientCommand(lostNative);applyClientCommand(lostNative);
if(calls!==2)throw Error("unknown native query replayed");
Test.featureIOSChatQmlSources=q=>{calls++;return {...original,requestId:q.commandId}};
Test.saveObject=(v,f)=>{files.push({v,f});throw Error("declared lost save return")};
const lostSave={...q,commandId:"ios-"+"c".repeat(32)};try{applyClientCommand(lostSave)}catch(e){}applyClientCommand(lostSave);
if(calls!==3||files.at(-1).f!=="feature-ios-chat-qml-sources.json")throw Error("unknown saved result replayed");
'''.replace('PACKET',json.dumps(original)).replace('QUERY',json.dumps(query)).replace('SOURCE',probe_source())
        result=subprocess.run(['node','-'],input=program,capture_output=True,text=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr)


if __name__=='__main__':unittest.main()
