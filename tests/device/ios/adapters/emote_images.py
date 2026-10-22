"""Original pre-HUD Vulkan image/actual marker/avatar geometry composition.

Images establish a current challenge and real changed subject pixels. Rig clip,
range/rate, restoration and independent replicated motion are separate joins.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import itertools
from adapters.graphics_subject_geometry import projected_box,near,rotate
from adapters.native_clock_join import validate_join
from adapters.native_feature_observation import exact,need
from adapters.native_vulkan_world_frame import validate as frame_packet,storage,absent,original_pixels
from adapters.normal_feature_state import context
from adapters.script_feature.history import same
from feature_journeys.contract import identifier
from feature_journeys.evidence import image_observation
from ios.adapters.emote_marker_measurements import body_preserved,orientation
from ios.adapters.emote_world import original as world_original,owned_marker,validate as world_packet,ACTION
from ios.adapters.graphics_history import follow_native
from ios.adapters import avatar_renderers

VERSION=1
FIELDS={'worldBefore','capture','retirement','worldAfter','clockJoin'}
REMOTE_FIELDS={'renderersBefore','renderersAfter'}


def originals(frame):return {key:frame[key] for key in frame.keys()-{'clockJoin'}}


def within(roi,box):
    need(type(roi) is list and len(roi)==4 and box[0]<=roi[0]<roi[2]<=box[2] and box[1]<=roi[1]<roi[3]<=box[3])


def avatar_box(bounds,view,extent):
    """Actual AABB projection, clipped to image edges; never invent geometry."""
    inverse=[-v for v in view['rotation'][:3]]+[view['rotation'][3]];points=[]
    for sides in itertools.product((0,1),repeat=3):
        world=[a+b*c for a,b,c in zip(bounds['corner'],bounds['dimensions'],sides)]
        camera=rotate([a-b for a,b in zip(world,view['position'])],inverse)+[1]
        clip=[sum(view['projection'][r*4+c]*camera[c] for c in range(4)) for r in range(4)]
        need(clip[3]>0);ndc=[n/clip[3] for n in clip[:3]];need(-1<=ndc[2]<=1)
        points.append([(ndc[0]+1)*extent[0]/2,(1-ndc[1])*extent[1]/2])
    return [max(0,min(p[0] for p in points)),max(0,min(p[1] for p in points)),
        min(extent[0],max(p[0] for p in points)),min(extent[1],max(p[1] for p in points))]


def compose(run,ticket,binding,frame,raw,policy,*,marker_nonce,marker_url,avatar_id=None):
    identifier(run);identifier(ticket);context(binding);exact(frame,FIELDS if avatar_id is None else FIELDS|REMOTE_FIELDS)
    need(type(policy) is dict and policy.get('source')=='world-render-target')
    clock=validate_join(frame['clockJoin'],originals(frame));pid=int(binding['processIdentity']);epoch=clock['nativeAfter']['capturedEpochMs']
    need(clock['nativeBefore']['processId']==clock['nativeAfter']['processId']==pid)
    before,after=frame['worldBefore'],frame['worldAfter']
    for packet in (before,after):world_original(packet);need(packet['processId']==pid and packet['runId']==run)
    world_packet(after,dict(schemaVersion=1,commandId=after['requestId'],action=ACTION,runId=run),pid,epoch,before)
    body_preserved(before,after)
    need(before['source']['tree']==after['source']['tree'])
    markers=[owned_marker(packet,marker_nonce,marker_url) for packet in (before,after)];need(same(markers[0],markers[1]))
    a,b=before['source']['view'],after['source']['view']
    need(a['mode']==b['mode']=='look at' and a['perspective'] is b['perspective'] is True
        and near(a['position'],b['position'],.001) and orientation(a['rotation'],b['rotation'])
        and near(a['fieldOfViewDegrees'],b['fieldOfViewDegrees'],.001) and near(a['aspectRatio'],b['aspectRatio'],.0001))
    capture,retirement=frame['capture'],frame['retirement']
    query=dict(schemaVersion=1,action='feature-vulkan-world-frame',operation='read',commandId=capture.get('commandId'),requestId=capture.get('requestId'))
    frame_packet(capture,query,pid,epoch);original_pixels(capture,raw)
    storage(retirement,dict(query,operation=retirement.get('operation'),commandId=retirement.get('commandId')),pid,epoch)
    need(absent(retirement) and retirement['instance']==capture['instance'] and retirement['sequence']>capture['sequence'])
    source=capture['source'];trace=source['renderTrace'];recorded=trace['recordedView']
    need(trace['forwardDrawCalls']>0 and near(recorded['position'],a['position'],.001)
        and orientation(recorded['rotation'],a['rotation']) and near(recorded['fieldOfViewDegrees'],a['fieldOfViewDegrees'],.001)
        and near(recorded['aspectRatio'],a['aspectRatio'],.0001))
    ordered=[before['clockBefore']['epochMs'],before['clockAfter']['epochMs'],capture['requestedEpochMs'],trace['recordedEpochMs'],
        source['submittedEpochMs'],source['fenceObservedEpochMs'],source['pixelsReadEpochMs'],capture['capturedEpochMs'],
        retirement['requestedEpochMs'],retirement['capturedEpochMs'],after['clockBefore']['epochMs'],after['clockAfter']['epochMs']]
    need(ordered==sorted(ordered) and clock['nativeBefore']['capturedEpochMs']<=ordered[0]<=ordered[-1]<=epoch
        and abs(a['aspectRatio']-source['targetExtent'][0]/source['targetExtent'][1])<=.01)
    within(policy['marker'],projected_box(markers[0],recorded,source['targetExtent']))
    if avatar_id is None:
        bounds=[]
        for packet in (before,after):
            avatar=packet['source']['avatar'];need(avatar['boundsReady']);bounds.append(avatar['bounds'])
    else:
        left,right=frame['renderersBefore'],frame['renderersAfter']
        avatar_renderers.original(left);avatar_renderers.validate(right,dict(schemaVersion=1,commandId=right['requestId'],
            action=avatar_renderers.ACTION,runId=run),pid,epoch,left)
        need(left['processId']==pid and left['runId']==run
            and before['clockAfter']['epochMs']<=left['clockBefore']['epochMs']<=left['clockAfter']['epochMs']<=capture['requestedEpochMs']
            and retirement['capturedEpochMs']<=right['clockBefore']['epochMs']<=right['clockAfter']['epochMs']<=after['clockBefore']['epochMs'])
        bounds=[avatar_renderers.bounds(packet,avatar_id,remote=True) for packet in (left,right)]
    for bound in bounds:within(policy['subject'],avatar_box(bound,recorded,source['targetExtent']))
    image,subject=image_observation(raw,run,ticket,policy)
    return dict(iosEmoteImageVersion=VERSION,capturedEpochMs=clock['hostBeforeEpochMs'],nativeEpochMs=ordered[0],
        frameId=trace['frameId'],image=image,markerId=markers[0]['id'],remoteSessionId=avatar_id,actualAvatarBounds=deepcopy(bounds[-1])),subject


def changed(run,binding,before,raw_before,ticket_before,after,raw_after,ticket_after,policy,*,marker_nonce,marker_url,avatar_id=None):
    left,subject=compose(run,ticket_before,binding,before,raw_before,policy,marker_nonce=marker_nonce,marker_url=marker_url,avatar_id=avatar_id)
    right,_=compose(run,ticket_after,binding,after,raw_after,policy,marker_nonce=marker_nonce,marker_url=marker_url,avatar_id=avatar_id)
    need(before['capture']['requestId']!=after['capture']['requestId'] and left['frameId']!=right['frameId']
        and after['clockJoin']['hostBeforeMonotonic']>=before['clockJoin']['hostAfterMonotonic'])
    follow_native(before['clockJoin']['nativeAfter'],after['clockJoin']['nativeBefore'])
    body_preserved(before['worldAfter'],after['worldBefore'])
    a,b=before['worldAfter']['source'],after['worldBefore']['source']
    need(a['tree']==b['tree'] and same(a['view'],b['view']) and same(a['cameraOrbit'],b['cameraOrbit'])
        and same(before['capture']['source']['renderTrace']['recordedView'],after['capture']['source']['renderTrace']['recordedView'])
        and same(before['capture']['source']['targetExtent'],after['capture']['source']['targetExtent'])
        and same(before['clockJoin']['nativeAfter']['graphics'],after['clockJoin']['nativeBefore']['graphics']))
    measured,_=image_observation(raw_after,run,ticket_after,policy,previous=subject,changed=True)
    return dict(iosEmoteImageChangeVersion=VERSION,before=left,after=right,subjectChangedFraction=measured['subjectChangedFraction'])
