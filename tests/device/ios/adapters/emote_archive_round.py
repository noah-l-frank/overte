"""One historical decode round over an unchanged complete file inventory.

Only already decoded original derivations are reused. No live guard, pending
journal, query, source clock, OS state or metadata retirement is cached.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from pathlib import Path

from adapters.native_clock_join import digest
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.original_file_reads import record,scope as file_reads
from adapters.script_feature.history import canonical
from adapters.script_feature.lock import ScriptSourceLock
from adapters.pure_original_validation import inherited_scope as pure_round,PROFILE as PURE_PROFILE
from ios.adapters.emote_original_lease import EmoteOriginalLease

_ACTIVE=ContextVar('ios_emote_historical_archive_round',default=None)
LIMIT=8*1024*1024


class Round:
    def __init__(self,value,lock,primary_lock):
        need(type(value) is dict and {'artifactRoot','stateRoot'}<=set(value)
            and all(type(value[key]) is str for key in ('artifactRoot','stateRoot'))
            and isinstance(lock,ScriptSourceLock) and isinstance(primary_lock,ScriptSourceLock))
        lock.assert_held();primary_lock.assert_held()
        self.identity=digest(value);self.lock,self.primary_lock=lock,primary_lock;self.rows={};self.bytes=0
        roots={Path(value['artifactRoot']),Path(value['stateRoot']),lock.path.parent,primary_lock.path.parent}
        selected=[]
        for root in sorted(roots,key=lambda path:(len(path.parts),str(path))):
            PrivateFeatureState(root/'emote-archive-round-boundary')._parent()
            if not any(root.is_relative_to(parent) for parent in selected):selected.append(root)
        self.leases=[EmoteOriginalLease(root,[]) for root in selected];self.guard()

    def guard(self):
        self.lock.assert_held();self.primary_lock.assert_held()
        for lease in self.leases:lease.guard()


@contextmanager
def scope(value,*,lock,primary_lock):
    current=_ACTIVE.get()
    if current is not None:
        need(current.identity==digest(value) and current.lock is lock and current.primary_lock is primary_lock)
        current.guard();yield;current.guard();return
    current=Round(value,lock,primary_lock);token=_ACTIVE.set(current)
    try:
        with pure_round(PURE_PROFILE,current.guard):yield
    finally:
        try:current.guard()
        finally:_ACTIVE.reset(token)


@contextmanager
def validation_batch(value,*,lock,primary_lock):
    """Share only pure validation across separately reopened snapshots.

    Typed derivation memos keep their individual snapshot boundaries. The
    enclosing complete original inventory forbids all writes until return.
    """
    current=Round(value,lock,primary_lock)
    with pure_round(PURE_PROFILE,current.guard):yield


def derived(owner,reference,decode):
    current=_ACTIVE.get()
    if current is None or not owner.historical:return decode()
    need(owner.lock is current.lock and owner.primary_lock is current.primary_lock)
    current.guard()
    key=canonical(dict(owner=type(owner).__module__+'.'+type(owner).__qualname__,path=str(owner.store.path),
        envelope=owner.envelope(dict(records=[],abandoned=[],pending=None)),reference=reference))
    if key in current.rows:
        value,reads,_size=current.rows[key]
        for path in reads:record(path)
        result=deepcopy(value);current.guard();return result
    # The complete pre-read inventory already exists. Every cold parser still
    # reads and validates actual bytes; the unchanged post-inventory prevents
    # a file changed after its first read from entering the memo.
    with file_reads(fresh=True) as reads:value=decode()
    current.guard();size=len(canonical(value))
    if size<=LIMIT:
        while current.rows and (current.bytes+size>LIMIT or len(current.rows)>=512):
            _,(_,_,removed)=current.rows.popitem();current.bytes-=removed
        current.rows[key]=(deepcopy(value),set(reads),size);current.bytes+=size
    for path in reads:record(path)
    return value


def component_read(owner,value,decode):
    """Scope pure original validation during a current component's read.

    The current decoder itself always runs, including pending/orphan checks.
    No live derivation is memoized. Its original-only validators may reuse
    identical successful arguments until the complete unchanged exit census.
    Scope exit precedes every caller's metadata save or new acquisition.
    """
    if owner.historical or _ACTIVE.get() is not None:return decode()
    boundary=dict(artifactRoot=str(owner.root),stateRoot=str(owner.store.path.parent),
        component=type(owner).__module__+'.'+type(owner).__qualname__,path=str(owner.store.path),original=value)
    with scope(boundary,lock=owner.lock,primary_lock=owner.primary_lock):return decode()
