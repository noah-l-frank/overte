"""Full original Worlds pixels before and after same-process restoration."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from io import BytesIO
from PIL import Image,ImageChops,ImageStat

from adapters.native_clock_join import digest
from adapters.native_feature_observation import need
from adapters.script_feature.history import same
from ios.adapters.navigation_admission_owner import NavigationAdmissionOwner
from ios.adapters.navigation_baseline_image import NavigationBaselineImage
from ios.adapters.navigation_initial_restored_image import NavigationInitialRestoredImage
from ios.adapters.navigation_static_comparison import recorded_view_equal,untouched
from ios.adapters.graphics_history import follow_native

VERSION=1


def compare(initial,current,admission):
    need(type(initial) is NavigationBaselineImage and type(current) is NavigationInitialRestoredImage
        and type(admission) is NavigationAdmissionOwner and initial.lock is current.lock is admission.lock
        and initial.run==current.run==admission.run and initial.role==current.role and initial.root==current.root)
    original=admission.archive();before,static,old_raw=initial.archive();after,restored,new_raw=current.archive()
    need(same(original,current.initial) and same(initial.binding,current.binding) and same(initial.binding,original['binding']))
    untouched(original,static)
    left_parts,right_parts=initial.originals(),current.originals();left,right=left_parts['capture'],right_parts['capture']
    follow_native(left_parts['nativeEnd']['nativeAfter'],right_parts['nativeStart']['nativeBefore'])
    need(left['instance']==right['instance'] and left['sequence']<right['sequence']
        and left['requestId']!=right['requestId'] and left['commandId']!=right['commandId']
        and left['source']['renderTrace']['frameId']!=right['source']['renderTrace']['frameId']
        and same(left['source']['targetExtent'],right['source']['targetExtent']))
    recorded_view_equal(left['source']['renderTrace']['recordedView'],right['source']['renderTrace']['recordedView'])
    with Image.open(BytesIO(old_raw)) as a,Image.open(BytesIO(new_raw)) as b:
        need(a.format==b.format=='PNG' and a.mode==b.mode=='RGBA' and a.size==b.size
            and list(a.size)==left['source']['targetExtent'])
        a.load();b.load();delta=ImageChops.difference(a,b);channels=delta.split();maximum=channels[0]
        for channel in channels[1:]:maximum=ImageChops.lighter(maximum,channel)
        changed=sum(maximum.histogram()[11:]);pixels=a.width*a.height;mean=sum(ImageStat.Stat(delta).mean)/4
        need(changed/pixels<=.001 and mean<=.5)
    return dict(iosNavigationInitialStaticComparisonVersion=VERSION,runId=initial.run,role=initial.role,
        initialImageSha256=before['rendered']['imageSha256'],currentImageSha256=after['rendered']['imageSha256'],
        initialAdmissionSha256=digest(original),restoredStateSha256=digest(restored),changedPixels=changed,pixels=pixels,meanChannelDelta=mean)
