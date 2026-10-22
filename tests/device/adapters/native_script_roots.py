"""Actual configured Script resource root, never inferred from engine URLs."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import math
import re
import time
import uuid
from urllib.parse import unquote,urlsplit,urlunsplit
from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.normal_ui import NativeUIError

VERSION=1
FILE='feature-script-roots.json'
LIMIT=16384


def command(value,*,ios=False):
    exact(value,{'schemaVersion','commandId','action'})
    need(type(ios) is bool and type(value['schemaVersion']) is int and value['schemaVersion']==1
        and value['action']=='feature-script-roots-observe' and type(value['commandId']) is str
        and re.fullmatch(('ios-' if ios else '')+'[0-9a-f]{32}',value['commandId']))
    return value


def root_url(value):
    need(type(value) is str and 1<=len(value)<=4096 and all(ord(char)>=32 and ord(char)!=127 for char in value))
    parsed=urlsplit(value);path=unquote(parsed.path,errors='strict')
    need(parsed.scheme in ('file','qrc') and not parsed.netloc and not parsed.query and not parsed.fragment
        and path==parsed.path and path.startswith('/') and '\\' not in path
        and not any(part in ('.','..') for part in path.split('/'))
        and path.rstrip('/').endswith('/scripts') and '//' not in path and not path.endswith('//'))
    path=path.rstrip('/')+'/'
    return 'qrc:'+path if parsed.scheme=='qrc' else urlunsplit(('file','',path,'',''))


def validate(value,request,pid,epoch,*,previous=None):
    need(type(request) is dict and type(request.get('commandId')) is str)
    command(request,ios=request['commandId'].startswith('ios-'))
    exact(value,{'scriptRootsVersion','commandId','instance','sequence','processId','requestedEpochMs','capturedEpochMs','source'})
    need(type(value['scriptRootsVersion']) is int and value['scriptRootsVersion']==VERSION
        and value['commandId']==request['commandId'] and integer(pid,1) and integer(value['processId'],1) and value['processId']==pid
        and type(value['instance']) is str and re.fullmatch('[0-9a-f]{32}',value['instance'])
        and integer(value['sequence'],1,1_000_000_000) and integer(value['requestedEpochMs'],1)
        and integer(value['capturedEpochMs'],1) and 0<=value['capturedEpochMs']-value['requestedEpochMs']<=1500)
    fresh(value['capturedEpochMs'],epoch)
    exact(value['source'],{'defaultScriptsUrl'});root_url(value['source']['defaultScriptsUrl'])
    if previous is not None:
        original=dict(schemaVersion=1,commandId=previous['commandId'],action='feature-script-roots-observe')
        validate(previous,original,pid,previous['capturedEpochMs'])
        need(value['instance']==previous['instance'] and value['sequence']>previous['sequence']
            and value['commandId']!=previous['commandId'] and value['capturedEpochMs']>=previous['capturedEpochMs']
            and value['source']==previous['source'])
    return value


class NativeScriptRoots:
    def __init__(self,send,original,clock_ms,guard,pid,*,ios=False,monotonic=time.monotonic,sleep=time.sleep):
        need(all(callable(fn) for fn in (send,original,clock_ms,guard,monotonic,sleep)) and integer(pid,1) and type(ios) is bool)
        self.send,self.original,self.clock_ms,self.guard,self.pid=send,original,clock_ms,guard,pid
        self.ios,self.monotonic,self.sleep=ios,monotonic,sleep;self.last=None

    def restore(self,original):
        need(self.last is None and type(original) is dict and 'commandId' in original and 'capturedEpochMs' in original)
        request=dict(schemaVersion=1,commandId=original['commandId'],action='feature-script-roots-observe')
        command(request,ios=self.ios);validate(original,request,self.pid,original['capturedEpochMs']);self.last=deepcopy(original)

    def read(self,after_sequence):
        try:
            need(integer(after_sequence,0,1_000_000_000) and (self.last is None or after_sequence>=self.last['sequence']) and self.guard() is not False)
            started=previous=self.monotonic();need(number(started,0,1e15))
            barrier=self.clock_ms();need(integer(barrier,1))
            request=dict(schemaVersion=1,commandId=('ios-' if self.ios else '')+uuid.uuid4().hex,action='feature-script-roots-observe')
            command(request,ios=self.ios);self.send(deepcopy(request))
            for attempt in range(51):
                need(self.guard() is not False)
                raw=self.original();need(type(raw) is str and len(raw.encode())<=LIMIT)
                try:value=decode(raw) if raw else None
                except json.JSONDecodeError:value=None
                now=self.monotonic();need(number(now,previous,1e15) and now-started<5 and self.guard() is not False);previous=now
                if type(value) is dict and value.get('commandId')==request['commandId']:
                    epoch=self.clock_ms();need(integer(epoch,barrier))
                    validate(value,request,self.pid,epoch,previous=self.last)
                    need(value['sequence']>after_sequence and value['requestedEpochMs']>=barrier and self.guard() is not False)
                    # Prepare both independent snapshots before the final
                    # actual guard/clocks. Copying cannot extend freshness or
                    # advance the accepted cursor on a failed acquisition.
                    candidate=deepcopy(value);result=deepcopy(value)
                    need(self.guard() is not False)
                    measured=self.monotonic();need(number(measured,previous,started+1.5))
                    final_epoch=self.clock_ms();need(integer(final_epoch,epoch))
                    fresh(value['capturedEpochMs'],final_epoch)
                    final=self.monotonic();need(number(final,measured,started+1.5))
                    need(max(final_epoch-value['capturedEpochMs'],
                        barrier-value['capturedEpochMs']+math.ceil((final-started)*1000),
                        final_epoch-value['capturedEpochMs']+math.ceil((final-measured)*1000))<=1500)
                    self.last=candidate;return result
                if attempt<50:self.sleep(.1)
        except Exception:raise NativeUIError('Original configured Script root is unavailable or invalid') from None
        raise NativeUIError('Original configured Script root did not produce this request')
