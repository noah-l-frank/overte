"""Join retained ordinary input, actual pending work and owned file absence.

This derives an early-cancellation fact, not whole Snapshot or quiet acceptance.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import integer,need
from adapters.script_feature.history import same
from ios.adapters.snapshot_input_owner import SnapshotInputOwner,reference
from ios.adapters.snapshot_manifest import SnapshotManifest,absent
from ios.adapters.snapshot_captures import pending_cancellation
from ios.adapters import snapshot_work


def pending(owner,capture_index,cancel_index,native_before,work_pending,work_cancelled,native_after,
            before_manifest,after_manifest,scripts_root,*,_combined=False):
    need(type(_combined) is bool)
    from ios.adapters import snapshot_combined_work
    module=snapshot_combined_work if _combined else snapshot_work
    need(isinstance(owner,SnapshotInputOwner) and isinstance(before_manifest,SnapshotManifest) and isinstance(after_manifest,SnapshotManifest)
        and integer(capture_index,1) and integer(cancel_index,capture_index+1))
    # Reopen actual durable input originals, including any lost-return proof.
    deliveries=[owner.validate_original(index) for index in (capture_index,cancel_index)]
    state=owner.decode(owner.previous);events=[state['events'][index-1] for index in (capture_index,cancel_index)]
    rows=[]
    for event,delivery,control in zip(events,deliveries,('snapshot.capture','snapshot.cancel')):
        need(event['controlId']==control and event['command']['operation']=='activate'
            and same(event['command'],delivery['command']))
        rows.append(reference(event['reference'],control))
    capture,cancel=rows;need(capture['snapshotNameOwned'] and cancel['snapshotNameOwned']
        and capture['snapshotName']==cancel['snapshotName'] and not capture['snapshotCapturing'] and cancel['snapshotCapturing']
        and capture['snapshotMode']==cancel['snapshotMode'] and capture['snapshotFormat']==cancel['snapshotFormat']
        and capture['snapshotSettingsLoaded'] and cancel['snapshotSettingsLoaded']
        and all(not row['snapshotStatusError'] and not row['snapshotSystemBlocked'] for row in rows))
    mode=('still','animated','panorama','cubemap')[capture['snapshotMode']]
    file_mode=('still-'+capture['snapshotFormat']) if mode=='still' else mode
    need(file_mode in ('still-png','still-jpg','animated','panorama','cubemap')
        and capture['snapshotName']=='parity-'+owner.run[:16]+'-'+file_mode)
    for source in (before_manifest,after_manifest):
        need(same(source.binding,owner.binding) and source.run==owner.run and source.role==owner.role
            and source.store.path.parent==owner.store.path.parent and source.lock.path==owner.lock.path)
    need(before_manifest.index<after_manifest.index)
    first,last=before_manifest.historical(),after_manifest.historical()
    first_clock,last_clock=first['clockJoin']['nativeAfter'],last['clockJoin']['nativeBefore']
    need(first_clock['instance']==last_clock['instance'] and first_clock['sequence']<last_clock['sequence']
        and first_clock['requestId']!=last_clock['requestId']
        and all(last_clock['lifecycle'][key]>=count for key,count in first_clock['lifecycle'].items()))
    before_absence,after_absence=(absent(frame,owner.pid,owner.run,file_mode) for frame in (first,last))
    proof=pending_cancellation(native_before,work_pending,work_cancelled,native_after,scripts_root,_combined=_combined)
    need(proof['processId']==owner.pid and proof['runId']==owner.run)
    work=module.admit(work_pending,scripts_root);need(work['state']['mode']==mode)
    take=[entry for entry in work['events'] if entry['closure']=='takeSnapshot' and entry['event']=='entry']
    finished=module.admit(work_cancelled,scripts_root)
    cancel_entries=[entry for entry in finished['events'] if entry['closure']=='cancelNativeCapture'
        and entry['event']=='entry' and entry['call']==proof['cancelCall']]
    need(take and len(cancel_entries)==1)
    selected=[entry for entry in take if entry['call']==next(row['call'] for row in work['events']
        if row['closure']=='takeSnapshot' and row['event']=='returned' and row['state']['captureId']==proof['captureId'])]
    need(len(selected)==1)
    capture_scope,cancel_scope=(event['reference']['scope'] for event in events)
    capture_return,cancel_return=(delivery['originalReceipt']['status']['sampleEpochMs'] for delivery in deliveries)
    need(first['clockJoin']['nativeAfter']['capturedEpochMs']<=native_before['clockBefore']['epochMs']
        <=capture_scope['sampleEpochMs']<=selected[0]['invokedEpochMs']
        and capture_return<=work_pending['clockBefore']['epochMs']
        and work_pending['clockAfter']['epochMs']<=cancel_scope['sampleEpochMs']<=cancel_entries[0]['invokedEpochMs']
        and cancel_return<=work_cancelled['clockBefore']['epochMs']
        and native_after['clockAfter']['epochMs']<=last['clockJoin']['nativeBefore']['capturedEpochMs'])
    result=dict(iosSnapshotOwnedPendingCancellationVersion=2 if _combined else 1,runId=owner.run,role=owner.role,processId=owner.pid,
        captureId=proof['captureId'],root=deepcopy(deliveries[0]['root']),captureInput=capture_index,cancelInput=cancel_index,
        cancelCall=proof['cancelCall'],beforeManifest=before_manifest.index,afterManifest=after_manifest.index,
        beforeAbsence=before_absence,afterAbsence=after_absence,quietWindowRequired=True,independentWitnessRequired=True)
    if _combined:result['workProfile']='combined'
    return result
