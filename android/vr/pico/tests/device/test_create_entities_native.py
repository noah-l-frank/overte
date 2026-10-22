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
            stage=Path(directory);source=(ROOT/'interface/src/scripting/TestScriptingInterface.cpp').read_text()
            (stage/'OriginalCreateEntities.inc').write_text(function(source,'QVariantMap TestScriptingInterface::featureCreateEntities('))
            binary=stage/'entity-test'
            subprocess.run(['c++','-std=c++17','-fPIC','-pthread','-I'+directory,'-I'+str(ROOT/'tests/device/native'),str(HERE/'create-entities-native.cpp'),
                '-o',str(binary),*libraries,*flags],check=True,timeout=60,env=environment)
            subprocess.run([str(binary)],check=True,timeout=10,env=environment)
            output=subprocess.check_output([str(binary),'--testScript'],timeout=10,env=environment,text=True)
            packets=[json.loads(line) for line in output.splitlines()];self.assertEqual(6,len(packets));previous=None
            for packet in packets[:5]:
                validate(packet,packet['requestId'],packet['processId'],packet['capturedEpochMs'],'a'*32);continuity(previous,packet);previous=packet
            validate(packets[5],packets[5]['requestId'],packets[5]['processId'],packets[5]['capturedEpochMs'],'a'*32)
            with self.assertRaises(NativeUIError):continuity(packets[4],packets[5])
            self.assertEqual([],packets[0]['source']['entities']);self.assertEqual('domain',packets[1]['source']['entities'][0]['hostType'])
            self.assertEqual('local',packets[2]['source']['entities'][0]['hostType']);self.assertEqual(1,len(packets[3]['source']['absentIds']))


if __name__=='__main__':unittest.main()
