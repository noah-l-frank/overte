"""Fresh original entity/view inventory; preparation and render proof are separate."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import re
import time
import uuid

from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.normal_ui import NativeUIError
from feature_journeys.graphics_fixture import subject_ids

VERSION=3
FILE='feature-graphics-subject.json'
LIMIT=262144


def command(value,*,ios=False):
    exact(value,{'schemaVersion','commandId','action','runId'})
    need(type(ios) is bool and type(value['schemaVersion']) is int and value['schemaVersion']==1
         and value['action']=='feature-graphics-subject-observe'
         and type(value['commandId']) is str and re.fullmatch(('ios-' if ios else '')+'[0-9a-f]{32}',value['commandId'])
         and type(value['runId']) is str and re.fullmatch('[0-9a-f]{32}',value['runId']))
    return value


def vector(value,size,low,high):
    need(type(value) is list and len(value)==size and all(number(v,low,high) for v in value))
    return value


def rotation(value):
    vector(value,4,-1.01,1.01);need(abs(sum(v*v for v in value)-1)<.02)


def text(value,limit):return type(value) is str and len(value)<=limit and '\0' not in value


def entity_id(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',value) is not None


def validate(value,request,pid,epoch,*,require_avatar=False,require_framework=False):
    need(type(require_avatar) is bool and type(require_framework) is bool)
    command(request,ios=request['commandId'].startswith('ios-'))
    exact(value,{'schemaVersion','requestId','runId','instance','sequence','processId','requestedEpochMs','capturedEpochMs','source'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['requestId']==request['commandId']
         and value['runId']==request['runId'] and type(value['instance']) is str and re.fullmatch('[0-9a-f]{32}',value['instance'])
         and integer(value['sequence'],1,1_000_000_000) and integer(value['processId'],1) and value['processId']==pid
         and integer(value['requestedEpochMs'],1) and integer(value['capturedEpochMs'],1)
         and 0<=value['capturedEpochMs']-value['requestedEpochMs']<1500)
    fresh(value['capturedEpochMs'],epoch)
    source=value['source'];need(type(source) is dict and type(source.get('subjectVersion')) is int
        and source['subjectVersion'] in (1,2,3) and (not require_avatar or source['subjectVersion']>=2)
        and (not require_framework or source['subjectVersion']==3))
    exact(source,{'subjectVersion','sceneUrl','view','entities','absentIds','scan'}|({'avatarPose'} if source['subjectVersion']>=2 else set())
        |({'framework','hmd'} if source['subjectVersion']==3 else set()))
    need(text(source['sceneUrl'],2048)
         and type(source['entities']) is list and len(source['entities'])<=7 and type(source['absentIds']) is list
         and len(source['absentIds'])<=7)
    if source['subjectVersion']>=2:
        pose=source['avatarPose'];exact(pose,{'feetPosition','orientation','modelScale'})
        vector(pose['feetPosition'],3,-1000000,1000000);rotation(pose['orientation'])
        need(number(pose['modelScale'],.0001,1000))
    view=source['view'];exact(view,{'position','rotation','mode','fieldOfViewDegrees','aspectRatio','perspective'})
    vector(view['position'],3,-1000000,1000000);rotation(view['rotation'])
    need(text(view['mode'],64) and number(view['fieldOfViewDegrees'],1,179) and number(view['aspectRatio'],.1,10)
         and type(view['perspective']) is bool)
    wanted=set(subject_ids(request['runId']).values());seen=set()
    for row in source['entities']:
        exact(row,{'id','name','type','hostType','position','rotation','dimensions','color','visible','mirrorMode',
            'hazeMode','sourceUrl','haze','lastEditedEpochUs'})
        need(entity_id(row['id']) and row['id'] in wanted and row['id'] not in seen
             and text(row['name'],256) and text(row['type'],64) and row['type']!='Unknown'
             and row['hostType'] in ('local','domain','avatar') and type(row['visible']) is bool
             and row['mirrorMode'] in ('none','mirror','portal') and integer(row['hazeMode'],0,2)
             and text(row['sourceUrl'],2048) and integer(row['lastEditedEpochUs'],0,9007199254740991))
        seen.add(row['id']);vector(row['position'],3,-1000000,1000000);rotation(row['rotation'])
        vector(row['dimensions'],3,0,1000000)
        need(type(row['color']) is list and len(row['color'])==3 and all(integer(v,0,255) for v in row['color']))
        haze=row['haze'];exact(haze,{'range','color','altitudeEffect','glare','backgroundBlend'})
        need(number(haze['range'],0,1000000000) and type(haze['color']) is list and len(haze['color'])==3
             and all(integer(v,0,255) for v in haze['color']) and type(haze['altitudeEffect']) is bool
             and type(haze['glare']) is bool and number(haze['backgroundBlend'],0,1))
    absent=source['absentIds']
    need(all(entity_id(v) and v in wanted for v in absent) and len(set(absent))==len(absent)
         and not seen.intersection(absent) and seen.union(absent)==wanted)
    scan=source['scan'];exact(scan,{'center','radiusMeters','propertyScope','scannedEntities','unowned'})
    need(type(scan['center']) is list and len(scan['center'])==3 and all(type(v) is int and v==0 for v in scan['center'])
         and type(scan['radiusMeters']) is int and scan['radiusMeters']==128
         and scan['propertyScope']=='graphics-spatial-v1' and integer(scan['scannedEntities'],0,1024)
         and type(scan['unowned']) is list and len(scan['unowned'])<=scan['scannedEntities'])
    scanned=set()
    for row in scan['unowned']:
        exact(row,{'id','sha256'})
        need(entity_id(row['id']) and row['id'] not in wanted and row['id'] not in scanned
             and type(row['sha256']) is str and re.fullmatch('[0-9a-f]{64}',row['sha256']))
        scanned.add(row['id'])
    if source['subjectVersion']==3:
        from adapters.vr_graphics_subject import validate_framework
        validate_framework(source,request['runId'])
    return value


class NativeGraphicsSubject:
    def __init__(self,send,read,clock_ms,guard,pid,*,ios=False,require_framework=False,monotonic=time.monotonic,sleep=time.sleep):
        need(all(callable(v) for v in (send,read,clock_ms,guard,monotonic,sleep)) and integer(pid,1) and type(ios) is bool and type(require_framework) is bool)
        self.send,self.original,self.clock_ms,self.guard,self.pid=send,read,clock_ms,guard,pid
        self.ios,self.monotonic,self.sleep=ios,monotonic,sleep
        self.require_framework=require_framework
        self.last=None

    def read(self,run,*,require_avatar=False,require_framework=False):
        try:
            need(type(require_avatar) is bool and type(require_framework) is bool)
            request=command(dict(schemaVersion=1,commandId=('ios-' if self.ios else '')+uuid.uuid4().hex,
                action='feature-graphics-subject-observe',runId=run),ios=self.ios)
            need(self.guard() is not False)
            started=previous=self.monotonic();need(number(started,0,1e15))
            requested=self.clock_ms();need(integer(requested,1))
            self.send(request)
            for attempt in range(51):
                need(self.guard() is not False)
                raw=self.original();need(type(raw) is str and len(raw.encode())<=LIMIT)
                try:value=decode(raw) if raw else None
                except json.JSONDecodeError:value=None
                need(self.guard() is not False)
                now=self.monotonic();need(number(now,0,1e15) and now>=previous and now-started<(1.5 if self.ios else 5))
                previous=now
                if type(value) is dict and value.get('requestId')==request['commandId']:
                    epoch=value.get('capturedEpochMs') if self.ios else self.clock_ms()
                    need(integer(epoch,1) and (self.ios or epoch>=requested))
                    validate(value,request,self.pid,epoch,require_avatar=require_avatar,require_framework=(require_framework or self.require_framework))
                    need(self.ios or value['requestedEpochMs']>=requested)
                    if self.last is not None:
                        need(value['instance']==self.last['instance'] and value['sequence']>self.last['sequence']
                             and value['capturedEpochMs']>=self.last['capturedEpochMs']
                             and value['source']['subjectVersion']==self.last['source']['subjectVersion'])
                    need(self.guard() is not False)
                    if not self.ios:
                        current=self.clock_ms();need(integer(current,1) and current>=epoch)
                        fresh(value['capturedEpochMs'],current)
                    now=self.monotonic();need(number(now,0,1e15) and now>=previous and now-started<(1.5 if self.ios else 5))
                    self.last=deepcopy(value);return value
                if attempt<50:self.sleep(.1)
        except Exception:
            raise NativeUIError('Original Graphics subject observation is unavailable or invalid') from None
        raise NativeUIError('Original Graphics subject observation did not produce this request')
