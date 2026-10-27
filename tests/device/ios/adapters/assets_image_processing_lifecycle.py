"""Pure actual processing/device join after ordinary Delete/Home originals.

Observed QIODevice/body edges only, never arbitrary bytes, QRunnable/pool,
plugin/decoder storage, physical GPU, process/SDK or whole Resource completion.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import exact,need
from adapters.script_feature.history import same
from ios.adapters import assets_image_reader as reader,assets_image_reader_processing as processing
from ios.adapters import assets_image_reader_lifecycle as lifecycle
from ios.adapters.assets_image_processing_sources import AssetsImageReaderProcessingSources
from ios.adapters.assets_image_processing_ownership import inspect_processing,owned_prefix
from ios.adapters.graphics_history import follow_native

VERSION=1


def closed(packet,parent,selected_tasks):
    source=processing.parent_links(packet,parent)
    need(type(selected_tasks) is list and selected_tasks and len(selected_tasks)==len(set(selected_tasks)))
    tasks={row['taskId']:row for row in source['tasks']};actual={row['id']:row for row in parent['source']['tasks']}
    need(list(tasks)==list(actual) and set(selected_tasks)<=set(tasks))
    observed=[];without=[]
    for task in selected_tasks:
        need(not tasks[task]['derivedMarkerAlive'] and not actual[task]['derivedMarkerAlive']
            and actual[task]['runReturned'] is not None and actual[task]['readReturned'] is not None
            and actual[task]['runUnwound'] is None and actual[task]['readUnwound'] is None)
        calls=[row for row in source['calls'] if row['taskId']==task]
        branches={row['branch'] for row in parent['source']['dispatches'] if row['taskId']==task}
        if not calls:
            # Positive complete native call census after actual marker expiry,
            # plus the original branch. No guessed decode/device/destruction.
            need(not branches or branches=={'cache-reuse'});without.append(task);continue
        need(len(calls)==1 and branches and 'cache-reuse' not in branches)
        row=calls[0]
        need(all(row[key] is not None for key in ('processingReturned','rawReturned','contentResetEntered',
            'contentResetReturned','deviceDestroyedObserved')) and row['processingUnwound'] is None
            and row['rawUnwound'] is None and row['deviceOwnersAlive'] is False)
        observed.append(deepcopy(row))
    return dict(callIds=[row['id'] for row in observed],deviceIds=[row['deviceId'] for row in observed],
        observations=observed,noProcessingTaskIds=sorted(without),source1Instance=source['source1Instance'],
        observedProcessingAndInputDeviceEdgesClosed=True,byteCopyCompletionAvailable=False,
        basePoolCompletionAvailable=False,decoderCompletionAvailable=False,gpuCompletionAvailable=False,resourceRetirementAvailable=False)


def signature(value):return {key:deepcopy(row) for key,row in value.items() if key!='clock'}


def compose(owner,scene,images,processes,baseline,pairs):
    need(isinstance(processes,AssetsImageReaderProcessingSources) and processes.lock is images.lock is scene.lock is owner.lock
        and processes.store.path.parent==images.store.path.parent and processes.run==images.run
        and same(processes.binding,images.binding) and type(pairs) is list and 3<=len(pairs)<=8)
    exact(baseline,{'image','processing','scene'})
    for pair in pairs:exact(pair,{'image','processing','scene'})
    base=lifecycle.compose(owner,scene,images,{key:baseline[key] for key in ('image','scene')},
        [{key:pair[key] for key in ('image','scene')} for pair in pairs])
    need(processes.previous is not None and same(processes.store.read(),processes.previous)
        and same(processes.decode(processes.previous),processes.state) and processes.state['pending'] is None
        and processes.raws.pending is None and not processes.state['interrupted']
        and pairs[-1]['processing']==processes.state['frames'][-1])
    directory=processes.store.path.parent;paths={p.name for p in directory.iterdir() if owned_prefix(p.name)}
    inspect_processing(directory,list(directory.iterdir()))
    before=lifecycle.frame(processes,baseline['processing'])['sample'];old=before
    before_image=lifecycle.frame(images,baseline['image'])['sample'];before_world=lifecycle.frame(scene,baseline['scene'])['scene']
    need(before_image['clockJoin']['hostAfterMonotonic']<=before['clockJoin']['hostBeforeMonotonic']
        and before['clockJoin']['hostAfterMonotonic']<=before_world['clockJoin']['hostBeforeMonotonic'])
    follow_native(before_image['clockJoin']['nativeAfter'],before['clockJoin']['nativeBefore'])
    follow_native(before['clockJoin']['nativeAfter'],before_world['clockJoin']['nativeBefore'])
    positive={row['taskId'] for row in before['originals']['processing']['source']['calls'] if row['processingEntered'] is not None}
    need(positive.intersection(base['observations'][0]['taskIds'])) # Actual positive buffer/body source, not an empty table.
    observations=[];frames=[]
    for pair,base_observation in zip(pairs,base['observations']):
        image=lifecycle.frame(images,pair['image'])['sample'];sample=lifecycle.frame(processes,pair['processing'])['sample']
        world=lifecycle.frame(scene,pair['scene'])['scene']
        need(image['clockJoin']['hostAfterMonotonic']<=sample['clockJoin']['hostBeforeMonotonic']
            and sample['clockJoin']['hostAfterMonotonic']<=world['clockJoin']['hostBeforeMonotonic']
            and old['clockJoin']['hostAfterMonotonic']<=sample['clockJoin']['hostBeforeMonotonic'])
        follow_native(image['clockJoin']['nativeAfter'],sample['clockJoin']['nativeBefore'])
        follow_native(sample['clockJoin']['nativeAfter'],world['clockJoin']['nativeBefore'])
        for key,module in (('processing',processing),('reader',reader)):
            packet=sample['originals'][key]
            module.validate(packet,dict(schemaVersion=1,action=module.ACTION,commandId=packet['requestId'],runId=processes.run),processes.pid,
                previous=old['originals'][key])
        parent=sample['originals']['reader'];queue_parent=image['originals']['reader']
        reader.validate(parent,dict(schemaVersion=1,action=reader.ACTION,commandId=parent['requestId'],runId=processes.run),processes.pid,previous=queue_parent)
        need(same(signature(parent['source']),signature(queue_parent['source'])))
        facts=closed(sample['originals']['processing'],parent,base_observation['taskIds'])
        observations.append(facts);frames.append(sample);old=sample
    first,last=frames[0],frames[-1]
    need(last['clockJoin']['hostBeforeMonotonic']-first['clockJoin']['hostAfterMonotonic']>=3
        and last['clockJoin']['hostBeforeEpochMs']-first['clockJoin']['hostAfterEpochMs']>=3000
        and last['clockJoin']['nativeBefore']['capturedEpochMs']-first['clockJoin']['nativeAfter']['capturedEpochMs']>=3000
        and last['originals']['processing']['source']['clock']['monotonicMs']-first['originals']['processing']['source']['clock']['monotonicMs']>=3000)
    for row in frames[1:]:need(same(signature(first['originals']['processing']['source']),signature(row['originals']['processing']['source'])))
    inspect_processing(directory,list(directory.iterdir()));need(paths=={p.name for p in directory.iterdir() if owned_prefix(p.name)})
    for child in (owner,owner.sources,scene,images,processes):need(same(child.store.read(),child.previous))
    return dict(assetImageProcessingLifecycleVersion=1,runId=processes.run,binding=deepcopy(processes.binding),
        entityId=base['entityId'],readerId=base['readerId'],removalCommandId=base['removalCommandId'],imageReaderLifecycle=base,
        baselineOriginals=deepcopy(baseline),sourceOriginals=deepcopy(pairs),observations=observations,
        observedProcessingAndInputDeviceEdgesClosed=True,byteCopyCompletionAvailable=False,
        basePoolCompletionAvailable=False,decoderCompletionAvailable=False,gpuCompletionAvailable=False,resourceRetirementAvailable=False)
