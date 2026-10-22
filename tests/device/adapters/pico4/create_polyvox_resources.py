"""Original weak PolyVox entity mesh/render-copy/texture histories."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import exact,integer,need
from adapters.token_create_ui import nonce


def validate(value,epoch):
    exact(value,{'createPolyvoxResourcesVersion','instance','sourceSequence','bindings','meshes','renderers','textures'})
    need(type(value['createPolyvoxResourcesVersion']) is int and value['createPolyvoxResourcesVersion']==1
        and nonce(value['instance']) and integer(value['sourceSequence'],1,1_000_000_000))
    known={};all_ids=set()
    for kind,limit in (('meshes',128),('renderers',64),('textures',96)):
        rows=value[kind];need(type(rows) is list and len(rows)<=limit);ids=[]
        for row in rows:
            exact(row,{'id','firstObservedEpochMs','alive'});need(nonce(row['id']) and integer(row['firstObservedEpochMs'],1,epoch)
                and type(row['alive']) is bool and row['id'] not in all_ids);ids.append(row['id']);all_ids.add(row['id'])
        need(ids==sorted(set(ids)));known[kind]=set(ids)
    need(type(value['bindings']) is list and len(value['bindings'])<=32);entities=[]
    from adapters.pico4.create_entities import entity_id
    for row in value['bindings']:
        exact(row,{'entityId','entityMesh','renderer','rendererMesh','textures','renderObservations'})
        need(entity_id(row['entityId']) and integer(row['renderObservations'],0,1_000_000_000)
            and type(row['textures']) is list and len(row['textures'])==(3 if row['renderObservations'] else 0))
        for field,kind in (('entityMesh','meshes'),('rendererMesh','meshes'),('renderer','renderers')):
            need(row[field] is None or row[field] in known[kind])
        need(all(v is None or v in known['textures'] for v in row['textures']) and (row['renderObservations']==0)==(row['renderer'] is None))
        entities.append(row['entityId'])
    need(entities==sorted(set(entities)));return value


def continuity(before,after):
    need(before['instance']==after['instance'] and after['sourceSequence']>before['sourceSequence'])
    for kind in ('meshes','renderers','textures'):
        rows={r['id']:r for r in after[kind]}
        for row in before[kind]:need(row['id'] in rows and row['firstObservedEpochMs']==rows[row['id']]['firstObservedEpochMs']
            and (row['alive'] or not rows[row['id']]['alive']))
    rows={r['entityId']:r for r in after['bindings']}
    for row in before['bindings']:need(row['entityId'] in rows and row['renderObservations']<=rows[row['entityId']]['renderObservations'])


def retired(value):return all(not row['alive'] for kind in ('meshes','renderers','textures') for row in value[kind])


def joined(value,identifier):
    rows=[r for r in value['bindings'] if r['entityId']==identifier];need(len(rows)==1);row=rows[0]
    meshes={r['id']:r for r in value['meshes']};renderers={r['id']:r for r in value['renderers']}
    return bool(row['renderObservations']>0 and row['entityMesh'] is not None and row['entityMesh']==row['rendererMesh']
        and meshes[row['entityMesh']]['alive'] and row['renderer'] is not None and renderers[row['renderer']]['alive'])


def stable(value):
    result=deepcopy(value);result.pop('sourceSequence');return result
