"""Original native retained IME-event receipts, not lifecycle verdicts.

The original native UI binding/nonce transport is still required. This reader
never constructs a missing event, supplies text as a read or assigns a context.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import re
from urllib.parse import urlsplit

VERSION=1
HEX=re.compile(r'[0-9a-f]{32}')
SHA=re.compile(r'[0-9a-f]{64}')
NONCE=re.compile(r'(?:ios-)?[0-9a-f]{32}')


def need(condition):
    if not condition:raise ValueError('Original native pending field commit is unavailable')


def exact(value,keys):need(type(value) is dict and set(value)==set(keys))
def integer(value,minimum=0,maximum=1_000_000_000_000_000):
    return type(value) is int and minimum<=value<=maximum
def sha(value):return type(value) is str and SHA.fullmatch(value) is not None
def digest(value):return hashlib.sha256(value.encode('utf-8')).hexdigest()


def component_url(value):
    need(type(value) is str and len(value)<=4096 and all(ord(c)>=32 and ord(c)!=127 for c in value))
    parsed=urlsplit(value)
    need(parsed.scheme in ('file','qrc') and not parsed.netloc and not parsed.query and not parsed.fragment
         and parsed.path.endswith('/hifi/dialogs/TabletRunningScripts.qml'))
    return value


def validate(value,request_id,run,pid,epoch_ms,*,original_component_url):
    need(type(request_id) is str and NONCE.fullmatch(request_id) is not None
         and type(run) is str and HEX.fullmatch(run) is not None and integer(pid,1) and integer(epoch_ms,1))
    exact(value,{'pendingFieldCommitVersion','requestId','instance','eventId','sequence','processId',
                 'createdEpochMs','capturedEpochMs','elapsedMs','pending','source','events'})
    need(type(value['pendingFieldCommitVersion']) is int and value['pendingFieldCommitVersion']==VERSION
         and value['requestId']==request_id and value['processId']==pid and type(value['processId']) is int
         and all(type(value[key]) is str and HEX.fullmatch(value[key]) is not None for key in ('instance','eventId'))
         and integer(value['sequence'],1) and integer(value['createdEpochMs'],1)
         and integer(value['capturedEpochMs'],value['createdEpochMs']) and integer(value['elapsedMs'])
         and type(value['pending']) is bool and epoch_ms-1500<=value['capturedEpochMs']<=epoch_ms+250
         and abs(value['capturedEpochMs']-value['createdEpochMs']-value['elapsedMs'])<=250)
    source=value['source']
    exact(source,{'componentUrl','fieldName','initialTextSha256','inputSha256','inputCodeUnits'})
    need(component_url(source['componentUrl'])==component_url(original_component_url) and source['fieldName']=='scriptFilter'
         and sha(source['initialTextSha256']) and sha(source['inputSha256'])
         and source['initialTextSha256']==digest('retry-'+run)
         and source['inputSha256']==digest('Overte ä Ω 東京 '+run)
         and integer(source['inputCodeUnits'],1,4096)
         and source['inputCodeUnits']==len(('Overte ä Ω 東京 '+run).encode('utf-16-le'))//2)
    events=value['events']
    need(type(events) is list and 1<=len(events)<=2 and value['pending']==(len(events)==1))
    prior_epoch=value['createdEpochMs'];prior_elapsed=0
    for index,event in enumerate(events):
        exact(event,{'sequence','kind','reason','capturedEpochMs','elapsedMs'})
        need(type(event['sequence']) is int and event['sequence']==index+1
             and integer(event['capturedEpochMs'],prior_epoch,value['capturedEpochMs'])
             and integer(event['elapsedMs'],prior_elapsed,value['elapsedMs'])
             and abs(event['capturedEpochMs']-value['createdEpochMs']-event['elapsedMs'])<=250)
        if index==0:need(event['kind']=='captured' and event['reason']=='none' and event['elapsedMs']<10000)
        else:
            need(event['kind'] in ('rejected','sent','expired','released'))
            if event['kind']=='rejected':
                need(event['reason'] in ('context-retired','focus-lost','editor-changed') and event['elapsedMs']<10000)
            elif event['kind']=='expired':need(event['reason']=='hold-deadline' and event['elapsedMs']>=10000)
            else:need(event['reason']=='none' and event['elapsedMs']<10000)
        prior_epoch,prior_elapsed=event['capturedEpochMs'],event['elapsedMs']
    if value['pending']:need(value['elapsedMs']<10000)
    return deepcopy(value)


class OriginalCommit:
    """Pin actual native event identity/history across independent nonce reads."""
    def __init__(self,run,pid,original_component_url):
        need(type(run) is str and HEX.fullmatch(run) is not None and integer(pid,1))
        self.run,self.pid,self.previous=run,pid,None
        self.original_component_url=component_url(original_component_url)
        self.requests=set()

    def read(self,value,request_id,epoch_ms):
        need(type(request_id) is str and NONCE.fullmatch(request_id) is not None
             and request_id not in self.requests and len(self.requests)<128)
        current=validate(value,request_id,self.run,self.pid,epoch_ms,original_component_url=self.original_component_url)
        old=self.previous
        if old is not None:
            need(all(current[k]==old[k] for k in ('instance','eventId','processId','createdEpochMs','source'))
                 and current['sequence']>old['sequence'] and current['capturedEpochMs']>=old['capturedEpochMs']
                 and current['elapsedMs']>=old['elapsedMs'] and len(current['events'])>=len(old['events'])
                 and current['events'][:len(old['events'])]==old['events'])
        self.previous=deepcopy(current);self.requests.add(request_id)
        return current

    def retired_attempt(self):
        value=self.previous
        need(value is not None and value['pending'] is False and len(value['events'])==2)
        event=value['events'][-1]
        need(event['kind']=='rejected' and event['reason']=='context-retired')
        # Return the original receipt only. The full observer must independently
        # join the actual new page/generation, text, keyboard and source binding.
        return deepcopy(event)
