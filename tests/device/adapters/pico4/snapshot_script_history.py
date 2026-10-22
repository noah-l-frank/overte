"""Original VM-bound Snapshot capture events, including pre-render cancellation.

This structural journal is not a feature verdict. Its caller must additionally
be joined to the reviewed Snapshot source and fresh independent Script work/UI.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
import re
from adapters.native_feature_observation import exact,integer,need
from adapters.native_script_membership import validate as membership
from adapters.native_script_observation import validate_code
from adapters.native_script_compilations import compilation
from feature_journeys.contract import typed_equal


def validate(value,epoch):
    exact(value,{'snapshotScriptHistoryVersion','instance','complete','sequence','events'})
    need(type(value['snapshotScriptHistoryVersion']) is int and value['snapshotScriptHistoryVersion']==1
        and type(value['instance']) is str and re.fullmatch('[0-9a-f]{32}',value['instance'])
        and value['complete'] is True and integer(value['sequence'],0,256)
        and type(value['events']) is list and len(value['events'])==value['sequence'])
    contexts={};previous=elapsed=0;callers={}
    for index,row in enumerate(value['events'],1):
        exact(row,{'sequence','kind','id','mode','revision','capturedEpochMs','elapsedMs','caller'})
        need(type(row['sequence']) is int and row['sequence']==index and row['kind'] in ('pending','processing','complete','cancelled','error')
            and type(row['id']) is str and re.fullmatch(r'snap_[0-9]{1,16}_[0-9]{1,10}',row['id'])
            and row['mode'] in ('still','animated','panorama','cubemap') and integer(row['revision'],1,2147483647)
            and integer(row['capturedEpochMs'],max(1,previous),epoch) and integer(row['elapsedMs'],elapsed))
        caller=row['caller'];exact(caller,{'callerVersion','method','sequence','invokedEpochMs','manager','code','compilation','snapshotWork'})
        need(type(caller['callerVersion']) is int and caller['callerVersion']==2 and caller['method']=='featureCaptureEvent'
            and integer(caller['sequence'],1,1_000_000_000) and integer(caller['invokedEpochMs'],1,row['capturedEpochMs']))
        membership(dict(complete=True,revision=1,managers=[caller['manager']]),caller['invokedEpochMs'])
        validate_code(caller['code'],caller['invokedEpochMs']);compilation(caller['compilation'],caller['invokedEpochMs'])
        work=caller['snapshotWork'];exact(work,{'snapshotScriptWorkVersion','scriptId','capturedEpochMs','timers','signalCallbacks',
            'timerCallbacks','signalInvocations','timerInvocations','timerRegistrations'})
        need(type(work['snapshotScriptWorkVersion']) is int and work['snapshotScriptWorkVersion']==1
            and work['scriptId']==caller['compilation']['scriptId'] and type(work['scriptId']) is int
            and integer(work['capturedEpochMs'],caller['invokedEpochMs'],row['capturedEpochMs'])
            and all(integer(work[key],0,1_000_000_000) for key in ('signalCallbacks','timerCallbacks','signalInvocations','timerInvocations','timerRegistrations'))
            and work['signalInvocations']>=work['signalCallbacks'] and work['timerInvocations']>=work['timerCallbacks']
            and type(work['timers']) is list and len(work['timers'])<=256 and work['timerRegistrations']>=len(work['timers']))
        handles=[]
        for timer in work['timers']:
            exact(timer,{'handle','active','singleShot','intervalMs','remainingMs'})
            need(integer(timer['handle'],1,2147483647) and type(timer['active']) is bool and type(timer['singleShot']) is bool
                and integer(timer['intervalMs'],-2147483648,2147483647) and integer(timer['remainingMs'],-1,2147483647)
                and (timer['remainingMs']>=0 if timer['active'] else timer['remainingMs']==-1))
            handles.append(timer['handle'])
        need(handles==sorted(set(handles)))
        need(caller['manager']['assigned'] and caller['code']['submitted']
            and caller['manager']['assignedEpochMs']<=caller['code']['submittedEpochMs']<=caller['compilation']['compiledEpochMs'])
        key=caller['manager']['instance'];old=callers.get(key)
        if old is not None:
            need(caller['sequence']>old['sequence'] and caller['invokedEpochMs']>=old['invokedEpochMs']
                and typed_equal(caller['manager'],old['manager']) and typed_equal(caller['code'],old['code']))
        callers[key]=caller
        old=contexts.get(row['id'])
        if row['kind']=='pending':need(old is None)
        else:
            need(old is not None and old['kind'] in ('pending','processing') and row['mode']==old['mode']
                and row['revision']>=old['revision'] and caller['manager']==old['caller']['manager']
                and caller['code']==old['caller']['code'] and caller['compilation']==old['caller']['compilation'])
            if row['kind']=='processing':need(row['mode']=='animated' and old['kind']=='pending')
        contexts[row['id']]=row;previous,elapsed=row['capturedEpochMs'],row['elapsedMs']
    return value


def continuity(before,after):
    need(after['instance']==before['instance'] and after['sequence']>=before['sequence']
        and typed_equal(after['events'][:len(before['events'])],before['events']))


def join_compilation(value,execution,snapshot_url,reviewed=None):
    """Join original VM callers to separately acquired native compilations.

    snapshot_url must come from the actual installed script-root owner, not a
    caller-supplied basename. The reviewed digest is independent source input;
    it is never sent to the native observer or treated as an observed event.
    """
    from adapters.native_script_observation import validate as validate_execution
    validate_execution(execution,execution['requestId'],execution['processId'],execution['capturedEpochMs'])
    validate(value,execution['capturedEpochMs'])
    if reviewed is None:
        import json
        from pathlib import Path
        reviewed=json.loads(Path(__file__).with_name('snapshot-script-pin.v1.json').read_text())
    exact(reviewed,{'encoding','codeUnits','sha256'})
    need(reviewed['encoding']=='utf-16le-code-units' and integer(reviewed['codeUnits'],1,4194304)
        and type(reviewed['sha256']) is str and re.fullmatch('[0-9a-f]{64}',reviewed['sha256'])
        and type(snapshot_url) is str and snapshot_url.endswith('/scripts/system/snapshot.js'))
    from urllib.parse import urlsplit,unquote
    url=urlsplit(snapshot_url)
    need(url.scheme in ('qrc','file') and not url.netloc and not url.query and not url.fragment
        and url.path.startswith('/') and unquote(url.path)==url.path and '\\' not in url.path
        and all(part not in ('.','..') for part in url.path.split('/')))
    members=execution['source']['membership'];need(members['complete'])
    selected=[]
    for engine in execution['source']['engines']:
        if not engine['running'] or engine['stopping'] or engine['finished']:continue
        need(engine.get('compiled',{}).get('complete') is True)
        for compiled in engine['compiled']['compilations']:
            if compiled['resourceName']==snapshot_url:
                need(all(compiled[key]==reviewed[key] for key in reviewed))
                owners=[row for row in members['managers'] if row['instance']==engine['required']['instance']]
                need(len(owners)==1)
                selected.append((owners[0],engine['code'],compiled))
    need(len(selected)==1)
    manager,code,compiled=selected[0]
    for event in value['events']:
        origin=event['caller']
        need(typed_equal(origin['manager'],manager) and typed_equal(origin['code'],code)
            and typed_equal(origin['compilation'],compiled))
    return compiled
