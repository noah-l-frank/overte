"""Private existing fixture control; receipts never establish native readiness."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import math
import re
import time
import uuid
from urllib.parse import urlsplit
from urllib.request import Request,HTTPRedirectHandler,ProxyHandler,build_opener
from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.normal_ui import NativeUIError
from fixture.messages_mixer import MessagesMixerObservation,valid_control_command

VERSION=2


def validate(value,epoch):
    need(type(value) is dict and type(value.get('mixerControlVersion')) is int and value['mixerControlVersion'] in (1,2))
    exact(value,{'mixerControlVersion','instance','sequence','capturedEpochMs','domainId','stackGeneration','processes','mixer','mixerIdentity'}
        | ({'runId','offlineFenced','commands'} if value['mixerControlVersion']==2 else set()))
    need(type(value['mixerControlVersion']) is int
        and type(value['instance']) is str and re.fullmatch('[0-9a-f]{32}',value['instance'])
        and integer(value['sequence'],1) and integer(value['stackGeneration'],1)
        and type(value['domainId']) is str and str(uuid.UUID(value['domainId']))==value['domainId'] and uuid.UUID(value['domainId']).int)
    fresh(value['capturedEpochMs'],epoch);exact(value['processes'],MessagesMixerObservation.ROLES)
    need(all(type(row) is str and re.fullmatch('[0-9a-f]{64}',row) for row in value['processes'].values())
        and len(set(value['processes'].values()))==len(value['processes']))
    mixer=value['mixer'];exact(mixer,{'mixerProcessVersion','running','generation','pending'})
    need(type(mixer['mixerProcessVersion']) is int and mixer['mixerProcessVersion']==1 and integer(mixer['generation'],1)
        and type(mixer['running']) is bool and type(mixer['pending']) is bool)
    need(type(value['mixerIdentity']) is str and re.fullmatch('[0-9a-f]{64}',value['mixerIdentity'])
        if mixer['running'] else value['mixerIdentity'] is None)
    if value['mixerControlVersion']==2:
        need(value['runId'] is None or type(value['runId']) is str and re.fullmatch('[0-9a-f]{32}',value['runId']))
        rows=value['commands'];need(type(rows) is list and len(rows)<=2 and type(value['offlineFenced']) is bool)
        for index,row in enumerate(rows):
            exact(row,{'commandId','action','observedGeneration','admittedEpochMs','completedEpochMs','status'})
            need(type(row['commandId']) is str and re.fullmatch('[0-9a-f]{32}',row['commandId'])
                and row['action'] in ('offline','online') and integer(row['observedGeneration'],1)
                and row['observedGeneration']<=mixer['generation']
                and row['status'] in ('pending','completed','failed') and integer(row['admittedEpochMs'],1)
                and row['admittedEpochMs']<=value['capturedEpochMs'])
            need(row['completedEpochMs'] is None if row['status']=='pending' else
                integer(row['completedEpochMs'],row['admittedEpochMs'],value['capturedEpochMs']))
            if index:
                need(rows[index-1]['status']!='pending' and row['admittedEpochMs']>=rows[index-1]['completedEpochMs']
                    and rows[index-1]['action']=='offline' and row['action']=='online')
        need(len({row['commandId'] for row in rows})==len(rows) and bool(rows)==(value['runId'] is not None)
            and value['offlineFenced']==any(row['action']=='online' for row in rows))
    return value


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise NativeUIError('Private Chat mixer redirect refused')


class FixtureMixerControl:
    def __init__(self,url,token,guard,*,readonly=False,clock_ms=lambda:int(time.time()*1000),monotonic=time.monotonic,opener=None):
        need(type(url) is str and len(url)<=256 and type(token) is str and re.fullmatch('[A-Za-z0-9_-]{40,128}',token)
            and type(readonly) is bool and callable(guard) and callable(clock_ms) and callable(monotonic))
        parsed=urlsplit(url)
        need(parsed.scheme=='http' and parsed.hostname=='127.0.0.1' and parsed.port is not None
            and 1<=parsed.port<=65535 and parsed.path=='/v1/messages-mixer-state' and not parsed.query and not parsed.fragment
            and not parsed.username and not parsed.password and parsed.geturl()==url
            and url=='http://127.0.0.1:'+str(parsed.port)+'/v1/messages-mixer-state')
        self.url,self._token,self.guard,self.readonly=url,token,guard,readonly
        self.clock_ms,self.monotonic=clock_ms,monotonic;self.previous=None
        self.identity=hashlib.sha256(url.encode('ascii')).hexdigest()
        self._opener=opener if opener is not None else build_opener(ProxyHandler({}),NoRedirect())

    def accept(self,value):
        if self.previous is not None:
            old=self.previous
            need(value['mixerControlVersion']>=old['mixerControlVersion']
                and all(value[key]==old[key] for key in ('instance','domainId','stackGeneration','processes'))
                and value['sequence']>old['sequence'] and value['capturedEpochMs']>=old['capturedEpochMs']
                and value['mixer']['generation']>=old['mixer']['generation'])
            if value['mixer']['generation']==old['mixer']['generation']:
                need(value['mixer']['running']==old['mixer']['running'] and value['mixerIdentity']==old['mixerIdentity'])
            if old['mixerControlVersion']==2:
                need(old['runId'] is None or value['runId']==old['runId'])
                need(not old['offlineFenced'] or value['offlineFenced'])
                need(len(value['commands'])>=len(old['commands']))
                for before,after in zip(old['commands'],value['commands']):
                    need(all(before[key]==after[key] for key in ('commandId','action','observedGeneration','admittedEpochMs')))
                    if before['status']!='pending':need(before==after)
        self.previous=deepcopy(value)

    def _request(self,command):
        try:
            need(self.guard() is not False and (command is None or valid_control_command(command) and not self.readonly))
            started=self.monotonic();need(number(started,0,1e15));requested=self.clock_ms();need(integer(requested,1))
            request=Request(self.url,data=None if command is None else json.dumps(command,separators=(',',':')).encode('ascii'),
                headers={'X-Overte-E2E-Token':self._token,'Content-Type':'application/json'},method='GET' if command is None else 'POST')
            with self._opener.open(request,timeout=1.5 if command is None else 10) as response:
                need(response.status==200 and response.geturl()==self.url)
                raw=response.read(8193);need(type(raw) is bytes and 0<len(raw)<=8192)
            value=decode(raw.decode('utf-8'));epoch_started=self.monotonic();epoch=self.clock_ms();need(integer(epoch,requested))
            validate(value,epoch);need(value['capturedEpochMs']>=requested and self.guard() is not False)
            guarded=self.monotonic();need(number(guarded,epoch_started,started+(1.5 if command is None else 10)))
            final_epoch=self.clock_ms();need(integer(final_epoch,epoch))
            finished=self.monotonic();need(number(finished,guarded,started+(1.5 if command is None else 10))
                and max(final_epoch-value['capturedEpochMs'],epoch-value['capturedEpochMs']+math.ceil((finished-epoch_started)*1000))<=1500)
            return value
        except Exception:
            raise NativeUIError('Original private Chat mixer source/control is unavailable') from None

    def state(self):
        value=self._request(None);self.accept(value);return value

    def command(self,command):
        # A single ordinary fixture command. The owner must journal first and
        # independently GET afterwards; this response cannot prove readiness.
        need(valid_control_command(command));return self._request(command)
