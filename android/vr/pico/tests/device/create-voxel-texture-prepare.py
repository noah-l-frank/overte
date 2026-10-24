"""Original qrc TextureCache/NetworkTexture/image units for the normal Add join.

No dependency installation or GPU context is performed here. All selected
repository units and existing external package inputs are stamped. Network
schemes other than the original local qrc/file path are closed host endpoints.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import importlib.util
import json
import re
from pathlib import Path
import subprocess
from xml.sax.saxutils import escape
from test_assets_read_native import ROOT,HERE,original


def prepare(stage,environment,prefix):
    stage=Path(stage);manifest={}
    def read(path):
        data=(ROOT/path).read_bytes();manifest[path]=hashlib.sha256(data).hexdigest();return data
    def copy(path,target=None):
        destination=stage/(target or Path(path).name);destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_bytes(read(path));return destination
    def write(path,value):
        destination=stage/path;destination.parent.mkdir(parents=True,exist_ok=True);destination.write_text(value);return destination
    def package(env_name,pattern,leaf):
        supplied=environment.get(env_name)
        if supplied:
            folder=Path(supplied).resolve(strict=True)
            if not (folder/leaf).is_file():raise ValueError('Existing texture dependency has no required input: '+env_name)
        else:
            packages=Path(environment['OVERTE_TEST_GLM_INCLUDE']).resolve(strict=True).parents[2]
            choices=sorted(packages.glob(pattern+'/p/'+leaf))
            if len(choices)!=1:raise ValueError('Select one already installed texture dependency with '+env_name)
            folder=choices[0]
            for _part in Path(leaf).parts:folder=folder.parent
        return folder
    nvtt=package('OVERTE_TEST_NVTT_ROOT','nvidi*','include/nvtt/nvtt.h')
    etc=package('OVERTE_TEST_ETC_ROOT','etc2*','include/Etc.h')
    openexr=package('OVERTE_TEST_OPENEXR_ROOT','opene*','include/OpenEXR/ImfIO.h')
    imath=package('OVERTE_TEST_IMATH_ROOT','imath*','include/Imath/ImathVec.h')
    tbb=package('OVERTE_TEST_TBB_ROOT','onetb*','include/tbb/concurrent_queue.h')
    libraries=[]
    for name,folder in (('nvtt',nvtt),('squish',nvtt),('EtcLib',etc),
            ('OpenEXR-3_1',openexr),('Iex-3_1',openexr),('IlmThread-3_1',openexr),('Imath-3_1',imath)):
        library=folder/'lib'/('lib'+name+'.a')
        if not library.is_file():raise ValueError('The existing texture dependency is not a native static library: '+name)
        manifest['external-library-'+name]=hashlib.sha256(library.read_bytes()).hexdigest();libraries.append(str(library))
    tbb_libraries=sorted({path.resolve(strict=True) for path in (tbb/'lib').glob('libtbb.so.*')})
    if len(tbb_libraries)!=1:raise ValueError('Expected one existing versioned TBB runtime')
    manifest['external-library-tbb']=hashlib.sha256(tbb_libraries[0].read_bytes()).hexdigest()
    libraries += [str(tbb_libraries[0]),'-Wl,-rpath,'+str(tbb/'lib'),'-lz']
    for folder in (nvtt,etc,openexr,imath,tbb):
        for path in sorted((folder/'include').rglob('*')):
            if path.is_file():manifest['external-header-'+str(path)]=hashlib.sha256(path.read_bytes()).hexdigest()

    cmake=read('CMakeLists.txt').decode()
    # Both reviewed product rendering-backend branches select this exact
    # original storage scheme. No backend/context is instantiated by the join.
    if cmake.count('    add_definitions(-DGPU_POINTER_STORAGE_RAW)')!=2:
        raise ValueError('Current original GPU pointer-storage configuration changed')
    read('libraries/gpu/src/gpu/PointerStorage.h')
    # These are the normal shared/ktx source globs and link dependency, not
    # an invented linkage profile for missing implementations.
    read('libraries/shared/CMakeLists.txt');read('libraries/ktx/CMakeLists.txt')
    read('cmake/macros/SetupHifiLibrary.cmake')

    # Preserve complete public declarations. The observer header has no original
    # inclusion guard; the staging guard preserves all original bytes behind it.
    for path in ('libraries/networking/src/ResourceCache.h','libraries/networking/src/ResourceManager.h',
            'libraries/networking/src/ResourceRequest.h','libraries/networking/src/FileResourceRequest.h',
            'libraries/networking/src/ByteRange.h','libraries/shared/src/PathUtils.h'):
        copy(path)
    observer=read('libraries/shared/src/ResourceRequestObserver.h')
    write('ResourceRequestObserver.h','#pragma once\n'+observer.decode())
    manifest['compiled-single-inclusion-ResourceRequestObserver.h']=hashlib.sha256((stage/'ResourceRequestObserver.h').read_bytes()).hexdigest()
    write('NodeList.h','#pragma once\n#include <NetworkingConstants.h>\n#include "create-voxel-native-join.h"\n')
    write('NetworkAccessManager.h','// Unused include in the selected complete ResourceCache source.\n')
    write('gl/GLHelpers.h','// No GL entrypoint is used by the selected original CPU TextureCache bodies.\n')

    # Reuse the existing exact URL/factory extractor, without its ATP endpoint
    # actors or alternate Resource implementation.
    spec=importlib.util.spec_from_file_location('create_original_resource_manager',HERE/'assets-resource-manager-prepare.py')
    manager=importlib.util.module_from_spec(spec);spec.loader.exec_module(manager)
    manager.prepare(stage,resource_data=True)
    header=(stage/'ResourceManager.h').read_text()
    start=header.index('    ResourceRequest* createResourceRequest(')
    end=header.index(';',start)+1
    declaration=header[start:end]
    write('ResourceManager.h',header[:end]+'\n'+declaration.replace('createResourceRequest(', 'createOriginalResourceRequest(',1)+header[end:])
    constants=read('libraries/networking/src/NetworkingConstants.h').decode()
    atp=next(line for line in constants.splitlines() if line.startswith('const QString URL_SCHEME_ATP ='))
    factory=stage/'AssetsResourceManagerOriginals.inc'
    factory.write_text(atp+'\n'+factory.read_text())
    source=read('libraries/networking/src/ResourceManager.cpp').decode()
    methods='\n'.join(original(source,signature) for signature in
        ('ResourceManager::ResourceManager(', 'ResourceManager::~ResourceManager('))
    write('CreateTextureResourceManager.cpp','''#include "ResourceManager.h"
#include <QCoreApplication>
#include <QThread>
#include <SharedUtil.h>
#include <NetworkLogging.h>
#include "FileResourceRequest.h"
class AssetClient:public QObject,public Dependency {
public:AssetClient(){qFatal("ATP startup is outside the owned qrc fixture");}
 void initCaching(){qFatal("ATP startup is outside the owned qrc fixture");}
};
class HTTPResourceRequest:public ResourceRequest {
public:using ResourceRequest::ResourceRequest;
protected:void doSend()override{qFatal("Remote texture requests are outside the owned qrc fixture");}
};
class AssetResourceRequest:public ResourceRequest {
public:using ResourceRequest::ResourceRequest;
protected:void doSend()override{qFatal("ATP texture requests are outside the owned qrc fixture");}
};
#include <ThreadHelpers.h>
'''+methods+'\n#include "AssetsResourceManagerOriginals.inc"\n'+'''
void observeCreateTextureRequest(ResourceRequest*,QObject*,const QUrl&);
ResourceRequest* ResourceManager::createResourceRequest(QObject* parent,const QUrl& url,const bool observable,const qint64 caller,const QString& extra){
 auto request=createOriginalResourceRequest(parent,url,observable,caller,extra);
 observeCreateTextureRequest(request,parent,url);return request;
}
''')

    # These original shared implementations use only newly private data/config
    # roots. No application settings, pre-existing cache or cleanup is adopted.
    units=[]
    for path in ('libraries/networking/src/ResourceCache.cpp','libraries/networking/src/ResourceRequest.cpp',
            'libraries/networking/src/FileResourceRequest.cpp','libraries/networking/src/NetworkLogging.cpp',
            'libraries/shared/src/ResourceRequestObserver.cpp','libraries/shared/src/StatTracker.cpp'):
        units.append(str(copy(path)))
    units.append(str(stage/'CreateTextureResourceManager.cpp'))
    for path in ('libraries/material-networking/src/material-networking/TextureCache.cpp',
            'libraries/material-networking/src/material-networking/KTXCache.cpp',
            'libraries/material-networking/src/material-networking/MaterialNetworkingLogging.cpp',
            'libraries/shared/src/shared/FileCache.cpp','libraries/shared/src/shared/FileUtils.cpp',
            'libraries/shared/src/shared/Storage.cpp','libraries/shared/src/shared/GlobalAppProperties.cpp',
            'libraries/shared/src/PathUtils.cpp','libraries/shared/src/SettingInterface.cpp',
            'libraries/shared/src/SettingHandle.cpp','libraries/shared/src/SettingManager.cpp',
            'libraries/shared/src/SettingHelpers.cpp','libraries/shared/src/SharedLogging.cpp',
            'libraries/shared/src/shared/JSONHelpers.cpp','libraries/shared/src/shared/QtHelpers.cpp',
            'libraries/shared/src/ColorUtils.cpp','libraries/shared/src/BRDF.cpp',
            'libraries/shared/src/SharedUtil.cpp','libraries/shared/src/GLMHelpers.cpp','libraries/shared/src/SerDes.cpp',
            'libraries/shared/src/Profile.cpp','libraries/shared/src/Trace.cpp','libraries/shared/src/Gzip.cpp','libraries/shared/src/ThreadHelpers.cpp',
            'libraries/image/src/image/Image.cpp','libraries/image/src/image/TextureProcessing.cpp',
            'libraries/image/src/image/ImageLogging.cpp','libraries/image/src/image/TGAReader.cpp',
            'libraries/image/src/image/OpenEXRReader.cpp','libraries/image/src/image/CubeMap.cpp',
            'libraries/gpu/src/gpu/Texture.cpp',
            'libraries/gpu/src/gpu/Texture_ktx.cpp','libraries/gpu/src/gpu/Framebuffer.cpp','libraries/gpu/src/gpu/GPULogging.cpp',
            'libraries/ktx/src/ktx/KTX.cpp','libraries/ktx/src/ktx/Reader.cpp',
            'libraries/ktx/src/ktx/Writer.cpp','libraries/ktx/src/ktx/Validation.cpp','libraries/ktx/src/TextureMeta.cpp'):
        read(path);units.append(str(ROOT/path))

    # Generate the original build-info template with explicit private-host
    # metadata. Trace/Profile implementations are complete originals; no Tracer
    # is installed and this fixture does not use tracing as its actual clocks.
    template=read('cmake/templates/BuildInfo.h.in').decode()
    build_info=re.sub(r'@[A-Z_]+@',lambda match:'0' if match[0]=='@USE_STABLE_GLOBAL_SERVICES@' else 'private-create-host',template)
    write('BuildInfo.h','#pragma once\n'+build_info)
    # No shader program or graphics backend is created by the CPU join. The
    # original enum template has an empty owned shader set, not invented IDs.
    enums=read('libraries/shaders/ShaderEnums.h.in').decode()
    write('ShaderEnums.h','#pragma once\n'+enums.replace('@SHADER_ENUMS@',''))

    # The real qrc aliases point at the repository's actual PNG/JPEG bytes.
    files=('serverless/Textures/ground_5-2K/2K-ground_5-diffuse.jpg',
        'serverless/Textures/ground_grass_gen_05.png')
    entries=[]
    for relative in files:
        path='interface/resources/'+relative;read(path)
        entries.append('<file alias="'+escape(relative)+'">'+escape(str(ROOT/path))+'</file>')
    qrc=write('create-texture-originals.qrc','<RCC><qresource prefix="/">'+''.join(entries)+'</qresource></RCC>\n')
    compiled=stage/'create-texture-originals-rcc.cpp'
    subprocess.run([str(prefix/'usr/lib64/qt5/bin/rcc'),'-name','create_texture_originals',str(qrc),'-o',str(compiled)],
        check=True,timeout=20,env=environment);units.append(str(compiled))

    moc_paths=[stage/name for name in ('ResourceCache.h','ResourceManager.h','ResourceRequest.h','FileResourceRequest.h','ResourceRequestObserver.h')]
    moc_paths += [ROOT/path for path in ('libraries/material-networking/src/material-networking/TextureCache.h',
        'libraries/material-networking/src/material-networking/KTXCache.h','libraries/shared/src/shared/FileCache.h',
        'libraries/shared/src/PathUtils.h','libraries/shared/src/SettingManager.h')]
    include_paths=('libraries/networking/src','libraries/material-networking/src','libraries/material-networking/src/material-networking',
        'libraries/image/src','libraries/ktx/src','libraries/shaders/src','libraries/shared/src','libraries/gpu/src','libraries/graphics/src')
    include=['-I'+str(stage),'-I'+str(ROOT),*('-I'+str(ROOT/path) for path in include_paths),
        *[flag for folder in (nvtt,etc,openexr,imath,tbb) for flag in ('-isystem',str(folder/'include'))],
        '-isystem',str(imath/'include/Imath')]
    moc_include=['-I'+str(stage),'-I'+str(ROOT),*('-I'+str(ROOT/path) for path in include_paths),*('-I'+str(folder/'include') for folder in (nvtt,etc,openexr,imath,tbb))]
    for index,path in enumerate(moc_paths):
        output=stage/('create-texture-original-'+str(index)+'-moc.cpp')
        subprocess.run([str(prefix/'usr/lib64/qt5/bin/moc'),'-DOVERTE_E2E_FEATURE_TESTS','-DANDROID_APP_PICO_INTERFACE',
            *moc_include,str(path),'-o',str(output)],check=True,timeout=20,env=environment);units.append(str(output))
    prefix_header=write('create-texture-prefix.h','''#include <list>
#include <chrono>
#include <map>
#include <limits>
#include <vector>
#include <functional>
#include <QCoreApplication>
#include <QString>
#include <cstdint>
''')
    for path in stage.rglob('*'):
        if path.is_file() and path.suffix in ('.h','.cpp','.qrc','.inc'):
            manifest['compiled-'+str(path.relative_to(stage))]=hashlib.sha256(path.read_bytes()).hexdigest()
    write('create-texture-original-provenance.json',json.dumps(manifest,sort_keys=True))
    environment['HIFI_USE_SOURCE_TREE_RESOURCES']='1'
    return ['-DOVERTE_CREATE_ORIGINAL_TEXTURES','-DDEV_BUILD','-DGPU_POINTER_STORAGE_RAW','-include',str(prefix_header),*include,*units,'-Wl,--start-group',*libraries,'-Wl,--end-group']
