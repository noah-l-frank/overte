"""Original native hold/attempt/release returns, independent of UI outcomes."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import re
from adapters.native_feature_observation import exact,fresh,integer,need
from adapters.script_feature.history import same
from adapters import pending_commit_owner as native
from ios.adapters.keyboard_source import identifier,clock
from ios.adapters.places_model import IOSPlacesModel

VERSION=1
ACTION='feature-ios-lifecycle-pending-commands'
FILE=ACTION+'.json'
LIMIT=262144


def command(value):
    exact(value,{'schemaVersion','commandId','action','runId'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['action']==ACTION
         and type(value['commandId']) is str and re.fullmatch('ios-[a-f0-9]{32}',value['commandId']) is not None)
    identifier(value['runId']);return value


def validate(value,query,pid,epoch=None,previous=None):
    command(query);exact(value,{'iosLifecyclePendingCommandsVersion','requestId','runId','instance','sequence','processId',
                              'clockDomain','clockBefore','clockAfter','source'})
    need(type(value['iosLifecyclePendingCommandsVersion']) is int and value['iosLifecyclePendingCommandsVersion']==VERSION
         and value['requestId']==query['commandId'] and value['runId']==query['runId'] and integer(pid,1)
         and type(value['processId']) is int and value['processId']==pid and integer(value['sequence'],1,1000000000)
         and value['clockDomain']=='native-main-lifecycle-pending-commands');identifier(value['instance'])
    a,b=value['clockBefore'],value['clockAfter'];clock(a);clock(b,floor=a)
    need(b['epochMs']-a['epochMs']<1500 and b['monotonicMs']-a['monotonicMs']<1500)
    if epoch is not None:fresh(b['epochMs'],epoch)
    source=value['source'];exact(source,{'installed','complete','commands'})
    need(type(source['installed']) is bool and type(source['complete']) is bool and type(source['commands']) is list
         and len(source['commands'])<=96 and len(json.dumps(source['commands'],ensure_ascii=False,separators=(',',':'),allow_nan=False).encode())<=131072)
    commands=set();previous_reply=None;recorded=0
    for index,row in enumerate(source['commands'],1):
        exact(row,{'index','command','reply','recordedEpochMs'});need(type(row['index']) is int and row['index']==index)
        request=row['command'];native.command(request,ios=True)
        need(request['operation'] in ('hold','attempt','release') and request['commandId'] not in commands);commands.add(request['commandId'])
        reply=row['reply'];need(type(reply) is dict and integer(reply.get('capturedEpochMs'),1))
        native.validate(reply,request,pid,reply['capturedEpochMs'])
        need(integer(row['recordedEpochMs'],max(recorded,reply['capturedEpochMs']),a['epochMs']));recorded=row['recordedEpochMs']
        if previous_reply is not None:
            need(reply['instance']==previous_reply['instance'] and reply['sequence']>previous_reply['sequence']
                 and reply['lastIntentSequence']>previous_reply['lastIntentSequence'] and reply['capturedEpochMs']>=previous_reply['capturedEpochMs'])
        previous_reply=reply
    need(len(json.dumps(value,ensure_ascii=False,allow_nan=False).encode())<=LIMIT)
    if previous is not None:
        validate(previous,dict(query,commandId=previous['requestId']),pid)
        need(value['instance']==previous['instance'] and value['sequence']>previous['sequence'] and value['requestId']!=previous['requestId'])
        clock(a,floor=previous['clockAfter']);old=previous['source']
        need((old['complete'] or not source['complete']) and (not old['installed'] or source['installed'])
             and same(old['commands'],source['commands'][:len(old['commands'])]))
    return value


def original(value):
    return validate(value,dict(schemaVersion=1,commandId=value.get('requestId'),action=ACTION,runId=value.get('runId')),value.get('processId'))


def delivered(value,request):
    original(value);native.command(request,ios=True)
    need(value['source']['installed'] and value['source']['complete'] and value['runId']==request['runId'])
    rows=[row for row in value['source']['commands'] if row['command']['commandId']==request['commandId']]
    need(len(rows)==1 and same(rows[0]['command'],request) and rows[0]['reply']['performed'] is True)
    return deepcopy(rows[0]['reply']) # Original native return, not editor/keyboard/generation evidence.


class IOSLifecyclePendingCommands(IOSPlacesModel):
    _action=ACTION
    _command=staticmethod(command)
    _validate=staticmethod(validate)
    _acquisition_key='iosLifecyclePendingCommandsAcquisitionVersion'
    _limit=LIMIT
