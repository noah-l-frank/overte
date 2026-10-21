"""Join original executable membership and world probe to fixed admission pins.

Pins are expectations from a reviewed repository commit. All returned identities
and domain facts remain the independent original source/probe values.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
from pathlib import Path
import re
from urllib.parse import urlsplit
from uuid import UUID

from adapters.emote_source_profile import select_from_roots
from adapters.native_feature_observation import exact,fresh,integer,need
from adapters.native_script_roots import root_url
from contracts import validate_probe_snapshot

VERSION=1
PINS=Path(__file__).resolve().parents[1]/'feature_journeys/phone-emote-admission-pins.v1.json'
KEYS=('encoding','codeUnits','sha256')
MANAGERS={'defaultScripts.js','system/create/edit.js','system/snapshot.js',
    'communityScripts/armored-chat/armored_chat.js','communityScripts/chatBubbles/chatBubbles.js',
    'communityScripts/notificationCore/notificationCore.js'}


def pin(value):
    need(value['encoding']=='utf-16le-code-units' and integer(value['codeUnits'],1,4194304)
        and type(value['sha256']) is str and re.fullmatch('[0-9a-f]{64}',value['sha256']))


def catalog(path=PINS):
    value=json.loads(Path(path).read_text());exact(value,{'phoneEmoteAdmissionCatalogVersion','sourceBase','managers','files','probe','native'})
    need(type(value['phoneEmoteAdmissionCatalogVersion']) is int and value['phoneEmoteAdmissionCatalogVersion']==VERSION
        and type(value['sourceBase']) is str and re.fullmatch('[0-9a-f]{40}',value['sourceBase'])
        and type(value['managers']) is list and len(value['managers'])==len(MANAGERS) and set(value['managers'])==MANAGERS
        and type(value['files']) is list and 1<=len(value['files'])<=1024)
    seen=set()
    for row in value['files']:
        exact(row,{'path','runtimePath','kind',*KEYS});pin(row)
        for name in ('path','runtimePath'):
            need(type(row[name]) is str and re.fullmatch(r'[A-Za-z0-9_+./ -]+',row[name])
                and not row[name].startswith('/') and all(part not in ('','..','.') for part in row[name].split('/')))
        need(row['path'].startswith('scripts/') and row['kind'] in ('script','json-module') and row['runtimePath'] not in seen)
        seen.add(row['runtimePath'])
    need(MANAGERS<=seen)
    probe=value['probe'];exact(probe,{'path',*KEYS});pin(probe);need(probe['path']=='tests/device/probe/overte_e2e_probe.js')
    need(type(value['native']) is list and len(value['native'])==1)
    for row in value['native']:
        exact(row,{'resourceName',*KEYS});pin(row);need(row['resourceName']=='(boundRequire)')
    return deepcopy(value)


def policy(value):
    exact(value,{'domainUrl','domainId','domainMarkers','probeUrl'})
    url=value['domainUrl'];need(type(url) is str and 1<=len(url)<=2048 and all(32<ord(c)<127 for c in url))
    parsed=urlsplit(url);need(parsed.scheme=='hifi' and parsed.hostname and parsed.port is not None
        and 1<=parsed.port<=65535 and parsed.username is None and parsed.password is None
        and not parsed.query and not parsed.fragment)
    need(type(value['domainId']) is str and str(UUID(value['domainId']))==value['domainId'] and UUID(value['domainId']).int!=0)
    markers=value['domainMarkers'];need(type(markers) is list and 1<=len(markers)<=32 and markers==sorted(set(markers))
        and all(type(item) is str and re.fullmatch('OVERTE_E2E_DOMAIN_[A-Z]+',item) for item in markers))
    allowed={'file:///data/'+prefix+'/io.github.noah_be.overte.phone/files/overte-e2e/overte_e2e_probe.js'
        for prefix in ('user/0','data')}
    need(value['probeUrl'] in allowed);return deepcopy(value)


def relative(value,root):
    need(type(value) is str and not any(char in value for char in ('?','#','%','\\')))
    if value.startswith(root):path=value[len(root):]
    else:
        need(root.startswith('file:') and value.startswith('file:///~//'));path=value[len('file:///~//'):]
    need(path and not path.startswith('/') and all(part not in ('','..','.') for part in path.split('/')))
    return path


def same_pin(actual,expected):need(all(actual[key]==expected[key] for key in KEYS))


def executable(group,*,pid,epoch,probe_url,pins_path=PINS):
    selected=select_from_roots(group['script'],group['rootsBefore'],group['rootsAfter'],pid=pid,epoch=epoch)
    need('managerProfile' in selected and selected['profile']['id']=='phone-one-shot-hide-v1')
    pins=catalog(pins_path);files={row['runtimePath']:row for row in pins['files']}
    helpers={row['resourceName']:row for row in pins['native']};root=root_url(group['rootsBefore']['source']['defaultScriptsUrl'])
    source=group['script']['source'];members=source['membership']['managers'];engines=source['engines']
    need(source['membership']['complete'] and {row['instance'] for row in members}=={row['required']['instance'] for row in engines})
    seen=set();proof=[];probe=None
    for engine in engines:
        need(engine['running'] and not engine['stopping'] and not engine['finished'])
        manager=next(row for row in members if row['instance']==engine['required']['instance']);need(manager['assigned'])
        if manager['url']==probe_url:
            name='probe';expected=pins['probe'];need(engine['url']==probe_url);probe=engine
        else:
            name=relative(manager['url'],root);need(name in MANAGERS and manager['url']==root+name
                and relative(engine['url'],root)==name);expected=files[name]
        need(name not in seen);seen.add(name)
        code=engine['code'];need(code['submitted'] and manager['assignedEpochMs']<=code['submittedEpochMs']);same_pin(code,expected)
        compiled=engine['compiled'];need(compiled['complete'])
        top=[row for row in compiled['compilations'] if row['resourceName'] in (manager['url'],engine['url'])
            and all(row[key]==code[key] for key in KEYS) and row['compiledEpochMs']>=code['submittedEpochMs']]
        need(top)
        for row in compiled['compilations']:
            resource=row['resourceName']
            if resource in helpers:expected_source=helpers[resource]
            elif resource==probe_url:need(name=='probe');expected_source=pins['probe']
            else:expected_source=files.get(relative(resource,root));need(expected_source is not None)
            same_pin(row,expected_source)
        for module in engine['required']['modules']:
            # cached reports whether that last require was a cache HIT, not
            # whether successful first instantiation left a cached module.
            path=relative(module['url'],root);need(module['loaded'] and path in files)
            originals=[row for row in compiled['compilations'] if row['resourceName'] not in helpers and row['resourceName']!=probe_url
                and relative(row['resourceName'],root)==path and row['compiledEpochMs']<=module['capturedEpochMs']]
            need(originals) # A loaded require event cannot replace its actual compilation.
        proof.append(dict(manager=deepcopy(manager),code=deepcopy(code),compiled=deepcopy(compiled)))
    need('defaultScripts.js' in seen and 'probe' in seen)
    return selected,probe,proof


def world(probe,expected,*,epoch,after_sequence=0,after_epoch=0):
    expected=policy(expected);validate_probe_snapshot(probe);fresh(probe['sampleEpochMs'],epoch)
    need(integer(probe['sampleSequence'],after_sequence+1) and probe['sampleEpochMs']>=after_epoch
        and probe['application']==dict(running=True,foreground=True))
    domain=probe['domain'];scene=probe['scene'];parsed=urlsplit(expected['domainUrl'])
    need(domain['connected'] and not domain['serverless'] and domain['protocol']=='hifi'
        and str(UUID(domain['id'].strip('{}')))==expected['domainId'] and domain['hostname'].lower()==parsed.hostname.lower()
        and scene['ready'] and scene['domainMarkers']==expected['domainMarkers']
        and scene['domainMarkerCount']==len(expected['domainMarkers'])
        and not set(scene['domainMarkers'])&set(scene['fixtureMarkers'])
        and scene['entityCount']>=scene['domainMarkerCount']+scene['fixtureMarkerCount'])
    actual=urlsplit(scene['url']);need(actual.scheme=='hifi' and actual.hostname==parsed.hostname and actual.port==parsed.port
        and actual.username is None and actual.password is None and not actual.query and not actual.fragment)
    return dict(domain=deepcopy(domain),scene=deepcopy(scene),sampleSequence=probe['sampleSequence'],sampleEpochMs=probe['sampleEpochMs'])
