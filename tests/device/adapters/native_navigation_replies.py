"""Original current native named-lookup callback and owned HTTP receipt join.

This read-only component does not establish a modal, arrival or full feature.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
import time
from urllib.parse import urlsplit
import uuid
from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.normal_ui import NativeUIError
from feature_journeys.navigation_fixture import configuration,validate_status

VERSION=1
FILE='feature-navigation-replies.json'
LIMIT=262144
HEX='[0-9a-f]{32}'


def command(value,*,ios=False):
    exact(value,{'schemaVersion','commandId','action','runId'})
    need(type(ios) is bool and type(value['schemaVersion']) is int and value['schemaVersion']==1
         and value['action']=='feature-navigation-replies' and type(value['commandId']) is str
         and re.fullmatch(('ios-' if ios else '')+HEX,value['commandId'])
         and type(value['runId']) is str and re.fullmatch(HEX,value['runId']))
    return value


def origin(value):
    need(type(value) is str and 0<len(value)<=512 and not any(ord(c)<=32 or ord(c)==127 for c in value))
    parsed=urlsplit(value);parsed.port
    need(parsed.scheme in ('http','https') and parsed.hostname and parsed.username is None and parsed.password is None
         and not parsed.path and not parsed.query and not parsed.fragment
         and value==parsed.scheme+'://'+parsed.netloc.lower())
    return value


def validate(value,request,pid,epoch):
    command(request,ios=request['commandId'].startswith('ios-'))
    exact(value,{'navigationReplyVersion','commandId','runId','instance','sequence','processId','capturedEpochMs','currentLookupGeneration','currentLookupActive','events'})
    need(type(value['navigationReplyVersion']) is int and value['navigationReplyVersion']==VERSION
         and value['commandId']==request['commandId'] and value['runId']==request['runId']
         and integer(pid,1) and integer(value['processId'],1) and value['processId']==pid
         and type(value['instance']) is str and re.fullmatch(HEX,value['instance'])
         and integer(value['currentLookupGeneration'],1) and type(value['currentLookupActive']) is bool
         and integer(value['sequence'],1,1_000_000_000) and type(value['events']) is list and len(value['events'])<=128)
    fresh(value['capturedEpochMs'],epoch)
    ids=set();responses=set();sequence=0;captured=0
    for event in value['events']:
        exact(event,{'sequence','eventId','runId','responseId','origin','httpStatus','networkError','contentNotFound','current','lookupGeneration','callbackEpochMs'})
        need(integer(event['sequence'],sequence+1,1_000_000_000) and type(event['eventId']) is str and re.fullmatch(HEX,event['eventId'])
             and event['eventId'] not in ids and event['runId']==request['runId']
             and type(event['responseId']) is str and (not event['responseId'] or re.fullmatch(HEX,event['responseId']))
             and (not event['responseId'] or event['responseId'] not in responses)
             and integer(event['httpStatus'],0,599) and integer(event['networkError'],1,499)
             and type(event['contentNotFound']) is bool and event['contentNotFound']==(event['networkError']==203)
             and event['current'] is True and integer(event['lookupGeneration'],1,value['currentLookupGeneration'])
             and integer(event['callbackEpochMs'],1) and captured<=event['callbackEpochMs']<=value['capturedEpochMs'])
        origin(event['origin']);ids.add(event['eventId'])
        if event['responseId']:responses.add(event['responseId'])
        sequence=event['sequence'];captured=event['callbackEpochMs']
    return value


class NativeNavigationReplies:
    def __init__(self,send,original,clock_ms,guard,pid,*,ios=False,monotonic=time.monotonic,sleep=time.sleep):
        need(all(callable(f) for f in (send,original,clock_ms,guard,monotonic,sleep)) and integer(pid,1) and type(ios) is bool)
        self.send,self.original,self.clock_ms,self.guard,self.pid=send,original,clock_ms,guard,pid
        self.ios,self.monotonic,self.sleep=ios,monotonic,sleep
        self.last=None;self.histories={}

    def read(self,run):
        request=dict(schemaVersion=1,commandId=('ios-' if self.ios else '')+uuid.uuid4().hex,action='feature-navigation-replies',runId=run)
        command(request,ios=self.ios)
        try:
            need(self.guard() is not False)
            started=self.monotonic();need(number(started,0,1e15));previous=started
            self.send(deepcopy(request))
            for attempt in range(51):
                now=self.monotonic();need(number(now,0,1e15) and previous<=now and now-started<5)
                need(self.guard() is not False)
                raw=self.original()
                try:value=decode(raw) if raw else None
                except ValueError:value=None
                if type(value) is dict and value.get('commandId')==request['commandId']:
                    validate(value,request,self.pid,self.clock_ms())
                    if self.last is not None:
                        need(value['instance']==self.last['instance'] and value['sequence']>self.last['sequence']
                             and value['capturedEpochMs']>=self.last['capturedEpochMs']
                             and value['currentLookupGeneration']>=self.last['currentLookupGeneration'])
                    if run in self.histories:
                        old=self.histories[run]
                        need(len(value['events'])>=len(old) and value['events'][:len(old)]==old)
                    need(len(self.histories)<32 or run in self.histories)
                    now=self.monotonic();need(number(now,0,1e15) and previous<=now and now-started<5 and self.guard() is not False)
                    self.last=deepcopy(value);self.histories[run]=deepcopy(value['events']);return value
                now=self.monotonic();need(number(now,0,1e15) and previous<=now);previous=now
                if now-started>=5 or attempt==50:break
                self.sleep(min(.1,5-(now-started)))
        except Exception:raise NativeUIError('Original native navigation reply source failed') from None
        raise NativeUIError('Original native navigation reply source failed')

    def owned_missing(self,run,*,owned_origin,ticket,after_epoch,provider_status,provider_instance,provider_inputs):
        # Origin/configuration come from the separately selected original fixture,
        # never from the callback under test. No modal/arrival verdict is returned.
        origin(owned_origin);need(type(ticket) is str and re.fullmatch(HEX,ticket) and integer(after_epoch,1))
        configuration(provider_inputs)
        validate_status(provider_status,instance=provider_instance,run=run,inputs=provider_inputs)
        need(provider_status['active'] and provider_status['ticket']==ticket)
        native=self.read(run)
        responses={row['responseId']:row for row in provider_status['responses']
            if row['kind']=='missing-name' and row['status']==404 and row['ticket']==ticket and row['completedEpochMs']>=after_epoch}
        matched=[(event,responses[event['responseId']]) for event in native['events']
            if native['currentLookupActive'] and event['lookupGeneration']==native['currentLookupGeneration']
            and event['origin']==owned_origin and event['httpStatus']==404 and event['contentNotFound']
            and event['callbackEpochMs']>=after_epoch and event['responseId'] in responses]
        need(bool(matched))
        event,response=matched[-1]
        return dict(native=deepcopy(event),http=deepcopy(response))
