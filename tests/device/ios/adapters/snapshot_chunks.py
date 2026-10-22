"""Fixed bounded version-2 Snapshot byte chunks; legacy reads stay version 1.

These codecs do not acquire originals or supply durable query/file ownership.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
import binascii
import hashlib
import re
from adapters.native_feature_observation import exact,integer,need
from snapshot_file_contract import read_request,MAX_FILE_BYTES,BOUNDED_CHUNK_BYTES

VERSION=2
CHUNK_BYTES=BOUNDED_CHUNK_BYTES
LIMIT=720896


def command(value):
    need(type(value) is dict and type(value.get('schemaVersion')) is int and value['schemaVersion']==VERSION
        and value.get('operation')=='read' and type(value.get('chunkBytes')) is int and value['chunkBytes']==CHUNK_BYTES)
    legacy=dict(value);legacy['schemaVersion']=1;legacy.pop('chunkBytes');read_request(legacy);return value


def packet(value,query,pid):
    command(query);exact(value,{'schemaVersion','commandId','operation','prefix','processId','sampleEpochMs','ok','file'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==VERSION and value['commandId']==query['commandId']
        and value['operation']=='read' and value['prefix']==query['prefix'] and value['ok'] is True and integer(pid,1)
        and type(value['processId']) is int and value['processId']==pid and integer(value['sampleEpochMs'],1))
    row=value['file'];exact(row,{'name','revision','size','offset','eof','data'})
    need(row['name']==query['name'] and row['revision']==query['revision'] and integer(row['size'],0,MAX_FILE_BYTES)
        and type(row['offset']) is int and row['offset']==query['offset']<=row['size'] and type(row['eof']) is bool
        and type(row['data']) is str and len(row['data'])<=4*((CHUNK_BYTES+2)//3))
    try:raw=base64.b64decode(row['data'],validate=True)
    except (ValueError,binascii.Error):need(False)
    need(base64.b64encode(raw).decode()==row['data'] and len(raw)==min(CHUNK_BYTES,row['size']-row['offset'])
        and row['eof']==(row['offset']+len(raw)==row['size']))
    return raw


def original_bytes(row,prefix,originals,pid):
    """Reassemble exact native parts and compare the independent whole hash.

    The caller retains every original query/packet and actual immutable file
    descriptor. This pure join neither installs bytes nor claims current state.
    """
    exact(row,{'name','size','revision','sha256'})
    need(integer(row['size'],0,MAX_FILE_BYTES) and type(row['sha256']) is str and re.fullmatch('[0-9a-f]{64}',row['sha256'])
        and type(originals) is list and len(originals)==max(1,(row['size']+CHUNK_BYTES-1)//CHUNK_BYTES))
    output=bytearray();seen=set();last=0
    for original in originals:
        exact(original,{'query','packet'});query,value=original['query'],original['packet'];raw=packet(value,query,pid)
        need(query['commandId'] not in seen and query['prefix']==prefix and query['name']==row['name']
            and query['revision']==row['revision'] and query['offset']==len(output) and value['file']['size']==row['size']
            and value['sampleEpochMs']>=last)
        seen.add(query['commandId']);last=value['sampleEpochMs'];output.extend(raw)
    need(len(output)==row['size'] and hashlib.sha256(output).hexdigest()==row['sha256']);return bytes(output)
