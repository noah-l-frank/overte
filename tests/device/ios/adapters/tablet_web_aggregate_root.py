"""Explicit owned continuation beside immutable Source3 and child headers.

This first bounded source root adds no screen/sample continuation or Ready
authority. The ordinary packet writer and aggregate clock/phase join still
own every actual query, raw reply and returned acquisition. Legacy constructors
remain literal and closed at their existing fences.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import os
from pathlib import Path
import time

from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState,context
from adapters.original_frame_store import OriginalFrameStore,MAX_FRAMES
from adapters.script_feature.history import same
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters import tablet_web_child_rotation as closed
from ios.adapters import tablet_web_rotation_fence as fence
from ios.adapters import tablet_web_parent_guard_cache as parent_guard_cache
from ios.adapters.emote_original_lease import EmoteOriginalLease
from ios.adapters.tablet_web_packets import TabletWebPackets,CAPTURES,COMPONENTS
from ios.adapters.tablet_web_source_owner import TabletWebSourceOwner,ORDER

VERSION=1
OWNER_VERSION=4
_PARENT_CACHE=parent_guard_cache.check
_PARENT_CACHE_CODE=_PARENT_CACHE.__code__


def forbidden(*_args,**_kwargs):need(False)


def root_name(run,role):return 'tabletweb-aggregate-root-'+run+'-'+role+'.json'


def child_name(component,run,role):
    need(component in ORDER)
    return 'tabletweb-'+component+'-aggregate-segment-'+run+'-'+role+'.json'


class TabletAggregateChild(TabletWebPackets):
    """One owned bounded segment, with an unequal immutable legacy prefix."""
    def __init__(self,owner,component):
        need(type(owner) is TabletWebAggregateRoot and component in ORDER)
        owner._parent_guard();self.owner=owner
        self.root,self.binding=owner.root,deepcopy(owner.binding)
        self.run,self.role,self.fixture,self.pid=owner.run,owner.role,owner.fixture,owner.pid
        self.component,self.module=component,COMPONENTS[component]
        self.historical,self.monotonic,self.epoch_ms=owner.historical,owner.monotonic,owner.epoch_ms
        self.guard=self.storage_guard=self._bound;self.clock=None
        self.prefix_descriptor=deepcopy(next(row for row in owner.parent['children'] if row['component']==component))
        self.first=self.prefix_descriptor['count']+1
        self.store=PrivateFeatureState(self.root/child_name(component,self.run,self.role))
        self.state=self.store.read();need(self.state is not None)
        self.saved=deepcopy(self.state);self._original_storage();self.history()

    def _bound(self):
        self.owner._parent_guard()
        need(self.prefix_descriptor==next(row for row in self.owner.parent['children'] if row['component']==self.component)
            and self.first==self.prefix_descriptor['count']+1
            and self.store.path==self.root/child_name(self.component,self.run,self.role)
            and same(self.store.read(),self.saved))
        if not self.historical:self.owner.bound()
        return True

    def _header(self):
        value=self.state
        exact(value,{'tabletWebAggregateChildVersion','binding','runId','role','fixtureUrl','processId',
            'component','firstIndex','nextRaw','records','pending','recordIntent','recordInspection'})
        need(type(value['tabletWebAggregateChildVersion']) is int and value['tabletWebAggregateChildVersion']==VERSION
            and all(same(value[key],self.owner.expected[key]) for key in self.owner.expected)
            and value['component']==self.component and type(value['firstIndex']) is int and value['firstIndex']==self.first
            and integer(value['nextRaw'],self.prefix_descriptor['nextRaw'],MAX_FRAMES+1)
            and type(value['records']) is list and len(value['records'])<=CAPTURES
            and all(type(ref) is dict and type(ref.get('index')) is int and ref['index']==self.first+index
                for index,ref in enumerate(value['records'])))

    def _record_start(self):return self.first

    def _prefix(self):
        # Reconstruct this actual literal reader for EACH use. Its canonical
        # bytes remain fixed by the original parent's inode/hash descriptor;
        # no foreign mutable peer-header pin is refreshed or rewritten.
        self._bound()
        reader=TabletWebPackets(self.root,self.binding,self.run,self.role,self.fixture,self.pid,
            self.component,forbidden,monotonic=self.monotonic,epoch_ms=forbidden,historical=True)
        need(not reader.blocked and len(reader.state['records'])==self.first-1
            and all(reader.originals.read(reader.originals.expand(ref))['status']=='returned' for ref in reader.state['records']))
        self._bound();return reader

    def _history_prefix(self):
        reader=self._prefix();packets=reader.history();queries=set()
        for reference in reader.state['records']:
            row=reader.originals.read(reader.originals.expand(reference))
            need(row['query'] is not None and row['query']['commandId'] not in queries)
            queries.add(row['query']['commandId'])
        return None if not packets else deepcopy(packets[-1]),packets,reader.state['nextRaw'],queries,deepcopy(reader.clock)

    def reference(self,index):
        self._bound();self._header();need(integer(index,1,self._next_index()-1))
        reference=(self._prefix().reference(index) if index<self.first else self.state['records'][index-self.first])
        need(reference['index']==index);return deepcopy(reference)

    def save(self):
        need(not self.historical);self._bound();self._header()
        self.store.write(self.state,self.saved);self.saved=deepcopy(self.state)

    def history(self):
        self._bound();lease=EmoteOriginalLease(self.root,[]);result=super().history()
        # This first root does not retire or reconcile ambiguous child work.
        for reference in self.state['records']:
            if self.originals.read(self.originals.expand(reference))['status']!='returned':self.blocked=True
        self._bound();lease.guard();return result


class TabletWebAggregateRoot(TabletWebSourceOwner):
    """Owned Source4, with at most128 additional rows per original segment."""
    def __init__(self,root,binding,run,role,fixture_url,pid,lock,guard,*,epoch_ms=lambda:int(time.time()*1000),
            monotonic=time.monotonic,historical=False,admission=None):
        self.root=Path(root);self.binding=deepcopy(context(binding))
        self.run,self.role,self.fixture,self.pid=run,role,fixture_url,pid
        self.expected=fence.scope(self.binding,run,role,fixture_url,pid)
        need(isinstance(lock,ScriptSourceLock) and lock.path==self.root/'script-feature-sources.lock'
            and type(historical) is bool and all(callable(fn) for fn in (guard,epoch_ms,monotonic)))
        lock.assert_held();self.lock,self.guard,self.epoch_ms,self.monotonic,self.historical=lock,guard,epoch_ms,monotonic,historical
        self.admission=deepcopy(admission);self._stored_read_depth=0
        if admission is not None:
            from ios.adapters.tablet_web_admission import validate
            validate(admission,self.binding)
            if not historical:need(admission['hostProcessId']==os.getpid())
        self.store=PrivateFeatureState(self.root/root_name(run,role));self.state=self.store.read()
        need(self.state is not None);self.saved=deepcopy(self.state)
        parent_path=self.root/('tabletweb-source-owner-'+run+'-'+role+'.json')
        raw,self.parent_signature=closed._raw(parent_path);self.parent_sha=hashlib.sha256(raw).hexdigest()
        self.parent=PrivateFeatureState(parent_path).read()
        self.legacy=fence._legacy(closed.decode(self.parent,self.expected),self.expected)
        self._header();self._parent_guard()
        if not historical:self.bound()
        self._original_storage();self.history()

    def _parent_guard(self):
        current=parent_guard_cache.check
        if current is not _PARENT_CACHE or current.__code__ is not _PARENT_CACHE_CODE:return self._parent_guard_literal()
        return current(self,self._parent_guard_literal)

    def _parent_guard_literal(self):
        self.lock.assert_held()
        raw,signature=closed._raw(self.root/('tabletweb-source-owner-'+self.run+'-'+self.role+'.json'))
        need(signature==self.parent_signature and hashlib.sha256(raw).hexdigest()==self.parent_sha)
        need(same(PrivateFeatureState(self.root/('tabletweb-source-owner-'+self.run+'-'+self.role+'.json')).read(),self.parent))
        need(same(self.expected,fence.scope(self.binding,self.run,self.role,self.fixture,self.pid)))
        need(same(self.legacy,fence._legacy(closed.decode(self.parent,self.expected),self.expected)))
        for descriptor in self.parent['children']:
            raw,signature=closed._raw(self.root/descriptor['headerName'])
            need(signature==descriptor['signature'] and hashlib.sha256(raw).hexdigest()==descriptor['sha256'])
        reference=self.parent['copyIntent']
        need(reference is not None and reference['phase'] in ('opened','saved'))
        def locked():self.lock.assert_held();return True
        copies=OriginalFrameStore(self.root,self.binding,self.run,self.role,locked,forbidden,
            namespace='tabletweb-closed-headers',schema_prefix='tabletWebClosedHeader',monotonic=self.monotonic)
        need(same(copies.read(reference),closed.copy_body(self.parent,self.expected)))
        return True

    def bound(self):
        need(not self.historical);self._parent_guard()
        need(self.guard() is not False and same(self.store.read(),self.saved))

    def _header(self):
        value=self.state
        exact(value.get('parent'),{'signature','sha256'})
        fence._signature(value['parent']['signature'],value['parent']['signature']['bytes'])
        refs=value.get('boundedSegmentRefs');need(type(refs) is list and len(refs)==len(ORDER))
        for ref in refs:
            exact(ref,{'component','headerName','firstIndex'})
            need(type(ref['firstIndex']) is int and 1<=ref['firstIndex']<=CAPTURES+1)
        exact(value,{'tabletWebSourceOwnerVersion','tabletWebAggregateRootVersion','binding','runId','role','fixtureUrl','processId',
            'parent','boundedSegmentRefs','firstIndex','apps','records','pending','intent','inspection','appIntent','appPending','appInspection','reconciled'})
        need(type(value['tabletWebSourceOwnerVersion']) is int and value['tabletWebSourceOwnerVersion']==OWNER_VERSION
            and type(value['tabletWebAggregateRootVersion']) is int and value['tabletWebAggregateRootVersion']==VERSION
            and all(same(value[key],self.expected[key]) for key in self.expected)
            and value['parent']==dict(signature=self.parent_signature,sha256=self.parent_sha)
            and type(value['firstIndex']) is int and value['firstIndex']==len(self.legacy['records'])+1
            and type(value['records']) is list and len(value['records'])<=128
            and type(value['apps']) is list and len(value['apps'])<=32 and value['apps'][:len(self.legacy['apps'])]==self.legacy['apps']
            and value['reconciled']==[] and self.legacy.get('reconciled',[])==[])
        expected=[dict(component=row['component'],headerName=child_name(row['component'],self.run,self.role),firstIndex=row['count']+1)
            for row in self.parent['children']]
        need(value['boundedSegmentRefs']==expected)

    def _original_storage(self,**_kwargs):
        self.originals=OriginalFrameStore(self.root,self.binding,self.run,self.role,self.stored_original_guard,self.frame_intent,
            namespace='tabletweb-acquisitions',schema_prefix='tabletWebAcquisition',monotonic=self.monotonic)
        self.app_originals=OriginalFrameStore(self.root,self.binding,self.run,self.role,self.stored_original_guard,self.app_intent,
            namespace='tabletweb-app-origins',schema_prefix='tabletWebAppAdmission',monotonic=self.monotonic)
        self.children={name:TabletAggregateChild(self,name) for name in ORDER}

    def record_references(self):return self.legacy['records']+self.state['records']

    def history(self):
        self._parent_guard();lease=EmoteOriginalLease(self.root,[]);result=super().history()
        self._parent_guard();lease.guard();return result

    def reconcile_unanswered(self,reader):
        # The original unresolved responsibility remains held. This initial
        # bounded profile never relabels an unknown/failed acquisition.
        need(False)


def open_owned(root,binding,run,role,fixture_url,pid,lock,guard,*,epoch_ms=lambda:int(time.time()*1000),monotonic=time.monotonic,admission=None):
    """Open only an ALREADY durable original Source3/closed-copy namespace.

    No query, SDK, grant, input, rotation, retiming or original adoption occurs
    here. Every nine-child initialization is declared in the root WAL before
    its first file birth. Incomplete initialization remains closed; a saved
    whole-root return can be recovered only through its actual nine children.
    """
    need(callable(guard) and guard() is not False)
    expected=fence.scope(binding,run,role,fixture_url,pid);root=Path(root)
    need(isinstance(lock,ScriptSourceLock) and lock.path==root/'script-feature-sources.lock');lock.assert_held()
    store=PrivateFeatureState(root/root_name(run,role));current=store.read()
    if current is not None:
        return TabletWebAggregateRoot(root,binding,run,role,fixture_url,pid,lock,guard,epoch_ms=epoch_ms,
            monotonic=monotonic,admission=admission)
    proof=closed.restore(root,binding,run,role,fixture_url,pid,lock,monotonic=monotonic)
    need(proof['historicalOnly'] is True and proof['phase']=='rotating')
    parent_path=root/('tabletweb-source-owner-'+run+'-'+role+'.json')
    raw,signature=closed._raw(parent_path);parent=PrivateFeatureState(parent_path).read()
    legacy=fence._legacy(closed.decode(parent,expected),expected)
    need(legacy.get('reconciled',[])==[])
    # Creation is intentionally once-only. A pre-existing child root without
    # its parent root is orphan responsibility, never initialization data.
    need(all(not os.path.lexists(root/child_name(name,run,role)) for name in ORDER))
    refs=[dict(component=row['component'],headerName=child_name(row['component'],run,role),firstIndex=row['count']+1)
        for row in parent['children']]
    value=dict(tabletWebSourceOwnerVersion=OWNER_VERSION,tabletWebAggregateRootVersion=VERSION,**deepcopy(expected),
        parent=dict(signature=signature,sha256=hashlib.sha256(raw).hexdigest()),boundedSegmentRefs=refs,
        firstIndex=len(legacy['records'])+1,apps=deepcopy(legacy['apps']),records=[],pending=None,intent=None,inspection=None,
        appIntent=None,appPending=None,appInspection=None,reconciled=[])
    # Own the parent before the nine children. Incomplete root initialization
    # is retained and refused by the constructor; no native request is sent.
    store.write(value,None)
    for descriptor in parent['children']:
        name=descriptor['component']
        child=dict(tabletWebAggregateChildVersion=VERSION,**deepcopy(expected),component=name,firstIndex=descriptor['count']+1,
            nextRaw=descriptor['nextRaw'],records=[],pending=None,recordIntent=None,recordInspection=None)
        PrivateFeatureState(root/child_name(name,run,role)).write(child,None)
    need(guard() is not False)
    return TabletWebAggregateRoot(root,binding,run,role,fixture_url,pid,lock,guard,epoch_ms=epoch_ms,
        monotonic=monotonic,admission=admission)


def _capacity_reached(source):
    # Only a genuinely full original bounded epoch starts this transition.
    # Unequal independent child cursors are retained, never padded/retimed.
    return len(source.state['records'])==CAPTURES or any(len(child.state['records'])==CAPTURES for child in source.children.values())


def _activate_literal(source):
    need(type(source) is TabletWebSourceOwner and not source.historical)
    source.bound();need(_capacity_reached(source))
    # Refuse an existing unknown root/copy responsibility BEFORE canonical CAS.
    need(not os.path.lexists(source.root/root_name(source.run,source.role)))
    need(all(not os.path.lexists(source.root/child_name(name,source.run,source.role)) for name in ORDER))
    prefixes=tuple('tabletweb-closed-headers-'+kind+'-sources-'+source.run+'-'+source.role+'-' for kind in ('frame','index'))
    need(not any(path.name.startswith(prefixes) for path in source.root.iterdir()))
    expected=fence.scope(source.binding,source.run,source.role,source.fixture,source.pid)
    value=closed.make(source);source.store.write(value,source.saved);cursor=deepcopy(value)
    # This is the existing Source3 CAS/copy protocol. A lost CAS return has
    # no copy intent and remains fenced; no future invocation repeats it.
    def guard():
        source.lock.assert_held();need(source.guard() is not False and same(source.store.read(),cursor))
        closed.decode(cursor,expected)
        for row in value['children']:
            raw,signature=closed._raw(source.root/row['headerName'])
            need(signature==row['signature'] and hashlib.sha256(raw).hexdigest()==row['sha256'])
        return True
    def intent(kind,reference):
        nonlocal cursor
        guard();changed=closed.with_copy_intent(cursor,kind,reference,expected)
        source.store.write(changed,cursor);cursor=deepcopy(changed)
    copies=OriginalFrameStore(source.root,source.binding,source.run,source.role,guard,intent,
        namespace='tabletweb-closed-headers',schema_prefix='tabletWebClosedHeader',monotonic=source.monotonic)
    copies.write(1,closed.copy_body(value,expected));guard()
    return open_owned(source.root,source.binding,source.run,source.role,source.fixture,source.pid,source.lock,source.guard,
        epoch_ms=source.epoch_ms,monotonic=source.monotonic,admission=source.admission)


def source_owner(root,binding,run,role,fixture_url,pid,lock,guard,*,epoch_ms=lambda:int(time.time()*1000),
        monotonic=time.monotonic,historical=False,admission=None,for_capture=False):
    """Default literal routing; explicit normal-factory capacity transition.

    The opt-in runs before an Action/Input/Sample owner is constructed, never
    replacing its source during a live1.5s acquisition. Unknown/incomplete
    copies stay fenced; historical/default callers never activate anything.
    """
    need(type(for_capture) is bool and (not for_capture or not historical))
    expected=fence.scope(binding,run,role,fixture_url,pid)
    path=Path(root)/root_name(run,role);PrivateFeatureState(path)._parent()
    if for_capture and not os.path.lexists(path):
        head=PrivateFeatureState(Path(root)/('tabletweb-source-owner-'+run+'-'+role+'.json')).read()
        if type(head) is dict and type(head.get('tabletWebSourceOwnerVersion')) is int and head['tabletWebSourceOwnerVersion']==3:
            # A preceding original copy may have succeeded before its caller
            # lost the local return. Reopen ONLY actual complete original
            # bytes through restore/open_owned; never repeat a copy write.
            legacy=fence._legacy(closed.decode(head,expected),expected)
            need(len(legacy['records'])==CAPTURES or any(row['count']==CAPTURES for row in head['children']))
            need(head['copyIntent'] is not None and head['copyIntent']['phase'] in ('opened','saved'))
            return open_owned(root,binding,run,role,fixture_url,pid,lock,guard,epoch_ms=epoch_ms,monotonic=monotonic,admission=admission)
        source=TabletWebSourceOwner(root,binding,run,role,fixture_url,pid,lock,guard,epoch_ms=epoch_ms,
            monotonic=monotonic,historical=False,admission=admission)
        return _activate_literal(source) if _capacity_reached(source) else source
    owner=TabletWebAggregateRoot if os.path.lexists(path) else TabletWebSourceOwner
    return owner(root,binding,run,role,fixture_url,pid,lock,guard,epoch_ms=epoch_ms,
        monotonic=monotonic,historical=historical,admission=admission)


_PARENT_GUARD_LITERAL=TabletWebAggregateRoot._parent_guard_literal
parent_guard_cache._PARENT_GUARD_CODE=_PARENT_GUARD_LITERAL.__code__
parent_guard_cache._PARENT_GUARD_GLOBALS=tuple((name,_PARENT_GUARD_LITERAL.__globals__[name])
    for name in _PARENT_GUARD_LITERAL.__code__.co_names if name in _PARENT_GUARD_LITERAL.__globals__)
