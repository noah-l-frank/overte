"""Exclusive native account-origin fixture ownership; no product endpoint setter."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from copy import deepcopy
import hashlib
import json
import re
import time
from urllib.parse import urlsplit
import uuid
from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.normal_ui import NativeUIError

VERSION=1
FILE='feature-account-origin-result.json'
HEX='[0-9a-f]{32}'
EMPTY=hashlib.sha256(b'').hexdigest()


def origin_text(value):
    need(type(value) is str and 0<len(value)<=1024 and value.isascii() and value.startswith('https://')
         and not any(ord(c)<33 or ord(c)==127 for c in value))
    try:
        parsed=urlsplit(value);port=parsed.port
        need(parsed.scheme=='https' and bool(parsed.hostname) and not parsed.path and not parsed.query and not parsed.fragment
             and not parsed.username and not parsed.password and '@' not in parsed.netloc
             and parsed.netloc==parsed.netloc.lower() and not parsed.netloc.endswith(':') and (port is None or 1<=port<=65535)
             and parsed.geturl()==value and '?' not in value and '#' not in value)
    except (ValueError,UnicodeError):raise NativeUIError('Native account origin is not a closed HTTPS origin') from None
    return value


def original_document(run,origin):
    need(type(run) is str and re.fullmatch(HEX,run))
    return (json.dumps(dict(schemaVersion=1,runId=run,origin=origin_text(origin)),sort_keys=True,separators=(',',':'))+'\n').encode()


def command(value,*,ios=False):
    need(type(value) is dict and type(ios) is bool)
    exact(value,{'schemaVersion','commandId','action','operation','runId','ownerToken','instance'}
          | ({'origin'} if value.get('operation')=='stage' else set()))
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['action']=='feature-account-origin'
         and value['operation'] in ('stage','observe','release')
         and type(value['commandId']) is str and re.fullmatch(('ios-' if ios else '')+HEX,value['commandId'])
         and all(type(value[key]) is str and re.fullmatch(HEX,value[key]) for key in ('runId','instance'))
         and type(value['ownerToken']) is str and re.fullmatch('[0-9a-f]{64}',value['ownerToken']))
    if value['operation']=='stage':origin_text(value['origin'])
    return value


def validate(value,request,pid,epoch):
    command(request,ios=request['commandId'].startswith('ios-'))
    exact(value,{'originVersion','commandId','instance','runId','operation','processId','sequence',
                 'requestedEpochMs','capturedEpochMs','source'})
    need(type(value['originVersion']) is int and value['originVersion']==VERSION
         and all(value[key]==request[key] for key in ('commandId','instance','runId','operation'))
         and integer(pid,1) and integer(value['processId'],1) and value['processId']==pid and integer(value['sequence'],1)
         and integer(value['requestedEpochMs'],1) and integer(value['capturedEpochMs'],1)
         and 0<=value['capturedEpochMs']-value['requestedEpochMs']<5000)
    fresh(value['capturedEpochMs'],epoch);source=value['source']
    if request['operation']!='observe':exact(source,{'performed'});need(source['performed'] is True)
    else:
        exact(source,{'originExists','ownerExists','originBytes','originSha256','originBase64','ownerBytes','ownerSha256','retired'})
        need(all(type(source[key]) is bool for key in ('originExists','ownerExists','retired'))
             and all(integer(source[key],0,4096) for key in ('originBytes','ownerBytes'))
             and all(type(source[key]) is str and re.fullmatch('[0-9a-f]{64}',source[key]) for key in ('originSha256','ownerSha256'))
             and type(source['originBase64']) is str and len(source['originBase64'])<=5464
             and (not source['originExists'] or source['ownerExists']))
        raw=base64.b64decode(source['originBase64'],validate=True)
        need(base64.b64encode(raw).decode()==source['originBase64'] and len(raw)==source['originBytes']
             and hashlib.sha256(raw).hexdigest()==source['originSha256']
             and source['originExists']==bool(raw) and source['ownerExists']==bool(source['ownerBytes'])
             and (source['ownerSha256']!=EMPTY if source['ownerExists'] else source['ownerSha256']==EMPTY))
        if raw:
            observed=decode(raw.decode());exact(observed,{'schemaVersion','runId','origin'})
            need(type(observed['schemaVersion']) is int and observed['schemaVersion']==1 and observed['runId']==request['runId']
                 and original_document(observed['runId'],observed['origin'])==raw)
    return value


class NativeAccountOrigin:
    def __init__(self,send,read,clock_ms,guard,pid,instance,*,ios=False,monotonic=time.monotonic,sleep=time.sleep):
        need(all(callable(v) for v in (send,read,clock_ms,guard,monotonic,sleep)) and integer(pid,1)
             and type(instance) is str and re.fullmatch(HEX,instance) and type(ios) is bool)
        self.send,self.original,self.clock_ms,self.guard,self.pid,self.instance=send,read,clock_ms,guard,pid,instance
        self.ios,self.monotonic,self.sleep=ios,monotonic,sleep;self.sequence=0;self.captured=0

    def request(self,owned,operation):
        try:
            exact(owned,{'runId','ownerToken','origin'})
            value=dict(schemaVersion=1,commandId=('ios-' if self.ios else '')+uuid.uuid4().hex,action='feature-account-origin',
                       operation=operation,runId=owned['runId'],ownerToken=owned['ownerToken'],instance=self.instance)
            if operation=='stage':value['origin']=owned['origin']
            command(value,ios=self.ios);need(self.guard() is not False)
            started=previous=self.monotonic();need(number(started,0,1e15));requested=self.clock_ms();need(integer(requested,1))
            self.send(value) # One dispatch, including uncertain stage/release. Poll only original bytes.
            for attempt in range(51):
                need(self.guard() is not False);raw=self.original()
                try:response=decode(raw) if raw else None
                except json.JSONDecodeError:response=None
                if type(response) is dict and response.get('commandId')==value['commandId']:
                    epoch=response.get('capturedEpochMs') if self.ios else self.clock_ms()
                    response=validate(response,value,self.pid,epoch)
                    need(response['sequence']>self.sequence and response['requestedEpochMs']>=self.captured
                         and (self.ios or response['requestedEpochMs']>=requested)
                         and self.guard() is not False)
                    now=self.monotonic();need(number(now,0,1e15) and previous<=now and now-started<5)
                    self.sequence=response['sequence'];self.captured=response['capturedEpochMs'];return response
                now=self.monotonic();need(number(now,0,1e15) and previous<=now);previous=now
                if now-started>=5 or attempt==50:break
                self.sleep(.1)
        except Exception:raise NativeUIError('Native account origin operation failed') from None
        raise NativeUIError('Native account origin result is unavailable')


class OwnedAccountOrigin:
    def __init__(self,source,store,binding,*,component_only=False):
        from adapters.normal_feature_state import context
        need(type(component_only) is bool)
        self.source,self.store,self.component_only=source,store,component_only
        self.binding=deepcopy(context(binding,component_only=component_only))

    def owned(self):
        from adapters.normal_feature_state import context
        need(self.source.guard() is not False)
        value=self.store.read();exact(value,{'ownershipVersion','binding','instance','data'})
        need(type(value['ownershipVersion']) is int and value['ownershipVersion']==1
             and context(value['binding'],component_only=self.component_only)==self.binding and value['instance']==self.source.instance)
        exact(value['data'],{'runId','ownerToken','origin'})
        original_document(value['data']['runId'],value['data']['origin'])
        need(type(value['data']['ownerToken']) is str and re.fullmatch('[0-9a-f]{64}',value['data']['ownerToken']))
        return value

    def stage(self,run,origin):
        import secrets
        original=original_document(run,origin)
        need(self.source.guard() is not False and self.store.read() is None)
        value=dict(ownershipVersion=1,binding=self.binding,instance=self.source.instance,
                   data=dict(runId=run,ownerToken=secrets.token_hex(32),origin=origin))
        self.store.write(value,None) # Durable intent before any native file is created.
        self.source.request(value['data'],'stage')
        observed=self.source.request(value['data'],'observe')['source']
        measured=base64.b64decode(observed['originBase64'],validate=True)
        need(observed['originExists'] and observed['ownerExists'] and not observed['retired'] and measured==original)
        return decode(measured.decode())['origin'] # Return the independently read bytes, never the input value.

    def release(self):
        value=self.owned();self.source.request(value['data'],'release')
        observed=self.source.request(value['data'],'observe')['source']
        need(observed['retired'] and not observed['originExists'] and not observed['ownerExists']
             and observed['originBytes']==observed['ownerBytes']==0 and self.source.guard() is not False)
        self.store.discard(value)
