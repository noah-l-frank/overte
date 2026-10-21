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
             and re.fullmatch('[0-9a-f]{40}',row['sourceBase']) is not None
             and row['encoding']=='utf-16le-code-units' and integer(row['codeUnits'],1,4194304)
             and type(row['sha256']) is str and re.fullmatch('[0-9a-f]{64}',row['sha256']) is not None
             and row['ui'] in ('native-qml','tablet-web') and row['chooserAfterPlay'] in ('hidden','retained'))
        seen.add(row['id'])
    need(seen==PROFILES)
    return value['profiles']


def assignment(value, engine):
    from adapters.native_script_membership import validate as membership_packet
    source=value['source']
    need(type(source.get('membershipSourceVersion')) is int and source['membershipSourceVersion']==1)
    membership=source.get('membership');membership_packet(membership,value['capturedEpochMs']);need(membership['complete'])
    rows=[row for row in membership['managers'] if row['instance']==engine['required']['instance']]
    need(len(rows)==1 and rows[0]['assigned'])
    return deepcopy(rows[0])


def select(value, installed_scripts_root, *, reviewed=None):
    return _select(value,installed_scripts_root,reviewed=reviewed,assigned=False)


def _select(value, installed_scripts_root, *, reviewed, assigned):
    # Root must come from actual application configuration. A normalized ~
    # table key alone never proves which local file was assigned to that manager.
    need(type(installed_scripts_root) is str and len(installed_scripts_root)<=4096)
    root=urlsplit(installed_scripts_root);path=unquote(root.path,errors='strict')
    need(root.scheme in ('qrc','file') and not root.netloc and not root.query and not root.fragment
         and root.path==path and path.startswith('/') and path.endswith('/scripts/')
         and '\\' not in path and not any(part in ('.','..') for part in path.split('/')))
    reviewed=pins() if reviewed is None else pins(reviewed)
    def urls(source_path):
        suffix=source_path[len('scripts/'):]
        physical='qrc:'+root.path+suffix if root.scheme=='qrc' else urlunsplit(('file','',root.path+suffix,'',''))
        options={physical}
        if assigned and root.scheme=='file':options.add('file:///~//'+suffix)
        return physical,options
    candidates=[]
    for profile in reviewed:
        physical,options=urls(profile['sourcePath'])
        rows=[engine for engine in value['source']['engines'] if engine['url'] in options
              and engine['running'] and not engine['stopping'] and not engine['finished']]
        for engine in rows:
            code=submitted_source(value,engine['url']);original=None
            if assigned:
                original=assignment(value,engine)
                need(original['url']==physical and original['assignedEpochMs']<=code['submittedEpochMs'])
            if all(code[key]==profile[key] for key in ('encoding','codeUnits','sha256')):
                selected=dict(profile=deepcopy(profile),url=engine['url'],engineInstance=engine['required']['instance'],code=code)
                if original is not None:selected.update(assignedUrl=original['url'],loadGeneration=original['loadGeneration'],assignedEpochMs=original['assignedEpochMs'])
                candidates.append(selected)
    known=set().union(*(urls(source)[1] for source in PATHS))
    active_urls={engine['url'] for engine in value['source']['engines'] if engine['running']
        and not engine['stopping'] and not engine['finished'] and engine['url'] in known}
    need(active_urls=={candidate['url'] for candidate in candidates} and len(candidates)==1)
    return candidates[0]


def select_from_roots(value, before, after, *, pid, epoch, reviewed=None):
    """Join actual application roots around original submitted engine code.

    This selects input semantics only. It supplies no Rig/pose/UI/pixel facts.
    The owning reader must durably retain all three originals and their cursors.
    """
    from adapters.native_script_roots import validate as roots_packet,root_url
    from adapters.native_script_observation import validate as scripts_packet
    from adapters.native_feature_observation import fresh
    need(type(value) is dict and type(before) is dict and type(after) is dict
        and type(value.get('requestId')) is str and re.fullmatch(r'(?:ios-)?[0-9a-f]{32}',value['requestId']))
    for packet in (before,after):
        roots_packet(packet,dict(schemaVersion=1,commandId=packet.get('commandId'),
            action='feature-script-roots-observe'),pid,epoch)
    roots_packet(after,dict(schemaVersion=1,commandId=after['commandId'],action='feature-script-roots-observe'),
        pid,epoch,previous=before)
    scripts_packet(value,value.get('requestId'),pid,epoch)
    need(before['instance']==value['instance']==after['instance']
        and before['requestedEpochMs']<=before['capturedEpochMs']<=value['requestedEpochMs']
        <=value['capturedEpochMs']<=after['requestedEpochMs']<=after['capturedEpochMs']
        and after['capturedEpochMs']-before['requestedEpochMs']<=1500)
    fresh(before['requestedEpochMs'],epoch)
    return _select(value,root_url(before['source']['defaultScriptsUrl']),reviewed=reviewed,assigned=True)
