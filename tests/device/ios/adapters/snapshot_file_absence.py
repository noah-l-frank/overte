"""Fresh empty prefixes and original retired native file jobs, with quiet.

This is file-channel retirement only. Script, capture/render resources,
destinations, independent witnesses and paired feature cleanup remain required.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
from adapters.native_clock_join import digest
from adapters.native_feature_observation import exact,need,number
from adapters.script_feature.history import same
from ios.adapters.snapshot_manifest import SnapshotManifest,absent
from ios.adapters.snapshot_owned_packet import SnapshotOwnedPacket
from ios.adapters.snapshot_file_work_packet import SnapshotFileWorkPacket
from ios.adapters.snapshot_remove_owner import SnapshotRemoveOwner
from ios.adapters.emote_native_prefix import follow
from ios.adapters import snapshot_file_work as file_work,snapshot_owned_files as owned_files


def _bound(owner,first):
    need(owner.binding==first.binding and owner.run==first.run and owner.role==first.role
        and owner.store.path.parent==first.store.path.parent and owner.lock.path==first.lock.path)


def original_sample(manifests,work,owned,removals):
    need(type(manifests) is list and 1<=len(manifests)<=5 and all(type(v) is SnapshotManifest for v in manifests)
        and type(work) is SnapshotFileWorkPacket and type(owned) is SnapshotOwnedPacket
        and type(removals) is list and len(removals)<=128 and all(type(v) is SnapshotRemoveOwner for v in removals))
    first=manifests[0];first.lock.assert_held()
    for owner in [*manifests,work,owned,*removals]:_bound(owner,first)
    frames=[];last_native=None;nonces=set();prefixes=set();times=[];references=[]
    for owner in manifests:
        frame=owner.historical();q=frame['query'];prefix=q['prefix'];mode=prefix[len('parity-'+first.run[:16]+'-'):]
        absent(frame,owner.pid,first.run,mode);need(prefix not in prefixes and q['commandId'] not in nonces)
        prefixes.add(prefix);nonces.add(q['commandId']);frames.append(frame);span=frame['clockJoin']
        if last_native is not None:follow(last_native,span['nativeBefore'])
        last_native=span['nativeAfter'];times.append(span)
        references.append(dict(kind='manifest',index=owner.index,journalSha256=digest(owner.previous)))
    work_frame=work.historical();owned_frame=owned.historical();work.qualified();owned.qualified()
    for owner,frame,kind in ((work,work_frame,'file-work'),(owned,owned_frame,'owned')):
        need(frame['query']['commandId'] not in nonces);nonces.add(frame['query']['commandId'])
        span=frame['acquisition'];follow(last_native,span['nativeBefore']);last_native=span['nativeAfter'];times.append(span)
        references.append(dict(kind=kind,index=owner.index,journalSha256=digest(owner.previous)))
    work_packet,owned_packet=work_frame['packet'],owned_frame['packet']
    file_work.drained(work_packet,[f['query'] for f in frames])
    for frame in frames:
        jobs=[r for r in work_packet['source']['jobs'] if same(r['query'],frame['query'])];need(len(jobs)==1)
        job=jobs[0];need(job['queuedEpochMs']>=frame['clockJoin']['nativeBefore']['capturedEpochMs']
            and job['enteredEpochMs']<=frame['packet']['sampleEpochMs']<=job['publishedEpochMs'])
    source=owned_packet['source'];need(source['complete'] and prefixes=={r['prefix'] for r in source['prefixes']}
        and all(r['initiallyEmpty'] for r in source['prefixes']))
    proofs={}
    for owner in removals:
        proof=owner.proof();file_id=proof['query']['fileId'];need(file_id not in proofs);proofs[file_id]=proof
        observed=owner.owner(owner.state['observations'][-1]).historical()
        owned_files.validate(owned_packet,owned_frame['query'],first.pid,previous=observed['packet'])
        references.append(dict(kind='remove',index=owner.index,journalSha256=digest(owner.previous)))
    need(set(proofs)=={r['id'] for r in source['files']})
    for row in source['files']:
        proof=proofs[row['id']];need(row['prefix'] in prefixes and row['removeCommandId']==proof['query']['commandId'])
        owned_files.removed(owned_packet,proof['query'],first.pid)
    need(all(not row['alive'] and row['finallyEpochMs'] is not None and row['expiredEpochMs'] is not None for row in source['jobs']))
    before=times[0]['hostBeforeEpochMs'];mono_before=times[0]['hostBeforeMonotonic']
    after=times[-1]['hostAfterEpochMs'];mono_after=times[-1]['hostAfterMonotonic']
    need(0<=after-before<1500 and 0<=mono_after-mono_before<1.5
        and abs(after-before-(mono_after-mono_before)*1000)<=250)
    return dict(iosSnapshotFileAbsenceSampleVersion=1,binding=deepcopy(first.binding),runId=first.run,role=first.role,
        prefixes=sorted(prefixes),references=references,queries=[deepcopy(f['query']) for f in frames],
        hostBeforeEpochMs=before,hostAfterEpochMs=after,hostBeforeMonotonic=mono_before,hostAfterMonotonic=mono_after,
        nativeBefore=deepcopy(times[0]['nativeBefore']),nativeAfter=deepcopy(last_native),
        fileWork=deepcopy(work_packet),ownedFiles=deepcopy(owned_packet))


def sample(manifests,work,owned,removals,*,guard,epoch_ms,monotonic):
    need(all(callable(v) for v in (guard,epoch_ms,monotonic)) and guard() is not False)
    value=original_sample(manifests,work,owned,removals)
    need(guard() is not False);now,mono=epoch_ms(),monotonic()
    before,mono_before=value['hostBeforeEpochMs'],value['hostBeforeMonotonic']
    after,mono_after=value['hostAfterEpochMs'],value['hostAfterMonotonic']
    need(number(now,after,before+1500) and number(mono,mono_after,mono_before+1.5)
        and now-before<1500 and mono-mono_before<1.5 and abs(now-before-(mono-mono_before)*1000)<=250)
    return value


def quiet(groups,samples):
    need(type(groups) is list and type(samples) is list and len(samples)==len(groups)>=3)
    for group,value in zip(groups,samples):
        need(type(group) in (tuple,list) and len(group)==4 and same(original_sample(*group),value))
    fields={'iosSnapshotFileAbsenceSampleVersion','binding','runId','role','prefixes','references',
        'queries','hostBeforeEpochMs','hostAfterEpochMs','hostBeforeMonotonic','hostAfterMonotonic','nativeBefore','nativeAfter','fileWork','ownedFiles'}
    first=samples[0];last=samples[-1];nonces=set();previous=None;work_previous=owned_previous=None
    for value in samples:
        exact(value,fields);need(type(value['iosSnapshotFileAbsenceSampleVersion']) is int and value['iosSnapshotFileAbsenceSampleVersion']==1
            and all(same(value[k],first[k]) for k in ('binding','runId','role','prefixes')))
        pid=int(value['binding']['processIdentity']);work=value['fileWork'];owned=value['ownedFiles']
        file_work.validate(work,dict(schemaVersion=1,action=file_work.ACTION,commandId=work['requestId'],runId=value['runId']),pid,previous=work_previous)
        owned_files.validate(owned,dict(schemaVersion=1,action=owned_files.ACTION,commandId=owned['requestId'],runId=value['runId']),pid,previous=owned_previous)
        file_work.drained(work,value['queries'])
        if previous is not None:
            follow(previous['nativeAfter'],value['nativeBefore'])
            need(value['hostBeforeEpochMs']>=previous['hostAfterEpochMs'] and value['hostBeforeMonotonic']>=previous['hostAfterMonotonic'])
            need(same(owned['source'],previous['ownedFiles']['source']))
            old={r['id'] for r in previous['fileWork']['source']['jobs']}
            new=[r['query'] for r in work['source']['jobs'] if r['id'] not in old]
            need(sorted(new,key=lambda q:q['commandId'])==sorted(value['queries'],key=lambda q:q['commandId']))
        for q in value['queries']:need(q['commandId'] not in nonces);nonces.add(q['commandId'])
        previous=value;work_previous=work;owned_previous=owned
    utc=last['hostBeforeEpochMs']-first['hostAfterEpochMs'];mono=(last['hostBeforeMonotonic']-first['hostAfterMonotonic'])*1000
    need(utc>=3000 and mono>=3000 and abs(utc-mono)<=250)
    for key in ('fileWork','ownedFiles'):
        a,b=first[key]['clockAfter'],last[key]['clockBefore'];u=b['epochMs']-a['epochMs'];m=b['monotonicMs']-a['monotonicMs']
        need(u>=3000 and m>=3000 and abs(u-m)<=250)
    return dict(iosSnapshotFileAbsenceQuietVersion=1,binding=deepcopy(first['binding']),runId=first['runId'],role=first['role'],
        prefixes=deepcopy(first['prefixes']),samples=len(samples),sampleSha256=[digest(v) for v in samples],
        fileChannelQuietMilliseconds=3000,pairedFeatureCleanupRequired=True,scriptCaptureAndDestinationQuietRequired=True)
