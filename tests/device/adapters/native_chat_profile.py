"""Original private native profile source and durable once-only restore intent."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import math
import re
import time
import uuid
from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.normal_ui import NativeUIError
from adapters.normal_feature_state import context
from adapters.independent_chat_receiver import binding_pid
from adapters.script_journey.history import pack,unpack,same
from adapters.script_journey.lock import ScriptSourceLock

VERSION=1
FILE='feature-chat-profile.json'
KEYS={'ArmoredChat-Messages','ArmoredChat-Config'}


def hex_value(value,length=32):
    return type(value) is str and re.fullmatch('[0-9a-f]{'+str(length)+'}',value) is not None


def command(value):
    exact(value,{'schemaVersion','commandId','runId','action','operation'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['action']=='feature-chat-profile'
        and hex_value(value['commandId']) and hex_value(value['runId']) and value['operation'] in ('acquire','inspect','restore'))
    return value


def fingerprints(value):
    exact(value,{'cache','worker','physical'})
    for source in ('cache','worker'):
        exact(value[source],KEYS);need(all(hex_value(row,64) for row in value[source].values()))
    exact(value['physical'],KEYS)
    for key,row in value['physical'].items():
        exact(row,{'present','sha256','empty'} if key=='ArmoredChat-Messages' else {'present','sha256'})
        need(type(row['present']) is bool and hex_value(row['sha256'],64))
        if key=='ArmoredChat-Messages':need(type(row['empty']) is bool)


def validate(value,request,pid,epoch):
    command(request)
    exact(value,{'chatProfileVersion','commandId','runId','instance','sequence','processId','capturedEpochMs',
        'owned','restoreAttempted','restored','original','current','settings','view'})
    need(type(value['chatProfileVersion']) is int and value['chatProfileVersion']==VERSION
        and all(value[key]==request[key] for key in ('commandId','runId')) and hex_value(value['instance'])
        and integer(value['sequence'],1) and integer(value['processId'],1) and value['processId']==pid
        and value['owned'] is True and type(value['restoreAttempted']) is bool and type(value['restored']) is bool
        and (not value['restored'] or value['restoreAttempted']))
    if request['operation']=='acquire':need(not value['restoreAttempted'] and not value['restored'])
    if request['operation']=='restore':need(value['restoreAttempted'])
    fingerprints(value['original']);fingerprints(value['current'])
    need(value['original']['cache']==value['original']['worker']
        and value['original']['physical']['ArmoredChat-Messages']['empty']
        and (not value['restored'] or value['current']==value['original']))
    exact(value['settings'],{'instance','writerInstance','mutationSequence','capturedEpochMs'})
    exact(value['view'],{'instance','sequence','capturedEpochMs'})
    need(all(hex_value(value['settings'][k]) for k in ('instance','writerInstance'))
        and integer(value['settings']['mutationSequence']) and hex_value(value['view']['instance']) and integer(value['view']['sequence'],1))
    for source in (value,value['settings'],value['view']):
        fresh(source['capturedEpochMs'],epoch);need(source['capturedEpochMs']<=value['capturedEpochMs'])
    return value


class NativeChatProfile:
    def __init__(self,send,read,clock_ms,guard,pid,*,monotonic=time.monotonic,sleep=time.sleep):
        need(all(callable(item) for item in (send,read,clock_ms,guard,monotonic,sleep)) and integer(pid,1))
        self.send,self.original,self.clock_ms,self.guard,self.pid=send,read,clock_ms,guard,pid
        self.monotonic,self.sleep=monotonic,sleep;self.last=None

    def accept(self,value):
        if self.last is not None:
            old=self.last
            need(value['runId']==old['runId'] and value['instance']==old['instance'] and value['sequence']>old['sequence']
                and value['capturedEpochMs']>=old['capturedEpochMs'] and value['original']==old['original']
                and (not old['restoreAttempted'] or value['restoreAttempted']))
            for key in ('instance','writerInstance'):need(value['settings'][key]==old['settings'][key])
            need(value['settings']['mutationSequence']>=old['settings']['mutationSequence']
                and value['settings']['capturedEpochMs']>=old['settings']['capturedEpochMs']
                and value['view']['instance']==old['view']['instance'] and value['view']['sequence']>old['view']['sequence']
                and value['view']['capturedEpochMs']>=old['view']['capturedEpochMs'])
        self.last=deepcopy(value)

    def perform(self,request):
        try:
            command(request);need(self.guard() is not False)
            started=previous=self.monotonic();need(number(started,0,1e15))
            requested=self.clock_ms();need(integer(requested,1));self.send(deepcopy(request))
            for attempt in range(31):
                need(self.guard() is not False);raw=self.original()
                if raw:
                    value=decode(raw)
                    if type(value) is dict and value.get('commandId')==request['commandId']:
                        epoch=self.clock_ms();need(integer(epoch,requested));validate(value,request,self.pid,epoch)
                        oldest=min(source['capturedEpochMs'] for source in (value,value['settings'],value['view']))
                        need(oldest>=requested and self.guard() is not False)
                        processing=self.monotonic();need(number(processing,previous,started+1.5))
                        final_epoch=self.clock_ms();need(integer(final_epoch,epoch));fresh(oldest,final_epoch)
                        need(self.guard() is not False)
                        now=self.monotonic();need(number(now,processing,started+1.5)
                            and max(final_epoch-oldest+math.ceil((now-processing)*1000),requested-oldest+math.ceil((now-started)*1000))<=1500)
                        self.accept(value);return value
                now=self.monotonic();need(number(now,previous,started+1.5));previous=now
                if now-started>=1.5 or attempt==30:break
                self.sleep(min(.05,1.5-(now-started)))
            need(False)
        except Exception:
            raise NativeUIError('Chat original profile source is unavailable; no input is repeated') from None


class OwnedChatProfile:
    """Persist admission before transport; pending acquire/restore is never resent."""
    def __init__(self,reader,store,binding,run,lock,*,component_only=False):
        need(isinstance(reader,NativeChatProfile) and hex_value(run) and isinstance(lock,ScriptSourceLock)
            and lock.path==store.path.with_name('script-sources.lock') and reader.last is None)
        self.reader,self.store,self.run,self.lock=reader,store,run,lock
        self.binding=deepcopy(context(binding,component_only=component_only));need(binding_pid(self.binding)==reader.pid)
        self.previous=store.read();self.attempts=[]
        self.base=dict(chatProfileOwnerVersion=VERSION,runId=run,binding=self.binding,transcript=pack([]))
        if self.previous is not None:
            exact(self.previous,set(self.base));need(all(same(self.previous[k],self.base[k]) for k in set(self.base)-{'transcript'}))
            attempts=unpack(self.previous['transcript']);seen=set()
            for index,row in enumerate(attempts):
                exact(row,{'request','result'});request=command(row['request'])
                need(request['runId']==run and request['commandId'] not in seen);seen.add(request['commandId'])
                self._allowed(request['operation'])
                if row['result'] is not None:
                    value=validate(row['result'],request,reader.pid,row['result']['capturedEpochMs']);reader.accept(value)
                    need(not value['restoreAttempted'] or any(old['request']['operation']=='restore' for old in attempts[:index+1]))
                self.attempts.append(deepcopy(row))

    def _allowed(self,operation):
        operations=[row['request']['operation'] for row in self.attempts]
        if operation=='acquire':need(not operations)
        else:need(operations and operations[0]=='acquire')
        if operation=='restore':need('restore' not in operations and self.reader.last is not None and not self.reader.last['restoreAttempted'])

    def write(self):
        need(same(self.store.read(),self.previous))
        value={**self.base,'transcript':pack(self.attempts)};self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value)

    def perform(self,operation):
        try:
            need(operation in ('acquire','inspect','restore') and len(self.attempts)<128)
            started=self.reader.monotonic();need(number(started,0,1e15))
            with self.lock.held():
                self._allowed(operation);need(self.reader.guard() is not False)
                request=command(dict(schemaVersion=1,commandId=uuid.uuid4().hex,runId=self.run,action='feature-chat-profile',operation=operation))
                self.attempts.append(dict(request=request,result=None));self.write()
                value=self.reader.perform(request)
                need(not value['restoreAttempted'] or any(row['request']['operation']=='restore' for row in self.attempts))
                self.attempts[-1]['result']=deepcopy(value);self.write()
                oldest=min(source['capturedEpochMs'] for source in (value,value['settings'],value['view']))
                epoch_started=self.reader.monotonic();need(number(epoch_started,started,started+1.5))
                epoch=self.reader.clock_ms();fresh(oldest,epoch);need(self.reader.guard() is not False)
                finished=self.reader.monotonic();need(number(finished,epoch_started,started+1.5)
                    and epoch-oldest+math.ceil((finished-epoch_started)*1000)<=1500)
                return value
        except Exception:
            raise NativeUIError('Chat profile ownership is unresolved; original intent is retained') from None
