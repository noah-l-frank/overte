"""Original AssetServer task/run/callback/weak-holder observations.

No callback or sticky product isBaking flag supplies completion. These parsers
perform no transport, process control, time acquisition or product mutation.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
import uuid
from adapters.native_feature_observation import exact,integer,need
from adapters.script_feature.history import same

VERSION=1
INPUTS={'hash','path','senderId','messageId'}


def identity(value):
    need(type(value) is str)
    try:parsed=uuid.UUID(value)
    except (ValueError,AttributeError):need(False)
    need(parsed.int!=0 and str(parsed)==value);return value


def clock(value):
    exact(value,{'epochMs','monotonicMs'});need(integer(value['epochMs'],1) and integer(value['monotonicMs']));return value


def after(value,previous):
    clock(value);clock(previous);need(all(value[key]>=previous[key] for key in value));return value


def inputs(value,kind):
    exact(value,INPUTS);need(all(type(item) is str and len(item)<=4096 and not any(ord(c)<32 or ord(c)==127 for c in item) for item in value.values()))
    need(re.fullmatch('[a-f0-9]{0,64}',value['hash']) is not None and len(value['hash']) in (0,64))
    if value['senderId']:identity(value['senderId'])
    if value['messageId']:need(re.fullmatch('0|[1-9][0-9]{0,9}',value['messageId']) is not None and int(value['messageId'])<2**32)
    if kind=='bake':need(len(value['hash'])==64 and value['path'].startswith('/') and not value['path'].endswith('/') and not value['senderId'] and not value['messageId'])
    else:need(not value['path'])
    return value


def job(value,captured):
    exact(value,{'id','kind','inputs','created','leaseAlive','leaseExpired','ownerKnown','ownerAlive','ownerExpired','objectAlive','objectExpired',
        'runEntered','runReturned','callbackEntered','callbackReturned','pendingRuns','pendingBodies','events'})
    identity(value['id']);kind=value['kind'];need(kind in ('bake','send','upload'));inputs(value['inputs'],kind);clock(value['created']);after(captured,value['created'])
    need(type(value['leaseAlive']) is type(value['ownerKnown']) is bool and type(value['events']) is list and 1<=len(value['events'])<=128)
    for key in ('runEntered','runReturned','callbackEntered','callbackReturned','pendingRuns','pendingBodies'):need(integer(value[key],0,128))
    need(value['runEntered']<=1 and value['runReturned']<=value['runEntered'] and value['callbackReturned']<=value['callbackEntered'])
    counters=dict(runEntered=0,runReturned=0,callbackEntered=0,callbackReturned=0);runs=[];callbacks=[];bodies=set();ids=set();previous=value['created'];original=None;bound=False;expired={}
    for index,event in enumerate(value['events'],1):
        exact(event,{'sequence','eventId','kind','clock','details'});need(type(event['sequence']) is int and event['sequence']==index)
        identity(event['eventId']);need(event['eventId'] not in ids);ids.add(event['eventId']);after(event['clock'],previous);after(captured,event['clock']);previous=event['clock']
        tag,details=event['kind'],event['details']
        if tag=='queued':
            need(index==1);exact(details,{'inputs'});original=deepcopy(inputs(details['inputs'],kind))
        elif tag=='owner-bound':
            exact(details,set());need(kind=='bake' and not bound and not expired);bound=True
        elif tag=='input-observed':
            exact(details,{'field','value'});field=details['field'];need(field in INPUTS and 'lease' not in expired
                and type(details['value']) is str and (not original[field] or original[field]==details['value']))
            original[field]=details['value'];inputs(original,kind)
        elif tag in ('run-enter','callback-enter'):
            exact(details,{'bodyId','callback'});identity(details['bodyId']);need(details['bodyId'] not in bodies and 'lease' not in expired);bodies.add(details['bodyId'])
            callback=tag=='callback-enter'
            if callback:need(kind=='bake' and details['callback'] in ('bake-complete','bake-failed','bake-aborted'));callbacks.append((details['bodyId'],details['callback']));counters['callbackEntered']+=1
            else:need(details['callback']=='run' and counters['runEntered']==0);runs.append((details['bodyId'],'run'));counters['runEntered']+=1
        elif tag in ('run-return','callback-return'):
            exact(details,{'bodyId','callback'});callback=tag=='callback-return';stack=callbacks if callback else runs
            need(stack and stack.pop()==(details['bodyId'],details['callback']));counters['callbackReturned' if callback else 'runReturned']+=1
        elif tag in ('lease-expired-observed','owner-expired-observed','object-expired-observed'):
            exact(details,set());which=tag.split('-',1)[0];need(which not in expired and (which=='lease' or kind=='bake') and (which!='owner' or bound));expired[which]=event['clock']
        else:need(False)
        need(original is not None)
    need(same(original,value['inputs']) and bound==value['ownerKnown'] and all(counters[key]==value[key] for key in counters)
        and value['pendingRuns']==len(runs) and value['pendingBodies']==len(callbacks))
    for which in ('lease','owner','object'):
        alive=value[which+'Alive'];actual=value[which+'Expired'];present=which=='lease' or kind=='bake' and (which=='object' or bound)
        if not present:need(alive is None and actual is None and which not in expired);continue
        need(type(alive) is bool and (actual is None)==alive)
        if alive:need(which not in expired)
        else:
            need(which in expired);after(actual,value['created']);after(expired[which],actual);after(captured,actual)
    return value


def validate(value,*,pid=None):
    exact(value,{'assetBackendWorkVersion','instance','sequence','processId','clock','available','complete','jobs','pendingBakes',
        'transferActiveThreads','bakeActiveThreads','queuedRequests','queueingRequests'})
    need(type(value['assetBackendWorkVersion']) is int and value['assetBackendWorkVersion']==VERSION and integer(value['sequence'],1)
        and integer(value['processId'],1) and (pid is None or value['processId']==pid) and type(value['available']) is type(value['complete']) is bool
        and type(value['jobs']) is list and len(value['jobs'])<=512 and type(value['pendingBakes']) is list and len(value['pendingBakes'])<=512
        and type(value['queueingRequests']) is bool)
    identity(value['instance']);clock(value['clock'])
    for key in ('transferActiveThreads','bakeActiveThreads','queuedRequests'):need(integer(value[key],0,1000000))
    jobs={}
    for row in value['jobs']:
        job(row,value['clock']);need(row['id'] not in jobs);jobs[row['id']]=row
        if value['complete'] and row['kind']=='bake':need(row['ownerKnown'])
    pending=set()
    for item in value['pendingBakes']:
        exact(item,{'id','hash'});identity(item['id']);need(item['id'] not in pending and item['id'] in jobs);pending.add(item['id'])
        need(jobs[item['id']]['kind']=='bake' and jobs[item['id']]['inputs']['hash']==item['hash'])
    return value


def accept(previous,value):
    validate(value)
    if previous is None:return deepcopy(value)
    validate(previous);need(all(value[key]==previous[key] for key in ('instance','processId')) and value['sequence']>previous['sequence']);after(value['clock'],previous['clock'])
    need(len(value['jobs'])>=len(previous['jobs']))
    for old,new in zip(previous['jobs'],value['jobs']):
        need(all(same(old[key],new[key]) for key in ('id','kind','created')) and same(old['events'],new['events'][:len(old['events'])]))
        for which in ('lease','owner','object'):
            if old[which+'Alive'] is False:need(new[which+'Alive'] is False and same(old[which+'Expired'],new[which+'Expired']))
    return deepcopy(value)


def drained(value):
    validate(value)
    return (value['available'] and value['complete'] and not value['pendingBakes'] and not value['transferActiveThreads'] and not value['bakeActiveThreads']
        and not value['queuedRequests'] and not value['queueingRequests'] and all(not row['leaseAlive'] and row['pendingRuns']==row['pendingBodies']==0
            and row['runEntered']==row['runReturned']==1 and row['callbackEntered']==row['callbackReturned']
            and (row['kind']!='bake' or row['callbackEntered']>0 and row['ownerKnown'] and row['ownerAlive'] is False and row['objectAlive'] is False) for row in value['jobs']))
