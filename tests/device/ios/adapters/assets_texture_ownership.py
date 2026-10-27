"""Original TextureMap/TextureSource weak groups, without GPU evaluation.

Expiry describes strong sharing owners only. Decoder jobs, destructors, GPU
operators, backend allocations and automatic product cleanup remain separate.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import exact,integer,need
from adapters.script_feature.history import same

VERSION=1
REVISION_LIMIT=1048576


def validate(value,geometries,consumers,clock,complete):
    from ios.adapters.assets_model_origin import identity,stamp,ordered
    exact(value,{'assetModelTextureOwnershipVersion','revision','nodes','links'})
    need(type(value['assetModelTextureOwnershipVersion']) is int and value['assetModelTextureOwnershipVersion']==VERSION
        and integer(value['revision'],0,REVISION_LIMIT) and type(value['nodes']) is list and len(value['nodes'])<=256
        and type(value['links']) is list and len(value['links'])<=512)
    nodes={};parents={row['id']:row for row in geometries}
    slots={(row['geometryId'],row['slot']) for row in consumers if row['kind']=='material'}
    for row in value['nodes']:
        exact(row,{'id','kind','born','strongOwnersAlive','ownershipExpiryObserved'})
        identity(row['id']);need(row['id'] not in nodes);nodes[row['id']]=row
        need(row['kind'] in ('map','source') and type(row['strongOwnersAlive']) is bool);stamp(row['born'],clock)
        if row['ownershipExpiryObserved'] is None:need(row['strongOwnersAlive'])
        else:
            need(not row['strongOwnersAlive']);stamp(row['ownershipExpiryObserved'],clock)
            ordered(row['born'],row['ownershipExpiryObserved'])
    ids=set();edges=set()
    for row in value['links']:
        exact(row,{'id','geometryId','materialSlot','channel','mapId','sourceId','born','lastObserved','revision'})
        identity(row['id']);need(row['id'] not in ids);ids.add(row['id'])
        need(type(row['geometryId']) is str and row['geometryId'] in parents
            and integer(row['materialSlot'],0,255) and (row['geometryId'],row['materialSlot']) in slots
            and integer(row['channel'],-1,255) and integer(row['revision'],1,value['revision']))
        stamp(row['born'],clock);stamp(row['lastObserved'],clock)
        ordered(parents[row['geometryId']]['born'],row['born']);ordered(row['born'],row['lastObserved'])
        for key,kind in (('mapId','map'),('sourceId','source')):
            need(type(row[key]) is str)
            if row[key]:
                need(row[key] in nodes and nodes[row[key]]['kind']==kind);ordered(nodes[row[key]]['born'],row['born'])
        need(not row['sourceId'] or row['mapId'])
        if row['channel']==-1:need(not row['mapId'] and not row['sourceId'])
        edge=tuple(row[key] for key in ('geometryId','materialSlot','channel','mapId','sourceId'))
        need(edge not in edges);edges.add(edge)
    # An allocation/cap failure can leave a partial node without a link, but
    # only an explicitly incomplete acquisition may carry that partial state.
    if complete:
        need(set(nodes)=={row[key] for row in value['links'] for key in ('mapId','sourceId') if row[key]}
            and value['revision']==max((row['revision'] for row in value['links']),default=0))
    return value


def successor(before,after,clock):
    from ios.adapters.assets_model_origin import ordered
    need(after['revision']>=before['revision'] and len(after['nodes'])>=len(before['nodes'])
        and len(after['links'])>=len(before['links']))
    for first,last in zip(before['nodes'],after['nodes']):
        need(all(same(first[key],last[key]) for key in first if key not in ('strongOwnersAlive','ownershipExpiryObserved'))
            and (first['strongOwnersAlive'] or not last['strongOwnersAlive'])
            and (first['ownershipExpiryObserved'] is None or same(first['ownershipExpiryObserved'],last['ownershipExpiryObserved'])))
        if first['strongOwnersAlive'] and not last['strongOwnersAlive']:ordered(clock,last['ownershipExpiryObserved'])
    for first,last in zip(before['links'],after['links']):
        need(all(same(first[key],last[key]) for key in first if key not in ('revision','lastObserved'))
            and last['revision']>=first['revision']);ordered(first['lastObserved'],last['lastObserved'])
        if last['revision']==first['revision']:need(same(first['lastObserved'],last['lastObserved']))
        else:need(after['revision']>before['revision'])
    if after['revision']==before['revision']:
        need(same(before['links'],after['links']) and len(before['nodes'])==len(after['nodes']))


def consumers(value,reader_id):
    from ios.adapters.assets_model_origin import geometry_consumers
    geometry=geometry_consumers(value,reader_id);history=value['source']['history']
    need(history['assetModelOriginHistoryVersion']>=5);inventory=history['textureOwnership']
    parents={row['id'] for row in geometry['geometries']}
    links=[row for row in inventory['links'] if row['geometryId'] in parents]
    selected={row[key] for row in links for key in ('mapId','sourceId') if row[key]}
    rows=[row for row in inventory['nodes'] if row['id'] in selected]
    # Empty/legacy inventories cannot establish that a textured model had no
    # holders. This fact requires original positive map AND source membership.
    need(any(row['kind']=='map' for row in rows) and any(row['kind']=='source' for row in rows))
    return dict(assetModelTextureConsumersVersion=VERSION,runId=geometry['runId'],processId=geometry['processId'],
        requestId=geometry['requestId'],historyInstance=geometry['historyInstance'],readerId=reader_id,
        nativeEpochMs=geometry['nativeEpochMs'],bodySha256=geometry['bodySha256'],bodyBytes=geometry['bodyBytes'],
        revision=inventory['revision'],nodes=deepcopy(rows),links=deepcopy(links),
        allKnownTextureOwnersGone=all(not row['strongOwnersAlive'] for row in rows),
        decoderCompletionAvailable=False,destructorCompletionAvailable=False,
        gpuCompletionAvailable=False,resourceRetirementAvailable=False)
