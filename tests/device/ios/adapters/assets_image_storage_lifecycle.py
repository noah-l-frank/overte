"""Pure selected runnable destruction/deallocation-call edges, never pool end."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import exact,need
from adapters.script_feature.history import same
from ios.adapters import assets_image_reader as reader,assets_image_reader_storage as storage
from ios.adapters import assets_image_reader_lifecycle as image_lifecycle,assets_image_processing_lifecycle as processing_lifecycle
from ios.adapters.assets_image_storage_sources import AssetsImageReaderStorageSources
from ios.adapters.assets_image_storage_ownership import inspect_storage,owned_prefix
from ios.adapters.graphics_history import follow_native

VERSION=1


def closed(packet,parent,selected_tasks):
    source=storage.parent_links(packet,parent)
    need(type(selected_tasks) is list and selected_tasks and len(selected_tasks)==len(set(selected_tasks)))
    actual={row['id']:row for row in parent['source']['tasks']}
    bound={row['taskId']:row for row in source['allocations'] if row['taskId']}
    need(set(bound)==set(actual) and set(selected_tasks)<=set(actual))
    observations=[]
    for task in selected_tasks:
        row=bound[task];original=actual[task]
        # Matching delete also runs for constructor failures. A successful
        # actual Source1 constructor and the actual derived destructor entry
        # distinguish this complete ordinary virtual-destruction path.
        need(original['constructorReturned'] is not None and not original['derivedMarkerAlive']
            and not row['derivedMarkerAlive'] and row['allocationThrew'] is None
            and all(row[key] is not None for key in ('allocationReturned','sourceAttached','destructorBodyEntered','deleteEntered','deleteReturned')))
        need(original['constructorReturned']['epochMs']<=row['destructorBodyEntered']['epochMs'])
        observations.append(deepcopy(row))
    return dict(allocationIds=[row['id'] for row in observations],observations=observations,
        source1Instance=source['source1Instance'],observedRunnableDestructorAndDeallocationEdgesClosed=True,
        byteCopyCompletionAvailable=False,poolCompletionAvailable=False,decoderCompletionAvailable=False,
        gpuCompletionAvailable=False,resourceRetirementAvailable=False)


def signature(value):return {key:deepcopy(row) for key,row in value.items() if key!='clock'}


def compose(owner,scene,images,processes,storages,baseline,pairs):
    need(isinstance(storages,AssetsImageReaderStorageSources) and storages.lock is processes.lock is images.lock is scene.lock is owner.lock
        and storages.store.path.parent==processes.store.path.parent and storages.run==processes.run
        and same(storages.binding,processes.binding) and type(pairs) is list and 3<=len(pairs)<=8)
    exact(baseline,{'image','processing','storage','scene'})
    for pair in pairs:exact(pair,{'image','processing','storage','scene'})
    base=processing_lifecycle.compose(owner,scene,images,processes,{key:baseline[key] for key in ('image','processing','scene')},
        [{key:pair[key] for key in ('image','processing','scene')} for pair in pairs])
    need(storages.previous is not None and same(storages.store.read(),storages.previous)
        and same(storages.decode(storages.previous),storages.state) and storages.state['pending'] is None
        and storages.raws.pending is None and not storages.state['interrupted']
        and pairs[-1]['storage']==storages.state['frames'][-1])
    directory=storages.store.path.parent;paths={p.name for p in directory.iterdir() if owned_prefix(p.name)}
    inspect_storage(directory,list(directory.iterdir()))
    before=image_lifecycle.frame(storages,baseline['storage'])['sample'];old=before
    before_processing=image_lifecycle.frame(processes,baseline['processing'])['sample']
    before_world=image_lifecycle.frame(scene,baseline['scene'])['scene']
    need(before_processing['clockJoin']['hostAfterMonotonic']<=before['clockJoin']['hostBeforeMonotonic']
        and before['clockJoin']['hostAfterMonotonic']<=before_world['clockJoin']['hostBeforeMonotonic'])
    follow_native(before_processing['clockJoin']['nativeAfter'],before['clockJoin']['nativeBefore'])
    follow_native(before['clockJoin']['nativeAfter'],before_world['clockJoin']['nativeBefore'])
    selected=set(base['imageReaderLifecycle']['observations'][0]['taskIds'])
    positive={row['taskId'] for row in before['originals']['storage']['source']['allocations'] if row['sourceAttached'] is not None}
    need(selected and selected<=positive)
    observations=[];frames=[]
    for pair,base_observation in zip(pairs,base['imageReaderLifecycle']['observations']):
        process=image_lifecycle.frame(processes,pair['processing'])['sample'];sample=image_lifecycle.frame(storages,pair['storage'])['sample']
        world=image_lifecycle.frame(scene,pair['scene'])['scene']
        need(process['clockJoin']['hostAfterMonotonic']<=sample['clockJoin']['hostBeforeMonotonic']
            and sample['clockJoin']['hostAfterMonotonic']<=world['clockJoin']['hostBeforeMonotonic']
            and old['clockJoin']['hostAfterMonotonic']<=sample['clockJoin']['hostBeforeMonotonic'])
        follow_native(process['clockJoin']['nativeAfter'],sample['clockJoin']['nativeBefore'])
        follow_native(sample['clockJoin']['nativeAfter'],world['clockJoin']['nativeBefore'])
        for key,module in (('storage',storage),('reader',reader)):
            packet=sample['originals'][key]
            module.validate(packet,dict(schemaVersion=1,action=module.ACTION,commandId=packet['requestId'],runId=storages.run),storages.pid,
                previous=old['originals'][key])
        parent=sample['originals']['reader'];processing_parent=process['originals']['reader']
        reader.validate(parent,dict(schemaVersion=1,action=reader.ACTION,commandId=parent['requestId'],runId=storages.run),storages.pid,
            previous=processing_parent)
        need(same(signature(parent['source']),signature(processing_parent['source'])))
        observations.append(closed(sample['originals']['storage'],parent,base_observation['taskIds']))
        frames.append(sample);old=sample
    first,last=frames[0],frames[-1]
    need(last['clockJoin']['hostBeforeMonotonic']-first['clockJoin']['hostAfterMonotonic']>=3
        and last['clockJoin']['hostBeforeEpochMs']-first['clockJoin']['hostAfterEpochMs']>=3000
        and last['clockJoin']['nativeBefore']['capturedEpochMs']-first['clockJoin']['nativeAfter']['capturedEpochMs']>=3000
        and last['originals']['storage']['source']['clock']['monotonicMs']-first['originals']['storage']['source']['clock']['monotonicMs']>=3000)
    for row in frames[1:]:need(same(signature(first['originals']['storage']['source']),signature(row['originals']['storage']['source'])))
    inspect_storage(directory,list(directory.iterdir()));need(paths=={p.name for p in directory.iterdir() if owned_prefix(p.name)})
    for child in (owner,owner.sources,scene,images,processes,storages):need(same(child.store.read(),child.previous))
    return dict(assetImageStorageLifecycleVersion=1,runId=storages.run,binding=deepcopy(storages.binding),
        entityId=base['entityId'],readerId=base['readerId'],removalCommandId=base['removalCommandId'],processingLifecycle=base,
        baselineOriginals=deepcopy(baseline),sourceOriginals=deepcopy(pairs),observations=observations,
        observedRunnableDestructorAndDeallocationEdgesClosed=True,byteCopyCompletionAvailable=False,
        poolCompletionAvailable=False,decoderCompletionAvailable=False,gpuCompletionAvailable=False,resourceRetirementAvailable=False)
