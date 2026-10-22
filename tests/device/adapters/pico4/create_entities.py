"""Actual bounded domain entity reads for the owned Create picker flow."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import re
import hashlib
import uuid
from adapters.native_feature_observation import exact,fresh,integer,need,number
from adapters.pico4.create_callbacks import NativeCreateCallbacks
from adapters.token_create_ui import nonce,UUID

FILE='feature-create-entities.json'
ACTION='feature-create-entities-observe'


def entity_id(value):return type(value) is str and re.fullmatch(UUID,value) and nonce(value)


def vector(value,length):
    need(type(value) is list and len(value)==length and all(number(v) for v in value))


def validate(value,request,pid,epoch,run):
    exact(value,{'schemaVersion','requestId','instance','sequence','requestedEpochMs','capturedEpochMs','processId','source'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and nonce(request) and value['requestId']==request
        and nonce(value['instance']) and integer(value['sequence'],1) and integer(pid,1)
        and integer(value['processId'],1) and value['processId']==pid and integer(value['requestedEpochMs'],1)
        and integer(value['capturedEpochMs'],value['requestedEpochMs'])
        and value['capturedEpochMs']-value['requestedEpochMs']<5000)
    fresh(value['capturedEpochMs'],epoch)
    source=value['source'];version=source.get('createEntitySourceVersion');exact(source,{'createEntitySourceVersion','runId','domainConnected','domainId','sessionId',
        'canRez','canRezTmp','entities','absentIds','scan'} | ({'domainSession'} if version in (2,3) else set())|({'entityLifetimes'} if version==3 else set()))
    need(type(source['createEntitySourceVersion']) is int and source['createEntitySourceVersion'] in (1,2,3)
        and type(run) is str and re.fullmatch('[0-9a-f]{32}',run) and source['runId']==run
        and all(type(source[k]) is bool for k in ('domainConnected','canRez','canRezTmp'))
        and all(source[k] is None or entity_id(source[k]) for k in ('domainId','sessionId'))
        and type(source['entities']) is list and type(source['absentIds']) is list
        and len(source['entities'])+len(source['absentIds'])<=32)
    if version in (2,3):
        session=source['domainSession'];exact(session,{'domainSessionVersion','instance','revision','connected','domainSha256','connectionBirth','connectedEpochMs'})
        need(type(session['domainSessionVersion']) is int and session['domainSessionVersion']==1 and nonce(session['instance'])
            and integer(session['revision']) and type(session['connected']) is bool and session['connected']==source['domainConnected']
            and type(session['domainSha256']) is str and (session['domainSha256']=='' if source['domainId'] is None else
                session['domainSha256']==hashlib.sha256((run+':').encode()+uuid.UUID(source['domainId']).bytes).hexdigest()))
        if session['connected']:
            need(session['revision']>=1 and type(session['connectionBirth']) is str and re.fullmatch('[0-9a-f]{32}',session['connectionBirth'])
                and integer(session['connectedEpochMs'],1,value['capturedEpochMs']) and source['domainId'] is not None)
        else:need(session['connectionBirth']=='' and session['connectedEpochMs']==0 and type(session['connectedEpochMs']) is int)
    ids=[]
    for row in source['entities']:
        exact(row,{'id','name','type','hostType','modelUrl','textures','position','rotation','dimensions','parentId','visible','locked','lastEditedEpochUs'}|({'visuallyReady','naturalDimensions','textureNames','renderInfo'} if version==3 else set()))
        need(entity_id(row['id']) and row['hostType'] in ('domain','avatar','local')
            and all(type(row[k]) is str and len(row[k])<=limit and not any(ord(c)<32 for c in row[k])
                for k,limit in (('name',256),('type',64),('modelUrl',4096),('textures',8192))))
        need(row['parentId'] is None or entity_id(row['parentId']))
        need(type(row['visible']) is bool and type(row['locked']) is bool and integer(row['lastEditedEpochUs'],1))
        for key in ('position','dimensions'):vector(row[key],3)
        vector(row['rotation'],4);need(all(v>=0 for v in row['dimensions']));ids.append(row['id'])
        if version==3:
            need(type(row['visuallyReady']) is bool);vector(row['naturalDimensions'],3)
            need(all(v>=0 for v in row['naturalDimensions']) and type(row['textureNames']) is dict and len(row['textureNames'])<=64)
            need(all(type(k) is str and 0<len(k)<=256 and not any(ord(c)<32 for c in k)
                and type(v) is str and len(v)<=4096 and not any(ord(c)<32 for c in v) for k,v in row['textureNames'].items()))
            exact(row['renderInfo'],{'vertices','textures','textureBytes','drawCalls'})
            need(all(integer(row['renderInfo'][k],0,1_000_000_000) for k in ('vertices','textures','drawCalls'))
                and integer(row['renderInfo']['textureBytes'],0,2**53-1))
    absent=source['absentIds'];need(ids==sorted(set(ids)) and absent==sorted(set(absent))
        and all(entity_id(v) for v in absent) and not set(ids)&set(absent))
    if version==3:
        need(type(source['entityLifetimes']) is list and len(source['entityLifetimes'])==len(ids)+len(absent))
        seen=[];births=set()
        for row in source['entityLifetimes']:
            exact(row,{'id','instance','firstObservedEpochMs','alive','inTree'})
            need(entity_id(row['id']) and nonce(row['instance']) and row['instance'] not in births
                and integer(row['firstObservedEpochMs'],1,value['capturedEpochMs'])
                and type(row['alive']) is bool and type(row['inTree']) is bool
                and row['inTree']==(row['id'] in ids) and (not row['inTree'] or row['alive']))
            seen.append(row['id']);births.add(row['instance'])
        need(seen==sorted(set(ids)|set(absent)))
    scan=source['scan'];exact(scan,{'center','radiusMeters','propertyScope','scannedEntities','unowned'});vector(scan['center'],3)
    need(scan['radiusMeters']==128 and type(scan['radiusMeters']) is int and scan['propertyScope']=='create-domain-v1'
        and integer(scan['scannedEntities'],0,1024) and type(scan['unowned']) is list and len(scan['unowned'])<=1024)
    foreign=[]
    for row in scan['unowned']:
        exact(row,{'id','sha256'});need(entity_id(row['id']) and type(row['sha256']) is str and re.fullmatch('[0-9a-f]{64}',row['sha256']))
        foreign.append(row['id'])
    need(foreign==sorted(set(foreign)) and not set(foreign)&(set(ids)|set(absent)))
    return value


def continuity(previous,value):
    if previous is None:return
    need(value['instance']==previous['instance'] and value['sequence']>previous['sequence']
        and value['capturedEpochMs']>=previous['capturedEpochMs'])
    a=previous['source'];b=value['source']
    need(all(a[k]==b[k] for k in ('createEntitySourceVersion','runId','domainId','sessionId','domainConnected')))
    if a['createEntitySourceVersion'] in (2,3):need(a['domainSession']==b['domainSession'])
    if a['createEntitySourceVersion']==3:
        current={r['id']:r for r in b['entityLifetimes']}
        for row in a['entityLifetimes']:
            need(row['id'] in current and all(row[k]==current[row['id']][k] for k in ('id','instance','firstObservedEpochMs'))
                and (row['alive'] or not current[row['id']]['alive']))
    tracked=lambda source:set(source['absentIds'])|{r['id'] for r in source['entities']}
    need(tracked(a)<=tracked(b))
    old={r['id']:r for r in a['entities']}
    for row in b['entities']:
        if row['id'] in old:need(row['lastEditedEpochUs']>=old[row['id']]['lastEditedEpochUs'])


def retired(source):
    return source['createEntitySourceVersion']==3 and not source['entities'] and all(not row['alive'] for row in source['entityLifetimes'])


class NativeCreateEntities(NativeCreateCallbacks):
    action=ACTION
    continuity=staticmethod(continuity)
    def __init__(self,*args,run,**kwargs):
        need(type(run) is str and re.fullmatch('[0-9a-f]{32}',run));self.run=run
        super().__init__(*args,**kwargs)
    def command(self,request):return super().command(request)|{'runId':self.run}
    def validate(self,value,request,pid,epoch):return validate(value,request,pid,epoch,self.run)
