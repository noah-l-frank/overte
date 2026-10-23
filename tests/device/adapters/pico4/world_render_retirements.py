"""One fresh read-only window over original retired capture inventories.

This warm reader is not a durable retirement owner. Its caller must retain the
original proofs and any uncertain query before allowing archive or host close.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import math
import time
import uuid

from adapters.graphics_journey.samples import retirement
from adapters.native_feature_observation import decode,exact,fresh,integer,need,number
from adapters.normal_ui import NativeUIError
from adapters.script_journey.history import canonical
from adapters.script_journey.lock import ScriptSourceLock
from feature_journeys.contract import identifier

VERSION=1
ACTION='feature-pico-world-render-retirements'
FILE='feature-pico-world-render-retirements.json'


def command(value):
    exact(value,{'schemaVersion','commandId','action','runId','captures'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['action']==ACTION
        and type(value['captures']) is list and 0<len(value['captures'])<=256)
    identifier(value['commandId']);identifier(value['runId'])
    requests=set();receipts=set()
    for row in value['captures']:
        exact(row,{'requestId','receiptIds'});identifier(row['requestId'])
        need(row['requestId'] not in requests and type(row['receiptIds']) is list and 0<len(row['receiptIds'])<=1024)
        requests.add(row['requestId'])
        for nonce in row['receiptIds']:
            identifier(nonce);need(nonce not in receipts);receipts.add(nonce)
    need(len(receipts)<=1024 and len(canonical(value))<=49152)
    return value


class PicoWorldRenderRetirements:
    def __init__(self,send,read,clock_ms,guard,pid,binding,lock,run,proofs,*,monotonic=time.monotonic,sleep=time.sleep):
        need(all(callable(value) for value in (send,read,clock_ms,guard,monotonic,sleep))
            and integer(pid,1) and isinstance(lock,ScriptSourceLock)
            and type(proofs) is list and 0<len(proofs)<=256)
        identifier(run);lock.assert_held()
        self.send,self.original,self.clock_ms,self.guard,self.pid=send,read,clock_ms,guard,pid
        self.binding,self.lock,self.run=deepcopy(binding),lock,run
        self.proofs=deepcopy(proofs);self.monotonic,self.sleep=monotonic,sleep
        self.instance=self.proofs[0]['memory']['instance']
        for proof in self.proofs:
            retirement(proof,proof['owner'],pid,binding,proof['owner']['role'])
            need(proof['memory']['instance']==self.instance)
        self.manifest=[dict(requestId=proof['owner']['capture']['commandId'],
            receiptIds=deepcopy(proof['owner']['receipts'])) for proof in self.proofs]
        command(dict(schemaVersion=1,commandId=uuid.uuid4().hex,action=ACTION,runId=run,captures=self.manifest))
        self.admitted=canonical(dict(binding=self.binding,proofs=self.proofs,manifest=self.manifest,
            instance=self.instance,pid=pid,run=run));self._sealed_admitted=self.admitted
        self.sequence=0;self.floor=max(proof['files']['absent']['sequence'] for proof in self.proofs)
        self.captured=0;self.pending=None;self.failed=False;self.last_raw=self.last_sha256=None
        self.queries=set();self.inventory_queries={proof['files'][key]['commandId']
            for proof in self.proofs for key in ('removed','absent')}

    def intact(self):
        self.lock.assert_held()
        need(self.admitted is self._sealed_admitted and canonical(dict(binding=self.binding,proofs=self.proofs,
            manifest=self.manifest,instance=self.instance,pid=self.pid,run=self.run))==self.admitted
            and self.guard() is not False)

    def clocks(self,started,requested,epochs):
        measured=self.monotonic();epoch=self.clock_ms();ended=self.monotonic()
        need(number(measured,started,started+1.5) and number(ended,measured,started+1.5)
            and ended-started<1.5 and integer(epoch,requested))
        for captured in epochs:
            fresh(captured,epoch)
            need(captured>=requested and max(epoch-captured,
                epoch-captured+math.ceil((ended-measured)*1000),
                requested-captured+math.ceil((ended-started)*1000))<1500)

    def validate(self,value,request,requested):
        exact(value,{'worldRenderRetirementsVersion','requestId','runId','instance','sequence','processId',
            'requestedEpochMs','capturedEpochMs','captures'})
        need(type(value['worldRenderRetirementsVersion']) is int and value['worldRenderRetirementsVersion']==VERSION
            and value['requestId']==request['commandId'] and value['runId']==self.run
            and value['instance']==self.instance and integer(value['sequence'],self.sequence+1)
            and integer(value['processId'],1) and value['processId']==self.pid
            and integer(value['requestedEpochMs'],max(requested,self.captured))
            and integer(value['capturedEpochMs'],value['requestedEpochMs'])
            and value['capturedEpochMs']-value['requestedEpochMs']<1500
            and type(value['captures']) is list and len(value['captures'])==len(self.proofs))
        previous=self.floor;queries=set();epochs=[value['requestedEpochMs'],value['capturedEpochMs']]
        for proof,packet in zip(self.proofs,value['captures']):
            updated=deepcopy(proof);updated['files']['absent']=deepcopy(packet)
            retirement(updated,proof['owner'],self.pid,self.binding,proof['owner']['role'])
            need(packet['sequence']>previous and packet['commandId'] not in self.inventory_queries|queries
                and packet['commandId']!=request['commandId']
                and value['requestedEpochMs']<=packet['capturedEpochMs']<=value['capturedEpochMs'])
            need({row['receiptId']:row['issued'] for row in packet['source']['receipts']}
                =={row['receiptId']:row['issued'] for row in proof['files']['absent']['source']['receipts']})
            queries.add(packet['commandId']);previous=packet['sequence'];epochs.append(packet['capturedEpochMs'])
        return previous,queries,epochs

    def read(self):
        need(not self.failed and self.pending is None and len(self.queries)<4096)
        try:
            with self.lock.held():
                self.intact();started=self.monotonic();need(number(started,0,1e15))
                requested=self.clock_ms();need(integer(requested,1))
                request=command(dict(schemaVersion=1,commandId=uuid.uuid4().hex,action=ACTION,
                    runId=self.run,captures=deepcopy(self.manifest)))
                need(request['commandId'] not in self.queries);self.pending=deepcopy(request)
                request_raw=canonical(request);self.send(deepcopy(request))
                for attempt in range(51):
                    self.intact();need(canonical(self.pending)==request_raw);raw=self.original()
                    need(type(raw) is str and len(raw.encode('utf-8'))<=200000)
                    try:value=decode(raw) if raw else None
                    except json.JSONDecodeError:value=None
                    if type(value) is dict and value.get('requestId')==request['commandId']:
                        floor,queries,epochs=self.validate(value,request,requested)
                        result=deepcopy(value);encoded=raw.encode('utf-8');sha=hashlib.sha256(encoded).hexdigest()
                        next_queries=self.queries|{request['commandId']};next_inventory=self.inventory_queries|queries
                        self.intact();self.clocks(started,requested,epochs);break
                    self.clocks(started,requested,[requested])
                    need(attempt<50);self.sleep(.02)
            # Include the actual source-lock exit; a ready-looking packet alone
            # never permits a retry following an uncertain context-manager exit.
            self.clocks(started,requested,epochs)
            self.sequence,self.captured,self.floor=value['sequence'],value['capturedEpochMs'],floor
            self.queries,self.inventory_queries=next_queries,next_inventory
            self.last_raw,self.last_sha256=encoded,sha;self.pending=None
            return result
        except Exception:
            self.failed=True
            raise NativeUIError('Original historical capture inventories are unavailable; query ownership is retained') from None
