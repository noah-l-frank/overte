"""Original Phone Navigation marker inventory; fixture input is never product evidence."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import math

from adapters.native_avatar_render import _OriginalQuery,envelope,nonce,validate as avatar_packet
from adapters.native_feature_observation import exact,integer,need,number
from adapters.native_graphics_subject import vector,rotation,entity_id
from adapters.native_phone_web_runtime import command as web_command
from adapters.world_render_evidence import recorded_view
from feature_journeys.contract import identifier

VERSION=1
FILE='phone-navigation-marker.json'
INPUT_FILE=FILE
NULL_ID='00000000-0000-0000-0000-000000000000'
VIEW={'position','rotation','projection','fieldOfViewDegrees','aspectRatio','nearClip','farClip','perspective'}


def command(value):
    exact(value,{'schemaVersion','commandId','action','runId'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and nonce(value['commandId'])
        and value['action']=='phone-navigation-marker-observe');identifier(value['runId']);return value


def input_command(value):
    need(type(value) is dict and value.get('operation') in ('prepare','release'))
    operation=value['operation']
    fields={'schemaVersion','commandId','action','operation','runId'}
    exact(value,fields|({'fixtureUrl','ticket','imageExtent','markerRoi'} if operation=='prepare' else {'fixtureInstance'}))
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and nonce(value['commandId'])
        and value['action']=='phone-navigation-marker-input');identifier(value['runId'])
    if operation=='prepare':
        identifier(value['ticket']);web_command(dict(schemaVersion=1,commandId=value['commandId'],
            action='feature-phone-web-runtime-observe',runId=value['runId'],fixtureUrl=value['fixtureUrl']))
        extent=value['imageExtent'];roi=value['markerRoi']
        need(type(extent) is list and len(extent)==2 and all(integer(v,240,16384) for v in extent)
            and type(roi) is list and len(roi)==4 and all(integer(v,0,16384) for v in roi))
        x0,y0,x1,y1=roi;w,h=extent
        need(x0<x1<=w and y0<y1<=h and x1-x0>=160 and y1-y0>=40 and (x1-x0)*(y1-y0)<=.1*w*h)
    else:need(nonce(value['fixtureInstance']))
    return value


def input_receipt(value,request):
    input_command(request)
    exact(value,{'phoneNavigationMarkerInputVersion','commandId','runId','fixtureInstance','operation','recorded'})
    need(type(value['phoneNavigationMarkerInputVersion']) is int and value['phoneNavigationMarkerInputVersion']==VERSION
        and value['commandId']==request['commandId'] and value['runId']==request['runId']
        and nonce(value['fixtureInstance']) and value['operation']==request['operation'] and value['recorded'] is True
        and (request['operation']=='prepare' or value['fixtureInstance']==request['fixtureInstance']))
    return value # Input receipt only, with no readiness or cleanup assertion.


def original_view(value):
    exact(value,VIEW|{'feetPosition','modelScale','boomLength','mode'})
    recorded_view({key:value[key] for key in VIEW});vector(value['feetPosition'],3,-1e6,1e6)
    need(number(value['modelScale'],.0001,1000) and number(value['boomLength'],0,10000) and type(value['mode']) is str)


def validate(value,request,pid,epoch):
    command(request);envelope(value,request,pid,epoch);source=value['source']
    exact(source,{'phoneNavigationMarkerVersion','fixtureInstance','runId','phase','createdEpochMs','originalInput',
        'originalView','objects','entities','absentIds','retainedObjects'})
    need(type(source['phoneNavigationMarkerVersion']) is int and source['phoneNavigationMarkerVersion']==VERSION
        and nonce(source['fixtureInstance']) and source['runId']==request['runId']
        and source['phase'] in ('creating','active','failed','releasing','drained')
        and integer(source['createdEpochMs'],1,value['capturedEpochMs']))
    input_command(source['originalInput']);need(source['originalInput']['operation']=='prepare'
        and source['originalInput']['runId']==source['runId'])
    original_view(source['originalView']);need(abs(source['originalInput']['imageExtent'][0]/source['originalInput']['imageExtent'][1]
        -source['originalView']['aspectRatio'])<=.005)
    objects=source['objects'];need(type(objects) is list and 0<len(objects)<=1)
    ids=[]
    for index,item in enumerate(objects):
        exact(item,{'role','id'});need(item['role']=='marker'
            and (item['id'] is None or entity_id(item['id']) and item['id']!=NULL_ID))
        if item['id'] is not None:ids.append(item['id'])
    need(len(set(ids))==len(ids) and integer(source['retainedObjects'],0,len(ids)))
    rows=source['entities'];absent=source['absentIds']
    need(type(rows) is list and len(rows)<=1 and type(absent) is list and len(absent)<=1)
    seen=[]
    for row in rows:
        exact(row,{'id','role','originalObject','name','type','parentId','hostType','position','rotation','dimensions','color','visible',
            'sourceUrl','locked','collisionless','canCastShadow','dpi','lastEditedEpochUs'})
        need(row['id'] in ids and row['id'] not in seen and any(item['id']==row['id'] and item['role']==row['role'] for item in objects)
            and type(row['originalObject']) is bool and entity_id(row['parentId']) and row['hostType'] in ('local','foreign')
            and type(row['name']) is str and len(row['name'])<=256 and '\0' not in row['name']
            and type(row['type']) is str and 0<len(row['type'])<=64 and '\0' not in row['type']
            and type(row['sourceUrl']) is str and len(row['sourceUrl'])<=2048 and '\0' not in row['sourceUrl']
            and all(type(row[key]) is bool for key in ('visible','locked','collisionless','canCastShadow'))
            and integer(row['dpi'],0,65535) and integer(row['lastEditedEpochUs'],0,9007199254740991))
        vector(row['position'],3,-1e6,1e6);rotation(row['rotation']);vector(row['dimensions'],3,0,1e6)
        need(type(row['color']) is list and len(row['color'])==3 and all(integer(c,0,255) for c in row['color']))
        seen.append(row['id'])
    need(all(id in ids and id not in seen for id in absent) and len(set(absent))==len(absent) and set(seen+absent)==set(ids))
    if source['phase']=='active':need(len(ids)==len(objects)==1)
    if source['phase']=='drained':need(not rows and source['retainedObjects']==0)
    return value


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


def layout(source):
    """Expected fixture geometry from original native setup view, not observations."""
    original_view(source['originalView']);input_command(source['originalInput'])
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


def near(actual,wanted,tolerance):
    if type(wanted) in (int,float):return number(actual,-1e9,1e9) and abs(actual-wanted)<=tolerance
    if type(wanted) is list:return type(actual) is list and len(actual)==len(wanted) and all(near(a,b,tolerance) for a,b in zip(actual,wanted))
    return type(actual) is type(wanted) and actual==wanted


def rotation_equal(a,b,tolerance):return near(a,b,tolerance) or near(a,[-v for v in b],tolerance)


def continuation(previous,value):
    old,new=previous['source'],value['source']
    need(all(old[key]==new[key] for key in ('fixtureInstance','runId','createdEpochMs','originalInput','originalView','objects')))
    allowed={'creating':{'creating','active','failed','releasing','drained'},'active':{'active','releasing','drained'},
        'failed':{'failed','releasing','drained'},'releasing':{'releasing','drained'},'drained':{'drained'}}
    need(new['phase'] in allowed[old['phase']])


def ready(value,avatar):
    """Separate original resource/view readiness; no pixels or input/Rig verdict."""
    validate(value,dict(schemaVersion=1,commandId=value.get('requestId'),action='phone-navigation-marker-observe',
        runId=value.get('source',{}).get('runId')),value.get('processId'),value.get('capturedEpochMs'))
    avatar_packet(avatar,dict(schemaVersion=1,commandId=avatar.get('requestId'),action='feature-avatar-render-observe'),
        value['processId'],avatar.get('capturedEpochMs'))
    source=value['source'];view=source['originalView'];current=avatar['source'];wanted=layout(source)
    need(source['phase']=='active' and value['instance']==avatar['instance'] and source['retainedObjects']==1
        and len(source['entities'])==1 and not source['absentIds'] and current['cameraMode']==view['mode']
        and near(current['pose']['feetPosition'],view['feetPosition'],.01) and near(current['pose']['modelScale'],view['modelScale'],.0001))
    for key in VIEW:need(near(current['view'][key],view[key],.0001))
    for row in source['entities']:
        name=row['role'];expected=wanted[name]
        need(row['originalObject'] and row['hostType']=='local' and row['parentId']==NULL_ID
            and row['type']==('Web' if name=='marker' else 'Box') and row['visible'] and not row['locked'] and row['collisionless'] and not row['canCastShadow']
            and row['name']=='e2e-'+source['runId']+'-navigation-'+name
            and near(row['position'],expected['position'],.001) and near(row['dimensions'],expected['dimensions'],.001)
            and rotation_equal(row['rotation'],expected['rotation'],.0001))
        if name=='marker':need(row['dpi']==100 and row['sourceUrl']==source['originalInput']['fixtureUrl']+'tickets/'
            +source['originalInput']['ticket']+'/graphics-marker.v1.html')
        else:need(row['color']==[128,128,128] and not row['sourceUrl'])
    return deepcopy(source['entities'])


def retired(value):
    source=value.get('source',{})
    validate(value,dict(schemaVersion=1,commandId=value.get('requestId'),action='phone-navigation-marker-observe',runId=source.get('runId')),
        value.get('processId'),value.get('capturedEpochMs'))
    need(source['phase']=='drained' and source['retainedObjects']==0 and not source['entities'])
    return deepcopy(source) # Web/Java callbacks and foreign-world preservation remain separate.


class NativePhoneNavigationMarker(_OriginalQuery):
    def read(self,run):
        need(self.ios is False);request=command(self._request('phone-navigation-marker-observe',runId=identifier(run)))
        def original(value,request,pid,epoch):
            validate(value,request,pid,epoch)
            if self.last is not None:continuation(self.last,value)
        return self._read(request,original)

    def restore(self,frames):
        need(self.ios is False and self.last is None and type(frames) is list and 0<len(frames)<=256)
        for value in frames:
            source=value.get('source',{})
            validate(value,dict(schemaVersion=1,commandId=value.get('requestId'),action='phone-navigation-marker-observe',runId=source.get('runId')),
                self.pid,value.get('capturedEpochMs'));self._advance(value)
            if self.last is not None:continuation(self.last,value)
            self.last=deepcopy(value)
