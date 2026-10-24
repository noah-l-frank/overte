"""Original rendered Web subject and DOM marker geometry, never requested pixels."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import math
from adapters.graphics_subject_geometry import near
from adapters.native_feature_observation import exact,need
from adapters.native_vulkan_world_frame import original_pixels,absent
from adapters.owned_vulkan_world_frame import VulkanWorldFrameOwner
from adapters.script_feature.history import same
from feature_journeys.evidence import image_observation,rectangle
from ios.adapters.world_web_geometry import rotate,original as geometry_original
from ios.adapters.world_web_dom import original as dom_original


def projected_dom_box(source,document,entity,control,view,extent):
    geometry_original(source);dom_original(document);rows=[row for row in source['source']['entities'] if row['id']==entity];need(len(rows)==1);row=rows[0]
    need(row['hostType']=='local' and row['visible'] and row['parentId']=='00000000-0000-0000-0000-000000000000' and row['billboardMode']=='none')
    body=document['source']['dom'];elements=[element for element in body['elements'] if element['id']==control]
    if control is not None:need(len(elements)==1 and elements[0]['visible'])
    need(near(row['rotation'],view['rotation'],.0001) or near(row['rotation'],[-x for x in view['rotation']],.0001))
    width,height=body['document']['width'],body['document']['height'];l,t,r,b=[0,0,width,height] if control is None else elements[0]['rect'];result=[]
    q=view['rotation'];need(type(view['projection']) is list and len(view['projection'])==16)
    for x,y in ((l,t),(r,t),(l,b),(r,b)):
        registration=row['registrationPoint'];dims=row['dimensions']
        local=[(x/width-registration[0])*dims[0],(1-y/height-registration[1])*dims[1],(.5-registration[2])*dims[2]]
        offset=rotate(local,row['rotation']);relative=rotate([a+b-c for a,b,c in zip(row['position'],offset,view['position'])],[-q[0],-q[1],-q[2],q[3]])
        camera=relative+[1];clip=[sum(view['projection'][r*4+c]*camera[c] for c in range(4)) for r in range(4)]
        need(clip[3]>0);nx,ny,nz=[value/clip[3] for value in clip[:3]]
        need(-1<=nx<=1 and -1<=ny<=1 and -1<=nz<=1);result.append([(nx+1)*extent[0]/2,(1-ny)*extent[1]/2])
    return [min(point[0] for point in result),min(point[1] for point in result),max(point[0] for point in result),max(point[1] for point in result)]


def measure(raw,run,ticket,policy,before,after,frame_owner,entity,*,ownership,previous=None,changed=False):
    need(isinstance(frame_owner,VulkanWorldFrameOwner) and type(changed) is bool);exact(policy,{'source','marker','subject'})
    # Qualification belongs to the exact acquisition archived by the sample.
    # Later native inspections retain fresh retirement evidence in the mutable
    # owner, but cannot replace this sample's original release timestamp.
    need(policy['source']=='world-render-target');owned=deepcopy(ownership)
    original=VulkanWorldFrameOwner.archive_original(owned,frame_owner.root,frame_owner.binding,run,frame_owner.role,0,frame_owner.request_id,frame_owner.lock)
    need(raw==original and owned['ticket']==ticket and owned['phase']=='released' and absent(owned['absence']))
    capture=owned['frame'];original_pixels(capture,raw);source=capture['source'];trace=source['renderTrace'];view=trace['recordedView']
    a,b=before['originals'],after['originals'];need(a['document'] is not None and b['document'] is not None)
    for snapshot in (before,after):
        current=snapshot['originals'];native_view=current['document']['source']['nativeView'];need(native_view['sourceIdentity']=='web-entity:'+entity)
        camera=current['geometry']['source']['view'];need(camera['perspective'] and near(camera['position'],view['position'],.001)
            and (near(camera['rotation'],view['rotation'],.0001) or near(camera['rotation'],[-v for v in view['rotation']],.0001))
            and near(camera['fieldOfViewDegrees'],view['fieldOfViewDegrees'],.001) and near(camera['aspectRatio'],view['aspectRatio'],.0001))
    need(a['document']['source']['nativeView']==b['document']['source']['nativeView']
        and a['document']['source']['dom']['editor']==b['document']['source']['dom']['editor']
        and same(a['geometry']['source'],b['geometry']['source']) and trace['forwardDrawCalls']>0)
    first,last=before['clockJoin'],after['clockJoin']
    need(first['hostAfterMonotonic']<=last['hostBeforeMonotonic'] and first['nativeAfter']['capturedEpochMs']<=capture['requestedEpochMs']
        <=trace['recordedEpochMs']<=source['submittedEpochMs']<=source['fenceObservedEpochMs']<=source['pixelsReadEpochMs']<=capture['capturedEpochMs']
        <=owned['absence']['requestedEpochMs']<=owned['absence']['capturedEpochMs']<=last['nativeBefore']['capturedEpochMs'])
    marker_box=projected_dom_box(a['geometry'],a['document'],entity,'feature-marker',view,source['targetExtent'])
    roi=rectangle(policy['marker'],source['targetExtent']);subject=rectangle(policy['subject'],source['targetExtent'])
    surface=projected_dom_box(a['geometry'],a['document'],entity,None,view,source['targetExtent'])
    need(surface[0]<=subject[0]<subject[2]<=surface[2] and surface[1]<=subject[1]<subject[3]<=surface[3])
    need(marker_box[0]<=roi[0]<roi[2]<=marker_box[2] and marker_box[1]<=roi[1]<roi[3]<=marker_box[3])
    # This feature's subject is the Web content itself. Exclude the entire
    # actual DOM challenge image, including pixels outside its selected ROI.
    need(subject[2]<=marker_box[0] or marker_box[2]<=subject[0] or subject[3]<=marker_box[1] or marker_box[3]<=subject[1])
    old_subject=None
    if previous is not None:
        exact(previous,{'requestId','ticket','frameOwnership'})
        previous_raw=VulkanWorldFrameOwner.archive_original(previous['frameOwnership'],frame_owner.root,frame_owner.binding,run,frame_owner.role,0,previous['requestId'],frame_owner.lock)
        old=previous['frameOwnership']['frame'];need(old['instance']==capture['instance'] and old['sequence']<capture['sequence']
            and old['capturedEpochMs']<=capture['requestedEpochMs'] and old['source']['renderTrace']['frameId']!=trace['frameId'])
        _measurement,old_subject=image_observation(previous_raw,run,previous['ticket'],policy)
    observed,_subject=image_observation(raw,run,ticket,policy,previous=old_subject,changed=changed)
    return dict(image=observed,frameId=trace['frameId'],nativeEpochMs=capture['capturedEpochMs'],lifecycle=deepcopy(last['nativeAfter']['lifecycle']))
