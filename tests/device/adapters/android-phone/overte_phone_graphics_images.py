"""Original Graphics PNG evidence with durable intent and strict file identity."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
from pathlib import Path
import re
import stat
import time

from adapters.native_feature_observation import exact,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.world_render_evidence import validate as capture_packet,original_pixels,LIMIT
from feature_journeys.contract import identifier

VERSION=1


def record(value):
    exact(value,{'graphicsImageVersion','binding','runId','role','stage','ticket','capture','name','phase','file'})
    need(type(value['graphicsImageVersion']) is int and value['graphicsImageVersion']==VERSION
         and value['role'] in ('primary','actor') and type(value['stage']) is int and value['stage'] in (0,1)
         and value['phase'] in ('planned','opened','saved'))
    context(value['binding']);identifier(value['runId']);identifier(value['ticket'])
    capture=value['capture'];need(type(capture) is dict)
    nonce=identifier(capture.get('requestId'))
    pid=value['binding']['processIdentity'].split(':')[0]
    need(pid.isdigit() and int(pid)>0)
    capture_packet(capture,nonce,int(pid),capture.get('capturedEpochMs'))
    need(capture['source']['captureVersion']==2)
    name='graphics-'+value['runId']+'-'+value['role']+'-'+str(value['stage'])+'-'+nonce+'.png'
    need(value['name']==name and re.fullmatch(r'[a-z0-9-]{1,120}\.png',name))
    if value['phase']=='planned':need(value['file'] is None)
    else:
        exact(value['file'],{'device','inode'})
        need(integer(value['file']['device'],0,2**64-1) and integer(value['file']['inode'],1,2**64-1))
    return value


class PhoneGraphicsImages:
    def __init__(self,root,binding,run,role,stage,guard,intent,*,monotonic=time.monotonic,timeout=5):
        context(binding);identifier(run)
        need(role in ('primary','actor') and type(stage) is int and stage in (0,1)
             and all(callable(v) for v in (guard,intent,monotonic)) and number(timeout,.01,5))
        self.root,self.binding,self.run,self.role,self.stage=Path(root),deepcopy(binding),run,role,stage
        self.guard,self.intent,self.monotonic,self.timeout=guard,intent,monotonic,timeout
        self.last_clock=None
        PrivateFeatureState(self.root/'graphics-evidence-boundary.json')._parent()

    def _path(self,value):
        record(value)
        need(value['binding']==self.binding and value['runId']==self.run and value['role']==self.role and value['stage']==self.stage)
        path=self.root/value['name'];PrivateFeatureState(path)._parent()
        return path

    def _file(self,path,descriptor,value):
        before=os.fstat(descriptor);current=path.lstat()
        for info in (before,current):
            need(stat.S_ISREG(info.st_mode) and info.st_nlink==1 and info.st_size<=LIMIT
                 and (os.name=='nt' or info.st_uid==os.geteuid() and stat.S_IMODE(info.st_mode)==0o600))
        need((before.st_dev,before.st_ino)==(current.st_dev,current.st_ino)
             ==(value['file']['device'],value['file']['inode']))

    def _now(self):
        now=self.monotonic();need(number(now,0,1e15) and (self.last_clock is None or now>=self.last_clock))
        self.last_clock=now;return now

    def _budget(self,started,previous):
        need(self.guard() is not False)
        now=self._now();need(previous<=now and now-started<self.timeout)
        return now

    def read(self,value):
        """Read original bytes in this scope; no fresh product result is created."""
        started=previous=self._now()
        previous=self._budget(started,previous);path=self._path(value)
        need(value['phase'] in ('opened','saved'))
        descriptor=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
        with os.fdopen(descriptor,'rb') as stream:
            self._file(path,stream.fileno(),value)
            raw=stream.read(LIMIT+1);self._file(path,stream.fileno(),value)
        original_pixels(value['capture'],raw)
        self._budget(started,previous)
        return raw

    def write(self,ticket,capture,raw):
        """Persist planned/opened intent before bytes; never overwrite a file."""
        started=previous=self._now();previous=self._budget(started,previous)
        identifier(ticket);need(type(capture) is dict)
        value=dict(graphicsImageVersion=VERSION,binding=deepcopy(self.binding),runId=self.run,role=self.role,stage=self.stage,
            ticket=ticket,capture=deepcopy(capture),name='graphics-'+self.run+'-'+self.role+'-'+str(self.stage)+'-'+str(capture.get('requestId'))+'.png',
            phase='planned',file=None)
        record(value);original_pixels(capture,raw)
        previous=self._budget(started,previous)
        path=self._path(value)
        need(self.intent(deepcopy(value)) is not False);previous=self._budget(started,previous)
        descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o600)
        with os.fdopen(descriptor,'wb') as stream:
            actual=os.fstat(stream.fileno());value.update(phase='opened',file=dict(device=actual.st_dev,inode=actual.st_ino))
            self._file(path,stream.fileno(),value)
            need(self.intent(deepcopy(value)) is not False);previous=self._budget(started,previous)
            need(stream.write(raw)==len(raw));stream.flush();os.fsync(stream.fileno())
            self._file(path,stream.fileno(),value);previous=self._budget(started,previous)
        need(self.read(value)==raw);previous=self._budget(started,previous)
        value['phase']='saved';need(self.intent(deepcopy(value)) is not False)
        self._budget(started,previous)
        return deepcopy(value)

    def absent(self,value):
        started=previous=self._now();previous=self._budget(started,previous);path=self._path(value)
        try:path.lstat()
        except FileNotFoundError:
            self._budget(started,previous);return True
        self._budget(started,previous);return False

    @classmethod
    def archive(cls,root,value):
        """Pure historical file validation: no SDK, repair, input or retiming."""
        record(value)
        reader=cls(root,value['binding'],value['runId'],value['role'],value['stage'],lambda:True,lambda _value:False)
        return reader.read(value)
