"""Explicit private Browser coordination on the original stdio operation host."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import math

from adapters.native_feature_observation import exact, need
from adapters.pico4.operation_protocol import dto_bytes, REQUEST_LIMIT
from feature_journeys.contract import identifier

VERSION = 1
OPERATIONS = ('begin', 'actor.start', 'consume', 'actor.return', 'finalize')


def budget(value, maximum):
    exact(value, {'id', 'startedMonotonic', 'deadlineMonotonic'})
    identifier(value['id'])
    need(all(type(value[key]) in (int, float) and math.isfinite(value[key])
        for key in ('startedMonotonic', 'deadlineMonotonic'))
        and 0 <= value['startedMonotonic'] < value['deadlineMonotonic']
        and value['deadlineMonotonic'] - value['startedMonotonic'] <= maximum)
    return value


def validate(value):
    exact(value, {'picoBrowserOperationRequestVersion', 'requestId', 'runId', 'fixtureUrl',
        'operation', 'wholeBudget', 'actionBudget', 'arguments'})
    need(type(value['picoBrowserOperationRequestVersion']) is int
        and value['picoBrowserOperationRequestVersion'] == VERSION)
    for key in ('requestId', 'runId'): identifier(value[key])
    need(type(value['fixtureUrl']) is str
        and value['fixtureUrl'].endswith('/runs/' + value['runId'] + '/')
        and value['operation'] in OPERATIONS)
    whole, action = budget(value['wholeBudget'], 120), budget(value['actionBudget'], 60)
    need(whole['startedMonotonic'] <= action['startedMonotonic']
        < action['deadlineMonotonic'] <= whole['deadlineMonotonic'])
    operation, fields = value['operation'], value['arguments']
    if operation == 'begin':
        exact(fields, {'artifactRoot', 'foreignFixtureUrl', 'nonce'})
        identifier(fields['nonce'])
        need(type(fields['artifactRoot']) is str and type(fields['foreignFixtureUrl']) is str)
    elif operation == 'actor.start':
        exact(fields, {'target', 'candidateArguments', 'fixtureUrl', 'actorToken', 'durationSeconds', 'artifactRoot'})
    elif operation == 'consume':
        exact(fields, {'journeyConsumptionExportVersion', 'name', 'rootSha256', 'rootStamp',
            'recordSha256', 'commonSha256', 'nonce', 'chunkPins'})
    else: need(fields is None)
    dto_bytes(value, REQUEST_LIMIT, arguments=True)
    return value
