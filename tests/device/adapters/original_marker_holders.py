"""Quiet actual marker resources and observed Qt roots, never retirement.

Only closed Avatar/Emote profiles are supported. Native originals and counters
remain unchanged. Each outstanding process group still requires real OS end.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy

from adapters.native_clock_join import digest
from adapters.native_feature_observation import need,validate as native_packet
from adapters.normal_feature_state import context
from adapters.script_ui_inventory import validate as inventory_packet
from adapters.script_ui_root_ownership import membership,validate as root_packet
from feature_journeys.contract import identifier
from feature_journeys.terminal import held
from ios.adapters.emote_native_prefix import follow
from ios.adapters.web_closures import validate as web_packet,continuity,drained,resources_for

VERSION=1
PROFILES={'avatar':'Avatar','emote':'Emote'}
KINDS={'scenegraph-node':'qsg-root','offscreen-image':'qimage','upload-image':'qimage',
    'native-bitmap':'qimage','native-view':'wk-view'}


def schema(profile,name):
    need(type(profile) is str and profile in PROFILES
        and name in ('Holder','WebDisposition','CacheHolder','UiDisposition','QtHolder','ProcessHolder'))
    return 'ios'+PROFILES[profile]+'Marker'+name+'Version'


def holder(profile,name,kind,original):
    schema(profile,'Holder');need(name in resources_for(5)|{'ui-manager','ui-picker','process'});identity=digest(original)
    result=dict(resource='panel:'+profile+'-marker-'+name+'-'+identity[:20],kind=kind,originalSha256=identity,original=deepcopy(original))
    held([{key:result[key] for key in ('resource','kind','originalSha256')}]);return result


def packet(value):
    need(type(value) is dict)
    web_packet(value,dict(schemaVersion=1,commandId=value.get('commandId'),action='feature-ios-web-closures',
        runId=value.get('runId'),fixtureUrl=value.get('fixtureUrl')),value.get('processId'),value.get('capturedEpochMs'))
    need(type(value['iosWebClosureVersion']) is int and value['iosWebClosureVersion']==5 and value['complete'] is True)
    return value


def web(profile,current,admitted,*,partial=False):
    """Callbacks/grants end; every actual cached allocation stays explicit."""
    key=schema(profile,'WebDisposition');need(type(partial) is bool);packet(admitted);packet(current)
    continuity(admitted,current,admitted['processId'])
    if not partial:
        drained(current,admitted)
        need(all(any(row['resources'][name]['created']>0 for row in admitted['contexts'])
            for name in resources_for(5)-{'native-presentation'}))
    need(all(counter['pending']==0 for row in current['contexts'] for counter in row['callbacks'].values())
        and all(row['resources']['policy-grant']['pending']==0 for row in current['contexts']))
    groups={}
    for item in current['contexts']:
        for name,counter in item['resources'].items():
            if counter['pending']:
                groups.setdefault(name,[]).append(dict(contextId=item['id'],descriptor=deepcopy(item['descriptor']),counter=deepcopy(counter)))
    holders=[]
    for name,rows in sorted(groups.items()):
        original={schema(profile,'CacheHolder'):VERSION,'runId':current['runId'],'processId':current['processId'],
            'sourceInstance':current['instance'],'resourceKind':name,'contexts':rows}
        holders.append(holder(profile,name,KINDS.get(name,'native-holder'),original))
    holders.sort(key=lambda row:row['resource'])
    return {key:VERSION,'runId':current['runId'],'originalSha256':digest(current),'contexts':deepcopy(current['contexts']),'holders':holders}


def ui(profile,inventory,*,pid,epoch=None,previous=None):
    """Current UI quiet plus actual historical weak roots, including detached."""
    key=schema(profile,'UiDisposition');inventory_packet(inventory,pid=pid,epoch=epoch)
    need(inventory['inventoryVersion']==2 and inventory['complete'] and not inventory['tabletShown']
        and not inventory['managers'] and not inventory['pickers'])
    roots=membership(inventory,pid=pid,epoch=epoch)
    need(roots['available'] and roots['complete'] and roots['wholeTreeReady'])
    if previous is not None:root_packet(roots,pid=pid,previous=previous)
    holders=[]
    for kind in ('manager','picker'):
        rows=[deepcopy(row) for row in roots['roots'] if row['kind']==kind and row['weakAlive']]
        if rows:
            original={schema(profile,'QtHolder'):VERSION,'processId':pid,'sourceInstance':roots['instance'],'rootKind':kind,'roots':rows}
            holders.append(holder(profile,'ui-'+kind,'qt-root',original))
    return {key:VERSION,'ownership':deepcopy(roots),'holders':holders}


def unchanged(first_web,last_web,first_ui,last_ui,*,pid):
    packet(first_web);packet(last_web);continuity(first_web,last_web,pid)
    root_packet(first_ui,pid=pid);root_packet(last_ui,pid=pid,previous=first_ui)
    need(first_web['contexts']==last_web['contexts'] and first_ui['roots']==last_ui['roots'])
    return True


def process(profile,admitted,current,*,binding,run):
    """Outstanding real process ownership; no UI death or callback assertion."""
    key=schema(profile,'ProcessHolder');binding=context(binding);identifier(run);pid=int(binding['processIdentity'])
    for value in (admitted,current):native_packet(value,value['requestId'],pid,value['capturedEpochMs'])
    follow(admitted,current)
    original={key:VERSION,'runId':run,'binding':binding,'processId':pid,'sourceInstance':admitted['instance'],
        'firstObservedNativeSha256':digest(admitted),'lifecycle':deepcopy(admitted['lifecycle'])}
    return holder(profile,'process','native-holder',original)
