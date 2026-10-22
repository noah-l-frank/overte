"""Original Pico world-browser lifecycle/input source, with closed native reads.

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
from adapters.script_journey.lock import ScriptSourceLock
from feature_journeys.contract import identifier

FILE='feature-pico-browser.json'
VERSION=2
CONTROLS={'text','bridge','reference','second','recovery','back','reload','foreign','navigate','scroll-up','scroll-down'}
IDENTITY={'handle','creation','grant','page','url'}


def fixture(run,url):
    identifier(run);need(type(url) is str and 0<len(url)<=512 and url.isascii() and not any(ord(c)<=32 or ord(c)==127 for c in url))
    parsed=urlsplit(url);parsed.port
    need(parsed.scheme in ('http','https') and parsed.hostname and parsed.username is None and parsed.password is None
        and not parsed.query and not parsed.fragment and parsed.path=='/feature-fixture/v1/runs/'+run+'/')
    return url


def command(value):
    need(type(value) is dict);op=value.get('operation');fields={'schemaVersion','commandId','action','runId','fixtureUrl','operation','ownerToken'}
    reference=value.get('action')=='pico-web-reference'
    exact(value,fields|({'surface'} if reference else set())|({'handle','creation','grant','page','control'} if op in ('input','measure') else set())|({'text'} if op=='input' else set()))
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['action'] in ('pico-world-web','pico-tablet-web','pico-web-reference')
        and op in ('reserve','observe','measure','input','retire','arm-held','deliver-held','cancel-held')
        and (op not in ('arm-held','deliver-held','cancel-held') or value['action']=='pico-tablet-web'))
    identifier(value['commandId']);identifier(value['ownerToken'])
    if reference:
        fixture(value['runId'],value['fixtureUrl'])
        need(value['surface'] in ('world','tablet'))
    else:fixture(value['runId'],value['fixtureUrl'])
    if op in ('input','measure'):
        need(type(value['handle']) is str and re.fullmatch('[1-9][0-9]{0,18}',value['handle'])
            and all(integer(value[k],1) for k in ('creation','grant','page')) and value['control'] in ({'play','pause','seekStart','seek'} if reference else CONTROLS)
            and (op=='measure' or type(value['text']) is str and len(value['text'].encode('utf-16-le'))//2<=512
            and not any(ord(c)<32 or ord(c)==127 or 0xE000<=ord(c)<=0xE05E for c in value['text'])
            and (value['control'] in ('text','foreign') or not value['text'])))
    return value


def identity(row):
    need(type(row['handle']) is str and re.fullmatch('[1-9][0-9]{0,18}',row['handle'])
        and all(integer(row[k],1) for k in ('creation','grant','page')) and type(row['url']) is str
        and 0<len(row['url'])<=131072 and not any(ord(c)<32 or ord(c)==127 for c in row['url']))
    return ':'.join(str(row[k]) for k in ('handle','creation','grant','page'))


def validate(value,request,pid,epoch):
    command(request)
    exact(value,{'picoBrowserVersion','commandId','runId','ownerToken','instance','sequence','processId','capturedEpochMs','status','source'})
    need(type(value['picoBrowserVersion']) is int and value['picoBrowserVersion'] in (1,VERSION)
        and value['commandId']==request['commandId'] and value['runId']==request['runId'] and value['ownerToken']==request['ownerToken']
        and integer(value['processId'],1) and value['processId']==pid and integer(value['sequence'],1)
        and value['status'] in ('pending','ready','unavailable'))
    identifier(value['instance']);fresh(value['capturedEpochMs'],epoch)
    source=value['source']
    if value['status']!='ready':exact(source,set());return value
    op=request['operation']
    if op=='measure':
        need(value['picoBrowserVersion']==2);exact(source,{'geometryRaw','nativeView'})
        view=source['nativeView'];exact(view,IDENTITY);identity(view)
        need(all(view[k]==request[k] for k in ('handle','creation','grant','page')))
        geometry_original(source['geometryRaw'],request,view['url'],value['capturedEpochMs'],visible=False)
        return value
    if op!='observe':
        field={'reserve':'reserved','input':'delivered','retire':'retired','arm-held':'armed','deliver-held':'delivered','cancel-held':'cancelled'}[op]
        exact(source,{field});need(source[field] is True);return value
    tablet=request['action']=='pico-tablet-web';surface='tablet' if tablet else request.get('surface','world')
    exact(source,{'retired','documents','requests','replies','inputs','domHistory','current'}|({'deferred'} if tablet else set()))
    if tablet:
        from adapters.pico4.tablet_browser_source import deferred
        deferred(source['deferred'],value['capturedEpochMs'])
    need(type(source['retired']) is bool and type(source['domHistory']) is dict and len(source['domHistory'])<=256)
    documents={};previous=0
    need(type(source['documents']) is list and len(source['documents'])<=256)
    for row in source['documents']:
        exact(row,IDENTITY|{'finishedEpochMs'});key=identity(row)
        need(key not in documents and integer(row['finishedEpochMs'],max(1,previous),value['capturedEpochMs']))
        documents[key]=row;previous=row['finishedEpochMs']
    if tablet:
        from adapters.pico4.tablet_browser_dom import validate as tablet_validate
    event_keys={}
    for kind in ('requests','replies'):
        rows=source[kind];need(type(rows) is list and len(rows)<=128);seen=set();previous=0
        for row in rows:
            exact(row,IDENTITY|{'message','capturedEpochMs'});key=identity(row)
            need(key in documents and row['url']==documents[key]['url'] and integer(row['capturedEpochMs'],max(1,previous),value['capturedEpochMs'])
                and row['capturedEpochMs']>=documents[key]['finishedEpochMs'] and type(row['message']) is str and len(row['message'])<=4096)
            packet=decode(row['message']);exact(packet,{'contract','action','sequence'}|({'surface'} if kind=='replies' else set()))
            need(packet['contract']=='overte-web-parity-v1' and packet['action']=='echo' and integer(packet['sequence'],1,1000000)
                and (kind!='replies' or packet['surface']==surface))
            pair=(key,packet['sequence']);need(pair not in seen);seen.add(pair);previous=row['capturedEpochMs']
        event_keys[kind]=seen
    need(event_keys['replies']<=event_keys['requests'])
    for key,packet in source['domHistory'].items():
        need(type(key) is str and key in documents)
        dom_request=dict(schemaVersion=1,commandId=packet['commandId'],action='feature-pico-tablet-dom-observe' if tablet else 'feature-web-dom-observe',runId=request['runId'],surface=surface,fixtureUrl=request['fixtureUrl'])
        (tablet_validate if tablet else validate_dom)(packet,dom_request,pid,packet['capturedEpochMs']);need(packet['status']=='ready')
        view=packet['source']['nativeView'];need(identity(view)==key and view['url']==documents[key]['url']
            and packet['capturedEpochMs']>=documents[key]['finishedEpochMs'] and packet['capturedEpochMs']<=value['capturedEpochMs'])
        echoes=packet['source']['dom']['echoes']
        need(all((key,row['sequence']) in event_keys['replies'] for row in echoes))
    input_history(source['inputs'],request,value['capturedEpochMs'],documents,version=value['picoBrowserVersion'])
    current=source['current'];need(type(current) is dict)
    if request['action']=='pico-web-reference':
        need(not source['domHistory'])
        if current:
            exact(current,{'nativeView'});view=current['nativeView']
            exact(view,IDENTITY|{'nativeFinished','httpErrorStatus','inlineLease','sourceUrl','sourceIdentity'})
            key=identity(view);need(key in documents and view['nativeFinished'] is True and view['inlineLease'] is False
                and type(view['httpErrorStatus']) is int and view['httpErrorStatus']==0
                and view['sourceUrl']==request['fixtureUrl']+'index.html' and view['url']==view['sourceUrl']
                and type(view['sourceIdentity']) is str and 0<len(view['sourceIdentity'])<=512)
    elif current:
        dom_request=dict(schemaVersion=1,commandId=request['commandId'],action='feature-pico-tablet-dom-observe' if tablet else 'feature-web-dom-observe',runId=request['runId'],surface=surface,fixtureUrl=request['fixtureUrl'])
        (tablet_validate if tablet else validate_dom)(current,dom_request,pid,epoch);key=identity(current['source']['nativeView'])
        need(key in source['domHistory'] and current==source['domHistory'][key])
    if source['retired']:
        need(not any(source[k] for k in ('documents','requests','replies','inputs','domHistory','current')))
        if tablet:need(source['deferred']==dict(armed=False,pending=False,held=None,deliveries=[]))
    return value


def geometry_original(raw,call,document,epoch,*,focused=False,visible=True):
    need(type(raw) is str);actual=decode(decode(raw))
    exact(actual,{'webGeometryVersion','requestId','instance','sequence','capturedEpochMs','document','control','editor','viewport','rect','center','hit','enabled','connected'})
    need(type(actual['webGeometryVersion']) is int and actual['webGeometryVersion']==1 and actual['requestId']==call['commandId']
        and actual['control']==call['control'] and integer(actual['sequence'],1) and integer(actual['capturedEpochMs'],max(1,epoch-1500),epoch))
    identifier(actual['instance']);doc=actual['document'];exact(doc,{'runId','href','responseId','readyState'})
    need(doc['runId']==call['runId'] and doc['href']==document and doc['readyState']=='complete')
    if doc['responseId'] is not None:identifier(doc['responseId'])
    viewport=actual['viewport'];exact(viewport,{'width','height','scale','offsetLeft','offsetTop'})
    need(number(viewport['width'],1,32768) and number(viewport['height'],1,32768)
        and number(viewport['scale'],1,1) and number(viewport['offsetLeft'],0,0) and number(viewport['offsetTop'],0,0))
    rect,center=actual['rect'],actual['center'];exact(rect,{'x','y','width','height'});exact(center,{'x','y'})
    need(number(rect['x'],-1e7,1e7) and number(rect['y'],-1e7,1e7) and number(rect['width'],.001,1e7) and number(rect['height'],.001,1e7)
        and number(center['x'],-1e7,1e7) and number(center['y'],-1e7,1e7)
        and (not visible or 0<=center['x']<viewport['width'] and 0<=center['y']<viewport['height'])
        and abs(center['x']-rect['x']-rect['width']/2)<=.001 and abs(center['y']-rect['y']-rect['height']/2)<=.001
        and all(type(actual[key]) is bool for key in ('hit','enabled','connected'))
        and (not visible or all(actual[key] for key in ('hit','enabled','connected'))))
    editor=actual['editor'];exact(editor,{'focused','text','cursor','anchor'});need(type(editor['focused']) is bool and (not focused or editor['focused']))
    if call['control'] in ('text','foreign'):
        need(type(editor['text']) is str);units=len(editor['text'].encode('utf-16-le'))//2
        need(units<=512 and integer(editor['cursor'],0,units) and integer(editor['anchor'],0,units))
    else:need(editor['text'] is editor['cursor'] is editor['anchor'] is None)
    if call['control'] in ('scroll-up','scroll-down'):
        need(rect==dict(x=0,y=0,width=viewport['width'],height=viewport['height']))
    return actual


def input_history(rows,request,epoch,documents,*,version=VERSION):
    need(type(rows) is list and len(rows)<=128);seen=set();previous=0
    for row in rows:
        exact(row,{'command','issuedEpochMs','geometryRaw','focusRaw','pointerEpochMs','imeEpochMs','nativeBeforeIME','completion'}|({'wheelEpochMs'} if version==2 else set()))
        call=command(row['command']);identifier(call['commandId'])
        need(call['operation']=='input' and call['commandId'] not in seen
            and all(call[key]==request[key] for key in ('action','runId','ownerToken','fixtureUrl'))
            and integer(row['issuedEpochMs'],max(1,previous),epoch))
        seen.add(call['commandId']);previous=row['issuedEpochMs'];stage=row['issuedEpochMs']
        first_geometry=None
        for key in ('geometryRaw','focusRaw'):
            raw=row[key]
            if raw is None:continue
            need(type(raw) is str and len(raw.encode('utf-8'))<=16384)
            decoded=decode(raw)
            # A failed original may be null; unavailable input is retained,
            # never promoted by manufacturing a replacement geometry packet.
            if decoded is None:continue
            need(type(decoded) is str);actual=decode(decoded)
            if type(actual) is not dict:continue
            need(actual.get('requestId')==call['commandId'] and actual.get('control')==call['control'])
            if key=='geometryRaw':first_geometry=actual
            elif first_geometry is not None:
                need(actual['instance']==first_geometry['instance'] and actual['sequence']>first_geometry['sequence'])
        for key in (('pointerEpochMs','wheelEpochMs','imeEpochMs') if version==2 else ('pointerEpochMs','imeEpochMs')):
            if row[key] is not None:need(integer(row[key],stage,epoch));stage=row[key]
        wheel=version==2 and row['wheelEpochMs'] is not None
        if wheel:
            need(call['control'] in ('scroll-up','scroll-down') and row['geometryRaw'] is not None
                and row['pointerEpochMs'] is row['imeEpochMs'] is row['focusRaw'] is None)
        elif call['control'] in ('scroll-up','scroll-down'):
            need(version==2 and row['pointerEpochMs'] is row['imeEpochMs'] is row['focusRaw'] is None)
        if row['pointerEpochMs'] is not None:need(row['geometryRaw'] is not None)
        native=row['nativeBeforeIME']
        if row['imeEpochMs'] is not None:
            need(call['control'] in ('text','foreign') and row['pointerEpochMs'] is not None and row['focusRaw'] is not None)
            exact(native,{'text','cursor','anchor','absoluteCursor','kind','sensitive','focused','enabled'})
            need(type(native['text']) is str and len(native['text'].encode('utf-16-le'))//2<=512
                and integer(native['cursor'],0,len(native['text'].encode('utf-16-le'))//2)
                and integer(native['anchor'],0,len(native['text'].encode('utf-16-le'))//2)
                and type(native['absoluteCursor']) is int and native['absoluteCursor']==native['cursor']
                and native['kind']==('url' if call['control']=='foreign' else 'text')
                and native['sensitive'] is False and native['focused'] is True and native['enabled'] is True)
        else:need(native is None)
        done=row['completion']
        if done is not None:
            exact(done,{'status','capturedEpochMs'});need(done['status'] in ('ready','unavailable') and integer(done['capturedEpochMs'],stage,epoch))
            if done['status']=='ready':
                need((wheel or row['pointerEpochMs'] is not None) and (call['control'] not in ('text','foreign') or row['imeEpochMs'] is not None))
                key=':'.join(str(call[k]) for k in ('handle','creation','grant','page'));need(key in documents)
                original=geometry_original(row['geometryRaw'],call,documents[key]['url'],row['wheelEpochMs'] if wheel else row['pointerEpochMs'])
                if row['imeEpochMs'] is not None:
                    focus=geometry_original(row['focusRaw'],call,documents[key]['url'],row['imeEpochMs'],focused=True)
                    need(focus['instance']==original['instance'] and focus['sequence']>original['sequence']
                        and focus['capturedEpochMs']>=row['pointerEpochMs']
                        and all(native[key]==focus['editor'][key] for key in ('text','cursor','anchor')))

    return rows


def continuity(previous,value):
    if previous is None:return
    need(value['instance']==previous['instance'] and value['runId']==previous['runId'] and value['ownerToken']==previous['ownerToken']
        and value['sequence']>previous['sequence'] and value['capturedEpochMs']>=previous['capturedEpochMs'])
    old,new=previous['source'],value['source']
    if 'documents' not in old or 'documents' not in new:return
    if 'deferred' in old and 'deferred' in new and not new['retired']:
        a,b=old['deferred'],new['deferred'];need(b['deliveries'][:len(a['deliveries'])]==a['deliveries'])
        if a['held'] is not None:need(b['held']==a['held'])
    if new['retired']:return # The separately authorized native retirement is explicit, never a missing file.
    need(not old['retired'])
    for key in ('documents','requests','replies'):need(new[key][:len(old[key])]==old[key])
    need(len(new['inputs'])>=len(old['inputs']))
    for before,after in zip(old['inputs'],new['inputs']):
        for key,original in before.items():
            if original is not None:need(after[key]==original)

    for key,packet in old['domHistory'].items():
        need(key in new['domHistory']);a=packet['source']['dom'];b=new['domHistory'][key]['source']['dom']
        need(b['instance']==a['instance'] and b['sequence']>=a['sequence'] and b['capturedEpochMs']>=a['capturedEpochMs']
            and (b['sequence']!=a['sequence'] or b==a))
        for history in ('attempts','echoes'):need(b[history][:len(a[history])]==a[history])


class PicoBrowserIO:
    action="pico-world-web"
    def __init__(self,send,original,clock_ms,guard,pid,*,source_lock,read_only=False,monotonic=time.monotonic,sleep=time.sleep):
        need(all(callable(v) for v in (send,original,clock_ms,guard,monotonic,sleep)) and integer(pid,1) and isinstance(source_lock,ScriptSourceLock) and type(read_only) is bool)
        self.lock,self.read_only=source_lock,read_only
        self.send,self.original,self.clock_ms,self.guard,self.pid=send,original,clock_ms,guard,pid
        self.monotonic,self.sleep,self.last=monotonic,sleep,None

    def request(self,run,url,owner,operation,*,reference_surface=None,**fields):
        request=command(dict(schemaVersion=1,commandId=uuid.uuid4().hex,action=self.action if reference_surface is None else 'pico-web-reference',runId=run,
            fixtureUrl=url,ownerToken=owner,operation=operation,**({'surface':reference_surface} if reference_surface is not None else {}),**fields))
        try:
            self.lock.assert_held();need(not self.read_only or operation in ('observe','measure'))
            start=previous=self.monotonic();requested=self.clock_ms();need(number(start,0,1e15) and integer(requested,1) and self.guard() is not False)
            self.send(request)
            for attempt in range(51):
                need(self.guard() is not False);raw=self.original()
                try:value=decode(raw) if raw else None
                except json.JSONDecodeError:value=None
                now=self.monotonic();need(number(now,previous,start+5));previous=now
                if type(value) is dict and value.get('commandId')==request['commandId']:
                    epoch=self.clock_ms();validate(value,request,self.pid,epoch);need(value['picoBrowserVersion']==VERSION)
                    need(value['capturedEpochMs']>=requested and value['status']!='unavailable')
                    if value['status']=='ready':
                        continuity(self.last,value);need(self.guard() is not False)
                        final=self.clock_ms();need(integer(final,epoch));fresh(value['capturedEpochMs'],final)
                        if operation=='observe' and reference_surface is None and value['source']['current']:
                            fresh(value['source']['current']['source']['dom']['capturedEpochMs'],final)
                        finished=self.monotonic();need(number(finished,previous,start+5) and finished-start<5
                            and max(final-value['capturedEpochMs'],requested-value['capturedEpochMs']+math.ceil((finished-start)*1000))<=1500)
                        checked_host,checked_epoch=finished,final
                        retained,returned=deepcopy(value),deepcopy(value)
                        self.lock.assert_held();need(self.guard() is not False)
                        final=self.clock_ms();finished=self.monotonic()
                        need(integer(final,checked_epoch) and number(finished,checked_host,start+5) and finished-start<5
                            and max(final-value['capturedEpochMs'],requested-value['capturedEpochMs']+math.ceil((finished-start)*1000))<=1500)
                        if operation=='observe' and reference_surface is None and value['source']['current']:
                            fresh(value['source']['current']['source']['dom']['capturedEpochMs'],final)
                        if operation=='measure':
                            geometry_original(value['source']['geometryRaw'],request,value['source']['nativeView']['url'],final,visible=False)
                        self.last=retained;return returned
                need(attempt<50 and now-start<5);self.sleep(.1)
        except Exception:raise NativeUIError('Original Pico World Web source or input is unavailable') from None
        raise NativeUIError('Original Pico World Web source did not produce this request')
