"""Closed native view/actual DOM acquisition; no full browser verdict or counters."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import re
import time
from urllib.parse import urlsplit
import uuid

from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.normal_ui import NativeUIError

VERSION=1
FILE='feature-web-dom-observation.json'
HEX='[0-9a-f]{32}'


def command(value,*,ios=False):
    exact(value,{'schemaVersion','commandId','action','runId','surface','fixtureUrl'})
    need(type(ios) is bool and type(value['schemaVersion']) is int and value['schemaVersion']==1
         and value['action']=='feature-web-dom-observe' and type(value['commandId']) is str
         and re.fullmatch(('ios-' if ios else '')+HEX,value['commandId'])
         and type(value['runId']) is str and re.fullmatch(HEX,value['runId'])
         and value['surface'] in ('world','tablet') and type(value['fixtureUrl']) is str
         and len(value['fixtureUrl'])<=512 and not any(ord(c)<33 or ord(c)==127 for c in value['fixtureUrl']))
    parsed=urlsplit(value['fixtureUrl'])
    need(parsed.scheme in ('http','https') and parsed.hostname and parsed.username is None and parsed.password is None
         and not parsed.query and not parsed.fragment and parsed.path=='/feature-fixture/v1/runs/'+value['runId']+'/')
    parsed.port
    return value


def dom(value,request,epoch):
    exact(value,{'webDOMVersion','requestId','instance','sequence','capturedEpochMs','document','editor','attempts','echoes'})
    need(type(value['webDOMVersion']) is int and value['webDOMVersion']==1 and value['requestId']==request['commandId']
         and type(value['instance']) is str and re.fullmatch(HEX,value['instance']) and integer(value['sequence'],1))
    fresh(value['capturedEpochMs'],epoch)
    document=value['document'];editor=value['editor']
    exact(document,{'runId','href','responseId','readyState'});exact(editor,{'text','focused'})
    need(document['runId']==request['runId'] and type(document['href']) is str and 0<len(document['href'])<=131072
         and not any(ord(c)<32 or ord(c)==127 for c in document['href']) and document['readyState']=='complete'
         and (document['responseId'] is None or type(document['responseId']) is str and re.fullmatch(HEX,document['responseId'])))
    # Preserve actual private input text. Product expectations stay exclusively
    # in the journey; the component accepts no desired text/count/outcome.
    need(type(editor['text']) is str and len(editor['text'].encode('utf-16-le',errors='strict'))//2<=512
         and type(editor['focused']) is bool)
    for key in ('attempts','echoes'):need(type(value[key]) is list and len(value[key])<=64)
    last=0
    for ordinal,entry in enumerate(value['attempts'],1):
        exact(entry,{'ordinal','capturedEpochMs','eventTimeMs'})
        need(type(entry['ordinal']) is int and entry['ordinal']==ordinal and integer(entry['capturedEpochMs'],1)
             and last<=entry['capturedEpochMs']<=value['capturedEpochMs'] and number(entry['eventTimeMs'],0,1e15))
        last=entry['capturedEpochMs']
    seen=set();last=0
    for entry in value['echoes']:
        exact(entry,{'sequence','surface','message','receivedEpochMs','observedEpochMs'})
        need(integer(entry['sequence'],1,1000000) and entry['sequence'] not in seen and entry['surface']==request['surface']
             and type(entry['message']) is str and len(entry['message'])<=4096
             and integer(entry['receivedEpochMs'],1) and integer(entry['observedEpochMs'],1)
             and last<=entry['receivedEpochMs']<=entry['observedEpochMs']<=value['capturedEpochMs'])
        packet=decode(entry['message']);exact(packet,{'contract','action','sequence','surface'})
        need(packet['contract']=='overte-web-parity-v1' and packet['action']=='echo'
             and type(packet['sequence']) is int and packet['sequence']==entry['sequence'] and packet['surface']==entry['surface'])
        seen.add(entry['sequence']);last=entry['receivedEpochMs']
    return value


def validate(value,request,pid,epoch):
    need(type(request.get('commandId')) is str);command(request,ios=request['commandId'].startswith('ios-'))
    exact(value,{'webNativeVersion','commandId','runId','surface','instance','sequence','processId','capturedEpochMs','status','source'})
    need(type(value['webNativeVersion']) is int and value['webNativeVersion']==VERSION
         and value['commandId']==request['commandId'] and value['runId']==request['runId'] and value['surface']==request['surface']
         and type(value['instance']) is str and re.fullmatch(HEX,value['instance'])
         and integer(value['sequence'],1) and integer(pid,1) and integer(value['processId'],1) and value['processId']==pid
         and value['status'] in ('pending','ready','unavailable'))
    fresh(value['capturedEpochMs'],epoch)
    if value['status']!='ready':exact(value['source'],set());return value
    source=value['source'];exact(source,{'nativeView','dom'})
    view=source['nativeView']
    exact(view,{'handle','creation','grant','page','url','nativeFinished','httpErrorStatus','inlineLease','sourceUrl','sourceIdentity'})
    need(type(view['handle']) is str and re.fullmatch('[1-9][0-9]{0,18}',view['handle'])
         and all(integer(view[k],1) for k in ('creation','grant','page'))
         and view['nativeFinished'] is True and type(view['httpErrorStatus']) is int
         and (view['httpErrorStatus']==0 or 400<=view['httpErrorStatus']<=599)
         and view['inlineLease'] is False
         and type(view['url']) is str and type(view['sourceUrl']) is str and 0<len(view['sourceUrl'])<=131072
         and type(view['sourceIdentity']) is str and 0<len(view['sourceIdentity'])<=512)
    dom(source['dom'],request,value['capturedEpochMs'])
    need(view['url']==source['dom']['document']['href'])
    prefix=request['fixtureUrl']+'tickets/'
    need(source['dom']['document']['responseId'] is not None
         and view['sourceUrl'].startswith(prefix)
         and re.fullmatch(HEX+r'/(?:index|reference)\.html',view['sourceUrl'][len(prefix):]))
    # Native source v1 deliberately cannot qualify an inline carrier from a
    # cooperative DOM label. Its separate actual ownership/byte join is pending.
    return value


class NativeWebDOMObservation:
    def __init__(self,send,read,clock_ms,guard,pid,*,ios=False,monotonic=time.monotonic,sleep=time.sleep):
        need(all(callable(v) for v in (send,read,clock_ms,guard,monotonic,sleep)) and integer(pid,1) and type(ios) is bool)
        self.send,self.original,self.clock_ms,self.guard,self.pid=send,read,clock_ms,guard,pid
        self.ios,self.monotonic,self.sleep=ios,monotonic,sleep
        self.last=None

    def read(self,run,surface,fixture_url):
        try:
            request=dict(schemaVersion=1,commandId=('ios-' if self.ios else '')+uuid.uuid4().hex,
                         action='feature-web-dom-observe',runId=run,surface=surface,fixtureUrl=fixture_url)
            command(request,ios=self.ios);need(self.guard() is not False)
            started=previous=self.monotonic();need(number(started,0,1e15));self.send(request)
            latest=None
            for attempt in range(51):
                need(self.guard() is not False);raw=self.original()
                try:value=decode(raw) if raw else None
                except json.JSONDecodeError:value=None
                if type(value) is dict and value.get('commandId')==request['commandId']:
                    validate(value,request,self.pid,self.clock_ms());need(value['status']!='unavailable')
                    if latest is not None:
                        need(value['instance']==latest['instance'] and value['sequence']>=latest['sequence']
                             and value['capturedEpochMs']>=latest['capturedEpochMs']
                             and (value['sequence']!=latest['sequence'] or value==latest))
                    latest=deepcopy(value)
                    if value['status']=='ready':
                        if self.last is not None:
                            old=self.last;old_source=old['source'];new_source=value['source']
                            need(value['instance']==old['instance'] and value['sequence']>old['sequence']
                                 and value['capturedEpochMs']>=old['capturedEpochMs'] and value['runId']==old['runId']
                                 and value['surface']==old['surface'] and new_source['nativeView']==old_source['nativeView']
                                 and new_source['dom']['instance']==old_source['dom']['instance']
                                 and new_source['dom']['sequence']>old_source['dom']['sequence']
                                 and new_source['dom']['capturedEpochMs']>=old_source['dom']['capturedEpochMs']
                                 and new_source['dom']['document']==old_source['dom']['document'])
                            for key in ('attempts','echoes'):
                                need(new_source['dom'][key][:len(old_source['dom'][key])]==old_source['dom'][key])
                        now=self.monotonic();need(number(now,0,1e15) and previous<=now and now-started<5 and self.guard() is not False)
                        self.last=deepcopy(value);return value
                now=self.monotonic();need(number(now,0,1e15) and previous<=now);previous=now
                if now-started>=5 or attempt==50:break
                self.sleep(min(.1,5-(now-started)))
        except Exception:raise NativeUIError('Original native browser DOM observation failed') from None
        raise NativeUIError('Original native browser DOM observation failed')
