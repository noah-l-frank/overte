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
    token=active.set(dict(entries={},costs={},bytes=0))
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


def _memo_key(key):
    if type(key) is bytes:return len(key)==32
    return (type(key) is tuple and len(key)==3 and key[0] is _SOURCE_KEY
        and key[1] is _SOURCE_EPOCH and type(key[2]) is bytes and len(key[2])==32)


def _memo_state(cache):
    # Complete bounded accounting, without reading/deepcopying entry values or
    # invoking opaque keys/equality. Detached/corrupt ledgers are not adopted.
    if type(cache) is not dict:return None
    names=tuple(cache)
    if len(names)!=3 or any(type(name) is not str for name in names):return None
    if not all(name in ('entries','costs','bytes') for name in names):return None
    entries,costs,total=cache['entries'],cache['costs'],cache['bytes']
    if (type(entries) is not dict or type(costs) is not dict or type(total) is not int
        or total<0 or total>MAX_BYTES or len(entries)!=len(costs) or len(entries)>MAX_ENTRIES):return None
    # Validate both key sets before looking up any key. Unknown user keys can
    # never execute __hash__/__eq__ as part of eviction or accounting.
    if any(not _memo_key(key) for key in entries) or any(not _memo_key(key) for key in costs):return None
    actual=0
    for key,cost in costs.items():
        if type(cost) is not int or not 0<cost<=MAX_BYTES or key not in entries:return None
        actual+=cost
        if actual>MAX_BYTES:return None
    if actual!=total:return None
    return entries,costs,total


def _memo_get(cache,key):
    state=_memo_state(cache)
    if state is None:return False,None
    entries,costs,_total=state
    if key not in entries:return False,None
    # Recency is a pure interpretation detail, never an original-file verdict.
    value=entries.pop(key);cost=costs.pop(key)
    entries[key]=value;costs[key]=cost
    return True,value


def _memo_store(cache,key,value,cost):
    state=_memo_state(cache)
    if state is None or not _memo_key(key) or type(cost) is not int or not 0<cost<=MAX_BYTES or MAX_ENTRIES<1:return False
    entries,costs,total=state
    if key in entries:return False
    while entries and (len(entries)>=MAX_ENTRIES or total+cost>MAX_BYTES):
        oldest=next(iter(entries));entries.pop(oldest);total-=costs.pop(oldest)
    if len(entries)>=MAX_ENTRIES or total+cost>MAX_BYTES:return False
    entries[key]=value;costs[key]=cost;cache['bytes']=total+cost
    return True


def _memo_valid():
    if (type is not _SOURCE_TYPE or len is not _SOURCE_LEN or tuple is not _SOURCE_TUPLE
        or dict is not _SOURCE_DICT or bytes is not _MEMO_BYTES or int is not _SOURCE_INT
        or str is not _SOURCE_STR or any is not _SOURCE_ANY or all is not _MEMO_ALL
        or iter is not _MEMO_ITER or next is not _MEMO_NEXT or _MEMO_FUNCTIONS is not _MEMO_LITERAL_FUNCTIONS
        or _literal_function is not _SOURCE_LITERAL_FUNCTION[0]
        or _literal_function.__code__ is not _SOURCE_LITERAL_FUNCTION[1]):return False
    return all(_literal_function(function,stamp) for function,stamp in (
        (_memo_key,_MEMO_FUNCTIONS[0]),(_memo_state,_MEMO_FUNCTIONS[1]),
        (_memo_get,_MEMO_FUNCTIONS[2]),(_memo_store,_MEMO_FUNCTIONS[3])))


def _memo_enabled():
    # Do not invoke a replaced eligibility helper even to choose fallback.
    if (_memo_valid is not _MEMO_VALID_FUNCTION or _memo_valid.__code__ is not _MEMO_VALID_CODE
        or _memo_valid.__defaults__ is not None or _memo_valid.__kwdefaults__ is not None):return False
    return _memo_valid()


def queries(rows,pid,*,strict=True):
    cache=_ACTIVE.get()
    if (_memo_enabled is not _MEMO_ENABLED_FUNCTION or _memo_enabled.__code__ is not _MEMO_ENABLED_CODE
        or _memo_enabled.__defaults__ is not None or _memo_enabled.__kwdefaults__ is not None):
        return original_queries(rows,pid,strict=strict)
    if cache is None or not _memo_enabled() or not bounded(rows,pid,strict):return original_queries(rows,pid,strict=strict)
    encoded=marshal.dumps((rows,pid,strict),4)
    if len(encoded)>MAX_BYTES:return original_queries(rows,pid,strict=strict)
    key=hashlib.sha256(encoded).digest()
    found,cached=_memo_get(cache,key)
    if found:return deepcopy(cached)
    result=original_queries(rows,pid,strict=strict)
    cost=len(encoded)+len(marshal.dumps(result,4))+len(key)
    _memo_store(cache,key,deepcopy(result),cost)
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
        or bytes is not _MEMO_BYTES or all is not _MEMO_ALL or iter is not _MEMO_ITER or next is not _MEMO_NEXT
        or _MEMO_FUNCTIONS is not _MEMO_LITERAL_FUNCTIONS
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
    found,cached=_memo_get(cache,key)
    if found:
        copied=_source_snapshot(cached)
        return copied[0] if copied is not None else _SOURCE_ORIGINAL_QUERY(rows,pid,strict=strict)
    result=_SOURCE_ORIGINAL_QUERY(private_rows,private_pid,strict=private_strict)
    if _source_epoch()!=epoch or _ACTIVE is not active or active.get() is not cache:return result
    current=_source_snapshot([rows,pid,strict])
    if current is None or current[1]!=encoded:return _SOURCE_ORIGINAL_QUERY(rows,pid,strict=strict)
    copied=_source_snapshot(result)
    if copied is None:return result
    copied_result,result_bytes=copied;cost=len(encoded)+len(result_bytes)+len(key[2])
    _memo_store(cache,key,copied_result,cost)
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
_MEMO_BYTES,_MEMO_ALL,_MEMO_ITER,_MEMO_NEXT=bytes,all,iter,next
_MEMO_FUNCTIONS=tuple(_function_stamp(function) for function in (_memo_key,_memo_state,_memo_get,_memo_store))
_MEMO_LITERAL_FUNCTIONS=_MEMO_FUNCTIONS
_MEMO_VALID_FUNCTION,_MEMO_VALID_CODE=_memo_valid,_memo_valid.__code__
_MEMO_ENABLED_FUNCTION,_MEMO_ENABLED_CODE=_memo_enabled,_memo_enabled.__code__
_SOURCE_FUNCTIONS=tuple((getter,_function_stamp(getter),_function_stamp(getter())) for getter in (
    lambda:original_queries,lambda:bounded,lambda:deepcopy,lambda:scope,lambda:_source_snapshot,
    lambda:_memo_key,lambda:_memo_state,lambda:_memo_get,lambda:_memo_store,lambda:_memo_valid,lambda:_memo_enabled,
    lambda:scope.__wrapped__,lambda:queries,lambda:source_queries,lambda:source_eligible,
    lambda:original_queries.__globals__['decode'],lambda:original_queries.__globals__['validate'],
    lambda:original_queries.__globals__['follow'],lambda:original_queries.__globals__['exact'],
    lambda:original_queries.__globals__['need'],lambda:original_queries.__globals__['same']))
_SOURCE_EPOCH=tuple((stamp[0],stamp[1],id(stamp[2]),id(stamp[3]),id(stamp[5])) for _getter,_getter_stamp,stamp in _SOURCE_FUNCTIONS)
_SOURCE_GETTERS,_SOURCE_LITERAL_EPOCH=_SOURCE_FUNCTIONS,_SOURCE_EPOCH
_SOURCE_EPOCH_FUNCTION,_SOURCE_EPOCH_CODE=_source_epoch,_source_epoch.__code__
