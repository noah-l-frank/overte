"""One synchronous passive End decode; immutable originals remain authority.

There is no reuse across a call, mutation, SDK operation or phase boundary.
Only the original historical Capture decoder may reuse its identical subtree.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from pathlib import Path
import stat
import sys
import time
from types import FunctionType,ModuleType
from adapters.native_clock_join import digest
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.original_file_reads import collect as collect_reads
from adapters.script_feature.history import same
from ios.adapters.snapshot_capture_owner import IOSSnapshotCaptureOwner
from ios.adapters.snapshot_photos_owner import IOSSnapshotPhotosOwner
from ios.adapters.snapshot_photos_archive import SnapshotPhotosArchive

_ACTIVE=ContextVar('ios_snapshot_photos_end_decode_round',default=None)
_CAPTURE=IOSSnapshotPhotosOwner.capture
_ARCHIVE=IOSSnapshotCaptureOwner.archive.__func__
_GUARD=SnapshotPhotosArchive.guard


def data(value,seen=None,depth=0):
    if type(value) in (str,int,float,bool,bytes,type(None)):return value
    if depth>=6:return ('identity',id(value))
    seen=set() if seen is None else seen
    if id(value) in seen:return ('cycle',id(value))
    seen=seen|{id(value)}
    if type(value) is dict:return tuple(sorted((str(key),data(item,seen,depth+1)) for key,item in value.items()))
    if type(value) in (list,tuple):return tuple(data(item,seen,depth+1) for item in value)
    if type(value) in (set,frozenset):return tuple(sorted((data(item,seen,depth+1) for item in value),key=repr))
    return ('identity',id(value))


def function(value):
    wrapped=getattr(value,'__wrapped__',None)
    cells=tuple((id(cell.cell_contents),id(cell.cell_contents.__code__)) for cell in (value.__closure__ or ()) if isinstance(cell.cell_contents,FunctionType))
    return (id(value),id(value.__code__),data(value.__defaults__),data(value.__kwdefaults__),
        None if not isinstance(wrapped,FunctionType) else (id(wrapped),id(wrapped.__code__)),cells)


def _methods_original(namespace):
    result=[]
    for name,value in sorted(namespace.items()):
        if isinstance(value,FunctionType):result.append((name,function(value)))
        elif isinstance(value,type):
            members=[]
            for parent in value.__mro__:
                for key,item in sorted(vars(parent).items()):
                    # Writer prohibition instrumentation is not a decoder.
                    # Reads/parent checks and all historical guards stay pinned.
                    if parent is PrivateFeatureState and key in ('write','discard'):continue
                    if isinstance(item,(staticmethod,classmethod)):item=item.__func__
                    if isinstance(item,FunctionType):members.append((parent,key,function(item)))
                    elif not key.startswith('__'):members.append((parent,key,data(item)))
            result.append((name,value,tuple(members)))
        elif isinstance(value,ModuleType):result.append((name,id(value)))
    return tuple(result)


def methods(namespace,memo=None):
    """Identical descriptors; an optional memo belongs to ONE identity check."""
    if memo is None:return _methods_original(namespace)
    functions=memo.setdefault('functions',{});classes=memo.setdefault('classes',{})
    def fingerprint(value):
        key=id(value)
        if key not in functions:functions[key]=(value,function(value))
        original,signature=functions[key];need(original is value);return signature
    result=[]
    for name,value in sorted(namespace.items()):
        if isinstance(value,FunctionType):result.append((name,fingerprint(value)))
        elif isinstance(value,type):
            key=id(value)
            if key not in classes:
                members=[]
                for parent in value.__mro__:
                    for attribute,item in sorted(vars(parent).items()):
                        if parent is PrivateFeatureState and attribute in ('write','discard'):continue
                        if isinstance(item,(staticmethod,classmethod)):item=item.__func__
                        if isinstance(item,FunctionType):members.append((parent,attribute,fingerprint(item)))
                        elif not attribute.startswith('__'):members.append((parent,attribute,data(item)))
                classes[key]=(value,tuple(members))
            original,members=classes[key];need(original is value);result.append((name,value,members))
        elif isinstance(value,ModuleType):result.append((name,id(value)))
    return tuple(result)


def modules():
    return {name:module for name,module in tuple(sys.modules.items()) if isinstance(module,ModuleType) and name!=__name__
        and (name.startswith(('ios.adapters.snapshot_','adapters.','feature_journeys.'))
            or name in ('ios.adapters.graphics_history','ios.adapters.bundle_identity','ios.adapters.installed_code','ios.adapters.tablet_web_admission',
                'ios.adapters.assets_controls','ios.adapters.assets_bundle_controls',
                'ios.adapters.assets_tree_controls','ios.adapters.assets_usage_controls'))}


# Original implementations are captured when this opt-in module is imported,
# before any round. Per-round mutable parser constants are additionally pinned.
_ORIGINAL={name:(module,methods(vars(module))) for name,module in modules().items()}


def parser_identity():
    need(IOSSnapshotPhotosOwner.capture is _CAPTURE and IOSSnapshotCaptureOwner.archive.__func__ is _ARCHIVE and SnapshotPhotosArchive.guard is _GUARD)
    # Shared aliases are fingerprinted once in THIS invocation only. Nothing
    # is borrowed from a previous check, readscope, phase or result verdict.
    memo={};current={}
    for name,(module,expected) in _ORIGINAL.items():
        need(sys.modules.get(name) is module);signature=methods(vars(module),memo)
        need(signature==expected);current[name]=(module,signature)
    result=[]
    for name,module in sorted(modules().items()):
        previous=current.get(name)
        signature=previous[1] if previous is not None and previous[0] is module else methods(vars(module),memo)
        constants=tuple((key,data(value)) for key,value in sorted(vars(module).items())
            if key.isupper() and key not in ('_ORIGINAL','_BASELINES','_DEPENDENCIES'))
        result.append((name,id(module),signature,constants))
    return tuple(result)


class InventoryLease:
    """Passive bounded bytes/stat boundary; this grants no product facts."""
    def __init__(self,roots,extras=()):
        from ios.adapters.snapshot_photos_end_graph import node,original_pin
        self.roots=tuple(Path(root) for root in roots);self.extras=tuple(Path(path) for path in extras)
        self.before=self.inventory();self.bytes={path:original_pin(path) for path,row in self.before.items() if stat.S_ISREG(row[2])}
        self.check()
    def inventory(self):
        from ios.adapters.snapshot_photos_end_graph import node
        result={}
        for root in self.roots:
            PrivateFeatureState(root/'photos-round-boundary')._parent();result[root]=node(root)
            entries=list(root.iterdir());need(len(entries)<8192)
            for path in entries:result[path]=node(path)
        for path in self.extras:result[path]=node(path)
        return result
    def check(self):need(self.inventory()==self.before);return True
    def finish(self):
        from ios.adapters.snapshot_photos_end_graph import original_pin
        self.check()
        for path,pin in self.bytes.items():need(same(original_pin(path),pin))
        self.check();return True


class DecodeRound:
    def __init__(self,graph):
        from ios.adapters.snapshot_photos_end_graph import SnapshotPhotosEndGraph
        need(type(graph) is SnapshotPhotosEndGraph);self.graph=graph;self.started=time.monotonic()
        self.paths=None if graph.previous is None else frozenset(graph.verify())
        self.header=deepcopy(graph.previous);self.scope=deepcopy(graph.scope());self.parsers=parser_identity()
        self.lease=InventoryLease(graph.roots.values(),graph.artifacts);self.entry=None;self.capture_reads=frozenset();self.decodes=self.hits=0;self.check()
    def check(self):
        need(0<=time.monotonic()-self.started<25 and same(self.graph.previous,self.header) and same(self.graph.scope(),self.scope)
            and parser_identity()==self.parsers);self.lease.check();return True
    def capture(self,owner,original):
        need(type(owner) is SnapshotPhotosArchive and owner.historical and owner.combined
            and getattr(original,'__func__',None) is _CAPTURE and getattr(owner.guard,'__func__',None) is _GUARD)
        self.check();owner.guard()
        key=(str(owner.root),str(owner.capture_store.path),id(owner.lock),digest(owner.binding),owner.run,owner.fixture_url,digest(owner.capture_pin))
        if self.entry is None:
            with collect_reads() as reads:value=original()
            need(bool(reads) and set(reads)<=set(self.lease.bytes));self.capture_reads=frozenset(reads);self.decodes+=1
            self.entry=(key,value[0],deepcopy(value[1]),value[2],value[3],self.memory(value))
        else:self.hits+=1
        stored,capture,result,artifact,raw,memory=self.entry;need(stored==key and bool(self.capture_reads) and self.capture_reads<=set(self.lease.bytes) and memory==self.memory((capture,result,artifact,raw)))
        # The original reader checks this Photos-to-Capture edge on every call;
        # reuse must preserve that exact check, including a changed live header.
        capture.bound();artifact.bound();need(type(raw) is bytes and type(artifact.state['fact']) is dict)
        if owner.state['capture'] is not None:need(same(owner.state['capture'],dict(resultSha256=digest(result),artifactSha256=digest(artifact.previous),file=artifact.state['fact']['file'])))
        owner.guard();self.check();return capture,deepcopy(result),artifact,raw
    @staticmethod
    def memory(value):
        capture,result,artifact,raw=value
        callbacks=tuple((id(getattr(callback,'__self__',None)),id(getattr(callback,'__func__',callback)),id(getattr(getattr(callback,'__func__',callback),'__code__',None))) for callback in (capture.guard,capture.runtime.component,capture.runtime.inputs,artifact.guard))
        return (type(capture),str(capture.store.path),str(capture.lock.path),id(capture.lock),digest(capture.binding),capture.run,capture.phase.fixture_url,digest(capture.previous),digest(capture.state),capture.historical,capture.combined,
            type(capture.runtime),id(capture.runtime),callbacks,type(artifact),str(artifact.store.path),id(artifact.lock),digest(artifact.binding),artifact.run,artifact.role,artifact.index,
            digest(artifact.previous),digest(artifact.state),digest(result),len(raw))
    def finish(self):self.check();self.lease.finish();self.check()


@contextmanager
def _entered(value):
    token=_ACTIVE.set(value)
    try:yield value
    finally:_ACTIVE.reset(token)


@contextmanager
def scope(graph):
    previous=_ACTIVE.get()
    if previous is not None:
        need(previous.graph is graph);previous.check();yield previous;previous.check();return
    value=DecodeRound(graph)
    with _entered(value):
        yield value
        value.finish()
    # Full graph parsing/byte guards execute after leaving the fast path too.
    if graph.previous is not None:graph.verify()
    graph.last_round_counts=dict(captureDecodes=value.decodes,captureHits=value.hits,captureOriginalReads=len(value.capture_reads))


def capture(owner,original):
    current=_ACTIVE.get()
    if current is None:return original()
    return current.capture(owner,original)


def verified_paths(graph):
    current=_ACTIVE.get()
    if current is None:return None
    need(current.graph is graph and current.paths is not None);current.check();return set(current.paths)
