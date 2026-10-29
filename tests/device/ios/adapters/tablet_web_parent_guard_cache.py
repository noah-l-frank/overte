"""The existing operation-local original cache for immutable Source3 proof.

Only original parent/closed-child/copy files enter this cache. Each hit uses
AvatarRecordCache's fresh inode/stat/private-directory and read-membership
checks. Current Root4 and active child WAL reads stay with their existing
callers, outside this immutable proof. No cache scope means the literal guard.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import copy
import json
from pathlib import Path
from types import FunctionType,BuiltinFunctionType,MethodType
from adapters import original_frame_store as frames
from adapters.native_feature_observation import need
from adapters.normal_feature_state import PrivateFeatureState
from adapters.script_feature.history import same
from adapters.script_feature.lock import ScriptSourceLock
from ios.adapters import tablet_web_child_rotation as closed
from ios.adapters import tablet_web_rotation_fence as fence
from ios.adapters.avatar_record_cache import AvatarRecordCache
from ios.adapters.tablet_web_record_cache import _ACTIVE,TabletRecordCache


class _Unsupported(Exception):pass
_DEFAULT_REFERENCES=[]
_KEEP_DEFAULT_REFERENCES=True


def _data(value,*,metadata=False):
    remaining=[4096];active=set()
    def visit(item,depth):
        remaining[0]-=1
        if remaining[0]<0 or depth>32:raise _Unsupported
        kind=type(item)
        if kind in (str,int,bool,type(None)):return [kind.__name__,item]
        if kind is float:
            encoded=item.hex()
            if encoded in ('inf','-inf','nan'):raise _Unsupported
            return ['float',encoded]
        if metadata and kind is BuiltinFunctionType:
            if _KEEP_DEFAULT_REFERENCES:_DEFAULT_REFERENCES.append(item)
            return ['builtin',id(item)]
        if metadata and kind is FunctionType:
            if item.__closure__:raise _Unsupported
            if _KEEP_DEFAULT_REFERENCES:_DEFAULT_REFERENCES.extend((item,item.__code__))
            return ['function',id(item),id(item.__code__),visit(item.__defaults__,depth+1),visit(item.__kwdefaults__,depth+1)]
        if kind not in ((dict,list,tuple) if metadata else (dict,list)):raise _Unsupported
        if id(item) in active:raise _Unsupported
        active.add(id(item))
        try:
            if kind is dict:
                if not all(type(key) is str for key in item):raise _Unsupported
                result=[[key,visit(item[key],depth+1)] for key in sorted(item)]
            else:result=[visit(part,depth+1) for part in item]
            return [kind.__name__,result]
        finally:active.remove(id(item))
    return visit(value,0)



def _header_key(value):
    # The common owner headers are ASCII exact JSON. Validate every actual
    # member without building a second type-tagged copy, then serialize them
    # through the same literal canonical encoder used by the original cache.
    # Unicode uses the old exact tree (astral and surrogate pairs stay distinct).
    remaining=4096;active=set();stack=[(value,0,False)]
    while stack:
        item,depth,leaving=stack.pop()
        if leaving:active.remove(id(item));continue
        remaining-=1
        if remaining<0 or depth>32:raise _Unsupported
        kind=type(item)
        if kind is str:
            if not item.isascii():return _data(value)
            continue
        if kind in (int,bool,type(None)):continue
        if kind is float:
            if item.hex() in ('inf','-inf','nan'):raise _Unsupported
            continue
        if kind not in (dict,list) or id(item) in active:raise _Unsupported
        active.add(id(item));stack.append((item,depth,True))
        if kind is dict:
            for key,part in item.items():
                if type(key) is not str:raise _Unsupported
                if not key.isascii():return _data(value)
                stack.append((part,depth+1,False))
        else:
            for part in item:stack.append((part,depth+1,False))
    # bool/int/float and signed zero have different JSON representations.
    # Only exact builtin values reach the encoder; no default/iterator hook.
    return ['ascii-json',closed.canonical(value).decode('ascii')]


def _function(function):
    if type(function) is FunctionType:
        if function.__closure__:raise _Unsupported
        return [id(function),id(function.__code__),_data(function.__defaults__,metadata=True),
            _data(function.__kwdefaults__,metadata=True)]
    if type(function) is BuiltinFunctionType:return [id(function),None,None,None]
    raise _Unsupported


# Actual historical proof entrypoints and original readers, not a module scan
# or an independent file cache. Unknown/replaced implementations run literally.
_READERS=[(closed,name) for name in ('_raw','_signature','decode','copy_body','_name','exact','need','same','canonical','deepcopy')]
_READERS += [(fence,name) for name in ('decode','_scope','scope','_legacy','_signature','_copy','context','identifier')]
_READERS += [(PrivateFeatureState,name) for name in ('__init__','read','_parent')]
_READERS += [(frames.OriginalFrameStore,name) for name in ('__init__','read','original','path','file','key','now','bound')]
_READERS += [(frames,name) for name in ('context','identifier','exact','integer','number','need','same','canonical')]
_READERS += [(AvatarRecordCache,name) for name in ('read','_read','signatures','absent')]
_READERS += [(TabletRecordCache,'read')]
_READERS += [(ScriptSourceLock,name) for name in ('assert_held','_check')]
_READERS += [(fence.json,'loads'),(frames.json,'loads'),(json,'dumps')]
_READERS += [(json.JSONEncoder,name) for name in ('__init__','encode','iterencode')]
_READERS += [(closed.hashlib,'sha256')]
_READERS += [(copy,name) for name in ('_deepcopy_dict','_deepcopy_list','_deepcopy_tuple','_keep_alive')]
def _lookup(owner,name):
    value=vars(owner).get(name)
    return value.__func__ if type(value) in (staticmethod,classmethod) else value


try:
    _BORN=tuple((owner,name,_lookup(owner,name),_function(_lookup(owner,name)),
        getattr(_lookup(owner,name),'__code__',None),getattr(_lookup(owner,name),'__defaults__',None),
        getattr(_lookup(owner,name),'__kwdefaults__',None)) for owner,name in _READERS)
except (AttributeError,KeyError,TypeError,ValueError,RecursionError,_Unsupported):_BORN=None
_KEEP_DEFAULT_REFERENCES=False
_DEFAULT_REFERENCES=tuple(_DEFAULT_REFERENCES)
_LINKS=tuple((owner,name,_lookup(owner,name)) for owner,name in
    ((closed,'base'),(fence,'json'),(frames,'json'),(fence,'base64'),(fence,'zlib'),(fence,'hashlib'),(json,'JSONEncoder'),
        (json.encoder,'c_make_encoder'),(json.encoder,'encode_basestring_ascii')))
_COPY_DISPATCH=copy._deepcopy_dispatch
_COPY_ATOMIC=getattr(copy,'_atomic_types',None)
_COPY_FUNCTIONS=tuple((kind,copy._deepcopy_dispatch[kind]) for kind in (dict,list,tuple))


def _epoch():
    try:
        if _BORN is None or _COPY_ATOMIC is None:return None
        seen={}
        if any(_lookup(owner,name) is not original for owner,name,original in _LINKS):return None
        if copy._deepcopy_dispatch is not _COPY_DISPATCH or copy._atomic_types is not _COPY_ATOMIC:return None
        if any(copy._deepcopy_dispatch.get(kind) is not original for kind,original in _COPY_FUNCTIONS):return None
        for owner,name,original,signature,_code,_defaults,_keywords in _BORN:
            if _lookup(owner,name) is not original:return None
            if type(original) is FunctionType and original.__code__ is not _code:return None
            identity=id(original)
            if identity not in seen:
                # Strong alias/code identities were checked above. A function
                # born without defaults/kwdefaults has no mutable default tree
                # to traverse while both current attributes remain None.
                if (type(original) is FunctionType and _defaults is None and _keywords is None
                        and original.__defaults__ is None and original.__kwdefaults__ is None):
                    seen[identity]=signature
                elif type(original) is BuiltinFunctionType:seen[identity]=signature
                else:seen[identity]=_function(original)
            if seen[identity]!=signature:return None
        # Mutable codec policy values participate in every current key.
        return _data(dict(child=[closed.VERSION,closed.PROFILE,closed.ORDER,closed.MAX_FRAMES,closed.LIMIT],
            parent=[fence.VERSION,fence.LEGACY,fence.MAX_HEAD_BYTES,fence.COPY_KEY,fence.MAX_FRAMES,fence.LIMIT],
            original=[frames.VERSION,frames.LIMIT,frames.MAX_FRAMES]),metadata=True)
    except (AttributeError,KeyError,TypeError,ValueError,RecursionError,_Unsupported):return None


def check(owner,literal):
    cache=_ACTIVE.get()
    if cache is None:return literal()
    from ios.adapters.tablet_web_aggregate_root import TabletWebAggregateRoot,_PARENT_GUARD_LITERAL
    if (type(owner) is not TabletWebAggregateRoot or type(cache) is not TabletRecordCache
            or type(cache.originals) is not AvatarRecordCache or type(owner.lock) is not ScriptSourceLock
            or type(owner.root) is not type(Path()) or type(literal) is not MethodType
            or literal.__self__ is not owner or literal.__func__ is not _PARENT_GUARD_LITERAL
            or literal.__func__.__code__ is not _PARENT_GUARD_CODE
            or literal.__func__.__defaults__ is not None or literal.__func__.__kwdefaults__ is not None):return literal()
    namespace=literal.__func__.__globals__
    if any(namespace.get(name) is not original for name,original in _PARENT_GUARD_GLOBALS):return literal()
    def header():
        owner.lock.assert_held()
        need(literal.__func__.__code__ is _PARENT_GUARD_CODE and literal.__func__.__defaults__ is None
            and literal.__func__.__kwdefaults__ is None
            and all(namespace.get(name) is original for name,original in _PARENT_GUARD_GLOBALS))
        need(owner.lock.path==owner.root/'script-feature-sources.lock')
        expected=fence.scope(owner.binding,owner.run,owner.role,owner.fixture,owner.pid)
        need(same(owner.expected,expected))
        return _header_key(dict(root=str(owner.root),binding=owner.binding,run=owner.run,role=owner.role,
            fixture=owner.fixture,pid=owner.pid,expected=owner.expected,parent=owner.parent,legacy=owner.legacy,
            parentSignature=owner.parent_signature,parentSha256=owner.parent_sha))
    try:
        epoch=_epoch()
        if epoch is None:return literal()
        identity=header()
    except _Unsupported:return literal()
    key=dict(tabletImmutableParentGuardVersion=1,owner=identity,parsers=epoch)
    def unchanged():
        current=header();need(current==identity and _epoch()==epoch)
    def decode():
        unchanged();result=literal();need(result is True);unchanged();return result
    answer=cache.read(key,decode);unchanged();need(answer is True);return answer


# Set by the owner's import after its literal body exists. The helper is loaded
# before owner construction, so ordinary parser aliases are retained at birth.
_PARENT_GUARD_CODE=None
_PARENT_GUARD_GLOBALS=()
