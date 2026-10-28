"""Bounded call-local reuse of pure GPU native-query validation.

Every caller still reads the actual raw carriers and checks their identities.
Only equal complete input bytes share pure decoding inside one World API call;
this module has no file, clock, SDK, native or freshness authority.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
import hashlib
import marshal
from types import FunctionType
from adapters.original_marker_clock_queries import queries as original_queries

MAX_BYTES=8*1024*1024
MAX_ENTRIES=512
_ACTIVE=ContextVar('world_web_original_clock_validation',default=None)


@contextmanager
def scope():
    active=_ACTIVE
    if active is not _SOURCE_ACTIVE:yield;return
    if active.get() is not None:yield;return
    token=active.set(dict(entries={},bytes=0))
    try:yield
    finally:active.reset(token)


def bounded(rows,pid,strict):
    # Bound work before constructing a cache key. Unsupported input keeps the
    # original validator's exact behavior, including all rejection predicates.
    if type(rows) is not list or len(rows)>128 or type(pid) is not int or type(strict) is not bool:return False
    count=0
    for row in rows:
        if type(row) is not dict or set(row)!={'query','raws'}:return False
        query=row['query'];raws=row['raws']
        if type(query) is not dict or set(query)!={'schemaVersion','commandId','action'}:return False
        if type(query['schemaVersion']) is not int or type(query['commandId']) is not str or type(query['action']) is not str:return False
        if len(query['commandId'])>64 or len(query['action'])>64 or type(raws) is not list or len(raws)>51:return False
        for raw in raws:
            if type(raw) is not str or len(raw)>MAX_BYTES:return False
            count+=len(raw.encode('utf-8'))
            if count>MAX_BYTES:return False
    return True


def queries(rows,pid,*,strict=True):
    cache=_ACTIVE.get()
    if cache is None or not bounded(rows,pid,strict):return original_queries(rows,pid,strict=strict)
    encoded=marshal.dumps((rows,pid,strict),4)
    if len(encoded)>MAX_BYTES:return original_queries(rows,pid,strict=strict)
    key=hashlib.sha256(encoded).digest()
    if key in cache['entries']:return deepcopy(cache['entries'][key])
    result=original_queries(rows,pid,strict=strict)
    cost=len(encoded)+len(marshal.dumps(result,4))+len(key)
    if len(cache['entries'])<MAX_ENTRIES and cache['bytes']+cost<=MAX_BYTES:
        cache['entries'][key]=deepcopy(result);cache['bytes']+=cost
    return result


# Source opt-in is stricter than the unchanged GPU default above. It cannot
# adopt entries created through a substituted parser/scope/constant epoch.
def _function_stamp(function):
    return (function,function.__code__,function.__defaults__,function.__kwdefaults__,
        None if function.__kwdefaults__ is None else tuple(function.__kwdefaults__.items()),
        function.__closure__,None if function.__closure__ is None else tuple(cell.cell_contents for cell in function.__closure__))


def _literal_function(value,stamp):
    original,code,defaults,keywords,items,closure,cells=stamp
    if (type(value) is not FunctionType or value is not original or value.__code__ is not code
        or value.__defaults__ is not defaults or value.__kwdefaults__ is not keywords or value.__closure__ is not closure):return False
    if keywords is not None:
        # Compare only literal keyword names and identity of default objects;
        # a foreign default must never execute opaque equality in this guard.
        if type(keywords) is not dict or len(keywords)!=len(items):return False
        actual=tuple(keywords.items())
        if any(type(key) is not str for key,_value in actual):return False
        if any(not any(key==name and item is old for name,old in items) for key,item in actual):return False
    if closure is not None:
        try:
            if any(cell.cell_contents is not old for cell,old in zip(closure,cells)):return False
        except ValueError:return False
    return True


def _source_snapshot(value):
    # Closed built-in tree only: never marshal caller containers. Captured
    # children are copied before decoding; no opaque key/buffer hooks execute.
    chunks=[];size=0;nodes=0
    def emit(tag,raw=b''):
        nonlocal size
        size+=1+8+len(raw)
        if size>MAX_BYTES:raise ValueError('Source snapshot byte bound')
        chunks.extend((tag,len(raw).to_bytes(8,'big'),raw))
    def walk(item,depth):
        nonlocal nodes
        nodes+=1
        if depth>64 or nodes>100000:raise ValueError('Source snapshot tree bound')
        kind=type(item)
        if item is None:emit(b'N');return None
        if kind is bool:emit(b'T' if item else b'F');return item
        if kind is int:
            if item.bit_length()>63:raise ValueError('Source snapshot integer bound')
            emit(b'I',item.to_bytes(8,'big',signed=True));return item
        if kind is float:emit(b'R',item.hex().encode('ascii'));return item
        if kind is str:
            if len(item)>MAX_BYTES:raise ValueError('Source snapshot string bound')
            emit(b'S',item.encode('utf-8'));return item
        if kind is list:
            children=tuple(item)
            if len(children)>100000:raise ValueError('Source snapshot list bound')
            emit(b'L',len(children).to_bytes(8,'big'))
            return [walk(child,depth+1) for child in children]
        if kind is dict:
            children=tuple(item.items())
            if len(children)>100000 or any(type(key) is not str for key,_child in children):raise ValueError('Source snapshot keys')
            emit(b'D',len(children).to_bytes(8,'big'))
            return {walk(key,depth+1):walk(child,depth+1) for key,child in children}
        raise ValueError('Source snapshot opaque value')
    try:return walk(value,0),b''.join(chunks)
    except (ValueError,UnicodeError,OverflowError,RecursionError):return None


def _source_epoch():
    if (type is not _SOURCE_TYPE or len is not _SOURCE_LEN or tuple is not _SOURCE_TUPLE or dict is not _SOURCE_DICT
        or bool is not _SOURCE_BOOL or int is not _SOURCE_INT or float is not _SOURCE_FLOAT or str is not _SOURCE_STR
        or list is not _SOURCE_LIST or any is not _SOURCE_ANY or zip is not _SOURCE_ZIP
        or ValueError is not _SOURCE_VALUE_ERROR or UnicodeError is not _SOURCE_UNICODE_ERROR
        or OverflowError is not _SOURCE_OVERFLOW_ERROR or RecursionError is not _SOURCE_RECURSION_ERROR
        or FunctionType is not _SOURCE_FUNCTION_TYPE or _ACTIVE is not _SOURCE_ACTIVE
        or MAX_BYTES is not _SOURCE_MAX_BYTES or MAX_ENTRIES is not _SOURCE_MAX_ENTRIES
        or hashlib.sha256 is not _SOURCE_SHA
        or _SOURCE_ORIGINAL_QUERY.__globals__['LIMIT'] is not _SOURCE_QUERY_LIMIT
        or _SOURCE_FUNCTIONS is not _SOURCE_GETTERS or _SOURCE_EPOCH is not _SOURCE_LITERAL_EPOCH):return None
    if (_literal_function is not _SOURCE_LITERAL_FUNCTION[0] or _literal_function.__code__ is not _SOURCE_LITERAL_FUNCTION[1]
        or _literal_function.__defaults__ is not _SOURCE_LITERAL_FUNCTION[2] or _literal_function.__kwdefaults__ is not _SOURCE_LITERAL_FUNCTION[3]):return None
    for getter,getter_stamp,stamp in _SOURCE_FUNCTIONS:
        if not _literal_function(getter,getter_stamp) or not _literal_function(getter(),stamp):return None
    # Strong original function/code/scope references stay in every Source key.
    # Restoring a literal epoch cannot relabel a foreign parser's GPU entries.
    return _SOURCE_EPOCH


def source_queries(rows,pid,*,strict=True):
    # Never invoke a substituted epoch guard, even to decide eligibility.
    if (_source_epoch is not _SOURCE_EPOCH_FUNCTION or _source_epoch.__code__ is not _SOURCE_EPOCH_CODE
        or _source_epoch.__defaults__ is not None or _source_epoch.__kwdefaults__ is not None):
        return _SOURCE_ORIGINAL_QUERY(rows,pid,strict=strict)
    epoch=_source_epoch()
    if epoch is None:return _SOURCE_ORIGINAL_QUERY(rows,pid,strict=strict)
    active=_ACTIVE;cache=active.get()
    if cache is None:return _SOURCE_ORIGINAL_QUERY(rows,pid,strict=strict)
    snapshot=_source_snapshot([rows,pid,strict])
    if snapshot is None:return _SOURCE_ORIGINAL_QUERY(rows,pid,strict=strict)
    private,encoded=snapshot;private_rows,private_pid,private_strict=private
    if not bounded(private_rows,private_pid,private_strict):return _SOURCE_ORIGINAL_QUERY(rows,pid,strict=strict)
    key=(_SOURCE_KEY,epoch,hashlib.sha256(encoded).digest())
    # Epoch access itself can emit audit events. Re-snapshot the caller AFTER
    # that check, before adopting a hit or decoding the immutable private tree.
    if _source_epoch()!=epoch or _ACTIVE is not active or active.get() is not cache:
        return _SOURCE_ORIGINAL_QUERY(rows,pid,strict=strict)
    current=_source_snapshot([rows,pid,strict])
    if current is None or current[1]!=encoded:return _SOURCE_ORIGINAL_QUERY(rows,pid,strict=strict)
    if key in cache['entries']:
        copied=_source_snapshot(cache['entries'][key])
        return copied[0] if copied is not None else _SOURCE_ORIGINAL_QUERY(rows,pid,strict=strict)
    result=_SOURCE_ORIGINAL_QUERY(private_rows,private_pid,strict=private_strict)
    if _source_epoch()!=epoch or _ACTIVE is not active or active.get() is not cache:return result
    current=_source_snapshot([rows,pid,strict])
    if current is None or current[1]!=encoded:return _SOURCE_ORIGINAL_QUERY(rows,pid,strict=strict)
    copied=_source_snapshot(result)
    if copied is None:return result
    copied_result,result_bytes=copied;cost=len(encoded)+len(result_bytes)+len(key[2])
    if len(cache['entries'])<MAX_ENTRIES and cache['bytes']+cost<=MAX_BYTES:
        cache['entries'][key]=copied_result;cache['bytes']+=cost
    return result




def source_eligible():
    if (_source_epoch is not _SOURCE_EPOCH_FUNCTION or _source_epoch.__code__ is not _SOURCE_EPOCH_CODE
        or _source_epoch.__defaults__ is not None or _source_epoch.__kwdefaults__ is not None):return False
    return _source_epoch() is not None


_SOURCE_ORIGINAL_QUERY=original_queries
_SOURCE_TYPE,_SOURCE_LEN,_SOURCE_TUPLE,_SOURCE_DICT=type,len,tuple,dict
_SOURCE_BOOL,_SOURCE_INT,_SOURCE_FLOAT,_SOURCE_STR,_SOURCE_LIST=bool,int,float,str,list
_SOURCE_ANY,_SOURCE_ZIP=any,zip
_SOURCE_VALUE_ERROR,_SOURCE_UNICODE_ERROR=ValueError,UnicodeError
_SOURCE_OVERFLOW_ERROR,_SOURCE_RECURSION_ERROR=OverflowError,RecursionError
_SOURCE_FUNCTION_TYPE=FunctionType
_SOURCE_ACTIVE,_SOURCE_MAX_BYTES,_SOURCE_MAX_ENTRIES=_ACTIVE,MAX_BYTES,MAX_ENTRIES
_SOURCE_SHA=hashlib.sha256
_SOURCE_QUERY_LIMIT=_SOURCE_ORIGINAL_QUERY.__globals__['LIMIT']
_SOURCE_KEY=object()
_SOURCE_LITERAL_FUNCTION=_function_stamp(_literal_function)
_SOURCE_FUNCTIONS=tuple((getter,_function_stamp(getter),_function_stamp(getter())) for getter in (
    lambda:original_queries,lambda:bounded,lambda:deepcopy,lambda:scope,lambda:_source_snapshot,
    lambda:scope.__wrapped__,lambda:queries,lambda:source_queries,lambda:source_eligible,
    lambda:original_queries.__globals__['decode'],lambda:original_queries.__globals__['validate'],
    lambda:original_queries.__globals__['follow'],lambda:original_queries.__globals__['exact'],
    lambda:original_queries.__globals__['need'],lambda:original_queries.__globals__['same']))
_SOURCE_EPOCH=tuple((stamp[0],stamp[1],id(stamp[2]),id(stamp[3]),id(stamp[5])) for _getter,_getter_stamp,stamp in _SOURCE_FUNCTIONS)
_SOURCE_GETTERS,_SOURCE_LITERAL_EPOCH=_SOURCE_FUNCTIONS,_SOURCE_EPOCH
_SOURCE_EPOCH_FUNCTION,_SOURCE_EPOCH_CODE=_source_epoch,_source_epoch.__code__
