"""Passive Audio1/2 history, including explicitly uncertain open raw tails.

No live owner, candidate/native query, input, append, adoption or resume method
exists here. Legacy1 can expose only originals it actually retained.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import json
import os
from pathlib import Path
from adapters.chat_journey.archive_file import ClosedOriginalFile,signature
from adapters.chat_journey.source_chunks import ChatSourceChunks,json_digest
from adapters.native_fd_owner import OriginalDescriptor,require_directory
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_journey.history import canonical,unpack,MAX_FRAMES
from adapters.pico4.audio_raw_archive import PART,PAGE,VERSION as RAW_VERSION

UNRESOLVED_ORIGINALS=[]


class AudioPCRawOriginals:
    historical_only=True
    def __init__(self,path):
        self.path=Path(path);self.directory=OriginalDescriptor(self.path.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
        self.files={};self.uncertain=[];self.recorded_parts=[]
        try:self.read_originals()
        except BaseException:
            try:closed=self.close()
            except BaseException:closed=False
            if not closed:UNRESOLVED_ORIGINALS.append(self)
            raise
    def read_originals(self):
        self.root=self.file(self.path.name,0o600);raw,stamp=self.root.read();self.disk=json.loads(raw)
        exact(self.disk,{'audioRawJournalVersion','scope','state'});need(type(self.disk['audioRawJournalVersion']) is int and self.disk['audioRawJournalVersion']==RAW_VERSION)
        need(canonical(self.disk)+b'\n'==raw);self.scope_sha=json_digest(self.disk['scope']);self.state=self.disk['state']
        self.receipts={}
        for page_ref in self.state['pages']:
            exact(page_ref,{'page','sha256','physical'})
            index=page_ref['page'];need(integer(index,0,(MAX_FRAMES-1)//PAGE))
            name=self.path.name+f'.index-{index:02d}.json';source=self.file(name,0o600);content,physical=source.read();value=json.loads(content)
            exact(value,{'audioRawRangeIndexVersion','scopeSha256','page','receipts'})
            need(type(value['audioRawRangeIndexVersion']) is int and value['audioRawRangeIndexVersion']==RAW_VERSION
                and integer(value['page'],0,(MAX_FRAMES-1)//PAGE) and value['scopeSha256']==self.scope_sha and value['page']==index
                and type(value['receipts']) is list and len(value['receipts'])==PAGE)
            if physical!=page_ref['physical'] or json_digest(value)!=page_ref['sha256']:
                self.uncertain.append(dict(unconfirmedIndex=index,actualPhysical=physical,actualSha256=hashlib.sha256(content).hexdigest()))
                continue
            for row in value['receipts']:
                if row is not None:need(row['read'] not in self.receipts);self.receipts[row['read']]=row
        for index,row in enumerate(self.state['parts']):
            name=self.path.name+f'.part-{index:03d}.bin';path=self.path.parent/name
            actual=signature(path.lstat())
            if not row['closed'] and actual[5]==0:
                self.guard();owner=OriginalDescriptor(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
                try:
                    owner.require(owner.fd);content=os.pread(owner.fd,PART+1,0);physical=signature(os.fstat(owner.fd))
                    need(content==b'' and physical==actual==signature(path.lstat()));self.guard();owner.require(owner.fd)
                finally:need(owner.close())
                self.files[name]=owner
            else:
                source=self.file(name,0o400 if row['closed'] else 0o600);content,physical=source.read()
            if actual[:2]!=row['physical'][:2]:
                self.uncertain.append(dict(foreignPart=index,actualPhysical=physical));self.recorded_parts.append(b'');continue
            need(len(content)<=PART and len(content)>=row['bytes'] and hashlib.sha256(content[:row['bytes']]).hexdigest()==row['sha256'])
            if row['closed']:need(actual==row['physical'] and len(content)==row['bytes'])
            elif actual!=row['physical'] or len(content)!=row['bytes']:
                self.uncertain.append(dict(part=index,confirmedPrefixBytes=row['bytes'],unconfirmedTailBytes=len(content)-row['bytes'],actualPhysical=physical))
            self.recorded_parts.append(content[:row['bytes']])
        expected=set(self.files)
        for path in self.path.parent.glob(self.path.name+'.*'):
            if path.name not in expected:self.uncertain.append(dict(unconfirmedFile=path.name,physical=signature(path.lstat())))
        self.pending=bool(self.state['pending']) or bool(self.uncertain)
    def guard(self):require_directory(self.directory,self.path.parent)
    def file(self,name,mode):
        need(name not in self.files);value=ClosedOriginalFile(self.path.parent/name,mode,self.guard);self.files[name]=value;return value
    def literal(self,reference):
        exact(reference,{'audioRawRangeVersion','scopeSha256','read','sha256'})
        need(reference['scopeSha256']==self.scope_sha and type(reference['audioRawRangeVersion']) is int
            and reference['audioRawRangeVersion']==RAW_VERSION and integer(reference['read'],0,self.state['reads']-1))
        need(reference['read'] in self.receipts);row=self.receipts[reference['read']];need(row['sha256']==reference['sha256'])
        raw=b''.join(self.recorded_parts[index][offset:offset+count] for index,offset,count in row['ranges'])
        need(len(raw)==row['bytes'] and hashlib.sha256(raw).hexdigest()==row['sha256'])
        return None if row['kind']=='none' else raw.decode('utf-8') if row['kind']=='utf8' else raw
    def report(self):return dict(historicalOnly=True,liveAuthority=False,pendingOrUncertain=self.pending,unconfirmed=self.uncertain,
        durableRawReceipts=len(self.receipts),openParts=sum(not row['closed'] for row in self.state['parts']),literalCompletenessGuaranteed=not self.pending)
    def close(self):return all([source.close() for source in self.files.values()]+[self.directory.close()])


class AudioPCActorOriginals:
    historical_only=True
    def __init__(self,path):
        self.path=Path(path);self.directory=OriginalDescriptor(self.path.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
        self.root=ClosedOriginalFile(self.path,0o600,lambda:require_directory(self.directory,self.path.parent))
        raw,stamp=self.root.read();self.disk=json.loads(raw);need(canonical(self.disk)+b'\n'==raw)
        self.version=self.disk['audioPCActorVersion'];need(type(self.version) is int and self.version in (1,2,3,4))
        self.history=ChatSourceChunks(PrivateFeatureState(self.path),self.disk['scope']);self.frames=self.history.load(self.disk['chunks'])
        self.state=unpack(self.disk['payload'])[0];self.raws=None
        if self.version>=2:self.raws=AudioPCRawOriginals(self.path.with_name('audio-recipe-pc-raw.json'))
    def original(self,index):
        from copy import deepcopy
        from adapters.native_feature_observation import decode
        need(integer(index,0,len(self.frames)-1));self.history.verify();frame=deepcopy(self.frames[index])
        if self.version>=2:
            if 'observationBundleRaw' in frame:
                from feature_journeys.contract import json_document
                need(self.version in (3,4) and type(self.disk['scope'].get('audioObservationBundleVersion')) is int
                    and self.disk['scope']['audioObservationBundleVersion']==1)
                frame['bundle']=json_document(self.raws.literal(frame.pop('observationBundleRaw')))
                for name in ('native','settings','pages'):frame[name]=decode(frame['bundle'][name+'Raw'])
            if 'packetsRaw' in frame:
                need(self.version==4 and type(self.disk['scope'].get('audioPreviewSourceBatchVersion')) is int
                    and self.disk['scope']['audioPreviewSourceBatchVersion']==2)
                raw=self.raws.literal(frame.pop('packetsRaw'));batch=decode(raw.decode('utf-8') if type(raw) is bytes else raw)
                from adapters.pico4.audio_pc_batch import packets as original_packets
                frame['packets']={row['captureId']:row for row in original_packets(batch)}
            for name in ('native','settings','pages','packet'):
                key=name+'Raw'
                if key in frame:
                    raw=self.raws.literal(frame.pop(key));frame[name]=decode(raw.decode('utf-8') if type(raw) is bytes else raw)
        return frame
    def report(self):return dict(historicalOnly=True,liveAuthority=False,actorVersion=self.version,frames=len(self.frames),
        completeRawTransport=False if self.raws is None else self.raws.report()['literalCompletenessGuaranteed'],
        pending=self.state['pending'] is not None)
    def close(self):return all([self.root.close(),self.directory.close()]+([] if self.raws is None else [self.raws.close()]))
