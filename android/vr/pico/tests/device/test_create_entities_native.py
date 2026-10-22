"""Compile original readonly Create domain getter against substituted tree APIs."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[4]
sys.path.insert(0,str(ROOT/'tests/device'))
from adapters.pico4.create_entities import validate,continuity
from adapters.normal_ui import NativeUIError
from test_create_callbacks_native import function


class CreateEntitiesNativeTests(unittest.TestCase):
    def test_original_getter_retains_moved_renamed_and_deleted_entity_ids(self):
        environment=dict(os.environ);major=environment.get('OVERTE_NATIVE_QT_MAJOR','6');self.assertIn(major,('5','6'))
        libraries=[]
        if major=='5' and environment.get('OVERTE_QT5_HOST_ROOT'):
            prefix=Path(environment['OVERTE_QT5_HOST_ROOT']).resolve(strict=True)
            environment.update(PKG_CONFIG_SYSROOT_DIR=str(prefix),PKG_CONFIG_LIBDIR=str(prefix/'usr/lib64/pkgconfig'),LD_LIBRARY_PATH=str(prefix/'usr/lib64'))
            libraries=['-L'+str(prefix/'usr/lib64')]
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt'+major+'Core'],text=True,env=environment))
        with tempfile.TemporaryDirectory(prefix='pico-create-entities-') as directory:
            stage=Path(directory);(stage/'EntityItem.h').write_text('#pragma once\n');source=(ROOT/'interface/src/scripting/TestScriptingInterface.cpp').read_text()
            (stage/'OriginalCreateEntities.inc').write_text(function(source,'QVariantMap TestScriptingInterface::featureCreateEntities('))
            factory=(ROOT/'libraries/entities-renderer/src/RenderableModelEntityItem.cpp').read_text()
            (stage/'OriginalEntityDeleter.inc').write_text(function(factory,'[](RenderableModelEntityItem* ptr)'))
            binary=stage/'entity-test'
            subprocess.run(['c++','-std=c++17','-fPIC','-pthread','-I'+directory,'-I'+str(ROOT/'tests/device/native'),str(HERE/'create-entities-native.cpp'),
                '-o',str(binary),*libraries,*flags],check=True,timeout=60,env=environment)
            subprocess.run([str(binary)],check=True,timeout=10,env=environment)
            output=subprocess.check_output([str(binary),'--testScript'],timeout=10,env=environment,text=True)
            packets=[json.loads(line) for line in output.splitlines()];self.assertEqual(7,len(packets));previous=None
            for packet in packets[:5]:
                validate(packet,packet['requestId'],packet['processId'],packet['capturedEpochMs'],'a'*32);continuity(previous,packet);previous=packet
            validate(packets[5],packets[5]['requestId'],packets[5]['processId'],packets[5]['capturedEpochMs'],'a'*32)
            validate(packets[6],packets[6]['requestId'],packets[6]['processId'],packets[6]['capturedEpochMs'],'a'*32)
            self.assertEqual('terrain',packets[6]['source']['entities'][0]['name'])
            self.assertEqual(2,len(packets[6]['source']['localCreations']['events']))
            with self.assertRaises(NativeUIError):continuity(packets[4],packets[5])
            self.assertEqual([],packets[0]['source']['entities']);self.assertEqual('domain',packets[1]['source']['entities'][0]['hostType'])
            self.assertEqual('local',packets[2]['source']['entities'][0]['hostType']);self.assertEqual(1,len(packets[3]['source']['absentIds']))

    def test_original_local_insertion_and_atomic_voxel_state_source(self):
        environment=dict(os.environ);major=environment.get('OVERTE_NATIVE_QT_MAJOR','6');libraries=[]
        self.assertIn(major,('5','6'))
        if major=='5':
            prefix=Path(environment['OVERTE_QT5_HOST_ROOT']).resolve(strict=True)
            environment.update(PKG_CONFIG_SYSROOT_DIR=str(prefix),PKG_CONFIG_LIBDIR=str(prefix/'usr/lib64/pkgconfig'),
                LD_LIBRARY_PATH=str(prefix/'usr/lib64'));libraries=['-L'+str(prefix/'usr/lib64')]
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt'+major+'Core'],text=True,env=environment))
        with tempfile.TemporaryDirectory(prefix='create-original-primitives-') as directory:
            stage=Path(directory);binary=stage/'test'
            insertion=(ROOT/'libraries/entities/src/EntityScriptingInterface.cpp').read_text()
            renderer=(ROOT/'libraries/entities-renderer/src/RenderablePolyVoxEntityItem.cpp').read_text()
            (stage/'OriginalLocalInsertion.inc').write_text(function(insertion,'bool EntityScriptingInterface::addLocalEntityCopy('))
            (stage/'OriginalAtomicVoxels.inc').write_text(function(renderer,'QVariantMap RenderablePolyVoxEntityItem::featureCreateVoxels('))
            subprocess.run(['c++','-std=c++17','-fPIC','-UNDEBUG','-pthread','-I'+directory,'-I'+str(ROOT/'tests/device/native'),
                '-isystem',str(Path(environment['OVERTE_TEST_GLM_INCLUDE']).resolve(strict=True)),
                str(HERE/'create-primitives-native.cpp'),'-o',str(binary),*libraries,*flags],check=True,timeout=60,env=environment)
            subprocess.run([str(binary)],check=True,timeout=10,env=environment)
            output=subprocess.check_output([str(binary),'--testScript'],text=True,timeout=10,env=environment)
            from adapters.pico4.create_entities import local_creations,voxel_source
            local,voxels=[json.loads(line) for line in output.splitlines()]
            local_creations(local,local['events'][-1]['observedEpochMs']);values=voxel_source(voxels)
            self.assertEqual(64,sum(v!=0 for v in values))
            self.assertEqual(bytes(255 if 2<=x<6 and 2<=y<6 and 2<=z<6 else 0
                for z in range(8) for y in range(8) for x in range(8)),values)


if __name__=='__main__':unittest.main()
