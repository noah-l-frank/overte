"""Passive Assets Layout2 range windows; no source/producer adoption."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
import hashlib
import os
import re
import stat
from copy import deepcopy

from adapters.chat_journey.archive_file import signature,ClosedOriginalFile
from adapters.native_fd_owner import OriginalDescriptor
from adapters.native_feature_observation import exact,integer,need,number
from adapters.pico4.audio_pc_originals import AudioPCRawOriginals
from adapters.pico4.assets_raw_ranges import reference,compact_reference,scope,MAX_LITERAL,AUX
from adapters.script_journey.history import canonical,MAX_FRAMES
from adapters.chat_journey.source_chunks import json_digest
from feature_journeys.contract import json_document


UNRESOLVED=[]


def checksum(value):
    need(type(value) is str and re.fullmatch('[0-9a-f]{64}',value));return value


def physical(value,*,mode=None,empty=True):
    need(type(value) is list and len(value)==8 and all(type(v) is int and 0<=v<2**64 for v in value)
        and value[1]>0 and stat.S_ISREG(value[2]) and value[3]==os.geteuid() and value[4]==1
        and integer(value[5],0 if empty else 1,65536))
    if mode is not None:need(stat.S_IMODE(value[2])==mode)


def pending_token(value,expected_sha,path,reads):
    exact(value,{'read','role','command','limit','parts','scopeSha256','rootPath','hostMonotonic','thread','sideBytes'})
    need(integer(value['read'],0,reads-1) and type(value['role']) is str and re.fullmatch('[a-z-]{1,32}',value['role'])
        and type(value['command']) is dict and len(canonical(value['command']))<=4096
        and integer(value['limit'],1,MAX_LITERAL) and type(value['parts']) is int
        and value['parts']==(value['limit']+65535)//65536+1 and value['scopeSha256']==expected_sha
        and value['rootPath']==str(path) and number(value['hostMonotonic'],0,1e15)
        and integer(value['thread'],1) and integer(value['sideBytes'],0,2*(11*48000*2*2+44)))
    json_digest(value['command'])


def control(value,expected,path):
    exact(value,{'audioRawJournalVersion','scope','state'})
    need(type(value['audioRawJournalVersion']) is int and value['audioRawJournalVersion']==1 and canonical(value['scope'])==canonical(expected))
    state=value['state'];exact(state,{'reads','pending','parts','pages'})
    need(integer(state['reads'],0,MAX_FRAMES) and type(state['pending']) is list and len(state['pending'])<=MAX_FRAMES
        and type(state['parts']) is list and len(state['parts'])<=MAX_FRAMES
        and type(state['pages']) is list and len(state['pages'])<=(MAX_FRAMES+31)//32)
    seen=set();digest=json_digest(expected)
    for token in state['pending']:
        pending_token(token,digest,path,state['reads']);need(token['read'] not in seen);seen.add(token['read'])
    for index,row in enumerate(state['parts']):
        exact(row,{'bytes','sha256','physical','closed'});checksum(row['sha256'])
        need(type(row['closed']) is bool and integer(row['bytes'],1 if row['closed'] else 0,65536)
            and (row['closed'] or index==len(state['parts'])-1))
        physical(row['physical'],mode=0o400 if row['closed'] else 0o600);need(row['physical'][5]==row['bytes'])
    seen=[]
    for page in state['pages']:
        exact(page,{'page','sha256','physical'});checksum(page['sha256']);physical(page['physical'],mode=0o600,empty=False)
        need(integer(page['page'],0,(MAX_FRAMES-1)//32) and page['page'] not in seen);seen.append(page['page'])
    need(seen==sorted(seen));return state


def index_receipts(value,page,sha,state):
    exact(value,{'audioRawRangeIndexVersion','scopeSha256','page','receipts'})
    need(type(value['audioRawRangeIndexVersion']) is int and value['audioRawRangeIndexVersion']==1
        and value['scopeSha256']==sha and type(value['page']) is int and value['page']==page
        and type(value['receipts']) is list and len(value['receipts'])==32)
    for slot,row in enumerate(value['receipts']):
        if row is None:continue
        exact(row,{'read','role','command','hostMonotonic','returnedHostMonotonic','kind','bytes','sha256','ranges'})
        need(integer(row['read'],0,state['reads']-1) and row['read']==page*32+slot and row['kind']=='bytes'
            and type(row['role']) is str and re.fullmatch('[a-z-]{1,32}',row['role'])
            and type(row['command']) is dict and len(canonical(row['command']))<=4096
            and number(row['hostMonotonic'],0,1e15) and number(row['returnedHostMonotonic'],row['hostMonotonic'],1e15)
            and integer(row['bytes'],0,MAX_LITERAL) and type(row['ranges']) is list and len(row['ranges'])<=65)
        checksum(row['sha256']);json_digest(row['command']);previous=-1;total=0
        for part in row['ranges']:
            need(type(part) is list and len(part)==3)
            item,start,size=part
            need(integer(item,0,len(state['parts'])-1) and item>previous and integer(start,0,65535)
                and integer(size,1,65536-start) and start+size<=state['parts'][item]['bytes'])
            previous=item;total+=size
        need(total==row['bytes'])


class AssetsRangeOriginals:
    def __init__(self,parent):
        self.parent=parent;self.path=parent.store.path.with_name(parent.store.path.name+'.child-raw2')
        self.raw=None;self.control=None;self.acquired_control=None
        try:
            self.control=ClosedOriginalFile(self.path,0o600,parent.directory_guard)
            raw,physical_root=self.control.read();self.acquired_control=raw
            admitted=json_document(raw);need(canonical(admitted)+b'\n'==raw)
            control(admitted,scope(parent.history_scope),self.path)
            self.raw=object.__new__(AudioPCRawOriginals)
            AudioPCRawOriginals.__init__(self.raw,self.path)
            need(canonical(self.raw.disk)+b'\n'==raw and self.raw.root.stamp==physical_root)
            for page in self.raw.state['pages']:
                original=self.raw.files.get(self.path.name+f'.index-{page["page"]:02d}.json')
                need(original is not None)
                index_receipts(json_document(original.raw),page['page'],self.raw.scope_sha,self.raw.state)
        except BaseException:
            UNRESOLVED.append(self);raise
        exact(self.raw.state,{'reads','pending','parts','pages'})
        need(self.raw.disk['scope']==scope(parent.history_scope) and integer(self.raw.state['reads'],0,MAX_FRAMES)
            and type(self.raw.state['pending']) is list and type(self.raw.state['parts']) is list
            and len(self.raw.state['parts'])<=MAX_FRAMES and type(self.raw.state['pages']) is list
            and len(self.raw.state['pages'])<=(MAX_FRAMES+31)//32)
        self.pinned=deepcopy(self.raw.disk);self.parts=tuple(self.raw.recorded_parts)
        self.verify()

    def verify(self):
        self.raw.guard();original,unused=self.control.read();value,unused=self.raw.root.read()
        need(value==original==canonical(self.pinned)+b'\n')
        for name,owner in self.raw.files.items():
            if type(owner) is OriginalDescriptor:
                owner.require(owner.fd);actual=os.pread(owner.fd,65537,0)
                need(actual==b'' and signature(os.fstat(owner.fd))==signature((self.path.parent/name).lstat()))
                owner.require(owner.fd)
            else:
                actual,physical=owner.read()
                if name.startswith(self.path.name+'.part-'):
                    index=int(name.rsplit('-',1)[1].split('.',1)[0])
                    # Unconfirmed tails remain explicitly unavailable; never
                    # replace the original prefix with later current bytes.
                    need(index<len(self.parts) and actual==self.parts[index])
                elif name==self.path.name:need(actual==canonical(self.pinned)+b'\n')
        self.raw.guard()

    def literal(self,value):
        self.verify();compact_reference(value)
        need(value['read'] in self.raw.receipts);record=self.raw.receipts[value['read']]
        tail=None if value['tailBundle'] is None else self.parent.bundle(value['tailBundle'])
        value=dict(assetsRawLiteralVersion=2,scopeSha256=self.parent.history.scope,read=value['read'],
            bytes=record['bytes']+(0 if tail is None else tail['bytes']),sha256=value['sha256'],tailBundle=value['tailBundle'],
            rangeOriginal=dict(audioRawRangeVersion=1,scopeSha256=self.raw.scope_sha,read=value['read'],sha256=record['sha256']))
        reference(value,self.parent.history.scope)
        need(value['rangeOriginal']['scopeSha256']==self.raw.scope_sha)
        raw=self.raw.literal(value['rangeOriginal']);need(type(raw) is bytes)
        if value['tailBundle'] is not None:
            tail=self.parent.bundle(value['tailBundle']);exact(tail,{'assetsRawWireTailVersion','read','bytes','sha256','data'})
            need(type(tail['assetsRawWireTailVersion']) is int and tail['assetsRawWireTailVersion']==1
                and tail['read']==value['read'] and integer(tail['bytes'],1,AUX) and type(tail['data']) is str)
            extra=base64.b64decode(tail['data'],validate=True)
            need(base64.b64encode(extra).decode('ascii')==tail['data'] and len(extra)==tail['bytes']
                and hashlib.sha256(extra).hexdigest()==tail['sha256']);raw+=extra
        need(len(raw)==value['bytes'] and hashlib.sha256(raw).hexdigest()==value['sha256']);self.verify();return raw

    def bill(self):
        return dict(parts=len(self.raw.files),bytes=sum((self.path.parent/name).stat().st_size for name in self.raw.files),
            pending=self.raw.pending)

    def close(self):
        results=[]
        for owner in (self.control,self.raw):
            if owner is not None:
                try:results.append(owner.close())
                except BaseException:results.append(False)
        return all(results)
