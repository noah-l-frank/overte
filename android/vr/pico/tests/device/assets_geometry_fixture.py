"""Additional valid indexed glTF data; original parity fixtures stay unchanged."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import struct
from adapters.assets_input import documents


def indexed_documents():
    result = documents()
    main = json.loads(result['gltf-bundle/main.gltf'])
    mesh = result['gltf-bundle/mesh/triangle.bin']
    main['asset']['generator'] = 'Overte Assets indexed CPU parser host fixture'
    main['buffers'][0]['byteLength'] = len(mesh)+6
    main['bufferViews'].append(dict(buffer=0, byteOffset=len(mesh), byteLength=6, target=34963))
    main['accessors'].append(dict(bufferView=3, componentType=5123, count=3, type='SCALAR', min=[0], max=[2]))
    main['meshes'][0]['primitives'][0]['indices'] = 3
    result['gltf-bundle/main.gltf'] = (json.dumps(main, indent=2)+'\n').encode()
    result['gltf-bundle/mesh/triangle.bin'] = mesh+struct.pack('<3H', 0, 1, 2)
    return result
