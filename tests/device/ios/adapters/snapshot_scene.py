"""Actual render-entry inputs carried by an ordinary consumed OpenGL frame.

This finite profile covers entity UUIDs, actual model/render transforms and
world bounds at balanced doRender entry/return. It does not cover material,
texture, animation-deformation fidelity or pixel coverage of individual items.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import re
from adapters.native_feature_observation import exact,integer,need,number
from adapters.script_feature.history import same
from ios.adapters import snapshot_provenance as provenance,snapshot_captures
from ios.adapters.places_model import IOSPlacesModel
ACTION='feature-ios-snapshot-scene'
FILE=ACTION+'.json'
LIMIT=262144
PROFILE='entity-render-entry-v1'


def command(value):
    prior=deepcopy(value);prior['action']=snapshot_captures.ACTION;snapshot_captures.command(prior)
    need(value['action']==ACTION);return value


def scene(value):
    exact(value,{'snapshotRenderedSceneVersion','profile','complete','entities'})
    need(type(value['snapshotRenderedSceneVersion']) is int and value['snapshotRenderedSceneVersion']==1
        and value['profile']==PROFILE and value['complete'] is True
        and type(value['entities']) is list and 1<=len(value['entities'])<=256)
    ids=set();items=set()
    for row in value['entities']:
        exact(row,{'entityId','rendererInstance','renderItemId','modelTransform','renderTransform','worldBounds','entered','returned'})
        identity=row['entityId'];need(type(identity) is str and re.fullmatch('[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',identity)
            and identity!='00000000-0000-0000-0000-000000000000' and identity not in ids);ids.add(identity)
        snapshot_captures.identity(row['rendererInstance'])
        need(integer(row['renderItemId'],1,2**32-1) and row['renderItemId'] not in items);items.add(row['renderItemId'])
        for key in ('modelTransform','renderTransform'):
            matrix=row[key];need(type(matrix) is list and len(matrix)==16
                and all(number(n,-1e12,1e12) for n in matrix) and matrix[12:]==[0,0,0,1])
        box=row['worldBounds'];need(type(box) is list and len(box)==6
            and all(number(n,-1e12,1e12) for n in box[:3]) and all(number(n,0,1e12) for n in box[3:])
            and integer(row['entered'],1,4096) and integer(row['returned'],1,4096) and row['entered']==row['returned'])
    return value


def frame(value,pid,epoch):
    provenance.recorded_frame(value,pid,epoch,version=2,extra={'scene','consumedEpochMs'})
    scene(value['scene']);need(integer(value['consumedEpochMs'],value['recordedEpochMs'],epoch))
    return value


def validate(value,query,pid,epoch=None,previous=None):
    command(query)
    exact(value,{'iosSnapshotSceneVersion','requestId','runId','instance','sequence','processId','clockDomain','clockBefore','clockAfter','source'})
    need(type(value['iosSnapshotSceneVersion']) is int and value['iosSnapshotSceneVersion']==1
        and value['requestId']==query['commandId'] and value['runId']==query['runId']
        and integer(pid,1) and integer(value['processId'],1) and value['processId']==pid
        and integer(value['sequence'],1,1000000000) and value['clockDomain']=='native-main-snapshot-scene')
    snapshot_captures.identity(value['instance'])
    for clock in (value['clockBefore'],value['clockAfter']):
        exact(clock,{'epochMs','monotonicMs'});need(integer(clock['epochMs'],1) and integer(clock['monotonicMs']))
    before,after=value['clockBefore'],value['clockAfter'];elapsed=after['epochMs']-before['epochMs'];mono=after['monotonicMs']-before['monotonicMs']
    need(0<=elapsed<1500 and 0<=mono<1500 and abs(elapsed-mono)<=250)
    if epoch is not None:
        from adapters.native_feature_observation import fresh
        fresh(after['epochMs'],epoch)
    source=value['source'];exact(source,{'complete','frame'});need(source['complete'] is True)
    frame(source['frame'],pid,before['epochMs']);need(0<=after['epochMs']-source['frame']['consumedEpochMs']<1500)
    need(len(json.dumps(value,allow_nan=False).encode())<=LIMIT)
    if previous is not None:
        validate(previous,dict(query,commandId=previous['requestId']),pid)
        need(value['instance']==previous['instance'] and value['sequence']>previous['sequence'] and value['requestId']!=previous['requestId']
            and all(before[key]>=previous['clockAfter'][key] for key in before))
        old=previous['source']['frame'];current=source['frame']
        if current['frameInstance']==old['frameInstance']:need(same(current,old))
        else:need(current['frameIndex']>old['frameIndex'] and current['recordedEpochMs']>=old['recordedEpochMs'])
    return value


def original(value):
    return validate(value,dict(schemaVersion=1,action=ACTION,commandId=value.get('requestId'),runId=value.get('runId')),value.get('processId'))


def measured_entities(value):
    scene(value)
    # Process-local renderer/item identities and draw counts remain preserved in
    # the originals. They cannot be compared as shared cross-device identities.
    return {row['entityId']:{key:deepcopy(row[key]) for key in ('modelTransform','renderTransform','worldBounds')}
        for row in value['entities']}


class IOSSnapshotScene(IOSPlacesModel):
    _limit=LIMIT;_action=ACTION;_command=staticmethod(command);_validate=staticmethod(validate)
    _acquisition_key='iosSnapshotSceneAcquisitionVersion'
