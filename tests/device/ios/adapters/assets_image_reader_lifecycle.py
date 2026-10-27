"""Actual Queue/Source1/H5 originals after normal removal; no whole retirement.

Pure join only: no query, input, write, timestamp, eviction or process/SDK close.
Derived marker and weak-group expiry never stand for base/pool/GPU completion.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import exact,need
from adapters.script_feature.history import same
from ios.adapters import assets_image_reader_queue as queue,assets_image_reader as reader,assets_texture_ownership as texture
from ios.adapters import assets_texture_release as release,assets_geometry_release as geometry
from ios.adapters.assets_image_reader_lifecycle_sources import AssetsImageReaderLifecycleSources
from ios.adapters.assets_scene_sources import AssetsSceneSources
from ios.adapters.graphics_history import follow_native
from ios.adapters.assets_image_reader_lifecycle_ownership import inspect_lifecycles,owned_prefix

VERSION=1


def linked_closed(packet,parent,origin,reader_id):
    """Complete actual selected-task/receiver set, including never-dispatched tasks."""
    linked=queue.texture_links(packet,parent,origin,reader_id);history=packet['source'];source1=parent['source']
    # The later actual Source1 original may contain new tasks/dispatches. Such
    # work is not silently omitted from a final sample's earlier queue prefix.
    need([row['taskId'] for row in history['taskTextureSources']]==[row['id'] for row in source1['tasks']]
        and [row['receiverId'] for row in history['receiverTextureSources']]==[row['id'] for row in source1['receivers']])
    # Every weak owner is positively compared with the exact H5 revision by
    # texture_links, including foreign tasks and receivers without dispatches.
    tasks={row['id']:row for row in source1['tasks']};wanted=set(linked['taskIds']);resources=set(linked['resourceIds'])
    entries={row['dispatchId']:row for row in linked['entries']}
    dispatches={row['id']:row for row in source1['dispatches'] if row['taskId'] in wanted}
    need(set(entries)==set(dispatches))
    for id_ in wanted:
        task=tasks[id_]
        need(all(task[key] is not None for key in ('constructorReturned','runEntered','readEntered','readReturned','runReturned'))
            and task['readUnwound'] is None and task['runUnwound'] is None
            and all(task[key] is False for key in ('derivedMarkerAlive','originalLeaseAlive','resourceObjectAlive','sourceOwnersAlive')))
    receivers={row['id']:row for row in source1['receivers'] if row['resourceId'] in resources}
    covered=set();queued=[];direct=[];rejected=[]
    for id_,dispatch in dispatches.items():
        row=entries[id_]
        need(dispatch['gpuKnown'] and dispatch['invokeReturned'] is not None and row['invokeReturned'] is not None
            and dispatch['gpuOwnersAlive'] is False and row['receiverObjectAlive'] is False)
        if row['eventId'] is not None:
            need(row['argumentValuesDestroyed'] is not None);queued.append(row['eventId'])
            if row['receiverId'] is None:
                need(row['deliveryEntered'] is None and row['deliveryReturned'] is None and row['deliveryUnwound'] is None)
            else:
                need(row['deliveryReturned'] is not None and row['deliveryUnwound'] is None
                    and row['receiverReturned'] is not None and row['receiverUnwound'] is None
                    and row['receiverId'] in receivers)
                covered.add(row['receiverId'])
        elif dispatch['invokeAccepted'] is False:
            need(row['invokeAccepted'] is False);rejected.append(id_)
        else:
            # Null queued metadata alone has no authority. Actual Source1's
            # synchronous native scope must identify and finish the direct call.
            matches=[value for value in receivers.values() if value['dispatchId']==id_
                and value['attribution']=='synchronous-invoke-scope']
            need(len(matches)==1 and row['invokeAccepted']);covered.add(matches[0]['id']);direct.append(id_)
    need(covered==set(receivers))
    for row in receivers.values():
        need(row['gpuKnown'] and row['sourceKnown'] and row['returned'] is not None and row['unwound'] is None
            and row['gpuOwnersAlive'] is False and row['sourceOwnersAlive'] is False)
    need(queued) # No invented argument-destruction proof from an empty/direct-only table.
    return dict(**linked,queuedEventIds=sorted(queued),directDispatchIds=sorted(direct),rejectedDispatchIds=sorted(rejected),
        receiverIds=sorted(covered),observedDerivedMarkersAndQtArgumentCopiesGone=True,
        allObservedGpuSharingOwnersGone=True,decoderCompletionAvailable=False,destructorCompletionAvailable=False,
        gpuCompletionAvailable=False,resourceRetirementAvailable=False)


def frame(owner,reference):
    need(reference in owner.state['frames']);original=owner.originals.expand(reference)
    value=owner.originals.read(original);owner.frame(value);return value


def queue_signature(history):
    # Preserve every body/weak/identity fact while excluding only the sampled
    # clocks in their own three independent domains, never retiming a phase.
    value=deepcopy(history);value.pop('clock')
    value['source1TextureReference'].pop('clock');value['originTextureReference'].pop('clock')
    return value


def reader_signature(history):
    return {key:deepcopy(value) for key,value in history.items() if key!='clock'}


def compose(owner,scene,images,baseline,pairs):
    """Guard current journals/actual original files, then pure normal-Delete join."""
    need(isinstance(scene,AssetsSceneSources) and isinstance(images,AssetsImageReaderLifecycleSources)
        and images.lock is scene.lock is owner.lock and images.store.path.parent==scene.store.path.parent==owner.store.path.parent
        and images.run==scene.run and same(images.binding,scene.binding)
        and type(pairs) is list and 3<=len(pairs)<=8)
    owner.lock.assert_held()
    directory=images.store.path.parent
    own_paths={path.name for path in directory.iterdir() if owned_prefix(path.name)}
    report=inspect_lifecycles(directory,list(directory.iterdir()))
    need(any(row['runId']==images.run and same(row['binding'],images.binding)
        and row['responsibilities']==['image-reader-resource-retirement'] for row in report))
    for child in (images,scene):
        need(child.previous is not None and same(child.store.read(),child.previous)
            and same(child.decode(child.previous),child.state) and child.state['pending'] is None and child.raws.pending is None)
    need(not images.state['interrupted']) # Unknown historical reads never become end authority.
    exact(baseline,{'image','scene'})
    for pair in pairs:exact(pair,{'image','scene'})
    need(pairs[-1]['image']==images.state['frames'][-1] and pairs[-1]['scene']==scene.state['frames'][-1])
    scene_refs=[pair['scene'] for pair in pairs]
    model=release.compose(owner,scene,scene_refs)
    normal_before=owner.frame(owner.state['baseline'])['clockJoin']
    normal_home=owner.frame(owner.state['contextClosedBy'])['clockJoin']
    before=frame(images,baseline['image'])['sample'];before_scene=frame(scene,baseline['scene'])['scene']
    need(before_scene['originals']['origin']['source']['history']['assetModelOriginHistoryVersion']==5
        and before['clockJoin']['hostAfterMonotonic']<=before_scene['clockJoin']['hostBeforeMonotonic'])
    initial=queue.texture_links(before['originals']['queue'],before['originals']['reader'],
        before_scene['originals']['origin'],model['readerId'])
    need(any(row['entityId']==model['entityId'] and row['present'] and row['loaded'] and row['addedToScene'] and not row['failed']
        for row in before_scene['originals']['origin']['source']['models'])
        and before_scene['clockJoin']['hostAfterMonotonic']<=normal_before['hostBeforeMonotonic']
        and before_scene['clockJoin']['hostAfterEpochMs']<=normal_before['hostBeforeEpochMs'])
    follow_native(before_scene['clockJoin']['nativeAfter'],normal_before['nativeBefore'])
    positive=texture.consumers(before_scene['originals']['origin'],model['readerId'])
    need(any(row['kind']=='source' and row['strongOwnersAlive'] for row in positive['nodes']))
    image_frames=[];scene_frames=[];observations=[];previous=before
    for pair in pairs:
        sample=frame(images,pair['image'])['sample'];world=frame(scene,pair['scene'])['scene']
        need(sample['clockJoin']['hostBeforeMonotonic']>=previous['clockJoin']['hostAfterMonotonic']
            and sample['clockJoin']['hostAfterMonotonic']<=world['clockJoin']['hostBeforeMonotonic'])
        for key,module in (('queue',queue),('reader',reader)):
            packet=sample['originals'][key]
            module.validate(packet,dict(schemaVersion=1,action=module.ACTION,commandId=packet['requestId'],runId=images.run),images.pid,
                previous=previous['originals'][key])
        observed=linked_closed(sample['originals']['queue'],sample['originals']['reader'],world['originals']['origin'],model['readerId'])
        need(observed['historyInstance']==initial['historyInstance'] and observed['bodySha256']==model['bodySha256']
            and observed['bodyBytes']==model['bodyBytes'] and set(initial['sourceIds'])<=set(observed['sourceIds'])
            and set(initial['taskIds'])<=set(observed['taskIds']))
        image_frames.append(sample);scene_frames.append(world);observations.append(observed);previous=sample
    first,last=image_frames[0],image_frames[-1]
    need(normal_home['hostAfterMonotonic']<=first['clockJoin']['hostBeforeMonotonic']
        and normal_home['hostAfterEpochMs']<=first['clockJoin']['hostBeforeEpochMs'])
    follow_native(normal_home['nativeAfter'],first['clockJoin']['nativeBefore'])
    need(last['clockJoin']['hostBeforeMonotonic']-first['clockJoin']['hostAfterMonotonic']>=3
        and last['clockJoin']['hostBeforeEpochMs']-first['clockJoin']['hostAfterEpochMs']>=3000
        and last['clockJoin']['nativeBefore']['capturedEpochMs']-first['clockJoin']['nativeAfter']['capturedEpochMs']>=3000)
    a,b=first['originals'],last['originals']
    need(b['queue']['source']['clock']['monotonicMs']-a['queue']['source']['clock']['monotonicMs']>=3000
        and b['reader']['source']['clock']['monotonicMs']-a['reader']['source']['clock']['monotonicMs']>=3000)
    for sample in image_frames[1:]:
        need(same(queue_signature(a['queue']['source']),queue_signature(sample['originals']['queue']['source']))
            and same(reader_signature(a['reader']['source']),reader_signature(sample['originals']['reader']['source'])))
    for child in (owner,owner.sources,scene,images):need(same(child.store.read(),child.previous))
    inspect_lifecycles(directory,list(directory.iterdir()))
    need(own_paths=={path.name for path in directory.iterdir() if owned_prefix(path.name)})
    return dict(assetImageReaderResourceLifecycleVersion=VERSION,runId=images.run,binding=deepcopy(images.binding),
        entityId=model['entityId'],readerId=model['readerId'],bodySha256=model['bodySha256'],bodyBytes=model['bodyBytes'],
        removalCommandId=model['removalCommandId'],textureRelease=model,baselineOriginals=deepcopy(baseline),sourceOriginals=deepcopy(pairs),
        observations=observations,observedImageReaderLifecycleEdgesClosed=True,
        eventStorageCompletionAvailable=False,byteCopyCompletionAvailable=False,basePoolCompletionAvailable=False,
        decoderCompletionAvailable=False,destructorCompletionAvailable=False,gpuCompletionAvailable=False,resourceRetirementAvailable=False)
