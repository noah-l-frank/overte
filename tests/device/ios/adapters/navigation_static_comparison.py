"""Untouched and restored actual full-target PNGs across a proved restart."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from io import BytesIO
from PIL import Image,ImageChops,ImageStat
from adapters.graphics_subject_geometry import near

from adapters.native_clock_join import digest
from adapters.native_feature_observation import need
from adapters.script_feature.history import same
from ios.adapters.navigation_admission_owner import NavigationAdmissionOwner
from ios.adapters.navigation_baseline_image import NavigationBaselineImage
from ios.adapters.navigation_restored_image import NavigationRestoredImage
from ios.adapters.navigation_process_owner import NavigationProcessOwner
from ios.adapters import navigation_source_prefix as prefix,scene_inventory,navigation_state
from ios.adapters.graphics_history import follow_native

VERSION=1


def recorded_view_equal(left,right):
    # Original JSON can encode a coordinate as 0 or 0.0. Compare measured
    # geometry numerically, retaining the originals and exact nonnumeric facts.
    need(set(left)==set(right))
    for key,value in left.items():
        if type(value) in (int,float,list):need(near(right[key],value,.0001))
        else:need(same(right[key],value))


def untouched(admission,image):
    """Join two actual static cuts in their genuine chronological order."""
    need(same(admission['binding'],image['binding']) and admission['runId']==image['runId']
        and same(admission['providerInputs'],image['providerInputs'])
        and same(scene_inventory.semantics(admission['originals']['inventory']),scene_inventory.semantics(image['originals']['inventory']))
        and same(admission['originals']['navigation']['source']['avatar'],image['originals']['navigation']['source']['avatar'])
        and same(admission['originals']['navigation']['source']['view'],image['originals']['navigation']['source']['view']))
    a,b=admission,image
    if image['clockJoin']['nativeAfter']['sequence']<admission['clockJoin']['nativeBefore']['sequence']:a,b=image,admission
    follow_native(a['clockJoin']['nativeAfter'],b['clockJoin']['nativeBefore'])
    old=dict(a['originals']);old['currentNavigation']=old.pop('navigation')
    current=dict(b['originals']);current['navigationBefore']=current.pop('navigation')
    run,pid=a['runId'],int(a['binding']['processIdentity']);prefix.follow(old,current,run,pid)
    for name,module in (('inventory',scene_inventory),('navigation',navigation_state)):
        packet=b['originals'][name]
        module.validate(packet,dict(schemaVersion=1,commandId=packet['requestId'],action=module.ACTION,runId=run),
            pid,previous=a['originals'][name])


def compare(initial,current,admission,transfer):
    """Full original pixel comparison, never reconstructed expected pixels."""
    need(type(initial) is NavigationBaselineImage and isinstance(current,NavigationRestoredImage)
        and isinstance(admission,NavigationAdmissionOwner) and isinstance(transfer,NavigationProcessOwner)
        and initial.lock is current.lock is admission.lock is transfer.lock
        and initial.run==current.run==admission.run==transfer.run and initial.role==current.role and initial.root==current.root)
    original=admission.archive();process=transfer.archive()
    before,static,old_raw=initial.archive();after,restored,new_raw=current.archive()
    need(same(original,process['initialAdmission']) and same(current.process_context,process)
        and same(initial.binding,original['binding']) and same(current.binding,process['restart']['input']['newBinding'])
        and initial.binding['processIdentity']!=current.binding['processIdentity'])
    untouched(original,static)
    left,right=initial.originals()['capture'],current.originals()['capture']
    need(left['instance']!=right['instance'] and left['requestId']!=right['requestId']
        and same(left['source']['targetExtent'],right['source']['targetExtent']))
    recorded_view_equal(left['source']['renderTrace']['recordedView'],right['source']['renderTrace']['recordedView'])
    with Image.open(BytesIO(old_raw)) as a,Image.open(BytesIO(new_raw)) as b:
        need(a.format==b.format=='PNG' and a.mode==b.mode=='RGBA' and a.size==b.size
            and list(a.size)==left['source']['targetExtent'])
        a.load();b.load();delta=ImageChops.difference(a,b);channels=delta.split();maximum=channels[0]
        for channel in channels[1:]:maximum=ImageChops.lighter(maximum,channel)
        changed=sum(maximum.histogram()[11:]);pixels=a.width*a.height;mean=sum(ImageStat.Stat(delta).mean)/4
        need(changed/pixels<=.001 and mean<=.5)
    return dict(iosNavigationStaticComparisonVersion=VERSION,runId=initial.run,role=initial.role,
        initialImageSha256=before['rendered']['imageSha256'],currentImageSha256=after['rendered']['imageSha256'],
        initialAdmissionSha256=digest(original),processContextSha256=digest(process),
        restoredStateSha256=digest(restored),changedPixels=changed,pixels=pixels,meanChannelDelta=mean)
