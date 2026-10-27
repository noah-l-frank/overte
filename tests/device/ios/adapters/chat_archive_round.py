"""One synchronous Chat decoder's completed historical proof DAG.

Original decoders remain the authority. Nothing is reused across the outer
call, mutation/query boundaries, a changed original file or a changed parser.
Only the existing exact bounded sender factory has a reusable dependency graph.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextvars import ContextVar
from copy import deepcopy
import inspect
from pathlib import Path
import stat
import sys
from types import FunctionType,ModuleType
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.original_file_reads import scope as read_scope,record
from adapters.script_feature.history import canonical,same

_ACTIVE=ContextVar('ios_chat_archive_decode_round',default=None)
_LAST_COUNTS=ContextVar('ios_chat_archive_decode_counts',default=(0,0))
_BASELINES={}
_DEPENDENCIES={}
_MODULES=tuple('ios.adapters.'+name for name in ('chat_draft_owner','chat_receive_sources','chat_peer_receipts','chat_send_receive','chat_draft_runtime'))
_FIELDS=('previous','state','binding','primary_binding','run','root','fixture_url','version','frontier','frontier_ticket',
    'source_bound','peer_actor','historical','subgraph_only','bound_record')
_MUTATORS=frozenset(('write','discard','save','query_intent','input_intent','storage_intent','capture','act','cleanup',
    'restore_history','resolve','recover','recover_observation','remember','remember_clock'))
_MAX_ENTRIES=32
_MAX_BYTES=2*1024*1024
_MAX_ENTRY_BYTES=256*1024


def function(value):
    target=getattr(value,'__func__',value)
    return target,getattr(target,'__code__',None),id(getattr(value,'__self__',None))


def module_signature(namespace):
    values=[]
    for name,value in sorted(namespace.items()):
        if isinstance(value,FunctionType):values.append((name,function(value)))
        elif isinstance(value,type):
            methods=[]
            for parent in value.__mro__:
                for key,item in sorted(vars(parent).items()):
                    if key in _MUTATORS:continue
                    if isinstance(item,(staticmethod,classmethod)):item=item.__func__
                    if isinstance(item,FunctionType):methods.append((parent,key,function(item)))
            values.append((name,value,tuple(methods)))
        elif isinstance(value,ContextVar):values.append((name,id(value)))
        elif isinstance(value,ModuleType):values.append((name,id(value)))
        elif name.isupper() and isinstance(value,(str,int,float,bool,tuple,frozenset,type(None))):values.append((name,value))
    return tuple(values)


def register(name,namespace):
    need(name in _MODULES and name not in _BASELINES)
    _BASELINES[name]=(namespace,module_signature(namespace))
    # The imported parser's globals are part of its authority too. Pin their
    # original helper functions/constants, including validators called through
    # an imported module, rather than only the outer function's __code__.
    pending=[namespace];seen=set()
    while pending:
        current=pending.pop()
        for value in tuple(current.values()):
            module=value if isinstance(value,ModuleType) else sys.modules.get(getattr(value,'__module__',''))
            label=getattr(module,'__name__','')
            if not label.startswith(('adapters.','ios.adapters.','feature_journeys.')) or label in seen or label==__name__:continue
            seen.add(label)
            if label in _MODULES:continue
            if label not in _DEPENDENCIES:_DEPENDENCIES[label]=(vars(module),module_signature(vars(module)))
            pending.append(vars(module))


def original_methods():
    return (all(name in _BASELINES and module_signature(_BASELINES[name][0])==_BASELINES[name][1] for name in _MODULES)
        and all(module_signature(namespace)==expected for namespace,expected in _DEPENDENCIES.values()))


def factory(context):
    from ios.adapters.chat_draft_runtime import IOSChatDraftRuntime
    from ios.adapters.chat_peer_receipts import IOSChatPeerReceipts
    from ios.adapters.chat_receive_sources import IOSChatReceiveSources
    need(type(context) is IOSChatPeerReceipts and context.bounded_sender and context.version==2 and unshadowed(context))
    wrapped=context.sender_owner;inner=getattr(wrapped,'__wrapped__',None)
    need(isinstance(inner,FunctionType) and inner.__code__ in IOSChatDraftRuntime._chat_receipt_contexts.__code__.co_consts)
    closure=inspect.getclosurevars(inner).nonlocals
    need(set(closure)=={'contexts','fixture_url','receive','run','self'}
        and closure['receive'] is context.receive and type(closure['receive']) is IOSChatReceiveSources)
    contexts=closure['contexts'];need(type(contexts) is dict and set(contexts)=={'primary','peer'}
        and contexts[context.recipient_role] is context and all(type(item) is IOSChatPeerReceipts for item in contexts.values()))
    role,selector=inner.__defaults__;runtime=closure['self'];source=context.receive
    need(role==context.sender_role and closure['run']==source.run)
    path=runtime.state_path(selector).with_name('ios-chat-draft-owner.json')
    lock=source.primary_lock if role=='primary' else source.lock
    need(path==lock.path.with_name('ios-chat-draft-owner.json'))
    return (id(context),id(wrapped),function(inner),inner.__defaults__,closure['fixture_url'],closure['run'],
        id(source),id(runtime),id(runtime.adapter),function(runtime.state_path),function(runtime.adapter.state_path),
        tuple((role,id(contexts[role])) for role in ('primary','peer')),str(path))


def memory(owner):
    value={key:getattr(owner,key) for key in _FIELDS if hasattr(owner,key)}
    value['root']=str(value['root']);value['storePath']=str(owner.store.path);value['lockPath']=str(owner.lock.path)
    if hasattr(owner,'primary_lock'):value['primaryLockPath']=str(owner.primary_lock.path)
    frames=owner.frames
    value['frames']={key:str(getattr(frames,key)) if key=='root' else getattr(frames,key)
        for key in ('root','binding','run','role','namespace','schema_prefix','kind')}
    callbacks=tuple(function(getattr(owner,key)) for key in ('bound','guard','monotonic') if hasattr(owner,key))
    callbacks+=tuple(function(getattr(frames,key)) for key in ('guard','intent','monotonic'))
    if not hasattr(owner,'peer_receipts'):
        callbacks+=((None,None,None) if owner.historical else function(owner.parts['check']),)
    context=getattr(owner,'peer_receipts',None)
    return canonical(value),callbacks,None if context is None else factory(context)


def node(path):
    row=path.lstat()
    need(stat.S_ISREG(row.st_mode) or stat.S_ISDIR(row.st_mode))
    return (row.st_dev,row.st_ino,row.st_mode,row.st_uid,row.st_gid,row.st_nlink,row.st_size,row.st_mtime_ns,row.st_ctime_ns)


def inventory(roots):
    result=[]
    for root in roots:
        PrivateFeatureState(root/'chat-round-boundary')._parent();entries=list(root.iterdir());need(len(entries)<=4096)
        result.append((str(root),node(root),tuple(sorted((path.name,node(path)) for path in entries))))
    return tuple(result)


def eligible(owner):
    from ios.adapters.chat_draft_owner import IOSChatDraftOwner
    from ios.adapters.chat_receive_sources import IOSChatReceiveSources
    from adapters.original_frame_store import OriginalFrameStore
    from adapters.script_feature.lock import ScriptSourceLock
    if type(owner) not in (IOSChatDraftOwner,IOSChatReceiveSources):return False
    context=getattr(owner,'peer_receipts',None)
    if context is None and not (_ACTIVE.get() is not None and type(owner) is IOSChatReceiveSources):return False
    if context is not None and not (owner.source_bound and owner.version in (6,7) and owner.previous is not None):return False
    if not original_methods():return False
    if (type(owner.store) is not PrivateFeatureState or type(owner.frames) is not OriginalFrameStore
            or type(owner.lock) is not ScriptSourceLock or not all(unshadowed(item) for item in (owner,owner.store,owner.frames,owner.lock))):return False
    if context is None:return _ACTIVE.get() is not None and type(owner) is IOSChatReceiveSources
    try:
        need(unshadowed(context))
        factory(context)
        if owner.historical:
            need(owner.guard.__closure__ is None
                and owner.guard.__code__ in IOSChatDraftOwner.archive.__func__.__code__.co_consts)
        return owner.source_bound and owner.version in (6,7) and owner.previous is not None
    except (AttributeError,KeyError,TypeError,ValueError,RuntimeError):return False


def unshadowed(value):
    return all(name not in vars(value) for parent in type(value).__mro__ for name,item in vars(parent).items()
        if isinstance(item,(FunctionType,staticmethod,classmethod)))


def proof_key(owner,snapshot,value):
    # Fresh archive wrappers have fresh bound-method/lambda identities. Their
    # exact literal code is checked independently; normalize only their own
    # receiver identity when naming the same original historical subgraph.
    body,callbacks,context=snapshot;normalized=[]
    for target,code,receiver in callbacks:
        if owner.historical and target is getattr(owner,'guard',None) and code is not None:target=code
        normalized.append((target,code,None if receiver==id(owner) else receiver))
    return str(owner.store.path),body,tuple(normalized),context,canonical(value)


class ArchiveRound:
    def __init__(self,owner):
        self.source=owner.peer_receipts.receive
        source=self.source
        from adapters.original_frame_store import OriginalFrameStore
        from adapters.script_feature.lock import ScriptSourceLock
        need(type(source.store) is PrivateFeatureState and type(source.frames) is OriginalFrameStore
            and type(source.lock) is ScriptSourceLock and type(source.primary_lock) is ScriptSourceLock
            and all(unshadowed(item) for item in (source,source.store,source.frames,source.lock,source.primary_lock)))
        self.receipts=tuple(inspect.getclosurevars(owner.peer_receipts.sender_owner.__wrapped__).nonlocals['contexts'].values())
        self.contexts=tuple(factory(item) for item in self.receipts)
        self.source_memory=memory(source);self.active={};self.pending=set();self.memo={};self.memo_bytes=0
        self.closed=False;self.hits=0;self.disabled=False
        self.roots=tuple(sorted({Path(source.bound_record[role+'ArtifactRoot']['path']) for role in ('primary','peer')}
            |{source.store.path.parent,owner.store.path.parent,source.primary_lock.path.parent,source.lock.path.parent},key=str))
        self.files=inventory(self.roots)

    def check(self):
        need(not self.closed and original_methods() and memory(self.source)==self.source_memory
            and tuple(factory(item) for item in self.receipts)==self.contexts)
        for owner,expected in tuple(self.active.items()):
            need(memory(owner)==expected and all(unshadowed(item) for item in (owner,owner.store,owner.frames,owner.lock)))
        need(all(unshadowed(item) for item in (self.source,self.source.store,self.source.frames,self.source.lock,self.source.primary_lock)))
        need(inventory(self.roots)==self.files)
        # Invoke the actual callbacks; a previous True verdict is never proof.
        self.source.bound()
        for owner in tuple(self.active):owner.bound()
        need(memory(self.source)==self.source_memory and inventory(self.roots)==self.files and original_methods())
        for owner,expected in tuple(self.active.items()):need(memory(owner)==expected)

    def run(self,owner,value,literal):
        snapshot=memory(owner);need(owner not in self.active)
        key=proof_key(owner,snapshot,value);need(key not in self.pending)
        self.active[owner]=snapshot;self.pending.add(key)
        started=owner.frames.now()
        try:
            self.check();owner.frames.bound(started)
            if not self.disabled and owner.historical and key in self.memo:
                result,dependencies=self.memo[key]
                for path in dependencies:record(path)
                self.hits+=1;self.check();owner.frames.bound(started)
                return deepcopy(result)
            with read_scope(fresh=True) as dependencies:result=literal()
            if any(path.parent not in self.roots for path in dependencies):self.disable()
            for path in dependencies:
                record(path)
            self.check()
            if not self.disabled and owner.historical:
                size=(len(snapshot[0])+len(key[-1])+len(canonical(result))
                    +sum(len(str(path).encode('utf-8')) for path in dependencies))
                # These are optimization storage bounds, never wire/read caps.
                # A fully validated literal result survives; its memo does not.
                if len(self.memo)>=_MAX_ENTRIES or size>_MAX_ENTRY_BYTES or self.memo_bytes+size>_MAX_BYTES:self.disable()
                else:self.memo[key]=(deepcopy(result),frozenset(dependencies));self.memo_bytes+=size
            return result
        finally:
            self.pending.remove(key);del self.active[owner]

    def disable(self):self.disabled=True;self.memo.clear();self.memo_bytes=0

    def close(self):
        try:self.check();need(not self.active and not self.pending)
        finally:
            # Counts contain no input, original, decoded tree or reusable proof.
            _LAST_COUNTS.set((self.hits,len(self.memo)));self.closed=True;self.memo.clear();self.memo_bytes=0


def decode(owner,value,literal):
    current=_ACTIVE.get()
    if not eligible(owner):
        if current is not None:current.disable()
        return literal()
    if current is not None:return current.run(owner,value,literal)
    try:current=ArchiveRound(owner)
    except (AttributeError,KeyError,TypeError,ValueError,RuntimeError):return literal()
    token=_ACTIVE.set(current)
    try:return current.run(owner,value,literal)
    finally:
        try:current.close()
        finally:_ACTIVE.reset(token)


def set_state(owner,state):
    current=_ACTIVE.get()
    if current is not None and owner in current.active:
        need(memory(owner)==current.active[owner]);owner.state=state;current.active[owner]=memory(owner)
    else:owner.state=state


def mutation():
    # A pure decoder cannot retain or consume a proof after beginning a write,
    # query, UI input or live capture. Refuse before that boundary has effects.
    need(_ACTIVE.get() is None)
