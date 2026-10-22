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
from adapters.native_script_compilations import validate as compiled_packet

PINS=Path(__file__).resolve().parents[1]/'feature_journeys/emote-source-pins.v1.json'
MANAGER_PINS=PINS.with_name('phone-emote-manager-pins.v1.json')
VERSION=3
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


def manager_pins(path=MANAGER_PINS):
    value=json.loads(Path(path).read_text());exact(value,{'contractVersion','managers'})
    need(type(value['contractVersion']) is int and value['contractVersion']==1
        and type(value['managers']) is list and len(value['managers'])==1)
    row=value['managers'][0]
    exact(row,{'id','sourcePath','runtimePath','sourceBase','encoding','codeUnits','sha256','includedProfiles'})
    need(row['id']=='phone-default-includes-v1' and row['sourcePath']=='scripts/+android_phoneInterface/defaultScripts.js'
        and row['runtimePath']=='defaultScripts.js' and type(row['sourceBase']) is str and re.fullmatch('[0-9a-f]{40}',row['sourceBase'])
        and row['encoding']=='utf-16le-code-units' and integer(row['codeUnits'],1,4194304)
        and type(row['sha256']) is str and re.fullmatch('[0-9a-f]{64}',row['sha256'])
        and row['includedProfiles']==['phone-one-shot-hide-v1'])
    return deepcopy(value['managers'])


def compiled_source(value,engine,physical,code,*,after_epoch):
    need(type(value['source'].get('compiledSourceVersion')) is int and value['source']['compiledSourceVersion']==1)
    inventory=engine.get('compiled');compiled_packet(inventory,value['capturedEpochMs']);need(inventory['complete'])
    # A top-level manager may retain its actual normalized key as V8 resource
    # name. Included files are evaluated with their actual resolved URL.
    names={physical}
    if physical==code.get('assignedUrl'):names.add(engine['url'])
    rows=[row for row in inventory['compilations'] if row['resourceName'] in names]
    need(len(rows)==1 and rows[0]['compiledEpochMs']>=after_epoch
        and all(rows[0][key]==code[key] for key in ('encoding','codeUnits','sha256')))
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
    candidates=[];managers=manager_pins() if assigned else [];unrelated=set()
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
                if assigned and value['source'].get('compiledSourceVersion')==1:
                    selected.update(sourceUrl=physical,compilation=compiled_source(value,engine,physical,
                        dict(code,assignedUrl=original['url']),after_epoch=code['submittedEpochMs']))
                candidates.append(selected)
    known=set().union(*(urls(source)[1] for source in PATHS))
    for manager in managers:
        physical,options=urls('scripts/'+manager['runtimePath']);known|=options
        for engine in value['source']['engines']:
            if engine['url'] not in options or not engine['running'] or engine['stopping'] or engine['finished']:continue
            code=submitted_source(value,engine['url']);original=assignment(value,engine)
            need(original['url']==physical and original['assignedEpochMs']<=code['submittedEpochMs'])
            if not all(code[key]==manager[key] for key in ('encoding','codeUnits','sha256')):
                # Pico loads Emote separately. Its real default manager remains
                # in the same Script inventory. Prove the actual compiled top
                # code and complete absence of reviewed Emote origins there;
                # an unknown default filename alone cannot be ignored.
                compiled_source(value,engine,physical,dict(code,assignedUrl=original['url']),after_epoch=code['submittedEpochMs'])
                inventory=engine['compiled'];paths={profile['sourcePath'] for profile in reviewed if profile['id'] in manager['includedProfiles']}
                included=[profile for profile in reviewed if profile['sourcePath'] in paths]
                names={urls(profile['sourcePath'])[0] for profile in included}
                if not any(row['resourceName'] in names or any(
                        all(row[key]==profile[key] for key in ('encoding','codeUnits','sha256')) for profile in included)
                        for row in inventory['compilations']):
                    unrelated.add(engine['required']['instance'])
                continue
            top=compiled_source(value,engine,physical,dict(code,assignedUrl=original['url']),after_epoch=code['submittedEpochMs'])
            for profile in reviewed:
                if profile['id'] not in manager['includedProfiles']:continue
                included,_options=urls(profile['sourcePath'])
                source=compiled_source(value,engine,included,profile,after_epoch=top['compiledEpochMs'])
                need(source['scriptId']!=top['scriptId'])
                candidates.append(dict(profile=deepcopy(profile),url=engine['url'],engineInstance=engine['required']['instance'],code=code,
                    assignedUrl=original['url'],loadGeneration=original['loadGeneration'],assignedEpochMs=original['assignedEpochMs'],
                    sourceUrl=source['resourceName'],compilation=source,managerProfile=deepcopy(manager),managerCompilation=top))
    active_urls={engine['url'] for engine in value['source']['engines'] if engine['running']
        and not engine['stopping'] and not engine['finished'] and engine['url'] in known
        and engine['required']['instance'] not in unrelated}
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
