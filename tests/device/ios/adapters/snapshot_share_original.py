"""Separate original Share file bytes, never an activity-sheet success receipt.

Installed extension/archive identities, normal input ownership and subsequent
process/quiet cleanup remain the enclosing feature owner's responsibilities.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import re
from adapters.native_feature_observation import decode,exact,integer,need
from adapters.script_feature.history import same
from ios.adapters.snapshot_destination import stamp,MAX_BYTES,HEX
from ios.adapters.snapshot_exports import FILE_NAME,original as export_original,outcome,history

VERSION=1
IMPORT_VERSION=1
FIELDS={'iosSnapshotShareOriginalVersion','runId','basename','instance','processId','receiverBundleId','clockDomain',
    'createdClock','phase','artifact','attachmentCount','registeredTypes','selectedType','receivedFilename','byteCount','sha256','events','queries'}
MUTABLE={'phase','receivedFilename','byteCount','sha256','events','queries'}
BUNDLE=r'[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+'


def original(value,previous=None):
    exact(value,FIELDS)
    need(type(value['iosSnapshotShareOriginalVersion']) is int and value['iosSnapshotShareOriginalVersion']==VERSION
        and type(value['runId']) is str and re.fullmatch(HEX,value['runId'])
        and type(value['instance']) is str and re.fullmatch(HEX,value['instance']) and integer(value['processId'],1)
        and type(value['receiverBundleId']) is str and re.fullmatch(BUNDLE,value['receiverBundleId'])
        and value['clockDomain']=='native-share-extension' and value['artifact']=='original.bytes'
        and type(value['basename']) is str and re.fullmatch(FILE_NAME,value['basename'])
        and value['basename'].startswith('parity-'+value['runId'][:16]+'-')
        and type(value['attachmentCount']) is int and value['attachmentCount']==1
        and value['phase'] in ('issued','complete','failed') and integer(value['byteCount'],0,MAX_BYTES)
        and type(value['sha256']) is str)
    types=value['registeredTypes'];need(type(types) is list and 1<=len(types)<=32
        and all(type(v) is str and 1<=len(v)<=256 and all(ord(c)>=32 for c in v) for v in types)
        and len(set(types))==len(types) and value['selectedType'] in types)
    # The native producer selects an actual advertised concrete UTType. The
    # host independently closes the supported filename/type correspondence.
    supported={'png':'public.png','jpg':'public.jpeg','jpeg':'public.jpeg','gif':'com.compuserve.gif','webp':'org.webmproject.webp'}
    need(value['selectedType']==supported[value['basename'].rsplit('.',1)[1]])
    need(value['receivedFilename'] is None or value['receivedFilename']==value['basename'])
    created=stamp(value['createdClock']);need(type(value['events']) is list and 1<=len(value['events'])<=512
        and type(value['queries']) is list and len(value['queries'])<=128)
    expected=['read-issued','callback-enter'];kinds=[];clock=created
    for index,event in enumerate(value['events'],1):
        exact(event,{'sequence','kind','clock'});need(type(event['sequence']) is int and event['sequence']==index)
        stamp(event['clock'],clock);clock=event['clock'];kind=event['kind']
        if index<=2:need(kind==expected[index-1])
        elif index==3:need(kind in ('read-completed','read-failed'))
        else:need(index<=6 and kind=={4:'callback-left',5:'weak-expired',6:'finish-issued'}[index])
        kinds.append(kind)
    complete='read-completed' in kinds;failed='read-failed' in kinds
    need((value['phase']=='complete')==complete and (value['phase']=='failed')==failed)
    if complete:need(value['receivedFilename']==value['basename'] and value['byteCount']>0 and re.fullmatch('[0-9a-f]{64}',value['sha256']))
    else:need(value['byteCount']==0 and value['sha256']=='')
    if 'finish-issued' in kinds:need(complete)
    query_clock=created;nonces=set();expiry=next((row['clock'] for row in value['events'] if row['kind']=='weak-expired'),None)
    for query in value['queries']:
        exact(query,{'requestId','clock','operationAlive'})
        need(type(query['requestId']) is str and re.fullmatch('ios-'+HEX,query['requestId']) and query['requestId'] not in nonces
            and type(query['operationAlive']) is bool);nonces.add(query['requestId']);stamp(query['clock'],query_clock);query_clock=query['clock']
        if expiry is not None and query_clock['epochMs']>=expiry['epochMs']:need(not query['operationAlive'])
        if not query['operationAlive']:need(expiry is not None);stamp(query_clock,expiry)
        if 'finish-issued' in kinds:need(query_clock['epochMs']<=value['events'][-1]['clock']['epochMs'])
    if 'finish-issued' in kinds:need(any(not query['operationAlive'] for query in value['queries']))
    if previous is not None:
        original(previous);need(all(same(value[k],previous[k]) for k in FIELDS-MUTABLE))
        for key in ('events','queries'):need(len(value[key])>=len(previous[key]) and same(value[key][:len(previous[key])],previous[key]))
        if previous['phase']!='issued':need(all(same(value[k],previous[k]) for k in ('phase','receivedFilename','byteCount','sha256')))
        if previous['receivedFilename'] is not None:need(value['receivedFilename']==previous['receivedFilename'])
    return value


def observation(value,request_id,*,pid,instance,epoch_ms,previous=None):
    original(value,previous);need(value['queries'] and value['processId']==pid and value['instance']==instance)
    if previous is not None:need(len(value['queries'])>len(previous['queries'])
        and all(row['requestId']!=request_id for row in previous['queries']))
    query=value['queries'][-1];need(query['requestId']==request_id and integer(epoch_ms,1)
        and -250<=epoch_ms-query['clock']['epochMs']<=1500);stamp(query['clock'],value['events'][-1]['clock'])
    return value


def received_original(value,exports,operation_id,raw,capture_raw):
    """Join two actual original byte streams and both native process histories.

    capture_raw must come from the outer owned Snapshot file acquisition, not an
    expected encoder or a picture synthesized from test settings.
    """
    original(value);export_original(exports);result=outcome(exports,operation_id)
    need(result['operation']['action']=='share' and result['nativeResult']['detail']==dict(status='success',hasError=False)
        and value['phase']=='complete' and value['runId']==exports['runId'] and value['basename']==result['operation']['fileName']
        and value['queries'] and not value['queries'][-1]['operationAlive']
        and len(value['events'])>=5 and value['events'][4]['kind']=='weak-expired'
        and type(raw) is bytes and type(capture_raw) is bytes and raw==capture_raw
        and len(raw)==value['byteCount'] and hashlib.sha256(raw).hexdigest()==value['sha256'])
    _owners,events,_depth=history(exports['source']);rows=events[operation_id]
    shown=[row for row in rows if row['kind']=='share-presentation-requested'];done=[row for row in rows if row['kind']=='share-completed']
    need(len(shown)==len(done)==1 and done[0]['detail']==dict(completed=True,hasError=False)
        and shown[0]['clock']['epochMs']<=value['createdClock']['epochMs']
        and value['events'][4]['clock']['epochMs']<=done[0]['clock']['epochMs'])
    # Distinct native processes have distinct monotonic epochs. Compare UTC
    # ordering across them, keeping every original monotonic clock unchanged.
    stamp(value['queries'][-1]['clock'],value['events'][4]['clock'])
    return dict(iosSnapshotSharedOriginalVersion=1,runId=value['runId'],basename=value['basename'],operationId=operation_id,
        bytes=len(raw),sha256=value['sha256'],receiverBundleId=value['receiverBundleId'],receiverInstance=value['instance'],
        receiverProcessId=value['processId'],receiverClock=deepcopy(value['queries'][-1]['clock']),
        extensionCompletionRequired=True,cleanupRequired=True)


def imported_original(value,metadata,raw,*,pid,bundle_id,receiver_bundle_id):
    """Verify unchanged extension metadata and bytes exposed by its archive app.

    A completed import is a transfer provenance, not a fresh extension query or
    proof that the extension process disappeared. Installed-code admission and
    candidate-bound AFC acquisition remain mandatory outer obligations.
    """
    exact(value,{'iosSnapshotShareImportVersion','runId','phase','clockBefore','clockAfter','instance','processId','bundleId',
        'clockDomain','originalMetadataSha256','byteCount','sha256'})
    need(type(value['iosSnapshotShareImportVersion']) is int and value['iosSnapshotShareImportVersion']==IMPORT_VERSION
        and value['phase']=='complete' and value['processId']==pid and integer(pid,1)
        and value['bundleId']==bundle_id and type(bundle_id) is str and re.fullmatch(BUNDLE,bundle_id)
        and value['clockDomain']=='native-share-archive' and type(value['instance']) is str and re.fullmatch(HEX,value['instance'])
        and type(metadata) is bytes and len(metadata)<=262144 and type(raw) is bytes
        and value['originalMetadataSha256']==hashlib.sha256(metadata).hexdigest()
        and integer(value['byteCount'],1,MAX_BYTES) and value['byteCount']==len(raw)
        and value['sha256']==hashlib.sha256(raw).hexdigest())
    stamp(value['clockBefore']);stamp(value['clockAfter'],value['clockBefore']);packet=decode(metadata.decode('utf-8'))
    original(packet);need(packet['runId']==value['runId'] and packet['receiverBundleId']==receiver_bundle_id
        and packet['sha256']==value['sha256'] and packet['byteCount']==value['byteCount']
        and packet['events'][-1]['kind']=='finish-issued'
        and packet['events'][-1]['clock']['epochMs']<=value['clockBefore']['epochMs'])
    return deepcopy(packet)
