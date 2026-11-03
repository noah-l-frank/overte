"""Passive Source4 role/range replay; no current observation or live adoption.

The existing generic raw reader supplies only actual literal-container bytes.
This reader binds them to the exact Source4 role, its original command and
phase bookends. It never dispatches, samples, creates a budget or renews one.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from pathlib import Path

from adapters.chat_journey.archive_file import ClosedOriginalFile
from adapters.chat_journey.source_chunks import ChatSourceChunks,json_digest
from adapters.native_fd_owner import OriginalDescriptor,require_directory
from adapters.native_feature_observation import exact,integer,need,number
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.pico4.audio_pc_originals import AudioPCRawOriginals
from adapters.pico4.emote_stream_frame import CONTROL_LIMIT,FRAME_LIMIT,control_reply,frame,continuity
from adapters.pico4.emote_stream_wire import wire_original,physical_stamp,strict_json
from adapters.script_journey.history import canonical,same
from feature_journeys.phase_fixture import validate as phase_packet
import os

VERSION=1
IDENTITY={'picoRemoteAvatarSourceVersion','area','role','runId','fixtureUrl','binding','subjectSessionId',
    'ownerPolicySha256','budgetSha256','rawScopeSha256','parentIdentity'}
STATE={'phase','chunks','pending','streamId','armCommandId','controls','lastSampleSequence',
    'lastNativeSampleEpochMs','sampleNode','nativeRootNode','armOriginal','drained'}
RECORD={'picoEmoteStreamRecordVersion','kind','command','rawReference','wireNonce','wirePhysical',
    'phaseBefore','phaseAfter','hostStarted','hostFinished'}
UNRESOLVED=[]


class PicoEmoteStreamArchive:
    historical_only=True
    live_authority=False

    def __init__(self,store,raw_path,*,guard):
        need(type(store) is PrivateFeatureState and callable(guard))
        self.store=store;self.path=store.path;self.raw_path=Path(raw_path);self.external_guard=guard
        self.directory=self.root=self.raw=None;self.failed=False;self.records=[];self.packets=[]
        self.identity=None;self.state=None;self.arm=None;self.last=None;self.controls=0;self.last_phase=None
        self.protocol='ready';self.policy=None;self.pending_records=[]
        try:
            self.directory=OriginalDescriptor(self.path.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
            self.root=ClosedOriginalFile(self.path,0o600,self.parent_guard)
            raw,self.root_stamp=self.root.read();self.header=strict_json(raw);need(canonical(self.header)+b'\n'==raw)
            exact(self.header,IDENTITY|{'phase','chunks','state'})
            self.identity={key:deepcopy(self.header[key]) for key in IDENTITY}
            self.identity_sha=json_digest(self.identity)
            need(type(self.identity['picoRemoteAvatarSourceVersion']) is int and self.identity['picoRemoteAvatarSourceVersion']==4
                and self.identity['area']=='emotes' and self.identity['role'] in ('primary','actor'))
            self.binding=context(self.identity['binding']);self.pid=int(self.binding['processIdentity'].split(':')[0])
            self.state=self.header['state'];exact(self.state,STATE)
            need(self.state['phase'] in ('ready','reading','running','stopped','drained')
                and self.header['phase']==self.state['phase'] and same(self.header['chunks'],self.state['chunks'])
                and integer(self.state['controls'],0,32) and integer(self.state['lastSampleSequence'],0,256)
                and type(self.state['drained']) is bool and (self.state['phase']=='reading')==(self.state['pending'] is not None))
            self.history=ChatSourceChunks(store,self.identity);self.records=self.history.load(self.header['chunks'])
            self.raw=AudioPCRawOriginals(self.raw_path);scope=self.raw.disk['scope']
            scope_version=scope.get('picoEmoteStreamOriginalsVersion')
            need(type(scope_version) is int and scope_version in (1,2))
            exact(scope,{'picoEmoteStreamOriginalsVersion','containerFormat','budgetSha256','baselineSha256',
                'parentIdentitySha256','roots','roles','maximumNativeFramesPerRole','maximumCompoundNativeFrames'}
                |({'captureCapacitySha256'} if scope_version==2 else set()))
            if scope_version==2:
                from adapters.pico4.emote_stream_capacity import descriptor
                need(scope['captureCapacitySha256']==json_digest(descriptor()))
            need(type(scope['picoEmoteStreamOriginalsVersion']) is int and scope['picoEmoteStreamOriginalsVersion'] in (1,2)
                and scope['containerFormat']=='audioRawJournalVersion1-raw-only' and scope['roles']==['primary','actor']
                and type(scope['maximumNativeFramesPerRole']) is int and scope['maximumNativeFramesPerRole']==256
                and type(scope['maximumCompoundNativeFrames']) is int and scope['maximumCompoundNativeFrames']==512
                and scope['budgetSha256']==self.identity['budgetSha256']
                and scope['parentIdentitySha256']==hashlib.sha256(canonical(self.identity['parentIdentity'])).hexdigest()
                and self.raw.scope_sha==self.identity['rawScopeSha256'])
            for record in self.records:self.replay(record)
            if self.state['phase']=='reading' and self.records and (self.controls!=self.state['controls']
                    or (0 if self.last is None else self.last['sampleSequence'])!=self.state['lastSampleSequence']):
                # A child/root CAS may have completed while its final accepted
                # state/response did not. Replay only the confirmed prefix;
                # expose that exact final original explicitly as uncertain.
                record=self.records[-1];pending=self.state['pending'];exact(pending,{'kind','command','hostStarted','nativeEpochMs','windowSeconds'})
                need(record['kind']==pending['kind'] and same(record['command'],pending['command'])
                    and record['hostStarted']==pending['hostStarted'])
                self.pending_records=[dict(record=deepcopy(record),packet=deepcopy(self.packets[-1]))]
                self.packets=[];self.arm=self.last=self.last_phase=self.policy=None;self.controls=0;self.protocol='ready'
                for record in self.records[:-1]:self.replay(record)
            need(self.controls==self.state['controls'])
            need(self.state['phase']=='reading' or self.protocol==self.state['phase'])
            if self.arm is None:need(all(self.state[key] is None for key in ('streamId','armCommandId','armOriginal','sampleNode','nativeRootNode')))
            else:
                need(self.state['streamId']==self.arm['streamId'] and self.state['armCommandId']==self.arm['armCommandId']
                    and same(self.state['armOriginal'],self.arm['armOriginal'])
                    and self.state['sampleNode']==self.arm['armOriginal']['sampleNode']
                    and self.state['nativeRootNode']==self.arm['armOriginal']['rootNode'])
            need(self.state['lastSampleSequence']==(0 if self.last is None else self.last['sampleSequence'])
                and self.state['lastNativeSampleEpochMs']==(None if self.last is None else self.last['capturedEpochMs']))
            self.memory=self._memory=(self.header,self.identity,self.state,self.records,self.packets,self.pending_records)
            self.memory_sha=json_digest(list(self.memory))
            self.guard()
        except BaseException:
            self.failed=True
            if not self.close():UNRESOLVED.append(self)
            raise

    def parent_guard(self):
        need(self.external_guard() is not False);require_directory(self.directory,self.path.parent)

    def guard(self):
        need(not self.failed);self.parent_guard();self.root.read();self.history.verify()
        need(self.memory is self._memory and all(first is second for first,second in zip(self.memory,
            (self.header,self.identity,self.state,self.records,self.packets,self.pending_records)))
            and json_digest(list(self.memory))==self.memory_sha
            and json_digest(self.identity)==self.identity_sha and same(self.header['state'],self.state))
        # Raw reader's snapshot is historical. Recheck its exact root/index/
            # part originals whenever it supplies a range to this bounded reader.
        self.raw.guard()
        for source in self.raw.files.values():
            if isinstance(source,ClosedOriginalFile):source.read()
        self.parent_guard()

    def replay(self,record):
        exact(record,RECORD);need(type(record['picoEmoteStreamRecordVersion']) is int and record['picoEmoteStreamRecordVersion']==1
            and record['kind'] in ('control','sample') and number(record['hostStarted'],0,1e15)
            and number(record['hostFinished'],record['hostStarted'],record['hostStarted']+5)
            and record['hostFinished']-record['hostStarted']<5)
        before,after=record['phaseBefore'],record['phaseAfter']
        for packet,previous in ((before,self.last_phase),(after,before)):
            phase_packet(packet,run=self.identity['runId'],area='emotes',request=packet['requestId'],
                epoch=packet['capturedEpochMs'],previous=previous)
            need(packet['active'] and packet['activations'])
        need(before['activations'][-1]['ticket']==after['activations'][-1]['ticket']);self.last_phase=after
        raw=self.raw.literal(record['rawReference']);limit=CONTROL_LIMIT if record['kind']=='control' else FRAME_LIMIT
        body,physical=wire_original(raw,record['wireNonce'],limit);need(list(physical)==record['wirePhysical']);value=strict_json(body)
        if record['kind']=='control':
            command=record['command'];need(record['hostFinished']-record['hostStarted']<1.5)
            control_reply(value,command,self.pid,value['capturedEpochMs'],self.identity['ownerPolicySha256'])
            if command['operation']=='arm':
                need(self.arm is None and not self.packets and self.protocol=='ready');self.arm=deepcopy(value)
                need(hashlib.sha256(command['ownerPolicy'].encode()).hexdigest()==self.identity['ownerPolicySha256'])
                self.policy=strict_json(command['ownerPolicy'])
                policy_version=self.policy.get('picoRemoteAvatarStreamPolicyVersion')
                need(type(policy_version) is int and policy_version in (1,2))
                extra={}
                if policy_version==2:
                    from adapters.pico4.emote_stream_capacity import descriptor
                    extra=descriptor();need(self.raw.disk['scope']['picoEmoteStreamOriginalsVersion']==2)
                    need(all(type(self.policy.get(key)) is int and self.policy[key]==value for key,value in extra.items()))
                else:need(self.raw.disk['scope']['picoEmoteStreamOriginalsVersion']==1)
                exact(self.policy,{'picoRemoteAvatarStreamPolicyVersion','runId','role','processId','parentScopeSha256',
                    'parentBaselineSha256','parentHostProcessIdentity','originalNativeEpochMs','deadlineNativeEpochMs',
                    'originalHostStartedMonotonic','originalHostDeadlineMonotonic','nativeFrameLimit','sampleIntervalMs'}|set(extra))
                need(canonical(self.policy).decode('ascii')==command['ownerPolicy'] and type(self.policy['picoRemoteAvatarStreamPolicyVersion']) is int
                    and self.policy['picoRemoteAvatarStreamPolicyVersion'] in (1,2) and self.policy['runId']==self.identity['runId']
                    and self.policy['role']==self.identity['role'] and integer(self.policy['processId'],1) and self.policy['processId']==self.pid
                    and self.policy['parentScopeSha256']==hashlib.sha256(canonical(self.identity['parentIdentity'])).hexdigest()
                    and self.policy['parentBaselineSha256']==self.raw.disk['scope']['baselineSha256']
                    and self.policy['parentHostProcessIdentity']==self.identity['parentIdentity']['parentHostProcessIdentity']
                    and integer(self.policy['nativeFrameLimit'],256,256) and integer(self.policy['sampleIntervalMs'],500,500)
                    and integer(self.policy['originalNativeEpochMs'],1)
                    and integer(self.policy['deadlineNativeEpochMs'],self.policy['originalNativeEpochMs']+1,self.policy['originalNativeEpochMs']+120000))
                start,end=self.policy['originalHostStartedMonotonic'],self.policy['originalHostDeadlineMonotonic']
                need(type(start) is str and type(end) is str and number(float(start),0,1e15)
                    and number(float(end),float(start),float(start)+120) and float(end)>float(start));self.protocol='running'
            else:
                need(self.arm is not None and value['streamId']==self.arm['streamId']
                    and same(value['armOriginal'],self.arm['armOriginal']))
                need(self.protocol==('running' if command['operation']=='stop' else 'stopped'))
                self.protocol='stopped' if command['operation']=='stop' else 'drained'
            self.controls+=1
        else:
            need(record['command'] is None and self.arm is not None and self.protocol=='running')
            frame(value,run=self.identity['runId'],subject=self.identity['subjectSessionId'],pid=self.pid,
                epoch=value['capturedEpochMs'],stream=self.arm['streamId'],policy_sha=self.identity['ownerPolicySha256'])
            original=self.arm['armOriginal']
            need(physical_stamp(physical[0])[:5]==original['rootNode'] and physical_stamp(physical[1])[:5]==original['sampleNode']
                and value['sampleSequence']>=original['sampleSequence'])
            if value['sampleSequence']==original['sampleSequence']:
                need(hashlib.sha256(body).hexdigest()==original['sha256'] and len(body)==original['bytes']
                    and physical_stamp(physical[1])==original['sampleStamp'])
            continuity(self.last,value);self.last=deepcopy(value)
        need(self.policy is not None and self.policy['originalNativeEpochMs']<=value['requestedEpochMs']
            <=value['capturedEpochMs']<self.policy['deadlineNativeEpochMs']
            and float(self.policy['originalHostStartedMonotonic'])<=record['hostStarted']
            <=record['hostFinished']<float(self.policy['originalHostDeadlineMonotonic']))
        self.packets.append(deepcopy(value))

    def original(self,index):
        self.guard();need(integer(index,0,len(self.packets)-1));result=(deepcopy(self.records[index]),deepcopy(self.packets[index]))
        self.guard();return result

    def report(self):
        self.guard();raw=self.raw.report()
        return dict(picoEmoteStreamArchiveVersion=VERSION,historicalOnly=True,liveAuthority=False,roleSourceVersion=4,
            records=len(self.records),samples=sum(record['kind']=='sample' for record in self.records),
            acceptedRecords=len(self.packets),unconfirmedRecords=len(self.pending_records),
            pendingOrUncertain=self.state['pending'] is not None or raw['pendingOrUncertain'],
            wholeFeatureComplete=False,independentActorQualified=False,stereoQualified=False,raw=raw)

    def pending_original(self,index):
        self.guard();need(integer(index,0,len(self.pending_records)-1));original=self.pending_records[index]
        result=dict(historicalOnly=True,liveAuthority=False,unconfirmed=True,record=deepcopy(original['record']),packet=deepcopy(original['packet']))
        self.guard();return result

    def close(self):
        results=[]
        if self.raw is not None:results.append(self.raw.close())
        if self.root is not None:results.append(self.root.close())
        if self.directory is not None:results.append(self.directory.close())
        return all(results)
