"""Existing Avatar parent/UI build joined to original Assets model resources.

No prebuilt object, alternate test runner, Model-ready flag or source URL rewrite
is admitted. Constructor/Rig/scene/render services remain declared host seams.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
from test_assets_read_native import ROOT,HERE,original


def prepare(stage,environment,prefix):
    spec=importlib.util.spec_from_file_location('avatar_assets_model_material',HERE/'assets-model-material-prepare.py')
    material=importlib.util.module_from_spec(spec);spec.loader.exec_module(material)
    command=material.prepare(stage,environment,prefix);stage=Path(stage)
    sources={}
    def read(path):
        raw=(ROOT/path).read_bytes();sources[path]=hashlib.sha256(raw).hexdigest();return raw.decode()
    def write(name,value):
        path=stage/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(value);return path
    cache=read('libraries/model-networking/src/model-networking/ModelCache.cpp')
    header=read('libraries/model-networking/src/model-networking/ModelCache.h')
    watcher=header[header.index('class GeometryResourceWatcher :'):header.index('\nclass MeshPart {')]
    # Includes the complete original watcher and actual ModelCache declaration,
    # constructor, formats and copy factory rather than the old glTF endpoint.
    host=read('android/vr/pico/tests/device/assets-model-material-host.h')
    start=host.index('class ModelCache:');end=host.index('\nstruct AssetsRecordedInput',start)
    comment=host.index('// Existing model-format startup')
    host=host[:comment]+'#include <FSTReader.h>\n'+watcher+host[end:]
    host=host[:host.index('\nstruct AssetsRecordedInput')]
    host=host.replace('public:DomainHandler& getDomainHandler()',
        'public:bool isIgnoringNode(const QUuid&){qFatal("Other Avatars are outside this primary loader join");return true;}\n DomainHandler& getDomainHandler()')
    write('AvatarOriginalModelResource.h',host)
    methods=('void GeometryResourceWatcher::startWatching(', 'void GeometryResourceWatcher::stopWatching(',
        'void GeometryResourceWatcher::setResource(', 'void GeometryResourceWatcher::resourceFinished(',
        'void GeometryResourceWatcher::resourceRefreshed(', 'Geometry::Geometry(',
        'ModelCache::ModelCache(', 'QSharedPointer<Resource> ModelCache::createResourceCopy(',
        'GeometryResource::GeometryResource(', 'void Geometry::setTextures(')
    write('AvatarOriginalGeometryWatcher.inc','\n'.join(original(cache,signature) for signature in methods))
    model_header=read('libraries/render-utils/src/Model.h')
    getters=('    const QUrl& getURL()', '    bool isLoaded()', '    const Geometry::Pointer& getGeometry()',
        '    QString e2eModelInstance()', '    QVariantMap e2eModelLoads()')
    write('AvatarOriginalModelGetters.inc','\n'.join(original(model_header,signature) for signature in getters))
    model=read('libraries/render-utils/src/Model.cpp')
    write('AvatarOriginalModelBodies.inc','\n'.join(original(model,signature) for signature in
        ('void Model::setURL(', 'void Model::loadURLFinished(', 'void Model::deleteGeometry(', 'void Model::setTextures(')))
    avatar=read('libraries/avatars-renderer/src/avatars-renderer/Avatar.cpp')
    write('AvatarOriginalBaseBodies.inc','\n'.join(original(avatar,signature) for signature in
        ('void Avatar::setSkeletonModelURL(', 'void Avatar::setModelURLFinished(')))
    # Full original FST/FBX/OBJ implementations and their actual registry types.
    serializer_paths=['libraries/model-serializers/src/FSTReader.cpp','libraries/model-serializers/src/FBXSerializer.cpp',
        'libraries/model-serializers/src/FBXSerializer_Node.cpp','libraries/model-serializers/src/FBXSerializer_Mesh.cpp',
        'libraries/model-serializers/src/FBXSerializer_Material.cpp','libraries/model-serializers/src/OBJSerializer.cpp']
    for path in serializer_paths:read(path)
    read('libraries/model-serializers/src/FSTReader.h');read('libraries/model-serializers/src/FBXSerializer.h')
    # Namespace/header changes apply solely to generated host endpoints.
    for path in stage.rglob('*'):
        if path.is_file() and path.suffix in ('.h','.cpp','.inc'):
            text=path.read_text();changed=text.replace('"assets-model-material-host.h"','"AvatarOriginalModelResource.h"')
            if changed!=text:path.write_text(changed)
    # Reuse original parser/GeometryResource bodies without the one-resource
    # observer's main, single-birth assumptions or huge vertex-array reports.
    core=(stage/'GeometryResourceParserCore.inc').read_text()
    a=core.index('static QJsonObject parsedHandoff;');b=core.index('#include "GeometryParserMaterialMapping.inc"',a)
    loader=read('libraries/model-networking/src/model-networking/ModelLoader.cpp')
    core=core[:a]+original(loader,'hfm::Model::Pointer ModelLoader::load(')+ '\n'+core[b:]
    core=core.replace('#include "AssetsOriginalBakerJoin.inc"','#include "AvatarOriginalBakerJoin.inc"')
    core=core[:core.index('\nstruct WorkerEvidence')]
    core=core.replace('static const QString SCRIPT_FIELD="script";','')
    write('AvatarOriginalParserCore.inc',core)
    # The full original Baker graph runs for every original resource. Its old
    # isolated observation wrapper required one empty graph and is not reused
    # as a fake parser/result endpoint for the Avatar's multiple resources.
    write('AvatarOriginalBakerJoin.inc','''#define Baker OriginalSourceBaker
#include "model-baker/Baker.h"
#include "AssetsOriginalBakerBody.inc"
#undef Baker
namespace baker {using Baker=OriginalSourceBaker;}
''')
    write('AvatarOriginalModelCore.cpp','''#include "AvatarOriginalModelResource.h"
#include <FBXSerializer.h>
#include <OBJSerializer.h>
#include <GLTFSerializer.h>
#include <Finally.h>
#include <QThreadPool>
#include "AvatarOriginalParserCore.inc"
#include "GeometryModelCacheOriginals.inc"
#include "GeometryResourceOriginals.inc"
#include "AvatarOriginalGeometryWatcher.inc"
''')
    # New endpoint is explicit: exact registered qrc originals remain original
    # FileResourceRequests; only the closed fixture HTTP byte service is a seam.
    manager=stage/'CreateTextureResourceManager.cpp';text=manager.read_text()
    text=text.replace('ResourceRequest* assetsRecordedRequest(', 'ResourceRequest* avatarOriginalRecordedRequest(')
    text=text.replace(' if(url.scheme()=="atp"){return assetsRecordedRequest(parent,url,observable,caller,extra); }',
        ' if(url.scheme()=="http" || url.scheme()=="https"){return avatarOriginalRecordedRequest(parent,url,observable,caller,extra); }')
    # OBJ is registered by the actual constructor, but its separate optional
    # URL existence service is outside this exact FST/FBX input. Refuse any
    # execution instead of inventing existence or fetching remote resources.
    text+='\nbool ResourceManager::resourceExists(const QUrl&){qFatal("OBJ URL-existence service is outside this original FST/FBX join");return false;}\n'
    manager.write_text(text)
    # Asset model methods that were not called in its old ownership scope now
    # use the actual original Geometry copy constructor and watcher metaobject.
    moc=stage/'AvatarOriginalModelResource-moc.cpp'
    subprocess.run([str(prefix/'usr/lib64/qt5/bin/moc'),'-DOVERTE_E2E_FEATURE_TESTS','-DANDROID_APP_PICO_INTERFACE',
        '-I'+str(stage),'-I'+str(HERE),str(stage/'AvatarOriginalModelResource.h'),'-o',str(moc)],check=True,timeout=20,env=environment)
    omitted={'assets-geometry-resource-native.cpp','assets-model-material-host-moc.cpp'}
    result=[value for value in command if Path(value).name not in omitted]
    result += [str(ROOT/path) for path in serializer_paths]
    # Original model-serializers/CMakeLists.txt requires target_draco(). Reuse
    # the already present host package; no installation or decoder substitute.
    read('libraries/model-serializers/CMakeLists.txt');read('cmake/macros/TargetDraco.cmake')
    supplied_draco=environment.get('OVERTE_TEST_DRACO_ROOT')
    if supplied_draco:draco=Path(supplied_draco).resolve(strict=True)
    else:
        packages=Path(environment['OVERTE_TEST_GLM_INCLUDE']).resolve(strict=True).parents[2]
        choices=sorted(packages.glob('draco*/p/lib/libdraco.a'))
        if len(choices)!=1:raise ValueError('Select one existing host Draco package with OVERTE_TEST_DRACO_ROOT')
        draco=choices[0].parents[1]
    if not (draco/'include/draco/compression/decode.h').is_file():raise ValueError('Existing host Draco headers missing')
    for dependency in sorted(draco.rglob('*')):
        if dependency.is_file():sources['dependency-draco/'+str(dependency.relative_to(draco))]=hashlib.sha256(dependency.read_bytes()).hexdigest()
    result += ['-isystem',str(draco/'include'),str(draco/'lib/libdraco.a')]
    result += [str(stage/'AvatarOriginalModelCore.cpp'),str(moc),'-DAVATAR_ORIGINAL_MODEL_LOADER']
    obj_moc=stage/'AvatarOriginalObjSerializer-moc.cpp'
    subprocess.run([str(prefix/'usr/lib64/qt5/bin/moc'),'-I'+str(stage),str(ROOT/'libraries/model-serializers/src/OBJSerializer.h'),'-o',str(obj_moc)],check=True,timeout=20,env=environment)
    result.append(str(obj_moc))
    # Register exact existing default FST/FBX/PNG bytes at their actual qrc
    # aliases. No compressed variants, content or model success is invented.
    from xml.sax.saxutils import escape
    import sys
    sys.path.insert(0,str(ROOT/'tests/device'))
    from feature_journeys.fixtures import pinned_resource
    pins=json.loads((ROOT/'tests/device/feature_journeys/resource-pins.v1.json').read_text())['resources']
    names=['avatar-a.fst','mannequin/mannequin.fbx']+[name for name in pins if name.startswith('mannequin/') and name.endswith('.png')]
    qrc_entries=[]
    for name in names:
        pinned_resource(name);source=pins[name]['source'];sources[source]=hashlib.sha256((ROOT/source).read_bytes()).hexdigest()
        alias='meshes/'+('defaultAvatar_full.fst' if name=='avatar-a.fst' else name)
        qrc_entries.append('<file alias="'+escape(alias)+'">'+escape(str(ROOT/source))+'</file>')
    qrc=write('AvatarOriginalModelInputs.qrc','<RCC><qresource prefix="/">'+''.join(qrc_entries)+'</qresource></RCC>\n')
    compiled_qrc=stage/'AvatarOriginalModelInputs-rcc.cpp'
    subprocess.run([str(prefix/'usr/lib64/qt5/bin/rcc'),'-name','avatar_original_model_inputs',str(qrc),'-o',str(compiled_qrc)],check=True,timeout=20,env=environment)
    result.append(str(compiled_qrc))
    # Preserve the complete actual input set; no historical delegate provenance
    # is represented as the changed compilation's manifest.
    for path in stage.rglob('*'):
        if path.is_file() and path.suffix in ('.h','.cpp','.inc'):
            sources['staged-'+str(path.relative_to(stage))]=hashlib.sha256(path.read_bytes()).hexdigest()
    write('avatar-model-original-provenance.json',json.dumps(dict(avatarOriginalModelLoaderVersion=1,
        composition='original-avatar-model-loader',dependencies=['bfe59118d61f4fd41120ef246d6e5b6e28003a1f',
            '744a51ee2b64f25665a940b445d5e5e433a5053d'],sources=sources),sort_keys=True))
    return result
