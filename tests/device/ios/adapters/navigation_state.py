"""Original native scene, physics and view reads; no render/whole-arrival verdict."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import math
from pathlib import Path
import re

from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.native_graphics_subject import vector,rotation,text
from adapters.native_scene_loads import validate as scene_packet,continuity as scene_continuity,committed
from ios.adapters.places_model import IOSPlacesModel
from navigation_observation import POSITIONS,same_viewpoint,viewpoint_urls

VERSION=1
ACTION='feature-ios-navigation-state'
FILE=ACTION+'.json'
LIMIT=262144
MARKER_IDS=tuple('00000000-0000-4000-8000-'+str(index).zfill(12) for index in range(1,6))


def command(value):
    exact(value,{'schemaVersion','commandId','action','runId'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and value['action']==ACTION
         and type(value['commandId']) is str and re.fullmatch('ios-[a-f0-9]{32}',value['commandId'])
         and type(value['runId']) is str and re.fullmatch('[a-f0-9]{32}',value['runId']))
    return value


def validate(value,query,pid,epoch=None,previous=None):
    command(query)
    exact(value,{'iosNavigationStateVersion','requestId','runId','instance','sequence','processId','clockDomain',
                 'clockBefore','clockAfter','source'})
    need(type(value['iosNavigationStateVersion']) is int and value['iosNavigationStateVersion']==VERSION
         and value['requestId']==query['commandId'] and value['runId']==query['runId']
         and integer(pid,1) and type(value['processId']) is int and value['processId']==pid
         and type(value['instance']) is str and re.fullmatch('[a-f0-9]{32}',value['instance'])
         and integer(value['sequence'],1,1_000_000_000) and value['clockDomain']=='native-main-navigation')
    before,after=value['clockBefore'],value['clockAfter']
    for clock in (before,after):
        exact(clock,{'epochMs','monotonicMs'});need(integer(clock['epochMs'],1) and integer(clock['monotonicMs'],0))
    utc=after['epochMs']-before['epochMs'];mono=after['monotonicMs']-before['monotonicMs']
    need(0<=utc<1500 and 0<=mono<1500 and abs(utc-mono)<=250)
    if epoch is not None:fresh(after['epochMs'],epoch)
    source=value['source'];exact(source,{'foreground','sceneUrl','domain','avatar','view','markers','absentMarkerIds','sceneLoads'})
    need(type(source['foreground']) is bool and text(source['sceneUrl'],2048))
    domain=source['domain'];exact(domain,{'handlerConnected','serverless','protocol'})
    need(type(domain['handlerConnected']) is bool and type(domain['serverless']) is bool and text(domain['protocol'],32))
    avatar=source['avatar'];exact(avatar,{'feetPosition','orientation','velocity','inAir','flying','modelScale'})
    vector(avatar['feetPosition'],3,-1000000,1000000);vector(avatar['velocity'],3,-100000,100000)
    rotation(avatar['orientation']);need(type(avatar['inAir']) is bool and type(avatar['flying']) is bool
                                       and number(avatar['modelScale'],.0001,1000))
    view=source['view'];exact(view,{'position','rotation','mode','fieldOfViewDegrees','aspectRatio','perspective'})
    vector(view['position'],3,-1000000,1000000);rotation(view['rotation'])
    need(text(view['mode'],64) and number(view['fieldOfViewDegrees'],1,179) and number(view['aspectRatio'],.01,100)
         and type(view['perspective']) is bool)
    need(type(source['markers']) is list and len(source['markers'])<=5
         and type(source['absentMarkerIds']) is list and len(source['absentMarkerIds'])<=5)
    seen=[]
    for row in source['markers']:
        exact(row,{'id','name','type','position','rotation','dimensions','color','visible','collisionless'})
        need(type(row['id']) is str and row['id'] in MARKER_IDS and text(row['name'],256) and text(row['type'],64)
             and type(row['visible']) is bool and type(row['collisionless']) is bool)
        vector(row['position'],3,-1000000,1000000);rotation(row['rotation']);vector(row['dimensions'],3,.000001,1000000)
        vector(row['color'],3,0,255);need(all(type(v) is int for v in row['color']));seen.append(row['id'])
    for id_ in source['absentMarkerIds']:need(type(id_) is str and id_ in MARKER_IDS);seen.append(id_)
    need(len(seen)==5 and len(set(seen))==5
         and [row['id'] for row in source['markers']]==sorted(row['id'] for row in source['markers'])
         and source['absentMarkerIds']==sorted(source['absentMarkerIds']))
    scene_query=dict(query,action='feature-scene-load-observe')
    scene=source['sceneLoads'];scene_packet(scene,scene_query,pid,after['epochMs'])
    need(before['epochMs']<=scene['capturedEpochMs']<=after['epochMs'])
    need(len(json.dumps(value,allow_nan=False,ensure_ascii=False).encode())<=LIMIT)
    if previous is not None:
        validate(previous,dict(query,commandId=previous['requestId']),pid)
        need(value['instance']==previous['instance'] and value['sequence']>previous['sequence']
             and value['requestId']!=previous['requestId'] and value['runId']==previous['runId']
             and before['epochMs']>=previous['clockAfter']['epochMs'] and before['monotonicMs']>=previous['clockAfter']['monotonicMs'])
        scene_continuity(previous['source']['sceneLoads'],scene,pid)
    return value


def pose_ready(value,url,label):
    """Necessary actual arrival state. Original rendered pixels are ALSO required.

    Neither a requested URL, a parsed entity set nor settled physics proves
    that this scene reached a completed visible Vulkan frame.
    """
    need(type(label) is str and label in POSITIONS and same_viewpoint(url,viewpoint_urls(url)[label]))
    validate(value,dict(schemaVersion=1,commandId=value['requestId'],action=ACTION,runId=value['runId']),value['processId'])
    source=value['source'];avatar=source['avatar'];domain=source['domain']
    need(source['foreground'] is True and same_viewpoint(source['sceneUrl'],url)
         and domain['serverless'] is True and domain['handlerConnected'] is True and domain['protocol'] in ('http','https')
         and avatar['inAir'] is False and avatar['flying'] is False and source['absentMarkerIds']==[])
    committed(source['sceneLoads'],url)
    need(math.dist(avatar['feetPosition'],[POSITIONS[label][key] for key in ('x','y','z')])<=.75
         and math.sqrt(sum(v*v for v in avatar['velocity']))<=.15)
    fixture=json.loads((Path(__file__).resolve().parents[2]/'fixture'/'scene.json').read_text())
    wanted={row['id'].strip('{}'):row for row in fixture['Entities'] if row['id'].strip('{}') in MARKER_IDS}
    need(set(wanted)==set(MARKER_IDS))
    for row in source['markers']:
        original=wanted[row['id']]
        need(row['type']==original['type'] and row['name']==original['name'] and row['visible'] is True
             and row['collisionless']==original['collisionless'] and row['rotation']==[0,0,0,1]
             and row['color']==[original['color'][channel] for channel in ('red','green','blue')])
        for field in ('position','dimensions'):
            need(all(abs(actual-original[field][axis])<=1e-4 for actual,axis in zip(row[field],('x','y','z'))))
    return deepcopy(source['avatar'])


class IOSNavigationState(IOSPlacesModel):
    _action=ACTION
    _command=staticmethod(command)
    _validate=staticmethod(validate)
    _acquisition_key='iosNavigationStateAcquisitionVersion'
