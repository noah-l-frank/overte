"""Passive original login observation; this transport cannot deliver input."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import re
from adapters.native_feature_observation import exact,fresh,integer,need
from adapters.script_journey.files import ScriptFileIO,nonce
from adapters.token_login_ui import VERSION as CONTROLS_VERSION,validate_metadata

VERSION=1
FILE='login-ui.json'


def qml_loads(value):
    exact(value,{'qmlLoadInventoryVersion','instance','complete','components','retiredComponents'})
    need(type(value['qmlLoadInventoryVersion']) is int and value['qmlLoadInventoryVersion']==1
         and nonce(value['instance']) and value['complete'] is True and type(value['components']) is list
         and len(value['components'])<=128 and type(value['retiredComponents']) is list
         and len(value['retiredComponents'])<=1024)
    ids=set()
    for row in value['components']:
        exact(row,{'id','sourceSha256','phase','loading','callbackPending','parentPresent'})
        need(nonce(row['id']) and row['id'] not in ids and type(row['sourceSha256']) is str
             and re.fullmatch('[0-9a-f]{64}',row['sourceSha256'])
             and row['phase'] in ('constructing','loading','finishing','finished')
             and all(type(row[key]) is bool for key in ('loading','callbackPending','parentPresent'))
             and row['callbackPending']==(row['phase']=='loading')
             and (row['phase']!='finished' or not row['loading']))
        ids.add(row['id'])
    retired=value['retiredComponents']
    need(all(nonce(key) for key in retired) and retired==sorted(set(retired)) and not ids.intersection(retired))
    return value


def accept_loads(previous,current):
    qml_loads(current)
    if previous is not None:
        qml_loads(previous);need(previous['instance']==current['instance']
            and set(previous['retiredComponents'])<=set(current['retiredComponents']))
        old={row['id']:row for row in previous['components']};live={row['id']:row for row in current['components']}
        need(set(old)<=set(live)|set(current['retiredComponents']))
        phases={'constructing':0,'loading':1,'finishing':2,'finished':3}
        for key in set(old)&set(live):
            need(old[key]['sourceSha256']==live[key]['sourceSha256']
                 and phases[old[key]['phase']]<=phases[live[key]['phase']])
    return deepcopy(current)


def inventory(value,*,profiles=frozenset({'qml-login-v1','phone-login-v1','tablet-menu-v1'})):
    need(type(profiles) is frozenset and profiles<=frozenset({'qml-login-v1','phone-login-v1','tablet-menu-v1','graphics-generic-v1','graphics-phone-v1'}))
    exact(value,{'inventoryVersion','complete','roots','retiredRoots','qmlLoads','keyboard3D'})
    qml_loads(value['qmlLoads']);exact(value['keyboard3D'],{'raised','enabled'})
    need(all(type(value['keyboard3D'][key]) is bool for key in ('raised','enabled')))
    need(type(value['inventoryVersion']) is int and value['inventoryVersion']==1 and value['complete'] is True
         and type(value['roots']) is list and len(value['roots'])<=16
         and type(value['retiredRoots']) is list and len(value['retiredRoots'])<=256)
    ids=set()
    for row in value['roots']:
        exact(row,{'id','profile','visible','inCurrentTree','callbackRunning','callbackItemPresent'})
        need(nonce(row['id']) and row['id'] not in ids and type(row['profile']) is str and row['profile'] in profiles
             and all(type(row[key]) is bool for key in ('visible','inCurrentTree','callbackRunning','callbackItemPresent'))
             and (row['profile']=='tablet-menu-v1' or not row['callbackItemPresent']
                 and (row['profile']=='graphics-generic-v1' or not row['callbackRunning'])))
        ids.add(row['id'])
    retired=value['retiredRoots']
    need(all(nonce(key) for key in retired) and retired==sorted(set(retired)) and not ids.intersection(retired))
    return value


def accept_inventory(previous,current,*,profiles=frozenset({'qml-login-v1','phone-login-v1','tablet-menu-v1'})):
    inventory(current,profiles=profiles)
    if previous is not None:
        inventory(previous,profiles=profiles)
        accept_loads(previous['qmlLoads'],current['qmlLoads'])
        alive={row['id']:row for row in current['roots']};old={row['id']:row for row in previous['roots']}
        need(set(previous['retiredRoots'])<=set(current['retiredRoots'])
             and set(old)<=set(alive)|set(current['retiredRoots']))
        need(all(alive[key]['profile']==old[key]['profile'] for key in set(alive)&set(old)))
    return deepcopy(current)


def validate(value,command,pid,epoch):
    exact(value,{'schemaVersion','commandId','action','instance','generation','sourceSequence',
        'lastCommandSequence','elapsedMs','capturedEpochMs','processId','loginControlsVersion',
        'loginObservationVersion','startupDialogPresent','loginInventory','ready','controls'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['commandId']==command
         and value['action']=='observe' and nonce(value['instance']) and nonce(value['generation'])
         and integer(value['sourceSequence'],1) and integer(value['lastCommandSequence']) and integer(value['elapsedMs'])
         and integer(value['processId'],1) and value['processId']==pid
         and type(value['loginControlsVersion']) is int and value['loginControlsVersion']==CONTROLS_VERSION
         and type(value['loginObservationVersion']) is int and value['loginObservationVersion']==VERSION
         and value['startupDialogPresent'] is False and value['ready'] is True
         and type(value['controls']) is list and len(value['controls'])<=7)
    fresh(value['capturedEpochMs'],epoch)
    inventory(value['loginInventory'])
    ids=set();tokens=set()
    for row in value['controls']:
        need(type(row) is dict);validate_metadata(row)
        need(nonce(row['token']) and row['id'] not in ids and row['token'] not in tokens)
        ids.add(row['id']);tokens.add(row['token'])
    pages=[row for row in value['controls'] if row['id']=='login.page']
    if pages:need(any(row['visible'] and row['inCurrentTree'] and row['profile']==pages[0]['profile']
        for row in value['loginInventory']['roots']))
    return value


class LoginObservationSource(ScriptFileIO):
    wire_action='login-ui-observe'
    validate_capture=staticmethod(validate)

    def capture(self):
        value=super().capture();need(value['capturedEpochMs']>=getattr(self,'epoch_floor',0))
        self.inventory=accept_inventory(getattr(self,'inventory',None),value['loginInventory'])
        self.epoch_floor=value['capturedEpochMs'];return value

    def restore_inventory(self,previous):
        self.inventory=accept_inventory(getattr(self,'inventory',None),previous['loginInventory'])

    def input(self,*_args,**_kwargs):need(False)
