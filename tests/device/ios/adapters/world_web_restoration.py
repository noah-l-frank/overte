"""Actual fenced before/after pixels over the former returned Web surface."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from io import BytesIO
import hashlib
import math
from PIL import Image,ImageChops,ImageStat
from adapters.graphics_subject_geometry import near
from adapters.native_feature_observation import integer,need
from adapters.native_vulkan_world_frame import original_pixels,absent
from adapters.owned_vulkan_world_frame import VulkanWorldFrameOwner
from adapters.script_feature.history import same
from ios.adapters.world_web_image import projected_dom_box
from ios.adapters.world_web_identity import WorldWebLease
from ios.adapters.world_web_sample import WorldWebSample
from ios.adapters.emote_marker_measurements import body_preserved,view_preserved


def original(owner):
    need(isinstance(owner,WorldWebSample) and owner.role=='primary' and same(owner.store.read(),owner.previous));owner.lock.assert_held()
    state=owner.decode(owner.previous);need(state['phase']=='captured' and state['qualificationInputs'] is None)
    owned=state['frameOwnership'];need(owned['phase']=='released' and absent(owned['absence']))
    raw=VulkanWorldFrameOwner.archive_original(owned,owner.frame_owner.root,owner.binding,owner.run,owner.role,0,owner.request,owner.lock)
    before,after=owner.source.frame(state['before']),owner.source.frame(state['after']);a,b=before['originals'],after['originals']
    need(before['ticket']==after['ticket']==state['ticket'] and a['document'] is b['document'] is None
        and same(a['world']['source']['tree']['entities'],b['world']['source']['tree']['entities']))
    body_preserved(a['world'],b['world']);view_preserved(a['world'],b['world'])
    capture=owned['frame'];original_pixels(capture,raw);gpu=capture['source'];trace=gpu['renderTrace'];view=a['world']['source']['view'];recorded=trace['recordedView']
    need(view['perspective'] and trace['forwardDrawCalls']>0 and near(view['position'],recorded['position'],.001)
        and (near(view['rotation'],recorded['rotation'],.0001) or near(view['rotation'],[-x for x in recorded['rotation']],.0001))
        and near(view['fieldOfViewDegrees'],recorded['fieldOfViewDegrees'],.001) and near(view['aspectRatio'],recorded['aspectRatio'],.0001))
    ordered=[before['clockJoin']['nativeAfter']['capturedEpochMs'],capture['requestedEpochMs'],trace['recordedEpochMs'],gpu['submittedEpochMs'],gpu['fenceObservedEpochMs'],
        gpu['pixelsReadEpochMs'],capture['capturedEpochMs'],owned['absence']['requestedEpochMs'],owned['absence']['capturedEpochMs'],after['clockJoin']['nativeBefore']['capturedEpochMs']]
    need(all(integer(value,1) for value in ordered) and ordered==sorted(ordered)
        and before['clockJoin']['hostAfterMonotonic']<=after['clockJoin']['hostBeforeMonotonic'])
    return state,raw,before,after


def restored(baseline,current,lease,*,after_native):
    need(isinstance(baseline,WorldWebSample) and isinstance(current,WorldWebSample) and isinstance(lease,WorldWebLease)
        and baseline is not current and baseline.request!=current.request and baseline.source is current.source is lease.source
        and baseline.lock is current.lock and same(baseline.binding,current.binding) and baseline.run==current.run and integer(after_native,1))
    first,old_raw,old_before,old_after=original(baseline);last,new_raw,new_before,new_after=original(current);owned=lease.packet();admission=lease.source.frame(owned['after'])
    entity=owned['returned']['returned']['entityId'];need(entity is not None)
    need(old_after['index']<admission['index']<new_before['index'] and admission['clockJoin']['nativeAfter']['capturedEpochMs']<=after_native
        <=new_before['clockJoin']['nativeBefore']['capturedEpochMs'] and old_after['clockJoin']['hostAfterMonotonic']<=new_before['clockJoin']['hostBeforeMonotonic'])
    body_preserved(old_before['originals']['world'],new_after['originals']['world']);view_preserved(old_before['originals']['world'],new_after['originals']['world'])
    need(same(old_before['originals']['world']['source']['tree']['entities'],new_after['originals']['world']['source']['tree']['entities']))
    a,b=first['frameOwnership']['frame'],last['frameOwnership']['frame'];need(a['instance']==b['instance'] and a['sequence']<b['sequence']
        and a['capturedEpochMs']<=b['requestedEpochMs'] and a['source']['renderTrace']['frameId']!=b['source']['renderTrace']['frameId']
        and a['source']['targetExtent']==b['source']['targetExtent'] and same(a['source']['renderTrace']['recordedView'],b['source']['renderTrace']['recordedView']))
    extent=b['source']['targetExtent'];roi=projected_dom_box(admission['originals']['geometry'],admission['originals']['document'],entity,None,b['source']['renderTrace']['recordedView'],extent)
    bounds=(math.floor(roi[0]),math.floor(roi[1]),math.ceil(roi[2]),math.ceil(roi[3]));need(0<=bounds[0]<bounds[2]<=extent[0] and 0<=bounds[1]<bounds[3]<=extent[1])
    old,new=Image.open(BytesIO(old_raw)).convert('RGB'),Image.open(BytesIO(new_raw)).convert('RGB');need(old.size==new.size==tuple(extent))
    delta=ImageChops.difference(old.crop(bounds),new.crop(bounds));red,green,blue=delta.split();maximum=ImageChops.lighter(ImageChops.lighter(red,green),blue)
    changed=sum(maximum.histogram()[11:]);pixels=delta.width*delta.height;mean=sum(ImageStat.Stat(delta).mean)/3
    need(changed/pixels<=.01 and mean<=2.)
    return dict(iosWorldWebRestorationImageVersion=1,runId=current.run,binding=deepcopy(current.binding),baselineRequest=baseline.request,currentRequest=current.request,
        baselineSha256=hashlib.sha256(old_raw).hexdigest(),currentSha256=hashlib.sha256(new_raw).hexdigest(),entityId=entity,roi=list(bounds),
        changedPixels=changed,pixels=pixels,meanChannelDelta=mean,afterNativeEpochMs=after_native)
