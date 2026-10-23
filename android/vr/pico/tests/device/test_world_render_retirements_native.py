"""Selected original GPU ledger/getter bodies and the complete batch header.

GPU production and application lifecycle are explicit host seams. Qt mutexes,
native receipt files and their original ownership validation are actual code.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[4]


def method(source,signature):
    start=source.index(signature);body=source.index('{',start);depth=1;end=body+1
    while depth:
        depth+=(source[end]=='{')-(source[end]=='}');end+=1
    return source[start:end]


def compile_source(directory):
    environment=dict(os.environ);major=environment.get('OVERTE_NATIVE_QT_MAJOR','6')
    assert major in ('5','6');paths=[]
    if major=='5' and environment.get('OVERTE_QT5_HOST_ROOT'):
        prefix=Path(environment['OVERTE_QT5_HOST_ROOT']).resolve(strict=True)
        environment.update(PKG_CONFIG_SYSROOT_DIR=str(prefix),PKG_CONFIG_LIBDIR=str(prefix/'usr/lib64/pkgconfig'),
            LD_LIBRARY_PATH=str(prefix/'usr/lib64'));paths=['-L'+str(prefix/'usr/lib64')]
    flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt'+major+'Core'],text=True,env=environment))
    gpu=(ROOT/'libraries/gpu/src/gpu/FeatureWorldRender.h').read_text()
    tsi=(ROOT/'interface/src/scripting/TestScriptingInterface.cpp').read_text()
    source=(HERE/'world-render-retirements-native.cpp').read_text().replace('GPU_INVENTORY_BODY',
        method(gpu,'QVariantMap receiptInventory(')).replace('GPU_ENABLED_BODY',method(gpu,'static bool enabled()'))
    source=source.replace('GPU_VALID_BODY',method(gpu,'static bool valid(')).replace('TSI_RECEIPTS_BODY',
        method(tsi,'QVariantMap TestScriptingInterface::featureWorldRenderReceipts('))
    source=source.replace('TSI_BATCH_BODY',method(tsi,'QVariantMap TestScriptingInterface::featurePicoWorldRenderRetirements('))
    path=Path(directory)/'selected-originals.cpp';path.write_text(source);binary=Path(directory)/'world-render-retirements'
    subprocess.run(['c++','-std=c++17','-fPIC','-DOVERTE_E2E_FEATURE_TESTS','-DANDROID_APP_PICO_INTERFACE',
        '-I'+str(ROOT/'tests/device/native'),str(path),'-o',str(binary),*paths,*flags],
        check=True,timeout=90,env=environment)
    return binary,environment


class WorldRenderRetirementsNativeTests(unittest.TestCase):
    def test_original_complete_native_inventories_and_failure_boundaries(self):
        with tempfile.TemporaryDirectory(prefix='pico-world-retirements-') as directory:
            binary,environment=compile_source(directory)
            subprocess.run([str(binary),'--testScript'],check=True,timeout=15,env=environment)


if __name__=='__main__':unittest.main()
