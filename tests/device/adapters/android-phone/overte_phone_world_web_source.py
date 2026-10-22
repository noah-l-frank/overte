"""Original Phone world-browser lifecycle/input source, with closed native reads.

Input receipts carry no observed effect. The retained histories are the original
native completion, script-facing delivery, script reply and passive DOM records.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import math
import re
import time
import uuid
from urllib.parse import urlsplit

from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.native_web_dom import validate as validate_dom
from adapters.normal_ui import NativeUIError
from feature_journeys.contract import identifier

FILE='phone-world-web.json'
VERSION=1
CONTROLS={'text','bridge','reference','second','recovery','back','reload','foreign','navigate'}
IDENTITY={'handle','creation','grant','page','url'}


def fixture(run,url):
    identifier(run);need(type(url) is str and 0<len(url)<=512 and url.isascii() and not any(ord(c)<=32 or ord(c)==127 for c in url))
    parsed=urlsplit(url);parsed.port
    need(parsed.scheme in ('http','https') and parsed.hostname and parsed.username is None and parsed.password is None
        and not parsed.query and not parsed.fragment and parsed.path=='/feature-fixture/v1/runs/'+run+'/')
    return url


def command(value):
    need(type(value) is dict);op=value.get('operation');fields={'schemaVersion','commandId','action','runId','fixtureUrl','operation','ownerToken'}
    reference=value.get('action')=='phone-web-reference'
    exact(value,fields|({'surface'} if reference else set())|({'handle','creation','grant','page','control','text'} if op=='input' else set()))
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['action'] in ('phone-world-web','phone-web-reference')
        and op in ('reserve','observe','input','retire'))
    identifier(value['commandId']);identifier(value['ownerToken'])
    if reference:
        from adapters.native_phone_web_runtime import command as runtime_command
        runtime_command(dict(schemaVersion=1,commandId=value['commandId'],action='feature-phone-web-reference-runtime-observe',runId=value['runId'],fixtureUrl=value['fixtureUrl']))
        need(value['surface'] in ('world','tablet'))
    else:fixture(value['runId'],value['fixtureUrl'])
    if op=='input':
        need(type(value['handle']) is str and re.fullmatch('[1-9][0-9]{0,18}',value['handle'])
            and all(integer(value[k],1) for k in ('creation','grant','page')) and value['control'] in ({'play','pause','seekStart','seek'} if reference else CONTROLS)
            and type(value['text']) is str and len(value['text'].encode('utf-16-le'))//2<=512
            and not any(ord(c)<32 or ord(c)==127 or 0xE000<=ord(c)<=0xE05E for c in value['text'])
            and (value['control'] in ('text','foreign') or not value['text']))
    return value


def identity(row):
    need(type(row['handle']) is str and re.fullmatch('[1-9][0-9]{0,18}',row['handle'])
        and all(integer(row[k],1) for k in ('creation','grant','page')) and type(row['url']) is str
        and 0<len(row['url'])<=131072 and not any(ord(c)<32 or ord(c)==127 for c in row['url']))
    return ':'.join(str(row[k]) for k in ('handle','creation','grant','page'))


def validate(value,request,pid,epoch):
    command(request)
    exact(value,{'phoneWorldWebVersion','commandId','runId','ownerToken','instance','sequence','processId','capturedEpochMs','status','source'})
    need(type(value['phoneWorldWebVersion']) is int and value['phoneWorldWebVersion']==VERSION
        and value['commandId']==request['commandId'] and value['runId']==request['runId'] and value['ownerToken']==request['ownerToken']
        and integer(value['processId'],1) and value['processId']==pid and integer(value['sequence'],1)
        and value['status'] in ('pending','ready','unavailable'))
    identifier(value['instance']);fresh(value['capturedEpochMs'],epoch)
    source=value['source']
    if value['status']!='ready':exact(source,set());return value
    op=request['operation']
    if op!='observe':
        field={'reserve':'reserved','input':'delivered','retire':'retired'}[op]
        exact(source,{field});need(source[field] is True);return value
    exact(source,{'retired','documents','requests','replies','domHistory','current'})
    need(type(source['retired']) is bool and type(source['domHistory']) is dict and len(source['domHistory'])<=256)
    documents={};previous=0
    need(type(source['documents']) is list and len(source['documents'])<=256)
    for row in source['documents']:
        exact(row,IDENTITY|{'finishedEpochMs'});key=identity(row)
        need(key not in documents and integer(row['finishedEpochMs'],max(1,previous),value['capturedEpochMs']))
        documents[key]=row;previous=row['finishedEpochMs']
    event_keys={}
    for kind in ('requests','replies'):
        rows=source[kind];need(type(rows) is list and len(rows)<=128);seen=set();previous=0
        for row in rows:
            exact(row,IDENTITY|{'message','capturedEpochMs'});key=identity(row)
            need(key in documents and row['url']==documents[key]['url'] and integer(row['capturedEpochMs'],max(1,previous),value['capturedEpochMs'])
                and row['capturedEpochMs']>=documents[key]['finishedEpochMs'] and type(row['message']) is str and len(row['message'])<=4096)
            packet=decode(row['message']);exact(packet,{'contract','action','sequence'}|({'surface'} if kind=='replies' else set()))
            need(packet['contract']=='overte-web-parity-v1' and packet['action']=='echo' and integer(packet['sequence'],1,1000000)
                and (kind!='replies' or packet['surface']=='world'))
            pair=(key,packet['sequence']);need(pair not in seen);seen.add(pair);previous=row['capturedEpochMs']
        event_keys[kind]=seen
    need(event_keys['replies']<=event_keys['requests'])
    for key,packet in source['domHistory'].items():
        need(type(key) is str and key in documents)
        dom_request=dict(schemaVersion=1,commandId=packet['commandId'],action='feature-web-dom-observe',runId=request['runId'],surface='world',fixtureUrl=request['fixtureUrl'])
        validate_dom(packet,dom_request,pid,packet['capturedEpochMs']);need(packet['status']=='ready')
        view=packet['source']['nativeView'];need(identity(view)==key and view['url']==documents[key]['url']
            and packet['capturedEpochMs']>=documents[key]['finishedEpochMs'] and packet['capturedEpochMs']<=value['capturedEpochMs'])
        echoes=packet['source']['dom']['echoes']
        need(all((key,row['sequence']) in event_keys['replies'] for row in echoes))
    current=source['current'];need(type(current) is dict)
    if request['action']=='phone-web-reference':
        need(not source['domHistory'])
        if current:
            exact(current,{'nativeView'});view=current['nativeView']
            exact(view,IDENTITY|{'nativeFinished','httpErrorStatus','inlineLease','sourceUrl','sourceIdentity'})
            key=identity(view);need(key in documents and view['nativeFinished'] is True and view['inlineLease'] is False
                and type(view['httpErrorStatus']) is int and view['httpErrorStatus']==0
                and view['sourceUrl']==request['fixtureUrl']+'index.html' and view['url']==view['sourceUrl']
                and type(view['sourceIdentity']) is str and 0<len(view['sourceIdentity'])<=512)
    elif current:
        dom_request=dict(schemaVersion=1,commandId=request['commandId'],action='feature-web-dom-observe',runId=request['runId'],surface='world',fixtureUrl=request['fixtureUrl'])
        validate_dom(current,dom_request,pid,epoch);key=identity(current['source']['nativeView'])
        need(key in source['domHistory'] and current==source['domHistory'][key])
    if source['retired']:need(not any(source[k] for k in ('documents','requests','replies','domHistory','current')))
    return value


def continuity(previous,value):
    if previous is None:return
    need(value['instance']==previous['instance'] and value['runId']==previous['runId'] and value['ownerToken']==previous['ownerToken']
        and value['sequence']>previous['sequence'] and value['capturedEpochMs']>=previous['capturedEpochMs'])
    old,new=previous['source'],value['source']
    if 'documents' not in old or 'documents' not in new:return
    if new['retired']:return # The separately authorized native retirement is explicit, never a missing file.
    need(not old['retired'])
    for key in ('documents','requests','replies'):need(new[key][:len(old[key])]==old[key])
    for key,packet in old['domHistory'].items():
        need(key in new['domHistory']);a=packet['source']['dom'];b=new['domHistory'][key]['source']['dom']
        need(b['instance']==a['instance'] and b['sequence']>=a['sequence'] and b['capturedEpochMs']>=a['capturedEpochMs']
            and (b['sequence']!=a['sequence'] or b==a))
        for history in ('attempts','echoes'):need(b[history][:len(a[history])]==a[history])


class PhoneWorldWebIO:
    def __init__(self,send,original,clock_ms,guard,pid,*,monotonic=time.monotonic,sleep=time.sleep):
        need(all(callable(v) for v in (send,original,clock_ms,guard,monotonic,sleep)) and integer(pid,1))
        self.send,self.original,self.clock_ms,self.guard,self.pid=send,original,clock_ms,guard,pid
        self.monotonic,self.sleep,self.last=monotonic,sleep,None

    def request(self,run,url,owner,operation,*,reference_surface=None,**fields):
        request=command(dict(schemaVersion=1,commandId=uuid.uuid4().hex,action='phone-world-web' if reference_surface is None else 'phone-web-reference',runId=run,
            fixtureUrl=url,ownerToken=owner,operation=operation,**({'surface':reference_surface} if reference_surface is not None else {}),**fields))
        try:
            start=previous=self.monotonic();requested=self.clock_ms();need(number(start,0,1e15) and integer(requested,1) and self.guard() is not False)
            self.send(request)
            for attempt in range(51):
                need(self.guard() is not False);raw=self.original()
                try:value=decode(raw) if raw else None
                except json.JSONDecodeError:value=None
                now=self.monotonic();need(number(now,previous,start+5));previous=now
                if type(value) is dict and value.get('commandId')==request['commandId']:
                    epoch=self.clock_ms();validate(value,request,self.pid,epoch)
                    need(value['capturedEpochMs']>=requested and value['status']!='unavailable')
                    if value['status']=='ready':
                        continuity(self.last,value);need(self.guard() is not False)
                        final=self.clock_ms();need(integer(final,epoch));fresh(value['capturedEpochMs'],final)
                        if operation=='observe' and reference_surface is None and value['source']['current']:
                            fresh(value['source']['current']['source']['dom']['capturedEpochMs'],final)
                        finished=self.monotonic();need(number(finished,previous,start+5) and finished-start<5
                            and max(final-value['capturedEpochMs'],requested-value['capturedEpochMs']+math.ceil((finished-start)*1000))<=1500)
                        self.last=deepcopy(value);return value
                need(attempt<50 and now-start<5);self.sleep(.1)
        except Exception:raise NativeUIError('Original Phone World Web source or input is unavailable') from None
        raise NativeUIError('Original Phone World Web source did not produce this request')
