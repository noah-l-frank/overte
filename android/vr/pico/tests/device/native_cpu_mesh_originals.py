"""Shared current-source CPU Mesh/Buffer bodies for Pico native owning tests.

No GPU backend or resource result is supplied here. Callers provide their own
source/provenance writers; the default fragments preserve the Baker selection.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
from test_assets_read_native import ROOT,original

CPU_SUPPORT_SOURCES=(
    'libraries/gpu/src/gpu/Resource.cpp','libraries/gpu/src/gpu/Sysmem.cpp',
    'libraries/gpu/src/gpu/PageManager.cpp','libraries/gpu/src/gpu/Format.cpp',
    'libraries/gpu/src/gpu/Stream.cpp','libraries/shared/src/AABox.cpp',
    'libraries/shared/src/GeometryUtil.cpp')


def source_unit(path):
    if path=='libraries/gpu/src/gpu/Resource.cpp':return 'namespace gpu {\n#include "'+str(ROOT/path)+'"\n}'
    return '#include "'+str(ROOT/path)+'"'


def mesh_fragment(read,write,provenance,extra=()):
    geometry=read('libraries/graphics/src/graphics/Geometry.cpp')
    signatures=('Mesh::Mesh()', 'Mesh::~Mesh(', 'void Mesh::setVertexFormatAndStream(',
        'void Mesh::setIndexBuffer(', 'void Mesh::setPartBuffer(', 'Box Mesh::evalPartBound(')+tuple(extra)
    methods={signature:original(geometry,signature) for signature in signatures}
    write('AssetsOriginalBakerMesh.inc','#include <graphics/Geometry.h>\nnamespace graphics {\n'+
        '\n'.join(methods.values())+'\n}\n')
    for name,body in methods.items():provenance[name]=hashlib.sha256(body.encode()).hexdigest()
    return '#include "AssetsOriginalBakerMesh.inc"'


def buffer_fragment(read,write,provenance,extra=()):
    buffer=read('libraries/gpu/src/gpu/Buffer.cpp')
    signatures=('void Buffer::incrementCreatedBufferCount(', 'uint32_t Buffer::getBufferCPUCount(',
        'Buffer::Size Buffer::getBufferCPUMemSize(', 'Buffer::Buffer(uint32_t usage, Size pageSize)',
        'Buffer::~Buffer(', 'Buffer::Size Buffer::resize(', 'void Buffer::markDirty(',
        'Buffer::Size Buffer::setData(', 'Buffer::Size Buffer::setSubData(', 'Buffer::Size Buffer::getSize(',
        'BufferView::BufferView()', 'BufferView::BufferView(const Element&',
        'BufferView::BufferView(const BufferPointer& buffer, const Element&',
        'BufferView::BufferView(const BufferPointer& buffer, Size offset, Size size, uint16 stride,')+tuple(extra)
    blocks={signature:original(buffer,signature) for signature in signatures}
    constants='\n'.join(line for line in buffer.splitlines() if line.startswith(('ContextMetricCount Buffer::','ContextMetricSize Buffer::','const Element BufferView::')))
    write('AssetsOriginalBuffer.inc','''#include <gpu/Buffer.h>
using namespace gpu;
#define COUNT_BUFFER_CREATIONS
'''+constants+'\n'+'\n'.join(blocks.values()))
    for name,body in blocks.items():provenance[name]=hashlib.sha256(body.encode()).hexdigest()
    return '#include "AssetsOriginalBuffer.inc"'
