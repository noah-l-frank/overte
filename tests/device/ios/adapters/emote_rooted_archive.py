"""Reopen an actual rooted cleanup graph without an SDK or live guard.

Only component envelopes and their latest committed reference are copied.
Every contributing native/input/file/pixel original is still fully decoded.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from contextlib import contextmanager
import hashlib
import marshal
from pathlib import Path
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import context
from adapters.original_file_reads import record as file_read,scope as file_reads
from adapters.script_feature.history import same,canonical
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from ios.adapters.emote_keys import IOSEmoteKeys
from ios.adapters.emote_restoration_frames import IOSEmoteRestorationFrames
from ios.adapters.emote_retirement import Frozen
from ios.adapters.emote_rooted_retirement import (IOSEmoteRootedNativeRetirement,
    IOSEmoteRootedRenderedRetirement,IOSEmoteRootedKeyedRetirement)
from ios.adapters.emote_rooted_scene_retirement import IOSEmoteRootedSceneRetirement
from ios.adapters.emote_archive_round import scope as original_round,LIMIT as ROUND_LIMIT

VERSION=1
PARTS={'native','frames','rendered','keys','keyed'}


def capture(owner,reference):
    need(type(owner) is IOSEmoteRootedKeyedRetirement and not owner.historical)
    owner.lock.assert_held();owner.primary_lock.assert_held()
    need(owner.state['pending'] is None and owner.state['records'] and same(reference,owner.state['records'][-1]))
    rendered=owner.rendered_owner
    parts=dict(native=rendered.native_owner,frames=rendered.frames_owner,rendered=rendered,keys=owner.keys_owner,keyed=owner)
    originals={}
    for name,part in parts.items():
        original=part.store.read();need(original is not None and same(original,part.previous)
            and part.state.get('pending') is None)
        originals[name]=deepcopy(original)
    value=dict(iosEmoteRootedArchiveVersion=VERSION,runId=owner.run,role=owner.role,binding=deepcopy(owner.binding),
        primaryBinding=deepcopy(owner.primary_binding),artifactRoot=str(owner.root),stateRoot=str(owner.store.path.parent),
        fixtureUrl=owner.fixture_url,phaseInstance=owner.phase_instance,imagePolicy=deepcopy(owner.policy),
        sourceLock=str(owner.lock.path),primaryLock=str(owner.primary_lock.path),reference=deepcopy(reference),
        paths={name:str(part.store.path) for name,part in parts.items()},owners=originals)
    for name,part in parts.items():need(same(part.store.read(),originals[name]))
    return value


def reopen(value,*,lock,primary_lock):
    exact(value,{'iosEmoteRootedArchiveVersion','runId','role','binding','primaryBinding','artifactRoot','stateRoot',
        'fixtureUrl','phaseInstance','imagePolicy','sourceLock','primaryLock','reference','paths','owners'})
    need(type(value['iosEmoteRootedArchiveVersion']) is int and value['iosEmoteRootedArchiveVersion']==VERSION
        and value['role'] in ('primary','actor') and isinstance(lock,ScriptSourceLock) and isinstance(primary_lock,ScriptSourceLock))
    lock.assert_held();primary_lock.assert_held();identifier(value['runId']);identifier(value['phaseInstance'])
    binding=context(value['binding']);primary=context(value['primaryBinding'])
    root=Path(value['artifactRoot']);state_root=Path(value['stateRoot'])
    need(root.is_absolute() and root.resolve()==root and root.is_dir()
        and state_root.is_absolute() and state_root.resolve()==state_root and state_root.is_dir()
        and str(lock.path)==value['sourceLock'] and lock.path==state_root/'script-feature-sources.lock'
        and str(primary_lock.path)==value['primaryLock'])
    exact(value['paths'],PARTS);exact(value['owners'],PARTS)
    paths={name:Path(path) for name,path in value['paths'].items()}
    need(len(set(paths.values()))==len(PARTS) and all(path.is_absolute() and path.resolve()==path
        and path.parent==state_root for path in paths.values()))
    originals=value['owners'];need(all(type(original) is dict for original in originals.values()))
    settings=dict(root=root,binding=binding,run=value['runId'],role=value['role'],lock=lock)
    native_paths=originals['native'].get('paths');exact(native_paths,{'sources','peers','files','entities','pointers'})
    need(type(native_paths['sources']) is str and Path(native_paths['sources']).parent==primary_lock.path.parent)
    native=IOSEmoteRootedNativeRetirement(Frozen(paths['native'],originals['native']),root,binding,primary,value['runId'],
        value['role'],value['fixtureUrl'],value['phaseInstance'],lock,primary_lock,value['imagePolicy'],native_paths,lambda:True,historical=True)
    frames=IOSEmoteRestorationFrames.archive(originals['frames'],store=Frozen(paths['frames'],originals['frames']),**settings)
    rendered=IOSEmoteRootedRenderedRetirement(Frozen(paths['rendered'],originals['rendered']),native,frames,historical=True)
    keys=IOSEmoteKeys.archive(originals['keys'],store=Frozen(paths['keys'],originals['keys']),**settings)
    keyed=IOSEmoteRootedKeyedRetirement(Frozen(paths['keyed'],originals['keyed']),rendered,keys,historical=True)
    need(keyed.state['pending'] is None and keyed.state['records'] and same(value['reference'],keyed.state['records'][-1]))
    return keyed


def read(value,*,lock,primary_lock):
    with original_round(value,lock=lock,primary_lock=primary_lock):
        return IOSEmoteRootedSceneRetirement(reopen(value,lock=lock,primary_lock=primary_lock)).read(value['reference'])


class CheckedGraphs:
    """Same-read actual typed results; never saved or used as fresh data."""
    def __init__(self,round_,boundary,lock,primary_lock):
        self.round,self.boundary,self.lock,self.primary_lock=round_,boundary,lock,primary_lock
        self.active,self.rows,self.bytes=True,{},0

    def guard(self):need(self.active);self.round.guard()

    @staticmethod
    def key(value):
        # Unlike JSON, this cannot alias tuples or mapping/list subclasses.
        # Unsupported inputs take the literal parser instead of a cache hit.
        try:return hashlib.sha256(marshal.dumps(value,4)).digest()
        except (ValueError,TypeError,OverflowError,RecursionError):return None

    def read(self,value):
        self.guard();need(type(value) is dict and all(value.get(key)==self.boundary[key]
            for key in ('artifactRoot','stateRoot','sourceLock','primaryLock')))
        key=self.key(value)
        if key is not None and key in self.rows:
            actual,reads,_size=self.rows[key]
            for path in reads:file_read(path)
            result=deepcopy(actual);self.guard();return result
        with file_reads(fresh=True) as reads:
            actual=IOSEmoteRootedSceneRetirement(reopen(value,lock=self.lock,primary_lock=self.primary_lock)).read(value['reference'])
        self.guard();size=len(canonical(actual))
        if key is not None and size<=ROUND_LIMIT:
            while self.rows and self.bytes+size>ROUND_LIMIT:
                _removed,(_value,_reads,count)=self.rows.popitem();self.bytes-=count
            self.rows[key]=(deepcopy(actual),set(reads),size);self.bytes+=size
        for path in reads:file_read(path)
        return actual


@contextmanager
def grouped(values,*,lock,primary_lock):
    """Run every literal snapshot decoder under one unchanged inventory.

    Only identical typed original subgraphs are reused. Old metadata cursors,
    pending journals and dependency membership remain independently checked.
    """
    need(type(values) is list and 1<=len(values)<=96 and all(type(value) is dict for value in values))
    fields=('artifactRoot','stateRoot','sourceLock','primaryLock')
    boundary={key:values[0].get(key) for key in fields}
    need(all(type(item) is str for item in boundary.values())
        and all(all(value.get(key)==boundary[key] for key in fields) for value in values))
    # These hashes identify this operation's scope; all facts below still come
    # from actual typed original reads, not the hashes or caller projections.
    boundary['snapshots']=[digest(value) for value in values]
    with original_round(boundary,lock=lock,primary_lock=primary_lock) as round_:
        reader=CheckedGraphs(round_,boundary,lock,primary_lock)
        try:
            for value in values:reader.read(value)
            yield reader
        finally:
            try:reader.guard()
            finally:reader.active=False
