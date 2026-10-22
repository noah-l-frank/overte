"""Original host operation deadline; reconstruction never renews it."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import exact,need,number
from adapters.normal_ui import NativeUIError

VERSION=1


def begin(epoch,monotonic):
    need(number(epoch,1,1e15) and number(monotonic,0,1e15))
    return dict(avatarOperationClockVersion=VERSION,hostStartedEpochMs=epoch,hostStartedMonotonic=monotonic,
        deadlineEpochMs=epoch+25000,deadlineMonotonic=monotonic+25)


def validate(value):
    exact(value,{'avatarOperationClockVersion','hostStartedEpochMs','hostStartedMonotonic','deadlineEpochMs','deadlineMonotonic'})
    need(type(value['avatarOperationClockVersion']) is int and value['avatarOperationClockVersion']==VERSION
        and number(value['hostStartedEpochMs'],1,1e15) and number(value['hostStartedMonotonic'],0,1e15)
        and value['deadlineEpochMs']==value['hostStartedEpochMs']+25000 and value['deadlineMonotonic']==value['hostStartedMonotonic']+25)
    return value


def check(value,epoch,monotonic):
    validate(value)
    if not (number(epoch,value['hostStartedEpochMs'],value['deadlineEpochMs'])
            and number(monotonic,value['hostStartedMonotonic'],value['deadlineMonotonic'])
            and epoch<value['deadlineEpochMs'] and monotonic<value['deadlineMonotonic']
            and abs(epoch-value['hostStartedEpochMs']-(monotonic-value['hostStartedMonotonic'])*1000)<=250):
        raise NativeUIError('Original Avatar recipe deadline has elapsed or changed; no input is repeated')
    return monotonic
