"""Original authorized World envelopes restrict independently measured events.

The Parent's World history supplies no Actor pose, effect, receipt or counter.
Its full original bytes and decoded size remain owned archival input.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy

from adapters.native_feature_observation import exact,integer,need
from adapters.pico4 import lifecycle_gesture as gesture
from adapters.pico4.lifecycle_world import LifecycleWorldHistory,MOVE
from adapters.script_journey.history import MAX_RAW


def decoded_bytes(original):
    exact(original,{'lifecycleWorldOwnerVersion','runId','binding','payload'})
    need(type(original['lifecycleWorldOwnerVersion']) is int and original['lifecycleWorldOwnerVersion'] in (1,2)
        and type(original['payload']) is dict and integer(original['payload'].get('bytes'),2,MAX_RAW))
    return original['payload']['bytes']


def restrictions(original,run,binding,pid,profile):
    state,_previous,_origin=LifecycleWorldHistory(run,binding,pid,profile).validate(original)
    need(1<=len(state['attempts'])<=2)
    # Only original authorized command bytes escape the historical validator.
    # Receipt IDs, phases, original Primary source rows and measured counts do
    # not supply the Actor's observations.
    envelopes=[deepcopy(attempt['envelope']) for attempt in state['attempts']]
    need(all(type(envelope) is dict for envelope in envelopes));return envelopes


def measured_attempts(events,envelopes):
    need(type(events) is list and type(envelopes) is list and len(events)==len(envelopes)<=2)
    for event,envelope in zip(events,envelopes):
        gesture.consumed(event,envelope)
        need(abs(event['sample']['raw'][0])<=1e-6
            and abs(event['sample']['raw'][1]-MOVE['strength'])<=1e-6)
    return len(events)
