"""Original actual ScriptManager/engine/worker QObject deaths, never table absence."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import math
import time
import uuid
from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.normal_ui import NativeUIError
from feature_journeys.contract import identifier

VERSION=1
FILE='feature-script-object-lifetimes.json'
LIMIT=65536
ACTION='feature-script-object-lifetimes-observe'


def command(value):
    exact(value,{'schemaVersion','commandId','action'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['action']==ACTION)
    identifier(value['commandId']);return value


def objects(value,captured):
    exact(value,{'complete','revision','capturedEpochMs','objects'})
    need(value['complete'] is True and integer(value['revision'],0,1000000000)
        and integer(value['capturedEpochMs'],1,captured) and type(value['objects']) is list and len(value['objects'])<=128)
    ids=[];revision=0
    for row in value['objects']:
        exact(row,{'instance','registeredEpochMs','managerAlive','engineAlive','workerCreated','workerAlive',
            'managerDestroyedEpochMs','engineDestroyedEpochMs','workerCreatedEpochMs','workerDestroyedEpochMs'})
        identifier(row['instance']);ids.append(row['instance'])
        need(integer(row['registeredEpochMs'],1,value['capturedEpochMs'])
            and all(type(row[key]) is bool for key in ('managerAlive','engineAlive','workerCreated','workerAlive')))
        revision+=1
        for kind in ('manager','engine','worker'):
            alive=row[kind+'Alive'];death=row[kind+'DestroyedEpochMs']
            if kind=='worker' and not row['workerCreated']:
                need(alive is False and type(death) is int and death==0
                    and type(row['workerCreatedEpochMs']) is int and row['workerCreatedEpochMs']==0)
                continue
            born=row['workerCreatedEpochMs'] if kind=='worker' else row['registeredEpochMs']
            need(integer(born,row['registeredEpochMs'],value['capturedEpochMs']))
            if kind=='worker':revision+=1
            if alive:need(type(death) is int and death==0)
            else:need(integer(death,born,value['capturedEpochMs']));revision+=1
        if row['workerCreated'] and not row['managerAlive']:
            need(row['workerCreatedEpochMs']<=row['managerDestroyedEpochMs'])
    need(ids==sorted(set(ids)) and revision==value['revision'])
    return value


def validate(value,request,pid,epoch,*,previous=None):
    command(request)
    exact(value,{'scriptObjectLifetimesVersion','commandId','instance','sequence','processId',
        'requestedEpochMs','capturedEpochMs','source'})
    need(type(value['scriptObjectLifetimesVersion']) is int and value['scriptObjectLifetimesVersion']==VERSION
        and value['commandId']==request['commandId'] and integer(pid,1) and type(value['processId']) is int and value['processId']==pid
        and integer(value['sequence'],1,1000000000) and integer(value['requestedEpochMs'],1)
        and integer(value['capturedEpochMs'],value['requestedEpochMs'],value['requestedEpochMs']+1500))
    identifier(value['instance']);fresh(value['capturedEpochMs'],epoch)
    source=objects(value['source'],value['capturedEpochMs'])
    need(source['capturedEpochMs']>=value['requestedEpochMs']);fresh(source['capturedEpochMs'],epoch)
    if previous is not None:
        validate(previous,dict(schemaVersion=1,commandId=previous['commandId'],action=ACTION),pid,previous['capturedEpochMs'])
        need(value['instance']==previous['instance'] and value['sequence']>previous['sequence']
            and value['commandId']!=previous['commandId'] and value['requestedEpochMs']>=previous['requestedEpochMs']
            and value['capturedEpochMs']>=previous['capturedEpochMs']
            and source['capturedEpochMs']>=previous['source']['capturedEpochMs'] and source['revision']>=previous['source']['revision'])
        current={row['instance']:row for row in source['objects']}
        for old in previous['source']['objects']:
            need(old['instance'] in current);row=current[old['instance']]
            need(row['registeredEpochMs']==old['registeredEpochMs'])
            for kind in ('manager','engine','worker'):
                if kind=='worker' and not old['workerCreated']:continue
                need(not row[kind+'Alive'] or old[kind+'Alive'])
                if not old[kind+'Alive']:need(row[kind+'DestroyedEpochMs']==old[kind+'DestroyedEpochMs'])
            if old['workerCreated']:
                need(row['workerCreated'] and row['workerCreatedEpochMs']==old['workerCreatedEpochMs'])
    return value


def selected(value,manager):
    """The caller pins manager from original compiled/assigned Script evidence."""
    identifier(manager)
    validate(value,dict(schemaVersion=1,commandId=value['commandId'],action=ACTION),value['processId'],value['capturedEpochMs'])
    rows=[row for row in value['source']['objects'] if row['instance']==manager];need(len(rows)==1)
    return deepcopy(rows[0])


def destroyed(value,manager):
    row=selected(value,manager)
    need(not row['managerAlive'] and not row['engineAlive'] and not row['workerAlive'])
    return row


class NativeScriptObjectLifetimes:
    def __init__(self,send,original,clock_ms,guard,pid,*,monotonic=time.monotonic,sleep=time.sleep):
        need(all(callable(fn) for fn in (send,original,clock_ms,guard,monotonic,sleep)) and integer(pid,1))
        self.send,self.original,self.clock_ms,self.guard,self.pid=send,original,clock_ms,guard,pid
        self.monotonic,self.sleep=monotonic,sleep;self.last=None

    def restore(self,value):
        need(self.last is None)
        validate(value,dict(schemaVersion=1,commandId=value['commandId'],action=ACTION),self.pid,value['capturedEpochMs'])
        self.last=deepcopy(value)

    def read(self,after_sequence=0):
        try:
            need(integer(after_sequence,0,1000000000) and (self.last is None or after_sequence>=self.last['sequence']) and self.guard() is not False)
            started=previous=self.monotonic();need(number(started,0,1e15))
            barrier=self.clock_ms();need(integer(barrier,1))
            request=dict(schemaVersion=1,commandId=uuid.uuid4().hex,action=ACTION);command(request);self.send(deepcopy(request))
            for attempt in range(51):
                need(self.guard() is not False);raw=self.original();need(type(raw) is str and len(raw.encode())<=LIMIT)
                try:value=decode(raw) if raw else None
                except json.JSONDecodeError:value=None
                now=self.monotonic();need(number(now,previous,started+5) and self.guard() is not False);previous=now
                if type(value) is dict and value.get('commandId')==request['commandId']:
                    epoch=self.clock_ms();need(integer(epoch,barrier));validate(value,request,self.pid,epoch,previous=self.last)
                    need(value['sequence']>after_sequence and value['requestedEpochMs']>=barrier)
                    candidate=deepcopy(value);result=deepcopy(value)
                    need(self.guard() is not False)
                    measured=self.monotonic();final_epoch=self.clock_ms();finished=self.monotonic()
                    need(number(measured,previous,started+1.5) and number(finished,measured,started+1.5)
                        and integer(final_epoch,epoch))
                    captured=value['source']['capturedEpochMs'];fresh(captured,final_epoch)
                    need(max(final_epoch-captured,barrier-captured+math.ceil((finished-started)*1000),
                        final_epoch-captured+math.ceil((finished-measured)*1000))<=1500)
                    self.last=candidate;return result
                if attempt<50:self.sleep(.1)
        except Exception:raise NativeUIError('Original Script object lifetimes are unavailable or invalid') from None
        raise NativeUIError('Original Script object lifetimes did not produce this request')
