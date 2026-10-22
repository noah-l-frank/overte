"""Passive actual Model/Geometry/material/resource originals for Pico Create."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import re
from adapters.native_feature_observation import exact,fresh,integer,need
from adapters.pico4.create_callbacks import NativeCreateCallbacks
from adapters.pico4.create_entities import entity_id
from adapters.token_create_ui import nonce

FILE='feature-create-models.json'
ACTION='feature-create-models-observe'


def digest(value):return type(value) is str and re.fullmatch('[0-9a-f]{64}',value)


def validate(value,request,pid,epoch,run):
    exact(value,{'schemaVersion','requestId','instance','sequence','requestedEpochMs','capturedEpochMs','processId','source'})
    need(type(value['schemaVersion']) is int and value['schemaVersion']==1 and nonce(request) and value['requestId']==request
        and nonce(value['instance']) and integer(value['sequence'],1) and integer(pid,1) and value['processId']==pid
        and integer(value['processId'],1) and integer(value['requestedEpochMs'],1)
        and integer(value['capturedEpochMs'],value['requestedEpochMs']) and value['capturedEpochMs']-value['requestedEpochMs']<2500)
    fresh(value['capturedEpochMs'],epoch)
    source=value['source'];exact(source,{'createModelResourcesVersion','runId','domainSession','bindings','models','geometries','materials','resources'})
    need(type(source['createModelResourcesVersion']) is int and source['createModelResourcesVersion']==1
        and type(run) is str and re.fullmatch('[0-9a-f]{32}',run) and source['runId']==run)
    session=source['domainSession'];exact(session,{'domainSessionVersion','instance','revision','connected','domainSha256','connectionBirth','connectedEpochMs'})
    need(type(session['domainSessionVersion']) is int and session['domainSessionVersion']==1 and nonce(session['instance'])
        and integer(session['revision']) and type(session['connected']) is bool
        and (session['domainSha256']=='' or digest(session['domainSha256'])))
    if session['connected']:
        need(session['revision']>=1 and nonce(session['connectionBirth']) and digest(session['domainSha256'])
            and integer(session['connectedEpochMs'],1,value['capturedEpochMs']))
    else:need(session['connectionBirth']=='' and type(session['connectedEpochMs']) is int and session['connectedEpochMs']==0)
    maps={}
    for key,maximum in (('models',64),('geometries',64),('materials',128),('resources',64)):
        rows=source[key];need(type(rows) is list and len(rows)<=maximum);ids=[];maps[key]={}
        for row in rows:
            exact(row,{'instance','firstObservedEpochMs','alive'}|({'state','sharedAvailable'} if key=='resources' else set()))
            need(nonce(row['instance']) and integer(row['firstObservedEpochMs'],1,value['capturedEpochMs']) and type(row['alive']) is bool)
            if key=='resources':
                need(type(row['sharedAvailable']) is bool and (not row['sharedAvailable'] or row['alive']))
                if row['sharedAvailable']:
                    state=row['state'];exact(state,{'url','loaded','failed'})
                    need(type(state['url']) is str and 0<len(state['url'])<=4096 and not any(ord(c)<32 for c in state['url'])
                        and type(state['loaded']) is bool and type(state['failed']) is bool)
                else:need(row['state'] is None)
            ids.append(row['instance']);maps[key][row['instance']]=row
        need(ids==sorted(set(ids)))
    need(type(source['bindings']) is list and len(source['bindings'])<=32);ids=[]
    for row in source['bindings']:
        need(type(row) is dict);model=row.get('model')
        exact(row,{'entityId','model'}|({'geometry','loaded','loadedSourceSha256','textures'} if model is not None else set()))
        need(entity_id(row['entityId']));ids.append(row['entityId'])
        if model is None:continue
        need(nonce(model) and model in maps['models'] and maps['models'][model]['alive'] and type(row['loaded']) is bool
            and (row['geometry'] is None or nonce(row['geometry']) and row['geometry'] in maps['geometries'] and maps['geometries'][row['geometry']]['alive'])
            and (row['loadedSourceSha256']=='' or digest(row['loadedSourceSha256']))
            and type(row['textures']) is list and len(row['textures'])<=128)
        if row['loaded']:need(row['geometry'] is not None and digest(row['loadedSourceSha256']))
        if row['geometry'] is None:need(not row['textures'] and row['loadedSourceSha256']=='')
        order=[];material_indices={}
        for texture in row['textures']:
            exact(texture,{'material','materialIndex','channel','slot','resource'})
            need(nonce(texture['material']) and texture['material'] in maps['materials'] and maps['materials'][texture['material']]['alive']
                and integer(texture['materialIndex'],0,63) and integer(texture['channel'],0,31) and type(texture['slot']) is str and 0<len(texture['slot'])<=256
                and not any(ord(c)<32 for c in texture['slot']) and nonce(texture['resource'])
                and texture['resource'] in maps['resources'] and maps['resources'][texture['resource']]['alive'])
            order.append((texture['materialIndex'],texture['channel']))
            need(material_indices.setdefault(texture['materialIndex'],texture['material'])==texture['material'])
        need(order==sorted(set(order)))
    need(ids==sorted(set(ids)))
    return value


def continuity(previous,value):
    if previous is None:return
    need(value['instance']==previous['instance'] and value['sequence']>previous['sequence']
        and value['capturedEpochMs']>=previous['capturedEpochMs'])
    a=previous['source'];b=value['source']
    need(all(a[k]==b[k] for k in ('createModelResourcesVersion','runId','domainSession')))
    for key in ('models','geometries','materials','resources'):
        rows={r['instance']:r for r in b[key]}
        for original in a[key]:
            need(original['instance'] in rows);current=rows[original['instance']]
            need(current['firstObservedEpochMs']==original['firstObservedEpochMs'] and (original['alive'] or not current['alive']))
    need({r['entityId'] for r in a['bindings']}<={r['entityId'] for r in b['bindings']})


def retired(source):
    return all(row['model'] is None for row in source['bindings']) and all(not row['alive']
        for key in ('models','geometries','materials','resources') for row in source[key])


class NativeCreateModelResources(NativeCreateCallbacks):
    action=ACTION
    continuity=staticmethod(continuity)
    def __init__(self,*args,run,**kwargs):
        need(type(run) is str and re.fullmatch('[0-9a-f]{32}',run));self.run=run
        super().__init__(*args,**kwargs)
    def command(self,request):return super().command(request)|{'runId':self.run}
    def validate(self,value,request,pid,epoch):return validate(value,request,pid,epoch,self.run)
