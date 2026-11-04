"""Source2-only prospective bill of actual known Snapshot originals.

This grants no Native/input/restore authority. A live typed Snapshot context
supplies its existing original owners; names alone never admit a new file.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
from json import encoder as _JSON_ENCODER_MODULE,decoder as _JSON_DECODER_MODULE,scanner as _JSON_SCANNER_MODULE
import os
from pathlib import Path
import re
import stat
import sys
import threading
from types import FunctionType

from adapters.chat_journey.archive_file import signature
from adapters.chat_journey.source_chunks import digest
from adapters.host_process_identity import host_identity
from adapters.native_fd_owner import OriginalDescriptor,require_directory
from adapters.native_feature_observation import need,integer
from adapters.pico4.lifecycle_namespace_bill import canonical_size,strict
from adapters.script_journey.history import canonical,unpack,MAX_FRAMES,MAX_RAW

UNRESOLVED=[]
# Original module objects/classes; inspect only raw class dictionaries below.
_JSON_CLASSES=(json.JSONEncoder,json.JSONDecoder)
_GROUP_RECORD_BYTES=2*65536


def _raw_class(cls):
    need(type(cls) is type)
    return type.__getattribute__(cls,'__dict__')


def _raw_function(cls,name):
    value=_raw_class(cls)[name]
    if type(value) is staticmethod:value=object.__getattribute__(value,'__func__')
    need(type(value) is FunctionType)
    return value


def _managed_class_guard():
    # Read only the original built-in metaclass's raw mapping: no application
    # descriptor, instance __dict__ getter or method bind precedes this proof.
    for cls,mro,fields,codes in _MANAGED_CLASS_PROOFS:
        current=_raw_class(cls)
        need(type.__getattribute__(cls,'__mro__') is mro and len(current)==len(fields)
            and all(type(name) is str for name in current) and all(current.get(name) is value for name,value in fields))
        for fn,code in codes:need(fn.__code__ is code)


class _SnapshotPackedCosts:
    SLOTS=512
    SLOT_BYTES=768
    FIXED_BYTES=4096
    def __init__(self,functions,constants):
        _managed_class_guard()
        need(type(functions) is tuple and type(constants) is tuple
            and len(functions)<=64 and all(callable(fn) for fn in functions) and all(type(value) is int for value in constants))
        self.functions=self._functions=functions
        self.codes=self._codes=tuple(getattr(fn,'__code__',None) for fn in functions)
        self.constants=self._constants=constants
        defaults=[];default_count=0
        for fn in functions:
            args=getattr(fn,'__defaults__',None);kwargs=getattr(fn,'__kwdefaults__',None)
            need(args is None or type(args) is tuple and len(args)<=64)
            need(kwargs is None or type(kwargs) is dict and len(kwargs)<=64
                and all(type(key) is str and len(key)<=128 for key in kwargs))
            entries=() if kwargs is None else tuple(kwargs.items())
            defaults.append((args,kwargs,entries));default_count+=1+(0 if args is None else len(args))+len(entries)
        self.defaults=self._defaults=tuple(defaults)
        self.default_bill=self._default_bill=3*256*default_count
        self.rows=self._rows=();self.pending=self._pending=None
        self.failed=False;self.hits=self.misses=0

    def guard(self,functions,constants):
        _managed_class_guard()
        need(self.failed is False and self.functions is self._functions and self.codes is self._codes
            and self.constants is self._constants and type(functions) is tuple and len(functions)==len(self.functions)
            and all(a is b for a,b in zip(functions,self.functions))
            and all(getattr(fn,'__code__',None) is code for fn,code in zip(functions,self.codes))
            and type(constants) is tuple and all(type(value) is int for value in constants) and constants==self.constants)
        need(self.defaults is self._defaults and type(self.defaults) is tuple and len(self.defaults)==len(self.functions)
            and self.default_bill is self._default_bill and integer(self.default_bill,0,16777216))
        for fn,(args,kwargs,entries) in zip(self.functions,self.defaults):
            need(getattr(fn,'__defaults__',None) is args and getattr(fn,'__kwdefaults__',None) is kwargs)
            if kwargs is not None:
                need(type(kwargs) is dict and len(kwargs)==len(entries)
                    and all(type(key) is str for key in kwargs) and all(kwargs.get(key) is value for key,value in entries))
        need(self.rows is self._rows and type(self.rows) is tuple and self.pending is self._pending
            and len(self.rows)+(self.pending is not None)<=self.SLOTS)
        need(type(self.SLOTS) is int and self.SLOTS==512 and type(self.SLOT_BYTES) is int and self.SLOT_BYTES==768 and type(self.FIXED_BYTES) is int and self.FIXED_BYTES==4096)
        if self.pending is not None:
            need(type(self.pending) is tuple and len(self.pending)==2 and type(self.pending[1]) is object)
            _COST_KEY(self.pending[0])

    @staticmethod
    def key(key):
        _managed_class_guard()
        need(type(key) is tuple and len(key)==3 and type(key[0]) is str and 0<len(key[0])<=128
            and re.fullmatch('[A-Za-z0-9_.-]{1,128}',key[0]) and type(key[1]) is str and re.fullmatch('[0-9a-f]{64}',key[1])
            and integer(key[2],1,65536))

    def metadata_bytes(self):
        _managed_class_guard()
        need(self.rows is self._rows and self.pending is self._pending)
        return self.FIXED_BYTES+self.SLOT_BYTES*(len(self.rows)+(self.pending is not None))

    def lookup(self,key):
        _managed_class_guard()
        _COST_KEY(key);need(self.pending is None)
        for row in self.rows:
            if row[:3]==key:self.hits+=1;return row[3:]
        return None

    def next_metadata_bytes(self):
        _managed_class_guard()
        need(self.pending is None)
        return self.SLOT_BYTES if len(self.rows)<self.SLOTS else 0

    def begin(self,key):
        _managed_class_guard()
        # Caller admits next_metadata_bytes in the SAME actual global bill
        # BEFORE allocating this pending row. A full memo uses the old path.
        _COST_KEY(key);need(self.pending is None)
        if len(self.rows)>=self.SLOTS:return None
        ticket=(key,object());self.pending=self._pending=ticket;return ticket

    def finish(self,ticket,delta,largest):
        _managed_class_guard()
        need(self.pending is self._pending is ticket and type(ticket) is tuple and len(ticket)==2
            and integer(delta,0,16777216) and integer(largest,0,delta))
        _COST_KEY(ticket[0]);entry=(*ticket[0],delta,largest)
        need(canonical_size(list(entry),256)<=256)
        self.rows=self._rows=(*self.rows,entry)
        self.pending=self._pending=None;self.misses+=1



class SnapshotSettingsNamespaceBill:
    def __init__(self,raw):
        _managed_class_guard()
        self.raw=self.original_raw=raw;self.lock=self.original_lock=raw.lock
        self.path=self.original_path=raw.path.parent;self.host=host_identity();self.thread=threading.get_ident()
        self.decoding=self.original_decoding=False
        need(all(type(cls) is type and len(cls.__dict__)<=128 for cls in _JSON_CLASSES))
        self.json_states=self.original_json_states=tuple((cls,tuple(cls.__dict__.items())) for cls in _JSON_CLASSES)
        self.json_bill=self.original_json_bill=3*256*sum(len(fields) for cls,fields in self.json_states)
        self.costs=self.original_costs=_SnapshotPackedCosts(self.cost_functions(),self.cost_constants())
        self.json_bill=self.original_json_bill=self.json_bill+self.costs.default_bill+3*256*sum(len(fields)+len(mro) for cls,mro,fields,codes in _MANAGED_CLASS_PROOFS)
        self.pure_methods=self.original_pure_methods=tuple((name,_raw_function(SnapshotSettingsNamespaceBill,name),
            _raw_function(SnapshotSettingsNamespaceBill,name).__code__) for name in
            ('cost_functions','cost_constants','cost_method_guard','plain_record'))
        self.cost_methods=self.original_cost_methods=tuple((name,_raw_function(_SnapshotPackedCosts,name),
            _raw_function(_SnapshotPackedCosts,name).__code__) for name in
            ('guard','key','lookup','next_metadata_bytes','begin','finish','metadata_bytes'))
        self.directory=self.original_directory=object.__new__(OriginalDescriptor)
        self.windows=[];self.failed=False
        try:
            OriginalDescriptor.__init__(self.directory,self.path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
            self.resource()
        except BaseException:_NAMESPACE_POISON(self);raise

    @staticmethod
    def cost_functions():
        # Actual used parser/length/decoder entrypoints, not a source verdict.
        return (strict,canonical_size,unpack,canonical,integer,need,
            strict.__globals__['json'].loads,canonical.__globals__['json'].dumps,
            canonical_size.__globals__['re'].finditer,
            unpack.__globals__['exact'],unpack.__globals__['integer'],unpack.__globals__['need'],
            unpack.__globals__['json'].loads,unpack.__globals__['canonical'],
            unpack.__globals__['base64'].b64decode,unpack.__globals__['base64'].b64encode,
            unpack.__globals__['zlib'].decompressobj,unpack.__globals__['hashlib'].sha256,
            unpack.__globals__['re'].fullmatch,
            json.__dict__.get('JSONEncoder'),json.__dict__.get('JSONDecoder'),
            *(_JSON_CLASSES[0].__dict__.get(name) for name in ('__init__','default','encode','iterencode')),
            *(_JSON_CLASSES[1].__dict__.get(name) for name in ('__init__','decode','raw_decode')),
            _JSON_ENCODER_MODULE.__dict__.get('_make_iterencode'),_JSON_ENCODER_MODULE.__dict__.get('c_make_encoder'),
            _JSON_ENCODER_MODULE.__dict__.get('encode_basestring_ascii'),_JSON_ENCODER_MODULE.__dict__.get('encode_basestring'),
            _JSON_DECODER_MODULE.__dict__.get('scanstring'),_JSON_DECODER_MODULE.__dict__.get('JSONObject'),
            _JSON_DECODER_MODULE.__dict__.get('JSONArray'),_JSON_DECODER_MODULE.__dict__.get('py_scanstring'),_JSON_SCANNER_MODULE.__dict__.get('make_scanner'),
            _JSON_SCANNER_MODULE.__dict__.get('py_make_scanner'))

    @staticmethod
    def cost_constants():
        return (MAX_RAW,MAX_FRAMES,unpack.__globals__['MAX_RAW'],
            unpack.__globals__['MAX_FRAMES'],unpack.__globals__['MAX_PACKED'],_GROUP_RECORD_BYTES)

    def cost_method_guard(self):
        _managed_class_guard()
        # No caller-overridden helper may run inside the callback-free phase.
        need(self.cost_methods is self.original_cost_methods and type(self.cost_methods) is tuple
            and len(self.cost_methods)==7 and type(self.costs) is _SnapshotPackedCosts
            and _raw_class(_SnapshotPackedCosts).get('__getattribute__',object.__getattribute__) is object.__getattribute__)
        need(self.pure_methods is self.original_pure_methods and type(self.pure_methods) is tuple
            and len(self.pure_methods)==4 and _raw_class(SnapshotSettingsNamespaceBill).get('__getattribute__',object.__getattribute__) is object.__getattribute__)
        fields=object.__getattribute__(self,'__dict__')
        for name,method,code in self.pure_methods:
            need(name not in fields and _raw_function(SnapshotSettingsNamespaceBill,name) is method and method.__code__ is code)
        need(self.json_states is self.original_json_states and type(self.json_states) is tuple and len(self.json_states)==2
            and self.json_bill is self.original_json_bill and integer(self.json_bill,0,MAX_RAW))
        for cls,fields in self.json_states:
            # No descriptor lookup on a potentially foreign class. Exact type
            # plus raw dictionary value-IS also catches new data descriptors.
            need(type(cls) is type and type(fields) is tuple and len(fields)<=128
                and len(cls.__dict__)==len(fields) and all(type(name) is str for name in cls.__dict__)
                and all(cls.__dict__.get(name) is value for name,value in fields))
        fields=object.__getattribute__(self.costs,'__dict__')
        for name,method,code in self.cost_methods:
            need(name not in fields and _raw_function(_SnapshotPackedCosts,name) is method and method.__code__ is code)
        self.costs.guard(self.pure_methods[0][1](),self.pure_methods[1][1]())

    @staticmethod
    def plain_record(value,depth=0):
        # A strict record normally consists only of these exact builtin types.
        # The old guarded path remains available for another decoder/debugger.
        kind=type(value)
        if any(kind is original for original in (str,int,float,bool,type(None))):return True
        if depth>512:return False
        if kind is list:return all(SnapshotSettingsNamespaceBill.plain_record(item,depth+1) for item in value)
        if kind is dict:return all(type(key) is str and SnapshotSettingsNamespaceBill.plain_record(item,depth+1)
            for key,item in value.items())
        return False

    def poison(self):
        # Failure retains even a class-descriptor substitution without invoking
        # the substituted __getattribute__/__dict__/failed descriptor.
        state=_NAMESPACE_DICT.__get__(self,SnapshotSettingsNamespaceBill)
        need(type(state) is dict);state['failed']=True
        if not any(owner is self for owner in UNRESOLVED):UNRESOLVED.append(self)

    def resource(self):
        _managed_class_guard()
        need(self.decoding is self.original_decoding is False)
        need(not self.failed and self.raw is self.original_raw and self.lock is self.original_lock
            and self.path is self.original_path and self.directory is self.original_directory
            and self.raw.path.parent==self.path and self.host==host_identity() and self.thread==threading.get_ident())
        need(self.costs is self.original_costs and type(self.costs) is _SnapshotPackedCosts)
        need(self.pure_methods is self.original_pure_methods and type(self.pure_methods) is tuple and len(self.pure_methods)==4)
        for name,method,code in self.pure_methods:
            need(name not in object.__getattribute__(self,'__dict__')
                and _raw_function(SnapshotSettingsNamespaceBill,name) is method and method.__code__ is code)
        _NAMESPACE_COST_GUARD(self)
        self.lock.assert_held();require_directory(self.directory,self.path)

    def read(self,path,expected,physical,mutex=None):
        """Fresh complete bytes from a KNOWN original, never inode discovery."""
        self.resource();need(path.parent==self.path and type(expected) is bytes and len(expected)<=65536)
        owner=object.__new__(OriginalDescriptor);self.windows.append(owner)
        try:
            OriginalDescriptor.__init__(owner,path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK|os.O_CLOEXEC)
            owner.require(owner.fd);before=os.fstat(owner.fd)
            if mutex is not None:mutex._check(owner.fd,path)
            need(stat.S_ISREG(before.st_mode) and before.st_uid==os.geteuid() and before.st_nlink==1
                and stat.S_IMODE(before.st_mode)==0o600 and signature(before)==list(physical))
            raw=os.pread(owner.fd,65537,0);owner.require(owner.fd);self.resource()
            need(raw==expected and len(raw)==before.st_size and signature(path.lstat())==signature(os.fstat(owner.fd))==list(physical))
            if mutex is not None:mutex._check(owner.fd,path)
            need(owner.close());self.windows.remove(owner);return raw
        except BaseException:_NAMESPACE_POISON(self);raise

    def known(self,context):
        """Only the actual existing owners can supply expected root/manifests."""
        from adapters.pico4.snapshot_settings_scope2_baseline import PicoSnapshotSettingsScope2Baseline
        from adapters.pico4.snapshot_cancel_owner import PicoSnapshotCancelOwner
        from adapters.pico4.snapshot_close_owner import PicoSnapshotCloseOwner
        need(type(context) is PicoSnapshotSettingsScope2Baseline and context.raw is self.raw
            and context.lock is self.lock and context.run==self.raw.run and context.binding==self.raw.binding)
        context.bound();base=context.parent;need(type(base) is PicoSnapshotCancelOwner)
        roots=[];containers=[];graphs=[];seen_graphs=set()
        def graph(value):
            if value is not None and id(value) not in seen_graphs:
                seen_graphs.add(id(value));graphs.append(value)
        def root(store,value):
            need(store.path.parent==self.path)
            if value is not None:roots.append((store,value));graph(value)
        def originals(owner):
            owner.verify();root(owner.root,owner.disk);graph(owner.values);graph(owner.scope)
            if owner.disk is not None:containers.append(owner)
        root(base.store,base.disk);graph(base.state);originals(base.originals)
        root(context.store,context.disk);graph(context.state);originals(context.originals)
        if base.files.state is not None:root(base.files.store,base.files.state)
        if base.save_owner is not None:
            saved=base.save_owner;need(saved.parent is base and saved.lock is self.lock)
            root(saved.store,saved.disk);graph(saved.state);originals(saved.originals)
        closed=base.close_owner
        if closed is not None:
            need(type(closed) is PicoSnapshotCloseOwner and closed.base is base and closed.lock is self.lock)
            closed.bound();root(closed.store,closed.disk);graph(closed.state);originals(closed.originals);originals(closed.statuses)
            returned=closed.parent;bg=closed.bg
            root(returned.store,returned.disk);graph(returned.state);originals(returned.originals)
            root(bg.store,bg.disk);graph(bg.state);graph(bg.parent);originals(bg.originals)
            root(bg.parent_store,bg.parent_disk);originals(bg.parent_originals)
            for store,header,owner in bg.ancestors:root(store,header);originals(owner)
        checkpoint=context.closed_checkpoint
        need(checkpoint is context.original_closed_checkpoint)
        if checkpoint is not None:
            from adapters.pico4.snapshot_settings_close import PicoSnapshotSettingsClose
            need(type(checkpoint) is PicoSnapshotSettingsClose and checkpoint.baseline is context
                and checkpoint.parent is closed and checkpoint.lock is self.lock)
            checkpoint.bound();root(checkpoint.store,checkpoint.disk);graph(checkpoint.state)
        # The raw root is guarded by its already held original Lifecycle file;
        # its immutable children have their own admitted original descriptors.
        self.raw.resource();root(self.raw.store,self.raw.state)
        rows={};parts=0
        for store,value in roots:
            data=canonical(value)+b'\n';store._parent();physical=signature(store.path.lstat())
            # Expected data comes from actual typed warm owners. Their own
            # guards bracket these full physical windows; no live fact is read
            # from a merely named header.
            if store.path.name in rows:need(rows[store.path.name][1]==data)
            else:rows[store.path.name]=(store.path,data,physical,'root',None)
        for owner in containers:
            manifest=owner.disk['chunks'];history=owner.history
            need(len(manifest)==len(history.identities))
            for i,expected in enumerate(manifest):
                path=history._path(i);need(history.signature(i)==history.identities[i])
                value=history.store(i).read();need(digest(value)==expected and history.signature(i)==history.identities[i])
                data=canonical(value)+b'\n';physical=signature(path.lstat())
                if path.name in rows:need(rows[path.name][1]==data)
                else:rows[path.name]=(path,data,physical,'chunk',None);parts+=1
        for path,data,physical in self.raw.known_children():
            need(path.name not in rows);rows[path.name]=(path,data,list(physical),'chunk',None);parts+=1
        mutex=self.mutex(context)
        try:info=mutex.path.lstat()
        except FileNotFoundError:
            need(base.files.state is None)
        else:
            need(base.files.state is not None and base.files.disk is not None
                and base.files.store.read()==base.files.disk==base.files.state)
            base.files.validate(base.files.state)
            need(mutex.path.name not in rows)
            rows[mutex.path.name]=(mutex.path,b'',signature(info),'mutex',mutex)
        return rows,parts,graphs

    def mutex(self,context):
        from adapters.pico4.snapshot_settings_scope2_baseline import PicoSnapshotSettingsScope2Baseline
        from adapters.pico4.snapshot_capture_files import PicoSnapshotCaptureFiles
        from adapters.script_journey.lock import ScriptSourceLock
        need(type(context) is PicoSnapshotSettingsScope2Baseline and context.raw is self.raw)
        files=context.parent.files
        need(type(files) is PicoSnapshotCaptureFiles and files.source.lock is self.lock
            and type(files.lock) is ScriptSourceLock and files.lock.path.parent==self.path
            and files.lock.path==files.store.path.with_name(files.store.path.name+'.lock'))
        return files.lock

    def measure(self,context):
        """One global family bill; original source and quotas are not reset.

        Existing roots keep their original typed warm owners' authority. This
        opens new full-byte/OFD windows; it does not assert continued OFD
        ownership that those legacy writers never provided.
        """
        _managed_class_guard()
        need(self.decoding is self.original_decoding is False)
        try:
            self.resource();self.raw.codec.guard()
            named={}
            with os.scandir(self.path) as entries:
                for index,entry in enumerate(entries):
                    need(index<4096)
                    if entry.name.startswith('snapshot-'):named[entry.name]=entry
            # Bound actual named files before constructing canonical copies or
            # expanding any history. Names do not admit a root or child.
            sizes={};mutex=self.mutex(context)
            for name,entry in named.items():
                info=entry.stat(follow_symlinks=False)
                need(stat.S_ISREG(info.st_mode) and info.st_uid==os.geteuid()
                    and stat.S_IMODE(info.st_mode)==0o600 and info.st_nlink==1 and 0<=info.st_size<=65536
                    and (info.st_size>0 or name==mutex.path.name))
                sizes[name]=info.st_size
            stored=sum(sizes.values());need(stored<=MAX_RAW)
            # Two bounded copies cover the named JSON and its derived exact
            # expected bytes; all decoded graphs and prospective wire copies
            # are billed separately below.
            need(2*stored+self.costs.metadata_bytes()+self.json_bill+3*65536+2097152<=MAX_RAW)
            rows,parts,graphs=self.known(context);need(set(rows)==set(named) and parts<=MAX_FRAMES)
            expected=sum(len(row[1]) for row in rows.values());need(expected==stored)
            retained=sum(canonical_size(graph) for graph in graphs)
            codec=self.raw.codec.metadata_bytes()+self.costs.metadata_bytes()+self.json_bill;held=self.raw.resource_bytes()
            need(2*stored+retained+codec+held+3*65536+2097152<=MAX_RAW)
            expanded=0;largest=0;entry_largest=0;pure=False;pure_guard=None
            # Canonical bytes are known from typed owners before collection.
            # Book ALL invocation-only DTO/row and possible numeric-slot copies
            # before allocating the first list/record. This is the same budget.
            nonmutex=sum(row[3]!='mutex' for row in rows.values());need(nonmutex>=1)
            # Plan simultaneous DTO extents from the SAME actual known bytes;
            # never assign a fresh byte/part/clock allowance to another group.
            batch_extra=running=0
            for name,(path,data,physical,kind,actual_mutex) in sorted(rows.items()):
                if kind=='mutex':continue
                charge=len(data)-1+3*256;need(charge<=_GROUP_RECORD_BYTES)
                if running and running+charge>_GROUP_RECORD_BYTES:
                    batch_extra=max(batch_extra,running);running=0
                running+=charge
            batch_extra=max(batch_extra,running)
            slot_reserve=min(nonmutex,self.costs.SLOTS-len(self.costs.rows))*self.costs.SLOT_BYTES
            batch=(sys.getprofile() is None and sys.gettrace() is None and
                2*stored+retained+codec+held+3*65536+2097152+batch_extra+slot_reserve<=MAX_RAW)
            if not batch:batch_extra=slot_reserve=0
            codec+=slot_reserve
            def expand(value):
                nonlocal expanded,largest,entry_largest
                if type(value) is dict:
                    if set(value)=={'encoding','bytes','sha256','data'}:
                        size=value['bytes'];need(integer(size,2,MAX_RAW))
                        prospective=expanded+size
                        need(2*stored+max(retained,2*prospective)+max(largest,size)
                            +codec+held+3*65536+2097152+batch_extra<=MAX_RAW)
                        if pure:pure_guard(self)
                        else:self.raw.codec.guard()
                        output=unpack(value)
                        if pure:pure_guard(self)
                        else:self.raw.codec.guard()
                        need(canonical_size(output)==size)
                        expanded=prospective;largest=max(largest,size);entry_largest=max(entry_largest,size);expand(output)
                    else:
                        for item in value.values():expand(item)
                elif type(value) is list:
                    for item in value:expand(item)
            def contribution(key,value,found,prepaid):
                nonlocal expanded,largest,entry_largest,codec
                if found is not None:
                    delta,peak=found;prospective=expanded+delta
                    need(2*stored+max(retained,2*prospective)+max(largest,peak)
                        +codec+held+3*65536+2097152+batch_extra<=MAX_RAW)
                    expanded=prospective;largest=max(largest,peak)
                else:
                    extra=0 if prepaid else self.costs.next_metadata_bytes()
                    need(2*stored+max(retained,2*expanded)+largest
                        +codec+extra+held+3*65536+2097152+batch_extra<=MAX_RAW)
                    ticket=self.costs.begin(key);codec+=extra;start=expanded;entry_largest=0
                    expand(value)
                    if ticket is not None:self.costs.finish(ticket,expanded-start,entry_largest)
            records=[] if batch else None;record_bytes=0
            # The full current credit is backed ONCE, before the first group.
            # expanded/largest/codec/held and original caller clocks never reset.
            decode_credit=MAX_RAW-(2*stored+codec+held+3*65536+2097152+batch_extra)
            need(decode_credit>=retained)
            def flush():
                nonlocal pure,pure_guard,record_bytes
                need(batch and records and record_bytes<=batch_extra)
                self.resource();self.raw.codec.guard();_NAMESPACE_COST_GUARD(self)
                eligible=(sys.getprofile() is None and sys.gettrace() is None
                    and all(self.plain_record(value) for key,value,found in records))
                names=tuple(key[0] for key,value,found in records)
                pure=eligible;pure_guard=self.pure_methods[2][1]
                if pure:
                    state=_NAMESPACE_DICT.__get__(self,SnapshotSettingsNamespaceBill)
                    state['decoding']=state['original_decoding']=True
                try:
                    for key,value,found in records:contribution(key,value,found,True)
                finally:
                    pure=False
                    state=_NAMESPACE_DICT.__get__(self,SnapshotSettingsNamespaceBill)
                    state['decoding']=state['original_decoding']=False
                records.clear();record_bytes=0
                del key,value,found
                _NAMESPACE_COST_GUARD(self);self.raw.codec.guard()
                # No group owns another group's original source window.
                self.resource();self.raw.codec.guard()
            for name,(path,expected_bytes,physical,kind,actual_mutex) in sorted(rows.items()):
                charge=0 if kind=='mutex' else len(expected_bytes)-1+3*256
                if batch and records and record_bytes+charge>_GROUP_RECORD_BYTES:flush()
                raw=self.read(path,expected_bytes,physical,actual_mutex)
                if kind=='mutex':need(raw==b'' and actual_mutex is mutex);continue
                value=strict(raw)
                if kind=='chunk':need(type(value.get('chatSampleChunkVersion')) is int and value['chatSampleChunkVersion']==1)
                key=(name,hashlib.sha256(raw).hexdigest(),len(raw));found=self.costs.lookup(key)
                if batch:
                    records.append((key,value,found));record_bytes+=charge
                    # The producer loop must not extend the last group's DTO
                    # lifetime across its flush/external resource callbacks.
                    del key,value,found,raw
                else:contribution(key,value,found,False)
            if batch:
                if records:flush()
                records=None
                # Final fresh whole-input footer also detects a mutation of an
                # earlier group during a later group's external read window.
                for name,(path,expected_bytes,physical,kind,actual_mutex) in sorted(rows.items()):
                    need(self.read(path,expected_bytes,physical,actual_mutex)==expected_bytes)
            codec=self.raw.codec.metadata_bytes()+self.costs.metadata_bytes()+self.json_bill
            self.resource();self.raw.codec.guard()
            current=set()
            with os.scandir(self.path) as entries:
                for index,entry in enumerate(entries):
                    need(index<4096)
                    if entry.name.startswith('snapshot-'):current.add(entry.name)
            need(current==set(rows))
            return dict(parts=parts,storedBytes=stored,
                decodedBytes=stored+max(retained,2*expanded)+codec+held,
                transientBytes=stored+largest+3*65536+batch_extra,largestExpandedBytes=largest,
                currentGraphBytes=retained,expandedProtocolBytes=expanded)
        except BaseException:_NAMESPACE_POISON(self);raise

    def close_host(self):
        _managed_class_guard()
        if self.failed or self.windows:return False
        self.resource()
        if not self.directory.close():_NAMESPACE_POISON(self);return False
        return True


_NAMESPACE_DICT=_raw_class(SnapshotSettingsNamespaceBill)['__dict__']
_NAMESPACE_POISON=_raw_function(SnapshotSettingsNamespaceBill,'poison')
_NAMESPACE_COST_GUARD=_raw_function(SnapshotSettingsNamespaceBill,'cost_method_guard')
_COST_KEY=_raw_function(_SnapshotPackedCosts,'key')
_MANAGED_CLASS_PROOFS=tuple((cls,type.__getattribute__(cls,'__mro__'),tuple(_raw_class(cls).items()),
    tuple((fn,fn.__code__) for value in _raw_class(cls).values()
        for fn in ([object.__getattribute__(value,'__func__')] if type(value) is staticmethod else [value])
        if type(fn) is FunctionType)) for cls in (_SnapshotPackedCosts,SnapshotSettingsNamespaceBill))
