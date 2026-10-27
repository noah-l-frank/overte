# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
"""One original read during the same guarded Source factory assembly.

The factory's literal constructor still decodes and independently copies its
public history. Its private cache is borrowed only until this context exits.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy

from adapters.native_feature_observation import need
from adapters.native_clock_join import digest
from adapters.script_feature.history import same
from ios.adapters.emote_original_lease import EmoteOriginalLease
from ios.adapters.world_web_api_clock import check as api_check

_BUILDING=ContextVar('ios_world_web_source_construction',default=None)


def methods(source):
    result=[]
    for name in ('decode','_decode','_decode_frames'):
        method=getattr(source,name);function=getattr(method,'__func__',None)
        result.append((function,getattr(function,'__code__',None)))
    return tuple(result)


def header(source):
    return (deepcopy(source.binding),source.run,source.role,source.pid,source.phase.fixture_url,source.version,
        str(source.store.path),id(source.store),id(source.lock),id(source.parts),id(source.guard),id(source.readers))


class _Construction:
    def __init__(self):
        self.source=None;self.active=False;self.inventory=None;self.pins=();self.frames=[]
        self.packet=self.state=self.identity=self.parsers=self.round=None
        self.links=();self.frame_sha=None;self.round_pins=self.round_header=None
        self.cache=None;self.cache_keys=None
    def prepare(self,source,literal):
        # A changed reader or an existing factory owner keeps the old literal
        # validation_round. No previous constructor can lend this context proof.
        if self.source is not None or methods(source)!=literal:return None
        source.lock.assert_held();self.source=source;self.identity=header(source);self.parsers=methods(source)
        self.inventory=EmoteOriginalLease(source.store.path.parent,[])
        self.packet=deepcopy(source.previous)
        self.pins=tuple(source.original_pins(self.packet).items())
        need(same(source.store.read(),self.packet));self.inventory.guard()
        return self
    def completed(self,source):
        # Called at the END of the literal constructor, before the factory can
        # alter memory. The stored envelope, not factory-returned state, fixes
        # records, pending and interrupted acquisitions.
        need(self.source is source and not self.active and source._construction is self)
        need(same(header(source),self.identity) and methods(source)==self.parsers)
        if self.packet is None:need(same(source.state,dict(records=[],pending=None,interrupted=[])))
        else:need(same(source.envelope(source.state),self.packet))
        self.state=deepcopy(source.state)
        links=[]
        for reference in self.state['records']:
            # A fresh constructor starts with an empty cache. Only the literal
            # decoder's unique current record may supply an internal frame.
            rows=[(key,frame) for key,frame in source._cache.items()
                if key[0]==reference['index'] and key[1]==reference['sha256']]
            need(len(rows)==1 and rows[0][1]['index']==reference['index']);links.append(rows[0])
        self.links=tuple(links);self.frames=[frame for _key,frame in self.links]
        self.cache=source._cache;self.cache_keys=frozenset(source._cache)
        self.frame_sha=digest(self.frames)
        need(len(self.frames)==len(source.frames))
    def retain(self,source):
        need(self.source is source and not self.active and source._round is None and source._write_round is None
            and source._construction is self and self.state is not None and self.frame_sha is not None)
        self.round=(self.packet,self.state,self.frames)
        self.round_pins=dict(self.pins);self.round_header=deepcopy(self.identity[:6])
        source._round=self.round;source._round_pins=self.round_pins
        source._round_header=self.round_header;self.active=True
        self.check(deep=True)
    def check(self,*,deep=False):
        api_check()
        source=self.source
        need(source is not None and self.active);source.lock.assert_held()
        need(source._construction is self and source._round is self.round and source._write_round is None
            and source._round_pins is self.round_pins and source._round_header is self.round_header
            and same(header(source),self.identity) and methods(source)==self.parsers
            and same(source.previous,self.packet) and same(source.store.read(),self.packet)
            and same(source.state,self.state) and source._round_pins==dict(self.pins))
        for path,signature in self.pins:need(source.original_signature(path)==signature)
        need(source._cache is self.cache and frozenset(source._cache)==self.cache_keys
            and tuple(id(frame) for frame in self.frames)==tuple(id(frame) for _key,frame in self.links)
            and all(source._cache.get(key) is frame for key,frame in self.links))
        # Only private frames are borrowed. All outward frame/projection values
        # are independent copies and this entire assembly is readonly. Check
        # their complete contents at both boundaries before any assembled owner
        # can escape; individual uses retain identity and original-file guards.
        if deep:need(digest(self.frames)==self.frame_sha)
        # Also protects interrupted/planned original carriers and unknown files
        # not present in the normal Source record-path pins.
        self.inventory.guard()
        api_check()
    def clear(self):
        source=self.source
        if source is not None:
            # A lost tag still fails check() and cannot leave THIS owned round
            # installed. Conversely, never clear a different/foreign round.
            if self.active and source._round is self.round:
                source._round=None
                if source._round_pins is self.round_pins:source._round_pins=None
                if source._round_header is self.round_header:source._round_header=None
            if getattr(source,'_construction',None) is self:source._construction=None
        self.source=None;self.active=False;self.frames=[];self.pins=()
        self.inventory=self.packet=self.state=self.identity=self.parsers=self.round=None
        self.links=();self.frame_sha=None;self.round_pins=self.round_header=None
        self.cache=None;self.cache_keys=None


def begin(source,literal):
    current=_BUILDING.get()
    return None if current is None else current.prepare(source,literal)


@contextmanager
def construct(factory):
    need(callable(factory));current=_Construction();token=_BUILDING.set(current)
    try:
        try:source=factory()
        finally:_BUILDING.reset(token)
        if current.source is not source:
            current.clear()
            with source.validation_round():yield source
        else:
            current.retain(source)
            try:yield source
            finally:current.check(deep=True)
    finally:current.clear()
