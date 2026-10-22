"""Private original Audio evidence bytes, with durable creation/deletion intent."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import io
import os
from pathlib import Path
import stat
import time
import wave
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState,context
from feature_journeys.contract import identifier

LIMIT=32*1024*1024


def wav(raw,rate,channels):
    need(type(raw) is bytes and 0<len(raw)<=LIMIT and integer(rate,8000,48000) and integer(channels,1,2) and len(raw)%(channels*2)==0)
    output=io.BytesIO()
    with wave.open(output,'wb') as stream:stream.setparams((channels,2,rate,0,'NONE','not compressed'));stream.writeframes(raw)
    return output.getvalue()


def record(value):
    exact(value,{'audioFileVersion','binding','provenance','runId','role','ticket','kind','sourceId','name','bytes','sha256','phase','file'})
    context(value['binding']);need(type(value['provenance']) is dict)
    need(type(value['audioFileVersion']) is int and value['audioFileVersion']==1 and value['role'] in ('primary','actor') and value['kind'] in ('input','sink','peer') and value['phase'] in ('planned','opened','saved','retiring','retired') and integer(value['bytes'],1,LIMIT))
    for key in ('runId','ticket','sourceId'):identifier(value[key])
    need(value['name']=='audio-'+value['runId']+'-'+value['role']+'-'+value['sourceId']+'-'+value['kind']+'.wav' and type(value['sha256']) is str and len(value['sha256'])==64 and all(c in '0123456789abcdef' for c in value['sha256']))
    if value['phase']=='planned':need(value['file'] is None)
    else:
        exact(value['file'],{'device','inode'});need(integer(value['file']['device'],0,2**64-1) and integer(value['file']['inode'],1,2**64-1))
    return value


class PhoneAudioFiles:
    def __init__(self,root,run,role,intent,guard,binding):
        self.root,self.run,self.role=Path(root),identifier(run),role
        need(role in ('primary','actor') and callable(intent) and callable(guard));self.intent,self.guard=intent,guard
        self.binding=deepcopy(context(binding))
        PrivateFeatureState(self.root/'audio-file-boundary.json')._parent()

    def path(self,value):
        record(value);need(value['runId']==self.run and value['role']==self.role and all(value['binding'][k]==self.binding[k] for k in self.binding if k!='processIdentity'));return self.root/value['name']

    def content(self,value,raw):
        need(type(raw) is bytes and len(raw)==value['bytes'] and hashlib.sha256(raw).hexdigest()==value['sha256'])
        with wave.open(io.BytesIO(raw),'rb') as stream:
            rate,channels,width,frames=stream.getframerate(),stream.getnchannels(),stream.getsampwidth(),stream.getnframes();pcm=stream.readframes(frames)
        need(8000<=rate<=48000 and channels in (1,2) and width==2 and 0<frames<=rate*60 and len(pcm)==frames*channels*2)
        source=value['provenance']
        if value['kind'] in ('input','sink'):
            from adapters.recorded_preview_evidence import validate
            validate(source,source['requestId'],int(value['binding']['processIdentity'].split(':')[0]),source['capturedEpochMs'])
            original=source['source'];tap=original[value['kind']]
            need(original['sampleRate']==rate and original['channels']==channels and tap['bytes']==len(pcm) and tap['sha256']==hashlib.sha256(pcm).hexdigest() and original['events'][-1]['phase']=='completed')
        else:
            need(source['captureId']==value['sourceId'] and source['exists'] is True and source['original']['captureId']==value['sourceId'])
            original=source['original'];need(original['bytes']==len(raw) and original['sha256']==hashlib.sha256(raw).hexdigest() and original['sampleRate']==rate and original['channels']==channels and original['frames']==frames and original['source']=='private-pc-playout-monitor')

    def identity(self,path,fd,value):
        before,current=os.fstat(fd),path.lstat()
        for info in (before,current):need(stat.S_ISREG(info.st_mode) and info.st_nlink==1 and info.st_size<=LIMIT and info.st_uid==os.geteuid() and stat.S_IMODE(info.st_mode)==0o600)
        need((before.st_dev,before.st_ino)==(current.st_dev,current.st_ino)==(value['file']['device'],value['file']['inode']))

    def read(self,value):
        started=time.monotonic();self.guard();path=self.path(value);need(value['phase'] in ('saved','retiring'))
        with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK),'rb') as stream:
            self.identity(path,stream.fileno(),value);raw=stream.read(LIMIT+1);self.identity(path,stream.fileno(),value)
        self.content(value,raw);self.guard();need(0<=time.monotonic()-started<5);return raw

    def write(self,ticket,kind,source_id,raw,provenance):
        started=time.monotonic();self.guard();identifier(ticket);identifier(source_id);need(type(raw) is bytes and 0<len(raw)<=LIMIT)
        value=dict(audioFileVersion=1,binding=deepcopy(self.binding),provenance=deepcopy(provenance),runId=self.run,role=self.role,ticket=ticket,kind=kind,sourceId=source_id,
            name='audio-'+self.run+'-'+self.role+'-'+source_id+'-'+kind+'.wav',bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),phase='planned',file=None)
        path=self.path(value);self.content(value,raw);need(self.intent(deepcopy(value)) is not False);self.guard()
        with os.fdopen(os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600),'wb') as stream:
            info=os.fstat(stream.fileno());value.update(phase='opened',file=dict(device=info.st_dev,inode=info.st_ino))
            self.identity(path,stream.fileno(),value);need(self.intent(deepcopy(value)) is not False);self.guard()
            need(stream.write(raw)==len(raw));stream.flush();os.fsync(stream.fileno());self.identity(path,stream.fileno(),value)
        value['phase']='saved';need(self.read(value)==raw and self.intent(deepcopy(value)) is not False and 0<=time.monotonic()-started<5);return value

    def retire(self,value):
        path=self.path(value);self.guard()
        if value['phase']=='retired':need(not path.exists() and not path.is_symlink());return value
        # Interrupted creations are deliberately incomplete, never empty green.
        if value['phase']=='saved':
            self.read(value);value=deepcopy(value);value['phase']='retiring';need(self.intent(value) is not False)
        need(value['phase']=='retiring')
        if path.exists() or path.is_symlink():self.read(value);path.unlink()
        need(not path.exists() and not path.is_symlink());self.guard()
        value=deepcopy(value);value['phase']='retired';need(self.intent(value) is not False);return value
