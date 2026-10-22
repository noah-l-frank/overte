"""Independent two-eye Navigation pixels from original source/retirement journal.

The trusted external policy selects original pixel regions in each native eye.
No crop/resize is published, desired location is accepted or source is retimed.
The existing generic marker/subject verifier measures each eye independently.
"""
# Copyright 2026 Overte contributors.
# SPDX-License-Identifier: Apache-2.0
from copy import deepcopy
import hashlib
import math
from pathlib import PurePosixPath
import time
from adapters.native_feature_observation import exact,integer,need
from adapters.normal_feature_state import context
from adapters.navigation_arrival import stereo_frame
from adapters.graphics_journey.originals import record as image_record
from adapters.graphics_journey.samples import retirement
from adapters.owned_world_render import WorldRenderOwner
from adapters.script_journey.history import unpack,canonical
from navigation_observation import viewpoint_urls
from .contract import identifier,json_document,result
from .evidence import image_observation,rectangle
from adapters.script_journey.measurements import fixture_scope

VERSION=1
PROFILE='pico-stereo-navigation-v1'
LIMIT=65536


def policy(value):
    exact(value,{'source','profile','sceneUrl','eyes'})
    need(value['source']=='world-render-target' and value['profile']==PROFILE)
    viewpoint_urls(value['sceneUrl']);need('?' not in value['sceneUrl'])
    exact(value['eyes'],{'left','right'})
    for eye in value['eyes'].values():
        exact(eye,{'marker','subject'})
        for roi in eye.values():rectangle(roi,(8192,8192))
        a,b=eye['marker'],eye['subject']
        need(a[2]-a[0]>=128 and a[3]-a[1]>=32
             and not (max(a[0],b[0])<min(a[2],b[2]) and max(a[1],b[1])<min(a[3],b[3])))
    return value


def original_name(run,role,journal_id):
    identifier(run);identifier(journal_id);need(role in ('primary','actor'))
    return 'navigation-'+run+'-'+role+'-'+journal_id+'.native.json'


def archive(metadata,raw,run,ticket,external_policy,*,role='primary'):
    """Historical original journal; never opens the recorded absolute path."""
    policy(external_policy);identifier(run);identifier(ticket)
    need(type(metadata) is bytes and 0<len(metadata)<=LIMIT and role in ('primary','actor'))
    body=json_document(metadata)
    exact(body,{'navigationStereoOwnerVersion','runId','binding','role','artifactRoot','journalId','payload'})
    need(type(body['navigationStereoOwnerVersion']) is int and body['navigationStereoOwnerVersion']==2
         and body['runId']==run and body['role']==role and type(body['artifactRoot']) is str
         and 0<len(body['artifactRoot'])<=4096 and PurePosixPath(body['artifactRoot']).is_absolute())
    identifier(body['journalId']);context(body['binding']);rows=unpack(body['payload']);need(len(rows)==1);state=rows[0]
    exact(state,{'ticket','phase','before','captureIntent','frame','image','memory','files','owner','proof'})
    need(state['ticket']==ticket and state['phase']=='complete' and type(state['frame']) is dict)
    frame=state['frame'];need(type(frame.get('navigationStereoSourceVersion')) is int and frame['navigationStereoSourceVersion']==2)
    facts=stereo_frame(frame,raw,run,body['binding'],external_policy['sceneUrl'])
    need(state['before']==frame['before']);WorldRenderOwner.acquisition(state['captureIntent'])
    need(state['captureIntent']['commandId']==frame['capture']['requestId'])
    image=state['image'];image_record(image)
    need(image['phase']=='saved' and image['kind']=='image' and image['runId']==run and image['ticket']==ticket
         and image['role']==role and image['stage']==0 and image['binding']==body['binding']
         and image['capture']==frame['capture'] and image['sha256']==hashlib.sha256(raw).hexdigest())
    proof=state['proof'];need(type(proof) is dict)
    retirement(proof,proof.get('owner'),int(body['binding']['processIdentity'].split(':',1)[0]),body['binding'],role)
    need(proof['memory']['instance']==frame['capture']['instance'] and proof['memory']['capturedEpochMs']>=frame['capture']['capturedEpochMs']
         and proof['owner']['capture']==state['captureIntent'] and proof['owner']==state['owner'] and proof['memory']==state['memory']
         and state['files']==dict(remove=proof['files']['removed'],inspect=proof['files']['absent']))
    return body,state,facts


def eye_regions(source,external_policy):
    """Both trusted regions must lie inside their actual original eye viewport."""
    width,height=source['targetExtent']
    for index,name in enumerate(('left','right')):
        eye=source['stereo']['eyes'][index];need(eye['eye']==name)
        x,y,w,h=eye['targetViewport'];bounds=[x,height-y-h,x+w,height-y]
        for roi in external_policy['eyes'][name].values():
            rectangle(roi,(width,height))
            need(bounds[0]<=roi[0]<roi[2]<=bounds[2] and bounds[1]<=roi[1]<roi[3]<=bounds[3])


def clocks(frame):
    start=min(frame['before']['probe']['sampleEpochMs'],frame['before']['probe']['nativeMotion']['sampleEpochMs'],
              frame['before']['probe']['render']['lastFrameEpochMs'],frame['before']['subject']['requestedEpochMs'],
              frame['capture']['source']['recordedEpochMs'],frame['nativeBefore']['requestedEpochMs'])
    end=frame['nativeAfter']['capturedEpochMs'];need(0<=end-start<=1500)
    return start,end


def source_identity(frame):
    """Original source clocks/cursors only; no pixel policy or feature verdict."""
    need(frame['navigationStereoSourceVersion']==2)
    source=frame['capture']['source'];capture=frame['capture'];before,after=frame['before'],frame['after']
    cameras=source['renderTrace']['cameraBatches'];start,end=clocks(frame)
    return dict(captureInstance=capture['instance'],nativeInstance=before['subject']['instance'],
        uiInstance=frame['uiBefore']['instance'],uiGeneration=frame['uiBefore']['generation'],
        earliestEpochMs=start,latestEpochMs=end,frameId=source['renderTrace']['frameId'],
        frameIndex=source['stereo']['frameIndex'],executionSequence=source['stereo']['executionSequence'],
        cursors=dict(nativeBefore=frame['nativeBefore']['sequence'],nativeAfter=frame['nativeAfter']['sequence'],
            uiBefore=frame['uiBefore']['sourceSequence'],uiAfter=frame['uiAfter']['sourceSequence'],capture=capture['sequence'],
            acquisition=source['acquisitionSequence'],execution=source['stereo']['executionSequence'],
            submission=source['presentation']['submissionSequence'],cameraFirst=min(c['sequence'] for c in cameras),
            cameraLast=max(c['sequence'] for c in cameras),subjectBefore=before['subject']['sequence'],
            subjectAfter=after['subject']['sequence'],probeBefore=before['probe']['sampleSequence'],probeAfter=after['probe']['sampleSequence']),
        requests=dict(nativeBefore=frame['nativeBefore']['requestId'],nativeAfter=frame['nativeAfter']['requestId'],
            uiBefore=frame['uiBefore']['commandId'],uiAfter=frame['uiAfter']['commandId'],
            subjectBefore=before['subject']['requestId'],subjectAfter=after['subject']['requestId'],capture=capture['requestId']))


def advance_sources(previous,current):
    need(all(previous[k]==current[k] for k in ('captureInstance','nativeInstance','uiInstance','uiGeneration'))
         and current['earliestEpochMs']>=previous['earliestEpochMs'] and current['latestEpochMs']>=previous['latestEpochMs'])
    a,b=previous['cursors'],current['cursors']
    need(all(b[k]>a[k] for k in ('capture','acquisition','execution','submission'))
         and b['nativeBefore']>a['nativeAfter'] and b['uiBefore']>a['uiAfter'] and b['subjectBefore']>a['subjectAfter']
         and b['probeBefore']>a['probeAfter'] and b['cameraFirst']>a['cameraLast'])


def advance(previous,current):
    need(all(previous[k]==current[k] for k in ('stereoNavigationSubjectVersion','runId','binding','role','stage','policySha256')))
    advance_sources(previous,current)


def observation(raw,metadata,run,ticket,fixture_url,external_policy,sample,*,previous=None,changed=False,role='primary',monotonic=time.monotonic):
    """Bind original source and measured per-eye pixels to the current sample."""
    started=last=monotonic();need(type(changed) is bool and callable(monotonic))
    def budget():
        nonlocal last
        now=monotonic();need(type(now) in (int,float) and math.isfinite(now) and 0<=started<=last<=now and now-started<5);last=now
    budget();fixture_scope(run,fixture_url)
    result('feature.world-navigation.observe',sample);need(sample['runId']==run)
    body,state,facts=archive(metadata,raw,run,ticket,external_policy,role=role);frame=state['frame'];source=frame['capture']['source']
    eye_regions(source,external_policy);start,end=clocks(frame)
    artifacts={row['kind']:row for row in sample['artifacts']};need('image' in artifacts and 'file' in artifacts)
    for kind,name in (('image',state['image']['name']),('file',original_name(run,role,body['journalId']))):
        row=artifacts[kind];need(row['name']==name and row['ticket']==ticket and row['capturedEpochMs']==frame['capture']['capturedEpochMs'])
    need(sample['state']['location']==facts['location'] and sample['capturedEpochMs']==start
         and sample['lifecycle']==frame['nativeBefore']['lifecycle'])
    subject=dict(stereoNavigationSubjectVersion=VERSION,runId=run,ticket=ticket,binding=deepcopy(body['binding']),role=role,stage=0,
        location=facts['location'],policySha256=hashlib.sha256(canonical(external_policy)).hexdigest(),eyes={},**source_identity(frame))
    if changed:
        need(type(previous) is dict and previous['location']!=subject['location'] and previous['ticket']!=ticket
             and subject['earliestEpochMs']>=previous['latestEpochMs'] and subject['latestEpochMs']-previous['earliestEpochMs']<=45000)
        advance(previous,subject)
    measured={}
    for eye in ('left','right'):
        budget();selection=external_policy['eyes'][eye]
        old=None if not changed else previous['eyes'][eye]
        value,image=image_observation(raw,run,ticket,dict(source='world-render-target',**selection),old,changed)
        subject['eyes'][eye]=image;measured[eye]=value
    budget()
    return dict(stereoNavigationEvidenceVersion=VERSION,sha256=hashlib.sha256(raw).hexdigest(),
        metadataSha256=hashlib.sha256(metadata).hexdigest(),eyes=measured,location=facts['location'],
        frameIndex=facts['frameIndex'],executionSequence=facts['executionSequence']),subject
