"""Original projected-avatar pixel changes; Rig/input/scene owners stay separate."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import io
import math
import time

from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.native_world_model_draws import avatar_draws
from adapters.world_render_evidence import original_pixels
from feature_journeys.contract import identifier
from feature_journeys.evidence import image_observation,rectangle
from overte_phone_graphics_effects import projected_box

VERSION=1
FRAME={'ticket','avatarBefore','avatarAfter','capture','draws'}


def original(run,frame,raw,pid,epoch,policy):
    identifier(run);exact(frame,FRAME);identifier(frame['ticket'])
    exact(policy,{'source','marker','subject'});need(policy['source']=='world-render-target')
    row=avatar_draws(frame['avatarBefore'],frame['avatarAfter'],frame['capture'],frame['draws'],pid,epoch)
    original_pixels(frame['capture'],raw)
    capture=frame['capture']['source'];extent=capture['targetExtent'];view=capture['renderTrace']['recordedView']
    box=projected_box(dict(position=[(a+b)/2 for a,b in zip(row['minimum'],row['maximum'])],
        dimensions=[b-a for a,b in zip(row['minimum'],row['maximum'])],rotation=[0,0,0,1]),view,extent)
    roi=[math.floor(box[0]),math.floor(box[1]),math.ceil(box[2]),math.ceil(box[3])]
    rectangle(roi,extent);subject=rectangle(policy['subject'],extent);marker=rectangle(policy['marker'],extent)
    need(roi[2]-roi[0]>=24 and roi[3]-roi[1]>=48)
    # The externally configured subject must actually cover this projected
    # avatar, without widening the common verifier into a mostly-background ROI.
    need(subject[0]<=roi[0] and subject[1]<=roi[1] and subject[2]>=roi[2] and subject[3]>=roi[3]
         and (subject[2]-subject[0])*(subject[3]-subject[1])<=2*(roi[2]-roi[0])*(roi[3]-roi[1]))
    need(not (max(roi[0],marker[0])<min(roi[2],marker[2]) and max(roi[1],marker[1])<min(roi[3],marker[3])))
    observation,subject_pixels=image_observation(raw,run,frame['ticket'],policy)
    return dict(row=row,roi=roi,image=observation,subject=subject_pixels)


def _stride(width,height):
    stride=max(1,math.ceil(math.sqrt(width*height/65536)))
    while math.ceil(width/stride)*math.ceil(height/stride)>65536:stride+=1
    return stride


def _steady(previous,current):
    left,right=previous['capture'],current['capture'];a,b=left['source'],right['source']
    need(left['instance']==right['instance'] and left['sequence']<right['sequence']
         and a['acquisitionSequence']<b['acquisitionSequence'] and a['renderTrace']['frameId']!=b['renderTrace']['frameId']
         and left['capturedEpochMs']<=right['requestedEpochMs']
         and all(a[key]==b[key] for key in ('sourceExtent','sourceViewport','targetExtent'))
         and a['renderTrace']['recordedView']==b['renderTrace']['recordedView'])
    before,after=previous['avatarAfter'],current['avatarBefore']
    need(before['instance']==after['instance'] and before['sequence']<after['sequence']
         and before['capturedEpochMs']<=after['requestedEpochMs'])
    for key in ('modelInstance','rigId','geometry','pose','cameraMode','view'):
        need(before['source'][key]==after['source'][key])


def measure(run,frame,raw,policy,pid,epoch_ms,guard,*,previous=None,monotonic=time.monotonic):
    """Return measured pixels, never requested animation or a visible-fragment mask.

    previous is an exact {frame, png} original pair. A full owner must reopen
    those bytes/metadata from its durable identity-bound evidence journal and
    join actual input/Rig/fixture/actor/cleanup sources before publication.
    """
    from PIL import Image
    need(integer(pid,1) and all(callable(value) for value in (epoch_ms,guard,monotonic)))
    started=last=monotonic();need(number(started,0,1e15))
    def budget():
        nonlocal last
        current=monotonic();need(number(current,last,1e15) and current-started<5);last=current
    need(guard() is not False);budget();epoch=epoch_ms();need(integer(epoch,1));budget();observed=last
    current=original(run,frame,raw,pid,epoch,policy);budget()
    value=dict(emotePixelsVersion=VERSION,ticket=frame['ticket'],frameId=frame['capture']['source']['renderTrace']['frameId'],
        imageSha256=current['image']['sha256'],modelInstance=current['row']['modelInstance'],
        geometryInstance=current['row']['geometryInstance'],bodyRoi=current['roi'],beforeTicket=None,beforeImageSha256=None,
        sampledBodyPixels=0,sampledControlPixels=0,bodyStride=None,controlStride=None,bodyChangedFraction=None,
        controlChangedFraction=None,subjectChangedFraction=None)
    if previous is not None:
        exact(previous,{'frame','png'});prior=previous['frame']
        old=original(run,prior,previous['png'],pid,prior['avatarAfter']['capturedEpochMs'],policy);budget()
        shared,_subject=image_observation(raw,run,frame['ticket'],policy,previous=old['subject'],changed=True);budget()
        _steady(prior,frame)
        need(prior['ticket']!=frame['ticket'])
        before_roi,after_roi=old['roi'],current['roi']
        roi=[min(before_roi[0],after_roi[0]),min(before_roi[1],after_roi[1]),
            max(before_roi[2],after_roi[2]),max(before_roi[3],after_roi[3])]
        extent=frame['capture']['source']['targetExtent']
        body_stride=_stride(roi[2]-roi[0],roi[3]-roi[1])
        control_stride=_stride(extent[0],extent[1])
        body_count=control_count=body_changed=control_changed=0
        marker=policy['marker'];margin=8
        excluded=[[roi[0]-margin,roi[1]-margin,roi[2]+margin,roi[3]+margin],
            [marker[0]-4,marker[1]-4,marker[2]+4,marker[3]+4]]
        with Image.open(io.BytesIO(previous['png'])) as left,Image.open(io.BytesIO(raw)) as right:
            left.load();right.load();need(left.size==right.size==tuple(extent));budget()
            for y in range(roi[1],roi[3],body_stride):
                budget()
                for x in range(roi[0],roi[2],body_stride):
                    body_count+=1
                    body_changed+=max(abs(a-b) for a,b in zip(left.getpixel((x,y))[:3],right.getpixel((x,y))[:3]))>25
            for y in range(0,extent[1],control_stride):
                budget()
                for x in range(0,extent[0],control_stride):
                    if any(r[0]<=x<r[2] and r[1]<=y<r[3] for r in excluded):continue
                    control_count+=1
                    control_changed+=max(abs(a-b) for a,b in zip(left.getpixel((x,y))[:3],right.getpixel((x,y))[:3]))>25
        need(1024<=body_count<=65536 and 1024<=control_count<=65536)
        body_fraction,control_fraction=body_changed/body_count,control_changed/control_count
        need(body_fraction>=.05 and control_fraction<=.01)
        value.update(bodyRoi=roi,beforeTicket=prior['ticket'],beforeImageSha256=old['image']['sha256'],
            sampledBodyPixels=body_count,sampledControlPixels=control_count,bodyStride=body_stride,controlStride=control_stride,
            bodyChangedFraction=body_fraction,controlChangedFraction=control_fraction,subjectChangedFraction=shared['subjectChangedFraction'])
    result=deepcopy(value);budget();need(guard() is not False);budget()
    delivered=epoch_ms();need(integer(delivered,epoch));budget()
    # Freshness belongs to the original current image/frame and source queries.
    # A historical comparison image deliberately keeps its original old time.
    final_epoch=max(delivered,epoch+math.ceil((last-observed)*1000))
    original(run,frame,raw,pid,final_epoch,policy);budget()
    final_epoch=max(delivered,epoch+math.ceil((last-observed)*1000))
    for stamp in (frame['avatarBefore']['capturedEpochMs'],frame['draws']['capturedEpochMs'],
            frame['capture']['source']['renderTrace']['recordedEpochMs']):fresh(stamp,final_epoch)
    return result
