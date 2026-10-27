"""Original Window callback, queued diagnostic lease and native upload join.

The independent HTTP and native-upload originals remain required. This source
cannot return a requested caller, run an input or manufacture a branch result.
Unknown actual caller/context data stays factual and cannot pass admission.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import json
import re
from adapters.native_feature_observation import exact,fresh,integer,need
from adapters.native_script_observation import validate_code
from adapters.script_feature.history import same
from ios.adapters import snapshot_combined_work,snapshot_combined_preflight_http as http,avatar_call_stack
from ios.adapters.create_state import command as state_command
from ios.adapters.places_model import IOSPlacesModel
from ios.adapters.snapshot_captures import identity
from ios.adapters.snapshot_exports import FILE_NAME,stamp
from ios.adapters.web_script_emissions import stack

VERSION=1
ACTION='feature-ios-snapshot-causal-dispatch'
FILE=ACTION+'.json'
LIMIT=262144
STAGES={'window','application','snapshot','snapshot-queue'}


def command(value):
    state_command(dict(value,action='feature-ios-create-state'));need(value['action']==ACTION);return value


def caller(value,epoch):
    need(type(value) is dict)
    if not value:return value
    base={'callerVersion','method','sequence','invokedEpochMs','manager','code'}
    need(base<=set(value)<=base|{'snapshotCombinedSources','snapshotCombinedStack'})
    need(type(value['callerVersion']) is int and value['callerVersion']==1 and value['method']=='shareSnapshot'
        and integer(value['sequence'],1,1000000000) and integer(value['invokedEpochMs'],1,epoch))
    from adapters.native_script_membership import validate as membership
    membership(dict(complete=True,revision=1,managers=[value['manager']]),value['invokedEpochMs'])
    validate_code(value['code'],value['invokedEpochMs'])
    need(value['manager']['assigned'] and value['code']['submitted']
        and value['manager']['assignedEpochMs']<=value['code']['submittedEpochMs'])
    if 'snapshotCombinedSources' in value:snapshot_combined_work.shared.code_sources(value['snapshotCombinedSources'],epoch,_combined=True)
    if 'snapshotCombinedStack' in value:stack(value['snapshotCombinedStack'],epoch)
    return value


def context(value):
    need(type(value) is dict)
    if not value:return value
    exact(value,{'httpInstance','clockDomain','xhrId','replyId','created','sent','finished','entered','read'})
    identity(value['httpInstance']);identity(value['xhrId']);identity(value['replyId'])
    need(value['clockDomain']=='native-process-snapshot-combined-preflight-http')
    previous=0
    for key,kind in (('created','created'),('sent','sent'),('finished','reply-finished'),('entered','callback-enter'),('read','text-read')):
        event=value[key];exact(event,{'sequence','eventId','xhrId','kind','clock','details'})
        identity(event['eventId']);stamp(event['clock']);need(event['kind']==kind and event['xhrId']==value['xhrId']
            and integer(event['sequence'],previous+1,1024) and type(event['details']) is dict)
        previous=event['sequence']
    need(value['entered']['details']==dict(callback='readystatechange',readyState=4))
    for key in ('sent','finished','read'):need(value[key]['details'].get('replyId')==value['replyId'])
    return value


def row(value,epoch):
    exact(value,{'instance','bornEpochMs','file','caller','http','hops','upload','associatedEpochMs','releasedEpochMs','leaseAlive'})
    identity(value['instance']);need(integer(value['bornEpochMs'],1,epoch) and type(value['leaseAlive']) is bool)
    file=value['file'];exact(file,{'privateName','name','nameSha256'})
    need(type(file['privateName']) is bool and type(file['name']) is str and type(file['nameSha256']) is str
        and len(file['nameSha256'])==64 and all(c in '0123456789abcdef' for c in file['nameSha256']))
    if file['privateName']:need(re.fullmatch(FILE_NAME,file['name']) and hashlib.sha256(file['name'].encode()).hexdigest()==file['nameSha256'])
    else:need(not file['name'])
    caller(value['caller'],value['bornEpochMs']);context(value['http'])
    if value['http']:need(value['http']['read']['clock']['epochMs']<=value['bornEpochMs'])
    need(type(value['hops']) is list and len(value['hops'])<=16);ids=set();prior=value['bornEpochMs']
    for hop in value['hops']:
        exact(hop,{'instance','stage','enteredEpochMs','leftEpochMs'});identity(hop['instance'])
        need(hop['instance'] not in ids and hop['stage'] in STAGES and integer(hop['enteredEpochMs'],prior,epoch))
        ids.add(hop['instance']);prior=hop['enteredEpochMs']
        if hop['leftEpochMs'] is not None:need(integer(hop['leftEpochMs'],hop['enteredEpochMs'],epoch))
    if value['upload'] is None:need(value['associatedEpochMs'] is None)
    else:identity(value['upload']);need(integer(value['associatedEpochMs'],value['bornEpochMs'],epoch))
    if value['releasedEpochMs'] is not None:
        need(not value['leaseAlive'] and integer(value['releasedEpochMs'],value['bornEpochMs'],epoch)
            and all(hop['leftEpochMs'] is not None and hop['leftEpochMs']<=value['releasedEpochMs'] for hop in value['hops']))
    # A weak pointer can expire before its diagnostic destructor acquires the
    # ledger mutex. That factual interval does not establish drained dispatch.
    return value


def validate(value,query,pid,epoch=None,previous=None):
    command(query);exact(value,{'iosSnapshotCausalDispatchVersion','requestId','runId','instance','sequence','processId','clockDomain','clockBefore','clockAfter','source'})
    identity(value['instance']);need(type(value['iosSnapshotCausalDispatchVersion']) is int and value['iosSnapshotCausalDispatchVersion']==1
        and value['requestId']==query['commandId'] and value['runId']==query['runId'] and integer(pid,1)
        and type(value['processId']) is int and value['processId']==pid and integer(value['sequence'],1,1000000000)
        and value['clockDomain']=='native-process-snapshot-causal-dispatch')
    a,b=value['clockBefore'],value['clockAfter'];stamp(a);stamp(b)
    delta={key:b[key]-a[key] for key in a};need(all(0<=item<1500 for item in delta.values()) and abs(delta['epochMs']-delta['monotonicMs'])<=250)
    if epoch is not None:fresh(b['epochMs'],epoch)
    source=value['source'];exact(source,{'complete','calls'});need(type(source['complete']) is bool and type(source['calls']) is list and len(source['calls'])<=64)
    ids=set();uploads=set();prior=0
    for observed in source['calls']:
        row(observed,a['epochMs']);need(observed['instance'] not in ids and observed['bornEpochMs']>=prior)
        ids.add(observed['instance']);prior=observed['bornEpochMs']
        if observed['upload'] is not None:need(observed['upload'] not in uploads);uploads.add(observed['upload'])
    need(len(json.dumps(value,ensure_ascii=False,allow_nan=False).encode())<=LIMIT)
    if previous is not None:
        validate(previous,dict(query,commandId=previous['requestId']),pid)
        need(value['instance']==previous['instance'] and value['sequence']>previous['sequence'] and value['requestId']!=previous['requestId']
            and all(a[key]>=previous['clockAfter'][key] for key in a))
        old=previous['source']['calls'];new=source['calls'];need(len(new)>=len(old) and (previous['source']['complete'] or not source['complete']))
        for before,after in zip(old,new):
            need(all(same(before[key],after[key]) for key in ('instance','bornEpochMs','file','caller','http'))
                and len(after['hops'])>=len(before['hops']) and (before['leaseAlive'] or not after['leaseAlive']))
            for first,last in zip(before['hops'],after['hops']):
                need(all(same(first[key],last[key]) for key in ('instance','stage','enteredEpochMs')))
                if first['leftEpochMs'] is not None:need(first['leftEpochMs']==last['leftEpochMs'])
            if before['releasedEpochMs'] is not None:need(same(before,after))
            if not before['leaseAlive']:
                need(len(before['hops'])==len(after['hops']) and same(before['upload'],after['upload']) and same(before['associatedEpochMs'],after['associatedEpochMs']))
            for key in ('upload','associatedEpochMs','releasedEpochMs'):
                if before[key] is not None:need(same(before[key],after[key]))
    return value


def original(value):
    need(type(value) is dict)
    return validate(value,dict(schemaVersion=1,action=ACTION,commandId=value.get('requestId'),runId=value.get('runId')),value.get('processId'))


def admitted(value,scripts_root):
    original(value);need(value['source']['complete']);root=snapshot_combined_work.shared.root_url(scripts_root)
    pins_doc=json.loads(snapshot_combined_work.PIN_FILE.read_text());exact(pins_doc,{'snapshotCombinedWorkSourcePinsVersion','encoding','sources'})
    need(type(pins_doc['snapshotCombinedWorkSourcePinsVersion']) is int and pins_doc['snapshotCombinedWorkSourcePinsVersion']==1
        and pins_doc['encoding']=='utf-16le-code-units' and set(pins_doc['sources'])==set(http.FILES))
    pins=pins_doc['sources'];result=[]
    for observed in value['source']['calls']:
        source=observed['caller'];need(set(source)=={'callerVersion','method','sequence','invokedEpochMs','manager','code','snapshotCombinedSources','snapshotCombinedStack'})
        need(source['manager']['url']==root+'defaultScripts.js' and source['snapshotCombinedSources']['complete'])
        code=source['snapshotCombinedSources']['evaluations'];need(len(code)==len(http.FILES))
        for path in http.FILES:
            actual=[entry for entry in code if entry['url']==root+path];need(len(actual)==1
                and all(actual[0][key]==pins[path][key] for key in ('sha256','codeUnits')))
        need(all(source['code'][key]==pins['defaultScripts.js'][key] for key in ('sha256','codeUnits')))
        frames=source['snapshotCombinedStack'];modules=[]
        need(frames is not None and frames['complete'])
        for index,frame in enumerate(frames['frames']):
            candidates=[entry for entry in code if hashlib.sha256(entry['url'].encode()).hexdigest()==frame['sourceUrlSha256']]
            need(len(candidates)==1);modules.append(dict(frame=index,url=candidates[0]['url']))
        avatar_call_stack.evaluated(frames,modules,observed['bornEpochMs'],code,required={'/system/snapshot.js','/modules/request.js'},top='/system/snapshot.js',_combined=True)
        result.append(deepcopy(observed))
    return result


def http_join(observed,value,scripts_root):
    """Join existing exact HTTP events; never envelope or retime a context."""
    http.admit(value,scripts_root);link=context(observed['http']);need(link and link['httpInstance']==value['instance'])
    events={event['eventId']:event for event in value['events']}
    for key in ('created','sent','finished','entered','read'):
        event=link[key];need(event['eventId'] in events and same(events[event['eventId']],event))
    states=http.events(value);need(link['xhrId'] in states)
    replies=states[link['xhrId']]['replies'];need(link['replyId'] in replies and replies[link['replyId']]['callbackRead'])
    return deepcopy(link)


def drained(value,owned_calls):
    original(value);need(type(owned_calls) in (list,tuple) and bool(owned_calls) and len(set(owned_calls))==len(owned_calls))
    calls={row['instance']:row for row in value['source']['calls']}
    if not value['source']['complete']:return False
    for key in owned_calls:
        identity(key);need(key in calls);observed=calls[key]
        if (observed['leaseAlive'] or observed['releasedEpochMs'] is None or not observed['hops']
                or any(hop['leftEpochMs'] is None for hop in observed['hops'])):return False
    return True


class IOSSnapshotCausalDispatch(IOSPlacesModel):
    _limit=LIMIT;_action=ACTION;_command=staticmethod(command);_validate=staticmethod(validate)
    _acquisition_key='iosSnapshotCausalDispatchAcquisitionVersion'
