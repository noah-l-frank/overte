"""Current actual Model mesh bounds/items, separate from draw pixels/lifetimes.

The dedicated getter enumerates existing models; no wanted entity IDs, bounds,
URL, dimensions or renderer verdict enters its query.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import math
import re
from adapters.native_feature_observation import exact,fresh,integer,need
from ios.adapters import create_state
from ios.adapters.places_model import IOSPlacesModel
from ios.adapters.scene_inventory import tree

VERSION=1
ACTION='feature-ios-assets-model-renderers'
FILE=ACTION+'.json'
LIMIT=262144


def command(value):
    exact(value,{'schemaVersion','commandId','action','runId'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['action']==ACTION
        and type(value['commandId']) is str and re.fullmatch('ios-[a-f0-9]{32}',value['commandId'])
        and type(value['runId']) is str and re.fullmatch('[a-f0-9]{32}',value['runId']));return value


def stamp(value):
    exact(value,{'epochMs','monotonicMs'});need(integer(value['epochMs'],1) and integer(value['monotonicMs'],0));return value


def vector(value):
    need(type(value) is list and len(value)==3 and all(type(item) in (int,float) and math.isfinite(item) and abs(item)<=1e12 for item in value))
    return value


def provenance(value):
    exact(value,{'modelUrl','watcherUrl','geometry'})
    for key in ('modelUrl','watcherUrl'):create_state.text(value[key],4096)
    geometry=value['geometry']
    if geometry is None:return
    exact(geometry,{'readerId','mappingIds'})
    need(type(geometry['readerId']) is str and (geometry['readerId']=='' or re.fullmatch('[a-f0-9]{32}',geometry['readerId']))
        and type(geometry['mappingIds']) is list and len(geometry['mappingIds'])<=8
        and all(type(item) is str and re.fullmatch('[a-f0-9]{32}',item) for item in geometry['mappingIds'])
        and len(set(geometry['mappingIds']))==len(geometry['mappingIds']))


def validate(value,query,pid,epoch=None,previous=None):
    command(query);exact(value,{'iosAssetsModelRenderersVersion','requestId','runId','instance','sequence','processId','clockDomain','clockBefore','clockAfter','source'})
    need(type(value['iosAssetsModelRenderersVersion']) is int and value['iosAssetsModelRenderersVersion']==VERSION
        and value['requestId']==query['commandId'] and value['runId']==query['runId']
        and type(value['processId']) is int and integer(pid,1) and value['processId']==pid
        and type(value['instance']) is str and re.fullmatch('[a-f0-9]{32}',value['instance'])
        and integer(value['sequence'],1) and value['clockDomain']=='native-main-assets-model-renderers')
    before,after=(stamp(value[key]) for key in ('clockBefore','clockAfter'))
    utc=after['epochMs']-before['epochMs'];mono=after['monotonicMs']-before['monotonicMs']
    need(0<=utc<1500 and 0<=mono<1500 and abs(utc-mono)<=250)
    if epoch is not None:fresh(after['epochMs'],epoch)
    source=value['source'];exact(source,{'complete','domainId','localSessionId','tree','models','renderedPixelsAvailable','resourceRetirementAvailable'})
    create_state.uuid(source['domainId']);create_state.uuid(source['localSessionId']);tree(source['tree'])
    need(source['complete'] is True and source['tree']['complete'] and source['renderedPixelsAvailable'] is False and source['resourceRetirementAvailable'] is False
        and type(source['models']) is list and len(source['models'])<=len(source['tree']['entities']))
    members={row['id'] for row in source['tree']['entities']};seen=[];all_items=[]
    for row in source['models']:
        exact(row,{'entityId','present','loaded','addedToScene','renderable','needsFixup','visible','failed','origin','renderItemIds','boundsReady','bounds'})
        need(row['entityId'] in members and row['entityId'] not in seen);seen.append(row['entityId'])
        for key in ('present','loaded','addedToScene','renderable','needsFixup','visible','failed','boundsReady'):need(type(row[key]) is bool)
        ids=row['renderItemIds'];need(type(ids) is list and len(ids)<=4096 and all(integer(item,1,2**32-1) for item in ids) and ids==sorted(set(ids)))
        all_items+=ids
        if row['present']:provenance(row['origin'])
        else:need(row['origin'] is None and not ids and not any(row[key] for key in ('loaded','addedToScene','renderable','needsFixup','visible','failed','boundsReady')))
        if row['boundsReady']:
            need(row['present'] and row['loaded'] and row['addedToScene'] and row['renderable'] and not row['needsFixup'] and ids)
            bounds=row['bounds'];exact(bounds,{'corner','dimensions'});vector(bounds['corner']);size=vector(bounds['dimensions'])
            need(all(item>=0 for item in size) and sum(item>0 for item in size)>=2)
        else:need(row['bounds'] is None)
    need(seen==sorted(seen) and len(all_items)<=4096 and len(set(all_items))==len(all_items))
    if previous is not None:
        validate(previous,dict(query,commandId=previous['requestId']),pid);old=previous['source']
        need(value['instance']==previous['instance'] and value['requestId']!=previous['requestId'] and value['sequence']>previous['sequence']
            and all(before[key]>=previous['clockAfter'][key] for key in before)
            and source['domainId']==old['domainId'] and source['localSessionId']==old['localSessionId']
            and source['tree']['treeInstance']==old['tree']['treeInstance'] and source['tree']['revisionBefore']>=old['tree']['revisionAfter'])
    return value


def original(value):return validate(value,dict(schemaVersion=1,commandId=value.get('requestId'),action=ACTION,runId=value.get('runId')),value.get('processId'))


def model(value,entity_id):
    original(value);rows=[row for row in value['source']['models'] if row['entityId']==entity_id];need(len(rows)==1);row=rows[0]
    need(row['present'] and row['loaded'] and row['addedToScene'] and row['visible'] and row['renderable'] and not row['needsFixup'] and not row['failed'] and row['boundsReady'])
    need(row['origin']['geometry'] is not None and row['origin']['geometry']['readerId'])
    return row


class IOSAssetsModelRenderers(IOSPlacesModel):
    _limit=LIMIT
    _action=ACTION
    _command=staticmethod(command)
    _validate=staticmethod(validate)
    _acquisition_key='iosAssetsModelRenderersAcquisitionVersion'
