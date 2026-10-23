"""Original server GetAll/meta/status joined to actual client request/reader.

Private disk files and original Qt request threads are real. Assignment/network,
wire writer and absent oven workers are explicit endpoints; no backend service,
worker, upload, render, physical device or current successful bake is qualified.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import unittest
from test_assets_read_native import prepare_source,HERE,ROOT,original
sys.path.insert(0,str(ROOT/'tests/device'))
from adapters.pico4.assets_source import validate


def prepare_server_originals(stage):
    stage=Path(stage)
    header=(ROOT/'assignment-client/src/assets/AssetServer.h').read_text()
    types=header[header.index('using BakeVersion ='):header.index('class BakeAssetTask;')]
    (stage/'AssetsServerTypes.inc').write_text(types)
    source=(ROOT/'assignment-client/src/assets/AssetServer.cpp').read_text()
    constants=source[source.index('static const QStringList BAKEABLE_MODEL_EXTENSIONS'):source.index('const QString ASSET_SERVER_LOGGING_TARGET_NAME')]
    meta_keys=source[source.index('static const QString BAKE_VERSION_KEY'):source.index('std::pair<bool, AssetMeta> AssetServer::readMetaFile(')]
    signatures=('QString AssetServer::getPathToAssetHash(', 'std::pair<AssetUtils::BakingStatus, QString> AssetServer::getAssetStatus(',
        'std::pair<bool, AssetMeta> AssetServer::readMetaFile(', 'void AssetServer::handleGetAllMappingOperation(')
    blocks={signature:original(source,signature) for signature in signatures}
    (stage/'AssetsServerOriginals.inc').write_text(constants+meta_keys+'\n'+'\n'.join(blocks.values()))
    provenance={key:hashlib.sha256(value.encode()).hexdigest() for key,value in blocks.items()}
    provenance['AssetServerTypes']=hashlib.sha256(types.encode()).hexdigest();provenance['AssetServerConstantsAndHelpers']=hashlib.sha256(constants.encode()).hexdigest()
    (stage/'server-original-provenance.json').write_text(json.dumps(provenance,sort_keys=True))
    return provenance


def build(stage):
    stage=Path(stage);environment=dict(os.environ);prefix=Path(environment['OVERTE_QT5_HOST_ROOT']).resolve(strict=True)
    environment.update(PKG_CONFIG_SYSROOT_DIR=str(prefix),PKG_CONFIG_LIBDIR=str(prefix/'usr/lib64/pkgconfig'),LD_LIBRARY_PATH=str(prefix/'usr/lib64'))
    flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt5Core'],text=True,env=environment))
    include,definitions=prepare_source(stage,environment,prefix)
    provenance=prepare_server_originals(stage)
    binary=stage/'assets-server-state'
    subprocess.run(['c++','-std=c++17','-fPIC','-UNDEBUG','-fmax-errors=3',*definitions,*include,
        str(HERE/'assets-server-state-native.cpp'),str(stage/'MappingRequest.cpp'),str(stage/'AssetRequest.cpp'),
        str(stage/'MappingRequest-moc.cpp'),str(stage/'AssetRequest-moc.cpp'),'-o',str(binary),'-L'+str(prefix/'usr/lib64'),*flags],
        check=True,timeout=90,env=environment)
    return binary,environment,provenance


class AssetsServerStateTests(unittest.TestCase):
    def test_original_server_status_meta_disk_and_actual_client_request_source(self):
        with tempfile.TemporaryDirectory(prefix='pico-assets-server-state-') as temporary:
            binary,environment,provenance=build(temporary)
            result=subprocess.run([str(binary),str(ROOT/'interface/resources/serverless/Models/standAngle.fbx'),'--testScript'],
                check=True,timeout=10,env=environment,capture_output=True,text=True)
            originals=json.loads(result.stdout);self.assertEqual(5,len(originals));previous=None;pid=None
            for frame in originals:
                packet=frame['clientOriginal'];pid=packet['processId'] if pid is None else pid;self.assertEqual(pid,packet['processId'])
                request=dict(schemaVersion=1,commandId=packet['requestId'],runId=packet['runId'],action='feature-pico-assets-observe')
                validate(packet,request,pid,packet['capturedEpochMs'])
                if previous is not None:
                    self.assertEqual(previous['instance'],packet['instance']);self.assertGreater(packet['sequence'],previous['sequence'])
                previous=packet
            first=originals[0]['serverFiles'];self.assertTrue(all(row['exists'] and row['hash']==row['sha256'] and row['bytes']>0 for row in first))
            expected=hashlib.sha256((ROOT/'interface/resources/serverless/Models/standAngle.fbx').read_bytes()).hexdigest()
            self.assertIn(expected,{row['hash'] for row in first});missing={row['hash'] for row in originals[1]['serverFiles'] if not row['exists']}
            self.assertEqual({expected},missing)
            self.assertTrue(any(not row['exists'] for row in originals[2]['serverFiles']))
            # Raw originals/body hashes stay available in a caller-owned private
            # evidence directory. They do not become fabricated oven receipts.
            destination=os.environ.get('OVERTE_ASSETS_SERVER_EVIDENCE')
            if destination is not None:
                from adapters.normal_feature_state import PrivateFeatureState
                from adapters.script_journey.history import pack
                directory=Path(destination).resolve(strict=True)
                PrivateFeatureState(directory/'server-state-originals.json').write(dict(serverHostEvidenceVersion=1,
                    nativeStdout=result.stdout,nativeStdoutSha256=hashlib.sha256(result.stdout.encode()).hexdigest(),
                    originalBodies=provenance,binarySha256=hashlib.sha256(binary.read_bytes()).hexdigest(),originals=pack(originals)),None)


if __name__=='__main__':unittest.main()
