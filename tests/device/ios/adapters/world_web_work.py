"""Actual original VM callback arguments, nesting, returns and source identity."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import re
from adapters.native_feature_observation import exact,fresh,integer,need
from adapters.native_script_membership import validate as membership
from adapters.native_script_observation import validate_code
from ios.adapters.places_model import IOSPlacesModel,text,tree as json_tree
from ios.adapters.create_state import command as state_command
from ios.adapters.world_web_files import originals

VERSION=1
ACTION='feature-ios-world-web-work'
FILE=ACTION+'.json'
LIMIT=262144


def command(value):
    state_command(dict(value,action='feature-ios-create-state'));need(value['action']==ACTION);return value


def worker(value,epoch,source_sequence):
    exact(value,{'runId','nonce','manager','code','calls','events','ended'})
    need(re.fullmatch('[0-9a-f]{32}',text(value['runId'],32)) and re.fullmatch('[0-9a-f]{32}',text(value['nonce'],32))
        and type(value['ended']) is bool and type(value['calls']) is list and len(value['calls'])<=32
        and type(value['events']) is list and 1<=len(value['events'])<=256)
    manager,code=value['manager'],value['code'];membership(dict(complete=True,revision=1,managers=[manager]),epoch);validate_code(code,epoch)
    need(manager['assigned'] and code['submitted'] and manager['assignedEpochMs']<=code['submittedEpochMs'])
    calls=[];last_seq=last_call=last_caller=0;last_epoch=code['submittedEpochMs'];ended=False;completed=[]
    for index,event in enumerate(value['events']):
        exact(event,{'sequence','event','call','payload','callerSequence','invokedEpochMs','capturedEpochMs'})
        need(integer(event['sequence'],last_seq+1,source_sequence) and integer(event['callerSequence'],last_caller+1)
            and integer(event['invokedEpochMs'],code['submittedEpochMs'],event['capturedEpochMs'])
            and integer(event['capturedEpochMs'],last_epoch,epoch) and integer(event['call'],0,1000000000) and not ended)
        last_seq,last_caller,last_epoch=event['sequence'],event['callerSequence'],event['capturedEpochMs'];kind=event['event'];payload=event['payload']
        need(type(payload) is dict);json_tree(payload)
        if kind=='loaded':
            need(index==0 and event['call']==0);exact(payload,{'entityId'})
            need(payload['entityId'] is None or type(payload['entityId']) is str and re.fullmatch('[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',payload['entityId']))
            continue
        need(index>0 and type(kind) is str and '-' in kind);prefix,phase=kind.rsplit('-',1)
        need(prefix in ('world-event','script-reply','ending') and phase in ('enter','return','finally') and event['call']>0)
        exact(payload,{'entityId'} if prefix=='ending' else {'entityId','message'})
        need(payload['entityId'] is None and prefix=='ending' or type(payload['entityId']) is str and re.fullmatch('[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',payload['entityId']))
        if prefix!='ending':text(payload['message'],4096)
        if phase=='enter':
            need(event['call']>last_call and len(calls)<32);last_call=event['call']
            calls.append(dict(call=event['call'],kind=prefix,payload=deepcopy(payload),returned=False))
        else:
            need(calls and calls[-1]['call']==event['call'] and calls[-1]['kind']==prefix and calls[-1]['payload']==payload)
            if phase=='return':need(not calls[-1]['returned']);calls[-1]['returned']=True
            else:
                current=calls.pop();completed.append(dict(**current,finallySequence=event['sequence']))
                if prefix=='ending':ended=True
    need(calls==value['calls'] and ended==value['ended']);return completed


def validate(value,query,pid,epoch=None,previous=None):
    command(query)
    exact(value,{'iosWorldWebWorkVersion','requestId','runId','instance','sequence','processId','clockDomain','clockBefore','clockAfter','source'})
    need(type(value['iosWorldWebWorkVersion']) is int and value['iosWorldWebWorkVersion']==VERSION
        and value['requestId']==query['commandId'] and value['runId']==query['runId']
        and re.fullmatch('[0-9a-f]{32}',text(value['instance'],32)) and integer(value['sequence'],1)
        and type(value['processId']) is int and value['processId']==pid and integer(pid,1)
        and value['clockDomain']=='native-main-ios-world-web-work')
    before,after=value['clockBefore'],value['clockAfter']
    for clock in (before,after):exact(clock,{'epochMs','monotonicMs'});need(integer(clock['epochMs'],1) and integer(clock['monotonicMs']))
    utc=after['epochMs']-before['epochMs'];mono=after['monotonicMs']-before['monotonicMs'];need(0<=utc<1500 and 0<=mono<1500 and abs(utc-mono)<=250)
    if epoch is not None:fresh(after['epochMs'],epoch)
    source=value['source'];exact(source,{'complete','eventSequence','workers'})
    need(type(source['complete']) is bool and integer(source['eventSequence']) and type(source['workers']) is list and len(source['workers'])<=32)
    keys=set();events=set()
    for row in source['workers']:
        need(row['runId']==query['runId'] and row['nonce'] not in keys);keys.add(row['nonce'])
        worker(row,after['epochMs'],source['eventSequence'])
        for event in row['events']:need(event['sequence'] not in events);events.add(event['sequence'])
    if previous is not None:
        validate(previous,dict(query,commandId=previous['requestId']),pid)
        need(value['instance']==previous['instance'] and value['sequence']>previous['sequence']
            and value['requestId']!=previous['requestId'] and before['epochMs']>=previous['clockAfter']['epochMs']
            and before['monotonicMs']>=previous['clockAfter']['monotonicMs']
            and source['eventSequence']>=previous['source']['eventSequence'] and (previous['source']['complete'] or not source['complete']))
        current={row['nonce']:row for row in source['workers']}
        for old in previous['source']['workers']:
            need(old['nonce'] in current);row=current[old['nonce']]
            need(all(row[key]==old[key] for key in ('runId','nonce','manager','code'))
                and row['events'][:len(old['events'])]==old['events'] and (not old['ended'] or row==old))
    return value


def original(value):
    return validate(value,dict(schemaVersion=1,commandId=value['requestId'],action=ACTION,runId=value['runId']),value['processId'])


def owned_worker(value,ownership,directory,entity_id):
    original(value);need(value['source']['complete'] and ownership['runId']==value['runId'])
    rows=[row for row in value['source']['workers'] if row['nonce']==ownership['nonce']];need(len(rows)==1);row=rows[0]
    raw=originals(ownership['runId'],ownership['fixtureUrl'],ownership['ticket'],ownership['nonce'])['script-bundle/main.js'].decode('utf-8').encode('utf-16le')
    need(row['manager']['url']==directory+'/script-bundle/main.js' and row['code']['encoding']=='utf-16le-code-units'
        and row['code']['codeUnits']==len(raw)//2 and row['code']['sha256']==hashlib.sha256(raw).hexdigest()
        and row['events'][0]['payload']['entityId']==entity_id)
    return deepcopy(row)


class IOSWorldWebWork(IOSPlacesModel):
    _action=ACTION
    _command=staticmethod(command)
    _validate=staticmethod(validate)
    _limit=LIMIT
    _acquisition_key='iosWorldWebWorkAcquisitionVersion'
