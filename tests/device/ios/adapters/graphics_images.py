"""Original WDA screen PNGs with separate host/native clocks and durable files.

The PNG has no GPU frame ID or native capture timestamp. Those cannot be
invented here: the feature owner must bracket this acquisition with original
completed frames, actual geometry/settings and challenge/subject pixels.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
from io import BytesIO
import os
from pathlib import Path
import stat
import time
import uuid

from adapters.native_feature_observation import exact,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack,unpack,same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier

VERSION=1
LIMIT=24*1024*1024


def pixels(raw):
    from PIL import Image
    need(type(raw) is bytes and 0<len(raw)<=LIMIT and raw[:8]==b'\x89PNG\r\n\x1a\n' and raw[-8:-4]==b'IEND')
    with Image.open(BytesIO(raw)) as image:
        need(image.format=='PNG' and image.mode in ('RGB','RGBA') and integer(image.width,1,4096)
             and integer(image.height,1,4096) and image.width*image.height<=8388608)
        image.load();return [image.width,image.height]


def capture_record(value,raw=None):
    exact(value,{'screenCaptureVersion','requestId','source','transport','sessionId','processId',
        'nativeBeforeMs','nativeAfterMs','hostBeginEpochMs','hostEndEpochMs','hostBeginMonotonic','hostEndMonotonic',
        'bytes','sha256','extent'})
    need(type(value['screenCaptureVersion']) is int and value['screenCaptureVersion']==VERSION
         and value['source']=='native-screen' and value['transport']=='webdriveragent-original-png'
         and type(value['requestId']) is str and value['requestId'].startswith('ios-'))
    identifier(value['requestId'][4:])
    need(type(value['sessionId']) is str and 0<len(value['sessionId'])<=160 and integer(value['processId'],1)
         and integer(value['nativeBeforeMs'],1) and integer(value['nativeAfterMs'],value['nativeBeforeMs'])
         and value['nativeAfterMs']-value['nativeBeforeMs']<1500
         and integer(value['hostBeginEpochMs'],1) and integer(value['hostEndEpochMs'],value['hostBeginEpochMs'])
         and number(value['hostBeginMonotonic'],0,1e15)
         and number(value['hostEndMonotonic'],value['hostBeginMonotonic'],1e15))
    elapsed=(value['hostEndMonotonic']-value['hostBeginMonotonic'])*1000
    need(elapsed<1500 and abs(value['hostEndEpochMs']-value['hostBeginEpochMs']-elapsed)<=250
         and abs(value['nativeAfterMs']-value['nativeBeforeMs']-elapsed)<=250
         and integer(value['bytes'],1,LIMIT) and type(value['sha256']) is str)
    need(len(value['sha256'])==64 and all(c in '0123456789abcdef' for c in value['sha256']))
    extent=value['extent'];need(type(extent) is list and len(extent)==2
        and all(integer(v,1,4096) for v in extent) and extent[0]*extent[1]<=8388608)
    if raw is not None:
        need(pixels(raw)==extent and len(raw)==value['bytes'] and hashlib.sha256(raw).hexdigest()==value['sha256'])
    return value


class IOSGraphicsImages:
    def __init__(self,store,root,binding,run,role,stage,client,clock_ms,guard,*,source_lock=None,
                 epoch_ms=lambda:int(time.time()*1000),monotonic=time.monotonic):
        self.store,self.root,self.binding=store,Path(root),deepcopy(context(binding))
        self.run,self.role,self.stage=identifier(run),role,stage
        need(role in ('primary','actor') and type(stage) is int and stage in (0,1)
             and all(callable(fn) for fn in (clock_ms,guard,epoch_ms,monotonic)) and callable(getattr(client,'call',None)))
        self.client,self.clock_ms,self.guard,self.epoch_ms,self.monotonic=client,clock_ms,guard,epoch_ms,monotonic
        self.last_clock=None
        self.lock=source_lock or ScriptSourceLock(store.path.with_name('script-feature-sources.lock'))
        need(isinstance(self.lock,ScriptSourceLock) and self.lock.path==store.path.with_name('script-feature-sources.lock'))
        PrivateFeatureState(self.root/'graphics-image-boundary.json')._parent()

    def _path(self,row):
        identifier(row['nonce']);need(row['name']=='graphics-'+self.run+'-'+self.role+'-'+str(self.stage)+'-'+row['nonce']+'.png')
        path=self.root/row['name'];PrivateFeatureState(path)._parent();return path

    def _load(self):
        self.lock.assert_held();need(self.guard() is not False)
        self.state=self.store.read();self.rows=[]
        if self.state is None:return
        exact(self.state,{'graphicsScreenImagesVersion','binding','runId','role','stage','root','transcript'})
        need(type(self.state['graphicsScreenImagesVersion']) is int and self.state['graphicsScreenImagesVersion']==VERSION
             and same(self.state['binding'],self.binding) and self.state['runId']==self.run and self.state['role']==self.role
             and type(self.state['stage']) is int and self.state['stage']==self.stage and self.state['root']==str(self.root))
        self.rows=unpack(self.state['transcript']);seen=set()
        for row in self.rows:
            exact(row,{'nonce','name','ticket','phase','file','capture'})
            identifier(row['ticket']);self._path(row);need(row['nonce'] not in seen);seen.add(row['nonce'])
            need(row['phase'] in ('planned','opened','saved','removed'))
            if row['file'] is None:need(row['phase'] in ('planned','removed'))
            else:
                exact(row['file'],{'device','inode'})
                need(integer(row['file']['device'],0,2**64-1) and integer(row['file']['inode'],1,2**64-1))
            if row['capture'] is not None:
                capture_record(row['capture']);need(row['capture']['sessionId']==self.binding['sessionId']
                    and row['capture']['processId']==int(self.binding['processIdentity'])
                    and row['capture']['requestId']=='ios-'+row['nonce'] and row['phase'] in ('saved','removed'))
            if row['phase']=='saved':need(row['file'] is not None and row['capture'] is not None)

    def _write(self):
        need(same(self.store.read(),self.state) and self.guard() is not False)
        value=dict(graphicsScreenImagesVersion=VERSION,binding=self.binding,runId=self.run,role=self.role,stage=self.stage,
                   root=str(self.root),transcript=pack(self.rows))
        self.store.write(value,self.state);need(same(self.store.read(),value));self.state=deepcopy(value)

    def _file(self,row,descriptor):
        path=self._path(row);before=os.fstat(descriptor);current=path.lstat()
        need(row['file'] is not None)
        for info in (before,current):
            need(stat.S_ISREG(info.st_mode) and info.st_nlink==1 and info.st_uid==os.geteuid()
                 and stat.S_IMODE(info.st_mode)==0o600 and info.st_size<=LIMIT)
        need((before.st_dev,before.st_ino)==(current.st_dev,current.st_ino)==(row['file']['device'],row['file']['inode']))

    def _clock(self):
        current=self.monotonic();need(number(current,0,1e15) and (self.last_clock is None or current>=self.last_clock))
        self.last_clock=current;return current

    def _budget(self,started):
        current=self._clock();need(current-started<1.5 and self.guard() is not False)

    def capture(self,ticket):
        try:
            with self.lock.held():
                self._load();identifier(ticket);need(all(row['phase'] in ('saved','removed') for row in self.rows))
                started=self._clock()
                row=dict(nonce=uuid.uuid4().hex,ticket=ticket,phase='planned',file=None,capture=None)
                row['name']='graphics-'+self.run+'-'+self.role+'-'+str(self.stage)+'-'+row['nonce']+'.png'
                self.rows.append(row);self._write();self._budget(started)
                descriptor=os.open(self._path(row),os.O_WRONLY|os.O_CREAT|os.O_EXCL|getattr(os,'O_NOFOLLOW',0),0o600)
                with os.fdopen(descriptor,'wb') as stream:
                    info=os.fstat(stream.fileno());row.update(phase='opened',file=dict(device=info.st_dev,inode=info.st_ino))
                    self._write();self._file(row,stream.fileno());self._budget(started)
                    native_before=self.clock_ms();host_begin=self.epoch_ms();mono_begin=self._clock();self._budget(started)
                    encoded=self.client.call('GET','/session/'+self.binding['sessionId']+'/screenshot')
                    need(type(encoded) is str and len(encoded)<=4*((LIMIT+2)//3));raw=base64.b64decode(encoded,validate=True)
                    extent=pixels(raw);host_end=self.epoch_ms();mono_end=self._clock();native_after=self.clock_ms()
                    packet=dict(screenCaptureVersion=VERSION,requestId='ios-'+row['nonce'],source='native-screen',
                        transport='webdriveragent-original-png',sessionId=self.binding['sessionId'],processId=int(self.binding['processIdentity']),
                        nativeBeforeMs=native_before,nativeAfterMs=native_after,hostBeginEpochMs=host_begin,hostEndEpochMs=host_end,
                        hostBeginMonotonic=mono_begin,hostEndMonotonic=mono_end,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),extent=extent)
                    capture_record(packet,raw);self._budget(started)
                    need(stream.write(raw)==len(raw));stream.flush();os.fsync(stream.fileno());self._file(row,stream.fileno())
                row.update(phase='saved',capture=packet);self._write();self._budget(started)
                need(self._read(row)==raw);self._budget(started)
                return deepcopy(row),raw
        except Exception:
            raise NativeUIError('Original iOS screen acquisition failed; file responsibility is retained') from None

    def _read(self,row):
        need(row['phase']=='saved')
        descriptor=os.open(self._path(row),os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
        with os.fdopen(descriptor,'rb') as stream:
            self._file(row,stream.fileno());before=os.fstat(stream.fileno());raw=stream.read(LIMIT+1)
            self._file(row,stream.fileno());after=os.fstat(stream.fileno())
            need((before.st_size,before.st_mtime_ns,before.st_ctime_ns)==(after.st_size,after.st_mtime_ns,after.st_ctime_ns))
        capture_record(row['capture'],raw);return raw

    def archive(self,nonce):
        """Read stored original bytes; never a fresh capture or product verdict."""
        with self.lock.held():
            self._load();rows=[row for row in self.rows if row['nonce']==nonce];need(len(rows)==1)
            return self._read(rows[0])

    def cleanup(self):
        """Remove only recorded file inodes and observe actual path absence."""
        try:
            with self.lock.held():
                started=self._clock()
                self._load()
                for row in self.rows:
                    need(self._clock()-started<20 and self.guard() is not False)
                    path=self._path(row)
                    try:
                        descriptor=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0)|getattr(os,'O_NONBLOCK',0))
                    except FileNotFoundError:descriptor=None
                    if descriptor is not None:
                        with os.fdopen(descriptor,'rb') as stream:
                            need(row['phase']!='removed')
                            self._file(row,stream.fileno());path.unlink()
                    try:path.lstat()
                    except FileNotFoundError:pass
                    else:need(False)
                    row['phase']='removed';self._write()
                    need(self._clock()-started<20 and self.guard() is not False)
                return all(row['phase']=='removed' for row in self.rows)
        except Exception:
            raise NativeUIError('Original screen file cleanup is unresolved; ownership is retained') from None
