"""Explicit DOM-only active segment129..256, never whole-feature admission.

The existing Packet query/raw/record writer owns every new transition. This
class supplies a fully replayed immutable predecessor and bounded global
indices; it does not create an SDK, weaken a current guard or open the parent.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import time

from adapters.native_feature_observation import exact,integer,need
from adapters.original_frame_store import MAX_FRAMES
from adapters.script_feature.history import same
from ios.adapters import tablet_web_dom_continuation as closed
from ios.adapters.emote_original_lease import EmoteOriginalLease
from ios.adapters.tablet_web_packets import TabletWebPackets,CAPTURES,COMPONENTS

VERSION=1
FIRST=CAPTURES+1


def segment_header(value,expected,first_ref):
    exact(value,{'tabletWebDOMActiveSegmentVersion','binding','runId','role','fixtureUrl','processId','component',
        'firstIndex','nextRaw','records','pending','recordIntent','recordInspection'})
    need(type(value['tabletWebDOMActiveSegmentVersion']) is int and value['tabletWebDOMActiveSegmentVersion']==VERSION
        and all(same(value[key],expected[key]) for key in expected) and value['component']=='dom'
        and type(value['firstIndex']) is int and value['firstIndex']==FIRST
        and integer(value['nextRaw'],1,MAX_FRAMES+1) and type(value['records']) is list
        and 1<=len(value['records'])<=CAPTURES and same(value['records'][0],first_ref)
        and all(type(ref) is dict and type(ref.get('index')) is int and ref['index']==FIRST+offset
            for offset,ref in enumerate(value['records'])))
    need(value['pending'] is None or type(value['pending']) is dict)
    need(value['recordIntent'] is None or type(value['recordIntent']) is dict)
    need(value['recordInspection'] is None or type(value['recordInspection']) is dict)


def open_segment(root,binding,run,role,fixture_url,pid,lock,guard,*,monotonic=time.monotonic,epoch_ms=lambda:int(time.time()*1000)):
    """Once-CAS a previously bound actual129 tail; never query during opening."""
    need(callable(guard) and guard() is not False)
    prefix=closed.TabletDOMClosedPrefix(root,binding,run,role,fixture_url,pid,lock,monotonic=monotonic)
    proof=prefix.adopted();need(guard() is not False)
    active=dict(tabletWebDOMActiveSegmentVersion=VERSION,binding=deepcopy(binding),runId=run,role=role,
        fixtureUrl=fixture_url,processId=pid,component='dom',firstIndex=FIRST,nextRaw=proof['nextRaw'],
        records=[deepcopy(prefix.state['successor'])],pending=None,recordIntent=None,recordInspection=None)
    changed=deepcopy(prefix.state);changed.update(tabletWebDOMContinuationVersion=closed.VERSION,active=active)
    prefix.save(changed)
    return TabletDOMSegment(root,binding,run,role,fixture_url,pid,lock,guard,monotonic=monotonic,epoch_ms=epoch_ms)


class TabletDOMSegment(TabletWebPackets):
    def __init__(self,root,binding,run,role,fixture_url,pid,lock,guard,*,monotonic=time.monotonic,epoch_ms=lambda:int(time.time()*1000)):
        need(all(callable(fn) for fn in (guard,monotonic,epoch_ms)) and guard() is not False)
        self.root=Path(root);self.binding=deepcopy(binding);self.run,self.role,self.fixture,self.pid=run,role,fixture_url,pid
        self.lock,self._current_guard,self._pinned_guard=lock,guard,guard
        self.monotonic,self.epoch_ms,self.historical,self.clock=monotonic,epoch_ms,False,None
        self.component,self.module='dom',COMPONENTS['dom']
        self.closed=closed.TabletDOMClosedPrefix(root,binding,run,role,fixture_url,pid,lock,monotonic=monotonic)
        need(self.closed.state['tabletWebDOMContinuationVersion']==closed.VERSION)
        self.store=self.closed.store;self.state=deepcopy(self.closed.state['active']);self.saved=deepcopy(self.state)
        self.guard=self.storage_guard=self._bound
        self._original_storage();self.history();self._bound()

    def _bound(self):
        need(not self.historical and self._current_guard is self._pinned_guard and self._current_guard() is not False
            and self.lock is self.closed.lock
            and same(closed.base.scope(self.binding,self.run,self.role,self.fixture,self.pid),self.closed.expected))
        return self.closed.guard()

    def _header(self):segment_header(self.state,self.closed.expected,self.closed.state['successor'])

    def _record_start(self):return FIRST

    def history(self):
        self._bound();lease=EmoteOriginalLease(self.root,[]);result=super().history()
        # Archiving uncertainty preserves its original; it cannot silently
        # admit another query through this first active continuation profile.
        for reference in self.state['records']:
            if self.originals.read(self.originals.expand(reference))['status']!='returned':self.blocked=True
        self._bound();lease.guard();return result

    def save(self):
        self._bound();need(same(self.saved,self.closed.state['active']));self._header()
        value=deepcopy(self.closed.state);value['active']=deepcopy(self.state)
        self.closed.save(value);self.saved=deepcopy(self.state)

    def _history_prefix(self):
        self.closed.history();e=self.closed.expected
        reader=TabletWebPackets._closed_dom(self.root,e['binding'],e['runId'],e['role'],e['fixtureUrl'],e['processId'],
            self.closed.old,monotonic=self.monotonic)
        packets=reader.history();need(not reader.blocked and packets)
        queries=set()
        for reference in self.closed.old['records']:
            row=reader.originals.read(reader.originals.expand(reference))
            need(row['query'] is not None and row['query']['commandId'] not in queries);queries.add(row['query']['commandId'])
        return deepcopy(packets[-1]),packets,self.closed.old['nextRaw'],queries,deepcopy(reader.clock)
