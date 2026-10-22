"""Original loaded bookmarks and stable persistence bytes; no mutation or verdict."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import json
import re
import time
import uuid

from adapters.native_clock_join import digest
from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.normal_ui import NativeUIError

VERSION=1
FILE='feature-ios-location-bookmarks.json'
LIMIT=262144
FILE_LIMIT=65536
REASONS={'location-unavailable','open-error','unsafe-file','too-large','read-error','changed-file'}


def command(value):
    exact(value,{'schemaVersion','commandId','action','runId'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['action']=='feature-ios-location-bookmarks'
         and type(value['commandId']) is str and re.fullmatch('ios-[a-f0-9]{32}',value['commandId'])
         and type(value['runId']) is str and re.fullmatch('[a-f0-9]{32}',value['runId']))
    return value


def original_bytes(value):
    exact(value,{'source','status','reason','bytes','sha256','contentBase64','identity'})
    need(value['source']=='app-local-data/bookmarks.json' and value['status'] in ('ready','absent','unavailable'))
    if value['status']!='ready':
        need(value['reason'] in REASONS if value['status']=='unavailable' else value['reason']=='')
        need(all(value[key] is None for key in ('bytes','sha256','contentBase64','identity')));return None
    need(value['reason']=='' and integer(value['bytes'],0,FILE_LIMIT) and type(value['sha256']) is str
         and re.fullmatch('[a-f0-9]{64}',value['sha256']) and type(value['contentBase64']) is str
         and len(value['contentBase64'])<=4*((FILE_LIMIT+2)//3))
    raw=base64.b64decode(value['contentBase64'],validate=True)
    need(base64.b64encode(raw).decode()==value['contentBase64'] and len(raw)==value['bytes']
         and hashlib.sha256(raw).hexdigest()==value['sha256'])
    exact(value['identity'],{'device','inode'})
    for key in ('device','inode'):
        text=value['identity'][key];need(type(text) is str and re.fullmatch('0|[1-9][0-9]{0,19}',text))
        need(int(text)<2**64 and (key!='inode' or int(text)>0))
    return raw


def validate(value,query,pid,epoch=None,previous=None):
    command(query)
    exact(value,{'iosLocationBookmarksVersion','requestId','runId','instance','sequence','processId','clockDomain',
                 'clockBefore','clockAfter','loaded','file'})
    need(type(value['iosLocationBookmarksVersion']) is int and value['iosLocationBookmarksVersion']==VERSION
         and value['requestId']==query['commandId'] and value['runId']==query['runId']
         and integer(pid,1) and type(value['processId']) is int and value['processId']==pid
         and type(value['instance']) is str and re.fullmatch('[a-f0-9]{32}',value['instance'])
         and integer(value['sequence'],1,1_000_000_000) and value['clockDomain']=='native-main-bookmarks')
    for clock in (value['clockBefore'],value['clockAfter']):
        exact(clock,{'epochMs','monotonicMs'});need(integer(clock['epochMs'],1) and integer(clock['monotonicMs'],0))
    before,after=value['clockBefore'],value['clockAfter']
    utc=after['epochMs']-before['epochMs'];mono=after['monotonicMs']-before['monotonicMs']
    need(0<=utc<1500 and 0<=mono<1500 and abs(utc-mono)<=250)
    if epoch is not None:fresh(after['epochMs'],epoch)
    loaded=value['loaded'];exact(loaded,{'source','entries','loadError'})
    need(loaded['source']=='LocationBookmarks.getBookmarks' and type(loaded['entries']) is dict and type(loaded['loadError']) is bool)
    need(len(json.dumps(loaded['entries'],allow_nan=False,ensure_ascii=False,separators=(',',':')).encode())<=65536)
    original_bytes(value['file'])
    need(len(json.dumps(value,allow_nan=False,ensure_ascii=False).encode())<=LIMIT)
    if previous is not None:
        validate(previous,dict(query,commandId=previous['requestId']),pid)
        need(value['instance']==previous['instance'] and value['sequence']>previous['sequence']
            and value['requestId']!=previous['requestId']
            and before['epochMs']>=previous['clockAfter']['epochMs'] and before['monotonicMs']>=previous['clockAfter']['monotonicMs'])
    return value


def saved(value):
    """Parse exact original bytes, preserving unavailable/invalid distinctions."""
    raw=original_bytes(value)
    if raw is None:return dict(status=value['status'],entries=None)
    try:
        entries=decode(raw.decode('utf-8'))
        if type(entries) is not dict:raise ValueError()
    except (UnicodeError,ValueError,RuntimeError):return dict(status='invalid-json',entries=None)
    return dict(status='ready',entries=entries)


def string_entries(value):
    need(type(value) is dict and len(value)<=1024)
    for name,address in value.items():
        need(type(name) is str and 0<len(name)<=4096 and type(address) is str and len(address)<=4096)
    return deepcopy(value)


class IOSLocationBookmarks:
    def __init__(self,send,read,clock_ms,guard,pid,*,monotonic=time.monotonic,sleep=time.sleep):
        need(all(callable(fn) for fn in (send,read,clock_ms,guard,monotonic,sleep)) and integer(pid,1))
        self.send,self.original,self.clock_ms,self.guard,self.pid=send,read,clock_ms,guard,pid
        self.monotonic,self.sleep=monotonic,sleep;self.last=self.acquisition=None

    def read(self,run):
        try:
            query=command(dict(schemaVersion=1,commandId='ios-'+uuid.uuid4().hex,action='feature-ios-location-bookmarks',runId=run))
            need(self.guard() is not False);started=last=self.monotonic();need(number(started,0,1e15))
            requested=self.clock_ms();need(integer(requested,1));self.send(deepcopy(query))
            for attempt in range(61):
                need(self.guard() is not False);raw=self.original();need(type(raw) is str and len(raw.encode())<=LIMIT)
                try:value=decode(raw) if raw else None
                except json.JSONDecodeError:value=None
                now=self.monotonic();need(number(now,last,1e15) and now-started<1.5);last=now
                if type(value) is dict and value.get('requestId')==query['commandId']:
                    epoch=self.clock_ms();need(integer(epoch,requested))
                    validate(value,query,self.pid,epoch,self.last);need(value['clockBefore']['epochMs']>=requested)
                    need(self.guard() is not False);ended=self.monotonic();need(number(ended,last,started+1.5) and ended-started<1.5)
                    self.last=deepcopy(value)
                    self.acquisition=dict(iosLocationBookmarksAcquisitionVersion=1,hostBeforeMonotonic=started,
                        hostAfterMonotonic=ended,nativeRequestedEpochMs=requested,nativeAfterEpochMs=epoch,originalSha256=digest(value))
                    return deepcopy(value)
                if attempt<60:self.sleep(.025)
        except Exception:raise NativeUIError('Original iOS location bookmarks are unavailable or invalid') from None
        raise NativeUIError('Original iOS location bookmarks did not produce this request')
