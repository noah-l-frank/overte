"""Actual new rebake of an existing pinned mapping, never a UI status verdict.

This separate predicate leaves first-upload bake admission unchanged. A quiet
existing mapping baseline, actual new work and current output are all required.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters import asset_backend_evidence as evidence,asset_backend_source as source,asset_backend_work as work
from adapters.native_feature_observation import need
from adapters.script_feature.history import same

VERSION=1


def ready(baseline,baseline_query,current,current_query,config,path,original_hash):
    before=evidence.original(baseline,baseline_query,config);after=evidence.original(current,current_query,config);source.accept(before,after)
    source.path(path);source.digest(original_hash);run=current_query['runId']
    need(path.startswith(('/e2e-'+run+'/', '/renamed-'+run+'/')) and path.rsplit('.',1)[-1] in after['source']['bakeableModelExtensions'])
    if not all(evidence.ready_source(packet) for packet in (before,after)):return None
    if any(not work.drained(packet['source'][key]) for packet in (before,after) for key in ('workBefore','workAfter')):return None
    if evidence.mapping(before).get(path)!=original_hash or evidence.mapping(after).get(path)!=original_hash:return None
    old_files,new_files=evidence.blobs(before),evidence.blobs(after)
    if original_hash not in old_files or original_hash not in new_files:return None
    if not same(old_files[original_hash],new_files[original_hash]):return None
    original=source.file(new_files[original_hash],name=original_hash,limit=32768,required=True)
    if not original:return None
    old={row['id'] for row in before['source']['workAfter']['jobs']};floor=before['source']['workAfter']['clock']
    jobs=[row for row in after['source']['workAfter']['jobs'] if row['id'] not in old and row['kind']=='bake'
        and row['inputs']['path']==path and row['inputs']['hash']==original_hash]
    if len(jobs)!=1 or not evidence.task_returned(jobs[0]) or any(jobs[0]['created'][key]<floor[key] for key in floor):return None
    prefix=after['source']['hiddenPrefix']+original_hash+'/'
    meta=[row for row in after['source']['meta'] if row['originalHash']==original_hash and row['mappingPath']==prefix+'meta.json']
    if len(meta)!=1 or meta[0]['decoded'] is None:return None
    actual=meta[0]['decoded']
    if actual['bakeVersion']!=after['source']['modelBakeVersion'] or actual['failedLastBake'] or actual['lastBakeErrors']:return None
    output=actual['redirectTarget'] or prefix+after['source']['modelOutputName'];source.path(output)
    if not output.startswith(prefix):return None
    output_hash=evidence.mapping(after).get(output)
    if output_hash in (None,original_hash) or output_hash not in new_files:return None
    raw=source.file(new_files[output_hash],name=output_hash,limit=32768,required=True)
    if not raw:return None
    return dict(assetBackendRebakeProofVersion=VERSION,baselineRequestId=before['requestId'],requestId=after['requestId'],jobId=jobs[0]['id'],path=path,
        originalHash=original_hash,metaHash=meta[0]['blobHash'],outputPath=output,outputHash=output_hash,outputBytes=len(raw))
