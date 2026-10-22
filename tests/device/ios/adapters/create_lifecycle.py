"""Actual queued Create-worker baseline and positive native resource retirement.

The ordinary editor script keeps running. Its original recurring timers remain
owned by the product; only new callbacks/handles/resources must disappear.
Heartbeat samples and naturally changing timer remaining time are observations,
not evidence of callback inactivity or a reason to reset counters.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy

from adapters.native_clock_join import digest
from adapters.native_feature_observation import need
from adapters.native_script_work import validate as worker_packet
from adapters.script_feature.history import same
from ios.adapters import create_state, create_work
from ios.adapters.create_actions import semantic_map, editor
from ios.adapters.create_product_state import selected

VERSION=1


def worker(value, work, scripts_root, *, quiet=True):
    need(type(quiet) is bool)
    source=create_work.admit(work,scripts_root,quiet=quiet)
    manager=next(row for row in source['roles'] if row['role']=='edit')
    query=dict(schemaVersion=1,commandId=value['requestId'],action='feature-script-work-observe',managerInstance=manager['manager']['instance'])
    worker_packet(value,query,work['processId'],value['capturedEpochMs'])
    need(same(value['source']['manager'],manager['manager']) and same(value['source']['code'],manager['code'])
         and value['source']['work']['signalCallbacks']==value['source']['work']['timerCallbacks']==0
         and value['source']['work']['evaluating'] is False
         and work['clockBefore']['epochMs']<=value['requestedEpochMs']<=value['capturedEpochMs']
         and value['capturedEpochMs']-work['clockAfter']['epochMs']<1500)
    return deepcopy(value['source']['work'])


def timers_restored(before, after):
    """Real timer handles/configuration, without comparing elapsed time."""
    original={row['handle']:row for row in before['timers']};current={row['handle']:row for row in after['timers']}
    need(set(current)<=set(original))
    for handle,row in original.items():
        if handle not in current:
            need(row['singleShot']);continue
        need(all(row[key]==current[handle][key] for key in ('handle','active','singleShot','intervalMs')))
    return True


def drained(baseline_create,baseline_work,baseline_worker,current_create,current_work,current_worker,scripts_root,owned_ids,*,editor_baseline=None):
    """Independent actual app restoration, weak expiry and queued VM barrier."""
    first,last=create_state.live(baseline_create),create_state.live(current_create)
    create_state.validate(current_create,dict(schemaVersion=1,commandId=current_create['requestId'],action=create_state.ACTION,runId=current_create['runId']),
                          baseline_create['processId'],previous=baseline_create)
    need(same(semantic_map(baseline_create),semantic_map(current_create)) and selected(last)==[] and not last['tabletShown']
         and all(first[key]==last[key] for key in ('domainId','localSessionId','canRez','canRezTmp'))
         and not any(not row['destroyed'] and row['kind']!='editor' for row in last['roots']))
    current_editor=editor(current_create)
    if current_editor is not None:
        need(editor_baseline is not None and not current_editor['active'] and not current_editor['numericFocus'] and not current_editor['changed']
             and current_editor['page']['selectedIds']==[] and current_editor['page']['tab']==editor_baseline['page']['tab']
             and same(current_editor['voxelSettings'],editor_baseline['voxelSettings']))
    create_work.validate(current_work,dict(schemaVersion=1,commandId=current_work['requestId'],action=create_work.ACTION,runId=current_work['runId']),
                         baseline_work['processId'],previous=baseline_work)
    life=create_work.retired(current_work,scripts_root,owned_ids)
    before=worker(baseline_worker,baseline_work,scripts_root);after=worker(current_worker,current_work,scripts_root)
    worker_packet(current_worker,dict(schemaVersion=1,commandId=current_worker['requestId'],action='feature-script-work-observe',
        managerInstance=baseline_worker['source']['manager']['instance']),current_work['processId'],current_worker['capturedEpochMs'],previous=baseline_worker)
    timers_restored(before,after)
    # Stable activity excludes the deliberately repeating heartbeat and each
    # read's capture time/sequence. Actual callback entries and lifecycle births
    # remain in this digest, so new work restarts the enclosing quiet interval.
    activity=dict(entities=life['entityLifetimes'],roles=[dict(role=row['role'],manager=row['manager'],code=row['code'],
        state=row['state'],calls=row['calls'],events=[event for event in row['events'] if event['event']!='snapshot']) for row in life['roles']],
        timers=[{key:row[key] for key in ('handle','active','singleShot','intervalMs')} for row in after['timers']])
    return dict(iosCreateDrainVersion=VERSION,activitySha256=digest(activity),entityIds=deepcopy(owned_ids),
                nativeEpochMs=current_worker['capturedEpochMs'])
