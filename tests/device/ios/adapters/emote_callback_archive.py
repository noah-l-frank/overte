"""Explicit Callback Archive2 over actual Native4/Rendered4/Keyed4 originals.

Only component envelopes and their latest committed reference are copied.
Every contributing native/input/file/pixel original is still fully decoded.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from contextlib import contextmanager
from pathlib import Path
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import context
from adapters.script_feature.history import same
from adapters.script_feature.lock import ScriptSourceLock
from feature_journeys.contract import identifier
from ios.adapters.emote_keys import IOSEmoteKeys
from ios.adapters.emote_restoration_frames import IOSEmoteRestorationFrames
from ios.adapters.emote_retirement import Frozen
from ios.adapters.emote_callback_retirement import IOSEmoteCallbackNativeRetirement
from ios.adapters.emote_callback_scene import (IOSEmoteCallbackRenderedRetirement,
    IOSEmoteCallbackKeyedRetirement,IOSEmoteCallbackSceneRetirement)
from ios.adapters.emote_archive_round import scope as original_round,LITERAL_PACKETS

VERSION=2
PARTS={'native','frames','rendered','keys','keyed'}


def capture(owner,reference):
    need(type(owner) is IOSEmoteCallbackKeyedRetirement and not owner.historical)
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
    native=IOSEmoteCallbackNativeRetirement(Frozen(paths['native'],originals['native']),root,binding,primary,value['runId'],
        value['role'],value['fixtureUrl'],value['phaseInstance'],lock,primary_lock,value['imagePolicy'],native_paths,lambda:True,historical=True)
    frames=IOSEmoteRestorationFrames.archive(originals['frames'],store=Frozen(paths['frames'],originals['frames']),**settings)
    rendered=IOSEmoteCallbackRenderedRetirement(Frozen(paths['rendered'],originals['rendered']),native,frames,historical=True)
    keys=IOSEmoteKeys.archive(originals['keys'],store=Frozen(paths['keys'],originals['keys']),**settings)
    keyed=IOSEmoteCallbackKeyedRetirement(Frozen(paths['keyed'],originals['keyed']),rendered,keys,historical=True)
    need(keyed.state['pending'] is None and keyed.state['records'] and same(value['reference'],keyed.state['records'][-1]))
    return keyed


def read(value,*,lock,primary_lock):
    with original_round(value,lock=lock,primary_lock=primary_lock,key_packet_policy=LITERAL_PACKETS):
        return IOSEmoteCallbackSceneRetirement(reopen(value,lock=lock,primary_lock=primary_lock)).read(value['reference'])


class CallbackGraphs:
    """Only the existing immutable round is shared; no graph-result cache."""
    def __init__(self,round_,boundary,lock,primary_lock):
        self.round,self.boundary,self.lock,self.primary_lock=round_,boundary,lock,primary_lock
        self.active=True

    def guard(self):need(self.active);self.round.guard()

    def read(self,value):
        self.guard();need(type(value) is dict and all(value.get(key)==self.boundary[key]
            for key in ('artifactRoot','stateRoot','sourceLock','primaryLock')))
        actual=IOSEmoteCallbackSceneRetirement(reopen(value,lock=self.lock,primary_lock=self.primary_lock)).read(value['reference'])
        self.guard();return actual


@contextmanager
def grouped(values,*,lock,primary_lock):
    """Literal new-profile reopens under the existing full immutable census.

    Packet originals use their existing literal raw decoder each time.
    No marshal/audit callback, new memo, copied result or current owner verdict
    is introduced. Existing original-only per-round validators retain their
    unchanged byte/inode/membership and owner/clock guards.
    """
    need(type(values) is list and 1<=len(values)<=96 and all(type(value) is dict for value in values))
    fields=('artifactRoot','stateRoot','sourceLock','primaryLock')
    boundary={key:values[0].get(key) for key in fields}
    need(all(type(item) is str for item in boundary.values())
        and all(all(value.get(key)==boundary[key] for key in fields) for value in values))
    boundary['snapshots']=[digest(value) for value in values]
    with original_round(boundary,lock=lock,primary_lock=primary_lock,key_packet_policy=LITERAL_PACKETS) as round_:
        reader=CallbackGraphs(round_,boundary,lock,primary_lock)
        try:
            for value in values:reader.read(value)
            yield reader
        finally:
            try:reader.guard()
            finally:reader.active=False
