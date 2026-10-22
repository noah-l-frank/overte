"""Original shutdown-drained and actual worker-exit ledger, never stop ACKs."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import re
import uuid
from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.native_script_membership import validate as membership
from adapters.native_script_observation import validate_code
from adapters.native_script_roots import NativeScriptRoots
from adapters.normal_ui import NativeUIError

VERSION=1
ACTION='feature-script-terminal-observe'
FILE='feature-script-terminal.json'
LIMIT=1048576


def identity(value):return type(value) is str and re.fullmatch('[0-9a-f]{32}',value) is not None


def command(value,*,ios=False):
    exact(value,{'schemaVersion','commandId','action'})
    need(type(ios) is bool and type(value['schemaVersion']) is int and value['schemaVersion']==1
        and value['action']==ACTION and type(value['commandId']) is str
        and re.fullmatch(('ios-' if ios else '')+'[0-9a-f]{32}',value['commandId']))
    return value


def history(value,epoch,pid):
    exact(value,{'scriptTerminalVersion','instance','processId','complete','eventSequence','events'})
    need(type(value['scriptTerminalVersion']) is int and value['scriptTerminalVersion']==VERSION
        and identity(value['instance']) and type(value['processId']) is int and value['processId']==pid
        and value['complete'] is True and integer(value['eventSequence'],0,512)
        and type(value['events']) is list and len(value['events'])==value['eventSequence'])
    threads={};managers=set();last_epoch=0;last_mono=0
    for index,row in enumerate(value['events']):
        exact(row,{'eventSequence','capturedEpochMs','monotonicMs','kind','threadInstance','manager','code','work'})
        need(type(row['eventSequence']) is int and row['eventSequence']==index+1
            and integer(row['capturedEpochMs'],max(1,last_epoch),epoch) and integer(row['monotonicMs'],last_mono)
            and row['kind'] in ('thread-bound','shutdown-drained','thread-finished') and identity(row['threadInstance']))
        membership(dict(complete=True,revision=1,managers=[row['manager']]),row['capturedEpochMs'])
        manager=row['manager'];need(manager['assigned']);thread=row['threadInstance']
        if row['kind']=='thread-bound':
            need(thread not in threads and manager['instance'] not in managers and row['code'] is None and row['work'] is None)
            threads[thread]=[row];managers.add(manager['instance'])
        else:
            need(thread in threads and row['manager']==threads[thread][0]['manager'])
            prior=threads[thread];validate_code(row['code'],row['capturedEpochMs'])
            need(not row['code']['submitted'] or manager['assignedEpochMs']<=row['code']['submittedEpochMs'])
            if row['kind']=='shutdown-drained':
                need(len(prior)==1);work=row['work'];exact(work,{'signalCallbacks','timerCallbacks','evaluating','timers'})
                need(all(type(work[key]) is int and work[key]==0 for key in ('signalCallbacks','timerCallbacks','timers'))
                    and work['evaluating'] is False)
            else:need(len(prior)==2 and row['code']==prior[1]['code'] and row['work'] is None)
            prior.append(row)
        last_epoch,last_mono=row['capturedEpochMs'],row['monotonicMs']
    return value


def accept(before,current):
    need(before['instance']==current['instance'] and before['processId']==current['processId']
        and current['eventSequence']>=before['eventSequence'] and current['events'][:len(before['events'])]==before['events'])
    return deepcopy(current)


def validate(value,request,pid,epoch,*,previous=None):
    command(request,ios=request['commandId'].startswith('ios-'))
    exact(value,{'scriptTerminalObservationVersion','commandId','instance','sequence','processId','requestedEpochMs','capturedEpochMs','source'})
    need(type(value['scriptTerminalObservationVersion']) is int and value['scriptTerminalObservationVersion']==VERSION
        and value['commandId']==request['commandId'] and identity(value['instance']) and integer(value['sequence'],1,1000000000)
        and integer(pid,1) and type(value['processId']) is int and value['processId']==pid
        and integer(value['requestedEpochMs'],1) and integer(value['capturedEpochMs'],value['requestedEpochMs'],value['requestedEpochMs']+1500))
    fresh(value['capturedEpochMs'],epoch);history(value['source'],value['capturedEpochMs'],pid)
    if previous is not None:
        validate(previous,dict(schemaVersion=1,commandId=previous['commandId'],action=ACTION),pid,previous['capturedEpochMs'])
        need(value['instance']==previous['instance'] and value['sequence']>previous['sequence']
            and value['commandId']!=previous['commandId'] and value['requestedEpochMs']>=previous['capturedEpochMs'])
        accept(previous['source'],value['source'])
    return value


def terminal(value,manager,code,*,after_sequence,after_epoch):
    """Both original terminal boundaries, pinned to independently read code."""
    validate(value,dict(schemaVersion=1,commandId=value['commandId'],action=ACTION),value['processId'],value['capturedEpochMs'])
    need(integer(after_sequence,1,value['source']['eventSequence']) and integer(after_epoch,1) and code['submitted'])
    rows=[row for row in value['source']['events'] if row['manager']['instance']==manager['instance']]
    need(len(rows)==3 and rows[0]['kind']=='thread-bound' and rows[1]['kind']=='shutdown-drained'
        and rows[2]['kind']=='thread-finished' and rows[0]['eventSequence']<=after_sequence
        and rows[1]['eventSequence']>after_sequence and rows[2]['eventSequence']>rows[1]['eventSequence']
        and all(row['manager']==manager for row in rows) and all(row['code']==code for row in rows[1:])
        and all(row['capturedEpochMs']>=after_epoch for row in rows[1:]))
    return deepcopy(rows)


class NativeScriptTerminal(NativeScriptRoots):
    def restore(self,original):
        need(self.last is None and type(original) is dict)
        query=dict(schemaVersion=1,commandId=original.get('commandId'),action=ACTION)
        command(query,ios=self.ios);validate(original,query,self.pid,original.get('capturedEpochMs'));self.last=deepcopy(original)

    def read(self,after_sequence):
        try:
            need(integer(after_sequence,0,1000000000) and (self.last is None or after_sequence>=self.last['sequence'])
                and self.guard() is not False)
            started=previous=self.monotonic();need(number(started,0,1e15));barrier=self.clock_ms();need(integer(barrier,1))
            query=dict(schemaVersion=1,commandId=('ios-' if self.ios else '')+uuid.uuid4().hex,action=ACTION)
            command(query,ios=self.ios);self.send(deepcopy(query))
            for attempt in range(51):
                need(self.guard() is not False);raw=self.original();need(type(raw) is str and len(raw.encode())<=LIMIT)
                try:value=decode(raw) if raw else None
                except json.JSONDecodeError:value=None
                now=self.monotonic();need(number(now,previous,1e15) and now-started<5);previous=now
                if type(value) is dict and value.get('commandId')==query['commandId']:
                    epoch=self.clock_ms();need(integer(epoch,barrier));validate(value,query,self.pid,epoch,previous=self.last)
                    need(value['sequence']>after_sequence and value['requestedEpochMs']>=barrier and self.guard() is not False)
                    final=self.monotonic();need(number(final,previous,1e15) and final-started<5
                        and max(epoch-value['capturedEpochMs'],barrier-value['capturedEpochMs']+(final-started)*1000)<=1500)
                    self.last=deepcopy(value);return deepcopy(value)
                if attempt<50:self.sleep(.1)
        except Exception:raise NativeUIError('Original Script terminal lifecycle is unavailable or invalid') from None
        raise NativeUIError('Original Script terminal lifecycle did not produce this request')
