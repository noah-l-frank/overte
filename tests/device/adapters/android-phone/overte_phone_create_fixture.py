"""Closed ordinary Create INPUT documents; never observation or export evidence.

NativeCreate's New PolyVox button creates an empty default volume. The complete
Create workflow must instead use its existing ordinary entity-JSON picker for
this controlled central cube, followed by normal Properties and voxel controls.
No Entity/Clipboard/bridge setter is an E2E input here.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import base64
import json
import struct
import zlib

from adapters.native_feature_observation import need
from feature_journeys.contract import identifier
from feature_journeys.fixtures import context,import_document

NAMES=('entity-import.json','voxel-import.json')


def voxel_data():
    """Existing QDataStream/quint16 + qCompress byte format, fixed 8³ cube.

    edit.js's central-cube creation uses start round(size/4)=2 and extent
    round(size/2)=4. RenderablePolyVox uses z*Y*X+y*Z+x; all axes here are 8.
    These bytes are fixture input only. The created native saved-data baseline
    and post-click readiness must be independently acquired afterwards.
    """
    data=bytearray(8**3)
    for z in range(2,6):
        for y in range(2,6):
            for x in range(2,6):data[z*64+y*8+x]=255
    compressed=struct.pack('>I',len(data))+zlib.compress(bytes(data),9)
    return base64.b64encode(struct.pack('>HHHI',8,8,8,len(compressed))+compressed).decode('ascii')


def voxel_document(run):
    identifier(run)
    return dict(DataVersion=3,Entities=[dict(name=context(run)['name']+'-voxel',type='PolyVox',
        dimensions=dict(x=1.,y=1.,z=1.),voxelVolumeSize=dict(x=8.,y=8.,z=8.),
        voxelData=voxel_data(),voxelSurfaceStyle=2,collisionless=True,dynamic=False)])


def documents(run,ticket,fixture_url):
    """Return two controlled originals for exclusive private staging."""
    identifier(run);identifier(ticket)
    values=(import_document(run,ticket,fixture_url),voxel_document(run))
    result={name:(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode()
            for name,value in zip(NAMES,values)}
    need(all(0<len(raw)<=16384 for raw in result.values()))
    return result
