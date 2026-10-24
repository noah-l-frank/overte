"""Bounded API-local reuse of exactly equal, fully validated event prefixes.

This stores pure transcript data only. Every packet header, acquisition clock,
explicit previous-packet relation and original file read stays independently
checked by its owning reader. No result, freshness or live history is cached.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from adapters.script_feature.history import canonical

MAX_KEYS=16
MAX_BYTES=8*1024*1024
_CURRENT=ContextVar('world_web_pure_event_prefixes',default=None)


@contextmanager
def scope():
    if _CURRENT.get() is not None:yield;return
    token=_CURRENT.set(dict(rows={},bytes=0))
    try:yield
    finally:_CURRENT.reset(token)


def key(value):
    return tuple(value[name] for name in ('iosWorldWebVersion','runId','fixtureUrl','instance','processId'))


def start(value):
    cache=_CURRENT.get()
    if cache is None:return None
    row=cache['rows'].get(key(value))
    if row is None:return None
    count=min(row['count'],len(value['events']))
    earlier=row['earlier'];ids=row['ids'];last=row['last']
    callback_enter=row['callback_enter'];callback_return=row['callback_return'];signal_return=row['signal_return']
    raw=row['canonical']
    if count<row['count']:
        events=list(earlier.values())[:count];raw=canonical(events)
        earlier={event['sequence']:event for event in events};ids={event['eventId'] for event in events}
        last=(0,0,0) if not events else (events[-1]['clock']['epochMs'],events[-1]['clock']['monotonicMs'],events[-1]['sequence'])
        callback_enter={event['detail']['entry'] for event in events if event['kind']=='callback-enter'}
        callback_return={event['detail']['entry'] for event in events if event['kind']=='callback-return'}
        signal_return={event['detail']['entry'] for event in events if event['kind']=='signal-return'}
    last_epoch,last_mono,last_sequence=last
    if (last_epoch>value['clockBefore']['epochMs']
        or last_mono>value['clockBefore']['monotonicMs'] or last_sequence>value['eventSequence']
        or canonical(value['events'][:count])!=raw):return None
    # Prefix events are private immutable copies. The validator reads earlier
    # details but adds only new entries to its separate dictionary and sets.
    return (count,dict(earlier),set(ids),last,set(callback_enter),set(callback_return),set(signal_return))


def remember(value,earlier,ids,last,callback_enter,callback_return,signal_return):
    cache=_CURRENT.get()
    if cache is None:return
    identity=key(value);old=cache['rows'].get(identity);count=len(value['events'])
    if old is not None and count<old['count']:return
    raw=canonical(value['events']);cost=len(raw)+1024
    if old is not None and raw==old['canonical']:return
    total=cache['bytes']-(0 if old is None else old['cost'])+cost
    if total>MAX_BYTES or old is None and len(cache['rows'])>=MAX_KEYS:return
    cache['rows'][identity]=dict(count=count,canonical=raw,cost=cost,earlier=deepcopy(earlier),ids=frozenset(ids),last=last,
        callback_enter=frozenset(callback_enter),callback_return=frozenset(callback_return),signal_return=frozenset(signal_return))
    cache['bytes']=total
