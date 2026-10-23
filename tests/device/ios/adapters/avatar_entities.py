"""Original AvatarApp entity returns/deletions, independent of renderer IDs."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import re

from adapters.native_feature_observation import exact,fresh,integer,need
from adapters.native_script_membership import validate as membership
from adapters.native_script_observation import validate_code
from ios.adapters import avatar_scripts,avatar_renderers
from ios.adapters.avatar_state import identity,session,text
from ios.adapters.places_http import installed
from ios.adapters.places_model import IOSPlacesModel
from ios.adapters.scene_inventory import uint64

VERSION=1
ACTION='feature-ios-avatar-entities'
FILE=ACTION+'.json'
LIMIT=262144


def command(value):
    exact(value,{'schemaVersion','commandId','action','runId'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['action']==ACTION
        and type(value['commandId']) is str and re.fullmatch('ios-[a-f0-9]{32}',value['commandId']) and identity(value['runId']))
    return value


def caller(value,epoch):
    exact(value,{'callerVersion','method','sequence','invokedEpochMs','manager','code','callerChain','avatarCode'})
    need(type(value['callerVersion']) is int and value['callerVersion']==1 and value['method'] in ('addEntity','deleteEntity')
        and integer(value['sequence'],1,1000000000) and integer(value['invokedEpochMs'],1,epoch))
    membership(dict(complete=True,revision=1,managers=[value['manager']]),epoch)
    need(value['manager']['assigned']);validate_code(value['code'],epoch);need(value['code']['submitted'])
    chain=value['callerChain'];need(type(chain) is list and 1<=len(chain)<=32)
    for source in chain:text(source,4096)
    installed(chain[0],'/system/avatarapp.js')
    source=value['avatarCode'];exact(source,{'avatarScriptVersion','instance','complete','code'})
    avatar_scripts.code_projection(source,epoch);need(source['complete'])
    entries=[row for row in source['code'] if row['url']==chain[0]];need(entries and all(row['submittedEpochMs']<=value['invokedEpochMs'] for row in entries))
    return value


def validate(value,query,pid,epoch=None,previous=None):
    command(query)
    exact(value,{'iosAvatarEntitiesVersion','requestId','runId','instance','sequence','processId','clockDomain','clockBefore','clockAfter','source'})
    need(type(value['iosAvatarEntitiesVersion']) is int and value['iosAvatarEntitiesVersion']==VERSION
        and value['requestId']==query['commandId'] and value['runId']==query['runId'] and identity(value['instance'])
        and integer(value['sequence'],1,1000000000) and type(value['processId']) is int and value['processId']==pid
        and integer(pid,1) and value['clockDomain']=='native-main-avatar-entities')
    before,after=value['clockBefore'],value['clockAfter']
    for clock in (before,after):exact(clock,{'epochMs','monotonicMs'});need(integer(clock['epochMs'],1) and integer(clock['monotonicMs'],0))
    utc,mono=after['epochMs']-before['epochMs'],after['monotonicMs']-before['monotonicMs']
    need(0<=utc<1500 and 0<=mono<1500 and abs(utc-mono)<=250)
    if epoch is not None:fresh(after['epochMs'],epoch)
    source=value['source'];exact(source,{'avatarEntitiesLedgerVersion','instance','complete','events'})
    need(type(source['avatarEntitiesLedgerVersion']) is int and source['avatarEntitiesLedgerVersion']==1 and identity(source['instance'])
        and type(source['complete']) is bool and type(source['events']) is list and len(source['events'])<=256)
    last_epoch=last_mono=0;ids=set();calls={};created=set();deleted=set()
    for index,event in enumerate(source['events'],1):
        exact(event,{'sequence','eventId','kind','clock','caller','entity'})
        need(type(event['sequence']) is int and event['sequence']==index and identity(event['eventId']) and event['eventId'] not in ids)
        ids.add(event['eventId']);clock=event['clock'];exact(clock,{'epochMs','monotonicMs'})
        need(integer(clock['epochMs'],max(last_epoch,1),after['epochMs']) and integer(clock['monotonicMs'],last_mono))
        if index>1:need(abs((clock['epochMs']-last_epoch)-(clock['monotonicMs']-last_mono))<=250)
        last_epoch,last_mono=clock['epochMs'],clock['monotonicMs']
        who=caller(event['caller'],clock['epochMs']);kind=event['kind'];entity=event['entity']
        need(kind in ('add-returned','deleted-local') and who['method']==('addEntity' if kind=='add-returned' else 'deleteEntity'))
        exact(entity,{'entityId','hostType','modelUrl','parentId','parentJointIndex','owningAvatarId','lastEditedEpochUs','localTreeAvailable'})
        session(entity['entityId']);session(entity['owningAvatarId']);text(entity['modelUrl']);uint64(entity['lastEditedEpochUs'])
        need(entity['hostType']=='avatar' and integer(entity['parentJointIndex'],-1,65535) and type(entity['localTreeAvailable']) is bool)
        need(type(entity['parentId']) is str and re.fullmatch(r'[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}',entity['parentId']))
        if kind=='add-returned':need(entity['entityId'] not in created);created.add(entity['entityId'])
        else:need(entity['entityId'] not in deleted);deleted.add(entity['entityId'])
        key=who['manager']['instance'];prior=calls.get(key)
        if prior:
            old=prior['caller'];need(who['sequence']>=old['sequence'] and who['manager']==old['manager'] and who['code']==old['code']
                and who['avatarCode']['instance']==old['avatarCode']['instance']
                and who['avatarCode']['code'][:len(old['avatarCode']['code'])]==old['avatarCode']['code'])
            if who['sequence']==prior['caller']['sequence']:need(kind==prior['kind']=='deleted-local' and who==prior['caller'])
        calls[key]=event
    need(len(json.dumps(value,allow_nan=False).encode())<=LIMIT)
    if previous:
        validate(previous,dict(query,commandId=previous['requestId']),pid)
        need(value['instance']==previous['instance'] and value['sequence']>previous['sequence'] and value['requestId']!=previous['requestId']
            and value['runId']==previous['runId'] and all(before[key]>=previous['clockAfter'][key] for key in before)
            and source['instance']==previous['source']['instance'] and len(source['events'])>=len(previous['source']['events'])
            and source['events'][:len(previous['source']['events'])]==previous['source']['events']
            and (previous['source']['complete'] or not source['complete']))
    return value


def original(value):
    return validate(value,dict(schemaVersion=1,commandId=value['requestId'],action=ACTION,runId=value['runId']),value['processId'])


def returned(value,before,scripts,expected_code,*,avatar_id,resource,after_epoch):
    """Retain actual original returned ownership before asynchronous geometry."""
    original(value);avatar_renderers.original(before);avatar_scripts.original(scripts)
    session(avatar_id);text(resource);need(resource and integer(after_epoch,1) and value['source']['complete'])
    need(value['processId']==before['processId']==scripts['processId']
        and value['runId']==before['runId']==scripts['runId'] and before['clockAfter']['epochMs']<=after_epoch)
    old={row['id'] for row in before['source']['tree']['entities']}
    candidates=[]
    for event in value['source']['events']:
        entity=event['entity']
        if event['kind']!='add-returned' or event['clock']['epochMs']<after_epoch or entity['modelUrl']!=resource:continue
        need(event['caller']['invokedEpochMs']>=after_epoch)
        need(entity['entityId'] not in old and entity['owningAvatarId'] in (avatar_id,avatar_renderers.SELF)
            and entity['parentId'] in (avatar_id,avatar_renderers.SELF) and entity['localTreeAvailable'])
        who=event['caller'];worker=avatar_scripts.worker(scripts,who['manager']['instance'])
        need(who['manager']==worker['membership'] and who['code']==worker['code']
            and who['avatarCode']['instance']==worker['avatar']['instance']
            and worker['avatar']['code'][:len(who['avatarCode']['code'])]==who['avatarCode']['code'])
        from ios.adapters.avatar_code import for_worker
        expected=for_worker(scripts,who['manager']['instance'],expected_code,required={'/system/avatarapp.js'})
        bound=avatar_scripts.bound_code(scripts,who['manager']['instance'],expected)
        need(any(row in who['avatarCode']['code'] and row['submittedEpochMs']<=who['invokedEpochMs'] for row in bound['/system/avatarapp.js']))
        candidates.append(event)
    need(len(candidates)==1);return deepcopy(candidates[0])


def created(value,before,after,scripts,expected_code,*,avatar_id,resource,after_epoch):
    """Join original returned ownership to independently loaded render facts."""
    event=returned(value,before,scripts,expected_code,avatar_id=avatar_id,resource=resource,after_epoch=after_epoch)
    avatar_renderers.original(after)
    need(after['processId']==value['processId'] and after['runId']==value['runId'] and event['clock']['epochMs']<=after['clockBefore']['epochMs'])
    entity=event['entity']
    # Presence/renderability is another original surface. Creation itself
    # cannot claim downloaded geometry, Hips parenting or an actual draw.
    need(avatar_renderers.wearable(after,entity['entityId'],avatar_id,resource))
    rendered=[row for row in after['source']['avatarEntities'] if row['id']==entity['entityId']];need(len(rendered)==1)
    need(entity['parentJointIndex']==rendered[0]['parentJointIndex'])
    return event


class IOSAvatarEntities(IOSPlacesModel):
    _action=ACTION
    _command=staticmethod(command)
    _validate=staticmethod(validate)
    _acquisition_key='iosAvatarEntitiesAcquisitionVersion'
