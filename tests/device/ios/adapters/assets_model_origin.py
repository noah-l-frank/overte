"""Original parser lineage and actual weak Geometry consumer lifetimes.

The source observes existing native download/parser/accept/copy bodies.
Rendered pixels and complete cache/texture/decoder retirement stay separate.
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
HISTORY_VERSION=4
HISTORY_READS=(1,2,3,4)
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
    need(type(value) is dict)
    version=value.get('assetModelOriginHistoryVersion')
    exact(value,{'assetModelOriginHistoryVersion','instance','complete','clock','downloads'}
        |({'geometries'} if type(version) is int and version>=3 else set())
        |({'consumerOwnership'} if type(version) is int and version>=4 else set()))
    need(type(version) is int and version in HISTORY_READS
        and type(value['complete']) is bool and type(value['downloads']) is list and len(value['downloads'])<=64)
    identity(value['instance']);stamp(value['clock']);need(value['clock']['epochMs']<=epoch);ids=set();total=0
    for row in value['downloads']:
        exact(row,{'id','kind','requestedUrl','effectiveUrl','bytes','sha256','base64','invokeAccepted',
            'resourceAlive','readerKnown','readerAlive','modelKnown','parsedModelAlive'}|set(TIMES)|({'resourceObjectAlive'} if version>=2 else set()))
        identity(row['id']);need(row['id'] not in ids);ids.add(row['id'])
        need(row['kind'] in ('model','mapping') and integer(row['bytes'],0,2**31-1)
            and type(row['sha256']) is str and re.fullmatch('[a-f0-9]{64}',row['sha256']))
        for key in ('requestedUrl','effectiveUrl'):create_state.text(row[key],4096)
        for key in ('resourceAlive','readerKnown','readerAlive','modelKnown','parsedModelAlive'):need(type(row[key]) is bool)
        if version>=2:need(type(row['resourceObjectAlive']) is bool)
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
    need(total<=65536)
    if version>=3:geometry_history(value['geometries'],{row['id']:row for row in value['downloads']},value['clock'])
    if version>=4:consumer_ownership(value['consumerOwnership'],value['geometries'],value['clock'])
    return value



def geometry_history(rows,downloads,clock):
    need(type(rows) is list and len(rows)<=128);seen=set()
    for row in rows:
        exact(row,{'id','readerId','mappingIds','kind','born','alive','destructionObserved'})
        identity(row['id']);need(row['id'] not in seen);seen.add(row['id']);identity(row['readerId'])
        reader=downloads.get(row['readerId'])
        need(reader is not None and reader['kind']=='model' and reader['modelKnown']
            and type(row['mappingIds']) is list and len(row['mappingIds'])<=8
            and row['kind'] in ('resource','mapping-resource','copy') and type(row['alive']) is bool)
        mappings=row['mappingIds'];need(all(type(id_) is str for id_ in mappings) and len(set(mappings))==len(mappings))
        for id_ in mappings:need(id_ in downloads and downloads[id_]['kind']=='mapping')
        stamp(row['born'],clock);ordered(reader['queued'],row['born'])
        if row['destructionObserved'] is None:need(row['alive'])
        else:
            need(not row['alive']);stamp(row['destructionObserved'],clock);ordered(row['born'],row['destructionObserved'])
    return rows


def consumer_ownership(value,geometries,clock):
    exact(value,{'assetModelConsumerOwnershipVersion','rows'})
    need(type(value['assetModelConsumerOwnershipVersion']) is int and value['assetModelConsumerOwnershipVersion']==1
        and type(value['rows']) is list and len(value['rows'])<=256)
    parents={row['id']:row for row in geometries};seen=set()
    for row in value['rows']:
        exact(row,{'id','geometryId','kind','slot','born','strongOwnersAlive','ownershipExpiryObserved'})
        identity(row['id']);need(row['id'] not in seen);seen.add(row['id'])
        need(type(row['geometryId']) is str and row['geometryId'] in parents
            and row['kind'] in ('mesh','material') and integer(row['slot'],0,255) and type(row['strongOwnersAlive']) is bool)
        stamp(row['born'],clock);ordered(parents[row['geometryId']]['born'],row['born'])
        if row['ownershipExpiryObserved'] is None:need(row['strongOwnersAlive'])
        else:
            need(not row['strongOwnersAlive']);stamp(row['ownershipExpiryObserved'],clock)
            ordered(row['born'],row['ownershipExpiryObserved'])
    return value


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
        need(after['instance']==before['instance'] and after['assetModelOriginHistoryVersion']>=before['assetModelOriginHistoryVersion']
            and len(after['downloads'])>=len(before['downloads']));ordered(before['clock'],after['clock'])
        for first,last in zip(before['downloads'],after['downloads']):
            for key in first:
                if key in ('resourceAlive','resourceObjectAlive','readerAlive','parsedModelAlive'):continue
                if key in TIMES or key=='invokeAccepted':need(first[key] is None or same(first[key],last[key]))
                elif key in ('readerKnown','modelKnown'):need(not first[key] or last[key])
                else:need(same(first[key],last[key]))
        if before['assetModelOriginHistoryVersion']>=3:
            need(len(after['geometries'])>=len(before['geometries']))
            for first,last in zip(before['geometries'],after['geometries']):
                need(all(same(first[key],last[key]) for key in first if key not in ('alive','destructionObserved'))
                    and (first['alive'] or not last['alive'])
                    and (first['destructionObserved'] is None or same(first['destructionObserved'],last['destructionObserved'])))
        if before['assetModelOriginHistoryVersion']>=4:
            left,right=before['consumerOwnership']['rows'],after['consumerOwnership']['rows']
            need(len(right)>=len(left))
            for first,last in zip(left,right):
                need(all(same(first[key],last[key]) for key in first if key not in ('strongOwnersAlive','ownershipExpiryObserved'))
                    and (first['strongOwnersAlive'] or not last['strongOwnersAlive'])
                    and (first['ownershipExpiryObserved'] is None or same(first['ownershipExpiryObserved'],last['ownershipExpiryObserved'])))
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


def geometry_consumers(value,reader_id):
    """Actual scoped Geometry holders; never texture/cache/GPU retirement."""
    original(value);identity(reader_id);source=value['source'];history_=source['history']
    need(source['complete'] and history_['assetModelOriginHistoryVersion']>=3)
    readers=[row for row in history_['downloads'] if row['id']==reader_id]
    need(len(readers)==1);reader=readers[0]
    need(reader['kind']=='model' and reader['readerKnown'] and reader['modelKnown']
        and reader['base64'] is not None and all(reader[key] is not None for key in TIMES) and reader['invokeAccepted'] is True)
    rows=[row for row in history_['geometries'] if row['readerId']==reader_id];need(rows)
    return dict(assetModelGeometryConsumersVersion=1,runId=value['runId'],processId=value['processId'],requestId=value['requestId'],
        historyInstance=history_['instance'],readerId=reader_id,bodySha256=reader['sha256'],bodyBytes=reader['bytes'],
        nativeEpochMs=value['clockAfter']['epochMs'],geometries=deepcopy(rows),
        readerAlive=reader['readerAlive'],originalLeaseAlive=reader['resourceAlive'],resourceObjectAlive=reader['resourceObjectAlive'],
        hfmAlive=reader['parsedModelAlive'],allKnownGeometryDead=all(not row['alive'] for row in rows),resourceRetirementAvailable=False)


def strong_consumers(value,reader_id):
    """Original mesh/material sharing groups; expiry is not GPU/destructor end."""
    geometry=geometry_consumers(value,reader_id);history_=value['source']['history']
    need(history_['assetModelOriginHistoryVersion']>=4)
    parents={row['id'] for row in geometry['geometries']}
    rows=[row for row in history_['consumerOwnership']['rows'] if row['geometryId'] in parents]
    # No ownership row is not evidence that a rendered model had no mesh.
    need(any(row['kind']=='mesh' for row in rows))
    return dict(assetModelStrongConsumersVersion=1,runId=geometry['runId'],processId=geometry['processId'],
        requestId=geometry['requestId'],historyInstance=geometry['historyInstance'],readerId=reader_id,
        nativeEpochMs=geometry['nativeEpochMs'],bodySha256=geometry['bodySha256'],bodyBytes=geometry['bodyBytes'],consumers=deepcopy(rows),
        allKnownStrongOwnersGone=all(not row['strongOwnersAlive'] for row in rows),
        destructorCompletionAvailable=False,resourceRetirementAvailable=False)


class IOSAssetsModelOrigin(IOSPlacesModel):
    _limit=LIMIT
    _action=ACTION
    _command=staticmethod(command)
    _validate=staticmethod(validate)
    _acquisition_key='iosAssetsModelOriginAcquisitionVersion'
