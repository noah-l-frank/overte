"""Complete original requests/decoder/hash checks and Pico read getter.

Protocol/cache/NodeList endpoints are explicit host boundaries, not an actual
Asset Server. No mutation endpoint or physical/backend success is qualified.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[4]
sys.path.insert(0,str(HERE))
from test_create_polyvox_controls_native import original


def compile_source(stage):
    environment=dict(os.environ);prefix=Path(environment['OVERTE_QT5_HOST_ROOT']).resolve(strict=True)
    environment.update(PKG_CONFIG_SYSROOT_DIR=str(prefix),PKG_CONFIG_LIBDIR=str(prefix/'usr/lib64/pkgconfig'),LD_LIBRARY_PATH=str(prefix/'usr/lib64'))
    flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt5Core'],text=True,env=environment))
    stage=Path(stage);include,definitions=prepare_source(stage,environment,prefix)
    binary=stage/'assets-read-test'
    subprocess.run(['c++','-std=c++17','-fPIC','-UNDEBUG','-fmax-errors=3',*definitions,*include,
        str(HERE/'assets-read-native.cpp'),str(stage/'MappingRequest.cpp'),str(stage/'AssetRequest.cpp'),
        str(stage/'MappingRequest-moc.cpp'),str(stage/'AssetRequest-moc.cpp'),'-o',str(binary),'-L'+str(prefix/'usr/lib64'),*flags],
        check=True,timeout=90,env=environment)
    return binary,environment


def prepare_source(stage,environment,prefix):
    stage=Path(stage);network=ROOT/'libraries/networking/src'
    for name in ('MappingRequest.h','MappingRequest.cpp','AssetRequest.h','AssetRequest.cpp','AssetUtils.h','ByteRange.h'):
        (stage/name).write_bytes((network/name).read_bytes())
    for name in ('AssetClient.h','DependencyManager.h'):(stage/name).write_text('#include "assets-read-endpoints-host.h"\n')
    (stage/'NodeList.h').write_text('#include "assets-read-nodes-host.h"\n')
    for name in ('StatTracker.h','Trace.h','ResourceCache.h'):(stage/name).write_text('// Explicit unused host endpoint.\n')
    (stage/'NetworkLogging.h').write_text('#include <QLoggingCategory>\nQ_DECLARE_LOGGING_CATEGORY(asset_client)\n')
    helpers=(network/'AssetUtils.cpp').read_text()
    code='const QString URL_SCHEME_ATP="atp";\nnamespace AssetUtils {\n'
    code+='\n'.join(original(helpers,signature) for signature in ('QUrl getATPUrl(', 'QByteArray hashData(', 'bool isValidFilePath(', 'bool isValidPath(', 'bool isValidHash('))+'\n}\n'
    code+=original((network/'ReceivedMessage.cpp').read_text(),'QString ReceivedMessage::readString(')+'\n'
    factories=(network/'AssetClient.cpp').read_text()
    code+='\n'.join(original(factories,signature) for signature in ('GetMappingRequest* AssetClient::createGetMappingRequest(', 'GetAllMappingsRequest* AssetClient::createGetAllMappingsRequest(', 'AssetRequest* AssetClient::createRequest('))+'\n'
    (stage/'AssetsReadOriginals.inc').write_text(code)
    source=(ROOT/'interface/src/scripting/TestScriptingInterface.cpp').read_text()
    (stage/'AssetsReadMethod.inc').write_text(original(source,'QVariantMap TestScriptingInterface::featurePicoAssetsRead(')+'\n'+original(source,'QVariantMap TestScriptingInterface::featurePicoAssetsReadRetire('))
    include=['-I'+str(stage),'-I'+str(HERE),'-I'+str(ROOT/'tests/device/native')]
    definitions=['-DOVERTE_E2E_FEATURE_TESTS','-DANDROID_APP_PICO_INTERFACE']
    for name in ('MappingRequest','AssetRequest'):
        subprocess.run([str(prefix/'usr/lib64/qt5/bin/moc'),*definitions,*include,str(stage/(name+'.h')),'-o',str(stage/(name+'-moc.cpp'))],check=True,timeout=15,env=environment)
    return include,definitions


class AssetsReadNativeTests(unittest.TestCase):
    def test_original_mapping_resolve_download_and_actual_request_retirement(self):
        with tempfile.TemporaryDirectory(prefix='pico-assets-read-originals-') as directory:
            binary,environment=compile_source(directory)
            for gate in ([],['--testScript']):subprocess.run([str(binary),*gate],check=True,timeout=10,env=environment)


if __name__=='__main__':unittest.main()
