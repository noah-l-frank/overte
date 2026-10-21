"""Original native scene request/queued-handoff lifetime; never a scene verdict."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import math
import re
import time
from urllib.parse import unquote,urlsplit,urlunsplit
import uuid
from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.normal_ui import NativeUIError

VERSION=1
FILE='feature-scene-load.json'
PHASES={'request':{'requested','reply','parsed','queued','committed','failed','stale','empty','destroyed'},
        'delivery':{'requested','running','delivered','destroyed'}}
RANK={'requested':0,'reply':1,'running':1,'parsed':2,'delivered':2,'queued':3,'committed':4,
      'failed':5,'stale':5,'empty':5,'destroyed':6}


def nonce(value):return type(value) is str and re.fullmatch('[0-9a-f]{32}',value) is not None


def command(value):
    exact(value,{'schemaVersion','commandId','action','runId'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['action']=='feature-scene-load-observe'
         and nonce(value['commandId']) and nonce(value['runId']))
    return value


def resource_hash(url):
    need(type(url) is str and 0<len(url)<=2048 and not any(ord(c)<=32 or ord(c)==127 for c in url))
    parsed=urlsplit(url);parsed.port
    need(parsed.scheme in ('http','https','file') and parsed.username is None and parsed.password is None and not parsed.fragment)
    # This helper consumes the actual native fully-encoded scene address. Only
    # its viewpoint query is omitted; no caller-selected expected digest is used.
    query=[item for item in parsed.query.split('&') if item and unquote(item.partition('=')[0])!='location']
    canonical=urlunsplit((parsed.scheme,parsed.netloc,parsed.path,'&'.join(query),''))
    return hashlib.sha256(canonical.encode()).hexdigest()


def validate(value,request,pid,epoch):
    command(request)
    exact(value,{'sceneLoadVersion','commandId','runId','instance','sequence','processId','capturedEpochMs',
        'currentGeneration','pendingLeases','complete','requests'})
    need(type(value['sceneLoadVersion']) is int and value['sceneLoadVersion']==VERSION
         and value['commandId']==request['commandId'] and value['runId']==request['runId'] and nonce(value['instance'])
         and integer(value['sequence'],1,1000000000) and integer(value['processId'],1) and value['processId']==pid
         and integer(value['currentGeneration']) and integer(value['pendingLeases'],0,128) and type(value['complete']) is bool
         and type(value['requests']) is list and len(value['requests'])<=128)
    fresh(value['capturedEpochMs'],epoch)
    seen=set();generation=0;started=0;pending=0
    for row in value['requests']:
        exact(row,{'id','kind','generation','resourceSha256','startedEpochMs','updatedEpochMs','releasedEpochMs','phase','pending','result','bytes'})
        need(nonce(row['id']) and row['id'] not in seen and type(row['kind']) is str and row['kind'] in PHASES
             and type(row['phase']) is str and row['phase'] in PHASES[row['kind']] and type(row['pending']) is bool
             and type(row['resourceSha256']) is str and re.fullmatch('[0-9a-f]{64}',row['resourceSha256'])
             and integer(row['startedEpochMs'],max(1,started)) and integer(row['updatedEpochMs'],row['startedEpochMs'],value['capturedEpochMs']))
        if row['kind']=='request':
            need(integer(row['generation'],generation+1,value['currentGeneration']));generation=row['generation']
        else:need(type(row['generation']) is int and row['generation']==0 and row['result'] is None and row['bytes'] is None)
        need((row['result'] is None and row['bytes'] is None)
             or integer(row['result'],0,8) and integer(row['bytes'],0,2**31-1))
        if row['phase'] in ('requested','empty'):need(row['result'] is None and row['bytes'] is None)
        if row['phase'] in ('reply','parsed','queued','committed'):
            need(row['result'] is not None)
            if row['phase']!='reply':need(row['result']==0 and row['bytes']>0)
        if row['pending']:need(row['releasedEpochMs'] is None and row['phase']!='destroyed');pending+=1
        else:need(integer(row['releasedEpochMs'],row['startedEpochMs'],value['capturedEpochMs'])
            and row['updatedEpochMs']==row['releasedEpochMs'] and row['phase'] in ('committed','failed','stale','empty','delivered','destroyed'))
        seen.add(row['id']);started=row['startedEpochMs']
    need(pending==value['pendingLeases'])
    return value


def continuity(previous,value,pid):
    if previous is None:return
    validate(previous,dict(schemaVersion=1,commandId=previous['commandId'],action='feature-scene-load-observe',runId=previous['runId']),pid,previous['capturedEpochMs'])
    need(value['instance']==previous['instance'] and value['sequence']>previous['sequence']
         and value['capturedEpochMs']>=previous['capturedEpochMs'] and value['currentGeneration']>=previous['currentGeneration']
         and value['runId']==previous['runId'] and len(value['requests'])>=len(previous['requests'])
         and (previous['complete'] or value['complete'] is False))
    for old,new in zip(previous['requests'],value['requests']):
        need(all(old[key]==new[key] for key in ('id','kind','generation','resourceSha256','startedEpochMs'))
             and new['updatedEpochMs']>=old['updatedEpochMs'] and RANK[new['phase']]>=RANK[old['phase']]
             and (old['pending'] or new==old)
             and (old['phase'] not in ('committed','failed','stale','empty','delivered','destroyed') or old['phase']==new['phase'])
             and (old['result'] is None or (new['result'],new['bytes'])==(old['result'],old['bytes'])))


def committed(value,url):
    """One actual committed generation plus absence of every traced live lease.

    Independent subject/view, HTTP delivery and rendered pixels are still needed.
    """
    need(type(value) is dict)
    validate(value,dict(schemaVersion=1,commandId=value.get('commandId'),action='feature-scene-load-observe',runId=value.get('runId')),
             value.get('processId'),value.get('capturedEpochMs'))
    need(value['complete'] is True and value['pendingLeases']==0)
    rows=[row for row in value['requests'] if row['kind']=='request' and row['generation']==value['currentGeneration']]
    need(len(rows)==1 and rows[0]['phase']=='committed' and rows[0]['pending'] is False and rows[0]['resourceSha256']==resource_hash(url))
    return deepcopy(rows[0])


class NativeSceneLoads:
    def __init__(self,send,original,clock_ms,guard,pid,*,monotonic=time.monotonic,sleep=time.sleep):
        need(all(callable(value) for value in (send,original,clock_ms,guard,monotonic,sleep)) and integer(pid,1))
        self.send,self.original,self.clock_ms,self.guard,self.pid=send,original,clock_ms,guard,pid
        self.monotonic,self.sleep,self.last=monotonic,sleep,None

    def read(self,run):
        try:
            request=command(dict(schemaVersion=1,commandId=uuid.uuid4().hex,action='feature-scene-load-observe',runId=run))
            started=previous=self.monotonic();need(number(started,0,1e15) and self.guard() is not False)
            requested=self.clock_ms();need(integer(requested,1));self.send(request)
            for attempt in range(51):
                need(self.guard() is not False)
                raw=self.original();need(type(raw) is str and len(raw.encode())<=262144)
                try:value=decode(raw) if raw else None
                except json.JSONDecodeError:value=None
                current=self.monotonic();need(number(current,previous,1e15) and current-started<5);previous=current
                if type(value) is dict and value.get('commandId')==request['commandId']:
                    epoch=self.clock_ms();need(integer(epoch,requested))
                    validate(value,request,self.pid,epoch);need(value['capturedEpochMs']>=requested and value['complete'] is True)
                    continuity(self.last,value,self.pid)
                    need(self.guard() is not False)
                    freshness_started=self.monotonic();need(number(freshness_started,previous,1e15));previous=freshness_started
                    final_epoch=self.clock_ms();need(integer(final_epoch,epoch));fresh(value['capturedEpochMs'],final_epoch)
                    need(self.guard() is not False)
                    finished=self.monotonic();need(number(finished,previous,1e15) and finished-started<5
                        and final_epoch-value['capturedEpochMs']+math.ceil((finished-freshness_started)*1000)<=1500)
                    self.last=deepcopy(value);return value
                if attempt<50:self.sleep(.1)
        except Exception:raise NativeUIError('Original native scene load observation is unavailable or invalid') from None
        raise NativeUIError('Original native scene load observation did not produce this request')
