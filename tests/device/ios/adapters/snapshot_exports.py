"""Original Photos/share callbacks and actual native export weak lifetimes.

These are native application outcomes. A Photos saved-original reader and an
independent share receiver must separately prove the actual destination bytes.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
from adapters.native_feature_observation import exact,fresh,integer,need
from adapters.script_feature.history import same
from ios.adapters.places_model import IOSPlacesModel
from ios.adapters.create_state import command as state_command,uuid

VERSION=1
ACTION='feature-ios-snapshot-exports'
FILE=ACTION+'.json'
LIMIT=262144
CALLBACKS={'qt-delivery','share-dismissed','photos-authorization','photos-authorized-main','photos-changes','photos-completion','share-completion'}
STATES={'current','cancelled','phase','ownerAlive','sheetPresent','sheetPresenting','sheetDismissing','sheetAttached'}
PREFIX=r'parity-[0-9a-f]{16}-(?:still-png|still-jpg|animated|panorama|cubemap)'
FILE_NAME=PREFIX+r'-snap_[0-9]{1,20}_[0-9]{1,10}\.(?:png|jpg|jpeg|webp|gif)'
DETAILS={'created':set(),'photos-authorization-requested':set(),'photos-authorization':{'status'},'main-enqueued':{'name'},
    'photos-commit-enqueued':set(),'photos-placeholder':{'identifier'},'photos-completed':{'success','hasError'},
    'share-created':set(),'share-presentation-requested':set(),'share-completed':{'completed','hasError'},
    'cancel-requested':set(),'delivery-enqueued':{'status','hasError'},'delivery-owner':{'present'},'qt-completed':{'status','hasError'},
    'callback-enter':{'name'},'callback-returned':{'name'}}


def command(value):
    state_command(dict(value,action='feature-ios-create-state'));need(value['action']==ACTION);return value


def stamp(value):
    exact(value,{'epochMs','monotonicMs'});need(integer(value['epochMs'],1) and integer(value['monotonicMs'],0));return value


def history(source):
    exact(source,{'iosSnapshotExportsSourceVersion','instance','bornEpochMs','complete','clock','authorization','operations','events'})
    need(type(source['iosSnapshotExportsSourceVersion']) is int and source['iosSnapshotExportsSourceVersion']==1
        and type(source['instance']) is str and re.fullmatch('[0-9a-f]{32}',source['instance'])
        and type(source['complete']) is bool and integer(source['authorization'],0,4))
    current=stamp(source['clock']);need(integer(source['bornEpochMs'],1,current['epochMs']))
    need(type(source['operations']) is list and len(source['operations'])<=64 and type(source['events']) is list and len(source['events'])<=2048)
    owners={};events={};depth={}
    for row in source['operations']:
        exact(row,{'id','action','fileName','owned','alive','state'});uuid(row['id'])
        need(row['id'] not in owners and row['action'] in ('save','share') and type(row['owned']) is bool and type(row['alive']) is bool)
        need((type(row['fileName']) is str and re.fullmatch(FILE_NAME,row['fileName'])) if row['owned'] else row['fileName']=='')
        if row['alive']:
            exact(row['state'],STATES);state=row['state']
            need(integer(state['phase'],0,4) and all(type(state[key]) is bool for key in STATES-{'phase'})
                and state['current']==(state['phase']!=0) and (state['phase']!=0 or not state['cancelled']))
            need(not any(state[k] for k in ('sheetPresenting','sheetDismissing','sheetAttached')) or state['sheetPresent'])
        else:need(row['state']=={})
        owners[row['id']]=row;events[row['id']]=[];depth[row['id']]={}
    last=dict(epochMs=source['bornEpochMs'],monotonicMs=0)
    for index,event in enumerate(source['events'],1):
        exact(event,{'sequence','operation','kind','clock','detail'});kind=event['kind'];identifier=event['operation']
        need(type(event['sequence']) is int and event['sequence']==index and identifier in owners and kind in DETAILS)
        clock=stamp(event['clock']);need(all(last[k]<=clock[k]<=current[k] for k in last));last=clock
        detail=event['detail'];exact(detail,DETAILS[kind]);prior=events[identifier]
        need((not prior and kind=='created') or (prior and kind!='created'))
        for key in ('success','hasError','completed','present'):
            if key in detail:need(type(detail[key]) is bool)
        if 'status' in detail:
            if kind=='photos-authorization':need(integer(detail['status'],0,4))
            else:need(detail['status'] in ('success','error','cancelled'))
        if kind=='photos-placeholder':
            need(owners[identifier]['action']=='save' and type(detail['identifier']) is str
                and len(detail['identifier'])<=4096 and all(ord(c)>=32 and ord(c)!=127 for c in detail['identifier']))
            need(owners[identifier]['owned'] or detail['identifier']=='')
        if 'name' in detail:need(detail['name'] in CALLBACKS)
        if kind.startswith('callback-'):
            name=detail['name'];old=depth[identifier].get(name,0)
            need(old==0 if kind=='callback-enter' else old==1);depth[identifier][name]=old+(1 if kind=='callback-enter' else -1)
        if kind.startswith('photos-'):need(owners[identifier]['action']=='save')
        if kind.startswith('share-'):need(owners[identifier]['action']=='share')
        kinds=[row['kind'] for row in prior]
        if kind=='photos-authorization':
            need('photos-authorization-requested' in kinds and depth[identifier].get('photos-authorization')==1)
        if kind=='photos-commit-enqueued':
            need(depth[identifier].get('photos-authorized-main')==1
                and any(row['kind']=='photos-authorization' and row['detail']['status'] in (3,4) for row in prior))
        if kind=='photos-placeholder':need('photos-commit-enqueued' in kinds and depth[identifier].get('photos-changes')==1)
        if kind=='photos-completed':need('photos-commit-enqueued' in kinds and depth[identifier].get('photos-completion')==1)
        if kind=='share-completed':need('share-created' in kinds and depth[identifier].get('share-completion')==1)
        if kind=='share-presentation-requested':need('share-created' in kinds)
        if kind=='delivery-enqueued':need('delivery-enqueued' not in kinds)
        if kind in ('delivery-owner','qt-completed'):
            need('delivery-enqueued' in kinds and depth[identifier].get('qt-delivery')==1)
        if kind=='qt-completed':
            enqueued=[row for row in prior if row['kind']=='delivery-enqueued'];need(len(enqueued)==1
                and same(enqueued[0]['detail'],detail) and any(row['kind']=='delivery-owner' and row['detail']['present'] for row in prior)
                and 'qt-completed' not in kinds)
        prior.append(event)
    for identifier,owner in owners.items():
        need(events[identifier])
        if not owner['alive']:need(all(value==0 for value in depth[identifier].values()))
    return owners,events,depth


def validate(value,query,pid,epoch=None,previous=None):
    command(query);exact(value,{'iosSnapshotExportsVersion','requestId','runId','instance','sequence','processId','clockDomain','clockBefore','clockAfter','source'})
    need(type(value['iosSnapshotExportsVersion']) is int and value['iosSnapshotExportsVersion']==1 and value['requestId']==query['commandId']
        and value['runId']==query['runId'] and type(value['processId']) is int and value['processId']==pid and integer(pid,1)
        and type(value['instance']) is str and re.fullmatch('[0-9a-f]{32}',value['instance']) and integer(value['sequence'],1)
        and value['clockDomain']=='native-main-snapshot-exports')
    a,b=stamp(value['clockBefore']),stamp(value['clockAfter']);s=value['source'];history(s)
    need(all(a[k]<=b[k]<a[k]+1500 for k in a) and abs(b['epochMs']-a['epochMs']-(b['monotonicMs']-a['monotonicMs']))<=250
        and a['epochMs']<=s['clock']['epochMs']<=b['epochMs'])
    if epoch is not None:fresh(b['epochMs'],epoch)
    if previous is not None:
        validate(previous,dict(query,commandId=previous['requestId']),pid)
        old=previous['source'];need(value['instance']==previous['instance'] and value['requestId']!=previous['requestId']
            and value['sequence']>previous['sequence'] and all(a[k]>=previous['clockAfter'][k] for k in a)
            and s['instance']==old['instance'] and s['bornEpochMs']==old['bornEpochMs']
            and all(s['clock'][k]>=old['clock'][k] for k in a) and (old['complete'] or not s['complete'])
            and len(s['events'])>=len(old['events']) and same(s['events'][:len(old['events'])],old['events']))
        owners={row['id']:row for row in s['operations']}
        for row in old['operations']:
            need(row['id'] in owners);new=owners[row['id']]
            need(all(same(row[k],new[k]) for k in ('id','action','fileName','owned')) and (row['alive'] or not new['alive']))
    return value


def original(value):return validate(value,dict(schemaVersion=1,commandId=value['requestId'],action=ACTION,runId=value['runId']),value['processId'])


def outcome(value,identifier):
    original(value);need(value['source']['complete']);owners,events,depth=history(value['source']);need(identifier in owners)
    owner=owners[identifier];need(owner['owned'] and owner['fileName'].startswith('parity-'+value['runId'][:16]+'-'));rows=events[identifier]
    done=[row for row in rows if row['kind']=='qt-completed'];need(len(done)==1)
    need(all(count==0 for count in depth[identifier].values()))
    return dict(operation=deepcopy(owner),nativeResult=deepcopy(done[0]),destinationOriginalRequired=True)


def drained(value):
    original(value);need(value['source']['complete']);owners,events,depth=history(value['source'])
    need(all(not row['alive'] for row in owners.values()) and all(not any(item.values()) for item in depth.values())
        and all(any(row['kind']=='delivery-enqueued' for row in rows) for rows in events.values()))
    return dict(iosSnapshotExportsDrainVersion=1,sourceInstance=value['source']['instance'],observedClock=deepcopy(value['source']['clock']),operations=sorted(owners))


def photos_asset(value,identifier):
    result=outcome(value,identifier);need(result['operation']['action']=='save'
        and result['nativeResult']['detail']==dict(status='success',hasError=False))
    _owners,events,_depth=history(value['source']);rows=events[identifier]
    placeholders=[row for row in rows if row['kind']=='photos-placeholder']
    completed=[row for row in rows if row['kind']=='photos-completed']
    need(len(placeholders)==len(completed)==1 and placeholders[0]['detail']['identifier']
        and completed[0]['detail']==dict(success=True,hasError=False))
    return dict(result,photosIdentifier=placeholders[0]['detail']['identifier'])


class IOSSnapshotExports(IOSPlacesModel):
    _action=ACTION
    _command=staticmethod(command)
    _validate=staticmethod(validate)
    _acquisition_key='iosSnapshotExportsAcquisitionVersion'
    _limit=LIMIT
