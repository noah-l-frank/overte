"""Immutable bounded carriers for actual iOS PCM bytes; no sound verdicts."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
from adapters.native_feature_observation import exact,integer,need
from adapters.original_frame_store import OriginalFrameStore

CHUNK=64*1024


class AudioPCMOriginals:
    def __init__(self,owner):
        self.owner=owner
        self.files=OriginalFrameStore(owner.root,owner.binding,owner.run,'primary',owner.bound,owner.storage_intent,
            namespace='ios-audio-close' if owner.version==3 else 'ios-audio-pcm',schema_prefix='iosAudioPCM',monotonic=owner.monotonic)
    def read(self,reference):return self.files.read(self.files.expand(reference))
    def write(self,value):
        owner=self.owner;owner.bound();need(owner.state['pending'] is None and len(owner.state['records'])<1024)
        reference=self.files.write(len(owner.state['records'])+1,value)
        owner.state['records'].append(reference);owner.state['pending']=None;owner.save();return reference
    def recover(self):
        owner=self.owner;wire=owner.state['pending']
        if wire is None:return
        need(wire['phase'] in ('opened','saved') and wire['index']==len(owner.state['records'])+1)
        self.files.read(wire);owner.state['records'].append(self.files.compact(dict(wire,phase='saved')))
        owner.state['pending']=None;owner.save()
    def chunks(self,kind,raw):
        need(kind in ('input','sink') and type(raw) is bytes and len(raw)<=32*1024*1024)
        references=[];count=(len(raw)+CHUNK-1)//CHUNK
        for index in range(count):
            part=raw[index*CHUNK:(index+1)*CHUNK]
            value=dict(audioPCMKind='chunk',audioPCMChunkVersion=1,recording=self.owner.recording,kind=kind,index=index,count=count,
                bytes=len(part),sha256=hashlib.sha256(part).hexdigest(),base64=base64.b64encode(part).decode('ascii'))
            references.append(self.write(value))
        return references
    def chunk(self,value):
        exact(value,{'audioPCMKind','audioPCMChunkVersion','recording','kind','index','count','bytes','sha256','base64'})
        need(value['audioPCMKind']=='chunk' and type(value['audioPCMChunkVersion']) is int and value['audioPCMChunkVersion']==1
            and value['recording']==self.owner.recording and value['kind'] in ('input','sink')
            and integer(value['count'],1,512) and integer(value['index'],0,value['count']-1) and integer(value['bytes'],1,CHUNK)
            and type(value['base64']) is str)
        raw=base64.b64decode(value['base64'],validate=True)
        need(len(raw)==value['bytes'] and hashlib.sha256(raw).hexdigest()==value['sha256']
            and base64.b64encode(raw).decode('ascii')==value['base64'])
        return raw
    def pcm(self,snapshot,kind):
        references=snapshot['chunks'][kind];need(type(references) is list and len(references)<=512)
        parts=[]
        for index,reference in enumerate(references):
            value=self.read(reference);raw=self.chunk(value)
            need(value['kind']==kind and value['index']==index and value['count']==len(references)
                and (index==len(references)-1 or len(raw)==CHUNK));parts.append(raw)
        raw=b''.join(parts);expected=snapshot['packet']['source'][kind]
        need(len(raw)==expected['bytes'] and hashlib.sha256(raw).hexdigest()==expected['sha256']);return raw
    def inventory(self,state):
        expected={self.files.path(self.files.expand(reference)) for reference in state['records']}|{self.owner.store.path}
        if state['pending'] is not None:expected.add(self.files.path(state['pending']))
        for index,path in enumerate(self.owner.root.iterdir()):
            need(index<8192)
            if path.name.startswith('ios-audio-close-' if self.owner.version==3 else 'ios-audio-pcm-'):need(path in expected)
