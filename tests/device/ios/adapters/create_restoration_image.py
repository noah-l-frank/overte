"""Original fenced pixels before marker setup and after its actual retirement.

Neither scene absence nor a Script/native cleanup acknowledgment establishes
that an old rendered marker has disappeared. Both PNGs remain owned originals.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from io import BytesIO
import hashlib
from PIL import Image,ImageChops,ImageStat
from adapters.graphics_subject_geometry import near,projected_box
from adapters.native_clock_join import validate_join
from adapters.native_feature_observation import need,integer
from adapters.native_vulkan_world_frame import validate as frame_packet,storage,absent,original_pixels
from adapters.owned_vulkan_world_frame import VulkanWorldFrameOwner
from adapters.script_feature.history import same
from ios.adapters import create_state
from ios.adapters.create_actions import semantic_map
from ios.adapters.create_sample import CreateSampleOwner

VERSION=1


def original(owner):
    need(isinstance(owner,CreateSampleOwner) and owner.role=='primary' and same(owner.store.read(),owner.previous))
    owner.lock.assert_held();state=owner.decode(owner.previous);need(state['phase']=='captured' and state['qualificationInputs'] is None)
    raw=VulkanWorldFrameOwner.archive_original(state['frameOwnership'],owner.frame_owner.root,owner.binding,owner.run,owner.role,0,owner.request,owner.lock)
    items=state['originals'];clock=validate_join(state['clockJoin'],items);pid=int(owner.binding['processIdentity'])
    need(clock['nativeBefore']['processId']==clock['nativeAfter']['processId']==pid
        and same(clock['nativeBefore']['lifecycle'],clock['nativeAfter']['lifecycle']))
    before,after=items['createBefore'],items['createAfter'];epoch=clock['nativeAfter']['capturedEpochMs']
    create_state.validate(before,dict(schemaVersion=1,commandId=before['requestId'],action=create_state.ACTION,runId=owner.run),pid,epoch)
    create_state.validate(after,dict(schemaVersion=1,commandId=after['requestId'],action=create_state.ACTION,runId=owner.run),pid,epoch,before)
    a,b=create_state.live(before),create_state.live(after)
    need(before['iosCreateStateVersion']>=3 and same(semantic_map(before),semantic_map(after))
        and same(a['tree']['entities'],b['tree']['entities']) and a['localSessionId']==b['localSessionId']
        and not a['tabletShown'] and not b['tabletShown'])
    capture,retirement=items['capture'],items['retirement'];query=dict(schemaVersion=1,action='feature-vulkan-world-frame',operation='read',
        commandId=capture['commandId'],requestId=capture['requestId'])
    frame_packet(capture,query,pid,epoch);original_pixels(capture,raw)
    storage(retirement,dict(query,operation=retirement['operation'],commandId=retirement['commandId']),pid,epoch)
    need(absent(retirement) and retirement['instance']==capture['instance'] and retirement['sequence']>capture['sequence'])
    trace=capture['source']['renderTrace'];recorded=trace['recordedView'];view=a['view']
    need(trace['forwardDrawCalls']>0 and view['perspective'] and near(recorded['position'],view['position'],.001)
        and (near(recorded['rotation'],view['rotation'],.0001) or near(recorded['rotation'],[-v for v in view['rotation']],.0001))
        and near(recorded['fieldOfViewDegrees'],view['fieldOfViewDegrees'],.001) and near(recorded['aspectRatio'],view['aspectRatio'],.0001)
        and all(near(a['view'][key],b['view'][key],.001) for key in ('position','rotation','fieldOfViewDegrees','aspectRatio')))
    times=[before['clockBefore']['epochMs'],before['clockAfter']['epochMs'],capture['requestedEpochMs'],trace['recordedEpochMs'],
        capture['source']['submittedEpochMs'],capture['source']['fenceObservedEpochMs'],capture['source']['pixelsReadEpochMs'],capture['capturedEpochMs'],
        retirement['requestedEpochMs'],retirement['capturedEpochMs'],after['clockBefore']['epochMs'],after['clockAfter']['epochMs']]
    need(all(integer(value,1) for value in times) and times==sorted(times)
        and clock['nativeBefore']['capturedEpochMs']<=times[0]<=times[-1]<=epoch)
    return state,raw


def restored(baseline,current,admission,marker_id,*,after_native):
    """Join real returned pixel originals to actual marker geometry and clocks."""
    need(isinstance(baseline,CreateSampleOwner) and isinstance(current,CreateSampleOwner) and baseline is not current
        and baseline.lock is current.lock and baseline.run==current.run and same(baseline.binding,current.binding)
        and baseline.request!=current.request and baseline.frame_owner.root==current.frame_owner.root and integer(after_native,1))
    first,old_raw=original(baseline);last,new_raw=original(current);a,b=first['originals'],last['originals']
    before,after=a['createAfter'],b['createBefore'];pid=int(current.binding['processIdentity'])
    create_state.validate(admission,dict(schemaVersion=1,commandId=admission['requestId'],action=create_state.ACTION,runId=current.run),pid,previous=before)
    create_state.validate(after,dict(schemaVersion=1,commandId=after['requestId'],action=create_state.ACTION,runId=current.run),pid,previous=admission)
    need(first['clockJoin']['hostAfterMonotonic']<=last['clockJoin']['hostBeforeMonotonic']
        and first['clockJoin']['hostAfterEpochMs']<=last['clockJoin']['hostBeforeEpochMs']
        and admission['clockAfter']['epochMs']<=after_native<=last['clockJoin']['nativeBefore']['capturedEpochMs']
        and a['capture']['instance']==b['capture']['instance'] and a['capture']['sequence']<b['capture']['sequence']
        and a['capture']['source']['renderTrace']['frameId']!=b['capture']['source']['renderTrace']['frameId']
        and a['capture']['capturedEpochMs']<=b['capture']['requestedEpochMs']
        and same(semantic_map(before),semantic_map(after)))
    rows=[row for row in admission['source']['entities'] if row['id']==marker_id]
    if marker_id is not None:
        need(len(rows)==1 and rows[0]['type']=='Web' and rows[0]['hostType']=='local' and rows[0]['visible']
            and marker_id not in semantic_map(before) and marker_id not in semantic_map(after))
    for state in (before,admission,after):
        need(all(state['source']['view'][key]==before['source']['view'][key] for key in ('perspective','uiWidth','uiHeight'))
            and state['source']['domainId']==before['source']['domainId'] and state['source']['localSessionId']==before['source']['localSessionId']
            and all(near(state['source']['view'][key],before['source']['view'][key],.001)
                for key in ('position','rotation','fieldOfViewDegrees','aspectRatio')))
    left,right=a['capture']['source'],b['capture']['source'];need(left['targetExtent']==right['targetExtent'])
    # A partial Script may have returned an entity UUID before any original
    # rendered geometry was acquired. Its Scope still proves actual returned
    # UUID/tree birth/weak expiry. Compare the entire original viewport rather
    # than inventing a box or omitting those potentially rendered pixels.
    roi=projected_box(rows[0],right['renderTrace']['recordedView'],right['targetExtent']) if marker_id is not None else (0,0,*right['targetExtent'])
    width,height=right['targetExtent'];x0,y0,x1,y1=roi
    need(0<=x0<x1<=width and 0<=y0<y1<=height)
    # Include every pixel covered by the actual projected marker, rather than
    # a supplied expected image/region or a newly generated background.
    import math
    bounds=(math.floor(x0),math.floor(y0),math.ceil(x1),math.ceil(y1))
    old=Image.open(BytesIO(old_raw)).convert('RGB');new=Image.open(BytesIO(new_raw)).convert('RGB')
    need(old.size==new.size==(width,height));delta=ImageChops.difference(old.crop(bounds),new.crop(bounds))
    red,green,blue=delta.split();maximum=ImageChops.lighter(ImageChops.lighter(red,green),blue)
    changed=sum(maximum.histogram()[11:]);pixels=delta.width*delta.height;mean=sum(ImageStat.Stat(delta).mean)/3
    need(changed/pixels<=.01 and mean<=2. if marker_id is not None else changed==0 and mean<=.1)
    return dict(iosCreateRestorationImageVersion=VERSION,runId=current.run,binding=deepcopy(current.binding),baselineRequest=baseline.request,
        currentRequest=current.request,baselineSha256=hashlib.sha256(old_raw).hexdigest(),currentSha256=hashlib.sha256(new_raw).hexdigest(),
        markerId=marker_id,roi=list(bounds),changedPixels=changed,pixels=pixels,meanChannelDelta=mean,afterNativeEpochMs=after_native)
