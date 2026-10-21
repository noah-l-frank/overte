"""Durable original-frame acquisition and real retained-consumer retirement.

The transcript retains uncertainty after a lost read/release. Reconstructing an
owner permits fresh cleanup inspection, never another acquisition of that ID.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import time
import uuid

from adapters.native_completed_frame import NativeCompletedFrame, command, validate, storage, absent
from adapters.native_feature_observation import exact, fresh, integer, need, number
from adapters.normal_feature_state import context
from adapters.normal_ui import NativeUIError
from adapters.script_feature.history import pack, unpack, same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier

VERSION=1


class CompletedFrameLease:
    def __init__(self,store,binding,run,role,factory,guard,*,source_lock=None,
                 monotonic=time.monotonic,sleep=time.sleep):
        self.store,self.binding,self.run,self.role=store,deepcopy(context(binding)),identifier(run),role
        need(role in ('primary','actor') and all(callable(fn) for fn in (factory,guard,monotonic,sleep)))
        self.factory,self.guard,self.monotonic,self.sleep=factory,guard,monotonic,sleep
        self.lock=source_lock or ScriptSourceLock(store.path.with_name('script-feature-sources.lock'))
        need(isinstance(self.lock,ScriptSourceLock) and self.lock.path==store.path.with_name('script-feature-sources.lock'))
        self.pid=int(binding['processIdentity']);need(self.pid>0)

    def _load(self):
        self.lock.assert_held();need(self.guard() is not False)
        self.state=self.store.read()
        if self.state is None:
            self.events=[];return
        exact(self.state,{'frameLeaseVersion','binding','runId','role','active','transcript'})
        need(type(self.state['frameLeaseVersion']) is int and self.state['frameLeaseVersion']==VERSION
             and same(self.state['binding'],self.binding) and self.state['runId']==self.run and self.state['role']==self.role)
        self.events=unpack(self.state['transcript']);seen=set();frames=set();reads=set();active=None;released=set();cursor=None
        for event in self.events:
            exact(event,{'command','packet'});query=command(event['command']);packet=event['packet']
            need(query['commandId'] not in seen);seen.add(query['commandId'])
            if query['operation']=='read':
                if active is None:
                    # Compatible complete legacy transcripts already bind an
                    # actual source birth. A lost legacy read without any birth
                    # cannot be adopted as cleanup proof in a new Context.
                    need(packet is not None);active=query['requestId']
                need(active==query['requestId'] and active not in reads and (cursor is not None or packet is not None));reads.add(active)
            else:
                if active is None and query['operation']=='inspect':active=query['requestId']
                need(active==query['requestId'])
                if query['operation']=='release':
                    need(active not in released);released.add(active)
            if packet is None:continue
            validator=validate if query['operation']=='read' else storage
            validator(packet,query,self.pid,packet.get('capturedEpochMs'))
            if query['operation']=='read':
                frame_id=packet['source']['renderTrace']['frameId']
                need(frame_id not in frames);frames.add(frame_id)
            if cursor is not None:
                need(packet['instance']==cursor['instance'] and packet['sequence']>cursor['sequence']
                     and packet['requestedEpochMs']>=cursor['capturedEpochMs'])
            cursor=packet
            if query['operation']!='read' and absent(packet):
                need(active in released);active=None
        need(self.state['active']==active)

    def _write(self,active):
        need(same(self.store.read(),self.state) and self.guard() is not False)
        value=dict(frameLeaseVersion=VERSION,binding=self.binding,runId=self.run,role=self.role,
                   active=active,transcript=pack(self.events))
        self.store.write(value,self.state);need(same(self.store.read(),value));self.state=deepcopy(value)

    def _perform(self,operation,request_id):
        started=self.monotonic();need(number(started,0,1e15))
        query=dict(schemaVersion=1,action='feature-completed-frame',commandId='ios-'+uuid.uuid4().hex,
                   requestId=request_id,operation=operation)
        def intent(actual):
            need(same(actual,query) and all(row['command']['commandId']!=actual['commandId'] for row in self.events))
            self.events.append(dict(command=deepcopy(actual),packet=None));self._write(request_id)
        reader=self.factory(intent);need(isinstance(reader,NativeCompletedFrame) and reader.pid==self.pid)
        for row in self.events:
            packet=row['packet']
            if packet is not None:
                reader.instance,reader.sequence,reader.epoch=packet['instance'],packet['sequence'],packet['capturedEpochMs']
        result=reader.perform(query)
        if operation=='read':
            frame_id=result['source']['renderTrace']['frameId']
            need(all(row['packet'] is None or row['command']['operation']!='read'
                     or row['packet']['source']['renderTrace']['frameId']!=frame_id for row in self.events))
        need(same(self.events[-1]['command'],query) and self.events[-1]['packet'] is None)
        self.events[-1]['packet']=deepcopy(result)
        drained=operation!='read' and absent(result)
        self._write(None if drained else request_id)
        epoch=reader.clock_ms();need(integer(epoch,result['capturedEpochMs']));fresh(result['capturedEpochMs'],epoch)
        ended=self.monotonic();need(number(ended,started,1e15) and ended-started<1.5 and self.guard() is not False)
        return result

    def capture(self):
        try:
            with self.lock.held():
                self._load();need(self.state is None or self.state['active'] is None)
                request_id='ios-'+uuid.uuid4().hex
                before=self._perform('inspect',request_id)['source']
                need(before==dict(retired=False,present=False,callbacks=0,gpuPending=False,metadataBytes=0))
                return self._perform('read',request_id)
        except Exception:
            raise NativeUIError('Completed frame acquisition failed; durable responsibility is retained') from None

    def drain(self):
        """Release once, then inspect fresh originals until all consumers drain.

        This is individual acquisition retirement, not the feature's final
        three-second quiet window. Immutable originals remain in the ledger.
        """
        try:
            started=previous=self.monotonic();need(number(started,0,1e15))
            with self.lock.held():
                self._load()
                if self.state is None or self.state['active'] is None:return None
                request_id=self.state['active']
                released=any(row['command']['requestId']==request_id and row['command']['operation']=='release' for row in self.events)
                if not released:
                    result=self._perform('release',request_id)
                    if absent(result):return result
                for attempt in range(81):
                    current=self.monotonic();need(number(current,previous,1e15) and current-started<20);previous=current
                    result=self._perform('inspect',request_id)
                    current=self.monotonic();need(number(current,previous,1e15) and current-started<20);previous=current
                    if absent(result):return result
                    if attempt<80:self.sleep(.25)
                need(False)
        except Exception:
            raise NativeUIError('Completed frame consumers remain unresolved; durable responsibility is retained') from None
