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
from adapters.original_marker_clock_queries import queries as original_queries

MAX_BYTES=8*1024*1024
MAX_ENTRIES=512
_ACTIVE=ContextVar('world_web_original_clock_validation',default=None)


@contextmanager
def scope():
    if _ACTIVE.get() is not None:yield;return
    token=_ACTIVE.set(dict(entries={},bytes=0))
    try:yield
    finally:_ACTIVE.reset(token)


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
