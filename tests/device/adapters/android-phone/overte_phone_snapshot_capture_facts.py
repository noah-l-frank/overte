"""Original VM/native capture timelines relative to one retained baseline.

These are raw source facts. Cancel requires the separate original fast-cancel
recipe; completion requires separately acquired original file/pixel evidence.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import need
from overte_phone_snapshot_measurements import validate
from overte_phone_snapshot_source import continuity


def capture_facts(baseline,current,*,run,pid,epoch):
    before=baseline['snapshot'];after=current['snapshot']
    original=validate(baseline,run=run,pid=pid,epoch=baseline['rootsAfter']['capturedEpochMs'])
    actual=validate(current,run=run,pid=pid,epoch=epoch)
    need(actual==original and current['rootsBefore']['source']==baseline['rootsAfter']['source'])
    continuity(before,after)
    need(not before['source']['captures'] and not before['source']['uploads'])
    initial=before['source']['scriptHistory'];history=after['source']['scriptHistory']
    events=history['events'][initial['sequence']:]
    originals=after['source']['history']['events'][before['source']['history']['sequence']:]
    native=[row for row in originals if row['kind'].startswith('capture-')]
    contexts={};timeline=[]
    for row in events:
        id=row['id']
        if row['kind']=='pending':
            need(id not in contexts);contexts[id]=dict(id=id,mode=row['mode'],pending=deepcopy(row),latest=deepcopy(row),native=[])
        else:
            need(id in contexts);contexts[id]['latest']=deepcopy(row)
        if row['kind']!='processing':timeline.append(row['kind'])
        need(row['kind']!='error') # Capture errors cannot become a completed checkpoint.
    need(len(contexts)<=8)
    for row in native:
        need(row['id'] in contexts);contexts[row['id']]['native'].append(deepcopy(row))
    for row in contexts.values():
        pending,last,work=row['pending'],row['latest'],row['native']
        begins=[item for item in work if item['kind']=='capture-begin']
        terminal=[item for item in work if item['kind']=='capture-status' and item['phase'] in ('complete','cancelled','error')]
        need(len(begins)<=1 and len(terminal)<=1 and (not begins or begins[0]==work[0])
            and (not work or begins) and all(item['capturedEpochMs']>=pending['capturedEpochMs'] for item in work))
        if terminal:
            need(begins and terminal[0]==work[-1] and terminal[0]['phase']!='error')
        if last['kind']=='complete':
            need(begins and len(terminal)==1 and terminal[0]['phase']=='complete' and terminal[0]['path']
                and terminal[0]['capturedEpochMs']<=last['capturedEpochMs'])
        elif last['kind']=='cancelled':
            need(not terminal or terminal[0]['phase']=='cancelled' and terminal[0]['capturedEpochMs']<=last['capturedEpochMs'])
            need(not begins or terminal)
        else:need(not terminal)
    live={row['id'] for row in after['source']['captures']}
    need(live<={id for id,row in contexts.items() if row['latest']['kind'] in ('pending','processing')})
    return dict(history=timeline,pending=any(row['latest']['kind'] in ('pending','processing') for row in contexts.values()),
        contexts=deepcopy(list(contexts.values())))
