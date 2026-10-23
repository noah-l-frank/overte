"""Prepare original GeometryResource/Resource ownership for the CPU parser join.

This is an additive host fixture. Cache/FST/texture/Baker endpoints remain
explicit; no fallback source binary or synthetic successful geometry is used.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
from test_assets_read_native import ROOT, HERE, original


def prepare_originals(stage, environment, prefix):
    stage=Path(stage);stage.mkdir(parents=True,exist_ok=True)
    provenance={}
    def source(path):
        data=(ROOT/path).read_bytes();provenance[path]=hashlib.sha256(data).hexdigest();return data.decode()
    network=ROOT/'libraries/networking/src'
    for name in ('ResourceRequest.h','ByteRange.h'):
        data=(network/name).read_bytes();(stage/name).write_bytes(data)
        provenance[name]=hashlib.sha256(data).hexdigest()
    request=source('libraries/networking/src/ResourceRequest.cpp')
    (stage/'GeometryResourceRequestOriginals.inc').write_text('\n'.join(original(request,signature) for signature in
        ('QString ResourceRequest::toHttpDateString(', 'void ResourceRequest::send(',
         'QString ResourceRequest::getResultString(', 'void ResourceRequest::recordBytesDownloadedInStats(')))
    spec=importlib.util.spec_from_file_location('geometry_resource_data_prepare',HERE/'assets-resource-data-prepare.py')
    data_prepare=importlib.util.module_from_spec(spec);spec.loader.exec_module(data_prepare)
    arguments=data_prepare.prepare(stage,environment,prefix)
    # Preserve the complete two original class declarations. The host does not
    # replace the Resource base with a lookalike weak receiver in this mode.
    header=source('libraries/model-networking/src/model-networking/ModelCache.h')
    classes=header[header.index('class Geometry {'):header.index('\nclass GeometryResourceWatcher :')]
    material_header=source('libraries/procedural/src/procedural/ProceduralMaterialCache.h')
    material_declaration=material_header[material_header.index('class NetworkMaterialResource : public Resource {'):
        material_header.index('\nusing NetworkMaterialResourcePointer =')]
    (stage/'AssetsGeometryResource.h').write_text('''#pragma once
#include <QSharedPointer>
#include <QJsonDocument>
#include <hfm/HFM.h>
#include "AssetsResource.h"
#include "ModelLoader.h"
class NetworkMaterial;
'''+material_declaration+'''
#include "GeometryParserMaterialMapping.inc"
Q_DECLARE_METATYPE(MaterialMapping)
class MeshPart;
using GeometryMappingPair=std::pair<QUrl,QVariantHash>;
Q_DECLARE_METATYPE(GeometryMappingPair)
'''+classes)
    model=source('libraries/model-networking/src/model-networking/ModelCache.cpp')
    extras=model[model.index('class GeometryExtra {'):model.index('\nclass GeometryReader :')]
    (stage/'GeometryResourceExtrasOriginals.inc').write_text(extras)
    signatures=('QUrl resolveTextureBaseUrl(', 'void GeometryResource::downloadFinished(',
        'void GeometryResource::onGeometryMappingLoaded(', 'void GeometryResource::setExtra(',
        'void GeometryResource::deleter(', 'void GeometryResource::resetTextures(')
    bodies={signature:original(model,signature) for signature in signatures}
    (stage/'GeometryResourceOriginals.inc').write_text('\n'.join(bodies.values()))
    fst=source('libraries/model-serializers/src/FSTReader.h')
    constants='\n'.join(next(line for line in fst.splitlines() if line.startswith('static const QString '+name+' ='))
        for name in ('TEXDIR_FIELD','WAIT_FOR_WEARABLES_FIELD'))
    (stage/'GeometryResourceConstantsOriginals.inc').write_text(constants+'\n')
    for name,body in {'class-declarations':classes,'mapping-extras':extras,
            'original-material-resource-declaration':material_declaration,**bodies}.items():
        provenance[name]=hashlib.sha256(body.encode()).hexdigest()
    (stage/'geometry-resource-original-provenance.json').write_text(json.dumps(provenance,sort_keys=True))
    for name in ('ResourceRequest','AssetsGeometryResource'):
        output=stage/(name+'-moc.cpp')
        subprocess.run([str(prefix/'usr/lib64/qt5/bin/moc'),'-I'+str(stage),str(stage/(name+'.h')),'-o',str(output)],
            check=True,timeout=20,env=environment)
        arguments.append(str(output))
    return arguments


def prepare(stage, environment, prefix):
    spec=importlib.util.spec_from_file_location('geometry_resource_parser_prepare',HERE/'assets-geometry-parser-prepare.py')
    parser_prepare=importlib.util.module_from_spec(spec);spec.loader.exec_module(parser_prepare)
    stage=Path(stage);command=parser_prepare.prepare(stage,environment,prefix)
    arguments=prepare_originals(stage,environment,prefix)
    # Reuse the current already-qualified CPU/reader observation implementation
    # byte-for-byte. Its separate main/weak host receiver are not compiled here.
    parser_source=(HERE/'assets-geometry-parser-native.cpp').read_text()
    core=parser_source[:parser_source.index('\nint main(')]
    include='#include "assets-geometry-parser-host.h"\n'
    if core.count(include)!=1:raise RuntimeError('Review parser core include boundary')
    core=core.replace(include,'',1)
    (stage/'GeometryResourceParserCore.inc').write_text(core)
    provenance=json.loads((stage/'geometry-resource-original-provenance.json').read_text())
    provenance['qualified-parser-core-source']=hashlib.sha256(parser_source.encode()).hexdigest()
    provenance['compiled-parser-core']=hashlib.sha256(core.encode()).hexdigest()
    (stage/'geometry-resource-original-provenance.json').write_text(json.dumps(provenance,sort_keys=True))
    for name in ('DependencyManager.h','ResourceManager.h','PathUtils.h'):
        (stage/name).write_text('#pragma once\n#include "assets-geometry-resource-host.h"\n')
    replaced=[]
    for argument in command:
        if argument==str(stage/'assets-geometry-parser-host-moc.cpp'):continue
        if argument==str(HERE/'assets-geometry-parser-native.cpp'):argument=str(HERE/'assets-geometry-resource-native.cpp')
        if argument==str(HERE/'assets-geometry-parser-host.h'):argument=str(HERE/'assets-geometry-resource-host.h')
        replaced.append(argument)
    return [*replaced,*arguments]
