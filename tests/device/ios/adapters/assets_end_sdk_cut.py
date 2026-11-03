"""Actual full original graph/membership around the existing SDK DELETE cut."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import need
from adapters.original_file_reads import collect as read_scope
from adapters.script_feature.history import same
from ios.adapters.assets_end_graph import inventory
from ios.adapters.emote_original_lease import EmoteOriginalLease


class AssetsSDKCut:
    def __init__(self,session):
        from ios.adapters.assets_end_sdk import AssetsSDKEnd
        need(type(session) is AssetsSDKEnd and session.state['phase']=='prepared')
        self.session,self.tx,self.expected=session,session.process.tx,None
        self.mutable={session.store.path,session.os_store().path}
        leases=[EmoteOriginalLease(root,[]) for root in self.tx.ownership.roots]
        with read_scope() as reads:
            session.bound();session.qualify();self.tx.current_graph()
        for lease in leases:lease.guard()
        self.paths=self.tx.inventory()-self.mutable
        self.pins={path:EmoteOriginalLease.signature(path.lstat()) for path in self.paths}
    def guard_preparing(self):
        self.tx.guard()
        for path,pin in self.pins.items():need(EmoteOriginalLease.signature(path.lstat())==pin)
    def issued(self,reads):
        need(type(reads) is set and self.expected is None);self.guard_preparing()
        s=self.session;need(s.state['phase']=='delete-issued')
        current=self.tx.inventory();need(current<=self.paths|self.mutable|reads)
        self.paths=current-self.mutable;self.pins={path:EmoteOriginalLease.signature(path.lstat()) for path in self.paths}
        self.expected=deepcopy(s.previous);self.os=deepcopy(s.os_store().read());self.guard()
    def guard(self):
        need(self.expected is not None);self.guard_preparing();s=self.session
        need(same(s.store.read(),self.expected) and same(s.previous,self.expected)
            and same(s.envelope(s.state),self.expected) and same(s.os_store().read(),self.os)
            and self.tx.inventory()-self.mutable==self.paths)
        # Constructor established the complete typed graph before the fresh
        # OS acquisition. Exact immutable pins/membership and current copied
        # owner bytes above carry that proof; no heavy graph re-decode enters
        # the unchanged1.5-second SDK DELETE freshness window.
        self.tx.current_metadata();return True
