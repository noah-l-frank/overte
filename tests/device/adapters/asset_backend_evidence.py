"""Backend evidence predicates, never an input or complete feature verdict.

Every fact is decoded from exact producer originals. The owning journey must
still join normal input, current device/process guards and retained ownership.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from adapters import asset_backend_client as client,asset_backend_source as source,asset_backend_work as work
from adapters.native_feature_observation import need
from adapters.script_feature.history import same

VERSION=1
QUIET_MS=3000


def original(value,query,config):return client.export(value,query,config)


def ready_source(packet):
    value=packet['source'];return value['available'] and value['complete'] and all(value[key]['available'] and value[key]['complete'] for key in ('workBefore','workAfter'))


def mapping(packet):return {row['path']:row['hash'] for row in packet['source']['memoryMappings']}


def blobs(packet):return {row['name']:row for row in packet['source']['blobs']}


def task_returned(row):
    return (row['runEntered']==row['runReturned']==1 and row['callbackEntered']==row['callbackReturned']==1 and row['pendingRuns']==row['pendingBodies']==0
        and row['leaseAlive'] is False and row['ownerKnown'] and row['ownerAlive'] is False and row['objectAlive'] is False
        and [event['details']['callback'] for event in row['events'] if event['kind']=='callback-enter']==['bake-complete'])


def bake_ready(baseline,baseline_query,current,current_query,config,path,original_hash):
    """A new actual Bake run plus readable current meta/output, or None.

    This proves neither model parsing/rendering nor Add to World. The expected
    original hash must separately join the ordinary upload's retained bytes.
    """
    before=original(baseline,baseline_query,config);after=original(current,current_query,config);source.accept(before,after)
    source.path(path);source.digest(original_hash);run=current_query['runId']
    need(path.startswith(('/e2e-'+run+'/', '/renamed-'+run+'/')) and path.rsplit('.',1)[-1] in after['source']['bakeableModelExtensions'])
    if not ready_source(before) or not ready_source(after):return None
    if path in mapping(before) or mapping(after).get(path)!=original_hash:return None
    old={row['id'] for row in before['source']['workAfter']['jobs']};floor=before['source']['workAfter']['clock']
    jobs=[row for row in after['source']['workAfter']['jobs'] if row['id'] not in old and row['kind']=='bake'
        and row['inputs']['path']==path and row['inputs']['hash']==original_hash and all(row['created'][key]>=floor[key] for key in floor) and task_returned(row)]
    if len(jobs)!=1:return None
    prefix=after['source']['hiddenPrefix']+original_hash+'/'
    meta=[row for row in after['source']['meta'] if row['originalHash']==original_hash and row['mappingPath']==prefix+'meta.json']
    if len(meta)!=1 or meta[0]['decoded'] is None:return None
    actual=meta[0]['decoded']
    if actual['bakeVersion']!=after['source']['modelBakeVersion'] or actual['failedLastBake'] or actual['lastBakeErrors']:return None
    output=actual['redirectTarget'] or prefix+after['source']['modelOutputName'];source.path(output)
    if not output.startswith(prefix):return None
    output_hash=mapping(after).get(output);files=blobs(after)
    if output_hash in (None,original_hash) or output_hash not in files or original_hash not in files:return None
    raw=source.file(files[output_hash],name=output_hash,limit=32768,required=True)
    if not raw or source.file(files[original_hash],name=original_hash,limit=32768,required=True) is None:return None
    return dict(assetBackendBakeProofVersion=VERSION,baselineRequestId=before['requestId'],requestId=after['requestId'],jobId=jobs[0]['id'],path=path,
        originalHash=original_hash,metaHash=meta[0]['blobHash'],outputPath=output,outputHash=output_hash,outputBytes=len(raw))


def restored(baseline,baseline_query,first,first_query,last,last_query,config):
    """Exact foreign/baseline restoration and two independent quiet durations.

    No mapping/blob is deleted here. Shared baseline hashes and hidden mappings
    must survive with original identities; every newly introduced blob must be
    gone. The owning journal still needs fresh current guards before retiring.
    """
    admitted=original(baseline,baseline_query,config);start=original(first,first_query,config);end=original(last,last_query,config)
    source.accept(admitted,start);source.accept(start,end);run=first_query['runId'];prefixes=('/e2e-'+run+'/', '/renamed-'+run+'/')
    need(not any(path.startswith(prefixes) for path in mapping(admitted)))
    if not all(ready_source(packet) for packet in (admitted,start,end)):return None
    baseline_map,baseline_blobs=mapping(admitted),blobs(admitted)
    # Unknown baseline bytes are never a proof that foreign content survived.
    if any(source.file(row,name=name,limit=32768,required=True) is None for name,row in baseline_blobs.items()):return None
    if any(row['decoded'] is None for row in admitted['source']['meta']):return None
    for packet in (start,end):
        if mapping(packet)!=baseline_map or not same(blobs(packet),baseline_blobs) or not same(packet['source']['meta'],admitted['source']['meta']):return None
    sources=[packet['source'][key] for packet in (admitted,start,end) for key in ('workBefore','workAfter')]
    if not all(work.drained(value) for value in sources):return None
    quiet_sources=sources[2:]
    if not all(same(value['jobs'],quiet_sources[0]['jobs']) for value in quiet_sources[1:]):return None
    native_ms=end['source']['workBefore']['clock']['monotonicMs']-start['source']['workAfter']['clock']['monotonicMs']
    host_ms=last['hostBefore']['hostMonotonicMs']-first['hostAfter']['hostMonotonicMs']
    if native_ms<QUIET_MS or host_ms<QUIET_MS:return None
    return dict(assetBackendRestorationProofVersion=VERSION,baselineRequestId=admitted['requestId'],firstRequestId=start['requestId'],lastRequestId=end['requestId'],
        nativeQuietMs=native_ms,hostQuietMs=host_ms,mappings=len(baseline_map),blobs=len(baseline_blobs),jobs=len(quiet_sources[0]['jobs']))
