"""Original Places models/queues, independent from input ACKs and saved bytes."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import re
import time
import uuid

from adapters.native_clock_join import digest
from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.normal_ui import NativeUIError
from ios.adapters.places_controls import identity,qml_source,snapshot as controls_snapshot

VERSION=2
FILE='feature-ios-places-model.json'
LIMIT=262144
ACTION='feature-ios-places-model'
PLACE_FIELDS={'placeName','placeAddress','placeDescription','attendance','capacity','placeId'}
BOOKMARK_FIELDS={'bookmarkName','bookmarkAddress'}
SERVER_FIELDS={'serverUrl','serverIndex','serverRegion','fetched','pinned','failed'}


def command(value):
    exact(value,{'schemaVersion','commandId','action','runId'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['action']==ACTION
         and type(value['commandId']) is str and re.fullmatch('ios-[a-f0-9]{32}',value['commandId'])
         and type(value['runId']) is str and re.fullmatch('[a-f0-9]{32}',value['runId']))
    return value


def text(value,maximum=16384):
    need(type(value) is str and len(value)<=maximum);value.encode('utf-8');return value


def tree(value,depth=0):
    need(depth<=12)
    if value is None or type(value) is bool:return
    if type(value) is str:text(value);return
    if type(value) in (int,float):need(number(value,-1e15,1e15));return
    if type(value) is list:
        need(len(value)<=1000)
        for entry in value:tree(entry,depth+1)
        return
    need(type(value) is dict and len(value)<=1024)
    for key,entry in value.items():text(key,4096);tree(entry,depth+1)


def model(value,kind):
    exact(value,{'visible','rows'});need(type(value['visible']) is bool and type(value['rows']) is list and len(value['rows'])<=1000)
    for row in value['rows']:
        exact(row,{'places':PLACE_FIELDS,'bookmarks':BOOKMARK_FIELDS,'servers':SERVER_FIELDS}[kind])
        if kind=='places':
            for key in ('placeName','placeAddress','placeDescription','placeId'):text(row[key])
            for key in ('attendance','capacity'):need(number(row[key],0,1e9))
        elif kind=='bookmarks':
            for entry in row.values():text(entry,4096)
        else:
            for key in ('serverUrl','serverRegion'):text(row[key],4096)
            need(integer(row['serverIndex'],0,1000))
            for key in ('fetched','pinned','failed'):need(type(row[key]) is bool)
    return value


def root(value,shown,version=1):
    exact(value,{'rootId','qmlSource','windowPresent','visible','active','loading','currentAddress','directoryWarning',
        'records','bookmarkAddresses','maturityFilter','pendingCommands','timerRunning','tab','search','dialog','lists'}
        | ({'popup','serverDraft'} if version==2 else set()))
    identity(value['rootId']);qml_source(value['qmlSource'])
    for key in ('windowPresent','visible','active','loading','timerRunning'):need(type(value[key]) is bool)
    need((not value['visible'] or value['windowPresent']) and value['active']==(shown and value['visible']))
    for key in ('currentAddress','directoryWarning','search'):text(value[key])
    if version==2:
        need(value['popup'] in ('none','bookmark','ratings','location'));text(value['serverDraft'],4096)
    need(integer(value['tab'],0,2) and type(value['records']) is list and type(value['bookmarkAddresses']) is dict
         and type(value['maturityFilter']) is list and len(value['maturityFilter'])<=16
         and type(value['pendingCommands']) is list and len(value['pendingCommands'])<=256)
    for entry in value['maturityFilter']:text(entry,128)
    for key in ('records','bookmarkAddresses','pendingCommands'):tree(value[key])
    for entry in value['records']:need(type(entry) is dict)
    for entry in value['pendingCommands']:
        need(type(entry) is dict and entry.get('channel')=='com.overte.places');text(entry.get('action'),128)
    dialog=value['dialog'];exact(dialog,{'visible','originalName','address','name'});need(type(dialog['visible']) is bool)
    if version==2:need(dialog['visible']==(value['popup']=='bookmark'))
    for key in ('originalName','address','name'):text(dialog[key],4096)
    exact(value['lists'],{'places','bookmarks','servers'})
    for kind,original in value['lists'].items():model(original,kind)
    return value


def validate(value,query,pid,epoch=None,previous=None):
    command(query);need(type(value) is dict and type(value.get('iosPlacesModelVersion')) is int and value['iosPlacesModelVersion'] in (1,2))
    version=value['iosPlacesModelVersion'];exact(value,{'iosPlacesModelVersion','requestId','runId','instance','sequence','processId',
        'clockDomain','clockBefore','clockAfter','complete','tabletShown','roots'}|({'preferences'} if version==2 else set()))
    need(type(value['iosPlacesModelVersion']) is int
         and value['requestId']==query['commandId'] and value['runId']==query['runId']
         and integer(pid,1) and type(value['processId']) is int and value['processId']==pid
         and type(value['instance']) is str and re.fullmatch('[a-f0-9]{32}',value['instance'])
         and integer(value['sequence'],1,1_000_000_000) and value['clockDomain']=='native-main-places-model'
         and type(value['complete']) is bool and type(value['tabletShown']) is bool
         and type(value['roots']) is list and len(value['roots'])<=32)
    if version==2:
        from ios.adapters.places_preferences import validate as preferences
        preferences(value['preferences'])
    for clock in (value['clockBefore'],value['clockAfter']):
        exact(clock,{'epochMs','monotonicMs'});need(integer(clock['epochMs'],1) and integer(clock['monotonicMs'],0))
    before,after=value['clockBefore'],value['clockAfter']
    utc=after['epochMs']-before['epochMs'];mono=after['monotonicMs']-before['monotonicMs']
    need(0<=utc<1500 and 0<=mono<1500 and abs(utc-mono)<=250)
    if epoch is not None:fresh(after['epochMs'],epoch)
    ids=set();active=0
    for entry in value['roots']:
        root(entry,value['tabletShown'],version);need(entry['rootId'] not in ids);ids.add(entry['rootId']);active+=entry['active']
    need(active<=1 and len(json.dumps(value,allow_nan=False,ensure_ascii=False).encode())<=LIMIT)
    if previous is not None:
        validate(previous,dict(query,commandId=previous['requestId']),pid)
        need(version>=previous['iosPlacesModelVersion'] and value['instance']==previous['instance'] and value['sequence']>previous['sequence']
             and value['requestId']!=previous['requestId'] and before['epochMs']>=previous['clockAfter']['epochMs']
             and before['monotonicMs']>=previous['clockAfter']['monotonicMs'])
    return value


def current(value):
    original(value)
    need(value['complete'] is True)
    active=[entry for entry in value['roots'] if entry['active']];need(len(active)==1)
    return deepcopy(active[0])


def join_controls(value,controls):
    """Join originals by actual root/source/PID, never by requested row values."""
    controls_snapshot(controls);actual=current(value)
    need(controls['open'] and controls['scope']['processId']==value['processId']
         and value['clockAfter']['epochMs']<=controls['scope']['sampleEpochMs']<value['clockAfter']['epochMs']+1500)
    pages=[entry for entry in controls['controls'] if entry['id']=='places.page']
    need(len(pages)==1 and pages[0]['rootId']==actual['rootId'] and pages[0]['qmlSource']==actual['qmlSource'])
    return actual


def drained(value):
    """QML queue condition only; HTTP/native callbacks require separate sources."""
    original(value)
    need(value['complete'] is True)
    return all(not entry['active'] and not entry['pendingCommands'] and not entry['timerRunning']
               and not entry['loading'] and not entry['dialog']['visible'] and entry.get('popup','none')=='none' for entry in value['roots'])


def original(value):
    need(type(value) is dict)
    return validate(value,dict(schemaVersion=1,commandId=value.get('requestId'),action=ACTION,runId=value.get('runId')),
                    value.get('processId'))


class IOSPlacesModel:
    _limit=LIMIT
    _action=ACTION
    _command=staticmethod(command)
    _validate=staticmethod(validate)
    _acquisition_key='iosPlacesModelAcquisitionVersion'
    def __init__(self,send,read,clock_ms,guard,pid,*,monotonic=time.monotonic,sleep=time.sleep):
        need(all(callable(fn) for fn in (send,read,clock_ms,guard,monotonic,sleep)) and integer(pid,1))
        self.send,self.original,self.clock_ms,self.guard,self.pid=send,read,clock_ms,guard,pid
        self.monotonic,self.sleep=monotonic,sleep;self.last=self.acquisition=None

    def read(self,run,*,native_before_floor=None):
        try:
            native_before_floor=deepcopy(native_before_floor)
            query=self._command(dict(schemaVersion=1,commandId='ios-'+uuid.uuid4().hex,action=self._action,runId=run))
            need(self.guard() is not False);started=last=self.monotonic();need(number(started,0,1e15))
            if native_before_floor is None:requested=self.clock_ms()
            else:
                # This is a retained BEFORE floor, not a newly sampled now.
                # The owner separately joins its actual raw/acquisition origin.
                from adapters.native_feature_observation import validate as native_floor
                native_floor(native_before_floor,native_before_floor['requestId'],self.pid,native_before_floor['capturedEpochMs'])
                requested=native_before_floor['capturedEpochMs']
            need(integer(requested,1));self.send(deepcopy(query))
            for attempt in range(61):
                need(self.guard() is not False);raw=self.original();need(type(raw) is str and len(raw.encode())<=self._limit)
                try:value=decode(raw,limit=self._limit) if raw else None
                except json.JSONDecodeError:value=None
                now=self.monotonic();need(number(now,last,1e15) and now-started<1.5);last=now
                if type(value) is dict and value.get('requestId')==query['commandId']:
                    epoch=self.clock_ms();need(integer(epoch,requested))
                    if native_before_floor is not None:need(epoch-requested<1500)
                    self._validate(value,query,self.pid,epoch,self.last);need(value['clockBefore']['epochMs']>=requested)
                    need(self.guard() is not False);ended=self.monotonic();need(number(ended,last,started+1.5) and ended-started<1.5)
                    self.last=deepcopy(value)
                    self.acquisition=dict(hostBeforeMonotonic=started,hostAfterMonotonic=ended,
                        nativeRequestedEpochMs=requested,nativeAfterEpochMs=epoch,originalSha256=digest(value))
                    self.acquisition[self._acquisition_key]=1
                    if native_before_floor is not None:self.acquisition['nativeBeforeOriginalFloorSha256']=digest(native_before_floor)
                    return deepcopy(value)
                if attempt<60:self.sleep(.025)
        except Exception:raise NativeUIError('Original iOS Places source is unavailable or invalid') from None
        raise NativeUIError('Original iOS Places source did not produce this request')
