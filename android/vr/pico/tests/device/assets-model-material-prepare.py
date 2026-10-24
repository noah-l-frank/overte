"""Extend the existing original ModelCache/Baker selector through PBR textures.

The same prior Assets byte-service endpoint remains explicit. ResourceCache,
shared services, NetworkMaterial and decoder/storage ownership are originals;
cache retention, a parentless glTF request and absent Model/render owners are
observed boundaries, never replaced by cache clearing or synthetic readiness.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import importlib.util
import json
import shlex
from pathlib import Path
import subprocess
from test_assets_read_native import ROOT,HERE,original


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,HERE/path)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result


def prepare(stage,environment,prefix):
    stage=Path(stage)
    command=module('assets_material_baker','assets-model-baker-prepare.py').prepare(stage,environment,prefix)
    # The native caller includes its own explicit host header. Full original
    # TUs must retain their real independent header/namespace boundaries; the
    # inherited parser's global host include would inject a competing global
    # network Texture declaration into original gpu::Texture definitions.
    host_header=str(HERE/'assets-geometry-resource-host.h')
    if command.count(host_header)!=1:
        raise ValueError('Review original native caller include boundary')
    at=command.index(host_header)
    if at<1 or command[at-1]!='-include':
        raise ValueError('The legacy host header no longer has one force-include boundary')
    command=command[:at-1]+command[at+1:]
    manifest={}
    def read(path):
        data=(ROOT/path).read_bytes();manifest[path]=hashlib.sha256(data).hexdigest();return data.decode()
    def write(name,text):
        path=stage/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
    # One Resource/DependencyManager declaration universe supplies both the
    # old model callers and the newly connected original TextureCache.
    read('libraries/shared/src/DependencyManager.cpp')
    write('DependencyManager.h',read('libraries/shared/src/DependencyManager.h'))
    write('Profile.h','#pragma once\n#include "'+str(ROOT/'libraries/shared/src/Profile.h')+'"\n')
    write('procedural/ProceduralMaterialCache.h',read('libraries/procedural/src/procedural/ProceduralMaterialCache.h'))
    compiler=read('cmake/compiler.cmake')
    if compiler.count('set(CMAKE_CXX_STANDARD 20)')!=1 or 'set(CMAKE_CXX_STANDARD_REQUIRED ON)' not in compiler:
        raise ValueError('Original required C++ standard changed; review the host translation')
    cache=read('libraries/model-networking/src/model-networking/ModelCache.cpp')
    cache_header=read('libraries/model-networking/src/model-networking/ModelCache.h')
    classes=cache_header[cache_header.index('class Geometry {'):cache_header.index('\nclass GeometryResourceWatcher :')]
    part=cache_header[cache_header.index('class MeshPart {'):cache_header.rindex('\n#endif')]
    write('AssetsGeometryResource.h','''#pragma once
#include <ResourceCache.h>
#include <hfm/HFM.h>
#include <procedural/ProceduralMaterialCache.h>
#include "ModelLoader.h"
#include <QUuid>
class MeshPart;
using GeometryMappingPair=std::pair<QUrl,QVariantHash>;
Q_DECLARE_METATYPE(GeometryMappingPair)
'''+classes+'\n'+part)
    write('GeometryParserMaterialMapping.inc','#include <procedural/ProceduralMaterialCache.h>\n')
    extras=cache[cache.index('class GeometryExtra {'):cache.index('\nclass GeometryReader :')]
    write('GeometryModelCacheOriginals.inc',extras+'\n'+'\n'.join(original(cache,signature) for signature in
        ('QSharedPointer<Resource> ModelCache::createResource(', 'GeometryResource::Pointer ModelCache::getGeometryResource(')))
    resource_methods=('QUrl resolveTextureBaseUrl(', 'void GeometryResource::downloadFinished(',
        'void GeometryResource::onGeometryMappingLoaded(', 'void GeometryResource::setExtra(',
        'void GeometryResource::deleter(', 'void GeometryResource::resetTextures(',
        'void GeometryResource::setGeometryDefinition(', 'void GeometryResource::setTextures(',
        'bool Geometry::areTexturesLoaded(')
    write('GeometryResourceOriginals.inc','\n'.join(original(cache,signature) for signature in resource_methods))
    # Preserve whole original PBR/MToon declarations and all their complete
    # method bodies. JSON/procedural/reference-material services remain outside
    # this non-MToon glTF input and are not supplied by another material getter.
    material=read('libraries/procedural/src/procedural/ProceduralMaterialCache.cpp')
    material_tail=material[material.index('NetworkMaterial::NetworkMaterial(const NetworkMaterial&'):]
    write('AssetsOriginalNetworkMaterials.cpp','#include <procedural/ProceduralMaterialCache.h>\n'+material_tail)
    hfm=read('libraries/hfm/src/hfm/HFM.cpp')
    palette=hfm[hfm.index('namespace {'):hfm.index('\nvoid HFMMaterial::getTextureNames(')]
    write('GeometryParserCpuOriginals.inc',palette)
    # Full GLM/Material/Profile implementations replace only their former
    # selected fragments/publication endpoint; no original function is omitted.
    cpu=stage/'AssetsOriginalBakerCpu.cpp';text=cpu.read_text()
    for line in ('#include "AssetsOriginalBakerVectors.inc"','#include "AssetsBakerProfileHost.inc"',
            '#include "'+str(ROOT/'libraries/shared/src/shared/JSONHelpers.cpp')+'"',
            '#include "'+str(ROOT/'libraries/shared/src/shared/QtHelpers.cpp')+'"'):
        text=text.replace(line+'\n','')
    # The unity's original CPU GPU units import gpu names globally. Parse
    # their later actual material/resource dependency first, in its normal
    # global declaration context, without injecting it into unrelated GPU TUs.
    cpu.write_text('#include <procedural/ProceduralMaterialCache.h>\n'+text)
    material_task=read('libraries/model-baker/src/model-baker/ParseMaterialMappingTask.cpp')
    json_include=next(line for line in material_task.splitlines() if line=='#include <QJsonArray>')
    closed=stage/'AssetsOriginalBakerClosedBranches.inc'
    closed.write_text(json_include+'\n'+closed.read_text())
    prefix_source=(stage/'GeometryResourceParserCore.inc').read_text()
    prefix_source=prefix_source.replace('bool graphics::Material::resetOpacityMap()const {qFatal("GPU opacity is outside CPU parser qualification");return false;}','')
    prefix_source=prefix_source.replace('bool gunzip(const QByteArray&,QByteArray&){qFatal("Compressed models are outside this parser join");return false;}','')
    prefix_source=prefix_source.replace('#if defined(ASSETS_ORIGINAL_MODEL_BAKER)\n#undef PROFILE_RANGE_EX\n#endif\n#define PROFILE_RANGE_EX(...)\n','')
    category=next(line for line in cache.splitlines() if line.startswith('Q_LOGGING_CATEGORY(trace_resource_parse_geometry,'))
    read('libraries/shared/src/Gzip.h')
    manifest['original-geometry-profile-category']=hashlib.sha256(category.encode()).hexdigest()
    write('GeometryResourceParserCore.inc','#include <Gzip.h>\n'+category+'\n'+prefix_source)
    textures=module('assets_material_textures','create-voxel-texture-prepare.py').prepare(stage,environment,prefix,
        node_list_header='assets-model-material-host.h',request_observer='observeAssetsMaterialRequest',
        recorded_atp_factory='assetsRecordedRequest',include_qrc_inputs=False)
    write('NetworkAccessManager.h','''#pragma once
#include <QNetworkAccessManager>
class NetworkAccessManager {public:static QNetworkAccessManager& getInstance(){
 qFatal("HTTP remains outside the recorded original Assets input scope");static QNetworkAccessManager value;return value;}};
''')
    support=[]
    for path in ('libraries/shared/src/DependencyManager.cpp','libraries/shared/src/Extents.cpp',
            'libraries/shared/src/Transform.cpp','libraries/graphics/src/graphics/Material.cpp',
            'libraries/graphics/src/graphics/TextureMap.cpp','libraries/graphics/src/graphics/GraphicsLogging.cpp'):
        read(path);support.append(str(ROOT/path))
    moc=stage/'assets-model-material-host-moc.cpp'
    subprocess.run([str(prefix/'usr/lib64/qt5/bin/moc'),'-DOVERTE_E2E_FEATURE_TESTS','-DANDROID_APP_PICO_INTERFACE',
        '-I'+str(stage),'-I'+str(HERE),str(HERE/'assets-model-material-host.h'),'-o',str(moc)],check=True,timeout=20,env=environment)
    # Regenerate the original GeometryResource metaobject after its exact class
    # declaration has been rebound to the single original Resource declaration.
    geometry_moc=stage/'AssetsGeometryResource-moc.cpp'
    subprocess.run([str(prefix/'usr/lib64/qt5/bin/moc'),'-DOVERTE_E2E_FEATURE_TESTS','-DANDROID_APP_PICO_INTERFACE',
        '-I'+str(stage),str(stage/'AssetsGeometryResource.h'),'-o',str(geometry_moc)],check=True,timeout=20,env=environment)
    procedural_moc=stage/'assets-model-material-procedural-moc.cpp'
    subprocess.run([str(prefix/'usr/lib64/qt5/bin/moc'),'-DOVERTE_E2E_FEATURE_TESTS','-DANDROID_APP_PICO_INTERFACE',
        '-I'+str(stage),str(stage/'procedural/ProceduralMaterialCache.h'),'-o',str(procedural_moc)],check=True,timeout=20,env=environment)
    obsolete={'ResourceRequest-moc.cpp','AssetsResource-moc.cpp','AssetsResourceObserver-moc.cpp',
        'assets-model-cache-moc.cpp','assets-geometry-parser-host-moc.cpp'}
    result=[]
    for value in command:
        if Path(value).name in obsolete:continue
        result.append('-std=c++20' if value=='-std=c++17' else value)
    qt_concurrent=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt5Concurrent'],text=True,env=environment))
    result += ['-DASSETS_ORIGINAL_MODEL_MATERIAL','-DOVERTE_E2E_FEATURE_TESTS','-DANDROID_APP_PICO_INTERFACE',
        '-I'+str(ROOT/'libraries/procedural/src'),str(stage/'AssetsOriginalNetworkMaterials.cpp'),str(moc),str(procedural_moc),*support,*textures,*qt_concurrent]
    for path in stage.rglob('*'):
        if path.is_file() and path.suffix in ('.h','.cpp','.inc'):
            manifest['staged-'+str(path.relative_to(stage))]=hashlib.sha256(path.read_bytes()).hexdigest()
    for filename in ('geometry-parser-original-provenance.json','geometry-resource-original-provenance.json',
            'model-cache-original-provenance.json','model-baker-original-provenance.json','create-texture-original-provenance.json'):
        data=json.loads((stage/filename).read_text())
        for key in list(data):
            if key.startswith('compiled-') and (stage/key.removeprefix('compiled-')).is_file():
                data[key]=hashlib.sha256((stage/key.removeprefix('compiled-')).read_bytes()).hexdigest()
        for key,name in (('compiled-parser-core','GeometryResourceParserCore.inc'),
                ('compiled-model-cache-originals','GeometryModelCacheOriginals.inc')):
            if key in data:data[key]=hashlib.sha256((stage/name).read_bytes()).hexdigest()
        data['composition']='original-model-material-texture';write(filename,json.dumps(data,sort_keys=True))
    write('model-material-original-provenance.json',json.dumps(manifest,sort_keys=True))
    return result
