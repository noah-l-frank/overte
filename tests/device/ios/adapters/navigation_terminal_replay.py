"""Local checked-data handoff for one actual historical terminal traversal.

This has no persistent cache and grants no live freshness or input authority.
Every consumer rechecks exact actual original files and the source inventory.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy

from adapters.native_feature_observation import need
from adapters.original_file_reads import scope as read_scope
from adapters.script_feature.history import same
from ios.adapters.emote_original_lease import EmoteOriginalLease
from ios.adapters.navigation_observation_owner import validation_round


class NavigationTerminalReplay:
    def __init__(self,terminal,mutable):
        from ios.adapters.navigation_terminal import NavigationTerminal
        need(type(terminal) is NavigationTerminal);f=terminal.flow;f.lock.assert_held()
        self.terminal=terminal;self.flow=f;self.mutable=list(mutable)
        self.leases=[EmoteOriginalLease(root,self.mutable) for root in {f.root,f.store.path.parent}]
        # Empty the existing predecessor round for this actual full traversal.
        # Its exit PNG checks belong to this same actual-read collection.
        with read_scope(fresh=True) as reads:
            with validation_round(fresh=True):self.seal=terminal.replay()
            need(same(terminal.store.read(),terminal.previous) and same(f.store.read(),f.previous))
        need(not set(self.mutable)&reads)
        self.pins={path:EmoteOriginalLease.signature(path.lstat()) for path in reads}
        self.carrier=deepcopy(terminal.previous);self.state=deepcopy(terminal.state)
        self.feature=deepcopy(f.previous);self.feature_state=deepcopy(f.state)
        self.context=(f.run,f.role,f.selector,f.root,f.store.path,terminal.store.path,f.lock,f.runtime,f.runtime.adapter)
        self.active=True
        self.guard()

    def guard(self):
        t,f=self.terminal,self.flow;f.lock.assert_held();need(self.active)
        need(self.context==(f.run,f.role,f.selector,f.root,f.store.path,t.store.path,f.lock,f.runtime,f.runtime.adapter)
            and t.flow is f and t.lock is f.lock and same(t.previous,self.carrier) and same(t.state,self.state)
            and same(f.previous,self.feature) and same(f.state,self.feature_state)
            and same(t.store.read(),self.carrier) and same(f.store.read(),self.feature))
        for lease in self.leases:lease.guard()
        for path,signature in self.pins.items():need(EmoteOriginalLease.signature(path.lstat())==signature)
        return deepcopy(self.seal)


@contextmanager
def checked(terminal,mutable):
    proof=NavigationTerminalReplay(terminal,mutable)
    try:yield proof
    finally:
        try:proof.guard()
        finally:proof.active=False
