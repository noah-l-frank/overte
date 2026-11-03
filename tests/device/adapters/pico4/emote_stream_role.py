"""Original Source4 role: arm once, sample passively, stop and drain honestly.

The source lives in the EXISTING remote-owner arena. Historical Source1/2/3,
mixed/rootless files, interrupted CAS and prior Source4 may never be adopted
as a new stream. The same native cycle remains the sole input Parent.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import uuid

from adapters.chat_journey.source_chunks import ChatSourceChunks,json_digest
from adapters.native_feature_observation import exact,integer,need,number
from adapters.native_fd_owner import require_directory
from adapters.pico4.avatar_remote_state import namespace_owned
from adapters.pico4.emote_stream_frame import ACTION,CONTROL_LIMIT,FRAME_LIMIT,control_reply,frame,continuity
from adapters.pico4.emote_stream_originals import PicoEmoteStreamOriginals
from adapters.pico4.emote_stream_policy import PicoEmoteStreamPolicy
from adapters.pico4.emote_stream_wire import PicoEmoteStreamWire,wire_original,physical_stamp,strict_json
from adapters.pico4.lifecycle_process_file import LifecycleProcessFile
from adapters.script_journey.history import canonical,same
from feature_journeys.phase_fixture import PhaseFixtureReader,validate as phase_packet

VERSION=4
UNRESOLVED=[]


class PicoEmoteStreamRole:
    def __init__(self,store,policy,originals,wire,phase,lock,subject,*,role):
        need(type(policy) is PicoEmoteStreamPolicy and type(originals) is PicoEmoteStreamOriginals
            and type(wire) is PicoEmoteStreamWire and type(phase) is PhaseFixtureReader and phase.area=='emotes'
            and phase.run==policy.run and role in ('primary','actor') and wire.role==role
            and originals.policy is policy and wire.archive is originals.archive and callable(wire.monotonic)
            and phase.fixture_url==policy.parent.source.phase.fixture_url)
        lock.assert_held();policy.bound();need(store.read() is None and not namespace_owned(store,store.path.name))
        self.store=self._store=store;self.policy=self._policy=policy;self.originals=self._originals=originals
        self.wire=self._wire=wire;self.phase=self._phase=phase;self.lock=self._lock=lock
        self.role=self._role=role;self.subject=self._subject=subject;self.run=policy.run
        self.monotonic=self._monotonic=wire.monotonic;self.clock_ms=self._clock_ms=wire.clock_ms
        self.binding=deepcopy(policy.disk['bindings'][role]);self.pid=int(self.binding['processIdentity'].split(':')[0])
        self.owner_policy=policy.policy(role);self.policy_sha=hashlib.sha256(self.owner_policy.encode()).hexdigest()
        self.identity=dict(picoRemoteAvatarSourceVersion=VERSION,area='emotes',role=role,runId=self.run,
            fixtureUrl=phase.fixture_url,binding=deepcopy(self.binding),subjectSessionId=subject,
            ownerPolicySha256=self.policy_sha,budgetSha256=hashlib.sha256(policy.raw).hexdigest(),
            rawScopeSha256=originals.archive.scope_sha,parentIdentity=deepcopy(policy.parent.identity))
        self.original_identity=canonical(self.identity);self.file=object.__new__(LifecycleProcessFile)
        self.failed=False;self.previous=None;self.operation=self.operation_seal=None;self.last_sample=self.last_sample_record=None
        self._sample=self._sample_sha=self._sample_record=None
        self.state=dict(phase='ready',chunks=[],pending=None,streamId=None,armCommandId=None,controls=0,
            lastSampleSequence=0,lastNativeSampleEpochMs=None,sampleNode=None,nativeRootNode=None,armOriginal=None,drained=False)
        try:
            LifecycleProcessFile.__init__(self.file,store);self.chunks=ChatSourceChunks(store,self.identity);self.chunks.load([])
            self.save()
        except BaseException:self.failed=True;UNRESOLVED.append(self);raise

    def guard(self):
        self.lock.assert_held();need(not self.failed and self.store is self._store and self.policy is self._policy
            and self.originals is self._originals and self.wire is self._wire and self.phase is self._phase
            and self.lock is self._lock and self.role==self._role and self.subject==self._subject
            and self.monotonic is self._monotonic and self.clock_ms is self._clock_ms
            and json_digest(self.identity)==hashlib.sha256(self.original_identity).hexdigest()
            and json_digest(self.binding)==json_digest(self.identity['binding']))
        self.policy.bound();self.originals.bound();self.file.guard();require_directory(self.file.parent,self.store.path.parent)
        need(self.last_sample is self._sample and self.last_sample_record==self._sample_record)
        if self.last_sample is not None:need(json_digest(self.last_sample)==self._sample_sha)
        need(same(self.store.read(),self.previous));self.chunks.verify()
        if self.previous is not None:
            need(all(same(self.previous[key],value) for key,value in self.identity.items())
                and json_digest(self.previous['state'])==json_digest(self.state) and self.previous['chunks']==self.state['chunks'])
        if self.operation is not None:
            need(type(self.operation_seal) is tuple and self.operation_seal is self._operation_seal
                and self.operation==self.operation_seal[0] and self.state['pending'] is not None
                and all(self.state['pending'][key]==value for key,value in zip(
                    ('hostStarted','nativeEpochMs','windowSeconds'),self.operation_seal)))
            now=self.monotonic();epoch=self.clock_ms();started,native,window=self.operation_seal
            need(number(now,started,started+window) and integer(epoch,native)
                and max((now-started)*1000,epoch-native)<window*1000)
        return True

    def save(self):
        # ChatSourceChunks uses its ordinary reading intent at this same root.
        # The exact state transition is authored here, not from a returned DTO.
        self.lock.assert_held();need(not self.failed);self.policy.bound();self.file.guard()
        require_directory(self.file.parent,self.store.path.parent);need(same(self.store.read(),self.previous));self.chunks.verify()
        value=dict(self.identity,phase=self.state['phase'],chunks=deepcopy(self.state['chunks']),state=deepcopy(self.state))
        self.file.write(value,self.previous);self.previous=deepcopy(value);self.guard()

    def put(self,value):
        self.guard();need(self.state['phase']=='reading' and self.state['pending'] is not None)
        index=len(self.state['chunks']);self.state['chunks']=self.chunks.append(value,self.state['chunks']);self.save();return index

    def phase_status(self,previous=None):
        self.guard();status=self.phase.status(previous)
        phase_packet(status,run=self.run,area='emotes',request=status['requestId'],epoch=status['capturedEpochMs'],previous=previous)
        need(status['active'] and status['activations']);self.guard();return status

    def begin(self,kind,command):
        self.guard();need(self.state['phase'] in ('ready','running','stopped') and self.state['pending'] is None)
        self.operation=self.monotonic();epoch=self.clock_ms();window=1.5 if kind=='control' else 5
        self.operation_seal=self._operation_seal=(self.operation,epoch,window)
        self.state.update(phase='reading',pending=dict(kind=kind,command=deepcopy(command),hostStarted=self.operation,
            nativeEpochMs=epoch,windowSeconds=window))
        self.save()

    def finish(self,kind,command,value,before,after):
        self.guard();need(before['activations'][-1]['ticket']==after['activations'][-1]['ticket'])
        reference=deepcopy(self.wire.last_reference);need(reference is not None)
        record=dict(picoEmoteStreamRecordVersion=1,kind=kind,command=deepcopy(command),rawReference=reference,
            wireNonce=self.wire.last_nonce,wirePhysical=list(self.wire.last_physical),phaseBefore=deepcopy(before),phaseAfter=deepcopy(after),
            hostStarted=self.operation,hostFinished=self.monotonic())
        index=self.put(record);self.guard();self.state['pending']=None;self.operation=None
        if kind=='sample':
            self.state.update(phase='running',lastSampleSequence=value['sampleSequence'],lastNativeSampleEpochMs=value['capturedEpochMs'],
                nativeRootNode=physical_stamp(self.wire.last_physical[0])[:5],sampleNode=physical_stamp(self.wire.last_physical[1])[:5])
        else:
            self.state['controls']+=1
            if command['operation']=='arm':self.state.update(phase='running',streamId=value['streamId'],armCommandId=value['armCommandId'],
                nativeRootNode=deepcopy(value['armOriginal']['rootNode']),sampleNode=deepcopy(value['armOriginal']['sampleNode']),
                armOriginal=deepcopy(value['armOriginal']))
            elif command['operation']=='stop':self.state['phase']='stopped'
            else:self.state.update(phase='drained',drained=True)
        self.save()
        if kind=='sample':
            # Admit this exact memory graph only after actual successful role
            # CAS/readback; generic guards and failed saves cannot reseal it.
            self.last_sample=self._sample=deepcopy(value);self.last_sample_record=self._sample_record=index
            self._sample_sha=json_digest(self.last_sample)
        self.guard();return deepcopy(value)

    def control(self,operation):
        try:
            self.guard();need(operation in ('arm','stop','drain') and self.state['controls']<32)
            need(self.state['phase']=={'arm':'ready','stop':'running','drain':'stopped'}[operation])
            request=dict(schemaVersion=1,commandId=uuid.uuid4().hex,action=ACTION,operation=operation,runId=self.run)
            if operation=='arm':request.update(subjectSessionId=self.subject,ownerPolicy=self.owner_policy)
            else:request.update(streamId=self.state['streamId'],armCommandId=self.state['armCommandId'],policySha256=self.policy_sha)
            self.begin('control',request);before=self.phase_status();value=self.wire.control(request)
            # The wire has already durably retained even malformed/late ACKs.
            control_reply(value,request,self.pid,self.clock_ms(),self.policy_sha)
            if self.state['armOriginal'] is not None:need(same(value['armOriginal'],self.state['armOriginal']))
            after=self.phase_status(before);return self.finish('control',request,value,before,after)
        except BaseException:self.failed=True;raise
        finally:self.operation=None

    def read(self):
        try:
            self.guard();need(self.state['phase']=='running' and self.state['lastSampleSequence']<256)
            # Actual old native sample time paces reads; it is not a desired
            # producer stamp. No same-frame rapid poll or cursor reset exists.
            old=self.state['lastNativeSampleEpochMs']
            if old is not None:need(self.clock_ms()>=old+500)
            self.begin('sample',None);before=self.phase_status();value=self.wire.read()
            frame(value,run=self.run,subject=self.subject,pid=self.pid,epoch=self.clock_ms(),
                stream=self.state['streamId'],policy_sha=self.policy_sha)
            need(physical_stamp(self.wire.last_physical[0])[:5]==self.state['nativeRootNode']
                and physical_stamp(self.wire.last_physical[1])[:5]==self.state['sampleNode'])
            original=self.state['armOriginal'];need(value['sampleSequence']>=original['sampleSequence'])
            if value['sampleSequence']==original['sampleSequence']:
                wire=self.originals.archive.literal(self.wire.last_reference)
                raw,unused=wire_original(wire,self.wire.last_nonce,FRAME_LIMIT)
                need(hashlib.sha256(raw).hexdigest()==original['sha256'] and len(raw)==original['bytes']
                    and physical_stamp(self.wire.last_physical[1])==original['sampleStamp'])
            need(value['sampleSequence']>self.state['lastSampleSequence'])
            continuity(self.last_sample,value);after=self.phase_status(before)
            return self.finish('sample',None,value,before,after)
        except BaseException:self.failed=True;raise
        finally:self.operation=None

    def original(self,index):
        """Replay actual immutable role record+wire; never send or cold-adopt."""
        self.guard();need(integer(index,0,len(self.state['chunks'])-1));records=self.chunks.load(self.state['chunks'])
        record=records[index];exact(record,{'picoEmoteStreamRecordVersion','kind','command','rawReference','wireNonce','wirePhysical',
            'phaseBefore','phaseAfter','hostStarted','hostFinished'})
        need(type(record['picoEmoteStreamRecordVersion']) is int and record['picoEmoteStreamRecordVersion']==1)
        kind=record['kind'];need(kind in ('sample','control'));raw=self.originals.archive.literal(record['rawReference'])
        body,physical=wire_original(raw,record['wireNonce'],FRAME_LIMIT if kind=='sample' else CONTROL_LIMIT)
        need(list(physical)==record['wirePhysical']);value=strict_json(body)
        self.guard();return record,value

    def close_host(self):
        result=self.file.close_host()
        if not result and self not in UNRESOLVED:UNRESOLVED.append(self)
        return result
