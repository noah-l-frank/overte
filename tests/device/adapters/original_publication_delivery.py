"""Original publication freshness at the actual context-owned HTTP send."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import need,number
from adapters.operation_transport_guard import scope


def fresh(clock,monotonic,epoch_ms):
    # These are the original host clocks, never a source guard/native read.
    now,epoch=monotonic(),epoch_ms()
    need(number(now,clock['hostAfterMonotonic'],clock['hostBeforeMonotonic']+1.5)
        and now-clock['hostBeforeMonotonic']<1.5
        and number(epoch,clock['hostAfterEpochMs'],clock['hostBeforeEpochMs']+1500)
        and epoch-clock['hostBeforeEpochMs']<1500
        and abs(epoch-clock['hostBeforeEpochMs']-(now-clock['hostBeforeMonotonic'])*1000)<=250)


def delivery(owner,clock):
    # SDK/native continuity is checked once outside the registered transport
    # guard. Calling it inside would recurse through its own SDK final guard.
    owner.bound();owner.acquisition(clock);original=deepcopy(clock)
    monotonic,epoch_ms=owner.monotonic,owner.epoch_ms
    return scope(lambda:fresh(original,monotonic,epoch_ms))
