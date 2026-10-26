"""Retry only typed effect readiness after releasing both actual SDK locks."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from functools import wraps
from adapters.native_feature_observation import need


class ObservationPending(BaseException):
    """Private signal crossing lock cleanup without normalizing its identity."""
    def __init__(self,ticket):self.ticket=ticket


def retry_observation(function):
    @wraps(function)
    def invoke(flow,*args,**kwargs):
        while True:
            try:return function(flow,*args,**kwargs)
            except ObservationPending as pending:
                need(flow.RETRY_OBSERVATION_READINESS and flow.lock._owner is None and flow.primary_lock._owner is None)
                flow.clock();status=flow.phase.status()
                need(status['active'] and status['activations'][-1]['ticket']==pending.ticket)
                flow.sleep(.05);flow.clock()
    return invoke
