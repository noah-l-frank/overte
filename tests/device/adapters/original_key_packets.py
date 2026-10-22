"""Closed immutable carriers for original global Qt key/IME packets.

The caller owns acquisition, nonce admission, native clocks and any cleanup
interpretation. This helper makes no SDK request and changes no native DTO.
Large raw carriers use the existing original-file limit, not private metadata.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import decode,exact,need
from adapters.normal_feature_state import context
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.history import same
from feature_journeys.contract import identifier
from ios.adapters import world_web_keys

VERSION=1
PROFILES={'avatar':'avatar','emote':'emote','worldweb':'worldWeb'}


class OriginalKeyPackets:
    def __init__(self,root,binding,run,role,subject,guard,intent,*,profile,monotonic=None):
        need(profile in PROFILES and role in ('primary','actor') and subject in ('primary','actor') and callable(guard) and callable(intent))
        self.profile,self.binding,self.run,self.role,self.subject=profile,deepcopy(context(binding)),identifier(run),role,subject
        prefix='world-web' if profile=='worldweb' else profile
        kwargs={} if monotonic is None else dict(monotonic=monotonic)
        self.originals=OriginalFrameStore(root,binding,run,role,guard,intent,namespace=prefix+'-'+subject+'-keys',
            schema_prefix=PROFILES[profile]+subject.title()+'KeysRaw',**kwargs)

    def original(self,value):return self.originals.original(value)

    def write(self,index,query,raw):
        world_web_keys.command(query);need(query['runId']==self.run and type(raw) is str and len(raw.encode())<=world_web_keys.LIMIT)
        # A stale AFC response can predate this source's privacy boundary.
        # Validate unchanged bytes before creating even a planned host file.
        packet=decode(raw,limit=world_web_keys.LIMIT);world_web_keys.privacy_qualified(packet)
        world_web_keys.validate(packet,query,int(self.binding['processIdentity']))
        compact=self.originals.write(index,dict(nativeKeysRawVersion=VERSION,profile=self.profile,runId=self.run,role=self.role,subject=self.subject,
            binding=deepcopy(self.binding),query=deepcopy(query),raw=raw))
        return self.originals.expand(compact)

    def inspect_partial(self,original):
        import os,base64,hashlib
        self.original(original);need(original['phase'] in ('opened','saved'));path=self.originals.path(original)
        descriptor=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
        with os.fdopen(descriptor,'rb') as stream:
            self.originals.file(path,stream.fileno(),original);raw=stream.read(original['bytes']+1);self.originals.file(path,stream.fileno(),original)
        need(len(raw)<=original['bytes']);complete=len(raw)==original['bytes'] and hashlib.sha256(raw).hexdigest()==original['sha256']
        if original['phase']=='saved':need(complete)
        return dict(file=deepcopy(original['file']),bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),contentBase64=base64.b64encode(raw).decode(),complete=complete)

    def read(self,original):
        value=self.originals.read(original);exact(value,{'nativeKeysRawVersion','profile','runId','role','subject','binding','query','raw'})
        need(type(value['nativeKeysRawVersion']) is int and value['nativeKeysRawVersion']==VERSION and value['profile']==self.profile
            and value['runId']==self.run and value['role']==self.role and value['subject']==self.subject and same(value['binding'],self.binding)
            and type(value['raw']) is str and len(value['raw'].encode())<=world_web_keys.LIMIT)
        world_web_keys.command(value['query']);need(value['query']['runId']==self.run);return value

    def packet(self,original):
        value=self.read(original);packet=decode(value['raw'],limit=world_web_keys.LIMIT)
        return world_web_keys.validate(packet,value['query'],int(self.binding['processIdentity']))
