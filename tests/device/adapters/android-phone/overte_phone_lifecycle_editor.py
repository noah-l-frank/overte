"""Fresh original Phone editor contexts and normal native input receipts."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import time
import uuid
from urllib.parse import urlsplit
from adapters.native_feature_observation import exact,need,integer,number,decode,fresh
from adapters.normal_ui import NativeUIError
from overte_phone_snapshot_readbacks import nonce

FILE='phone-lifecycle-editor.json'
EDITORS={'create','chat','scripts'}
SUFFIXES=dict(create='/system/create/qml/NativeCreate.qml',chat='/communityScripts/armored-chat/armored_chat.qml',scripts='/hifi/dialogs/TabletRunningScripts.qml')


def command(value):
    input=type(value) is dict and value.get('action')=='phone-lifecycle-editor-input'
    exact(value,{'schemaVersion','commandId','action','runId'}|({'operation','fieldToken','observationSequence'} if input else set()))
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and nonce(value['commandId']) and nonce(value['runId'])
        and value['action'] in ('phone-lifecycle-editor-observe','phone-lifecycle-editor-input'))
    if input:need(value['operation'] in ('focus','type') and nonce(value['fieldToken']) and integer(value['observationSequence'],1))
    return value


def source(value,run,epoch):
    exact(value,{'phoneLifecycleEditorVersion','instance','sequence','capturedEpochMs','canonicalSources','current','contexts','osKeyboardVisible'})
    need(type(value['phoneLifecycleEditorVersion']) is int and value['phoneLifecycleEditorVersion']==1 and nonce(value['instance'])
        and integer(value['sequence'],1) and integer(value['capturedEpochMs'],1,epoch) and type(value['osKeyboardVisible']) is bool)
    urls=value['canonicalSources'];exact(urls,EDITORS)
    for editor,url in urls.items():
        need(type(url) is str and 0<len(url)<=4096);parsed=urlsplit(url)
        need(parsed.scheme in ('file','qrc') and not parsed.netloc and not parsed.query and not parsed.fragment
            and parsed.path.endswith(SUFFIXES[editor]) and not any(ord(char)<32 or ord(char)==127 for char in url))
    need(type(value['contexts']) is list and len(value['contexts'])<=64);tokens=set();fields=set();active=[]
    for row in value['contexts']:
        exact(row,{'editor','token','fieldToken','sourceUrl','createdEpochMs','retiredEpochMs','alive','attached','active'})
        need(row['editor'] in EDITORS and nonce(row['token']) and row['token'] not in tokens and nonce(row['fieldToken']) and row['fieldToken'] not in fields
            and row['sourceUrl']==urls[row['editor']] and integer(row['createdEpochMs'],1,value['capturedEpochMs'])
            and integer(row['retiredEpochMs'],0,value['capturedEpochMs']) and all(type(row[key]) is bool for key in ('alive','attached','active')))
        tokens.add(row['token']);fields.add(row['fieldToken'])
        if row['retiredEpochMs']:need(row['retiredEpochMs']>=row['createdEpochMs'] and not row['active'])
        if row['active']:need(row['alive'] and row['attached'] and row['retiredEpochMs']==0);active.append(row)
    current=value['current'];need(type(current) is dict and current.get('status') in ('none','ready'))
    if current['status']=='none':exact(current,{'status'});need(not active)
    else:
        exact(current,{'status','editor','token','fieldToken','sourceUrl','text','focused','frame'})
        need(len(active)==1 and all(current[key]==active[0][key] for key in ('editor','token','fieldToken','sourceUrl'))
            and type(current['focused']) is bool and type(current['text']) is str)
        text='Overte ä Ω 東京 '+run if current['editor']=='create' else ('reply-' if current['editor']=='chat' else 'retry-')+run
        need(current['text'] in ('',text) and type(current['frame']) is list and len(current['frame'])==4
            and all(number(item,0,16384) for item in current['frame']) and min(current['frame'][2:])>0)
    return value


def advance(before,after):
    need(all(before[key]==after[key] for key in ('runId','instance','processId')) and after['sequence']>before['sequence']
        and after['capturedEpochMs']>=before['capturedEpochMs'])
    a,b=before['source'],after['source'];need(a['instance']==b['instance'] and a['canonicalSources']==b['canonicalSources']
        and b['sequence']>a['sequence'] and b['capturedEpochMs']>=a['capturedEpochMs'])
    old={row['token']:row for row in a['contexts']};new={row['token']:row for row in b['contexts']};need(set(old)<=set(new))
    for token,row in old.items():
        current=new[token];need(all(current[key]==row[key] for key in ('editor','token','fieldToken','sourceUrl','createdEpochMs'))
            and (row['alive'] or not current['alive']))
        if row['retiredEpochMs']:need(current['retiredEpochMs']==row['retiredEpochMs'] and not current['active'])


class PhoneLifecycleEditorSource:
    def __init__(self,send,read,clock_ms,guard,pid,*,intent=None,monotonic=time.monotonic,sleep=time.sleep):
        need(all(callable(fn) for fn in (send,read,clock_ms,guard,monotonic,sleep)) and integer(pid,1) and (intent is None or callable(intent)))
        self.send,self.read,self.clock_ms,self.guard,self.pid=send,read,clock_ms,guard,pid
        self.intent,self.monotonic,self.sleep,self.last=intent,monotonic,sleep,None
    def request(self,run,operation='observe'):
        try:
            request=dict(schemaVersion=1,commandId=uuid.uuid4().hex,action='phone-lifecycle-editor-observe',runId=run)
            if operation!='observe':
                need(self.intent is not None and self.last is not None and self.last['runId']==run and self.last['source']['current']['status']=='ready')
                request.update(action='phone-lifecycle-editor-input',operation=operation,fieldToken=self.last['source']['current']['fieldToken'],
                    observationSequence=self.last['source']['sequence'])
            command(request);need(self.guard() is not False);previous=started=self.monotonic();requested=self.clock_ms();need(integer(requested,1))
            if operation!='observe':need(self.intent(deepcopy(request)) is not False and self.guard() is not False)
            self.send(request)
            for attempt in range(51):
                need(self.guard() is not False);raw=self.read();need(type(raw) is str and len(raw.encode())<=65536)
                try:value=decode(raw) if raw else None
                except json.JSONDecodeError:value=None
                now=self.monotonic();need(number(now,previous,1e15) and now-started<5);previous=now
                if type(value) is dict and value.get('requestId')==request['commandId']:
                    exact(value,{'schemaVersion','requestId','runId','instance','sequence','processId','requestedEpochMs','capturedEpochMs','performed','source'})
                    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['runId']==run and nonce(value['instance']) and integer(value['sequence'],1)
                        and type(value['processId']) is int and value['processId']==self.pid and type(value['performed']) is bool
                        and (operation!='observe' or value['performed'] is False) and integer(value['requestedEpochMs'],requested)
                        and integer(value['capturedEpochMs'],value['requestedEpochMs']) and value['capturedEpochMs']-value['requestedEpochMs']<1500)
                    fresh(value['capturedEpochMs'],self.clock_ms());source(value['source'],run,value['capturedEpochMs'])
                    need(value['source']['capturedEpochMs']>=value['requestedEpochMs'])
                    if self.last is not None:advance(self.last,value)
                    now=self.monotonic();need(self.guard() is not False and number(now,previous,1e15) and now-started<5);fresh(value['capturedEpochMs'],self.clock_ms())
                    self.last=deepcopy(value);return deepcopy(value)
                if attempt<50:self.sleep(.1)
        except Exception:raise NativeUIError('Original Phone lifecycle editor source or normal input is unavailable') from None
        raise NativeUIError('Original Phone lifecycle editor source did not produce this request')
