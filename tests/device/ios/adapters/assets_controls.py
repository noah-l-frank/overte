"""Original iOS Assets/picker controls and retained native weak roots.

These UI facts are neither AssetServer hashes nor upload/bake/model evidence.
Normal input still needs its candidate/process guard and once-only caller WAL.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
from urllib.parse import unquote,urlsplit
import uuid
from adapters.native_feature_observation import exact,integer,need,number
from adapters.script_feature.history import same

VERSION=1
IDS=frozenset(('assets.menu','assets.open','assets.upload','assets.home','asset-file.folder','asset-file.select','asset-file.cancel'))
SUFFIXES=dict(menu='/hifi/tablet/TabletMenuItem.qml',page='/hifi/dialogs/TabletAssetServer.qml',picker='/dialogs/NativeFileBrowser.qml')


def identity(value):
    need(type(value) is str)
    parsed=uuid.UUID(value);need(parsed.int!=0 and str(parsed)==value)


def text(value,limit=4096):
    need(type(value) is str and len(value)<=limit and all(ord(char)>=32 and ord(char)!=127 for char in value));return value


def local(value):
    text(value);url=urlsplit(value);path=unquote(url.path)
    need(url.scheme=='file' and not url.netloc and not url.query and not url.fragment
        and path.startswith('/') and '\x00' not in path and not any(part in ('.','..') for part in path.split('/')))
    return path


def source(value,role):
    text(value);url=urlsplit(value)
    need(role in SUFFIXES and url.scheme in ('file','qrc') and not url.netloc and not url.query and not url.fragment
        and url.path.endswith(SUFFIXES[role]) and not any(part in ('.','..') for part in unquote(url.path).split('/')))


def control_id(value):
    from ios.adapters.assets_bundle_controls import IDS as BUNDLE_IDS
    from ios.adapters.assets_tree_controls import control_id as tree_control
    from ios.adapters.assets_usage_controls import control_id as usage_control
    return type(value) is str and (value in IDS or value in BUNDLE_IDS or tree_control(value) or usage_control(value) or re.fullmatch(r'asset-file\.row\.(?:0|[1-9][0-9]{0,3})',value) is not None)


def metadata(value):
    need(type(value) is dict and control_id(value.get('controlId')))
    if type(value.get('assetControlVersion')) is int and value['assetControlVersion']==4:
        from ios.adapters.assets_usage_controls import metadata as usage_metadata
        return usage_metadata(value)
    if type(value.get('assetControlVersion')) is int and value['assetControlVersion']==3:
        from ios.adapters.assets_tree_controls import metadata as tree_metadata
        return tree_metadata(value)
    if type(value.get('assetControlVersion')) is int and value['assetControlVersion']==2:
        from ios.adapters.assets_bundle_controls import metadata as bundle_metadata
        return bundle_metadata(value)
    need(value['controlId'] in IDS or re.fullmatch(r'asset-file\.row\.(?:0|[1-9][0-9]{0,3})',value['controlId']) is not None)
    role=value.get('role');exact(value,{'assetControlVersion','role','rootId','windowId','componentSource','controlId'}
        | ({'sourceType','labelSha256'} if role=='menu' else {'ownerRootId','rowUrl','fieldText','navigationSource'}))
    need(type(value['assetControlVersion']) is int and value['assetControlVersion']==VERSION)
    for key in ('rootId','windowId'):identity(value[key])
    source(value['componentSource'],role)
    if role=='menu':
        need(value['controlId'] in ('assets.menu','assets.open') and type(value['sourceType']) is int
            and value['sourceType']==(2 if value['controlId']=='assets.menu' else 1)
            and type(value['labelSha256']) is str and re.fullmatch('[a-f0-9]{64}',value['labelSha256']))
    else:
        identity(value['ownerRootId']);text(value['rowUrl']);text(value['fieldText'])
        need((role=='picker')==value['controlId'].startswith('asset-file.'))
        if value['controlId'].startswith('asset-file.row.'):local(value['rowUrl'])
        else:need(value['rowUrl']=='')
        if value['controlId']!='asset-file.folder':need(value['fieldText']=='')
        text(value['navigationSource'])
        if value['controlId']=='assets.home':
            url=urlsplit(value['navigationSource']);need(url.scheme in ('file','qrc') and not url.netloc and not url.query and not url.fragment
                and url.path.endswith('/hifi/tablet/TabletNavigation.qml'))
        else:need(value['navigationSource']=='')
    return value


def inventory(value,*,pid=None):
    exact(value,{'iosAssetUiInventoryVersion','available','complete','instance','sequence','capturedEpochMs','processId','roots'})
    need(type(value['iosAssetUiInventoryVersion']) is int and value['iosAssetUiInventoryVersion']==VERSION
        and all(type(value[key]) is bool for key in ('available','complete')) and integer(value['sequence'],1)
        and integer(value['capturedEpochMs'],1) and integer(value['processId'],1)
        and (pid is None or value['processId']==pid) and type(value['roots']) is list and len(value['roots'])<=128)
    identity(value['instance']);seen=set();pages=set()
    for row in value['roots']:
        role=row.get('role');need(role in ('page','picker') and type(row.get('alive')) is bool)
        extra=set() if not row['alive'] else {'windowId','visible'}|({'directory','chosen','closing','requestId','error','bundleReview'}
            if role=='picker' else {'busy','bundleRequest','status','canWrite','selectedPath','selectedUrl','modelId','modelRevision','pendingBundle','destinationOpen'})
        exact(row,{'rootId','role','componentSource','ownerRootId','firstObservedEpochMs','alive'}|extra)
        identity(row['rootId']);identity(row['ownerRootId']);source(row['componentSource'],role)
        need(row['rootId'] not in seen and integer(row['firstObservedEpochMs'],1,value['capturedEpochMs']))
        seen.add(row['rootId'])
        if role=='page':need(row['ownerRootId']==row['rootId']);pages.add(row['rootId'])
        if not row['alive']:continue
        need(type(row['visible']) is bool)
        if row['windowId'] is not None:identity(row['windowId'])
        if role=='picker':
            local(row['directory']);need(type(row['chosen']) is list and len(row['chosen'])<=32 and len(set(row['chosen']))==len(row['chosen']))
            for selected in row['chosen']:local(selected)
            need(type(row['closing']) is type(row['bundleReview']) is bool);text(row['error'])
            if row['requestId']!='':identity(row['requestId'])
        else:
            need(all(type(row[key]) is bool for key in ('busy','canWrite','pendingBundle','destinationOpen')) and integer(row['modelRevision']))
            for key in ('status','selectedPath','selectedUrl'):text(row[key])
            if row['bundleRequest']!='':identity(row['bundleRequest'])
            if row['modelId'] is not None:identity(row['modelId'])
            elif value['complete']:need(False)
    if value['complete']:need(all(row['ownerRootId'] in pages for row in value['roots']))
    return value


def folder(value):
    text(value)
    need(re.fullmatch(r'/(?:[^/\x00-\x1f]+/)*feature-assets-[a-f0-9]{32}-[a-f0-9]{16}',value)
        and not any(part in ('.','..') for part in value.split('/')))
    return value


def project(value):
    need(type(value.get('assetControlsVersion')) is int and value['assetControlsVersion']==VERSION)
    original=inventory(value['assetInventory'],pid=value['processId']);need(original['available'] and original['complete'])
    scope={key:value[key] for key in ('processId','instance','sampleEpochMs','elapsedMs','lastSequence')}
    rows=[]
    for row in value['controls']:
        if not control_id(row.get('id')):continue
        need(row['assetControl']['controlId']==row['id']);metadata(row['assetControl']);rows.append(deepcopy(row))
    return dict(iosAssetControlsVersion=VERSION,scope=deepcopy(scope),controls=rows,inventory=deepcopy(original))


def same_reference(reference,current,identifier):
    exact(reference,{'iosAssetControlsVersion','scope','controls','inventory'});exact(current,set(reference))
    need(reference['iosAssetControlsVersion']==current['iosAssetControlsVersion']==VERSION and control_id(identifier))
    a,b=reference['scope'],current['scope']
    need(all(a[key]==b[key] for key in ('processId','instance','lastSequence'))
        and 0<=b['sampleEpochMs']-a['sampleEpochMs']<1500 and 0<=b['elapsedMs']-a['elapsedMs']<1500)
    old=[row for row in reference['controls'] if row['id']==identifier];new=[row for row in current['controls'] if row['id']==identifier]
    need(len(old)==len(new)==1 and same(old[0],new[0]));metadata(new[0]['assetControl'])
    return deepcopy(new[0])
