"""Original tablet QML/XHR/reply ownership; neither navigation nor an effect verdict."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import math
import re
import time
import uuid
from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.normal_ui import NativeUIError

VERSION=1
FILE='feature-tablet-http.json'
STATE={'readyState','errorCode','status','timerActive','readyHandler','timeoutHandler','callbackDepth'}
KINDS={'bound','state','callback-enter','callback-exit','destroying','destroyed','reply','reply-destroyed'}


def nonce(value):return type(value) is str and re.fullmatch('[0-9a-f]{32}',value) is not None


def digest(value):return type(value) is str and re.fullmatch('[0-9a-f]{64}',value) is not None


def command(value):
    exact(value,{'schemaVersion','commandId','action','runId'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['action']=='feature-tablet-http-observe'
         and nonce(value['commandId']) and nonce(value['runId']))
    return value


def state(value):
    exact(value,STATE)
    need(integer(value['readyState'],0,4) and integer(value['errorCode'],0,499)
        and (value['status'] is None or integer(value['status'],0,599))
        and integer(value['callbackDepth'],0,16)
        and all(type(value[key]) is bool for key in ('timerActive','readyHandler','timeoutHandler')))


def validate(value,request,pid,epoch):
    command(request)
    exact(value,{'tabletHttpVersion','commandId','runId','instance','sequence','processId','capturedEpochMs',
        'complete','containerPresent','roots','requests'})
    need(type(value['tabletHttpVersion']) is int and value['tabletHttpVersion']==VERSION
        and value['commandId']==request['commandId'] and value['runId']==request['runId'] and nonce(value['instance'])
        and integer(value['sequence'],1,1000000000) and integer(value['processId'],1) and value['processId']==pid
        and type(value['complete']) is bool and type(value['containerPresent']) is bool
        and type(value['roots']) is list and len(value['roots'])<=128
        and type(value['requests']) is list and len(value['requests'])<=512)
    fresh(value['capturedEpochMs'],epoch)
    roots={};requests=set();qml_ids=set();global_events=set();reply_ids=set();queued=0
    for root in value['roots']:
        exact(root,{'id','sourceSha256','helperAlive','rootAlive','inCurrentTree','callbackIds','callbackDepth'})
        need(nonce(root['id']) and root['id'] not in roots and digest(root['sourceSha256'])
            and all(type(root[key]) is bool for key in ('helperAlive','rootAlive','inCurrentTree'))
            and (not root['helperAlive'] or root['rootAlive']) and (not root['inCurrentTree'] or root['helperAlive']))
        if root['helperAlive']:
            need(type(root['callbackIds']) is list and len(root['callbackIds'])<=512
                and all(integer(item,0,1000000000) for item in root['callbackIds'])
                and root['callbackIds']==sorted(set(root['callbackIds'])) and integer(root['callbackDepth'],0,16))
        else:need(root['callbackIds'] is None and root['callbackDepth'] is None)
        roots[root['id']]=root
    for row in value['requests']:
        exact(row,{'id','rootId','qmlRequestId','paramsSha256','queuedEpochMs','events','bound','requestAlive','state','replies','destroyed'})
        need(nonce(row['id']) and row['id'] not in requests and type(row['rootId']) is str and row['rootId'] in roots
            and integer(row['qmlRequestId'],0,1000000000) and (row['rootId'],row['qmlRequestId']) not in qml_ids
            and digest(row['paramsSha256']) and integer(row['queuedEpochMs'],max(1,queued),value['capturedEpochMs'])
            and type(row['events']) is list and len(row['events'])<=128
            and type(row['replies']) is list and len(row['replies'])<=8
            and type(row['bound']) is bool and type(row['destroyed']) is bool)
        requests.add(row['id']);qml_ids.add((row['rootId'],row['qmlRequestId']));queued=row['queuedEpochMs']
        bound=False;destroyed=False;current=None;depth=0;ready=0;replies={};sequence=0;occurred=queued;received=queued
        for event in row['events']:
            exact(event,{'sequence','kind','occurredEpochMs','receivedEpochMs','state','replyId'})
            need(integer(event['sequence'],sequence+1,8192) and event['sequence'] not in global_events
                and type(event['kind']) is str and event['kind'] in KINDS
                and integer(event['occurredEpochMs'],occurred,value['capturedEpochMs'])
                and integer(event['receivedEpochMs'],max(received,event['occurredEpochMs']),value['capturedEpochMs']))
            kind=event['kind'];need(not destroyed or kind=='reply-destroyed')
            if kind=='bound':
                need(not bound and event['state']==dict(readyState=0,errorCode=0,status=None,
                    timerActive=False,readyHandler=False,timeoutHandler=False,callbackDepth=0));bound=True
            else:need(bound)
            if kind=='reply':
                need(nonce(event['replyId']) and event['replyId'] not in reply_ids and event['state'] is None)
                replies[event['replyId']]=dict(created=event['occurredEpochMs'],destroyed=False);reply_ids.add(event['replyId'])
            elif kind=='reply-destroyed':
                need(nonce(event['replyId']) and event['replyId'] in replies and not replies[event['replyId']]['destroyed'] and event['state'] is None)
                replies[event['replyId']]['destroyed']=True
            else:need(event['replyId'] is None)
            if kind=='destroyed':need(event['state'] is None);destroyed=True
            elif kind not in ('reply','reply-destroyed'):
                state(event['state'])
                if kind=='callback-enter':depth+=1
                elif kind=='callback-exit':depth-=1
                need(event['state']['callbackDepth']==depth and 0<=depth<=16 and event['state']['readyState']>=ready)
                ready=event['state']['readyState'];current=event['state']
            sequence=event['sequence'];global_events.add(sequence)
            occurred=event['occurredEpochMs'];received=event['receivedEpochMs']
        need(row['bound']==bound and row['destroyed']==destroyed and row['state']==current
            and (type(row['requestAlive']) is bool if bound else row['requestAlive'] is None)
            and (not destroyed or row['requestAlive'] is False) and len(row['replies'])==len(replies))
        for reply,identifier in zip(row['replies'],replies):
            exact(reply,{'id','createdEpochMs','urlSha256','alive','destroyed'})
            original=replies[identifier]
            need(reply['id']==identifier and reply['createdEpochMs']==original['created'] and digest(reply['urlSha256'])
                and type(reply['alive']) is bool and type(reply['destroyed']) is bool
                and reply['destroyed']==original['destroyed'] and (not reply['destroyed'] or reply['alive'] is False))
    need(global_events==set(range(1,len(global_events)+1)))
    for root in roots.values():
        need(root['callbackIds'] is None or all((root['id'],item) in qml_ids for item in root['callbackIds']))
    return value


def continuity(previous,value,pid):
    if previous is None:return
    validate(previous,dict(schemaVersion=1,commandId=previous['commandId'],action='feature-tablet-http-observe',runId=previous['runId']),pid,previous['capturedEpochMs'])
    need(value['instance']==previous['instance'] and value['sequence']>previous['sequence'] and value['runId']==previous['runId']
        and value['capturedEpochMs']>=previous['capturedEpochMs'] and (previous['complete'] or value['complete'] is False))
    for field in ('roots','requests'):
        need(len(value[field])>=len(previous[field]))
        for old,new in zip(previous[field],value[field]):
            keys=('id','sourceSha256') if field=='roots' else ('id','rootId','qmlRequestId','paramsSha256','queuedEpochMs')
            need(all(old[key]==new[key] for key in keys))
            if field=='roots':
                need((old['helperAlive'] or not new['helperAlive']) and (old['rootAlive'] or not new['rootAlive']))
                if new['callbackIds'] is not None:
                    known={row['qmlRequestId'] for row in previous['requests'] if row['rootId']==old['id']}
                    need(not (set(new['callbackIds'])-set(old['callbackIds'] or []))&known)
            else:
                need(new['events'][:len(old['events'])]==old['events'] and len(new['replies'])>=len(old['replies'])
                    and (old['requestAlive'] is not False or new['requestAlive'] is False))
                for a,b in zip(old['replies'],new['replies']):
                    need(all(a[key]==b[key] for key in ('id','createdEpochMs','urlSha256')) and (a['alive'] or not b['alive']))


def released(value):
    """Require actual original UI roots, callbacks, timers and replies to retire.

    An empty map, completed HTTP status, absent XHR or hidden page alone cannot
    satisfy this predicate. Its caller must independently enforce a quiet window.
    """
    need(type(value) is dict)
    validate(value,dict(schemaVersion=1,commandId=value.get('commandId'),action='feature-tablet-http-observe',runId=value.get('runId')),
        value.get('processId'),value.get('capturedEpochMs'))
    need(value['complete'] is True)
    for root in value['roots']:need(not root['helperAlive'] and not root['rootAlive'])
    for row in value['requests']:
        need(row['bound'] and row['state']['callbackDepth']==0
            and all(reply['destroyed'] and not reply['alive'] for reply in row['replies']))
        if not row['destroyed']:
            need(row['requestAlive'] is True and row['state']['readyState']==4
                and not any(row['state'][key] for key in ('timerActive','readyHandler','timeoutHandler')))
    return True


class NativeTabletHttp:
    def __init__(self,send,original,clock_ms,guard,pid,*,monotonic=time.monotonic,sleep=time.sleep):
        need(all(callable(value) for value in (send,original,clock_ms,guard,monotonic,sleep)) and integer(pid,1))
        self.send,self.original,self.clock_ms,self.guard,self.pid=send,original,clock_ms,guard,pid
        self.monotonic,self.sleep,self.last=monotonic,sleep,None

    def read(self,run):
        try:
            request=command(dict(schemaVersion=1,commandId=uuid.uuid4().hex,action='feature-tablet-http-observe',runId=run))
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
        except Exception:raise NativeUIError('Original native tablet HTTP observation is unavailable or invalid') from None
        raise NativeUIError('Original native tablet HTTP observation did not produce this request')
