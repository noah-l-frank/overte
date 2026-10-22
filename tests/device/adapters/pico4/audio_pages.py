"""Original canonical Audio page identities; absence is not Qt retirement."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import re
import time
from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.pico4.lifecycle_source import nonce

VERSION=1
FILE='navigation-ui-observation.json'
LIMIT=65536
OBJECTS=('pageId','contextId','rootId','windowId')
LIFE=('pageAlive','contextAlive','rootAlive','windowAlive')
IDENTITY=('id',*OBJECTS,'firstObservedEpochMs','originalPeakValuesEnabled')


def validate(value,epoch):
    exact(value,{'instance','sequence','capturedEpochMs','componentSourceSha256','current','originals'})
    need(nonce(value['instance']) and integer(value['sequence'],1) and type(value['componentSourceSha256']) is str
        and re.fullmatch('[0-9a-f]{64}',value['componentSourceSha256']) and type(value['current']) is str)
    fresh(value['capturedEpochMs'],epoch)
    rows=value['originals'];need(type(rows) is list and len(rows)<=64);ids=set();current=[]
    for row in rows:
        exact(row,{*IDENTITY,*LIFE,'alive','attached','visible','current'})
        need(nonce(row['id']) and row['id'] not in ids and all(nonce(row[key]) for key in OBJECTS)
            and len({row[key] for key in OBJECTS})==len(OBJECTS)
            and integer(row['firstObservedEpochMs'],1,value['capturedEpochMs'])
            and all(type(row[key]) is bool for key in (*LIFE,'alive','attached','visible','current','originalPeakValuesEnabled')))
        ids.add(row['id']);need(row['alive']==(row['pageAlive'] or row['contextAlive']))
        if row['attached']:need(row['pageAlive'] and row['contextAlive'] and row['rootAlive'])
        if row['visible']:need(row['attached'] and row['windowAlive'])
        if row['current']:need(row['visible']);current.append(row['id'])
    need(current==([value['current']] if value['current'] else []));return value


def accept(previous,current):
    if previous is not None:
        need(current['instance']==previous['instance'] and current['componentSourceSha256']==previous['componentSourceSha256']
            and current['sequence']>previous['sequence'] and current['capturedEpochMs']>=previous['capturedEpochMs']
            and len(current['originals'])>=len(previous['originals']))
        for old,new in zip(previous['originals'],current['originals']):
            need(all(old[key]==new[key] for key in IDENTITY) and all(old[key] or not new[key] for key in LIFE))
    return deepcopy(current)


def original(value,identifier):
    rows=[row for row in value['originals'] if row['id']==identifier];need(len(rows)==1);return deepcopy(rows[0])


class PicoAudioPages:
    def __init__(self,read,clock_ms,guard,pid,bridge,source_lock,*,monotonic=time.monotonic,sleep=time.sleep):
        from adapters.script_journey.lock import ScriptSourceLock
        from adapters.pico4.navigation import identifier
        need(all(callable(f) for f in (read,clock_ms,guard,monotonic,sleep)) and integer(pid,1)
            and identifier(bridge) and isinstance(source_lock,ScriptSourceLock))
        self.read,self.clock_ms,self.guard,self.pid,self.bridge,self.source_lock=read,clock_ms,guard,pid,bridge,source_lock
        self.monotonic,self.sleep=monotonic,sleep;self.previous,self.last_raw,self.last_sha256=None,None,None
    def packet(self,raw,epoch):
        from adapters.pico4.navigation import validate_snapshot
        need(type(raw) is str and len(raw.encode())<=LIMIT);packet=decode(raw);validate_snapshot(packet,self.pid,epoch)
        need(packet['bridgeId']==self.bridge and packet.get('picoAudioPageVersion')==VERSION)
        value=packet['picoAudioPages'];validate(value,epoch)
        need(value['capturedEpochMs']<=packet['updatedEpochMs'] and (packet['open'] or not value['current']))
        return packet
    def restore(self,value):
        validate(value,value['capturedEpochMs']);need(self.guard() is not False)
        need(self.previous is None or self.previous==value);self.previous=deepcopy(value)
    def capture(self):
        with self.source_lock.held():
            need(self.guard() is not False);started=last=self.monotonic();requested=self.clock_ms()
            need(number(started,0,1e15) and integer(requested,1))
            for attempt in range(51):
                need(self.guard() is not False);raw=self.read()
                need(type(raw) is str and len(raw.encode())<=LIMIT)
                try:value=decode(raw) if raw else None
                except json.JSONDecodeError:value=None
                now=self.monotonic();need(number(now,0,1e15) and last<=now and now-started<5);last=now
                if type(value) is dict and type(value.get('picoAudioPages')) is dict:
                    epoch=self.clock_ms();packet=self.packet(raw,epoch);pages=packet['picoAudioPages']
                    if self.previous is None or pages['sequence']>self.previous['sequence']:
                        accepted=accept(self.previous,pages);result=deepcopy(packet);digest=hashlib.sha256(raw.encode()).hexdigest()
                        need(self.guard() is not False);final_epoch=self.clock_ms();fresh(pages['capturedEpochMs'],final_epoch)
                        completed=self.monotonic();captured=pages['capturedEpochMs']
                        need(number(completed,0,1e15) and last<=completed and completed-started<5
                            and max(final_epoch-captured,requested-captured+(completed-started)*1000)<=1500)
                        self.previous,self.last_raw,self.last_sha256=accepted,raw,digest;return result
                if attempt<50:self.sleep(.1)
            need(False)
