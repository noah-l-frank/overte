"""Closed original baked and unbaked lineage DTOs; no source acquisition."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import re
from adapters.native_feature_observation import exact,integer,need
from feature_journeys.asset_fixture import BUNDLES
from feature_journeys.contract import identifier
from ios.adapters import create_state

COMMON={'runId','processId','domainId','entityId','creationRequestId','originRequestId','readerId',
        'nativeGeometryRequestId','backendRequestId','path','sha256','bytes'}
BAKED=COMMON|{'assetModelBakedInputProofVersion','bakeRequestId','outputPath'}
BUNDLE=COMMON|{'assetModelBundleInputProofVersion','resource','files'}


def validate(value):
    need(type(value) is dict)
    baked='assetModelBakedInputProofVersion' in value;exact(value,BAKED if baked else BUNDLE)
    key='assetModelBakedInputProofVersion' if baked else 'assetModelBundleInputProofVersion'
    need(type(value[key]) is int and value[key]==1);identifier(value['runId']);need(integer(value['processId'],1))
    for key in ('domainId','entityId'):create_state.uuid(value[key])
    for key in ('creationRequestId','originRequestId','nativeGeometryRequestId'):
        need(type(value[key]) is str and re.fullmatch('ios-[a-f0-9]{32}',value[key]))
    for key in (('backendRequestId','bakeRequestId') if baked else ('backendRequestId',)):
        need(type(value[key]) is str and re.fullmatch('assets-[a-f0-9]{32}',value[key]))
    need(type(value['readerId']) is str and re.fullmatch('[a-f0-9]{32}',value['readerId'])
        and integer(value['bytes'],1) and type(value['sha256']) is str and re.fullmatch('[a-f0-9]{64}',value['sha256'])
        and type(value['path']) is str and value['path'].startswith('/') and len(value['path'])<=4096)
    if baked:
        need(type(value['outputPath']) is str and value['outputPath'].startswith('/.baked/') and len(value['outputPath'])<=4096)
    else:
        need(integer(value['bytes'],1,32768))
        resource=value['resource'];need(resource in ('gltf-bundle/main.gltf','obj-bundle/main.obj'))
        primary,paths=BUNDLES[resource];need(value['path'].endswith('/'+primary));prefix=value['path'][:-len(primary)]
        need(type(value['files']) is list and len(value['files'])==len(paths));seen=set()
        for row in value['files']:
            exact(row,{'path','bytes','sha256'})
            need(type(row['path']) is str and row['path'] in {prefix+path for path in paths} and row['path'] not in seen
                and integer(row['bytes'],1,32768) and type(row['sha256']) is str and re.fullmatch('[a-f0-9]{64}',row['sha256']))
            seen.add(row['path'])
            if row['path']==value['path']:need(row['bytes']==value['bytes'] and row['sha256']==value['sha256'])
    return value
