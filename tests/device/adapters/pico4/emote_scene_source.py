"""Original Pico local scene stimulus ownership; never stereo/feature evidence."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import math
from urllib.parse import urlsplit

from adapters.native_avatar_render import _OriginalQuery,envelope,nonce,controlled_resources
from adapters.native_feature_observation import exact,integer,need,number
from adapters.native_graphics_subject import vector,rotation,entity_id,text
from adapters.world_render_evidence import recorded_view
from adapters.pico4.graphics_scene import rotation_equal

VERSION=1
FILE='feature-pico-emote-scene.json'
OBSERVE='feature-pico-emote-scene-observe'
INPUT='feature-pico-emote-scene-input'
PHASES=('creating','active','failed','releasing','drained')
ROLES=('backdrop','marker')
NULL='00000000-0000-0000-0000-000000000000'
VIEW={'position','rotation','projection','fieldOfViewDegrees','aspectRatio','nearClip','farClip','perspective'}


def layout(value):
    extent,roi=value['imageExtent'],value['markerRoi']
    need(type(extent) is list and len(extent)==2 and all(integer(v,240,16384) for v in extent)
        and type(roi) is list and len(roi)==4 and all(integer(v,0,16384) for v in roi))
    x0,y0,x1,y1=roi;w,h=extent
    need(x1<=w and y1<=h and x1-x0>=160 and y1-y0>=40 and (x1-x0)*(y1-y0)<=.1*w*h)


def command(value):
    base={'schemaVersion','commandId','action','runId'}
    need(type(value) is dict and value.get('action') in (OBSERVE,INPUT))
    if value['action']==INPUT:
        need(value.get('operation') in ('prepare','release'));base.add('operation')
        base|={'ticket','fixtureUrl','imageExtent','markerRoi'} if value['operation']=='prepare' else {'fixtureInstance'}
    exact(value,base)
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and nonce(value['commandId']) and nonce(value['runId']))
    if value['action']==INPUT:
        if value['operation']=='prepare':
            need(nonce(value['ticket']) and text(value['fixtureUrl'],512) and not any(ord(c)<=32 or ord(c)==127 for c in value['fixtureUrl']))
            p=urlsplit(value['fixtureUrl']);p.port
            need(p.scheme in ('http','https') and p.hostname and p.username is None and p.password is None and '@' not in p.netloc
                and not p.query and not p.fragment and p.path=='/feature-fixture/v1/runs/'+value['runId']+'/')
            layout(value)
        else:need(nonce(value['fixtureInstance']))
    return value


def receipt(value,request,pid,epoch):
    command(request);need(request['action']==INPUT);envelope(value,request,pid,epoch)
    source=value['source'];exact(source,{'picoEmoteSceneInputVersion','commandId','runId','fixtureInstance','operation','recorded'})
    need(type(source['picoEmoteSceneInputVersion']) is int and source['picoEmoteSceneInputVersion']==VERSION
        and source['commandId']==request['commandId'] and source['runId']==request['runId'] and nonce(source['fixtureInstance'])
        and source['operation']==request['operation'] and source['recorded'] is True)
    if request['operation']=='release':need(source['fixtureInstance']==request['fixtureInstance'])
    return value


def validate(value,request,pid,epoch):
    command(request);need(request['action']==OBSERVE);envelope(value,request,pid,epoch)
    source=value['source'];exact(source,{'picoEmoteSceneVersion','fixtureInstance','runId','phase','createdEpochMs','originalInput','originalView','objects','entities','absentIds','retainedObjects'})
    need(type(source['picoEmoteSceneVersion']) is int and source['picoEmoteSceneVersion']==VERSION and nonce(source['fixtureInstance'])
        and source['runId']==request['runId'] and source['phase'] in PHASES and integer(source['createdEpochMs'],1,value['capturedEpochMs']))
    original=command(source['originalInput']);need(original['action']==INPUT and original['operation']=='prepare' and original['runId']==source['runId'])
    view=source['originalView'];exact(view,VIEW|{'feetPosition','modelScale','boomLength','mode','hmd'})
    recorded_view({key:view[key] for key in VIEW});vector(view['feetPosition'],3,-1e6,1e6)
    need(view['hmd'] is True and view['mode']=='look at' and number(view['modelScale'],.0001,1000) and number(view['boomLength'],1.5,25)
        and abs(original['imageExtent'][0]/original['imageExtent'][1]-view['aspectRatio'])<=.005)
    objects=source['objects'];need(type(objects) is list and len(objects)<=2 and integer(source['retainedObjects'],0,len(objects)))
    ids={};roles=[]
    for row in objects:
        exact(row,{'role','id'});roles.append(row['role']);need(row['id'] is None or entity_id(row['id']) and row['id']!=NULL)
        if row['id'] is not None:need(row['id'] not in ids);ids[row['id']]=row['role']
    need(roles==list(ROLES[:len(objects)]))
    present=source['entities'];absent=source['absentIds'];need(type(present) is list and type(absent) is list and len(present)+len(absent)==len(ids))
    measured=[]
    for row in present:
        exact(row,{'id','role','originalObject','name','type','parentId','hostType','position','rotation','dimensions','color','visible','sourceUrl','locked','collisionless','canCastShadow','dpi','lastEditedEpochUs'})
        need(row['id'] in ids and row['role']==ids[row['id']] and row['id'] not in measured);measured.append(row['id'])
        need(type(row['originalObject']) is bool and text(row['name'],256) and text(row['type'],64) and entity_id(row['parentId'])
            and row['hostType'] in ('local','foreign') and text(row['sourceUrl'],2048)
            and all(type(row[k]) is bool for k in ('visible','locked','collisionless','canCastShadow'))
            and number(row['dpi'],0,1e6) and integer(row['lastEditedEpochUs'],1))
        vector(row['position'],3,-1e6,1e6);rotation(row['rotation']);vector(row['dimensions'],3,0,1e8)
        need(type(row['color']) is list and len(row['color'])==3 and all(integer(v,0,255) for v in row['color']))
    need(len(absent)==len(set(absent)) and all(id in ids for id in absent) and set(measured).isdisjoint(absent) and set(measured)|set(absent)==set(ids))
    if source['phase']=='active':need(len(objects)==2 and len(ids)==2)
    if source['phase']=='drained':need(not present and not source['retainedObjects'])
    return value


def continuity(before,current):
    if before is None:return
    need(current['instance']==before['instance'] and current['sequence']>before['sequence'] and current['requestId']!=before['requestId']
        and current['capturedEpochMs']>=before['capturedEpochMs'])
    a,b=before['source'],current['source']
    need(all(a[key]==b[key] for key in ('fixtureInstance','runId','createdEpochMs','originalInput','originalView','objects')))
    allowed={'creating':PHASES,'active':('active','releasing','drained'),'failed':('failed','releasing','drained'),
        'releasing':('releasing','drained'),'drained':('drained',)}
    need(b['phase'] in allowed[a['phase']])
    need(b['retainedObjects']<=a['retainedObjects'])


def _solve(matrix,vector):
    rows=[[float(matrix[row*4+column]) for column in range(4)]+[float(vector[row])] for row in range(4)]
    for column in range(4):
        pivot=max(range(column,4),key=lambda row:abs(rows[row][column]));need(abs(rows[pivot][column])>1e-12)
        rows[column],rows[pivot]=rows[pivot],rows[column]
        scale=rows[column][column];rows[column]=[value/scale for value in rows[column]]
        for row in range(4):
            if row==column:continue
            scale=rows[row][column];rows[row]=[a-scale*b for a,b in zip(rows[row],rows[column])]
    result=[row[4] for row in rows];need(all(number(v,-1e12,1e12) for v in result));return result


def _rotate(q,p):
    length=math.sqrt(sum(v*v for v in q));need(length>0);x,y,z,w=[v/length for v in q]
    def cross(a,b):return [a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]]
    first=cross([x,y,z],p);second=cross([x,y,z],first)
    return [a+2*(w*b+c) for a,b,c in zip(p,first,second)]


def expected_layout(source):
    """Expected fixture geometry from original native setup view, not observations."""
    recorded_view({key:source['originalView'][key] for key in VIEW});command(source['originalInput'])
    v=source['originalView'];w,h=source['originalInput']['imageExtent'];x0,y0,x1,y1=source['originalInput']['markerRoi']
    def point(x,y,distance):
        p=_solve(v['projection'],[2*x/w-1,1-2*y/h,-1,1]);need(abs(p[3])>1e-8)
        p=[a/p[3] for a in p[:3]];need(p[2]<-1e-8)
        local=[a*(-distance/p[2]) for a in p];offset=_rotate(v['rotation'],local)
        return [a+b for a,b in zip(v['position'],offset)],local
    forward=_rotate(v['rotation'],[0,0,-1]);depth=sum((a-b)*c for a,b,c in zip(v['feetPosition'],v['position'],forward))+4*v['modelScale']
    need(number(depth,v['nearClip']*4+1e-9,1e6))
    result={}
    for name,left,top,right,bottom,distance in (('backdrop',-.05*w,-.05*h,1.05*w,1.05*h,depth),
            ('marker',x0,y0,x1,y1,max(.25,v['nearClip']*2))):
        a,la=point(left,top,distance);b,lb=point(right,bottom,distance)
        result[name]=dict(position=[(x+y)/2 for x,y in zip(a,b)],dimensions=[abs(lb[0]-la[0]),abs(lb[1]-la[1]),.01],rotation=deepcopy(v['rotation']))
    return result



def ready(value,prepare,avatar):
    source=value['source'];validate(value,dict(schemaVersion=1,commandId=value.get('requestId'),action=OBSERVE,runId=source.get('runId')),
        value.get('processId'),value.get('capturedEpochMs'));controlled_resources(avatar)
    current=avatar['source'];view=source['originalView'];expected=expected_layout(source)
    need(source['phase']=='active' and source['originalInput']==command(prepare) and len(source['entities'])==2
        and source['retainedObjects']==2 and not source['absentIds'] and value['instance']==avatar['instance']
        and value['processId']==avatar['processId'] and current['cameraMode']==view['mode'] and current.get('cameraStateVersion')==1
        and current['cameraState']['hmd'] is True and abs(current['cameraState']['boomLength']-view['boomLength'])<=.0001)
    def near(a,b,tolerance):return len(a)==len(b) and all(abs(x-y)<=tolerance for x,y in zip(a,b))
    need(near(current['pose']['feetPosition'],view['feetPosition'],.01) and abs(current['pose']['modelScale']-view['modelScale'])<=.0001
        and near(current['view']['position'],view['position'],.01) and rotation_equal(current['view']['rotation'],view['rotation'],.001)
        and near(current['view']['projection'],view['projection'],.0001))
    for key in ('fieldOfViewDegrees','aspectRatio','nearClip','farClip'):need(abs(current['view'][key]-view[key])<=.0001)
    for row in source['entities']:
        need(row['originalObject'] and row['hostType']=='local' and row['parentId']==NULL and row['visible'] and not row['locked']
            and row['collisionless'] and not row['canCastShadow'] and row['name']=='e2e-'+source['runId']+'-emote-'+row['role']
            and near(row['position'],expected[row['role']]['position'],.001) and near(row['dimensions'],expected[row['role']]['dimensions'],.001)
            and rotation_equal(row['rotation'],expected[row['role']]['rotation'],.0001))
        if row['role']=='marker':need(row['type']=='Web' and row['sourceUrl']==prepare['fixtureUrl']+'tickets/'+prepare['ticket']+'/graphics-marker.v1.html' and row['dpi']==100)
        else:need(row['type']=='Box' and row['color']==[128,128,128] and not row['sourceUrl'])
    return deepcopy(source)


def retired(value):
    source=value['source'];validate(value,dict(schemaVersion=1,commandId=value.get('requestId'),action=OBSERVE,runId=source.get('runId')),
        value.get('processId'),value.get('capturedEpochMs'))
    return source['phase']=='drained' and not source['entities'] and source['retainedObjects']==0


class NativePicoEmoteScene(_OriginalQuery):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);need(self.ios is False);self.last_observation=None
    def read(self,run):
        request=command({**self._request(OBSERVE),'runId':run});value=self._read(request,validate)
        continuity(self.last_observation,value);self.last_observation=deepcopy(value);return value
    def input(self,request,*,intent):
        command(request);need(request['action']==INPUT and callable(intent));intent(deepcopy(request))
        return self._read(request,receipt) # Exactly one dispatch; uncertain input stays owned.
    def restore(self,rows):
        need(self.last is None and type(rows) is list and 0<len(rows)<=512)
        seen=set()
        for row in rows:
            exact(row,{'request','packet'});request=command(row['request']);value=row['packet']
            need(request['commandId'] not in seen);seen.add(request['commandId'])
            (validate if request['action']==OBSERVE else receipt)(value,request,self.pid,value['capturedEpochMs']);self._advance(value)
            if request['action']==OBSERVE:continuity(self.last_observation,value);self.last_observation=deepcopy(value)
            self.last=deepcopy(value)
