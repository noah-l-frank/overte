"""Original current VoxelVolume/mesh/state/compression and existing sources."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import importlib.util
import hashlib
import json
from pathlib import Path
import subprocess
from test_assets_read_native import ROOT,HERE,original
from native_cpu_mesh_originals import CPU_SUPPORT_SOURCES,source_unit,mesh_fragment,buffer_fragment


def prepare(stage,environment,prefix):
    stage=Path(stage);provenance={}
    def read(path):
        data=(ROOT/path).read_bytes();provenance[path]=hashlib.sha256(data).hexdigest();return data.decode()
    def write(name,data):(stage/name).write_text(data)
    renderer=read('libraries/entities-renderer/src/RenderablePolyVoxEntityItem.cpp')
    start=renderer.index('// FIXME: move to GLM helpers')
    end=renderer.index('\nEntityItemPointer RenderablePolyVoxEntityItem::factory(')
    storage=renderer[start:end]
    write('OriginalCreateVoxelStorage.inc',storage)
    signatures=('RenderablePolyVoxEntityItem::RenderablePolyVoxEntityItem(',
        'RenderablePolyVoxEntityItem::~RenderablePolyVoxEntityItem(',
        'void RenderablePolyVoxEntityItem::initializePolyVox(',
        'EntityItemPointer RenderablePolyVoxEntityItem::factory(',
        'void RenderablePolyVoxEntityItem::changeUpdates(',
        'void RenderablePolyVoxEntityItem::startUpdates(', 'void RenderablePolyVoxEntityItem::stopUpdates(',
        'void RenderablePolyVoxEntityItem::update(', 'void RenderablePolyVoxEntityItem::setVoxelVolumeSize(',
        'bool inUserBounds(', 'uint8_t RenderablePolyVoxEntityItem::getVoxelInternal(',
        'void RenderablePolyVoxEntityItem::setVoxelMarkNeighbors(', 'bool RenderablePolyVoxEntityItem::setVoxelInternal(',
        'bool RenderablePolyVoxEntityItem::updateOnCount(', 'bool RenderablePolyVoxEntityItem::setCuboid(',
        'void RenderablePolyVoxEntityItem::forEachVoxelValue(', 'QByteArray RenderablePolyVoxEntityItem::volDataToArray(',
        'void RenderablePolyVoxEntityItem::uncompressVolumeData(', 'void RenderablePolyVoxEntityItem::setVoxelsFromData(',
        'void RenderablePolyVoxEntityItem::compressVolumeDataAndSendEditPacket(',
        'void RenderablePolyVoxEntityItem::compressVolumeDataFinished(',
        'void RenderablePolyVoxEntityItem::recomputeMesh(', 'void RenderablePolyVoxEntityItem::setMesh(',
        'void RenderablePolyVoxEntityItem::computeShapeInfoWorker(', 'void RenderablePolyVoxEntityItem::setCollisionPoints(',
        'bool RenderablePolyVoxEntityItem::isVoxelDataReady(',
        'QVariantMap RenderablePolyVoxEntityItem::featureCreateVoxels(',
        'bool RenderablePolyVoxEntityItem::findDetailedRayIntersection(')
    blocks={signature:original(renderer,signature) for signature in signatures}
    base=read('libraries/entities/src/PolyVoxEntityItem.cpp.in')
    for signature in ('bool PolyVoxEntityItem::isEdged(PolyVoxSurfaceStyle', 'bool PolyVoxEntityItem::isEdged()',
            'glm::vec3 PolyVoxEntityItem::getSurfacePositionAdjustment(', 'glm::mat4 PolyVoxEntityItem::voxelToLocalMatrix(',
            'glm::mat4 PolyVoxEntityItem::voxelToWorldMatrix(', 'glm::mat4 PolyVoxEntityItem::worldToVoxelMatrix(',
            'glm::vec3 PolyVoxEntityItem::worldCoordsToVoxelCoords('):blocks[signature]=original(base,signature)
    item=read('libraries/entities/src/EntityItem.cpp.in')
    blocks['void EntityItem::recordCreationTime(']=original(item,'void EntityItem::recordCreationTime(')
    header=read('libraries/entities/src/EntityItem.h.in')
    write('OriginalCreateEntityInline.inc',original(header,'bool isVisuallyReady() const')+'\n'+
        next(line for line in header.splitlines() if 'bool _visuallyReady { true };' in line)+'\n')
    polyvox_header=read('libraries/entities/src/PolyVoxEntityItem.h.in')
    write('OriginalCreatePolyvoxBaseInline.inc',original(polyvox_header,'virtual QVariantMap featureCreateVoxels(')+'\n'+
        original(polyvox_header,'virtual bool isVoxelDataReady() const')+'\n')
    constants=read('libraries/entities/src/EntityItemPropertiesMacros.h')
    property_definitions=read('libraries/entities/src/EntityItemProperties.txt')
    read('cmake/macros/GenerateEntityProperties.cmake')
    start_macro=constants.index('#define DEFINE_VARIABLE_RENDER_REF(')
    end_macro=constants.index('\n#define ENTITY_PROPERTY_SUBCLASS_METHODS',start_macro)
    texture_macro=constants[start_macro:end_macro]
    calls=[]
    for axis in 'XYZ':
        name=axis.lower()+'TextureURL'
        definition=next(line for line in property_definitions.splitlines() if 'prop:'+name+' ' in line)
        if not ('type:QString ' in definition and 'default:"" ' in definition and 'renderProp' in definition):
            raise ValueError('Current original texture property generation changed')
        calls.append('DEFINE_VARIABLE_RENDER_REF('+axis+'TextureURL, '+name+', QString, "");')
    write('OriginalCreateTextureProperties.inc',texture_macro+'\n'+'\n'.join(calls)+'\n#undef DEFINE_VARIABLE_RENDER_REF\n')
    read('libraries/shared/src/SimulationFlags.h')
    write('OriginalCreateInsertionConstants.inc','#include <SimulationFlags.h>\n'+
        next(line for line in constants.splitlines() if line.startswith('const quint64 UNKNOWN_CREATED_TIME ='))+'\n')
    tree=read('libraries/entities/src/EntityTree.cpp')
    blocks['EntityItemPointer EntityTree::addEntity(']=original(tree,'EntityItemPointer EntityTree::addEntity(')
    getter=read('interface/src/scripting/TestScriptingInterface.cpp')
    write('OriginalCreateEntities.inc',original(getter,'QVariantMap TestScriptingInterface::featureCreateEntities(')+'\n')
    api=read('libraries/entities/src/EntityScriptingInterface.cpp')
    for signature in ('bool EntityScriptingInterface::polyVoxWorker(', 'bool EntityScriptingInterface::setVoxelsInCuboid(',
            'bool EntityScriptingInterface::isLoaded(', 'bool EntityScriptingInterface::isVoxelDataReady(',
            'bool EntityScriptingInterface::addLocalEntityCopy('):
        blocks[signature]=original(api,signature)
    constant=next(line for line in renderer.splitlines() if line.startswith('const float MARCHING_CUBE_COLLISION_HULL_OFFSET ='))
    write('OriginalCreateVoxelMethods.inc',constant+'\n'+'\n'.join(blocks.values()))
    write('OriginalPolyvoxRenderUpdate.inc',original(renderer,'void PolyVoxEntityRenderer::doRenderUpdateAsynchronousTyped('))
    write('EntityItem.h','#pragma once\n#include "create-voxel-native-join.h"\n')
    read('libraries/shared/src/DependencyManager.cpp')
    cpu=[source_unit('libraries/shared/src/DependencyManager.cpp')]
    for path in CPU_SUPPORT_SOURCES:read(path);cpu.append(source_unit(path))
    cpu.append(mesh_fragment(read,write,provenance,('void Mesh::setVertexBuffer(', 'void Mesh::addAttribute(',
        'void Mesh::evalVertexFormat(', 'void Mesh::evalVertexStream(')))
    cpu.append(buffer_fragment(read,write,provenance,('Buffer::Buffer(uint32_t usage, Size size, const Byte* bytes, Size pageSize)',
        'BufferView::BufferView(Buffer* newBuffer, const Element&')))
    shapes=read('libraries/shared/src/ShapeInfo.cpp')
    shape_methods='\n'.join(original(shapes,signature) for signature in
        ('void ShapeInfo::setParams(', 'void ShapeInfo::setHalfExtents(', 'void ShapeInfo::setPointCollection('))
    minimum=next(line for line in shapes.splitlines() if line.startswith('const float MIN_HALF_EXTENT ='))
    write('OriginalCreateVoxelShape.inc','#include <ShapeInfo.h>\n'+minimum+'\n'+shape_methods)
    cpu.append('#include "OriginalCreateVoxelShape.inc"')
    write('CreateVoxelOriginalCpu.cpp','#include <array>\n#include <vector>\n#include <memory>\n#include <QCoreApplication>\n#include <GLMHelpers.h>\n#include <GeometryUtil.h>\n#include <graphics/Geometry.h>\n'+ '\n'.join(cpu)+'\n')
    edit=read('scripts/system/create/edit.js')
    deletion='\n'.join(original(edit,signature) for signature in ('function sortSelectedEntities(',
        'function recursiveDelete(', 'createApp.deleteSelectedEntities = function()'))+';\n'
    write('original-voxel-delete.js',deletion)
    # Reuse the already exercised normal Add extraction: complete defaults,
    # original createNewEntity/fromQml/dialog handler, no alternate creation.
    creation=edit[edit.index('    function copyProperties(a, b) {'):edit.index('    var fcreateNewEntity;')]
    creation+='\n'+original(edit,'function createNewEntity(')
    creation+='\nvar shouldUseEditTabletApp='+original(edit,'function() {\n        return HMD.active')+';\n'
    creation+='\n'.join(original(edit,signature) for signature in ('function createNewEntityDialogButtonCallback(',
        'function handleNewPolyVoxDialogResult(', 'function closeExistingDialogWindow(', 'function fromQml('))
    creation+='\nbuttonHandlers.newPolyVoxButton=createNewEntityDialogButtonCallback("PolyVox");\n'
    write('original-voxel-add.js',creation)
    validation=read('scripts/system/create/modules/picoQmlMessageValidation.js')
    write('original-voxel-validation.js','var validatePicoQmlMessage=(function(){var module={exports:{}};\n'+validation+'\nreturn module.exports;})();\n')
    texture_spec=importlib.util.spec_from_file_location('create_voxel_texture_prepare',HERE/'create-voxel-texture-prepare.py')
    textures=importlib.util.module_from_spec(texture_spec);texture_spec.loader.exec_module(textures)
    texture_inputs=textures.prepare(stage,environment,prefix)
    moc=stage/'create-voxel-native-join-moc.cpp'
    subprocess.run([str(prefix/'usr/lib64/qt5/bin/moc'),'-I'+str(stage),'-I'+str(ROOT),
        str(HERE/'create-voxel-native-join.h'),'-o',str(moc)],check=True,timeout=20,env=environment)
    for name,body in blocks.items():provenance[name]=hashlib.sha256(body.encode()).hexdigest()
    for name in ('OriginalCreateVoxelStorage.inc','OriginalCreateVoxelMethods.inc','OriginalPolyvoxRenderUpdate.inc',
            'OriginalCreateEntityInline.inc','OriginalCreatePolyvoxBaseInline.inc','OriginalCreateInsertionConstants.inc','OriginalCreateEntities.inc',
            'OriginalCreateTextureProperties.inc',
            'AssetsOriginalBakerMesh.inc','AssetsOriginalBuffer.inc','OriginalCreateVoxelShape.inc',
            'CreateVoxelOriginalCpu.cpp','original-voxel-delete.js','original-voxel-add.js','original-voxel-validation.js'):
        provenance['compiled-'+name]=hashlib.sha256((stage/name).read_bytes()).hexdigest()
    write('create-voxel-native-original-provenance.json',json.dumps(provenance,sort_keys=True))
    return [str(HERE/'create-voxel-native-join.cpp'),str(stage/'CreateVoxelOriginalCpu.cpp'),str(moc),*texture_inputs]
