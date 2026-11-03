"""Explicit selected Assets graph, local end originals and metadata-only CAS.

The current graph must independently prove normal server restoration BEFORE
Stop. Retained byte/image/cache/GPU originals stay intact after local OS/SDK
end; neither this owner nor those ends establish whole resource reclamation.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
from adapters.native_clock_join import digest
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.original_file_reads import collect as read_scope
from adapters.script_feature.history import same
from ios.adapters.assets_budget import operation,check
from ios.adapters.assets_end_graph import AssetsFinalArchive,AssetsOwnership,inventory,selection
from ios.adapters.assets_end_process import AssetsProcessEnd
from ios.adapters.assets_end_sdk import AssetsSDKEnd
from ios.adapters.emote_original_lease import EmoteOriginalLease
from ios.adapters.assets_end_metadata import signature


class AssetsPairedLocalEnd:
    def __init__(self,runtime,selected,locks):
        from ios.adapters.assets_selected_runtime import SelectedAssetsRuntime
        need(type(runtime) is SelectedAssetsRuntime and type(selected) is AssetsFinalArchive and runtime.assets_selection is selected)
        selected.selected_guard();need(set(locks)=={'primary','actor'})
        self.runtime,self.archive,self.locks=runtime,selected,dict(locks);self.context=selection(selected.context)
        self.run,self.monotonic=selected.run,runtime.monotonic;self.ownership=None
        selected.validate=lambda copies:AssetsOwnership(self.context,copies,self.locks,selected).read(owned=self.owned_paths())
        for role in ('primary','actor'):
            need(locks[role].path==Path(self.context['roles'][role]['stateRoot'])/'script-feature-sources.lock');locks[role].assert_held()
        self.processes={};self.sessions={}
        actor=AssetsProcessEnd(self,'actor');primary=AssetsProcessEnd(self,'primary',peer=actor)
        self.processes=dict(actor=actor,primary=primary)
        actor_sdk=AssetsSDKEnd(actor,self.processes);primary_sdk=AssetsSDKEnd(primary,self.processes,peer=actor_sdk)
        self.sessions=dict(actor=actor_sdk,primary=primary_sdk)
        if selected.state is not None and selected.state['phase'] not in ('selecting','selected','freezing'):
            self.ownership=AssetsOwnership(self.context,selected.copies(),self.locks,selected)
        self.guard()
    def role_root(self,role):return Path(self.context['roles'][role]['artifactRoot'])
    def guard(self):
        check()
        for lock in self.locks.values():lock.assert_held()
        self.archive.selected_guard();return True
    def inventory(self):return inventory(self.ownership.roots,locks=self.locks.values())
    def owned_paths(self):
        result=self.archive.owned_paths()
        for owner in self.processes.values():result|=owner.owned_paths()
        for owner in self.sessions.values():result|=owner.owned_paths()
        return result
    def current_metadata(self):
        self.guard();need(self.ownership is not None)
        retired=self.archive.state['retired']
        for index,path in enumerate(self.archive.paths):
            before=signature(path.path);current=path.read();need(signature(path.path)==before)
            copy=self.ownership.copies[str(path.path)];expected=self.archive.metadata_pins[str(path.path)]
            may_be_absent=index<retired or index==retired and self.archive.state['phase']=='retiring'
            if may_be_absent and current is None:need(before is None)
            else:need(same(current,copy) and (None if before is None else list(before))==expected)
        return True
    def current_graph(self):
        self.guard();self.current_metadata()
        with read_scope() as reads:
            reports=self.ownership.read(owned=self.owned_paths());self.require_membership(reads)
        return reports
    def require_membership(self,reads):
        need(type(reads) is set and self.ownership is not None)
        # Exact end-owner paths are separately typed, reopened and bounded.
        # Merely listing them never makes an unknown file an original read.
        self.archive.selected_guard()
        for reference in self.archive.state['records']:self.archive.copy(reference)
        for owner in self.processes.values():
            if owner.previous is not None:
                owner.decode(owner.store.read())
                if owner.state['fence'] is not None:owner.fence()
                elif owner.state['pending'] is not None:
                    need(owner.state['pending']['phase'] in ('opened','saved'));owner.frames.read(owner.state['pending'])
                if owner.os_store().read() is not None:owner.os_state()
        for owner in self.sessions.values():
            if owner.previous is not None:
                owner.decode(owner.store.read())
                for reference,key in zip(owner.state['records'],('sdk','installed')):owner.original(reference,key)
                if owner.os_store().read() is not None:owner.os_state()
        # Current SDK/InstalledBinding stores are independently known from the
        # caller's selected canonical target map. Actual reads, never copied
        # envelope digests, provide their membership here.
        for info in self.context['roles'].values():
            session=self.runtime.adapter.read_session(info['target'])
            actual=PrivateFeatureState(self.runtime.state_path(info['target'])).read();need(same(session,actual))
            self.runtime.adapter._binding_store(info['target']).read()
        found=self.inventory()
        need(found<=reads)
        return True
    @operation
    def freeze(self,phase):
        self.guard()
        if self.archive.state['phase']=='selected':
            ownership,reads=AssetsOwnership.capture(self.context,self.locks,self.archive,owned=self.owned_paths())
            self.archive.paths=[PrivateFeatureState(Path(path)) for path in sorted(ownership.copies)]
            self.archive.metadata_pins=deepcopy(ownership.metadata_pins)
            self.ownership=ownership;self.archive.begin(phase)
        need(self.archive.state['phase'] in ('freezing','validated'));self.archive.freeze()
        self.ownership=AssetsOwnership(self.context,self.archive.copies(),self.locks,self.archive)
        self.current_graph()
        self.current_metadata();return deepcopy(self.archive.previous)
    @operation
    def advance(self):
        self.guard();need(self.archive.state['phase'] in ('validated','retiring','complete'))
        if self.archive.state['phase']=='complete':self.completed();return True
        # The selected Actor is stopped first. Primary cannot consume a peer's
        # issued intent as absence; both stage0 quiet windows must be original.
        for role in ('actor','primary'):
            process=self.processes[role]
            if process.state is None:process.prepare()
            if process.state['phase']=='prepared':process.stop()
            if not process.advance():return False
        for role in ('actor','primary'):
            if not self.sessions[role].finish():return False
        self.retire_metadata();return True
    def end_originals(self):
        for role in ('actor','primary'):self.processes[role].completed()
        for role in ('actor','primary'):self.sessions[role].completed()
    @operation
    def retire_metadata(self):
        self.guard();self.end_originals();self.current_metadata()
        a=self.archive;need(a.state['phase'] in ('validated','retiring','complete'))
        if a.state['phase']=='complete':self.completed();return
        self.current_graph()
        leases=[EmoteOriginalLease(root,[p.path for p in a.paths]+[a.store.path]) for root in self.ownership.roots]
        a.state['phase']='retiring';a.save()
        while a.state['retired']<len(a.paths):
            index=a.state['retired'];path=a.paths[index];copy=a.copy(a.state['records'][index])
            # A lost discard return is recovered only for this exact next CAS
            # position; no later disappearance or foreign replacement adopted.
            current=path.read();need(current is None or same(current,copy))
            self.guard();self.end_originals();self.current_metadata()
            for lease in leases:lease.guard()
            if current is not None:path.discard(copy)
            need(path.read() is None)
            for lease in leases:lease.guard()
            a.state['retired']+=1;a.save()
        a.state['phase']='complete';a.save();self.completed()
    def completed(self):
        self.guard();need(self.archive.state['phase']=='complete');self.end_originals();self.current_graph()
        return dict(performed=True,localProcessesEnded=True,sdkSessionsAbsent=True,
            serverRestoration='original-normal-delete-and-blob-baseline',wholeAssetsComplete=False,
            byteDecoderRetirementProven=False,globalPoolRetirementProven=False,gpuRetirementProven=False)


def completed_replay(runtime,run,fixture_url,ticket,roles,locks):
    """Pure current-files route; never reconstruct a live SDK/source factory.

    Explicit normal target mapping is still supplied independently. Pending,
    missing or foreign end context refuses rather than becoming empty cleanup.
    """
    from ios.adapters.assets_end_selection import archive
    from ios.adapters.assets_selected_runtime import SelectedAssetsRuntime
    selected=archive(runtime,run,fixture_url,ticket,roles,locks)
    need(selected.state is not None and selected.state['phase']=='complete')
    readonly_runtime=SelectedAssetsRuntime(runtime.adapter,selected,monotonic=runtime.monotonic,epoch_ms=runtime.epoch_ms)
    return AssetsPairedLocalEnd(readonly_runtime,selected,locks).completed()
