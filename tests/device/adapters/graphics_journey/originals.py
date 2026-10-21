"""Original stereo Graphics PNG/native metadata with durable file identity.

The writer validates storage identity; semantic scene/effect/currentness belongs
exclusively to original native readers and the independent evidence verifier.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import os
from pathlib import Path
import re
import stat
import time
from adapters.native_feature_observation import exact,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.world_render_evidence import validate as capture_packet,original_pixels,LIMIT
from feature_journeys.contract import identifier,json_document,typed_equal
from feature_journeys.stereo_graphics_evidence import FIELDS,SURFACE_FIELDS,LIMIT as METADATA_LIMIT

VERSION=2


def record(value):
    exact(value,{'graphicsOriginalVersion','binding','runId','role','stage','ticket','kind','capture','name','sha256','bytes','phase','file'})
    need(type(value['graphicsOriginalVersion']) is int and value['graphicsOriginalVersion'] in (1,2)
        and type(value['role']) is str and value['role'] in ('primary','actor')
        and type(value['stage']) is int and value['stage'] in (0,1)
        and type(value['kind']) is str and value['kind'] in ('image','file')
        and type(value['phase']) is str and value['phase'] in ('planned','opened','saved'))
    context(value['binding']);identifier(value['runId']);identifier(value['ticket']);capture=value['capture']
    need(type(capture) is dict);nonce=identifier(capture.get('requestId'))
    pid=value['binding']['processIdentity'].split(':')[0];need(pid.isdigit() and int(pid)>0);pid=int(pid)
    capture_packet(capture,nonce,pid,capture.get('capturedEpochMs'),stereo=True,require_cameras=True)
    limit=LIMIT if value['kind']=='image' else METADATA_LIMIT
    need(integer(value['bytes'],1,limit) and type(value['sha256']) is str and re.fullmatch('[0-9a-f]{64}',value['sha256']))
    suffix='.png' if value['kind']=='image' else '.native.json'
    name='graphics-'+value['runId']+'-'+value['role']+'-'+str(value['stage'])+'-'+nonce+suffix
    need(value['name']==name and re.fullmatch(r'[a-z0-9-]{1,120}'+re.escape(suffix),name))
    if value['kind']=='image':need(value['sha256']==capture['source']['image']['sha256'] and value['bytes']==capture['source']['image']['bytes'])
    if value['phase']=='planned':need(value['file'] is None)
    else:
        exact(value['file'],{'device','inode'})
        need(integer(value['file']['device'],0,2**64-1) and integer(value['file']['inode'],1,2**64-1))
    return value


def transition(previous,value):
    """The durable owner must apply this check before accepting a new intent."""
    record(value)
    if previous is None:need(value['phase']=='planned');return
    record(previous)
    need(all(typed_equal(previous[key],value[key]) for key in previous if key not in ('phase','file')))
    phases={'planned':0,'opened':1,'saved':2};a,b=phases[previous['phase']],phases[value['phase']]
    need(b in (a,a+1) and (a==0 or previous['file']==value['file'])
        and (a!=b or typed_equal(previous,value)))


def content(value,raw):
    record(value)
    need(type(raw) is bytes and len(raw)==value['bytes'] and hashlib.sha256(raw).hexdigest()==value['sha256'])
    if value['kind']=='image':original_pixels(value['capture'],raw)
    else:
        body=json_document(raw);version=body.get('stereoGraphicsEvidenceVersion') if type(body) is dict else None
        exact(body,SURFACE_FIELDS if version==2 else FIELDS)
        need(type(body['stereoGraphicsEvidenceVersion']) is int and version in (1,2)
            and all(typed_equal(body[key],value[key]) for key in ('binding','runId','role','stage','ticket','capture')))
    return raw


class GraphicsOriginals:
    def __init__(self,root,binding,run,role,stage,guard,intent,*,monotonic=time.monotonic,timeout=5):
        context(binding);identifier(run)
        need(type(role) is str and role in ('primary','actor') and type(stage) is int and stage in (0,1)
            and all(callable(v) for v in (guard,intent,monotonic)) and number(timeout,.01,5))
        self.root,self.binding,self.run,self.role,self.stage=Path(root),deepcopy(binding),run,role,stage
        self.guard,self.intent,self.monotonic,self.timeout=guard,intent,monotonic,timeout;self.last_clock=None
        PrivateFeatureState(self.root/'graphics-evidence-boundary.json')._parent()

    def _path(self,value):
        record(value)
        need(value['binding']==self.binding and value['runId']==self.run and value['role']==self.role and value['stage']==self.stage)
        path=self.root/value['name'];PrivateFeatureState(path)._parent();return path

    def _file(self,path,descriptor,value):
        before=os.fstat(descriptor);current=path.lstat();limit=LIMIT if value['kind']=='image' else METADATA_LIMIT
        for info in (before,current):
            need(stat.S_ISREG(info.st_mode) and info.st_nlink==1 and info.st_size<=limit
                and (os.name=='nt' or info.st_uid==os.geteuid() and stat.S_IMODE(info.st_mode)==0o600))
        need((before.st_dev,before.st_ino)==(current.st_dev,current.st_ino)==(value['file']['device'],value['file']['inode']))

    def _now(self):
        now=self.monotonic();need(number(now,0,1e15) and (self.last_clock is None or now>=self.last_clock));self.last_clock=now;return now

    def _budget(self,started,previous):
        need(self.guard() is not False);now=self._now();need(previous<=now and now-started<self.timeout);return now

    def read(self,value):
        """Original owned bytes; no current product observation is created."""
        started=previous=self._now();previous=self._budget(started,previous);path=self._path(value)
        need(value['phase'] in ('opened','saved'));limit=LIMIT if value['kind']=='image' else METADATA_LIMIT
        descriptor=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
        with os.fdopen(descriptor,'rb') as stream:
            self._file(path,stream.fileno(),value);raw=stream.read(limit+1);self._file(path,stream.fileno(),value)
        content(value,raw);self._budget(started,previous);return raw

    def write(self,ticket,capture,raw,*,kind='image'):
        """Reserve planned/opened ownership before bytes; never overwrite."""
        started=previous=self._now();previous=self._budget(started,previous);identifier(ticket)
        need(type(capture) is dict and type(raw) is bytes and type(kind) is str and kind in ('image','file'))
        limit=LIMIT if kind=='image' else METADATA_LIMIT;need(0<len(raw)<=limit)
        suffix='.png' if kind=='image' else '.native.json'
        value=dict(graphicsOriginalVersion=VERSION,binding=deepcopy(self.binding),runId=self.run,role=self.role,stage=self.stage,
            ticket=ticket,kind=kind,capture=deepcopy(capture),name='graphics-'+self.run+'-'+self.role+'-'+str(self.stage)+'-'+str(capture.get('requestId'))+suffix,
            sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),phase='planned',file=None)
        content(value,raw);previous=self._budget(started,previous);path=self._path(value)
        need(self.intent(deepcopy(value)) is not False);previous=self._budget(started,previous)
        descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o600)
        with os.fdopen(descriptor,'wb') as stream:
            actual=os.fstat(stream.fileno());value.update(phase='opened',file=dict(device=actual.st_dev,inode=actual.st_ino));self._file(path,stream.fileno(),value)
            need(self.intent(deepcopy(value)) is not False);previous=self._budget(started,previous)
            need(stream.write(raw)==len(raw));stream.flush();os.fsync(stream.fileno());self._file(path,stream.fileno(),value)
            previous=self._budget(started,previous)
        need(self.read(value)==raw);previous=self._budget(started,previous)
        value['phase']='saved';need(self.intent(deepcopy(value)) is not False);self._budget(started,previous);return deepcopy(value)

    def absent(self,value):
        started=previous=self._now();previous=self._budget(started,previous);path=self._path(value)
        try:path.lstat()
        except FileNotFoundError:self._budget(started,previous);return True
        self._budget(started,previous);return False

    @classmethod
    def archive(cls,root,value):
        """Pure historical storage validation, without input, repair or retiming."""
        record(value)
        scope=cls(root,value['binding'],value['runId'],value['role'],value['stage'],lambda:True,lambda _:False)
        return scope.read(value)
