"""Fresh CPU glTF parser/registry sources; no prebuilt Overte shared objects.

The optional host executable owns a real QRunnable. Transport, MToon, opacity
GPU inspection and baking are explicit fail-closed endpoints, not readiness.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
from test_assets_read_native import ROOT, HERE, original


def prepare(stage, environment, prefix):
    stage = Path(stage)
    stage.mkdir(parents=True, exist_ok=True)
    provenance = {}
    def source(path):
        data = (ROOT/path).read_bytes()
        provenance[path] = hashlib.sha256(data).hexdigest()
        return data.decode()
    def bodies(path, signatures):
        text = source(path)
        return '\n'.join(original(text, signature) for signature in signatures)
    def write(name, data):
        target = stage/name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(data)

    for name in ('DependencyManager.h', 'ResourceManager.h', 'PathUtils.h'):
        write(name, '#pragma once\n#include "assets-geometry-parser-host.h"\n')
    write('NetworkAccessManager.h', '''#pragma once
#include <QNetworkAccessManager>
class NetworkAccessManager {public:static QNetworkAccessManager& getInstance(){qFatal("HTTP is outside the recorded ATP parser join");static QNetworkAccessManager value;return value;}};
''')
    # This branch is not used by the ordinary PBR fixture. Entering it refuses
    # qualification; it cannot produce substitute material or geometry data.
    mtoon_methods = ('Shade', 'ShadingShift', 'ShadingToony', 'Matcap', 'ParametricRim',
        'ParametricRimFresnelPower', 'ParametricRimLift', 'RimLightingMix', 'OutlineWidth',
        'Outline', 'UVAnimationScrollXSpeed', 'UVAnimationScrollYSpeed', 'UVAnimationRotationSpeed')
    write('procedural/ProceduralMaterialCache.h', '#pragma once\n#include <graphics/Material.h>\n'
        'class NetworkMToonMaterial:public graphics::Material {public:NetworkMToonMaterial(){qFatal("MToon is outside CPU parser qualification");}\n'+
        '\n'.join('template<class T> void set'+name+'(const T&){qFatal("MToon endpoint");}' for name in mtoon_methods)+'\n};\n')

    # Preserve complete original headers and serializer translation unit.
    for name, path in {
        'GLTFSerializer.h': 'libraries/model-serializers/src/GLTFSerializer.h',
        'GLTFSerializer.cpp': 'libraries/model-serializers/src/GLTFSerializer.cpp',
        'ModelLoader.h': 'libraries/model-networking/src/model-networking/ModelLoader.h',
        'hfm/HFM.h': 'libraries/hfm/src/hfm/HFM.h',
        'hfm/HFMSerializer.h': 'libraries/hfm/src/hfm/HFMSerializer.h',
        'hfm/HFMFormatRegistry.h': 'libraries/hfm/src/hfm/HFMFormatRegistry.h',
        'hfm/ModelFormatRegistry.h': 'libraries/hfm/src/hfm/ModelFormatRegistry.h',
    }.items():
        write(name, source(path))
    loader_header = (stage/'ModelLoader.h').read_text()
    declaration = next(line for line in loader_header.splitlines() if 'Model::Pointer load(' in line)
    write('ModelLoader.h', loader_header.replace(declaration, declaration+'\n'+declaration.replace(' load(', ' loadOriginal(')))
    loader = source('libraries/model-networking/src/model-networking/ModelLoader.cpp')
    loader_delegate = loader.replace('ModelLoader::load(', 'ModelLoader::loadOriginal(', 1)
    write('GeometryParserOriginals.inc', '\n'.join([
        source('libraries/hfm/src/hfm/HFMFormatRegistry.cpp'),
        source('libraries/hfm/src/hfm/ModelFormatRegistry.cpp'),
        loader_delegate,
        source('libraries/shared/src/shared/MediaTypeLibrary.cpp'),
        source('libraries/shared/src/BlendshapeConstants.cpp'),
    ]))
    provenance['compiled-loader-delegate'] = hashlib.sha256(loader_delegate.encode()).hexdigest()
    provenance['compiled-loader-declaration'] = hashlib.sha256((stage/'ModelLoader.h').read_bytes()).hexdigest()
    cmake = source('CMakeLists.txt')
    glm_definitions = [line.strip() for line in cmake.splitlines() if line.strip() in
        ('add_definitions(-DGLM_FORCE_RADIANS)', 'add_definitions(-DGLM_ENABLE_EXPERIMENTAL)', 'add_definitions(-DGLM_FORCE_CTOR_INIT)')]
    if len(glm_definitions) != 3:
        raise RuntimeError('Review current product GLM construction definitions')
    model_cache = source('libraries/model-networking/src/model-networking/ModelCache.cpp')
    declaration = model_cache[model_cache.index('class GeometryReader : public QRunnable {'):model_cache.index('\nvoid GeometryReader::run()')]
    reader_run = original(model_cache, 'void GeometryReader::run(')
    write('GeometryReaderOriginals.inc', declaration+'\n'+reader_run)
    provenance['original-geometry-reader-declaration'] = hashlib.sha256(declaration.encode()).hexdigest()
    provenance['original-geometry-reader-run'] = hashlib.sha256(reader_run.encode()).hexdigest()
    material_header = source('libraries/procedural/src/procedural/ProceduralMaterialCache.h')
    material_mapping = '\n'.join(next(line for line in material_header.splitlines() if line.startswith(prefix))
        for prefix in ('using NetworkMaterialResourcePointer =', 'using MaterialMapping ='))
    write('GeometryParserMaterialMapping.inc', 'class NetworkMaterialResource;\n'+material_mapping+'\n')
    provenance['original-material-mapping-declarations'] = hashlib.sha256(material_mapping.encode()).hexdigest()
    # CPU declarations are original. Only actually required methods are linked.
    material = source('libraries/graphics/src/graphics/Material.cpp')
    constants = '\n'.join(line for line in material.splitlines()
        if line.startswith(('const float Material::', 'const MaterialKey::', 'const std::string Material::', 'const glm::vec3 Material::')))
    methods = ('Material::Material()', 'void Material::setEmissive(', 'void Material::setOpacity(',
        'void Material::setUnlit(', 'void Material::setAlbedo(', 'void Material::setRoughness(',
        'void Material::setMetallic(', 'void Material::setOpacityCutoff(',
        'void Material::setOpacityMapMode(', 'MaterialKey::OpacityMapMode Material::getOpacityMapMode(')
    hfm = source('libraries/hfm/src/hfm/HFM.cpp')
    palette = hfm[hfm.index('namespace {'):hfm.index('\nvoid HFMMaterial::getTextureNames(')]
    glm = source('libraries/shared/src/GLMHelpers.cpp')
    vectors = '\n'.join(line for line in glm.splitlines() if line.startswith(('const vec3 Vectors::MAX', 'const vec3 Vectors::MIN')))
    write('GeometryParserCpuOriginals.inc', '\n'.join([
        'using namespace graphics;', constants,
        *(original(material, signature) for signature in methods),
        palette, vectors,
        bodies('libraries/shared/src/Extents.cpp', ('void Extents::reset(', 'void Extents::addPoint(')),
        *(original(glm, signature) for signature in ('glm::vec3 extractTranslation(', 'glm::vec3 extractScale(', 'glm::quat glmExtractRotation(')),
        bodies('libraries/shared/src/Transform.cpp', ('void Transform::evalRotationScale(',)),
    ]))
    # No current code is replaced by an older binary. Header dependencies are
    # admitted by content hash as well as their actual absolute paths.
    glm_root = Path(environment['OVERTE_TEST_GLM_INCLUDE']).resolve(strict=True)
    def dependency(name, relative):
        explicit = environment.get('OVERTE_TEST_'+name.upper()+'_INCLUDE')
        if explicit:
            return Path(explicit).resolve(strict=True)
        candidates = sorted(glm_root.parents[2].glob(name+'*/p/include/'+relative))
        if len(candidates) != 1:
            raise RuntimeError('Set OVERTE_TEST_'+name.upper()+'_INCLUDE to one reviewed existing header root')
        return candidates[0].parents[len(Path(relative).parts)-1]
    dependency_roots = {'cgltf': dependency('cgltf','cgltf.h'), 'glad': dependency('glad','glad/glad.h'), 'glm': glm_root}
    for name, relative in (('cgltf', 'cgltf.h'), ('glad', 'glad/glad.h'), ('glm', 'glm/glm.hpp')):
        header = dependency_roots[name]/relative
        provenance[str(header)] = hashlib.sha256(header.read_bytes()).hexdigest()
    for name in ('GeometryReaderOriginals.inc', 'GeometryParserOriginals.inc', 'GeometryParserCpuOriginals.inc'):
        provenance['compiled-'+name] = hashlib.sha256((stage/name).read_bytes()).hexdigest()
    write('geometry-parser-original-provenance.json', json.dumps(provenance, sort_keys=True))
    for header in ('GLTFSerializer.h', 'assets-geometry-parser-host.h'):
        path = stage/header if header == 'GLTFSerializer.h' else HERE/header
        subprocess.run([str(prefix/'usr/lib64/qt5/bin/moc'), '-I'+str(stage), str(path), '-o', str(stage/(path.stem+'-moc.cpp'))],
            check=True, timeout=20, env=environment)
    flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs', 'Qt5Core', 'Qt5Gui', 'Qt5Network', 'Qt5Test'], text=True, env=environment))
    includes = [stage, stage/'hfm', HERE, ROOT/'libraries/hfm/src', ROOT/'libraries/shared/src', ROOT/'libraries/shared/src/shared', ROOT/'libraries/gpu/src', ROOT/'libraries/graphics/src',
        ROOT/'libraries/image/src', ROOT/'libraries/model-serializers/src']
    return ['c++', '-std=c++17', '-fPIC', '-UNDEBUG', '-DGLM_FORCE_RADIANS', '-DGLM_ENABLE_EXPERIMENTAL', '-DGLM_FORCE_CTOR_INIT',
        '-fmax-errors=3', '-ffunction-sections', '-fdata-sections',
        '-include', str(HERE/'assets-geometry-parser-host.h'),
        *('-I'+str(path) for path in includes), *('-isystem'+str(path) for path in dependency_roots.values()),
        str(HERE/'assets-geometry-parser-native.cpp'), str(stage/'GLTFSerializer.cpp'),
        str(stage/'GLTFSerializer-moc.cpp'), str(stage/'assets-geometry-parser-host-moc.cpp'),
        '-Wl,--gc-sections', '-pthread', '-o', str(stage/'geometry-parser'), '-L'+str(prefix/'usr/lib64'), *flags]
