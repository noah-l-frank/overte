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
