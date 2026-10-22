"""Actual scene pixels joined to original native arrival state and GPU lifetime.

This prerequisite is not canonical challenge-image or whole-journey evidence.
The owning operation must still retain the immutable originals and its durable
one-send frame ownership, independent actor and per-ticket challenge evidence.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from io import BytesIO
import math

from adapters.native_clock_join import validate_join,digest
from adapters.native_feature_observation import exact,integer,need
from adapters.native_vulkan_world_frame import validate as frame_packet,storage,absent,original_pixels
from adapters.graphics_subject_geometry import near,rotate
from adapters.render_view import recorded_view
from adapters.normal_feature_state import context
from feature_journeys.contract import identifier
from ios.adapters.navigation_state import validate as state_packet,command as state_command,pose_ready

VERSION=1
PIXELS_VERSION=1
FIELDS={'navigationBefore','capture','retirement','navigationAfter','clockJoin'}


def originals(frame):return {name:frame[name] for name in FIELDS-{'clockJoin'}}


def project(point,view,extent):
    """Project a measured fixture point using the original GPU recorded matrix."""
    recorded_view(view)
    inverse=[-v for v in view['rotation'][:3]]+[view['rotation'][3]]
    camera=rotate([a-b for a,b in zip(point,view['position'])],inverse)+[1]
    clip=[sum(view['projection'][row*4+col]*camera[col] for col in range(4)) for row in range(4)]
    if clip[3]<=0:return None
    ndc=[v/clip[3] for v in clip[:3]]
    if not all(-1<v<1 for v in ndc):return None
    return [(ndc[0]+1)*extent[0]/2,(1-ndc[1])*extent[1]/2]


def wall_pixels(raw,view,extent,wall):
    """Visible original purple collision-wall face, excluding guessed screen ROIs.

    Fixed conservative chroma thresholds qualify this controlled fixture. They
    do not purport to calibrate arbitrary production lighting or physical iOS
    rendering, which remains untested. Unknown/offscreen/occluded is a failure.
    """
    from PIL import Image
    recorded_view(view)
    need(type(extent) is list and len(extent)==2 and all(integer(v,128,4096) for v in extent)
         and wall['rotation']==[0,0,0,1] and wall['color']==[180,80,180])
    front=wall['position'][2]+wall['dimensions'][2]/2
    need(view['position'][2]>front+view['nearClip'])
    points=[];radius=max(1,min(8,round(min(extent)*.005)))
    with Image.open(BytesIO(raw)) as original:
        need(original.format=='PNG' and original.mode=='RGBA' and list(original.size)==extent)
        original.load();image=original.convert('RGB')
        for horizontal in (.15,.325,.5,.675,.85):
            for vertical in (.55,.7,.825):
                point=[wall['position'][0]+(horizontal-.5)*wall['dimensions'][0],
                       wall['position'][1]+(vertical-.5)*wall['dimensions'][1],front]
                projected=project(point,view,extent)
                if projected is None:continue
                x,y=[round(v) for v in projected]
                if not radius<=x<extent[0]-radius or not radius<=y<extent[1]-radius:continue
                patch=image.crop((x-radius,y-radius,x+radius+1,y+radius+1))
                pixels=[patch.getpixel((px,py)) for py in range(patch.height) for px in range(patch.width)]
                purple=sum(min(r,b)>45 and min(r,b)>g+20 and abs(r-b)<45 for r,g,b in pixels)/len(pixels)
                points.append(dict(world=point,pixel=[x,y],purpleFraction=purple))
    need(len(points)>=6 and len({tuple(row['pixel']) for row in points})==len(points)
         and sum(row['purpleFraction']>=.8 for row in points)/len(points)>=.8)
    return dict(iosNavigationScenePixelsVersion=PIXELS_VERSION,profile='controlled-purple-wall-v1',
                extent=deepcopy(extent),radius=radius,samples=points)


def compose(run,binding,frame,raw,*,url,label,capture_query):
    """Validate already acquired originals without minting fresh source clocks."""
    identifier(run);context(binding);exact(frame,FIELDS);pid=int(binding['processIdentity']);need(pid>0)
    clock=validate_join(frame['clockJoin'],originals(frame));native_first,native_last=clock['nativeBefore'],clock['nativeAfter']
    need(native_first['processId']==native_last['processId']==pid
         and native_first['lifecycle']==native_last['lifecycle'])
    before,after=frame['navigationBefore'],frame['navigationAfter']
    for packet in (before,after):
        state_packet(packet,state_command(dict(schemaVersion=1,commandId=packet.get('requestId'),
            action='feature-ios-navigation-state',runId=run)),pid,native_last['capturedEpochMs'])
        pose_ready(packet,url,label)
    state_packet(after,dict(schemaVersion=1,commandId=after['requestId'],action='feature-ios-navigation-state',runId=run),
                 pid,native_last['capturedEpochMs'],before)
    first,last=before['source'],after['source']
    need(first['sceneLoads']['currentGeneration']==last['sceneLoads']['currentGeneration']
         and first['sceneLoads']['requests']==last['sceneLoads']['requests'] and first['markers']==last['markers']
         and first['domain']==last['domain'] and first['sceneUrl']==last['sceneUrl']
         and before['iosNavigationStateVersion']==after['iosNavigationStateVersion']
         and first.get('challengeMarker')==last.get('challengeMarker')
         and math.dist(first['avatar']['feetPosition'],last['avatar']['feetPosition'])<=.025
         and near(first['avatar']['orientation'],last['avatar']['orientation'],.0001)
         and near(first['avatar']['modelScale'],last['avatar']['modelScale'],.0001))
    capture,retired=frame['capture'],frame['retirement'];frame_packet(capture,capture_query,pid,native_last['capturedEpochMs'])
    original_pixels(capture,raw)
    storage(retired,dict(schemaVersion=1,action='feature-vulkan-world-frame',operation=retired.get('operation'),
        requestId=capture_query['requestId'],commandId=retired.get('commandId')),pid,native_last['capturedEpochMs'])
    need(absent(retired) and retired['instance']==capture['instance'] and retired['sequence']>capture['sequence']
         and retired['commandId']!=capture['commandId'])
    source=capture['source'];trace=source['renderTrace'];recorded=trace['recordedView']
    need(trace['forwardDrawCalls']>0)
    for live in (first['view'],last['view']):
        need(live['perspective'] is True and near(recorded['position'],live['position'],.001)
             and (near(recorded['rotation'],live['rotation'],.0001) or near(recorded['rotation'],[-v for v in live['rotation']],.0001))
             and near(recorded['fieldOfViewDegrees'],live['fieldOfViewDegrees'],.001)
             and near(recorded['aspectRatio'],live['aspectRatio'],.0001))
    need(first['view']['mode']==last['view']['mode'])
    ordered=[native_first['capturedEpochMs'],before['clockBefore']['epochMs'],before['clockAfter']['epochMs'],
        capture['requestedEpochMs'],trace['recordedEpochMs'],source['submittedEpochMs'],source['fenceObservedEpochMs'],
        source['pixelsReadEpochMs'],capture['capturedEpochMs'],retired['requestedEpochMs'],retired['capturedEpochMs'],
        after['clockBefore']['epochMs'],after['clockAfter']['epochMs'],native_last['capturedEpochMs']]
    need(ordered==sorted(ordered) and all(integer(v,1) for v in ordered))
    extent=source['targetExtent'];need(abs(extent[0]/extent[1]-recorded['aspectRatio'])<=.01)
    wall=next(row for row in last['markers'] if row['name']=='OVERTE_E2E_COLLISION_WALL')
    pixels=wall_pixels(raw,recorded,extent,wall)
    return dict(iosNavigationRenderedStateVersion=VERSION,runId=run,binding=deepcopy(binding),location=label,
        originalsSha256=digest(originals(frame)),imageSha256=source['image']['sha256'],pixelSha256=source['image']['pixelSha256'],
        frameId=trace['frameId'],nativeEpochMs=before['clockBefore']['epochMs'],
        acquiredHostEpochMs=clock['hostBeforeEpochMs'],sceneGeneration=last['sceneLoads']['currentGeneration'],pixels=pixels)
