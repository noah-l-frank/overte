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
from snapshot_observation import inspect_snapshot


def _file_completion(inputs,index,before_work,after_work,before_native,after_native,before_files,artifact,scripts_root,*,mode,output_format,_combined=False):
    need(type(_combined) is bool)
    from ios.adapters import snapshot_combined_work
    work_source=snapshot_combined_work if _combined else work
    need(type(inputs) is SnapshotInputOwner and type(before_files) is SnapshotManifest and type(artifact) is SnapshotArtifact)
    delivered=inputs.validate_original(index);event=inputs.state['events'][index-1]
    need(event['controlId']=='snapshot.capture' and event['command']['operation']=='activate')
    row=next(row for row in event['reference']['controls'] if row['id']=='snapshot.capture')
    modes=('still','animated','panorama','cubemap')
    need(mode in modes and row['snapshotMode']==modes.index(mode) and row['snapshotFormat'] in ('png','jpg')
        and output_format in ({row['snapshotFormat'],'gif'} if mode=='animated' else {row['snapshotFormat']})
        and row['snapshotNameOwned']
        and row['snapshotSettingsLoaded'] and not row['snapshotCapturing'] and not row['snapshotProcessing']
        and not row['snapshotStatusError'])
    for owner in (before_files,artifact):
        need(same(owner.binding,inputs.binding) and owner.run==inputs.run and owner.role==inputs.role
            and owner.store.path.parent==inputs.store.path.parent and owner.lock.path==inputs.lock.path)
    label='still-'+row['snapshotFormat'] if mode=='still' else mode
    before=before_files.historical();absent(before,inputs.pid,inputs.run,label)
    need(row['snapshotName']==before['query']['prefix'] and artifact.state is not None
        and artifact.state['phase']=='copied' and artifact.state['before']>before_files.index)
    fact,raw=artifact.originals();need(artifact.read()==raw)
    work_source.validate(after_work,dict(schemaVersion=1,action=work_source.ACTION,commandId=after_work['requestId'],runId=inputs.run),
        inputs.pid,previous=before_work)
    initial=work_source.admit(before_work,scripts_root,quiet=True);final=work_source.admit(after_work,scripts_root,quiet=True)
    need(same(initial['manager'],final['manager']) and final['state']['mode']==mode
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
        and take[1]['state']['mode']==take[2]['state']['mode']==mode
        and take[1]['state']['captureCounter']==take[2]['state']['captureCounter']==final['state']['captureCounter'])
    prior={row['instance'] for row in before_native['source']['captures']}
    captures=[row for row in after_native['source']['captures'] if row['instance'] not in prior]
    need(len(captures)==1 and captures[0]['requestId']==request)
    capture=captures[0];history=[entry for entry in after_native['source']['events'] if entry['capture']==capture['instance']]
    need([entry['kind'] for entry in history[:2]]==['begin','accepted']
        and not any(entry['kind'] in ('cancel-requested','cancelled','cancel-delivered','rejected') for entry in history))
    terminal=[entry for entry in history if entry['kind']=='status' and entry['detail']['phase'] in ('complete','error')]
    need(len(terminal)==1 and terminal[0]['detail']==dict(phase='complete',hasPath=True,hasError=False))
    processing=[entry for entry in history if entry['kind']=='status' and entry['detail']['phase']=='processing']
    if mode!='still':
        need(len(processing)==1 and processing[0]['detail']==dict(phase='processing',hasPath=mode=='animated',hasError=False)
            and processing[0]['sequence']<terminal[0]['sequence'])
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
    need(fact['file']['name']==row['snapshotName']+'-'+request+'.'+output_format
        and fact['prefix']==row['snapshotName'] and fact['file']['size']==len(raw))
    first,after,_chunks=artifact.owners()
    need(terminal[0]['capturedEpochMs']<=first.historical()['clockJoin']['nativeBefore']['capturedEpochMs']
        and after_native['clockAfter']['epochMs']<=after.historical()['clockJoin']['nativeAfter']['capturedEpochMs'])
    return dict(binding=deepcopy(inputs.binding),runId=inputs.run,role=inputs.role,
        processId=inputs.pid,inputIndex=index,captureId=request,captureInstance=capture['instance'],mode=mode,format=output_format,
        file=deepcopy(fact['file']),artifactIndex=artifact.index,completedNativeEpochMs=terminal[0]['capturedEpochMs'],
        decodedImageRequired=True,destinationOutcomeRequired=True,independentWitnessRequired=True,quietWindowRequired=True)


def completed(inputs,index,before_work,after_work,before_native,after_native,before_files,artifact,scripts_root,*,_combined=False):
    # Keep the released still-only version-1 result and its exact field values.
    need(type(inputs) is SnapshotInputOwner and type(index) is int and 1<=index<=len(inputs.state['events']))
    event=inputs.state['events'][index-1]
    row=next(row for row in event['reference']['controls'] if row['id']=='snapshot.capture')
    result=_file_completion(inputs,index,before_work,after_work,before_native,after_native,before_files,artifact,scripts_root,
        mode='still',output_format=row['snapshotFormat'],_combined=_combined)
    return dict(iosSnapshotCompletedCaptureVersion=2,workProfile='combined',**result) if _combined else dict(iosSnapshotCompletedCaptureVersion=1,**result)


def output_set(inputs,index,before_work,after_work,before_native,after_native,before_files,artifacts,scripts_root):
    """One actual capture and its complete still/GIF or projection output set.

    Each artifact reopens original file/chunk/job histories. The initial and final
    manifest sets must agree exactly, so extra, missing and foreign output cannot
    be hidden by selecting just one otherwise valid artifact.
    """
    need(type(inputs) is SnapshotInputOwner and type(before_files) is SnapshotManifest
        and type(index) is int and 1<=index<=len(inputs.state['events'])
        and type(artifacts) is list and 1<=len(artifacts)<=2 and all(type(v) is SnapshotArtifact for v in artifacts))
    event=inputs.state['events'][index-1]
    rows=[row for row in event['reference']['controls'] if row['id']=='snapshot.capture'];need(len(rows)==1)
    control=rows[0];modes=('still','animated','panorama','cubemap');number=control['snapshotMode']
    need(type(number) is int and 0<=number<len(modes));mode=modes[number]
    formats={'png','gif'} if mode=='animated' else {control['snapshotFormat']}
    # The ordinary animated profile uses the existing PNG still companion.
    need(mode!='animated' or control['snapshotFormat']=='png')
    need(len(artifacts)==len(formats) and len({v.index for v in artifacts})==len(artifacts))
    completed_files=[];names=set();observed_formats=set();manifest_ids=None
    for artifact in artifacts:
        need(artifact.state is not None and artifact.state['phase']=='copied')
        fact,raw=artifact.originals();extension=fact['file']['name'].rsplit('.',1)[-1]
        need(extension in formats and extension not in observed_formats);observed_formats.add(extension)
        result=_file_completion(inputs,index,before_work,after_work,before_native,after_native,before_files,artifact,scripts_root,
            mode=mode,output_format=extension)
        names.add(result['file']['name']);completed_files.append(result)
        first,last,_=artifact.owners();ids=(first.index,last.index)
        if manifest_ids is None:manifest_ids=ids
        else:need(ids==manifest_ids)
        for manifest in (first,last):
            actual=manifest.historical()['packet']['files']
            need(len(actual)==len(formats))
            # All artifacts use these same immutable complete manifests.
            need({row['name'] for row in actual}=={v.state['fact']['file']['name'] for v in artifacts})
    need(observed_formats==formats and len(names)==len(formats))
    first=completed_files[0]
    need(all(all(same(v[key],first[key]) for key in ('binding','runId','role','processId','inputIndex','captureId',
        'captureInstance','mode','completedNativeEpochMs')) for v in completed_files))
    return dict(iosSnapshotOutputSetVersion=1,binding=deepcopy(inputs.binding),runId=inputs.run,role=inputs.role,
        inputIndex=index,mode=mode,captureId=first['captureId'],files=sorted(completed_files,key=lambda v:v['format']),
        decodedImagesRequired=True,sceneFidelityRequired=True,destinationOutcomeRequired=True,
        independentWitnessRequired=True,quietWindowRequired=True)


def decoded_output_set(*args):
    """Decode the exact complete original set; no orientation/motion claim."""
    result=output_set(*args);artifacts=args[7];images=[]
    for capture in result['files']:
        artifact=next(v for v in artifacts if v.index==capture['artifactIndex']);raw=artifact.read()
        mode='animated' if capture['format']=='gif' else 'still' if result['mode']=='animated' else result['mode']
        image=inspect_snapshot(raw,mode=mode,file_format=capture['format'])
        need(image['sha256']==capture['file']['sha256'] and image['bytes']==capture['file']['size']);images.append(image)
    return dict(iosSnapshotDecodedOutputSetVersion=1,capture=result,images=images,
        sceneFidelityRequired=True,visualMotionRequired=result['mode']=='animated',orientationRequired=result['mode'] in ('panorama','cubemap'),
        destinationOutcomeRequired=True,independentWitnessRequired=True,quietWindowRequired=True)


def decoded(inputs,index,before_work,after_work,before_native,after_native,before_files,artifact,scripts_root,*,_combined=False):
    """Decode the same original file after the complete capture/source join.

    The common decoder verifies encoding and complete nonuniform pixels. Scene
    fidelity, system destinations and independent witness evidence stay open.
    """
    capture=completed(inputs,index,before_work,after_work,before_native,after_native,before_files,artifact,scripts_root,_combined=_combined)
    raw=artifact.read();image=inspect_snapshot(raw,mode=capture['mode'],file_format=capture['format'])
    need(image['sha256']==capture['file']['sha256'] and image['bytes']==capture['file']['size'])
    result=dict(iosSnapshotDecodedCaptureVersion=2 if _combined else 1,capture=capture,image=image,sceneFidelityRequired=True,
        destinationOutcomeRequired=True,independentWitnessRequired=True,quietWindowRequired=True)
    if _combined:result['workProfile']='combined'
    return result
