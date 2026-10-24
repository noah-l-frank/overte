"""Role/run/seal-owned once-only normal Stop and independent OS originals.

This partial process owner retains all frozen and current metadata. It cannot
delete an SDK, retire holders by changing counters or complete the Emote area.
After issued/uncertain Stop it can only read the existing SDK's OS endpoint.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.operation_transport_guard import scope as transport_scope
from adapters.original_frame_store import OriginalFrameStore
from adapters.script_feature.history import pack,unpack,same
from ios.adapters.emote_operation import clock,operation
from ios.adapters.emote_rooted_feature import IOSEmoteRootedFeature
from ios.adapters.emote_rooted_final_archive import IOSEmoteRootedFinalArchive
from ios.adapters.emote_rooted_ownership import IOSEmoteRootedOwnership
from ios.adapters.installed_code import source as source_packet
from ios.adapters.installed_process_runtime import admitted_source,mark_stopped,retired_process_observer
from ios.adapters.process_retirement import IOSProcessRetirement,filename
from ios.adapters.retired_process import absent


class IOSEmoteRootedProcessEnd:
    def __init__(self,flow,ownership,archive,seal,*,peer=None,retirement=None):
        need(type(flow) is IOSEmoteRootedFeature and type(ownership) is IOSEmoteRootedOwnership
            and type(archive) is IOSEmoteRootedFinalArchive and flow.run==ownership.roles.run)
        self.flow,self.ownership,self.archive,self.seal,self.peer=flow,ownership,archive,deepcopy(seal),peer
        self.retirement=retirement
        if retirement is not None:
            from ios.adapters.emote_rooted_end_archive import IOSEmoteRootedEndArchive
            need(type(retirement) is IOSEmoteRootedEndArchive and retirement.archive is archive
                and retirement.ownership is ownership and same(retirement.seal,seal) and retirement.state is not None)
            retirement.bound()
        self.runtime,self.run,self.role,self.root,self.lock=flow.runtime,flow.run,flow.role,flow.root,flow.lock
        self.primary_lock=flow.primary_lock
        for lock in ownership.roles.locks.values():lock.assert_held()
        need(flow.lock is ownership.roles.locks[flow.role] and flow.primary_lock is ownership.roles.locks['primary'])
        flow.load()
        if flow.state is None and retirement is not None:
            # Actual typed end intent, rather than a missing file, authorizes
            # interpreting this retained feature copy during pure replay.
            original_store=flow.store
            flow.store=retirement.store_for(original_store.path,archive.copies()[str(original_store.path)])
            try:flow.load()
            finally:flow.store=original_store
        need(flow.state is not None and flow.state['phase']=='cleaned')
        self.binding=deepcopy(flow.state['binding']);self.monotonic=flow.monotonic
        self.deadline=self.last_clock=None;self.phase=flow.phase
        self.store=PrivateFeatureState(flow.store.path.with_name('ios-emote-'+self.role+'-'+self.run+'-rooted-process-end.json'))
        self.frames=OriginalFrameStore(self.root,self.binding,self.run,self.role,self.bound,self.intent,
            namespace='emote-rooted-process',schema_prefix='emoteRootedProcess',monotonic=self.monotonic)
        self.previous=self.store.read();self.state=None if self.previous is None else self.decode(self.previous)
        self.peer_identity()

    def clock(self):return clock(self)
    def peer_identity(self):
        if self.role=='actor':need(self.peer is None);return None
        need(type(self.peer) is IOSEmoteRootedProcessEnd and self.peer.role=='actor' and self.peer.run==self.run
            and self.peer.runtime is self.runtime and self.peer.flow.selector==self.flow.actor_selector
            and self.peer.primary_lock is self.lock and self.peer.lock is self.ownership.roles.locks['actor']
            and self.peer.archive is self.archive and same(self.peer.seal,self.seal))
        return self.peer
    def envelope(self,state):
        return dict(iosEmoteRootedProcessEndVersion=1,runId=self.run,role=self.role,binding=self.binding,artifactRoot=str(self.root),
            archiveSha256=digest(self.archive.previous),sealSha256=digest(self.seal),payload=pack([state]))
    def os_store(self):return PrivateFeatureState(self.store.path.with_name(filename('emote',self.role,0)))
    def os_state(self):
        raw=self.os_store().read()
        if raw is None:return None
        return IOSProcessRetirement.archive(raw,path=self.os_store().path,binding=self.binding,source=self.state['source'],
            bundle=self.state['bundleId'],run=self.run,role=self.role,stage=0,profile='emote')
    def decode(self,value):
        exact(value,{'iosEmoteRootedProcessEndVersion','runId','role','binding','artifactRoot','archiveSha256','sealSha256','payload'})
        rows=unpack(value['payload']);need(type(value['iosEmoteRootedProcessEndVersion']) is int and len(rows)==1 and same(value,self.envelope(rows[0])))
        state=rows[0];exact(state,{'phase','source','bundleId','peer','fence','pending','processSha256'})
        need(state['phase'] in ('prepared','stop-issued','stopped','complete'));source_packet(state['source'])
        need(state['bundleId']==self.runtime.adapter.target(self.flow.selector)['appId'])
        if self.role=='actor':need(state['peer'] is None)
        else:
            peer=self.peer_identity();need(state['peer'] is not None and same(peer.store.read(),state['peer'])
                and same(peer.previous,state['peer']) and peer.state is not None and peer.state['phase']=='complete')
        if state['fence'] is not None:self.frames.expand(state['fence'])
        if state['pending'] is not None:self.frames.original(state['pending']);need(state['phase']=='prepared' and state['fence'] is None)
        if state['phase']!='prepared':need(state['fence'] is not None and state['pending'] is None)
        if state['phase']=='complete':need(type(state['processSha256']) is str and digest(self.os_store().read())==state['processSha256'])
        else:need(state['processSha256'] is None)
        return deepcopy(state)
    def bound(self,*,writing=False):
        for lock in self.ownership.roles.locks.values():lock.assert_held()
        need(same(self.store.read(),self.previous) and same(self.flow.state['binding'],self.binding)
            and same(self.archive.store.read(),self.archive.previous))
        if not writing:need(self.previous is None and self.state is None or self.previous is not None and same(self.state,self.decode(self.previous)))
        return True
    def save(self):
        self.bound(writing=True);value=self.envelope(self.state);self.decode(value);self.store.write(value,self.previous)
        need(same(self.store.read(),value));self.previous=deepcopy(value)
    def intent(self,event,wire):
        need(event=='original' and self.state['phase']=='prepared' and self.state['fence'] is None and wire['index']==1)
        self.state['pending']=deepcopy(wire);self.save()
    def outputs(self):
        self.bound();result={self.store.path}
        if self.state is not None:
            if self.state['fence'] is not None:result.add(self.frames.path(self.frames.expand(self.state['fence'])))
            if self.state['pending'] is not None:result.add(self.frames.path(self.state['pending']))
        return result
    def fence_original(self):
        self.bound();need(self.state is not None and self.state['fence'] is not None)
        return self.frames.read(self.frames.expand(self.state['fence']))
    def fence_validate(self):
        from ios.adapters.emote_rooted_fence_original import validate
        return validate(self.fence_original(),self.ownership,self.archive,self.seal,retirement=getattr(self,'retirement',None))
    def completed(self):
        self.bound();need(self.state is not None and self.state['phase']=='complete')
        self.fence_validate();state=self.os_state()
        need(state is not None and state['pending'] is None and state['windows'] and state['windows'][-1]['complete'])
        if self.peer is not None:self.peer.completed()
        return deepcopy(self.previous)
    def overrides(self):
        need(self.role=='actor');self.completed();return self.fence_validate()['metadata']

    @operation(30)
    def prepare(self):
        self.bound();need(self.state is None)
        from ios.adapters.emote_rooted_fence import _seal
        proof=self.ownership.read();_seal(proof,self.seal,run=self.run,role=self.role,binding=self.binding)
        need(self.archive.state is not None and self.archive.state['phase']=='validated')
        peer=None if self.peer is None else self.peer.completed()
        source=admitted_source(self.runtime,self.flow.selector,self.binding)
        self.state=dict(phase='prepared',source=source,bundleId=self.runtime.adapter.target(self.flow.selector)['appId'],peer=peer,
            fence=None,pending=None,processSha256=None);self.save()

    @operation(30)
    def stop(self,scope,pointers,keys):
        self.bound();need(self.state is not None and self.state['phase']=='prepared')
        from ios.adapters.emote_rooted_fence_cut import IOSEmoteRootedFenceCut
        from ios.adapters.emote_rooted_fence import acquire,current
        need(same(admitted_source(self.runtime,self.flow.selector,self.binding),self.state['source']))
        cut=IOSEmoteRootedFenceCut(self)
        if self.state['pending'] is not None:
            pending=self.state['pending'];need(pending['phase'] in ('opened','saved'))
            value=self.frames.read(pending)
            from ios.adapters.emote_rooted_fence_original import validate
            validate(value,self.ownership,self.archive,self.seal)
            self.state.update(fence=self.frames.compact(dict(pending,phase='saved')),pending=None);self.save()
        if self.state['fence'] is None:
            value=acquire(self.ownership,self.archive,self.seal,scope,pointers,keys,self.phase,end=self,cut=cut)
            ref=self.frames.write(1,value);self.state.update(fence=ref,pending=None);self.save()
        else:value=self.fence_original();self.fence_validate();cut.recovered(value)
        cut.freeze(value)
        current(value['acquisitions'],value['nativeClock'],epoch_ms=self.flow.epoch_ms,monotonic=self.monotonic)
        self.state['phase']='stop-issued';self.save()
        def guard():
            self.bound();cut.guard()
            current(value['acquisitions'],value['nativeClock'],epoch_ms=self.flow.epoch_ms,monotonic=self.monotonic)
        with transport_scope(guard):
            guard();self.runtime._emote_rooted_stop(self,cut)

    @operation(30)
    def advance(self):
        self.bound();need(self.state is not None and self.state['phase'] in ('stop-issued','stopped','complete'))
        if self.state['phase']=='complete':self.completed();return True
        # All further native/UI/image/phase acquisition is forbidden here.
        # Only this original fence plus the independent OS source are used.
        self.fence_validate()
        reader=retired_process_observer(self.runtime,self.flow.selector,self.binding,self.state['source'])
        owner=IOSProcessRetirement(self.os_store(),reader,self.binding,self.run,self.role,0,self.lock,profile='emote')
        complete=owner.advance();current=owner.current();fence=self.fence_original()
        need(current['acquisition']['hostBeforeEpochMs']>=fence['phaseAfter']['capturedEpochMs'])
        if absent(current['original']):
            mark_stopped(self.runtime,self.flow.selector,self.binding,self.state['source']);self.state['phase']='stopped'
        if complete:self.state.update(phase='complete',processSha256=digest(owner.previous))
        self.save();return bool(complete)
