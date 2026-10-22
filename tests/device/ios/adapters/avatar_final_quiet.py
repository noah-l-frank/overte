"""Pure actual Avatar postlogout subject quiet, with unchanged source DTOs."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import need
from adapters.script_feature.history import same
from ios.adapters import world_web_keys
from ios.adapters.emote_native_prefix import follow


def account_equal(left,right):
    a,b=deepcopy(left),deepcopy(right)
    # The native account getter genuinely samples its observation timestamp on
    # each read. Preserve both originals, compare the actual account state and
    # immutable event history without treating this timestamp as a mutation.
    for value in (a,b):value['observation'].pop('capturedEpochMs',None)
    return same(a,b)


def subject_quiet(samples,binding,*,run,role):
    need(type(samples) is list and len(samples)>=3)
    a,b=samples[0],samples[-1]
    frames=[dict(clockJoin=row['ui']['clockJoin']) for row in samples]
    a['pointers'].receipt(a['left'],binding,run,role)
    proof=b['pointers'].quiet(frames,baseline=a['left'])
    native_a,native_b=a['ui']['clockJoin']['nativeAfter'],b['ui']['clockJoin']['nativeBefore']
    keys_a,keys_b=a['tail'].keys(a['ui']),b['tail'].keys(b['ui'])
    need(keys_a['source']['instance']==keys_b['source']['instance'])
    clock_a,clock_b=keys_a['clockAfter'],keys_b['clockBefore']
    q=dict(hostAfterFirstEpochMs=frames[0]['clockJoin']['hostAfterEpochMs'],hostBeforeLastEpochMs=frames[-1]['clockJoin']['hostBeforeEpochMs'],
        hostAfterFirstMonotonic=frames[0]['clockJoin']['hostAfterMonotonic'],hostBeforeLastMonotonic=frames[-1]['clockJoin']['hostBeforeMonotonic'],
        nativeAfterFirstEpochMs=clock_a['epochMs'],nativeBeforeLastEpochMs=clock_b['epochMs'],
        nativeAfterFirstMonotonicMs=clock_a['monotonicMs'],nativeBeforeLastMonotonicMs=clock_b['monotonicMs'],
        nativeInstance=keys_a['source']['instance'],processId=keys_a['processId'])
    from feature_journeys.retirement_receipts import quiet,binding_from_context
    quiet(q,binding_from_context(binding))
    before_native=frames[0]['clockJoin']['nativeBefore'];epoch=before_native['capturedEpochMs']
    for row in samples:
        keys=row['tail'].keys(row['ui']);world_web_keys.drained(keys)
        need(same(keys['source'],keys_a['source']))
        need(row['proof']['endpointEpochMs']<=epoch and same(row['model']['source'],a['model']['source'])
            and same(row['ui']['packets']['http']['events'],a['ui']['packets']['http']['events']))
        for native in (row['ui']['clockJoin']['nativeBefore'],row['ui']['clockJoin']['nativeAfter'],row['right']['clockJoin']['nativeAfter']):
            need(same(native['lifecycle'],before_native['lifecycle']) and account_equal(native['account'],before_native['account'])
                and native['capturedEpochMs']>=epoch)
        follow(row['ui']['clockJoin']['nativeAfter'],row['right']['clockJoin']['nativeBefore'])
    need(proof['last']['clockJoin']['nativeAfter']['capturedEpochMs']>=native_b['capturedEpochMs'])
    http_a,http_b=a['ui']['packets']['http']['clockAfter'],b['ui']['packets']['http']['clockBefore']
    need(3000<=http_b['epochMs']-http_a['epochMs']<60000 and 3000<=http_b['monotonicMs']-http_a['monotonicMs']<60000)
    return q
