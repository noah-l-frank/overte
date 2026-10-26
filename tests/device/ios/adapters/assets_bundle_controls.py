"""Original bundle review/destination fields, separate from server outcomes."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from urllib.parse import unquote,urlsplit
from adapters.native_feature_observation import exact,integer,need
from ios.adapters.assets_controls import identity,local,source,text

VERSION=1
CONTROL_VERSION=2
IDS=frozenset(('asset-file.bundle-primary','asset-file.bundle-use','asset-file.bundle-back',
    'assets.destination','assets.destination.accept','assets.destination.cancel'))


def relative(value):
    text(value,256);need(value and not value.startswith('/') and '\\' not in value and all(part not in ('','.','..') for part in value.split('/')))
    return value


def manifest(value):
    if value is None:return None
    exact(value,{'root','urls','relativePaths','primaryIndex','primaryPath'})
    root=local(value['root']).rstrip('/');paths=value['relativePaths'];urls=value['urls']
    need(root and type(paths) is list and type(urls) is list and 1<=len(paths)<=32 and len(paths)==len(urls))
    need(all(type(item) is str for item in paths+urls) and len(set(paths))==len(paths) and len(set(urls))==len(urls))
    for path,url in zip(paths,urls):relative(path);need(local(url)==root+'/'+path)
    need(type(value['primaryIndex']) is int and -1<=value['primaryIndex']<len(paths))
    need(value['primaryPath']==('' if value['primaryIndex']==-1 else paths[value['primaryIndex']]))
    return value


def destination(value):
    text(value,128)
    import re
    need(re.fullmatch(r'/(?:e2e|renamed)-[a-f0-9]{32}/',value) is not None);return value


def metadata(value):
    exact(value,{'assetControlVersion','role','rootId','windowId','componentSource','controlId','ownerRootId',
        'bundle','fieldText','choiceIndex','choiceCount','destinationId','destinationText'})
    need(type(value['assetControlVersion']) is int and value['assetControlVersion']==CONTROL_VERSION and value['controlId'] in IDS)
    role='picker' if value['controlId'].startswith('asset-file.') else 'page';need(value['role']==role);source(value['componentSource'],role)
    for key in ('rootId','windowId','ownerRootId'):identity(value[key])
    actual=manifest(value['bundle']);need(actual is not None);text(value['fieldText']);text(value['destinationText'])
    if role=='picker':
        need(value['destinationId'] is None and value['destinationText']=='' and value['fieldText']=='' and type(value['choiceIndex']) is int
            and value['choiceIndex']==actual['primaryIndex'] and type(value['choiceCount']) is int and value['choiceCount']==len(actual['relativePaths']))
    else:
        identity(value['destinationId']);need(value['ownerRootId']==value['rootId'] and actual['primaryIndex']>=0
            and value['choiceIndex']==-1 and type(value['choiceIndex']) is int and value['choiceCount']==0 and type(value['choiceCount']) is int)
        if value['controlId']!='assets.destination':need(value['fieldText']=='')
        else:need(value['fieldText']==value['destinationText'])
    return value


def inventory(value,*,pid,ui=None):
    exact(value,{'iosAssetsBundleUiVersion','instance','sequence','processId','capturedEpochMs','available','complete','rows'})
    need(type(value['iosAssetsBundleUiVersion']) is int and value['iosAssetsBundleUiVersion']==VERSION
        and integer(value['processId'],1) and value['processId']==pid and integer(value['sequence'],1)
        and integer(value['capturedEpochMs'],1) and type(value['available']) is type(value['complete']) is bool
        and type(value['rows']) is list and len(value['rows'])<=128)
    identity(value['instance']);seen=set()
    for row in value['rows']:
        role=row.get('role');need(role in ('page','picker'))
        exact(row,{'rootId','ownerRootId','role','bundle'}|({'destinationId','destinationVisible','destinationText','uploadedPrimaryUrl'} if role=='page' else set()))
        identity(row['rootId']);identity(row['ownerRootId']);need(row['rootId'] not in seen);seen.add(row['rootId']);actual=manifest(row['bundle'])
        if role=='page':
            need(row['ownerRootId']==row['rootId'] and type(row['destinationVisible']) is bool);identity(row['destinationId']);text(row['destinationText'])
            text(row['uploadedPrimaryUrl']);url=urlsplit(row['uploadedPrimaryUrl'])
            need(not row['uploadedPrimaryUrl'] or url.scheme=='atp' and not url.netloc and not url.query and not url.fragment
                and unquote(url.path).startswith(('/e2e-','/renamed-')))
            if row['destinationVisible']:need(actual is not None and actual['primaryIndex']>=0)
        if ui is not None:
            matches=[old for old in ui['roots'] if old['rootId']==row['rootId'] and old['role']==role and old['alive']]
            need(len(matches)==1 and matches[0]['ownerRootId']==row['ownerRootId'])
            if role=='page':need(matches[0]['pendingBundle']==(actual is not None) and matches[0]['destinationOpen']==row['destinationVisible'])
            else:need(matches[0]['bundleReview']==(actual is not None))
    if ui is not None and value['complete']:
        need(ui['available'] and ui['complete'] and seen=={row['rootId'] for row in ui['roots'] if row['alive']})
    return value
