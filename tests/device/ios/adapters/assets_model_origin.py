"""Actual parsed-model input and render-geometry lineage, never a render verdict.

The separate source observes existing native download/parser/accept bodies.
Cache, texture and decoder ownership remains explicitly unavailable.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import re
from adapters.native_feature_observation import exact,fresh,integer,need
from adapters.script_feature.history import same
from ios.adapters import create_state
from ios.adapters.places_model import IOSPlacesModel
from ios.adapters.scene_inventory import tree

VERSION=1
ACTION='feature-ios-assets-model-origin'
FILE=ACTION+'.json'
LIMIT=262144
TIMES=('received','readerCreated','runEntered','runReturned','queued','invokeReturned','deliveryEntered','deliveryReturned')
IDENTITY='[a-f0-9]{32}'


def command(value):
    exact(value,{'schemaVersion','commandId','action','runId'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['action']==ACTION
        and type(value['commandId']) is str and re.fullmatch('ios-'+IDENTITY,value['commandId'])
        and type(value['runId']) is str and re.fullmatch(IDENTITY,value['runId']));return value


def identity(value):need(type(value) is str and re.fullmatch(IDENTITY,value));return value


def stamp(value,upper=None):
    exact(value,{'epochMs','monotonicMs'});need(integer(value['epochMs'],1) and integer(value['monotonicMs']))
    if upper is not None:need(all(value[key]<=upper[key] for key in value))
    return value


def ordered(before,after):
    if after is not None:need(before is not None and all(before[key]<=after[key] for key in before))


def history(value,epoch):
    exact(value,{'assetModelOriginHistoryVersion','instance','complete','clock','downloads'})
    need(type(value['assetModelOriginHistoryVersion']) is int and value['assetModelOriginHistoryVersion']==1
        and type(value['complete']) is bool and type(value['downloads']) is list and len(value['downloads'])<=64)
    identity(value['instance']);stamp(value['clock']);need(value['clock']['epochMs']<=epoch);ids=set();total=0
    for row in value['downloads']:
        exact(row,{'id','kind','requestedUrl','effectiveUrl','bytes','sha256','base64','invokeAccepted',
            'resourceAlive','readerKnown','readerAlive','modelKnown','parsedModelAlive'}|set(TIMES))
        identity(row['id']);need(row['id'] not in ids);ids.add(row['id'])
        need(row['kind'] in ('model','mapping') and integer(row['bytes'],0,2**31-1)
            and type(row['sha256']) is str and re.fullmatch('[a-f0-9]{64}',row['sha256']))
        for key in ('requestedUrl','effectiveUrl'):create_state.text(row[key],4096)
        for key in ('resourceAlive','readerKnown','readerAlive','modelKnown','parsedModelAlive'):need(type(row[key]) is bool)
        need(row['readerKnown'] or not row['readerAlive']);need(row['modelKnown'] or not row['parsedModelAlive'])
        for key in TIMES:
            if row[key] is not None:stamp(row[key],value['clock'])
        need(row['received'] is not None)
        for a,b in (('received','readerCreated'),('readerCreated','runEntered'),('runEntered','runReturned'),
            ('runEntered','queued'),('queued','invokeReturned'),('queued','deliveryEntered'),('deliveryEntered','deliveryReturned')):ordered(row[a],row[b])
        need(row['readerKnown']==(row['readerCreated'] is not None) and row['modelKnown']==(row['queued'] is not None)
            and ((row['invokeReturned'] is None and row['invokeAccepted'] is None) or
                 (row['invokeReturned'] is not None and type(row['invokeAccepted']) is bool)))
        if row['kind']=='mapping':need(not row['readerKnown'] and not row['modelKnown'] and all(row[key] is None for key in TIMES[1:]))
        if row['base64'] is None:need(not value['complete'])
        else:
            need(type(row['base64']) is str and len(row['base64'])<=43692);raw=base64.b64decode(row['base64'],validate=True)
            need(0<len(raw)<=32768 and base64.b64encode(raw).decode()==row['base64'] and len(raw)==row['bytes']
                and hashlib.sha256(raw).hexdigest()==row['sha256']);total+=len(raw)
    need(total<=65536);return value


def validate(value,query,pid,epoch=None,previous=None):
    command(query);exact(value,{'iosAssetsModelOriginVersion','requestId','runId','instance','sequence','processId',
        'clockDomain','clockBefore','clockAfter','source'})
    need(type(value['iosAssetsModelOriginVersion']) is int and value['iosAssetsModelOriginVersion']==1
        and value['requestId']==query['commandId'] and value['runId']==query['runId'] and integer(pid,1)
        and type(value['processId']) is int and value['processId']==pid and integer(value['sequence'],1)
        and value['clockDomain']=='native-main-assets-model-origin');identity(value['instance'])
    a,b=value['clockBefore'],value['clockAfter'];stamp(a);stamp(b);ordered(a,b)
    need(b['epochMs']-a['epochMs']<1500 and b['monotonicMs']-a['monotonicMs']<1500
        and abs((b['epochMs']-a['epochMs'])-(b['monotonicMs']-a['monotonicMs']))<=250)
    if epoch is not None:fresh(b['epochMs'],epoch)
    source=value['source'];exact(source,{'complete','domainId','localSessionId','tree','models','history','resourceRetirementAvailable'})
    create_state.uuid(source['domainId']);create_state.uuid(source['localSessionId']);tree(source['tree']);history(source['history'],b['epochMs'])
    need(type(source['complete']) is bool and source['complete']==source['history']['complete'] and source['resourceRetirementAvailable'] is False
        and source['tree']['complete'] and type(source['models']) is list and len(source['models'])<=len(source['tree']['entities']))
    members={row['id'] for row in source['tree']['entities']};seen=set();downloads={row['id']:row for row in source['history']['downloads']}
    for row in source['models']:
        exact(row,{'entityId','present','loaded','addedToScene','failed','origin'})
        need(row['entityId'] in members and row['entityId'] not in seen);seen.add(row['entityId'])
        need(all(type(row[key]) is bool for key in ('present','loaded','addedToScene','failed')))
        if not row['present']:need(not any(row[key] for key in ('loaded','addedToScene','failed')) and row['origin'] is None);continue
        origin=row['origin'];exact(origin,{'modelUrl','watcherUrl','geometry'})
        for key in ('modelUrl','watcherUrl'):create_state.text(origin[key],4096)
        if origin['geometry'] is None:need(not row['loaded']);continue
        geometry=origin['geometry'];exact(geometry,{'readerId','mappingIds'})
        need(type(geometry['readerId']) is str and (geometry['readerId']=='' or geometry['readerId'] in downloads and downloads[geometry['readerId']]['kind']=='model')
            and type(geometry['mappingIds']) is list and len(geometry['mappingIds'])<=8 and len(set(geometry['mappingIds']))==len(geometry['mappingIds']))
        for id_ in geometry['mappingIds']:need(type(id_) is str and id_ in downloads and downloads[id_]['kind']=='mapping')
    if previous is not None:
        validate(previous,dict(query,commandId=previous['requestId']),pid);old=previous['source']
        need(value['instance']==previous['instance'] and value['sequence']>previous['sequence'] and value['requestId']!=previous['requestId']
            and source['domainId']==old['domainId'] and source['localSessionId']==old['localSessionId']
            and source['tree']['treeInstance']==old['tree']['treeInstance'] and (old['complete'] or not source['complete']))
        ordered(previous['clockAfter'],a);before=old['history'];after=source['history']
        need(after['instance']==before['instance'] and len(after['downloads'])>=len(before['downloads']));ordered(before['clock'],after['clock'])
        for first,last in zip(before['downloads'],after['downloads']):
            for key in first:
                if key in ('resourceAlive','readerAlive','parsedModelAlive'):continue
                if key in TIMES or key=='invokeAccepted':need(first[key] is None or same(first[key],last[key]))
                elif key in ('readerKnown','modelKnown'):need(not first[key] or last[key])
                else:need(same(first[key],last[key]))
    return value


def original(value):
    return validate(value,dict(schemaVersion=1,action=ACTION,commandId=value.get('requestId'),runId=value.get('runId')),value.get('processId'))


def parsed_input(value,entity_id):
    """Observe actual parser-to-geometry lineage; no pixel/lifetime verdict."""
    original(value);source=value['source'];need(source['complete'])
    rows=[row for row in source['models'] if row['entityId']==entity_id];need(len(rows)==1);model=rows[0]
    need(model['present'] and model['loaded'] and model['addedToScene'] and not model['failed'])
    geometry=model['origin']['geometry'];need(geometry is not None and geometry['readerId'])
    reader=next(row for row in source['history']['downloads'] if row['id']==geometry['readerId'])
    need(reader['base64'] is not None and all(reader[key] is not None for key in TIMES) and reader['invokeAccepted'] is True)
    return dict(assetModelParsedInputVersion=1,runId=value['runId'],processId=value['processId'],requestId=value['requestId'],
        entityId=entity_id,readerId=reader['id'],modelUrl=model['origin']['modelUrl'],watcherUrl=model['origin']['watcherUrl'],
        requestedUrl=reader['requestedUrl'],effectiveUrl=reader['effectiveUrl'],bytes=reader['bytes'],sha256=reader['sha256'],
        mappingIds=deepcopy(geometry['mappingIds']))


class IOSAssetsModelOrigin(IOSPlacesModel):
    _limit=LIMIT
    _action=ACTION
    _command=staticmethod(command)
    _validate=staticmethod(validate)
    _acquisition_key='iosAssetsModelOriginAcquisitionVersion'
