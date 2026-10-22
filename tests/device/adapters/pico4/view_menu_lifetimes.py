"""Original menu StackView/Timer/context weak histories; no inferred release."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import exact,fresh,integer,need
from adapters.native_avatar_render import nonce

VERSION=1
FLAGS={'pageAlive','stackAlive','timerAlive','contextAlive','timerContextAlive'}


def validate(value,epoch):
    exact(value,{'instance','sequence','capturedEpochMs','originals'})
    need(nonce(value['instance']) and integer(value['sequence'],1,9007199254740991)
        and integer(value['capturedEpochMs'],1) and type(value['originals']) is list and len(value['originals'])<=32)
    fresh(value['capturedEpochMs'],epoch);ids=set()
    for row in value['originals']:
        exact(row,{'instance','firstObservedEpochMs','alive','timerRunning','pendingMenuItem'}|FLAGS)
        need(nonce(row['instance']) and row['instance'] not in ids
            and integer(row['firstObservedEpochMs'],1,value['capturedEpochMs'])
            and all(type(row[k]) is bool for k in FLAGS|{'alive','timerRunning','pendingMenuItem'})
            and row['alive']==any(row[k] for k in FLAGS)
            and (row['timerAlive'] or not row['timerRunning'] and not row['pendingMenuItem']))
        ids.add(row['instance'])
    return value


def accept(previous,current):
    validate(current,current['capturedEpochMs'])
    if previous is not None:
        validate(previous,previous['capturedEpochMs'])
        need(current['instance']==previous['instance'] and current['sequence']>previous['sequence']
            and current['capturedEpochMs']>=previous['capturedEpochMs'] and len(current['originals'])>=len(previous['originals']))
        for old,new in zip(previous['originals'],current['originals']):
            need(all(new[k]==old[k] for k in ('instance','firstObservedEpochMs'))
                and all(old[k] or not new[k] for k in FLAGS))
    return current


def retired(initial,current):
    accept(initial,current);prior={row['instance'] for row in initial['originals']}
    owned=[row for row in current['originals'] if row['instance'] not in prior]
    need(owned) # An unobserved menu lifetime cannot supply a retirement proof.
    return all(not row['alive'] for row in owned)
