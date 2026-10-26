"""Separate Photos resource originals; native Save ACKs never supply bytes."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import re
from adapters.native_feature_observation import exact,integer,need
from adapters.script_feature.history import same
from ios.adapters.snapshot_exports import FILE_NAME,photos_asset

VERSION=2
READS=(1,2)
MAX_BYTES=256*1024*1024
HEX=r'[0-9a-f]{32}'
FIELDS={'iosSnapshotDestinationVersion','runId','kind','basename','photosIdentifier','instance','processId','clockDomain',
        'createdClock','events','queries','phase','resource','byteCount','sha256','artifact','deletion'}


def stamp(value,floor=None):
    exact(value,{'epochMs','monotonicMs'});need(integer(value['epochMs'],1) and integer(value['monotonicMs']))
    if floor is not None:
        utc=value['epochMs']-floor['epochMs'];mono=value['monotonicMs']-floor['monotonicMs']
        need(utc>=0 and mono>=0 and abs(utc-mono)<=250)
    return value


def original(value,previous=None):
    need(type(value) is dict);version=value.get('iosSnapshotDestinationVersion')
    need(type(version) is int and version in READS);exact(value,FIELDS|({'artifactRevision'} if version>=2 else set()))
    need(type(value['iosSnapshotDestinationVersion']) is int and value['iosSnapshotDestinationVersion'] in READS
        and value['kind']=='photos-resource' and value['clockDomain']=='native-companion-photos'
        and type(value['runId']) is str and re.fullmatch(HEX,value['runId'])
        and type(value['instance']) is str and re.fullmatch(HEX,value['instance']) and integer(value['processId'],1)
        and type(value['basename']) is str and re.fullmatch(FILE_NAME,value['basename'])
        and value['basename'].startswith('parity-'+value['runId'][:16]+'-')
        and type(value['photosIdentifier']) is str and 0<len(value['photosIdentifier'])<=4096
        and all(ord(c)>=32 and ord(c)!=127 for c in value['photosIdentifier'])
        and value['artifact']=='original.bytes' and value['phase'] in ('issued','failed','complete')
        and integer(value['byteCount'],0,MAX_BYTES) and type(value['sha256']) is str)
    created=stamp(value['createdClock']);need(type(value['events']) is list and 1<=len(value['events'])<=512
        and type(value['queries']) is list and len(value['queries'])<=128)
    if value['resource'] is not None:
        exact(value['resource'],{'originalFilename','type'});need(value['resource']['originalFilename']==value['basename']
            and type(value['resource']['type']) is int and value['resource']['type']==1)
    seen=[];depth={'data':0,'completion':0};clock=created;expired=False;terminal=False;deletes=[];delete_depth={'changes':0,'completion':0};delete_result=None;delete_expired=False
    for index,event in enumerate(value['events'],1):
        exact(event,{'sequence','kind','clock','detail'});need(type(event['sequence']) is int and event['sequence']==index)
        stamp(event['clock'],clock);clock=event['clock'];kind=event['kind'];detail=event['detail']
        if type(kind) is str and kind.startswith('delete-'):
            need(expired and 'read-completed' in seen and not delete_expired and value['deletion'] is not None)
            if kind=='delete-issued':need(not deletes);exact(detail,set())
            else:
                need(deletes and deletes[0]=='delete-issued')
                if kind in ('delete-changes-enter','delete-completion-enter'):
                    exact(detail,set());name=kind.split('-')[1];need(delete_depth[name]==0 and kind not in deletes and delete_result is None)
                    if name=='completion':need(delete_depth['changes']==0)
                    else:need('delete-completion-enter' not in deletes)
                    delete_depth[name]=1
                elif kind in ('delete-changes-left','delete-completion-left'):
                    exact(detail,set());name=kind.split('-')[1];need(delete_depth[name]==1);delete_depth[name]=0
                elif kind=='delete-completed':
                    exact(detail,{'success','hasError'});need(delete_depth['completion']==1 and delete_result is None
                        and all(type(detail[k]) is bool for k in detail));delete_result=detail
                else:
                    need(kind=='delete-weak-expired' and delete_result is not None and not any(delete_depth.values()));exact(detail,set());delete_expired=True
            deletes.append(kind);continue
        need(kind in ('read-issued','resource-selected','read-failed','callback-enter','callback-left','read-completed','weak-expired') and not expired)
        if kind.startswith('callback-'):
            exact(detail,{'name'});name=detail['name'];need(name in depth and 'resource-selected' in seen)
            if kind=='callback-enter':
                need(depth[name]==0 and not terminal and (name!='data' or 'completion' not in [row['detail'].get('name') for row in value['events'][:index-1]]));depth[name]+=1
            else:need(depth[name]==1);depth[name]-=1
        else:
            exact(detail,set())
            if kind=='read-issued':need(not seen)
            else:
                need(seen and seen[0]=='read-issued')
                if kind=='resource-selected':need(seen==['read-issued'] and value['resource'] is not None)
                elif kind in ('read-completed','read-failed'):
                    need(not terminal and (kind!='read-completed' or depth['completion']==1));terminal=True
                else:need(not any(depth.values()) and terminal);expired=True
        seen.append(kind)
    if value['phase']=='complete':need('read-completed' in seen and 'read-failed' not in seen and value['byteCount']>0
        and re.fullmatch('[0-9a-f]{64}',value['sha256']))
    else:need(value['sha256']=='' and ('read-failed' in seen)==(value['phase']=='failed') and 'read-completed' not in seen)
    if version>=2:
        need((type(value['artifactRevision']) is str and re.fullmatch('[a-f0-9]{64}',value['artifactRevision']))
            if value['phase']=='complete' else value['artifactRevision'] is None)
    deletion=value['deletion']
    if deletion is None:need(not deletes)
    else:
        exact(deletion,{'phase'});need(deletes and deletion['phase'] in ('issued','complete','failed'))
        if deletion['phase']=='issued':need(delete_result is None)
        else:
            need(delete_result is not None and (deletion['phase']=='complete')==(delete_result==dict(success=True,hasError=False)))
            if deletion['phase']=='complete':need('delete-changes-left' in deletes)
    query_ids=set();query_clock=created
    for query in value['queries']:
        exact(query,{'requestId','clock','operationAlive','deletionAlive','assetPresent','authorization'})
        need(type(query['requestId']) is str and re.fullmatch('ios-'+HEX,query['requestId']) and query['requestId'] not in query_ids
            and type(query['operationAlive']) is bool and type(query['deletionAlive']) is bool and integer(query['authorization'],0,4)
            and (type(query['assetPresent']) is bool if query['authorization']==3 else query['assetPresent'] is None));query_ids.add(query['requestId'])
        stamp(query['clock'],query_clock);query_clock=query['clock']
        expiry=next((row for row in value['events'] if row['kind']=='weak-expired'),None)
        if expiry is not None and query_clock['epochMs']>=expiry['clock']['epochMs']:
            need(not query['operationAlive'])
        expiry=next((row for row in value['events'] if row['kind']=='delete-weak-expired'),None)
        if expiry is not None and query_clock['epochMs']>=expiry['clock']['epochMs']:need(not query['deletionAlive'])
    if previous is not None:
        original(previous);need(all(same(value[k],previous[k]) for k in FIELDS-{'events','queries','phase','resource','byteCount','sha256','deletion'}))
        need(len(value['events'])>=len(previous['events']) and same(value['events'][:len(previous['events'])],previous['events'])
            and len(value['queries'])>=len(previous['queries']) and same(value['queries'][:len(previous['queries'])],previous['queries'])
            and value['byteCount']>=previous['byteCount'])
        if previous['resource'] is not None:need(same(value['resource'],previous['resource']))
        if previous['phase']!='issued':need(value['phase']==previous['phase'] and value['byteCount']==previous['byteCount'] and value['sha256']==previous['sha256'])
        if version>=2 and previous.get('artifactRevision') is not None:need(value['artifactRevision']==previous['artifactRevision'])
        if previous['deletion'] is not None:
            need(value['deletion'] is not None)
            if previous['deletion']['phase']!='issued':need(value['deletion']==previous['deletion'])
    return value


def observation(value,request_id,*,pid,instance,epoch_ms,previous=None):
    original(value,previous);need(value['queries'] and value['processId']==pid and value['instance']==instance)
    if previous is not None:need(len(value['queries'])>len(previous['queries'])
        and all(row['requestId']!=request_id for row in previous['queries']))
    query=value['queries'][-1];need(query['requestId']==request_id and -250<=epoch_ms-query['clock']['epochMs']<=1500)
    stamp(query['clock'],value['events'][-1]['clock'])
    if 'weak-expired' in [row['kind'] for row in value['events']]:need(not query['operationAlive'])
    return value


def saved_original(value,exports,operation_id,raw):
    """Join actual native Photos transaction/asset to independent destination bytes.

    The normal input journal, companion installed identity, fresh observation,
    later Photos deletion and ordinary restoration remain outer responsibilities.
    """
    original(value);transaction=photos_asset(exports,operation_id)
    need(value['phase']=='complete' and value['queries'] and not value['queries'][-1]['operationAlive']
        and value['queries'][-1]['authorization'] in (3,4)
        and any(row['kind']=='weak-expired' for row in value['events'])
        and value['runId']==exports['runId'] and value['basename']==transaction['operation']['fileName']
        and value['photosIdentifier']==transaction['photosIdentifier']
        and type(raw) is bytes and len(raw)==value['byteCount'] and hashlib.sha256(raw).hexdigest()==value['sha256'])
    stamp(value['queries'][-1]['clock'],value['events'][-1]['clock'])
    # The two processes have independent monotonic epochs. Only their original
    # UTC order is comparable; never transplant the client monotonic clock.
    need(value['createdClock']['epochMs']>=transaction['nativeResult']['clock']['epochMs'])
    return dict(iosSnapshotSavedOriginalVersion=1,runId=value['runId'],basename=value['basename'],
        photosIdentifier=value['photosIdentifier'],operationId=operation_id,bytes=len(raw),sha256=value['sha256'],
        destinationInstance=value['instance'],destinationProcessId=value['processId'],
        destinationClock=deepcopy(value['queries'][-1]['clock']),cleanupRequired=True)


def photos_absent(value,exports,operation_id,raw):
    """Actual deletion commit, callback expiry and separate full-access lookup.

    This one native absence still requires the outer quiet window and normal
    input/owned artifact retirement. Limited-library invisibility is refused.
    """
    saved=saved_original(value,exports,operation_id,raw);query=value['queries'][-1]
    need(value['deletion']==dict(phase='complete') and query['authorization']==3
        and query['assetPresent'] is False and not query['deletionAlive']
        and any(row['kind']=='delete-weak-expired' for row in value['events']))
    return dict(iosSnapshotPhotosAbsenceVersion=1,savedOriginal=saved,clock=deepcopy(query['clock']),quietWindowRequired=True)
