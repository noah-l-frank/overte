"""Complete original mapping model, proxy constructor and original role strings."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import json
from pathlib import Path
import subprocess
from test_assets_read_native import ROOT,HERE,original


def prepare(stage,environment,prefix):
    stage=Path(stage);header=(ROOT/'interface/src/scripting/AssetMappingsScriptingInterface.h').read_text()
    start=header.index('class AssetMappingModel :');end=header.index('Q_DECLARE_METATYPE(AssetMappingModel*)',start)+len('Q_DECLARE_METATYPE(AssetMappingModel*)')
    declaration=header[start:end]
    (stage/'AssetsMappingModel.h').write_text('#pragma once\n#include <QStandardItemModel>\n#include <QTimer>\n#include <QHash>\n'+declaration+'\n')
    source=(ROOT/'interface/src/scripting/AssetMappingsScriptingInterface.cpp').read_text()
    signatures=('AssetMappingModel::AssetMappingModel(', 'bool AssetMappingModel::isAutoRefreshEnabled(',
        'void AssetMappingModel::setAutoRefreshEnabled(', 'bool AssetMappingModel::isKnownFolder(',
        'void AssetMappingModel::refresh(', 'void AssetMappingModel::clear(', 'void AssetMappingModel::setupRoles(',
        'AssetMappingsScriptingInterface::AssetMappingsScriptingInterface(')
    bodies={signature:original(source,signature) for signature in signatures}
    interval=next(line for line in source.splitlines() if line.startswith('static const int AUTO_REFRESH_INTERVAL ='))
    registration=next(line for line in source.splitlines() if line.startswith('int assetMappingModelMetatypeId ='))
    utils=(ROOT/'libraries/networking/src/AssetUtils.cpp').read_text();status=original(utils,'QString bakingStatusToString(')
    (stage/'AssetsMappingOriginals.inc').write_text(interval+'\n'+registration+'\nnamespace AssetUtils {\n'+status+'\n}\n'+'\n'.join(bodies.values()))
    provenance={name:hashlib.sha256(value.encode()).hexdigest() for name,value in bodies.items()}
    provenance.update(declaration=hashlib.sha256(declaration.encode()).hexdigest(),bakingStatusToString=hashlib.sha256(status.encode()).hexdigest(),
        interval=hashlib.sha256(interval.encode()).hexdigest(),registration=hashlib.sha256(registration.encode()).hexdigest())
    (stage/'mapping-original-provenance.json').write_text(json.dumps(provenance,sort_keys=True))
    output=stage/'mapping-model-moc.cpp'
    subprocess.run([str(prefix/'usr/lib64/qt5/bin/moc'),str(stage/'AssetsMappingModel.h'),'-o',str(output)],check=True,timeout=20,env=environment)
    return ['-DASSETS_ORIGINAL_MAPPING_MODEL',str(output)]
