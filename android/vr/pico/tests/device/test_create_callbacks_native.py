"""Selected QtCore native Create callback history and original getter test."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
import json
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[4]
sys.path.insert(0,str(ROOT/'tests/device'))
from adapters.pico4.create_callbacks import active,continuity,validate


def function(source,signature):
    start=source.index(signature);end=source.index('{',start)+1;depth=1
    while depth:
        depth+=(source[end]=='{')-(source[end]=='}');end+=1
    return source[start:end]


class CreateCallbacksNativeTests(unittest.TestCase):
    def test_original_callback_history_membership_and_immutable_getter(self):
        environment=dict(os.environ);major=environment.get('OVERTE_NATIVE_QT_MAJOR','6');self.assertIn(major,('5','6'))
        libraries=[]
        if major=='5' and environment.get('OVERTE_QT5_HOST_ROOT'):
            prefix=Path(environment['OVERTE_QT5_HOST_ROOT']).resolve(strict=True)
            environment.update(PKG_CONFIG_SYSROOT_DIR=str(prefix),PKG_CONFIG_LIBDIR=str(prefix/'usr/lib64/pkgconfig'),LD_LIBRARY_PATH=str(prefix/'usr/lib64'))
            libraries=['-L'+str(prefix/'usr/lib64')]
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt'+major+'Core'],text=True,env=environment))
        with tempfile.TemporaryDirectory(prefix='pico-create-callbacks-') as directory:
            stage=Path(directory)
            engine=(ROOT/'libraries/script-engine/src/ScriptEngines.cpp').read_text()
            getter=(ROOT/'interface/src/scripting/TestScriptingInterface.cpp').read_text()
            (stage/'OriginalCreateCallbacks.inc').write_text(function(engine,'QVariantMap ScriptEngines::featureCreateCallbackObservation(')
                +'\n'+function(getter,'QVariantMap TestScriptingInterface::featureCreateCallbacks('))
            binary=stage/'callback-test'
            subprocess.run(['c++','-std=c++17','-fPIC','-pthread','-I'+directory,'-I'+str(ROOT/'libraries/script-engine/src'),
                str(HERE/'create-callbacks-native.cpp'),'-o',str(binary),*libraries,*flags],check=True,timeout=60,env=environment)
            subprocess.run([str(binary)],check=True,timeout=10,env=environment)
            output=subprocess.check_output([str(binary),'--testScript'],timeout=10,env=environment,text=True)
            packets=[json.loads(line) for line in output.splitlines()]
            self.assertEqual(3,len(packets));previous=None
            for packet in packets:
                validate(packet,packet['requestId'],packet['processId'],packet['capturedEpochMs'])
                continuity(previous,packet);previous=packet
            self.assertEqual(1,len(active(packets[0])))
            self.assertEqual(1,len(active(packets[1])))
            self.assertEqual(1,active(packets[1])[0]['dispatches'])
            self.assertEqual([],active(packets[2]))


if __name__=='__main__':unittest.main()
