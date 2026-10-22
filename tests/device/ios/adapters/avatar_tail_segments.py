"""Bounded private byte segments for actual Avatar tail originals only.

No native fact, timestamp, input acknowledgement or resource absence is made.
The caller durably retains every parent and child transition before proceeding.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import binascii
import hashlib
import os
import re
from adapters.native_feature_observation import exact,integer,need
from adapters.original_file_reads import record
from adapters.original_frame_store import OriginalFrameStore,MAX_FRAMES
from adapters.script_feature.history import same

VERSION=1
CHUNK_BYTES=524288
LIMIT=4*1024*1024
LABELS={'scripts','http','people','uikit','geometry','partial','record'}


def sha(raw):return hashlib.sha256(raw).hexdigest()


class AvatarTailSegments:
    def __init__(self,root,binding,run,role,subject,guard,intent,*,monotonic):
        need(subject in ('primary','actor') and callable(intent));self.subject,self.intent=subject,intent
        self.store=OriginalFrameStore(root,binding,run,role,guard,self.transition,
            namespace='avatar-'+subject+'-tail-parts',schema_prefix='avatarTailSegment',monotonic=monotonic)
        self.writing=None

    def parent(self,value):
        exact(value,{'avatarTailSegmentsVersion','label','tag','bytes','sha256','first','chunks','complete'})
        need(type(value['avatarTailSegmentsVersion']) is int and value['avatarTailSegmentsVersion']==VERSION
            and value['label'] in LABELS and type(value['tag']) is str and re.fullmatch('[0-9a-f]{64}',value['tag'])
            and integer(value['bytes'],0,LIMIT) and type(value['sha256']) is str and re.fullmatch('[0-9a-f]{64}',value['sha256'])
            and integer(value['first'],1,MAX_FRAMES) and type(value['chunks']) is list and type(value['complete']) is bool)
        count=max(1,(value['bytes']+CHUNK_BYTES-1)//CHUNK_BYTES)
        need(value['first']+count-1<=MAX_FRAMES and len(value['chunks'])<=count)
        for index,chunk in enumerate(value['chunks']):
            self.store.original(chunk);need(chunk['index']==value['first']+index)
            if index<len(value['chunks'])-1:need(chunk['phase']=='saved')
        if value['complete']:need(len(value['chunks'])==count and all(row['phase']=='saved' for row in value['chunks']))
        return value

    def transition(self,kind,reference):
        need(kind=='original' and self.writing is not None);self.store.original(reference);value=self.writing
        offset=reference['index']-value['first'];need(integer(offset,0,len(value['chunks'])))
        if offset==len(value['chunks']):need(reference['phase']=='planned');value['chunks'].append(deepcopy(reference))
        else:
            old=value['chunks'][offset]
            need(all(reference[key]==old[key] for key in old if key not in ('phase','file'))
                and (old['phase'],reference['phase']) in (('planned','opened'),('opened','saved'))
                and (old['file'] is None or old['file']==reference['file']))
            value['chunks'][offset]=deepcopy(reference)
        self.parent(value);need(self.intent(deepcopy(value)) is not False)

    def write(self,label,tag,raw,first):
        need(type(raw) is bytes and self.writing is None)
        value=dict(avatarTailSegmentsVersion=VERSION,label=label,tag=tag,bytes=len(raw),sha256=sha(raw),first=first,chunks=[],complete=False)
        self.parent(value);need(self.intent(deepcopy(value)) is not False);self.writing=value
        try:
            count=max(1,(len(raw)+CHUNK_BYTES-1)//CHUNK_BYTES)
            for index in range(count):
                offset=index*CHUNK_BYTES;body=dict(avatarTailSegmentBodyVersion=VERSION,subject=self.subject,label=label,tag=tag,
                    parentBytes=len(raw),parentSha256=sha(raw),offset=offset,data=base64.b64encode(raw[offset:offset+CHUNK_BYTES]).decode())
                self.store.write(first+index,body)
            value['complete']=True;self.parent(value);need(self.intent(deepcopy(value)) is not False)
            need(self.read(value)==raw);return deepcopy(value)
        finally:self.writing=None

    def inspect(self,value):
        """Actual opened-file prefixes; no file is created or acknowledgement inferred."""
        self.parent(value);rows=[]
        for ref in value['chunks']:
            path=self.store.path(ref)
            if ref['phase']=='planned':need(not os.path.lexists(path));rows.append(None);continue
            descriptor=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
            with os.fdopen(descriptor,'rb') as stream:
                self.store.file(path,stream.fileno(),ref);raw=stream.read(ref['bytes']+1);self.store.file(path,stream.fileno(),ref)
            need(len(raw)<=ref['bytes']);record(path)
            complete=len(raw)==ref['bytes'] and sha(raw)==ref['sha256']
            need(ref['phase']!='saved' or complete)
            rows.append(dict(bytes=len(raw),sha256=sha(raw),complete=complete))
        return rows

    def retained(self,value,snapshots):
        """Revalidate exactly frozen partial bytes; never manufacture a full raw."""
        need(type(snapshots) is list and same(self.inspect(value),snapshots))
        if len(snapshots)==max(1,(value['bytes']+CHUNK_BYTES-1)//CHUNK_BYTES) and all(row is not None and row['complete'] for row in snapshots):
            self.read(value)
        return deepcopy(snapshots)

    def read(self,value):
        self.parent(value);snapshots=self.inspect(value)
        count=max(1,(value['bytes']+CHUNK_BYTES-1)//CHUNK_BYTES)
        need(len(value['chunks'])==count and all(row is not None and row['complete'] for row in snapshots))
        output=bytearray()
        for ref in value['chunks']:
            body=self.store.read(ref);exact(body,{'avatarTailSegmentBodyVersion','subject','label','tag','parentBytes','parentSha256','offset','data'})
            need(type(body['avatarTailSegmentBodyVersion']) is int and body['avatarTailSegmentBodyVersion']==VERSION
                and body['subject']==self.subject and body['label']==value['label'] and body['tag']==value['tag']
                and type(body['parentBytes']) is int and body['parentBytes']==value['bytes'] and body['parentSha256']==value['sha256']
                and type(body['offset']) is int and body['offset']==len(output) and type(body['data']) is str)
            try:raw=base64.b64decode(body['data'],validate=True)
            except (ValueError,binascii.Error):need(False)
            need(base64.b64encode(raw).decode()==body['data'] and len(raw)==min(CHUNK_BYTES,value['bytes']-len(output)))
            output.extend(raw)
        need(len(output)==value['bytes'] and sha(output)==value['sha256']);return bytes(output)
