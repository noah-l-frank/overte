"""Frozen shared PC playout monitor for the existing Pico normal Audio recipe."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import time
import uuid
import wave
from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState
from feature_journeys.contract import identifier
from feature_journeys.fixtures import challenge
from voice_peer.fixture import CLI


def invoke(root,action,*,_literal=None,**fields):
    need(action in ('status','domain-check','position','receive-preview','receive-preview-owned','preview-source','preview-source-retire','preview-source-batch','preview-files','preview-release'))
    command=[sys.executable,str(CLI),'--state-dir',str(root),action]
    for key,value in fields.items():command.extend(['--'+key.replace('_','-'),str(value)])
    token=None if _literal is None else _literal.before(action,fields)
    try:
        result=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
            timeout=15 if action in ('receive-preview','receive-preview-owned') else 5,check=_literal is None)
    except (OSError,subprocess.SubprocessError) as error:
        if _literal is not None:_literal.uncertain(token,getattr(error,'stdout',None))
        raise RuntimeError('Owned PC Audio original source is unavailable') from None
    if _literal is not None:
        _literal.after(token,result.stdout)
        need(result.returncode==0)
    try:
        need(len(result.stdout)<=1024*1024)
        from adapters.native_feature_observation import decode
        return decode(result.stdout.decode('utf-8'))
    except Exception:
        if _literal is not None:_literal.rejected(token)
        raise


def configuration(value):
    exact(value,{'audioConfigurationVersion','artifactRoot','peerState','peerClientSha256','peerRunnerSha256','domainId'})
    need(type(value['audioConfigurationVersion']) is int and value['audioConfigurationVersion']==1)
    for key in ('artifactRoot','peerState'):
        path=Path(value[key]);need(path.is_absolute() and str(path)==value[key]);PrivateFeatureState(path/'audio-boundary.json')._parent()
    for key in ('peerClientSha256','peerRunnerSha256'):need(type(value[key]) is str and len(value[key])==64 and all(c in '0123456789abcdef' for c in value[key]))
    need(str(uuid.UUID(value['domainId']))==value['domainId'] and uuid.UUID(value['domainId']).int!=0)
    return deepcopy(value)


class PicoAudioPeer:
    def __init__(self,config,session_hash,guard,*,call=invoke,epoch_ms=lambda:int(time.time()*1000),raw_call=None):
        self.config=configuration(config);self.root=Path(config['peerState']);self.session_hash=session_hash
        self.guard,self.call,self.epoch_ms=guard,call,epoch_ms;need(callable(guard) and callable(call) and callable(epoch_ms))
        self.observations=[];self.last_file=self.last_metadata=None
        self.reply_observer=self._reply_observer=None
        self.raw_call=invoke if call is invoke else raw_call
        self.literal=self._literal=None;self.last_raw_reference=None
        self.session_hash=self.session()

    def bind_reply_observer(self,callback):
        need(callable(callback) and self.reply_observer is self._reply_observer is None and not self.observations)
        self.reply_observer=self._reply_observer=callback

    def bind_literal_source(self,source):
        need(self.literal is self._literal is None and not self.observations and callable(self.raw_call))
        self.literal=self._literal=source

    def session(self):
        self.guard();value=PrivateFeatureState(self.root/'session.json').read();need(type(value) is dict)
        digest=hashlib.sha256(__import__('json').dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        need(self.session_hash in (None,digest));self.guard();return digest

    def request(self,action,**fields):
        need(self.reply_observer is self._reply_observer)
        if action in ('preview-files','preview-release','preview-source','preview-source-retire','preview-source-batch'):fields['request_id']=uuid.uuid4().hex
        need(self.literal is self._literal)
        self.session()
        if self.literal is None:value=self.call(self.root,action,**fields)
        else:
            peer=self;archive=self.literal
            class Literal:
                def before(self,action,fields):return archive.before(action,fields)
                def after(self,token,raw):peer.last_raw_reference=archive.after(token,raw)
                def uncertain(self,token,raw):return archive.uncertain(token,raw)
                def rejected(self,token):return archive.rejected(token)
            value=self.raw_call(self.root,action,_literal=Literal(),**fields)
        if self.reply_observer is not None:self.reply_observer(action,deepcopy(value))
        self.session();need(type(value) is dict)
        need(len(self.observations)<16)
        self.observations.append(dict(action=action,reply=deepcopy(value)))
        if 'request_id' in fields:need(value.get('requestId')==fields['request_id'])
        return value

    def status(self):
        value=self.request('status');client=value.get('client')
        need(value.get('schemaVersion')==1 and value.get('previewProviderVersion')==1 and type(value['previewProviderVersion']) is int and value.get('recordedPreviewEnabled') is True and value.get('previewRunnerSha256')==self.config['peerRunnerSha256'] and value.get('clientRunning') is True and value.get('snapshotFresh') is True and value.get('audioRouted') is True and value.get('clientSha256')==self.config['peerClientSha256'] and type(client) is dict and client.get('connected') is True and client.get('mixerReady') is True and client.get('localEcho') is False and client.get('serverEcho') is False and number(value.get('snapshotAgeSeconds'),0,1.5))
        need(self.request('domain-check',domain_id=self.config['domainId']).get('sameDomain') is True)
        return value

    def packet(self,ticket):
        value=self.request('preview-files',capture_id=identifier(ticket))
        exact(value,{'schemaVersion','requestId','instance','captureId','capturedEpochMs','exists','retired','original'})
        identifier(value['requestId'])
        identifier(value['instance']);need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['captureId']==ticket and type(value['exists']) is bool and type(value['retired']) is bool)
        fresh(value['capturedEpochMs'],self.epoch_ms())
        need((value['original'] is not None)==value['exists']);return value

    def original(self,run,ticket):
        self.status();packet=self.packet(ticket);source=packet['original']
        if source is None:return packet,None
        exact(source,{'schemaVersion','instance','captureId','challenge','source','startedEpochMs','completedEpochMs','bytes','sha256','device','inode','sampleRate','channels','frames','clientSha256','runnerSha256','pcAudioStats','physicalAudioHardwareTested'})
        need(type(source['schemaVersion']) is int and source['schemaVersion']==1 and source['instance']==packet['instance'] and source['captureId']==ticket and source['challenge']==challenge(run,ticket).hex() and source['source']=='private-pc-playout-monitor' and source['physicalAudioHardwareTested'] is False and source['clientSha256']==self.config['peerClientSha256'] and source['runnerSha256']==self.config['peerRunnerSha256'] and integer(source['sampleRate'],8000,48000) and integer(source['channels'],1,2) and integer(source['frames'],3*source['sampleRate'],11*source['sampleRate']) and integer(source['bytes'],1,32*1024*1024) and integer(source['startedEpochMs'],1) and integer(source['completedEpochMs'],source['startedEpochMs'],packet['capturedEpochMs']) and type(source['pcAudioStats']) is list and 1<=len(source['pcAudioStats'])<=128)
        path=self.root/('preview-'+ticket+'.wav');self.session()
        def signature(info):
            need(stat.S_ISREG(info.st_mode) and info.st_nlink==1 and info.st_uid==os.geteuid() and stat.S_IMODE(info.st_mode)==0o600)
            return [info.st_dev,info.st_ino,info.st_mode,info.st_uid,info.st_nlink,info.st_size,info.st_mtime_ns,info.st_ctime_ns]
        with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK),'rb') as stream:
            before=os.fstat(stream.fileno());current=path.lstat()
            need(signature(before)==signature(current) and before.st_size<=32*1024*1024)
            need((before.st_dev,before.st_ino)==(current.st_dev,current.st_ino)==(source['device'],source['inode']))
            raw=stream.read(32*1024*1024+1);after=os.fstat(stream.fileno());last=path.lstat()
            need(signature(after)==signature(last)==signature(before))
        need(len(raw)==source['bytes'] and hashlib.sha256(raw).hexdigest()==source['sha256']);self.session()
        metadata=self.root/('preview-'+ticket+'.json')
        with os.fdopen(os.open(metadata,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK),'rb') as stream:
            meta_before=signature(os.fstat(stream.fileno()));need(meta_before==signature(metadata.lstat()) and meta_before[5]<=65536)
            meta_raw=stream.read(65537)
            need(meta_before==signature(os.fstat(stream.fileno()))==signature(metadata.lstat()) and len(meta_raw)==meta_before[5])
        from adapters.native_feature_observation import decode
        need(json.dumps(decode(meta_raw.decode('utf-8')),sort_keys=True,separators=(',',':'))==json.dumps(source,sort_keys=True,separators=(',',':'))
             and signature(path.lstat())==signature(before))
        # Phone performs this byte/header join in its separate file owner.
        # Pico keeps the original PC file in place, so validate it here.
        with wave.open(io.BytesIO(raw),'rb') as wav:
            rate,channels,width,frames=wav.getframerate(),wav.getnchannels(),wav.getsampwidth(),wav.getnframes()
            pcm=wav.readframes(frames)
        need((rate,channels,width,frames)==(source['sampleRate'],source['channels'],2,source['frames'])
             and len(pcm)==frames*channels*2)
        self.last_file=dict(name=path.name,phase='saved',file=signature(before),bytes=len(raw),sha256=source['sha256'])
        self.last_metadata=dict(name=metadata.name,phase='saved',file=meta_before,bytes=len(meta_raw),
            sha256=hashlib.sha256(meta_raw).hexdigest(),raw=meta_raw.decode('utf-8'))
        return packet,raw

    def receive(self,run,ticket,seconds):
        self.status();return self.request('receive-preview',challenge=challenge(run,ticket).hex(),capture_id=ticket,seconds=seconds)

    def source(self,ticket):
        from adapters.pico4.audio_pc_source import validate,verify_kernel
        started=time.monotonic()
        value=self.request('preview-source',capture_id=identifier(ticket))
        validate(value,ticket,value['requestId'],self.epoch_ms());verify_kernel(value)
        validate(value,ticket,value['requestId'],self.epoch_ms());need(0<=time.monotonic()-started<=1.5)
        return value

    def sources(self,captures):
        from adapters.pico4.audio_pc_source import validate,verify_kernel
        need(type(captures) is tuple and 1<=len(captures)<=9 and len(set(captures))==len(captures))
        for ticket in captures:identifier(ticket)
        started=time.monotonic()
        batch=self.request('preview-source-batch',capture_ids=','.join(captures))
        from adapters.pico4.audio_pc_batch import packets as original_packets
        need(type(batch.get('audioPreviewSourceBatchVersion')) is int and batch['audioPreviewSourceBatchVersion']==2)
        values=original_packets(batch);need(len(values)==len(captures))
        seen=set();previous=None
        for ticket,packet in zip(captures,values):
            validate(packet,ticket,packet['requestId'],self.epoch_ms());verify_kernel(packet)
            validate(packet,ticket,packet['requestId'],self.epoch_ms())
            need(packet['requestId'] not in seen);seen.add(packet['requestId'])
            if previous is not None:
                need(all(packet[key]==previous[key] for key in ('producerSha256','instance','provider','clientProcess'))
                    and packet['sequence']>previous['sequence'])
            previous=packet
        need(0<=time.monotonic()-started<=1.5)
        return dict(audioPreviewSourceBatchVersion=2,requestId=batch['requestId'],packets=values)

    def receive_owned(self,run,ticket,seconds,request):
        status=self.status();need(status['client'].get('muted') is True)
        return self.request('receive-preview-owned',challenge=challenge(run,ticket).hex(),
            capture_id=identifier(ticket),seconds=seconds,source_request_id=identifier(request))

    def retire_recorder(self,ticket):
        from adapters.pico4.audio_pc_source import validate,verify_kernel
        value=self.request('preview-source-retire',capture_id=identifier(ticket))
        validate(value,ticket,value['requestId'],self.epoch_ms());verify_kernel(value)
        need(value['source'] is not None and value['source']['state']=='retired')
        return value

    def release(self,ticket):
        self.request('preview-release',capture_id=ticket);value=self.packet(ticket)
        need(value['retired'] and not value['exists'] and value['original'] is None);return value
