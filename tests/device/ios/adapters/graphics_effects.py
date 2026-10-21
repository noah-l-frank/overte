"""Measured haze/mirror subject pixels on original, unmodified iOS screens."""
# Pure ROI algorithm derives from frozen Phone fe4684bf46585088370b3a328a738f147e670b97.
# iOS source frames, clocks, native-screen geometry and interval joins are separate.
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
from io import BytesIO
import math
import time

from adapters.native_feature_observation import fresh,integer,need,number
from adapters.graphics_subject_geometry import projected_box,steady_subject
from adapters.script_feature.history import same
from feature_journeys.contract import identifier
from feature_journeys.graphics_fixture import subject_ids
from feature_journeys.graphics_resources import validate_status
from ios.adapters.graphics_measurements import compose

VERSION=1


def compare(run,feature,fixture_url,binding,before,raw_before,after,raw_after,policy,provider_instance,
            epoch_ms,guard,*,monotonic=time.monotonic):
    """No requested state argument; direction follows actual native setting.

    Historical before/after joins validate originals. A separately sampled host
    clock must still qualify the newly acquired after interval at both ends of
    this bounded computation. Original native clocks are never compared to it.
    """
    from PIL import Image
    identifier(run);need(feature in ('haze','mirror') and all(callable(fn) for fn in (epoch_ms,guard,monotonic)))
    started=previous=monotonic();need(number(started,0,1e15))
    def bound():
        nonlocal previous
        current=monotonic();need(number(current,previous,1e15) and current-started<5 and guard() is not False);previous=current
    bound();epoch=epoch_ms();need(integer(epoch,1));bound()
    first=compose(run,before['provider']['ticket'],fixture_url,binding,before,raw_before,policy,
        provider_instance=provider_instance,after_epoch=math.floor(before['clockJoin']['hostBeforeEpochMs']))
    last=compose(run,after['provider']['ticket'],fixture_url,binding,after,raw_after,policy,
        provider_instance=provider_instance,after_epoch=math.floor(after['clockJoin']['hostBeforeEpochMs']))
    fresh(math.floor(last['capturedEpochMs']),epoch)
    need(before['provider']['ticket']!=after['provider']['ticket']
         and 0<=after['clockJoin']['hostBeforeEpochMs']-before['clockJoin']['hostAfterEpochMs']<=45000)
    validate_status(after['provider'],instance=provider_instance,run=run,url=fixture_url.rsplit('/runs/',1)[0],
        request=after['provider']['requestId'],previous=before['provider'])
    for source in ('nativeBefore','nativeAfter','subjectBefore','subjectAfter','frameBefore','frameAfter'):
        need(before[source]['instance']==after[source]['instance'] and after[source]['sequence']>before[source]['sequence'])
    for source in ('graphics','tablet'):
        need(before[source]['instance']==after[source]['instance']
             and after[source]['sourceSequence']>before[source]['sourceSequence'])
    need(before['clockJoin']['nativeAfter']['instance']==after['clockJoin']['nativeBefore']['instance']
         and after['clockJoin']['nativeBefore']['sequence']>before['clockJoin']['nativeAfter']['sequence']
         and same(before['nativeAfter']['lifecycle'],after['nativeBefore']['lifecycle']))
    field='hazeSetting' if feature=='haze' else 'mirrorsSetting'
    left,right=before['nativeAfter']['graphics'],after['nativeBefore']['graphics']
    need(left[field]!=right[field] and all(same(left[key],right[key]) for key in left if key!=field))
    need(all(actual['state'][feature]==actual['state'][feature+'Pass'] for actual in (first,last)))
    steady_subject(before['subjectAfter'],after['subjectBefore'])
    a,b=before['frameAfter']['source'],after['frameBefore']['source']
    need(all(same(a[key],b[key]) for key in ('sourceExtent','targetExtent'))
         and same(a['renderTrace']['recordedView'],b['renderTrace']['recordedView'])
         and first['screenViewport']==last['screenViewport'] and before['screen']['extent']==after['screen']['extent'])
    rows={row['id']:row for row in after['subjectBefore']['source']['entities']};ids=subject_ids(run)
    target=rows[ids['fog-board' if feature=='haze' else 'reflector']]
    view=b['renderTrace']['recordedView'];extent=b['targetExtent'];offset=last['screenViewport'][:2]
    def projected(row):
        box=projected_box(row,view,extent)
        return [box[0]+offset[0],box[1]+offset[1],box[2]+offset[0],box[3]+offset[1]]
    box=projected(target);marker=projected(rows[ids['marker']])
    dx=(box[2]-box[0])*.25;dy=(box[3]-box[1])*.25
    roi=[math.ceil(box[0]+dx),math.ceil(box[1]+dy),math.floor(box[2]-dx),math.floor(box[3]-dy)]
    need(roi[2]-roi[0]>=4 and roi[3]-roi[1]>=4)
    excluded=[[math.floor(marker[0])-2,math.floor(marker[1])-2,math.ceil(marker[2])+2,math.ceil(marker[3])+2],policy['marker']]
    count=changes=0;sums=[[0,0,0],[0,0,0]];orange_count=[0,0]
    with Image.open(BytesIO(raw_before)) as left_image,Image.open(BytesIO(raw_after)) as right_image:
        left_image.load();right_image.load();need(left_image.size==right_image.size==tuple(after['screen']['extent']))
        for y in range(roi[1],roi[3]):
            if (y-roi[1])%64==0:bound()
            for x in range(roi[0],roi[2]):
                if any(r[0]<=x<r[2] and r[1]<=y<r[3] for r in excluded):continue
                pair=(left_image.getpixel((x,y)),right_image.getpixel((x,y)));count+=1
                changes+=max(abs(a-b) for a,b in zip(pair[0][:3],pair[1][:3]))>25
                for index in (0,1):
                    rgb=pair[index]
                    for channel in range(3):sums[index][channel]+=rgb[channel]
                    orange_count[index]+=rgb[0]>60 and rgb[0]-rgb[1]>12 and rgb[0]-rgb[2]>12
    need(64<=count<=8388608)
    means=[[v/count for v in row] for row in sums];orange=[v/count for v in orange_count]
    blue=[rgb[2]-rgb[0] for rgb in means];changed=changes/count;direction=1 if right[field] else -1
    need(changed>=.05)
    if feature=='haze':need(direction*(blue[1]-blue[0])>10)
    else:need(direction*(orange[1]-orange[0])>.005)
    result=dict(graphicsEffectsVersion=VERSION,feature=feature,beforeTicket=before['provider']['ticket'],afterTicket=after['provider']['ticket'],
        beforeSha256=hashlib.sha256(raw_before).hexdigest(),afterSha256=hashlib.sha256(raw_after).hexdigest(),targetId=target['id'],
        roi=roi,excluded=excluded,pixels=count,meanRgbBefore=means[0],meanRgbAfter=means[1],
        blueDominanceBefore=blue[0],blueDominanceAfter=blue[1],orangeFractionBefore=orange[0],orangeFractionAfter=orange[1],changedFraction=changed)
    bound();current=epoch_ms();need(integer(current,epoch));fresh(math.floor(last['capturedEpochMs']),current);bound()
    need(max(current-last['capturedEpochMs'],epoch-last['capturedEpochMs']+(previous-started)*1000)<=1500)
    return deepcopy(result)
