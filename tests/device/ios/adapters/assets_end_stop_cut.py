"""Carry actual full Assets proof across its fresh once-only Stop fence.

No original verdict is inferred from pins. Full typed graph/membership is
established before the fresh native acquisition; exact immutable inventory and
known own WAL transitions guard that already established proof until Stop.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import need
from adapters.original_file_reads import collect
from adapters.script_feature.history import same
from ios.adapters.assets_end_graph import inventory
from ios.adapters.emote_original_lease import EmoteOriginalLease
from ios.adapters.installed_code import cleanup_record


class AssetsStopCut:
    def __init__(self,owner):
        from ios.adapters.assets_end_process import AssetsProcessEnd
        need(type(owner) is AssetsProcessEnd and owner.state is not None and owner.state['phase']=='prepared')
        self.owner,self.tx=owner,owner.tx;self.frozen=owner.archive.frozen_identity();self.fence_value=None;self.issued=None
        # This is the exact InstalledBinding this selected normal Stop may
        # advance via the shared verified bound→retiring→retired grammar.
        self.binding_store=owner.runtime.adapter._binding_store(owner.target)
        self.binding_original=deepcopy(self.binding_store.read());need(self.binding_original is not None)
        leases=[EmoteOriginalLease(root,[]) for root in self.tx.ownership.roots]
        with collect() as reads:
            self.tx.current_graph()
            self.binding_store.read()
            if owner.state['fence'] is not None:owner.fence()
            elif owner.state['pending'] is not None:
                need(owner.state['pending']['phase'] in ('opened','saved'));owner.frames.read(owner.state['pending'])
        for lease in leases:lease.guard()
        self.mutable={owner.store.path,self.binding_store.path};self.paths=self.tx.inventory()-self.mutable
        self.pins={p:EmoteOriginalLease.signature(p.lstat()) for p in self.paths};self.expected_new=set();self.unchanged()
    def unchanged(self):
        self.owner.bound();need(self.owner.archive.frozen_identity()==self.frozen)
        self.tx.current_metadata()
        for path,pin in self.pins.items():need(EmoteOriginalLease.signature(path.lstat())==pin)
        current=self.binding_store.read();need(current is not None)
        need(same(cleanup_record(self.binding_original,current),current))
        # A planned exact own original path is a responsibility exception, not
        # read/absence evidence. acquired() must validate its actual inode/body
        # before the cut may authorize any Stop.
        need(self.tx.inventory()-self.mutable<=self.paths|self.expected_new)
        return True
    def original_intent(self,wire):
        self.owner.frames.original(wire);need(wire['index']==1 and self.fence_value is None)
        path=self.owner.frames.path(wire);need(not self.expected_new or self.expected_new=={path});self.unchanged()
        self.expected_new={path}
    def acquired(self,value):
        self.unchanged();need(self.fence_value is None and same(self.owner.fence(),value))
        with collect() as reads:
            self.owner.fence();self.owner.frames.read(self.owner.frames.expand(self.owner.state['fence']))
        found=self.tx.inventory()-self.mutable
        need(found<=self.paths|reads and self.expected_new<=reads)
        self.paths=found;self.pins={p:EmoteOriginalLease.signature(p.lstat()) for p in found}
        self.expected_new=set();self.fence_value=deepcopy(value);self.unchanged()
    def issue(self):
        self.unchanged();need(self.fence_value is not None)
        self.issued=self.owner.envelope(dict(self.owner.state,phase='stop-issued'))
    def guard(self):
        need(self.issued is not None and same(self.owner.previous,self.issued)
            and same(self.owner.envelope(self.owner.state),self.issued))
        self.unchanged();need(self.tx.inventory()-self.mutable==self.paths)
        need(same(self.owner.fence(),self.fence_value));return True
