"""Original native avatar drive/feet/tracking; no gesture counts or peer verdict."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import math
import time
from urllib.parse import urlsplit
import uuid
from adapters.native_feature_observation import LIMIT,decode,exact,fresh,integer,need,number
from adapters.pico4.lifecycle_source import nonce

VERSION=1
FILE='feature-lifecycle-drive.json'
ACTION='feature-lifecycle-drive-observe'


def vector(value,length=3,low=-1e8,high=1e8):
    need(type(value) is list and len(value)==length and all(number(v,low,high) for v in value));return value


def quaternion(value):
    vector(value,4,-1,1);need(abs(sum(v*v for v in value)-1)<=.01)


def validate(value,request,pid,epoch):
    exact(value,{'lifecycleDriveVersion','commandId','runId','instance','sequence','processId','capturedEpochMs','source'})
    need(type(value['lifecycleDriveVersion']) is int and value['lifecycleDriveVersion']==VERSION
        and nonce(value['commandId']) and value['commandId']==request['commandId']
        and nonce(value['runId']) and value['runId']==request['runId'] and nonce(value['instance'])
        and integer(value['sequence'],1) and integer(value['processId'],1) and value['processId']==pid)
    fresh(value['capturedEpochMs'],epoch)
    source=value['source'];exact(source,{'sceneUrl','feetPosition','bodyPosition','orientation','modelScale',
        'sensorToWorld','driveKeys','rawDriveKeys','disabledDriveKeys','physics','motors','tracking'})
    need(type(source['sceneUrl']) is str and 0<len(source['sceneUrl'])<=2048 and urlsplit(source['sceneUrl']).scheme
        and number(source['modelScale'],.001,1000))
    for key in ('feetPosition','bodyPosition'):vector(source[key])
    quaternion(source['orientation']);vector(source['sensorToWorld'],16)
    columns=[source['sensorToWorld'][index:index+3] for index in (0,4,8)]
    scales=[math.sqrt(sum(v*v for v in column)) for column in columns]
    need(.001<=scales[0]<=1000 and all(abs(v-scales[0])<=.001 for v in scales)
        and all(abs(sum(a*b for a,b in zip(columns[i],columns[j])))<=.001 for i,j in ((0,1),(0,2),(1,2)))
        and all(abs(source['sensorToWorld'][index])<=.0001 for index in (3,7,11))
        and abs(source['sensorToWorld'][15]-1)<=.0001)
    x,y,z=columns
    need(x[0]*(y[1]*z[2]-y[2]*z[1])-y[0]*(x[1]*z[2]-x[2]*z[1])+z[0]*(x[1]*y[2]-x[2]*y[1])>0)
    vector(source['driveKeys'],12,-1e6,1e6);vector(source['rawDriveKeys'],12,-1e6,1e6)
    need(type(source['disabledDriveKeys']) is list and len(source['disabledDriveKeys'])==12
        and all(type(v) is bool for v in source['disabledDriveKeys']))
    for drive,raw,disabled in zip(source['driveKeys'],source['rawDriveKeys'],source['disabledDriveKeys']):
        need(drive==(0 if disabled else raw))
    physics=source['physics'];exact(physics,{'ready','state','seated','stuck','linearVelocity'})
    need(all(type(physics[k]) is bool for k in ('ready','seated','stuck')) and integer(physics['state'],0,4))
    vector(physics['linearVelocity'])
    motors=source['motors'];exact(motors,{'advancedMovement','actionEnabled','scriptedEnabled','actionVelocity',
        'scriptedVelocity','scriptedTimescale','thrust','pushing','braking','beingPushed'})
    need(all(type(motors[k]) is bool for k in ('advancedMovement','actionEnabled','scriptedEnabled','pushing','braking','beingPushed'))
        and number(motors['scriptedTimescale'],0,1e8))
    for key in ('actionVelocity','scriptedVelocity','thrust'):vector(motors[key])
    tracking=source['tracking'];exact(tracking,{'head','leftHand','rightHand'})
    for pose in tracking.values():
        exact(pose,{'valid','position','rotation'});need(type(pose['valid']) is bool)
        vector(pose['position']);quaternion(pose['rotation'])
    return value


def continuity(previous,current):
    if previous is not None:
        need(current['instance']==previous['instance'] and current['runId']==previous['runId']
            and current['sequence']>previous['sequence'] and current['capturedEpochMs']>=previous['capturedEpochMs']
            and current['commandId']!=previous['commandId'])
    return deepcopy(current)


class AvatarDisplacement:
    """Primary original feet anchor; an independent peer join is still required."""
    def __init__(self,original):
        validate(original,original,original['processId'],original['capturedEpochMs'])
        source=original['source'];need(source['physics']['ready'] and source['physics']['state']==0
            and not source['physics']['seated'] and not source['physics']['stuck'])
        self.original=deepcopy(original)
        need(self.measure(original)['heldInputs']==[] and all(abs(v)<=.025 for v in source['physics']['linearVelocity'])
            and all(abs(v)<=.025 for v in source['motors']['actionVelocity']))
    def measure(self,current):
        validate(current,current,current['processId'],current['capturedEpochMs']);old=self.original
        need(current['processId']==old['processId'] and current['instance']==old['instance'] and current['runId']==old['runId']
            and current['sequence']>=old['sequence'] and current['capturedEpochMs']>=old['capturedEpochMs'])
        source=current['source'];need(source['sceneUrl']==old['source']['sceneUrl'] and source['modelScale']==old['source']['modelScale'])
        physics=source['physics'];motors=source['motors'];drive=source['driveKeys']
        need(physics['ready'] and physics['state']==0 and not physics['seated'] and not physics['stuck']
            and all(pose['valid'] for pose in source['tracking'].values()))
        # This narrow shared journey permits only longitudinal ground drive.
        # Keep raw disabled/blocked inputs in the source; never call them held.
        need(all(abs(value)<=1e-6 for index,value in enumerate(drive) if index!=2) and -1<=drive[2]<=1)
        held=[]
        if motors['advancedMovement'] and motors['actionEnabled'] and drive[2]!=0:
            # Original Pico plugin maps LY=-runtimeY; Application maps driveZ=-TranslateZ.
            held=['forward' if drive[2]>0 else 'backward']
        delta=[value-origin for value,origin in zip(source['feetPosition'],old['source']['feetPosition'])]
        return dict(heldInputs=held,positionDelta=delta,worldDisplacement=math.sqrt(sum(v*v for v in delta)))


class AvatarReleaseWindow:
    """Three-dimensional primary stability; never an independent peer verdict."""
    def __init__(self,anchor):
        need(isinstance(anchor,AvatarDisplacement));self.anchor=anchor
        self.previous,self.origin,self.native_start,self.host_start,self.host_last=None,None,None,None,None
    def observe(self,packet,monotonic):
        try:return self._observe(packet,monotonic)
        except Exception:
            self.origin,self.native_start,self.host_start=None,None,None
            raise
    def _observe(self,packet,monotonic):
        self.anchor.measure(packet)
        need(number(monotonic,0,1e15) and (self.host_last is None or monotonic>=self.host_last))
        if self.previous is not None and (packet['capturedEpochMs']-self.previous['capturedEpochMs']>1000
                or monotonic-self.host_last>1):self.origin=None
        self.previous=continuity(self.previous,packet);self.host_last=monotonic
        measured=self.anchor.measure(packet);point=packet['source']['feetPosition']
        if measured['heldInputs']:
            self.origin,self.native_start,self.host_start=None,None,None
            return False
        moved=self.origin is not None and math.sqrt(sum((v-o)**2 for v,o in zip(point,self.origin)))>.025
        if self.origin is None or moved:
            self.origin=deepcopy(point);self.native_start=packet['capturedEpochMs'];self.host_start=monotonic
        return not measured['heldInputs'] and packet['capturedEpochMs']-self.native_start>=3000 and monotonic-self.host_start>=3


class PicoLifecycleDrive:
    def __init__(self,send,original,clock_ms,guard,pid,*,monotonic=time.monotonic,sleep=time.sleep):
        need(all(callable(f) for f in (send,original,clock_ms,guard,monotonic,sleep)) and integer(pid,1))
        self.send,self.original,self.clock_ms,self.guard,self.pid=send,original,clock_ms,guard,pid
        self.monotonic,self.sleep=monotonic,sleep;self.previous,self.last_raw,self.last_sha256=None,None,None
    def restore(self,original):
        validate(original,original,self.pid,original['capturedEpochMs']);need(self.guard() is not False)
        need(self.previous is None or self.previous==original);self.previous=deepcopy(original)
    def capture(self,run):
        need(nonce(run) and self.guard() is not False)
        request=dict(schemaVersion=1,commandId=uuid.uuid4().hex,action=ACTION,runId=run)
        started=previous=self.monotonic();requested=self.clock_ms();need(number(started,0,1e15) and integer(requested,1))
        self.send(request)
        for attempt in range(51):
            need(self.guard() is not False)
            raw=self.original();need(type(raw) is str and len(raw.encode('utf-8'))<=LIMIT)
            try:value=decode(raw) if raw else None
            except json.JSONDecodeError:value=None
            now=self.monotonic();need(number(now,0,1e15) and previous<=now and now-started<5);previous=now
            need(self.guard() is not False)
            if type(value) is dict and value.get('commandId')==request['commandId']:
                epoch=self.clock_ms();validate(value,request,self.pid,epoch);need(value['capturedEpochMs']>=requested)
                accepted=continuity(self.previous,value);need(self.guard() is not False)
                completed=self.monotonic();need(number(completed,0,1e15) and previous<=completed and completed-started<5
                    and max(epoch-value['capturedEpochMs'],requested-value['capturedEpochMs']+(completed-started)*1000)<=1500)
                self.previous,self.last_raw,self.last_sha256=accepted,raw,hashlib.sha256(raw.encode()).hexdigest()
                return deepcopy(value)
            if attempt<50:self.sleep(.1)
        need(False)
