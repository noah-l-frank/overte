"""Durable passive native-clock query ownership for new marker profiles.

The legacy Emote v1 envelopes remain byte/schema compatible. These reads never
create an input, Script VM or GPU operation; unknown source delivery is retained
before a distinct later observation, with every returned native prefix checked.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from copy import deepcopy
import re
from adapters.native_feature_observation import decode,exact,need,validate,LIMIT
from adapters.script_feature.history import same
from ios.adapters.emote_native_prefix import follow


def fields(profile):
    need(profile in ('emote','avatar','worldweb'));return set() if profile=='emote' else {'nativeQueries'}


def queries(rows,pid,*,strict=True):
    need(type(rows) is list and len(rows)<=128);last=None;nonces=set()
    for row in rows:
        exact(row,{'query','raws'});query=row['query'];exact(query,{'schemaVersion','commandId','action'})
        need(type(query['schemaVersion']) is int and query['schemaVersion']==1 and query['action']=='feature-native-observe'
            and type(query['commandId']) is str and re.fullmatch('ios-[a-f0-9]{32}',query['commandId']) and query['commandId'] not in nonces)
        nonces.add(query['commandId']);need(type(row['raws']) is list and len(row['raws'])<=51)
        accepted=None
        for raw in row['raws']:
            need(type(raw) is str and len(raw.encode())<=LIMIT)
            if not strict:continue
            try:value=decode(raw)
            except ValueError:continue
            if type(value) is not dict or value.get('requestId')!=query['commandId']:continue
            validate(value,query['commandId'],pid,value.get('capturedEpochMs'))
            if accepted is not None:need(same(accepted,value))
            else:
                if last is not None:follow(last,value)
                accepted=value;last=value
    return last


def bracket(profile,value,pid,*,query_decoder=None):
    if not fields(profile):return
    # An explicit pure decoder belongs only to this synchronous validation.
    # The default/shared/legacy path still calls its original queries directly.
    need(query_decoder is None or callable(query_decoder))
    last=(queries if query_decoder is None else query_decoder)(value['nativeQueries'],pid)
    need(last is not None and same(last,value['clockJoin']['nativeAfter']))
    first=value['clockJoin']['nativeBefore'];matched=False
    for row in value['nativeQueries']:
        if row['query']['commandId']!=first['requestId']:continue
        for raw in row['raws']:
            try:packet=decode(raw)
            except ValueError:continue
            if same(packet,first):matched=True
    need(matched)


def floor(profile,partial,current,pid):
    if not fields(profile):return
    last=queries(partial['nativeQueries'],pid)
    if last is not None:follow(last,current['clockJoin']['nativeBefore'])


@contextmanager
def owned(owner):
    if not fields(owner.PROFILE):yield;return
    owner.bound()
    send,read=owner.native.send,owner.native.original
    def sending(query):
        pending=owner.state['pending'];need(pending is not None and len(pending['nativeQueries'])<128)
        pending['nativeQueries'].append(dict(query=deepcopy(query),raws=[]));owner.save();return send(query)
    def reading():
        raw=read();pending=owner.state['pending'];need(pending is not None and pending['nativeQueries'])
        need(type(raw) is str and len(raw.encode())<=LIMIT);rows=pending['nativeQueries'][-1]['raws']
        if not rows or rows[-1]!=raw:
            need(len(rows)<51);rows.append(raw);owner.save()
        return raw
    owner.native.send,owner.native.original=sending,reading
    try:yield
    finally:owner.native.send,owner.native.original=send,read
