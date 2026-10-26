"""Conditional native Share retirement and independent file/run observations."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import re
from adapters.native_feature_observation import decode,exact,integer,need
from adapters.script_feature.history import same
from ios.adapters.snapshot_destination import stamp
from ios.adapters.snapshot_share_query_owner import host_clock
from ios.adapters import snapshot_share_original as share


FILES=[('group','original.bytes'),('group','share-original.json'),('archive','original.bytes'),
    ('archive','original-extension.json'),('archive','import-intent.json'),('archive','import-original.json')]


def sha(raw):return hashlib.sha256(raw).hexdigest()


def intent(raw,imported):
    need(type(raw) is bytes);value=decode(raw.decode('utf-8'));need(type(value) is dict)
    expected={key:item for key,item in imported.items() if key not in {'clockAfter','originalMetadataSha256','byteCount','sha256'}}
    expected.update(phase='issued',artifactRevision=None);need(same(value,expected));return value


def original(value,nonce,imported,metadata,import_raw,intent_raw,*,receiver_bundle_id):
    receiver=share.imported_metadata(imported,metadata,pid=imported['processId'],bundle_id=imported['bundleId'],receiver_bundle_id=receiver_bundle_id)
    need(imported['iosSnapshotShareImportVersion']==2 and type(import_raw) is bytes and same(decode(import_raw.decode('utf-8')),imported));intent(intent_raw,imported)
    exact(value,{'snapshotShareRetirementVersion','runId','instance','processId','bundleId','clockDomain','originalMetadataSha256','importOriginalSha256',
        'groupRootIdentity','archiveRootIdentity','files','requestId','clockBefore','clockAfter','steps','complete','readersClosed'})
    need(type(value['snapshotShareRetirementVersion']) is int and value['snapshotShareRetirementVersion']==1
        and value['requestId']==nonce and type(nonce) is str and re.fullmatch('ios-[a-f0-9]{32}',nonce)
        and all(same(value[key],imported[key]) for key in ('runId','instance','processId','bundleId','clockDomain','groupRootIdentity','archiveRootIdentity'))
        and type(value['processId']) is int and value['originalMetadataSha256']==sha(metadata) and value['importOriginalSha256']==sha(import_raw)
        and type(value['complete']) is bool and type(value['readersClosed']) is bool and type(value['files']) is list and len(value['files'])==6
        and type(value['steps']) is list and len(value['steps'])<=8)
    stamp(value['clockBefore'],imported['clockAfter']);stamp(value['clockAfter'],value['clockBefore'])
    expected={('group','original.bytes'):(receiver['sha256'],receiver['byteCount'],receiver['artifactRevision']),
        ('archive','original.bytes'):(imported['sha256'],imported['byteCount'],imported['artifactRevision']),
        ('group','share-original.json'):(sha(metadata),len(metadata),None),('archive','original-extension.json'):(sha(metadata),len(metadata),None),
        ('archive','import-original.json'):(sha(import_raw),len(import_raw),None),('archive','import-intent.json'):(sha(intent_raw),len(intent_raw),None)}
    for row,(root,name) in zip(value['files'],FILES):
        exact(row,{'root','name','revision','sha256','byteCount'});digest,count,revision=expected[(root,name)]
        need(row['root']==root and row['name']==name and type(row['revision']) is str and re.fullmatch('[a-f0-9]{64}',row['revision'])
            and row['sha256']==digest and type(row['byteCount']) is int and row['byteCount']==count and (revision is None or row['revision']==revision))
    steps=[('unlink',root,name) for root,name in FILES]+[('rmdir',root,'snapshot-share-'+imported['runId']) for root in ('group','archive')]
    previous=value['clockBefore']
    for index,(row,(kind,root,name)) in enumerate(zip(value['steps'],steps),1):
        exact(row,{'sequence','kind','root','name','succeeded','clock'})
        need(type(row['sequence']) is int and row['sequence']==index and (row['kind'],row['root'],row['name'])==(kind,root,name)
            and type(row['succeeded']) is bool and (row['succeeded'] or index==len(value['steps'])))
        stamp(row['clock'],previous);previous=row['clock']
    stamp(value['clockAfter'],previous)
    if value['complete']:need(value['readersClosed'] and len(value['steps'])==8 and all(row['succeeded'] for row in value['steps']))
    return value


def observation(value,nonce,retire_nonce,imported,metadata,import_raw,intent_raw,*,receiver_bundle_id,previous=None):
    exact(value,{'snapshotShareRetirementObservationVersion','requestId','runId','processId','clockDomain','clockBefore','clockAfter','retirement',
        'groupRunAbsent','archiveRunAbsent','observationErrors'})
    need(type(value['snapshotShareRetirementObservationVersion']) is int and value['snapshotShareRetirementObservationVersion']==1
        and value['requestId']==nonce and type(nonce) is str and re.fullmatch('ios-[a-f0-9]{32}',nonce)
        and nonce!=retire_nonce
        and value['runId']==imported['runId'] and type(value['processId']) is int and value['processId']==imported['processId']
        and value['clockDomain']=='native-share-archive' and all(type(value[key]) is bool for key in ('groupRunAbsent','archiveRunAbsent','observationErrors')))
    original(value['retirement'],retire_nonce,imported,metadata,import_raw,intent_raw,receiver_bundle_id=receiver_bundle_id)
    stamp(value['clockBefore'],value['retirement']['clockAfter']);stamp(value['clockAfter'],value['clockBefore'])
    if previous is not None:
        observation(previous,previous['requestId'],retire_nonce,imported,metadata,import_raw,intent_raw,receiver_bundle_id=receiver_bundle_id)
        need(value['requestId']!=previous['requestId'] and same(value['retirement'],previous['retirement']));stamp(value['clockBefore'],previous['clockAfter'])
    return value


def qualified(value):
    need(value['retirement']['complete'] and value['retirement']['readersClosed'] and value['groupRunAbsent'] and value['archiveRunAbsent'] and not value['observationErrors'])
    return value


def quiet(observations,hosts,run):
    need(type(observations) is list and type(hosts) is list and len(observations)==len(hosts)==3)
    need(len({value['requestId'] for value in observations})==3)
    previous=None
    for value,host in zip(observations,hosts):
        qualified(value);need(value['runId']==run);exact(host,{'before','after'});host_clock(host['before']);host_clock(host['after'],host['before'])
        need(host['after']['monotonicMs']-host['before']['monotonicMs']<5500 and host['after']['epochMs']-host['before']['epochMs']<5500)
        if previous is not None:
            need(same(value['retirement'],previous[0]['retirement']) and value['requestId']!=previous[0]['requestId'])
            stamp(value['clockBefore'],previous[0]['clockAfter']);host_clock(host['before'],previous[1]['after'])
        previous=(value,host)
    native_a,native_b=observations[0]['clockAfter'],observations[-1]['clockBefore'];host_a,host_b=hosts[0]['after'],hosts[-1]['before']
    native_ms=native_b['monotonicMs']-native_a['monotonicMs'];host_ms=host_b['monotonicMs']-host_a['monotonicMs']
    need(min(native_ms,host_ms,native_b['epochMs']-native_a['epochMs'],host_b['epochMs']-host_a['epochMs'])>=3000)
    return dict(snapshotShareFilesQuietVersion=1,runId=run,nativeMilliseconds=native_ms,hostMilliseconds=host_ms,
        requestIds=[value['requestId'] for value in observations],historicalOriginalsOnly=True,sourceJournalRetirementRequired=True,wholeFeatureRequired=True)
