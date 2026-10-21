"""Decode owned world-surface identity in both original executing eye views.

This is historical pixel reduction, not a live clock or UI visibility verdict.
The caller must independently admit the actual UI composition and native state.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import hashlib
import io
import math
import time
from adapters.native_feature_observation import integer,need
from adapters.graphics_journey.geometry import aligned_entities
from adapters.stereo_graphics_pixels import original_context,cameras,world,project,marker,quad,inside
from adapters.vr_graphics_subject import separate_inventory
from feature_journeys.graphics_fixture import PICO_RESOURCE,PICO_PROFILE
from feature_journeys.graphics_surface_cues import COLUMNS,ROWS,decode
from feature_journeys.evidence import MarkerNotReady

VERSION=1


def reflected(point,mirror):
    normal=[a-b for a,b in zip(world(mirror,[0,0,1]),mirror['position'])]
    distance=sum((a-b)*n for a,b,n in zip(point,mirror['position'],normal))
    return [a-2*distance*n for a,n in zip(point,normal)]


def statistics(values):
    need(type(values) is list and values)
    count=len(values);sums=[sum(rgb[c] for rgb in values) for c in range(3)];histogram=[0]*64
    for rgb in values:histogram[(rgb[0]//64)*16+(rgb[1]//64)*4+rgb[2]//64]+=1
    return dict(pixels=count,meanRgb=[value/count for value in sums],blueDominance=(sums[2]-sums[0])/count,
        orangeFraction=sum(rgb[0]>60 and rgb[0]-rgb[1]>12 and rgb[0]-rgb[2]>12 for rgb in values)/count,histogram=histogram)


def surface_cells(image,row,mirror,camera,source,eye,carrier,marker_views,budget):
    """Read central original pixels; never crop, enlarge or reconstruct a cell."""
    def point(u,v):
        value=world(row,[(u-.5)*row['dimensions'][0],(.5-v)*row['dimensions'][1],0])
        return project(reflected(value,mirror) if mirror is not None else value,camera,source,eye)
    polygon=[point(u,v) for u,v in ((0,0),(1,0),(1,1),(0,1))]
    excluded=[quad(carrier,view,source,eye,plane=True) for view in marker_views]
    values=[]
    for y in range(ROWS):
        budget();line=[]
        for x in range(COLUMNS):
            center=point((x+.5)/COLUMNS,(y+.5)/ROWS)
            # Original eye spacing, no minimum inferred from a resized PNG.
            need(math.dist(point(x/COLUMNS,(y+.5)/ROWS),point((x+1)/COLUMNS,(y+.5)/ROWS))>=3
                and math.dist(point((x+.5)/COLUMNS,y/ROWS),point((x+.5)/COLUMNS,(y+1)/ROWS))>=3)
            locations=set()
            for dy in (-.25,0,.25):
                for dx in (-.25,0,.25):
                    pixel=point((x+.5+dx)/COLUMNS,(y+.5+dy)/ROWS)
                    if any(inside(pixel,shape) for shape in excluded):raise MarkerNotReady('world surface obscured by near marker')
                    locations.add(tuple(math.floor(v) for v in pixel))
            need(len(locations)>=4)
            line.append(dict(center=center,values=[list(image.getpixel(location)[:3]) for location in sorted(locations)]))
        values.append(line)
    return values,polygon


def decode_cells(values,surface,run,ticket):
    bits=[];whites=[];calibration=[];contrasts=[]
    for row in values:
        means=[[sum(rgb[c] for rgb in cell['values'])/len(cell['values']) for c in range(3)] for cell in row]
        black,white=means[:2];delta=[b-a for a,b in zip(black,white)];length=sum(v*v for v in delta)
        if length<40**2:raise MarkerNotReady('world surface contrast unavailable')
        contrast=math.sqrt(length);contrasts.append(contrast);calibration.append(statistics(row[1]['values']))
        decoded=[]
        for cell,mean in zip(row,means):
            fraction=sum((a-b)*d for a,b,d in zip(mean,black,delta))/length
            bit=0 if abs(fraction)<=.18 else 1 if abs(fraction-1)<=.18 else None
            if bit is None:raise MarkerNotReady('ambiguous world surface cell')
            endpoint=white if bit else black
            if any(math.dist(rgb,endpoint)>max(6,.20*contrast) for rgb in cell['values']):
                raise MarkerNotReady('mixed world surface cell')
            decoded.append(bit)
            if bit:whites.extend(cell['values'])
        if decoded[:2]!=[0,1]:raise MarkerNotReady('invalid world surface calibration')
        bits.extend(decoded[2:])
    raw=int(''.join(str(v) for v in bits),2).to_bytes(24,'big')
    try:identity=decode(raw,surface,run=run,ticket=ticket)
    except ValueError as error:raise MarkerNotReady('invalid original world surface code') from error
    return identity|statistics(whites)|dict(calibrationRows=calibration,minimumContrast=min(contrasts))


def read_surface(image,row,mirror,views,source,eye,carrier,marker_views,budget,run,ticket,surface,required):
    results=[];polygons=[];all_values=[]
    for camera in views:
        values,polygon=surface_cells(image,row,mirror,camera,source,eye,carrier,marker_views,budget)
        polygons.append(polygon);all_values.extend(rgb for line in values for cell in line for rgb in cell['values'])
        try:value=decode_cells(values,surface,run,ticket)
        except MarkerNotReady:
            if required:raise
            continue
        if not required:raise MarkerNotReady('reflection code remains while native mirror is off')
        if not value['current']:raise MarkerNotReady('stale or foreign original world surface code')
        results.append(value)
    if not required:return statistics(all_values)|dict(surfaceCodeVersion=VERSION,surface=surface,current=False,polygons=polygons)
    need(results and all(row['challengeSha256']==results[0]['challengeSha256'] for row in results))
    # Each actual used camera must decode, not only a convenient candidate.
    return results[0]|dict(polygons=polygons,cameraCount=len(results))


def reduce_original(capture,raw,before,after,*,run,ticket,scene_ticket,fixture_url,pid,monotonic=time.monotonic):
    from PIL import Image
    need(callable(monotonic) and type(after) is dict and integer(after.get('capturedEpochMs'),1))
    started=previous=monotonic();need(type(started) in (int,float) and math.isfinite(started) and started>=0)
    def budget():
        nonlocal previous
        current=monotonic();need(type(current) in (int,float) and math.isfinite(current)
            and previous<=current and current-started<5);previous=current
    source,rows,ids,carrier=original_context(capture,raw,before,after,run=run,ticket=ticket,
        scene_ticket=scene_ticket,fixture_url=fixture_url,pid=pid,epoch=after['capturedEpochMs'],resource=PICO_RESOURCE)
    for packet in (before,after):
        aligned_entities(packet,run,scene_ticket,fixture_url,scene_inventory=separate_inventory(packet)['scene'],profile=PICO_PROFILE)
    forward=cameras(source,'forward');mirrors=source['renderTrace']['mirrorDrawCommands']>0
    views=cameras(source,'mirror') if mirrors else forward
    with Image.open(io.BytesIO(raw)) as image:
        image.load();eyes={}
        for eye in ('left','right'):
            eyes[eye]=dict(marker=marker(image,carrier,source,forward[eye],eye,run,ticket),
                haze=read_surface(image,rows[ids['fog-board']],None,forward[eye],source,eye,carrier,forward[eye],budget,run,ticket,'haze',True),
                mirror=read_surface(image,rows[ids['reflected-color']],rows[ids['reflector']],views[eye],source,eye,carrier,forward[eye],budget,run,ticket,'reflection',mirrors))
    oldest=min(before['requestedEpochMs'],source['recordedEpochMs']);need(after['capturedEpochMs']-oldest<=1500);budget()
    return dict(stereoGraphicsSurfacePixelsVersion=VERSION,requestId=capture['requestId'],sha256=hashlib.sha256(raw).hexdigest(),
        pixelSha256=source['image']['pixelSha256'],frameIndex=source['stereo']['frameIndex'],
        executionSequence=source['stereo']['executionSequence'],eyes=eyes,capturedEpochMs=oldest)
