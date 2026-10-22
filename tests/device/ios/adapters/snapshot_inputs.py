"""Actual Snapshot normal-command reception/return, never capture effects."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import re
from urllib.parse import urlsplit
from adapters.native_feature_observation import exact,fresh,integer,need
from adapters.script_feature.history import same
from ios.adapters.places_model import IOSPlacesModel
from ios.adapters.snapshot_export_controls import identity,IDS as EXPORT_IDS
from ios.adapters.snapshot_capture_controls import IDS as CAPTURE_IDS,PREFIX
from ios.adapters.snapshot_exports import stamp

VERSION=1
ACTION='feature-ios-snapshot-inputs'
FILE=ACTION+'.json'
LIMIT=1048576
IDS=CAPTURE_IDS|EXPORT_IDS


def command(value):
    exact(value,{'schemaVersion','commandId','action','runId'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['action']==ACTION
        and type(value['commandId']) is str and re.fullmatch('ios-[0-9a-f]{32}',value['commandId'])
        and type(value['runId']) is str and re.fullmatch('[0-9a-f]{32}',value['runId']));return value


def native_command(value,control):
    need(type(value) is dict and control in IDS);operation=value.get('operation')
    need(operation in ('activate','replace'));exact(value,{'schemaVersion','commandId','instance','sequence','observedElapsedMs','fieldToken','operation'}
        |({'text'} if operation=='replace' else set()))
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and integer(value['sequence'],1) and integer(value['observedElapsedMs']))
    for key in ('commandId','instance','fieldToken'):identity(value[key])
    if operation=='replace':need(control=='snapshot.name' and type(value['text']) is str and (value['text']=='' or PREFIX.fullmatch(value['text'])))
    return value


def root(value):
    exact(value,{'rootId','qmlSource'});identity(value['rootId']);source=value['qmlSource']
    need(type(source) is str and len(source)<=4096 and all(ord(c)>=32 and ord(c)!=127 for c in source))
    url=urlsplit(source);need(url.scheme in ('file','qrc') and not url.netloc and not url.query and not url.fragment
        and url.path.endswith('/system/snapshot/NativeSnapshotReview.qml'));return value


def validate(value,query,pid,epoch=None,previous=None):
    command(query);exact(value,{'iosNormalInputsVersion','profile','requestId','runId','instance','sequence','processId',
        'clockDomain','clockBefore','clockAfter','source'})
    need(type(value['iosNormalInputsVersion']) is int and value['iosNormalInputsVersion']==VERSION and value['profile']=='snapshot'
        and value['requestId']==query['commandId'] and value['runId']==query['runId'] and integer(pid,1)
        and type(value['processId']) is int and value['processId']==pid and type(value['instance']) is str
        and re.fullmatch('[0-9a-f]{32}',value['instance']) and integer(value['sequence'],1,1_000_000_000)
        and value['clockDomain']=='native-process-normal-inputs')
    before,after=stamp(value['clockBefore']),stamp(value['clockAfter']);utc=after['epochMs']-before['epochMs'];mono=after['monotonicMs']-before['monotonicMs']
    need(0<=utc<1500 and 0<=mono<1500 and abs(utc-mono)<=250)
    if epoch is not None:fresh(after['epochMs'],epoch)
    source=value['source'];exact(source,{'complete','events'});need(type(source['complete']) is bool and type(source['events']) is list and len(source['events'])<=512)
    received={};returned=set();events=set();last=None
    for index,row in enumerate(source['events'],1):
        exact(row,{'sequence','eventId','inputId','kind','clock','details'})
        need(type(row['sequence']) is int and row['sequence']==index);identity(row['eventId']);identity(row['inputId'])
        need(row['eventId'] not in events);events.add(row['eventId']);clock=stamp(row['clock'])
        need(all(clock[k]<=after[k] and (last is None or clock[k]>=last[k]) for k in clock));last=clock
        details=row['details'];identifier=row['inputId']
        if row['kind']=='received':
            exact(details,{'outerCommandId','command','controlId','root'})
            need(identifier not in received and type(details['outerCommandId']) is str and re.fullmatch('ios-[0-9a-f]{32}',details['outerCommandId']))
            native_command(details['command'],details['controlId']);root(details['root']);received[identifier]=row
        else:
            need(row['kind']=='returned' and identifier in received and identifier not in returned);returned.add(identifier)
            original=received[identifier];expected=original['details'];inner=expected['command']
            exact(details,{'schemaVersion','commandId','status'});need(type(details['schemaVersion']) is int and details['schemaVersion']==1
                and details['commandId']==expected['outerCommandId'])
            status=details['status'];exact(status,{'schemaVersion','commandId','instance','sequence','performed','processId','sampleEpochMs'})
            need(type(status['schemaVersion']) is int and status['schemaVersion']==1 and status['commandId']==inner['commandId']
                and status['instance']==inner['instance'] and type(status['sequence']) is int and status['sequence']==inner['sequence']
                and type(status['performed']) is bool and type(status['processId']) is int and status['processId']==pid
                and integer(status['sampleEpochMs'],original['clock']['epochMs'],clock['epochMs']))
    need(len(json.dumps(value,ensure_ascii=False,allow_nan=False).encode())<=LIMIT)
    if previous is not None:
        validate(previous,dict(query,commandId=previous['requestId']),pid)
        need(value['instance']==previous['instance'] and value['sequence']>previous['sequence'] and value['requestId']!=previous['requestId']
            and all(before[k]>=previous['clockAfter'][k] for k in before) and (previous['source']['complete'] or not source['complete'])
            and source['events'][:len(previous['source']['events'])]==previous['source']['events'])
    return value


def original(value):
    return validate(value,dict(schemaVersion=1,action=ACTION,commandId=value.get('requestId'),runId=value.get('runId')),value.get('processId'))


def delivered(value,expected_command,control_id,expected_root):
    """Resolve one retained native UUID from actual positive original return.

    The outer owner must have durably saved this exact command/root before
    sending. This function acquires nothing, resends nothing, and proves no
    capture, cancellation, file, export, UI closure or quiet-window result.
    """
    original(value);native_command(expected_command,control_id);root(expected_root);need(value['source']['complete'])
    found=[row for row in value['source']['events'] if row['kind']=='received'
        and row['details']['command']['commandId']==expected_command['commandId']]
    need(len(found)==1);entry=found[0]
    need(same(entry['details']['command'],expected_command) and entry['details']['controlId']==control_id
        and same(entry['details']['root'],expected_root))
    returned=[row for row in value['source']['events'] if row['kind']=='returned' and row['inputId']==entry['inputId']]
    need(len(returned)==1 and returned[0]['details']['status']['performed'] is True)
    return dict(iosSnapshotInputDeliveryVersion=1,command=deepcopy(expected_command),originalReceipt=deepcopy(returned[0]['details']),
        root=deepcopy(expected_root),productOutcomeRequired=True)


class IOSSnapshotInputs(IOSPlacesModel):
    _action=ACTION
    _command=staticmethod(command)
    _validate=staticmethod(validate)
    _acquisition_key='iosSnapshotInputsAcquisitionVersion'
    _limit=LIMIT
