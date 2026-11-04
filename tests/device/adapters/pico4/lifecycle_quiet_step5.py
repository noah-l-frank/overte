"""Original Background5 quiet copies/window state over the same admitted bank."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from dataclasses import dataclass
import hashlib,math
from types import FunctionType,MethodType
from adapters.native_feature_observation import LIMIT,need
from adapters.chat_journey.source_chunks import json_digest
from adapters.pico4.lifecycle_namespace_bill import canonical_size
from adapters.pico4.lifecycle_background_state5 import LifecycleBackgroundState5,OriginalGraph5,helper_method
from adapters.pico4 import lifecycle_drive as drive
from adapters.script_journey.history import canonical
PART=65536
_ABSENT=object()

def window_checksum(shape,maximum):
    # Fast selection is a bound, NEVER a new accepted grammar/size limit.
    # <=512 queued nodes/64 depth and <=64KiB projected ASCII JSON ensure
    # current text+UTF8+walk temporaries fit the already charged3*PART work.
    pending=[(shape,0,False)];active=set();bound=nodes=0;fast=True
    while pending:
        item,depth,exit=pending.pop()
        if exit:active.remove(id(item));continue
        kind=type(item);nodes+=1
        if nodes>512 or depth>64:fast=False;break
        if kind is dict or kind is list:
            need(id(item) not in active)
            if len(item)>512 or nodes+len(pending)+len(item)>512:fast=False;break
            active.add(id(item));pending.append((item,depth,True))
            bound+=2+max(0,len(item)-1)
            if kind is dict:
                need(all(type(key) is str for key in item))
                bound+=sum(12*len(key)+3 for key in item)
                if bound>PART:fast=False;break
                pending.extend((child,depth+1,False) for child in item.values())
            else:pending.extend((child,depth+1,False) for child in item)
        elif kind is str:bound+=12*len(item)+2
        elif kind is int:bound+=2+item.bit_length()
        elif kind is float:need(math.isfinite(item));bound+=32
        elif kind is bool:bound+=5
        elif kind is type(None):bound+=4
        else:need(False)
        if bound>PART:fast=False;break
    pending=active=None
    if not fast:
        size=canonical_size(shape,maximum);return size,json_digest(shape)
    raw=canonical(shape);need(len(raw)<=bound and len(raw)<=maximum)
    return len(raw),hashlib.sha256(raw).hexdigest()


@dataclass(eq=False)
class QuietHandle5:
    book:object
    stage:object
    invocation:object=None
    role:str=''
    window:object=None
    anchor:object=None
    seal:object=None
    original_seal:object=None


@dataclass(eq=False)
class QuietRequest5:
    book:object
    row:object
    handle:object
    invocation:object
    role:str
    stage:object
    created:bool
    old_seal:object=None
    next_seal:object=None
    mutated:bool=False
    complete:object=None
    confirmed:bool=False
    failed:bool=False
    identity:object=None
    original_identity:object=None


class QuietBook5:
    def __init__(self,helper):
        need(type(helper) is LifecycleBackgroundState5)
        self.helper=helper;self.handles=self._handles=();self.active=self._active=None;self.failed=self.closed=False;self.invocation=None;self.invocations=0
        self.fixed=self._fixed=(helper,helper.owner,helper.bank)
        self.ready=self._ready=False
        self.classes=(drive.AvatarDisplacement,drive.AvatarReleaseWindow)
        methods=[]
        for cls,names in ((self.classes[0],('__init__','measure')),(self.classes[1],('__init__','observe','_observe'))):
            raw=type.__getattribute__(cls,'__dict__')
            for name in names:
                function=raw.get(name);need(type(function) is FunctionType)
                methods.append((cls,name,function,function.__code__))
        self.methods=tuple(methods)
        self.mros=tuple(type.__getattribute__(cls,'__mro__') for cls in self.classes)
        self.dictionaries=tuple(type.__getattribute__(cls,'__dict__')['__dict__'] for cls in self.classes)
        functions=[]
        for name in ('validate','continuity','vector','quaternion'):
            function=getattr(drive,name);need(type(function) is FunctionType)
            functions.append((name,function,function.__code__))
        self.functions=tuple(functions)
        self.records=[]
        for cls in (QuietHandle5,QuietRequest5):
            raw=type.__getattribute__(cls,'__dict__')
            fields=tuple((name,raw.get(name,_ABSENT)) for name in cls.__dataclass_fields__)
            self.records.append((cls,type.__getattribute__(cls,'__mro__'),raw['__dict__'],fields))
        self.records=tuple(self.records)
        self.checksum=(window_checksum,window_checksum.__code__,canonical,canonical.__code__,hashlib.sha256,math.isfinite,canonical_size,canonical_size.__code__,json_digest,json_digest.__code__)
        self.pure=(drive.deepcopy,drive.math.sqrt,drive.number,drive.fresh,drive.integer,drive.need,drive.exact,drive.nonce,drive.urlsplit)
        need(type(drive.deepcopy) is FunctionType)
        dispatch=drive.deepcopy.__globals__.get('_deepcopy_dispatch');need(type(dispatch) is dict)
        handlers=[];atomic=drive.deepcopy.__globals__.get('_atomic_types')
        atomic_ids=None
        if atomic is not None:
            need(type(atomic) is set or type(atomic) is frozenset)
            atomic_ids=frozenset(id(kind) for kind in atomic)
            need(all(id(kind) in atomic_ids for kind in (str,int,float,bool,type(None)))
                and not any(id(kind) in atomic_ids for kind in (dict,list,tuple)))
        kinds=(dict,list,tuple) if atomic is not None else (dict,list,tuple,str,int,float,bool,type(None))
        for kind in kinds:
            function=dispatch.get(kind);need(type(function) is FunctionType)
            handlers.append((kind,function,function.__code__))
        self.copy_profile=(drive.deepcopy,drive.deepcopy.__code__,dispatch,tuple(handlers),atomic,atomic_ids)
        self.ready=self._ready=True

    def profile(self):
        copy=self.copy_profile
        need(type(drive.deepcopy) is FunctionType and drive.deepcopy is copy[0]
            and drive.deepcopy.__code__ is copy[1] and drive.deepcopy.__globals__.get('_deepcopy_dispatch') is copy[2])
        atomic=drive.deepcopy.__globals__.get('_atomic_types')
        need(atomic is copy[4])
        if atomic is not None:
            need((type(atomic) is set or type(atomic) is frozenset)
                and frozenset(id(kind) for kind in atomic)==copy[5])
        for kind,function,code in copy[3]:
            current=copy[2].get(kind);need(type(current) is FunctionType and current is function and current.__code__ is code)
        need(window_checksum is self.checksum[0] and window_checksum.__code__ is self.checksum[1]
            and canonical is self.checksum[2] and canonical.__code__ is self.checksum[3]
            and hashlib.sha256 is self.checksum[4] and math.isfinite is self.checksum[5]
            and type(canonical_size) is FunctionType and canonical_size is self.checksum[6] and canonical_size.__code__ is self.checksum[7]
            and type(json_digest) is FunctionType and json_digest is self.checksum[8] and json_digest.__code__ is self.checksum[9])
        need(drive.AvatarDisplacement is self.classes[0] and drive.AvatarReleaseWindow is self.classes[1])
        need(self.records[0][0] is QuietHandle5 and self.records[1][0] is QuietRequest5)
        for cls,mro,dictionary,fields in self.records:
            raw=type.__getattribute__(cls,'__dict__')
            need(type.__getattribute__(cls,'__mro__') is mro and raw.get('__dict__') is dictionary
                and '__getattribute__' not in raw and '__getattr__' not in raw
                and all(raw.get(name,_ABSENT) is original for name,original in fields))
        for cls,mro,dictionary in zip(self.classes,self.mros,self.dictionaries):
            namespace=type.__getattribute__(cls,'__dict__')
            need(type.__getattribute__(cls,'__mro__') is mro and '__getattribute__' not in namespace and '__getattr__' not in namespace
                and namespace.get('__dict__') is dictionary
                and all(name not in namespace for name in ('original',) if cls is self.classes[0])
                and all(name not in namespace for name in ('anchor','previous','origin','native_start','host_start','host_last') if cls is self.classes[1]))
        for cls,name,function,code in self.methods:
            current=type.__getattribute__(cls,'__dict__').get(name)
            need(type(current) is FunctionType and current is function and current.__code__ is code)
        for name,function,code in self.functions:
            current=getattr(drive,name);need(type(current) is FunctionType and current is function and current.__code__ is code)
        need(all(a is b for a,b in zip((drive.deepcopy,drive.math.sqrt,drive.number,drive.fresh,drive.integer,drive.need,drive.exact,drive.nonce,drive.urlsplit),self.pure)))

    def shape(self,handle):
        book_method(self,'profile')();need(type(handle) is QuietHandle5 and handle.book is self)
        window,anchor=handle.window,handle.anchor
        need(type(window) is self.classes[1] and type(anchor) is self.classes[0] and window.anchor is anchor)
        need(set(object.__getattribute__(window,'__dict__'))=={'anchor','previous','origin','native_start','host_start','host_last'}
            and set(object.__getattribute__(anchor,'__dict__'))=={'original'})
        return dict(anchor=anchor.original,previous=window.previous,origin=window.origin,
            nativeStart=window.native_start,hostStart=window.host_start,hostLast=window.host_last)

    def basic(self):
        need(self.fixed is self._fixed and self.fixed[0] is self.helper
            and self.fixed[1] is self.helper.owner and self.fixed[2] is self.helper.bank
            and self.helper.quiet is self.helper._quiet is self
            and self.handles is self._handles and type(self.handles) is tuple and len(self.handles)<=512
            and self.active is self._active and type(self.ready) is bool and self.ready is self._ready)

    def token(self):
        book_method(self,'basic')();book_method(self,'profile')();helper_method(self.helper,'guard')()
        need(not self.failed and not self.closed and not self.helper.failed and not self.helper.bank.failed
            and not self.helper.bank.frozen and self.active is None and self.invocations<512)
        self.invocations+=1;self.invocation=(self,object(),self.invocations)
        return self.invocation

    def sealed(self,handle):
        shape=book_method(self,'shape')(handle);size,digest=window_checksum(shape,2*LIMIT+4096)
        return (handle.window,handle.anchor,handle.anchor.original,handle.window.previous,handle.window.origin,size,digest)

    def guard_handle(self,handle,*,pending=False):
        book_method(self,'profile')()
        need(type(handle) is QuietHandle5 and handle.book is self
            and any(handle is row for row in self.handles)
            and type(handle.stage) is OriginalGraph5 and handle.stage.holder is self.helper
            and handle.stage.graph is handle and type(handle.seal) is tuple and len(handle.seal)==7
            and handle.seal is handle.original_seal and type(handle.seal[5]) is int
            and 0<=handle.seal[5]<=2*LIMIT+4096 and type(handle.seal[6]) is str and len(handle.seal[6])==64)
        if pending:return # Exact active prospective mutation is not a current verdict.
        seal=handle.seal;shape=book_method(self,'shape')(handle)
        need(handle.window is seal[0] and handle.anchor is seal[1] and handle.anchor.original is seal[2]
            and handle.window.previous is seal[3] and handle.window.origin is seal[4])
        size,digest=window_checksum(shape,seal[5])
        need(size==seal[5] and digest==seal[6]
            and handle.stage.reserve>=3*seal[5]+6*PART)

    def metadata_bytes(self):
        book_method(self,'basic')()
        if not self.ready:return 3*PART
        # Actual pending work is charged by its exact OriginalGraph5 stage.
        # No resource-only call invents a healthy current window verdict.
        if self.failed or self.helper.failed or self.helper.bank.failed:return 3*PART
        book_method(self,'profile')() # Raw record class guards precede every record field access.
        pending=self.active
        need(pending is None or type(pending) is QuietRequest5 and pending.book is self
            and type(pending.stage) is OriginalGraph5 and pending.stage.holder is self.helper
            and any(pending.stage is row for row in self.helper.held))
        for handle in self.handles:
            book_method(self,'guard_handle')(handle,pending=pending is not None and pending.handle is handle and pending.mutated)
        return 3*PART

    def prepare(self,row,handle,invocation,role):
        helper=self.helper
        stage=OriginalGraph5(helper,row,3*PART);stage.reserve_before(3*PART)
        helper.held.append(stage);helper._held_seal=(*helper._held_seal,stage)
        request=QuietRequest5(self,row,handle,invocation,role,stage,handle is None);stage.graph=request
        try:
            book_method(self,'basic')();book_method(self,'profile')();helper_method(helper,'guard')()
            need(not self.failed and not self.closed and not helper.failed and not helper.bank.failed
                and not helper.bank.frozen and self.active is None
                and invocation is self.invocation and type(invocation) is tuple and len(invocation)==3
                and invocation[0] is self and type(role) is str and role in ('quiet','finalQuiet'))
            phase=helper.owner.state['phase']
            need(type(phase) is str and phase in (('returned',) if role=='quiet' else ('release-issued','released')))
            self.active=self._active=request
            if handle is None:
                need(len(self.handles)<512);request.handle=QuietHandle5(self,stage,invocation,role)
            else:
                book_method(self,'guard_handle')(handle)
                need(handle.invocation is invocation and type(handle.role) is str and handle.role==role)
                request.old_seal=handle.seal
            request.identity=request.original_identity=(self,row,request.handle,invocation,role,stage,request.created)
            stage.reserve_before(3*canonical_size(row)+3*PART);helper_method(helper,'preflight')();book_method(self,'request_guard')(request);return request
        except BaseException:
            book_method(self,'fail')(request);raise

    def request_guard(self,request):
        book_method(self,'profile')()
        need(type(request) is QuietRequest5 and request is self.active and request.book is self
            and type(request.identity) is tuple and len(request.identity)==7
            and request.identity is request.original_identity)
        expected=request.identity
        need(request.book is expected[0] and request.row is expected[1] and request.handle is expected[2]
            and request.invocation is expected[3] and request.role is expected[4]
            and request.stage is expected[5] and type(request.created) is bool and request.created is expected[6]
            and type(request.mutated) is type(request.confirmed) is type(request.failed) is bool
            and (request.complete is None or type(request.complete) is bool))

    def observe(self,request,packet,row_host):
        book_method(self,'basic')();book_method(self,'request_guard')(request);need(type(packet) is dict and type(packet['drive']) is dict and request.complete is None)
        book_method(self,'profile')()
        if not request.created:book_method(self,'guard_handle')(request.handle)
        size=canonical_size(packet['drive'],LIMIT)
        request.stage.reserve_before(request.stage.reserve+18*size+8*PART)
        helper_method(self.helper,'preflight')();book_method(self,'profile')();book_method(self,'request_guard')(request)
        handle=request.handle;request.mutated=True
        if request.created:
            # Both actual objects stay assigned before their original ctor can fail.
            handle.anchor=object.__new__(self.classes[0])
            self.methods[0][2](handle.anchor,packet['drive'])
            handle.window=object.__new__(self.classes[1])
            self.methods[2][2](handle.window,handle.anchor)
        request.complete=self.methods[3][2](handle.window,packet['drive'],row_host)
        need(type(request.complete) is bool);book_method(self,'profile')()
        request.next_seal=book_method(self,'sealed')(handle)

    def confirm(self,request):
        book_method(self,'basic')();book_method(self,'request_guard')(request);need(request.mutated and type(request.complete) is bool
            and request.next_seal is not None and not request.confirmed)
        book_method(self,'profile')();handle=request.handle
        handle.seal=handle.original_seal=request.next_seal
        if request.created:
            request.stage.graph=handle
            self.handles=self._handles=(*self.handles,handle)
        else:
            handle.stage.reserve_before(3*handle.seal[5]+6*PART)
        request.confirmed=True
        # Old seal, parsed packet and full prospective request remain charged
        # until the original caller completes byte/global-bill confirmation.
        helper_method(self.helper,'preflight')()

    def finish(self,request):
        book_method(self,'basic')();book_method(self,'request_guard')(request);need(request.confirmed and not request.failed)
        helper=self.helper;handle=request.handle;stage=request.stage
        # The generic packet stage has already dropped all parsed DTO/batch aliases.
        need(helper.active is None)
        request.row=request.old_seal=request.next_seal=None
        stage.source=None
        if request.created:
            stage.graph=handle;stage.reserve_before(3*handle.seal[5]+6*PART)
        else:
            need(helper.held[-1] is stage and helper._held_seal[-1] is stage)
            stage.graph=None;stage.reserve_seal=None
            helper.held.pop();helper._held_seal=helper._held_seal[:-1]
        self.active=self._active=None;book_method(self,'metadata_bytes')();helper_method(helper,'preflight')()
        return request.complete,handle

    def fail(self,request):
        # Strong stages were already registered before guards. Do not follow a
        # possibly foreign request.stage or invoke its setter during failure.
        self.failed=self.helper.failed=self.helper.bank.failed=True
        from adapters.pico4.lifecycle_background_raw_state import UNRESOLVED
        if not any(owner is self.helper for _path,owner in UNRESOLVED):UNRESOLVED.append((self.helper.bank.path.parent,self.helper))
        # Never clear active/prospective or partial original objects on failure.

    def known_stages(self):
        book_method(self,'basic')();book_method(self,'profile')()
        need(not self.failed and self.active is None)
        for handle in self.handles:book_method(self,'guard_handle')(handle)
        return tuple(handle.stage for handle in self.handles)

    def close_host(self):
        try:
            book_method(self,'known_stages')();self.closed=True
            # Data and charge remain held until actual host exit. This is a
            # known memory stage, not a kernel-close or product-cleanup claim.
            return True
        except BaseException:return False


BOOK_METHODS=('__init__','profile','shape','basic','token','sealed','guard_handle','metadata_bytes',
    'prepare','request_guard','observe','confirm','finish','fail','known_stages','close_host')
BOOK_FIELDS=('helper','handles','_handles','active','_active','failed','closed','invocation','invocations',
    'fixed','_fixed','ready','_ready','classes','methods','mros','dictionaries','functions','records',
    'checksum','pure','copy_profile')


def capture_api():
    cls=QuietBook5;raw=type.__getattribute__(cls,'__dict__');methods=[]
    for name in BOOK_METHODS:
        function=raw.get(name);need(type(function) is FunctionType)
        methods.append((name,function,function.__code__))
    return cls,type.__getattribute__(cls,'__mro__'),raw['__dict__'],tuple(methods)


def guard_api(book,proof):
    need(type(proof) is tuple and len(proof)==4 and proof[0] is QuietBook5 and type(book) is QuietBook5)
    raw=type.__getattribute__(QuietBook5,'__dict__')
    need(type.__getattribute__(QuietBook5,'__mro__') is proof[1] and raw.get('__dict__') is proof[2]
        and '__getattribute__' not in raw and '__getattr__' not in raw
        and all(name not in raw for name in BOOK_FIELDS))
    for name,function,code in proof[3]:
        current=raw.get(name);need(type(current) is FunctionType and current is function and current.__code__ is code)
    # Raw class proof precedes any instance binding; no foreign getter is called.
    for name,function,code in proof[3]:
        bound=object.__getattribute__(book,name)
        need(type(bound) is MethodType and bound.__self__ is book and bound.__func__ is function)
    return book


_BOOK_API=capture_api()
def book_method(book,name):
    guard_api(book,_BOOK_API)
    need(type(name) is str and name in BOOK_METHODS)
    return object.__getattribute__(book,name)
