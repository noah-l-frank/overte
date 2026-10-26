"""Original avatar drive keys and 3D feet positions, never requested movement."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import math
import re
from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.script_feature.history import same
from ios.adapters.keyboard_source import identifier,sha,clock
from ios.adapters.places_model import IOSPlacesModel
from ios.adapters import scene_inventory as scene
from ios.adapters import lifecycle_touch as touch

VERSION=2
READS=(1,2)
ACTION='feature-ios-lifecycle-world'
FILE=ACTION+'.json'
LIMIT=262144
DRIVE_KEYS=12
FORWARD=2 # Native MyAvatar::TRANSLATE_Z; positive multiplies actual forward.


def command(value):
    exact(value,{'schemaVersion','commandId','action','runId'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['action']==ACTION
         and type(value['commandId']) is str and re.fullmatch('ios-[a-f0-9]{32}',value['commandId']) is not None)
    identifier(value['runId']);return value


def vector(value,count):need(type(value) is list and len(value)==count and all(number(n,-1e8,1e8) for n in value));return value


def validate(value,query,pid,epoch=None,previous=None):
    command(query);exact(value,{'iosLifecycleWorldVersion','requestId','runId','instance','sequence','processId','clockDomain','clockBefore','clockAfter','source'})
    need(type(value['iosLifecycleWorldVersion']) is int and value['iosLifecycleWorldVersion'] in READS
         and value['requestId']==query['commandId'] and value['runId']==query['runId'] and integer(pid,1)
         and type(value['processId']) is int and value['processId']==pid and integer(value['sequence'],1,1000000000)
         and value['clockDomain']=='native-main-lifecycle-world');identifier(value['instance'])
    a,b=value['clockBefore'],value['clockAfter'];clock(a);clock(b,floor=a)
    need(b['epochMs']-a['epochMs']<1500 and b['monotonicMs']-a['monotonicMs']<1500)
    if epoch is not None:fresh(b['epochMs'],epoch)
    source=value['source'];keys={'scene','domain','avatar','drive','lifecycle'}
    if value['iosLifecycleWorldVersion']>=2:keys|={'touch','pad'}
    exact(source,keys)
    if value['iosLifecycleWorldVersion']>=2:
        touch.validate(source['touch'],a['epochMs'],b['epochMs']);touch.pad(source['pad'])
    original=source['scene'];need(original['iosSceneInventoryVersion']>=2)
    scene.validate(original,dict(query,action=scene.ACTION),pid,b['epochMs'])
    need(a['epochMs']<=original['clockBefore']['epochMs']<=original['clockAfter']['epochMs']<=b['epochMs'])
    life=source['lifecycle'];exact(life,{'backgrounds','activations','launches'})
    need(all(integer(life[key],0,1000000) for key in life) and life['launches']>=1)
    domain=source['domain'];exact(domain,{'connected','serverless','domainId','selfSha256','avatarMixerSha256','addressSha256'})
    need(type(domain['connected']) is bool and type(domain['serverless']) is bool)
    need(type(domain['domainId']) is str and re.fullmatch('[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}',domain['domainId']) is not None)
    for key in ('selfSha256','addressSha256'):sha(domain[key])
    if domain['avatarMixerSha256'] is not None:sha(domain['avatarMixerSha256'])
    avatar=source['avatar'];exact(avatar,{'objectId','feetPosition','velocity','orientation','inAir','flying','modelScale'})
    identifier(avatar['objectId']);vector(avatar['feetPosition'],3);vector(avatar['velocity'],3);vector(avatar['orientation'],4)
    need(.9<=sum(n*n for n in avatar['orientation'])<=1.1 and number(avatar['modelScale'],.0001,1000)
         and type(avatar['inAir']) is bool and type(avatar['flying']) is bool)
    drive=source['drive'];exact(drive,{'raw','effective','disabled'});vector(drive['raw'],DRIVE_KEYS);vector(drive['effective'],DRIVE_KEYS)
    need(type(drive['disabled']) is list and len(drive['disabled'])==DRIVE_KEYS and all(type(n) is bool for n in drive['disabled']))
    need(all(drive['effective'][i]==(0 if drive['disabled'][i] else drive['raw'][i]) for i in range(DRIVE_KEYS)))
    if previous is not None:
        validate(previous,dict(query,commandId=previous['requestId']),pid)
        need(value['iosLifecycleWorldVersion']>=previous['iosLifecycleWorldVersion'])
        need(value['instance']==previous['instance'] and value['sequence']>previous['sequence'] and value['requestId']!=previous['requestId'])
        clock(a,floor=previous['clockAfter'])
        scene.validate(original,dict(query,action=scene.ACTION),pid,b['epochMs'],previous=previous['source']['scene'])
        need(all(life[key]>=previous['source']['lifecycle'][key] for key in life))
        if value['iosLifecycleWorldVersion']>=2 and previous['iosLifecycleWorldVersion']>=2:
            touch.validate(source['touch'],a['epochMs'],b['epochMs'],previous=previous['source']['touch'])
    return value


def original(value):
    return validate(value,dict(schemaVersion=1,commandId=value['requestId'],action=ACTION,runId=value['runId']),value['processId'])


def context(value):
    original(value);source=value['source'];s=source['scene']['source'];domain=source['domain']
    need(domain['connected'] and not domain['serverless'] and domain['avatarMixerSha256'] is not None and domain['domainId']!='00000000-0000-0000-0000-000000000000')
    need(s['tree']['complete'] and s['sceneLoads']['complete'] and s['sceneLoads']['pendingLeases']==0 and s['commitOrigin']['complete'])
    result=dict(processId=value['processId'],runId=value['runId'],instance=value['instance'],domain=deepcopy(domain),
                avatarId=source['avatar']['objectId'],modelScale=source['avatar']['modelScale'],tree=s['tree']['treeInstance'],
                sceneSource=s['sceneLoads']['instance'],sceneGeneration=s['sceneLoads']['currentGeneration'],commitOrigin=deepcopy(s['commitOrigin']))
    if value['iosLifecycleWorldVersion']>=2:
        result['touchInstance']=source['touch']['instance'];result['padId']=source['pad']['objectId'] if source['pad'] else None
    return result


def measure(baseline,current):
    """Partial measured world facts; original dispatched gestures remain required."""
    need(same(context(baseline),context(current)))
    if not same(baseline,current):validate(current,dict(schemaVersion=1,commandId=current['requestId'],action=ACTION,runId=current['runId']),baseline['processId'],previous=baseline)
    first,last=baseline['source'],current['source']
    for value in (first,last):need(not value['avatar']['inAir'] and not value['avatar']['flying'])
    need(all(n==0 for n in first['drive']['raw']) and all(n==0 for n in first['drive']['effective']))
    drive=last['drive']['effective'];need(all(n==0 for i,n in enumerate(drive) if i!=FORWARD) and drive[FORWARD]>=0)
    delta=[a-b for a,b in zip(last['avatar']['feetPosition'],first['avatar']['feetPosition'])]
    return dict(heldInputs=['forward'] if drive[FORWARD]>0 else [],positionDelta=dict(zip(('x','y','z'),delta)),
                worldDisplacement=math.sqrt(sum(n*n for n in delta)))


def stationary(values):
    """Three seconds about one original 3D anchor; a constant-radius arc fails."""
    need(type(values) is list and 4<=len(values)<=64)
    first=values[0];original(first);anchor=first['source']['avatar']['feetPosition']
    for index,value in enumerate(values):
        facts=measure(first,value);need(facts['heldInputs']==[])
        need(math.dist(anchor,value['source']['avatar']['feetPosition'])<=.025)
        if index:
            previous=values[index-1];validate(value,dict(schemaVersion=1,commandId=value['requestId'],action=ACTION,runId=value['runId']),value['processId'],previous=previous)
            need(value['clockBefore']['monotonicMs']-previous['clockAfter']['monotonicMs']<=1500
                 and value['clockBefore']['epochMs']-previous['clockAfter']['epochMs']<=1500)
    before,after=first['clockAfter'],values[-1]['clockBefore']
    need(after['epochMs']-before['epochMs']>=3000 and after['monotonicMs']-before['monotonicMs']>=3000)
    return dict(nativeMilliseconds=after['epochMs']-before['epochMs'],samples=len(values),position=deepcopy(anchor))


def contact_attempt(baseline,current):
    """One actual ordinary contact, separate from acceptance or displacement."""
    need(baseline['iosLifecycleWorldVersion']>=2 and current['iosLifecycleWorldVersion']>=2)
    need(same(context(baseline),context(current)))
    validate(current,dict(schemaVersion=1,commandId=current['requestId'],action=ACTION,runId=current['runId']),
             baseline['processId'],previous=baseline)
    id_,row=touch.new_contact(baseline['source']['touch'],current['source']['touch'])
    return dict(contactId=id_,**row)


def active_forward(baseline,current):
    """Current native pad ownership AND independently measured forward effect.

    A completed W3C call, a world-routed touch or an old pressed event cannot
    substitute for this still-active contact/actual plugin/drive-key join.
    """
    row=contact_attempt(baseline,current);source=current['source'];pad=touch.pad(source['pad'])
    need(pad is not None and pad['active'] and pad['enabled'] and not pad['hidden'] and pad['fixed'] and pad['moveValid'])
    journal=source['touch'];need(journal['active']==[row['contactId']] and row['ended'] is None
         and row['route']==row['lastRoute']=='world' and row['nativeId']==pad['moveNativeId']
         and same(row['position'],pad['movePoint']))
    events=[event for event in journal['events'] if any(p['id']==row['contactId'] for p in event['points'])]
    need(all(event['route']=='world' for event in events))
    first=next(p for p in events[0]['points'] if p['id']==row['contactId'])
    origin=baseline['source']['pad'];need(origin is not None and origin['objectId']==pad['objectId']
        and same(origin['viewport'],pad['viewport']) and same(origin['center'],pad['center']) and origin['radius']==pad['radius'])
    need(math.dist(first['position'],pad['center'])<=pad['radius'] and same(pad['moveOrigin'],pad['center'])
         and pad['movePoint'][1]<pad['moveOrigin'][1])
    facts=measure(baseline,current);need(facts['heldInputs']==['forward'])
    need(.3<=facts['worldDisplacement']<=3 and abs(facts['positionDelta']['y'])<=.05
         and 0<=journal['clockBefore']['epochMs']-row['began']['epochMs']<=12000
         and 0<=journal['clockBefore']['monotonicMs']-row['began']['monotonicMs']<=12000)
    return dict(contact=row,facts=facts)


def contact_released(held,current):
    """Actual terminal event for that held contact, not native quiet yet."""
    need(same(context(held),context(current)))
    validate(current,dict(schemaVersion=1,commandId=current['requestId'],action=ACTION,runId=current['runId']),
             held['processId'],previous=held)
    before=touch.contacts(held['source']['touch']);after=touch.contacts(current['source']['touch'])
    ids=held['source']['touch']['active'];need(len(ids)==1 and current['source']['touch']['active']==[])
    id_=ids[0];need(before[id_]['ended'] is None and id_ in after and after[id_]['ended'] is not None
                    and after[id_]['terminal'] in ('released','cancelled'))
    need(set(before)==set(after) and current['source']['pad'] is not None and not current['source']['pad']['moveValid']
         and all(n==0 for n in current['source']['drive']['raw']) and all(n==0 for n in current['source']['drive']['effective']))
    return deepcopy(after[id_])


class IOSLifecycleWorld(IOSPlacesModel):
    _action=ACTION
    _command=staticmethod(command)
    _validate=staticmethod(validate)
    _acquisition_key='iosLifecycleWorldAcquisitionVersion'
    _limit=LIMIT
