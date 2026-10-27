"""Original next-step ModelCache/GeometryExtra/cache-admission source fragments.

Preparation only: these fragments do not qualify cache startup, LRU policy,
scheduling, Baker output or rendering. No old shared object is consulted.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import json
from pathlib import Path
from test_assets_read_native import ROOT, original


def prepare_fragments(stage):
    stage=Path(stage);stage.mkdir(parents=True,exist_ok=True)
    paths={
        'cache':'libraries/networking/src/ResourceCache.cpp',
        'model':'libraries/model-networking/src/model-networking/ModelCache.cpp',
        'declaration':'libraries/model-networking/src/model-networking/ModelCache.h',
    }
    sources={name:(ROOT/path).read_text() for name,path in paths.items()}
    signatures={
        'original-cache-admission':('cache','QSharedPointer<Resource> ResourceCache::getResource('),
        'original-geometry-factory':('model','QSharedPointer<Resource> ModelCache::createResource('),
        'original-geometry-extra-caller':('model','GeometryResource::Pointer ModelCache::getGeometryResource('),
    }
    fragments={name:original(sources[source],signature) for name,(source,signature) in signatures.items()}
    declaration=sources['declaration']
    fragments['original-model-cache-declaration']=declaration[declaration.index('class ModelCache : public ResourceCache, public Dependency {'):
        declaration.index('\nclass MeshPart {')]
    # Require the original weak lookup/metadata/admission ordering explicitly;
    # no shortened fresh-only path or rewritten setter sequence is substituted.
    admission=fragments['original-cache-admission']
    expected=['resource = createResource(url);','resource->setExtra(extra);','resource->setExtraHash(extraHash);',
        'resource->setSelf(resource);','resource->setCache(this);','resource->moveToThread(qApp->thread());',
        'resource->ensureLoading();']
    fresh=admission[admission.index('if (!resource) {\n        resource = createResource(url);'):]
    positions=[fresh.index(value) for value in expected]
    if positions!=sorted(positions):raise RuntimeError('Review current normal cache admission ordering')
    caller=fragments['original-geometry-extra-caller']
    if 'GeometryExtra geometryExtra = { mapping, textureBaseUrl, combineParts };' not in caller:
        raise RuntimeError('Review current normal ModelCache extra construction')
    for name,body in fragments.items():(stage/(name+'.inc')).write_text(body+'\n')
    provenance={paths[name]:hashlib.sha256(source.encode()).hexdigest() for name,source in sources.items()}
    provenance.update({name:hashlib.sha256(body.encode()).hexdigest() for name,body in fragments.items()})
    (stage/'model-cache-admission-original-provenance.json').write_text(json.dumps(provenance,sort_keys=True))
    return fragments
