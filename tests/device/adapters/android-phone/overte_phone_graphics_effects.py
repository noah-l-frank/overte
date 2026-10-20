"""Original target-pixel comparisons for the controlled Graphics subjects."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import io
import itertools
import math
import time

from adapters.native_feature_observation import exact,fresh,integer,need
from adapters.normal_feature_state import context
from adapters.world_render_evidence import recorded_view
from feature_journeys.contract import identifier
from feature_journeys.graphics_fixture import subject_ids
from feature_journeys.graphics_resources import validate_status
from overte_phone_graphics_images import record as image_record
from overte_phone_graphics_measurements import compose,steady_subject
from overte_phone_graphics_samples import retirement
from overte_phone_script_history import same

VERSION=1
FRAME={'ticket','afterEpochMs','nativeBefore','subjectBefore','graphics','tablet','capture',
       'subjectAfter','nativeAfter','provider','image','retirement'}


def rotate(vector,quaternion):
    length=math.sqrt(sum(v*v for v in quaternion));need(length>0)
    x,y,z,w=[v/length for v in quaternion];a,b,c=vector
    dot=x*a+y*b+z*c;length=x*x+y*y+z*z
    cross=[y*c-z*b,z*a-x*c,x*b-y*a]
    return [2*dot*u+(w*w-length)*v+2*w*k for u,v,k in zip((x,y,z),vector,cross)]


def projected_box(row,view,extent):
    """Conservative visible box from original world geometry and recorded P."""
    recorded_view(view);need(type(extent) is list and len(extent)==2 and all(integer(v,1,4096) for v in extent))
    projected=[];inverse=[-v for v in view['rotation'][:3]]+[view['rotation'][3]]
    for signs in itertools.product((-1,1),repeat=3):
        local=[sign*size/2 for sign,size in zip(signs,row['dimensions'])]
        world=[a+b for a,b in zip(rotate(local,row['rotation']),row['position'])]
        camera=rotate([a-b for a,b in zip(world,view['position'])],inverse)+[1]
        clip=[sum(view['projection'][r*4+c]*camera[c] for c in range(4)) for r in range(4)]
        need(clip[3]>0)
        ndc=[v/clip[3] for v in clip[:3]];need(all(-1<=v<=1 for v in ndc))
        projected.append(((ndc[0]+1)*extent[0]/2,(1-ndc[1])*extent[1]/2))
    return [min(p[0] for p in projected),min(p[1] for p in projected),
            max(p[0] for p in projected),max(p[1] for p in projected)]


def original(run,frame,raw,binding,role,fixture_url,policy):
    exact(frame,FRAME);image_record(frame['image']);context(binding)
    need(frame['image']['binding']==binding and frame['image']['role']==role and frame['image']['runId']==run
         and frame['image']['phase']=='saved' and frame['image']['ticket']==frame['ticket']
         and same(frame['image']['capture'],frame['capture']))
    pid=int(binding['processIdentity'].split(':')[0]);provider=frame['provider']
    actual=compose(run,frame['ticket'],fixture_url,pid,provider,provider['instance'],provider['requestId'],
        frame['nativeBefore'],frame['subjectBefore'],frame['graphics'],frame['tablet'],frame['capture'],raw,
        frame['subjectAfter'],frame['nativeAfter'],max(provider['capturedEpochMs'],frame['nativeAfter']['capturedEpochMs']),
        frame['afterEpochMs'],policy)
    proof=frame['retirement'];retirement(proof,proof['owner'],pid,binding,role)
    need(proof['owner']['capture']['commandId']==frame['capture']['requestId']
         and proof['memory']['instance']==frame['capture']['instance'])
    return actual


def compare(run,feature,fixture_url,binding,role,before,raw_before,after,raw_after,policy,
            epoch_ms,guard,*,monotonic=time.monotonic):
    """Return measured ROI statistics; no requested setting is an argument.

    Original native settings determine the observed direction of change. The
    controlled board must gain blue haze, or the mirror must gain the owned
    orange reflection, when its independently observed native setting is on.
    """
    from PIL import Image
    identifier(run);need(feature in ('haze','mirror') and role in ('primary','actor')
        and all(callable(value) for value in (epoch_ms,guard,monotonic)))
    started=previous=monotonic();need(type(started) in (int,float) and math.isfinite(started) and started>=0)
    def bound():
        nonlocal previous
        current=monotonic();need(type(current) in (int,float) and math.isfinite(current) and previous<=current and current-started<5)
        previous=current
    need(guard() is not False);bound();first_query_started=previous
    epoch=epoch_ms();need(integer(epoch,1));bound()
    left=original(run,before,raw_before,binding,role,fixture_url,policy)
    right=original(run,after,raw_after,binding,role,fixture_url,policy)
    need(epoch>=after['nativeAfter']['capturedEpochMs'])
    fresh(right['capturedEpochMs'],epoch)
    validate_status(after['provider'],instance=before['provider']['instance'],run=run,
        url=fixture_url.rsplit('/runs/',1)[0],request=after['provider']['requestId'],previous=before['provider'])
    need(all(actual['state'][feature]==actual['state'][feature+'Pass'] for actual in (left,right)))
    need(before['ticket']!=after['ticket'] and before['image']['stage']==after['image']['stage']
         and before['provider']['instance']==after['provider']['instance']
         and 0<=after['nativeAfter']['capturedEpochMs']-before['nativeAfter']['capturedEpochMs']<=45000
         and after['nativeBefore']['capturedEpochMs']>=before['nativeAfter']['capturedEpochMs']
         and after['nativeBefore']['instance']==before['nativeAfter']['instance']
         and after['nativeBefore']['sequence']>before['nativeAfter']['sequence']
         and after['capture']['instance']==before['capture']['instance']
         and after['capture']['sequence']>before['capture']['sequence']
         and after['capture']['source']['acquisitionSequence']>before['capture']['source']['acquisitionSequence'])
    a,b=before['capture']['source'],after['capture']['source']
    need(a['renderTrace']['frameId']!=b['renderTrace']['frameId']
         and all(same(a[key],b[key]) for key in ('sourceExtent','sourceViewport','targetExtent')))
    av,bv=a['renderTrace']['recordedView'],b['renderTrace']['recordedView']
    need(same(av,bv)) # No alignment, resizing, exposure correction or guessed camera.
    fields_before,fields_after=before['nativeAfter']['graphics'],after['nativeBefore']['graphics']
    changed='hazeSetting' if feature=='haze' else 'mirrorsSetting'
    need(fields_before[changed]!=fields_after[changed]
         and all(fields_before[key]==fields_after[key] for key in fields_before if key!=changed)
         and before['nativeAfter']['lifecycle']==after['nativeBefore']['lifecycle'])
    subjects_before,subjects_after=before['subjectAfter']['source'],after['subjectBefore']['source']
    steady_subject(before['subjectAfter'],after['subjectBefore'])
    need(all(same(subjects_before[key],subjects_after[key]) for key in ('sceneUrl','entities','absentIds','scan')))
    wanted=subject_ids(run);rows={row['id']:row for row in subjects_after['entities']}
    target=rows[wanted['fog-board' if feature=='haze' else 'reflector']]
    extent=b['targetExtent'];box=projected_box(target,bv,extent)
    marker=projected_box(rows[wanted['marker']],bv,extent)
    # The interior excludes silhouette/occlusion edges. Exclude both the actual
    # complete world marker card and external decoder ROI, with a two-pixel rim.
    dx=(box[2]-box[0])*.25;dy=(box[3]-box[1])*.25
    roi=[math.ceil(box[0]+dx),math.ceil(box[1]+dy),math.floor(box[2]-dx),math.floor(box[3]-dy)]
    need(roi[2]-roi[0]>=4 and roi[3]-roi[1]>=4)
    excluded=[[math.floor(marker[0])-2,math.floor(marker[1])-2,math.ceil(marker[2])+2,math.ceil(marker[3])+2],policy['marker']]
    count=changes=0;sums=[[0,0,0],[0,0,0]];orange_count=[0,0]
    with Image.open(io.BytesIO(raw_before)) as image_before,Image.open(io.BytesIO(raw_after)) as image_after:
        image_before.load();image_after.load();need(image_before.size==image_after.size==tuple(extent))
        for y in range(roi[1],roi[3]):
            if (y-roi[1])%64==0:bound()
            for x in range(roi[0],roi[2]):
                if any(r[0]<=x<r[2] and r[1]<=y<r[3] for r in excluded):continue
                pair=(image_before.getpixel((x,y)),image_after.getpixel((x,y)));count+=1
                changes+=max(abs(a-b) for a,b in zip(pair[0][:3],pair[1][:3]))>25
                for index in (0,1):
                    rgb=pair[index]
                    for channel in range(3):sums[index][channel]+=rgb[channel]
                    orange_count[index]+=rgb[0]>60 and rgb[0]-rgb[1]>12 and rgb[0]-rgb[2]>12
    need(64<=count<=8388608)
    means=[[value/count for value in row] for row in sums]
    changed_fraction=changes/count;orange=[value/count for value in orange_count]
    blue=[row[2]-row[0] for row in means]
    direction=1 if fields_after[changed] else -1
    need(changed_fraction>=.05)
    if feature=='haze':need(direction*(blue[1]-blue[0])>10)
    else:need(direction*(orange[1]-orange[0])>.005)
    result=deepcopy(dict(graphicsEffectsVersion=VERSION,feature=feature,beforeTicket=before['ticket'],afterTicket=after['ticket'],
        beforeSha256=hashlib.sha256(raw_before).hexdigest(),afterSha256=hashlib.sha256(raw_after).hexdigest(),
        targetId=target['id'],roi=roi,excluded=excluded,pixels=count,meanRgbBefore=means[0],meanRgbAfter=means[1],
        blueDominanceBefore=blue[0],blueDominanceAfter=blue[1],orangeFractionBefore=orange[0],orangeFractionAfter=orange[1],
        changedFraction=changed_fraction))
    need(guard() is not False);bound();freshness_started=previous
    current_epoch=epoch_ms();need(integer(current_epoch,epoch));fresh(right['capturedEpochMs'],current_epoch)
    bound();need(guard() is not False);bound()
    need(max(current_epoch-right['capturedEpochMs']+math.ceil((previous-freshness_started)*1000),
        epoch-right['capturedEpochMs']+math.ceil((previous-first_query_started)*1000))<=1500)
    return result
