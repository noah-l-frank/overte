"""Versioned Close originals: one complete frame, or explicit role fallback.

Only pure serialized capacity selects the layout. A failed original-file or
manifest operation always propagates; it never authorizes another write path.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import zlib

from adapters.chat_journey.source_chunks import ChatSourceChunks, json_digest, VERSION as CHUNK_VERSION
from adapters.native_feature_observation import exact, need, number
from adapters.normal_feature_state import PrivateFeatureState, context
from adapters.pico4.snapshot_originals import nonce
from adapters.pico4.snapshot_upload_originals import SnapshotUploadOriginals, KINDS, ALL_KINDS
from adapters.script_journey.history import canonical, MAX_RAW, MAX_PACKED

VERSION=2
READS=(1,2)


class SnapshotCloseOriginals(SnapshotUploadOriginals):
    VERSION_KEY='snapshotCloseOriginalsVersion'
    VERBS=('close',)

    def __init__(self,path,run,binding,verb):
        need(nonce(run) and verb in self.VERBS);self.root=PrivateFeatureState(path)
        self.disk=self.root.read();self.version=VERSION
        if self.disk is not None:
            self.version=self.disk.get(self.VERSION_KEY)
            need(type(self.version) is int and self.version in READS)
        self.scope={self.VERSION_KEY:self.version,'runId':run,'binding':deepcopy(context(binding)),'role':'snapshot-'+verb}
        self.history=ChatSourceChunks(self.root,self.scope);self.values=[];self.indices={};self.frames={}
        if self.disk is not None:
            exact(self.disk,set(self.scope)|{'phase','chunks'})
            need(all(type(self.disk[key]) is type(value) and self.disk[key]==value for key,value in self.scope.items()) and self.disk['phase']=='reading')
            self.values=self.history.load(self.disk['chunks'])
        else:self.history.inventory(0)
        for index,value in enumerate(self.values):
            self.original(value);digest=json_digest(value);need(digest not in self.indices);self.indices[digest]=index

    def original(self,value):
        json_digest(value);exact(value,{'kind','original'})
        need(type(value['kind']) is str and value['kind'] in (ALL_KINDS if self.version==1 else ALL_KINDS+('fullFrame',)) and type(value['original']) is dict)
        if value['kind']=='fullFrame':self.frame(value['original'])

    @staticmethod
    def frame(row):
        exact(row,set(KINDS)|{'hostMonotonic'})
        need(all(type(row[kind]) is dict for kind in KINDS) and number(row['hostMonotonic'],0,1e15))

    def fits(self,row):
        # No writes and no exception-driven fallback. Reproduce the existing
        # pack and child envelope bounds, including its physical final newline.
        original=dict(kind='fullFrame',original=row);raw=canonical([original])
        if len(raw)>MAX_RAW:return False
        encoded=base64.b64encode(zlib.compress(raw,level=9)).decode('ascii')
        if len(encoded)>MAX_PACKED:return False
        transcript=dict(encoding='zlib-base64-json',bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),data=encoded)
        child=dict(chatSampleChunkVersion=CHUNK_VERSION,scopeSha256=self.history.scope,index=len(self.values),transcript=transcript)
        return len(canonical(child))+1<=65536

    def encode(self,state,*,host_only=False):
        # Reject tuples, subclasses, coerced dictionary keys and nonfinite
        # values over the COMPLETE graph before the first possible write.
        json_digest(state);need(type(host_only) is bool);self.verify()
        need(type(state['frames']) is list)
        for row in state['frames']:self.frame(row)
        if state['received'] is not None:need(type(state['received']) is dict)
        if self.version==1:return super().encode(state,host_only=host_only)
        result=deepcopy(state);references=[]
        for row in state['frames']:
            digest=json_digest(row)
            if digest in self.frames:
                reference=self.frames[digest]
                need(self.decode_frame(reference)==row)
            else:
                # A missing host-only reference must fail before capacity work
                # or any root/child write, including the empty initial root.
                need(not host_only)
                if self.fits(row):reference=dict(fullFrame=self.put('fullFrame',row))
                else:reference=dict(roleFrames={kind:self.put(kind,row[kind]) for kind in KINDS},hostMonotonic=row['hostMonotonic'])
                self.frames[digest]=deepcopy(reference)
            references.append(deepcopy(reference))
        result['frames']=references
        if state['received'] is not None:result['received']=self.put('received',state['received'],host_only=host_only)
        self.verify();return result

    def decode_frame(self,reference):
        need(type(reference) is dict)
        if set(reference)=={'fullFrame'}:row=self.get('fullFrame',reference['fullFrame'])
        else:
            exact(reference,{'roleFrames','hostMonotonic'});exact(reference['roleFrames'],set(KINDS))
            row=dict({kind:self.get(kind,reference['roleFrames'][kind]) for kind in KINDS},hostMonotonic=reference['hostMonotonic'])
        self.frame(row);return row

    def decode(self,state):
        json_digest(state)
        if self.version==1:return super().decode(state)
        self.verify();result=deepcopy(state);need(type(state['frames']) is list);rows=[]
        for reference in state['frames']:
            row=self.decode_frame(reference);digest=json_digest(row)
            if digest in self.frames:need(self.frames[digest]==reference)
            else:self.frames[digest]=deepcopy(reference)
            rows.append(row)
        result['frames']=rows
        if state['received'] is not None:result['received']=self.get('received',state['received'])
        self.verify();return result
