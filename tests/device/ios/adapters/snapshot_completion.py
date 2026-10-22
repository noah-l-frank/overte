"""Join actual normal capture input, native completion and original file bytes.

This narrow still-image proof does not claim decoded pixels, Photos/Share/upload
outcomes, independent witness agreement or the complete feature's cleanup.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import need
from adapters.script_feature.history import same
from ios.adapters.snapshot_artifact import SnapshotArtifact
from ios.adapters.snapshot_input_owner import SnapshotInputOwner
from ios.adapters.snapshot_manifest import SnapshotManifest,absent
from ios.adapters import snapshot_work as work,snapshot_captures as native


def completed(inputs,index,before_work,after_work,before_native,after_native,before_files,artifact,scripts_root):
    need(type(inputs) is SnapshotInputOwner and type(before_files) is SnapshotManifest and type(artifact) is SnapshotArtifact)
    delivered=inputs.validate_original(index);event=inputs.state['events'][index-1]
    need(event['controlId']=='snapshot.capture' and event['command']['operation']=='activate')
    row=next(row for row in event['reference']['controls'] if row['id']=='snapshot.capture')
    need(row['snapshotMode']==0 and row['snapshotFormat'] in ('png','jpg') and row['snapshotNameOwned']
        and row['snapshotSettingsLoaded'] and not row['snapshotCapturing'] and not row['snapshotProcessing']
        and not row['snapshotStatusError'])
    for owner in (before_files,artifact):
        need(same(owner.binding,inputs.binding) and owner.run==inputs.run and owner.role==inputs.role
            and owner.store.path.parent==inputs.store.path.parent and owner.lock.path==inputs.lock.path)
    mode='still-'+row['snapshotFormat'];before=before_files.historical();absent(before,inputs.pid,inputs.run,mode)
    need(row['snapshotName']==before['query']['prefix'] and artifact.state is not None
        and artifact.state['phase']=='copied' and artifact.state['before']>before_files.index)
    fact,raw=artifact.originals();need(artifact.read()==raw)
    work.validate(after_work,dict(schemaVersion=1,action=work.ACTION,commandId=after_work['requestId'],runId=inputs.run),
        inputs.pid,previous=before_work)
    initial=work.admit(before_work,scripts_root,quiet=True);final=work.admit(after_work,scripts_root,quiet=True)
    need(same(initial['manager'],final['manager']) and final['state']['mode']=='still'
        and final['state']['captureCounter']==initial['state']['captureCounter']+1)
    native.validate(after_native,dict(schemaVersion=1,action=native.ACTION,commandId=after_native['requestId'],runId=inputs.run),
        inputs.pid,previous=before_native);native.drained(before_native);native.drained(after_native)
    need(all(value['processId']==inputs.pid and value['runId']==inputs.run for value in (before_work,after_work,before_native,after_native)))
    start=initial['latest']['sequence'];events=[entry for entry in final['events'] if entry['sequence']>start]
    entries=[entry for entry in events if entry['closure']=='takeSnapshot' and entry['event']=='entry'];need(len(entries)==1)
    entry=entries[0];take=[entry for entry in events if entry['call']==entries[0]['call']]
    need([entry['event'] for entry in take]==['entry','returned','finally']
        and all(entry['closure']=='takeSnapshot' for entry in take) and not take[0]['state']['captureId'])
    request=take[1]['state']['captureId'];need(request and take[2]['state']['captureId']==request
        and take[1]['state']['mode']==take[2]['state']['mode']=='still'
        and take[1]['state']['captureCounter']==take[2]['state']['captureCounter']==final['state']['captureCounter'])
    prior={row['instance'] for row in before_native['source']['captures']}
    captures=[row for row in after_native['source']['captures'] if row['instance'] not in prior]
    need(len(captures)==1 and captures[0]['requestId']==request)
    capture=captures[0];history=[entry for entry in after_native['source']['events'] if entry['capture']==capture['instance']]
    need([entry['kind'] for entry in history[:2]]==['begin','accepted']
        and not any(entry['kind'] in ('cancel-requested','cancelled','cancel-delivered','rejected') for entry in history))
    terminal=[entry for entry in history if entry['kind']=='status' and entry['detail']['phase'] in ('complete','error')]
    need(len(terminal)==1 and terminal[0]['detail']==dict(phase='complete',hasPath=True,hasError=False))
    callbacks=[]
    for callback in events:
        if callback['closure']!='onNativeCaptureStatus' or callback['event']!='entry' or callback['state']['captureId']!=request:continue
        call=[entry for entry in events if entry['call']==callback['call']]
        if ([entry['event'] for entry in call]==['entry','returned','finally'] and all(entry['closure']==callback['closure'] for entry in call)
                and all(not work.pending(entry['state']) for entry in call[1:])):callbacks.append(call)
    need(len(callbacks)==1);call=callbacks[0];need(call[0]['invokedEpochMs']>=terminal[0]['capturedEpochMs'])
    managers=[row for row in after_work['source']['timerSources']['workers'] if row['membership']['instance']==final['manager']['instance']]
    need(len(managers)==1)
    deadlines=[timer for timer in managers[0]['timerWork']['timers'] if timer['handle'] in take[1]['state']['timerHandles'] and timer['intervalMs']==60000]
    need(len(deadlines)==1 and deadlines[0]['singleShot'] and deadlines[0]['activeAtBirth'] and deadlines[0]['fired']==0)
    scope=event['reference']['scope'];receipt=delivered['originalReceipt']['status']
    need(before['clockJoin']['nativeAfter']['capturedEpochMs']<=scope['sampleEpochMs']<=take[0]['invokedEpochMs']
        and before_work['clockAfter']['epochMs']<=take[0]['invokedEpochMs']
        and before_native['clockAfter']['epochMs']<=take[0]['invokedEpochMs']
        and take[-1]['capturedEpochMs']<=capture['bornEpochMs']
        and call[-1]['capturedEpochMs']<=after_work['clockBefore']['epochMs']
        and receipt['sampleEpochMs']<=after_work['clockBefore']['epochMs'])
    need(fact['file']['name']==row['snapshotName']+'-'+request+'.'+row['snapshotFormat']
        and fact['prefix']==row['snapshotName'] and fact['file']['size']==len(raw))
    first,after,_chunks=artifact.owners()
    need(terminal[0]['capturedEpochMs']<=first.historical()['clockJoin']['nativeBefore']['capturedEpochMs']
        and after_native['clockAfter']['epochMs']<=after.historical()['clockJoin']['nativeAfter']['capturedEpochMs'])
    return dict(iosSnapshotCompletedCaptureVersion=1,binding=deepcopy(inputs.binding),runId=inputs.run,role=inputs.role,
        processId=inputs.pid,inputIndex=index,captureId=request,captureInstance=capture['instance'],mode='still',format=row['snapshotFormat'],
        file=deepcopy(fact['file']),artifactIndex=artifact.index,completedNativeEpochMs=terminal[0]['capturedEpochMs'],
        decodedImageRequired=True,destinationOutcomeRequired=True,independentWitnessRequired=True,quietWindowRequired=True)
