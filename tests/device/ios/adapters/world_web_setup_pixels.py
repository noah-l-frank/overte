"""Full actual world target restoration after setup that never gained a lease."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from io import BytesIO
import hashlib
from PIL import Image,ImageChops,ImageStat
from adapters.native_feature_observation import integer,need
from adapters.script_feature.history import same
from ios.adapters.world_web_restoration import original
from ios.adapters.world_web_sample import WorldWebSample
from ios.adapters.emote_marker_measurements import body_preserved,view_preserved


def restored(baseline,current,*,after_native):
    need(type(baseline) is WorldWebSample and type(current) is WorldWebSample and baseline is not current
        and baseline.source is current.source and baseline.lock is current.lock and baseline.request!=current.request
        and same(baseline.binding,current.binding) and baseline.run==current.run and integer(after_native,1))
    a,old_raw,old_before,old_after=original(baseline);b,new_raw,new_before,new_after=original(current)
    need(old_after['index']<new_before['index'] and old_after['clockJoin']['nativeAfter']['capturedEpochMs']<=after_native
        <=new_before['clockJoin']['nativeBefore']['capturedEpochMs']
        and old_after['clockJoin']['hostAfterMonotonic']<=new_before['clockJoin']['hostBeforeMonotonic'])
    body_preserved(old_before['originals']['world'],new_after['originals']['world'])
    view_preserved(old_before['originals']['world'],new_after['originals']['world'])
    need(same(old_before['originals']['world']['source']['tree']['entities'],new_after['originals']['world']['source']['tree']['entities']))
    old,new=a['frameOwnership']['frame'],b['frameOwnership']['frame']
    need(old['instance']==new['instance'] and old['sequence']<new['sequence']
        and old['capturedEpochMs']<=new['requestedEpochMs']
        and old['source']['renderTrace']['frameId']!=new['source']['renderTrace']['frameId']
        and same(old['source']['renderTrace']['recordedView'],new['source']['renderTrace']['recordedView'])
        and old['source']['targetExtent']==new['source']['targetExtent'])
    extent=new['source']['targetExtent'];first=Image.open(BytesIO(old_raw)).convert('RGB');last=Image.open(BytesIO(new_raw)).convert('RGB')
    need(first.size==last.size==tuple(extent));delta=ImageChops.difference(first,last);r,g,blue=delta.split()
    maximum=ImageChops.lighter(ImageChops.lighter(r,g),blue);changed=sum(maximum.histogram()[11:]);pixels=delta.width*delta.height
    mean=sum(ImageStat.Stat(delta).mean)/3;need(changed/pixels<=.01 and mean<=2.)
    return dict(iosWorldWebSetupRestorationImageVersion=1,runId=baseline.run,binding=deepcopy(baseline.binding),
        baselineRequest=baseline.request,currentRequest=current.request,baselineSha256=hashlib.sha256(old_raw).hexdigest(),
        currentSha256=hashlib.sha256(new_raw).hexdigest(),roi=[0,0,extent[0],extent[1]],changedPixels=changed,pixels=pixels,
        meanChannelDelta=mean,afterNativeEpochMs=after_native)
