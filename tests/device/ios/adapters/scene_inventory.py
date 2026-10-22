"""Whole native EntityTree enumeration and opaque editable-wire fingerprints.

Map absence is not renderer/Web/GPU callback retirement. No entity mutation,
expected entity list, partial radius or semantic success enters the query.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import re

from adapters.native_feature_observation import exact,fresh,integer,need
from adapters.native_graphics_subject import entity_id
from adapters.native_scene_loads import validate as scene_packet,continuity as scene_continuity
from adapters.native_scene_loads import committed
from adapters.script_feature.history import same
from ios.adapters.places_model import IOSPlacesModel

VERSION=2
READS=(1,2)
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


def commit_origin(value,pid,epoch):
    exact(value,{'iosSceneCommitOriginVersion','instance','processId','currentGeneration','commits','complete','latest'})
    need(type(value['iosSceneCommitOriginVersion']) is int and value['iosSceneCommitOriginVersion']==1
         and type(value['instance']) is str and re.fullmatch('[0-9a-f]{32}',value['instance'])
         and type(value['processId']) is int and value['processId']==pid
         and integer(value['currentGeneration'],0) and integer(value['commits'],0,128) and type(value['complete']) is bool)
    latest=value['latest']
    if latest is None:need(value['commits']==0);return value
    exact(latest,{'generation','resourceSha256','bodyBytes','bodySha256','clockBefore','clockAfter','tree'})
    need(value['commits']>0 and integer(latest['generation'],value['commits'],value['currentGeneration'])
         and integer(latest['bodyBytes'],1,2**31-1))
    for key in ('resourceSha256','bodySha256'):
        need(type(latest[key]) is str and re.fullmatch('[0-9a-f]{64}',latest[key]))
    before,after=latest['clockBefore'],latest['clockAfter']
    for packet in (before,after):
        exact(packet,{'epochMs','monotonicMs'});need(integer(packet['epochMs'],1) and integer(packet['monotonicMs'],0))
    utc=after['epochMs']-before['epochMs'];mono=after['monotonicMs']-before['monotonicMs']
    need(0<=utc<1500 and 0<=mono<1500 and abs(utc-mono)<=250 and after['epochMs']<=epoch)
    tree(latest['tree']);need(not value['complete'] or latest['tree']['complete'] is True)
    return value


def validate(value,query,pid,epoch=None,previous=None):
    command(query)
    exact(value,{'iosSceneInventoryVersion','requestId','runId','instance','sequence','processId','clockDomain',
                 'clockBefore','clockAfter','source'})
    version=value['iosSceneInventoryVersion']
    need(type(version) is int and version in READS
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
    source=value['source'];exact(source,{'tree','sceneLoads'}|({'commitOrigin'} if version>=2 else set()));tree(source['tree'])
    scene=source['sceneLoads'];scene_packet(scene,dict(query,action='feature-scene-load-observe'),pid,after['epochMs'])
    need(before['epochMs']<=scene['capturedEpochMs']<=after['epochMs']
         and len(json.dumps(value,allow_nan=False,ensure_ascii=False).encode())<=LIMIT)
    if version>=2:
        origin=commit_origin(source['commitOrigin'],pid,before['epochMs'])
        need(origin['currentGeneration']==scene['currentGeneration'])
        if origin['latest'] is not None:
            latest=origin['latest'];need(latest['tree']['treeInstance']==source['tree']['treeInstance'])
        if scene['complete']:
            imported=[row for row in scene['requests'] if row['kind']=='request' and row['phase']=='committed']
            need(origin['commits']==len(imported))
            if imported:
                actual=imported[-1];latest=origin['latest'];need(latest is not None
                    and latest['generation']==actual['generation'] and latest['resourceSha256']==actual['resourceSha256']
                    and latest['bodyBytes']==actual['bytes'])
    if previous is not None:
        validate(previous,dict(query,commandId=previous['requestId']),pid)
        need(version>=previous['iosSceneInventoryVersion'] and value['instance']==previous['instance'] and value['sequence']>previous['sequence']
             and value['requestId']!=previous['requestId'] and value['runId']==previous['runId']
             and before['epochMs']>=previous['clockAfter']['epochMs'] and before['monotonicMs']>=previous['clockAfter']['monotonicMs']
             and abs((before['epochMs']-previous['clockAfter']['epochMs'])-(before['monotonicMs']-previous['clockAfter']['monotonicMs']))<=250
             and source['tree']['treeInstance']==previous['source']['tree']['treeInstance']
             and source['tree']['revisionBefore']>=previous['source']['tree']['revisionAfter'])
        scene_continuity(previous['source']['sceneLoads'],scene,pid)
        if previous['iosSceneInventoryVersion']>=2:
            old,new=previous['source']['commitOrigin'],source['commitOrigin']
            need(new['instance']==old['instance'] and new['commits']>=old['commits']
                 and (old['complete'] or new['complete'] is False))
            if new['commits']==old['commits']:need(same(new['latest'],old['latest']))
            else:
                need(new['latest'] is not None)
                if old['latest'] is not None:
                    first,last=old['latest'],new['latest']
                    need(0<new['commits']-old['commits']<=last['generation']-first['generation']
                         and all(last['clockBefore'][key]>=first['clockAfter'][key] for key in ('epochMs','monotonicMs')))
    return value


def original(value):
    need(type(value) is dict)
    return validate(value,dict(schemaVersion=1,commandId=value.get('requestId'),action=ACTION,runId=value.get('runId')),value.get('processId'))


def tree_semantics(source):
    tree(source);need(source['complete'] is True)
    return {row['id']:dict(hostType=row['hostType'],bytes=row['semanticBytes'],sha256=row['semanticSha256']) for row in source['entities']}


def semantics(value):
    """Only the declared editable-wire profile; original clocks stay separate."""
    original(value);return tree_semantics(value['source']['tree'])


def unchanged_since_commit(value,url):
    """Require the actual committed editable map, before leaving a scene.

    This does not prove resource-byte availability for later restoration,
    renderer/lifetime quiet, camera/physics equality or unowned settings.
    """
    original(value);need(value['iosSceneInventoryVersion']>=2)
    source=value['source'];origin=source['commitOrigin'];latest=origin['latest']
    need(origin['complete'] is True and latest is not None)
    actual=committed(source['sceneLoads'],url)
    need(latest['generation']==source['sceneLoads']['currentGeneration']==actual['generation']
         and latest['resourceSha256']==actual['resourceSha256']
         and latest['bodyBytes']==actual['bytes']
         and actual['startedEpochMs']<=latest['clockBefore']['epochMs']<=latest['clockAfter']['epochMs']<=actual['releasedEpochMs']
         and tree_semantics(latest['tree'])==tree_semantics(source['tree']))
    return deepcopy(latest)


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
