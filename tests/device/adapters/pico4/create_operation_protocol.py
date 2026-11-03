"""Private existing-Parent component messages, separate from Common evidence."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import math
from adapters.pico4.operation_protocol import dto_bytes,REQUEST_LIMIT,need
from feature_journeys.contract import identifier,arguments as feature_arguments

VERSION=1
OPERATIONS=('prepare','act','sample','reconcile','cleanup','input.begin','input.end','peer.start','peer.accept')


def validate(value):
    need(type(value) is dict and set(value)=={'picoCreateOperationRequestVersion','requestId','runId','fixtureUrl','operation','budget','arguments'})
    need(type(value['picoCreateOperationRequestVersion']) is int and value['picoCreateOperationRequestVersion']==VERSION)
    for key in ('requestId','runId'):identifier(value[key])
    need(type(value['fixtureUrl']) is str and value['fixtureUrl'].endswith('/runs/'+value['runId']+'/') and value['operation'] in OPERATIONS)
    dto_bytes(value,REQUEST_LIMIT,arguments=True);budget=value['budget']
    need(type(budget) is dict and set(budget)=={'id','startedMonotonic','deadlineMonotonic'});identifier(budget['id'])
    need(all(type(budget[key]) in (int,float) and math.isfinite(budget[key]) for key in ('startedMonotonic','deadlineMonotonic'))
        and 0<=budget['startedMonotonic']<budget['deadlineMonotonic']<=budget['startedMonotonic']+60)
    operation,fields=value['operation'],value['arguments']
    if operation=='input.begin':
        need(type(fields) is dict and set(fields)=={'operation','arguments'} and fields['operation'] in ('prepare','act','cleanup'))
        operation,fields=fields['operation'],fields['arguments']
    if operation=='act':
        feature_arguments('feature.create.act',fields)
        need(fields['runId']==value['runId'] and fields['fixtureUrl']==value['fixtureUrl'])
    elif operation=='peer.start':
        need(type(fields) is dict and set(fields)=={'target','candidateArguments','fixtureUrl','actorToken','durationSeconds','artifactRoot'})
    else:need(fields is None)
    return value
