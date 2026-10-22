"""Join independent native Create originals to primary pixels and output bytes.

Action metadata admits only actual owned identities. Every public state field
is derived again from the original native scene, never from an input receipt.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy

from adapters.native_feature_observation import exact,need
from adapters.script_feature.history import same
from feature_journeys.contract import result
from feature_journeys.scenarios import SCENARIOS
from ios.adapters import create_state
from ios.adapters.create_actions import semantic_map
from ios.adapters.create_product_state import project
from ios.adapters.graphics_history import follow_native

VERSION=1


def compose(run,binding,sequence,before,after,baseline,*,owned_ids,marker=None,voxel_baseline=None,sample=None,export=None,files=None):
    """Inputs are completed source/owner originals, validated by their owners."""
    first,last=before['clockJoin'],after['clockJoin'];left,right=before['originals']['createAfter'],after['originals']['createBefore']
    pid=int(binding['processIdentity'])
    need(before['ticket']==after['ticket'] and before['index']<after['index']
        and first['hostAfterMonotonic']<=last['hostBeforeMonotonic']
        and first['hostAfterEpochMs']<=last['hostBeforeEpochMs']
        and first['nativeAfter']['capturedEpochMs']<=last['nativeBefore']['capturedEpochMs']
        and first['nativeBefore']['processId']==last['nativeAfter']['processId']==pid
        and same(first['nativeBefore']['lifecycle'],last['nativeAfter']['lifecycle']))
    follow_native(first['nativeAfter'],last['nativeBefore'])
    start,end=first['hostBeforeEpochMs'],last['hostAfterEpochMs'];mono=last['hostAfterMonotonic']-first['hostBeforeMonotonic']
    need(0<=end-start<1500 and 0<=mono<1.5 and abs(end-start-mono*1000)<=250)
    for frame in (before,after):
        phase=frame['phaseAfter'];need(phase['active'] and phase['activations'][-1]['ticket']==before['ticket'])
    stimulus=before['phaseBefore']['activations'][-1]['stimulus']
    evidence=[row['evidence'] for row in SCENARIOS['create']['steps'] if row['verb']==stimulus['verb'] and same(row['inputs'],stimulus['inputs'])]
    required=[] if stimulus['verb'] in ('baseline','cleanup') else (evidence[0] if evidence else None)
    need(required is not None and all(same(row,required) for row in evidence)
        and (not ({'image','changed'} & set(required)) or sample is not None) and ('file' not in required or export is not None))
    need(before['phaseBefore']['instance']==after['phaseAfter']['instance']
        and same(before['phaseBefore']['activations'],after['phaseAfter']['activations']))
    create_state.validate(right,dict(schemaVersion=1,commandId=right['requestId'],action=create_state.ACTION,runId=run),pid,previous=left)
    ignored=deepcopy(owned_ids);resources=[]
    if marker is not None:
        exact(marker,{'marker','manager','code','sourceUrl','iosCreateMarkerAdmissionVersion'})
        need(marker['iosCreateMarkerAdmissionVersion']==1);ignored.append(marker['marker']['id'])
        scripts=after['originals']['domain']['source']['scriptOriginal']['source']
        members=scripts['membership'];need(members['complete'] and any(same(row,marker['manager']) for row in members['managers']))
        engines=[row for row in scripts['engines'] if row['required']['instance']==marker['manager']['instance']]
        need(len(engines)==1 and same(engines[0]['code'],marker['code']) and engines[0]['url']==marker['sourceUrl'])
        for packet in (left,right):
            rows=[row for row in packet['source']['entities'] if row['id']==marker['marker']['id']]
            need(len(rows)==1 and all(same(rows[0][key],marker['marker'][key]) for key in ('id','type','name','sourceUrl','userData','hostType','position','rotation','dimensions')))
        resources+=['entity:create-marker','script:create-marker','file:create-marker-input']
    need(same(semantic_map(baseline),semantic_map(left,ignored)) and same(semantic_map(left),semantic_map(right)))
    measured=project(right,run,owned_ids,voxel_baseline=voxel_baseline)
    need(same(measured,project(left,run,owned_ids,voxel_baseline=voxel_baseline)))
    resources+=['entity:'+role for role in measured['objects']]
    if measured['editor']:resources.append('panel:create')
    if measured['picker']:resources.append('panel:create-picker')
    if files is not None:
        need(files['source']['exists']);resources.append('file:create-import-json')
        if files['source']['files'][1]['exists']:resources.append('file:create-export-json')
    artifacts=[]
    if sample is not None:
        exact(sample,{'state','frameOwnership','measurement'})
        frame=sample['state'];originals=frame['originals'];observed=sample['measurement']
        need(frame['qualificationInputs']['changed']==('changed' in required))
        need(frame['phase']=='qualified' and frame['ticket']==before['ticket'] and marker is not None
            and same(observed,frame['qualification']) and same(observed['state'],measured)
            and first['nativeAfter']['capturedEpochMs']<=frame['clockJoin']['nativeBefore']['capturedEpochMs']
            <=frame['clockJoin']['nativeAfter']['capturedEpochMs']<=last['nativeBefore']['capturedEpochMs']
            and first['hostAfterMonotonic']<=frame['clockJoin']['hostBeforeMonotonic']
            <=frame['clockJoin']['hostAfterMonotonic']<=last['hostBeforeMonotonic']
            and all(same(semantic_map(left),semantic_map(originals[key])) for key in ('createBefore','createAfter'))
            and same(observed['lifecycle'],last['nativeAfter']['lifecycle']))
        follow_native(first['nativeAfter'],frame['clockJoin']['nativeBefore']);follow_native(frame['clockJoin']['nativeAfter'],last['nativeBefore'])
        need(same(frame['frameOwnership'],sample['frameOwnership']))
        artifacts.append(dict(kind='image',name=sample['frameOwnership']['name'],sequence=sequence,capturedEpochMs=observed['capturedEpochMs'],
            ticket=before['ticket'],source='world-render-target'))
    if export is not None:
        exact(export,{'name','measurement','model','current'})
        need(files is not None and same(files,export['current']['packet']) and export['measurement']['entityId'] in owned_ids
            and same(semantic_map(export['model']),semantic_map(right))
            and first['nativeAfter']['capturedEpochMs']<=files['clockBefore']['epochMs']<=files['clockAfter']['epochMs']<=last['nativeBefore']['capturedEpochMs'])
        artifacts.append(dict(kind='file',name=export['name'],sequence=sequence,capturedEpochMs=start,ticket=before['ticket']))
    value=dict(schemaVersion=1,contractVersion=16,runId=run,sequence=sequence,capturedEpochMs=start,state=measured,
        artifacts=artifacts,resources=sorted(resources),lifecycle=deepcopy(last['nativeAfter']['lifecycle']))
    result('feature.create.observe',value)
    return value
