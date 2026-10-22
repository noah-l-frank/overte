"""Original returned Tablet app buttons, model membership and weak visuals.

A matching label or an acknowledged click is never a button identity or a Web
effect. The separate Script/VM owner must prove callback and worker drainage.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import re
import uuid
from adapters.native_feature_observation import exact,fresh,integer,need
from adapters.native_script_membership import validate as membership
from adapters.native_script_observation import validate_code
from ios.adapters import tablet_web_sources as sources
from ios.adapters.tablet_web_source import IOSTabletWebSource

VERSION=1
ACTION='feature-ios-tablet-app-buttons'
FILE=ACTION+'.json'
LIMIT=2097152
IDS=frozenset('tablet-web-app.'+verb for verb in ('open','inline','return'))
FIELDS=frozenset({'tabletAppButton'})
SEMANTIC=re.compile(r'tablet-web-app\.([0-9a-f]{32})\.([0-9a-f]{32})\.(open|inline|return)')


def command(value):
    need(type(value) is dict and value.get('action')==ACTION)
    sources.command(dict(value,action=sources.ACTION));return value


def caller(value,epoch):
    if value is None:return None
    exact(value,{'callerVersion','method','sequence','invokedEpochMs','manager','code'})
    need(type(value['callerVersion']) is int and value['callerVersion']==1 and value['method']=='addButton'
        and integer(value['sequence'],1,1_000_000_000) and integer(value['invokedEpochMs'],1,epoch))
    membership(dict(complete=True,revision=1,managers=[value['manager']]),value['invokedEpochMs'])
    validate_code(value['code'],value['invokedEpochMs'])
    need(value['manager']['assigned'] and value['code']['submitted'] and value['manager']['assignedEpochMs']<=value['code']['submittedEpochMs'])
    return value


def metadata(value):
    exact(value,{'instance','button','control','root','rootInstance','semanticId','uuid','featureRun','fixtureUrl','nonce','verb'})
    for key in ('instance','button','control','root','rootInstance','featureRun','nonce'):sources.identifier(value[key])
    need(value['verb'] in ('open','inline','return') and value['semanticId']=='tablet-web-app.'+value['featureRun']+'.'+value['nonce']+'.'+value['verb'])
    need(type(value['uuid']) is str)
    try:need(str(uuid.UUID(value['uuid']))==value['uuid'] and uuid.UUID(value['uuid']).int>0)
    except ValueError:need(False)
    sources.command(dict(schemaVersion=1,action=sources.ACTION,commandId='ios-'+'0'*32,runId=value['featureRun'],fixtureUrl=value['fixtureUrl']))
    return value


def control_id(value):return type(value) is str and value in IDS


def validate(value,query,pid,epoch=None,previous=None):
    command(query);exact(value,{'iosTabletAppButtonsVersion','commandId','runId','fixtureUrl','instance','sequence','processId',
        'clockDomain','clockBefore','clockAfter','complete','rootInstance','models','tablets','buttons','controls'})
    need(type(value['iosTabletAppButtonsVersion']) is int and value['iosTabletAppButtonsVersion']==VERSION
        and all(value[k]==query[k] for k in ('commandId','runId','fixtureUrl')) and integer(pid,1)
        and type(value['processId']) is int and value['processId']==pid and integer(value['sequence'],1)
        and value['clockDomain']=='native-main-ios-tablet-app-buttons' and type(value['complete']) is bool
        and len(json.dumps(value,ensure_ascii=False,separators=(',',':')).encode())<=LIMIT)
    for key in ('instance','rootInstance'):sources.identifier(value[key])
    a,b=value['clockBefore'],value['clockAfter'];sources.stamp(a);sources.stamp(b,floor=a)
    need(max(b['epochMs']-a['epochMs'],b['monotonicMs']-a['monotonicMs'])<1500)
    if epoch is not None:fresh(b['epochMs'],epoch)
    collections={}
    for key,limit in (('models',128),('tablets',128),('buttons',384),('controls',1024)):
        need(type(value[key]) is list and len(value[key])<=limit);collections[key]={}
        for row in value[key]:
            need(type(row) is dict);sources.identifier(row.get('id'));need(row['id'] not in collections[key]);collections[key][row['id']]=row
    def life(row,born):
        need(type(row['alive']) is bool);sources.stamp(row[born],b)
        if row['expired'] is None:need(row['alive'])
        else:sources.stamp(row['expired'],b,row[born]);need(not row['alive'])
    for key in ('models','tablets'):
        for row in value[key]:exact(row,{'id','born','expired','alive'});life(row,'born')
    semantic_ids=set()
    for row in value['buttons']:
        exact(row,{'id','uuid','semanticId','fixtureUrl','caller','model','tablet','root','inserted','returned','removed','expired','alive','clicks'})
        found=SEMANTIC.fullmatch(row['semanticId']) if type(row['semanticId']) is str else None
        need(found and row['fixtureUrl']==query['fixtureUrl'] and found[1]==query['runId'] and (row['semanticId'],row['uuid']) not in semantic_ids);semantic_ids.add((row['semanticId'],row['uuid']))
        need(type(row['uuid']) is str)
        try:need(str(uuid.UUID(row['uuid']))==row['uuid'] and uuid.UUID(row['uuid']).int>0)
        except ValueError:need(False)
        life(row,'inserted');caller(row['caller'],row['inserted']['epochMs'])
        need(row['model'] in collections['models']);sources.stamp(row['inserted'],floor=collections['models'][row['model']]['born'])
        if row['returned'] is None:need(row['tablet'] is None and row['root'] is None and not row['clicks'])
        else:
            need(row['tablet'] in collections['tablets']);sources.identifier(row['root'])
            sources.stamp(row['returned'],b,row['inserted']);sources.stamp(row['returned'],floor=collections['tablets'][row['tablet']]['born'])
        if row['removed'] is not None:sources.stamp(row['removed'],b,row['returned'] or row['inserted'])
        need(type(row['clicks']) is list and len(row['clicks'])<=512);last=row['returned']
        for click in row['clicks']:
            need(last is not None);sources.stamp(click,row['removed'] or row['expired'] or b,last);last=click
    for row in value['controls']:
        exact(row,{'id','button','root','born','expired','alive'});life(row,'born')
        need(row['button'] in collections['buttons']);button=collections['buttons'][row['button']]
        need(button['returned'] is not None and row['root']==button['root']);sources.stamp(row['born'],b,button['returned'])
    if previous is not None:
        validate(previous,dict(query,commandId=previous['commandId']),pid)
        need(all(value[key]==previous[key] for key in ('instance','rootInstance','processId')) and value['sequence']>previous['sequence']
            and value['commandId']!=previous['commandId'] and (previous['complete'] or not value['complete']))
        sources.stamp(a,floor=previous['clockAfter'])
        for key in collections:
            need(len(value[key])>=len(previous[key]))
            mutable={'expired','alive'}|({'returned','tablet','root','removed','clicks'} if key=='buttons' else set())
            for old,new in zip(previous[key],value[key]):
                need(all(new[k]==old[k] for k in old if k not in mutable))
                need(old['alive'] or not new['alive'])
                for name in mutable-{'alive','clicks','tablet','root'}:
                    if old[name] is not None:need(new[name]==old[name])
                    elif new[name] is not None:sources.stamp(new[name],floor=previous['clockAfter'])
                if key=='buttons':
                    if old['returned'] is not None:need(new['tablet']==old['tablet'] and new['root']==old['root'])
                    need(new['clicks'][:len(old['clicks'])]==old['clicks'])
                    for click in new['clicks'][len(old['clicks']):]:sources.stamp(click,floor=previous['clockAfter'])
            first='inserted' if key=='buttons' else 'born'
            for row in value[key][len(previous[key]):]:sources.stamp(row[first],floor=previous['clockAfter'])
    return value


def original(value):
    return validate(value,dict(schemaVersion=1,action=ACTION,commandId=value['commandId'],runId=value['runId'],fixtureUrl=value['fixtureUrl']),value['processId'])


def selected(value,control,profile):
    original(value);metadata(control);need(value['complete'] and control['instance']==value['instance'] and control['rootInstance']==value['rootInstance']
        and control['featureRun']==value['runId'] and control['fixtureUrl']==value['fixtureUrl'])
    rows=[row for row in value['buttons'] if row['id']==control['button']];need(len(rows)==1);button=rows[0]
    need(button['caller'] is not None and button['alive'] and button['returned'] is not None and button['removed'] is None
        and button['uuid']==control['uuid'] and button['semanticId']==control['semanticId'] and button['root']==control['root'])
    manager=button['caller']['manager'];need(manager['instance']==profile['engineInstance'] and manager['url']==profile['assignedUrl']
        and manager['loadGeneration']==profile['loadGeneration'] and manager['assignedEpochMs']==profile['assignedEpochMs'] and button['caller']['code']==profile['code'])
    need(any(row['id']==control['control'] and row['button']==button['id'] and row['root']==control['root'] and row['alive'] for row in value['controls']))
    return deepcopy(button)


def retired(before,current):
    original(before);validate(current,dict(schemaVersion=1,action=ACTION,commandId=current['commandId'],runId=current['runId'],fixtureUrl=current['fixtureUrl']),current['processId'],previous=before)
    need(before['complete'] and current['complete'])
    for row in current['buttons']:need(row['removed'] is not None and row['expired'] is not None and not row['alive'])
    for row in current['controls']:need(row['expired'] is not None and not row['alive'])
    # A shared live TabletProxy/model is not owned by this app Script. Only its
    # actual added proxy and bound visual controls must have weakly expired.
    return deepcopy(current)


class IOSTabletWebButtons(IOSTabletWebSource):
    _action=ACTION
    _command=staticmethod(command)
    _validate=staticmethod(validate)
    _limit=LIMIT
