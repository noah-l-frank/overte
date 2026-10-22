"""Original native Create modal delivery and weak listener/root/context facts."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import re
from adapters.native_feature_observation import exact,fresh,integer,need
from adapters.pico4.create_callbacks import NativeCreateCallbacks
from adapters.pico4.create_file_ui import component,inventory as validate_inventory
from adapters.token_create_ui import nonce

VERSION=1
FILE='feature-create-dialogs.json'
ACTION='feature-create-dialogs-observe'
IDENTITIES=('id','rootId','listenerId','contextId','windowId')
TIMES=('registeredEpochMs','enteredEpochMs','returnedEpochMs')
ALIVE=('listenerAlive','rootAlive','contextAlive','windowAlive')


def dialogs(value,epoch):
    exact(value,{'createDialogSourceVersion','instance','sequence','elapsedMs','complete','dialogs'})
    need(type(value['createDialogSourceVersion']) is int and value['createDialogSourceVersion'] in (1,2,3)
         and nonce(value['instance']) and integer(value['sequence'],1) and integer(value['elapsedMs'])
         and type(value['complete']) is bool and type(value['dialogs']) is list and len(value['dialogs'])<=32
         and (value['complete'] or not value['dialogs']))
    identities={};ids=[]
    for row in value['dialogs']:
        exact(row,set(IDENTITIES+TIMES+ALIVE)|{'role','componentSource','pending','dispatches'}
            | ({'responseSha256'} if value['createDialogSourceVersion']>=2 else set())
            | ({'browseSettingRead'} if value['createDialogSourceVersion']>=3 else set()))
        need(all(nonce(row[k]) and (row[k] not in identities or k in ('contextId','windowId') and identities[row[k]]==k) for k in IDENTITIES)
             and len({row[k] for k in IDENTITIES})==len(IDENTITIES))
        identities.update((row[k],k) for k in IDENTITIES);ids.append(row['id'])
        need(row['role'] in ('import','export'));component(row['componentSource'],'/dialogs/NativeFileBrowser.qml')
        need(integer(row['registeredEpochMs'],1,epoch) and integer(row['enteredEpochMs']) and integer(row['returnedEpochMs'])
             and all(type(row[k]) is bool for k in ALIVE+('pending',)) and integer(row['dispatches'],0,1))
        if value['createDialogSourceVersion']>=3 and row['browseSettingRead'] is not None:
            from adapters.pico4.create_browse_setting import browse_read
            browse_read(row['browseSettingRead'],row['registeredEpochMs'])
        if value['createDialogSourceVersion']>=2:
            digest=row['responseSha256'];need(digest is None or type(digest) is str and re.fullmatch('[0-9a-f]{64}',digest))
            need(row['enteredEpochMs']!=0 or digest is None)
            need(row['returnedEpochMs']==0 or digest is not None)
        if row['enteredEpochMs']==0:need(row['returnedEpochMs']==0 and row['pending'] and row['dispatches']==0)
        elif row['returnedEpochMs']==0:
            need(row['registeredEpochMs']<=row['enteredEpochMs']<=epoch and row['pending'] and row['dispatches']==1)
        else:need(row['registeredEpochMs']<=row['enteredEpochMs']<=row['returnedEpochMs']<=epoch and not row['pending'] and row['dispatches']==0)
    need(ids==sorted(ids));return value


def validate(value,request,pid,epoch):
    exact(value,{'schemaVersion','requestId','instance','sequence','requestedEpochMs','capturedEpochMs','processId','source'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==VERSION and nonce(request)
         and value['requestId']==request and nonce(value['instance']) and integer(value['sequence'],1)
         and integer(pid,1) and integer(value['processId'],1) and value['processId']==pid
         and integer(value['requestedEpochMs'],1) and integer(value['capturedEpochMs'],value['requestedEpochMs'])
         and value['capturedEpochMs']-value['requestedEpochMs']<5000)
    fresh(value['capturedEpochMs'],epoch);dialogs(value['source'],value['capturedEpochMs']);need(value['source']['complete'])
    return value


def continuity(previous,value):
    if previous is None:return
    need(previous['instance']==value['instance'] and value['sequence']>previous['sequence']
         and value['capturedEpochMs']>=previous['capturedEpochMs'])
    old=previous['source'];new=value['source']
    need(new['createDialogSourceVersion']==old['createDialogSourceVersion'] and new['instance']==old['instance'] and new['sequence']>old['sequence'] and new['elapsedMs']>=old['elapsedMs'])
    current={row['id']:row for row in new['dialogs']}
    for row in old['dialogs']:
        need(row['id'] in current);now=current[row['id']]
        need(all(now[k]==row[k] for k in IDENTITIES+('registeredEpochMs','role','componentSource'))
             and all(row[k]==0 or row[k]==now[k] for k in ('enteredEpochMs','returnedEpochMs'))
             and all(row[k] or not now[k] for k in ALIVE))
        if old['createDialogSourceVersion']>=3 and row['browseSettingRead'] is not None:need(now['browseSettingRead']==row['browseSettingRead'])
        if old['createDialogSourceVersion']>=2 and row['responseSha256'] is not None:need(now['responseSha256']==row['responseSha256'])


def active(value):
    validate(value,value['requestId'],value['processId'],value['capturedEpochMs'])
    return [dict(row) for row in value['source']['dialogs'] if row['pending'] or row['dispatches']
        or any(row[k] for k in ('listenerAlive','rootAlive','contextAlive'))]


def ui_bindings(value,inventory):
    validate_inventory(inventory)
    exact(value,{'bindingVersion','inventoryInstance','inventorySequence','complete','bindings'})
    need(type(value['bindingVersion']) is int and value['bindingVersion']==VERSION
         and value['inventoryInstance']==inventory['instance'] and integer(value['inventorySequence'],1)
         and value['inventorySequence']==inventory['sequence'] and type(value['complete']) is bool
         and type(value['bindings']) is list and len(value['bindings'])<=16
         and (value['complete'] or not value['bindings']))
    roots={r['id']:r for r in inventory['roots'] if r['profile']!='create-editor-v1'};seen=[];sources=set();native_ids=set()
    for row in value['bindings']:
        exact(row,{'uiRootId','native'});need(row['uiRootId'] in roots)
        native=row['native'];exact(native,{'bindingVersion','sourceInstance','dialogId','rootId','listenerId','contextId','windowId','role'})
        need(type(native['bindingVersion']) is int and native['bindingVersion']==VERSION
             and all(nonce(native[k]) for k in ('sourceInstance','dialogId','rootId','listenerId','contextId','windowId'))
             and native['role'] in ('import','export') and roots[row['uiRootId']]['profile']=='create-'+native['role']+'-json-v1')
        need(native['dialogId'] not in native_ids);native_ids.add(native['dialogId']);sources.add(native['sourceInstance'])
        seen.append(row['uiRootId'])
    need(len(sources)<=1 and seen==sorted(set(seen)) and (not value['complete'] or inventory['complete'] and set(seen)==set(roots)))
    return value


def joined(binding,value):
    """Match an actual pre-input native pointer binding to its original source."""
    exact(binding,{'bindingVersion','sourceInstance','dialogId','rootId','listenerId','contextId','windowId','role'})
    need(type(binding['bindingVersion']) is int and binding['bindingVersion']==VERSION
         and all(nonce(binding[k]) for k in ('sourceInstance','dialogId','rootId','listenerId','contextId','windowId'))
         and binding['role'] in ('import','export'))
    validate(value,value['requestId'],value['processId'],value['capturedEpochMs'])
    need(binding['bindingVersion']==VERSION and binding['sourceInstance']==value['source']['instance'])
    rows=[r for r in value['source']['dialogs'] if r['id']==binding['dialogId']];need(len(rows)==1)
    row=rows[0];need(all(row[k]==binding[k] for k in ('rootId','listenerId','contextId','windowId','role')))
    return dict(row)


class NativeCreateDialogs(NativeCreateCallbacks):
    action=ACTION
    validate=staticmethod(validate)
    continuity=staticmethod(continuity)
