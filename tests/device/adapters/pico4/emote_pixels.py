"""Measure original avatar pixels in both actual Pico eye cameras.

Pixel differences are measurements; the full owner must independently join the
normal input, original advancing Rig/clip, scene/actor and cleanup sources.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import io
import math
import time

from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.pico4.emote_model_draws import avatar_draws,camera_key
from adapters.stereo_graphics_pixels import project
from adapters.world_render_evidence import original_pixels
from feature_journeys.contract import identifier
from feature_journeys.evidence import image_observation,rectangle

VERSION=1
FRAME={'ticket','avatarBefore','avatarAfter','capture','draws'}
EYES=('left','right')


def stride(width,height):
    value=max(1,math.ceil(math.sqrt(width*height/65536)))
    while math.ceil(width/value)*math.ceil(height/value)>65536:value+=1
    return value


def model_cameras(capture,row):
    """Select only original camera rows actually used by this model's draws."""
    result={eye:[] for eye in EYES}
    available={camera_key(batch['sequence'],camera):camera for batch in capture['source']['renderTrace']['cameraBatches']
        if batch['role']=='forward' for camera in batch['cameras']}
    for use in row['cameraUses']:
        camera=available[camera_key(use['batchSequence'],use)]
        value={key:deepcopy(camera[key]) for key in ('view','projection','viewport')}
        if value not in result[use['eye']]:result[use['eye']].append(value)
    need(all(result.values()));return result


def projected_body(row,cameras,source,eye):
    boxes=[]
    for camera in cameras:
        points=[project([x,y,z],camera,source,eye) for x in (row['minimum'][0],row['maximum'][0])
            for y in (row['minimum'][1],row['maximum'][1]) for z in (row['minimum'][2],row['maximum'][2])]
        boxes.append([math.floor(min(p[0] for p in points)),math.floor(min(p[1] for p in points)),
            math.ceil(max(p[0] for p in points)),math.ceil(max(p[1] for p in points))])
    # All used cameras must agree within original pixel rounding. Selecting a
    # convenient view from a multi-camera/ambiguous source cannot qualify it.
    need(all(box==boxes[0] for box in boxes));roi=boxes[0]
    rectangle(roi,source['targetExtent']);need(roi[2]-roi[0]>=24 and roi[3]-roi[1]>=48)
    return roi


def original(run,frame,raw,pid,epoch,policy):
    identifier(run);exact(frame,FRAME);identifier(frame['ticket'])
    exact(policy,{'picoEmotePixelPolicyVersion','source','eyes'})
    need(type(policy['picoEmotePixelPolicyVersion']) is int and policy['picoEmotePixelPolicyVersion']==VERSION
        and policy['source']=='world-render-target');exact(policy['eyes'],set(EYES))
    row=avatar_draws(frame['avatarBefore'],frame['avatarAfter'],frame['capture'],frame['draws'],pid,epoch)
    original_pixels(frame['capture'],raw);source=frame['capture']['source'];cameras=model_cameras(frame['capture'],row)
    result={}
    for index,eye in enumerate(EYES):
        expected=policy['eyes'][eye];exact(expected,{'marker','subject'})
        marker=rectangle(expected['marker'],source['targetExtent']);subject=rectangle(expected['subject'],source['targetExtent'])
        viewport=source['stereo']['eyes'][index]['targetViewport'];height=source['targetExtent'][1]
        region=[viewport[0],height-viewport[1]-viewport[3],viewport[0]+viewport[2],height-viewport[1]]
        for roi in (marker,subject):need(region[0]<=roi[0]<roi[2]<=region[2] and region[1]<=roi[1]<roi[3]<=region[3])
        body=projected_body(row,cameras[eye],source,eye)
        need(subject[0]<=body[0] and subject[1]<=body[1] and subject[2]>=body[2] and subject[3]>=body[3]
            and (subject[2]-subject[0])*(subject[3]-subject[1])<=2*(body[2]-body[0])*(body[3]-body[1]))
        observation,_pixels=image_observation(raw,run,frame['ticket'],dict(source=policy['source'],**expected))
        result[eye]=dict(bodyRoi=body,imageSha256=observation['sha256'],cameras=cameras[eye])
    return dict(row=row,eyes=result)


def steady(previous,current,old,new):
    left,right=previous['capture'],current['capture'];a,b=left['source'],right['source']
    need(left['instance']==right['instance'] and left['sequence']<right['sequence']
        and a['acquisitionSequence']<b['acquisitionSequence'] and a['renderTrace']['frameId']!=b['renderTrace']['frameId']
        and a['stereo']['frameIndex']!=b['stereo']['frameIndex'] and a['stereo']['executionSequence']<b['stereo']['executionSequence']
        and a['presentation']['submissionSequence']<b['presentation']['submissionSequence']
        and left['capturedEpochMs']<=right['requestedEpochMs']
        and all(a[key]==b[key] for key in ('sourceExtent','sourceViewport','targetExtent')))
    before,after=previous['avatarAfter'],current['avatarBefore']
    need(before['instance']==after['instance'] and before['sequence']<after['sequence'] and before['capturedEpochMs']<=after['requestedEpochMs'])
    for key in ('modelInstance','rigId','geometry','pose','cameraMode'):need(before['source'][key]==after['source'][key])
    motion={}
    for eye in EYES:
        first,last=old['eyes'][eye]['cameras'],new['eyes'][eye]['cameras']
        need(len(first)==len(last)==1)
        # Measured headset/late-pose changes are retained, never replaced by a
        # fixed Phone camera. A larger change needs another original pair.
        need(first[0]['viewport']==last[0]['viewport']
            and all(abs(x-y)<=.002 for x,y in zip(first[0]['view'],last[0]['view']))
            and all(abs(x-y)<=.002 for x,y in zip(first[0]['projection'],last[0]['projection'])))
        motion[eye]=dict(maximumViewElementChange=max(abs(x-y) for x,y in zip(first[0]['view'],last[0]['view'])),
            maximumProjectionElementChange=max(abs(x-y) for x,y in zip(first[0]['projection'],last[0]['projection'])))
    return motion


def differences(left,right,body,marker,region,budget):
    body_stride=stride(body[2]-body[0],body[3]-body[1]);control_stride=stride(region[2]-region[0],region[3]-region[1])
    count=changed=controls=control_changed=0
    for y in range(body[1],body[3],body_stride):
        budget()
        for x in range(body[0],body[2],body_stride):
            count+=1;changed+=max(abs(a-b) for a,b in zip(left.getpixel((x,y))[:3],right.getpixel((x,y))[:3]))>25
    excluded=[[body[0]-8,body[1]-8,body[2]+8,body[3]+8],[marker[0]-4,marker[1]-4,marker[2]+4,marker[3]+4]]
    for y in range(region[1],region[3],control_stride):
        budget()
        for x in range(region[0],region[2],control_stride):
            if any(r[0]<=x<r[2] and r[1]<=y<r[3] for r in excluded):continue
            controls+=1;control_changed+=max(abs(a-b) for a,b in zip(left.getpixel((x,y))[:3],right.getpixel((x,y))[:3]))>25
    need(1024<=count<=65536 and 1024<=controls<=65536)
    body_fraction,control_fraction=changed/count,control_changed/controls
    need(body_fraction>=.05 and control_fraction<=.01)
    return dict(bodyRoi=body,sampledBodyPixels=count,sampledControlPixels=controls,bodyStride=body_stride,controlStride=control_stride,
        bodyChangedFraction=body_fraction,controlChangedFraction=control_fraction)


def measure(run,frame,raw,policy,pid,epoch_ms,guard,*,previous=None,monotonic=time.monotonic):
    """Return per-eye raw pixel measurements, without an animation verdict.

    previous is an exact original {frame,png} archive. Historical reduction uses
    only its original source interval. The current image keeps all native times.
    """
    from PIL import Image
    need(integer(pid,1) and all(callable(value) for value in (epoch_ms,guard,monotonic)))
    started=last=monotonic();need(number(started,0,1e15))
    def budget():
        nonlocal last
        current=monotonic();need(number(current,last,1e15) and current-started<5);last=current
    need(guard() is not False);budget();epoch=epoch_ms();need(integer(epoch,1));budget();observed=last
    current=original(run,frame,raw,pid,epoch,policy);budget()
    result=dict(picoEmotePixelsVersion=VERSION,ticket=frame['ticket'],frameId=frame['capture']['source']['renderTrace']['frameId'],
        imageSha256=frame['capture']['source']['image']['sha256'],pixelSha256=frame['capture']['source']['image']['pixelSha256'],
        modelInstance=current['row']['modelInstance'],geometryInstance=current['row']['geometryInstance'],
        beforeTicket=None,beforeImageSha256=None,eyes={eye:dict(bodyRoi=current['eyes'][eye]['bodyRoi']) for eye in EYES})
    if previous is not None:
        exact(previous,{'frame','png'});prior=previous['frame'];need(prior['ticket']!=frame['ticket'])
        old=original(run,prior,previous['png'],pid,prior['avatarAfter']['capturedEpochMs'],policy);budget();motion=steady(prior,frame,old,current)
        extent=frame['capture']['source']['targetExtent'];height=extent[1]
        with Image.open(io.BytesIO(previous['png'])) as left,Image.open(io.BytesIO(raw)) as right:
            left.load();right.load();need(left.size==right.size==tuple(extent));budget()
            for index,eye in enumerate(EYES):
                before,after=old['eyes'][eye]['bodyRoi'],current['eyes'][eye]['bodyRoi']
                body=[min(before[0],after[0]),min(before[1],after[1]),max(before[2],after[2]),max(before[3],after[3])]
                viewport=frame['capture']['source']['stereo']['eyes'][index]['targetViewport']
                region=[viewport[0],height-viewport[1]-viewport[3],viewport[0]+viewport[2],height-viewport[1]]
                result['eyes'][eye]={**differences(left,right,body,policy['eyes'][eye]['marker'],region,budget),**motion[eye]}
        result.update(beforeTicket=prior['ticket'],beforeImageSha256=old['eyes']['left']['imageSha256'])
    retained=deepcopy(result);budget();need(guard() is not False);budget()
    delivered=epoch_ms();need(integer(delivered,epoch));budget()
    final=max(delivered,epoch+math.ceil((last-observed)*1000))
    original(run,frame,raw,pid,final,policy);budget()
    # Revalidation/PNG decoding is also inside the original native age window.
    need(guard() is not False);budget();clock=epoch_ms();need(integer(clock,delivered));budget()
    final=max(clock,epoch+math.ceil((last-observed)*1000))
    for stamp in (frame['avatarBefore']['capturedEpochMs'],frame['avatarAfter']['capturedEpochMs'],frame['draws']['capturedEpochMs'],
            frame['capture']['source']['renderTrace']['recordedEpochMs']):fresh(stamp,final)
    return retained
