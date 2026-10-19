"""Select input semantics from actual submitted bundled source, not platform."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit, urlunsplit
from adapters.native_feature_observation import exact, integer, need
from adapters.native_script_observation import submitted_source

PINS=Path(__file__).resolve().parents[1]/'feature_journeys/emote-source-pins.v1.json'
PROFILES={'phone-one-shot-hide-v1','touch-one-shot-chooser-v1','tablet-one-shot-sit-hold-v1'}
PATHS={'scripts/system/+android_phoneInterface/phoneEmote.js','scripts/system/emote.js'}


def pins(path=PINS):
    value=json.loads(Path(path).read_text())
    exact(value,{'contractVersion','profiles'})
    need(type(value['contractVersion']) is int and value['contractVersion']==1
         and type(value['profiles']) is list and len(value['profiles'])==3)
    seen=set()
    for row in value['profiles']:
        exact(row,{'id','sourcePath','sourceBase','encoding','codeUnits','sha256','ui','chooserAfterPlay'})
        need(type(row['id']) is str and row['id'] in PROFILES and row['id'] not in seen
             and type(row['sourcePath']) is str and row['sourcePath'] in PATHS and type(row['sourceBase']) is str
             and re.fullmatch('[0-9a-f]{10,40}',row['sourceBase']) is not None
             and row['encoding']=='utf-16le-code-units' and integer(row['codeUnits'],1,4194304)
             and type(row['sha256']) is str and re.fullmatch('[0-9a-f]{64}',row['sha256']) is not None
             and row['ui'] in ('native-qml','tablet-web') and row['chooserAfterPlay'] in ('hidden','retained'))
        seen.add(row['id'])
    need(seen==PROFILES)
    return value['profiles']


def select(value, installed_scripts_root, *, reviewed=None):
    # Root must come from the existing actual installed-candidate resource
    # binding. This helper never infers it from a script URL or filesystem scan.
    need(type(installed_scripts_root) is str and len(installed_scripts_root)<=4096)
    root=urlsplit(installed_scripts_root)
    path=unquote(root.path,errors='strict')
    need(root.scheme in ('qrc','file') and not root.netloc and not root.query and not root.fragment
         and root.path==path and path.startswith('/') and path.endswith('/scripts/')
         and '\\' not in path and not any(part in ('.','..') for part in path.split('/')))
    reviewed=pins() if reviewed is None else pins(reviewed)
    candidates=[]
    for profile in reviewed:
        resource=root.path+profile['sourcePath'][len('scripts/'):]
        url=urlunsplit((root.scheme,'',resource,'',''))
        # Qt canonical qrc spelling is qrc:/scripts/... rather than qrc:///.
        if root.scheme=='qrc':url='qrc:'+resource
        rows=[engine for engine in value['source']['engines'] if engine['url']==url
              and engine['running'] and not engine['stopping'] and not engine['finished']]
        if rows:
            code=submitted_source(value,url)
            if all(code[key]==profile[key] for key in ('encoding','codeUnits','sha256')):
                candidates.append(dict(profile=deepcopy(profile),url=url,
                    engineInstance=rows[0]['required']['instance'],code=code))
    # A running source at a known startup URL must match exactly one reviewed
    # profile. Unknown code cannot fall through to a basename/platform guess.
    active_urls={engine['url'] for engine in value['source']['engines'] if engine['running']
        and not engine['stopping'] and not engine['finished'] and engine['url'] in {
            ('qrc:' if root.scheme=='qrc' else 'file://')+root.path+p[len('scripts/'):]
            for p in PATHS}}
    need(active_urls=={candidate['url'] for candidate in candidates})
    # Multiple known startup surfaces are ambiguous even if their labels match.
    need(len(candidates)==1)
    return candidates[0]
