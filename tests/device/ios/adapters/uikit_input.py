"""Actual UIKit dispatch/contact originals; quiescence is not weak retirement.

The source stores no text, key codes, coordinates or input descriptions. Its
native producer remains uncompiled; these pure readers do not execute UIKit.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import re
from adapters.native_feature_observation import exact,fresh,integer,need
from ios.adapters import tablet_web_source as native

VERSION=1
ACTION='feature-ios-uikit-input'
FILE=ACTION+'.json'
LIMIT=2097152
KINDS={'event','touch','press','view','window'}


def command(value):
    need(type(value) is dict and value.get('action')==ACTION)
    native.sources.command(dict(value,action=native.sources.ACTION));return value


def _identity(value):
    """A global source retains old genuine targets across fixture runs."""
    need(type(value) is dict and type(value.get('source')) is dict)
    root=value['source'].get('fixtureUrl');need(type(root) is str)
    found=re.fullmatch(r'https?://[^/]+/feature-fixture/v1/runs/([0-9a-f]{32})/',root);need(found)
    query=dict(schemaVersion=1,action=native.ACTION,commandId='ios-'+'0'*32,runId=found[1],fixtureUrl=root)
    native.command(query);native.identity(value,query);return value


def validate(value,query,pid,epoch=None,previous=None):
    command(query);exact(value,{'iosUIKitInputVersion','commandId','runId','fixtureUrl','instance','sequence','processId','clockDomain',
        'clockBefore','clockAfter','complete','installed','applicationClass','installation','failure','dispatchSequence',
        'pendingDispatches','objects','targets','contacts','dispatches'})
    need(type(value['iosUIKitInputVersion']) is int and value['iosUIKitInputVersion']==VERSION
        and all(value[k]==query[k] for k in ('commandId','runId','fixtureUrl')) and integer(pid,1)
        and type(value['processId']) is int and value['processId']==pid and integer(value['sequence'],1)
        and value['clockDomain']=='native-main-ios-uikit-input' and type(value['complete']) is bool and type(value['installed']) is bool
        and type(value['applicationClass']) is str and len(value['applicationClass'])<=256
        and (value['failure'] is None or type(value['failure']) is str and 0<len(value['failure'])<=128)
        and integer(value['dispatchSequence']) and len(json.dumps(value,ensure_ascii=False,separators=(',',':')).encode())<=LIMIT)
    native.sources.identifier(value['instance']);a,b=value['clockBefore'],value['clockAfter'];native.sources.stamp(a);native.sources.stamp(b,floor=a)
    need(max(b['epochMs']-a['epochMs'],b['monotonicMs']-a['monotonicMs'])<1500)
    if epoch is not None:fresh(b['epochMs'],epoch)
    if value['installation'] is not None:native.sources.stamp(value['installation'],a)
    if value['complete']:need(value['installed'] and value['installation'] is not None and value['failure'] is None and value['applicationClass'])
    objects={};targets={};contacts={};dispatches={};pending=[]
    for collection,limit in (('objects',8192),('targets',1024),('contacts',8192),('dispatches',4096),('pendingDispatches',4096)):
        need(type(value[collection]) is list and len(value[collection])<=limit)
    for row in value['objects']:
        exact(row,{'id','kind','born','expired','alive'});native.sources.identifier(row['id'])
        need(row['id'] not in objects and row['kind'] in KINDS and type(row['alive']) is bool)
        native.sources.stamp(row['born'],b,value['installation']);objects[row['id']]=row
        if row['expired'] is not None:native.sources.stamp(row['expired'],b,row['born']);need(not row['alive'])
        else:need(row['alive'])
    def object_(identifier,kind,nullable=False):
        if nullable and identifier is None:return None
        native.sources.identifier(identifier);need(identifier in objects and objects[identifier]['kind'] in kind);return objects[identifier]
    for row in value['targets']:
        exact(row,{'view','identity','bound'});obj=object_(row['view'],{'view'});need(row['view'] not in targets)
        _identity(row['identity']);native.sources.stamp(row['bound'],a,obj['born']);targets[row['view']]=row
    def source_(source,target,window):
        object_(target,{'view','window'},True);object_(window,{'window'},True)
        if source is None:return
        exact(source,{'view','identity','bound','ancestry'});need(source['view'] in targets and {k:v for k,v in source.items() if k!='ancestry'}==targets[source['view']]
            and type(source['ancestry']) is list and 1<=len(source['ancestry'])<=128
            and all(type(id_) is str for id_ in source['ancestry']) and len(source['ancestry'])==len(set(source['ancestry'])) and source['ancestry'][0]==target and source['ancestry'][-1]==source['view'])
        for id_ in source['ancestry']:object_(id_,{'view'})
    for row in value['contacts']:
        exact(row,{'id','kind','object','target','window','source','began','ended','phase','active'})
        native.sources.identifier(row['id']);need(row['id'] not in contacts and row['kind'] in ('touch','press')
            and integer(row['phase'],0,4) and type(row['active']) is bool)
        obj=object_(row['object'],{row['kind']});source_(row['source'],row['target'],row['window'])
        native.sources.stamp(row['began'],a,obj['born'])
        if row['ended'] is None:need(row['active'] and row['phase']<3)
        else:native.sources.stamp(row['ended'],a,row['began']);need(not row['active'] and row['phase'] in (3,4))
        contacts[row['id']]=row
    seen={};active_objects=set();last_entered=value['installation'];used={}
    for index,row in enumerate(value['dispatches'],1):
        exact(row,{'sequence','event','entered','returned','finally','phases'})
        need(type(row['sequence']) is int and row['sequence']==index);obj=object_(row['event'],{'event'})
        native.sources.stamp(row['entered'],a,obj['born']);native.sources.stamp(row['entered'],floor=last_entered);last_entered=row['entered'];need(type(row['phases']) is list and len(row['phases'])<=8192)
        if row['returned'] is not None:native.sources.stamp(row['returned'],b,row['entered']);need(row['finally'] is not None)
        if row['finally'] is not None:native.sources.stamp(row['finally'],b,row['returned'] or row['entered'])
        else:pending.append(index)
        within=row['returned'] or row['finally'] or b
        last_use=row['finally'] or row['entered']
        if row['event'] not in used or last_use['epochMs']>=used[row['event']]['epochMs']:used[row['event']]=last_use
        for phase in row['phases']:
            exact(phase,{'object','contact','kind','phase','target','window','source'})
            need(phase['kind'] in ('touch','press') and integer(phase['phase'],0,4));object_(phase['object'],{phase['kind']})
            source_(phase['source'],phase['target'],phase['window'])
            if phase['contact'] is None:need(not value['complete']);continue
            native.sources.identifier(phase['contact']);need(phase['contact'] in contacts);original_=contacts[phase['contact']]
            need(all(phase[key]==original_[key] for key in ('object','kind','target','window','source')))
            if phase['phase']==0:
                need(phase['contact'] not in seen and phase['object'] not in active_objects)
                native.sources.stamp(original_['began'],within,row['entered']);active_objects.add(phase['object'])
            else:need(phase['contact'] in seen and seen[phase['contact']]<3 and phase['object'] in active_objects)
            if phase['phase']>=3:
                need(original_['ended'] is not None);native.sources.stamp(original_['ended'],within,row['entered']);active_objects.remove(phase['object'])
            seen[phase['contact']]=phase['phase'];used[phase['object']]=original_['ended'] or original_['began']
        dispatches[index]=row
    for id_,last in used.items():
        if objects[id_]['expired'] is not None:native.sources.stamp(objects[id_]['expired'],floor=last)
    need(value['dispatchSequence']==len(dispatches) and set(seen)==set(contacts)
        and all(row['phase']==seen[id_] for id_,row in contacts.items())
        and all(integer(entry,1,value['dispatchSequence']) for entry in value['pendingDispatches'])
        and len(value['pendingDispatches'])==len(set(value['pendingDispatches']))
        and set(value['pendingDispatches'])==set(pending))
    if previous is not None:
        validate(previous,dict(query,commandId=previous['commandId']),pid)
        need(all(value[k]==previous[k] for k in ('instance','processId','applicationClass','installation','installed'))
            and value['sequence']>previous['sequence'] and value['commandId']!=previous['commandId']
            and (previous['complete'] or not value['complete']) and (previous['failure'] is None or value['failure']==previous['failure']))
        native.sources.stamp(a,floor=previous['clockAfter'])
        for collection in ('objects','targets','contacts','dispatches'):
            need(len(value[collection])>=len(previous[collection]))
            for old,new in zip(previous[collection],value[collection]):
                mutable={'expired','alive'} if collection=='objects' else {'phase','active','ended'} if collection=='contacts' else {'returned','finally'} if collection=='dispatches' else set()
                need(all(new[k]==old[k] for k in old if k not in mutable))
                for key in mutable-{'alive','active','phase'}:
                    if old[key] is not None:need(new[key]==old[key])
                    elif new[key] is not None:native.sources.stamp(new[key],floor=previous['clockAfter'])
                if collection=='objects' and not old['alive']:need(not new['alive'])
                if collection=='contacts' and not old['active']:need(new==old)
            first={'objects':'born','targets':'bound','contacts':'began','dispatches':'entered'}[collection]
            for new in value[collection][len(previous[collection]):]:native.sources.stamp(new[first],floor=previous['clockAfter'])
    return value


def original(value):
    return validate(value,dict(schemaVersion=1,action=ACTION,commandId=value['commandId'],runId=value['runId'],fixtureUrl=value['fixtureUrl']),value['processId'])


def join_sources(value,sources,transcript):
    """Exact actual WK creation/source association; independent clock origins."""
    original(value);native.join_sources(transcript,sources)
    need(value['complete'] and all(value[k]==sources[k]==transcript[k] for k in ('runId','fixtureUrl','processId')))
    for target in value['targets']:
        if target['identity']['source']['fixtureUrl']!=value['fixtureUrl']:continue
        matches=[event for event in transcript['events'] if event['kind']=='view-created' and event['identity']==target['identity']]
        need(len(matches)==1 and matches[0]['clock']['epochMs']<=target['bound']['epochMs']<=value['clockBefore']['epochMs'])
    return deepcopy(value)


def quiescent(before,current,*,after_epoch,require_delivery=False,kind='touch'):
    """Actual ended contacts and returned dispatches, never cached object death."""
    original(before);validate(current,dict(schemaVersion=1,action=ACTION,commandId=current['commandId'],runId=current['runId'],fixtureUrl=current['fixtureUrl']),current['processId'],previous=before)
    need(type(require_delivery) is bool and kind in ('touch','press') and integer(after_epoch,1)
        and before['complete'] and current['complete'] and current['clockBefore']['epochMs']>=after_epoch
        and not current['pendingDispatches'] and all(not row['active'] for row in current['contacts'])
        and all(row['returned'] is not None and row['finally'] is not None for row in current['dispatches']))
    if require_delivery:
        old={row['id'] for row in before['contacts']}
        need(any(row['id'] not in old and row['kind']==kind and row['began']['epochMs']>=after_epoch and row['ended'] is not None for row in current['contacts']))
    return deepcopy(current)


def retired(admitted,current):
    """Positive zeroing-weak death of observed owned views/events/contacts."""
    quiescent(admitted,current,after_epoch=admitted['clockAfter']['epochMs'])
    own={row['view'] for row in current['targets'] if row['identity']['source']['fixtureUrl']==current['fixtureUrl']}
    need(own);contacts={row['id'] for row in current['contacts'] if row['source'] is not None and row['source']['view'] in own}
    objects=set(own)
    for row in current['contacts']:
        if row['id'] in contacts:objects.add(row['object']);objects.update(row['source']['ancestry'])
    for row in current['dispatches']:
        if any(phase['contact'] in contacts for phase in row['phases']):objects.add(row['event'])
    rows={row['id']:row for row in current['objects']}
    need(all(not rows[id_]['alive'] and rows[id_]['expired'] is not None for id_ in objects))
    return sorted(objects)


class IOSUIKitInput(native.IOSTabletWebSource):
    _action=ACTION
    _command=staticmethod(command)
    _validate=staticmethod(validate)
    _limit=LIMIT
