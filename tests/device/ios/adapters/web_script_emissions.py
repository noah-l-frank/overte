"""Actual native Web emitter callers and real queued/sink receipt originals.

World and Tablet identities remain their genuine native schemas. No payload or
VM interval match creates a caller when its actual native context is missing.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import json
import re
from adapters.native_feature_observation import exact,fresh,integer,need
from adapters.native_script_membership import validate as membership
from adapters.native_script_observation import validate_code
from adapters.script_feature.history import same
from ios.adapters import tablet_web_source as tablet,world_web_source as world

VERSION=1
ACTION='feature-ios-web-script-emissions'
FILE=ACTION+'.json'
LIMIT=2097152
ROUTES={'tablet-proxy','tablet-surface','tablet-window','world-surface'}


def command(value):
    need(type(value) is dict and value.get('action')==ACTION);tablet.command(dict(value,action=tablet.ACTION));return value


def echo(value):
    if type(value) is str:
        need(len(value.encode())<=4096);raw=value.strip();need(raw.startswith('{') and raw.endswith('}'))
        parts=raw[1:-1].split(',');need(len(parts)==4);seen=set()
        pattern=r'[ \t\r\n]*"(contract|action|surface|sequence)"[ \t\r\n]*:[ \t\r\n]*("(?:overte-web-parity-v1|echo|tablet|world)"|[1-9][0-9]{0,6})[ \t\r\n]*'
        for part in parts:
            found=re.fullmatch(pattern,part);need(found is not None and found[1] not in seen);seen.add(found[1])
        value=json.loads(raw)
    exact(value,{'contract','action','sequence','surface'})
    need(value['contract']=='overte-web-parity-v1' and value['action']=='echo' and value['surface'] in ('tablet','world')
        and integer(value['sequence'],1,1000000));return value


def caller(value,epoch):
    if value is None:return None
    exact(value,{'callerVersion','method','sequence','invokedEpochMs','manager','code','emitStack'})
    need(type(value['callerVersion']) is int and value['callerVersion']==1 and value['method']=='emitScriptEvent'
        and integer(value['sequence'],1,1000000000) and integer(value['invokedEpochMs'],1,epoch))
    membership(dict(complete=True,revision=1,managers=[value['manager']]),value['invokedEpochMs']);validate_code(value['code'],value['invokedEpochMs'])
    need(value['manager']['assigned'] and value['code']['submitted'] and value['manager']['assignedEpochMs']<=value['code']['submittedEpochMs'])
    stack(value['emitStack'],epoch)
    return value


def stack(value,epoch):
    if value is None:return None
    exact(value,{'emitStackVersion','instance','complete','frames'})
    need(type(value['emitStackVersion']) is int and value['emitStackVersion']==1 and type(value['complete']) is bool
        and type(value['frames']) is list and len(value['frames'])<=32)
    tablet.sources.identifier(value['instance'])
    need(not value['complete'] or bool(value['frames']))
    for frame in value['frames']:
        exact(frame,{'scriptId','line','column','sourceUrlSha256','compiled','isEval','isConstructor'})
        need(all(type(frame[key]) is int and -1<=frame[key]<=2147483647 for key in ('scriptId','line','column'))
            and type(frame['sourceUrlSha256']) is str and re.fullmatch('[0-9a-f]{64}',frame['sourceUrlSha256'])
            and type(frame['isEval']) is bool and type(frame['isConstructor']) is bool)
        if frame['compiled'] is not None:
            code=frame['compiled'];exact(code,{'urlSha256','encoding','codeUnits','sha256','firstObservedEpochMs'})
            need(type(code['urlSha256']) is str and re.fullmatch('[0-9a-f]{64}',code['urlSha256']) and code['encoding']=='utf-16le-code-units'
                and integer(code['codeUnits'],0,4194304) and type(code['sha256']) is str and re.fullmatch('[0-9a-f]{64}',code['sha256'])
                and integer(code['firstObservedEpochMs'],1,epoch))
        if value['complete']:need(frame['compiled'] is not None and frame['compiled']['urlSha256']==frame['sourceUrlSha256'] and all(frame[key]>0 for key in ('scriptId','line','column')))
    return value


def validate(value,query,pid,epoch=None,previous=None):
    command(query)
    exact(value,{'iosWebScriptEmissionsVersion','commandId','runId','fixtureUrl','instance','sequence','processId','clockDomain',
        'clockBefore','clockAfter','complete','callSequence','queueSequence','sinkSequence','objects','calls','queues','sinks'})
    need(type(value['iosWebScriptEmissionsVersion']) is int and value['iosWebScriptEmissionsVersion']==VERSION
        and all(value[key]==query[key] for key in ('commandId','runId','fixtureUrl')) and integer(pid,1)
        and type(value['processId']) is int and value['processId']==pid and integer(value['sequence'],1)
        and value['clockDomain']=='native-process-ios-web-script-emissions' and type(value['complete']) is bool
        and len(json.dumps(value,ensure_ascii=False,separators=(',',':')).encode())<=LIMIT)
    tablet.sources.identifier(value['instance']);a,b=value['clockBefore'],value['clockAfter'];tablet.sources.stamp(a);tablet.sources.stamp(b,floor=a)
    need(max(b['epochMs']-a['epochMs'],b['monotonicMs']-a['monotonicMs'])<1500)
    if epoch is not None:fresh(b['epochMs'],epoch)
    ids=set();collections={}
    for key,limit in (('objects',1024),('calls',512),('queues',2048),('sinks',2048)):
        need(type(value[key]) is list and len(value[key])<=limit);rows={}
        for row in value[key]:
            need(type(row) is dict);tablet.sources.identifier(row.get('id'));need(row['id'] not in ids);ids.add(row['id']);rows[row['id']]=row
        collections[key]=rows
    objects,calls,queues,sinks=(collections[key] for key in ('objects','calls','queues','sinks'))
    for row in value['objects']:
        exact(row,{'id','born','expired','alive'});tablet.sources.stamp(row['born'],a);need(type(row['alive']) is bool)
        if row['expired'] is None:need(row['alive'])
        else:tablet.sources.stamp(row['expired'],b,row['born']);need(not row['alive'])
    def body(row,start):
        tablet.sources.stamp(row[start],a)
        if row['returned'] is not None:tablet.sources.stamp(row['returned'],a,row[start]);need(row['finally'] is not None)
        if row['finally'] is not None:tablet.sources.stamp(row['finally'],a,row['returned'] or row[start])
    ordinal=0;callers={};compiled_sources={};vm_stacks={}
    for row in value['calls']:
        exact(row,{'id','sequence','object','surface','target','message','caller','entered','returned','finally'})
        need(type(row['sequence']) is int and row['sequence']==ordinal+1 and row['object'] in objects and row['surface'] in ('tablet','world')
            and type(row['target']) is str and 0<len(row['target'].encode())<=512)
        if row['surface']=='world':need(re.fullmatch('[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}',row['target']))
        echo(row['message']);body(row,'entered');tablet.sources.stamp(row['entered'],floor=objects[row['object']]['born'])
        actual=caller(row['caller'],row['entered']['epochMs'])
        if actual is not None:
            key=actual['manager']['instance'];need(actual['sequence']>callers.get(key,0));callers[key]=actual['sequence']
            source=actual['emitStack']
            if source is not None:
                need(vm_stacks.get(key,source['instance'])==source['instance']);vm_stacks[key]=source['instance']
            for frame in source['frames'] if source is not None else []:
                if frame['compiled'] is None:continue
                compiled_key=(key,frame['scriptId']);need(same(compiled_sources.get(compiled_key,frame['compiled']),frame['compiled']))
                compiled_sources[compiled_key]=frame['compiled']
        ordinal=row['sequence']
    need(type(value['callSequence']) is int and value['callSequence']==ordinal)
    ordinal=0
    for row in value['queues']:
        exact(row,{'id','sequence','call','route','created','entered','returned','finally','captureAlive','expired'})
        need(type(row['sequence']) is int and row['sequence']==ordinal+1 and row['route'] in ROUTES
            and (row['call'] is None or row['call'] in calls) and type(row['captureAlive']) is bool)
        tablet.sources.stamp(row['created'],a)
        if row['call'] is not None:tablet.sources.stamp(row['created'],floor=calls[row['call']]['entered'])
        if row['entered'] is None:need(row['returned'] is row['finally'] is None)
        else:body(row,'entered');tablet.sources.stamp(row['entered'],floor=row['created'])
        if row['expired'] is None:need(row['captureAlive'])
        else:
            tablet.sources.stamp(row['expired'],b,row['finally'] or row['created']);need(not row['captureAlive'])
        ordinal=row['sequence']
    need(type(value['queueSequence']) is int and value['queueSequence']==ordinal and integer(value['sinkSequence']))
    ordinal=0
    for row in value['sinks']:
        exact(row,{'id','sequence','kind','call','identity','message','entered','returned','finally'})
        need(integer(row['sequence'],ordinal+1,value['sinkSequence']) and row['kind'] in ('script-event-slot','page-reply')
            and (row['call'] is None or row['call'] in calls));echo(row['message']);body(row,'entered')
        identity=row['identity'];need(type(identity) is dict)
        (tablet if identity.get('surface')=='tablet' else world).identity(identity,query)
        if row['call'] is not None:
            actual=calls[row['call']];tablet.sources.stamp(row['entered'],floor=actual['entered'])
            need(identity['surface']==('tablet' if actual['surface']=='tablet' else 'world-entity') and same(row['message'],actual['message']))
        ordinal=row['sequence']
    if previous is not None:
        validate(previous,dict(query,commandId=previous['commandId']),pid)
        need(value['instance']==previous['instance'] and value['sequence']>previous['sequence'] and value['commandId']!=previous['commandId']
            and (previous['complete'] or not value['complete']));tablet.sources.stamp(a,floor=previous['clockAfter'])
        for counter in ('callSequence','queueSequence','sinkSequence'):need(value[counter]>=previous[counter])
        for key in collections:
            need(len(value[key])>=len(previous[key]))
            mutable={'expired','alive'} if key=='objects' else {'entered','returned','finally','expired','captureAlive'} if key=='queues' else {'returned','finally'}
            for old,new in zip(previous[key],value[key]):
                need(all(same(new[field],old[field]) for field in old if field not in mutable))
                for field in mutable & {'entered','returned','finally','expired'}:
                    if old[field] is not None:need(same(new[field],old[field]))
                    elif new[field] is not None:tablet.sources.stamp(new[field],floor=previous['clockAfter'])
                alive='alive' if key=='objects' else 'captureAlive' if key=='queues' else None
                if alive:need(old[alive] or not new[alive])
                if key=='queues' and old['expired'] is not None:need(same(new,old))
            start={'objects':'born','calls':'entered','queues':'created','sinks':'entered'}[key]
            for row in value[key][len(previous[key]):]:tablet.sources.stamp(row[start],floor=previous['clockAfter'])
    return value


def original(value):
    return validate(value,dict(schemaVersion=1,action=ACTION,commandId=value['commandId'],runId=value['runId'],fixtureUrl=value['fixtureUrl']),value['processId'])


def selected_vm(value,sink,profile):
    """Join actual API/VM/root code only; this does not identify a JS closure."""
    original(value);need(value['complete'] and any(same(sink,row) for row in value['sinks']) and sink['call'] is not None
        and sink['returned'] is not None and sink['finally'] is not None)
    rows=[row for row in value['calls'] if row['id']==sink['call']];need(len(rows)==1);call=rows[0]
    actual=caller(call['caller'],call['entered']['epochMs']);need(actual is not None and call['returned'] is not None and call['finally'] is not None)
    manager=actual['manager'];need(manager['instance']==profile['engineInstance'] and manager['url']==profile['assignedUrl']
        and manager['loadGeneration']==profile['loadGeneration'] and manager['assignedEpochMs']==profile['assignedEpochMs'] and same(actual['code'],profile['code']))
    return deepcopy(call)


def selected(value,sink,profile,locations):
    """Require the whole real compiled stack and pinned call locations.

    locations must be derived from independent original compiled source bytes,
    including wrappers. URL hashes alone and Work callback intervals are not
    source identity. isEval/constructor paths are unavailable for this profile.
    """
    call=selected_vm(value,sink,profile);observed=call['caller']['emitStack']
    need(observed is not None and observed['complete'] and type(locations) is list and 0<len(locations)<=32 and len(locations)==len(observed['frames']))
    for actual,expected in zip(observed['frames'],locations):
        exact(expected,{'sourceUrlSha256','sha256','codeUnits','line','column'})
        need(not actual['isEval'] and not actual['isConstructor'] and expected['line']==actual['line'] and expected['column']==actual['column']
            and expected['sourceUrlSha256']==actual['sourceUrlSha256'] and expected['sha256']==actual['compiled']['sha256']
            and expected['codeUnits']==actual['compiled']['codeUnits'] and integer(expected['line'],1) and integer(expected['column'],1)
            and type(expected['codeUnits']) is int)
    return call


def settled(value,profile):
    original(value);need(value['complete']);owned=set()
    for call in value['calls']:
        actual=call['caller']
        if actual is None or actual['manager']['instance']!=profile['engineInstance']:continue
        need(actual['manager']['url']==profile['assignedUrl'] and actual['manager']['loadGeneration']==profile['loadGeneration']
            and actual['manager']['assignedEpochMs']==profile['assignedEpochMs'] and same(actual['code'],profile['code'])
            and call['returned'] is not None and call['finally'] is not None);owned.add(call['id'])
    for row in value['queues']:
        if row['call'] not in owned:continue
        need(not row['captureAlive'] and row['expired'] is not None
            and (row['entered'] is None or row['returned'] is not None and row['finally'] is not None))
    for row in value['sinks']:
        if row['call'] in owned:need(row['returned'] is not None and row['finally'] is not None)
    return sorted(owned)


class IOSWebScriptEmissions(tablet.IOSTabletWebSource):
    _action=ACTION
    _command=staticmethod(command)
    _validate=staticmethod(validate)
    _limit=LIMIT
