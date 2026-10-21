"""Original VR tablet opacity prerequisites; coded pixels prove visibility."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters.native_feature_observation import exact,integer,need,number
from feature_journeys.contract import identifier
from adapters.native_graphics_subject import entity_id

VERSION=1


def polygon(value):
    need(type(value) is list and len(value)==4 and all(type(p) is list and len(p)==2
        and all(number(v,-1e9,1e9) for v in p) for p in value));return value


def validate(value):
    need(type(value) is dict and type(value.get('complete')) is bool)
    exact(value,{'compositionVersion','complete'}|({'screen','root','viewport','ancestors'} if value['complete'] else set()))
    need(type(value['compositionVersion']) is int and value['compositionVersion']==VERSION)
    if not value['complete']:return value
    screen=value['screen'];exact(screen,{'id','parentId','type','hostType','visible','alpha','useBackground','pulseAlphaMode'})
    need(entity_id(screen['id']) and entity_id(screen['parentId']))
    need(screen['id']!=screen['parentId'] and screen['type']=='Web' and screen['hostType']=='local'
        and all(type(screen[k]) is bool for k in ('visible','useBackground')) and number(screen['alpha'],0,1)
        and integer(screen['pulseAlphaMode'],0,2))
    root=value['root'];exact(root,{'id','class','objectName','color','radius','width','height','quad'})
    identifier(root['id']);need(type(root['class']) is str and root['class'].startswith('TabletRoot_QMLTYPE_')
        and len(root['class'])<=128 and root['objectName']=='tabletRoot' and type(root['color']) is list
        and len(root['color'])==4 and all(number(v,0,1) for v in root['color'])
        and number(root['radius'],0,1e6) and all(number(root[k],.0001,1e6) for k in ('width','height')))
    polygon(root['quad']);viewport=value['viewport']
    need(type(viewport) is list and len(viewport)==2 and all(integer(v,1,65536) for v in viewport)
        and type(value['ancestors']) is list and 1<=len(value['ancestors'])<=128)
    for row in value['ancestors']:
        exact(row,{'visible','opacity','layerEnabled','maskPresent','clip'})
        need(all(type(row[k]) is bool for k in ('visible','layerEnabled','maskPresent')) and number(row['opacity'],0,1))
        if row['clip'] is not None:polygon(row['clip'])
    return value


def covers(quad,viewport):
    polygon(quad)
    def cross(a,b,p):return (b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0])
    turns=[cross(quad[i],quad[(i+1)%4],quad[(i+2)%4]) for i in range(4)]
    need(all(v>1e-8 for v in turns) or all(v< -1e-8 for v in turns))
    for point in ((0,0),(viewport[0],0),(viewport[0],viewport[1]),(0,viewport[1])):
        sides=[cross(a,b,point) for a,b in zip(quad,quad[1:]+quad[:1])]
        # No bounding-box substitution for a rotated/clipped background.
        need(all(v>=-1e-8 for v in sides) or all(v<=1e-8 for v in sides))


def admit(ui,subject):
    need(ui['graphicsObservationVersion']==2);value=validate(ui['composition'])
    if not ui['tabletShown']:return value
    need(value['complete']);screen=value['screen'];root=value['root'];framework=subject['source']['framework']
    need(screen['id']==framework['tablet']['screen'] and screen['parentId']==framework['tablet']['frame']
        and screen['visible'] and screen['alpha']==1 and screen['useBackground'] and screen['pulseAlphaMode']==0
        and root['color'][3]==1 and root['radius']==0 and not framework['keyboard']['raised'])
    rows={row['id']:row for row in framework['entities']}
    need(screen['id'] in rows and screen['parentId'] in rows and rows[screen['id']]['present']
        and rows[screen['parentId']]['present'] and rows[screen['id']]['type']=='Web'
        and rows[screen['id']]['parentId']==screen['parentId'])
    covers(root['quad'],value['viewport'])
    for row in value['ancestors']:
        need(row['visible'] and row['opacity']==1 and not row['layerEnabled'] and not row['maskPresent'])
        if row['clip'] is not None:covers(row['clip'],value['viewport'])
    return value
