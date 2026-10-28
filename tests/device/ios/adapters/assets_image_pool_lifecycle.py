"""Pure selected admission/slot/run/delete/scope closure; global pool stays open."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import exact,need
from adapters.script_feature.history import same
from ios.adapters import assets_image_reader as reader,assets_image_reader_storage as storage,assets_image_reader_pool as pool
from ios.adapters import assets_image_reader_lifecycle as image_lifecycle,assets_image_storage_lifecycle as storage_lifecycle
from ios.adapters.assets_image_pool_sources import AssetsImageReaderPoolSources
from ios.adapters.assets_image_pool_ownership import inspect_pool,owned_prefix
from ios.adapters.graphics_history import follow_native

VERSION=1


def ordered(a,b):
    need(a['epochMs']<=b['epochMs'] and pool.u64(a['steadyNs'])<=pool.u64(b['steadyNs']))


def one(events,kind):
    rows=[row for row in events if row['kind']==kind];need(len(rows)==1);return rows[0]


def chain(rows):
    need(len({row['threadSlotId'] for row in rows})==1)
    for before,after in zip(rows,rows[1:]):ordered(before,after)


def selected_admission(q,registration,allocation):
    rid=registration['id'];events=[row for row in q['events'] if row['registrationId']==rid]
    register,retire=one(events,3),one(events,4);ordered(register,retire)
    need(not registration['live'] and allocation['deleteEntered'] is not None and allocation['deleteReturned'] is not None
        and allocation['deleteEntered']['epochMs']<=retire['epochMs']<=allocation['deleteReturned']['epochMs'])
    admissions=[row for row in q['admissions'] if row['registrationId']==rid];need(len(admissions)==1);admission=admissions[0]
    aid,pid=admission['id'],admission['poolId'];created=one([row for row in q['events'] if row['poolId']==pid],1)
    actual=[row for row in events if row['admissionId']==aid]
    entered=one(actual,admission['operation']);returned=one(actual,pool.ROOTS[admission['operation']][0])
    need(not any(row['kind'] in (7,10,13,19,23,27,30) for row in events));chain([entered,returned]);ordered(register,entered);ordered(created,entered)
    need(not any(row['admissionId'] not in (0,aid) for row in events))
    queued={row['slotId']:row for row in actual if row['kind']==14};removed={row['slotId']:row for row in actual if row['kind']==15}
    need(len(queued)==sum(row['kind']==14 for row in actual) and len(removed)==sum(row['kind']==15 for row in actual)
        and set(queued)==set(removed))
    for sid,event in queued.items():ordered(entered,event);ordered(event,removed[sid])
    takes={};matches={}
    for row in events:
        if row['kind'] in (28,29,30,31):takes.setdefault(row['operationId'],[]).append(row)
    for oid,operation in takes.items():
        take_start=one(operation,28);take_end=one(operation,29);chain([take_start,take_end]);ordered(register,take_start)
        found=[row for row in operation if row['kind']==31]
        if take_end['flags']:
            need(len(found)==1);match=found[0]
            need(match['admissionId']==take_end['admissionId']==aid and match['slotId'] in removed
                and removed[match['slotId']]['flags']==3 and match['slotId'] not in matches)
            chain([take_start,removed[match['slotId']],match,take_end]);matches[match['slotId']]=take_end
        else:need(not found and take_end['admissionId']==0)
    need(set(matches)=={sid for sid,event in removed.items() if event['flags']==3})
    workers=[row for row in actual if row['kind']==16];runs=[row for row in actual if row['kind']==17]
    cancellations=[row for row in actual if row['kind']==24]
    worker_slots=any(row['flags']==1 for row in removed.values());cancel_slots=any(row['flags']==2 for row in removed.values())
    if not returned['flags']:
        need(admission['operation']==8 and not queued and not workers and not runs and not cancellations and not matches)
        outcome='try-start-declined-storage-independently-deallocated'
    elif runs:
        need(len(runs)==1 and not cancellations and not cancel_slots);run=runs[0]
        need(run['flags'] in (3,5));path=run['flags']>>1
        run_return=one(actual,18);deleting=one(actual,20);deleted=one(actual,21);iteration=one(actual,22)
        chain([run,run_return,deleting,retire,deleted,iteration]);ordered(entered,run)
        need(deleting['epochMs']<=allocation['deleteEntered']['epochMs'] and allocation['deleteReturned']['epochMs']<=deleted['epochMs'])
        if path==1:
            need(len(workers)==1 and not matches);ordered(workers[0],run)
            need(not any(row['flags']==3 for row in removed.values()))
            for event in removed.values():
                if event['flags']==1:ordered(event,workers[0])
        else:
            need(path==2 and not workers and not worker_slots and len(matches)==1)
            chain([next(iter(matches.values())),run])
        outcome='worker-iteration-returned' if path==1 else 'stolen-iteration-returned'
    elif cancellations:
        need(len(cancellations)==1 and cancel_slots and not workers and not worker_slots and not matches)
        deleted=one(actual,25);scope=one(actual,26);chain([cancellations[0],retire,deleted,scope])
        for event in removed.values():
            if event['flags']==2:chain([event,cancellations[0]])
        need(cancellations[0]['epochMs']<=allocation['deleteEntered']['epochMs'] and allocation['deleteReturned']['epochMs']<=deleted['epochMs'])
        outcome='clear-cancel-delete-scope-returned'
    else:
        # A successful public tryTake transfers ownership. Actual independent
        # Storage deallocation closes that transfer; slot removal alone cannot.
        need(not workers and not worker_slots and not cancel_slots and len(matches)==1)
        transferred=next(iter(matches.values()));ordered(transferred,retire)
        outcome='try-take-transfer-independently-deallocated'
    pool_ends=[row for row in q['events'] if row['kind']==2 and row['poolId']==pid]
    if pool_ends:
        for event in actual:ordered(event,pool_ends[0])
    # Promotion alone never constitutes an outcome: it has to lead to a closed
    # run, clear-delete, transfer, or a declined tryStart with no queue at all.
    return dict(registrationId=rid,allocationId=allocation['id'],admission=deepcopy(admission),
        outcome=outcome,slotIds=sorted(queued),events=deepcopy(events))


def closed(packet,storage_packet,parent,selected_tasks):
    source=pool.parent_links(packet,storage_packet,parent);q=source['qt']
    need(source['complete'] and q['healthy'] and q['cutComplete'] and q['inFlight']==0)
    base=storage_lifecycle.closed(storage_packet,parent,selected_tasks)
    allocation_by_task={row['taskId']:row for row in storage_packet['source']['allocations'] if row['taskId']}
    bindings={row['taskId']:row for row in source['bindings']};actual={row['id']:row for row in parent['source']['tasks']}
    need(set(bindings)==set(actual)==set(allocation_by_task))
    regs={row['id']:row for row in q['registrations']};need(set(regs)=={row['registrationId'] for row in bindings.values()})
    observations=[]
    for task in selected_tasks:
        binding=bindings[task];reg=regs[binding['registrationId']];allocation=allocation_by_task[task]
        need(reg['allocationId']==binding['allocationId']==allocation['id'])
        observations.append(selected_admission(q,reg,allocation))
    return dict(taskIds=list(selected_tasks),allocationIds=base['allocationIds'],observations=observations,
        observedSelectedRunnablePoolEdgesClosed=True,byteCopyCompletionAvailable=False,globalPoolCompletionAvailable=False,
        decoderCompletionAvailable=False,gpuCompletionAvailable=False,resourceRetirementAvailable=False)


def signature(value):
    result=deepcopy(value);result.pop('clock',None)
    for key in ('epochMs','steadyNs','mutationSerial','inFlight'):result['qt'].pop(key,None)
    return result


def compose(owner,scene,images,processes,storages,pools,baseline,pairs):
    need(isinstance(pools,AssetsImageReaderPoolSources) and pools.lock is storages.lock is processes.lock is images.lock is scene.lock is owner.lock
        and pools.store.path.parent==storages.store.path.parent and pools.run==storages.run and same(pools.binding,storages.binding)
        and type(pairs) is list and 3<=len(pairs)<=8)
    exact(baseline,{'image','processing','storage','pool','scene'})
    for pair in pairs:exact(pair,{'image','processing','storage','pool','scene'})
    base=storage_lifecycle.compose(owner,scene,images,processes,storages,{key:baseline[key] for key in ('image','processing','storage','scene')},
        [{key:pair[key] for key in ('image','processing','storage','scene')} for pair in pairs])
    need(pools.previous is not None and same(pools.store.read(),pools.previous) and same(pools.decode(pools.previous),pools.state)
        and pools.state['pending'] is None and pools.raws.pending is None and not pools.state['interrupted']
        and pairs[-1]['pool']==pools.state['frames'][-1])
    directory=pools.store.path.parent;paths={p.name for p in directory.iterdir() if owned_prefix(p.name)}
    inspect_pool(directory,list(directory.iterdir()))
    previous=image_lifecycle.frame(pools,baseline['pool'])['sample'];before_storage=image_lifecycle.frame(storages,baseline['storage'])['sample']
    before_world=image_lifecycle.frame(scene,baseline['scene'])['scene']
    need(before_storage['clockJoin']['hostAfterMonotonic']<=previous['clockJoin']['hostBeforeMonotonic']
        and previous['clockJoin']['hostAfterMonotonic']<=before_world['clockJoin']['hostBeforeMonotonic'])
    follow_native(before_storage['clockJoin']['nativeAfter'],previous['clockJoin']['nativeBefore']);follow_native(previous['clockJoin']['nativeAfter'],before_world['clockJoin']['nativeBefore'])
    selected=base['observations'][0]['allocationIds'];positive={row['allocationId'] for row in previous['originals']['pool']['source']['bindings']}
    need(selected and set(selected)<=positive)
    frames=[];observations=[]
    for pair,base_observation in zip(pairs,base['observations']):
        storage_sample=image_lifecycle.frame(storages,pair['storage'])['sample'];sample=image_lifecycle.frame(pools,pair['pool'])['sample']
        world=image_lifecycle.frame(scene,pair['scene'])['scene']
        need(storage_sample['clockJoin']['hostAfterMonotonic']<=sample['clockJoin']['hostBeforeMonotonic']
            and sample['clockJoin']['hostAfterMonotonic']<=world['clockJoin']['hostBeforeMonotonic']
            and previous['clockJoin']['hostAfterMonotonic']<=sample['clockJoin']['hostBeforeMonotonic'])
        follow_native(storage_sample['clockJoin']['nativeAfter'],sample['clockJoin']['nativeBefore']);follow_native(sample['clockJoin']['nativeAfter'],world['clockJoin']['nativeBefore'])
        for key,module in (('pool',pool),('storage',storage),('reader',reader)):
            packet=sample['originals'][key];module.validate(packet,dict(schemaVersion=1,action=module.ACTION,commandId=packet['requestId'],runId=pools.run),pools.pid,previous=previous['originals'][key])
        for key,module in (('storage',storage),('reader',reader)):
            newer,older=sample['originals'][key],storage_sample['originals'][key]
            module.validate(newer,dict(schemaVersion=1,action=module.ACTION,commandId=newer['requestId'],runId=pools.run),pools.pid,previous=older)
            need(same(storage_lifecycle.signature(newer['source']),storage_lifecycle.signature(older['source'])))
        tasks=[row['taskId'] for row in storage_sample['originals']['storage']['source']['allocations'] if row['id'] in base_observation['allocationIds']]
        observations.append(closed(sample['originals']['pool'],sample['originals']['storage'],sample['originals']['reader'],tasks))
        frames.append(sample);previous=sample
    first,last=frames[0],frames[-1]
    need(last['clockJoin']['hostBeforeMonotonic']-first['clockJoin']['hostAfterMonotonic']>=3
        and last['clockJoin']['hostBeforeEpochMs']-first['clockJoin']['hostAfterEpochMs']>=3000
        and last['clockJoin']['nativeBefore']['capturedEpochMs']-first['clockJoin']['nativeAfter']['capturedEpochMs']>=3000
        and pool.u64(last['originals']['pool']['source']['qt']['steadyNs'])-pool.u64(first['originals']['pool']['source']['qt']['steadyNs'])>=3000000000)
    for row in frames[1:]:need(same(signature(first['originals']['pool']['source']),signature(row['originals']['pool']['source'])))
    inspect_pool(directory,list(directory.iterdir()));need(paths=={p.name for p in directory.iterdir() if owned_prefix(p.name)})
    for child in (owner,owner.sources,scene,images,processes,storages,pools):need(same(child.store.read(),child.previous))
    return dict(assetImagePoolLifecycleVersion=1,runId=pools.run,binding=deepcopy(pools.binding),entityId=base['entityId'],
        readerId=base['readerId'],removalCommandId=base['removalCommandId'],storageLifecycle=base,baselineOriginals=deepcopy(baseline),
        sourceOriginals=deepcopy(pairs),observations=observations,observedSelectedRunnablePoolEdgesClosed=True,
        byteCopyCompletionAvailable=False,globalPoolCompletionAvailable=False,decoderCompletionAvailable=False,
        gpuCompletionAvailable=False,resourceRetirementAvailable=False)
