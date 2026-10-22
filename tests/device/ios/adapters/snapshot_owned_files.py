"""Native-owned capture files and one-shot removal work; never an absence ACK."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import re
from adapters.native_feature_observation import exact,fresh,integer,need
from adapters.script_feature.history import same
from ios.adapters.snapshot_captures import identity
from ios.adapters.snapshot_exports import stamp
from ios.adapters.snapshot_file_work import command as work_command
from ios.adapters.snapshot_manifest import manifest
from ios.adapters.places_model import IOSPlacesModel
from snapshot_file_contract import read_request

VERSION=1
ACTION='feature-ios-snapshot-owned-files'
REMOVE='feature-ios-snapshot-file-remove'
FILE=ACTION+'.json'
LIMIT=262144


def command(value):
    original=deepcopy(value);original['action']='feature-ios-snapshot-file-work';work_command(original)
    need(value['action']==ACTION);return value


def remove_command(value):
    exact(value,{'schemaVersion','commandId','action','runId','fileId','manifestCommandId'})
    command({key:(ACTION if key=='action' else value[key]) for key in ('schemaVersion','commandId','action','runId')})
    need(value['action']==REMOVE);identity(value['fileId'])
    need(type(value['manifestCommandId']) is str and re.fullmatch('ios-[a-f0-9]{32}',value['manifestCommandId']))
    return value


def witness(value,row,epoch):
    exact(value,{'pathObservedEpochMs','phase','fileName','captureInstance','requestId','bornEpochMs','terminal','nativeDrained'})
    identity(value['captureInstance'])
    need(type(value['requestId']) is str and re.fullmatch('snap_[0-9]{1,20}_[0-9]{1,10}',value['requestId'])
        and value['fileName']==row['name'] and '-'+value['requestId']+'.' in row['name']
        and value['phase'] in ('processing','complete','save-attempt') and value['terminal'] in ('','complete','error','cancelled')
        and type(value['nativeDrained']) is bool and integer(value['bornEpochMs'],1,epoch)
        and integer(value['pathObservedEpochMs'],value['bornEpochMs'],epoch))
    return value


def immutable_witness(value):return {k:v for k,v in value.items() if k not in ('terminal','nativeDrained')}


def validate(value,query,pid,epoch=None,previous=None):
    command(query);exact(value,{'iosSnapshotOwnedFilesVersion','requestId','runId','instance','sequence','processId',
        'clockDomain','clockBefore','clockAfter','source'})
    need(type(value['iosSnapshotOwnedFilesVersion']) is int and value['iosSnapshotOwnedFilesVersion']==VERSION
        and value['requestId']==query['commandId'] and value['runId']==query['runId'] and integer(pid,1)
        and type(value['processId']) is int and value['processId']==pid and integer(value['sequence'],1,1000000000)
        and value['clockDomain']=='native-main-snapshot-owned-files');identity(value['instance'])
    before,after=stamp(value['clockBefore']),stamp(value['clockAfter']);end=after['epochMs']
    utc,mono=end-before['epochMs'],after['monotonicMs']-before['monotonicMs']
    need(0<=utc<1500 and 0<=mono<1500 and abs(utc-mono)<=250)
    if epoch is not None:fresh(end,epoch)
    source=value['source'];exact(source,{'complete','prefixes','files','jobs'})
    need(type(source['complete']) is bool and all(type(source[k]) is list and len(source[k])<=128 for k in ('prefixes','files','jobs')))
    prefixes={};files={};jobs={};names=set()
    for row in source['prefixes']:
        exact(row,{'prefix','query','sampleEpochMs','initiallyEmpty'});read_request(row['query'])
        need(row['query']['operation']=='list' and row['query']['prefix']==row['prefix']
            and row['prefix'].startswith('parity-'+query['runId'][:16]+'-') and row['prefix'] not in prefixes
            and integer(row['sampleEpochMs'],1,end) and type(row['initiallyEmpty']) is bool)
        prefixes[row['prefix']]=row
    for row in source['files']:
        exact(row,{'id','prefix','file','capture','manifestQuery','observedEpochMs','removeCommandId'})
        identity(row['id']);need(row['id'] not in files and row['prefix'] in prefixes)
        admission=prefixes[row['prefix']];need(admission['initiallyEmpty'])
        read_request(row['manifestQuery']);need(row['manifestQuery']['operation']=='list'
            and row['manifestQuery']['prefix']==row['prefix'] and row['manifestQuery']['commandId']!=admission['query']['commandId'])
        # Reuse the exact unchanged manifest-row grammar and file byte bounds.
        manifest(dict(schemaVersion=1,commandId=row['manifestQuery']['commandId'],operation='list',prefix=row['prefix'],
            processId=pid,sampleEpochMs=row['observedEpochMs'],ok=True,files=[row['file']]),row['manifestQuery'],pid)
        pair=(row['prefix'],row['file']['name']);need(pair not in names);names.add(pair)
        need(integer(row['observedEpochMs'],admission['sampleEpochMs'],end))
        witness(row['capture'],row['file'],end);need(row['capture']['bornEpochMs']>=admission['sampleEpochMs']
            and row['capture']['pathObservedEpochMs']<=row['observedEpochMs'])
        need(type(row['removeCommandId']) is str and (row['removeCommandId']=='' or re.fullmatch('ios-[a-f0-9]{32}',row['removeCommandId'])))
        files[row['id']]=row
    for row in source['jobs']:
        exact(row,{'query','queuedEpochMs','enteredEpochMs','returnedEpochMs','finallyEpochMs','expiredEpochMs','alive','result'})
        remove_command(row['query']);q=row['query'];need(q['runId']==query['runId'] and q['commandId'] not in jobs and q['fileId'] in files)
        owned=files[q['fileId']];need(owned['capture']['nativeDrained'] and owned['capture']['terminal']
            and owned['removeCommandId']==q['commandId'] and owned['manifestQuery']['commandId']==q['manifestCommandId']
            and integer(row['queuedEpochMs'],owned['observedEpochMs'],end) and type(row['alive']) is bool)
        start=row['queuedEpochMs']
        for key in ('enteredEpochMs','returnedEpochMs','finallyEpochMs','expiredEpochMs'):
            if row[key] is not None:need(integer(row[key],start,end));start=row[key]
        if row['result'] is not None:
            result=row['result'];need(type(result) is dict);exact(result,{'ok','unlinkIssued','sampleEpochMs'} if result.get('ok') is True else {'ok','unlinkIssued','sampleEpochMs','error'})
            need(type(result['ok']) is bool and type(result['unlinkIssued']) is bool and row['enteredEpochMs'] is not None
                and integer(result['sampleEpochMs'],row['enteredEpochMs'],row['returnedEpochMs'] or row['finallyEpochMs'] or end))
            if result['ok']:need(result['unlinkIssued'])
            else:need(type(result['error']) is str and 0<len(result['error'])<=128)
        if row['returnedEpochMs'] is not None:need(row['enteredEpochMs'] is not None and row['finallyEpochMs'] is not None)
        if row['finallyEpochMs'] is not None:need(row['enteredEpochMs'] is not None)
        if row['expiredEpochMs'] is not None:need(not row['alive'])
        if source['complete'] and not row['alive']:need(row['finallyEpochMs'] is not None and row['expiredEpochMs'] is not None)
        jobs[q['commandId']]=row
    for row in files.values():need(not row['removeCommandId'] or row['removeCommandId'] in jobs)
    need([r['prefix'] for r in source['prefixes']]==sorted(prefixes) and [r['id'] for r in source['files']]==sorted(files)
        and [r['query']['commandId'] for r in source['jobs']]==sorted(jobs)
        and len(json.dumps(source,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode())<=240000
        and len(json.dumps(value,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode())<=LIMIT)
    if previous is not None:
        validate(previous,dict(query,commandId=previous['requestId']),pid)
        need(value['instance']==previous['instance'] and value['sequence']>previous['sequence'] and value['requestId']!=previous['requestId']
            and all(before[k]>=previous['clockAfter'][k] for k in before)
            and abs(before['epochMs']-previous['clockAfter']['epochMs']-before['monotonicMs']+previous['clockAfter']['monotonicMs'])<=250
            and (previous['source']['complete'] or not source['complete']))
        old_source=previous['source'];floor=previous['clockBefore']['epochMs']
        for old in old_source['prefixes']:need(old['prefix'] in prefixes and same(prefixes[old['prefix']],old))
        old_prefixes={r['prefix'] for r in old_source['prefixes']};old_files={r['id'] for r in old_source['files']}
        for key,row in prefixes.items():
            if key not in old_prefixes:need(row['sampleEpochMs']>=floor)
        for key,row in files.items():
            if key not in old_files:need(row['observedEpochMs']>=floor)
        for old in old_source['files']:
            need(old['id'] in files);row=files[old['id']]
            need(same({k:v for k,v in row.items() if k not in ('capture','removeCommandId')},
                {k:v for k,v in old.items() if k not in ('capture','removeCommandId')})
                and same(immutable_witness(row['capture']),immutable_witness(old['capture']))
                and (not old['capture']['nativeDrained'] or row['capture']['nativeDrained'])
                and (not old['capture']['terminal'] or old['capture']['terminal']==row['capture']['terminal'])
                and (not old['removeCommandId'] or old['removeCommandId']==row['removeCommandId']))
        for old in old_source['jobs']:
            key=old['query']['commandId'];need(key in jobs);row=jobs[key]
            need(same(row['query'],old['query']) and row['queuedEpochMs']==old['queuedEpochMs'] and (old['alive'] or not row['alive']))
            for k in ('enteredEpochMs','returnedEpochMs','finallyEpochMs','expiredEpochMs','result'):
                if old[k] is not None:need(same(row[k],old[k]))
                elif row[k] is not None:need((row[k]['sampleEpochMs'] if k=='result' else row[k])>=floor)
        old_ids={r['query']['commandId'] for r in old_source['jobs']}
        for key,row in jobs.items():
            if key not in old_ids:need(row['queuedEpochMs']>=floor)
    return value


def original(value):
    return validate(value,dict(schemaVersion=1,action=ACTION,commandId=value.get('requestId'),runId=value.get('runId')),value.get('processId'))


def removed(value,query,pid):
    """One fully retired successful unlink, requiring independent absence later."""
    validate(value,dict(schemaVersion=1,action=ACTION,commandId=value.get('requestId'),runId=query.get('runId')),pid)
    remove_command(query);need(value['source']['complete'])
    rows=[r for r in value['source']['jobs'] if same(r['query'],query)];need(len(rows)==1)
    row=rows[0];need(row['result'] is not None and row['result']['ok'] and row['result']['unlinkIssued']
        and row['returnedEpochMs'] is not None and row['finallyEpochMs'] is not None and row['expiredEpochMs'] is not None and not row['alive'])
    need(all(not r['alive'] and r['finallyEpochMs'] is not None and r['expiredEpochMs'] is not None for r in value['source']['jobs']))
    return dict(iosSnapshotFileRemovedVersion=1,query=deepcopy(query),result=deepcopy(row['result']),independentAbsenceRequired=True,quietWindowRequired=True)


class IOSSnapshotOwnedFiles(IOSPlacesModel):
    _limit=LIMIT
    _action=ACTION
    _command=staticmethod(command)
    _validate=staticmethod(validate)
    _acquisition_key='iosSnapshotOwnedFilesAcquisitionVersion'
