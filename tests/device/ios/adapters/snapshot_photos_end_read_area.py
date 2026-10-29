"""Opt-in passive reuse of fully decoded historical Inventory/Capture inputs.

No outcome, current SDK/OS observation or live reader is cached. Every hit
performs actual original byte reads; a remembered pathname is not membership.
The area owns no file or lock and may not survive its caller's read boundary.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import stat
import time
from adapters.native_clock_join import digest
from adapters.native_feature_observation import need
from adapters.normal_feature_state import context
from adapters.original_file_reads import collect,readonly,record
from adapters.script_feature.history import same
from feature_journeys.contract import identifier

_ACTIVE=ContextVar('snapshot_photos_end_passive_read_area',default=None)
MAX_FILES=16384
MAX_ENTRIES=64
MAX_SECONDS=25


def callback(value):
    function=getattr(value,'__func__',value)
    return id(getattr(value,'__self__',None)),id(function),id(getattr(function,'__code__',None))


def memory(owner):
    """Pin every mutable JSON header/state completely, plus runtime aliases."""
    from ios.adapters.snapshot_photos_end_round import data
    rows=[]
    for name,value in sorted(vars(owner).items()):
        if name in ('state','previous','binding','capture_pin','artifact','os_scope'):
            rows.append((name,digest(value)))
        elif callable(value):rows.append((name,callback(value)))
        elif isinstance(value,Path):rows.append((name,str(value)))
        elif type(value) is SimpleNamespace:rows.append((name,digest(vars(value))))
        else:rows.append((name,data(value)))
    return type(owner),id(owner),tuple(rows)


class ReadArea:
    def __init__(self,roots,locks,bindings,run,fixture_url):
        from ios.adapters.snapshot_photos_end_graph import node,original_pin
        # Preload the two deliberate Combined-only lazy parser dependencies
        # before taking parser identities. No observation or decoder runs here.
        from ios.adapters import snapshot_combined_work,snapshot_combined_packets
        # These definitions are reached by the selected historical decoders.
        # Load them before the baseline; their identities remain fully pinned.
        from ios.adapters import snapshot_frontend_branch,snapshot_frontend_consumption
        from feature_journeys import snapshot_concurrency,snapshot_domain_client
        # Page replay reaches these lazy native/UI validators even when the
        # caller did not import a whole test/runtime graph first. Load their
        # definitions BEFORE the parser baseline; all later checks stay exact.
        from adapters import native_animation_history
        from ios.adapters import assets_bundle_controls,assets_tree_controls,assets_usage_controls
        # JourneyFiles.setup replays Pending.archive before Share's next
        # Capture hit. Its historical runtime class is a parser dependency,
        # not a live SDK or source. Pin it before this same baseline too.
        from ios.adapters import snapshot_pending_runtime
        from ios.adapters.snapshot_photos_end_round import parser_identity
        from ios.adapters import snapshot_photos_end_round as parser_module
        need(set(roots)==set(locks)==set(bindings)=={'main','photos','archive'})
        self.roots={name:Path(path) for name,path in roots.items()};need(len(set(self.roots.values()))==3)
        self.locks=dict(locks);self.bindings={name:deepcopy(context(value)) for name,value in bindings.items()}
        self.run,self.fixture_url=identifier(run),fixture_url;self.started=time.monotonic();self.cache={};self.counts={}
        self.descriptor=self.describe()
        for name,lock in self.locks.items():
            need(lock.path==self.roots[name]/'script-feature-sources.lock');lock.assert_held()
        self.parser_module=parser_module;self.parser_functions=self.parser_headers()
        self.parsers=parser_identity();self.before=self.inventory()
        self.bytes={path:original_pin(path) for path,row in self.before.items() if stat.S_ISREG(row[2])}
        self.check()
    def describe(self):
        return digest(dict(roots={name:str(path) for name,path in self.roots.items()},bindings=self.bindings,run=self.run,fixtureUrl=self.fixture_url)),tuple(sorted((name,id(lock),str(lock.path)) for name,lock in self.locks.items()))
    def parser_headers(self):
        return tuple(callback(getattr(self.parser_module,name)) for name in ('parser_identity','data','methods','function','modules'))
    def inventory(self):
        from adapters.normal_feature_state import PrivateFeatureState
        from ios.adapters.snapshot_photos_end_graph import node
        result={}
        for root in self.roots.values():
            PrivateFeatureState(root/'passive-read-boundary')._parent()
            pending=[root]
            while pending:
                path=pending.pop()
                need(len(result)<MAX_FILES);row=node(path)
                need(stat.S_ISDIR(row[2]) or stat.S_ISREG(row[2]) and row[5]==1);result[path]=row
                if len(result)%256==0:need(0<=time.monotonic()-self.started<MAX_SECONDS)
                if stat.S_ISDIR(row[2]):
                    children=[]
                    for child in path.iterdir():
                        if path==root:need(len(children)+1<8192)
                        need(len(result)+len(pending)+len(children)<MAX_FILES);children.append(child)
                    pending.extend(sorted(children,key=str))
        return result
    def check(self):
        from ios.adapters.snapshot_photos_end_round import parser_identity
        need(0<=time.monotonic()-self.started<MAX_SECONDS)
        need(self.describe()==self.descriptor)
        need(self.parser_headers()==self.parser_functions)
        need(parser_identity()==self.parsers)
        for name,lock in self.locks.items():
            need(lock.path==self.roots[name]/'script-feature-sources.lock');lock.assert_held()
        need(self.inventory()==self.before);return True
    def reread(self,paths):
        from ios.adapters.snapshot_photos_end_graph import original_pin
        need(bool(paths) and set(paths)<=set(self.bytes))
        for path in sorted(paths,key=str):
            need(same(original_pin(path),self.bytes[path]))
            # original_pin has just actually opened/read/rechecked this exact
            # no-follow inode. This is actual IO, never membership from a pin.
            record(path)
    def finish(self):
        from ios.adapters.snapshot_photos_end_graph import original_pin
        self.check()
        for key,entry in self.cache.items():
            if entry['kind']=='capture':
                owner=entry['owner'];need(memory(owner)==entry['memory'] and memory(owner.runtime)==entry['runtime']);owner.bound()
            else:
                self.inventory_current(entry['owner'],key,entry)
        for path,pin in self.bytes.items():need(same(original_pin(path),pin))
        self.check()
    def capture(self,cls,store,lock,binding,run,url,combined,decode):
        from ios.adapters.snapshot_capture_owner import IOSSnapshotCaptureOwner
        from ios.adapters.snapshot_capture_runtime import IOSSnapshotCaptureRuntime
        need(cls is IOSSnapshotCaptureOwner and combined is True and store.path==self.roots['main']/'ios-snapshot-primary-capture-owner.json'
            and lock is self.locks['main'] and same(binding,self.bindings['main']) and run==self.run and url==self.fixture_url)
        key=('capture',cls,str(store.path),id(lock),digest(binding),run,'primary',combined,url)
        self.check();entry=self.cache.get(key)
        if entry is None:
            need(len(self.cache)<MAX_ENTRIES)
            with collect() as paths:owner=decode()
            need(type(owner) is IOSSnapshotCaptureOwner and type(owner.runtime) is IOSSnapshotCaptureRuntime and owner.historical
                and owner.combined is True and owner.sources is None and owner.selector is None and owner.lock is lock
                and owner.run==run and same(owner.binding,binding) and owner.store.path==store.path and owner.phase.fixture_url==url
                and same(owner.envelope(owner.state),owner.previous))
            owner.bound();need(bool(paths) and set(paths)<=set(self.bytes))
            entry=dict(kind='capture',owner=owner,memory=memory(owner),runtime=memory(owner.runtime),paths=frozenset(paths))
            self.cache[key]=entry;self.counts['captureDecodes']=self.counts.get('captureDecodes',0)+1
        else:self.counts['captureHits']=self.counts.get('captureHits',0)+1
        owner=entry['owner'];need(memory(owner)==entry['memory'] and memory(owner.runtime)==entry['runtime'])
        owner.bound();self.reread(entry['paths']);owner.bound();self.check();return owner
    def inventory_key(self,owner):
        from ios.adapters.snapshot_share_inventory_owner import SnapshotShareSourceInventoryOwner
        need(type(owner) is SnapshotShareSourceInventoryOwner and owner.historical and owner.ctx is None
            and owner.root==self.roots['archive'] and owner.lock is self.locks['archive'] and owner.run==self.run
            and owner.fixture_url==self.fixture_url and same(owner.binding,self.bindings['archive'])
            and owner.share.historical and owner.share.combined is True and owner.share.root==self.roots['main']
            and owner.share.lock is self.locks['main'] and owner.share.archive_lock is self.locks['archive']
            and same(owner.share.binding,self.bindings['main']))
        return ('inventory',type(owner),str(owner.store.path),id(owner),id(owner.lock),digest(owner.binding),owner.run,'primary',True,owner.fixture_url)
    def inventory_original(self,owner,decode):
        key=self.inventory_key(owner)
        self.check();owner.bound();entry=self.cache.get(key)
        if entry is None:
            need(len(self.cache)<MAX_ENTRIES)
            with collect() as paths:value,raw=decode()
            need(type(value) is dict and type(raw) is bytes and bool(paths) and set(paths)<=set(self.bytes))
            entry=dict(kind='inventory',owner=owner,value=deepcopy(value),raw=raw,headers=self.inventory_headers(owner),paths=frozenset(paths))
            self.cache[key]=entry;self.counts['inventoryDecodes']=self.counts.get('inventoryDecodes',0)+1
        else:self.counts['inventoryHits']=self.counts.get('inventoryHits',0)+1
        self.inventory_current(owner,key,entry)
        self.reread(entry['paths'])
        self.inventory_current(owner,key,entry);self.check()
        return deepcopy(entry['value']),entry['raw']
    @staticmethod
    def inventory_headers(owner):
        return tuple(memory(value) for value in (owner,owner.share,owner.share.queries,owner.sealed,owner.admission))
    def inventory_current(self,owner,key,entry):
        need(self.inventory_key(owner)==key and entry['owner'] is owner
            and self.inventory_headers(owner)==entry['headers'])
        owner.bound()
        need(self.inventory_key(owner)==key and entry['owner'] is owner
            and self.inventory_headers(owner)==entry['headers'])


@contextmanager
def scope(roots,locks,bindings,run,fixture_url):
    # A separate area cannot borrow an earlier factory's in-memory objects.
    need(_ACTIVE.get() is None)
    with readonly():
        area=ReadArea(roots,locks,bindings,run,fixture_url);token=_ACTIVE.set(area)
        try:
            yield area
            area.finish()
        finally:
            _ACTIVE.reset(token);area.cache.clear()


def capture_archive(cls,store,lock,binding,run,fixture_url,combined,decode):
    area=_ACTIVE.get()
    return decode() if area is None else area.capture(cls,store,lock,binding,run,fixture_url,combined,decode)


def inventory_original(owner,decode):
    area=_ACTIVE.get()
    return decode() if area is None else area.inventory_original(owner,decode)



def inventory_original_with_fresh_proof(owner):
    """One atomic pure historical read; no outcome or inter-call memo."""
    area=_ACTIVE.get()
    if area is None:
        value,raw=owner.original();return value,raw,owner.proof()
    area.check();value,raw=owner.original()
    def current_original():
        key=area.inventory_key(owner);entry=area.cache.get(key)
        need(entry is not None);area.inventory_current(owner,key,entry)
    current_original();result=owner._proof_from_original(value,raw)
    current_original();area.check();return value,raw,result
