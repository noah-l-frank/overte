"""Pure compiler/write/mapping originals, never installed or loaded-root admission.

Version-one direct-unit source remains literal in chat_qml_sources. The new
native cache getter is not exported/transported yet. No live feature or import,
AOT, SDK, process or installed-binary authority follows from this component.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
from adapters.native_feature_observation import exact,fresh,integer,need
from adapters.script_feature.history import same
from ios.adapters.chat_qml_sources import digest,identity,interval,url

DOMAIN='native-qt-steady-clock'
MAX_BYTES=4*1024*1024


def file(value):
    exact(value,{'device','inode','bytes','modifiedSeconds','modifiedNanoseconds','changedSeconds','changedNanoseconds'})
    for field in ('device','inode'):
        need(type(value[field]) is str and re.fullmatch('0|[1-9][0-9]{0,19}',value[field]) and int(value[field])<2**64)
    need(int(value['inode'])>0 and integer(value['bytes'],0,MAX_BYTES))
    for field in ('modifiedSeconds','changedSeconds'):need(integer(value[field],0,10**15))
    for field in ('modifiedNanoseconds','changedNanoseconds'):need(integer(value[field],0,999999999))
    return value


def compiler_prefix(value,pid):
    # Actual internal prefix BEFORE completed direct-unit publication. Do not
    # fabricate unitGeneration/compiledEpochMs to pass the literal v1 reader.
    exact(value,{'qtOverteQmlCompilerInputVersion','instance','sequence','processId','qtVersion','encoding',
        'codeUnits','sha256','requestedUrl','resolvedUrl','sourceBeforeEpochMs','sourceAfterEpochMs',
        'compilerUnitBytes','compilerUnitSha256'})
    need(type(value['qtOverteQmlCompilerInputVersion']) is int and value['qtOverteQmlCompilerInputVersion']==1
        and type(value['processId']) is int and value['processId']==pid
        and value['qtVersion']=='6.11.1' and value['encoding']=='utf16-le-code-units'
        and integer(value['sequence'],1,1000000000) and integer(value['codeUnits'],1,1024*1024)
        and integer(value['compilerUnitBytes'],1,MAX_BYTES))
    identity(value['instance']);digest(value['sha256']);digest(value['compilerUnitSha256'])
    url(value['requestedUrl']);url(value['resolvedUrl'])
    need(integer(value['sourceBeforeEpochMs'],1) and integer(value['sourceAfterEpochMs'],value['sourceBeforeEpochMs']))
    return value


def ordered(before,after):
    # Both clocks were sampled inside native Qt. File mtime/host transfer time
    # never becomes this clock or source/compiler freshness.
    interval(before,after)


def write(value,pid):
    exact(value,{'qtOverteQmlCacheWriteVersion','clockDomain','writerId','processId','compilerOwnerId',
        'compilerOwnerGeneration','compilerInput','writeSequence','writeBefore','writeAfter','bytes',
        'writeArgumentSha256','fileBefore','written','committed','fileCommitted'})
    need(type(value['qtOverteQmlCacheWriteVersion']) is int and value['qtOverteQmlCacheWriteVersion']==1
        and value['clockDomain']==DOMAIN and type(value['processId']) is int and value['processId']==pid
        and integer(value['compilerOwnerGeneration'],0,999999999)
        and integer(value['writeSequence'],1,1000000000) and integer(value['bytes'],1,MAX_BYTES)
        and type(value['written']) is int and value['written']==value['bytes'] and value['committed'] is True)
    identity(value['writerId']);identity(value['compilerOwnerId']);digest(value['writeArgumentSha256'])
    compiler=compiler_prefix(value['compilerInput'],pid);ordered(value['writeBefore'],value['writeAfter'])
    need(compiler['sourceAfterEpochMs']<=value['writeBefore']['epochMs']
        and compiler['compilerUnitBytes']==value['bytes'])
    before=file(value['fileBefore']);after=file(value['fileCommitted'])
    need(before['device']==after['device'] and before['inode']==after['inode'] and after['bytes']==value['bytes'])
    return value


def mapping(value,pid):
    exact(value,{'qtOverteQmlCacheMappingVersion','clockDomain','mappingId','mappingSequence','processId',
        'mapBefore','mapAfter','mappedFile','mappedBytes','mappedSha256','writeOriginal'})
    need(type(value['qtOverteQmlCacheMappingVersion']) is int and value['qtOverteQmlCacheMappingVersion']==1
        and value['clockDomain']==DOMAIN and type(value['processId']) is int and value['processId']==pid
        and integer(value['mappingSequence'],1,1000000000) and integer(value['mappedBytes'],1,MAX_BYTES))
    identity(value['mappingId']);digest(value['mappedSha256']);ordered(value['mapBefore'],value['mapAfter'])
    source=write(value['writeOriginal'],pid);actual=file(value['mappedFile'])
    need(same(actual,source['fileCommitted']) and value['mappedBytes']==source['bytes']
        and value['mappedSha256']==source['writeArgumentSha256'])
    ordered(source['writeAfter'],value['mapBefore']);return value


def validate(value,pid,epoch=None,previous=None):
    exact(value,{'qtOverteQmlCacheUnitVersion','clockDomain','processId','unitOwnerId','unitReadBefore','unitReadAfter',
        'unitGeneration','unitBytes','unitSha256','mappingOriginal'})
    need(integer(pid,1) and type(value['qtOverteQmlCacheUnitVersion']) is int and value['qtOverteQmlCacheUnitVersion']==1
        and value['clockDomain']==DOMAIN and type(value['processId']) is int and value['processId']==pid
        and integer(value['unitGeneration'],0,999999999) and integer(value['unitBytes'],1,MAX_BYTES))
    identity(value['unitOwnerId']);digest(value['unitSha256']);interval(value['unitReadBefore'],value['unitReadAfter'],current=True)
    original=mapping(value['mappingOriginal'],pid)
    need(value['unitBytes']==original['mappedBytes'] and value['unitSha256']==original['mappedSha256'])
    ordered(original['mapAfter'],value['unitReadBefore'])
    if epoch is not None:fresh(value['unitReadAfter']['epochMs'],epoch)
    if previous is not None:
        validate(previous,pid)
        ordered(previous['unitReadAfter'],value['unitReadBefore'])
        if value['unitOwnerId']==previous['unitOwnerId'] and value['unitGeneration']==previous['unitGeneration']:
            need(all(same(value[key],previous[key]) for key in value if key not in ('unitReadBefore','unitReadAfter')))
        elif value['unitOwnerId']==previous['unitOwnerId']:
            need(value['unitGeneration']>previous['unitGeneration'])
    return value


def observed_chain(value,pid):
    """Original component data only; no root, imports or installed Qt verdict."""
    validate(value,pid);return deepcopy(value)
