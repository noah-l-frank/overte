"""Whole native EntityTree enumeration and opaque editable-wire fingerprints.

Map absence is not renderer/Web/GPU callback retirement. No entity mutation,
expected entity list, partial radius or semantic success enters the query.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import re

from adapters.native_feature_observation import exact,fresh,integer,need
from adapters.native_graphics_subject import entity_id
from adapters.native_scene_loads import validate as scene_packet,continuity as scene_continuity
from ios.adapters.places_model import IOSPlacesModel

VERSION=1
ACTION='feature-ios-scene-inventory'
FILE=ACTION+'.json'
LIMIT=262144
PROFILE='native-entity-edit-wire-v1'


def command(value):
    exact(value,{'schemaVersion','commandId','action','runId'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['action']==ACTION
         and type(value['commandId']) is str and re.fullmatch('ios-[a-f0-9]{32}',value['commandId'])
         and type(value['runId']) is str and re.fullmatch('[a-f0-9]{32}',value['runId']))
    return value


def uint64(value):
    need(type(value) is str and re.fullmatch('0|[1-9][0-9]{0,19}',value) and int(value)<2**64)
    return value


def tree(value):
    exact(value,{'entityInventoryVersion','profile','treeInstance','revisionBefore','revisionAfter','totalEntities','complete','entities'})
    need(type(value['entityInventoryVersion']) is int and value['entityInventoryVersion']==1 and value['profile']==PROFILE
         and type(value['treeInstance']) is str and re.fullmatch('[a-f0-9]{32}',value['treeInstance'])
         and integer(value['revisionBefore'],0) and integer(value['revisionAfter'],value['revisionBefore'])
         and integer(value['totalEntities'],0) and type(value['complete']) is bool
         and type(value['entities']) is list and len(value['entities'])<=min(512,value['totalEntities']))
    ids=[]
    for row in value['entities']:
        exact(row,{'id','hostType','ready','createdEpochUs','lastEditedEpochUs','lastEditedAfterEpochUs','semanticBytes','semanticSha256'})
        need(entity_id(row['id']) and row['hostType'] in ('domain','local','avatar') and type(row['ready']) is bool)
        for key in ('createdEpochUs','lastEditedEpochUs','lastEditedAfterEpochUs'):uint64(row[key])
        if row['ready']:
            need(row['lastEditedEpochUs']==row['lastEditedAfterEpochUs'] and integer(row['semanticBytes'],1,65536)
                 and type(row['semanticSha256']) is str and re.fullmatch('[a-f0-9]{64}',row['semanticSha256']))
        else:need(row['semanticBytes'] is None and row['semanticSha256'] is None)
        ids.append(row['id'])
    need(ids==sorted(ids) and len(set(ids))==len(ids))
    if value['complete']:
        need(value['revisionBefore']==value['revisionAfter']<=1_000_000_000 and value['totalEntities']==len(ids)
             and all(row['ready'] for row in value['entities']))
    return value


def validate(value,query,pid,epoch=None,previous=None):
    command(query)
    exact(value,{'iosSceneInventoryVersion','requestId','runId','instance','sequence','processId','clockDomain',
                 'clockBefore','clockAfter','source'})
    need(type(value['iosSceneInventoryVersion']) is int and value['iosSceneInventoryVersion']==VERSION
         and value['requestId']==query['commandId'] and value['runId']==query['runId']
         and integer(pid,1) and type(value['processId']) is int and value['processId']==pid
         and type(value['instance']) is str and re.fullmatch('[a-f0-9]{32}',value['instance'])
         and integer(value['sequence'],1,1_000_000_000) and value['clockDomain']=='native-main-scene-inventory')
    before,after=value['clockBefore'],value['clockAfter']
    for clock in (before,after):
        exact(clock,{'epochMs','monotonicMs'});need(integer(clock['epochMs'],1) and integer(clock['monotonicMs'],0))
    utc=after['epochMs']-before['epochMs'];mono=after['monotonicMs']-before['monotonicMs']
    need(0<=utc<1500 and 0<=mono<1500 and abs(utc-mono)<=250)
    if epoch is not None:fresh(after['epochMs'],epoch)
    source=value['source'];exact(source,{'tree','sceneLoads'});tree(source['tree'])
    scene=source['sceneLoads'];scene_packet(scene,dict(query,action='feature-scene-load-observe'),pid,after['epochMs'])
    need(before['epochMs']<=scene['capturedEpochMs']<=after['epochMs']
         and len(json.dumps(value,allow_nan=False,ensure_ascii=False).encode())<=LIMIT)
    if previous is not None:
        validate(previous,dict(query,commandId=previous['requestId']),pid)
        need(value['instance']==previous['instance'] and value['sequence']>previous['sequence']
             and value['requestId']!=previous['requestId'] and value['runId']==previous['runId']
             and before['epochMs']>=previous['clockAfter']['epochMs'] and before['monotonicMs']>=previous['clockAfter']['monotonicMs']
             and abs((before['epochMs']-previous['clockAfter']['epochMs'])-(before['monotonicMs']-previous['clockAfter']['monotonicMs']))<=250
             and source['tree']['treeInstance']==previous['source']['tree']['treeInstance']
             and source['tree']['revisionBefore']>=previous['source']['tree']['revisionAfter'])
        scene_continuity(previous['source']['sceneLoads'],scene,pid)
    return value


def original(value):
    need(type(value) is dict)
    return validate(value,dict(schemaVersion=1,commandId=value.get('requestId'),action=ACTION,runId=value.get('runId')),value.get('processId'))


def semantics(value):
    """Only the declared editable-wire profile; original clocks stay separate."""
    original(value);source=value['source']['tree'];need(source['complete'] is True)
    return {row['id']:dict(hostType=row['hostType'],bytes=row['semanticBytes'],sha256=row['semanticSha256']) for row in source['entities']}


def same_entities(before,after):
    """May compare stages after independent binding admission; no freshness."""
    first,last=semantics(before),semantics(after);need(before['runId']==after['runId'])
    return first==last


def absent(value,owned_ids):
    """Only actual whole-map nonmembership, not object/consumer drainage."""
    need(type(owned_ids) in (list,tuple) and bool(owned_ids) and len(set(owned_ids))==len(owned_ids)
         and all(entity_id(value) for value in owned_ids))
    return set(semantics(value)).isdisjoint(owned_ids)


class IOSSceneInventory(IOSPlacesModel):
    _action=ACTION
    _command=staticmethod(command)
    _validate=staticmethod(validate)
    _acquisition_key='iosSceneInventoryAcquisitionVersion'
