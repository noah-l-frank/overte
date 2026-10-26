"""Original normal baking/import controls and actual effective permissions.

UI enabled/checked state remains distinct from current native Node/API rights.
This module performs no permission changes, input or resource verdicts.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import exact,integer,need,number
from ios.adapters.assets_controls import identity,source,text
from ios.adapters.assets_tree_controls import selection

VERSION=1
CONTROL_VERSION=4
IDS=frozenset(('assets.baking','assets.import','assets.import-uploaded','assets.model.url','assets.model.shape','assets.model.dynamic','assets.model.accept','assets.model.cancel'))
FIELDS={'rootId','windowId','componentSource','treeId','modelId','treeRevision','selectedPaths','currentPath','currentUrl','canWrite','busy',
    'apiId','clientNodeId','domainId','permissions','importAllowed','uploadedPrimaryUrl','baking','importButtonId','importEnabled','uploadedImportButtonId','uploadedImportVisible','uploadedImportEnabled','model'}


def control_id(value):return type(value) is str and value in IDS


def page(value):
    exact(value,FIELDS)
    for key in ('rootId','windowId','treeId','modelId','apiId','clientNodeId','domainId','importButtonId','uploadedImportButtonId'):identity(value[key])
    source(value['componentSource'],'page');need(integer(value['treeRevision']));selection(value['selectedPaths'],value['currentPath'],value['currentUrl'])
    for key in ('canWrite','busy','importAllowed','importEnabled','uploadedImportVisible','uploadedImportEnabled'):need(type(value[key]) is bool)
    permissions=value['permissions'];exact(permissions,{'canWriteAssets','canRez','canRezTmp'});need(all(type(item) is bool for item in permissions.values()))
    text(value['uploadedPrimaryUrl']);baking=value['baking'];exact(baking,{'id','checked','enabled'});identity(baking['id']);need(type(baking['checked']) is type(baking['enabled']) is bool)
    model=value['model'];exact(model,{'id','visible','urlId','url','shapeId','shapeIndex','shapeCount','dynamicId','dynamicChecked','dynamicEnabled','name','position'})
    for key in ('id','urlId','shapeId','dynamicId'):identity(model[key])
    for key in ('visible','dynamicChecked','dynamicEnabled'):need(type(model[key]) is bool)
    text(model['url']);text(model['name']);need(type(model['shapeCount']) is int and model['shapeCount']==6 and integer(model['shapeIndex'],0,5))
    if model['visible']:
        exact(model['position'],{'x','y','z'});need(all(number(item) for item in model['position'].values()))
    else:need(model['position'] is None)
    need(len({baking['id'],value['importButtonId'],value['uploadedImportButtonId'],model['id'],model['urlId'],model['shapeId'],model['dynamicId']})==7)
    return value


def input_ready(value,identifier):
    page(value);need(control_id(identifier));model=value['model'];visible=model['visible']
    if identifier=='assets.baking':return not visible and value['baking']['enabled']
    if identifier in ('assets.import','assets.import-uploaded'):
        return not visible and (value['importEnabled'] if identifier=='assets.import' else value['uploadedImportVisible'] and value['uploadedImportEnabled'])
    if not visible:return False
    if identifier in ('assets.model.cancel','assets.model.url','assets.model.shape'):return True
    if identifier=='assets.model.dynamic':return model['dynamicEnabled']
    return identifier=='assets.model.accept'


def metadata(value):
    exact(value,{'assetControlVersion','role','rootId','ownerRootId','windowId','componentSource','controlId','inputReady','usage'})
    need(type(value['assetControlVersion']) is int and value['assetControlVersion']==CONTROL_VERSION and value['role']=='page' and control_id(value['controlId']) and type(value['inputReady']) is bool)
    page(value['usage']);need(value['ownerRootId']==value['rootId'] and all(value[key]==value['usage'][key] for key in ('rootId','windowId','componentSource')))
    need(value['inputReady']==input_ready(value['usage'],value['controlId']));return value


def inventory(value,*,pid,ui,tree=None):
    exact(value,{'iosAssetsUsageUiVersion','instance','sequence','processId','capturedEpochMs','available','complete','pages'})
    need(type(value['iosAssetsUsageUiVersion']) is int and value['iosAssetsUsageUiVersion']==VERSION and integer(value['sequence'],1)
        and integer(value['processId'],1) and value['processId']==pid and integer(value['capturedEpochMs'],1)
        and type(value['available']) is type(value['complete']) is bool and type(value['pages']) is list and len(value['pages'])<=128)
    identity(value['instance']);need(type(ui) is dict and type(tree) is dict and abs(value['capturedEpochMs']-ui['capturedEpochMs'])<=250
        and abs(value['capturedEpochMs']-tree['capturedEpochMs'])<=250);seen=set()
    for current in value['pages']:
        page(current);need(current['rootId'] not in seen);seen.add(current['rootId'])
        actual=[row for row in tree['pages'] if row['rootId']==current['rootId']];roots=[row for row in ui['roots'] if row['rootId']==current['rootId'] and row['role']=='page' and row['alive']]
        need(len(actual)==len(roots)==1 and all(actual[0][key]==current[key] for key in ('rootId','windowId','componentSource','treeId','modelId','treeRevision','selectedPaths','currentPath','currentUrl','canWrite','busy')))
    if value['complete']:need(value['available'] and ui['available'] and ui['complete'] and tree['available'] and tree['complete']
        and seen=={row['rootId'] for row in ui['roots'] if row['role']=='page' and row['alive']})
    return value


def project(packet,root_id):
    inventory(packet['assetUsageInventory'],pid=packet['processId'],ui=packet['assetInventory'],tree=packet['assetTreeInventory'])
    need(type(packet['assetUsageControlsVersion']) is int and packet['assetUsageControlsVersion']==VERSION and packet['assetUsageInventory']['available'] and packet['assetUsageInventory']['complete'])
    pages=[row for row in packet['assetUsageInventory']['pages'] if row['rootId']==root_id];need(len(pages)==1);return deepcopy(pages[0])
