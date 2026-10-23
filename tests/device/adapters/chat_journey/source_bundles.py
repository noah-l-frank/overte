"""Lossless original JSON bundles in the existing bounded immutable chunks.

No source acquisition, current observation, receipt adoption or limit increase.
All parts consume the existing physical frame/raw budgets; logical originals
also retain the original aggregate uncompressed JSON budget.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
import hashlib
import json
import re
import zlib

from adapters.chat_journey.source_chunks import ChatSourceChunks,digest
from adapters.chat_journey.observation_cursor import plain
from adapters.native_feature_observation import exact,integer,need
from adapters.script_journey.history import canonical,unpack,MAX_FRAMES,MAX_RAW,MAX_PACKED

VERSION=1
PART_BYTES=MAX_PACKED//2


def reference(value):
    exact(value,{'parts','bytes','sha256'})
    need(integer(value['parts'],1,MAX_FRAMES) and integer(value['bytes'],1,MAX_RAW-2)
        and type(value['sha256']) is str and re.fullmatch('[0-9a-f]{64}',value['sha256']))
    return value


def logical_bytes(references):
    need(type(references) is list and len(references)<=MAX_FRAMES)
    total=2;parts=0
    for index,value in enumerate(references):
        reference(value);total+=value['bytes']+(1 if index else 0);parts+=value['parts']
        need(total<=MAX_RAW and parts<=MAX_FRAMES)
    return total


def prepare(value,sequence,references):
    need(integer(sequence,0,MAX_FRAMES-1) and sequence==len(references))
    logical_bytes(references);plain(value);raw=canonical(value)
    encoded=base64.b64encode(zlib.compress(raw,level=9)).decode('ascii')
    parts=[encoded[offset:offset+PART_BYTES] for offset in range(0,len(encoded),PART_BYTES)]
    ref=dict(parts=len(parts),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
    logical_bytes([*references,ref])
    return ref,[dict(sourceBundlePartVersion=VERSION,bundle=sequence,part=index,parts=len(parts),data=data)
        for index,data in enumerate(parts)]


def decode_parts(parts,ref,sequence):
    reference(ref);need(type(parts) is list and len(parts)==ref['parts'] and integer(sequence,0,MAX_FRAMES-1))
    for index,part in enumerate(parts):
        exact(part,{'sourceBundlePartVersion','bundle','part','parts','data'})
        need(type(part['sourceBundlePartVersion']) is int and part['sourceBundlePartVersion']==VERSION
            and type(part['bundle']) is int and part['bundle']==sequence
            and type(part['part']) is int and part['part']==index
            and type(part['parts']) is int and part['parts']==ref['parts']
            and type(part['data']) is str and 0<len(part['data'])<=PART_BYTES
            and (index==len(parts)-1 or len(part['data'])==PART_BYTES))
    encoded=''.join(part['data'] for part in parts);compressed=base64.b64decode(encoded,validate=True)
    need(base64.b64encode(compressed).decode('ascii')==encoded)
    decoder=zlib.decompressobj();raw=decoder.decompress(compressed,ref['bytes']+1)
    need(len(raw)==ref['bytes'] and decoder.eof and not decoder.unused_data and not decoder.unconsumed_tail
        and hashlib.sha256(raw).hexdigest()==ref['sha256'])
    value=json.loads(raw);need(canonical(value)==raw)
    return value,raw


def original(history,manifest,references,index):
    """Only the same original parts, re-read in full under their actual stamps."""
    need(type(history) is ChatSourceChunks and type(manifest) is list and type(references) is list
        and integer(index,0,len(references)-1))
    logical_bytes(references);need(sum(value['parts'] for value in references)==len(manifest)==len(history.identities))
    history.verify();start=sum(value['parts'] for value in references[:index]);parts=[]
    for position in range(start,start+references[index]['parts']):
        need(history.signature(position)==history.identities[position])
        value=history.store(position).read()
        need(digest(value)==manifest[position] and history.signature(position)==history.identities[position])
        exact(value,{'chatSampleChunkVersion','scopeSha256','index','transcript'})
        need(type(value['chatSampleChunkVersion']) is int and value['chatSampleChunkVersion']==1
            and type(value['index']) is int and value['index']==position and value['scopeSha256']==history.scope)
        decoded=unpack(value['transcript']);need(len(decoded)==1);parts.append(decoded[0])
    result=decode_parts(parts,references[index],index);history.verify();return result
