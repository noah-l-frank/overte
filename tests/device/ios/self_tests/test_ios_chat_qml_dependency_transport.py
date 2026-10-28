"""Actual existing physical/HTTP/AFC/IPA and JS-probe paths; native Qt is a model."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json,struct,subprocess,unittest
from unittest.mock import patch
from adapters.normal_ui import NativeUIError
from ios.adapters import feature_observation,chat_qml_sources
from ios.self_tests import test_ios_chat_qml_cache_runtime as physical_fixture
from ios.self_tests import test_ios_chat_qml_dependencies as dependency_fixture
from ios.self_tests import test_ios_qt_image_bytes as image_fixture
from ios.self_tests.chat_qml_cache_source_fixture import RUN
from self_tests.test_native_feature_observation import probe_source


def packet(original,image,sequence):
    # New modeled native observations only. Original compiler/write/map/eval
    # clocks stay unchanged; no retained source receipt is relabeled or retimed.
    value=deepcopy(original);source=value['source'];epoch=source['loadBefore']['epochMs']-90
    _unused,object_model=dependency_fixture.fixture(epoch)
    source['iosLoadedQmlSourceVersion']=3
    clock=lambda delta:dict(epochMs=epoch+delta,monotonicMs=delta)
    for field,component,before,after in (('dependencyAtLoad',True,102,107),
            ('dependencyAtRead',False,value['clockAfter']['epochMs']-epoch,value['clockAfter']['epochMs']-epoch)):
        obj=deepcopy(object_model);obj['componentMatched']=component;graph=obj['source']
        graph.update(before=clock(before),after=clock(after))
        for pass_name in ('beforeOriginal','afterOriginal'):
            if component:
                # The real evaluation model occurs later than this new load
                # snapshot; it is unavailable here, never moved backwards.
                for edge in graph[pass_name]['edges']:
                    if edge['kind']=='dependent-script':edge['evaluation']={}
        source[field]=obj
    first=deepcopy(image);first.update(sequence=sequence,beforeEpochMs=value['clockAfter']['epochMs'],afterEpochMs=value['clockAfter']['epochMs'])
    second=deepcopy(first);second.update(sequence=sequence+1,beforeEpochMs=first['afterEpochMs'],symbolFileOffset='257')
    value.update(iosChatQmlSourcesVersion=3,qtEntryImage=first,qtDependencyEntryImage=second)
    return value


class ChatQmlDependencyTransportTests(unittest.TestCase):
    def runtime(self,*,short_segment=False):
        if short_segment:
            real_macho=image_fixture.macho
            def bytes_with_nonexecutable_tail():
                raw=bytearray(real_macho());struct.pack_into('<Q',raw,32+24+48,384);return bytes(raw)
            with patch.object(image_fixture,'macho',side_effect=bytes_with_nonexecutable_tail):
                case=physical_fixture.ChatQmlCachePhysicalRuntimeTests();self.addCleanup(case.doCleanups);case.setUp()
        else:
            case=physical_fixture.ChatQmlCachePhysicalRuntimeTests();self.addCleanup(case.doCleanups);case.setUp()
        post=feature_observation.post_request.side_effect
        case.transport_mutate=None
        def existing_transport(request,timeout):
            response=post(request,timeout);query=json.loads(request.data)
            if query['action']==chat_qml_sources.ACTION:
                value=packet(json.loads(case.boundary.raw),case.image,2*case.sequence-1)
                if case.transport_mutate:case.transport_mutate(value)
                case.boundary.raw=json.dumps(value)
            return response
        self.enterContext(patch.object(feature_observation,'post_request',side_effect=existing_transport));return case

    def test_actual_physical_source_binds_both_getters_without_new_session_and_keeps_historical_eval(self):
        case=self.runtime();original,bindings=case.f.adapter._chat_qml_dependency_source('test-only',RUN)
        self.assertEqual(original,json.loads(case.boundary.raw));self.assertEqual(2,len(bindings))
        self.assertEqual([original['qtEntryImage'],original['qtDependencyEntryImage']],[v['original'] for v in bindings])
        self.assertTrue(all(v['imageBytesBound'] and not v['qtSdkSourceAvailable'] and not v['importGraphAvailable'] and not v['aotGraphAvailable'] for v in bindings))
        later,_bindings=case.f.adapter._chat_qml_dependency_source('test-only',RUN)
        query=dict(schemaVersion=1,action=chat_qml_sources.ACTION,runId=RUN,commandId=later['requestId'])
        chat_qml_sources.validate(later,query,42,previous=original)
        event=lambda v:v['source']['dependencyAtRead']['source']['afterOriginal']['edges'][0]['evaluation']['original']
        self.assertEqual(event(original),event(later));self.assertEqual((2,2),(len(case.boundary.queries),len(case.afc)))
        case.assert_owners_unchanged()

    def test_missing_graph_or_legacy_outer_cannot_become_a_dependency_source(self):
        for fault in ('missing','legacy'):
            case=self.runtime()
            def mutate(value):
                if fault=='missing':value['source']['dependencyAtRead']={}
                else:value['iosChatQmlSourcesVersion']=2
            case.transport_mutate=mutate
            with self.subTest(fault=fault),self.assertRaises((ValueError,NativeUIError)):
                case.f.adapter._chat_qml_dependency_source('test-only',RUN)
            self.assertEqual((1,1),(len(case.boundary.queries),len(case.afc)));case.assert_owners_unchanged()

    def test_second_actual_callsite_must_independently_lie_in_selected_ipa_executable_range(self):
        case=self.runtime(short_segment=True)
        case.transport_mutate=lambda value:value['qtDependencyEntryImage'].update(symbolFileOffset='400')
        # Offset400 is below actual fileBytes512 and shares the same true
        # header/UUID/file digest. Only the actual parsed executable range0..384
        # rejects it; cache getter offset256 remains valid.
        with self.assertRaises((ValueError,NativeUIError)):
            case.f.adapter._chat_qml_dependency_source('test-only',RUN)
        self.assertEqual((1,1),(len(case.boundary.queries),len(case.afc)));case.assert_owners_unchanged()

    def test_lost_return_or_changed_process_never_replays_queries_or_returns_an_old_source(self):
        case=self.runtime();original,_bindings=case.f.adapter._chat_qml_dependency_source('test-only',RUN)
        case.lost=True
        with self.assertRaises((ValueError,NativeUIError)):case.f.adapter._chat_qml_dependency_source('test-only',RUN)
        self.assertEqual((2,1),(len(case.boundary.queries),len(case.afc)))
        self.assertNotEqual(original['requestId'],case.boundary.queries[-1]['commandId'])
        case.lost=False;case.f.process['pid']=43
        with self.assertRaises((ValueError,NativeUIError)):case.f.adapter._chat_qml_dependency_source('test-only',RUN)
        self.assertEqual((2,1),(len(case.boundary.queries),len(case.afc)));case.assert_owners_unchanged()

    def test_actual_existing_js_probe_writes_v3_original_once_to_same_private_filename(self):
        case=self.runtime();original,_bindings=case.f.adapter._chat_qml_dependency_source('test-only',RUN)
        query=dict(schemaVersion=1,commandId='ios-'+'9'*32,action=chat_qml_sources.ACTION,runId=RUN)
        program='''const Uuid={generate:()=>"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"};
const objectKeysMatch=(v,k)=>JSON.stringify(Object.keys(v).sort())===JSON.stringify(k.sort());
const original=PACKET;let calls=0,saved=[];
const Test={featureIOSChatQmlSources:q=>{calls++;return {...original,requestId:q.commandId}},saveObject:(v,f)=>saved.push({v,f})};
SOURCE
const q=QUERY;applyClientCommand(q);applyClientCommand(q);
if(calls!==1||saved.length!==1||saved[0].f!=="feature-ios-chat-qml-sources.json")throw Error("replayed/foreign writer");
process.stdout.write(JSON.stringify(saved[0].v));
'''.replace('PACKET',json.dumps(original)).replace('QUERY',json.dumps(query)).replace('SOURCE',probe_source())
        result=subprocess.run(['node','-'],input=program,text=True,capture_output=True,timeout=5)
        self.assertEqual(0,result.returncode,result.stderr);saved=json.loads(result.stdout)
        self.assertEqual(dict(original,requestId=query['commandId']),saved);chat_qml_sources.original(saved)


if __name__=='__main__':unittest.main()
