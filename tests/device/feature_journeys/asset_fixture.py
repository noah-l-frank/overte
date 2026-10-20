"""Closed original input bundles for the ordinary Assets file browser.

Hashes describe controlled INPUT bytes. They are never observation results or
proof that an upload, server bake or rendered model succeeded.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
from .fixtures import companion,context,pinned_resource

VERSION=1
BUNDLES={
    'gltf-bundle/main.gltf':('main.gltf',('main.gltf','mesh/triangle.bin','textures/checker.png')),
    'obj-bundle/main.obj':('main.obj',('main.obj','materials/palette.mtl','textures/checker.png')),
    'asset-stand.fbx':('stand.fbx',('stand.fbx',)),
}


def bundle(run,ticket,fixture_url,resource):
    from .contract import arguments
    from .scenarios import VERSION as FEATURE_VERSION
    arguments('feature.assets.act',dict(contractVersion=FEATURE_VERSION,runId=run,ticket=ticket,
        fixtureUrl=fixture_url,verb='upload',inputs={'resource':resource}))
    primary,paths=BUNDLES[resource]
    rows=[]
    for path in paths:
        name=resource if resource=='asset-stand.fbx' else resource.split('/')[0]+'/'+path
        raw=pinned_resource(name) if resource=='asset-stand.fbx' else companion(name)
        rows.append(dict(relativePath=path,resourceUrl=fixture_url+'tickets/'+ticket+'/'+name,
            bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest()))
    return dict(assetBundleVersion=VERSION,runId=run,ticket=ticket,primaryPath=primary,
        destination='/'+context(run)['name']+'/',files=rows)
