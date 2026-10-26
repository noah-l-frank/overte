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

VERSION=2
READS=(1,2)
FIELDS={'worldBefore','capture','retirement','worldAfter','clockJoin'}
REMOTE_FIELDS={'renderersBefore','renderersAfter'}


class EmoteImagePending(AssertionError):
    """Valid original images do not yet show independently changed pixels."""


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


def exclusive_subject(packet,avatar_id,policy,view,extent):
    """Conservatively exclude every other actual rendered Avatar AABB.

    This is the same original projection predicate as Avatar Images1. Unknown
    geometry fails closed; no self/remote body can supply another body's ROI.
    """
    roi=policy['subject'];inverse=[-v for v in view['rotation'][:3]]+[view['rotation'][3]]
    for row in packet['source']['avatars']:
        if row['sessionId']==avatar_id or not (row['addedToScene'] and row['shouldRender']):continue
        need(row['boundsReady']);bounds=row['bounds'];points=[]
        for sides in itertools.product((0,1),repeat=3):
            world=[a+b*c for a,b,c in zip(bounds['corner'],bounds['dimensions'],sides)]
            camera=rotate([a-b for a,b in zip(world,view['position'])],inverse)+[1]
            points.append([sum(view['projection'][r*4+c]*camera[c] for c in range(4)) for r in range(4)])
        if any(all(p[axis]<-p[3] for p in points) or all(p[axis]>p[3] for p in points) for axis in range(3)):continue
        box=avatar_box(bounds,view,extent)
        need(max(roi[0],box[0])>=min(roi[2],box[2]) or max(roi[1],box[1])>=min(roi[3],box[3]))


def compose(run,ticket,binding,frame,raw,policy,*,marker_nonce,marker_url,avatar_id=None,legacy=False):
    identifier(run);identifier(ticket);context(binding);need(type(legacy) is bool)
    exact(frame,FIELDS if legacy and avatar_id is None else FIELDS|REMOTE_FIELDS)
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
    marker_box=projected_box(markers[0],recorded,source['targetExtent'])
    within(policy['marker'],marker_box)
    # Exclude the entire actual marker projection, including pixels outside
    # the selected challenge crop. Those pixels can change with a ticket and
    # must never be counted as an Avatar pose change.
    subject=policy['subject'];need(marker_box[2]<=subject[0] or subject[2]<=marker_box[0]
        or marker_box[3]<=subject[1] or subject[3]<=marker_box[1])
    if legacy and avatar_id is None:
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
        if avatar_id is None:
            selected=[row['sessionId'] for row in left['source']['avatars'] if row['self']];need(len(selected)==1);selected=selected[0]
            from ios.adapters.emote_peer import session_sha
            need(before['source']['domain']['selfSha256']==after['source']['domain']['selfSha256']==session_sha(selected))
            bounds=[avatar_renderers.bounds(packet,selected,remote=False) for packet in (left,right)]
            need(all(same(bound,world['source']['avatar']['bounds']) and world['source']['avatar']['boundsReady'] for bound,world in zip(bounds,(before,after))))
        else:selected=avatar_id;bounds=[avatar_renderers.bounds(packet,selected,remote=True) for packet in (left,right)]
        if not legacy:
            for packet in (left,right):exclusive_subject(packet,selected,policy,recorded,source['targetExtent'])
    for bound in bounds:within(policy['subject'],avatar_box(bound,recorded,source['targetExtent']))
    image,subject=image_observation(raw,run,ticket,policy)
    return dict(iosEmoteImageVersion=1 if legacy else VERSION,capturedEpochMs=clock['hostBeforeEpochMs'],nativeEpochMs=ordered[0],
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
    try:measured,_=image_observation(raw_after,run,ticket_after,policy,previous=subject,changed=True)
    except AssertionError as error:
        # Both exact original PNGs, markers, ROIs, nonblank subjects and their
        # actual temporal/body/camera joins passed above. Only the separate
        # subject-change assertion remains pending; no result is committed.
        raise EmoteImagePending(str(error)) from error
    return dict(iosEmoteImageChangeVersion=VERSION,before=left,after=right,subjectChangedFraction=measured['subjectChangedFraction'])
