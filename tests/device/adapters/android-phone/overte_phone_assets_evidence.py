"""Assets use the existing immutable private original/PNG engines."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from overte_phone_create_evidence import CreateOriginals,CreateImages
from collections import OrderedDict
import hashlib
import json
import os
import threading
from overte_phone_emote_originals import LIMIT
from overte_phone_script_history import canonical,same

class AssetsOriginals(CreateOriginals):
    KINDS=frozenset({'assets','assets-input','assets-retirement'})
    _parsed=OrderedDict()
    _parsed_bytes=0
    _parsed_lock=threading.RLock()
    def read(self,value):
        # Cache only JSON parsing of immutable historical bytes. Every call
        # still reads and hashes the entire actual file, checks both original
        # inode boundaries, owner/mode/link count and both live five-second
        # guards. Cached values never replace a fresh native observation.
        started=self.now();self.bound(started);path=self.path(value);need(value['phase'] in ('opened','saved'))
        descriptor=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        with os.fdopen(descriptor,'rb') as stream:
            self.file(path,stream.fileno(),value);raw=stream.read(LIMIT+1);self.file(path,stream.fileno(),value)
        need(len(raw)==value['bytes'] and hashlib.sha256(raw).hexdigest()==value['sha256'])
        key=(str(path),value['file']['device'],value['file']['inode'],value['sha256'],sha_binding(self.binding))
        with AssetsOriginals._parsed_lock:
            body=AssetsOriginals._parsed.get(key)
            if body is None:
                body=json.loads(raw.decode('utf-8'));need(canonical(body)==raw)
                exact(body,{'emoteFrameVersion','kind','binding','runId','role','index','frame'})
                need(type(body['emoteFrameVersion']) is int and body['emoteFrameVersion']==1 and same(body['binding'],self.binding)
                    and body['kind']==self.kind and body['runId']==self.run and body['role']==self.role and type(body['index']) is int and body['index']==value['index'] and type(body['frame']) is dict)
                while AssetsOriginals._parsed and AssetsOriginals._parsed_bytes+len(raw)>16*1024*1024:
                    _old,(_body,size)=AssetsOriginals._parsed.popitem(last=False);AssetsOriginals._parsed_bytes-=size
                AssetsOriginals._parsed[key]=(body,len(raw));AssetsOriginals._parsed_bytes+=len(raw)
            else:body=body[0];AssetsOriginals._parsed.move_to_end(key)
        self.bound(started);return deepcopy(body['frame'])

def sha_binding(value):return hashlib.sha256(canonical(value)).hexdigest()

class AssetsImages(CreateImages):
    KIND='assets'

from copy import deepcopy
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import context
from feature_journeys.contract import identifier
from overte_phone_assets_source import validate as download_packet
from overte_phone_assets_backend import bytes_for

class AssetsDownload(CreateImages):
    """Same exclusive inode/prefix engine, retaining original downloaded glTF."""
    KIND='assets-download'
    LIMIT=1048576
    @classmethod
    def valid_stage(cls,stage):return integer(stage,1,256)
    @classmethod
    def record(cls,value):
        exact(value,{'assetsDownloadVersion','binding','runId','role','stage','ticket','download','name','phase','file'})
        need(type(value['assetsDownloadVersion']) is int and value['assetsDownloadVersion']==1 and value['role'] in ('primary','actor') and cls.valid_stage(value['stage'])
            and value['phase'] in ('planned','opened','saved'));context(value['binding']);identifier(value['runId']);identifier(value['ticket'])
        packet=value['download'];pid=int(value['binding']['processIdentity'].split(':')[0])
        download_packet(packet,dict(schemaVersion=1,commandId=packet['requestId'],action='phone-assets-download',runId=value['runId'],hash=packet['source']['hash']),pid,packet['capturedEpochMs'])
        need(value['name']=='assets-download-'+value['runId']+'-'+value['role']+'-'+str(value['stage'])+'-'+packet['requestId']+'.gltf')
        if value['phase']=='planned':need(value['file'] is None)
        else:exact(value['file'],{'device','inode'});need(integer(value['file']['device'],0,2**64-1) and integer(value['file']['inode'],1,2**64-1))
        return value
    def value(self,ticket,packet):
        return dict(assetsDownloadVersion=1,binding=deepcopy(self.binding),runId=self.run,role=self.role,stage=self.stage,ticket=ticket,download=deepcopy(packet),
            name='assets-download-'+self.run+'-'+self.role+'-'+str(self.stage)+'-'+packet['requestId']+'.gltf',phase='planned',file=None)
    def content(self,value,raw):need(raw==bytes_for(value['download'],value['download']['source']['hash']))
