"""Passive original Avatar commands/returns; never feature-effect evidence."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import re
from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.script_feature.history import same
from feature_journeys.contract import identifier
from ios.adapters import avatar_controls as controls
from ios.adapters.places_model import IOSPlacesModel

VERSION=1
ACTION='feature-ios-avatar-inputs'
FILE=ACTION+'.json'
LIMIT=1048576


def command(value):
    exact(value,{'schemaVersion','commandId','action','runId'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['action']==ACTION
        and type(value['commandId']) is str and re.fullmatch('ios-[0-9a-f]{32}',value['commandId']))
    identifier(value['runId']);return value


def clock(value):
    exact(value,{'epochMs','monotonicMs'});need(integer(value['epochMs'],1) and integer(value['monotonicMs']))
    return value


def native_command(value,control):
    base={'schemaVersion','commandId','instance','sequence','observedElapsedMs','fieldToken','operation'}
    action=value.get('operation');extra={'replace':{'text'},'set-value':{'value'},'select-index':{'index'},'activate':set()}
    need(action in extra);exact(value,base|extra[action]);need(type(value['schemaVersion']) is int and value['schemaVersion']==1
        and all(controls.nonce(value[key]) for key in ('commandId','instance','fieldToken'))
        and integer(value['sequence'],1) and integer(value['observedElapsedMs']))
    if action=='replace':need(control in controls.FIELDS);controls.text(value['text'],4096)
    elif action=='set-value':need(control=='avatar.scale' and number(value['value'],.1,4))
    elif action=='select-index':need(control=='avatar.wearable-choice' and integer(value['index'],0,31))
    return value


def validate(value,query,pid,epoch=None,previous=None):
    command(query);exact(value,{'iosNormalInputsVersion','profile','requestId','runId','instance','sequence','processId',
        'clockDomain','clockBefore','clockAfter','source'})
    need(type(value['iosNormalInputsVersion']) is int and value['iosNormalInputsVersion']==VERSION and value['profile']=='avatar'
        and value['requestId']==query['commandId'] and value['runId']==query['runId'] and integer(pid,1)
        and type(value['processId']) is int and value['processId']==pid and type(value['instance']) is str
        and re.fullmatch('[0-9a-f]{32}',value['instance']) and integer(value['sequence'],1,1_000_000_000)
        and value['clockDomain']=='native-process-normal-inputs')
    before,after=clock(value['clockBefore']),clock(value['clockAfter'])
    utc,mono=after['epochMs']-before['epochMs'],after['monotonicMs']-before['monotonicMs']
    need(0<=utc<1500 and 0<=mono<1500 and abs(utc-mono)<=250)
    if epoch is not None:fresh(after['epochMs'],epoch)
    source=value['source'];exact(source,{'complete','events'})
    need(type(source['complete']) is bool and type(source['events']) is list and len(source['events'])<=512)
    events=set();received={};returned=set();last=None
    for index,row in enumerate(source['events'],1):
        exact(row,{'sequence','eventId','inputId','kind','clock','details'})
        need(type(row['sequence']) is int and row['sequence']==index and controls.nonce(row['eventId'])
            and row['eventId'] not in events and controls.nonce(row['inputId']));events.add(row['eventId'])
        stamp=clock(row['clock']);need(stamp['epochMs']<=after['epochMs'] and stamp['monotonicMs']<=after['monotonicMs'])
        if last:need(all(stamp[key]>=last[key] for key in stamp))
        last=stamp;details=row['details'];identity=row['inputId']
        if row['kind']=='received':
            exact(details,{'outerCommandId','command','controlId','root'})
            need(identity not in received and type(details['outerCommandId']) is str
                and re.fullmatch('ios-[0-9a-f]{32}',details['outerCommandId']) and controls.control_id(details['controlId'])
                and details['controlId'] not in ('avatar.page','people.page'))
            native_command(details['command'],details['controlId']);root=details['root']
            if root is not None:
                exact(root,{'rootId','qmlSource'});need(controls.nonce(root['rootId']));controls.component(root['qmlSource'])
            elif details['controlId'] not in ('avatar.entry','people.entry'):need(False)
            received[identity]=row
        else:
            need(row['kind']=='returned' and identity in received and identity not in returned);returned.add(identity)
            original=received[identity];expected=original['details'];cmd=expected['command']
            exact(details,{'schemaVersion','commandId','status'})
            need(type(details['schemaVersion']) is int and details['schemaVersion']==1 and details['commandId']==expected['outerCommandId'])
            status=details['status'];exact(status,{'schemaVersion','commandId','instance','sequence','performed','processId','sampleEpochMs'})
            need(type(status['schemaVersion']) is int and status['schemaVersion']==1 and status['commandId']==cmd['commandId']
                and status['instance']==cmd['instance'] and type(status['sequence']) is int and status['sequence']==cmd['sequence']
                and type(status['performed']) is bool and type(status['processId']) is int and status['processId']==pid
                and integer(status['sampleEpochMs'],original['clock']['epochMs'],stamp['epochMs']))
    need(len(json.dumps(value,ensure_ascii=False,allow_nan=False).encode())<=LIMIT)
    if previous is not None:
        validate(previous,dict(query,commandId=previous['requestId']),pid)
        need(value['instance']==previous['instance'] and value['sequence']>previous['sequence']
            and value['requestId']!=previous['requestId'] and before['epochMs']>=previous['clockAfter']['epochMs']
            and before['monotonicMs']>=previous['clockAfter']['monotonicMs']
            and (previous['source']['complete'] or not source['complete'])
            and source['events'][:len(previous['source']['events'])]==previous['source']['events'])
    return value


def original(value):
    return validate(value,dict(schemaVersion=1,commandId=value.get('requestId'),action=ACTION,runId=value.get('runId')),value.get('processId'))


def delivered(value,original_intent):
    """Recover only an unchanged original, actually returned positive receipt.

    Missing/partial/rejected records remain unresolved. A receipt allows later
    input ownership recovery; actual feature outcomes need separate sources.
    """
    from ios.adapters.avatar_input_owner import intent,delivery
    original(value);need(value['source']['complete']);intent(original_intent,value['processId'])
    expected=original_intent['nativeCommand'];matches=[]
    for row in value['source']['events']:
        if row['kind']=='received' and row['details']['command']['commandId']==expected['commandId']:
            need(same(row['details']['command'],expected) and row['details']['controlId']==original_intent['controlId'])
            matches.append(row)
    need(len(matches)==1);start=matches[0]
    root=start['details']['root'];rows=[row for row in original_intent['reference']['controls'] if row['id']==original_intent['controlId']]
    if root is not None and 'rootId' in rows[0]:need(all(rows[0][key]==root[key] for key in root))
    if original_intent['controlId']=='tablet.home' or original_intent['controlId'].startswith('tablet.page.'):
        pages=[row for row in original_intent['reference']['controls'] if row['id'] in ('avatar.page','people.page')]
        need(root is not None and len(pages)==1 and all(pages[0][key]==root[key] for key in root))
    returned=[row for row in value['source']['events'] if row['inputId']==start['inputId'] and row['kind']=='returned']
    need(len(returned)==1 and returned[0]['details']['status']['performed'] is True)
    result=dict(command=deepcopy(expected),originalReceipt=deepcopy(returned[0]['details']))
    delivery(result,original_intent,value['processId']);return result


class IOSAvatarInputs(IOSPlacesModel):
    _limit=LIMIT
    _action=ACTION
    _command=staticmethod(command)
    _validate=staticmethod(validate)
    _acquisition_key='iosAvatarInputsAcquisitionVersion'
