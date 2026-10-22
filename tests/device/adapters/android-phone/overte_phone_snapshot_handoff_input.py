"""One ordinary Save/Share input admitted before an original OS handoff.

Delivery has a durable one-send boundary and reads only the unchanged original
Qt input receipt afterwards. A receipt never proves Save, Share or file effects.
The normal foreground-only writer and every other control remain unchanged.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import re
import time

from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.normal_ui import NativeUIError
from overte_phone_snapshot_controls import validate,original_path
from overte_phone_snapshot_handoff import binding as handoff_binding
from overte_phone_script_files import nonce


def plan(value,pid,epoch):
    exact(value,{'request','original'});request=value['request'];original=value['original']
    exact(request,{'schemaVersion','commandId','action','instance','generation','sequence','observedElapsedMs','controlId','controlToken'})
    need(type(request['schemaVersion']) is int and request['schemaVersion']==1 and request['action']=='activate'
        and all(nonce(request[key]) for key in ('commandId','instance','generation','controlToken'))
        and type(request['controlId']) is str and re.fullmatch(r'snapshot\.(?:save|share)\.[0-9a-f]{64}',request['controlId'])
        and integer(request['sequence'],1) and integer(request['observedElapsedMs']))
    validate(original,original['commandId'],pid,epoch)
    rows=[row for row in original['controls'] if row['id']==request['controlId']]
    need(original['ready'] and len(rows)==1);row=rows[0]
    need(row['enabled'] and row['inputReady'] and original_path(row['path'])
        and hashlib.sha256(row['path'].encode()).hexdigest()==request['controlId'].rsplit('.',1)[1]
        and row['token']==request['controlToken'] and original['instance']==request['instance']
        and original['generation']==request['generation'] and original['lastCommandSequence']+1==request['sequence']
        and original['elapsedMs']==request['observedElapsedMs'])
    return value


def admission(value,pid,owner,epoch):
    plan(value,pid,epoch)
    need(integer(epoch,owner['startedEpochMs']) and epoch<owner['deadlineEpochMs'])


def receipt(value,request,pid):
    exact(value,{'schemaVersion','commandId','action','performed','instance','generation','sequence','processId'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['performed'] is True
        and type(value['processId']) is int and value['processId']==pid and integer(value['sequence'],1)
        and all(value[key]==request[key] for key in ('commandId','action','instance','generation','sequence')))
    return value


class SnapshotHandoffInput:
    def __init__(self,send,read,clock_ms,foreground_guard,system_guard,pid,owner,admit,*,monotonic=time.monotonic,sleep=time.sleep):
        handoff_binding(owner)
        need(integer(pid,1) and owner['processId']==pid
            and all(callable(fn) for fn in (send,read,clock_ms,foreground_guard,system_guard,admit,monotonic,sleep)))
        self.send,self.read,self.clock_ms,self.foreground_guard,self.system_guard=send,read,clock_ms,foreground_guard,system_guard
        self.pid,self.owner,self.admit=pid,deepcopy(owner),admit
        self.monotonic,self.sleep,self.issued=monotonic,sleep,False

    def deliver(self,value):
        try:
            need(not self.issued and self.foreground_guard() is not False)
            started=previous=self.monotonic();need(number(started,0,1e15))
            epoch=self.clock_ms();admission(value,self.pid,self.owner,epoch)
            request=deepcopy(value['request'])
            # Persist an issued intent BEFORE the sole write. An uncertain write
            # is recovered through originals, never a second click.
            need(self.admit(deepcopy(value),deepcopy(self.owner)) is True)
            self.issued=True
            need(self.foreground_guard() is not False)
            now=self.monotonic();need(number(now,previous,1e15) and now-started<5);previous=now
            admission(value,self.pid,self.owner,self.clock_ms())
            self.send(dict(schemaVersion=1,commandId=request['commandId'],action='phone-snapshot-ui',request=request),deepcopy(value))
            return self._receipt(request,started,previous,epoch)
        except Exception:raise NativeUIError('Original Snapshot OS handoff input delivery is unavailable or uncertain') from None

    def observe(self,value):
        """Recover only the archived exact receipt; never admit or send again."""
        try:
            need(self.system_guard() is not False)
            plan(value,self.pid,value['original']['capturedEpochMs'])
            started=self.monotonic();need(number(started,0,1e15))
            epoch=self.clock_ms();need(integer(epoch,self.owner['startedEpochMs']) and epoch<self.owner['deadlineEpochMs'])
            return self._receipt(value['request'],started,started,epoch)
        except Exception:raise NativeUIError('Original Snapshot OS handoff receipt recovery failed') from None

    def _receipt(self,request,started,previous,epoch):
        for attempt in range(51):
            need(self.system_guard() is not False)
            raw=self.read();need(type(raw) is str and len(raw.encode())<=65536)
            try:actual=decode(raw) if raw else None
            except json.JSONDecodeError:actual=None
            need(self.system_guard() is not False)
            now=self.monotonic();need(number(now,previous,1e15) and now-started<5);previous=now
            current=self.clock_ms();need(integer(current,epoch) and current<self.owner['deadlineEpochMs'])
            if type(actual) is dict and actual.get('commandId')==request['commandId']:
                receipt(actual,request,self.pid);need(self.system_guard() is not False)
                final_epoch=self.clock_ms();need(integer(final_epoch,current) and final_epoch<self.owner['deadlineEpochMs'])
                now=self.monotonic();need(number(now,previous,1e15) and now-started<5)
                return deepcopy(actual)
            if attempt<50:self.sleep(.1)
        raise NativeUIError('Original Snapshot OS handoff input receipt is unavailable')
