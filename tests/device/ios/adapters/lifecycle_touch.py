"""Passive originals of ordinary Qt touch routing, never a gesture ACK.

Each contact is born in a real Application touch event. A world route means
that Application reached its ordinary world handlers; effective drive keys
remain a separate source. These records neither hold nor release contacts.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import exact,integer,need,number
from adapters.script_feature.history import same
from ios.adapters.keyboard_source import clock,identifier

VERSION=1
ROUTES={'ui','captured','world'}
PHASES={'pressed','updated','stationary','released','cancelled'}


def point(value):
    need(type(value) is list and len(value)==2 and all(number(n,-100000,100000) for n in value));return value


def validate(value,before_epoch,after_epoch,previous=None):
    exact(value,{'iosLifecycleTouchVersion','instance','clockDomain','clockBefore','clockAfter','installed','birth',
                 'complete','failure','events','devices','active'})
    need(type(value['iosLifecycleTouchVersion']) is int and value['iosLifecycleTouchVersion']==VERSION
         and value['clockDomain']=='native-main-lifecycle-touch' and value['installed'] is True
         and value['complete'] is True and value['failure'] is None)
    identifier(value['instance']);birth=value['birth'];clock(birth)
    a,b=value['clockBefore'],value['clockAfter'];clock(a,floor=birth);clock(b,floor=a)
    need(before_epoch<=a['epochMs']<=b['epochMs']<=after_epoch
         and b['monotonicMs']-a['monotonicMs']<1500 and b['epochMs']-a['epochMs']<1500)
    devices={};need(type(value['devices']) is list and len(value['devices'])<=8)
    for row in value['devices']:
        exact(row,{'id','alive'});identifier(row['id']);need(row['id'] not in devices and type(row['alive']) is bool)
        devices[row['id']]=row
    events=value['events'];need(type(events) is list and len(events)<=128)
    contacts={};active={};last=birth;device_timestamp={}
    for index,event in enumerate(events):
        exact(event,{'sequence','clock','device','eventTimestampMs','route','kind','points'})
        need(type(event['sequence']) is int and event['sequence']==index+1 and type(event['device']) is str and event['device'] in devices
             and integer(event['eventTimestampMs']) and event['route'] in ROUTES
             and event['kind'] in ('begin','update','end','cancel'))
        clock(event['clock'],floor=last,ceiling=a);last=event['clock']
        device=event['device'];timestamp=event['eventTimestampMs']
        need(timestamp>=device_timestamp.get(device,0));device_timestamp[device]=timestamp
        points=event['points'];need(type(points) is list and 1<=len(points)<=16)
        if event['kind']=='begin':need(not any(key[0]==device for key in active))
        ids=set();native_ids=set()
        for row in points:
            exact(row,{'id','nativeId','phase','position'});identifier(row['id']);point(row['position'])
            need(row['id'] not in ids and integer(row['nativeId'],0,2147483647)
                 and row['nativeId'] not in native_ids and row['phase'] in PHASES)
            ids.add(row['id']);native_ids.add(row['nativeId']);key=(device,row['nativeId']);phase=row['phase']
            if event['kind']=='begin':need(phase=='pressed')
            if event['kind']=='end':need(phase=='released')
            if event['kind']=='cancel':need(phase=='cancelled')
            if phase=='pressed':
                need(key not in active and row['id'] not in contacts)
                active[key]=row['id'];contacts[row['id']]=dict(device=device,nativeId=row['nativeId'],
                    began=deepcopy(event['clock']),ended=None,route=event['route'],position=deepcopy(row['position']))
            else:need(active.get(key)==row['id'])
            contact=contacts[row['id']];contact['position']=deepcopy(row['position'])
            contact['lastRoute']=event['route'];contact['lastClock']=deepcopy(event['clock'])
            if phase in ('released','cancelled'):
                contact['ended']=deepcopy(event['clock']);contact['terminal']=phase;del active[key]
        if event['kind'] in ('end','cancel'):need(not any(key[0]==device for key in active))
    need(type(value['active']) is list and all(type(id_) is str for id_ in value['active']) and len(value['active'])==len(set(value['active']))
         and set(value['active'])==set(active.values()) and all(devices[key[0]]['alive'] for key in active))
    if previous is not None:
        validate(previous,previous['clockBefore']['epochMs'],previous['clockAfter']['epochMs'])
        need(value['instance']==previous['instance'] and same(birth,previous['birth'])
             and same(events[:len(previous['events'])],previous['events']) and len(events)>=len(previous['events']))
        clock(a,floor=previous['clockAfter'])
        for event in events[len(previous['events']):]:clock(event['clock'],floor=previous['clockAfter'])
        old=previous['devices'];need([r['id'] for r in value['devices'][:len(old)]]==[r['id'] for r in old])
        need(all(prior['alive'] or not devices[prior['id']]['alive'] for prior in old))
    return contacts


def pad(value):
    if value is None:return None
    exact(value,{'objectId','active','enabled','hidden','viewport','fixed','center','radius',
                 'moveValid','moveNativeId','moveOrigin','movePoint'})
    identifier(value['objectId'])
    need(all(type(value[key]) is bool for key in ('active','enabled','hidden','fixed','moveValid')))
    need(type(value['viewport']) is list and len(value['viewport'])==2
         and all(integer(n,1,10000) for n in value['viewport']) and number(value['radius'],.01,10000))
    for key in ('center','moveOrigin'):point(value[key])
    need(all(0<=n<limit for n,limit in zip(value['center'],value['viewport'])))
    if value['moveValid']:
        need(integer(value['moveNativeId'],0,2147483647));point(value['movePoint'])
    else:need(type(value['moveNativeId']) is int and value['moveNativeId']==-1 and value['movePoint'] is None)
    return value


def contacts(value):
    return validate(value,value['clockBefore']['epochMs'],value['clockAfter']['epochMs'])


def new_contact(before,after):
    """Exactly one original new contact, including UI-intercepted attempts."""
    old=contacts(before);new=validate(after,after['clockBefore']['epochMs'],after['clockAfter']['epochMs'],previous=before)
    need(before['active']==[] and len(new)==len(old)+1)
    added=set(new)-set(old);need(len(added)==1)
    identifier_=next(iter(added));return identifier_,deepcopy(new[identifier_])
