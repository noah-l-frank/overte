"""Existing immutable original cache for one Final2 historical row.

No live owner, current pending row, input, freshness or quiet verdict enters
this memo. The complete prefix decoder still owns order/pending/inventory.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from types import FunctionType,BuiltinFunctionType,ModuleType
from adapters.native_feature_observation import need
from adapters.script_feature.history import same,canonical
from ios.adapters.avatar_record_cache import AvatarRecordCache

_OWNER=_GUARD=_GUARD_CODE=None
_BORN=();_BINDINGS=();_REFERENCES=[]
_CAPTURE=False


class _Unsupported(Exception):pass


def _data(value,depth=0):
    if depth>16:raise _Unsupported
    kind=type(value)
    if kind is str or kind is int or kind is bool or kind is type(None):return (kind.__name__,value)
    if kind is float:return ('float',value.hex())
    if kind is FunctionType:
        if value.__closure__:raise _Unsupported
        if _CAPTURE:_REFERENCES.extend((value,value.__code__))
        return ('function',id(value),id(value.__code__),_data(value.__defaults__,depth+1),_data(value.__kwdefaults__,depth+1))
    if kind is BuiltinFunctionType:
        if _CAPTURE:_REFERENCES.append(value)
        return ('builtin',id(value))
    if kind is set or kind is frozenset:
        if not all(type(item) is str for item in value):raise _Unsupported
        return (kind.__name__,tuple(sorted(value)))
    if kind is tuple or kind is list:return (kind.__name__,tuple(_data(item,depth+1) for item in value))
    if kind is dict:
        if not all(type(key) is str for key in value):raise _Unsupported
        return ('dict',tuple((key,_data(value[key],depth+1)) for key in sorted(value)))
    raise _Unsupported


def _signature(function):
    if type(function) is not FunctionType or function.__closure__:raise _Unsupported
    return (function.__code__,_data(function.__defaults__),_data(function.__kwdefaults__))


def _lookup(owner,name):
    if type(owner) is dict:values=(owner,)
    elif type(owner) is type:
        if any(type(parent) is not type for parent in owner.__mro__):raise _Unsupported
        values=(vars(parent) for parent in owner.__mro__)
    elif type(owner) is ModuleType:values=(vars(owner),)
    else:raise _Unsupported
    for namespace in values:
        if name in namespace:
            value=namespace[name]
            return value.__func__ if (type(value) is staticmethod or type(value) is classmethod) else value
    return None


def bind(owner,guard,readers,bindings):
    global _OWNER,_GUARD,_GUARD_CODE,_BORN,_BINDINGS,_CAPTURE
    _OWNER,_GUARD,_GUARD_CODE=owner,guard,guard.__code__
    _CAPTURE=True
    try:
        _BORN=tuple((container,name,_lookup(container,name),_signature(_lookup(container,name))) for container,name in readers)
        _BINDINGS=tuple((container,name,_lookup(container,name),None if mode=='identity' else _data(_lookup(container,name)))
            for container,name,mode in bindings)
    except (AttributeError,TypeError,ValueError,RecursionError,_Unsupported):_BORN=None
    finally:_CAPTURE=False


def _literal():
    if _BORN is None or _GUARD.__code__ is not _GUARD_CODE:return False
    try:
        return all(_lookup(container,name) is function and function.__code__ is signature[0]
            and _signature(function)==signature for container,name,function,signature in _BORN) and all(
            _lookup(container,name) is value and (token is None or _data(value)==token)
            for container,name,value,token in _BINDINGS)
    except (AttributeError,TypeError,ValueError,RecursionError,_Unsupported):return False


def read(owner,row,material,previous,index,policy,decode):
    cache=getattr(owner,'historical_rows',None)
    if (type(owner) is not _OWNER or not owner.historical or type(cache) is not AvatarRecordCache
            or row['status']!='observed' or owner.guard is not _GUARD or owner.originals.guard is not _GUARD
            or not _literal()):return decode()
    def header():
        owner.lock.assert_held()
        need(type(owner) is _OWNER and owner.historical and owner.historical_rows is cache
            and owner.guard is _GUARD and owner.originals.guard is _GUARD)
        original=owner.originals
        need(original.root==owner.root and same(original.binding,owner.binding) and original.run==owner.run
            and original.role==owner.role and original.kind=='sources')
        return dict(root=str(owner.root),store=str(owner.store.path),lock=str(owner.lock.path),
            binding=owner.binding,runId=owner.run,role=owner.role,subject=owner.subject,inputs=owner.inputs,
            original=dict(root=str(original.root),namespace=original.namespace,schema=original.schema_prefix,kind=original.kind))
    try:current_policy=_data(policy())
    except _Unsupported:return decode()
    before=canonical(header())
    # These are the actual current metadata, row/material and previous model.
    # Prefix length and a later pending row cannot authorize this old row.
    key=dict(avatarFinalPostLogoutRowVersion=1,owner=before.decode('ascii'),row=row,material=material,previous=previous,index=index,policy=current_policy)
    encoded=canonical(key)
    def checked():
        need(_literal() and _data(policy())==current_policy and canonical(header())==before and canonical(key)==encoded);answer=decode()
        need(_literal() and _data(policy())==current_policy and canonical(header())==before and canonical(key)==encoded);return answer
    if encoded not in cache.rows and len(cache.rows)>=512:return decode()
    answer=cache.read(key,checked)
    need(_literal() and _data(policy())==current_policy and canonical(header())==before and canonical(key)==encoded);return answer
