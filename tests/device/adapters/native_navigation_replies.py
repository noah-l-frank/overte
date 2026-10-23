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

VERSION=2
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
    need(type(value['navigationReplyVersion']) is int and value['navigationReplyVersion'] in (1,2)
         and value['commandId']==request['commandId'] and value['runId']==request['runId']
         and integer(pid,1) and integer(value['processId'],1) and value['processId']==pid
         and type(value['instance']) is str and re.fullmatch(HEX,value['instance'])
         and integer(value['currentLookupGeneration'],1) and type(value['currentLookupActive']) is bool
         and integer(value['sequence'],1,1_000_000_000) and type(value['events']) is list and len(value['events'])<=128)
    fresh(value['capturedEpochMs'],epoch)
    ids=set();responses=set();captures=set();sequence=0;captured=0
    for event in value['events']:
        validate_event(event,request['runId'],generation=value['currentLookupGeneration'],epoch=value['capturedEpochMs'],
                       after_sequence=sequence,after_epoch=captured,require_capture=value['navigationReplyVersion']==2)
        need(value['navigationReplyVersion']==2 or not ({'replyCaptureId','replyCapturedEpochMs'} & set(event)))
        need(event['eventId'] not in ids and (not event['responseId'] or event['responseId'] not in responses))
        if value['navigationReplyVersion']==2:
            need(event['replyCaptureId'] not in captures);captures.add(event['replyCaptureId'])
        ids.add(event['eventId'])
        if event['responseId']:responses.add(event['responseId'])
        sequence=event['sequence'];captured=event['callbackEpochMs']
    return value


def validate_event(event,run,*,generation,epoch,after_sequence=0,after_epoch=0,require_capture=False):
    """Pure original callback validation, including historical presentation joins."""
    need(type(event) is dict and type(require_capture) is bool)
    captured = {'replyCaptureId','replyCapturedEpochMs'} & set(event)
    exact(event,{'sequence','eventId','runId','responseId','origin','httpStatus','networkError','contentNotFound','current','lookupGeneration','callbackEpochMs'} | captured)
    need(not require_capture or captured=={'replyCaptureId','replyCapturedEpochMs'})
    need(type(run) is str and re.fullmatch(HEX,run) and integer(generation,1) and integer(epoch,1)
         and integer(after_sequence) and integer(after_epoch)
         and integer(event['sequence'],after_sequence+1,1_000_000_000)
         and type(event['eventId']) is str and re.fullmatch(HEX,event['eventId']) and event['runId']==run
         and type(event['responseId']) is str and (not event['responseId'] or re.fullmatch(HEX,event['responseId']))
         and integer(event['httpStatus'],0,599) and integer(event['networkError'],1,499)
         and type(event['contentNotFound']) is bool and event['contentNotFound']==(event['networkError']==203)
         and event['current'] is True and integer(event['lookupGeneration'],1,generation)
         and integer(event['callbackEpochMs'],1) and after_epoch<=event['callbackEpochMs']<=epoch)
    if captured:
        need(captured=={'replyCaptureId','replyCapturedEpochMs'} and type(event['replyCaptureId']) is str
             and re.fullmatch(HEX,event['replyCaptureId']) and integer(event['replyCapturedEpochMs'],1,event['callbackEpochMs']))
    origin(event['origin'])
    return event


def join_missing(reply,provider,ticket,after_epoch,owned_origin):
    """Already validated original packets; no query or desired native outcome."""
    origin(owned_origin);need(type(ticket) is str and re.fullmatch(HEX,ticket) and integer(after_epoch,1))
    responses={row['responseId']:row for row in provider['responses']
        if row['ticket']==ticket and row['kind']=='missing-name' and row['status']==404 and row['completedEpochMs']>=after_epoch}
    matches=[(event,responses[event['responseId']]) for event in reply['events']
        if event['responseId'] in responses and event['origin']==owned_origin and event['httpStatus']==404
        and event['contentNotFound'] and event['callbackEpochMs']>=after_epoch
        and event.get('replyCapturedEpochMs',event['callbackEpochMs'])>=after_epoch]
    need(len(matches)==1);event,response=matches[0]
    return dict(event=deepcopy(event),response=deepcopy(response))


def continuation(previous,current):
    """Pure cursor/history comparison; never query or rewrite an original."""
    need(current['navigationReplyVersion']==previous['navigationReplyVersion']
        and current['instance']==previous['instance'] and current['processId']==previous['processId']
        and current['sequence']>previous['sequence'] and current['capturedEpochMs']>=previous['capturedEpochMs']
        and current['commandId']!=previous['commandId'] and current['currentLookupGeneration']>=previous['currentLookupGeneration'])
    if current['runId']==previous['runId']:
        need(current['events'][:len(previous['events'])]==previous['events'] and len(current['events'])>=len(previous['events']))


class NativeNavigationReplies:
    def __init__(self,send,original,clock_ms,guard,pid,*,ios=False,monotonic=time.monotonic,sleep=time.sleep):
        need(all(callable(f) for f in (send,original,clock_ms,guard,monotonic,sleep)) and integer(pid,1) and type(ios) is bool)
        self.send,self.original,self.clock_ms,self.guard,self.pid=send,original,clock_ms,guard,pid
        self.ios,self.monotonic,self.sleep=ios,monotonic,sleep
        self.last=None;self.histories={};self.requests=set()

    def read(self,run):
        request=dict(schemaVersion=1,commandId=('ios-' if self.ios else '')+uuid.uuid4().hex,action='feature-navigation-replies',runId=run)
        command(request,ios=self.ios)
        try:
            need(len(self.requests)<4096 and request['commandId'] not in self.requests)
            self.requests.add(request['commandId'])
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
                        continuation(self.last,value)
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
            and event['callbackEpochMs']>=after_epoch and event.get('replyCapturedEpochMs',event['callbackEpochMs'])>=after_epoch
            and event['responseId'] in responses]
        need(bool(matched))
        event,response=matched[-1]
        return dict(native=deepcopy(event),http=deepcopy(response))
