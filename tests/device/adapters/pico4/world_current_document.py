"""Pico-only current document source; original finish never becomes current grant.

This source changes neither legacy Web observation nor World journey predicates.
The caller owns transport, original bytes, target lifetime and source locking.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import re
import time
import uuid

from adapters.native_feature_observation import decode, exact, fresh, integer, need, number
from adapters.native_web_dom import command as dom_command, dom
from adapters.normal_ui import NativeUIError
from adapters.script_journey.lock import ScriptSourceLock

VERSION=1
FILE='feature-world-current-document.json'
LIMIT=65536
HEX=r'[0-9a-f]{32}'
NATIVE={'handle','itemInstance','creation','grant','page','url','sourceUrl','sourceIdentity',
        'created','authorized','sessionActive','suspended','loading','capturedEpochMs','capturedMonotonicMs'}
JAVA={'handle','creation','grant','page','url','sourceUrl','ownerCurrent','active','foreground','windowFocused',
      'destroyed','closing','loading','capturedEpochMs','capturedElapsedMs'}
CLOCKS={'capturedEpochMs','capturedMonotonicMs','capturedElapsedMs'}
FINISH={'handle','creation','grant','page','url','finishedEpochMs'}


def strict(value):
    """Refuse Python aliases/subclasses before equality can forgive bool/int."""
    if type(value) is dict:
        need(all(type(k) is str for k in value))
        for item in value.values():strict(item)
    elif type(value) is list:
        for item in value:strict(item)
    else:need(value is None or type(value) in (str,bool,int,float))
    json.dumps(value,allow_nan=False)


def command(value):
    strict(value)
    exact(value,{'schemaVersion','commandId','action','runId','fixtureUrl','operation','ownerToken'})
    need(value['action']=='pico-world-web' and value['operation']=='observe-current-document'
         and type(value['ownerToken']) is str and re.fullmatch(HEX,value['ownerToken']))
    base={k:v for k,v in value.items() if k not in ('ownerToken','operation')}
    base.update(action='feature-web-dom-observe',surface='world');dom_command(base)
    return value


def identity(value):
    need(type(value['handle']) is str and re.fullmatch(r'[1-9][0-9]{0,18}',value['handle'])
         and all(integer(value[k],1) for k in ('creation','grant','page'))
         and all(type(value[k]) is str and 0<len(value[k])<=131072
                 and not any(ord(c)<32 or ord(c)==127 for c in value[k]) for k in ('url','sourceUrl')))


def semantic(value):return {k:v for k,v in value.items() if k not in CLOCKS}


def validate(value,request,pid,epoch):
    command(request);strict(value)
    exact(value,{'picoWorldCurrentDocumentVersion','commandId','runId','ownerToken','instance','sequence','processId',
                 'requestedEpochMs','requestedMonotonicMs','capturedEpochMs','capturedMonotonicMs','status','source'})
    need(type(value['picoWorldCurrentDocumentVersion']) is int and value['picoWorldCurrentDocumentVersion']==VERSION
         and all(value[k]==request[k] for k in ('commandId','runId','ownerToken'))
         and integer(pid,1) and integer(value['processId'],1) and value['processId']==pid
         and type(value['instance']) is str and re.fullmatch(HEX,value['instance']) and integer(value['sequence'],1)
         and type(value['status']) is str and value['status'] in ('pending','ready','unavailable')
         and all(integer(value[k],1) for k in ('requestedEpochMs','capturedEpochMs'))
         and all(integer(value[k]) for k in ('requestedMonotonicMs','capturedMonotonicMs'))
         and value['capturedMonotonicMs']>=value['requestedMonotonicMs'])
    fresh(value['capturedEpochMs'],epoch)
    if value['status']=='unavailable':exact(value['source'],set());return value
    need(-250<=value['capturedEpochMs']-value['requestedEpochMs']<=1500
         and value['capturedMonotonicMs']-value['requestedMonotonicMs']<=1500)
    if value['status']=='pending':exact(value['source'],set());return value
    source=value['source'];exact(source,{'authorityBefore','authorityAfter','originalFinish','documents','domRaw','dom'})
    for side in ('authorityBefore','authorityAfter'):
        pair=source[side];exact(pair,{'native','java'})
        native=pair['native'];java=pair['java'];exact(native,NATIVE);exact(java,JAVA)
        for item in (native,java):
            identity(item);fresh(item['capturedEpochMs'],value['capturedEpochMs'])
            need(value['requestedEpochMs']-250<=item['capturedEpochMs']<=value['capturedEpochMs']+250)
        need(type(native['itemInstance']) is str and re.fullmatch(HEX,native['itemInstance'])
             and type(native['sourceIdentity']) is str
             and re.fullmatch(r'web-entity:[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',native['sourceIdentity'])
             and all(native[k] is True for k in ('created','authorized','sessionActive'))
             and all(native[k] is False for k in ('suspended','loading'))
             and all(java[k] is True for k in ('ownerCurrent','active','foreground','windowFocused'))
             and all(java[k] is False for k in ('destroyed','closing','loading'))
             and integer(native['capturedMonotonicMs']) and integer(java['capturedElapsedMs']))
        need(value['requestedMonotonicMs']<=native['capturedMonotonicMs']<=value['capturedMonotonicMs']
             and all(native[k]==java[k] for k in ('handle','creation','grant','page','url','sourceUrl')))
    a=source['authorityBefore'];b=source['authorityAfter']
    need(all(semantic(a[k])==semantic(b[k]) for k in ('native','java'))
         and a['native']['capturedMonotonicMs']<=b['native']['capturedMonotonicMs']
         and a['java']['capturedElapsedMs']<=b['java']['capturedElapsedMs']<=a['java']['capturedElapsedMs']+1500
         and a['native']['capturedEpochMs']-250<=a['java']['capturedEpochMs']<=b['java']['capturedEpochMs']<=b['native']['capturedEpochMs']+250)
    native=b['native'];prefix=request['fixtureUrl']+'tickets/'
    need(native['sourceUrl'].startswith(prefix) and re.fullmatch(HEX+r'/index\.html',native['sourceUrl'][len(prefix):]))
    documents=source['documents'];need(type(documents) is list and 0<len(documents)<=256)
    seen=set();last=0
    for row in documents:
        exact(row,FINISH)
        extended=dict(row,sourceUrl=row['url']);identity(extended)
        need(integer(row['finishedEpochMs'],1) and last<=row['finishedEpochMs']<=value['capturedEpochMs']+250)
        key=tuple(row[k] for k in ('handle','creation','grant','page','url'));need(key not in seen);seen.add(key);last=row['finishedEpochMs']
    finish=source['originalFinish'];exact(finish,FINISH)
    identity(dict(finish,sourceUrl=finish['url']));need(integer(finish['finishedEpochMs'],1))
    need(sum(row==finish for row in documents)==1
         and all(finish[k]==native[k] for k in ('handle','creation','page','url')))
    # The original finish grant deliberately may precede current native grant.
    raw=source['domRaw'];need(type(raw) is str and len(raw.encode('utf-8'))<=16384)
    transaction=decode(raw);exact(transaction,{'before','domRaw','after'})
    need(json.dumps(transaction['before'],sort_keys=True)==json.dumps(a['java'],sort_keys=True)
         and json.dumps(transaction['after'],sort_keys=True)==json.dumps(b['java'],sort_keys=True)
         and type(transaction['domRaw']) is str and len(transaction['domRaw'].encode('utf-8'))<=8192)
    original=decode(transaction['domRaw']);need(type(original) is str)
    original=decode(original);strict(original)
    need(json.dumps(original,sort_keys=True)==json.dumps(source['dom'],sort_keys=True))
    dom(original,dict(request,surface='world'),value['capturedEpochMs'])
    need(original['document']['href']==native['url'] and original['document']['responseId'] is not None
         and a['java']['capturedEpochMs']-250<=original['capturedEpochMs']<=b['java']['capturedEpochMs']+250)
    return value


class PicoWorldCurrentDocument:
    """One nonce/send/read-only DOM transaction; same-nonce polls only read bytes."""
    def __init__(self,send,read,clock_ms,guard,pid,source_lock,*,monotonic=time.monotonic,sleep=time.sleep):
        need(all(callable(v) for v in (send,read,clock_ms,guard,monotonic,sleep)) and integer(pid,1) and type(source_lock) is ScriptSourceLock)
        self.lock=source_lock;self.last=self.raw=self.last_request=None
        self.send,self.read_raw,self.clock_ms,self.guard,self.pid=send,read,clock_ms,guard,pid
        self.monotonic,self.sleep=monotonic,sleep

    def read(self,run,fixture_url,owner):
        need(self.lock._owner is None and self.guard() is not False)
        started=self.monotonic();requested=self.clock_ms()
        need(number(started,0,1e15) and integer(requested,1))
        with self.lock.held():
            value,request,raw=self._read(run,fixture_url,owner,started,requested)
            saved,result,saved_request=deepcopy(value),deepcopy(value),deepcopy(request)
        # Publication follows the real outer source-lock release. No new DOM
        # request/frame/timestamp is acquired to make stale originals fresh.
        validate(result,request,self.pid,self.clock_ms())
        need(self.guard() is not False)
        epoch=self.clock_ms();now=self.monotonic()
        need(number(now,started,1e15) and now-started<=1.5
             and -250<=epoch-value['requestedEpochMs']<=1500)
        for captured in (result['capturedEpochMs'],result['source']['dom']['capturedEpochMs'],
                         *(result['source'][side][kind]['capturedEpochMs']
                           for side in ('authorityBefore','authorityAfter') for kind in ('native','java'))):
            fresh(captured,epoch)
        self.last,self.raw,self.last_request=saved,raw,saved_request
        return result

    def original(self):
        need(self.raw is not None)
        return dict(raw=self.raw,request=deepcopy(self.last_request))

    def _read(self,run,fixture_url,owner,started,requested):
        self.lock.assert_held()
        request=dict(schemaVersion=1,commandId=uuid.uuid4().hex,action='pico-world-web',runId=run,
                     fixtureUrl=fixture_url,operation='observe-current-document',ownerToken=owner)
        command(request);need(self.guard() is not False)
        previous=started;self.send(deepcopy(request));latest=None
        for attempt in range(31):
            need(self.guard() is not False);raw=self.read_raw()
            need(type(raw) is str and len(raw.encode('utf-8'))<=LIMIT)
            value=decode(raw) if raw else None
            if type(value) is dict and value.get('commandId')==request['commandId']:
                validate(value,request,self.pid,self.clock_ms());need(value['status']!='unavailable')
                need(value['requestedEpochMs']>=requested-250)
                if latest is not None:
                    need(value['instance']==latest['instance'] and value['requestedEpochMs']==latest['requestedEpochMs']
                         and value['requestedMonotonicMs']==latest['requestedMonotonicMs']
                         and value['sequence']>=latest['sequence'] and value['capturedEpochMs']>=latest['capturedEpochMs']
                         and value['capturedMonotonicMs']>=latest['capturedMonotonicMs']
                         and (value['sequence']!=latest['sequence'] or value==latest))
                latest=deepcopy(value)
                if value['status']=='ready':
                    result=deepcopy(value)
                    need(self.guard() is not False)
                    epoch=self.clock_ms();now=self.monotonic()
                    need(number(now,0,1e15) and previous<=now and -250<=epoch-value['requestedEpochMs']<=1500
                         and 0<=now-started<=1.5)
                    validate(result,request,self.pid,epoch)
                    return result,request,raw
            now=self.monotonic();need(number(now,0,1e15) and previous<=now and now-started<=1.5);previous=now
            if attempt==30:break
            self.sleep(min(.05,1.5-(now-started)))
        raise NativeUIError('Pico current document source is unavailable')
