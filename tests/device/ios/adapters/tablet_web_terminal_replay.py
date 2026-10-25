"""One lock-scoped checked Tablet original graph, never current authority.

Use the existing neutral original-inventory/read-membership primitives. The
actual complete decoder runs before this handoff; every reuse rechecks every
source file and only the exact declared process/OS/CAS metadata may change.
No freshness, phase authority, OS receipt or input result is cached here.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from adapters.native_feature_observation import need
from adapters.original_file_reads import scope as read_scope,record
from adapters.script_feature.history import same
from ios.adapters.emote_original_lease import EmoteOriginalLease


class TabletTerminalReplay:
    def __init__(self,terminal,mutable):
        from ios.adapters.tablet_web_terminal import TabletWebTerminal
        need(type(terminal) is TabletWebTerminal and getattr(terminal,'checked_replay',None) is None)
        f=terminal.feature;f.clock();terminal.lock.assert_held()
        self.terminal,self.feature,self.mutable=terminal,f,list(mutable)
        roots={f.root}
        if f.screen is not None:roots.add(Path(f.screen['artifactRoot']))
        self.leases=[EmoteOriginalLease(root,self.mutable) for root in roots]
        with read_scope(fresh=True) as reads:
            self.seal=terminal.replay();self.floors=terminal.phase_floors()
            self.carrier=terminal.store.read();self.feature_carrier=f.store.read()
            need(same(self.carrier,terminal.previous))
        need(not set(self.mutable)&reads and all(any(path==root or path.is_relative_to(root) for root in roots) for path in reads))
        self.pins={path:EmoteOriginalLease.signature(path.lstat()) for path in reads}
        self.state=deepcopy(terminal.state);self.saved,self.feature_state=deepcopy(f.saved),deepcopy(f.state)
        self.identity=(f.runtime,f.runtime.adapter,f.selector,f.root,f.run,f.role,f.store.path,terminal.store.path,terminal.lock)
        self.config=deepcopy(dict(binding=f.binding,setup=f.setup,origins=f.origins,screen=f.screen));self.active=True
        for lease in self.leases:lease.guard()
    def guard(self):
        t,f=self.terminal,self.feature;t.lock.assert_held();f.clock()
        need(self.active and getattr(t,'checked_replay',None) is self and t.feature is f
            and self.identity==(f.runtime,f.runtime.adapter,f.selector,f.root,f.run,f.role,f.store.path,t.store.path,t.lock)
            and same(self.config,dict(binding=f.binding,setup=f.setup,origins=f.origins,screen=f.screen))
            and same(t.previous,self.carrier) and same(t.state,self.state)
            and same(f.saved,self.saved) and same(f.state,self.feature_state)
            and same(t.store.read(),self.carrier) and same(f.store.read(),self.feature_carrier))
        for lease in self.leases:lease.guard()
        for path,signature in self.pins.items():
            need(EmoteOriginalLease.signature(path.lstat())==signature);record(path)
        return deepcopy(self.seal)


@contextmanager
def checked(terminal,mutable):
    proof=TabletTerminalReplay(terminal,mutable);terminal.checked_replay=proof
    try:proof.guard();yield proof
    finally:
        try:proof.guard()
        finally:proof.active=False;terminal.checked_replay=None
