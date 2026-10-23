"""Original current VoxelVolume/mesh/state/compression and existing sources."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
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
    api=read('libraries/entities/src/EntityScriptingInterface.cpp')
    for signature in ('bool EntityScriptingInterface::polyVoxWorker(', 'bool EntityScriptingInterface::setVoxelsInCuboid('):
        blocks[signature]=original(api,signature)
    constant=next(line for line in renderer.splitlines() if line.startswith('const float MARCHING_CUBE_COLLISION_HULL_OFFSET ='))
    write('OriginalCreateVoxelMethods.inc',constant+'\n'+'\n'.join(blocks.values()))
    write('OriginalCreateVoxelDeleter.inc','const auto originalCreateVoxelDeleter = '+original(renderer,'[](RenderablePolyVoxEntityItem* ptr)')+';\n')
    write('OriginalPolyvoxRenderUpdate.inc',original(renderer,'void PolyVoxEntityRenderer::doRenderUpdateAsynchronousTyped('))
    write('EntityItem.h','#pragma once\n#include "create-voxel-native-join.h"\n')
    cpu=[]
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
    glm=read('libraries/shared/src/GLMHelpers.cpp')
    vectors='\n'.join(line for line in glm.splitlines() if line.startswith('const vec3 Vectors::'))
    write('OriginalCreateVoxelVectors.inc',vectors+'\n');cpu.append('#include "OriginalCreateVoxelVectors.inc"')
    write('CreateVoxelOriginalCpu.cpp','#include <array>\n#include <vector>\n#include <memory>\n#include <QCoreApplication>\n#include <GLMHelpers.h>\n#include <GeometryUtil.h>\n#include <graphics/Geometry.h>\n'+ '\n'.join(cpu)+'\n')
    edit=read('scripts/system/create/edit.js')
    deletion='\n'.join(original(edit,signature) for signature in ('function sortSelectedEntities(',
        'function recursiveDelete(', 'createApp.deleteSelectedEntities = function()'))+';\n'
    write('original-voxel-delete.js',deletion)
    moc=stage/'create-voxel-native-join-moc.cpp'
    subprocess.run([str(prefix/'usr/lib64/qt5/bin/moc'),'-I'+str(stage),'-I'+str(ROOT),
        str(HERE/'create-voxel-native-join.h'),'-o',str(moc)],check=True,timeout=20,env=environment)
    for name,body in blocks.items():provenance[name]=hashlib.sha256(body.encode()).hexdigest()
    for name in ('OriginalCreateVoxelStorage.inc','OriginalCreateVoxelMethods.inc','OriginalCreateVoxelDeleter.inc','OriginalPolyvoxRenderUpdate.inc',
            'AssetsOriginalBakerMesh.inc','AssetsOriginalBuffer.inc','OriginalCreateVoxelShape.inc',
            'OriginalCreateVoxelVectors.inc','CreateVoxelOriginalCpu.cpp','original-voxel-delete.js'):
        provenance['compiled-'+name]=hashlib.sha256((stage/name).read_bytes()).hexdigest()
    write('create-voxel-native-original-provenance.json',json.dumps(provenance,sort_keys=True))
    return [str(HERE/'create-voxel-native-join.cpp'),str(stage/'CreateVoxelOriginalCpu.cpp'),str(moc)]
