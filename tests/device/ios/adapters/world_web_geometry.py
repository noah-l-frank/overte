"""Actual Web Entity registration, DPI, camera and DOM-to-UIKit projection."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import math
import re
from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.native_graphics_subject import vector,rotation,entity_id
from ios.adapters import world_web_dom as dom,emote_world
from ios.adapters.create_state import command as state_command
from ios.adapters.native_geometry import validate as uikit_original
from ios.adapters.places_model import IOSPlacesModel,text
from ios.adapters.scene_inventory import tree,uint64

VERSION=1
ACTION='feature-ios-world-web-geometry'
FILE=ACTION+'.json'
LIMIT=262144


def command(value):
    state_command(dict(value,action='feature-ios-create-state'));need(value['action']==ACTION);return value


def validate(value,query,pid,epoch=None,previous=None):
    command(query)
    exact(value,{'iosWorldWebGeometryVersion','requestId','runId','instance','sequence','processId','clockDomain','clockBefore','clockAfter','source'})
    need(type(value['iosWorldWebGeometryVersion']) is int and value['iosWorldWebGeometryVersion']==VERSION
        and value['requestId']==query['commandId'] and value['runId']==query['runId']
        and type(value['processId']) is int and value['processId']==pid and integer(pid,1)
        and re.fullmatch('[0-9a-f]{32}',text(value['instance'],32)) and integer(value['sequence'],1)
        and value['clockDomain']=='native-main-ios-world-web-geometry')
    before,after=value['clockBefore'],value['clockAfter']
    for clock in (before,after):exact(clock,{'epochMs','monotonicMs'});need(integer(clock['epochMs'],1) and integer(clock['monotonicMs']))
    utc=after['epochMs']-before['epochMs'];mono=after['monotonicMs']-before['monotonicMs'];need(0<=utc<1500 and 0<=mono<1500 and abs(utc-mono)<=250)
    if epoch is not None:fresh(after['epochMs'],epoch)
    source=value['source'];exact(source,{'complete','tree','entities','view'});need(source['complete'] is True)
    inventory=tree(source['tree']);need(inventory['complete']);entries={row['id']:row for row in inventory['entities']}
    need(type(source['entities']) is list and len(source['entities'])<=64);seen=set()
    for row in source['entities']:
        exact(row,{'id','hostType','parentId','position','rotation','dimensions','registrationPoint','dpi','inputMode','billboardMode','visible','locked','sourceUrl','userData','lastEditedEpochUs'})
        need(entity_id(row['id']) and row['id'] in entries and row['id'] not in seen);seen.add(row['id'])
        need(row['hostType']==entries[row['id']]['hostType'] and row['hostType'] in ('local','avatar','domain')
            and (row['parentId']=='00000000-0000-0000-0000-000000000000' or entity_id(row['parentId'])))
        vector(row['position'],3,-1e8,1e8);rotation(row['rotation']);vector(row['dimensions'],3,.000001,1e6)
        vector(row['registrationPoint'],3,0,1);need(number(row['dpi'],1,1000) and row['inputMode'] in ('mouse','touch')
            and row['billboardMode'] in ('none','yaw','full')
            and type(row['visible']) is bool and type(row['locked']) is bool)
        text(row['sourceUrl'],4096);text(row['userData'],8192);uint64(row['lastEditedEpochUs'])
        need(row['lastEditedEpochUs']==entries[row['id']]['lastEditedEpochUs'])
    view=source['view'];exact(view,{'position','rotation','fieldOfViewDegrees','aspectRatio','perspective','uiWidth','uiHeight'})
    vector(view['position'],3,-1e8,1e8);rotation(view['rotation'])
    need(number(view['fieldOfViewDegrees'],1,179) and number(view['aspectRatio'],.01,100) and type(view['perspective']) is bool
        and integer(view['uiWidth'],1,16384) and integer(view['uiHeight'],1,16384))
    if previous is not None:
        original(previous);need(value['instance']==previous['instance'] and value['sequence']>previous['sequence']
            and value['requestId']!=previous['requestId'] and before['epochMs']>=previous['clockAfter']['epochMs']
            and before['monotonicMs']>=previous['clockAfter']['monotonicMs']
            and source['tree']['treeInstance']==previous['source']['tree']['treeInstance']
            and source['tree']['revisionBefore']>=previous['source']['tree']['revisionAfter'])
    return value


def original(value):
    return validate(value,dict(schemaVersion=1,commandId=value['requestId'],action=ACTION,runId=value['runId']),value['processId'])


def rotate(vector,quaternion):
    length=math.sqrt(sum(value*value for value in quaternion));need(length>0)
    x,y,z,w=[value/length for value in quaternion];vx,vy,vz=vector
    tx,ty,tz=2*(y*vz-z*vy),2*(z*vx-x*vz),2*(x*vy-y*vx)
    return [vx+w*tx+y*tz-z*ty,vy+w*ty+z*tx-x*tz,vz+w*tz+x*ty-y*tx]


def point(value,document,world,uikit,entity,control):
    return _point(value,document,world,uikit,entity,control)


def point_snapshot(value,document,world,uikit,entity,control,native_snapshot):
    """The new actual DOM-before-World acquisition, joined to its byte source."""
    from ios.adapters import world_web_snapshot as legacy,world_web_whole_snapshot as whole
    from adapters.script_feature.history import same
    version=native_snapshot.get('iosWorldWebSnapshotVersion');need(type(version) is int and version in (1,2))
    snapshot=legacy if version==1 else whole
    query=dict(schemaVersion=1,commandId=native_snapshot['commandId'],action=snapshot.ACTION,
        runId=native_snapshot['runId'],fixtureUrl=native_snapshot['fixtureUrl'])
    snapshot.validate(native_snapshot,query,value['processId']);need(native_snapshot['status']=='ready')
    originals=snapshot.selected(native_snapshot,('geometry','document','world'))
    need(same(originals['geometry'],value) and same(originals['document'],document) and same(originals['world'],world))
    return _point(value,document,world,uikit,entity,control,native_snapshot=native_snapshot)


def _point(value,document,world,uikit,entity,control,*,native_snapshot=None):
    """Original DOM rectangle on the actual unparented Web Entity plane."""
    original(value);dom.original(document);emote_world.original(world)
    need(value['runId']==document['runId']==world['runId'] and value['processId']==document['processId']==world['processId'])
    if native_snapshot is None:
        need(0<=value['clockAfter']['epochMs']-world['clockBefore']['epochMs']<1500
            and world['clockBefore']['epochMs']<=document['source']['dom']['capturedEpochMs']
                <=document['capturedEpochMs']<=value['clockAfter']['epochMs'])
    else:
        need(native_snapshot['clockBefore']['epochMs']<=document['source']['dom']['capturedEpochMs']<=document['capturedEpochMs']
            <=world['clockBefore']['epochMs']<=value['clockAfter']['epochMs']<=native_snapshot['clockAfter']['epochMs'])
    source=value['source'];need(source['tree']==world['source']['tree'])
    rows=[row for row in source['entities'] if row['id']==entity];need(len(rows)==1);row=rows[0]
    markers=[marker for marker in world['source']['markers'] if marker['id']==entity];need(len(markers)==1);marker=markers[0]
    need(all(row[key]==marker[key] for key in ('id','hostType','sourceUrl','userData','position','rotation','dimensions','visible','lastEditedEpochUs'))
        and row['hostType']=='local' and row['parentId']=='00000000-0000-0000-0000-000000000000'
        and row['visible'] and not row['locked'] and row['inputMode']=='touch' and row['billboardMode']=='none')
    native=document['source']['nativeView'];need(native['sourceIdentity']=='web-entity:'+entity and native['sourceUrl']==row['sourceUrl'])
    observed=document['source']['dom'];elements=[element for element in observed['elements'] if element['id']==control]
    need(len(elements)==1 and elements[0]['enabled'] and elements[0]['visible']);rect=elements[0]['rect']
    width,height=observed['document']['width'],observed['document']['height']
    expected=[dimension*39.3701*row['dpi'] for dimension in row['dimensions'][:2]]
    scale=min(1,4096/max(expected));expected=[min(2048,d*scale) for d in expected]
    need(abs(width-expected[0])<=2 and abs(height-expected[1])<=2)
    # Actual DOM centre must be fully visible, with a margin from hit borders.
    need(rect[0]>=0 and rect[1]>=0 and rect[2]<=width and rect[3]<=height and rect[2]-rect[0]>=8 and rect[3]-rect[1]>=8)
    uv=[(rect[0]+rect[2])/2/width,(rect[1]+rect[3])/2/height];registration=row['registrationPoint'];dims=row['dimensions']
    local=[(uv[0]-registration[0])*dims[0],(1-uv[1]-registration[1])*dims[1],(.5-registration[2])*dims[2]]
    offset=rotate(local,row['rotation']);position=[a+b for a,b in zip(row['position'],offset)];view=source['view'];need(view['perspective'])
    need(all(view[key]==world['source']['view'][key] for key in ('position','rotation','fieldOfViewDegrees','aspectRatio','perspective')))
    q=view['rotation'];relative=rotate([a-b for a,b in zip(position,view['position'])],[-q[0],-q[1],-q[2],q[3]])
    x,y,z=relative;need(z<-.01);half=math.tan(math.radians(view['fieldOfViewDegrees'])/2)
    nx,ny=x/(-z*half*view['aspectRatio']),y/(-z*half);need(number(nx,-.9,.9) and number(ny,-.9,.9))
    native_ui,viewport=uikit_original(uikit,uikit['commandId'],native_epoch_ms=value['clockAfter']['epochMs'])
    need(type(native_ui['nativeUi'].get('keyboardVisible')) is bool and number(native_ui['nativeUi'].get('imeInsetBottom'),0,10000)
        and abs(view['uiWidth']-native_ui['window']['width'])<=1 and abs(view['uiHeight']-native_ui['window']['height'])<=1
        and abs(view['uiWidth']/view['uiHeight']-view['aspectRatio'])<.005)
    x=viewport['x']+(nx+1)*viewport['width']/2;y=viewport['y']+(1-ny)*viewport['height']/2
    need(y+8<native_ui['nativeUi']['surfaceHeight']-native_ui['nativeUi']['imeInsetBottom'])
    return dict(x=x,y=y,
        surfaceWidth=native_ui['nativeUi']['surfaceWidth'],surfaceHeight=native_ui['nativeUi']['surfaceHeight'],
        elementBirth=elements[0]['birth'],domInstance=observed['instance'],domPoint=[uv[0]*width,uv[1]*height])


class IOSWorldWebGeometry(IOSPlacesModel):
    _action=ACTION
    _command=staticmethod(command)
    _validate=staticmethod(validate)
    _limit=LIMIT
    _acquisition_key='iosWorldWebGeometryAcquisitionVersion'
