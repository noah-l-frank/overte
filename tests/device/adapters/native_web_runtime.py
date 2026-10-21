"""Original native/Android UI-fence Web inventories; no expected cleanup as facts."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import math
import re
import time
from urllib.parse import urlsplit
import uuid

from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.normal_ui import NativeUIError
from feature_journeys.contract import identifier

VERSION=2
FILE='feature-web-runtime.json'
LIMIT=262144


def handle(value):
    return type(value) is str and re.fullmatch('[1-9][0-9]{0,18}',value) is not None and int(value)<=9223372036854775807


def digest(value):return type(value) is str and re.fullmatch('[0-9a-f]{64}',value) is not None


def command(value):
    exact(value,{'schemaVersion','commandId','action','runId','fixtureUrl'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['action']=='feature-web-runtime-observe')
    identifier(value['commandId']);identifier(value['runId']);root=value['fixtureUrl']
    need(type(root) is str and 0<len(root)<=512 and root.isascii() and not any(ord(c)<=32 or ord(c)==127 for c in root))
    parsed=urlsplit(root);parsed.port
    need(parsed.scheme in ('http','https') and parsed.hostname and parsed.username is None and parsed.password is None
        and not parsed.query and not parsed.fragment and parsed.path=='/feature-fixture/v1/runs/'+value['runId']+'/')
    return value


def native_snapshot(value,epoch):
    exact(value,{'capturedEpochMs','complete','knownHandles','views'})
    need(integer(value['capturedEpochMs'],1) and value['complete'] is True
        and type(value['knownHandles']) is list and len(value['knownHandles'])<=256
        and type(value['views']) is list and len(value['views'])<=128)
    fresh(value['capturedEpochMs'],epoch);known=set();last=0
    for row in value['knownHandles']:
        exact(row,{'handle','firstObservedEpochMs','sourceSha256'})
        need(handle(row['handle']) and row['handle'] not in known and digest(row['sourceSha256'])
            and integer(row['firstObservedEpochMs'],max(1,last),value['capturedEpochMs']))
        last=row['firstObservedEpochMs'];known.add(row['handle'])
    ids=[]
    for row in value['views']:
        exact(row,{'handle','surface','creation','grant','page','sourceOwned','documentOwned','creationOwned',
            'sourceSha256','documentSha256','creationSha256','sessionActive','authorized','created','pendingCreate',
            'retryPending','suspended','loading','callbacks','scriptReplies','domPending'})
        need(handle(row['handle']) and row['handle'] in known and row['handle'] not in ids and row['surface'] in ('world','tablet')
            and all(integer(row[key],0,9007199254740991) for key in ('creation','grant','page'))
            and all(digest(row[key]) for key in ('sourceSha256','documentSha256','creationSha256'))
            and all(type(row[key]) is bool for key in ('sourceOwned','documentOwned','creationOwned','sessionActive','authorized',
                'created','pendingCreate','retryPending','suspended','loading','domPending'))
            and integer(row['callbacks'],0,32) and integer(row['scriptReplies'],0,1024))
        ids.append(row['handle'])
    need(ids==sorted(ids,key=int));return known


def validate(value,request,pid,epoch,*,require_renderers=False):
    need(type(require_renderers) is bool)
    command(request)
    exact(value,{'webRuntimeVersion','commandId','runId','instance','sequence','processId','capturedEpochMs','status','source'})
    need(type(value['webRuntimeVersion']) is int and value['webRuntimeVersion'] in (1,2)
        and (not require_renderers or value['webRuntimeVersion']==2)
        and value['commandId']==request['commandId'] and value['runId']==request['runId']
        and integer(value['processId'],1) and value['processId']==pid and integer(value['sequence'],1,1_000_000_000)
        and integer(value['capturedEpochMs'],1) and value['status'] in ('pending','ready','unavailable'))
    identifier(value['instance']);fresh(value['capturedEpochMs'],epoch)
    if value['status']!='ready':exact(value['source'],set());return value
    source=value['source'];exact(source,{'nativeBefore','java','nativeAfter'})
    before,after,java=source['nativeBefore'],source['nativeAfter'],source['java']
    first=native_snapshot(before,epoch);last=native_snapshot(after,epoch)
    need(after['knownHandles'][:len(before['knownHandles'])]==before['knownHandles'])
    exact(java,{'javaWebRuntimeVersion','commandId','instance','sequence','processId','capturedEpochMs','complete','views','creations'}|({'renderers'} if value['webRuntimeVersion']==2 else set()))
    need(type(java['javaWebRuntimeVersion']) is int and java['javaWebRuntimeVersion']==value['webRuntimeVersion'] and java['commandId']==request['commandId']
        and integer(java['sequence'],1,1_000_000_000) and integer(java['processId'],1) and java['processId']==pid
        and integer(java['capturedEpochMs'],1) and java['complete'] is True
        and type(java['views']) is list and len(java['views'])<=128 and type(java['creations']) is list and len(java['creations'])<=128)
    identifier(java['instance']);fresh(java['capturedEpochMs'],epoch)
    need(before['capturedEpochMs']<=java['capturedEpochMs']<=after['capturedEpochMs']<=value['capturedEpochMs']
        and value['capturedEpochMs']-before['capturedEpochMs']<=1500)
    ids=[]
    for row in java['views']:
        exact(row,{'handle','creation','grant','page','active','destroyed','closing','ownerCurrent','foreground','loading',
            'sourceOwned','documentOwned','sourceSha256','documentSha256'})
        need(handle(row['handle']) and row['handle'] not in ids and integer(row['creation'],1,9007199254740991)
            and all(integer(row[key],0,9007199254740991) for key in ('grant','page'))
            and all(type(row[key]) is bool for key in ('active','destroyed','closing','ownerCurrent','foreground','loading','sourceOwned','documentOwned'))
            and digest(row['sourceSha256']) and digest(row['documentSha256'])
            and (row['handle'] in first or row['sourceOwned'] or row['documentOwned']))
        ids.append(row['handle'])
    need(ids==sorted(ids,key=int));ids=[]
    for row in java['creations']:
        exact(row,{'handle','creation','sourceOwned','sourceSha256'})
        need(handle(row['handle']) and row['handle'] not in ids and integer(row['creation'],1,9007199254740991)
            and type(row['sourceOwned']) is bool and digest(row['sourceSha256']) and (row['sourceOwned'] or row['handle'] in first))
        ids.append(row['handle'])
    need(ids==sorted(ids,key=int))
    if value['webRuntimeVersion']==2:
        renderers(java['renderers'],first)
    return value


def renderers(rows,known):
    need(type(rows) is list and len(rows)<=128)
    ids=[]
    for row in rows:
        exact(row,{'id','handle','creation','sourceOwned','sourceSha256','objectAlive','threadAlive',
            'mainCallbacks','glCallbacks','retainedCallbacks','closed','released','releaseSucceeded'})
        identifier(row['id']);need(row['id'] not in ids and handle(row['handle'])
            and integer(row['creation'],1,9007199254740991) and digest(row['sourceSha256'])
            and all(type(row[key]) is bool for key in ('sourceOwned','objectAlive','threadAlive','closed','released','releaseSucceeded'))
            and all(integer(row[key],0,1000000000) for key in ('mainCallbacks','glCallbacks'))
            and integer(row['retainedCallbacks'],0,128) and (row['sourceOwned'] or row['handle'] in known)
            and (not row['released'] or row['closed']))
        ids.append(row['id'])
    need(ids==sorted(ids))
    return rows


def continuity(previous,value,pid,fixture_url):
    if previous is None:return
    request=dict(schemaVersion=1,commandId=previous['commandId'],action='feature-web-runtime-observe',
        runId=previous['runId'],fixtureUrl=fixture_url)
    validate(previous,request,pid,previous['capturedEpochMs'])
    need(previous['status']=='ready' and value['status']=='ready' and value['instance']==previous['instance']
        and value['sequence']>previous['sequence'] and value['capturedEpochMs']>=previous['capturedEpochMs']
        and value['source']['java']['instance']==previous['source']['java']['instance']
        and value['source']['java']['sequence']>previous['source']['java']['sequence']
        and value['source']['java']['capturedEpochMs']>=previous['source']['java']['capturedEpochMs']
        and value['source']['nativeBefore']['capturedEpochMs']>=previous['source']['nativeAfter']['capturedEpochMs'])
    old=previous['source']['nativeAfter']['knownHandles'];new=value['source']['nativeBefore']['knownHandles']
    need(new[:len(old)]==old)
    need(value['webRuntimeVersion']==previous['webRuntimeVersion'])
    if value['webRuntimeVersion']==2:
        old={row['id']:row for row in previous['source']['java']['renderers']}
        new={row['id']:row for row in value['source']['java']['renderers']}
        need(old.keys()<=new.keys())
        for key,before in old.items():
            after=new[key]
            need(all(before[field]==after[field] for field in ('handle','creation','sourceOwned','sourceSha256'))
                and all(not before[field] or after[field] for field in ('closed','released'))
                and (before['releaseSucceeded'] or not after['releaseSucceeded'])
                and (before['objectAlive'] or not after['objectAlive'])
                and (before['threadAlive'] or not after['threadAlive']))



def active_marker(value,source_url):
    """A separate readiness assertion. Returns only original matching rows."""
    need(type(source_url) is str);wanted=hashlib.sha256(source_url.encode()).hexdigest()
    native=[row for row in value['source']['nativeAfter']['views'] if row['surface']=='world'
        and row['sourceOwned'] and row['documentOwned'] and row['sessionActive'] and row['authorized'] and row['created']
        and not row['pendingCreate'] and not row['suspended'] and row['sourceSha256']==wanted]
    need(len(native)==1)
    java=[row for row in value['source']['java']['views'] if row['handle']==native[0]['handle'] and row['sourceOwned']
        and row['documentOwned'] and row['active'] and not row['destroyed'] and not row['closing']
        and row['ownerCurrent'] and row['foreground'] and not row['loading'] and row['sourceSha256']==wanted
        and row['documentSha256']==native[0]['documentSha256'] and row['creation']==native[0]['creation']
        and row['grant']==native[0]['grant'] and row['page']==native[0]['page'] and row['grant']>0 and row['page']>0]
    need(len(java)==1)
    if value['webRuntimeVersion']==2:
        actual=[row for row in value['source']['java']['renderers'] if row['handle']==native[0]['handle']
            and row['creation']==native[0]['creation'] and row['sourceOwned'] and row['sourceSha256']==wanted
            and row['objectAlive'] and row['threadAlive'] and not row['closed'] and not row['released']]
        need(len(actual)==1)
    return deepcopy(dict(native=native[0],java=java[0]))


def released(value,*,require_renderers=False):
    """Original scoped authorities/inventories; no entity-absence inference."""
    need(type(require_renderers) is bool and value['status']=='ready'
        and (not require_renderers or value['webRuntimeVersion']==2))
    hashes={row['sourceSha256'] for row in value['source']['nativeAfter']['knownHandles']}
    need(hashes) # A never-observed scope cannot prove its own release.
    for snapshot in (value['source']['nativeBefore'],value['source']['nativeAfter']):
        for row in snapshot['views']:
            need(not row['sourceOwned'] and not row['documentOwned'] and row['callbacks']==0 and row['scriptReplies']==0 and not row['domPending'])
            need(not row['pendingCreate'] and not row['retryPending'])
            need(not row['sessionActive'] or row['sourceSha256'] not in hashes and row['documentSha256'] not in hashes)
    for row in value['source']['java']['views']:
        need(not row['sourceOwned'] and not row['documentOwned'] and row['sourceSha256'] not in hashes and row['documentSha256'] not in hashes)
    need(not any(row['sourceOwned'] or row['sourceSha256'] in hashes for row in value['source']['java']['creations']))
    if value['webRuntimeVersion']==2:
        rows=value['source']['java']['renderers']
        if require_renderers:need(rows)
        for row in rows:
            need(row['closed'] and row['released'] and row['releaseSucceeded'] and not row['threadAlive']
                and row['mainCallbacks']==row['glCallbacks']==row['retainedCallbacks']==0)
    return deepcopy(value['source'])


class NativeWebRuntime:
    def __init__(self,send,original,clock_ms,guard,pid,*,require_renderers=False,monotonic=time.monotonic,sleep=time.sleep):
        need(all(callable(v) for v in (send,original,clock_ms,guard,monotonic,sleep)) and integer(pid,1))
        self.send,self.original,self.clock_ms,self.guard,self.pid=send,original,clock_ms,guard,pid
        self.monotonic,self.sleep,self.last=monotonic,sleep,None
        self.scope=None
        need(type(require_renderers) is bool);self.require_renderers=require_renderers

    def read(self,run,fixture_url):
        try:
            request=command(dict(schemaVersion=1,commandId=uuid.uuid4().hex,action='feature-web-runtime-observe',runId=run,fixtureUrl=fixture_url))
            started=previous=self.monotonic();need(number(started,0,1e15) and self.guard() is not False)
            need(self.scope in (None,(run,fixture_url)));self.scope=(run,fixture_url)
            requested=self.clock_ms();need(integer(requested,1))
            if self.last is not None:need(requested>=self.last['capturedEpochMs'])
            issued=self.monotonic();need(number(issued,previous,1e15) and issued-started<5);previous=issued;self.send(request)
            pending=None
            for attempt in range(51):
                need(self.guard() is not False);raw=self.original();need(type(raw) is str and len(raw.encode())<=LIMIT)
                try:value=decode(raw) if raw else None
                except json.JSONDecodeError:value=None
                now=self.monotonic();need(number(now,previous,1e15) and now-started<5);previous=now
                if type(value) is dict and value.get('commandId')==request['commandId']:
                    epoch=self.clock_ms();need(integer(epoch,requested));status=value.get('status')
                    # Pending timestamps are original request history, not current facts.
                    validate(value,request,self.pid,value.get('capturedEpochMs') if status=='pending' else epoch,require_renderers=self.require_renderers)
                    need(value['capturedEpochMs']>=requested and status!='unavailable')
                    if status=='pending':
                        need(pending is None or value==pending);pending=deepcopy(value)
                    else:
                        need(value['source']['nativeBefore']['capturedEpochMs']>=requested)
                        continuity(self.last,value,self.pid,fixture_url)
                        need(self.guard() is not False)
                        freshness_started=self.monotonic();need(number(freshness_started,previous,1e15));previous=freshness_started
                        final=self.clock_ms();need(integer(final,epoch));fresh(value['source']['nativeBefore']['capturedEpochMs'],final)
                        need(self.guard() is not False);finished=self.monotonic()
                        need(number(finished,previous,1e15) and finished-started<5
                            and max(final-value['source']['nativeBefore']['capturedEpochMs']+math.ceil((finished-freshness_started)*1000),
                                requested-value['source']['nativeBefore']['capturedEpochMs']+math.ceil((finished-issued)*1000))<=1500)
                        self.last=deepcopy(value);return value
                if attempt<50:self.sleep(.1)
        except Exception:raise NativeUIError('Original native Web runtime observation is unavailable or invalid') from None
        raise NativeUIError('Original native Web runtime observation did not produce this request')
