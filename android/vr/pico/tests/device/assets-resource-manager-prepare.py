"""Original URL normalization and ResourceManager factory, explicit startup seam."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import json
from pathlib import Path
from test_assets_read_native import ROOT,original


def prepare(stage,*,resource_data=False):
    stage=Path(stage);source=(ROOT/'libraries/networking/src/ResourceManager.cpp').read_text()
    signatures=('QString ResourceManager::normalizeURL(', 'const QSet<QString>& getKnownUrls(',
        'QUrl ResourceManager::normalizeURL(', 'ResourceRequest* ResourceManager::createResourceRequest(')
    bodies={signature:original(source,signature) for signature in signatures}
    constants=(ROOT/'libraries/networking/src/NetworkingConstants.h').read_text()
    lines='\n'.join(next(line for line in constants.splitlines() if line.startswith('const QString '+name+' =')) for name in
        ('URL_SCHEME_QRC','HIFI_URL_SCHEME_FILE','HIFI_URL_SCHEME_HTTP','HIFI_URL_SCHEME_HTTPS','HIFI_URL_SCHEME_FTP'))
    compiled='\n'.join(bodies.values())
    if resource_data:
        compiled=compiled.replace('ResourceRequest* ResourceManager::createResourceRequest(',
            'ResourceRequest* ResourceManager::createOriginalResourceRequest(',1)
    (stage/'AssetsResourceManagerOriginals.inc').write_text(lines+'\n'+compiled)
    provenance={name:hashlib.sha256(body.encode()).hexdigest() for name,body in bodies.items()}
    provenance['networking-scheme-constants']=hashlib.sha256(lines.encode()).hexdigest()
    if resource_data:provenance['factory-delegate-compilation']=hashlib.sha256(compiled.encode()).hexdigest()
    (stage/'resource-manager-original-provenance.json').write_text(json.dumps(provenance,sort_keys=True))
    return ['-DASSETS_ORIGINAL_RESOURCE_MANAGER_FACTORY','-pthread']
