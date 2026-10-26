"""Anchored unchanged Share archive chunks, preserving native original clocks."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
import re
from adapters.native_feature_observation import exact,need
from ios.adapters.snapshot_destination import stamp
from ios.adapters import snapshot_share_original as share


CHUNK_BYTES=512*1024
CHUNK_LIMIT=720896


def chunk(value,nonce,offset,imported,metadata,*,pid,bundle_id,receiver_bundle_id,previous=None):
    share.imported_metadata(imported,metadata,pid=pid,bundle_id=bundle_id,receiver_bundle_id=receiver_bundle_id)
    need(imported['iosSnapshotShareImportVersion']>=2)
    exact(value,{'snapshotShareChunkVersion','nonce','runId','instance','processId','basename','clockDomain','clockBefore','clockAfter',
        'revision','byteCount','sha256','offset','eof','readerClosed','data'})
    need(type(value['snapshotShareChunkVersion']) is int and value['snapshotShareChunkVersion']==1
        and type(nonce) is str and re.fullmatch('ios-[a-f0-9]{32}',nonce) and value['nonce']==nonce
        and all(value[key]==imported[key] for key in ('runId','instance','basename','byteCount','sha256'))
        and type(value['processId']) is int and value['processId']==pid and type(value['byteCount']) is int and value['clockDomain']=='native-share-archive'
        and value['revision']==imported['artifactRevision'] and type(value['offset']) is int and value['offset']==offset
        and 0<=offset<value['byteCount'] and offset%CHUNK_BYTES==0 and type(value['eof']) is bool and value['readerClosed'] is True
        and type(value['data']) is str and len(value['data'])<=4*((CHUNK_BYTES+2)//3))
    stamp(value['clockBefore'],imported['clockAfter']);stamp(value['clockAfter'],value['clockBefore'])
    need(value['clockAfter']['epochMs']-value['clockBefore']['epochMs']<1500 and value['clockAfter']['monotonicMs']-value['clockBefore']['monotonicMs']<1500)
    raw=base64.b64decode(value['data'],validate=True)
    need(base64.b64encode(raw).decode()==value['data'] and len(raw)==min(CHUNK_BYTES,value['byteCount']-offset)
        and value['eof']==(offset+len(raw)==value['byteCount']))
    if previous is not None:
        need(all(value[key]==previous[key] for key in ('runId','instance','processId','basename','revision','byteCount','sha256'))
            and value['nonce']!=previous['nonce'] and offset==previous['offset']+CHUNK_BYTES);stamp(value['clockBefore'],previous['clockAfter'])
    return raw


def original_bytes(values,imported,metadata,*,pid,bundle_id,receiver_bundle_id):
    need(type(values) is list and len(values)==(imported['byteCount']+CHUNK_BYTES-1)//CHUNK_BYTES)
    output=bytearray();previous=None;nonces=set()
    for value in values:
        need(value['nonce'] not in nonces);nonces.add(value['nonce'])
        output.extend(chunk(value,value['nonce'],len(output),imported,metadata,pid=pid,bundle_id=bundle_id,receiver_bundle_id=receiver_bundle_id,previous=previous));previous=value
    raw=bytes(output);share.imported_original(imported,metadata,raw,pid=pid,bundle_id=bundle_id,receiver_bundle_id=receiver_bundle_id)
    return raw
