"""Carry a closed paired census through the exact fresh fence to normal Stop.

The only admission is one successfully decoded final-fence append per actual
Source owner plus this exact process coordinator. Nothing names a namespace-
wide mutable region. An unknown file cannot join a later inventory snapshot.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy

from adapters.native_clock_join import digest
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import same
from ios.adapters.emote_original_lease import EmoteOriginalLease
from ios.adapters.world_web_rooted_inventory import WorldWebRootedInventory,inventory
from ios.adapters.world_web_sources import WorldWebSources


class WorldWebStopInventory:
    def __init__(self,census,process,parts):
        from ios.adapters.world_web_process_end import WorldWebProcessEnd
        from ios.adapters.world_web_fence import original
        need(type(census) is WorldWebRootedInventory and type(process) is WorldWebProcessEnd)
        self.census,self.process=census,process;terminal=census.terminal
        need(process.flow is (terminal.flow if process.role=='primary' else terminal.actor))
        need(terminal.state['phase']=='ending' and terminal.state['seal'] is not None
            and terminal.state['end'] is None and len(terminal.state['records'])==2 and terminal.state['pending'] is None)
        process.bound();need(process.state['phase']=='fencing' and process.state['fence'] is None
            and process.state['processSha256'] is None and digest(original(parts['retirement']))==process.state['sceneSha256'])
        self.initial_process=deepcopy(process.state);self.sources=[]
        for name in ('source','peer'):
            source=parts[name]
            if source is None:continue
            need(type(source) is WorldWebSources and not source.historical and source.version>=4
                and source.store.path in census.paths and source.run==process.run and source.state['pending'] is None)
            source.lock.assert_held()
            need(same(source.store.read(),source.previous) and same(source.envelope(source.state),source.previous))
            self.sources.append((name,source,deepcopy(source.state)))
        need(len(self.sources)==(1 if process.role=='primary' else 2))
        self.heads={source.store.path for _name,source,_state in self.sources}
        self.paths=set(census.paths);self.pins=dict(census.signatures);self.expected=None
        # No Source has changed yet. Process.prepare may have created only its
        # actual typed coordinator after the earlier successful whole census.
        self.initial_guard()

    def initial_guard(self):
        census=self.census;process=self.process
        need(census.current_roots()==census.roots)
        process.bound();need(same(process.state,self.initial_process))
        need(inventory(census.roots)-census.owned()-{process.store.path}==self.paths-{process.store.path})
        for path,signature in self.pins.items():
            need(EmoteOriginalLease.signature(path.lstat())==signature)
        return True

    def freeze(self,fresh,reads):
        """Called inside the successful Source append rounds, before they close."""
        need(self.expected is None and type(reads) is set)
        process=self.process;process.bound();need(same(process.state,self.initial_process))
        current={}
        for name,source,old in self.sources:
            need(source._write_round is not None and source._round is not None)
            source.guard_originals();source.guard_saved_state()
            state=source.state;reference=fresh['primary' if name=='source' else 'own']
            need(state['pending'] is None and same(state['interrupted'],old['interrupted'])
                and len(state['records'])==len(old['records'])+1
                and same(state['records'][:-1],old['records']) and same(state['records'][-1],reference)
                and same(source.store.read(),source.previous) and same(source.envelope(state),source.previous))
            # The actual Source writer accepted this complete record before
            # admitting it to its guarded round. Its literal private frame is
            # checked here; no host model or expected native value supplies it.
            frame=source._round[2][-1]
            need(frame['index']==reference['index'] and frame['label']=='final-fence'
                and frame['phaseBefore']['active'] is False and frame['phaseAfter']['active'] is False)
            # Source pins deliberately have their own field layout. Verify
            # that layout, then retain the full census signature (including
            # gid) around the actual current head read. Never mix layouts or
            # exempt a head merely because its CAS append was expected.
            for path,signature in source.original_pins(source.previous).items():
                before=EmoteOriginalLease.signature(path.lstat())
                need(source.original_signature(path)==signature)
                if path==source.store.path:
                    need(same(source.store.read(),source.previous) and same(source.envelope(state),source.previous))
                need(EmoteOriginalLease.signature(path.lstat())==before and source.original_signature(path)==signature)
                current[path]=before
            source.guard_originals();source.guard_saved_state()
        need(set(current)-self.paths<=reads)
        need(self.census.current_roots()==self.census.roots)
        need(inventory(self.census.roots)-self.census.owned()-{process.store.path}==(self.paths|set(current))-{process.store.path})
        for path,signature in self.pins.items():
            if path not in self.heads:need(EmoteOriginalLease.signature(path.lstat())==signature)
        self.pins.update(current);self.paths.update(current)
        self.expected=process.envelope(dict(self.initial_process,phase='stop-issued',fence=deepcopy(fresh)))
        return True

    def guard(self):
        need(self.expected is not None)
        process=self.process;process.bound()
        need(same(process.previous,self.expected) and same(process.store.read(),self.expected))
        need(self.census.current_roots()==self.census.roots
            and inventory(self.census.roots)-self.census.owned()-{process.store.path}==self.paths-{process.store.path})
        for path,signature in self.pins.items():
            if path==process.store.path:continue
            PrivateFeatureState(path)._parent();need(EmoteOriginalLease.signature(path.lstat())==signature)
        return True
