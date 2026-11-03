"""Original passive Actor microphone transport; no microphone or playback input.

This native source reader supplies typed raw packets/files only. Its caller
must own the actual SDK/source/run/role lock and durable query intent BEFORE
send. Independent capture does not qualify compiled native/physical hardware.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import base64
import hashlib
import io
import json
import re
import time
import uuid
import wave
from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.normal_ui import NativeUIError

ACTION='feature-ios-audio-passive-capture'
FILE='feature-ios-audio-passive-capture.json'
VERSION=1
MAX_ORIGINAL=2*1024*1024
MAX_CHUNK=4096
KINDS=('intent','capture','wav')
OPERATIONS=('start','observe','capture','read','release','recover','files')
PROFILE='qt-source-read-to-passive-acoustic-tap'
FLAGS=('physicalADCQualified','acousticQualified','peerQualified')


def hex32(value):return type(value) is str and re.fullmatch('[0-9a-f]{32}',value) is not None

def command(value):
    need(type(value) is dict);operation=value.get('operation')
    exact(value,{'schemaVersion','commandId','action','operation','instance','runId','role','leaseId','startCommandId'} |
        ({'seconds'} if operation=='start' else {'kind','offset','bytes'} if operation=='read' else set()))
    need(type(value['schemaVersion']) is int and value['schemaVersion']==VERSION and value['action']==ACTION
        and operation in OPERATIONS and value['role']=='actor' and hex32(value['runId'])
        and hex32(value['leaseId']) and hex32(value['instance']) and type(value['commandId']) is str
        and re.fullmatch('ios-[0-9a-f]{32}',value['commandId']) and type(value['startCommandId']) is str
        and re.fullmatch('ios-[0-9a-f]{32}',value['startCommandId']))
    if operation=='start':need(integer(value['seconds'],6,10) and value['startCommandId']==value['commandId'])
    if operation=='read':
        need(value['kind'] in KINDS and integer(value['offset'],0,MAX_ORIGINAL)
            and integer(value['bytes'],1,MAX_CHUNK) and value['offset']+value['bytes']<=MAX_ORIGINAL)
    return value


def descriptor(value,kind):
    need(kind in KINDS and type(value) is dict and type(value.get('exists')) is bool)
    if not value['exists']:exact(value,{'kind','exists'});need(value['kind']==kind);return value
    exact(value,{'kind','exists','complete','bytes','sha256','device','inode'})
    need(value['kind']==kind and type(value['complete']) is bool and integer(value['bytes'],0,MAX_ORIGINAL)
        and type(value['sha256']) is str and re.fullmatch('[0-9a-f]{64}',value['sha256'])
        and all(type(value[key]) is str and re.fullmatch('[0-9]{1,24}',value[key]) for key in ('device','inode')))
    return value


def state(value,request,*,full=False):
    exact(value,{'passiveAcousticVersion','profile','owned','runId','role','leaseId','instance','admissionEpoch',
        'captureGeneration','inputGeneration','inputRouteRevision','startedEpochMs','startedMonotonicMs','active','complete','invalid','sampleRate','channels',
        'bytes','coveredBytes','targetBytes','inputCallbacks','watchdogOwned','watchdogActive',*FLAGS} |
        ({'rows'} if full else {'originRows','originRowsSha256'}))
    need(type(value['passiveAcousticVersion']) is int and value['passiveAcousticVersion']==VERSION
        and value['profile']==PROFILE and all(type(value[key]) is bool for key in
            ('owned','active','complete','invalid','watchdogOwned','watchdogActive',*FLAGS))
        and all(value[key] is False for key in FLAGS)
        and integer(value['captureGeneration'],0,1000000000))
    if not full:
        need(integer(value['originRows'],0,2048) and type(value['originRowsSha256']) is str
            and re.fullmatch('[0-9a-f]{64}',value['originRowsSha256']))
    if not value['owned']:
        need(not any(value[key] for key in ('active','complete','invalid','watchdogOwned','watchdogActive'))
            and all(value[key]=='' for key in ('runId','role','leaseId','instance'))
            and all(type(value[key]) is int and value[key]==0 for key in ('admissionEpoch','startedEpochMs',
                'startedMonotonicMs','inputGeneration','sampleRate','channels','bytes','coveredBytes','targetBytes','inputCallbacks'))
            and value['inputRouteRevision']=='0')
        if full:need(value['rows']==[])
        else:need(value['originRows']==0)
        return value
    need(value['runId']==request['runId'] and value['leaseId']==request['leaseId'] and value['role']=='actor'
        and value['instance']==request['instance'] and integer(value['captureGeneration'],1,1000000000)
        and integer(value['inputGeneration'],1,1000000000) and type(value['inputRouteRevision']) is str
        and re.fullmatch('[0-9]{1,24}',value['inputRouteRevision'])
        and integer(value['admissionEpoch'],1,4000000000) and value['admissionEpoch'] & 3==1
        and integer(value['startedEpochMs'],1) and integer(value['startedMonotonicMs'],1)
        and integer(value['sampleRate'],8000,48000) and integer(value['channels'],1,2)
        and integer(value['targetBytes'],1,1920000) and integer(value['bytes'],0,value['targetBytes'])
        and integer(value['coveredBytes'],0,value['targetBytes']) and integer(value['inputCallbacks'],0,2048)
        and value['targetBytes']%(value['sampleRate']*value['channels']*2)==0
        and 6<=value['targetBytes']//(value['sampleRate']*value['channels']*2)<=10)
    if value['complete']:
        need(not value['active'] and not value['invalid'] and value['bytes']==value['coveredBytes']==value['targetBytes'])
    if value['active']:need(not value['invalid'] and not value['complete'] and value['watchdogOwned'])
    if value['invalid']:need(not value['active'] and not value['complete'])
    if full:need(type(value['rows']) is list and len(value['rows'])<=2048)
    else:need(value['originRows']==value['inputCallbacks'])
    return value


def validate(value,request,pid,clock,*,original_only=False):
    command(request);need(type(original_only) is bool and original_only==(request['operation']=='read'))
    exact(value,{'passiveAcousticReplyVersion','commandId','instance','sequence','processId','runId','role','leaseId',
        'operation','requestedEpochMs','capturedEpochMs','source'})
    need(type(value['passiveAcousticReplyVersion']) is int and value['passiveAcousticReplyVersion']==VERSION
        and integer(pid,1) and integer(value['sequence'],1,1000000000)
        and value['processId']==pid and integer(value['processId'],1)
        and all(value[key]==request[key] for key in ('commandId','instance','runId','role','leaseId','operation'))
        and integer(value['requestedEpochMs'],1) and integer(value['capturedEpochMs'],value['requestedEpochMs'])
        and value['capturedEpochMs']-value['requestedEpochMs']<5000)
    if original_only:need(clock is None)
    else:
        need(type(clock) is dict and clock['processId']==pid and clock['instance']==request['instance'])
        fresh(value['capturedEpochMs'],clock['capturedEpochMs'])
    source=value['source']
    if request['operation']=='read':
        exact(source,{'kind','offset','bytes','base64','sha256','original','originalOnly'});need(source['originalOnly'] is True)
        descriptor(source['original'],source['kind']);need(source['original']['exists'] and source['original']['complete'])
        need(all(source[key]==request[key] for key in ('kind','offset','bytes')) and type(source['base64']) is str)
        raw=base64.b64decode(source['base64'],validate=True)
        need(len(raw)==source['bytes'] and base64.b64encode(raw).decode()==source['base64']
            and type(source['sha256']) is str and hashlib.sha256(raw).hexdigest()==source['sha256'])
    else:
        exact(source,{'state','files','retired','startAttempted','captureAttempted','releaseAttempted','openOriginalFds','originalBytes'})
        need(all(type(source[key]) is bool for key in ('retired','startAttempted','captureAttempted','releaseAttempted'))
            and type(source['files']) is list and len(source['files'])==3)
        for row,kind in zip(source['files'],KINDS):descriptor(row,kind)
        state(source['state'],request)
        actual=[row for row in source['files'] if row['exists']]
        need(integer(source['openOriginalFds'],0,3) and source['openOriginalFds']==len(actual)
            and integer(source['originalBytes'],0,MAX_ORIGINAL*3) and source['originalBytes']==sum(row['bytes'] for row in actual))
        if source['retired']:
            need(source['releaseAttempted'] and not source['state']['owned'] and not actual)
    return value


class IOSAudioPassiveCaptureSource:
    def __init__(self,send,read,guard,native_clock,pid,instance,run,lease,*,start_command_id,intent,monotonic=time.monotonic,sleep=time.sleep):
        need(all(callable(fn) for fn in (send,read,guard,native_clock,intent,monotonic,sleep))
            and integer(pid,1) and all(hex32(v) for v in (instance,run,lease)) and type(start_command_id) is str
            and re.fullmatch('ios-[0-9a-f]{32}',start_command_id))
        self.send,self.read,self.guard,self.native_clock,self.intent=send,read,guard,native_clock,intent
        self.pid,self.instance,self.run,self.lease=pid,instance,run,lease
        self.start_command_id=start_command_id
        self.monotonic,self.sleep=monotonic,sleep;self.sequence=0;self.epoch=0

    def query(self,operation,**fields):
        query=dict(schemaVersion=VERSION,commandId=self.start_command_id if operation=='start' else 'ios-'+uuid.uuid4().hex,action=ACTION,operation=operation,
            instance=self.instance,runId=self.run,role='actor',leaseId=self.lease,startCommandId=self.start_command_id,**fields)
        command(query);need(self.guard() is not False)
        started=previous=self.monotonic();need(number(started,0,1e15))
        # The caller's real ownership WAL must return only AFTER durable intent.
        need(self.intent(deepcopy(query)) is not False);need(self.guard() is not False);self.send(query)
        for attempt in range(101):
            need(self.guard() is not False);raw=self.read()
            try:value=decode(raw) if raw else None
            except json.JSONDecodeError:value=None
            if type(value) is dict and value.get('commandId')==query['commandId']:
                original_only=operation=='read'
                clock=None if original_only else self.native_clock()
                validate(value,query,self.pid,clock,original_only=original_only)
                need(value['sequence']>self.sequence and value['capturedEpochMs']>=self.epoch)
                now=self.monotonic();need(number(now,previous,started+5) and now-started<5)
                self.sequence,self.epoch=value['sequence'],value['capturedEpochMs']
                need(self.guard() is not False);return query,value
            now=self.monotonic();need(number(now,previous,started+5));previous=now
            if now-started>=5 or attempt==100:break
            self.sleep(min(.05,5-(now-started)))
        raise NativeUIError('Original passive iOS Audio capture reply is unavailable')

    def original(self,reference):
        kind=reference.get('kind');descriptor(reference,kind);need(reference['exists'] and reference['complete'])
        result=bytearray()
        while len(result)<reference['bytes']:
            _,packet=self.query('read',kind=kind,offset=len(result),bytes=min(MAX_CHUNK,reference['bytes']-len(result)))
            need(packet['source']['original']==reference)
            result.extend(base64.b64decode(packet['source']['base64'],validate=True))
        raw=bytes(result);need(len(raw)==reference['bytes'] and hashlib.sha256(raw).hexdigest()==reference['sha256'])
        return raw


def original_intent(raw,request,pid):
    """Original creator body, not a native ACK or an expected-field factory."""
    command(request);need(request['operation']=='start' and integer(pid,1) and type(raw) is bytes)
    value=decode(raw.decode('utf-8'),limit=MAX_ORIGINAL)
    exact(value,{'passiveAcousticIntentVersion','instance','runId','leaseId','role','processId','issuedEpochMs','command'})
    need(type(value['passiveAcousticIntentVersion']) is int and value['passiveAcousticIntentVersion']==VERSION
        and all(value[key]==request[key] for key in ('instance','runId','leaseId','role'))
        and type(value['processId']) is int and value['processId']==pid and integer(value['issuedEpochMs'],1)
        and value['command']==request)
    command(value['command']);return value


def original_frame(raw,wav,request,pid):
    """Validate original microphone bytes/rows; never a playback success verdict."""
    command(request);need(type(raw) is bytes and len(raw)<=MAX_ORIGINAL and type(wav) is bytes and len(wav)<=MAX_ORIGINAL)
    value=decode(raw.decode('utf-8'),limit=MAX_ORIGINAL)
    exact(value,{'passiveAcousticOriginalVersion','instance','runId','role','leaseId','processId',
        'requestedEpochMs','capturedEpochMs','captureCommand','source','wav'})
    need(type(value['passiveAcousticOriginalVersion']) is int and value['passiveAcousticOriginalVersion']==VERSION
        and integer(pid,1) and value['processId']==pid and integer(value['processId'],1)
        and all(value[key]==request[key] for key in ('instance','runId','role','leaseId'))
        and integer(value['requestedEpochMs'],1) and integer(value['capturedEpochMs'],value['requestedEpochMs'])
        and value['capturedEpochMs']-value['requestedEpochMs']<5000)
    need(request['operation']=='capture' and value['captureCommand']==request)
    command(value['captureCommand'])
    source=state(value['source'],request,full=True)
    need(source['owned'] and source['complete'] and not source['active'] and not source['invalid'])
    descriptor(value['wav'],'wav');need(value['wav']['exists'] and value['wav']['complete']
        and value['wav']['bytes']==len(wav) and value['wav']['sha256']==hashlib.sha256(wav).hexdigest())
    with wave.open(io.BytesIO(wav),'rb') as reader:
        need(reader.getcomptype()=='NONE' and reader.getsampwidth()==2 and reader.getnchannels()==source['channels']
            and reader.getframerate()==source['sampleRate'] and reader.getnframes()*source['channels']*2==source['targetBytes'])
        pcm=reader.readframes(reader.getnframes());need(not reader.readframes(1))
    need(len(pcm)==source['targetBytes'] and len(wav)==44+len(pcm))
    rows=source['rows'];need(1<=len(rows)<=2048 and len(rows)==source['inputCallbacks'])
    offset=previous=0;last_epoch=source['startedEpochMs'];last_mono=source['startedMonotonicMs']
    for index,row in enumerate(rows):
        exact(row,{'sequence','generation','routeRevision','readBeforeEpochMs','readAfterEpochMs',
            'readBeforeMonotonicMs','readAfterMonotonicMs','tapEpochMs','tapMonotonicMs',
            'readBytes','readSha256','offset','bytes','sha256'})
        need(integer(row['sequence'],previous+1,1000000000) and integer(row['generation'],1,1000000000)
            and row['generation']==source['inputGeneration'] and row['routeRevision']==source['inputRouteRevision']
            and integer(row['readBytes'],1,16*1024*1024) and integer(row['offset'],0,source['targetBytes'])
            and row['offset']==offset and integer(row['bytes'],1,row['readBytes'])
            and offset+row['bytes']<=len(pcm) and row['readBytes']%(source['channels']*2)==0
            and row['bytes']%(source['channels']*2)==0
            and (row['bytes']==row['readBytes'] or index==len(rows)-1 and offset+row['bytes']==len(pcm))
            and integer(row['readBeforeEpochMs'],last_epoch,value['capturedEpochMs'])
            and integer(row['readAfterEpochMs'],row['readBeforeEpochMs'],value['capturedEpochMs'])
            and integer(row['tapEpochMs'],row['readAfterEpochMs'],value['capturedEpochMs'])
            and integer(row['readBeforeMonotonicMs'],last_mono)
            and integer(row['readAfterMonotonicMs'],row['readBeforeMonotonicMs'])
            and integer(row['tapMonotonicMs'],row['readAfterMonotonicMs'])
            and abs((row['tapEpochMs']-source['startedEpochMs'])-(row['tapMonotonicMs']-source['startedMonotonicMs']))<=250
            and type(row['readSha256']) is str and re.fullmatch('[0-9a-f]{64}',row['readSha256'])
            and row['sha256']==hashlib.sha256(pcm[offset:offset+row['bytes']]).hexdigest()
            and (row['readBytes']!=row['bytes'] or row['readSha256']==row['sha256']))
        offset+=row['bytes'];previous=row['sequence'];last_epoch=row['tapEpochMs'];last_mono=row['tapMonotonicMs']
    need(offset==len(pcm)==source['coveredBytes'])
    return value
