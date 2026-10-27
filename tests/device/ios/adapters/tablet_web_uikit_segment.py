"""Explicit UIKit-only initial/active129..256 through the Packet writer.

Original contacts and dispatches seed the actual native floor. Storage
continuation neither proves release/retirement nor admits whole Source input.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from pathlib import Path
import time

from adapters.native_feature_observation import exact,integer,need
from adapters.original_frame_store import MAX_FRAMES
from adapters.script_feature.history import same
from ios.adapters import tablet_web_uikit_continuation as closed
from ios.adapters.emote_original_lease import EmoteOriginalLease
from ios.adapters.tablet_web_packets import TabletWebPackets,CAPTURES,COMPONENTS

VERSION=2
READS=(1,2)
BOUND_VERSION=1
FIRST=CAPTURES+1


def segment_header(value,expected,first_ref):
    exact(value,{'tabletWebUIKitActiveSegmentVersion','binding','runId','role','fixtureUrl','processId','component',
        'firstIndex','nextRaw','records','pending','recordIntent','recordInspection'})
    version=value['tabletWebUIKitActiveSegmentVersion']
    need(type(version) is int and version in READS
        and all(same(value[key],expected[key]) for key in expected) and value['component']=='uikit'
        and type(value['firstIndex']) is int and value['firstIndex']==FIRST
        and integer(value['nextRaw'],1,MAX_FRAMES+1) and type(value['records']) is list
        and (1 if version==BOUND_VERSION else 0)<=len(value['records'])<=CAPTURES
        and all(type(ref) is dict and type(ref.get('index')) is int and ref['index']==FIRST+offset
            for offset,ref in enumerate(value['records'])))
    need((first_ref is None and version==VERSION and not value['records'])
        or first_ref is not None and value['records'] and same(value['records'][0],first_ref))
    need(value['pending'] is None or type(value['pending']) is dict)
    need(value['recordIntent'] is None or type(value['recordIntent']) is dict)
    need(value['recordInspection'] is None or type(value['recordInspection']) is dict)


def open_segment(root,binding,run,role,fixture_url,pid,lock,guard,*,monotonic=time.monotonic,epoch_ms=lambda:int(time.time()*1000)):
    """Once-CAS bound original129; opening itself never queries UIKit."""
    need(callable(guard) and guard() is not False)
    prefix=closed.TabletUIKitClosedPrefix(root,binding,run,role,fixture_url,pid,lock,monotonic=monotonic)
    need(prefix.state['tabletWebUIKitContinuationVersion']==closed.BOUND_VERSION)
    proof=prefix.adopted();need(guard() is not False)
    active=dict(tabletWebUIKitActiveSegmentVersion=BOUND_VERSION,binding=deepcopy(binding),runId=run,role=role,
        fixtureUrl=fixture_url,processId=pid,component='uikit',firstIndex=FIRST,nextRaw=proof['nextRaw'],
        records=[deepcopy(prefix.state['successor'])],pending=None,recordIntent=None,recordInspection=None)
    changed=deepcopy(prefix.state);changed.update(tabletWebUIKitContinuationVersion=closed.ACTIVE_VERSION,active=active)
    prefix.save(changed)
    return TabletUIKitSegment(root,binding,run,role,fixture_url,pid,lock,guard,monotonic=monotonic,epoch_ms=epoch_ms)


def open_initial_segment(root,binding,run,role,fixture_url,pid,lock,guard,*,monotonic=time.monotonic,epoch_ms=lambda:int(time.time()*1000)):
    """Fence the first real query129 before send; no precreated successor."""
    need(callable(guard) and guard() is not False)
    prefix=closed.TabletUIKitClosedPrefix(root,binding,run,role,fixture_url,pid,lock,monotonic=monotonic)
    need(prefix.state['tabletWebUIKitContinuationVersion']==closed.FENCE_VERSION)
    proof=prefix.history();need(guard() is not False)
    active=dict(tabletWebUIKitActiveSegmentVersion=VERSION,binding=deepcopy(binding),runId=run,role=role,
        fixtureUrl=fixture_url,processId=pid,component='uikit',firstIndex=FIRST,nextRaw=proof['nextRaw'],
        records=[],pending=None,recordIntent=None,recordInspection=None)
    changed=deepcopy(prefix.state);changed.update(tabletWebUIKitContinuationVersion=closed.VERSION,successor=None,active=active)
    prefix.save(changed)
    return TabletUIKitSegment(root,binding,run,role,fixture_url,pid,lock,guard,monotonic=monotonic,epoch_ms=epoch_ms)


class TabletUIKitSegment(TabletWebPackets):
    def __init__(self,root,binding,run,role,fixture_url,pid,lock,guard,*,monotonic=time.monotonic,epoch_ms=lambda:int(time.time()*1000),historical=False):
        need(type(historical) is bool and all(callable(fn) for fn in (guard,monotonic,epoch_ms))
            and (historical or guard() is not False))
        self.root=Path(root);self.binding=deepcopy(binding);self.run,self.role,self.fixture,self.pid=run,role,fixture_url,pid
        self.lock,self._current_guard,self._pinned_guard=lock,guard,guard
        self.monotonic,self.epoch_ms,self.historical,self.clock=monotonic,epoch_ms,historical,None
        self.component,self.module='uikit',COMPONENTS['uikit']
        self.closed=closed.TabletUIKitClosedPrefix(root,binding,run,role,fixture_url,pid,lock,monotonic=monotonic)
        need(self.closed.state['tabletWebUIKitContinuationVersion'] in (closed.ACTIVE_VERSION,)+closed.INITIAL_VERSIONS)
        self.store=self.closed.store;self.state=deepcopy(self.closed.state['active']);self.saved=deepcopy(self.state)
        self.guard=self.storage_guard=self._bound
        self._original_storage();self.history();self._bound()

    def _bound(self):
        need(self._current_guard is self._pinned_guard and (self.historical or self._current_guard() is not False)
            and self.lock is self.closed.lock
            and same(closed.base.scope(self.binding,self.run,self.role,self.fixture,self.pid),self.closed.expected))
        return self.closed.guard()

    def _header(self):segment_header(self.state,self.closed.expected,self.closed.state['successor'])

    def _record_start(self):return FIRST

    def stamp(self):
        need(not self.historical);return super().stamp()

    def reference(self,index):
        self._bound();self._header();need(integer(index,1,self._next_index()-1))
        reference=(self.closed.old['records'][index-1] if index<FIRST else self.state['records'][index-FIRST])
        need(reference['index']==index);return deepcopy(reference)

    def history(self):
        self._bound();lease=EmoteOriginalLease(self.root,[]);result=super().history()
        for reference in self.state['records']:
            if self.originals.read(self.originals.expand(reference))['status']!='returned':self.blocked=True
        self._bound();lease.guard();return result

    def save(self):
        need(not self.historical);self._bound();need(same(self.saved,self.closed.state['active']))
        value=deepcopy(self.closed.state);value['active']=deepcopy(self.state)
        if value['tabletWebUIKitContinuationVersion'] in closed.INITIAL_VERSIONS and value['successor'] is None and self.state['records']:
            # Bind only the first actual completed original held by the
            # previous durable intent. Both normal archive and opened-file
            # recovery reach this same CAS, without replaying query129.
            need(not self.saved['records'] and len(self.state['records'])==1
                and self.saved['pending'] is not None and self.saved['recordIntent'] is not None)
            reference=self.originals.original(self.saved['recordIntent'])
            need(reference['index']==FIRST and reference['phase'] in ('opened','saved')
                and same(self.originals.compact(dict(reference,phase='saved')),self.state['records'][0])
                and same(self.originals.read(reference),self.saved['pending']))
            value['successor']=deepcopy(self.state['records'][0])
        segment_header(self.state,self.closed.expected,value['successor'])
        self.closed.save(value);self.saved=deepcopy(self.state)

    def _history_prefix(self):
        self.closed.history()
        reader=closed._snapshot(self.root,self.closed.expected,self.closed.old,self.monotonic)
        packets=reader.history();need(not reader.blocked and packets);queries=set()
        for reference in self.closed.old['records']:
            row=reader.originals.read(reader.originals.expand(reference))
            need(row['query'] is not None and row['query']['commandId'] not in queries);queries.add(row['query']['commandId'])
        return deepcopy(packets[-1]),packets,self.closed.old['nextRaw'],queries,deepcopy(reader.clock)
