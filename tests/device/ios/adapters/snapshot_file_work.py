"""Actual queued native Snapshot file-job work and separate weak expiry."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from adapters.native_feature_observation import exact,integer,need
from adapters.script_feature.history import same
from ios.adapters.snapshot_work import command as work_command
from ios.adapters.snapshot_captures import identity
from ios.adapters.places_model import IOSPlacesModel
from ios.adapters.snapshot_exports import stamp
from snapshot_file_contract import read_request

VERSION=1
ACTION='feature-ios-snapshot-file-work'
FILE=ACTION+'.json'
LIMIT=2097152


def command(value):
    original=deepcopy(value);original['action']='feature-ios-snapshot-work';work_command(original)
    need(value['action']==ACTION);return value


def validate(value,query,pid,epoch=None,previous=None):
    from adapters.native_feature_observation import fresh
    command(query);exact(value,{'iosSnapshotFileWorkVersion','requestId','runId','instance','sequence','processId',
        'clockDomain','clockBefore','clockAfter','source'})
    need(type(value['iosSnapshotFileWorkVersion']) is int and value['iosSnapshotFileWorkVersion']==VERSION
        and value['requestId']==query['commandId'] and value['runId']==query['runId'] and integer(pid,1)
        and type(value['processId']) is int and value['processId']==pid and integer(value['sequence'],1,1000000000)
        and value['clockDomain']=='native-main-snapshot-file-work');identity(value['instance'])
    before,after=stamp(value['clockBefore']),stamp(value['clockAfter'])
    utc,mono=after['epochMs']-before['epochMs'],after['monotonicMs']-before['monotonicMs']
    need(0<=utc<1500 and 0<=mono<1500 and abs(utc-mono)<=250)
    if epoch is not None:fresh(after['epochMs'],epoch)
    source=value['source'];exact(source,{'complete','jobs'})
    need(type(source['complete']) is bool and type(source['jobs']) is list and len(source['jobs'])<=1024)
    ids=[]
    for row in source['jobs']:
        exact(row,{'id','query','queuedEpochMs','enteredEpochMs','returnedEpochMs','finallyEpochMs','expiredEpochMs',
            'publication','publishedEpochMs','alive'});identity(row['id']);ids.append(row['id']);read_request(row['query'])
        need(row['query']['prefix'].startswith('parity-'+query['runId'][:16]+'-')
            and integer(row['queuedEpochMs'],1,after['epochMs']) and type(row['alive']) is bool)
        start=row['queuedEpochMs']
        for key in ('enteredEpochMs','publishedEpochMs','returnedEpochMs','finallyEpochMs','expiredEpochMs'):
            if row[key] is not None:need(integer(row[key],start,after['epochMs']));start=row[key]
        need((row['publication'] is None)==(row['publishedEpochMs'] is None))
        if row['publication'] is not None:need(type(row['publication']) is bool and row['enteredEpochMs'] is not None)
        if row['returnedEpochMs'] is not None:need(row['enteredEpochMs'] is not None and row['finallyEpochMs'] is not None)
        if row['finallyEpochMs'] is not None:need(row['enteredEpochMs'] is not None)
        if row['expiredEpochMs'] is not None:need(not row['alive'])
        if source['complete'] and not row['alive']:need(row['finallyEpochMs'] is not None and row['expiredEpochMs'] is not None)
    need(ids==sorted(set(ids)) and len(json.dumps(source,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode())<=1572864
        and len(json.dumps(value,allow_nan=False).encode())<=LIMIT)
    if previous is not None:
        validate(previous,dict(query,commandId=previous['requestId']),pid)
        need(value['instance']==previous['instance'] and value['sequence']>previous['sequence'] and value['requestId']!=previous['requestId']
            and all(before[key]>=previous['clockAfter'][key] for key in before)
            and abs(before['epochMs']-previous['clockAfter']['epochMs']-before['monotonicMs']+previous['clockAfter']['monotonicMs'])<=250
            and (previous['source']['complete'] or not source['complete']))
        current={row['id']:row for row in source['jobs']}
        for old in previous['source']['jobs']:
            need(old['id'] in current);row=current[old['id']]
            need(same(row['query'],old['query']) and row['queuedEpochMs']==old['queuedEpochMs'] and (old['alive'] or not row['alive']))
            for key in ('enteredEpochMs','returnedEpochMs','finallyEpochMs','expiredEpochMs','publishedEpochMs','publication'):
                if old[key] is not None:need(same(row[key],old[key]))
                # Worker events can occur after the preceding row snapshot but
                # before that getter's after-clock. Keep the original bracket.
                elif row[key] is not None and key!='publication':need(row[key]>=previous['clockBefore']['epochMs'])
        for row in source['jobs']:
            if row['id'] not in {old['id'] for old in previous['source']['jobs']}:need(row['queuedEpochMs']>=previous['clockBefore']['epochMs'])
    return value


def original(value):
    return validate(value,dict(schemaVersion=1,action=ACTION,commandId=value.get('requestId'),runId=value.get('runId')),value.get('processId'))


def drained(value,queries):
    original(value);need(value['source']['complete'] and type(queries) is list and queries)
    for query in queries:
        read_request(query);rows=[row for row in value['source']['jobs'] if same(row['query'],query)]
        need(len(rows)==1 and rows[0]['publication'] is True and rows[0]['returnedEpochMs'] is not None)
    need(all(not row['alive'] and row['finallyEpochMs'] is not None and row['expiredEpochMs'] is not None for row in value['source']['jobs']))
    return deepcopy(value['source'])


def retired(value,queries):
    """Error-path body/capture death, without successful publication credit.

    Failed or thrown native work can release its actual functor. This proves
    neither a successful query nor file presence/absence; its original query
    and any partial output remain owned by the enclosing error cleanup.
    """
    original(value);need(value['source']['complete'] and type(queries) is list and queries)
    nonces=set()
    for query in queries:
        read_request(query);need(query['commandId'] not in nonces);nonces.add(query['commandId'])
        rows=[row for row in value['source']['jobs'] if same(row['query'],query)]
        need(len(rows)==1 and rows[0]['enteredEpochMs'] is not None and rows[0]['finallyEpochMs'] is not None)
    need(all(not row['alive'] and row['finallyEpochMs'] is not None and row['expiredEpochMs'] is not None for row in value['source']['jobs']))
    return deepcopy(value['source'])


class IOSSnapshotFileWork(IOSPlacesModel):
    _limit=LIMIT
    _action=ACTION
    _command=staticmethod(command)
    _validate=staticmethod(validate)
    _acquisition_key='iosSnapshotFileWorkAcquisitionVersion'
