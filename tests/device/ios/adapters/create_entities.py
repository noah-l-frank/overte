"""Actual API-return UUIDs, real Tree births/removals and weak EntityItem death.

A delete return is only an original operand. It proves neither removal nor
lifetime drainage. Ownership requires the separate actual returned add UUID,
VM code/manager and the successful native Tree insertion of that same UUID.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import re

from adapters.native_feature_observation import exact,fresh,integer,need
from adapters.native_script_membership import validate as membership
from adapters.native_script_observation import validate_code
from adapters.script_feature.history import same
from ios.adapters.places_model import IOSPlacesModel

VERSION=1
ACTION='feature-ios-create-entities'
FILE=ACTION+'.json'
LIMIT=1048576


def nonce(value):
    need(type(value) is str and re.fullmatch(r'[a-f0-9]{32}',value));return value


def entity_id(value):return type(value) is str and re.fullmatch(r'[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}',value) and value!='00000000-0000-0000-0000-000000000000'


def command(value):
    exact(value,{'schemaVersion','commandId','action','runId'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['action']==ACTION
        and type(value['commandId']) is str and re.fullmatch(r'ios-[a-f0-9]{32}',value['commandId']))
    nonce(value['runId']);return value


def calls(value,epoch):
    exact(value,{'createEntityCallsVersion','instance','complete','events'})
    need(type(value['createEntityCallsVersion']) is int and value['createEntityCallsVersion']==1 and type(value['complete']) is bool
        and type(value['events']) is list and len(value['events'])<=512);nonce(value['instance'])
    ids=set();managers={};last_epoch=last_mono=0
    for sequence,event in enumerate(value['events'],1):
        exact(event,{'sequence','eventId','kind','clock','caller','entityId','localTreeAvailable'})
        need(type(event['sequence']) is int and event['sequence']==sequence and event['kind'] in ('add-returned','delete-returned')
            and type(event['localTreeAvailable']) is bool and (event['entityId'] is None or entity_id(event['entityId'])))
        nonce(event['eventId']);need(event['eventId'] not in ids);ids.add(event['eventId'])
        clock=event['clock'];exact(clock,{'epochMs','monotonicMs'})
        need(integer(clock['epochMs'],max(1,last_epoch),epoch) and integer(clock['monotonicMs'],last_mono))
        if sequence>1:need(abs(clock['epochMs']-last_epoch-clock['monotonicMs']+last_mono)<=250)
        last_epoch,last_mono=clock['epochMs'],clock['monotonicMs']
        caller=event['caller'];exact(caller,{'callerVersion','method','sequence','invokedEpochMs','manager','code'})
        need(type(caller['callerVersion']) is int and caller['callerVersion']==1 and caller['method']==('addEntity' if event['kind']=='add-returned' else 'deleteEntity')
            and integer(caller['sequence'],1,1000000000) and integer(caller['invokedEpochMs'],1,clock['epochMs']))
        manager,code=caller['manager'],caller['code'];membership(dict(complete=True,revision=1,managers=[manager]),clock['epochMs']);validate_code(code,clock['epochMs'])
        need(manager['assigned'] and code['submitted'] and manager['assignedEpochMs']<=code['submittedEpochMs']<=caller['invokedEpochMs'])
        old=managers.get(manager['instance'])
        if old is not None:need(same(old['manager'],manager) and same(old['code'],code) and old['sequence']<caller['sequence'])
        managers[manager['instance']]=caller
    return value


def lifetimes(value,epoch):
    exact(value,{'entityTreeLifetimesVersion','treeInstance','treeBornEpochMs','complete','eventSequence','observedEpochMs','observedMonotonicMs','events','entities'})
    need(type(value['entityTreeLifetimesVersion']) is int and value['entityTreeLifetimesVersion']==1 and type(value['complete']) is bool
        and integer(value['treeBornEpochMs'],1,epoch) and integer(value['observedEpochMs'],value['treeBornEpochMs'],epoch)
        and integer(value['observedMonotonicMs'],0) and integer(value['eventSequence'],0,1024)
        and type(value['events']) is list and len(value['events'])==value['eventSequence'] and type(value['entities']) is list and len(value['entities'])<=512)
    nonce(value['treeInstance']);born={};removed={};last_epoch=value['treeBornEpochMs'];last_mono=0
    for index,event in enumerate(value['events'],1):
        exact(event,{'sequence','kind','id','birth','epochMs','monotonicMs'});nonce(event['birth'])
        need(type(event['sequence']) is int and event['sequence']==index and event['kind'] in ('inserted','removed') and entity_id(event['id'])
            and integer(event['epochMs'],last_epoch,value['observedEpochMs']) and integer(event['monotonicMs'],last_mono,value['observedMonotonicMs']))
        if index>1:need(abs(event['epochMs']-last_epoch-event['monotonicMs']+last_mono)<=250)
        last_epoch,last_mono=event['epochMs'],event['monotonicMs']
        if event['kind']=='inserted':need(event['birth'] not in born);born[event['birth']]=event
        else:
            need(event['birth'] in born and event['birth'] not in removed and born[event['birth']]['id']==event['id']);removed[event['birth']]=event
    need(len(value['entities'])==len(born));seen=set();live_ids=set();previous_inserted=0
    for row in value['entities']:
        exact(row,{'id','birth','insertedSequence','bornEpochMs','bornMonotonicMs','removedSequence','removedEpochMs','removedMonotonicMs',
            'destroyed','destructionObservedEpochMs','destructionObservedMonotonicMs'})
        need(row['birth'] not in seen and row['birth'] in born and type(row['destroyed']) is bool);seen.add(row['birth']);event=born[row['birth']]
        need(row['id']==event['id'] and row['insertedSequence']==event['sequence'] and row['bornEpochMs']==event['epochMs'] and row['bornMonotonicMs']==event['monotonicMs']
            and row['insertedSequence']>previous_inserted);previous_inserted=row['insertedSequence']
        if row['birth'] in removed:
            event=removed[row['birth']];need(row['removedSequence']==event['sequence'] and row['removedEpochMs']==event['epochMs'] and row['removedMonotonicMs']==event['monotonicMs'])
        else:
            need(row['removedSequence']==row['removedEpochMs']==row['removedMonotonicMs']==0 and row['id'] not in live_ids);live_ids.add(row['id'])
        if row['destroyed']:
            need(row['removedSequence']>0 and integer(row['destructionObservedEpochMs'],row['removedEpochMs'],value['observedEpochMs'])
                and integer(row['destructionObservedMonotonicMs'],row['removedMonotonicMs'],value['observedMonotonicMs']))
        else:need(row['destructionObservedEpochMs']==row['destructionObservedMonotonicMs']==0)
    return value


def validate(value,query,pid,epoch=None,previous=None):
    command(query);exact(value,{'iosCreateEntitiesVersion','requestId','runId','instance','sequence','processId','clockDomain','clockBefore','clockAfter','source'})
    need(type(value['iosCreateEntitiesVersion']) is int and value['iosCreateEntitiesVersion']==1 and value['requestId']==query['commandId'] and value['runId']==query['runId']
        and type(value['processId']) is int and value['processId']==pid and integer(pid,1) and integer(value['sequence'],1,1000000000)
        and value['clockDomain']=='native-main-create-entities');nonce(value['instance'])
    before,after=value['clockBefore'],value['clockAfter']
    for clock in (before,after):exact(clock,{'epochMs','monotonicMs'});need(integer(clock['epochMs'],1) and integer(clock['monotonicMs'],0))
    utc,mono=after['epochMs']-before['epochMs'],after['monotonicMs']-before['monotonicMs'];need(0<=utc<1500 and 0<=mono<1500 and abs(utc-mono)<=250)
    if epoch is not None:fresh(after['epochMs'],epoch)
    source=value['source'];exact(source,{'calls','tree'});calls(source['calls'],after['epochMs']);lifetimes(source['tree'],after['epochMs'])
    need(before['epochMs']<=source['tree']['observedEpochMs']<=after['epochMs'] and len(json.dumps(value,allow_nan=False).encode())<=LIMIT)
    if previous is not None:
        validate(previous,dict(query,commandId=previous['requestId']),pid)
        need(value['instance']==previous['instance'] and value['sequence']>previous['sequence'] and value['requestId']!=previous['requestId']
            and value['runId']==previous['runId'] and all(before[key]>=previous['clockAfter'][key] for key in before))
        for group in ('calls','tree'):
            old,new=previous['source'][group],source[group];key='instance' if group=='calls' else 'treeInstance'
            need(old[key]==new[key] and (old['complete'] or not new['complete']) and len(new['events'])>=len(old['events']) and same(new['events'][:len(old['events'])],old['events']))
        old,new=previous['source']['tree'],source['tree'];need(old['treeBornEpochMs']==new['treeBornEpochMs'] and new['observedEpochMs']>=old['observedEpochMs']
            and new['observedMonotonicMs']>=old['observedMonotonicMs'] and len(new['entities'])>=len(old['entities']))
        for first,last in zip(old['entities'],new['entities']):
            need(all(same(first[key],last[key]) for key in ('id','birth','insertedSequence','bornEpochMs','bornMonotonicMs'))
                and (not first['removedSequence'] or all(first[key]==last[key] for key in ('removedSequence','removedEpochMs','removedMonotonicMs')))
                and (not first['destroyed'] or all(first[key]==last[key] for key in ('destroyed','destructionObservedEpochMs','destructionObservedMonotonicMs'))))
    return value


def original(value):return validate(value,dict(schemaVersion=1,commandId=value['requestId'],action=ACTION,runId=value['runId']),value['processId'])


def returned(value,before,manager,code,*,after_epoch):
    original(before);validate(value,dict(schemaVersion=1,commandId=value['requestId'],action=ACTION,runId=value['runId']),before['processId'],previous=before)
    need(all(packet['source'][group]['complete'] for packet in (before,value) for group in ('calls','tree')) and type(after_epoch) is int
        and after_epoch>=before['clockAfter']['epochMs'] and manager['assignedEpochMs']>=after_epoch)
    old=before['source']['calls']['events'];events=[event for event in value['source']['calls']['events'][len(old):] if event['kind']=='add-returned'
        and same(event['caller']['manager'],manager) and same(event['caller']['code'],code)]
    need(len(events)==1);event=events[0];need(event['localTreeAvailable'] and event['caller']['invokedEpochMs']>=after_epoch and event['clock']['epochMs']>=after_epoch)
    row=None
    if event['entityId'] is not None:
        prior={entry['birth'] for entry in before['source']['tree']['entities']}
        rows=[entry for entry in value['source']['tree']['entities'] if entry['birth'] not in prior and entry['id']==event['entityId']
            and event['caller']['invokedEpochMs']<=entry['bornEpochMs']<=event['clock']['epochMs']]
        need(len(rows)==1);row=rows[0]
    else:
        prior={entry['birth'] for entry in before['source']['tree']['entities']}
        need(all(entry['birth'] in prior for entry in value['source']['tree']['entities']))
    return dict(iosCreateReturnedEntityVersion=1,returned=deepcopy(event),birth=None if row is None else deepcopy(row),treeInstance=value['source']['tree']['treeInstance'])


def retired(value,ownership,*,after_epoch):
    original(value);exact(ownership,{'iosCreateReturnedEntityVersion','returned','birth','treeInstance'})
    need(type(ownership['iosCreateReturnedEntityVersion']) is int and ownership['iosCreateReturnedEntityVersion']==1 and value['source']['calls']['complete'] and value['source']['tree']['complete']
        and ownership['treeInstance']==value['source']['tree']['treeInstance'] and type(after_epoch) is int and after_epoch>0
        and any(same(event,ownership['returned']) for event in value['source']['calls']['events']))
    original_event=ownership['returned'];birth=ownership['birth'];need(original_event['kind']=='add-returned')
    if birth is None:need(original_event['entityId'] is None);return None
    need(original_event['entityId']==birth['id'])
    rows=[row for row in value['source']['tree']['entities'] if row['birth']==birth['birth']];need(len(rows)==1);row=rows[0]
    need(all(same(row[key],birth[key]) for key in ('id','birth','insertedSequence','bornEpochMs','bornMonotonicMs')) and row['destroyed'] and row['removedSequence']>0)
    need(not any(entry['id']==birth['id'] and (entry['removedSequence']==0 or not entry['destroyed']) for entry in value['source']['tree']['entities']))
    deletes=[event for event in value['source']['calls']['events'] if event['kind']=='delete-returned' and event['entityId']==birth['id']
        and event['localTreeAvailable'] and same(event['caller']['manager'],original_event['caller']['manager']) and same(event['caller']['code'],original_event['caller']['code'])
        and event['caller']['invokedEpochMs']>=after_epoch and event['caller']['invokedEpochMs']<=row['removedEpochMs']<=event['clock']['epochMs']]
    need(len(deletes)==1 and row['destructionObservedEpochMs']>=row['removedEpochMs'])
    return deepcopy(row)


class IOSCreateEntities(IOSPlacesModel):
    _action=ACTION
    _command=staticmethod(command)
    _validate=staticmethod(validate)
    _acquisition_key='iosCreateEntitiesAcquisitionVersion'
    _limit=LIMIT
