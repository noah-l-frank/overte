"""One-use retained Actor history replay before the next source-lock turn.

Only immutable originals cross the unlocked interval. Three actual owners and
their graphs remain pinned; the Primary scheduling journal may advance freely.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
import threading

from adapters.native_feature_observation import need
from overte_phone_script_history import same,unpack
from overte_phone_snapshots_constructor_history import graph_digest
from overte_phone_snapshots_history_pass import SnapshotHistoryReadPass,signature
from overte_phone_snapshots_role import role_state


class SnapshotActorHistoryPass(SnapshotHistoryReadPass):
    def __init__(self,actor,role,prepared):
        f=actor.feature;f.lock.assert_held()
        need(actor.read_ready_mode() is not None and f.role==role.role=='actor'
            and f.state['phase']=='cleaned' and f.state['current'] is f.state['handoff'] is None
            and actor.state['phase']=='watching' and actor.state['pending'] is None
            and role.state['phase']=='ready' and role.state['pending'] is None
            and not role.system and not role._host_publication and getattr(f,'_system_scope',None) is None)
        self.actor,self.role,self.feature=actor,role,f
        self.prepared=deepcopy(prepared);self.prepared_digest=graph_digest(self.prepared)
        self.stores=(f.store,actor.store,role.store)
        self.paths=tuple(store.path for store in self.stores)
        self.headers=tuple(deepcopy(prepared[key]) for key in ('feature','actor','role'))
        need(all(header is not None for header in self.headers))
        self.signatures=tuple(signature(path) for path in self.paths)
        self.root,self.run,self.binding,self.configuration=f.root,f.run,deepcopy(f.binding),deepcopy(f.config)
        self.root_identity=signature(self.root)[:5]
        need(self.root.resolve(strict=True)==self.root)
        self.guard_callback=f.guard;self.scope=getattr(f.adapter,'_existing_input_scope',None)
        self.scope_value=deepcopy(self.scope)
        self.graphs=tuple(graph_digest(value) for value in (f.state,actor.state,role.state,role.frames))
        self.process,self.thread=os.getpid(),threading.get_ident()
        self.closed=self.started=self.replaying=False;self.digest=None
        self.files={};self.file_seal=self.file_seal_sha256=None
        self._headers();self._memory()

    def _headers(self,*,metadata_only=False):
        f,a,r=self.feature,self.actor,self.role
        need(type(metadata_only) is bool and (not metadata_only or self.replaying and self.started and f.lock._owner is None)
            and not self.closed and os.getpid()==self.process and threading.get_ident()==self.thread
            and (f.store,a.store,r.store)==self.stores and tuple(store.path for store in self.stores)==self.paths
            and f.root==self.root and f.run==self.run and f.role==r.role=='actor'
            and self.root.resolve(strict=True)==self.root and signature(self.root)[:5]==self.root_identity
            and same(f.binding,self.binding) and same(f.config,self.configuration)
            and f.guard is self.guard_callback and getattr(f,'_system_scope',None) is None
            and getattr(f.adapter,'_existing_input_scope',None) is self.scope and same(self.scope,self.scope_value)
            and not r.system and not r._host_publication)
        for store,header,pinned,current in zip(self.stores,self.headers,self.signatures,(f.previous,a.previous,r.previous)):
            need(same(current,header) and signature(store.path)==pinned)
            # During the complete host replay, every guard still checks the
            # exact owner inode and change metadata. Actual JSON owner reads
            # bracket that replay and remain mandatory at every locked check.
            if not metadata_only:need(same(store.read(),header))
            need(signature(store.path)==pinned)
        return True

    def _memory(self,*,verify_graph=True):
        f,a,r=self.feature,self.actor,self.role
        need(graph_digest(self.prepared)==self.prepared_digest
            and same(f.state,unpack(self.headers[0]['payload'])[0])
            and same(a.state,unpack(self.headers[1]['payload'])[0])
            and same(r.state,role_state(self.headers[2],self.binding,self.run,'actor'))
            and tuple(graph_digest(value) for value in (f.state,a.state,r.state))==self.graphs[:3])
        if verify_graph:need(graph_digest(r.frames)==self.graphs[3])

    def guard(self):
        need(self.feature.lock._owner is None and self.started)
        return self._headers(metadata_only=self.replaying)

    def read(self):
        try:
            need(not self.closed and not self.started and self.feature.lock._owner is None)
            self.started=True;self.guard();self._memory();self.replaying=True
            try:frames=self.role._restore_historical_originals(self.guard,receipts=self)
            finally:self.replaying=False
            self.guard();self._memory()
            # Serialized originals reorder JSON object keys. Compare their
            # meaning, keeping the separate same-call memory graph seal.
            need(same(frames,self.role.frames))
            self.file_seal=tuple(self.files.items());self.file_seal_sha256=self._files_digest(self.file_seal)
            self.digest=self.graphs[3]
            return self.digest
        except BaseException:
            self.close();raise

    def check(self):
        self.feature.lock.assert_held();need(self.started and self.digest==self.graphs[3])
        self._headers();self._memory();self._verify_files()

    def actor_unchanged(self):
        """Current Role work cannot alter the previous quiet/lifecycle graph."""
        self.feature.lock.assert_held()
        need(graph_digest(self.actor.state)==self.graphs[1]
            and same(self.actor.previous,self.headers[1])
            and signature(self.actor.store.path)==self.signatures[1]
            and same(self.actor.store.read(),self.headers[1])
            and signature(self.actor.store.path)==self.signatures[1])

    def finish(self):
        """Requalify after fresh native/phase callbacks; consume no current fact."""
        f,r=self.feature,self.role
        self.check();r.bound();r.history_authority()
        status=f.phase.status(self.prepared['phase'])
        for key in ('fixturePhaseVersion','instance','runId','area','createdEpochMs','activations'):
            need(same(status[key],self.prepared['phase'][key]))
        if status['active']:self.actor.cleanup_phase(status,self.prepared['phase'])
        self.check();return status
