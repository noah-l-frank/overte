"""One verified immutable raw-part pass shared by Lifecycle layouts3/4.

No query, source clock, manifest confirmation or live adoption occurs here.
Callers admit the complete batch budget and original namespace before entry.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import os
from adapters.chat_journey.archive_file import signature
from adapters.chat_journey.source_chunks import json_digest
from adapters.native_feature_observation import LIMIT,exact,integer,need,number
from adapters.observer_return import state as file_state
from adapters.pico4.audio_raw_archive import AudioRawArchive
from adapters.script_journey.history import canonical

BACKGROUND_ROLES=('ui','gesture','drive','background','feature')
SOURCE_ROLES4=(*BACKGROUND_ROLES,'pending')
SOURCE_ROLES4_PENDING=(*SOURCE_ROLES4,'pending-wire')
PENDING_WIRE_LIMIT=32768+4096


def record_literal(record,*,index,roles,parts):
    exact(record,{'read','role','command','hostMonotonic','returnedHostMonotonic','kind','bytes','sha256','ranges'})
    need(type(record['read']) is int and record['read']==index
        and type(record['role']) is str and record['role'] in roles and type(record['command']) is dict
        and number(record['hostMonotonic'],0,1e15)
        and number(record['returnedHostMonotonic'],record['hostMonotonic'],1e15)
        and record['kind'] in ('utf8','none','bytes')
        and integer(record['bytes'],0,32768 if record['role']=='pending' else
            PENDING_WIRE_LIMIT if record['role']=='pending-wire' else LIMIT)
        and type(record['ranges']) is list)
    json_digest(record['command']);pieces=[]
    for row in record['ranges']:
        need(type(row) is list and len(row)==3);part,start,size=row
        need(integer(part,0,len(parts)-1) and integer(start,0,len(parts[part]))
            and integer(size,1,len(parts[part])-start));pieces.append(parts[part][start:start+size])
    literal=b''.join(pieces)
    need(len(literal)==record['bytes'] and hashlib.sha256(literal).hexdigest()==record['sha256'])
    if record['kind']=='none':need(literal==b'')
    if record['kind']=='utf8':literal.decode('utf-8')
    return literal


def verified_ranges(archive,*,roles,materialize,pending_bodies=()):
    need(type(archive) is AudioRawArchive and type(roles) is tuple
        and roles in (BACKGROUND_ROLES,SOURCE_ROLES4,SOURCE_ROLES4_PENDING) and type(materialize) is bool)
    archive.lock.assert_held()
    if roles==BACKGROUND_ROLES:need(type(archive.scope.get('lifecycleBackgroundOriginalsVersion')) is int and archive.scope['lifecycleBackgroundOriginalsVersion']==3)
    else:
        need(type(archive.scope.get('lifecycleSourceRawVersion')) is int and archive.scope['lifecycleSourceRawVersion']==4)
        if roles==SOURCE_ROLES4_PENDING:
            need(type(archive.scope.get('pendingNativeReadVersion')) is int and archive.scope['pendingNativeReadVersion']==1)
        else:need('pendingNativeReadVersion' not in archive.scope)
    need(type(pending_bodies) is tuple and len(pending_bodies)<=512)
    selected={}
    if pending_bodies:
        from adapters.pico4.lifecycle_pending_read import body_key,body_original
        need(roles is SOURCE_ROLES4_PENDING)
        for reference in pending_bodies:
            identity=body_key(reference);read=identity[2]
            need(identity[1]==archive.scope_sha and read not in selected)
            selected[read]=reference
    parts=[]
    for index,row in enumerate(archive.state['parts']):
        if row['closed']:
            raw,physical=archive.closed[index].read()
        else:
            owner=archive.writer;owner.require(owner.fd)
            raw=os.pread(owner.fd,65537,0);physical=signature(os.fstat(owner.fd));owner.require(owner.fd)
        need(physical==row['physical'] and len(raw)==row['bytes']
            and hashlib.sha256(raw).hexdigest()==row['sha256'])
        parts.append(raw)
    for index,(expected,physical) in archive.page_pins.items():
        actual,raw,stamp=file_state(archive.page_store(index))
        need(actual==expected and raw==canonical(expected)+b'\n' and stamp==physical)
    by_read={};records={}
    for page,value in sorted(archive.pages.items()):
        for position,record in enumerate(value['receipts']):
            if record is None:continue
            literal=record_literal(record,index=page*32+position,roles=roles,parts=parts)
            if record['read'] in selected:
                body_original(literal,selected[record['read']],record=record,scope_sha=archive.scope_sha,run=archive.scope['runId'])
            records[record['read']]=record
            if materialize:
                by_read[record['read']]=literal
    need(all(read in records for read in selected))
    return by_read,records
