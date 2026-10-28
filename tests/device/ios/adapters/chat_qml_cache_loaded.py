"""Optional cached-root observation; imports/AOT/installed Qt stay unavailable.

The existing request, probe, result filename, authenticated HTTP/AFC factory and
version-one direct-unit reader remain in use. This is no complete Chat gate.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from urllib.parse import urlsplit
from adapters.native_feature_observation import exact,integer,need
from adapters.script_feature.history import same
from ios.adapters import chat_qml_cache_originals as cache
from ios.adapters.chat_qml_sources import identity,interval,url,pins

COVERAGE=dict(importGraphAvailable=False,aotGraphAvailable=False,installedQtSourceAvailable=False)


def object_receipt(value,pid,*,component):
    exact(value,{'qtOverteQmlObjectCacheReceiptVersion','processId','executableUnitId','componentMatched','unitSourceUrl','unitFinalUrl','unit'})
    need(type(value['qtOverteQmlObjectCacheReceiptVersion']) is int and value['qtOverteQmlObjectCacheReceiptVersion']==1
        and type(value['processId']) is int and value['processId']==pid
        and type(value['componentMatched']) is bool and value['componentMatched'] is component)
    identity(value['executableUnitId']);cache.validate(value['unit'],pid)
    source=value['unit']['mappingOriginal']['writeOriginal']['compilerInput']
    need(url(value['unitSourceUrl'])==url(source['requestedUrl'])
        and url(value['unitFinalUrl'])==url(source['resolvedUrl']))
    return value


def identity_fields(value):
    result=deepcopy(value);result.pop('componentMatched')
    result['unit'].pop('unitReadBefore');result['unit'].pop('unitReadAfter');return result


def compiler_origin(value):return value['cacheAtLoad']['unit']['mappingOriginal']['writeOriginal']['compilerInput']


def loaded(value,pid,epoch,read_after_epoch):
    exact(value,{'iosLoadedQmlSourceVersion','instance','loadSequence','loadId','objectId',
        'creationContextId','objectContextId','processId','clockDomain','loadBefore','loadCompleted',
        'requestedUrl','selectedUrl','componentUrl','creationContextUrl','objectContextUrl',
        'sourceKind','cacheAtLoad','cacheAtRead','coverage'})
    need(type(value['iosLoadedQmlSourceVersion']) is int and value['iosLoadedQmlSourceVersion']==2
        and integer(value['loadSequence'],1,64) and type(value['processId']) is int and value['processId']==pid
        and value['clockDomain']=='native-main-qml-load' and value['sourceKind']=='observed-cache')
    for field in ('instance','loadId','objectId','creationContextId','objectContextId'):identity(value[field])
    interval(value['loadBefore'],value['loadCompleted']);need(value['loadCompleted']['epochMs']<=epoch)
    need(integer(read_after_epoch,epoch))
    for field in ('requestedUrl','selectedUrl','componentUrl'):url(value[field])
    for field in ('creationContextUrl','objectContextUrl'):url(value[field],empty=True)
    need(urlsplit(value['requestedUrl']).path.endswith('/armored-chat/armored_chat.qml'))
    load=object_receipt(value['cacheAtLoad'],pid,component=True)
    current=object_receipt(value['cacheAtRead'],pid,component=False)
    need(identity_fields(load)==identity_fields(current))
    at_load=load['unit'];at_read=current['unit']
    need(value['loadBefore']['epochMs']<=at_load['unitReadBefore']['epochMs']
        and at_load['unitReadAfter']['epochMs']<=value['loadCompleted']['epochMs']
        and epoch<=at_read['unitReadBefore']['epochMs']<=at_read['unitReadAfter']['epochMs']<=read_after_epoch)
    cache.validate(at_read,pid,epoch=read_after_epoch,previous=at_load)
    exact(value['coverage'],{'importGraphAvailable','aotGraphAvailable','installedQtSourceAvailable'})
    need(all(flag is False for flag in value['coverage'].values()))
    need(len(json.dumps(value,ensure_ascii=False,allow_nan=False).encode())<=32768)
    return value


def same_load(current,previous):
    need(current['iosLoadedQmlSourceVersion']==previous['iosLoadedQmlSourceVersion']==2)
    need(all(same(current[key],previous[key]) for key in current if key!='cacheAtRead'))
    cache.validate(current['cacheAtRead']['unit'],current['processId'],previous=previous['cacheAtRead']['unit'])
    return True


def pin_observed_unit(value,expected_url):
    """Compare only observed decoded root input to independent reviewed pins."""
    from ios.adapters.chat_qml_sources import original
    original(value);actual=value['source'];need(actual['iosLoadedQmlSourceVersion']==2)
    compiler=compiler_origin(actual);expected=pins()
    need(url(compiler['resolvedUrl'])==url(expected_url)
        and all(compiler[field]==expected[field] for field in ('codeUnits','sha256')))
    # coverage remains false; this never admits imports, native AOT or SDK.
    return deepcopy(actual)


def dependency_unit(value):
    exact(value,{'unitOwnerId','unitGeneration','unitBytes','unitSha256','aot'})
    identity(value['unitOwnerId']);cache.digest(value['unitSha256'])
    need(integer(value['unitGeneration'],0,999999999) and integer(value['unitBytes'],200,4*1024*1024)
        and type(value['aot']) is bool);return value


def script_evaluation_original(value,pid,unit,before_epoch):
    exact(value,{'scriptDataId','original','currentExecutableAssociationAvailable','parentContextAssociationAvailable'})
    identity(value['scriptDataId']);need(value['currentExecutableAssociationAvailable'] is False
        and value['parentContextAssociationAvailable'] is False)
    original=value['original']
    exact(original,{'qtOverteQmlScriptEvaluationVersion','processId','clockDomain','scriptDataId','unit',
        'executableUnitId','before','after','evaluated','moduleStateTransition','sequence'})
    need(type(original['qtOverteQmlScriptEvaluationVersion']) is int and original['qtOverteQmlScriptEvaluationVersion']==1
        and type(original['processId']) is int and original['processId']==pid and original['clockDomain']==cache.DOMAIN
        and original['scriptDataId']==value['scriptDataId'] and original['evaluated'] is True
        and original['moduleStateTransition']=='unevaluated-to-evaluated'
        and integer(original['sequence'],1,1000000000))
    identity(original['executableUnitId']);dependency_unit(original['unit'])
    need(same(original['unit'],unit) and unit['aot'] is False)
    interval(original['before'],original['after']);need(original['after']['epochMs']<=before_epoch)
    return value


def _dependency_pass(value,pid,before,after):
    exact(value,{'nodes','edges'});nodes,edges=value['nodes'],value['edges']
    need(type(nodes) is list and 1<=len(nodes)<=64 and type(edges) is list and len(edges)<=256)
    owners=set();total=0
    for index,node in enumerate(nodes):
        exact(node,{'index','unit','sourceKind','sourceOriginal','captureBefore','captureAfter'})
        interval(node['captureBefore'],node['captureAfter'])
        need(node['captureAfter']['epochMs']<=after)
        need(type(node['index']) is int and node['index']==index)
        unit=dependency_unit(node['unit']);need(unit['unitOwnerId'] not in owners);owners.add(unit['unitOwnerId'])
        total+=unit['unitBytes'];need(total<=16*1024*1024)
        kind,original=node['sourceKind'],node['sourceOriginal']
        need(kind in ('unavailable','mapped-cache','direct-unit','compiler-prefix'))
        if kind=='unavailable':need(type(original) is dict and not original);continue
        need(unit['aot'] is False)
        if kind=='mapped-cache':
            cache.validate(original,pid)
            need(all(original[key]==unit[key] for key in ('unitOwnerId','unitGeneration','unitBytes','unitSha256'))
                and node['captureBefore']['epochMs']<=original['unitReadBefore']['epochMs']
                    <=original['unitReadAfter']['epochMs']<=node['captureAfter']['epochMs'])
        elif kind=='direct-unit':
            from ios.adapters.chat_qml_sources import compiler_input
            compiler_input(original,pid,node['captureBefore']['epochMs'])
            need(all(original[key]==unit[key] for key in ('unitGeneration','unitBytes','unitSha256')))
        else:
            cache.compiler_prefix(original,pid)
            need(original['compilerUnitBytes']==unit['unitBytes'] and original['compilerUnitSha256']==unit['unitSha256']
                and original['sourceAfterEpochMs']<=node['captureBefore']['epochMs'])
    found=set();reachable={0};script_evaluations={}
    for edge in edges:
        need(type(edge) is dict and edge.get('kind') in ('self-type','resolved-type','dependent-script'))
        keys={'from','kind','slot','to','missing'}
        if edge['kind']=='dependent-script':keys|={'scriptDataId','evaluation'}
        exact(edge,keys);need(integer(edge['from'],0,len(nodes)-1) and integer(edge['slot'],0,2**31-1)
            and integer(edge['to'],-1,len(nodes)-1) and type(edge['missing']) is bool
            and edge['missing'] is (edge['to']==-1))
        channel='script' if edge['kind']=='dependent-script' else 'type'
        key=(edge['from'],channel,edge['slot']);need(key not in found);found.add(key)
        if edge['kind']=='self-type':need(edge['to']==edge['from'] and edge['missing'] is False)
        if edge['kind']=='dependent-script':
            identity(edge['scriptDataId']);need(type(edge['evaluation']) is dict)
            if edge['evaluation']:
                need(edge['to']>=0)
                script_evaluation_original(edge['evaluation'],pid,nodes[edge['to']]['unit'],before)
                need(edge['evaluation']['scriptDataId']==edge['scriptDataId'])
                # A single actual ScriptData state publishes one immutable
                # event original. Historical child edges and empty events do
                # not require the same current child-unit association.
                original=edge['evaluation']['original'];script=edge['scriptDataId']
                need(script not in script_evaluations or same(script_evaluations[script],original))
                script_evaluations[script]=original
    for _ in nodes:
        for edge in edges:
            if edge['from'] in reachable and edge['to']>=0:reachable.add(edge['to'])
    need(reachable==set(range(len(nodes))));return value


def dependency_original(value,pid):
    exact(value,{'qtOverteQmlDependencyOriginalVersion','processId','clockDomain','before','after',
        'beforeOriginal','afterOriginal','coverage'})
    need(integer(pid,1) and type(value['qtOverteQmlDependencyOriginalVersion']) is int
        and value['qtOverteQmlDependencyOriginalVersion']==1 and type(value['processId']) is int
        and value['processId']==pid and value['clockDomain']==cache.DOMAIN)
    interval(value['before'],value['after'],current=True)
    exact(value['coverage'],{'importGraphAvailable','aotGraphAvailable','nativeTypeCodeAvailable',
        'dynamicDependenciesAvailable','currentRootEvaluationAvailable','dependencyMembershipCurrentAvailable','installedQtSourceAvailable'})
    need(all(flag is False for flag in value['coverage'].values()))
    first=_dependency_pass(value['beforeOriginal'],pid,value['before']['epochMs'],value['after']['epochMs'])
    last=_dependency_pass(value['afterOriginal'],pid,value['before']['epochMs'],value['after']['epochMs'])
    # Both passes read the SAME immutable loader originals. Capture/read clocks
    # are not rewritten into the current query; fresh query clocks are separate.
    need(same(first,last))
    need(len(json.dumps(value,ensure_ascii=False,allow_nan=False).encode())<=65536);return value


def dependencies_for_loaded_root(value,source):
    """Partial raw-owner join only. No current execution/import/SDK authority."""
    from ios.adapters.chat_qml_sources import original
    original(source);pid=source['processId'];loaded=source['source']
    need(loaded['iosLoadedQmlSourceVersion']==2)
    exact(value,{'qtOverteQmlObjectDependencyOriginalVersion','processId','executableUnitId','componentMatched','source'})
    need(type(value['qtOverteQmlObjectDependencyOriginalVersion']) is int and value['qtOverteQmlObjectDependencyOriginalVersion']==1
        and type(value['processId']) is int and value['processId']==pid and value['componentMatched'] is False)
    identity(value['executableUnitId']);need(value['executableUnitId']==loaded['cacheAtRead']['executableUnitId'])
    graph=dependency_original(value['source'],pid);root=graph['afterOriginal']['nodes'][0]['unit']
    current=loaded['cacheAtRead']['unit']
    need(root['aot'] is False and all(root[key]==current[key]
        for key in ('unitOwnerId','unitGeneration','unitBytes','unitSha256'))
        and graph['before']['epochMs']>=current['unitReadAfter']['epochMs'])
    return deepcopy(value)


def _dependency_for_cache(value,observed,pid,component):
    exact(value,{'qtOverteQmlObjectDependencyOriginalVersion','processId','executableUnitId','componentMatched','source'})
    need(type(value['qtOverteQmlObjectDependencyOriginalVersion']) is int and value['qtOverteQmlObjectDependencyOriginalVersion']==1
        and type(value['processId']) is int and value['processId']==pid and value['componentMatched'] is component)
    identity(value['executableUnitId']);need(value['executableUnitId']==observed['executableUnitId'])
    graph=dependency_original(value['source'],pid);root=graph['afterOriginal']['nodes'][0]['unit'];unit=observed['unit']
    need(root['aot'] is False and all(root[key]==unit[key] for key in ('unitOwnerId','unitGeneration','unitBytes','unitSha256'))
        and graph['before']['epochMs']>=unit['unitReadAfter']['epochMs']);return graph


def dependency_membership(value):
    result=deepcopy(value['source']['afterOriginal'])
    for node in result['nodes']:
        node.pop('captureBefore');node.pop('captureAfter')
        if node['sourceKind']=='mapped-cache':
            node['sourceOriginal'].pop('unitReadBefore');node['sourceOriginal'].pop('unitReadAfter')
    for edge in result['edges']:edge.pop('evaluation',None)
    return result


def same_load_dependencies(current,previous):
    need(current['iosLoadedQmlSourceVersion']==previous['iosLoadedQmlSourceVersion']==3)
    need(all(same(current[key],previous[key]) for key in current if key not in ('cacheAtRead','dependencyAtRead')))
    cache.validate(current['cacheAtRead']['unit'],current['processId'],previous=previous['cacheAtRead']['unit'])
    old,new=previous['dependencyAtRead'],current['dependencyAtRead']
    need(new['source']['before']['epochMs']>=old['source']['after']['epochMs']
        and new['source']['before']['monotonicMs']>=old['source']['after']['monotonicMs']
        and same(dependency_membership(old),dependency_membership(new)))
    for before,after in zip(old['source']['afterOriginal']['edges'],new['source']['afterOriginal']['edges']):
        if before['kind']=='dependent-script' and before['evaluation'] and after['evaluation']:
            original,observed=before['evaluation']['original'],after['evaluation']['original']
            if not same(original,observed):need(observed['sequence']>original['sequence']
                and observed['before']['epochMs']>=original['after']['epochMs']
                and observed['before']['monotonicMs']>=original['after']['monotonicMs'])
    return True


def loaded_dependencies(value,pid,epoch,read_after_epoch):
    exact(value,{'iosLoadedQmlSourceVersion','instance','loadSequence','loadId','objectId',
        'creationContextId','objectContextId','processId','clockDomain','loadBefore','loadCompleted',
        'requestedUrl','selectedUrl','componentUrl','creationContextUrl','objectContextUrl',
        'sourceKind','cacheAtLoad','cacheAtRead','coverage','dependencyAtLoad','dependencyAtRead'})
    need(type(value['iosLoadedQmlSourceVersion']) is int and value['iosLoadedQmlSourceVersion']==3
        and integer(value['loadSequence'],1,64) and type(value['processId']) is int and value['processId']==pid
        and value['clockDomain']=='native-main-qml-load' and value['sourceKind']=='observed-cache')
    for field in ('instance','loadId','objectId','creationContextId','objectContextId'):identity(value[field])
    interval(value['loadBefore'],value['loadCompleted']);need(value['loadCompleted']['epochMs']<=epoch)
    need(integer(read_after_epoch,epoch))
    for field in ('requestedUrl','selectedUrl','componentUrl'):url(value[field])
    for field in ('creationContextUrl','objectContextUrl'):url(value[field],empty=True)
    need(urlsplit(value['requestedUrl']).path.endswith('/armored-chat/armored_chat.qml'))
    load=object_receipt(value['cacheAtLoad'],pid,component=True)
    current=object_receipt(value['cacheAtRead'],pid,component=False)
    need(identity_fields(load)==identity_fields(current))
    at_load=load['unit'];at_read=current['unit']
    need(value['loadBefore']['epochMs']<=at_load['unitReadBefore']['epochMs']
        and at_load['unitReadAfter']['epochMs']<=value['loadCompleted']['epochMs']
        and epoch<=at_read['unitReadBefore']['epochMs']<=at_read['unitReadAfter']['epochMs']<=read_after_epoch)
    cache.validate(at_read,pid,epoch=read_after_epoch,previous=at_load)
    exact(value['coverage'],{'importGraphAvailable','aotGraphAvailable','installedQtSourceAvailable'})
    need(all(flag is False for flag in value['coverage'].values()))
    load_graph=_dependency_for_cache(value['dependencyAtLoad'],load,pid,True)
    read_graph=_dependency_for_cache(value['dependencyAtRead'],current,pid,False)
    need(value['loadBefore']['epochMs']<=load_graph['before']['epochMs']<=load_graph['after']['epochMs']<=value['loadCompleted']['epochMs']
        and epoch<=read_graph['before']['epochMs']<=read_graph['after']['epochMs']<=read_after_epoch
        and same(dependency_membership(value['dependencyAtLoad']),dependency_membership(value['dependencyAtRead'])))
    need(len(json.dumps(value,ensure_ascii=False,allow_nan=False).encode())<=57344)
    return value
