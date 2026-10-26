"""Original Lifecycle command reception/return, independent of editor effects."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import re
from adapters.native_feature_observation import exact,fresh,integer,need
from adapters.script_feature.history import same
from ios.adapters.places_model import IOSPlacesModel
from ios.adapters.snapshot_export_controls import identity as uuid
from ios.adapters.keyboard_source import clock,identifier
from ios.adapters import lifecycle_fields as fields,tablet_back_controls as back

VERSION=1
ACTION='feature-ios-lifecycle-inputs'
FILE=ACTION+'.json'
LIMIT=1048576
IDS=frozenset(fields.IDS)|{'chat.input','tablet.back'}


def command(value):
    exact(value,{'schemaVersion','commandId','action','runId'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==VERSION and value['action']==ACTION
         and type(value['commandId']) is str and re.fullmatch('ios-[a-f0-9]{32}',value['commandId']) is not None)
    identifier(value['runId']);return value


def native_command(value,control):
    need(type(value) is dict and control in IDS);operation=value.get('operation')
    need(operation in ('activate','replace') and (control!='tablet.back' or operation=='activate'))
    exact(value,{'schemaVersion','commandId','instance','sequence','observedElapsedMs','fieldToken','operation'}
          |({'text'} if operation=='replace' else set()))
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and integer(value['sequence'],1) and integer(value['observedElapsedMs']))
    for key in ('commandId','instance','fieldToken'):uuid(value[key])
    if operation=='replace':need(fields.owned_text(value['text'],fields.IDS.get(control,'chat')))
    return value


def root(value,control,request):
    need(control in IDS)
    if control=='tablet.back':
        exact(value,{'kind','observation'});need(value['kind']=='back')
        row=value['observation'];exact(row,{'id','token','enabled','focused'}|back.FIELDS);back.metadata(row)
        need(row['token']==request['fieldToken'])
    else:
        exact(value,{'kind','identity'});need(value['kind']=='field');fields.identity(value['identity'])
        need(value['identity']['editor']==fields.IDS.get(control,'chat'))
    return value


def _validate(value,query,pid,epoch=None,previous=None,*,query_validator,input_validator,root_validator,profile):
    query_validator(query);exact(value,{'iosNormalInputsVersion','profile','requestId','runId','instance','sequence','processId',
                               'clockDomain','clockBefore','clockAfter','source'})
    need(type(value['iosNormalInputsVersion']) is int and value['iosNormalInputsVersion']==1 and value['profile']==profile
         and value['requestId']==query['commandId'] and value['runId']==query['runId'] and integer(pid,1)
         and type(value['processId']) is int and value['processId']==pid and integer(value['sequence'],1)
         and value['clockDomain']=='native-process-normal-inputs');identifier(value['instance'])
    a,b=value['clockBefore'],value['clockAfter'];clock(a);clock(b,floor=a)
    need(b['epochMs']-a['epochMs']<1500 and b['monotonicMs']-a['monotonicMs']<1500)
    if epoch is not None:fresh(b['epochMs'],epoch)
    source=value['source'];exact(source,{'complete','events'})
    need(type(source['complete']) is bool and type(source['events']) is list and len(source['events'])<=512
         and len(json.dumps(source['events'],ensure_ascii=False,separators=(',',':'),allow_nan=False).encode())<=524288)
    inputs={};returned=set();events=set();last=None
    for index,row in enumerate(source['events'],1):
        exact(row,{'sequence','eventId','inputId','kind','clock','details'})
        need(type(row['sequence']) is int and row['sequence']==index);uuid(row['eventId']);uuid(row['inputId'])
        need(row['eventId'] not in events);events.add(row['eventId']);clock(row['clock'],floor=last,ceiling=b);last=row['clock']
        details=row['details'];key=row['inputId']
        if row['kind']=='received':
            exact(details,{'outerCommandId','command','controlId','root'})
            need(key not in inputs and type(details['outerCommandId']) is str and re.fullmatch('ios-[a-f0-9]{32}',details['outerCommandId']) is not None)
            input_validator(details['command'],details['controlId']);root_validator(details['root'],details['controlId'],details['command']);inputs[key]=row
        else:
            need(row['kind']=='returned' and key in inputs and key not in returned);returned.add(key)
            received=inputs[key];original=received['details'];inner=original['command']
            exact(details,{'schemaVersion','commandId','status'});need(type(details['schemaVersion']) is int and details['schemaVersion']==1
                 and details['commandId']==original['outerCommandId'])
            status=details['status'];exact(status,{'schemaVersion','commandId','instance','sequence','performed','processId','sampleEpochMs'})
            need(type(status['schemaVersion']) is int and status['schemaVersion']==1 and status['commandId']==inner['commandId']
                 and status['instance']==inner['instance'] and type(status['sequence']) is int and status['sequence']==inner['sequence']
                 and type(status['performed']) is bool and type(status['processId']) is int and status['processId']==pid
                 and integer(status['sampleEpochMs'],received['clock']['epochMs'],row['clock']['epochMs']))
    need(len(json.dumps(value,ensure_ascii=False,allow_nan=False).encode())<=LIMIT)
    if previous is not None:
        _validate(previous,dict(query,commandId=previous['requestId']),pid,query_validator=query_validator,
                  input_validator=input_validator,root_validator=root_validator,profile=profile)
        need(value['instance']==previous['instance'] and value['sequence']>previous['sequence'] and value['requestId']!=previous['requestId'])
        clock(a,floor=previous['clockAfter'])
        need((previous['source']['complete'] or not source['complete']) and same(previous['source']['events'],source['events'][:len(previous['source']['events'])]))
    return value


def validate(value,query,pid,epoch=None,previous=None):
    return _validate(value,query,pid,epoch,previous,query_validator=command,input_validator=native_command,root_validator=root,profile='lifecycle')


def original(value):
    return validate(value,dict(schemaVersion=1,action=ACTION,commandId=value.get('requestId'),runId=value.get('runId')),value.get('processId'))


def _delivered(value,expected,control,original_root,*,original_validator,input_validator,root_validator,delivery_key):
    original_validator(value);input_validator(expected,control);root_validator(original_root,control,expected);need(value['source']['complete'])
    rows=[row for row in value['source']['events'] if row['kind']=='received' and row['details']['command']['commandId']==expected['commandId']]
    need(len(rows)==1);received=rows[0]
    need(same(received['details']['command'],expected) and received['details']['controlId']==control and same(received['details']['root'],original_root))
    returned=[row for row in value['source']['events'] if row['kind']=='returned' and row['inputId']==received['inputId']]
    need(len(returned)==1 and returned[0]['details']['status']['performed'] is True)
    return {delivery_key:1,'command':deepcopy(expected),'root':deepcopy(original_root),
            'originalReceipt':deepcopy(returned[0]['details']),'productOutcomeRequired':True}


def delivered(value,expected,control,original_root):
    return _delivered(value,expected,control,original_root,original_validator=original,input_validator=native_command,
                      root_validator=root,delivery_key='iosLifecycleInputDeliveryVersion')


class IOSLifecycleInputs(IOSPlacesModel):
    _action=ACTION
    _command=staticmethod(command)
    _validate=staticmethod(validate)
    _acquisition_key='iosLifecycleInputsAcquisitionVersion'
    _limit=LIMIT
