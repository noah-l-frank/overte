"""Opt-in Source4 gap coordinator on the ORIGINAL normal Emote Parent.

There is no second recipe, input engine or120s owner. Arm is attached before
the first original baseline read, after that Parent durably issues its budget.
Capture/recognition and whole-feature retirement remain separate obligations.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager,ExitStack
from copy import deepcopy
import hashlib

from adapters.host_process_identity import host_identity
from adapters.chat_journey.source_chunks import json_digest
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.pico4.avatar_remote_state import source_store,namespace_owned
from adapters.pico4.emote_native_cycle import PicoEmoteNativeCycle
from adapters.pico4.emote_stream_frame import independent
from adapters.pico4.emote_stream_originals import PicoEmoteStreamOriginals
from adapters.pico4.emote_stream_policy import PicoEmoteStreamPolicy
from adapters.pico4.emote_stream_role import PicoEmoteStreamRole
from adapters.pico4.emote_stream_wire import PicoEmoteStreamWire
from adapters.pico4.lifecycle_process_file import LifecycleProcessFile
from adapters.pico4.probe_originals import same_callable
from adapters.script_journey.history import canonical,same

VERSION=1
UNRESOLVED=[]


class PicoEmoteStreamCycle:
    def __init__(self,parent,roles,*,capacity=None):
        need(type(parent) is PicoEmoteNativeCycle and type(roles) is dict and set(roles)=={'primary','actor'})
        parent.source.lock.assert_held();parent.bound()
        need(parent.previous is None and parent.state is None and not parent.source.frames and parent.inputs.previous is None)
        if capacity is not None:
            from adapters.pico4.emote_stream_capacity import PicoEmoteStreamCapacity
            need(type(capacity) is PicoEmoteStreamCapacity);capacity.matches(parent,roles)
        self.capacity=self._capacity=capacity
        self.parent=self._parent=parent;self.source=self._source=parent.source;self.host=host_identity()
        admitted=[]
        for role in ('primary','actor'):
            config=roles[role];exact(config,{'adapter','target','native','binding','phase','lock','subject'})
            context(config['binding'])
            need(config['phase'].run==parent.source.run and config['phase'].area=='emotes'
                and config['adapter'].kind=='pico' and config['adapter'].profile['package']=='org.overte.pico'
                and type(config['target']) is str and config['target'])
            row=dict(config,binding=deepcopy(config['binding']));admitted.append((role,row))
        self.roles=self._roles=tuple(admitted)
        need(self.roles[0][1]['lock'] is self.source.lock and self.roles[1][1]['lock'].path!=self.source.lock.path
            and self.roles[0][1]['binding']==self.source.binding)
        self.path=self._path=parent.store.path.with_name(parent.store.path.name+'.child-stream-cycle.json')
        self.store=self._store=PrivateFeatureState(self.path);need(self.store.read() is None)
        self.previous=self._previous=None;self.previous_sha=None
        self.file=self._file=None;self.policy=self._policy=None;self.originals=self._originals=None
        self.streams=self._streams={};self._stream_pins=();self._wire_pins=()
        self._pending_originals=()
        self.failed=False;self.bootstrapping=self._bootstrapping=False;self.phase=self._phase='attached'
        self.retirement=self._retirement=None;self.retirement_sha=None
        self.source_pins=(self.source.lock,self.source.monotonic,self.source.clock_ms,self.source.phase,self.source.run,
            json_digest(self.source.binding),self.parent.store,self.parent.identity,json_digest(self.parent.identity))
        self.config_pins=tuple(self.config_pin(role,row) for role,row in self.roles)
        self.original_read=self._original_read=self.source.read
        self.original_guard=self._original_guard=self.source.guard
        self.read_hook=self._read_hook=self.read;self.guard_hook=self._guard_hook=self.source_guard
        self.source.read=self.read_hook;self.source.guard=self.guard_hook

    @staticmethod
    def config_pin(role,row):
        native,phase,adapter=row['native'],row['phase'],row['adapter']
        return (role,row,adapter,adapter.adb,adapter.adb.execute_bytes,row['target'],native,
            native.send,native.clock_ms,native.guard,getattr(native,'pid',None),row['binding'],json_digest(row['binding']),
            phase,phase.client,phase.client.request,phase.fixture_url,phase.run,phase.area,phase.epoch_ms,phase.monotonic,
            row['lock'],row['lock'].path,row['subject'])

    def configs(self):
        need(self.roles is self._roles and len(self.roles)==len(self.config_pins)==2)
        wires=dict(self._wire_pins)
        for (role,row),pin in zip(self.roles,self.config_pins):
            need(role==pin[0] and row is pin[1]);exact(row,{'adapter','target','native','binding','phase','lock','subject'})
            adapter,native,phase=row['adapter'],row['native'],row['phase']
            need(adapter is pin[2] and adapter.adb is pin[3] and same_callable(adapter.adb.execute_bytes,pin[4])
                and adapter.kind=='pico' and adapter.profile['package']=='org.overte.pico' and row['target']==pin[5]
                and native is pin[6] and all(same_callable(first,second) for first,second in (
                    (native.send,pin[7]),(native.clock_ms,pin[8]),(native.guard,pin[9])))
                and type(getattr(native,'pid',None)) is type(pin[10]) and getattr(native,'pid',None)==pin[10]
                and row['binding'] is pin[11] and json_digest(row['binding'])==pin[12]
                and phase is pin[13] and phase.client is pin[14] and same_callable(phase.client.request,pin[15])
                and (phase.fixture_url,phase.run,phase.area)==pin[16:19]
                and same_callable(phase.epoch_ms,pin[19]) and same_callable(phase.monotonic,pin[20])
                and row['lock'] is pin[21] and row['lock'].path==pin[22] and row['subject']==pin[23])
            wire=wires.get(role)
            if wire is None:need(getattr(native,'phase_fence',None) is None)
            else:need(type(wire) is PicoEmoteStreamWire and wire.native is native
                and native.phase_fence is wire.fence is wire._fence and wire.fence.owner is wire)

    def identity(self):
        need(not self.failed and host_identity()==self.host and self.parent is self._parent
            and self.parent.source is self.source is self._source and self.path==self._path and self.store.path==self.path
            and self.store is self._store and self.file is self._file and self.policy is self._policy
            and self.originals is self._originals and self.phase==self._phase
            and type(self.bootstrapping) is bool and self.bootstrapping is self._bootstrapping
            and self.streams is self._streams and tuple(self.streams)==tuple(role for role,stream,pin in self._stream_pins)
            and self.retirement is self._retirement
            and (self.retirement is None or json_digest(self.retirement)==self.retirement_sha)
            and same_callable(self.source.read,self.read_hook)
            and self.read_hook is self._read_hook and same_callable(self.source.guard,self.guard_hook)
            and self.guard_hook is self._guard_hook and same_callable(self.original_read,self._original_read)
            and same_callable(self.original_guard,self._original_guard))
        need(self.capacity is self._capacity)
        if self.capacity is not None:self.capacity.resource_identity()
        self.configs();pins=self.source_pins
        need(self.source.lock is pins[0] and same_callable(self.source.monotonic,pins[1])
            and same_callable(self.source.clock_ms,pins[2]) and self.source.phase is pins[3]
            and self.source.run==pins[4] and json_digest(self.source.binding)==pins[5]
            and self.parent.store is pins[6] and self.parent.identity is pins[7] and json_digest(self.parent.identity)==pins[8])
        for role,stream,identity in self._stream_pins:
            need(self.streams[role] is stream and type(stream) is PicoEmoteStreamRole
                and stream.policy is self.policy and stream.originals is self.originals
                and json_digest(stream.identity)==identity and stream.role==role)
        need(self.previous is self._previous and (self.previous is None or json_digest(self.previous)==self.previous_sha))
        if self.file is not None:self.file.guard();need(same(self.store.read(),self.previous))
        if self.policy is not None:need(self.policy.parent is self.parent);self.policy.identity()
        if self.originals is not None:need(self.originals.policy is self.policy)

    def source_guard(self):
        # Parent.bound reaches this hook, so it must never call Parent.bound.
        self.identity();value=self.original_guard();self.identity();return value

    def locks(self):
        self.identity()
        for role,config in self.roles:config['lock'].assert_held()

    @contextmanager
    def held(self):
        self.identity()
        locks=sorted((config['lock'] for role,config in self.roles),key=lambda lock:str(lock.path))
        need(all(lock._owner is None for lock in locks))
        with ExitStack() as stack:
            for lock in locks:stack.enter_context(lock.held())
            self.identity();yield;self.identity()

    def save(self,**changes):
        self.locks();self.identity();self.parent.bound()
        need(set(changes)<={'phase','policy','originals','stream','retirement'})
        phase=changes.get('phase',self.phase);policy=changes.get('policy',self.policy)
        originals=changes.get('originals',self.originals);streams=dict(self.streams);retirement=changes.get('retirement',self.retirement)
        if 'stream' in changes:
            role,stream=changes['stream'];need(self.phase=='arming' and role in ('primary','actor') and role not in streams
                and type(stream) is PicoEmoteStreamRole and stream.policy is policy and stream.originals is originals
                and stream.wire is dict(self._wire_pins)[role]);streams[role]=stream
        allowed={'attached':('arming',),'arming':('arming','armed'),'armed':('armed','stopping'),
            'stopping':('stopping','stopped'),'stopped':('stopped','drained'),'drained':('drained',)}
        need(phase in allowed[self.phase])
        if self.phase=='attached':
            need(self.parent.previous is not None and self.parent.state['phase']=='baseline-issued'
                and json_digest(self.parent.state)==json_digest(self.parent.previous['state'])
                and not self.source.frames and self.parent.inputs.previous is None)
        if policy is not None:need(type(policy) is PicoEmoteStreamPolicy and policy.parent is self.parent)
        if originals is not None:need(type(originals) is PicoEmoteStreamOriginals and originals.policy is policy)
        if phase=='armed':need(policy is not None and originals is not None and set(streams)=={'primary','actor'}
            and all(stream.state['phase']=='running' and stream.state['pending'] is None and stream.state['controls']==1 for stream in streams.values()))
        if phase in ('stopping','stopped','drained'):
            need(self.parent.state['phase']=='native-quiet' and len(self.parent.state['steps'])==4
                and json_digest(self.parent.state)==json_digest(self.parent.previous['state']))
            exact(retirement,{'originalParentNativeQuiet','sourceStopped','sourceDrained','independentActorQualified','stereoQualified','wholeFeatureComplete'})
            need(all(retirement[key] is False for key in ('independentActorQualified','stereoQualified','wholeFeatureComplete')))
            if phase in ('stopped','drained'):need(retirement['sourceStopped'] is True)
            if phase=='stopped':need(all(stream.state['phase']=='stopped' for stream in streams.values()) and retirement['sourceDrained'] is False)
            if phase=='drained':need(all(stream.state['phase']=='drained' and stream.state['drained'] is True for stream in streams.values())
                and retirement['sourceDrained'] is True)
        value=dict(picoEmoteStreamCycleVersion=VERSION,parentIdentity=deepcopy(self.parent.identity),
            phase=phase,budgetSha256=None if policy is None else hashlib.sha256(policy.raw).hexdigest(),
            roleJournals={role:str(stream.store.path) for role,stream in streams.items()},
            retirement=deepcopy(retirement),wholeFeatureComplete=False)
        try:self.file.write(value,self.previous)
        except BaseException:self.failed=True;UNRESOLVED.append(self);raise
        # ONLY this successful original CAS/readback admits evolving objects
        # and phase. Neither identity()/guard nor arbitrary public mutation
        # can reseal a different graph or skip the first actual source ARM.
        self.previous=self._previous=deepcopy(value);self.previous_sha=json_digest(self.previous)
        self.phase=self._phase=phase;self.policy=self._policy=policy;self.originals=self._originals=originals
        self.streams=self._streams=streams;self._stream_pins=tuple((role,stream,json_digest(stream.identity)) for role,stream in streams.items())
        self.retirement=self._retirement=deepcopy(retirement);self.retirement_sha=None if retirement is None else json_digest(self.retirement)
        self.bootstrapping=self._bootstrapping=phase=='arming';self.identity();self.parent.bound()

    def wire(self,role,config,box):
        self.save();ticket=(self.file.stamp,self.previous)
        # The actual arming CAS owns installation before this one-time native
        # final callback attachment. Construction performs no Source IO.
        wire=PicoEmoteStreamWire(config['adapter'],config['target'],config['native'],self.originals.archive,
            lambda box=box:box[0].guard(),role=role,monotonic=self.source.monotonic)
        self.file.guard();need(self.file.stamp==ticket[0] and self.previous is ticket[1] and same(self.store.read(),self.previous))
        self._wire_pins=self._wire_pins+((role,wire),);self.identity();return wire

    def pending_original(self,kind,selected,*args,**options):
        need((kind,selected) in (('policy',PicoEmoteStreamPolicy),('originals',PicoEmoteStreamOriginals)))
        original=object.__new__(selected)
        # Resource retention is NOT business admission. Keep the actual object
        # strongly reachable before its constructor can obtain files/OFDs,
        # including successful construction followed by unknown parent CAS.
        self._pending_originals=self._pending_originals+((kind,original,False),)
        selected.__init__(original,*args,**options)
        self._pending_originals=tuple((label,owner,True if owner is original else complete)
            for label,owner,complete in self._pending_originals)
        return original

    def original_admitted(self,kind,original):
        need((kind=='policy' and self._policy is original) or (kind=='originals' and self._originals is original))
        self._pending_originals=tuple(row for row in self._pending_originals if row[1] is not original)

    def bootstrap(self):
        self.locks();self.identity();need(self.phase=='attached' and not self.bootstrapping)
        need(self.parent.state is not None and self.parent.state['phase']=='baseline-issued'
            and self.parent.state['baseline'] is None and not self.source.frames)
        self.file=self._file=object.__new__(LifecycleProcessFile)
        try:
            LifecycleProcessFile.__init__(self.file,self.store);self.save(phase='arming')
            if self.capacity is not None:self.capacity.activate()
            policy=self.pending_original('policy',PicoEmoteStreamPolicy,self.parent,
                {role:dict(binding=config['binding'],clock=config['native'].clock_ms) for role,config in self.roles},capacity=self.capacity)
            self.save(policy=policy);self.original_admitted('policy',policy)
            roots=[source_store(config['adapter'],config['target'],self.source.run,area='emotes').path.parent for role,config in self.roles]
            originals=self.pending_original('originals',PicoEmoteStreamOriginals,self.policy,roots,capacity=self.capacity)
            self.save(originals=originals);self.original_admitted('originals',originals)
            # BOTH existing arenas must be empty before either native ARM.
            for role,config in self.roles:
                store=source_store(config['adapter'],config['target'],self.source.run,area='emotes')
                need(store.read() is None and not namespace_owned(store,store.path.name))
            for role,config in self.roles:
                box=[]
                wire=self.wire(role,config,box)
                stream=PicoEmoteStreamRole(source_store(config['adapter'],config['target'],self.source.run,area='emotes'),
                    self.policy,self.originals,wire,config['phase'],config['lock'],config['subject'],role=role)
                box.append(stream);self.save(stream=(role,stream));stream.control('arm');self.save()
            self.save(phase='armed')
        except BaseException:self.failed=True;UNRESOLVED.append(self);raise

    def read(self):
        self.identity()
        if self.phase=='attached':self.bootstrap()
        need(not self.bootstrapping and self.phase=='armed');self.identity()
        value=self.original_read();self.identity();return value

    def baseline(self):
        self.locks();self.identity();value=self.parent.baseline();self.identity();need(self.phase=='armed');return value

    def act(self,call):
        self.locks();self.identity();need(self.phase=='armed');value=self.parent.act(call);self.identity();return value

    def sample_pair(self):
        self.locks();self.identity();need(self.phase=='armed')
        primary=self.streams['primary'].read();actor=self.streams['actor'].read();independent(primary,actor)
        self.identity();return dict(primary=primary,actor=actor)

    def cleanup(self,*,sleep):
        self.locks();self.identity();need(self.phase=='armed')
        quiet=self.parent.cleanup(sleep=sleep)
        retirement=dict(originalParentNativeQuiet=deepcopy(quiet),sourceStopped=False,sourceDrained=False,
            independentActorQualified=False,stereoQualified=False,wholeFeatureComplete=False)
        self.save(phase='stopping',retirement=retirement)
        for role,stream in self.streams.items():stream.control('stop')
        retirement=dict(self.retirement,sourceStopped=True);self.save(phase='stopped',retirement=retirement);return deepcopy(self.retirement)

    def drain(self):
        # Caller returns to the real native event loop outside both locks;
        # there is no rapid drain retry, manufactured QObject death or sleep.
        self.locks();self.identity();need(self.phase=='stopped')
        for role,stream in self.streams.items():stream.control('drain')
        retirement=dict(self.retirement,sourceDrained=True);self.save(phase='drained',retirement=retirement);return deepcopy(self.retirement)

    def close_host(self):
        # Public substitutions must never redirect finalization to foreign
        # owners. Only the actual admitted originals may close their own OFDs.
        results=[stream.close_host() for role,stream,pin in self._stream_pins]
        seen={id(stream) for role,stream,pin in self._stream_pins}
        for kind,owner,complete in self._pending_originals:
            if id(owner) in seen:continue
            seen.add(id(owner))
            if complete:results.append(owner.close_host())
            else:results.append(False) # Partial/uncertain constructors stay strongly owned.
        if self._originals is not None and id(self._originals) not in seen:results.append(self._originals.close_host())
        if self._policy is not None and id(self._policy) not in seen:results.append(self._policy.close_host())
        if self._capacity is not None:results.append(self._capacity.close_host())
        if self._file is not None and hasattr(self._file,'parent'):results.append(self._file.close_host())
        result=all(results)
        if not result and self not in UNRESOLVED:UNRESOLVED.append(self)
        return result
