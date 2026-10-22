"""Per-eye browser pixels joined to original document, renderer and retirement sources."""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import math
from pathlib import PurePosixPath
import time
from adapters.native_feature_observation import exact,need
from adapters.normal_feature_state import context
from adapters.pico4.browser_stereo import original_name,VERSION as OWNER_VERSION
from adapters.pico4.browser_stereo_source import validate as frame_packet
from adapters.graphics_journey.originals import record as image_record
from adapters.graphics_journey.samples import retirement
from adapters.owned_world_render import WorldRenderOwner
from adapters.script_journey.history import unpack,canonical
from navigation_observation import viewpoint_urls
from .contract import identifier,json_document,result
from .evidence import image_observation,rectangle
from .stereo_navigation_evidence import eye_regions,stereo_source_identity,advance_sources

VERSION=1
PROFILE='pico-stereo-tablet-web-v1'
LIMIT=65536


def policy(value):
    exact(value,{'source','profile','sceneUrl','eyes'})
    need(value['source']=='world-render-target' and value['profile']==PROFILE)
    viewpoint_urls(value['sceneUrl']);need('?' not in value['sceneUrl']);exact(value['eyes'],{'left','right'})
    for eye in value['eyes'].values():
        exact(eye,{'marker','subject'})
        for roi in eye.values():rectangle(roi,(8192,8192))
        a,b=eye['marker'],eye['subject']
        need(a[2]-a[0]>=128 and a[3]-a[1]>=32
            and not (max(a[0],b[0])<min(a[2],b[2]) and max(a[1],b[1])<min(a[3],b[3])))
    return value


def archive(metadata,raw,run,ticket,external_policy,*,role='primary'):
    policy(external_policy)
    return archive_sources(metadata,raw,run,ticket,external_policy['sceneUrl'],role=role)


def archive_sources(metadata,raw,run,ticket,scene_url,*,role='primary'):
    """Validate retained original provenance independently of pixel ROI policy."""
    identifier(run);identifier(ticket);viewpoint_urls(scene_url)
    need(type(metadata) is bytes and 0<len(metadata)<=LIMIT and role in ('primary','actor'))
    body=json_document(metadata)
    exact(body,{'picoBrowserStereoOwnerVersion','runId','binding','role','artifactRoot','journalId','scope','payload'})
    need(type(body['picoBrowserStereoOwnerVersion']) is int and body['picoBrowserStereoOwnerVersion']==OWNER_VERSION
        and body['runId']==run and body['role']==role and type(body['artifactRoot']) is str
        and 0<len(body['artifactRoot'])<=4096 and PurePosixPath(body['artifactRoot']).is_absolute())
    identifier(body['journalId']);context(body['binding']);rows=unpack(body['payload']);need(len(rows)==1);state=rows[0]
    exact(state,{'ticket','phase','before','captureIntent','frame','image','memory','files','owner','proof'})
    need(state['ticket']==ticket and state['phase']=='complete' and type(state['frame']) is dict)
    frame=state['frame'];facts=frame_packet(frame,raw,run,body['binding'],scene_url)
    exact(body['scope'],{'fixtureUrl','foreignFixtureUrl','ownerToken','scriptUrl'})
    need(all(frame[key]==value for key,value in body['scope'].items()) and state['before']==frame['before'])
    WorldRenderOwner.acquisition(state['captureIntent']);need(state['captureIntent']['commandId']==frame['capture']['requestId'])
    image=state['image'];image_record(image)
    need(image['phase']=='saved' and image['kind']=='image' and image['runId']==run and image['ticket']==ticket
        and image['role']==role and image['stage']==0 and image['binding']==body['binding'] and image['capture']==frame['capture']
        and image['sha256']==hashlib.sha256(raw).hexdigest())
    proof=state['proof'];retirement(proof,proof.get('owner'),int(body['binding']['processIdentity'].split(':',1)[0]),body['binding'],role)
    need(proof['memory']['instance']==frame['capture']['instance'] and proof['memory']['capturedEpochMs']>=frame['capture']['capturedEpochMs']
        and proof['owner']['capture']==state['captureIntent'] and proof['owner']==state['owner'] and proof['memory']==state['memory']
        and state['files']==dict(remove=proof['files']['removed'],inspect=proof['files']['absent']))
    return body,state,facts


def source_identity(frame,facts):
    value=stereo_source_identity(frame)
    value.update(earliestEpochMs=facts['earliestEpochMs'],latestEpochMs=facts['latestEpochMs'],
        browserInstance=frame['browserBefore']['instance'],runtimeInstance=frame['runtimeBefore']['instance'],
        javaInstance=frame['runtimeBefore']['source']['java']['instance'],scriptsInstance=frame['scriptsBefore']['instance'],
        httpInstance=frame['httpBefore']['instance'])
    for suffix in ('Before','After'):
        for family in ('browser','runtime'):
            packet=frame[family+suffix];value['cursors'][family+suffix]=packet['sequence'];value['requests'][family+suffix]=packet['commandId']
        value['cursors']['java'+suffix]=frame['runtime'+suffix]['source']['java']['sequence']
        value['cursors']['scripts'+suffix]=frame['scripts'+suffix]['sampleSequence']
    return value


def advance(previous,current):
    need(all(previous[k]==current[k] for k in ('stereoBrowserSubjectVersion','runId','binding','role','stage','policySha256',
        'browserInstance','runtimeInstance','javaInstance','scriptsInstance','httpInstance')))
    advance_sources(previous,current)
    need(all(current['cursors'][family+'Before']>previous['cursors'][family+'After']
        for family in ('browser','runtime','java','scripts')))


def observation(raw,metadata,run,ticket,fixture_url,external_policy,sample,*,previous=None,changed=False,role='primary',monotonic=time.monotonic):
    started=last=monotonic();need(type(changed) is bool)
    def budget():
        nonlocal last
        now=monotonic();need(type(now) in (int,float) and math.isfinite(now) and 0<=started<=last<=now and now-started<5);last=now
    budget();result('feature.tablet-web.observe',sample);need(sample['runId']==run)
    body,state,facts=archive(metadata,raw,run,ticket,external_policy,role=role);frame=state['frame']
    need(frame['fixtureUrl']==fixture_url);eye_regions(frame['capture']['source'],external_policy)
    artifacts={row['kind']:row for row in sample['artifacts']};need('image' in artifacts and 'file' in artifacts)
    for kind,name in (('image',state['image']['name']),('file',original_name(run,role,body['journalId']))):
        row=artifacts[kind];need(row['name']==name and row['ticket']==ticket and row['capturedEpochMs']==frame['capture']['capturedEpochMs'])
    need(sample['state']==facts['state'] and sample['capturedEpochMs']==facts['earliestEpochMs']
        and sample['lifecycle']==frame['nativeBefore']['lifecycle'])
    subject=dict(stereoBrowserSubjectVersion=VERSION,runId=run,ticket=ticket,binding=deepcopy(body['binding']),role=role,stage=0,
        state=deepcopy(facts['state']),policySha256=hashlib.sha256(canonical(external_policy)).hexdigest(),eyes={},**source_identity(frame,facts))
    if changed:
        need(type(previous) is dict and previous['ticket']!=ticket and subject['earliestEpochMs']>=previous['latestEpochMs']
            and subject['latestEpochMs']-previous['earliestEpochMs']<=45000);advance(previous,subject)
    measured={}
    for eye in ('left','right'):
        budget();selection=external_policy['eyes'][eye];old=None if not changed else previous['eyes'][eye]
        value,image=image_observation(raw,run,ticket,dict(source='world-render-target',**selection),old,changed)
        subject['eyes'][eye]=image;measured[eye]=value
    budget()
    return dict(stereoBrowserEvidenceVersion=VERSION,sha256=hashlib.sha256(raw).hexdigest(),
        metadataSha256=hashlib.sha256(metadata).hexdigest(),eyes=measured,frameIndex=facts['frameIndex'],
        executionSequence=facts['executionSequence']),subject
