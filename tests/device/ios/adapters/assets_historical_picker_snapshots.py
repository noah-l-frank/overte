"""One historical Page inventory's exact Picker snapshot interpretations.

Every reuse physically rereads the original dependencies and mutable headers.
Only an unchanged typed snapshot result is reused; current page/native facts,
Episode authority and Page original reads remain outside this scope.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import os
from pathlib import Path
import stat
import sys
from types import FunctionType,MethodType,ModuleType,CodeType
from time import monotonic
from adapters import original_frame_store,native_feature_observation,normal_feature_state,native_clock_join
from adapters.script_feature import history
from ios.adapters import assets_episodes,assets_end_graph
from adapters.native_feature_observation import need
from adapters.original_file_reads import collect,record,active as original_read_active
from adapters.script_feature.history import canonical,same,unpack
from ios.adapters.assets_end_metadata import RecordingAssetsMetadata,signature
from ios.adapters import assets_picker,assets_page_picker,assets_page_lease,assets_born_page_lease
from ios.adapters import assets_page_identity_round,assets_controls,assets_files,normal_input
from ios.adapters import assets_bundle_controls,assets_tree_controls,assets_usage_controls


_MODULES=(assets_picker,assets_page_picker,assets_page_lease,assets_born_page_lease,
    assets_page_identity_round,assets_controls,assets_files,normal_input,original_frame_store,
    native_feature_observation,normal_feature_state,native_clock_join,history,assets_episodes,assets_end_graph,
    assets_bundle_controls,assets_tree_controls,assets_usage_controls)


def _function(value):
    if type(value) in (MethodType,classmethod,staticmethod):value=value.__func__
    return (value,value.__code__) if type(value) is FunctionType else (value,None)


def _bindings():
    result=[]
    for module in _MODULES:
        for name,value in vars(module).items():
            if type(value) is FunctionType:result.append((module,name,None,_function(value)))
            elif type(value) is type and value.__module__==module.__name__:
                result.append((module,name,None,_function(value)))
                for method,member in vars(value).items():
                    if type(member) in (FunctionType,classmethod,staticmethod):result.append((module,name,method,_function(member)))
    return tuple(result)


_BINDINGS=_bindings()
_PICKER_METHODS={name:_function(getattr(assets_page_picker.PageLeasePicker,name))
    for cls in assets_page_picker.PageLeasePicker.__mro__ for name,value in vars(cls).items() if type(value) is FunctionType}
_SOURCE_BYTES={Path(module.__file__).resolve():Path(module.__file__).resolve().read_bytes() for module in _MODULES}
_SOURCE_BYTES[Path(__file__).resolve()]=Path(__file__).resolve().read_bytes()


def policy(pickers=()):
    for module,name,method,expected in _BINDINGS:
        value=vars(module).get(name)
        if method is not None:
            if type(value) is not type:return False
            value=vars(value).get(method)
        if _function(value)!=expected:return False
    return (all(path.read_bytes()==raw for path,raw in _SOURCE_BYTES.items())
        and all(picker.OWNER_VERSION==2 and picker.files.OWNER_VERSION==4 for picker in pickers)
        and all(_function(getattr(picker,name))==expected for picker in pickers for name,expected in _PICKER_METHODS.items()))


def _value(value,seen=None):
    # Keep values in memory only. Type/object/code and complete container
    # contents matter; no repr or target-looking string grants authority.
    seen=set() if seen is None else seen
    if type(value) in (type(None),bool,int,float,str,bytes):return (type(value),value)
    if id(value) in seen:return ('cycle',id(value))
    seen=seen|{id(value)}
    if type(value) is FunctionType:
        cells=tuple(_value(cell.cell_contents,seen) for cell in value.__closure__ or ())
        return (value,value.__code__,_value(value.__defaults__,seen),_value(value.__kwdefaults__,seen),cells)
    if type(value) in (classmethod,staticmethod,MethodType):return (type(value),_value(value.__func__,seen))
    if type(value) is dict:return (dict,tuple((key,_value(item,seen)) for key,item in value.items()))
    if type(value) in (tuple,list):return (type(value),tuple(_value(item,seen) for item in value))
    if type(value) in (set,frozenset):return (type(value),frozenset(_value(item,seen) for item in value))
    if type(value) in (ModuleType,type):return (type(value),value)
    attributes=getattr(value,'__dict__',None)
    if type(attributes) is dict:return (type(value),id(value),_value(attributes,seen))
    # Pattern/ContextVar/C-callable identities are retained. Code-visible
    # module/class members used to reach them are independently pinned below.
    return (type(value),id(value))


class ClosedParserPolicy:
    """Closed repository namespaces plus transitive code-used codec globals."""
    def __init__(self):
        self.rows=[];self.modules=set();self.functions=set();self.classes={};self.module_names={}
        self.repo=Path(__file__).resolve().parents[4]
        for module in (*_MODULES,sys.modules[__name__]):self.module(module)
    def owned(self,module):
        path=vars(module).get('__file__')
        return type(path) is str and Path(path).resolve().is_relative_to(self.repo)
    def add(self,namespace,names):
        names=tuple(names);self.rows.append((namespace,names,tuple(_value(namespace[name]) for name in names)))
    def module(self,module):
        if module in self.modules:return
        self.modules.add(module);namespace=vars(module)
        self.module_names[module]=tuple(namespace);self.add(namespace,self.module_names[module])
        for value in tuple(namespace.values()):self.follow(value)
    def follow(self,value):
        if type(value) is ModuleType:
            if self.owned(value):self.module(value)
        elif type(value) in (classmethod,staticmethod,MethodType):self.follow(value.__func__)
        elif type(value) is FunctionType:self.function(value)
        elif type(value) is type and value not in self.classes and value.__module__.startswith(('ios.','adapters.','feature_journeys.')):
            namespace=vars(value);self.classes[value]=tuple(namespace);self.add(namespace,self.classes[value])
            for item in tuple(namespace.values()):self.follow(item)
    def function(self,function):
        if function in self.functions:return
        self.functions.add(function);names=set()
        def code(value):
            names.update(value.co_names)
            for item in value.co_consts:
                if type(item) is CodeType:code(item)
        code(function.__code__);namespace=function.__globals__
        module=sys.modules.get(namespace.get('__name__'))
        if type(module) is ModuleType and vars(module) is namespace and self.owned(module):self.module(module)
        selected=sorted(names & namespace.keys());self.add(namespace,selected)
        for name in selected:
            value=namespace[name];self.follow(value)
            if type(value) is ModuleType:
                members=vars(value);used=sorted(names & members.keys());self.add(members,used)
                for key in used:self.follow(members[key])
            elif type(value) is type:
                # Method lookup is literal, including an inherited parser port.
                for cls in value.__mro__:
                    members=vars(cls);used=sorted(names & members.keys());self.add(members,used)
                    for key in used:self.follow(members[key])
    def unchanged(self):
        for namespace,names,values in self.rows:
            # Entire repository namespaces were entered with all their keys;
            # distinguish them from a transitive external codec's used subset.
            if any(name not in namespace for name in names):return False
            if tuple(_value(namespace[name]) for name in names)!=values:return False
        for module,names in self.module_names.items():
            if tuple(vars(module))!=names:return False
        for cls,names in self.classes.items():
            if tuple(vars(cls))!=names:return False
        return True


def physical(path,expected=None):
    """Actual private bytes/inode, without assigning any missing birth identity."""
    started=monotonic();path=Path(path);before=signature(path);need(before is not None)
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
    try:
        info=os.fstat(fd)
        need(stat.S_ISREG(info.st_mode) and info.st_uid==os.geteuid() and stat.S_IMODE(info.st_mode)==0o600
            and info.st_nlink==1 and 0<info.st_size<=1024*1024)
        raw=b''
        while len(raw)<=1024*1024:
            part=os.read(fd,min(65536,1024*1024+1-len(raw)))
            if not part:break
            raw+=part
        fields=('st_dev','st_ino','st_mode','st_nlink','st_uid','st_size','st_mtime_ns','st_ctime_ns')
        need(tuple(getattr(info,key) for key in fields)==before
            and tuple(getattr(os.fstat(fd),key) for key in fields)==before and signature(path)==before
            and len(raw)==info.st_size)
    finally:os.close(fd)
    need(monotonic()-started<5)
    value=(before,hashlib.sha256(raw).hexdigest())
    if expected is not None:need(value==expected);record(path)
    return value


class HistoricalPickerSnapshots:
    def __init__(self,episodes,pickers):
        self.episodes,self.pickers=episodes,dict(pickers);self.owner=None;self.active=True;self.enabled=True;self.cache={};self.parser_policy=None
        self.headers=[episodes,episodes.selected,*self.pickers.values(),*[picker.files for picker in self.pickers.values()]]
        self.memory=canonical([(owner.store.path.as_posix(),owner.previous) for owner in self.headers])
        self.fixed=self.interpretation_context()
        self.roots={Path(info[key]) for info in episodes.context['roles'].values() for key in ('stateRoot','artifactRoot')}
        self.roots.update(Path(row['path']) for entry in episodes.state['entries'] for roots in entry['directories'].values()
            for row in roots.values() if row['identity'] is not None)
        self.directories=self.directory_identity();self.guard()
    def interpretation_context(self):
        return canonical([original_read_active(),self.episodes.state,self.episodes.context,self.episodes.selection,
            [(index,id(picker),id(picker.files),picker.binding,picker.files.state,picker.files.binding,
                picker.files.run,picker.files.url,picker.files.role,picker.files.native.pid,
                id(picker.lock),id(picker.files.lock),id(picker.episode),picker.episode.index,
                picker.episode.descriptor,picker.episode.original) for index,picker in sorted(self.pickers.items())]])
    def directory_identity(self):
        result={}
        for root in self.roots:
            entries=list(root.iterdir());need(len(entries)<=8192)
            result[str(root)]=(signature(root),{path.name:signature(path) for path in entries})
        return result
    def bind(self,owner):
        need(self.active and self.owner is None and owner.historical and owner.episodes is self.episodes
            and type(owner) in (assets_page_lease.OwnedAssetsPageLease,assets_born_page_lease.BornAssetsPageLease)
            and all(owner.pickers.get(index) is picker for index,picker in self.pickers.items())
            and set(owner.pickers)==set(self.pickers))
        self.owner=owner;self.headers.append(owner);self.memory=canonical([(value.store.path.as_posix(),value.previous) for value in self.headers]);self.guard()
    def guard(self):
        self.episodes.guard()
        need(self.active and self.memory==canonical([(owner.store.path.as_posix(),owner.previous) for owner in self.headers]))
        need(self.fixed==self.interpretation_context())
        for owner in self.headers:need(same(owner.store.read(),owner.previous))
        for lock in self.episodes.locks.values():lock.assert_held()
        for picker in self.pickers.values():
            picker.lock.assert_held()
            for lock in picker.episode.locks.values():lock.assert_held()
            if picker.state is not None:need(same(picker.state,unpack(picker.previous['payload'])[0]))
        need(self.directories==self.directory_identity())
        return True
    def decode(self,owner,picker,value):
        need(self.active and owner is self.owner and any(picker is item for item in self.pickers.values()))
        if self.parser_policy is None:
            # The Page owner/state/links now exist. The raw skeletons passed to
            # __init__ deliberately have no Page authority and cannot decode.
            need(policy(self.pickers.values()) and not self.cache)
            self.guard()
            for original_picker in self.pickers.values():
                if original_picker.previous is not None:original_picker.decode(deepcopy(original_picker.previous))
                self.guard()
            self.parser_policy=ClosedParserPolicy()
        if not self.enabled or not policy(self.pickers.values()) or not self.parser_policy.unchanged():
            self.enabled=False;self.cache.clear();return picker.decode(value)
        self.guard();key=(id(picker),canonical(value));entry=self.cache.get(key)
        if entry is not None:
            need(canonical(entry['result'])==entry['resultBytes'])
            # The Page record/current header supplied the exact snapshot again.
            # Reread all first-decoder originals with exact physical identities.
            for path,pin in entry['originals'].items():physical(path,pin)
            self.guard();return deepcopy(entry['result'])
        with collect() as reads:result=picker.decode(value)
        originals={path:physical(path) for path in reads};self.guard()
        if policy(self.pickers.values()) and self.parser_policy.unchanged():self.cache[key]=dict(result=deepcopy(result),resultBytes=canonical(result),originals=originals)
        else:self.enabled=False;self.cache.clear()
        return result
    def close(self):
        try:
            if self.parser_policy is None:
                # No snapshot was interpreted or reused. An empty historical
                # scope still requires the original parser and file guards.
                need(not self.cache and policy(self.pickers.values()))
                self.parser_policy=ClosedParserPolicy()
            need(self.parser_policy.unchanged());self.guard()
            for entry in self.cache.values():
                for path,pin in entry['originals'].items():physical(path,pin)
            self.guard()
        finally:
            self.active=False;self.cache.clear()
            if self.owner is not None:
                need(self.owner.snapshot_scope is self);self.owner.snapshot_scope=None
            self.owner=None


@contextmanager
def historical_picker_snapshots(episodes,pickers,metadata):
    if (type(metadata) not in (type(None),RecordingAssetsMetadata) or not policy(pickers.values())
            or any(type(picker) is not assets_page_picker.PageLeasePicker for picker in pickers.values())):
        yield None;return
    scope=HistoricalPickerSnapshots(episodes,pickers)
    try:yield scope
    finally:scope.close()
