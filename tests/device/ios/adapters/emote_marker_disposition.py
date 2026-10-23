"""Original quiet marker holders before independent Emote process retirement.

This admits no callback or policy grant. Cached native/image/GPU objects remain
explicitly held; only an independently verified process end can retire them.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy

from adapters.native_clock_join import digest
from adapters.native_feature_observation import need
from feature_journeys.terminal import held
from ios.adapters.web_closures import validate,continuity,drained,resources_for

VERSION=1
KINDS={'scenegraph-node':'qsg-root','offscreen-image':'qimage','upload-image':'qimage',
    'native-bitmap':'qimage','native-view':'wk-view'}


def packet(value):
    need(type(value) is dict)
    validate(value,dict(schemaVersion=1,commandId=value.get('commandId'),action='feature-ios-web-closures',
        runId=value.get('runId'),fixtureUrl=value.get('fixtureUrl')),value.get('processId'),value.get('capturedEpochMs'))
    need(value['iosWebClosureVersion']==5 and value['complete'] is True)
    return value


def disposition(current,admitted,*,partial=False):
    need(type(partial) is bool);packet(admitted);packet(current)
    continuity(admitted,current,admitted['processId'])
    if not partial:
        drained(current,admitted)
        required=resources_for(5)-{'native-presentation'}
        need(all(any(row['resources'][name]['created']>0 for row in admitted['contexts']) for name in required))
    need(all(counter['pending']==0 for row in current['contexts'] for counter in row['callbacks'].values())
        and all(row['resources']['policy-grant']['pending']==0 for row in current['contexts']))
    rows=[]
    for context in current['contexts']:
        for name,counter in context['resources'].items():
            if not counter['pending']:continue
            original=dict(iosEmoteMarkerHolderVersion=VERSION,runId=current['runId'],processId=current['processId'],
                sourceInstance=current['instance'],contextId=context['id'],descriptor=deepcopy(context['descriptor']),
                resourceKind=name,counter=deepcopy(counter))
            identity=digest(original)
            rows.append(dict(resource='panel:emote-'+name+'-'+identity[:20],kind=KINDS.get(name,'native-holder'),
                originalSha256=identity,original=original))
    rows.sort(key=lambda row:row['resource'])
    held([{key:row[key] for key in ('resource','kind','originalSha256')} for row in rows])
    return dict(iosEmoteMarkerDispositionVersion=VERSION,runId=current['runId'],mode='held' if rows else 'released',
        originalSha256=digest(current),contexts=deepcopy(current['contexts']),holders=rows)


def unchanged(first,last):
    """No activity changed; this supplies no duration or process-death fact."""
    packet(first);packet(last);continuity(first,last,first['processId'])
    need(first['contexts']==last['contexts']);return True
