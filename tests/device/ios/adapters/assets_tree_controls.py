"""Original Assets model/tree/selection and existing rename/delete controls.

UI model rows contain paths and reported bake labels, not server hashes or
worker/output facts. Independent GetAll replies retain that separate role.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
from adapters.native_feature_observation import exact,integer,need
from ios.adapters.assets_controls import identity,source,text

VERSION=1
CONTROL_VERSION=3
LIMIT=64
IDS=frozenset(('assets.refresh','assets.rename','assets.rename.path','assets.rename.accept','assets.rename.cancel',
    'assets.delete','assets.delete.accept','assets.delete.cancel'))
ROW=re.compile(r'assets\.tree\.row\.(0|[1-9][0-9]?)')
FIELDS={'assetControlVersion','role','rootId','ownerRootId','windowId','componentSource','controlId','treeId','modelId',
    'treeRevision','selectedPaths','currentPath','currentUrl','row','renameId','renameVisible','renameText','deleteId','deleteVisible','canWrite','busy'}


def control_id(value):return type(value) is str and (value in IDS or ROW.fullmatch(value) is not None)


def path(value,*,empty=False):
    text(value);need(empty and value=='' or value.startswith('/') and value!='/' and '\\' not in value and '//' not in value
        and all(part not in ('.','..') for part in value.split('/')))
    return value


def owned_root(value):
    text(value,128);need(re.fullmatch(r'/(?:e2e|renamed)-[a-f0-9]{32}/',value));return value


def model_row(value):
    exact(value,{'modelIndex','name','path','folder','url','fullPath','status','bakingErrors'})
    need(type(value['modelIndex']) is list and 1<=len(value['modelIndex'])<=16 and all(integer(index,0,63) for index in value['modelIndex'])
        and type(value['folder']) is bool);text(value['name'],256);path(value['path']);path(value['fullPath'])
    need(value['path']==value['fullPath']+('/' if value['folder'] else '') and value['url']=='atp:'+value['fullPath']
        and value['name']==value['fullPath'].rsplit('/',1)[-1])
    text(value['bakingErrors'],8192);need(value['status'] in ('--','Not Baked','Pending','Baking','Baked','Error'))
    if value['folder']:need(value['status']=='--')
    return value


def row(value):
    exact(value,{'index','model','depth','selected','expanded'});model_row(value['model'])
    need(integer(value['index'],0,LIMIT-1) and integer(value['depth'],0,15) and value['depth']==len(value['model']['modelIndex'])-1
        and type(value['selected']) is type(value['expanded']) is bool)
    if not value['model']['folder']:need(not value['expanded'])
    return value


def selection(paths,current,url):
    need(type(paths) is list and len(paths)<=LIMIT and all(type(item) is str for item in paths) and len(paths)==len(set(paths)))
    for item in paths:path(item)
    path(current,empty=True);text(url);need((not current)==(not url))
    if current:need(url=='atp:'+current.rstrip('/'))


def metadata(value):
    exact(value,FIELDS);need(type(value['assetControlVersion']) is int and value['assetControlVersion']==CONTROL_VERSION
        and value['role']=='page' and control_id(value['controlId']))
    for key in ('rootId','ownerRootId','windowId','treeId','modelId','renameId','deleteId'):identity(value[key])
    need(value['rootId']==value['ownerRootId']);source(value['componentSource'],'page');need(integer(value['treeRevision']))
    selection(value['selectedPaths'],value['currentPath'],value['currentUrl']);text(value['renameText'])
    for key in ('renameVisible','deleteVisible','canWrite','busy'):need(type(value[key]) is bool)
    match=ROW.fullmatch(value['controlId'])
    if match:need(value['row'] is not None and row(value['row'])['index']==int(match[1]))
    else:need(value['row'] is None)
    return value


def page(value):
    exact(value,{'rootId','windowId','treeId','modelId','componentSource','treeRevision','filterText','selectedPaths','currentPath','currentUrl',
        'modelRows','rows','renameId','renameVisible','renameText','deleteId','deleteVisible','canWrite','busy'})
    for key in ('rootId','windowId','treeId','modelId','renameId','deleteId'):identity(value[key])
    source(value['componentSource'],'page');need(integer(value['treeRevision']));text(value['filterText']);text(value['renameText'])
    for key in ('renameVisible','deleteVisible','canWrite','busy'):need(type(value[key]) is bool)
    selection(value['selectedPaths'],value['currentPath'],value['currentUrl'])
    need(type(value['modelRows']) is list and len(value['modelRows'])<=LIMIT and type(value['rows']) is list and len(value['rows'])<=LIMIT)
    paths={};indexes={}
    for item in value['modelRows']:
        model_row(item);need(item['path'] not in paths and tuple(item['modelIndex']) not in indexes)
        paths[item['path']]=item;indexes[tuple(item['modelIndex'])]=item
        if len(item['modelIndex'])>1:
            parent=indexes.get(tuple(item['modelIndex'][:-1]));need(parent is not None and parent['folder'] and item['fullPath'].rsplit('/',1)[0]+'/'==parent['path'])
    for index,item in enumerate(value['rows']):
        row(item);need(item['index']==index and item['model']['path'] in paths and item['model']==paths[item['model']['path']]
            and item['selected']==(item['model']['path'] in value['selectedPaths']))
    visible={item['model']['path'] for item in value['rows']};need(set(value['selectedPaths'])<=visible and (not value['currentPath'] or value['currentPath'] in visible))
    return value


def inventory(value,*,pid,ui):
    exact(value,{'iosAssetsTreeUiVersion','instance','sequence','processId','capturedEpochMs','available','complete','pages'})
    need(type(value['iosAssetsTreeUiVersion']) is int and value['iosAssetsTreeUiVersion']==VERSION and integer(value['sequence'],1)
        and integer(value['processId'],1) and value['processId']==pid and integer(value['capturedEpochMs'],1)
        and type(value['available']) is type(value['complete']) is bool and type(value['pages']) is list and len(value['pages'])<=128)
    identity(value['instance']);seen=set()
    for actual in value['pages']:
        page(actual);need(actual['rootId'] not in seen);seen.add(actual['rootId'])
        roots=[old for old in ui['roots'] if old['rootId']==actual['rootId'] and old['alive'] and old['role']=='page'];need(len(roots)==1)
        old=roots[0];need(all(old[key]==actual[key] for key in ('windowId','modelId','componentSource','canWrite','busy'))
            and old['modelRevision']==actual['treeRevision'] and old['selectedPath']==actual['currentPath'] and old['selectedUrl']==actual['currentUrl'])
    if value['complete']:need(ui['available'] and ui['complete'] and seen=={old['rootId'] for old in ui['roots'] if old['alive'] and old['role']=='page'})
    return value


def project(packet,root_id):
    inventory(packet['assetTreeInventory'],pid=packet['processId'],ui=packet['assetInventory']);need(packet['assetTreeControlsVersion']==VERSION
        and packet['assetTreeInventory']['available'] and packet['assetTreeInventory']['complete'])
    pages=[item for item in packet['assetTreeInventory']['pages'] if item['rootId']==root_id];need(len(pages)==1);return deepcopy(pages[0])
