"""Original seven-entity fixture geometry, with explicit inventory partition."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from urllib.parse import urlsplit,parse_qs
from adapters.native_feature_observation import need,number
from feature_journeys.graphics_fixture import scene
from feature_journeys.graphics_resources import RESOURCE

VERSION=1


def near(actual,wanted,tolerance=1e-4):
    if type(wanted) in (int,float):return number(actual,-1e9,1e9) and abs(actual-wanted)<=tolerance
    if type(wanted) is list:return type(actual) is list and len(actual)==len(wanted) and all(near(a,b,tolerance) for a,b in zip(actual,wanted))
    return type(actual) is type(wanted) and actual==wanted


def aligned_entities(packet,run,scene_ticket,fixture_url,*,scene_inventory=None):
    """Readiness checks compare stimulus with originals; return no feature facts."""
    source=packet['source'];expected=scene(run,scene_ticket,fixture_url)
    need(not source['absentIds'] and len(source['entities'])==7 and not (source['scan']['unowned'] if scene_inventory is None else scene_inventory))
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
