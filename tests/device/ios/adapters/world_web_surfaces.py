"""Actual cache/root/renderer-lease ownership; cached is never destroyed.

Every identity originates at the native cache operand or native renderer
acquisition. This read source owns no resource and performs no cache operation.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import re
import json
from adapters.native_feature_observation import exact,fresh,integer,need
from ios.adapters.create_state import command as state_command
from ios.adapters.places_model import IOSPlacesModel,text
from ios.adapters.world_web_snapshot import bracket

VERSION=1
ACTION='feature-ios-world-web-surfaces'
FILE=ACTION+'.json'
LIMIT=262144
SOURCE_LIMIT=240000
HEX='[0-9a-f]{32}'


def command(value):
    state_command(dict(value,action='feature-ios-create-state'));need(value['action']==ACTION);return value


def birth(value):need(type(value) is str and re.fullmatch(HEX,value));return value


def source(value,pid,epoch,previous=None):
    need(len(json.dumps(value,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode('utf-8'))<=SOURCE_LIMIT)
    exact(value,{'iosWebSurfaceOwnershipVersion','instance','sequence','processId','capturedEpochMs','monotonicMs','complete',
        'eventSequence','events','surfaces','leases'})
    need(type(value['iosWebSurfaceOwnershipVersion']) is int and value['iosWebSurfaceOwnershipVersion']==1
        and integer(value['sequence'],1,1000000000) and type(value['processId']) is int and value['processId']==pid
        and integer(value['capturedEpochMs'],1,epoch) and integer(value['monotonicMs']) and value['complete'] is True)
    birth(value['instance']);need(type(value['surfaces']) is list and len(value['surfaces'])<=512
        and type(value['leases']) is list and len(value['leases'])<=2048 and type(value['events']) is list
        and integer(value['eventSequence'],0,8192) and len(value['events'])==value['eventSequence'])
    surfaces={};leases={}
    for row in value['surfaces']:
        exact(row,{'birth','rootSource','cached','surfaceAlive','rootBirth','rootAlive'});birth(row['birth']);text(row['rootSource'],4096)
        need(row['birth'] not in surfaces and row['rootSource'] and all(type(row[key]) is bool for key in ('cached','surfaceAlive','rootAlive'))
            and (row['rootBirth']=='' or birth(row['rootBirth'])) and (not row['rootAlive'] or row['rootBirth'])
            and (not row['cached'] or row['surfaceAlive']))
        surfaces[row['birth']]=row
    for row in value['leases']:
        exact(row,{'birth','surfaceBirth','entityId','sourceUrl','alive'});birth(row['birth']);text(row['sourceUrl'],131072)
        need(row['birth'] not in leases and row['surfaceBirth'] in surfaces and type(row['alive']) is bool
            and type(row['entityId']) is str and re.fullmatch('[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',row['entityId'])
            and row['entityId']!='00000000-0000-0000-0000-000000000000' and row['sourceUrl'])
        leases[row['birth']]=row
    phases={};roots={};seen_leases=set();last_epoch=last_mono=0
    for index,event in enumerate(value['events'],1):
        exact(event,{'sequence','kind','surfaceBirth','rootBirth','leaseBirth','epochMs','monotonicMs'})
        need(type(event['sequence']) is int and event['sequence']==index and event['surfaceBirth'] in surfaces
            and integer(event['epochMs'],max(1,last_epoch),value['capturedEpochMs'])
            and integer(event['monotonicMs'],last_mono,value['monotonicMs']))
        last_epoch,last_mono=event['epochMs'],event['monotonicMs'];key=event['surfaceBirth'];kind=event['kind']
        if kind=='built':
            need(key not in phases and event['rootBirth']==event['leaseBirth']=='');phases[key]='built'
        else:
            need(key in phases)
            if kind=='root-created':
                need(key not in roots and event['rootBirth']==surfaces[key]['rootBirth'] and event['rootBirth'] and event['leaseBirth']=='')
                roots[key]=event['rootBirth']
            else:
                need(event['rootBirth']==roots.get(key,''))
                if kind=='reserved':need(phases[key]=='built' and event['leaseBirth']=='');phases[key]='cached'
                elif kind=='acquired':need(phases[key]=='cached' and event['leaseBirth']=='');phases[key]='acquired'
                elif kind=='released':need(phases[key]=='acquired' and event['leaseBirth']=='');phases[key]='cached'
                else:
                    need(kind=='renderer-acquired' and phases[key]=='acquired' and event['leaseBirth'] in leases and event['leaseBirth'] not in seen_leases
                        and leases[event['leaseBirth']]['surfaceBirth']==key);seen_leases.add(event['leaseBirth'])
    need(set(phases)==set(surfaces) and seen_leases==set(leases))
    for key,row in surfaces.items():need(row['cached']==(phases[key]=='cached') and row['rootBirth']==roots.get(key,''))
    if previous is not None:
        source(previous,pid,previous['capturedEpochMs']);need(value['instance']==previous['instance'] and value['sequence']>previous['sequence']
            and value['capturedEpochMs']>=previous['capturedEpochMs'] and value['monotonicMs']>=previous['monotonicMs']
            and value['events'][:previous['eventSequence']]==previous['events'] and value['eventSequence']>=previous['eventSequence'])
        for name,immutable,alive in (('surfaces',('birth','rootSource'),('surfaceAlive','rootAlive')),('leases',('birth','surfaceBirth','entityId','sourceUrl'),('alive',))):
            old=previous[name];new=value[name];need(len(new)>=len(old))
            for before,after in zip(old,new):
                need(all(before[field]==after[field] for field in immutable)
                    and all(before[field] or not after[field] for field in alive))
                if name=='surfaces' and before['rootBirth']:need(before['rootBirth']==after['rootBirth'])
    return value


def validate(value,query,pid,epoch=None,previous=None):
    command(query);exact(value,{'iosWorldWebSurfacesVersion','requestId','runId','instance','sequence','processId','clockDomain','clockBefore','clockAfter','source'})
    need(type(value['iosWorldWebSurfacesVersion']) is int and value['iosWorldWebSurfacesVersion']==VERSION
        and value['requestId']==query['commandId'] and value['runId']==query['runId'] and integer(value['sequence'],1)
        and type(value['processId']) is int and value['processId']==pid and integer(pid,1)
        and value['clockDomain']=='native-main-ios-world-web-surfaces');birth(value['instance'])
    bracket(value['clockBefore'],value['clockAfter'])
    if epoch is not None:fresh(value['clockAfter']['epochMs'],epoch)
    source(value['source'],pid,value['clockAfter']['epochMs'],None if previous is None else previous['source'])
    need(value['clockBefore']['epochMs']<=value['source']['capturedEpochMs']<=value['clockAfter']['epochMs'])
    if previous is not None:
        validate(previous,dict(query,commandId=previous['requestId']),pid)
        need(value['instance']==previous['instance'] and value['sequence']>previous['sequence']
            and value['clockBefore']['epochMs']>=previous['clockAfter']['epochMs']
            and value['clockBefore']['monotonicMs']>=previous['clockAfter']['monotonicMs'])
    return value


class IOSWorldWebSurfaces(IOSPlacesModel):
    _action=ACTION
    _command=staticmethod(command)
    _validate=staticmethod(validate)
    _limit=LIMIT
    _acquisition_key='iosWorldWebSurfacesAcquisitionVersion'
