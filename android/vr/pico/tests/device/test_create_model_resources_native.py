"""Original native Model/material source with explicit substituted load actor."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
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
from adapters.normal_ui import NativeUIError
from adapters.pico4.create_model_resources import validate,continuity,retired,NativeCreateModelResources
from test_create_callbacks_native import function


class CreateModelResourcesNativeTests(unittest.TestCase):
    def test_original_bounded_source_retains_actual_weak_model_material_and_cached_qobject(self):
        environment=dict(os.environ);major=environment.get('OVERTE_NATIVE_QT_MAJOR','6');self.assertIn(major,('5','6'))
        libraries=[]
        if major=='5' and environment.get('OVERTE_QT5_HOST_ROOT'):
            prefix=Path(environment['OVERTE_QT5_HOST_ROOT']).resolve(strict=True)
            environment.update(PKG_CONFIG_SYSROOT_DIR=str(prefix),PKG_CONFIG_LIBDIR=str(prefix/'usr/lib64/pkgconfig'),LD_LIBRARY_PATH=str(prefix/'usr/lib64'))
            libraries=['-L'+str(prefix/'usr/lib64')]
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt'+major+'Core'],text=True,env=environment))
        with tempfile.TemporaryDirectory(prefix='pico-create-model-resources-') as directory:
            stage=Path(directory);(stage/'model-networking').mkdir()
            (stage/'Model.h').write_text('#pragma once\n')
            (stage/'model-networking/ModelCache.h').write_text('#pragma once\n')
            getter=(ROOT/'interface/src/scripting/TestScriptingInterface.cpp').read_text()
            geometry=(ROOT/'libraries/model-networking/src/model-networking/ModelCache.h').read_text()
            association=(ROOT/'libraries/entities-renderer/src/RenderableModelEntityItem.h').read_text()
            resource=(ROOT/'libraries/networking/src/ResourceCache.cpp').read_text()
            (stage/'OriginalSaveObject.inc').write_text(function(getter,'void TestScriptingInterface::saveObject('))
            (stage/'OriginalCreateModels.inc').write_text(function(getter,'QVariantMap TestScriptingInterface::featureCreateModels('))
            (stage/'OriginalResourceRetirement.inc').write_text(function(resource,'void Resource::allReferencesCleared('))
            (stage/'OriginalMaterials.inc').write_text(function(geometry,'    const NetworkMaterials& featureCreateMaterials('))
            (stage/'OriginalAssociation.inc').write_text(function(association,'    ModelPointer featureCreateModel('))
            binary=stage/'resource-test'
            subprocess.run(['c++','-std=c++17','-fPIC','-pthread','-I'+directory,'-I'+str(ROOT/'tests/device/native'),
                str(HERE/'create-model-resources-native.cpp'),'-o',str(binary),*libraries,*flags],check=True,timeout=60,env=environment)
            subprocess.run([str(binary)],check=True,timeout=10,env=environment)
            output=subprocess.check_output([str(binary),'--testScript'],timeout=15,env=environment,text=True)
        packets=[json.loads(line) for line in output.splitlines()];self.assertEqual(13,len(packets));previous=None
        for packet in packets:
            validate(packet,packet['requestId'],packet['processId'],packet['capturedEpochMs'],'a'*32)
            if packet is not packets[-1]:continuity(previous,packet)
            previous=packet
        self.assertFalse(retired(packets[7]['source']))
        self.assertFalse(retired(packets[8]['source']))
        self.assertTrue(retired(packets[9]['source']))
        with self.assertRaises(NativeUIError):continuity(packets[-2],packets[-1])
        for mutate in (lambda p:p['source']['resources'][0].update(alive=False),
                lambda p:p['source']['bindings'][0]['textures'][0].update(resource='e'*32),
                lambda p:p['source']['bindings'][0].update(geometry='e'*32),
                lambda p:p['source']['models'][0].update(firstObservedEpochMs=p['capturedEpochMs']+1),
                lambda p:p.update(processId=True),
                lambda p:p['source']['bindings'][0].update(loadedSourceSha256=''),
                lambda p:p['source'].update(expected='requested')):
            invalid=deepcopy(packets[1]);mutate(invalid)
            with self.assertRaises(NativeUIError):validate(invalid,invalid['requestId'],packets[1]['processId'],invalid['capturedEpochMs'],'a'*32)
        invalid=deepcopy(packets[9]);invalid['sequence']+=1;invalid['source']['models'][0]['alive']=True
        with self.assertRaises(NativeUIError):continuity(packets[9],invalid)
        invalid=deepcopy(packets[9]);invalid['sequence']+=1;invalid['source']['materials']=[]
        with self.assertRaises(NativeUIError):continuity(packets[9],invalid)
        # Passive private command accepts no desired URL/UUID/material or load request.
        reader=NativeCreateModelResources(lambda c:None,lambda:'',lambda:1,lambda:True,1,run='a'*32)
        self.assertEqual({'schemaVersion':1,'commandId':'b'*32,'action':'feature-create-models-observe','runId':'a'*32},reader.command('b'*32))


if __name__=='__main__':unittest.main()
