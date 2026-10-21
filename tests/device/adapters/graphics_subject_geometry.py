"""Pure geometry joins selected from frozen Phone sources; no platform input."""
# Derived from fe4684bf46585088370b3a328a738f147e670b97.
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import itertools
import math
from urllib.parse import parse_qs,urlsplit
from adapters.native_feature_observation import integer,need,number
from adapters.render_view import recorded_view
from feature_journeys.graphics_fixture import scene,VIEW
from feature_journeys.graphics_resources import RESOURCE

VERSION=1


def near(actual,wanted,tolerance=1e-4):
    if type(wanted) in (int,float):return number(actual,-1e9,1e9) and abs(actual-wanted)<=tolerance
    if type(wanted) is list:return type(actual) is list and len(actual)==len(wanted) and all(near(a,b,tolerance) for a,b in zip(actual,wanted))
    return type(actual) is type(wanted) and actual==wanted


def aligned_entities(packet,run,scene_ticket,fixture_url):
    """Readiness checks compare stimulus with originals; return no feature facts."""
    source=packet['source'];expected=scene(run,scene_ticket,fixture_url)
    need(not source['absentIds'] and len(source['entities'])==7 and not source['scan']['unowned'])
    root=urlsplit(fixture_url);actual=urlsplit(source['sceneUrl']);query=parse_qs(actual.query,strict_parsing=True)
    need(actual.scheme==root.scheme and actual.netloc==root.netloc and actual.username is None
         and actual.password is None and not actual.fragment and set(query)<={'location'}
         and all(len(values)==1 and len(values[0])<=256 for values in query.values())
         and actual.path==root.path+'tickets/'+scene_ticket+'/'+RESOURCE)
    for document in expected['Entities']:
        rows=[row for row in source['entities'] if row['id']==document['id'].strip('{}')];need(len(rows)==1)
        row=rows[0]
        need(row['name']==document['name'] and row['type']==document['type'] and row['hostType'] in ('local','domain') and row['visible'])
        for field,axes in (('position','xyz'),('dimensions','xyz'),('rotation','xyzw')):
            need(near(row[field],[document[field][axis] for axis in axes]))
        if 'color' in document:need(row['color']==[document['color'][axis] for axis in ('red','green','blue')])
        if 'mirrorMode' in document:need(row['mirrorMode']==document['mirrorMode'])
        if 'sourceUrl' in document:need(row['sourceUrl']==document['sourceUrl'])
        if document['type']=='Zone':
            haze=document['haze']
            need(row['hazeMode']==2 and near(row['haze']['range'],haze['hazeRange'])
                 and row['haze']['color']==[haze['hazeColor'][axis] for axis in ('red','green','blue')]
                 and row['haze']['glare']==haze['hazeEnableGlare'] and row['haze']['altitudeEffect']==haze['hazeAltitudeEffect']
                 and near(row['haze']['backgroundBlend'],haze['hazeBackgroundBlend']))
def aligned_subject(packet,run,scene_ticket,fixture_url):
    aligned_entities(packet,run,scene_ticket,fixture_url)
    view=packet['source']['view'];need(view['perspective'] and view['mode'] in ('first person','first person look at')
        and near(view['position'],[VIEW['position'][a] for a in 'xyz'],.01))
    # Quaternions q/-q represent the same measured view. Do not rewrite either.
    rotation=[VIEW['rotation'][a] for a in 'xyzw']
    need(near(view['rotation'],rotation,.001) or near(view['rotation'],[-v for v in rotation],.001))


def steady_subject(before,after):
    left,right=before['source'],after['source']
    need(all(left[key]==right[key] for key in ('subjectVersion','sceneUrl','entities','absentIds','scan')))
    a,b=left['view'],right['view']
    need(a['mode']==b['mode'] and a['perspective']==b['perspective'] and near(a['position'],b['position'],.001)
         and near(a['fieldOfViewDegrees'],b['fieldOfViewDegrees'],.001) and near(a['aspectRatio'],b['aspectRatio'],.0001))
    need(near(a['rotation'],b['rotation'],.0001) or near(a['rotation'],[-v for v in b['rotation']],.0001))
    if left['subjectVersion']>=2:
        a,b=left['avatarPose'],right['avatarPose']
        need(near(a['feetPosition'],b['feetPosition'],.001) and near(a['modelScale'],b['modelScale'],.0001)
             and (near(a['orientation'],b['orientation'],.0001) or near(a['orientation'],[-v for v in b['orientation']],.0001)))
    if left['subjectVersion']==3:
        a,b=left['cameraOrbit'],right['cameraOrbit']
        need(all(near(a[key],b[key],.0001) for key in ('boomLength','minimumBoomLength','defaultBoomLength'))
             and (near(a['lookAtRotation'],b['lookAtRotation'],.0001)
                  or near(a['lookAtRotation'],[-v for v in b['lookAtRotation']],.0001)))



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


