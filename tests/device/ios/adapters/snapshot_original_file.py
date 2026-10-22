"""Join immutable actual byte chunks, stable manifests and real file-job death.

The returned bytes are private input to image/artifact validation. This does not
claim a capture, displayed image, Photos/Share/upload outcome or whole cleanup.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_feature_observation import need
from adapters.script_feature.history import same
from ios.adapters.snapshot_chunk_owner import SnapshotChunk
from ios.adapters.snapshot_manifest import SnapshotManifest
from ios.adapters import snapshot_chunks as chunks,snapshot_file_work as work


def original(before,after,owners,file_work):
    need(type(before) is SnapshotManifest and type(after) is SnapshotManifest and before.index<after.index
        and type(owners) is list and 1<=len(owners)<=1024 and all(type(owner) is SnapshotChunk for owner in owners))
    for owner in [after]+owners:
        need(same(owner.binding,before.binding) and owner.run==before.run and owner.role==before.role and owner.pid==before.pid
            and owner.store.path.parent==before.store.path.parent and owner.lock.path==before.lock.path)
    need([owner.index for owner in owners]==list(range(owners[0].index,owners[0].index+len(owners))))
    first,last=before.historical(),after.historical();parts=[owner.historical() for owner in owners]
    need(first['query']['prefix']==last['query']['prefix'] and same(first['packet']['files'],last['packet']['files']))
    names={part['query']['name'] for part in parts};need(len(names)==1)
    rows=[row for row in first['packet']['files'] if row['name'] in names];need(len(rows)==1);row=rows[0]
    frames=[first]+parts+[last];queries=[];previous=None;clock_nonces=set()
    for frame in frames:
        query,packet,join=frame['query'],frame['packet'],frame['clockJoin'];queries.append(query)
        for clock in (join['nativeBefore'],join['nativeAfter']):
            need(clock['requestId'] not in clock_nonces);clock_nonces.add(clock['requestId'])
            if previous is not None:
                need(clock['instance']==previous['instance'] and clock['sequence']>previous['sequence']
                    and clock['capturedEpochMs']>=previous['capturedEpochMs']
                    and all(clock['lifecycle'][key]>=value for key,value in previous['lifecycle'].items()))
            previous=clock
    need(len({query['commandId'] for query in queries})==len(queries))
    work.original(file_work);need(file_work['processId']==before.pid and file_work['runId']==before.run
        and file_work['clockBefore']['epochMs']>=last['clockJoin']['nativeAfter']['capturedEpochMs'])
    work.drained(file_work,queries)
    for frame in frames:
        jobs=[job for job in file_work['source']['jobs'] if same(job['query'],frame['query'])];need(len(jobs)==1)
        job=jobs[0];need(job['enteredEpochMs']<=frame['packet']['sampleEpochMs']<=job['publishedEpochMs'])
    raw=chunks.original_bytes(row,first['query']['prefix'],[dict(query=part['query'],packet=part['packet']) for part in parts],before.pid)
    fact=dict(iosSnapshotOriginalFileVersion=1,binding=deepcopy(before.binding),runId=before.run,role=before.role,
        processId=before.pid,prefix=first['query']['prefix'],file=deepcopy(row),beforeManifest=before.index,afterManifest=after.index,
        chunks=[owner.index for owner in owners],queryIds=[query['commandId'] for query in queries],
        fileWork=dict(instance=file_work['instance'],sequence=file_work['sequence']),
        imageOutcomeRequired=True,destinationOutcomeRequired=True,quietWindowRequired=True)
    return fact,raw
