"""Original local/remote Avatar geometry draws and same-view PNG qualification.

The remote path consumes the real second Phone's AvatarManager, camera, GPU
trace and PNG. It never manufactures a local AvatarRender observation for a
remote avatar or accepts a requested appearance/scale as a measurement.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import io
import math
import time
from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.native_avatar_render import validate as viewer_packet
from adapters.native_world_model_draws import validate as draw_packet
from adapters.world_render_evidence import original_pixels
from feature_journeys.contract import identifier
from feature_journeys.evidence import image_observation,rectangle
from overte_phone_avatar_people_native import validate as avatar_packet,session,digest
from overte_phone_avatar_people_measurements import request,native_model_semantics,entity_semantics
from overte_phone_graphics_effects import projected_box
from overte_phone_emote_pixels import _stride

VERSION=1
FRAME={'ticket','subjectSession','wearableIds','avatarBefore','avatarAfter','viewerBefore','viewerAfter','capture','draws'}


def near(a,b,tolerance):return len(a)==len(b) and all(abs(x-y)<=tolerance for x,y in zip(a,b))


def selected(packet,subject):
    rows=[row for row in [packet['source']['avatar'],*packet['source']['peers']] if row['sessionId']==subject]
    need(len(rows)==1);return rows[0]


def original(run,frame,raw,pid,epoch,policy):
    identifier(run);exact(frame,FRAME);identifier(frame['ticket']);subject=session(frame['subjectSession'])
    exact(policy,{'source','marker','subject'});need(policy['source']=='world-render-target')
    for packet in (frame['avatarBefore'],frame['avatarAfter']):
        avatar_packet(packet,request(packet),pid,epoch,previous=frame['avatarBefore'] if packet is frame['avatarAfter'] else None);need(packet['runId']==run)
    before,after=frame['avatarBefore'],frame['avatarAfter'];capture=frame['capture'];trace=capture['source']['renderTrace']
    need(before['instance']==after['instance'] and before['sequence']<after['sequence']
        and before['capturedEpochMs']<=trace['recordedEpochMs'] and capture['source']['capturedEpochMs']<=after['requestedEpochMs'])
    left,right=selected(before,subject),selected(after,subject)
    need(native_model_semantics(left)==native_model_semantics(right) and not left['replicated']
        and all(left[key] is True for key in ('loaded','visible','addedToScene','shouldRender'))
        and left['geometry'] is not None and left['geometry']['texturesLoaded']
        and abs(left['targetScale']-left['scale'])<=.005)
    for packet in (frame['viewerBefore'],frame['viewerAfter']):
        viewer_packet(packet,dict(schemaVersion=1,commandId=packet['requestId'],action='feature-avatar-render-observe'),pid,epoch)
        need(packet['instance']==before['instance'] and packet['source']['cameraMode']=='independent')
        live=packet['source']['view'];recorded=trace['recordedView']
        need(near(live['position'],recorded['position'],.0001) and near(live['projection'],recorded['projection'],.0001)
            and (near(live['rotation'],recorded['rotation'],.0001) or near(live['rotation'],[-v for v in recorded['rotation']],.0001)))
        for key in ('fieldOfViewDegrees','aspectRatio','nearClip','farClip'):need(abs(live[key]-recorded[key])<=.0001*max(1,abs(recorded[key])))
    va,vb=frame['viewerBefore'],frame['viewerAfter'];need(va['sequence']<vb['sequence']
        and va['capturedEpochMs']<=trace['recordedEpochMs'] and capture['source']['capturedEpochMs']<=vb['requestedEpochMs'])
    draw_packet(frame['draws'],dict(schemaVersion=1,commandId=frame['draws']['requestId'],action='feature-world-model-draws-observe',
        captureRequestId=capture['requestId']),pid,epoch,capture=capture);original_pixels(capture,raw)
    models=frame['draws']['source']['modelTrace']['models']
    def drawn(model,skinned):
        rows=[row for row in models if row['modelInstance']==model['modelInstance']];need(len(rows)==1);row=rows[0]
        need(model['loaded'] and model['visible'] and model['addedToScene'] and model['geometry'] is not None
            and model['geometry']['texturesLoaded'] and row['geometryInstance']==model['geometry']['instance']
            and row['loadedSourcePresent'] and row['loadedSourceSha256']==digest(model['geometry']['url'])
            and row['originalGeometryDrawCommands']==row['drawCommands'] and (row['skinnedDrawCommands']>0 if skinned else True))
        return row
    body=drawn(left,True);need(all(a<b for a,b in zip(body['minimum'],body['maximum'])))
    ids=frame['wearableIds'];need(type(ids) is list and len(ids)<=1 and len(set(ids))==len(ids))
    need(entity_semantics(before['source']['avatarEntities'])==entity_semantics(after['source']['avatarEntities']))
    rows=[body]
    for id in ids:
        session(id);matches=[row for row in before['source']['avatarEntities']['entities'] if row['entityId']==id];need(len(matches)==1)
        entity=matches[0];need(entity['parentId']==subject and entity['host']=='avatar' and entity['type']=='Model' and entity['visible']
            and entity['parentJointIndex']==left['hipsJoint'] and entity['model'] is not None)
        rows.append(drawn(entity['model'],False))
    low=[min(row['minimum'][axis] for row in rows) for axis in range(3)];high=[max(row['maximum'][axis] for row in rows) for axis in range(3)]
    extent=capture['source']['targetExtent'];view=trace['recordedView']
    box=projected_box(dict(position=[(a+b)/2 for a,b in zip(low,high)],dimensions=[b-a for a,b in zip(low,high)],rotation=[0,0,0,1]),view,extent)
    roi=[math.floor(box[0]),math.floor(box[1]),math.ceil(box[2]),math.ceil(box[3])]
    rectangle(roi,extent);configured=rectangle(policy['subject'],extent);marker=rectangle(policy['marker'],extent)
    need(roi[2]-roi[0]>=24 and roi[3]-roi[1]>=48 and configured[0]<=roi[0] and configured[1]<=roi[1]
        and configured[2]>=roi[2] and configured[3]>=roi[3]
        and (configured[2]-configured[0])*(configured[3]-configured[1])<=4*(roi[2]-roi[0])*(roi[3]-roi[1]))
    need(not (max(roi[0],marker[0])<min(roi[2],marker[2]) and max(roi[1],marker[1])<min(roi[3],marker[3])))
    observation,pixels=image_observation(raw,run,frame['ticket'],policy)
    return dict(row=body,rows=rows,roi=roi,image=observation,subject=pixels,subjectSession=left['sessionId'],
        perspective='local' if left['sessionId']==before['source']['avatar']['sessionId'] else 'remote')


def _steady(previous,current):
    a,b=previous['capture'],current['capture'];left,right=a['source'],b['source']
    need(a['instance']==b['instance'] and a['sequence']<b['sequence'] and left['acquisitionSequence']<right['acquisitionSequence']
        and a['capturedEpochMs']<=b['requestedEpochMs'] and left['renderTrace']['frameId']!=right['renderTrace']['frameId']
        and all(left[key]==right[key] for key in ('sourceExtent','sourceViewport','targetExtent'))
        and left['renderTrace']['recordedView']==right['renderTrace']['recordedView'] and previous['subjectSession']==current['subjectSession'])
    old,new=previous['avatarAfter'],current['avatarBefore'];need(old['instance']==new['instance'] and old['sequence']<new['sequence']
        and old['capturedEpochMs']<=new['requestedEpochMs'])
    old,new=selected(old,previous['subjectSession']),selected(new,current['subjectSession'])
    need(near(old['feetPosition'],new['feetPosition'],.005) and (near(old['orientation'],new['orientation'],.001)
        or near(old['orientation'],[-v for v in new['orientation']],.001)))


def measure(run,frame,raw,policy,pid,epoch_ms,guard,*,previous=None,monotonic=time.monotonic):
    """Return measured pixels, never requested appearance or scale or a visible-fragment mask.

    previous is an exact {frame, png} original pair. A full owner must reopen
    those bytes/metadata from its durable identity-bound evidence journal and
    join actual normal input/resource/fixture/actor/cleanup sources before publication.
    """
    from PIL import Image
    need(integer(pid,1) and all(callable(value) for value in (epoch_ms,guard,monotonic)))
    started=last=monotonic();need(number(started,0,1e15))
    def budget():
        nonlocal last
        current=monotonic();need(number(current,last,1e15) and current-started<5);last=current
    need(guard() is not False);budget();epoch=epoch_ms();need(integer(epoch,1));budget();observed=last
    current=original(run,frame,raw,pid,epoch,policy);budget()
    value=dict(avatarPeoplePixelsVersion=VERSION,ticket=frame['ticket'],frameId=frame['capture']['source']['renderTrace']['frameId'],
        imageSha256=current['image']['sha256'],modelInstance=current['row']['modelInstance'],
        geometryInstance=current['row']['geometryInstance'],subjectSession=current['subjectSession'],perspective=current['perspective'],bodyRoi=current['roi'],beforeTicket=None,beforeImageSha256=None,
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
