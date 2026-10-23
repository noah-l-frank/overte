"""Pinned normal Asset Browser input files, never observed upload/bake state."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from feature_journeys.asset_fixture import BUNDLES,bundle
from feature_journeys.fixtures import companion,pinned_resource

PREFIX={'gltf-bundle/main.gltf':'gltf-bundle','obj-bundle/main.obj':'obj-bundle','asset-stand.fbx':'fbx-bundle'}
NAMES=tuple(sorted(prefix+'/'+name for resource,prefix in PREFIX.items() for name in BUNDLES[resource][1]))
DIRECTORIES=tuple(sorted({part.rsplit('/',1)[0] for part in NAMES}|{'gltf-bundle','obj-bundle','fbx-bundle'}))


def documents():
    return {prefix+'/'+name:(pinned_resource(resource) if resource=='asset-stand.fbx' else companion(prefix+'/'+name))
            for resource,prefix in PREFIX.items() for name in BUNDLES[resource][1]}


def manifest(run,ticket,fixture_url,resource):
    return bundle(run,ticket,fixture_url,resource)
