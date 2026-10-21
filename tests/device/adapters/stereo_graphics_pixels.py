"""Original per-eye Graphics pixels joined to actual executed GPU cameras.

No input, camera setter, crop, resize, eye duplication or requested feature state
is involved. All candidate cameras are retained; an ambiguous projection fails.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import io
import math
import time

from adapters.native_feature_observation import integer,need
from adapters.native_graphics_subject import validate as subject_packet
from adapters.native_scene_loads import resource_hash
from adapters.world_render_evidence import validate as capture_packet,original_pixels,camera_batches
from feature_journeys.contract import identifier
from feature_journeys.evidence import MarkerNotReady
from feature_journeys.fixtures import challenge
from feature_journeys.graphics_fixture import subject_ids

VERSION=1


def multiply(matrix,point):
    return [sum(matrix[column*4+row]*point[column] for column in range(4)) for row in range(4)]


def world(row,local):
    x,y,z,w=row['rotation'];norm=math.sqrt(x*x+y*y+z*z+w*w)
    x,y,z,w=(v/norm for v in (x,y,z,w));a,b,c=local
    dot=x*a+y*b+z*c;length=x*x+y*y+z*z;cross=(y*c-z*b,z*a-x*c,x*b-y*a)
    return [p+2*dot*u+(w*w-length)*v+2*w*k for p,u,v,k in zip(row['position'],(x,y,z),local,cross)]


def cameras(source,role):
    need(role in ('forward','mirror'));rows=camera_batches(source);result={eye:[] for eye in ('left','right')}
    for batch in rows:
        if batch['role']!=role:continue
        for camera in batch['cameras']:
            # Do not select a convenient slot or reconstruct a non-jittered P.
            value={key:deepcopy(camera[key]) for key in ('view','projection','viewport')}
            if value not in result[camera['eye']]:result[camera['eye']].append(value)
    need(all(result.values()));return result


def project(point,camera,source,eye):
    clip=multiply(camera['projection'],multiply(camera['view'],list(point)+[1]))
    need(clip[3]>1e-9);ndc=[v/clip[3] for v in clip[:3]]
    need(all(math.isfinite(v) and -1<=v<=1 for v in ndc))
    viewport=camera['viewport'];index=0 if eye=='left' else 1
    # Doubled GL viewports and instanced shader split-screen both map a complete
    # eye projection to this actual half of the original camera viewport.
    sx=viewport[0]+index*viewport[2]/2+(ndc[0]+1)*viewport[2]/4
    sy=viewport[1]+(ndc[1]+1)*viewport[3]/2
    original=source['sourceViewport'];width,height=source['targetExtent']
    x=(sx-original[0])*width/original[2];y=height-(sy-original[1])*height/original[3]
    target=source['stereo']['eyes'][index]['targetViewport']
    need(target[0]<=x<target[0]+target[2] and height-target[1]-target[3]<=y<height-target[1])
    return [x,y]


def quad(row,camera,source,eye,*,inset=0,plane=False):
    need(all(type(v) in (int,float) and v>0 for v in row['dimensions']) and 0<=inset<.5)
    width,height,depth=row['dimensions'];factor=.5-inset
    return [project(world(row,[x*width*factor,y*height*factor,0 if plane else depth/2]),camera,source,eye)
        for x,y in ((-1,1),(1,1),(1,-1),(-1,-1))]


def inside(point,polygon):
    signs=[]
    for a,b in zip(polygon,polygon[1:]+polygon[:1]):
        value=(b[0]-a[0])*(point[1]-a[1])-(b[1]-a[1])*(point[0]-a[0])
        signs.append(value)
    return all(v>=0 for v in signs) or all(v<=0 for v in signs)


def marker(image,row,source,views,eye,run,ticket):
    wanted=''.join(f'{byte:08b}' for byte in challenge(run,ticket));points=[]
    for camera in views:
        polygon=quad(row,camera,source,eye,plane=True)
        # Native marker stimulus is 160x40 with a 128x32 cell interior.
        # Require sufficient original projected spacing, never enlarge a card.
        distances=[math.dist(polygon[i],polygon[(i+1)%4]) for i in range(4)]
        need(min(distances[0],distances[2])>=160 and min(distances[1],distances[3])>=40)
        actual=[]
        for index in range(128):
            u=(4+(index%32+.5)*4)/160;v=(4+(index//32+.5)*8)/40
            point=project(world(row,[(u-.5)*row['dimensions'][0],(.5-v)*row['dimensions'][1],0]),camera,source,eye)
            x,y=(math.floor(value) for value in point);rgb=image.getpixel((x,y))[:3]
            if not (max(rgb)<70 or min(rgb)>185):
                raise MarkerNotReady('ambiguous',cell=index,rgb=list(rgb))
            actual.append('0' if max(rgb)<70 else '1');points.append([x,y])
        if ''.join(actual)!=wanted:
            raise MarkerNotReady('mismatch',observed=int(''.join(actual),2).to_bytes(16,'big').hex())
    decoded=int(''.join(actual),2).to_bytes(16,'big')
    return dict(samplePixels=points,challengeSha256=hashlib.sha256(decoded).hexdigest())


def statistics(image,row,marker_row,source,views,marker_views,eye,budget):
    polygons=[quad(row,camera,source,eye,inset=.25) for camera in views]
    excluded=[quad(marker_row,camera,source,eye,plane=True) for camera in marker_views]
    left=math.ceil(max(min(p[0] for p in polygon) for polygon in polygons))
    right=math.floor(min(max(p[0] for p in polygon) for polygon in polygons))
    top=math.ceil(max(min(p[1] for p in polygon) for polygon in polygons))
    bottom=math.floor(min(max(p[1] for p in polygon) for polygon in polygons))
    need(right-left>=4 and bottom-top>=4 and (right-left)*(bottom-top)<=8388608)
    count=orange=0;sums=[0,0,0];histogram=[0]*64
    for y in range(top,bottom):
        if (y-top)%16==0:budget()
        for x in range(left,right):
            point=[x+.5,y+.5]
            if not all(inside(point,polygon) for polygon in polygons) or any(inside(point,polygon) for polygon in excluded):continue
            rgb=image.getpixel((x,y))[:3];count+=1
            for channel in range(3):sums[channel]+=rgb[channel]
            orange+=rgb[0]>60 and rgb[0]-rgb[1]>12 and rgb[0]-rgb[2]>12
            histogram[(rgb[0]//64)*16+(rgb[1]//64)*4+rgb[2]//64]+=1
    need(count>=64)
    return dict(entityId=row['id'],roi=[left,top,right,bottom],pixels=count,meanRgb=[v/count for v in sums],
        blueDominance=(sums[2]-sums[0])/count,orangeFraction=orange/count,histogram=histogram,
        polygons=polygons,excludedMarkerPolygons=excluded)


def _original(capture,raw,before,after,*,run,ticket,scene_ticket,fixture_url,pid,epoch,budget):
    from PIL import Image
    need(all(type(value) is dict for value in (capture,before,after)) and integer(pid,1) and integer(epoch,1))
    identifier(run);identifier(ticket);identifier(scene_ticket)
    capture_packet(capture,capture.get('requestId'),pid,epoch,stereo=True,require_cameras=True)
    original_pixels(capture,raw)
    for packet in (before,after):
        subject_packet(packet,dict(schemaVersion=1,commandId=packet.get('requestId'),
            action='feature-graphics-subject-observe',runId=run),pid,epoch,require_avatar=True)
    need(before['instance']==after['instance'] and before['requestId']!=after['requestId'] and after['sequence']>before['sequence']
        and before['capturedEpochMs']<=capture['requestedEpochMs']<=capture['capturedEpochMs']<=after['requestedEpochMs']
        and after['capturedEpochMs']-before['requestedEpochMs']<=1500
        and before['source']['entities']==after['source']['entities']
        and not before['source']['absentIds'] and not after['source']['absentIds'])
    expected=fixture_url+'tickets/'+scene_ticket+'/graphics-scene.v1.json'
    need(resource_hash(before['source']['sceneUrl'])==resource_hash(after['source']['sceneUrl'])==resource_hash(expected))
    wanted=subject_ids(run);rows={row['id']:row for row in after['source']['entities']}
    for name,key in wanted.items():need(rows[key]['name']=='e2e-'+run+'-graphics-'+name)
    carrier=rows[wanted['marker']]
    need(carrier['type']=='Web' and carrier['visible'] and carrier['sourceUrl']==fixture_url+'tickets/'+scene_ticket+'/graphics-marker.v1.html')
    for name in ('fog-board','reflector'):
        need(rows[wanted[name]]['type']=='Box' and rows[wanted[name]]['visible'])
    need(rows[wanted['reflector']]['mirrorMode']=='mirror')
    source=capture['source'];forward=cameras(source,'forward')
    mirror_role='mirror' if source['renderTrace']['mirrorDrawCommands']>0 else 'forward'
    reflection=cameras(source,mirror_role)
    with Image.open(io.BytesIO(raw)) as image:
        image.load();eyes={}
        for eye in ('left','right'):
            eyes[eye]=dict(marker=marker(image,carrier,source,forward[eye],eye,run,ticket),
                haze=statistics(image,rows[wanted['fog-board']],carrier,source,forward[eye],forward[eye],eye,budget),
                mirror=statistics(image,rows[wanted['reflector']],carrier,source,reflection[eye],forward[eye],eye,budget))
    budget()
    oldest=min(before['requestedEpochMs'],capture['source']['recordedEpochMs'])
    return dict(stereoGraphicsPixelsVersion=VERSION,requestId=capture['requestId'],sha256=hashlib.sha256(raw).hexdigest(),
        pixelSha256=source['image']['pixelSha256'],frameIndex=source['stereo']['frameIndex'],
        executionSequence=source['stereo']['executionSequence'],mirrorCameraRole=mirror_role,eyes=eyes,
        subjects=dict(instance=before['instance'],beforeRequest=before['requestId'],beforeSequence=before['sequence'],
            afterRequest=after['requestId'],afterSequence=after['sequence']),capturedEpochMs=oldest)


def measure(capture,raw,before,after,*,run,ticket,scene_ticket,fixture_url,pid,epoch,
            guard,clock_ms,monotonic=time.monotonic):
    need(all(callable(v) for v in (guard,clock_ms,monotonic)) and integer(epoch,1))
    started=previous=monotonic();need(type(started) in (int,float) and math.isfinite(started) and started>=0)
    def budget():
        nonlocal previous
        current=monotonic();need(type(current) in (int,float) and math.isfinite(current)
            and previous<=current and current-started<5);previous=current
    need(guard() is not False);budget()
    value=_original(capture,raw,before,after,run=run,ticket=ticket,scene_ticket=scene_ticket,
        fixture_url=fixture_url,pid=pid,epoch=epoch,budget=budget)
    need(guard() is not False);budget();freshness_started=previous
    final=clock_ms();need(integer(final,epoch));budget();need(guard() is not False);budget()
    oldest=value['capturedEpochMs']
    need(max(final-oldest+math.ceil((previous-freshness_started)*1000),
        epoch-oldest+math.ceil((previous-started)*1000))<=1500)
    return value


def reduce_original(capture,raw,before,after,*,run,ticket,scene_ticket,fixture_url,pid,monotonic=time.monotonic):
    """Pure bounded archive recomputation at the original source interval.

    No current clock/guard is accepted or fabricated. The caller must bind this
    historical fact to its independently acquired current artifact/sample before
    using it in a live journey. Original capture timestamps are never changed.
    """
    need(callable(monotonic) and type(after) is dict and integer(after.get('capturedEpochMs'),1))
    started=previous=monotonic();need(type(started) in (int,float) and math.isfinite(started) and started>=0)
    def budget():
        nonlocal previous
        current=monotonic();need(type(current) in (int,float) and math.isfinite(current)
            and previous<=current and current-started<5);previous=current
    value=_original(capture,raw,before,after,run=run,ticket=ticket,scene_ticket=scene_ticket,
        fixture_url=fixture_url,pid=pid,epoch=after['capturedEpochMs'],budget=budget)
    need(after['capturedEpochMs']-value['capturedEpochMs']<=1500);budget()
    return value
