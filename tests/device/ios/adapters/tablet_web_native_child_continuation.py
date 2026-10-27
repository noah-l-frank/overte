"""Bounded continuation for the seven remaining native Tablet channels.

The existing Packet writer owns queries/raws/recovery. Closed original
graphs and independent peer headers supply no whole SourceReady authority.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
import hashlib
from pathlib import Path
import time
import zlib

from adapters.native_feature_observation import decode as json_decode,exact,integer,need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.original_frame_store import OriginalFrameStore,MAX_FRAMES
from adapters.original_file_reads import record as original_read,scope as file_reads
from adapters.script_feature.history import canonical,same
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters import tablet_web_child_rotation as children,tablet_web_rotation_fence as base
from ios.adapters.emote_original_lease import EmoteOriginalLease
from ios.adapters.tablet_web_packets import TabletWebPackets,CAPTURES,COMPONENTS
from ios.adapters.tablet_web_segments import TabletWebSourceSegments
from ios.adapters import tablet_web_native_semantics as native_semantics
from ios.adapters.tablet_web_record_cache import scope as record_scope

VERSION=1
BODY_VERSION=1
ACTIVE_VERSION=1
KINDS=frozenset({'sources','trace','buttons','state','closures','emissions','deferred'})
PROFILE='tabletweb-native-component-prefix'
FIRST=CAPTURES+1
_OWN_READ=ContextVar('tablet_native_child_own_read',default=None)


def forbidden(*_args,**_kwargs):need(False)


def _kind(component):need(type(component) is str and component in KINDS)


@contextmanager
def _literal_own_reads():
    # A caller's existing memo must not substitute for this own graph's
    # literal reads or native DTO validators. Restore it before live work.
    token=native_semantics._ACTIVE.set(None)
    try:
        with record_scope(None):yield
    finally:native_semantics._ACTIVE.reset(token)


class _OwnFrames(OriginalFrameStore):
    """Existing literal file reader with an operation-local lifetime only."""
    def __init__(self,original,batch):
        self.__dict__.update(original.__dict__);self.batch=batch;self.guard=batch.guard

    def read(self,value):
        self.batch.local();path=self.path(value);self.batch.expected_reads.add(path)
        result=super().read(value);self.batch.dependency(path);return result

    def manifest(self,value):
        self.batch.local();path=self.manifest_path(value);self.batch.expected_reads.add(path)
        result=super().manifest(value);self.batch.dependency(path);return result

    write=append=forbidden


class _OwnSegments(TabletWebSourceSegments):
    def __init__(self,original,batch):
        self.__dict__.update(original.__dict__);self.batch=batch;self.store=_OwnFrames(original.store,batch)

    def inspect(self,value):
        self.batch.guard();self.parent(value)
        paths=[self.store.path(ref) for ref in value['chunks'] if ref['phase']!='planned']
        self.batch.expected_reads.update(paths);result=super().inspect(value)
        for path in paths:self.batch.dependency(path)
        self.batch.guard();return result

    def read(self,value):
        self.batch.local();result=super().read(value);self.batch.local();return result

    write=transition=forbidden


class _OwnPackets(TabletWebPackets):
    def history(self):
        need(self.guard() is not False);result=super().history();need(self.guard() is not False);return result

    def reference(self,index):
        need(self.guard() is not False);return super().reference(index)


class _OwnReadBatch:
    """One pure own graph; no derivation, DTO or proof result is cached."""
    def __init__(self,prefix,reads):
        need(_OWN_READ.get() is None)
        self.prefix,self.reads,self.inventory=prefix,reads,prefix.inventory
        self.root,self.lock,self.component=prefix.root,prefix.lock,prefix.component
        self.expected=deepcopy(prefix.expected);self.path=prefix.store.path;self.active=True;self.expected_reads=set()
        self.inventory.guard();self.lock.assert_held()

    def local(self):
        prefix=self.prefix
        need(self.active and _OWN_READ.get() is self and prefix.alive and prefix.root==self.root
            and prefix.lock is self.lock and prefix.component==self.component and same(prefix.expected,self.expected)
            and prefix.store.path==self.path)
        self.lock.assert_held()

    def guard(self):
        self.local();result=self.prefix.guard();self.local();return result

    def dependency(self,path):
        self.local();path=Path(path)
        need(path.is_absolute() and path.is_relative_to(self.root) and path.resolve(strict=True)==path
            and path.relative_to(self.root).as_posix() in self.inventory.rows and path in self.reads)

    def reader(self,reader):
        self.local();need(reader.historical is True and reader.root==self.root and reader.component==self.component
            and same(base.scope(reader.binding,reader.run,reader.role,reader.fixture,reader.pid),self.expected))
        reader.original_guard=self.guard
        if type(reader) is _OwnPackets:reader.guard=reader.storage_guard=self.guard
        reader.originals=_OwnFrames(reader.originals,self);reader.segments=_OwnSegments(reader.segments,self)

    def bind(self):
        self.local();prefix=self.prefix
        prefix.copies=_OwnFrames(prefix.copies,self);prefix.records=_OwnFrames(prefix.records,self)
        self.expected_reads.add(prefix.store.path)
        parent=prefix._parent()
        self.expected_reads.add(self.root/('tabletweb-source-owner-'+self.expected['runId']+'-'+self.expected['role']+'.json'))
        for child in parent['children']:self.expected_reads.add(self.root/child['headerName'])
        reference=parent['copyIntent']
        need(reference is not None and reference['phase'] in ('opened','saved'))
        copies=OriginalFrameStore(self.root,self.expected['binding'],self.expected['runId'],self.expected['role'],
            self.guard,forbidden,namespace='tabletweb-closed-headers',schema_prefix='tabletWebClosedHeader',monotonic=prefix.monotonic)
        self.expected_reads.add(copies.path(reference))

    def finish(self):
        try:
            self.guard()
            need(self.expected_reads<=self.reads)
            for path in self.reads:self.dependency(path)
        finally:
            # Every failed decode still checks the complete original census.
            # No mutated/missing/new carrier can be hidden by a parser error.
            try:self.lock.assert_held()
            finally:self.inventory.guard()


def _old(raw,expected,component):
    _kind(component);value=json_decode(raw.decode('utf-8'),limit=base.MAX_HEAD_BYTES)
    exact(value,{'tabletWebPacketsVersion','binding','runId','role','fixtureUrl','processId','component',
        'nextRaw','records','pending','recordIntent','recordInspection'})
    need(type(value['tabletWebPacketsVersion']) is int and value['tabletWebPacketsVersion'] in (1,2)
        and all(same(value[key],expected[key]) for key in expected) and value['component']==component
        and type(value['records']) is list and len(value['records'])==CAPTURES
        and integer(value['nextRaw'],1,MAX_FRAMES+1)
        and value['pending'] is value['recordIntent'] is value['recordInspection'] is None)
    return value


def segment_header(value,expected,component,first):
    _kind(component)
    exact(value,{'tabletWebNativeChildActiveSegmentVersion','binding','runId','role','fixtureUrl','processId','component',
        'firstIndex','nextRaw','records','pending','recordIntent','recordInspection'})
    need(type(value['tabletWebNativeChildActiveSegmentVersion']) is int and value['tabletWebNativeChildActiveSegmentVersion']==ACTIVE_VERSION
        and all(same(value[key],expected[key]) for key in expected) and value['component']==component
        and type(value['firstIndex']) is int and value['firstIndex']==FIRST
        and integer(value['nextRaw'],1,MAX_FRAMES+1) and type(value['records']) is list and len(value['records'])<=CAPTURES
        and all(type(ref) is dict and type(ref.get('index')) is int and ref['index']==FIRST+offset
            for offset,ref in enumerate(value['records'])))
    need((first is None and not value['records']) or first is not None and value['records'] and same(value['records'][0],first))
    for name in ('pending','recordIntent','recordInspection'):need(value[name] is None or type(value[name]) is dict)


def decode(value,expected,component):
    expected=base._scope(expected);_kind(component)
    exact(value,{'tabletWebPacketsVersion','tabletWebNativeChildContinuationVersion','profile','phase','scope','component',
        'parent','previousHeader','copyIntent','manifests','manifestIntent','firstRecord','active'})
    need(type(value['tabletWebPacketsVersion']) is int and value['tabletWebPacketsVersion']==3
        and type(value['tabletWebNativeChildContinuationVersion']) is int and value['tabletWebNativeChildContinuationVersion']==VERSION
        and value['profile']==PROFILE and value['phase']=='rotating' and same(value['scope'],expected) and value['component']==component)
    parent=value['parent'];exact(parent,{'signature','sha256'});base._signature(parent['signature'],parent['signature']['bytes'])
    need(type(parent['sha256']) is str and len(parent['sha256'])==64 and all(c in '0123456789abcdef' for c in parent['sha256']))
    prior=value['previousHeader'];exact(prior,{'signature','sha256','data','bytes'})
    need(integer(prior['bytes'],1,base.MAX_HEAD_BYTES) and type(prior['data']) is str and len(prior['data'])<=base.MAX_HEAD_BYTES)
    try:
        packed=base64.b64decode(prior['data'],validate=True);need(base64.b64encode(packed).decode('ascii')==prior['data'])
        stream=zlib.decompressobj();raw=stream.decompress(packed,prior['bytes']+1)
    except (ValueError,zlib.error):need(False)
    need(len(raw)==prior['bytes'] and stream.eof and not stream.unused_data and not stream.unconsumed_tail
        and hashlib.sha256(raw).hexdigest()==prior['sha256'])
    base._signature(prior['signature'],len(raw));old=_old(raw,expected,component)
    need(type(value['manifests']) is list and len(value['manifests'])<=1)
    for ref in value['manifests']:OriginalFrameStore.manifest_reference(ref);need(ref['block']==1)
    if value['manifestIntent'] is not None:
        intent=value['manifestIntent'];exact(intent,{'tabletWebSourcePacketManifestVersion','reference','phase'})
        need(type(intent['tabletWebSourcePacketManifestVersion']) is int and intent['tabletWebSourcePacketManifestVersion']==1
            and intent['phase'] in ('planned','saved'))
        ref=intent['reference'];OriginalFrameStore.manifest_reference(ref)
        need(ref['block']==1 and ref['count']==(value['manifests'][0]['count'] if value['manifests'] else 0)+1)
    if value['copyIntent'] is not None:base._copy(value['copyIntent'],expected)
    first=value['firstRecord']
    if first is not None:
        exact(first,{'index','sha256','bytes','device','inode'})
        need(type(first['index']) is int and first['index']==FIRST and integer(first['bytes'],2,1048576)
            and integer(first['device'],0,2**64-1) and integer(first['inode'],1,2**64-1)
            and type(first['sha256']) is str and len(first['sha256'])==64 and all(c in '0123456789abcdef' for c in first['sha256']))
    active=value['active']
    if active is None:need(first is None)
    else:
        need(value['manifestIntent'] is None and len(value['manifests'])==1 and value['manifests'][0]['count']==CAPTURES
            and value['copyIntent'] is not None and value['copyIntent']['phase'] in ('opened','saved'))
        segment_header(active,expected,component,first)
        if not active['records'] and active['pending'] is None:
            need(active['nextRaw']==old['nextRaw'] and active['recordIntent'] is active['recordInspection'] is None)
    need(len(canonical(value))+1<=base.MAX_HEAD_BYTES);return raw,old


def snapshot(root,expected,state,component,monotonic):
    """Literal old Packet1/2 reader, forced historical and query-free."""
    _kind(component)
    batch=_OWN_READ.get()
    reader=object.__new__(_OwnPackets if batch is not None else TabletWebPackets);reader.root=Path(root);reader.binding=deepcopy(expected['binding'])
    reader.run,reader.role,reader.fixture,reader.pid=expected['runId'],expected['role'],expected['fixtureUrl'],expected['processId']
    reader.component,reader.module=component,COMPONENTS[component]
    reader.guard=reader.storage_guard=reader.epoch_ms=forbidden;reader.monotonic=monotonic;reader.historical=True;reader.clock=None
    reader.store=PrivateFeatureState(reader.root/children._name(component,expected));reader.state=deepcopy(state);reader.saved=deepcopy(state)
    reader._original_storage()
    if batch is not None:batch.reader(reader)
    reader.history();return reader


def prepare(source,component):
    _kind(component);source.bound();expected=base.scope(source.binding,source.run,source.role,source.fixture,source.pid)
    lease=EmoteOriginalLease(source.root,[]);parent_raw,parent_signature=children._raw(source.store.path)
    proof=children.restore(source.root,source.binding,source.run,source.role,source.fixture,source.pid,source.lock,monotonic=source.monotonic)
    child=source.children[component];packets=child.history()
    need(not child.historical and not child.blocked and packets and same(packets[-1],proof['children'][component])
        and same(child.store.read(),child.saved) and same(child.saved,child.state))
    raw,signature=children._raw(child.store.path);old=_old(raw,expected,component)
    need(all(child.originals.read(child.originals.expand(ref))['status']=='returned' for ref in old['records']))
    parent=source.store.read();children.decode(parent,expected);descriptor=next(row for row in parent['children'] if row['component']==component)
    need(signature==descriptor['signature'] and hashlib.sha256(raw).hexdigest()==descriptor['sha256'])
    value=dict(tabletWebPacketsVersion=3,tabletWebNativeChildContinuationVersion=VERSION,profile=PROFILE,phase='rotating',scope=expected,
        component=component,parent=dict(signature=parent_signature,sha256=hashlib.sha256(parent_raw).hexdigest()),
        previousHeader=dict(signature=signature,sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw),data=base64.b64encode(zlib.compress(raw,9)).decode('ascii')),
        copyIntent=None,manifests=[],manifestIntent=None,firstRecord=None,active=None)
    decode(value,expected,component);lease.guard();return value


def install(source,component,value):
    need(same(prepare(source,component),value));child=source.children[component];raw,signature=children._raw(child.store.path)
    need(signature==value['previousHeader']['signature'] and hashlib.sha256(raw).hexdigest()==value['previousHeader']['sha256'])
    child.store.write(value,child.saved)


def read_barrier(value,binding,run,role,fixture_url,pid,component):
    decode(value,base.scope(binding,run,role,fixture_url,pid),component)
    raise base.TabletHeaderRotating('Native child original prefix remains fenced; whole acquisition is unavailable')


class TabletNativeChildClosedPrefix:
    def __init__(self,root,binding,run,role,fixture_url,pid,component,lock,*,monotonic=time.monotonic):
        self.alive=True;self.root=Path(root);self.expected=base.scope(binding,run,role,fixture_url,pid);self.component=component
        self.lock,self.monotonic=lock,monotonic
        _kind(component);need(isinstance(lock,ScriptSourceLock) and lock.path==self.root/'script-feature-sources.lock');lock.assert_held()
        self.store=PrivateFeatureState(self.root/children._name(component,self.expected));self.state=self.store.read()
        self.raw,self.old=decode(self.state,self.expected,component);self.peers=self._read_peers()
        self.copies=OriginalFrameStore(root,binding,run,role,self.guard,self.intent,
            namespace='tabletweb-'+component+'-closed',schema_prefix='tabletWebClosedHeader',monotonic=monotonic)
        self.records=OriginalFrameStore(root,binding,run,role,self.guard,self.intent,
            namespace='tabletweb-'+component+'-packets',schema_prefix='tabletWebSourcePacket',monotonic=monotonic)
        self.guard()

    def _parent(self):
        expected=self.expected;path=self.root/('tabletweb-source-owner-'+expected['runId']+'-'+expected['role']+'.json')
        raw,signature=children._raw(path)
        need(signature==self.state['parent']['signature'] and hashlib.sha256(raw).hexdigest()==self.state['parent']['sha256'])
        parent=PrivateFeatureState(path).read();children.decode(parent,expected);return parent

    def _read_peers(self):
        peers={};expected=self.expected
        for child in self._parent()['children']:
            name=child['component']
            if name==self.component:continue
            path=self.root/child['headerName'];raw,signature=children._raw(path);digest=hashlib.sha256(raw).hexdigest()
            if signature!=child['signature'] or digest!=child['sha256']:
                args=(self.root,expected['binding'],expected['runId'],expected['role'],expected['fixtureUrl'],expected['processId'])
                if name=='dom':
                    from ios.adapters.tablet_web_dom_original_link import read
                    proof=read(*args,self.lock,monotonic=self.monotonic)
                elif name=='uikit':
                    from ios.adapters.tablet_web_uikit_original_link import read
                    proof=read(*args,self.lock,monotonic=self.monotonic)
                else:proof=read_own(*args,name,self.lock,monotonic=self.monotonic)
                need(proof['component']==name and proof['subgraphOnly'] is True and proof['peerAuthority'] is False)
                confirmed,identity=children._raw(path);need(confirmed==raw and identity==signature)
            peers[name]=dict(signature=signature,sha256=digest)
        return peers

    def guard(self):
        need(self.alive);self.lock.assert_held();need(same(self.store.read(),self.state))
        raw,old=decode(self.state,self.expected,self.component);need(raw==self.raw and same(old,self.old))
        parent=self._parent();reference=parent['copyIntent'];need(reference is not None and reference['phase'] in ('opened','saved'))
        def locked():self.lock.assert_held();return True
        e=self.expected
        copies=OriginalFrameStore(self.root,e['binding'],e['runId'],e['role'],locked,forbidden,
            namespace='tabletweb-closed-headers',schema_prefix='tabletWebClosedHeader',monotonic=self.monotonic)
        need(same(copies.read(reference),children.copy_body(parent,e)))
        for child in parent['children']:
            if child['component']==self.component:
                need(child['signature']==self.state['previousHeader']['signature'] and child['sha256']==self.state['previousHeader']['sha256']
                    and child['lastRecord']==self.old['records'][-1] and child['nextRaw']==self.old['nextRaw'])
            else:
                actual,identity=children._raw(self.root/child['headerName']);prior=self.peers[child['component']]
                need(identity==prior['signature'] and hashlib.sha256(actual).hexdigest()==prior['sha256'])
        return True

    def body(self):
        return dict(tabletWebNativeChildClosedBodyVersion=BODY_VERSION,profile=PROFILE,component=self.component,
            scope=deepcopy(self.expected),parent=deepcopy(self.state['parent']),previousHeader=deepcopy(self.state['previousHeader']))

    def save(self,value):
        self.guard();decode(value,self.expected,self.component);self.store.write(value,self.state);self.state=deepcopy(value)

    def intent(self,kind,value):
        changed=deepcopy(self.state)
        if kind=='original':
            base._copy(value,self.expected);previous=changed['copyIntent']
            if previous is None:need(value['phase']=='planned')
            else:need((previous['phase'],value['phase']) in (('planned','opened'),('opened','saved'))
                and all(same(value[key],previous[key]) for key in value if key not in ('phase','file'))
                and (previous['file'] is None or same(previous['file'],value['file'])))
            changed['copyIntent']=deepcopy(value)
        else:
            need(kind=='manifest');previous=changed['manifestIntent']
            if previous is None:need(value['phase']=='planned')
            else:need(previous['phase']=='planned' and value['phase']=='saved' and same(previous['reference'],value['reference']))
            changed['manifestIntent']=deepcopy(value)
        self.save(changed)

    def copy(self):need(self.state['copyIntent'] is None);return self.copies.write(1,self.body())

    def index(self):
        need(self.state['active'] is None and self.state['copyIntent'] is not None and self.state['copyIntent']['phase']=='saved'
            and same(self.copies.read(self.state['copyIntent']),self.body()) and self.state['manifestIntent'] is None)
        count=self.state['manifests'][0]['count'] if self.state['manifests'] else 0
        for ref in self.old['records'][count:]:
            refs=self.records.append(self.state['manifests'],ref);changed=deepcopy(self.state)
            changed.update(manifests=refs,manifestIntent=None);self.save(changed)

    def history(self):
        self.guard();lease=EmoteOriginalLease(self.root,[])
        need(self.state['copyIntent'] is not None and self.state['copyIntent']['phase'] in ('opened','saved')
            and same(self.copies.read(self.state['copyIntent']),self.body()) and self.state['manifestIntent'] is None
            and len(self.state['manifests'])==1 and self.state['manifests'][0]['count']==CAPTURES
            and same(self.records.manifest(self.state['manifests'][0]),self.old['records']))
        need(all(row['status']=='returned' for row in self.records.restore(self.state['manifests'],CAPTURES)))
        reader=snapshot(self.root,self.expected,self.old,self.component,self.monotonic);packets=reader.history()
        need(not reader.blocked and packets);self.guard();lease.guard()
        return dict(component=self.component,historicalOnly=True,phase='rotating',globalIndex=CAPTURES,nextIndex=FIRST,
            nextRaw=self.old['nextRaw'],nativeFloor=deepcopy(packets[-1]))


class _OwnPrefix(TabletNativeChildClosedPrefix):
    def _read_peers(self):
        peers={}
        for child in self._parent()['children']:
            if child['component']==self.component:continue
            raw,signature=children._raw(self.root/child['headerName'])
            peers[child['component']]=dict(signature=signature,sha256=hashlib.sha256(raw).hexdigest())
        return peers

    def guard(self):
        need(self.alive);batch=_OWN_READ.get()
        if batch is not None and batch.prefix is self:
            batch.local();result=super().guard();batch.local();return result
        self.inventory.guard();result=super().guard();self.inventory.guard();return result

    save=intent=copy=index=forbidden


def read_own(root,binding,run,role,fixture_url,pid,component,lock,*,monotonic=time.monotonic):
    prefix=object.__new__(_OwnPrefix);prefix.alive=True;batch=token=None;inventory=None
    try:
        with _literal_own_reads(),file_reads(fresh=True) as reads:
            try:
                need(_OWN_READ.get() is None)
                prefix.inventory=inventory=EmoteOriginalLease(root,[])
                prefix.__init__(root,binding,run,role,fixture_url,pid,component,lock,monotonic=monotonic)
                batch=_OwnReadBatch(prefix,reads);token=_OWN_READ.set(batch);batch.bind()
                if prefix.state['active'] is None:result=prefix.history()
                else:
                    reader=object.__new__(TabletNativeChildSegment);reader.root=Path(root);reader.binding=deepcopy(binding)
                    reader.run,reader.role,reader.fixture,reader.pid=run,role,fixture_url,pid
                    reader.component,reader.module=component,COMPONENTS[component]
                    reader.lock,reader._current_guard,reader._pinned_guard=lock,forbidden,forbidden
                    reader.monotonic,reader.epoch_ms,reader.historical,reader.clock=monotonic,forbidden,True,None
                    reader.closed=prefix;reader.store=prefix.store;reader.state=deepcopy(prefix.state['active']);reader.saved=deepcopy(reader.state)
                    reader.guard=reader.storage_guard=reader._bound;reader._original_storage();batch.reader(reader);packets=reader.history()
                    need(not reader.blocked and packets and reader.state['pending'] is reader.state['recordIntent'] is reader.state['recordInspection'] is None)
                    result=dict(component=component,historicalOnly=True,phase='rotating',globalIndex=reader._next_index()-1,
                        nextIndex=reader._next_index(),nextRaw=reader.state['nextRaw'],nativeFloor=deepcopy(packets[-1]))
                prefix.guard();result=deepcopy(dict(result,subgraphOnly=True,peerAuthority=False))
            finally:
                try:
                    if batch is not None:batch.finish()
                    elif inventory is not None:
                        try:
                            need(isinstance(lock,ScriptSourceLock));lock.assert_held()
                        finally:inventory.guard()
                finally:
                    if batch is not None:batch.active=False
                    if token is not None:_OWN_READ.reset(token)
                    prefix.alive=False
        for path in reads:original_read(path)
        return result
    finally:prefix.alive=False


def open_initial_segment(root,binding,run,role,fixture_url,pid,component,lock,guard,*,monotonic=time.monotonic,epoch_ms=lambda:int(time.time()*1000)):
    _kind(component);need(callable(guard) and guard() is not False)
    prefix=TabletNativeChildClosedPrefix(root,binding,run,role,fixture_url,pid,component,lock,monotonic=monotonic)
    need(prefix.state['active'] is None);proof=prefix.history();need(guard() is not False)
    active=dict(tabletWebNativeChildActiveSegmentVersion=ACTIVE_VERSION,binding=deepcopy(binding),runId=run,role=role,
        fixtureUrl=fixture_url,processId=pid,component=component,firstIndex=FIRST,nextRaw=proof['nextRaw'],records=[],
        pending=None,recordIntent=None,recordInspection=None)
    value=deepcopy(prefix.state);value['active']=active;prefix.save(value)
    return TabletNativeChildSegment(root,binding,run,role,fixture_url,pid,component,lock,guard,monotonic=monotonic,epoch_ms=epoch_ms)


class TabletNativeChildSegment(TabletWebPackets):
    def __init__(self,root,binding,run,role,fixture_url,pid,component,lock,guard,*,monotonic=time.monotonic,epoch_ms=lambda:int(time.time()*1000),historical=False):
        _kind(component);need(type(historical) is bool and all(callable(fn) for fn in (guard,monotonic,epoch_ms))
            and (historical or guard() is not False))
        self.root=Path(root);self.binding=deepcopy(binding);self.run,self.role,self.fixture,self.pid=run,role,fixture_url,pid
        self.component,self.module=component,COMPONENTS[component];self.lock,self._current_guard,self._pinned_guard=lock,guard,guard
        self.monotonic,self.epoch_ms,self.historical,self.clock=monotonic,epoch_ms,historical,None
        self.closed=TabletNativeChildClosedPrefix(root,binding,run,role,fixture_url,pid,component,lock,monotonic=monotonic)
        need(self.closed.state['active'] is not None);self.store=self.closed.store;self.state=deepcopy(self.closed.state['active']);self.saved=deepcopy(self.state)
        self.guard=self.storage_guard=self._bound;self._original_storage();self.history();self._bound()

    def _bound(self):
        need(self._current_guard is self._pinned_guard and (self.historical or self._current_guard() is not False)
            and self.lock is self.closed.lock and self.component==self.closed.component
            and same(base.scope(self.binding,self.run,self.role,self.fixture,self.pid),self.closed.expected))
        return self.closed.guard()

    def _header(self):segment_header(self.state,self.closed.expected,self.component,self.closed.state['firstRecord'])
    def _record_start(self):return FIRST
    def stamp(self):need(not self.historical);return super().stamp()

    def reference(self,index):
        self._bound();self._header();need(integer(index,1,self._next_index()-1))
        ref=self.closed.old['records'][index-1] if index<FIRST else self.state['records'][index-FIRST]
        need(ref['index']==index);return deepcopy(ref)

    def history(self):
        self._bound();lease=EmoteOriginalLease(self.root,[]);result=super().history()
        for ref in self.state['records']:
            if self.originals.read(self.originals.expand(ref))['status']!='returned':self.blocked=True
        self._bound();lease.guard();return result

    def save(self):
        need(not self.historical);self._bound();need(same(self.saved,self.closed.state['active']))
        value=deepcopy(self.closed.state);value['active']=deepcopy(self.state)
        if value['firstRecord'] is None and self.state['records']:
            need(not self.saved['records'] and len(self.state['records'])==1 and self.saved['pending'] is not None and self.saved['recordIntent'] is not None)
            ref=self.originals.original(self.saved['recordIntent'])
            need(ref['index']==FIRST and ref['phase'] in ('opened','saved')
                and same(self.originals.compact(dict(ref,phase='saved')),self.state['records'][0]) and same(self.originals.read(ref),self.saved['pending']))
            value['firstRecord']=deepcopy(self.state['records'][0])
        segment_header(self.state,self.closed.expected,self.component,value['firstRecord'])
        self.closed.save(value);self.saved=deepcopy(self.state)

    def _history_prefix(self):
        self.closed.history();reader=snapshot(self.root,self.closed.expected,self.closed.old,self.component,self.monotonic)
        packets=reader.history();need(not reader.blocked and packets);queries=set()
        for ref in self.closed.old['records']:
            row=reader.originals.read(reader.originals.expand(ref))
            need(row['query'] is not None and row['query']['commandId'] not in queries);queries.add(row['query']['commandId'])
        return deepcopy(packets[-1]),packets,self.closed.old['nextRaw'],queries,deepcopy(reader.clock)
