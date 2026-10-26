"""Passive original HUD/tablet navigation identities beside unchanged UI rows."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from urllib.parse import unquote,urlsplit
from adapters.native_feature_observation import exact,integer,need
from ios.adapters.keyboard_source import identifier
from ios.adapters.snapshot_export_controls import identity as uuid

VERSION=1
IDS=frozenset({'hud.tablet','tablet.home','tablet.close','create.entry','chat.entry','scripts.entry',
    'scripts.menu','scripts.menu-edit','scripts.menu-running'}|{'tablet.page.'+str(i) for i in range(1,33)})
FIELDS={'controlId','controlObject','windowObject','containerObject','contextObject','qmlSource','surface','inputReady'}


def metadata(value):
    exact(value,FIELDS);need(value['controlId'] in IDS and type(value['inputReady']) is bool)
    for key in ('controlObject','windowObject','containerObject','contextObject'):identifier(value[key])
    need(value['surface']==('hud' if value['controlId']=='hud.tablet' else 'tablet'))
    source=value['qmlSource'];need(type(source) is str and 1<=len(source)<=4096 and all(ord(c)>=32 and ord(c)!=127 for c in source))
    parsed=urlsplit(source);path=unquote(parsed.path)
    need(parsed.scheme in ('qrc','file') and not parsed.netloc and not parsed.query and not parsed.fragment
         and path.startswith('/') and path.endswith('.qml') and not any(p in ('.','..') for p in path.split('/')))
    return value


def inventory(value):
    exact(value,{'iosLifecycleNavigationVersion','complete','controls'})
    need(type(value['iosLifecycleNavigationVersion']) is int and value['iosLifecycleNavigationVersion']==VERSION
         and type(value['complete']) is bool and type(value['controls']) is list and len(value['controls'])<=len(IDS))
    ids=set();tokens=set();objects=set()
    for row in value['controls']:
        exact(row,FIELDS|{'token'});uuid(row['token']);metadata({key:row[key] for key in FIELDS})
        need(row['controlId'] not in ids and row['token'] not in tokens and row['controlObject'] not in objects)
        ids.add(row['controlId']);tokens.add(row['token']);objects.add(row['controlObject'])
    return value


def membership(ui):
    source=inventory(ui['lifecycleNavigation']);actual={row['id']:row for row in ui['controls'] if row['id'] in IDS}
    rows={row['controlId']:row for row in source['controls']};need(set(rows)<=set(actual))
    if source['complete']:need(set(rows)==set(actual))
    for key,row in rows.items():
        need(row['token']==actual[key]['token'] and (not row['inputReady'] or actual[key]['enabled'])
             and (row['surface']!='tablet' or ui['tabletShown']))
    return source


def project(ui,control):
    from ios.adapters.normal_input import observation
    observation(ui,ui['processId'],ui['sampleEpochMs']);need(control in IDS)
    source=membership(ui);need(source['complete']);rows=[row for row in source['controls'] if row['controlId']==control]
    controls=[row for row in ui['controls'] if row['id']==control];need(len(rows)==1 and len(controls)==1)
    actual=rows[0];row=controls[0];need(actual['inputReady'] and row['enabled'])
    return dict(scope=dict(processId=ui['processId'],instance=ui['instance'],sampleEpochMs=ui['sampleEpochMs'],
        elapsedMs=ui['elapsedMs'],sequence=ui['lastSequence']),control={key:deepcopy(row[key]) for key in ('id','token','enabled','focused')},
        root={key:deepcopy(actual[key]) for key in FIELDS})
