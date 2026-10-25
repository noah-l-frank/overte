"""One live capture's already validated immutable Final row prefix.

Only old component originals are reused. Every new row and every current group
is decoded normally. Entry and exit decode the complete original graph. No
quiet/public proof, native clock, transport, input or metadata CAS is cached.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import os
from pathlib import Path
from adapters.native_clock_join import digest
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.original_file_reads import record,scope as read_scope
from adapters.script_feature.history import canonical,same
from ios.adapters.emote_original_lease import EmoteOriginalLease


class FinalCapturePrefix:
    def __init__(self,owner):
        from ios.adapters.avatar_final import IOSAvatarFinal
        from ios.adapters.avatar_held_final import IOSAvatarHeldFinal
        need(type(owner) in (IOSAvatarFinal,IOSAvatarHeldFinal) and not owner.historical and getattr(owner,'_capture_prefix',None) is None)
        owner.bound();need(owner.state['pending'] is None)
        self.owner=owner;self.context=self.identity();self.rows=deepcopy(owner.state['rows'])
        self.next=owner.file(len(self.rows)+1).path if len(self.rows)<128 else None
        self.previous=canonical(owner.previous)
        need(self.next is None or not os.path.lexists(self.next))
        self.pins={};self.summary=None

    def identity(self):
        owner=self.owner
        for lock in owner.locks.values():lock.assert_held()
        return (type(owner),str(owner.root),str(owner.store.path),owner.run,owner.role,
            (type(owner.authority),id(owner.authority),owner.authority.run,type(owner.authority.client),id(owner.authority.client),owner.authority.client.url),
            tuple((role,id(owner.locks[role]),str(owner.locks[role].path)) for role in ('primary','actor')),
            canonical(dict(bindings=owner.bindings,inputs=owner.inputs)))

    def __enter__(self):
        owner=self.owner;owner._prefix_building=True
        roots={owner.root,owner.store.path.parent}
        for subject in ('primary','actor'):
            item=owner.input(subject);roots.add(Path(item['root']))
            roots.update(Path(path).parent for path in item['paths'].values())
        leases=[EmoteOriginalLease(root,[]) for root in sorted(roots)]
        try:
            with read_scope(fresh=True) as reads:
                actual=owner.parse(owner.previous) if owner.previous is not None else deepcopy(owner.state)
            for lease in leases:lease.guard()
            need(same(actual,owner.state) and canonical(owner.previous)==self.previous)
            self.summary=deepcopy(getattr(owner,'_prefix_summary',dict(last={},sequence=0,components={})))
            self.pins={path:EmoteOriginalLease.signature(path.lstat()) for path in reads}
        finally:
            owner._prefix_building=False
            if hasattr(owner,'_prefix_summary'):del owner._prefix_summary
        self.guard(owner.state);owner._capture_prefix=self;return self

    def guard(self,state):
        self.owner.bound()
        need(self.identity()==self.context and same(state['rows'][:len(self.rows)],self.rows)
            and len(state['rows'])>=len(self.rows))
        parents={path.parent for path in self.pins}
        def ancestors():
            for parent in parents:PrivateFeatureState(parent/'.avatar-final-prefix-parent')._parent()
        ancestors()
        for path,pin in self.pins.items():need(EmoteOriginalLease.signature(path.lstat())==pin)
        ancestors()
        if self.next is not None and os.path.lexists(self.next):
            index=len(self.rows)+1;pending=state['pending'];rows=state['rows']
            original=PrivateFeatureState(self.next).read();need(original is not None)
            if len(rows)>len(self.rows):
                ref=rows[index-1]['reference'];need(ref is not None and ref['index']==index and digest(original)==ref['sha256'])
            else:need(pending is not None and pending['index']==index and pending['value'] is not None and same(original,pending['value']))
        for path in self.pins:record(path)

    def resume(self,state):
        self.guard(state);return len(self.rows),deepcopy(self.summary)

    def __exit__(self,kind,value,traceback):
        owner=self.owner
        try:
            self.guard(owner.state)
        finally:owner._capture_prefix=None
        # A failed acquisition keeps its exact durable pending ownership. It
        # cannot become a successful capture merely because a prefix is valid.
        if kind is None:owner.parse(owner.previous);self.guard(owner.state)
