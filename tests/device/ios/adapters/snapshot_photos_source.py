"""Actual companion permission and unchanged original byte-chunk contracts."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
import hashlib
import re
from adapters.native_feature_observation import exact,integer,need
from ios.adapters import snapshot_companion_source as companion,snapshot_destination as destination
from ios.adapters.snapshot_destination import stamp,MAX_BYTES

CHUNK_BYTES=512*1024
CHUNK_LIMIT=720896


def permission(value,nonce,*,pid,bundle,previous=None):
    companion.original(value,action='photos',nonce=nonce,pid=pid,bundle=bundle,previous=previous)
    need(value['status']=='ready' and value['readWriteAuthorizationBefore']==value['readWriteAuthorizationAfter']==3)
    return value


def chunk(value,nonce,offset,original,*,pid,previous=None):
    destination.original(original)
    need(original['iosSnapshotDestinationVersion']>=2)
    exact(value,{'snapshotPhotosChunkVersion','nonce','runId','instance','processId','basename','clockBefore','clockAfter',
        'revision','byteCount','sha256','offset','eof','readerClosed','data'})
    need(type(value['snapshotPhotosChunkVersion']) is int and value['snapshotPhotosChunkVersion']==1
        and value['nonce']==nonce and type(nonce) is str and re.fullmatch('ios-[0-9a-f]{32}',nonce)
        and original['phase']=='complete' and value['runId']==original['runId'] and value['instance']==original['instance']
        and type(value['processId']) is int and value['processId']==pid==original['processId'] and value['basename']==original['basename']
        and value['byteCount']==original['byteCount'] and integer(value['byteCount'],1,MAX_BYTES) and value['sha256']==original['sha256']
        and type(value['revision']) is str and re.fullmatch('[a-f0-9]{64}',value['revision']) and value['revision']==original['artifactRevision']
        and type(value['offset']) is int and value['offset']==offset and 0<=offset<value['byteCount'] and offset%CHUNK_BYTES==0
        and type(value['eof']) is bool and value['readerClosed'] is True and type(value['data']) is str and len(value['data'])<=4*((CHUNK_BYTES+2)//3))
    stamp(value['clockBefore']);stamp(value['clockAfter'],value['clockBefore'])
    need(value['clockAfter']['epochMs']-value['clockBefore']['epochMs']<1500 and value['clockAfter']['monotonicMs']-value['clockBefore']['monotonicMs']<1500)
    expired=[event for event in original['events'] if event['kind']=='weak-expired'];need(len(expired)==1);stamp(value['clockBefore'],expired[0]['clock'])
    if original['queries']:stamp(value['clockBefore'],original['queries'][-1]['clock'])
    raw=base64.b64decode(value['data'],validate=True)
    need(base64.b64encode(raw).decode()==value['data'] and len(raw)==min(CHUNK_BYTES,value['byteCount']-offset) and value['eof']==(offset+len(raw)==value['byteCount']))
    if previous is not None:
        need(all(value[key]==previous[key] for key in ('runId','instance','processId','basename','revision','byteCount','sha256'))
            and value['nonce']!=previous['nonce'] and offset==previous['offset']+CHUNK_BYTES);stamp(value['clockBefore'],previous['clockAfter'])
    return raw


def original_bytes(values,original,pid):
    need(type(values) is list and len(values)==(original['byteCount']+CHUNK_BYTES-1)//CHUNK_BYTES)
    output=bytearray();previous=None;nonces=set()
    for value in values:
        need(value['nonce'] not in nonces);nonces.add(value['nonce']);output.extend(chunk(value,value['nonce'],len(output),original,pid=pid,previous=previous));previous=value
    need(len(output)==original['byteCount'] and hashlib.sha256(output).hexdigest()==original['sha256']);return bytes(output)


def retirement(value,nonce,original,raw,*,pid,previous=None):
    """Actual once-only file/journal/run retirement and fresh absence reads."""
    destination.original(original);need(original['iosSnapshotDestinationVersion']>=2 and original['deletion']==dict(phase='complete')
        and original['queries'] and original['queries'][-1]['authorization']==3
        and original['queries'][-1]['assetPresent'] is False and original['queries'][-1]['operationAlive'] is False
        and original['queries'][-1]['deletionAlive'] is False)
    need(type(raw) is bytes and 1<=len(raw)<=262144)
    exact(value,{'snapshotPhotosRetirementVersion','nonce','receipt','clockBefore','clockAfter','runAbsent','originalAbsent','journalAbsent'})
    need(type(value['snapshotPhotosRetirementVersion']) is int and value['snapshotPhotosRetirementVersion']==1
        and type(nonce) is str and re.fullmatch('ios-[a-f0-9]{32}',nonce) and value['nonce']==nonce)
    receipt=value['receipt'];exact(receipt,{'phase','runId','instance','processId','artifactRevision','artifactSha256','byteCount',
        'journalSha256','clockBefore','clockAfter','steps','readersClosed'})
    need(receipt['phase'] in ('complete','failed') and receipt['runId']==original['runId'] and receipt['instance']==original['instance']
        and type(receipt['processId']) is int and receipt['processId']==pid==original['processId']
        and receipt['artifactRevision']==original['artifactRevision'] and receipt['artifactSha256']==original['sha256']
        and type(receipt['byteCount']) is int and receipt['byteCount']==original['byteCount']
        and type(receipt['journalSha256']) is str and re.fullmatch('[a-f0-9]{64}',receipt['journalSha256'])
        and type(receipt['readersClosed']) is bool and type(receipt['steps']) is list
        and receipt['steps']==['original-unlinked','journal-unlinked','run-removed'][:len(receipt['steps'])] and len(receipt['steps'])<=3)
    for before,after in ((receipt['clockBefore'],receipt['clockAfter']),(value['clockBefore'],value['clockAfter'])):
        stamp(before);stamp(after,before);need(after['epochMs']-before['epochMs']<1500 and after['monotonicMs']-before['monotonicMs']<1500)
    stamp(receipt['clockBefore'],original['queries'][-1]['clock']);stamp(value['clockBefore'],receipt['clockAfter'])
    for key in ('runAbsent','originalAbsent','journalAbsent'):need(type(value[key]) is bool)
    if receipt['phase']=='complete':need(receipt['readersClosed'] and len(receipt['steps'])==3
        and receipt['journalSha256']==hashlib.sha256(raw).hexdigest() and all(value[key] for key in ('runAbsent','originalAbsent','journalAbsent')))
    if previous is not None:
        need(value['nonce']!=previous['nonce'] and value['receipt']==previous['receipt']);stamp(value['clockBefore'],previous['clockAfter'])
    return value
