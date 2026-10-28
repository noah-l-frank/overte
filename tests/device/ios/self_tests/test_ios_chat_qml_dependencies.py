"""Strict dependency/evaluation reader countercases; Qt producers are models.

The existing reviewed root input pin is read independently. No native Qt,
module evaluation, loader threading or SDK execution is simulated as a PASS.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import unittest
from adapters.normal_ui import NativeUIError
from ios.adapters import chat_qml_cache_loaded as reader
from ios.self_tests.chat_qml_cache_source_fixture import cache_packet,unit


def fixture(epoch=None):
    source=cache_packet() if epoch is None else cache_packet(epoch);epoch=source['clockBefore']['epochMs']-1000
    current=unit(source,True);origin=deepcopy(current)
    code={key:origin[key] for key in ('unitOwnerId','unitGeneration','unitBytes','unitSha256')};code['aot']=False
    prefix=deepcopy(origin['mappingOriginal']['writeOriginal']['compilerInput'])
    child=dict(unitOwnerId='7'*32,unitGeneration=0,unitBytes=prefix['compilerUnitBytes'],unitSha256=prefix['compilerUnitSha256'],aot=False)
    clock=lambda delta:dict(epochMs=epoch+delta,monotonicMs=delta)
    event=dict(qtOverteQmlScriptEvaluationVersion=1,processId=42,clockDomain='native-qt-steady-clock',
        scriptDataId='4'*32,unit=deepcopy(child),executableUnitId='5'*32,before=clock(200),after=clock(201),
        evaluated=True,moduleStateTransition='unevaluated-to-evaluated',sequence=3)
    evaluation=dict(scriptDataId='4'*32,original=event,currentExecutableAssociationAvailable=False,parentContextAssociationAvailable=False)
    first=dict(nodes=[dict(index=0,unit=code,sourceKind='mapped-cache',sourceOriginal=origin),
        dict(index=1,unit=child,sourceKind='compiler-prefix',sourceOriginal=prefix)],
        edges=[dict(**{'from':0},kind='dependent-script',slot=0,to=1,missing=False,scriptDataId='4'*32,evaluation=evaluation),
            dict(**{'from':1},kind='self-type',slot=1,to=1,missing=False)])
    for node in first['nodes']:node.update(captureBefore=clock(39),captureAfter=clock(42))
    first['nodes'][0]['sourceOriginal'].update(unitReadBefore=clock(40),unitReadAfter=clock(41))
    last=deepcopy(first)
    graph=dict(qtOverteQmlDependencyOriginalVersion=1,processId=42,clockDomain='native-qt-steady-clock',
        before=clock(1002),after=clock(1007),beforeOriginal=first,afterOriginal=last,
        coverage=dict(importGraphAvailable=False,aotGraphAvailable=False,nativeTypeCodeAvailable=False,
            dynamicDependenciesAvailable=False,currentRootEvaluationAvailable=False,
            dependencyMembershipCurrentAvailable=False,installedQtSourceAvailable=False))
    obj=dict(qtOverteQmlObjectDependencyOriginalVersion=1,processId=42,executableUnitId='b'*32,componentMatched=False,source=graph)
    return source,obj


class ChatQmlDependencyOriginalTests(unittest.TestCase):
    def test_observed_owner_edges_and_historical_evaluation_stay_partial_after_real_root_decoder_join(self):
        source,obj=fixture();before=deepcopy(obj)
        self.assertEqual(obj,reader.dependencies_for_loaded_root(obj,source));self.assertEqual(before,obj)
        self.assertTrue(all(value is False for value in obj['source']['coverage'].values()))

    def test_actual_membership_owner_or_generation_must_match_both_readonly_passes(self):
        for fault in ('owner','generation','edge','script-data'):
            _source,obj=fixture();last=obj['source']['afterOriginal']
            if fault=='owner':last['nodes'][1]['unit']['unitOwnerId']='6'*32
            elif fault=='generation':last['nodes'][1]['unit']['unitGeneration']=1
            elif fault=='edge':last['edges'].pop()
            else:last['edges'][0]['scriptDataId']='6'*32
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):reader.dependency_original(obj['source'],42)

    def test_equal_source_hash_or_url_does_not_replace_current_root_owner_or_executable(self):
        for fault in ('owner','executable'):
            source,obj=fixture()
            if fault=='executable':obj['executableUnitId']='6'*32
            else:
                for name in ('beforeOriginal','afterOriginal'):
                    node=obj['source'][name]['nodes'][0];node['unit']['unitOwnerId']='6'*32
                    node['sourceOriginal']['unitOwnerId']='6'*32
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):reader.dependencies_for_loaded_root(obj,source)

    def test_cached_value_noop_failed_or_foreign_unit_cannot_become_successful_current_evaluation(self):
        for fault in ('cached-noop','current-root','context','unit','foreign-executable','late-event'):
            _source,obj=fixture()
            for name in ('beforeOriginal','afterOriginal'):
                value=obj['source'][name]['edges'][0]['evaluation'];event=value['original']
                if fault=='cached-noop':event['moduleStateTransition']='already-evaluated'
                elif fault=='current-root':value['currentExecutableAssociationAvailable']=True
                elif fault=='context':value['parentContextAssociationAvailable']=True
                elif fault=='unit':event['unit']['unitGeneration']=2
                elif fault=='foreign-executable':event['executableUnitId']=None
                else:event['after']['epochMs']+=2000
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):reader.dependency_original(obj['source'],42)

    def test_unknown_native_or_aot_edges_stay_unavailable_and_cannot_self_claim_complete(self):
        source,obj=fixture()
        for name in ('beforeOriginal','afterOriginal'):
            obj['source'][name]['edges'].append(dict(**{'from':0},kind='resolved-type',slot=2,to=-1,missing=True))
        self.assertEqual(obj,reader.dependencies_for_loaded_root(obj,source))
        for field in obj['source']['coverage']:
            changed=deepcopy(obj);changed['source']['coverage'][field]=True
            with self.subTest(field=field),self.assertRaises(NativeUIError):reader.dependency_original(changed['source'],42)

    def test_unreachable_duplicate_out_of_range_and_unbound_compiler_output_are_rejected(self):
        for fault in ('unreachable','duplicate','range','prefix','too-many'):
            _source,obj=fixture()
            for name in ('beforeOriginal','afterOriginal'):
                value=obj['source'][name]
                if fault=='unreachable':value['edges']=value['edges'][1:]
                elif fault=='duplicate':value['edges'].append(deepcopy(value['edges'][0]))
                elif fault=='range':value['edges'][0]['to']=64
                elif fault=='prefix':value['nodes'][1]['sourceOriginal']['compilerUnitSha256']='0'*64
                else:value['nodes']*=65
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):reader.dependency_original(obj['source'],42)

    def test_one_actual_resolved_type_slot_cannot_be_both_self_and_foreign(self):
        _source,obj=fixture()
        for name in ('beforeOriginal','afterOriginal'):
            # Existing self edge is from1/slot1/to1. Target0 already exists and
            # is reachable, so no dangling node/owner/eval fact masks this case.
            obj['source'][name]['edges'].append(dict(**{'from':1},kind='resolved-type',slot=1,to=0,missing=False))
        with self.assertRaises(NativeUIError):reader.dependency_original(obj['source'],42)

    def test_original_loader_capture_clocks_cannot_be_retimed_into_current_graph_query(self):
        for fault in ('retimed-unit','future-capture'):
            _source,obj=fixture();graph=obj['source']
            for name in ('beforeOriginal','afterOriginal'):
                node=graph[name]['nodes'][0]
                if fault=='retimed-unit':
                    node['sourceOriginal']['unitReadBefore']=deepcopy(graph['before'])
                    node['sourceOriginal']['unitReadAfter']=deepcopy(graph['after'])
                else:
                    node['captureAfter']={key:value+10 for key,value in graph['after'].items()}
            with self.subTest(fault=fault),self.assertRaises(NativeUIError):reader.dependency_original(graph,42)


    def test_one_script_data_identity_cannot_report_two_different_nonempty_evaluation_originals(self):
        source,obj=fixture()
        first=obj['source']['beforeOriginal'];duplicate=deepcopy(first['edges'][0]);duplicate['slot']=2
        first['edges'].append(duplicate)
        # Existing target1, a distinct script slot and unchanged valid clocks:
        # this repeated immutable event is a permitted graph, not a duplicate
        # edge/owner, dangling target or query-pass mismatch.
        obj['source']['afterOriginal']=deepcopy(first)
        self.assertEqual(obj,reader.dependencies_for_loaded_root(obj,source))
        for state in ('one-empty','both-empty','different-historical-child'):
            allowed=deepcopy(obj)
            for name in ('beforeOriginal','afterOriginal'):
                edges=allowed['source'][name]['edges'];edges[-1]['evaluation']={}
                if state=='both-empty':edges[0]['evaluation']={}
                elif state=='different-historical-child':edges[-1]['to']=0
            with self.subTest(allowed=state):self.assertEqual(allowed,reader.dependencies_for_loaded_root(allowed,source))
        for name in ('beforeOriginal','afterOriginal'):
            # Both events remain individually valid; only their sequence
            # differs for the SAME ScriptData, and BOTH passes are identical.
            graph=obj['source'][name];edge=graph['edges'][-1]
            edge['evaluation']['original']['sequence']+=1
            reader.script_evaluation_original(edge['evaluation'],42,graph['nodes'][edge['to']]['unit'],obj['source']['before']['epochMs'])
        self.assertEqual(obj['source']['beforeOriginal'],obj['source']['afterOriginal'])
        with self.assertRaises(NativeUIError):reader.dependencies_for_loaded_root(obj,source)



if __name__=='__main__':unittest.main()
