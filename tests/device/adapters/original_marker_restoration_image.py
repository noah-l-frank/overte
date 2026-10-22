"""Actual post-retirement marker pixels versus untouched pre-marker fences."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from io import BytesIO
import hashlib
import math
from PIL import Image,ImageChops,ImageStat
from adapters.graphics_subject_geometry import projected_box
from adapters.native_feature_observation import need
from adapters.original_marker_restoration_frames import OriginalMarkerRestorationFrames
from adapters.script_feature.history import same
from ios.adapters.emote_native_prefix import follow

VERSION=1


def restored(owner,baseline_ref,current_ref,admission,marker_id,*,after_native):
    """Read actual originals; no fixture, SDK, image filling or fresh clocks."""
    need(isinstance(owner,OriginalMarkerRestorationFrames) and baseline_ref!=current_ref);owner.lock.assert_held()
    first,last=owner.original(baseline_ref),owner.original(current_ref)
    need(first['kind']=='initial' and last['kind']=='cleanup' and first['requestId']!=last['requestId'])
    baseline,old_raw=owner.frame(baseline_ref);current,new_raw=owner.frame(current_ref);c=owner.components
    before,after=baseline['worldAfter'],current['worldBefore'];pid=int(owner.binding['processIdentity'])
    c.world_packet(admission,dict(schemaVersion=1,commandId=admission['requestId'],action=c.WORLD_ACTION,runId=owner.run),pid,previous=before)
    c.world_packet(after,dict(schemaVersion=1,commandId=after['requestId'],action=c.WORLD_ACTION,runId=owner.run),pid,previous=admission)
    need(same(c.actual_domain(before),c.actual_domain(admission)) and same(c.actual_domain(before),c.actual_domain(after)))
    c.body_preserved(before,admission);c.body_preserved(before,after);c.view_preserved(before,after)
    tree=before['source']['tree'];need(tree['treeInstance']==admission['source']['tree']['treeInstance']==after['source']['tree']['treeInstance']
        and same(tree['entities'],after['source']['tree']['entities']) and marker_id not in {row['id'] for row in tree['entities']})
    markers=[row for row in admission['source']['markers'] if row['id']==marker_id]
    need(len(markers)==1 and markers[0]['type']=='Web' and markers[0]['hostType']=='local' and markers[0]['visible'])
    marker=markers[0];need(marker_id not in {row['id'] for row in after['source']['tree']['entities']})
    follow(baseline['clockJoin']['nativeAfter'],current['clockJoin']['nativeBefore']);follow(after_native,current['clockJoin']['nativeBefore'])
    need(baseline['clockJoin']['hostAfterEpochMs']<=current['clockJoin']['hostBeforeEpochMs']
        and baseline['clockJoin']['hostAfterMonotonic']<=current['clockJoin']['hostBeforeMonotonic']
        and admission['clockAfter']['epochMs']<=after_native['requestedEpochMs'])
    a,b=baseline['capture'],current['capture'];need(a['instance']==b['instance'] and a['sequence']<b['sequence']
        and a['capturedEpochMs']<=b['requestedEpochMs'] and a['source']['renderTrace']['frameId']!=b['source']['renderTrace']['frameId']
        and a['source']['targetExtent']==b['source']['targetExtent']
        and same(a['source']['renderTrace']['recordedView'],b['source']['renderTrace']['recordedView']))
    extent=b['source']['targetExtent'];roi=projected_box(marker,b['source']['renderTrace']['recordedView'],extent)
    x0,y0,x1,y1=roi;need(0<=x0<x1<=extent[0] and 0<=y0<y1<=extent[1])
    bounds=(math.floor(x0),math.floor(y0),math.ceil(x1),math.ceil(y1))
    old=Image.open(BytesIO(old_raw)).convert('RGB');new=Image.open(BytesIO(new_raw)).convert('RGB');need(old.size==new.size==tuple(extent))
    delta=ImageChops.difference(old.crop(bounds),new.crop(bounds));red,green,blue=delta.split()
    maximum=ImageChops.lighter(ImageChops.lighter(red,green),blue);changed=sum(maximum.histogram()[11:]);pixels=delta.width*delta.height
    mean=sum(ImageStat.Stat(delta).mean)/3;need(pixels>0 and changed/pixels<=.01 and mean<=2.)
    return dict(markerRestorationImageVersion=VERSION,profile=owner.PROFILE,runId=owner.run,role=owner.role,binding=deepcopy(owner.binding),
        baselineReference=deepcopy(baseline_ref),currentReference=deepcopy(current_ref),baselineRequest=first['requestId'],currentRequest=last['requestId'],
        baselineSha256=hashlib.sha256(old_raw).hexdigest(),currentSha256=hashlib.sha256(new_raw).hexdigest(),markerId=marker_id,
        roi=list(bounds),changedPixels=changed,pixels=pixels,meanChannelDelta=mean,afterNativeEpochMs=after_native['capturedEpochMs'])
