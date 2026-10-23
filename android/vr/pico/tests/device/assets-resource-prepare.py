"""Original ATP resource requests; physical-file and transport endpoints declared."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import json
from pathlib import Path
import subprocess
from test_assets_read_native import ROOT,HERE,original


def prepare(stage,environment,prefix):
    stage=Path(stage);network=ROOT/'libraries/networking/src';provenance={}
    for name in ('ResourceRequest.h','AssetResourceRequest.h','AssetResourceRequest.cpp','FeatureAssetRequestBirth.h'):
        data=(network/name).read_bytes();(stage/name).write_bytes(data);provenance[name]=hashlib.sha256(data).hexdigest()
    source=(network/'ResourceRequest.cpp').read_text()
    signatures=('QString ResourceRequest::toHttpDateString(', 'void ResourceRequest::send(',
        'QString ResourceRequest::getResultString(', 'void ResourceRequest::recordBytesDownloadedInStats(')
    bodies={signature:original(source,signature) for signature in signatures}
    (stage/'AssetsResourceOriginals.inc').write_text('\n'.join(bodies.values()))
    provenance.update({name:hashlib.sha256(body.encode()).hexdigest() for name,body in bodies.items()})
    server=(ROOT/'assignment-client/src/assets/AssetServer.cpp').read_text();mapping=original(server,'void AssetServer::handleGetMappingOperation(')
    (stage/'AssetsServerMappingOriginal.inc').write_text(mapping);provenance['AssetServer::handleGetMappingOperation']=hashlib.sha256(mapping.encode()).hexdigest()
    (stage/'resource-original-provenance.json').write_text(json.dumps(provenance,sort_keys=True))
    (stage/'StatTracker.h').write_text('#include "assets-resource-stat-host.h"\n')
    (stage/'Profile.h').write_text('// Explicit unused profiling endpoint.\n')
    logging=stage/'NetworkLogging.h';logging.write_text(logging.read_text()+'\nQ_DECLARE_LOGGING_CATEGORY(networking)\n')
    arguments=['-DASSETS_ORIGINAL_RESOURCE_READ',str(stage/'AssetResourceRequest.cpp')]
    for name in ('ResourceRequest','AssetResourceRequest'):
        output=stage/(name+'-moc.cpp')
        subprocess.run([str(prefix/'usr/lib64/qt5/bin/moc'),'-I'+str(stage),str(stage/(name+'.h')),'-o',str(output)],check=True,timeout=20,env=environment)
        arguments.append(str(output))
    return arguments
