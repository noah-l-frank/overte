"""Original ModelCache extra admission and weak-cache ownership before Baker.

Cache startup/scheduling, alternate-extra copies, unused LRU and successful
textures remain explicit host endpoints; all executed acquisition/removal bodies
are complete current originals. No previous source binary is linked.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
from test_assets_read_native import ROOT, HERE, original


def prepare(stage, environment, prefix):
    spec=importlib.util.spec_from_file_location('model_cache_geometry_prepare',HERE/'assets-geometry-resource-prepare.py')
    geometry=importlib.util.module_from_spec(spec);spec.loader.exec_module(geometry)
    stage=Path(stage);command=geometry.prepare(stage,environment,prefix)
    model=(ROOT/'libraries/model-networking/src/model-networking/ModelCache.cpp').read_text()
    resource=(ROOT/'libraries/networking/src/ResourceCache.cpp').read_text()
    signatures=('QSharedPointer<Resource> ResourceCache::getResource(',
        'void ResourceCache::removeUnusedResource(', 'void ResourceCache::removeResource(',
        'void ResourceCache::resetTotalResourceCounter(', 'void ResourceCache::updateTotalSize(')
    blocks={signature:original(resource,signature) for signature in signatures}
    for signature in ('QSharedPointer<Resource> ModelCache::createResource(',
            'GeometryResource::Pointer ModelCache::getGeometryResource('):
        blocks[signature]=original(model,signature)
    extras=model[model.index('class GeometryExtra {'):model.index('\nclass GeometryReader :')]
    header=(ROOT/'libraries/networking/src/ResourceCache.h').read_text()
    constants='\n'.join(next(line for line in header.splitlines() if line.startswith('static const qint64 '+name+' ='))
        for name in ('BYTES_PER_MEGABYTES','BYTES_PER_GIGABYTES'))
    (stage/'GeometryModelCacheOriginals.inc').write_text(constants+'\n'+extras+'\n'+'\n'.join(blocks.values()))
    provenance={signature:hashlib.sha256(body.encode()).hexdigest() for signature,body in blocks.items()}
    provenance['original-cache-size-constants']=hashlib.sha256(constants.encode()).hexdigest()
    provenance['original-extra-and-hash-declarations']=hashlib.sha256(extras.encode()).hexdigest()
    provenance['original-registered-type-hash-helpers']=hashlib.sha256((ROOT/'libraries/shared/src/RegisteredMetaTypes.h').read_bytes()).hexdigest()
    provenance['compiled-model-cache-originals']=hashlib.sha256((stage/'GeometryModelCacheOriginals.inc').read_bytes()).hexdigest()
    (stage/'model-cache-original-provenance.json').write_text(json.dumps(provenance,sort_keys=True))
    moc=stage/'assets-model-cache-moc.cpp'
    subprocess.run([str(prefix/'usr/lib64/qt5/bin/moc'),'-DASSETS_ORIGINAL_MODEL_CACHE',
        '-I'+str(stage),str(HERE/'assets-resource-cache-host.h'),'-o',str(moc)],
        check=True,timeout=20,env=environment)
    return [*command,'-DASSETS_ORIGINAL_MODEL_CACHE',str(moc)]
